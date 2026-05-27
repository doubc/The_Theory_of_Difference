"""
engine/unsealing_mechanism.py — 解封机制 (Unsealing Mechanism)

Phase 2 P1 组件 #1

职责：当结构达到前主体态时，自动检测并触发分级解封。

理论依据：
- 《象界》第八章：前主体态是低语义层所能达到的最充分完成形态
- 解封不是外部操作，而是结构自发达到密度后的自然结果
- 解封是分级过程：Level 1（边界开放）→ Level 2（内部耦合）→ Level 3（全通道开放）
- 《Appearing Before Appearing》§3.1：界面调节模式必须稳定（不是全有/全无）

设计文档：docs/phase2_unsealing_return_flow_design.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Deque
from collections import deque
import torch

from engine.pre_subjectivity_convergence import ConvergenceResult


# =============================================================================
# 界面交换记录 & 界面模式稳定性
# =============================================================================

@dataclass
class InterfaceExchangeRecord:
    """单次时间步的界面交换记录

    记录在当前时间步中，边界上各交换通道的吞吐量比例。
    模式向量归一化后表示各通道的相对活跃程度。
    """
    timestamp: int
    # 各交换通道的活跃比例（归一化后）: channel_name → [0, 1]
    channel_pattern: Dict[str, float] = field(default_factory=dict)
    # 总活跃交换数（归一化前）
    total_active: int = 0
    # 总边界边数
    total_edges: int = 0

    @property
    def openness(self) -> float:
        """总体开放度 = total_active / total_edges"""
        if self.total_edges == 0:
            return 0.0
        return self.total_active / self.total_edges

    def __repr__(self) -> str:
        n_channels = len(self.channel_pattern)
        return (
            f"InterfaceExchange[ts={self.timestamp}, "
            f"openness={self.openness:.3f}, channels={n_channels}]"
        )


@dataclass
class InterfacePatternStability:
    """界面模式稳定性追踪器

    追踪界面交换模式在连续时间步之间的一致性。

    理论依据（ABA §3.1）：
        界面不仅是"开放"或"封闭"，而是具有选择性介导的模式。
        此模式本身必须在连续交互中保持稳定，才能构成真正的界面。

    计算方式：
        1. 维护最近 W 个时间步的交换模式向量
        2. 计算相邻时间步模式向量的余弦相似度
        3. 稳定性 = 所有相邻相似度的平均值
        4. 稳定性 ≥ threshold → 界面模式稳定

    这解决了缺口1：Level 1 不再是全有/全无，
    而是要求开放模式本身具有一致性。
    """
    window_size: int = 5
    stability_threshold: float = 0.7

    # 历史交换记录（滑动窗口）
    _records: Deque[InterfaceExchangeRecord] = field(
        default_factory=lambda: deque(maxlen=5)
    )
    # 历史稳定性分数
    _stability_history: List[float] = field(default_factory=list)

    def __post_init__(self):
        # 确保 deque 的 maxlen 与 window_size 一致
        if self._records.maxlen != self.window_size:
            self._records = deque(self._records, maxlen=self.window_size)

    def record(self, exchange: InterfaceExchangeRecord) -> float:
        """记录一次交换，返回当前模式稳定性分数。

        Args:
            exchange: 当前时间步的交换记录

        Returns:
            当前稳定性分数 [0, 1]，记录不足时返回 0.0
        """
        self._records.append(exchange)
        stability = self._compute_stability()
        self._stability_history.append(stability)
        return stability

    def _compute_stability(self) -> float:
        """计算当前窗口内的模式稳定性。

        计算相邻时间步模式向量的余弦相似度，取平均。
        记录数 < 2 时返回 0.0（无法计算变化）。
        """
        records = list(self._records)
        if len(records) < 2:
            return 0.0

        similarities = []
        for i in range(1, len(records)):
            prev = records[i - 1].channel_pattern
            curr = records[i].channel_pattern
            sim = self._pattern_cosine_sim(prev, curr)
            similarities.append(sim)

        if not similarities:
            return 0.0
        return sum(similarities) / len(similarities)

    @staticmethod
    def _pattern_cosine_sim(
        a: Dict[str, float],
        b: Dict[str, float],
    ) -> float:
        """计算两个模式字典的余弦相似度。

        对两个字典的并集键构建向量，缺失键补 0。
        返回值 ∈ [0, 1]（因为所有值 ≥ 0）。n        """
        if not a and not b:
            return 1.0  # 两个空模式视为完全相同
        if not a or not b:
            return 0.0  # 一个空一个非空 → 完全不同

        all_keys = set(a.keys()) | set(b.keys())
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for k in all_keys:
            va = a.get(k, 0.0)
            vb = b.get(k, 0.0)
            dot += va * vb
            norm_a += va * va
            norm_b += vb * vb

        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0

        return dot / (norm_a ** 0.5 * norm_b ** 0.5)

    @property
    def is_stable(self) -> bool:
        """当前界面模式是否稳定"""
        if not self._stability_history:
            return False
        return self._stability_history[-1] >= self.stability_threshold

    @property
    def current_stability(self) -> float:
        """当前稳定性分数"""
        if not self._stability_history:
            return 0.0
        return self._stability_history[-1]

    @property
    def is_ready(self) -> bool:
        """是否有足够记录进行评估（至少 2 条）"""
        return len(self._records) >= 2

    @property
    def n_records(self) -> int:
        return len(self._records)

    @property
    def dominant_channels(self) -> List[str]:
        """返回最近记录中平均活跃度最高的通道（降序）"""
        if not self._records:
            return []
        channel_totals: Dict[str, float] = {}
        for rec in self._records:
            for ch, val in rec.channel_pattern.items():
                channel_totals[ch] = channel_totals.get(ch, 0.0) + val
        n = len(self._records)
        avg = {ch: total / n for ch, total in channel_totals.items()}
        return sorted(avg, key=avg.get, reverse=True)

    def get_stability_trend(self, last_n: Optional[int] = None) -> List[float]:
        """获取稳定性历史趋势"""
        if last_n is None:
            return list(self._stability_history)
        return list(self._stability_history[-last_n:])

    def reset(self):
        """重置所有状态"""
        self._records.clear()
        self._stability_history.clear()

    def __repr__(self) -> str:
        return (
            f"InterfacePatternStability["
            f"records={len(self._records)}/{self.window_size}, "
            f"stability={self.current_stability:.3f}, "
            f"stable={self.is_stable}]"
        )


# =============================================================================
# 解封事件
# =============================================================================

@dataclass
class UnsealingEvent:
    """解封事件"""
    structure_id: int
    timestamp: int
    convergence_report: ConvergenceResult
    unsealing_level: int  # 0=无, 1=边界开放, 2=内部耦合, 3=全通道开放
    previous_level: int   # 上一级等级
    reason: str
    high_semantic_capacity: float  # 可承载的高语义容量 [0, 1]

    def __repr__(self) -> str:
        direction = (
            f"升级 {self.previous_level}→{self.unsealing_level}"
            if self.unsealing_level > self.previous_level
            else f"降级 {self.previous_level}→{self.unsealing_level}"
        )
        return (
            f"UnsealingEvent[structure={self.structure_id}, "
            f"level={direction}, capacity={self.high_semantic_capacity:.3f}, "
            f"ts={self.timestamp}]"
        )


# =============================================================================
# 解封机制
# =============================================================================

class UnsealingMechanism:
    """
    解封机制 — 当结构达到前主体态时，自动触发解封。

    解封不是单次事件，而是分级过程：
      Level 0: 未达前主体态 — 无解封，结构仅低语义运行
      Level 1: 边界界面开放 — 允许外部高语义扰动进入边界层
      Level 2: 内部耦合开放 — 允许高语义内容在结构内部各机制间流动
      Level 3: 全通道开放 — 结构完全进入可承载高语义的状态

    每个等级都有独立的触发条件和回退机制。

    理论边界：
      - 解封是结构自发的，UnsealingMechanism 的角色是"检测"而非"执行"
      - 解封等级取决于耦合强度和稳定性，不是外部指令
      - 降级是自动的：当结构不再满足当前等级条件时，自动回退
    """

    # 解封等级名称（用于日志和报告）
    LEVEL_NAMES = {
        0: "封闭",
        1: "边界开放",
        2: "内部耦合",
        3: "全通道开放",
    }

    def __init__(
        self,
        # Level 1 条件
        l1_coupling_threshold: float = 0.30,
        l1_stability_threshold: float = 0.50,
        # Level 2 条件
        l2_coupling_threshold: float = 0.50,
        l2_stability_threshold: float = 0.70,
        # Level 3 条件
        l3_coupling_threshold: float = 0.70,
        l3_stability_threshold: float = 0.85,
        # 界面模式稳定性参数
        interface_stability_window: int = 5,
        interface_stability_threshold: float = 0.7,
    ):
        """
        Args:
            l1_coupling_threshold: Level 1 最小耦合强度
            l1_stability_threshold: Level 1 最小稳定性
            l2_coupling_threshold: Level 2 最小耦合强度
            l2_stability_threshold: Level 2 最小稳定性
            l3_coupling_threshold: Level 3 最小耦合强度
            l3_stability_threshold: Level 3 最小稳定性
            interface_stability_window: 界面模式稳定性滑动窗口大小
            interface_stability_threshold: 界面模式稳定性阈值
        """
        self.l1_coupling_threshold = l1_coupling_threshold
        self.l1_stability_threshold = l1_stability_threshold
        self.l2_coupling_threshold = l2_coupling_threshold
        self.l2_stability_threshold = l2_stability_threshold
        self.l3_coupling_threshold = l3_coupling_threshold
        self.l3_stability_threshold = l3_stability_threshold

        # 界面模式稳定性追踪器
        self._interface_stability = InterfacePatternStability(
            window_size=interface_stability_window,
            stability_threshold=interface_stability_threshold,
        )
        # 各结构的界面稳定性追踪器: structure_id → InterfacePatternStability
        self._structure_interface_stability: Dict[int, InterfacePatternStability] = {}

        # 当前解封状态: structure_id → level
        self._unsealing_levels: Dict[int, int] = {}
        # 解封事件历史
        self._unsealing_events: List[UnsealingEvent] = []

    def evaluate(
        self,
        structure_id: int,
        convergence_result: ConvergenceResult,
        timestamp: int,
    ) -> Optional[UnsealingEvent]:
        """
        评估结构的解封等级是否发生变化。

        逻辑：
          1. 根据收敛结果计算应达到的目标等级
          2. 如果目标等级 != 当前等级 → 生成解封事件
          3. 如果目标等级 == 当前等级 → 无变化，返回 None

        Args:
            structure_id: 结构 ID
            convergence_result: 前主体态收束判定结果
            timestamp: 当前时间戳

        Returns:
            UnsealingEvent 如果解封等级发生变化，否则 None
        """
        current_level = self._unsealing_levels.get(structure_id, 0)
        target_level = self._compute_target_level(convergence_result)

        if target_level == current_level:
            return None

        previous_level = current_level
        capacity = self._compute_capacity(convergence_result)
        reason = self._reason(previous_level, target_level)

        event = UnsealingEvent(
            structure_id=structure_id,
            timestamp=timestamp,
            convergence_report=convergence_result,
            unsealing_level=target_level,
            previous_level=previous_level,
            reason=reason,
            high_semantic_capacity=capacity,
        )

        self._unsealing_levels[structure_id] = target_level
        self._unsealing_events.append(event)
        return event

    def record_interface_exchange(
        self,
        structure_id: int,
        timestamp: int,
        channel_pattern: Dict[str, float],
        total_active: int = 0,
        total_edges: int = 0,
    ) -> float:
        """记录结构的一次界面交换，返回当前模式稳定性。

        每个时间步调用一次，追踪该结构的界面交换模式。
        当模式稳定性达到阈值时，认为该结构的界面调节已模式化。

        Args:
            structure_id: 结构 ID
            timestamp: 当前时间戳
            channel_pattern: 各交换通道的活跃比例（归一化后）
            total_active: 总活跃交换数
            total_edges: 总边界边数

        Returns:
            当前界面模式稳定性分数 [0, 1]
        """
        if structure_id not in self._structure_interface_stability:
            self._structure_interface_stability[structure_id] = InterfacePatternStability(
                window_size=self._interface_stability.window_size,
                stability_threshold=self._interface_stability.stability_threshold,
            )

        tracker = self._structure_interface_stability[structure_id]
        record = InterfaceExchangeRecord(
            timestamp=timestamp,
            channel_pattern=channel_pattern,
            total_active=total_active,
            total_edges=total_edges,
        )
        return tracker.record(record)

    def get_interface_stability(self, structure_id: int) -> Optional[InterfacePatternStability]:
        """获取指定结构的界面模式稳定性追踪器"""
        return self._structure_interface_stability.get(structure_id)

    def is_interface_stable(self, structure_id: int) -> bool:
        """指定结构的界面模式是否已稳定"""
        tracker = self._structure_interface_stability.get(structure_id)
        if tracker is None:
            return False
        return tracker.is_stable

    def _compute_target_level(self, result: ConvergenceResult) -> int:
        """根据收束结果计算应达到的解封等级"""
        # 如果未通过所有条件，直接返回 Level 0
        if not result.all_conditions_met:
            return 0

        min_coupling = result.min_coupling
        stability = result.stability_score

        # 从高到低检查（优先匹配高等级）
        if (min_coupling >= self.l3_coupling_threshold
                and stability >= self.l3_stability_threshold):
            return 3
        elif (min_coupling >= self.l2_coupling_threshold
                and stability >= self.l2_stability_threshold):
            return 2
        elif (min_coupling >= self.l1_coupling_threshold
                and stability >= self.l1_stability_threshold):
            return 1

        return 0

    def _compute_capacity(self, result: ConvergenceResult) -> float:
        """
        计算高语义承载容量 [0, 1]。

        容量 = 耦合强度 × 稳定性 × 六阈值满足度
        只有当所有条件都满足时，容量才 > 0。
        """
        if not result.all_conditions_met:
            return 0.0

        six_score = 1.0 if result.six_thresholds_met else 0.0
        capacity = min(1.0, (
            result.min_coupling
            * result.stability_score
            * six_score
        ))
        return max(0.0, capacity)

    def _reason(self, from_level: int, to_level: int) -> str:
        """生成解封原因说明"""
        from_name = self.LEVEL_NAMES.get(from_level, f"Level {from_level}")
        to_name = self.LEVEL_NAMES.get(to_level, f"Level {to_level}")

        if to_level > from_level:
            return f"解封升级: {from_name} → {to_name}"
        else:
            return f"解封降级: {from_name} → {to_name}"

    # ─── 查询接口 ───

    def get_current_level(self, structure_id: int) -> int:
        """获取结构的当前解封等级"""
        return self._unsealing_levels.get(structure_id, 0)

    def get_level_name(self, structure_id: int) -> str:
        """获取结构的当前解封等级名称"""
        level = self.get_current_level(structure_id)
        return self.LEVEL_NAMES.get(level, f"Level {level}")

    def get_event_history(
        self, structure_id: Optional[int] = None
    ) -> List[UnsealingEvent]:
        """获取解封事件历史"""
        if structure_id is not None:
            return [
                e for e in self._unsealing_events
                if e.structure_id == structure_id
            ]
        return list(self._unsealing_events)

    def get_all_structures_status(self) -> Dict[int, Dict]:
        """获取所有结构的解封状态摘要

        优化：先聚合事件计数，避免 O(n_structures × n_events) 的嵌套扫描。
        """
        # 预聚合：structure_id → event count [O(n_events)]
        event_counts: Dict[int, int] = {}
        for e in self._unsealing_events:
            event_counts[e.structure_id] = event_counts.get(e.structure_id, 0) + 1

        result = {}
        for sid, level in self._unsealing_levels.items():
            result[sid] = {
                'level': level,
                'level_name': self.LEVEL_NAMES.get(level, f"Level {level}"),
                'event_count': event_counts.get(sid, 0),
            }
        return result

    def get_structures_by_level(self) -> Dict[int, List[int]]:
        """按解封等级分组返回结构 ID 列表

        Returns:
            {level: [structure_id, ...], ...}
            例如: {0: [1, 3], 1: [2], 3: [5]}
        """
        grouped: Dict[int, List[int]] = {i: [] for i in range(4)}
        for sid, level in self._unsealing_levels.items():
            grouped[level].append(sid)
        # 过滤空列表
        return {k: v for k, v in grouped.items() if v}

    def __repr__(self) -> str:
        n_structures = len(self._unsealing_levels)
        n_events = len(self._unsealing_events)
        if n_structures == 0:
            return "UnsealingMechanism[empty]"
        levels = self._unsealing_levels
        avg_level = sum(levels.values()) / n_structures
        return (
            f"UnsealingMechanism[structures={n_structures}, "
            f"events={n_events}, avg_level={avg_level:.2f}]"
        )

    def reset(self):
        """重置所有状态"""
        self._unsealing_levels.clear()
        self._unsealing_events.clear()
        self._interface_stability.reset()
        for tracker in self._structure_interface_stability.values():
            tracker.reset()
        self._structure_interface_stability.clear()
