"""
engine/cooperative_emergence_detector.py — 协同涌现检测器 (CooperativeEmergenceDetector)

Phase 2 P1 组件（新增）

职责：检测六个结构条件的协同涌现模式——不是六个条件的独立收敛，
而是它们在足够高密度下开始协同振荡、同步跨越阈值、形成新的耦合拓扑。

理论依据：
- 《Appearing Before Appearing》§4.4 路线 (b)：第七阈值不是新的离散结构条件，
  而是六阈值在高密度下的质变涌现（已有条件的涌现后果）
- 协同涌现的核心特征：
  1. 同步跨越（synchronized_crossing）：六个条件几乎同时跨越各自的阈值线
  2. 耦合拓扑相变（coupling_topology_transition）：耦合矩阵的拓扑结构发生质变
  3. 协同振荡（cooperative_oscillation）：六个条件的值开始协同波动
  4. 互信息突增（mutual_information_surge）：条件间的统计依赖性突然增强

与 SeventhThresholdDetector 的区别：
- SeventhThresholdDetector 检测的是 ODI 时间序列中的相变信号（单变量）
- CooperativeEmergenceDetector 检测的是六条件之间的协同模式（多变量）
- 两者互补：前者检测"密度跃迁"，后者检测"结构协同"

使用方式：
    detector = CooperativeEmergenceDetector()
    for step in range(n_steps):
        result = detector.feed(
            threshold_result=six_threshold_result,
            coupling_matrix=coupling_matrix,
            odi_result=odi_result,
            timestamp=step,
        )
        if result.cooperative_emergence_detected:
            print(f"协同涌现! type={result.emergence_type}, "
                  f"confidence={result.confidence:.2f}")
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Deque
from dataclasses import dataclass, field
from collections import deque

from engine.six_threshold_detector import SixThresholdResult, SixThresholdDetector
from engine.organizational_density_index import DensityIndexResult


# ─── 默认配置 ───
DEFAULT_CE_CONFIG = {
    # 同步跨越检测
    'sync_window': 5,              # 同步窗口：多少步内六个条件都跨越算"同步"
    'sync_threshold_ratio': 0.8,   # 同步比例：窗口内至少 80% 的条件跨越

    # 耦合拓扑相变检测
    'topology_history_window': 10,  # 拓扑比较的历史窗口
    'topology_change_threshold': 0.4,  # 拓扑变化阈值（Jaccard 距离）

    # 协同振荡检测
    'oscillation_window': 8,       # 振荡检测窗口
    'oscillation_correlation_threshold': 0.6,  # 协同相关系数阈值

    # 互信息突增检测
    'mi_window': 10,               # 互信息估计窗口
    'mi_surge_threshold': 0.3,     # 互信息突增阈值

    # 综合判定
    'min_emergence_confidence': 0.45,  # 最低涌现可信度
    'odi_pre_subjective_min': 0.5,     # 最低 ODI 要求（前主体态地板）
}


@dataclass
class SynchronizedCrossing:
    """同步跨越信号"""
    detected: bool = False
    crossing_step: int = 0         # 检测到同步跨越的时间戳
    n_synchronized: int = 0        # 同步跨越的条件数（最大 6）
    sync_ratio: float = 0.0        # 同步比例
    threshold_crossings: Dict[str, int] = field(default_factory=dict)  # 条件 → 跨越时间戳

    @property
    def is_strong(self) -> bool:
        return self.detected and self.sync_ratio >= 0.8


@dataclass
class CouplingTopologyTransition:
    """耦合拓扑相变信号"""
    detected: bool = False
    transition_step: int = 0       # 检测到拓扑变化的时间戳
    jaccard_distance: float = 0.0  # 新旧拓扑的 Jaccard 距离
    edges_gained: List[Tuple[str, str]] = field(default_factory=list)  # 新增的耦合边
    edges_lost: List[Tuple[str, str]] = field(default_factory=list)    # 消失的耦合边
    old_density: float = 0.0       # 旧拓扑密度
    new_density: float = 0.0       # 新拓扑密度

    @property
    def is_expansive(self) -> bool:
        """拓扑扩展（边增加）而非收缩"""
        return self.detected and len(self.edges_gained) > len(self.edges_lost)


@dataclass
class CooperativeOscillation:
    """协同振荡信号"""
    detected: bool = False
    mean_pairwise_correlation: float = 0.0  # 平均成对相关系数
    max_correlation: float = 0.0            # 最大成对相关系数
    correlated_pairs: List[Tuple[str, str]] = field(default_factory=list)  # 强相关的条件对
    anti_correlated_pairs: List[Tuple[str, str]] = field(default_factory=list)  # 强负相关的条件对
    timestamp: int = 0


@dataclass
class MutualInformationSurge:
    """互信息突增信号"""
    detected: bool = False
    current_mi: float = 0.0        # 当前互信息估计
    baseline_mi: float = 0.0       # 基线互信息
    mi_ratio: float = 0.0          # 互信息比（当前 / 基线）
    timestamp: int = 0


@dataclass
class CooperativeEmergenceResult:
    """协同涌现检测结果"""
    cooperative_emergence_detected: bool = False
    emergence_type: str = 'none'   # 'none' | 'synchronized_crossing' | 'topology_transition' |
                                    # 'cooperative_oscillation' | 'mi_surge' | 'multi_pattern'
    confidence: float = 0.0        # [0, 1]
    timestamp: int = 0

    # 各信号详情
    sync_crossing: SynchronizedCrossing = field(default_factory=SynchronizedCrossing)
    topology_transition: CouplingTopologyTransition = field(default_factory=CouplingTopologyTransition)
    cooperative_oscillation: CooperativeOscillation = field(default_factory=CooperativeOscillation)
    mi_surge: MutualInformationSurge = field(default_factory=MutualInformationSurge)

    # 综合信息
    n_active_signals: int = 0      # 活跃信号数
    odi_at_detection: float = 0.0  # 检测时的 ODI
    description: str = ''          # 涌现描述

    @property
    def emergence_label(self) -> str:
        labels = {
            'none': '无协同涌现',
            'synchronized_crossing': '同步跨越',
            'topology_transition': '耦合拓扑相变',
            'cooperative_oscillation': '协同振荡',
            'mi_surge': '互信息突增',
            'multi_pattern': '多模式协同涌现',
        }
        return labels.get(self.emergence_type, '未知')

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.7:
            return '高可信度'
        elif self.confidence >= 0.45:
            return '中可信度'
        elif self.confidence > 0:
            return '低可信度'
        return '无可信度'

    def __repr__(self):
        return (f"CooperativeEmergence[{self.emergence_label}] "
                f"conf={self.confidence:.2f} ({self.confidence_label}) "
                f"signals={self.n_active_signals}")


class CooperativeEmergenceDetector:
    """协同涌现检测器

    检测六个结构条件的协同涌现模式。

    核心检测维度：
    1. 同步跨越 (Synchronized Crossing)：六个条件在短时间内同步跨越阈值线
    2. 耦合拓扑相变 (Coupling Topology Transition)：耦合矩阵的拓扑结构发生质变
    3. 协同振荡 (Cooperative Oscillation)：六个条件的值开始协同波动
    4. 互信息突增 (Mutual Information Surge)：条件间的统计依赖性突然增强

    理论立场：
    - 协同涌现不是六个条件的简单叠加
    - 协同涌现是六个条件在高密度下产生的新组织属性
    - 检测器的任务是区分"独立收敛"和"协同涌现"

    使用方式：
        detector = CooperativeEmergenceDetector()
        for step in range(n_steps):
            result = detector.feed(
                threshold_result=six_threshold_result,
                coupling_matrix=coupling_matrix,
                odi_result=odi_result,
                timestamp=step,
            )
    """

    # 六个条件的名称（与 SixThresholdDetector 一致）
    CONDITION_NAMES = [
        'interface_regulation',       # 3.1
        'self_sustaining',            # 3.2
        'retention',                  # 3.3
        'replication',                # 3.4
        'selection',                  # 3.5
        'functional_differentiation', # 3.6
    ]

    def __init__(self, config: Optional[Dict] = None):
        """
        Args:
            config: 配置参数，覆盖 DEFAULT_CE_CONFIG
        """
        self._config = dict(DEFAULT_CE_CONFIG)
        if config:
            self._config.update(config)

        # 历史数据
        self._threshold_history: Deque[SixThresholdResult] = deque(maxlen=100)
        self._coupling_history: Deque[Dict[str, Dict[str, float]]] = deque(maxlen=50)
        self._odi_history: Deque[float] = deque(maxlen=100)

        # 条件值历史（用于协同振荡检测）
        self._condition_values: Dict[str, Deque[float]] = {
            name: deque(maxlen=50) for name in self.CONDITION_NAMES
        }

        # 阈值跨越记录：condition_name → crossing_timestamp
        self._crossing_timestamps: Dict[str, int] = {}

        # 检测结果历史
        self._history: List[CooperativeEmergenceResult] = []
        self._emergence_count: int = 0
        self._step_count: int = 0

    def feed(
        self,
        threshold_result: SixThresholdResult,
        coupling_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        odi_result: Optional[DensityIndexResult] = None,
        timestamp: Optional[int] = None,
    ) -> CooperativeEmergenceResult:
        """输入一次检测结果，返回协同涌现检测结果。

        Args:
            threshold_result: 六阈值检测结果
            coupling_matrix: 耦合矩阵 {mechanism: {mechanism: strength}}
            odi_result: 组织密度指数结果（可选，用于 ODI 门控）
            timestamp: 时间戳

        Returns:
            CooperativeEmergenceResult 协同涌现检测结果
        """
        if timestamp is not None:
            self._step_count = timestamp
        else:
            self._step_count += 1

        # 更新历史
        self._threshold_history.append(threshold_result)
        if coupling_matrix is not None:
            self._coupling_history.append(coupling_matrix)
        if odi_result is not None:
            self._odi_history.append(odi_result.odi)

        # 更新条件值历史
        self._update_condition_values(threshold_result)

        # 更新阈值跨越记录
        self._update_crossing_timestamps(threshold_result)

        # ── 执行四维度检测 ──
        sync = self._detect_synchronized_crossing()
        topology = self._detect_topology_transition()
        oscillation = self._detect_cooperative_oscillation()
        mi = self._detect_mi_surge()

        # ── 融合判定 ──
        active_signals = []
        confidence_scores = []

        if sync.detected:
            active_signals.append('synchronized_crossing')
            # 同步比例越高，可信度越高
            conf = min(0.3 + 0.5 * sync.sync_ratio, 0.85)
            confidence_scores.append(conf)

        if topology.detected:
            active_signals.append('topology_transition')
            # Jaccard 距离越大，可信度越高
            conf = min(0.3 + 0.5 * topology.jaccard_distance, 0.8)
            confidence_scores.append(conf)

        if oscillation.detected:
            active_signals.append('cooperative_oscillation')
            conf = min(0.3 + 0.5 * oscillation.mean_pairwise_correlation, 0.75)
            confidence_scores.append(conf)

        if mi.detected:
            active_signals.append('mi_surge')
            conf = min(0.3 + 0.4 * mi.mi_ratio, 0.7)
            confidence_scores.append(conf)

        # 确定涌现类型和可信度
        odi_at = self._odi_history[-1] if self._odi_history else 0.0
        odi_gate = odi_at >= self._config['odi_pre_subjective_min']

        if not active_signals or not odi_gate:
            emergence_type = 'none'
            confidence = 0.0
        elif len(active_signals) == 1:
            emergence_type = active_signals[0]
            confidence = confidence_scores[0] if confidence_scores else 0.3
        else:
            emergence_type = 'multi_pattern'
            # 多信号融合：取最高可信度 + 协同加成
            confidence = min(
                max(confidence_scores) + 0.12 * (len(active_signals) - 1),
                1.0
            )

        detected = (
            len(active_signals) > 0
            and confidence >= self._config['min_emergence_confidence']
            and odi_gate
        )

        if detected:
            self._emergence_count += 1

        # 构建描述
        description = self._build_description(
            detected, active_signals, sync, topology, oscillation, mi, odi_at
        )

        result = CooperativeEmergenceResult(
            cooperative_emergence_detected=detected,
            emergence_type=emergence_type if detected else 'none',
            confidence=confidence,
            timestamp=self._step_count,
            sync_crossing=sync,
            topology_transition=topology,
            cooperative_oscillation=oscillation,
            mi_surge=mi,
            n_active_signals=len(active_signals),
            odi_at_detection=odi_at,
            description=description,
        )

        self._history.append(result)
        return result

    def _update_condition_values(self, result: SixThresholdResult):
        """从阈值结果中提取各条件的归一化值并更新历史"""
        for status in result.threshold_statuses:
            # 将阈值 ID 映射到条件名称
            name_map = {
                '3.1': 'interface_regulation',
                '3.2': 'self_sustaining',
                '3.3': 'retention',
                '3.4': 'replication',
                '3.5': 'selection',
                '3.6': 'functional_differentiation',
            }
            cond_name = name_map.get(status.threshold_id)
            if cond_name is not None:
                # 归一化值：value / threshold（上限 1.0）
                if status.threshold > 0:
                    normalized = min(status.value / status.threshold, 1.0)
                else:
                    normalized = 1.0 if status.value > 0 else 0.0
                self._condition_values[cond_name].append(normalized)

    def _update_crossing_timestamps(self, result: SixThresholdResult):
        """更新阈值跨越记录"""
        name_map = {
            '3.1': 'interface_regulation',
            '3.2': 'self_sustaining',
            '3.3': 'retention',
            '3.4': 'replication',
            '3.5': 'selection',
            '3.6': 'functional_differentiation',
        }
        for status in result.threshold_statuses:
            cond_name = name_map.get(status.threshold_id)
            if cond_name is not None and status.is_met:
                if cond_name not in self._crossing_timestamps:
                    self._crossing_timestamps[cond_name] = self._step_count

    def _detect_synchronized_crossing(self) -> SynchronizedCrossing:
        """检测同步跨越

        逻辑：在最近的 sync_window 步内，六个条件中有多个跨越了各自的阈值线。
        如果跨越的条件比例超过阈值，则判定为同步跨越。

        理论含义：独立收敛时，六个条件会先后跨越阈值（因为各自速率不同）。
        协同涌现时，六个条件会在短时间内同步跨越——这是相变的特征。
        """
        window = self._config['sync_window']
        threshold_ratio = self._config['sync_threshold_ratio']

        if len(self._threshold_history) < 2:
            return SynchronizedCrossing()

        # 检查最近 window 步内的跨越事件
        recent_crossings = {}
        for cond_name, crossing_ts in self._crossing_timestamps.items():
            if crossing_ts >= self._step_count - window:
                recent_crossings[cond_name] = crossing_ts

        n_sync = len(recent_crossings)
        sync_ratio = n_sync / len(self.CONDITION_NAMES)

        detected = sync_ratio >= threshold_ratio

        return SynchronizedCrossing(
            detected=detected,
            crossing_step=self._step_count if detected else 0,
            n_synchronized=n_sync,
            sync_ratio=sync_ratio,
            threshold_crossings=dict(recent_crossings),
        )

    def _detect_topology_transition(self) -> CouplingTopologyTransition:
        """检测耦合拓扑相变

        逻辑：比较最近窗口的耦合矩阵与更早窗口的耦合矩阵。
        如果拓扑结构（哪些机制对之间有强耦合）发生了显著变化，
        则判定为拓扑相变。

        使用 Jaccard 距离衡量拓扑变化：
        - 将耦合矩阵二值化（强度 > 阈值 → 有边）
        - 计算新旧边集的 Jaccard 距离

        理论含义：独立收敛时，耦合拓扑是渐变的。
        协同涌现时，耦合拓扑会突然重组——新的耦合边出现，旧的消失。
        """
        window = self._config['topology_history_window']
        change_threshold = self._config['topology_change_threshold']

        if len(self._coupling_history) < 2 * window:
            return CouplingTopologyTransition()

        coupling_list = list(self._coupling_history)

        # 旧拓扑：更早的 window 个耦合矩阵的平均
        old_matrices = coupling_list[-2*window:-window]
        # 新拓扑：最近 window 个耦合矩阵的平均
        new_matrices = coupling_list[-window:]

        # 计算平均耦合矩阵
        old_avg = self._average_coupling_matrix(old_matrices)
        new_avg = self._average_coupling_matrix(new_matrices)

        # 二值化（使用耦合阈值 0.3）
        coupling_threshold = 0.3
        old_edges = self._matrix_to_edge_set(old_avg, coupling_threshold)
        new_edges = self._matrix_to_edge_set(new_avg, coupling_threshold)

        # Jaccard 距离
        if old_edges or new_edges:
            intersection = old_edges & new_edges
            union = old_edges | new_edges
            jaccard_dist = 1.0 - len(intersection) / len(union) if union else 0.0
        else:
            jaccard_dist = 0.0

        edges_gained = sorted(new_edges - old_edges)
        edges_lost = sorted(old_edges - new_edges)

        old_density = len(old_edges) / max(len(self.CONDITION_NAMES) * (len(self.CONDITION_NAMES) - 1) / 2, 1)
        new_density = len(new_edges) / max(len(self.CONDITION_NAMES) * (len(self.CONDITION_NAMES) - 1) / 2, 1)

        detected = jaccard_dist >= change_threshold

        return CouplingTopologyTransition(
            detected=detected,
            transition_step=self._step_count if detected else 0,
            jaccard_distance=jaccard_dist,
            edges_gained=edges_gained,
            edges_lost=edges_lost,
            old_density=old_density,
            new_density=new_density,
        )

    def _average_coupling_matrix(
        self,
        matrices: List[Dict[str, Dict[str, float]]],
    ) -> Dict[str, Dict[str, float]]:
        """计算多个耦合矩阵的平均"""
        if not matrices:
            return {}

        avg: Dict[str, Dict[str, float]] = {}
        n = len(matrices)
        for mat in matrices:
            for ma, inner in mat.items():
                if ma not in avg:
                    avg[ma] = {}
                for mb, strength in inner.items():
                    avg[ma][mb] = avg[ma].get(mb, 0.0) + strength / n
        return avg

    @staticmethod
    def _matrix_to_edge_set(
        matrix: Dict[str, Dict[str, float]],
        threshold: float,
    ) -> set:
        """将耦合矩阵转换为边集（二值化）"""
        edges = set()
        for ma, inner in matrix.items():
            for mb, strength in inner.items():
                if strength >= threshold and ma != mb:
                    # 规范化边（字母序，避免重复）
                    edge = tuple(sorted([ma, mb]))
                    edges.add(edge)
        return edges

    def _detect_cooperative_oscillation(self) -> CooperativeOscillation:
        """检测协同振荡

        逻辑：计算六个条件值时间序列的成对相关系数。
        如果多个条件对之间出现强正相关或强负相关，
        则判定为协同振荡。

        理论含义：独立收敛时，六个条件的值是独立变化的。
        协同涌现时，六个条件的值开始协同波动——
        这是系统进入新的组织模式的统计特征。
        """
        window = self._config['oscillation_window']
        corr_threshold = self._config['oscillation_correlation_threshold']

        # 收集最近 window 步的条件值
        values_matrix = []
        for cond_name in self.CONDITION_NAMES:
            vals = list(self._condition_values[cond_name])
            if len(vals) < window:
                return CooperativeOscillation()
            values_matrix.append(vals[-window:])

        values_arr = np.array(values_matrix)  # (6, window)

        # 计算成对相关系数
        correlated_pairs = []
        anti_correlated_pairs = []
        correlations = []

        for i in range(len(self.CONDITION_NAMES)):
            for j in range(i + 1, len(self.CONDITION_NAMES)):
                x = values_arr[i]
                y = values_arr[j]

                # Pearson 相关系数
                x_std = np.std(x)
                y_std = np.std(y)
                if x_std < 1e-10 or y_std < 1e-10:
                    corr = 0.0
                else:
                    corr = float(np.corrcoef(x, y)[0, 1])
                    if np.isnan(corr):
                        corr = 0.0

                correlations.append(corr)

                pair = (self.CONDITION_NAMES[i], self.CONDITION_NAMES[j])
                if abs(corr) >= corr_threshold:
                    if corr > 0:
                        correlated_pairs.append(pair)
                    else:
                        anti_correlated_pairs.append(pair)

        if not correlations:
            return CooperativeOscillation()

        mean_corr = float(np.mean(np.abs(correlations)))
        max_corr = float(np.max(np.abs(correlations))) if correlations else 0.0

        # 协同振荡：至少 3 对强相关
        detected = len(correlated_pairs) + len(anti_correlated_pairs) >= 3

        return CooperativeOscillation(
            detected=detected,
            mean_pairwise_correlation=mean_corr,
            max_correlation=max_corr,
            correlated_pairs=correlated_pairs,
            anti_correlated_pairs=anti_correlated_pairs,
            timestamp=self._step_count,
        )

    def _detect_mi_surge(self) -> MutualInformationSurge:
        """检测互信息突增

        逻辑：使用直方图法估计六个条件之间的互信息。
        比较最近窗口的互信息与基线窗口的互信息。
        如果互信息显著增加，则判定为互信息突增。

        简化实现：使用成对相关系数的平方作为互信息的代理
        （对于高斯变量，MI = -0.5 * log(1 - corr^2)）。

        理论含义：独立收敛时，条件间的统计依赖性低。
        协同涌现时，条件间的统计依赖性突然增强——
        这是"条件开始协同"的信息论特征。
        """
        window = self._config['mi_window']
        surge_threshold = self._config['mi_surge_threshold']

        # 需要至少 2*window 个数据点
        for cond_name in self.CONDITION_NAMES:
            if len(self._condition_values[cond_name]) < 2 * window:
                return MutualInformationSurge()

        # 收集条件值
        values_matrix = []
        for cond_name in self.CONDITION_NAMES:
            vals = list(self._condition_values[cond_name])
            values_matrix.append(vals)

        values_arr = np.array(values_matrix)  # (6, n_steps)

        # 最近窗口和基线窗口
        recent = values_arr[:, -window:]
        baseline = values_arr[:, -2*window:-window]

        # 估计互信息（使用相关系数代理）
        recent_mi = self._estimate_mutual_information_proxy(recent)
        baseline_mi = self._estimate_mutual_information_proxy(baseline)

        mi_ratio = recent_mi / max(baseline_mi, 1e-10)

        detected = (
            recent_mi >= surge_threshold
            and mi_ratio >= 1.5  # 互信息至少增加 50%
        )

        return MutualInformationSurge(
            detected=detected,
            current_mi=recent_mi,
            baseline_mi=baseline_mi,
            mi_ratio=mi_ratio,
            timestamp=self._step_count,
        )

    @staticmethod
    def _estimate_mutual_information_proxy(values: np.ndarray) -> float:
        """使用相关系数估计互信息的代理

        对于高斯变量，成对 MI = -0.5 * log(1 - corr^2)。
        对所有成对求和作为总互信息的代理。

        Args:
            values: (n_conditions, n_steps) 条件值矩阵

        Returns:
            互信息代理值
        """
        n_conditions = values.shape[0]
        total_mi = 0.0
        n_pairs = 0

        for i in range(n_conditions):
            for j in range(i + 1, n_conditions):
                x = values[i]
                y = values[j]
                x_std = np.std(x)
                y_std = np.std(y)
                if x_std < 1e-10 or y_std < 1e-10:
                    continue
                corr = float(np.corrcoef(x, y)[0, 1])
                if np.isnan(corr):
                    continue
                corr_sq = corr ** 2
                if corr_sq >= 0.99:
                    corr_sq = 0.99  # 避免 log(0)
                mi = -0.5 * np.log(1.0 - corr_sq)
                total_mi += mi
                n_pairs += 1

        return total_mi / max(n_pairs, 1)

    def _build_description(
        self,
        detected: bool,
        active_signals: List[str],
        sync: SynchronizedCrossing,
        topology: CouplingTopologyTransition,
        oscillation: CooperativeOscillation,
        mi: MutualInformationSurge,
        odi: float,
    ) -> str:
        """构建涌现描述"""
        if not detected:
            return "无协同涌现"

        parts = []
        if 'synchronized_crossing' in active_signals:
            parts.append(
                f"{sync.n_synchronized}/6 条件在 {self._config['sync_window']} 步内同步跨越阈值"
            )
        if 'topology_transition' in active_signals:
            direction = "扩展" if topology.is_expansive else "收缩"
            parts.append(
                f"耦合拓扑{direction}：+{len(topology.edges_gained)}边 -{len(topology.edges_lost)}边 "
                f"(Jaccard={topology.jaccard_distance:.3f})"
            )
        if 'cooperative_oscillation' in active_signals:
            parts.append(
                f"协同振荡：{len(oscillation.correlated_pairs)}正相关对 "
                f"{len(oscillation.anti_correlated_pairs)}负相关对 "
                f"(mean|corr|={oscillation.mean_pairwise_correlation:.3f})"
            )
        if 'mi_surge' in active_signals:
            parts.append(
                f"互信息突增：{mi.baseline_mi:.3f}→{mi.current_mi:.3f} (×{mi.mi_ratio:.2f})"
            )

        parts.append(f"ODI={odi:.4f}")
        return "; ".join(parts)

    # ─── 查询接口 ───

    @property
    def emergence_count(self) -> int:
        """检测到的协同涌现次数"""
        return self._emergence_count

    @property
    def latest_result(self) -> Optional[CooperativeEmergenceResult]:
        """最近一次检测结果"""
        return self._history[-1] if self._history else None

    @property
    def has_emergence_occurred(self) -> bool:
        """是否至少发生过一次协同涌现"""
        return self._emergence_count > 0

    def get_emergence_history(self) -> List[CooperativeEmergenceResult]:
        """获取所有检测到的协同涌现事件"""
        return [r for r in self._history if r.cooperative_emergence_detected]

    def get_signal_summary(self) -> Dict:
        """获取各信号的触发统计"""
        if not self._history:
            return {'n_evaluations': 0}

        sync_count = sum(1 for r in self._history if r.sync_crossing.detected)
        topo_count = sum(1 for r in self._history if r.topology_transition.detected)
        osc_count = sum(1 for r in self._history if r.cooperative_oscillation.detected)
        mi_count = sum(1 for r in self._history if r.mi_surge.detected)

        return {
            'n_evaluations': len(self._history),
            'n_emergence': self._emergence_count,
            'sync_crossing_triggers': sync_count,
            'topology_transition_triggers': topo_count,
            'cooperative_oscillation_triggers': osc_count,
            'mi_surge_triggers': mi_count,
        }

    def reset(self):
        """重置所有状态"""
        self._threshold_history.clear()
        self._coupling_history.clear()
        self._odi_history.clear()
        for dq in self._condition_values.values():
            dq.clear()
        self._crossing_timestamps.clear()
        self._history.clear()
        self._emergence_count = 0
        self._step_count = 0
