"""
engine/six_threshold_detector.py — 六阈值同步检测器 (SixThresholdDetector)

Phase 2 P1 组件 #1

职责：同步检测六个结构阈值，判定是否跨越"象界"进入前主体态。

理论依据：
- 《Appearing Before Appearing》§3.1-3.6：六重结构阈值
- 《象界》八章生成链：六个转化方向
- 核心要求：六阈值必须同时收敛（AND关系，不是OR）
  → 任一阈值未达标，则未跨越象界
  → 全部达标，进入前主体态判定

六个阈值：
3.1 界面调节度 — 封装边界的活跃交换比例
3.2 自维持稳健性 — 扰动后重建成功率
3.3 保持深度 — 偏置场的递归调用层数
3.4 复制保真度 — 跨实例模式重建的相似度
3.5 选择压力 — 组织变体的延续概率差异
3.6 功能分化指数 — 内部组件贡献不对称度（Gini系数）
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ThresholdStatus:
    """单个阈值的状态"""
    threshold_id: str       # "3.1" ~ "3.6"
    name: str               # 阈值名称
    value: float = 0.0      # 当前值
    threshold: float = 0.0  # 目标阈值
    is_met: bool = False    # 是否达标

    def __repr__(self):
        status = "✓" if self.is_met else "✗"
        return f"[{status} {self.threshold_id}] {self.name}: {self.value:.4f} (threshold={self.threshold:.4f})"


@dataclass
class SixThresholdResult:
    """六阈值检测结果"""
    all_met: bool = False                   # 是否全部达标
    threshold_statuses: List[ThresholdStatus] = field(default_factory=list)
    n_met: int = 0                          # 达标的阈值数
    bottleneck: Optional[str] = None        # 最低得分的阈值（瓶颈）
    timestamp: int = 0                      # 检测时间戳

    def __repr__(self):
        status = "ALL_MET" if self.all_met else f"{self.n_met}/6"
        details = " | ".join(str(s) for s in self.threshold_statuses)
        return f"SixThreshold[{status}] {details}"


class SixThresholdDetector:
    """六阈值同步检测器

    同步检测六个结构阈值，判定是否跨越"象界"进入前主体态。

    判定逻辑：六阈值必须同时收敛（AND关系）
    - 任一阈值未达标 → 未跨越象界
    - 全部达标 → 进入前主体态判定

    阈值参数（τ₁~τ₆）可通过构造函数配置，默认值基于理论推导。
    """

    # 默认阈值参数
    DEFAULT_THRESHOLDS = {
        '3.1_interface_regulation': 0.3,    # 界面调节度阈值
        '3.2_self_sustaining': 0.5,         # 自维持稳健性阈值
        '3.3_retention_depth': 2.0,         # 保持深度阈值（层数）
        '3.4_replication_fidelity': 0.6,    # 复制保真度阈值
        '3.5_selection_pressure': 0.2,      # 选择压力阈值
        '3.6_functional_differentiation': 0.3,  # 功能分化指数阈值（Gini）
    }

    THRESHOLD_NAMES = {
        '3.1_interface_regulation': '界面调节度',
        '3.2_self_sustaining': '自维持稳健性',
        '3.3_retention_depth': '保持深度',
        '3.4_replication_fidelity': '复制保真度',
        '3.5_selection_pressure': '选择压力',
        '3.6_functional_differentiation': '功能分化指数',
    }

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        """
        Args:
            thresholds: 自定义阈值参数，覆盖默认值
        """
        self._thresholds = dict(self.DEFAULT_THRESHOLDS)
        if thresholds:
            self._thresholds.update(thresholds)

        # 历史记录
        self._history: List[SixThresholdResult] = []
        self._step_count: int = 0

    def detect(self,
               # 3.1 界面调节度
               active_exchanges: int = 0,
               total_boundary_edges: int = 1,
               # 3.2 自维持稳健性
               rebuild_success_count: int = 0,
               perturbation_count: int = 1,
               # 3.3 保持深度
               bias_recursion_depth: float = 0.0,
               # 3.4 复制保真度
               replicated_pattern: Optional[torch.Tensor] = None,
               original_pattern: Optional[torch.Tensor] = None,
               # 3.5 选择压力
               variant_continuation_probs: Optional[Dict[str, float]] = None,
               # 3.6 功能分化指数
               component_contributions: Optional[Dict[str, float]] = None,
               # 时间戳
               timestamp: Optional[int] = None,
               ) -> SixThresholdResult:
        """执行六阈值同步检测

        每个参数对应一个阈值的计算输入。
        未提供的参数将使用默认值（通常是0，即未达标）。

        Args:
            active_exchanges: 活跃交换的边界边数
            total_boundary_edges: 总边界边数
            rebuild_success_count: 扰动后成功重建次数
            perturbation_count: 总扰动次数
            bias_recursion_depth: 偏置场最大递归深度
            replicated_pattern: 复制后的模式
            original_pattern: 原始模式
            variant_continuation_probs: 各变体的延续概率
            component_contributions: 各组件的贡献度
            timestamp: 时间戳

        Returns:
            SixThresholdResult 检测结果
        """
        if timestamp is not None:
            self._step_count = timestamp
        else:
            self._step_count += 1

        statuses = []

        # ── 3.1 界面调节度 ──
        # 计算方式: active_exchanges / total_boundary_edges
        tau_31 = self._thresholds['3.1_interface_regulation']
        if total_boundary_edges > 0:
            interface_regulation = active_exchanges / total_boundary_edges
        else:
            interface_regulation = 0.0
        met_31 = interface_regulation > tau_31
        statuses.append(ThresholdStatus(
            threshold_id='3.1', name=self.THRESHOLD_NAMES['3.1_interface_regulation'],
            value=interface_regulation, threshold=tau_31, is_met=met_31,
        ))

        # ── 3.2 自维持稳健性 ──
        # 计算方式: rebuild_success_count / perturbation_count
        tau_32 = self._thresholds['3.2_self_sustaining']
        if perturbation_count > 0:
            self_sustaining = rebuild_success_count / perturbation_count
        else:
            self_sustaining = 0.0
        met_32 = self_sustaining > tau_32
        statuses.append(ThresholdStatus(
            threshold_id='3.2', name=self.THRESHOLD_NAMES['3.2_self_sustaining'],
            value=self_sustaining, threshold=tau_32, is_met=met_32,
        ))

        # ── 3.3 保持深度 ──
        # 计算方式: max(recursion_depth for bias in memory)
        tau_33 = self._thresholds['3.3_retention_depth']
        retention_depth = bias_recursion_depth
        met_33 = retention_depth > tau_33
        statuses.append(ThresholdStatus(
            threshold_id='3.3', name=self.THRESHOLD_NAMES['3.3_retention_depth'],
            value=retention_depth, threshold=tau_33, is_met=met_33,
        ))

        # ── 3.4 复制保真度 ──
        # 计算方式: structural_similarity(original, replicated)
        tau_34 = self._thresholds['3.4_replication_fidelity']
        if replicated_pattern is not None and original_pattern is not None:
            replication_fidelity = self._compute_structural_similarity(
                original_pattern, replicated_pattern)
        else:
            replication_fidelity = 0.0
        met_34 = replication_fidelity > tau_34
        statuses.append(ThresholdStatus(
            threshold_id='3.4', name=self.THRESHOLD_NAMES['3.4_replication_fidelity'],
            value=replication_fidelity, threshold=tau_34, is_met=met_34,
        ))

        # ── 3.5 选择压力 ──
        # 计算方式: max_prob - min_prob（归一化）
        tau_35 = self._thresholds['3.5_selection_pressure']
        if variant_continuation_probs and len(variant_continuation_probs) >= 2:
            probs = list(variant_continuation_probs.values())
            selection_pressure = max(probs) - min(probs)
        else:
            selection_pressure = 0.0
        met_35 = selection_pressure > tau_35
        statuses.append(ThresholdStatus(
            threshold_id='3.5', name=self.THRESHOLD_NAMES['3.5_selection_pressure'],
            value=selection_pressure, threshold=tau_35, is_met=met_35,
        ))

        # ── 3.6 功能分化指数 ──
        # 计算方式: GiniCoefficient(component_contributions)
        tau_36 = self._thresholds['3.6_functional_differentiation']
        if component_contributions and len(component_contributions) >= 2:
            contributions = list(component_contributions.values())
            gini = self._gini_coefficient(contributions)
        else:
            gini = 0.0
        met_36 = gini > tau_36
        statuses.append(ThresholdStatus(
            threshold_id='3.6', name=self.THRESHOLD_NAMES['3.6_functional_differentiation'],
            value=gini, threshold=tau_36, is_met=met_36,
        ))

        # ── 综合判定 ──
        n_met = sum(1 for s in statuses if s.is_met)
        all_met = n_met == 6

        # 找到瓶颈（得分与阈值差距最大的）
        bottleneck = None
        if not all_met:
            max_gap = -float('inf')
            for s in statuses:
                if not s.is_met:
                    gap = s.threshold - s.value
                    if gap > max_gap:
                        max_gap = gap
                        bottleneck = s.threshold_id

        result = SixThresholdResult(
            all_met=all_met,
            threshold_statuses=statuses,
            n_met=n_met,
            bottleneck=bottleneck,
            timestamp=self._step_count,
        )

        self._history.append(result)
        return result

    def _compute_structural_similarity(self, original: torch.Tensor,
                                        replicated: torch.Tensor) -> float:
        """计算结构相似性（余弦相似度的简化版）"""
        flat_orig = original.flatten().float()
        flat_rep = replicated.flatten().float()

        # 确保尺寸一致
        min_len = min(len(flat_orig), len(flat_rep))
        flat_orig = flat_orig[:min_len]
        flat_rep = flat_rep[:min_len]

        dot = (flat_orig * flat_rep).sum().item()
        norm_orig = (flat_orig ** 2).sum().item() ** 0.5
        norm_rep = (flat_rep ** 2).sum().item() ** 0.5

        if norm_orig < 1e-8 or norm_rep < 1e-8:
            return 0.0

        similarity = dot / (norm_orig * norm_rep)
        return max(0.0, min(1.0, similarity))

    def _gini_coefficient(self, values: List[float]) -> float:
        """计算基尼系数

        衡量分布的不均匀程度：
        - 0 = 完全均匀（所有组件贡献相同）
        - 1 = 极度不均匀（一个组件贡献全部）

        用于功能分化指数：贡献越不均匀，功能分化越明显。
        """
        if not values:
            return 0.0

        values = sorted(values)
        n = len(values)
        if n == 0:
            return 0.0

        total = sum(values)
        if total < 1e-10:
            return 0.0

        # 基尼系数公式
        numerator = sum((2 * i - n - 1) * v for i, v in enumerate(values, 1))
        gini = numerator / (n * total)

        return max(0.0, min(1.0, gini))

    @property
    def is_all_met(self) -> bool:
        """最近一次检测是否全部达标"""
        if not self._history:
            return False
        return self._history[-1].all_met

    @property
    def current_result(self) -> Optional[SixThresholdResult]:
        """最近一次检测结果"""
        if not self._history:
            return None
        return self._history[-1]

    def get_history_summary(self, last_n: int = 10) -> Dict:
        """获取最近 N 次检测的摘要"""
        recent = self._history[-last_n:] if self._history else []
        if not recent:
            return {'n_detections': 0}

        return {
            'n_detections': len(self._history),
            'n_recent': len(recent),
            'n_all_met': sum(1 for r in recent if r.all_met),
            'avg_n_met': float(np.mean([r.n_met for r in recent])),
            'latest_bottleneck': recent[-1].bottleneck,
            'all_met_count': sum(1 for r in self._history if r.all_met),
        }

    def reset(self):
        """重置检测器状态"""
        self._history.clear()
        self._step_count = 0
