"""
叙事递归追踪器 — NarrativeRecursionTracker

对应机制：循环 + 锁定（设计书 P1 #4）

核心能力：
1. 追踪同一 Zone 的叙事如何随时间演化
2. 检测"叙事锁定"：市场叙事不再更新，结构进入稳态
3. 计算叙事漂移率（narrative_drift）作为质量维度
4. 叙事聚类：相似叙事自动归并

数据流：
  compile_full() → Structure.narrative_context
  → track_narrative_evolution() → NarrativeEvolutionChain
  → compute_drift_rate() → float (0~1)
  → detect_narrative_lock() → LockReport
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

import numpy as np


# ─── 数据结构 ──────────────────────────────────────────────

@dataclass
class NarrativeSnapshot:
    """某一时刻的叙事快照"""
    text: str
    timestamp: datetime
    zone_key: str
    structure_id: str
    phase_tendency: str = ""
    conservation_flux: float = 0.0
    cycle_count: int = 0


@dataclass
class NarrativeEvolutionStep:
    """叙事演化链中的一步"""
    from_snapshot: NarrativeSnapshot
    to_snapshot: NarrativeSnapshot
    similarity: float  # 0~1, 文本相似度
    drift_delta: float  # 叙事漂移量
    phase_changed: bool  # 阶段是否变化
    flux_direction: str  # 通量方向: positive/negative/neutral
    days_between: int = 0


@dataclass
class NarrativeEvolutionChain:
    """一个 Zone 的完整叙事演化链"""
    zone_key: str
    steps: list[NarrativeEvolutionStep] = field(default_factory=list)
    snapshots: list[NarrativeSnapshot] = field(default_factory=list)

    @property
    def total_drift(self) -> float:
        """总漂移量"""
        if not self.steps:
            return 0.0
        return sum(s.drift_delta for s in self.steps)

    @property
    def avg_similarity(self) -> float:
        """平均相似度"""
        if not self.steps:
            return 1.0
        return np.mean([s.similarity for s in self.steps])

    @property
    def latest_narrative(self) -> str:
        if self.snapshots:
            return self.snapshots[-1].text
        return ""

    @property
    def is_locked(self) -> bool:
        """叙事是否已锁定（最近3步相似度 > 0.9）"""
        if len(self.steps) < 3:
            return False
        recent = self.steps[-3:]
        return all(s.similarity > 0.9 for s in recent)


@dataclass
class LockReport:
    """叙事锁定报告"""
    zone_key: str
    is_locked: bool
    lock_strength: float  # 0~1
    locked_narrative: str
    lock_duration_days: int
    lock_start_index: int  # 从第几步开始锁定
    recommendation: str  # 建议操作


@dataclass
class DriftReport:
    """叙事漂移报告"""
    zone_key: str
    drift_rate: float  # 每步平均漂移
    drift_trend: str  # accelerating/decelerating/stable
    high_drift_steps: list[int]  # 高漂移步骤索引
    narrative_diversity: float  # 叙事多样性 (0~1)


# ─── 追踪器 ──────────────────────────────────────────────

class NarrativeRecursionTracker:
    """
    叙事递归追踪器

    追踪每个 Zone 的叙事如何随时间演化，检测锁定和漂移。
    """

    def __init__(self, similarity_threshold: float = 0.7,
                 lock_threshold: float = 0.9,
                 lock_min_steps: int = 3):
        self.similarity_threshold = similarity_threshold
        self.lock_threshold = lock_threshold
        self.lock_min_steps = lock_min_steps
        self._chains: dict[str, NarrativeEvolutionChain] = {}

    # ─── 核心接口 ──────────────────────────────────────────

    def track_evolution(
        self,
        structures: list,
        symbol: str = "",
        prev_snapshots: dict[str, list[NarrativeSnapshot]] | None = None,
    ) -> dict[str, NarrativeEvolutionChain]:
        """
        从编译结果追踪叙事演化。

        Args:
            structures: compile_full() 输出的 Structure 列表
            symbol: 品种代码
            prev_snapshots: 前一次的叙事快照 {zone_key: [NarrativeSnapshot]}

        Returns:
            {zone_key: NarrativeEvolutionChain}
        """
        # 按 zone_key 分组当前结构
        current_by_zone: dict[str, list] = {}
        for st in structures:
            zone_key = f"{symbol}:{st.zone.price_center:.0f}"
            current_by_zone.setdefault(zone_key, []).append(st)

        chains = {}

        for zone_key, structs in current_by_zone.items():
            # 取该 Zone 最新的结构
            latest = max(structs, key=lambda s: s.t_end or datetime.min)

            snapshot = NarrativeSnapshot(
                text=latest.narrative_context or "",
                timestamp=latest.t_end or datetime.now(),
                zone_key=zone_key,
                structure_id=f"{symbol}_S{len(structs)}",
                phase_tendency=latest.motion.phase_tendency if latest.motion else "",
                conservation_flux=latest.motion.conservation_flux if latest.motion else 0.0,
                cycle_count=latest.cycle_count,
            )

            # 获取前次快照
            prev = prev_snapshots.get(zone_key, []) if prev_snapshots else []

            chain = self._build_chain(zone_key, prev, snapshot)
            chains[zone_key] = chain
            self._chains[zone_key] = chain

        return chains

    def detect_all_locks(self) -> list[LockReport]:
        """检测所有 Zone 的叙事锁定"""
        reports = []
        for zone_key, chain in self._chains.items():
            report = self.detect_lock(chain)
            if report.is_locked:
                reports.append(report)
        return reports

    def compute_all_drift_rates(self) -> dict[str, DriftReport]:
        """计算所有 Zone 的叙事漂移率"""
        reports = {}
        for zone_key, chain in self._chains.items():
            reports[zone_key] = self.compute_drift_rate(chain)
        return reports

    # ─── 分析接口 ──────────────────────────────────────────

    def _build_chain(
        self,
        zone_key: str,
        prev_snapshots: list[NarrativeSnapshot],
        current: NarrativeSnapshot,
    ) -> NarrativeEvolutionChain:
        """从历史快照和当前快照构建演化链"""
        chain = NarrativeEvolutionChain(zone_key=zone_key)

        # 所有快照按时间排序
        all_snapshots = sorted(prev_snapshots + [current], key=lambda s: s.timestamp)
        chain.snapshots = all_snapshots

        # 构建步骤
        for i in range(1, len(all_snapshots)):
            prev = all_snapshots[i - 1]
            curr = all_snapshots[i]

            similarity = self._text_similarity(prev.text, curr.text)
            drift_delta = 1.0 - similarity
            phase_changed = prev.phase_tendency != curr.phase_tendency
            flux_dir = self._flux_direction(prev.conservation_flux, curr.conservation_flux)
            days = max((curr.timestamp - prev.timestamp).days, 0)

            step = NarrativeEvolutionStep(
                from_snapshot=prev,
                to_snapshot=curr,
                similarity=similarity,
                drift_delta=drift_delta,
                phase_changed=phase_changed,
                flux_direction=flux_dir,
                days_between=days,
            )
            chain.steps.append(step)

        return chain

    def detect_lock(self, chain: NarrativeEvolutionChain) -> LockReport:
        """检测叙事锁定"""
        if len(chain.steps) < self.lock_min_steps:
            return LockReport(
                zone_key=chain.zone_key,
                is_locked=False,
                lock_strength=0.0,
                locked_narrative=chain.latest_narrative,
                lock_duration_days=0,
                lock_start_index=-1,
                recommendation="数据不足，无法判断",
            )

        # 从后往前找锁定起点
        lock_start = len(chain.steps)
        for i in range(len(chain.steps) - 1, -1, -1):
            if chain.steps[i].similarity >= self.lock_threshold:
                lock_start = i
            else:
                break

        lock_length = len(chain.steps) - lock_start
        is_locked = lock_length >= self.lock_min_steps

        if is_locked:
            lock_days = sum(
                chain.steps[i].days_between
                for i in range(lock_start, len(chain.steps))
            )
            strength = min(1.0, lock_length / 5.0)  # 5步以上锁定 = 满强度
            rec = self._lock_recommendation(chain, lock_start)
        else:
            lock_days = 0
            strength = 0.0
            rec = "叙事仍在演化中"

        return LockReport(
            zone_key=chain.zone_key,
            is_locked=is_locked,
            lock_strength=strength,
            locked_narrative=chain.latest_narrative,
            lock_duration_days=lock_days,
            lock_start_index=lock_start,
            recommendation=rec,
        )

    def compute_drift_rate(self, chain: NarrativeEvolutionChain) -> DriftReport:
        """计算叙事漂移率"""
        if not chain.steps:
            return DriftReport(
                zone_key=chain.zone_key,
                drift_rate=0.0,
                drift_trend="stable",
                high_drift_steps=[],
                narrative_diversity=0.0,
            )

        drifts = [s.drift_delta for s in chain.steps]
        avg_drift = np.mean(drifts)

        # 漂移趋势
        if len(drifts) >= 3:
            first_half = np.mean(drifts[:len(drifts) // 2])
            second_half = np.mean(drifts[len(drifts) // 2:])
            if second_half > first_half * 1.3:
                trend = "accelerating"
            elif second_half < first_half * 0.7:
                trend = "decelerating"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # 高漂移步骤（> 平均值 + 1 标准差）
        threshold = avg_drift + np.std(drifts) if len(drifts) > 1 else avg_drift
        high_drift = [i for i, d in enumerate(drifts) if d > threshold]

        # 叙事多样性：唯一叙事文本占比
        unique_texts = set(s.text for s in chain.snapshots if s.text)
        diversity = len(unique_texts) / max(len(chain.snapshots), 1)

        return DriftReport(
            zone_key=chain.zone_key,
            drift_rate=avg_drift,
            drift_trend=trend,
            high_drift_steps=high_drift,
            narrative_diversity=diversity,
        )

    # ─── 工具方法 ──────────────────────────────────────────

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """文本相似度（SequenceMatcher）"""
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _flux_direction(prev_flux: float, curr_flux: float) -> str:
        """通量变化方向"""
        delta = curr_flux - prev_flux
        if abs(delta) < 0.01:
            return "neutral"
        return "positive" if delta > 0 else "negative"

    @staticmethod
    def _lock_recommendation(chain: NarrativeEvolutionChain, lock_start: int) -> str:
        """锁定时的建议"""
        latest = chain.snapshots[-1] if chain.snapshots else None
        if latest and latest.phase_tendency in ("accumulation", "compression"):
            return "叙事锁定 + 蓄势阶段 → 关注突破方向"
        elif latest and latest.phase_tendency in ("release", "trending"):
            return "叙事锁定 + 释放阶段 → 趋势可能延续"
        return "叙事已锁定 → 关注结构是否进入新阶段"

    # ─── 序列化 ──────────────────────────────────────────

    def to_dict(self) -> dict:
        """导出为可序列化字典"""
        result = {}
        for zone_key, chain in self._chains.items():
            result[zone_key] = {
                "zone_key": zone_key,
                "total_drift": chain.total_drift,
                "avg_similarity": chain.avg_similarity,
                "is_locked": chain.is_locked,
                "latest_narrative": chain.latest_narrative,
                "step_count": len(chain.steps),
                "snapshot_count": len(chain.snapshots),
                "steps": [
                    {
                        "from": s.from_snapshot.text[:50],
                        "to": s.to_snapshot.text[:50],
                        "similarity": round(s.similarity, 3),
                        "drift": round(s.drift_delta, 3),
                        "phase_changed": s.phase_changed,
                        "flux_dir": s.flux_direction,
                        "days": s.days_between,
                    }
                    for s in chain.steps
                ],
            }
        return result

    @classmethod
    def from_store(cls, store, symbol: str = "") -> NarrativeRecursionTracker:
        """从 GraphStore 加载历史叙事数据构建追踪器"""
        tracker = cls()
        narratives = store.load_all_narratives()

        if symbol:
            narratives = [n for n in narratives if n.get("symbol") == symbol or n.get("product") == symbol]

        # 按 zone_key 分组
        by_zone: dict[str, list[NarrativeSnapshot]] = {}
        for n in narratives:
            zk = n.get("zone_key", "")
            if not zk:
                continue
            ts_str = n.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
            except (ValueError, TypeError):
                ts = datetime.now()

            snapshot = NarrativeSnapshot(
                text=n.get("text", ""),
                timestamp=ts,
                zone_key=zk,
                structure_id=n.get("narrative_id", ""),
            )
            by_zone.setdefault(zk, []).append(snapshot)

        # 构建演化链
        for zk, snapshots in by_zone.items():
            snapshots.sort(key=lambda s: s.timestamp)
            chain = NarrativeEvolutionChain(zone_key=zk, snapshots=snapshots)
            for i in range(1, len(snapshots)):
                prev = snapshots[i - 1]
                curr = snapshots[i]
                sim = cls._text_similarity(prev.text, curr.text)
                step = NarrativeEvolutionStep(
                    from_snapshot=prev,
                    to_snapshot=curr,
                    similarity=sim,
                    drift_delta=1.0 - sim,
                    phase_changed=False,
                    flux_direction="neutral",
                    days_between=max((curr.timestamp - prev.timestamp).days, 0),
                )
                chain.steps.append(step)
            tracker._chains[zk] = chain

        return tracker
