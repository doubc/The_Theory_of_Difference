"""
engine/layer_narrative_tracker.py — 分层叙事追踪器 (LayerNarrativeTracker)

Phase 5 Track B1 组件（新增）

职责：
  Track B1 的核心基础设施，实现分层叙事追踪。
  在 NSC (NarrativeSelfEmergence) 的全球 NSI 基础上，进一步分解为
  L0 (MINI), L1 (INSTITUTIONAL), L2 (CIVILIZATION) 三个层级的独立叙事追踪，
  并计算层间叙事相关性（H28）和叙事传导延迟（H29）。

理论依据：
  - 差异先行本体论 → 各层级应有独立的叙事轨迹
  - 发生学先行 vs 时间先行 → 层间叙事传导存在延迟
  - 对象是差异关系的凝聚态 → 每层叙事具有结构性独立性

四个子组件：
  1. PerLayerContinuityTracker — 单层主题连续性追踪（每层独立 Jaccard 滑动窗口）
  2. PerLayerStabilityTracker — 单层叙事稳定性追踪
  3. PerLayerHistoryTracker — 单层关键转折点检测
  4. InterLayerAnalyzer — 层间叙事相关性（Pearson r）与传导延迟（L0→L1→L2）

H28: 各层级 NSI 相关系数 < 0.5（层级叙事独立性）
H29: L0→L2 叙事传导延迟 50-200 步

设计原则：
  1. 不修改现有 NSE 组件，只做外部包装
  2. 每层使用与 NSE 类似的连续性/稳定性/历史追踪，但输入分解到单层
  3. MSI/ODI 全球值作为共享输入（不重新计算）
  4. 叙事主题（narrative_themes）按层级过滤：MINI→MINI_NARRATIVE, INSTITUTIONAL→INSTITUTIONAL, CIVILIZATION→CIVILIZATION
  5. 所有度量必须是结构性、可计算的、可证伪的
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import numpy as np


# ─── 默认配置 ───
DEFAULT_LAYER_NARRATIVE_CONFIG = {
    # Per-layer continuity (each layer uses independent Jaccard window)
    'continuity_window': 100,               # 每个层的连续性计算窗口
    'continuity_jaccard_threshold': 0.3,    # 每个层的 Jaccard 相似度阈值
    'continuity_min_steps': 50,             # 每个层的最小连续步数

    # Per-layer stability
    'stability_window': 100,                # 每个层的稳定化计算窗口
    'stability_min_coherence': 0.3,         # 最低叙事相干度

    # Per-layer history (turning points)
    'history_max_turning_points': 25,       # 每层最大关键转折点存储数
    'history_second_deriv_threshold': 0.05, # 二阶导数极值阈值
    'history_lookback': 20,                 # 回望窗口
    'history_signal_weights': {             # 各信号在转折点检测中的权重
        'activity': 0.5,                    # 层级活动度变化
        'odi': 0.3,                         # ODI 变化
        'msi': 0.2,                         # MSI 变化
    },

    # Inter-layer analysis
    'inter_layer_min_samples': 30,          # 层间分析所需最小样本数
    'inter_layer_correlation_window': 200,  # 相关性计算的滑动窗口
    'inter_layer_delay_max': 500,           # 传导延迟搜索上限
    'inter_layer_correlation_threshold': 0.5,  # H28: 相关性阈值
    'inter_layer_delay_min': 50,            # H29: 延迟下限
    'inter_layer_delay_max': 200,           # H29: 延迟上限

    # Layer definitions
    'layer_levels': ['MINI', 'INSTITUTIONAL', 'CIVILIZATION'],

    # NSI computation
    'nsi_alpha': 0.4,   # 时间连续性权重
    'nsi_beta': 0.3,    # 叙事稳定性权重
    'nsi_gamma': 0.3,   # 自我历史深度权重
    'nsi_min_odi': 0.3, # NSI 开始增长的 ODI 阈值（低于全球 NSE，因为是单层）
}


@dataclass
class PerLayerNSIResult:
    """单层叙事自我指数结果"""
    level: str                              # 层级名称
    nsi: float                              # [0, 1]
    temporal_continuity: float              # 时间连续性分量
    narrative_stability: float              # 叙事稳定性分量
    self_history_depth: float               # 自我历史深度分量
    is_nsi_active: bool                     # NSI 是否活跃
    step: int                               # 当前步数


@dataclass
class InterLayerCorrelationResult:
    """层间叙事相关性结果（H28）"""
    pairwise_correlations: Dict[str, float]  # e.g. {"MINI→INSTITUTIONAL": 0.23, ...}
    all_below_threshold: bool                # 是否所有相关系数 < 0.5
    threshold: float                         # 相关性阈值
    n_samples: int                           # 参与计算的样本数
    passing: bool                            # H28 是否通过


@dataclass
class ConductionDelayResult:
    """叙事传导延迟结果（H29）"""
    l0_to_l1_delay: Optional[int]            # MINI→INSTITUTIONAL 延迟（步数）
    l1_to_l2_delay: Optional[int]            # INSTITUTIONAL→CIVILIZATION 延迟
    l0_to_l2_delay: Optional[int]            # MINI→CIVILIZATION 延迟（主要假设）
    delay_mode: str                          # "cross_correlation", "turning_point", "insufficient_data"
    n_detection_events: int                  # 用于检测的事件/样本数
    passing: bool                            # H29 是否通过（50-200 步范围内）
    passing_reason: str                      # 通过/失败原因


@dataclass
class LayerNarrativeSummary:
    """分层叙事追踪完整摘要"""
    per_layer: Dict[str, PerLayerNSIResult]   # 每层当前 NSI
    inter_layer_correlation: InterLayerCorrelationResult  # H28
    conduction_delay: ConductionDelayResult    # H29
    total_steps: int
    layer_activity: Dict[str, float]          # 每层活跃度
    nsi_history: Dict[str, List[float]]       # 每层 NSI 时间序列（最后 200 步）


class PerLayerContinuityTracker:
    """单层叙事连续性追踪器

    轻量版 TemporalContinuityTracker，仅追踪单层主题连续性。
    使用该层活动度（activity signal）而非主题集合来计算连续性。
    """

    def __init__(self, level: str, config: Optional[Dict] = None):
        cfg = {**DEFAULT_LAYER_NARRATIVE_CONFIG, **(config or {})}
        self.level = level
        self.window_size = cfg['continuity_window']
        self.jaccard_threshold = cfg['continuity_jaccard_threshold']
        self.min_steps = cfg['continuity_min_steps']

        # Binary presence signal: is this layer active at each step?
        self._presence_history: Deque[bool] = deque(maxlen=self.window_size + 20)
        self._activity_level_history: Deque[float] = deque(maxlen=self.window_size + 20)
        self._continuous_steps = 0
        self._step_count = 0

    def update(self, activity_level: float, step: int) -> float:
        """更新本层连续性

        Parameters
        ----------
        activity_level : float
            本层当前活动度（0-1，如有层级的 narrative_level_distribution 归一化值）
        step : int
            当前步数

        Returns
        -------
        float
            本层连续性分数 [0, 1]
        """
        self._step_count += 1
        is_active = activity_level > 0.01
        self._presence_history.append(is_active)
        self._activity_level_history.append(activity_level)

        # Continuity = presence persistence + activity level smoothness
        if len(self._presence_history) < self.min_steps:
            return 0.0

        # Presence continuity: ratio of steps where layer was active in window
        recent_presences = list(self._presence_history)[-self.min_steps:]
        presence_ratio = sum(recent_presences) / max(1, len(recent_presences))

        # Activity smoothness: coefficient of variation of activity levels
        recent_activities = list(self._activity_level_history)[-self.window_size:]
        if len(recent_activities) >= 10:
            mean_act = np.mean(recent_activities)
            std_act = np.std(recent_activities)
            if mean_act > 1e-8:
                cv = std_act / mean_act
                smoothness = max(0.0, min(1.0, 1.0 - cv))
            else:
                smoothness = 0.0
        else:
            smoothness = 0.0

        # Combined: 60% presence + 40% smoothness
        continuity = 0.6 * presence_ratio + 0.4 * smoothness
        return float(np.clip(continuity, 0.0, 1.0))

    def get_summary(self) -> Dict:
        return {
            'level': self.level,
            'continuous_steps': self._step_count,
            'presence_ratio': float(np.mean(list(self._presence_history))) if self._presence_history else 0.0,
            'total_steps': self._step_count,
        }


class PerLayerStabilityTracker:
    """单层叙事稳定性追踪器

    轻量版 InstitutionalNarrativeStabilizer。
    使用该层的 activity_level 时间序列的波动性来评估稳定性。
    """

    def __init__(self, level: str, config: Optional[Dict] = None):
        cfg = {**DEFAULT_LAYER_NARRATIVE_CONFIG, **(config or {})}
        self.level = level
        self.window_size = cfg['stability_window']
        self.min_coherence = cfg['stability_min_coherence']

        self._activity_history: Deque[float] = deque(maxlen=self.window_size + 20)
        self._stability_history: Deque[float] = deque(maxlen=50)
        self._step_count = 0

    def update(self, activity_level: float, step: int) -> float:
        """更新本层稳定性

        Parameters
        ----------
        activity_level : float
            本层活动度
        step : int
            当前步数

        Returns
        -------
        float
            本层稳定性分数 [0, 1]
        """
        self._step_count += 1
        self._activity_history.append(activity_level)

        if len(self._activity_history) < 20:
            stability = 0.0
        else:
            recent = list(self._activity_history)[-min(50, len(self._activity_history)):]
            mean_act = np.mean(recent)
            std_act = np.std(recent)

            if mean_act > 1e-8:
                cv = std_act / mean_act
                # CV越小越稳定
                stability = max(0.0, min(1.0, 1.0 - cv))
            else:
                stability = 0.0

            # Boost for sustained activity
            if mean_act > self.min_coherence:
                stability = min(1.0, stability + 0.1)

        self._stability_history.append(stability)
        return stability

    def get_summary(self) -> Dict:
        return {
            'level': self.level,
            'current_stability': float(self._stability_history[-1]) if self._stability_history else 0.0,
            'mean_stability': float(np.mean(list(self._stability_history))) if self._stability_history else 0.0,
            'total_steps': self._step_count,
        }


class PerLayerHistoryTracker:
    """单层关键转折点检测器

    轻量版 SelfHistoryAccumulator。
    检测每层活动度的时间序列二阶导数极值点。
    """

    def __init__(self, level: str, config: Optional[Dict] = None):
        cfg = {**DEFAULT_LAYER_NARRATIVE_CONFIG, **(config or {})}
        self.level = level
        self.max_turning_points = cfg['history_max_turning_points']
        self.deriv_threshold = cfg['history_second_deriv_threshold']
        self.lookback = cfg['history_lookback']
        self.signal_weights = cfg['history_signal_weights']

        self._activity_history: Deque[float] = deque(maxlen=self.lookback + 10)
        self._odi_history: Deque[float] = deque(maxlen=self.lookback + 10)
        self._msi_history: Deque[float] = deque(maxlen=self.lookback + 10)
        self._turning_points: List[Dict] = []
        self._step_count = 0

    def update(self, activity_level: float, odi: float, msi: float, step: int) -> float:
        """更新本层转折点检测

        Parameters
        ----------
        activity_level : float
            本层活动度
        odi : float
            全球 ODI
        msi : float
            全球 MSI
        step : int
            当前步数

        Returns
        -------
        float
            本层历史深度 [0, 1]
        """
        self._step_count += 1
        self._activity_history.append(activity_level)
        self._odi_history.append(odi)
        self._msi_history.append(msi)

        # 检测转折点：信号时间序列的二阶导数极值
        if len(self._activity_history) >= 5:
            # 计算多信号加权二阶导数
            weighted_second_deriv = 0.0

            for signal_name, history, weight in [
                ('activity', self._activity_history, self.signal_weights.get('activity', 0.5)),
                ('odi', self._odi_history, self.signal_weights.get('odi', 0.3)),
                ('msi', self._msi_history, self.signal_weights.get('msi', 0.2)),
            ]:
                hist = list(history)
                if len(hist) >= 5:
                    # First derivative (central difference)
                    f_prime = (hist[-1] - hist[-3]) / 2.0 if len(hist) >= 3 else 0.0
                    # Second derivative
                    if len(hist) >= 5:
                        f_double_prime = (hist[-1] - 2 * hist[-3] + hist[-5]) / 4.0
                    else:
                        f_double_prime = 0.0
                    weighted_second_deriv += weight * abs(f_double_prime)

            # 检测转折点
            if weighted_second_deriv > self.deriv_threshold:
                # 避免重复记录相邻步的转折点
                if (not self._turning_points or
                        step - self._turning_points[-1]['step'] > 10):
                    self._turning_points.append({
                        'step': step,
                        'activity_level': float(activity_level),
                        'odi': float(odi),
                        'msi': float(msi),
                        'second_deriv': float(weighted_second_deriv),
                    })

                    # 限制存储数量
                    if len(self._turning_points) > self.max_turning_points:
                        self._turning_points = self._turning_points[-self.max_turning_points:]

        # History depth = ratio of turning points to max capacity
        depth = len(self._turning_points) / max(1, self.max_turning_points)
        return float(min(1.0, depth))

    def get_turning_point_steps(self) -> List[int]:
        return [tp['step'] for tp in self._turning_points]

    def get_summary(self) -> Dict:
        return {
            'level': self.level,
            'n_turning_points': len(self._turning_points),
            'turning_point_steps': self.get_turning_point_steps(),
            'detection_threshold': self.deriv_threshold,
            'total_steps': self._step_count,
        }


class InterLayerAnalyzer:
    """层间叙事分析器

    计算：
    - H28: 各层级 NSI 相关系数 < 0.5
    - H29: L0→L2 叙事传导延迟 50-200 步
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_LAYER_NARRATIVE_CONFIG, **(config or {})}
        self.layer_levels = cfg['layer_levels']
        self.min_samples = cfg['inter_layer_min_samples']
        self.correlation_window = cfg['inter_layer_correlation_window']
        self.delay_max = cfg['inter_layer_delay_max']
        self.correlation_threshold = cfg['inter_layer_correlation_threshold']
        self.delay_min = cfg['inter_layer_delay_min']
        self.delay_max_val = cfg['inter_layer_delay_max']

        # Per-layer NSI history
        self._nsi_history: Dict[str, List[float]] = {
            level: [] for level in self.layer_levels
        }
        # Per-layer turning point steps
        self._turning_points: Dict[str, List[int]] = {
            level: [] for level in self.layer_levels
        }
        self._total_steps = 0

    def record_nsi(self, level: str, nsi: float):
        """记录一步的 NSI"""
        if level in self._nsi_history:
            self._nsi_history[level].append(nsi)

    def record_turning_points(self, level: str, steps: List[int]):
        """更新某层的转折点步数列表"""
        if level in self._turning_points:
            self._turning_points[level] = sorted(list(set(steps)))

    def step_increment(self):
        self._total_steps += 1

    def compute_correlation(self) -> InterLayerCorrelationResult:
        """计算层间 NSI 相关性 (H28)"""
        pairwise = {}
        n_samples = 0

        for i, la in enumerate(self.layer_levels):
            for j, lb in enumerate(self.layer_levels):
                if i >= j:
                    continue
                key = f"{la}→{lb}"
                a_hist = self._nsi_history.get(la, [])
                b_hist = self._nsi_history.get(lb, [])

                # Align lengths
                min_len = min(len(a_hist), len(b_hist))
                if min_len < self.min_samples:
                    pairwise[key] = 0.0
                    n_samples = min_len
                    continue

                a = np.array(a_hist[-min_len:])
                b = np.array(b_hist[-min_len:])

                if np.std(a) > 1e-10 and np.std(b) > 1e-10:
                    corr = float(np.corrcoef(a, b)[0, 1])
                else:
                    corr = 0.0

                pairwise[key] = round(corr, 4)
                n_samples = min_len

        all_below = all(abs(v) < self.correlation_threshold for v in pairwise.values())
        passing = all_below and n_samples >= self.min_samples

        return InterLayerCorrelationResult(
            pairwise_correlations=pairwise,
            all_below_threshold=all_below,
            threshold=self.correlation_threshold,
            n_samples=n_samples,
            passing=passing,
        )

    def compute_conduction_delay(self) -> ConductionDelayResult:
        """计算叙事传导延迟 (H29)

        使用两种方法：
        1. Cross-correlation based: 寻找 L0 NSI 序列与 L2 NSI 序列的时移互相关峰值
        2. Turning point based: L0 转折点后 L2 转折点的延迟中位数

        选择信息量更大的方法报告。
        """
        # Method 1: Cross-correlation
        l0_nsi = self._nsi_history.get('MINI', [])
        l2_nsi = self._nsi_history.get('CIVILIZATION', [])

        if len(l0_nsi) >= self.min_samples and len(l2_nsi) >= self.min_samples:
            a = np.array(l0_nsi)
            b = np.array(l2_nsi)
            min_len = min(len(a), len(b))
            a = a[-min_len:]
            b = b[-min_len:]

            # Cross-correlation at various lags
            max_lag = min(self.delay_max, min_len // 2)
            best_lag = 0
            best_corr = -1.0

            # Search: L0 leads L2 → positive lag means L0 before L2
            for lag in range(1, max_lag):
                if lag >= len(a) or lag >= len(b):
                    break
                corr = float(np.corrcoef(a[:-lag], b[lag:])[0, 1]) if len(a[:-lag]) >= 3 else 0.0
                if corr > best_corr:
                    best_corr = corr
                    best_lag = lag

            if best_lag >= self.delay_min and best_lag <= self.delay_max_val:
                delay_cc = best_lag
                delay_mode_cc = "cross_correlation"
            else:
                delay_cc = None
                delay_mode_cc = "cross_correlation_out_of_range"
        else:
            delay_cc = None
            delay_mode_cc = "insufficient_data"

        # Method 2: Turning point based
        l0_tps = self._turning_points.get('MINI', [])
        l2_tps = self._turning_points.get('CIVILIZATION', [])

        if len(l0_tps) >= 3 and len(l2_tps) >= 1:
            detected_delays = []
            for l0_tp in l0_tps:
                # Find first L2 turning point after this L0 turning point
                later_l2 = [t for t in l2_tps if t > l0_tp]
                if later_l2:
                    delay = later_l2[0] - l0_tp
                    if 0 < delay <= self.delay_max:
                        detected_delays.append(delay)

            if detected_delays:
                delay_tp = int(np.median(detected_delays))
                delay_mode_tp = "turning_point"
            else:
                delay_tp = None
                delay_mode_tp = "no_match"
        else:
            delay_tp = None
            delay_mode_tp = "insufficient_turning_points"

        # Also compute L1-L2 delay
        l1_tps = self._turning_points.get('INSTITUTIONAL', [])
        l0_to_l1 = None
        l1_to_l2 = None

        if len(l0_tps) >= 3 and len(l1_tps) >= 1:
            detected = []
            for tp0 in l0_tps:
                later_l1 = [t for t in l1_tps if t > tp0]
                if later_l1:
                    d = later_l1[0] - tp0
                    if 0 < d <= self.delay_max:
                        detected.append(d)
            if detected:
                l0_to_l1 = int(np.median(detected))

        if len(l1_tps) >= 3 and len(l2_tps) >= 1:
            detected = []
            for tp1 in l1_tps:
                later_l2 = [t for t in l2_tps if t > tp1]
                if later_l2:
                    d = later_l2[0] - tp1
                    if 0 < d <= self.delay_max:
                        detected.append(d)
            if detected:
                l1_to_l2 = int(np.median(detected))

        # Decide which method to report
        if delay_cc is not None:
            l0_to_l2 = delay_cc
            delay_mode = delay_mode_cc
            n_events = min(len(l0_nsi), len(l2_nsi))
        elif delay_tp is not None:
            l0_to_l2 = delay_tp
            delay_mode = delay_mode_tp
            n_events = len(detected_delays)
        else:
            l0_to_l2 = None
            delay_mode = "insufficient_data"
            n_events = 0

        # Evaluate H29
        if l0_to_l2 is not None:
            passing_h29 = (self.delay_min <= l0_to_l2 <= self.delay_max_val)
            reason = (f"L0→L2 delay={l0_to_l2} steps "
                      f"({delay_mode}, n_events={n_events})")
        else:
            passing_h29 = False
            reason = f"Insufficient data to compute delay"

        return ConductionDelayResult(
            l0_to_l1_delay=l0_to_l1,
            l1_to_l2_delay=l1_to_l2,
            l0_to_l2_delay=l0_to_l2,
            delay_mode=delay_mode,
            n_detection_events=n_events,
            passing=passing_h29,
            passing_reason=reason,
        )

    def get_nsi_history(self, level: str) -> List[float]:
        return list(self._nsi_history.get(level, []))

    def get_summary(self) -> Dict:
        """获取层间分析摘要"""
        corr_result = self.compute_correlation()
        delay_result = self.compute_conduction_delay()

        return {
            'correlation': {
                'pairwise': corr_result.pairwise_correlations,
                'all_below_threshold': corr_result.all_below_threshold,
                'n_samples': corr_result.n_samples,
                'passing': corr_result.passing,
            },
            'delay': {
                'l0_to_l1': delay_result.l0_to_l1_delay,
                'l1_to_l2': delay_result.l1_to_l2_delay,
                'l0_to_l2': delay_result.l0_to_l2_delay,
                'mode': delay_result.delay_mode,
                'n_events': delay_result.n_detection_events,
                'passing': delay_result.passing,
                'reason': delay_result.passing_reason,
            },
            'nsi_history_lengths': {
                level: len(hist)
                for level, hist in self._nsi_history.items()
            },
            'turning_point_counts': {
                level: len(self._turning_points.get(level, []))
                for level in self.layer_levels
            },
        }


class LayerNarrativeTracker:
    """分层叙事追踪器 — Phase 5 Track B1

    职责：
    - 在 L0 (MINI), L1 (INSTITUTIONAL), L2 (CIVILIZATION) 独立追踪 NSI
    - 计算层间叙事相关性（H28）
    - 检测叙事传导延迟（H29）

    使用方式：在 HierarchicalEvolver 的步骤回调中调用。
    每步传入与 NSE 相同的信号（MSI, ODI, narrative_level_distribution 等），
    轨迹自动在内部按层分解追踪。

    与 NSE 的关系：
    - NSE 计算全球 NSI（全系统叙事自我）
    - LayerNarrativeTracker 计算每层 NSI 和层间指标
    - 两者并行运行，不相互依赖
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_LAYER_NARRATIVE_CONFIG, **(config or {})}
        self.layer_levels = self.config['layer_levels']

        # Per-layer trackers
        self._continuity_trackers: Dict[str, PerLayerContinuityTracker] = {}
        self._stability_trackers: Dict[str, PerLayerStabilityTracker] = {}
        self._history_trackers: Dict[str, PerLayerHistoryTracker] = {}

        for level in self.layer_levels:
            self._continuity_trackers[level] = PerLayerContinuityTracker(level, self.config)
            self._stability_trackers[level] = PerLayerStabilityTracker(level, self.config)
            self._history_trackers[level] = PerLayerHistoryTracker(level, self.config)

        # Inter-layer analyzer
        self._inter_layer = InterLayerAnalyzer(self.config)

        # Per-layer NSI history
        self._layer_nsi_history: Dict[str, List[float]] = {
            level: [] for level in self.layer_levels
        }
        self._layer_continuity_history: Dict[str, List[float]] = {
            level: [] for level in self.layer_levels
        }
        self._layer_stability_history: Dict[str, List[float]] = {
            level: [] for level in self.layer_levels
        }
        self._layer_depth_history: Dict[str, List[float]] = {
            level: [] for level in self.layer_levels
        }

        self._total_steps = 0
        self._step_count = 0

    def step(
        self,
        msi: float,
        odi: float,
        narrative_level_distribution: Dict[str, int],
        step: int = 0,
        level_states: Optional[Dict[str, Dict]] = None,
        **kwargs,
    ) -> Dict[str, PerLayerNSIResult]:
        """执行一步分层叙事追踪

        Parameters
        ----------
        msi : float
            全球 MSI 值
        odi : float
            全球 ODI 值
        narrative_level_distribution : Dict[str, int]
            叙事层级分布 {level_name: count}，例如 {'MINI': 5, 'INSTITUTIONAL': 3, 'CIVILIZATION': 1}
        step : int
            当前步数
        level_states : Optional[Dict[str, Dict]]
            CSC 提供的层级状态字典 {level: {stability_score, odi, ...}}

        Returns
        -------
        Dict[str, PerLayerNSIResult]
            每层的 NSI 结果 {level: PerLayerNSIResult}
        """
        self._step_count += 1
        self._total_steps += 1
        actual_step = step if step > 0 else self._step_count

        results = {}

        # Normalize level distribution: total count → per-layer activity level [0, 1]
        total_count = sum(narrative_level_distribution.values()) or 1

        for level in self.layer_levels:
            # Compute per-layer activity level
            count = narrative_level_distribution.get(level, 0)
            if level == 'MINI':
                # MINI activity = MINI_NARRATIVE count / max possible
                activity_level = min(1.0, count / max(1, total_count * 2))
            else:
                activity_level = min(1.0, count / max(1, total_count))

            # Clamp for safety
            activity_level = float(np.clip(activity_level, 0.0, 1.0))

            # Per-layer stability: prefer level_states from CSC if available
            if level_states and level in level_states:
                stability_from_csc = level_states[level].get('stability_score', 0.0)
            else:
                stability_from_csc = None

            # 1. Update continuity
            continuity = self._continuity_trackers[level].update(activity_level, actual_step)
            self._layer_continuity_history[level].append(continuity)

            # 2. Update stability
            if stability_from_csc is not None:
                # Use CSC-provided stability directly
                stability = float(np.clip(stability_from_csc, 0.0, 1.0))
            else:
                stability = self._stability_trackers[level].update(activity_level, actual_step)
            self._layer_stability_history[level].append(stability)

            # 3. Update history (turning points)
            history_depth = self._history_trackers[level].update(activity_level, odi, msi, actual_step)
            self._layer_depth_history[level].append(history_depth)

            # 4. Compute per-layer NSI
            nsi_result = self._compute_layer_nsi(level, continuity, stability, history_depth, odi, actual_step)
            self._layer_nsi_history[level].append(nsi_result.nsi)

            # Record for inter-layer analysis
            self._inter_layer.record_nsi(level, nsi_result.nsi)

            results[level] = nsi_result

        # Update turning points in inter-layer analyzer
        for level in self.layer_levels:
            tp_steps = self._history_trackers[level].get_turning_point_steps()
            self._inter_layer.record_turning_points(level, tp_steps)

        self._inter_layer.step_increment()
        return results

    def _compute_layer_nsi(
        self,
        level: str,
        continuity: float,
        stability: float,
        history_depth: float,
        odi: float,
        step: int,
    ) -> PerLayerNSIResult:
        """计算单层 NSI

        使用与全球 NSE 相同的加权公式，但 ODI 阈值稍低（单层更容易活跃）。
        """
        alpha = self.config['nsi_alpha']
        beta = self.config['nsi_beta']
        gamma = self.config['nsi_gamma']
        nsi_min_odi = self.config['nsi_min_odi']

        # ODI gating
        odi_gate = min(1.0, odi / nsi_min_odi) if nsi_min_odi > 0 else 1.0
        is_nsi_active = odi >= nsi_min_odi

        raw_nsi = alpha * continuity + beta * stability + gamma * history_depth
        nsi = raw_nsi * odi_gate

        return PerLayerNSIResult(
            level=level,
            nsi=float(np.clip(nsi, 0.0, 1.0)),
            temporal_continuity=float(continuity),
            narrative_stability=float(stability),
            self_history_depth=float(history_depth),
            is_nsi_active=is_nsi_active,
            step=step,
        )

    def get_inter_layer_correlation(self) -> InterLayerCorrelationResult:
        """获取层间相关性 (H28)"""
        return self._inter_layer.compute_correlation()

    def get_conduction_delay(self) -> ConductionDelayResult:
        """获取传导延迟 (H29)"""
        return self._inter_layer.compute_conduction_delay()

    def get_layer_nsi_history(self, level: str) -> List[float]:
        """获取某层 NSI 历史"""
        return list(self._layer_nsi_history.get(level, []))

    def get_all_nsi_histories(self) -> Dict[str, List[float]]:
        """获取所有层 NSI 历史"""
        return {level: list(hist) for level, hist in self._layer_nsi_history.items()}

    def get_layer_activity_profile(self) -> Dict[str, float]:
        """获取每层当前活动度（最后 50 步均值）"""
        profile = {}
        for level in self.layer_levels:
            recent = self._layer_nsi_history.get(level, [])[-50:]
            profile[level] = float(np.mean(recent)) if recent else 0.0
        return profile

    def get_summary(self) -> LayerNarrativeSummary:
        """获取完整摘要"""
        # Current per-layer NSI
        per_layer_nsi = {}
        for level in self.layer_levels:
            hist = self._layer_nsi_history.get(level, [])
            if hist:
                last_nsi = hist[-1]
                last_odi = 0.0
                # use the global odi from last step as a proxy
                nsi_odi = last_nsi  # conservative: use nsi itself as odi proxy
                per_layer_nsi[level] = PerLayerNSIResult(
                    level=level,
                    nsi=float(last_nsi),
                    temporal_continuity=float(self._layer_continuity_history[level][-1]) if self._layer_continuity_history.get(level) else 0.0,
                    narrative_stability=float(self._layer_stability_history[level][-1]) if self._layer_stability_history.get(level) else 0.0,
                    self_history_depth=float(self._layer_depth_history[level][-1]) if self._layer_depth_history.get(level) else 0.0,
                    is_nsi_active=float(last_nsi) > 0.01,
                    step=self._step_count,
                )
        
        # Inter-layer metrics
        corr_result = self.get_inter_layer_correlation()
        delay_result = self.get_conduction_delay()
        
        # Layer activity
        activity = {}
        for level in self.layer_levels:
            recent_nsi = self._layer_nsi_history.get(level, [])[-100:]
            activity[level] = float(np.mean(recent_nsi)) if recent_nsi else 0.0
        
        # NSI histories (last 200 steps for plot data)
        nsi_histories = {}
        for level in self.layer_levels:
            hist = self._layer_nsi_history.get(level, [])
            nsi_histories[level] = hist[-200:] if len(hist) > 200 else hist
        
        return LayerNarrativeSummary(
            per_layer=per_layer_nsi,
            inter_layer_correlation=corr_result,
            conduction_delay=delay_result,
            total_steps=self._total_steps,
            layer_activity=activity,
            nsi_history=nsi_histories,
        )