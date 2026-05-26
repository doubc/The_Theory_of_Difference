"""
engine/unsealing_mechanism.py — 解封机制 (Unsealing Mechanism)

Phase 2 P1 组件 #1

职责：当结构达到前主体态时，自动检测并触发分级解封。

理论依据：
- 《象界》第八章：前主体态是低语义层所能达到的最充分完成形态
- 解封不是外部操作，而是结构自发达到密度后的自然结果
- 解封是分级过程：Level 1（边界开放）→ Level 2（内部耦合）→ Level 3（全通道开放）

设计文档：docs/phase2_unsealing_return_flow_design.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import torch

from engine.pre_subjectivity_convergence import ConvergenceResult


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
    ):
        """
        Args:
            l1_coupling_threshold: Level 1 最小耦合强度
            l1_stability_threshold: Level 1 最小稳定性
            l2_coupling_threshold: Level 2 最小耦合强度
            l2_stability_threshold: Level 2 最小稳定性
            l3_coupling_threshold: Level 3 最小耦合强度
            l3_stability_threshold: Level 3 最小稳定性
        """
        self.l1_coupling_threshold = l1_coupling_threshold
        self.l1_stability_threshold = l1_stability_threshold
        self.l2_coupling_threshold = l2_coupling_threshold
        self.l2_stability_threshold = l2_stability_threshold
        self.l3_coupling_threshold = l3_coupling_threshold
        self.l3_stability_threshold = l3_stability_threshold

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
