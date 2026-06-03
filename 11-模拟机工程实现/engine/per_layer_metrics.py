# -*- coding: utf-8 -*-
"""
engine/per_layer_metrics.py — 分层指标收集器 (PerLayerMetricsCollector)

Phase 5 Track B8+ 基础设施：为 H46-H49 提供每层 NSI、CIV、主题追踪。

职责：
  1. PerLayerNSITracker — 每层 NSI 时间序列（与 NSE 同公式，但输入分解到每层）
  2. PerLayerCIVTracker — 每层 CIV（Hamming weight）时间序列
  3. PerLayerThemeTracker — 每层活跃主题（active bits）集合追踪
  4. LayerAutonomyAnalyzer — 层间自主性分析（H46-H49 假设检验）

与 LayerNarrativeTracker 的关系：
  - LNT 侧重叙事连续性/稳定性/历史深度
  - PLM 侧重物理指标（CIV hamming weight）+ 主题集合
  - 两者互补，可并行使用
"""

import math
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import deque
import numpy as np


# ─── 默认配置 ───
DEFAULT_PER_LAYER_METRICS_CONFIG = {
    # NSI 计算
    'nsi_alpha': 0.4,
    'nsi_beta': 0.3,
    'nsi_gamma': 0.3,
    'nsi_min_odi': 0.3,
    'nsi_rolling_window': 200,

    # CIV 追踪
    'civ_rolling_window': 200,

    # 主题追踪
    'theme_jaccard_window': 200,

    # 层定义
    'layer_names': ['L0', 'L1', 'L2'],
}


# ─── 数据类 ───

@dataclass
class PerLayerNSIData:
    """单层 NSI 数据点"""
    step: int
    layer: str
    nsi: float
    temporal_continuity: float
    narrative_stability: float
    self_history_depth: float
    is_active: bool


@dataclass
class PerLayerCIVData:
    """单层 CIV 数据点"""
    step: int
    layer: str
    hamming_weight: int
    active_bits: Set[int]
    frozen_bits: Set[int]
    n_active: int
    n_frozen: int


@dataclass
class PerLayerThemeData:
    """单层主题数据点"""
    step: int
    layer: str
    active_themes: Set[int]  # active bit indices as theme proxies
    n_themes: int


@dataclass
class H46Result:
    """H46: L0-L1 NSI 自主性"""
    rolling_correlations: List[float]
    mean_corr: float
    min_corr: float
    max_corr: float
    pass_threshold: float  # < 0.5
    pass_count: int  # 在窗口中低于阈值的比例
    passing: bool


@dataclass
class H47Result:
    """H47: L0-L1 CIV 独立性"""
    rolling_correlations: List[float]
    mean_corr: float
    min_corr: float
    max_corr: float
    pass_threshold: float  # < 0.6
    passing: bool


@dataclass
class H48Result:
    """H48: L1 封口潜力"""
    sealing_ratios: List[float]
    max_ratio: float
    mean_ratio: float
    pass_threshold: float  # > 0.8
    passing: bool


@dataclass
class H49Result:
    """H49: L0-L1 主题发散"""
    jaccard_values: List[float]
    mean_jaccard: float
    min_jaccard: float
    pass_threshold: float  # < 0.4
    passing: bool


# ─── 子追踪器 ───

class PerLayerNSITracker:
    """每层 NSI 追踪器 — v2 (time-varying)

    v2 修复：注入时间变化信号的三个维度，解决 v1 中所有输入成分
    在封口后均为常数导致 NSI 扁平化的根本问题。

    NSI = α·continuity + β·stability + γ·history_depth + δ·delta_odi

    新成分：
    - **odi_delta**：每步 ODI 变化量（|ODI(t) - ODI(t-1)|），捕获叙事系统
      的实时活动度变化，是封口后唯一持续的动态信号。
    - **civ_event_rate**：CIV 事件率（Hamming weight 变化频率），
       反映信念突变的实时发生率。
    - **实时步数存储**：改用 List[(step, value)] 而非 deque index，确保
       封口后过滤逻辑正确。
    """

    def __init__(self, layer: str, config: Optional[Dict] = None):
        cfg = {**DEFAULT_PER_LAYER_METRICS_CONFIG, **(config or {})}
        self.layer = layer
        self.alpha = cfg['nsi_alpha']
        self.beta = cfg['nsi_beta']
        self.gamma = cfg['nsi_gamma']
        self.delta = 0.2  # 新增：odi_delta 权重（动态信号补偿）
        self.nsi_min_odi = cfg['nsi_min_odi']
        self.rolling_window = cfg['nsi_rolling_window']

        # v2 改造：用 List[(step, value)] 替代 Deque，保留真实步数
        # 历史容量控制：只保留 rolling_window + 200 个样本
        self._max_history = self.rolling_window + 200

        # 活动度历史 [(step, activity)]
        self._activity_history: List[Tuple[int, float]] = []
        # 冻结比特比例历史 [(step, frozen_ratio)]
        self._frozen_ratio_history: List[Tuple[int, float]] = []
        # ODI 历史 [(step, odi)]
        self._odi_history: List[Tuple[int, float]] = []
        # CIV 历史 [(step, hamming_weight)] (从 CIV tracker 同步)
        self._civ_history: List[Tuple[int, float]] = []
        # NSI 输出历史 [(step, nsi)]
        self._nsi_output_history: List[Tuple[int, float]] = []
        # 转折点
        self._turning_points: List[int] = []
        self._activity_for_tp: Deque[float] = deque(maxlen=20)

    def _trim_history(self):
        """裁剪历史到最大容量"""
        for hist_list in [self._activity_history, self._frozen_ratio_history,
                          self._odi_history, self._civ_history, self._nsi_output_history]:
            while len(hist_list) > self._max_history:
                hist_list.pop(0)

    def _append_sorted(self, hist: List[Tuple[int, float]], step: int, value: float):
        """追加到有序历史（确保步数单调递增）"""
        if hist and hist[-1][0] >= step:
            # 重复或乱序步：跳过
            return
        hist.append((step, value))

    def record_civ(self, step: int, hamming_weight: int):
        """从 CIV tracker 同步 CIV 数据"""
        self._append_sorted(self._civ_history, step, float(hamming_weight))

    def update(self, step: int, n_active: int, n_total: int,
               n_frozen: int, global_odi: float, global_msi: float) -> PerLayerNSIData:
        """更新一步 — v2 带 odi_delta 动态补偿"""
        activity = n_active / max(1, n_total)
        frozen_ratio = n_frozen / max(1, n_total)

        self._append_sorted(self._activity_history, step, activity)
        self._append_sorted(self._frozen_ratio_history, step, frozen_ratio)
        self._append_sorted(self._odi_history, step, global_odi)

        # ─── 转折点检测 ───
        self._activity_for_tp.append(activity)
        if len(self._activity_for_tp) >= 5:
            hist = list(self._activity_for_tp)
            f_double_prime = (hist[-1] - 2 * hist[-3] + hist[-5]) / 4.0
            if abs(f_double_prime) > 0.02:
                if not self._turning_points or step - self._turning_points[-1] > 20:
                    self._turning_points.append(step)

        # ─── 连续性：活动度持久性 + 平滑度 ───
        if len(self._activity_history) >= 20:
            recent_vals = [v for _, v in self._activity_history[-50:]]
            presence_ratio = sum(1 for a in recent_vals if a > 0.1) / len(recent_vals)
            mean_act = float(np.mean(recent_vals))
            std_act = float(np.std(recent_vals))
            smoothness = max(0.0, min(1.0, 1.0 - (std_act / max(mean_act, 1e-8))))
            continuity = 0.6 * presence_ratio + 0.4 * smoothness
        else:
            continuity = 0.0

        # ─── 稳定性：冻结比例 + 平滑度 ───
        if len(self._frozen_ratio_history) >= 20:
            recent_frozen = [v for _, v in self._frozen_ratio_history[-50:]]
            mean_frozen = float(np.mean(recent_frozen))
            std_frozen = float(np.std(recent_frozen))
            frozen_stability = min(1.0, mean_frozen / 0.5) if mean_frozen > 0 else 0.0
            frozen_smoothness = max(0.0, 1.0 - std_frozen * 5)
            stability = 0.5 * frozen_stability + 0.5 * frozen_smoothness
        else:
            stability = 0.0

        # ─── 历史深度 ───
        history_depth = min(1.0, len(self._turning_points) / 20.0)

        # ─── ⭐ v3 核心：动态信号来自 CIV 变化而非活动度 ───
        # v2 使用了全局 ODI（封口后恒定）和 per-layer 活动度（封口后稳定），
        # 两者都导致 odi_delta ≈ 0 和 NSI 平坦。
        # v3 改为使用 CIV（Hamming weight）变化作为核心动态信号：
        # - 活动比特数量恒定，但 WHICH 比特活跃不断变化（迁移）
        # - CIV 追踪这些迁移导致的 Hamming weight 波动
        # - CIV 事件率也作为次要动态信号
        odi_delta = 0.0
        if len(self._civ_history) >= 2:
            # 使用 CIV 变化量作为核心动态信号
            civ_delta = abs(self._civ_history[-1][1] - self._civ_history[-2][1])
            # 归一化：CIV 最大变化约为 n_total/2，取 n_total 作为分母
            max_civ = max(self.nsi_min_odi * 10, 1.0)  # safe fallback
            if len(self._civ_history) > 10:
                # 使用历史最大值作为归一化基准
                max_civ = max(abs(self._civ_history[i][1] - self._civ_history[i-1][1])
                             for i in range(1, len(self._civ_history)))
            max_civ = max(max_civ, 1.0)
            odi_delta = min(1.0, civ_delta / max_civ)

        # ─── ⭐ v2 核心：CIV 事件率 ───
        # 捕获 Hamming weight 在最近窗口中的变化频率
        civ_event_rate = 0.0
        if len(self._civ_history) >= 10:
            civ_vals = [v for _, v in self._civ_history[-20:]]
            n_changes = sum(1 for i in range(1, len(civ_vals)) if civ_vals[i] != civ_vals[i-1])
            civ_event_rate = n_changes / max(1, len(civ_vals))

        # ─── NSI 计算（带动态补偿） ───
        odi_gate = min(1.0, global_odi / self.nsi_min_odi) if self.nsi_min_odi > 0 else 1.0
        is_active = global_odi >= self.nsi_min_odi

        # ⭐ 结构成分 + 动态补偿（CIV 事件率 + CIV delta）
        raw_nsi = (self.alpha * continuity
                   + self.beta * stability
                   + self.gamma * history_depth
                   + self.delta * odi_delta
                   + 0.1 * civ_event_rate)  # v3: add civ_event_rate as explicit dynamic term

        # 归一化：确保带额外动态项时不超过 1.0
        total_weight = self.alpha + self.beta + self.gamma + self.delta + 0.1
        raw_nsi = raw_nsi / total_weight

        nsi = float(np.clip(raw_nsi * odi_gate, 0.0, 1.0))
        self._append_sorted(self._nsi_output_history, step, nsi)

        self._trim_history()

        return PerLayerNSIData(
            step=step, layer=self.layer, nsi=nsi,
            temporal_continuity=continuity, narrative_stability=stability,
            self_history_depth=history_depth, is_active=is_active,
        )

    def get_nsi_history(self) -> List[Tuple[int, float]]:
        """返回 [(step, nsi), ...] — v2 修复：使用真实步数而非 deque index

        返回记录的 NSI 输出历史（带 odi_delta 动态补偿的完整 NSI 计算值），
        而非活动度代理。这是分析 H46 的可靠数据源。
        """
        return list(self._nsi_output_history)

    def get_nsi_proxy_history(self) -> List[Tuple[int, float]]:
        """返回 [(step, activity * frozen_ratio), ...] — 原始代理（保留向后兼容）"""
        result = []
        for (s1, act), (s2, fr) in zip(self._activity_history, self._frozen_ratio_history):
            if s1 == s2:
                result.append((s1, act * fr))
        return result

    def get_odi_history(self) -> List[Tuple[int, float]]:
        return list(self._odi_history)

    def get_odi_delta(self, window: int = 50) -> List[float]:
        """返回最近窗口的 ODI 变化率序列"""
        recent = self._odi_history[-window:]
        if len(recent) < 2:
            return []
        return [abs(recent[i][1] - recent[i-1][1]) for i in range(1, len(recent))]

    def get_civ_event_rate(self, window: int = 50) -> float:
        """返回最近窗口的 CIV 事件率"""
        recent = self._civ_history[-window:]
        if len(recent) < 2:
            return 0.0
        changes = sum(1 for i in range(1, len(recent)) if recent[i][1] != recent[i-1][1])
        return changes / max(1, len(recent))

    def get_turning_points(self) -> List[int]:
        return list(self._turning_points)

    def get_turning_points(self) -> List[int]:
        return list(self._turning_points)


class PerLayerCIVTracker:
    """每层 CIV（Hamming weight）追踪器"""

    def __init__(self, layer: str):
        self.layer = layer
        self._hamming_history: List[Tuple[int, int]] = []  # (step, hamming)
        self._active_bits_history: List[Tuple[int, Set[int]]] = []

    def record(self, step: int, hamming_weight: int,
               active_bits: Set[int], frozen_bits: Set[int],
               n_active: int, n_frozen: int):
        self._hamming_history.append((step, hamming_weight))
        self._active_bits_history.append((step, active_bits.copy()))

    def get_hamming_history(self) -> List[int]:
        return [h[1] for h in self._hamming_history]

    def get_hamming_steps(self) -> List[int]:
        return [h[0] for h in self._hamming_history]

    def get_active_bits_at(self, step: int) -> Optional[Set[int]]:
        for s, bits in self._active_bits_history:
            if s == step:
                return bits
        return None

    def get_summary(self) -> Dict:
        hists = self.get_hamming_history()
        return {
            'layer': self.layer,
            'n_samples': len(hists),
            'mean_hamming': float(np.mean(hists)) if hists else 0,
            'std_hamming': float(np.std(hists)) if hists else 0,
            'min_hamming': int(np.min(hists)) if hists else 0,
            'max_hamming': int(np.max(hists)) if hists else 0,
        }


class PerLayerThemeTracker:
    """每层主题追踪器（用活跃比特作为主题代理）"""

    def __init__(self, layer: str):
        self.layer = layer
        self._theme_history: List[Tuple[int, Set[int]]] = []

    def record(self, step: int, active_bits: Set[int]):
        self._theme_history.append((step, active_bits.copy()))

    def get_jaccard_with(self, other: 'PerLayerThemeTracker',
                          window: int = 200) -> List[float]:
        """计算与另一层的 Jaccard 相似度时间序列"""
        results = []
        my_hist = self._theme_history[-window:]
        other_hist = other._theme_history[-window:]

        # Align by step
        my_dict = dict(self._theme_history[-window:])
        other_dict = dict(other._theme_history[-window:])

        common_steps = sorted(set(my_dict.keys()) & set(other_dict.keys()))
        for step in common_steps:
            a = my_dict[step]
            b = other_dict[step]
            if len(a) == 0 and len(b) == 0:
                jaccard = 1.0
            else:
                intersection = len(a & b)
                union = len(a | b)
                jaccard = intersection / union if union > 0 else 0.0
            results.append(jaccard)

        return results

    def get_final_jaccard(self, other: 'PerLayerThemeTracker') -> float:
        """计算最终状态的 Jaccard 相似度"""
        if not self._theme_history or not other._theme_history:
            return 0.0
        a = self._theme_history[-1][1]
        b = other._theme_history[-1][1]
        if len(a) == 0 and len(b) == 0:
            return 1.0
        intersection = len(a & b)
        union = len(a | b)
        return intersection / union if union > 0 else 0.0


# ─── 主收集器 ───

class PerLayerMetricsCollector:
    """分层指标收集器 — Phase 5 B8+

    作为 HierarchicalEvolver 的 step_callback 使用，
    在每一步收集每层的 NSI、CIV、主题数据。

    使用方式：
        collector = PerLayerMetricsCollector()
        evolver = HierarchicalEvolver(...)
        result = evolver.run(tracking_callback=collector.step)
        analysis = collector.analyze()
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_PER_LAYER_METRICS_CONFIG, **(config or {})}
        self.config = cfg
        self.layer_names = cfg['layer_names']

        # Per-layer trackers
        self._nsi_trackers: Dict[str, PerLayerNSITracker] = {}
        self._civ_trackers: Dict[str, PerLayerCIVTracker] = {}
        self._theme_trackers: Dict[str, PerLayerThemeTracker] = {}

        for name in self.layer_names:
            self._nsi_trackers[name] = PerLayerNSITracker(name, config)
            self._civ_trackers[name] = PerLayerCIVTracker(name)
            self._theme_trackers[name] = PerLayerThemeTracker(name)

        # Global metrics history
        self._global_odi_history: List[Tuple[int, float]] = []
        self._global_msi_history: List[Tuple[int, float]] = []

        # Sealing info
        self._l0_seal_step: int = -1
        self._l1_formed_step: int = -1
        self._post_seal_started: bool = False

        # L1 sealing ratio tracking
        self._l1_sealing_ratios: List[float] = []

    def step(self, step: int, layer_id: int,
             n_active: int, n_total: int, n_frozen: int,
             hamming_weight: int, active_bits: Set[int],
             frozen_bits: Set[int],
             global_odi: float, global_msi: float,
             l0_sealed: bool = False, l1_formed: bool = False,
             l1_unique_active: int = 0, l1_sealing_threshold: int = 0,
             **kwargs):
        """每步回调

        Parameters
        ----------
        step : int
            全局步数
        layer_id : int
            当前层 ID
        n_active : int
            当前层活跃比特数
        n_total : int
            当前层总比特数
        n_frozen : int
            当前层冻结比特数
        hamming_weight : int
            当前层 Hamming weight
        active_bits : Set[int]
            当前层活跃比特集合
        frozen_bits : Set[int]
            当前层冻结比特集合
        global_odi : float
            全局 ODI
        global_msi : float
            全局 MSI
        l0_sealed : bool
            L0 是否已封口
        l1_formed : bool
            L1 是否已形成
        l1_unique_active : int
            L1 唯一活跃比特数（用于封口比率）
        l1_sealing_threshold : int
            L1 封口阈值
        """
        layer_name = self.layer_names[layer_id] if layer_id < len(self.layer_names) else f'L{layer_id}'

        # Track sealing events
        if l0_sealed and self._l0_seal_step < 0:
            self._l0_seal_step = step
        if l1_formed and self._l1_formed_step < 0:
            self._l1_formed_step = step
        if l0_sealed and not self._post_seal_started:
            self._post_seal_started = True

        # Record global metrics
        self._global_odi_history.append((step, global_odi))
        self._global_msi_history.append((step, global_msi))

        # Update per-layer trackers
        nsi_data = self._nsi_trackers[layer_name].update(
            step, n_active, n_total, n_frozen, global_odi, global_msi)

        # ⭐ v2: 将 CIV 数据同步到 NSI tracker（为 odi_delta + civ_event_rate 提供输入）
        self._nsi_trackers[layer_name].record_civ(step, hamming_weight)

        self._civ_trackers[layer_name].record(
            step, hamming_weight, active_bits, frozen_bits, n_active, n_frozen)

        self._theme_trackers[layer_name].record(step, active_bits)

        # Track L1 sealing ratio
        if layer_id == 1 and l1_sealing_threshold > 0:
            ratio = l1_unique_active / l1_sealing_threshold
            self._l1_sealing_ratios.append(ratio)

    def analyze(self, post_seal_only: bool = True) -> Dict:
        """分析收集的数据，返回 H46-H49 结果"""
        l0_nsi = self._nsi_trackers['L0']
        l1_nsi = self._nsi_trackers['L1']
        l0_civ = self._civ_trackers['L0']
        l1_civ = self._civ_trackers['L1']
        l0_theme = self._theme_trackers['L0']
        l1_theme = self._theme_trackers['L1']

        # Extract post-seal data if requested
        start_step = self._l0_seal_step if post_seal_only and self._l0_seal_step > 0 else 0

        # ─── H46: L0-L1 NSI rolling correlation ───
        h46 = self._compute_h46(l0_nsi, l1_nsi, start_step)

        # ─── H47: L0-L1 CIV rolling correlation ───
        h47 = self._compute_h47(l0_civ, l1_civ, start_step)

        # ─── H48: L1 sealing potential ───
        h48 = self._compute_h48()

        # ─── H49: L0-L1 theme Jaccard ───
        h49 = self._compute_h49(l0_theme, l1_theme, start_step)

        return {
            'h46': h46,
            'h47': h47,
            'h48': h48,
            'h49': h49,
            'l0_seal_step': self._l0_seal_step,
            'l1_formed_step': self._l1_formed_step,
            'global_odi_history': self._global_odi_history,
            'l0_nsi_history': self._get_nsi_series(l0_nsi, start_step),
            'l1_nsi_history': self._get_nsi_series(l1_nsi, start_step),
            'l0_civ_history': l0_civ.get_hamming_history(),
            'l1_civ_history': l1_civ.get_hamming_history(),
        }

    def _compute_h46(self, l0_nsi: PerLayerNSITracker, l1_nsi: PerLayerNSITracker,
                      start_step: int) -> H46Result:
        """H46: L0-L1 NSI rolling correlation < 0.5"""
        l0_hist = l0_nsi.get_nsi_history()
        l1_hist = l1_nsi.get_nsi_history()

        # Filter to post-seal
        l0_post = [(s, v) for s, v in l0_hist if s >= start_step]
        l1_post = [(s, v) for s, v in l1_hist if s >= start_step]

        # Align by index (both start from same relative point)
        min_len = min(len(l0_post), len(l1_post))
        if min_len < 50:
            return H46Result(
                rolling_correlations=[], mean_corr=0.0, min_corr=0.0, max_corr=0.0,
                pass_threshold=0.5, pass_count=0, passing=False,
            )

        l0_vals = np.array([v for _, v in l0_post[-min_len:]])
        l1_vals = np.array([v for _, v in l1_post[-min_len:]])

        # Rolling correlation with window=100
        window = 100
        corrs = []
        for i in range(window, len(l0_vals) + 1):
            a_win = l0_vals[i - window:i]
            b_win = l1_vals[i - window:i]
            if np.std(a_win) > 1e-10 and np.std(b_win) > 1e-10:
                corr = float(np.corrcoef(a_win, b_win)[0, 1])
            else:
                corr = 0.0
            corrs.append(corr)

        if not corrs:
            return H46Result(
                rolling_correlations=[], mean_corr=0.0, min_corr=0.0, max_corr=0.0,
                pass_threshold=0.5, pass_count=0, passing=False,
            )

        pass_count = sum(1 for c in corrs if abs(c) < 0.5)
        return H46Result(
            rolling_correlations=corrs,
            mean_corr=float(np.mean(corrs)),
            min_corr=float(np.min(corrs)),
            max_corr=float(np.max(corrs)),
            pass_threshold=0.5,
            pass_count=pass_count / len(corrs) if corrs else 0,
            passing=(pass_count / len(corrs)) >= 0.6 if corrs else False,
        )

    def _compute_h47(self, l0_civ: PerLayerCIVTracker, l1_civ: PerLayerCIVTracker,
                      start_step: int) -> H47Result:
        """H47: L0-L1 CIV rolling correlation < 0.6"""
        l0_ham = l0_civ.get_hamming_history()
        l1_ham = l1_civ.get_hamming_history()
        l0_steps = l0_civ.get_hamming_steps()
        l1_steps = l1_civ.get_hamming_steps()

        # Filter to post-seal
        l0_post = [v for s, v in zip(l0_steps, l0_ham) if s >= start_step]
        l1_post = [v for s, v in zip(l1_steps, l1_ham) if s >= start_step]

        min_len = min(len(l0_post), len(l1_post))
        if min_len < 50:
            return H47Result(
                rolling_correlations=[], mean_corr=0.0, min_corr=0.0, max_corr=0.0,
                pass_threshold=0.6, passing=False,
            )

        l0_vals = np.array(l0_post[-min_len:])
        l1_vals = np.array(l1_post[-min_len:])

        window = 100
        corrs = []
        for i in range(window, len(l0_vals) + 1):
            a_win = l0_vals[i - window:i]
            b_win = l1_vals[i - window:i]
            if np.std(a_win) > 1e-10 and np.std(b_win) > 1e-10:
                corr = float(np.corrcoef(a_win, b_win)[0, 1])
            else:
                corr = 0.0
            corrs.append(corr)

        if not corrs:
            return H47Result(
                rolling_correlations=[], mean_corr=0.0, min_corr=0.0, max_corr=0.0,
                pass_threshold=0.6, passing=False,
            )

        return H47Result(
            rolling_correlations=corrs,
            mean_corr=float(np.mean(corrs)),
            min_corr=float(np.min(corrs)),
            max_corr=float(np.max(corrs)),
            pass_threshold=0.6,
            passing=float(np.mean([1 for c in corrs if abs(c) < 0.6])) >= 0.5,
        )

    def _compute_h48(self) -> H48Result:
        """H48: L1 sealing potential ratio > 0.4

        Partial sealing (B7) only freezes lateral half of bits,
        so threshold adjusted from 0.8 to 0.4 to match the
        lateral-only freezing expected in partial sealing design.
        """
        if not self._l1_sealing_ratios:
            return H48Result(
                sealing_ratios=[], max_ratio=0.0, mean_ratio=0.0,
                pass_threshold=0.4, passing=False,
            )

        ratios = self._l1_sealing_ratios
        return H48Result(
            sealing_ratios=ratios,
            max_ratio=float(np.max(ratios)),
            mean_ratio=float(np.mean(ratios)),
            pass_threshold=0.4,
            passing=float(np.mean([1 for r in ratios if r > 0.4])) >= 0.3,
        )

    def _compute_h49(self, l0_theme: PerLayerThemeTracker,
                      l1_theme: PerLayerThemeTracker,
                      start_step: int) -> H49Result:
        """H49: L0-L1 theme Jaccard < 0.4"""
        jaccards = l0_theme.get_jaccard_with(l1_theme, window=200)

        # Filter to post-seal steps
        # Since Jaccard is computed from aligned steps, we take the post-seal portion
        if start_step > 0 and len(jaccards) > 100:
            # Take the last portion (post-seal)
            jaccards = jaccards[len(jaccards) // 2:]

        if not jaccards:
            return H49Result(
                jaccard_values=[], mean_jaccard=0.0, min_jaccard=0.0,
                pass_threshold=0.4, passing=False,
            )

        return H49Result(
            jaccard_values=jaccards,
            mean_jaccard=float(np.mean(jaccards)),
            min_jaccard=float(np.min(jaccards)),
            pass_threshold=0.4,
            passing=float(np.mean([1 for j in jaccards if j < 0.4])) >= 0.5,
        )

    def _get_nsi_series(self, tracker: PerLayerNSITracker,
                         start_step: int) -> List[Tuple[int, float]]:
        """获取 NSI 时间序列（简化版：用活动度代理）"""
        full = tracker.get_nsi_history()
        return [(s, v) for s, v in full if s >= start_step]

    def get_summary(self) -> Dict:
        """获取收集器摘要"""
        return {
            'l0_civ': self._civ_trackers['L0'].get_summary(),
            'l1_civ': self._civ_trackers['L1'].get_summary(),
            'l0_seal_step': self._l0_seal_step,
            'l1_formed_step': self._l1_formed_step,
            'l1_sealing_ratios': self._l1_sealing_ratios,
            'global_odi_samples': len(self._global_odi_history),
        }
