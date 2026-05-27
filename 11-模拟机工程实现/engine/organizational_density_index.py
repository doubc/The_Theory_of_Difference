"""
engine/organizational_density_index.py — 组织密度指数 (OrganizationalDensityIndex)

Phase 2 P1 组件（新增）

职责：用连续值度量替代二值收束判定，建模"组织密度连续体"。

理论依据：
- 《Appearing Before Appearing》§4.4：前主体态不是固定阈值，而是一个范围
- "从结构到现象的过渡是组织密度连续增长，不是尖锐边界"
- 六阈值全部达标是前主体态的"地板"，不是"天花板"

核心概念：
组织密度指数（ODI）∈ [0, 1]，由六个子指数加权合成：
1. 阈值接近度（threshold_proximity）：各阈值距达标线的归一化距离
2. 耦合密度（coupling_density）：机制间耦合强度的整体水平
3. 稳定性裕度（stability_margin）：扰动后结构保持的连续评分
4. 防火墙纯度（firewall_purity）：结构描述中无高语义污染的度量
5. 时间一致性（temporal_consistency）：密度在时间轴上的稳定程度
6. 跨机制共振（cross_mechanism_resonance）：六机制的协同振荡强度

设计原则：
- ODI = 0：完全无序，无任何结构
- ODI = 0.5：六阈值全部刚好达标（前主体态地板）
- ODI → 1：组织高度致密化（可能涌现第七阈值的区域）
- ODI 不是"主体性度量"，纯结构性
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from engine.six_threshold_detector import SixThresholdDetector, SixThresholdResult


# ─── 默认权重 ───
# 六个子指数的权重，总和为 1.0
DEFAULT_SUBINDEX_WEIGHTS = {
    'threshold_proximity':  0.30,   # 最重要：六阈值达标是基础
    'coupling_density':     0.20,   # 机制间耦合
    'stability_margin':     0.20,   # 扰动下的结构保持
    'firewall_purity':      0.10,   # 语义防火墙（二元→连续）
    'temporal_consistency': 0.10,   # 时间维度稳定性
    'cross_mechanism_resonance': 0.10,  # 跨机制协同
}

# ─── 密度分区 ───
DENSE_ZONES = {
    'sparse':        (0.0, 0.3),    # 稀疏区：结构尚未成形
    'structuring':   (0.3, 0.5),    # 结构化区：部分阈值达标
    'pre_subjective':(0.5, 0.7),    # 前主体态区：六阈值达标
    'dense':         (0.7, 0.85),   # 致密区：高度组织化
    'ultra_dense':   (0.85, 1.0),   # 超致密区：可能涌现第七阈值
}


@dataclass
class SubIndexValues:
    """六个子指数的值"""
    threshold_proximity:  float = 0.0
    coupling_density:     float = 0.0
    stability_margin:     float = 0.0
    firewall_purity:      float = 1.0   # 默认为1（无违规）
    temporal_consistency: float = 0.0
    cross_mechanism_resonance: float = 0.0

    def as_array(self, weights: Dict[str, float]) -> Tuple[np.ndarray, np.ndarray]:
        """返回 (values, weights) 数组"""
        keys = list(weights.keys())
        vals = np.array([getattr(self, k) for k in keys])
        wts = np.array([weights[k] for k in keys])
        return vals, wts


@dataclass
class DensityIndexResult:
    """组织密度指数计算结果"""
    odi: float = 0.0                        # 组织密度指数 [0, 1]
    subindices: SubIndexValues = field(default_factory=SubIndexValues)
    zone: str = 'sparse'                    # 密度分区
    densification_rate: float = 0.0         # 密化速率（ΔODI/Δt）
    is_densifying: bool = False             # 是否正在致密化
    timestamp: int = 0

    @property
    def is_pre_subjective(self) -> bool:
        """是否达到前主体态地板（ODI ≥ 0.5）"""
        return self.odi >= 0.5

    @property
    def is_ultra_dense(self) -> bool:
        """是否进入超致密区（ODI ≥ 0.85）"""
        return self.odi >= 0.85

    @property
    def zone_label(self) -> str:
        """密度分区的中文标签"""
        labels = {
            'sparse': '稀疏区',
            'structuring': '结构化区',
            'pre_subjective': '前主体态区',
            'dense': '致密区',
            'ultra_dense': '超致密区',
        }
        return labels.get(self.zone, '未知')

    def __repr__(self):
        return (f"ODI[{self.odi:.4f}] zone={self.zone_label} "
                f"densifying={self.is_densifying} rate={self.densification_rate:+.4f}")


class OrganizationalDensityIndex:
    """组织密度指数计算器

    用连续值度量替代二值收束判定，建模"组织密度连续体"。

    使用方式：
        odi = OrganizationalDensityIndex()
        result = odi.compute(
            threshold_result=six_threshold_result,
            coupling_matrix=coupling_matrix,
            stability_score=st.0,
            field_names=field_names,
            timestamp=step,
        )
        print(result.odi, result.zone)
    """

    def __init__(self,
                 weights: Optional[Dict[str, float]] = None,
                 temporal_window: int = 5,
                 densification_threshold: float = 0.01):
        """
        Args:
            weights: 子指数权重（覆盖默认值）
            temporal_window: 时间一致性计算窗口
            densification_threshold: 密化速率阈值（超过此值认为正在致密化）
        """
        self._weights = dict(DEFAULT_SUBINDEX_WEIGHTS)
        if weights:
            self._weights.update(weights)
        # 归一化权重
        total = sum(self._weights.values())
        self._weights = {k: v / total for k, v in self._weights.items()}

        self._temporal_window = temporal_window
        self._densification_threshold = densification_threshold

        # 历史记录
        self._odi_history: List[float] = []
        self._result_history: List[DensityIndexResult] = []
        self._step_count: int = 0

    def compute(self,
                threshold_result: Optional[SixThresholdResult] = None,
                coupling_matrix: Optional[Dict[str, Dict[str, float]]] = None,
                stability_score: Optional[float] = None,
                field_names: Optional[List[str]] = None,
                timestamp: Optional[int] = None,
                ) -> DensityIndexResult:
        """计算组织密度指数

        每个参数对应一个子指数的计算输入。
        未提供的参数将使用默认值（通常是0）。

        Args:
            threshold_result: 六阈值检测结果
            coupling_matrix: 耦合矩阵 {mechanism: {mechanism: strength}}
            stability_score: 稳定性评分 [0, 1]
            field_names: 待检查语义防火墙的字段名列表
            timestamp: 时间戳

        Returns:
            DensityIndexResult 密度指数结果
        """
        if timestamp is not None:
            self._step_count = timestamp
        else:
            self._step_count += 1

        # ── 计算六个子指数 ──
        sub = SubIndexValues()

        # 1. 阈值接近度
        if threshold_result is not None:
            sub.threshold_proximity = self._compute_threshold_proximity(threshold_result)

        # 2. 耦合密度
        if coupling_matrix is not None:
            sub.coupling_density = self._compute_coupling_density(coupling_matrix)

        # 3. 稳定性裕度
        if stability_score is not None:
            sub.stability_margin = float(np.clip(stability_score, 0.0, 1.0))

        # 4. 防火墙纯度
        if field_names is not None:
            sub.firewall_purity = self._compute_firewall_purity(field_names)

        # 5. 时间一致性
        sub.temporal_consistency = self._compute_temporal_consistency()

        # 6. 跨机制共振
        if threshold_result is not None and coupling_matrix is not None:
            sub.cross_mechanism_resonance = self._compute_resonance(
                threshold_result, coupling_matrix)

        # ── 加权合成 ODI ──
        vals, wts = sub.as_array(self._weights)
        odi = float(np.dot(vals, wts))
        odi = float(np.clip(odi, 0.0, 1.0))

        # ── 确定密度分区 ──
        zone = self._classify_zone(odi)

        # ── 计算密化速率 ──
        densification_rate = 0.0
        is_densifying = False
        if self._odi_history:
            prev_odi = self._odi_history[-1]
            densification_rate = odi - prev_odi
            is_densifying = densification_rate > self._densification_threshold

        result = DensityIndexResult(
            odi=odi,
            subindices=sub,
            zone=zone,
            densification_rate=densification_rate,
            is_densifying=is_densifying,
            timestamp=self._step_count,
        )

        self._odi_history.append(odi)
        self._result_history.append(result)
        return result

    def _compute_threshold_proximity(self, result: SixThresholdResult) -> float:
        """计算阈值接近度

        对每个阈值，计算 value/threshold 的归一化值（上限1.0）。
        然后取几何平均（惩罚不均衡——某个阈值远低于其他）。

        返回 [0, 1]：
        - 1.0 = 所有阈值都远超阈值线
        - 0.0 = 所有阈值都远低于阈值线
        - ~0.5 = 所有阈值刚好达标
        """
        ratios = []
        for status in result.threshold_statuses:
            if status.threshold <= 0:
                ratios.append(1.0 if status.value > 0 else 0.0)
            else:
                ratio = status.value / status.threshold
                ratios.append(min(ratio, 1.0))

        if not ratios:
            return 0.0

        # 使用几何平均：惩罚短板
        log_sum = sum(np.log(max(r, 1e-10)) for r in ratios)
        geo_mean = np.exp(log_sum / len(ratios))
        return float(np.clip(geo_mean, 0.0, 1.0))

    def _compute_coupling_density(self,
                                   coupling_matrix: Dict[str, Dict[str, float]]) -> float:
        """计算耦合密度

        所有机制对耦合强度的均值（归一化到 [0, 1]）。
        使用算术平均（耦合是累积的，不是短板驱动的）。
        """
        mechanisms = SixThresholdDetector.THRESHOLD_NAMES.keys()
        keys = list(mechanisms)
        strengths = []

        for i, ma in enumerate(keys):
            for j, mb in enumerate(keys):
                if i >= j:
                    continue
                strength = coupling_matrix.get(ma, {}).get(mb, 0.0)
                strength = max(strength, coupling_matrix.get(mb, {}).get(ma, 0.0))
                strengths.append(strength)

        if not strengths:
            return 0.0

        mean_strength = float(np.mean(strengths))
        return float(np.clip(mean_strength, 0.0, 1.0))

    def _compute_firewall_purity(self, field_names: List[str]) -> float:
        """计算防火墙纯度

        检查字段名中是否包含高语义违规词汇。
        返回 1.0（无违规）到 0.0（全部违规）之间的连续值。
        """
        if not field_names:
            return 1.0

        forbidden = {
            'identity', 'identity_boundary', 'self_identity',
            'will', 'volition', 'intention', 'desire',
            'recollection', 'reminiscence', 'episodic_memory',
            'self_representation', 'self_model', 'self_aware',
            'evaluation', 'judgment', 'value_judgment',
            'meaning', 'significance', 'purpose', 'teleology',
        }

        violation_count = 0
        for name in field_names:
            name_lower = name.lower()
            for term in forbidden:
                if term in name_lower:
                    violation_count += 1
                    break  # 每个字段最多计一次

        purity = 1.0 - (violation_count / len(field_names))
        return float(np.clip(purity, 0.0, 1.0))

    def _compute_temporal_consistency(self) -> float:
        """计算时间一致性

        基于最近 N 次 ODI 的方差：方差越小，一致性越高。
        第一次计算返回 0.5（无历史信息）。
        """
        if len(self._odi_history) < 2:
            return 0.5

        window = min(self._temporal_window, len(self._odi_history))
        recent = self._odi_history[-window:]
        variance = float(np.var(recent))

        # 方差 → 一致性：方差越小，一致性越高
        # 使用指数衰减映射：consistency = exp(-k * variance)
        k = 10.0  # 调节系数：方差 0.1 时 consistency ≈ 0.37, 方差 0.01 时 ≈ 0.90
        consistency = np.exp(-k * variance)
        return float(np.clip(consistency, 0.0, 1.0))

    def _compute_resonance(self,
                           threshold_result: SixThresholdResult,
                           coupling_matrix: Dict[str, Dict[str, float]]) -> float:
        """计算跨机制共振

        衡量六机制之间的协同程度：
        - 各阈值达标程度的方差（方差小 = 均衡 = 共振）
        - 耦合矩阵的谱半径（最大特征值 = 共振强度）

        返回 [0, 1]。
        """
        # 阈值均衡度
        values = [s.value for s in threshold_result.threshold_statuses]
        thresholds = [s.threshold for s in threshold_result.threshold_statuses]

        if not values or any(t <= 0 for t in thresholds):
            return 0.0

        ratios = [min(v / t, 1.0) for v, t in zip(values, thresholds)]
        ratio_mean = np.mean(ratios)
        ratio_var = np.var(ratios)

        # 均衡度：均值高且方差低 → 高共振
        balance = ratio_mean * (1.0 - ratio_var)

        # 耦合谱半径（简化：用耦合矩阵的Frobenius范数归一化）
        mechanisms = list(SixThresholdDetector.THRESHOLD_NAMES.keys())
        n = len(mechanisms)
        mat = np.zeros((n, n))
        for i, ma in enumerate(mechanisms):
            for j, mb in enumerate(mechanisms):
                if i != j:
                    mat[i, j] = coupling_matrix.get(ma, {}).get(mb, 0.0)

        frob_norm = np.linalg.norm(mat, 'fro')
        max_norm = np.sqrt(n * (n - 1))  # 最大可能范数（所有元素=1）
        spectral = frob_norm / max_norm if max_norm > 0 else 0.0

        resonance = 0.6 * balance + 0.4 * spectral
        return float(np.clip(resonance, 0.0, 1.0))

    def _classify_zone(self, odi: float) -> str:
        """根据 ODI 值分类密度分区"""
        for zone_name, (lo, hi) in DENSE_ZONES.items():
            if lo <= odi < hi or (hi == 1.0 and odi >= lo):
                return zone_name
        return 'sparse'

    @property
    def current_odi(self) -> float:
        """最近一次 ODI 值"""
        if not self._odi_history:
            return 0.0
        return self._odi_history[-1]

    @property
    def max_odi(self) -> float:
        """历史最大 ODI 值"""
        if not self._odi_history:
            return 0.0
        return max(self._odi_history)

    @property
    def densification_trend(self) -> float:
        """密化趋势：最近 N 次 ODI 的线性回归斜率"""
        if len(self._odi_history) < 2:
            return 0.0

        window = min(self._temporal_window, len(self._odi_history))
        recent = self._odi_history[-window:]
        x = np.arange(len(recent))
        slope = float(np.polyfit(x, recent, 1)[0]) if len(recent) >= 2 else 0.0
        return slope

    def get_density_trajectory(self, last_n: int = 20) -> List[Tuple[int, float]]:
        """获取最近 N 次密度轨迹 [(timestamp, odi), ...]"""
        recent = self._result_history[-last_n:] if self._result_history else []
        return [(r.timestamp, r.odi) for r in recent]

    def get_zone_transitions(self) -> List[Tuple[int, str, str]]:
        """获取密度分区转换记录 [(timestamp, from_zone, to_zone), ...]"""
        transitions = []
        for i in range(1, len(self._result_history)):
            prev_zone = self._result_history[i - 1].zone
            curr_zone = self._result_history[i].zone
            if prev_zone != curr_zone:
                transitions.append((
                    self._result_history[i].timestamp,
                    prev_zone,
                    curr_zone,
                ))
        return transitions

    def reset(self):
        """重置所有状态"""
        self._odi_history.clear()
        self._result_history.clear()
        self._step_count = 0
