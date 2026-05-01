"""
反身性闭环检测器 — ReflexivityDetector

对应机制：自指（设计书 P1 #5）

核心能力：
1. 检测规则 → 结构 → 失效 的反身性闭环
2. 追踪同一结构模板的历史有效性衰减
3. 自动降级衰减中的模板（A层 → B层）
4. 生成反身性报告

反身性闭环定义：
  Rule → identifies → Structure → (evolves_to)* → Structure' → invalidates → Rule

这意味着：规则识别了某种结构，但市场演化后该结构导致规则失效——
这正是 Soros 反身性理论在价格结构中的体现。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import numpy as np


# ─── 数据结构 ──────────────────────────────────────────────

@dataclass
class RuleMatchRecord:
    """规则匹配记录"""
    rule_id: str
    structure_id: str
    match_time: datetime
    confidence: float  # 匹配置信度
    outcome: str = ""  # 后验结果: success/failure/pending
    outcome_return: float = 0.0  # 后验收益率


@dataclass
class InvalidationEvent:
    """规则失效事件"""
    rule_id: str
    structure_id: str  # 导致失效的结构
    invalidation_time: datetime
    reason: str
    severity: float  # 0~1, 失效严重程度


@dataclass
class ReflexivityLoop:
    """反身性闭环"""
    rule_id: str
    matched_structure: str  # 规则最初匹配的结构
    invalidating_structure: str  # 导致失效的结构
    evolution_length: int  # 演化链长度
    loop_duration_days: int  # 闭环持续天数
    invalidation_count: int  # 该规则被失效的次数
    template_effectiveness: float  # 模板当前有效性 (0~1)


@dataclass
class TemplateDecayReport:
    """模板衰减报告"""
    rule_id: str
    total_matches: int
    success_count: int
    failure_count: int
    pending_count: int
    success_rate: float
    decay_rate: float  # 有效性衰减速率
    current_tier: str  # 当前层级 A/B/C/D
    recommended_tier: str  # 建议层级
    should_downgrade: bool
    recent_effectiveness: list[float]  # 最近N次的有效性序列
    decay_trend: str  # accelerating/decelerating/stable


@dataclass
class ReflexivityReport:
    """反身性分析总报告"""
    timestamp: datetime
    total_rules: int
    active_loops: list[ReflexivityLoop]
    decay_reports: list[TemplateDecayReport]
    systemic_reflexivity: float  # 系统级反身性指标 (0~1)
    high_risk_rules: list[str]  # 高风险规则 ID
    recommendations: list[str]


# ─── 检测器 ──────────────────────────────────────────────

class ReflexivityDetector:
    """
    反身性闭环检测器

    检测规则有效性衰减和反身性闭环，支持自动降级。
    """

    def __init__(
        self,
        decay_window: int = 20,  # 衰减计算窗口
        downgrade_threshold: float = 0.4,  # 降级阈值
        min_matches: int = 5,  # 最少匹配数才做衰减分析
    ):
        self.decay_window = decay_window
        self.downgrade_threshold = downgrade_threshold
        self.min_matches = min_matches
        self._match_records: list[RuleMatchRecord] = []
        self._invalidation_events: list[InvalidationEvent] = []

    # ─── 核心接口 ──────────────────────────────────────────

    def detect_loops(self, graph) -> list[ReflexivityLoop]:
        """
        从 StructureGraph 检测反身性闭环。

        Args:
            graph: StructureGraph 实例

        Returns:
            检测到的反身性闭环列表
        """
        loops = []
        raw_loops = graph.get_reflexivity_loops()

        for raw in raw_loops:
            rule_id = raw.get("rule", "")
            matched = raw.get("matched_structure", "")
            invalidating = raw.get("invalidating_structure", "")
            evo_len = raw.get("evolution_length", 0)

            # 计算该规则的总失效次数
            inv_count = sum(
                1 for e in self._invalidation_events
                if e.rule_id == rule_id
            )

            # 计算模板有效性
            effectiveness = self._compute_template_effectiveness(rule_id)

            # 计算闭环持续天数
            duration = self._compute_loop_duration(matched, invalidating)

            loop = ReflexivityLoop(
                rule_id=rule_id,
                matched_structure=matched,
                invalidating_structure=invalidating,
                evolution_length=evo_len,
                loop_duration_days=duration,
                invalidation_count=inv_count,
                template_effectiveness=effectiveness,
            )
            loops.append(loop)

        return loops

    def analyze_template_decay(self) -> list[TemplateDecayReport]:
        """
        分析所有规则模板的有效性衰减。

        Returns:
            每个规则的衰减报告
        """
        # 按规则分组匹配记录
        by_rule: dict[str, list[RuleMatchRecord]] = {}
        for record in self._match_records:
            by_rule.setdefault(record.rule_id, []).append(record)

        reports = []
        for rule_id, records in by_rule.items():
            report = self._analyze_single_rule(rule_id, records)
            reports.append(report)

        return reports

    def generate_report(self, graph) -> ReflexivityReport:
        """
        生成完整的反身性分析报告。

        Args:
            graph: StructureGraph 实例
        """
        loops = self.detect_loops(graph)
        decay_reports = self.analyze_template_decay()

        # 系统级反身性指标
        if decay_reports:
            systemic = np.mean([r.decay_rate for r in decay_reports])
        else:
            systemic = 0.0

        # 高风险规则
        high_risk = [
            r.rule_id for r in decay_reports
            if r.should_downgrade or r.decay_rate > 0.6
        ]

        # 建议
        recommendations = self._generate_recommendations(loops, decay_reports)

        return ReflexivityReport(
            timestamp=datetime.now(),
            total_rules=len(decay_reports),
            active_loops=loops,
            decay_reports=decay_reports,
            systemic_reflexivity=systemic,
            high_risk_rules=high_risk,
            recommendations=recommendations,
        )

    # ─── 记录接口 ──────────────────────────────────────────

    def record_match(
        self,
        rule_id: str,
        structure_id: str,
        confidence: float,
        match_time: datetime | None = None,
    ) -> None:
        """记录一次规则匹配"""
        record = RuleMatchRecord(
            rule_id=rule_id,
            structure_id=structure_id,
            match_time=match_time or datetime.now(),
            confidence=confidence,
        )
        self._match_records.append(record)

    def record_outcome(
        self,
        rule_id: str,
        structure_id: str,
        outcome: str,
        outcome_return: float = 0.0,
    ) -> None:
        """更新匹配记录的后验结果"""
        for record in reversed(self._match_records):
            if record.rule_id == rule_id and record.structure_id == structure_id:
                record.outcome = outcome
                record.outcome_return = outcome_return
                break

    def record_invalidation(
        self,
        rule_id: str,
        structure_id: str,
        reason: str,
        severity: float = 0.5,
    ) -> None:
        """记录一次规则失效事件"""
        event = InvalidationEvent(
            rule_id=rule_id,
            structure_id=structure_id,
            invalidation_time=datetime.now(),
            reason=reason,
            severity=severity,
        )
        self._invalidation_events.append(event)

    # ─── 自动降级 ──────────────────────────────────────────

    def auto_downgrade(self, graph) -> list[dict]:
        """
        自动降级衰减中的模板。

        Returns:
            降级操作列表 [{rule_id, from_tier, to_tier, reason}]
        """
        actions = []
        reports = self.analyze_template_decay()

        for report in reports:
            if report.should_downgrade:
                action = {
                    "rule_id": report.rule_id,
                    "from_tier": report.current_tier,
                    "to_tier": report.recommended_tier,
                    "reason": f"衰减率 {report.decay_rate:.2f} 超过阈值 {self.downgrade_threshold}",
                    "success_rate": report.success_rate,
                    "total_matches": report.total_matches,
                }
                actions.append(action)

                # 在图谱中标记
                rule_node = f"rule:{report.rule_id}"
                if rule_node in graph.G:
                    graph.G.nodes[rule_node]["auto_downgraded"] = True
                    graph.G.nodes[rule_node]["downgrade_time"] = datetime.now().isoformat()
                    graph.G.nodes[rule_node]["original_tier"] = report.current_tier

        return actions

    # ─── 内部分析 ──────────────────────────────────────────

    def _compute_template_effectiveness(self, rule_id: str) -> float:
        """计算模板当前有效性"""
        records = [
            r for r in self._match_records
            if r.rule_id == rule_id and r.outcome in ("success", "failure")
        ]
        if not records:
            return 0.5  # 无数据，返回中性值

        # 按时间排序，取最近 window 条
        records.sort(key=lambda r: r.match_time)
        recent = records[-self.decay_window:]

        successes = sum(1 for r in recent if r.outcome == "success")
        return successes / len(recent)

    def _compute_loop_duration(self, matched: str, invalidating: str) -> int:
        """计算闭环持续天数"""
        matched_time = None
        invalidating_time = None

        for r in self._match_records:
            if r.structure_id == matched:
                matched_time = r.match_time
                break

        for e in self._invalidation_events:
            if e.structure_id == invalidating:
                invalidating_time = e.invalidation_time
                break

        if matched_time and invalidating_time:
            return max((invalidating_time - matched_time).days, 0)
        return 0

    def _analyze_single_rule(
        self, rule_id: str, records: list[RuleMatchRecord]
    ) -> TemplateDecayReport:
        """分析单个规则的衰减"""
        total = len(records)
        success = sum(1 for r in records if r.outcome == "success")
        failure = sum(1 for r in records if r.outcome == "failure")
        pending = sum(1 for r in records if r.outcome == "pending")
        success_rate = success / max(total - pending, 1)

        # 按时间排序
        records.sort(key=lambda r: r.match_time)
        outcomes = [r for r in records if r.outcome in ("success", "failure")]

        # 衰减率：最近 window 的有效率 vs 早期有效率
        if len(outcomes) >= self.min_matches:
            half = len(outcomes) // 2
            early_rate = sum(1 for r in outcomes[:half] if r.outcome == "success") / max(half, 1)
            late_rate = sum(1 for r in outcomes[half:] if r.outcome == "success") / max(len(outcomes) - half, 1)
            decay_rate = max(0.0, early_rate - late_rate)
        else:
            decay_rate = 0.0

        # 最近有效性序列
        recent_eff = []
        window = outcomes[-self.decay_window:]
        for i in range(0, len(window), max(1, len(window) // 5)):
            chunk = window[i:i + max(1, len(window) // 5)]
            chunk_rate = sum(1 for r in chunk if r.outcome == "success") / len(chunk)
            recent_eff.append(round(chunk_rate, 3))

        # 衰减趋势
        if len(recent_eff) >= 3:
            first = np.mean(recent_eff[:len(recent_eff) // 2])
            second = np.mean(recent_eff[len(recent_eff) // 2:])
            if second < first * 0.8:
                trend = "accelerating"
            elif second > first * 1.1:
                trend = "recovering"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # 层级判定
        current_tier = self._rate_to_tier(success_rate)
        recommended_tier = self._rate_to_tier(success_rate - decay_rate)
        should_downgrade = (
            decay_rate > self.downgrade_threshold
            and current_tier != recommended_tier
            and total >= self.min_matches
        )

        return TemplateDecayReport(
            rule_id=rule_id,
            total_matches=total,
            success_count=success,
            failure_count=failure,
            pending_count=pending,
            success_rate=success_rate,
            decay_rate=decay_rate,
            current_tier=current_tier,
            recommended_tier=recommended_tier,
            should_downgrade=should_downgrade,
            recent_effectiveness=recent_eff,
            decay_trend=trend,
        )

    @staticmethod
    def _rate_to_tier(rate: float) -> str:
        """有效率 → 层级"""
        if rate >= 0.7:
            return "A"
        elif rate >= 0.5:
            return "B"
        elif rate >= 0.3:
            return "C"
        return "D"

    @staticmethod
    def _generate_recommendations(
        loops: list[ReflexivityLoop],
        decay_reports: list[TemplateDecayReport],
    ) -> list[str]:
        """生成建议"""
        recs = []

        high_decay = [r for r in decay_reports if r.decay_rate > 0.5]
        if high_decay:
            recs.append(
                f"⚠️ {len(high_decay)} 个规则有效性快速衰减，建议重新审视规则逻辑"
            )

        downgrades = [r for r in decay_reports if r.should_downgrade]
        if downgrades:
            rule_ids = [r.rule_id for r in downgrades[:3]]
            recs.append(
                f"🔽 {len(downgrades)} 个规则建议降级: {', '.join(rule_ids)}"
            )

        active_loops = [l for l in loops if l.template_effectiveness < 0.4]
        if active_loops:
            recs.append(
                f"🔄 {len(active_loops)} 个反身性闭环活跃，市场正在自我修正"
            )

        if not recs:
            recs.append("✅ 所有规则模板有效性稳定")

        return recs

    # ─── 序列化 ──────────────────────────────────────────

    def to_dict(self) -> dict:
        """导出为可序列化字典"""
        return {
            "match_records": len(self._match_records),
            "invalidation_events": len(self._invalidation_events),
            "rules_tracked": len(set(r.rule_id for r in self._match_records)),
            "decay_window": self.decay_window,
            "downgrade_threshold": self.downgrade_threshold,
        }

    def get_rule_history(self, rule_id: str) -> list[dict]:
        """获取某个规则的完整匹配历史"""
        records = [r for r in self._match_records if r.rule_id == rule_id]
        records.sort(key=lambda r: r.match_time)
        return [
            {
                "structure_id": r.structure_id,
                "match_time": r.match_time.isoformat(),
                "confidence": r.confidence,
                "outcome": r.outcome,
                "return": r.outcome_return,
            }
            for r in records
        ]
