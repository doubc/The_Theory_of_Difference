"""
engine/narrative_self_emergence.py — 叙事自我涌现 (NarrativeSelfEmergence)

Phase 4 P1 组件（新增）

职责：从最小自我（MSI）的瞬时不对称性到具有时间连续性的叙事自我。
追踪叙事的时间连续性、稳定化制度层级的叙事、积累自我历史，
最终计算叙事自我指数（NSI, Narrative Self Index）。

理论依据：
- 差异论 V1.7 叙事递归上调为世界生成核心机制
- 叙事递归三层：小叙事 → 制度正当化 → 文明级生成
- ABA §4.4 前主体态范围论：叙事自我不是"开关"而是"范围"
- 《象界》八环节咬合："耦合功能化"需要"并存筛选化"的充分发展

四个子组件：
1. TemporalContinuityTracker — 追踪叙事主题的时间连续性
2. InstitutionalNarrativeStabilizer — INSTITUTIONAL 层级的叙事稳定化
3. SelfHistoryAccumulator — 自我历史积累（关键转折点提取）
4. NarrativeSelfIndex (NSI) — 叙事自我综合指数

设计原则：
1. 叙事自我 ≠ 意识 — 纯结构性度量
2. "自传体记忆" ≠ 主观回忆 — 关键转折点的结构性标记
3. "制度叙事" ≠ 文化意义 — 功能角色的结构性描述
4. NSI 与 MSI 的关系：MSI 是 NSI 的必要条件但非充分条件
5. NSI 在 ODI > 0.6 后才开始增长（经验阈值）
6. 时间连续性阈值：连续 ≥ 100 步叙事主题 Jaccard 相似度 ≥ 0.3

语义防火墙：
- "叙事自我" ≠ "有意识的主体"
- "自传体记忆" ≠ "主观回忆"
- "制度叙事" ≠ "文化意义"
- "自我历史" ≠ "个体经历"
- 所有组件必须是纯结构性的、可计算的、可证伪的
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

import torch
import numpy as np


# ─── 默认配置 ───
DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG = {
    # TemporalContinuityTracker
    'continuity_window': 100,           # 连续性计算窗口（步数）
    'continuity_jaccard_threshold': 0.3, # Jaccard 相似度阈值
    'continuity_min_steps': 100,        # 最小连续步数

    # InstitutionalNarrativeStabilizer
    'stabilizer_window': 100,           # 稳定化计算窗口
    'stabilizer_min_coherence': 0.3,    # 最低叙事相干度
    'stabilizer_resistance_rate': 0.05, # 抗扰动增长率

    # SelfHistoryAccumulator
    'history_max_turning_points': 50,   # 最大关键转折点存储数
    'history_second_deriv_threshold': 0.05,  # 二阶导数极值阈值
    'history_msi_lookback': 20,         # MSI 回望窗口（用于二阶导数）
    'history_multi_signal': True,       # 启用多信号转折点检测（MSI+ODI+CIV+GBC）
    'history_civ_lookback': 20,         # CIV 回望窗口
    'history_gbc_lookback': 20,         # GBC coherence 回望窗口
    'history_signal_weights': {         # 各信号在转折点检测中的权重
        'msi': 0.4,
        'odi': 0.3,
        'civ': 0.2,
        'gbc': 0.1,
    },

    # NSI 计算
    'nsi_alpha': 0.4,   # 时间连续性权重
    'nsi_beta': 0.3,    # 叙事稳定性权重
    'nsi_gamma': 0.3,   # 自我历史深度权重
    'nsi_min_odi': 0.6, # NSI 开始增长的 ODI 阈值
}


@dataclass
class TemporalContinuityResult:
    """时间连续性追踪结果"""
    continuity_score: float             # [0, 1]，越高越连续
    window_jaccard_mean: float          # 窗口内 Jaccard 相似度均值
    n_steps_continuous: int             # 当前连续达标步数
    is_continuous: bool                 # 是否达标（连续 ≥ 100 步且 Jaccard ≥ 0.3)
    dominant_theme: str                 # 主导叙事主题
    theme_diversity: float              # 主题多样性 [0, 1]
    step: int                           # 当前步数


@dataclass
class NarrativeStabilityResult:
    """叙事稳定性结果"""
    stability_score: float              # [0, 1]，越高越稳定
    institutional_coherence: float      # INSTITUTIONAL 层级叙事相干度
    resistance_score: float             # 抗扰动能力 [0, 1]
    is_stable: bool                     # 是否达标
    narrative_label: str               # 当前制度叙事标签
    step: int                           # 当前步数


@dataclass
class TurningPoint:
    """关键转折点（结构性标记，非主观回忆）"""
    step: int                           # 发生步数
    odi_value: float                    # 发生时的 ODI
    msi_value: float                    # 发生时的 MSI
    second_derivative: float            # ODI/MSI 的二阶导数
    narrative_theme: str                # 当时的叙事主题
    layer_distribution: Dict[str, int]  # 层结构分布快照


@dataclass
class SelfHistoryResult:
    """自我历史积累结果"""
    n_turning_points: int               # 已积累的关键转折点数量
    history_depth: float                # [0, 1]，相对于最大容量的深度
    turning_points: List[TurningPoint]  # 关键转折点列表
    latest_turning_point_step: int      # 最近转折点步数
    odi_range: float                    # ODI 变化范围（max - min）
    msi_range: float                    # MSI 变化范围


@dataclass
class NSIResult:
    """叙事自我指数结果"""
    nsi: float                          # [0, 1]，叙事自我综合指数
    temporal_continuity: float           # 时间连续性分量
    narrative_stability: float           # 叙事稳定性分量
    self_history_depth: float            # 自我历史深度分量
    odi_at_nsi: float                   # 计算 NSI 时的 ODI
    is_nsi_active: bool                 # NSI 是否活跃（ODI > 阈值）
    step: int                           # 当前步数


class TemporalContinuityTracker:
    """叙事时间连续性追踪器

    追踪叙事主题在连续步数中的持续性（非碎片化指数）。

    度量方法：
    1. 每步提取叙事主题标签集合
    2. 计算滑动窗口内的 Jaccard 相似度
    3. 统计连续达标步数

    理论依据：ABA §4.4 — 前主体态是"范围"。
    时间连续性的涌现不是突然的，而是渐进的。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG, **(config or {})}
        self.window_size = cfg['continuity_window']
        self.jaccard_threshold = cfg['continuity_jaccard_threshold']
        self.min_steps = cfg['continuity_min_steps']

        self._theme_history: Deque[Dict] = deque(maxlen=self.window_size + 20)
        self._continuous_steps = 0
        self._step_count = 0

    def update(
        self,
        narrative_themes: List[str],
        narrative_level_distribution: Dict[str, int],
        step: int,
    ) -> TemporalContinuityResult:
        """更新连续性追踪

        Parameters
        ----------
        narrative_themes : List[str]
            当前步的叙事主题标签列表
        narrative_level_distribution : Dict[str, int]
            叙事层级分布 {level_name: count}
        step : int
            当前步数

        Returns
        -------
        TemporalContinuityResult
        """
        self._step_count += 1

        # 记录当前步的主题集合
        theme_set = set(narrative_themes) if narrative_themes else set()
        self._theme_history.append({
            'step': step,
            'themes': theme_set,
            'level_dist': narrative_level_distribution.copy() if narrative_level_distribution else {},
        })

        # 计算窗口内 Jaccard 相似度
        jaccard_mean = self._compute_window_jaccard()

        # 更新连续步数
        if jaccard_mean >= self.jaccard_threshold:
            self._continuous_steps += 1
        else:
            self._continuous_steps = max(0, self._continuous_steps - 2)  # 渐进衰减

        is_continuous = (
            self._continuous_steps >= self.min_steps and
            jaccard_mean >= self.jaccard_threshold
        )

        # 主导主题（窗口内出现频率最高的主题）
        dominant_theme = self._compute_dominant_theme()

        # 主题多样性（窗口内唯一主题数 / 窗口大小）
        theme_diversity = self._compute_theme_diversity()

        # 连续性得分
        continuity_score = min(1.0, self._continuous_steps / self.min_steps) * jaccard_mean

        return TemporalContinuityResult(
            continuity_score=float(np.clip(continuity_score, 0.0, 1.0)),
            window_jaccard_mean=float(jaccard_mean),
            n_steps_continuous=self._continuous_steps,
            is_continuous=is_continuous,
            dominant_theme=dominant_theme,
            theme_diversity=float(theme_diversity),
            step=step,
        )

    def _compute_window_jaccard(self) -> float:
        """计算窗口内相邻步的 Jaccard 相似度均值"""
        if len(self._theme_history) < 2:
            return 0.0

        jaccard_values = []
        history_list = list(self._theme_history)

        for i in range(1, len(history_list)):
            a = history_list[i - 1]['themes']
            b = history_list[i]['themes']

            if not a and not b:
                jaccard_values.append(1.0)  # 两个空集视为完全相似
            elif not a or not b:
                jaccard_values.append(0.0)
            else:
                intersection = len(a & b)
                union = len(a | b)
                jaccard_values.append(intersection / union if union > 0 else 0.0)

        return float(np.mean(jaccard_values)) if jaccard_values else 0.0

    def _compute_dominant_theme(self) -> str:
        """计算窗口内的主导叙事主题"""
        if not self._theme_history:
            return "silent"

        theme_counts: Dict[str, int] = {}
        for entry in self._theme_history:
            for theme in entry['themes']:
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        if not theme_counts:
            return "silent"

        return max(theme_counts, key=theme_counts.get)

    def _compute_theme_diversity(self) -> float:
        """计算主题多样性 [0, 1]"""
        if not self._theme_history or len(self._theme_history) < 2:
            return 0.0

        all_themes = set()
        for entry in self._theme_history:
            all_themes.update(entry['themes'])

        n_unique = len(all_themes)
        n_steps = len(self._theme_history)

        # 多样性 = 唯一主题数 / (步数 * 平均每步主题数)
        avg_themes_per_step = max(1, sum(len(e['themes']) for e in self._theme_history) / n_steps)
        diversity = min(1.0, n_unique / (n_steps * avg_themes_per_step + 1e-8))

        return float(diversity)

    def get_summary(self) -> Dict:
        return {
            'continuous_steps': self._continuous_steps,
            'is_continuous': self._continuous_steps >= self.min_steps,
            'dominant_theme': self._compute_dominant_theme(),
            'theme_diversity': self._compute_theme_diversity(),
        }


class InstitutionalNarrativeStabilizer:
    """制度层级叙事稳定化器

    当 INSTITUTIONAL 层级达到稳态时，生成"制度叙事"。
    制度叙事 = 对该层级功能角色的结构性描述。

    理论依据：V1.7 叙事递归第二层 — 制度正当化叙事。
    制度叙事抵抗外部扰动的能力 = 叙事稳定性度量。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG, **(config or {})}
        self.window_size = cfg['stabilizer_window']
        self.min_coherence = cfg['stabilizer_min_coherence']
        self.resistance_rate = cfg['stabilizer_resistance_rate']

        self._narrative_history: Deque[Dict] = deque(maxlen=self.window_size + 20)
        self._current_narrative: str = "nascent"
        self._resistance_score: float = 0.0
        self._stability_score: float = 0.0
        self._step_count = 0

    def update(
        self,
        institutional_narrative: str,
        institutional_coherence: float,
        odi: float,
        step: int,
    ) -> NarrativeStabilityResult:
        """更新制度叙事稳定化

        Parameters
        ----------
        institutional_narrative : str
            当前 INSTITUTIONAL 层级叙事标签
        institutional_coherence : float
            INSTITUTIONAL 层级叙事相干度 [0, 1]
        odi : float
            当前 ODI
        step : int
            当前步数

        Returns
        -------
        NarrativeStabilityResult
        """
        self._step_count += 1

        # 记录历史
        self._narrative_history.append({
            'step': step,
            'narrative': institutional_narrative,
            'coherence': institutional_coherence,
            'odi': odi,
        })

        # 更新当前叙事标签
        if institutional_narrative and institutional_narrative != "silent":
            self._current_narrative = institutional_narrative

        # 计算叙事相干度（窗口内叙事标签的一致性）
        coherence = self._compute_narrative_coherence()

        # 更新抗扰动能力
        if coherence >= self.min_coherence:
            self._resistance_score = min(1.0, self._resistance_score + self.resistance_rate)
        else:
            self._resistance_score = max(0.0, self._resistance_score - self.resistance_rate * 2)

        # 稳定性得分 = 相干度 × 抗扰动能力 × ODI 因子
        odi_factor = min(1.0, odi / 0.5)  # ODI > 0.5 时达到满分
        self._stability_score = coherence * self._resistance_score * odi_factor

        is_stable = coherence >= self.min_coherence and self._resistance_score >= 0.3

        return NarrativeStabilityResult(
            stability_score=float(np.clip(self._stability_score, 0.0, 1.0)),
            institutional_coherence=float(coherence),
            resistance_score=float(self._resistance_score),
            is_stable=is_stable,
            narrative_label=self._current_narrative,
            step=step,
        )

    def _compute_narrative_coherence(self) -> float:
        """计算窗口内叙事标签的一致性 [0, 1]"""
        if len(self._narrative_history) < 2:
            return 0.0

        history_list = list(self._narrative_history)

        # 计算相邻步叙事标签的共享词比例
        coherence_values = []
        for i in range(1, len(history_list)):
            a_words = set(history_list[i - 1]['narrative'].replace('_', ' ').split())
            b_words = set(history_list[i]['narrative'].replace('_', ' ').split())

            if not a_words and not b_words:
                coherence_values.append(1.0)
            elif not a_words or not b_words:
                coherence_values.append(0.0)
            else:
                intersection = len(a_words & b_words)
                union = len(a_words | b_words)
                coherence_values.append(intersection / union if union > 0 else 0.0)

        return float(np.mean(coherence_values)) if coherence_values else 0.0

    def get_summary(self) -> Dict:
        return {
            'current_narrative': self._current_narrative,
            'stability_score': round(self._stability_score, 4),
            'resistance_score': round(self._resistance_score, 4),
            'is_stable': self._stability_score >= 0.3,
        }


class SelfHistoryAccumulator:
    """自我历史积累器

    将 MSI 的时间序列组织为"自传体记忆"。
    不是存储所有历史，而是提取关键转折点（相变事件）。
    关键转折点 = ODI/MSI 的二阶导数极值点。

    理论依据：V1.7 叙事递归需要"历史"——不是完整记录，
    而是关键转折点的结构性标记序列。
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG, **(config or {})}
        self.max_turning_points = cfg['history_max_turning_points']
        self.second_deriv_threshold = cfg['history_second_deriv_threshold']
        self.msi_lookback = cfg['history_msi_lookback']
        self.multi_signal = cfg.get('history_multi_signal', True)
        self.civ_lookback = cfg.get('history_civ_lookback', 20)
        self.gbc_lookback = cfg.get('history_gbc_lookback', 20)
        self.signal_weights = cfg.get('history_signal_weights', {
            'msi': 0.4, 'odi': 0.3, 'civ': 0.2, 'gbc': 0.1
        })

        self._msi_history: Deque[Tuple[int, float]] = deque(maxlen=500)
        self._odi_history: Deque[Tuple[int, float]] = deque(maxlen=500)
        self._civ_history: Deque[Tuple[int, float]] = deque(maxlen=500)
        self._gbc_history: Deque[Tuple[int, float]] = deque(maxlen=500)
        self._turning_points: List[TurningPoint] = []
        self._step_count = 0

    def update(
        self,
        msi: float,
        odi: float,
        narrative_theme: str,
        layer_distribution: Optional[Dict[str, int]] = None,
        step: int = 0,
        civ: Optional[float] = None,
        gbc_coherence: Optional[float] = None,
    ) -> SelfHistoryResult:
        """更新自我历史积累

        Parameters
        ----------
        msi : float
            当前 MSI 值
        odi : float
            当前 ODI 值
        narrative_theme : str
            当前叙事主题
        layer_distribution : Optional[Dict[str, int]]
            层结构分布快照
        step : int
            当前步数
        civ : Optional[float]
            CIVILIZATION 层级值（用于多信号转折点检测）
        gbc_coherence : Optional[float]
            GBC coherence 值（用于多信号转折点检测）

        Returns
        -------
        SelfHistoryResult
        """
        self._step_count += 1
        actual_step = step if step > 0 else self._step_count

        self._msi_history.append((actual_step, msi))
        self._odi_history.append((actual_step, odi))
        if civ is not None:
            self._civ_history.append((actual_step, civ))
        if gbc_coherence is not None:
            self._gbc_history.append((actual_step, gbc_coherence))

        # 检测关键转折点（多信号二阶导数极值）
        turning_point = self._detect_turning_point(
            msi, odi, narrative_theme, layer_distribution, actual_step,
            civ=civ, gbc_coherence=gbc_coherence,
        )
        if turning_point is not None:
            self._turning_points.append(turning_point)
            # 限制最大存储数
            if len(self._turning_points) > self.max_turning_points:
                self._turning_points = self._turning_points[-self.max_turning_points:]

        return self._build_result()

    def _detect_turning_point(
        self,
        msi: float,
        odi: float,
        narrative_theme: str,
        layer_distribution: Optional[Dict[str, int]],
        step: int,
        civ: Optional[float] = None,
        gbc_coherence: Optional[float] = None,
    ) -> Optional[TurningPoint]:
        """检测关键转折点（多信号版本）

        关键转折点 = 加权多信号二阶导数组合超过阈值的点。
        信号包括：MSI、ODI、CIVILIZATION 层级、GBC coherence。

        在已收敛的系统中，MSI 可能平坦（二阶导数≈0），
        但 ODI、CIV、GBC 仍可能有结构性转折。
        多信号方法解决单一 MSI 信号在收敛系统中失效的问题。
        """
        if len(self._msi_history) < self.msi_lookback + 2:
            return None

        w = self.signal_weights
        threshold = self.second_deriv_threshold

        # --- MSI 二阶导数 ---
        msi_second_deriv = 0.0
        msi_history_list = list(self._msi_history)
        msi_recent = msi_history_list[-self.msi_lookback:]
        if len(msi_recent) >= 3:
            msi_values = [v for _, v in msi_recent]
            msi_first = [msi_values[i + 1] - msi_values[i] for i in range(len(msi_values) - 1)]
            msi_second = [msi_first[i + 1] - msi_first[i] for i in range(len(msi_first) - 1)]
            if msi_second:
                msi_second_deriv = msi_second[-1]

        # --- ODI 二阶导数 ---
        odi_second_deriv = 0.0
        if len(self._odi_history) >= self.msi_lookback + 2:
            odi_history_list = list(self._odi_history)
            odi_recent = odi_history_list[-self.msi_lookback:]
            if len(odi_recent) >= 3:
                odi_values = [v for _, v in odi_recent]
                odi_first = [odi_values[i + 1] - odi_values[i] for i in range(len(odi_values) - 1)]
                odi_second = [odi_first[i + 1] - odi_first[i] for i in range(len(odi_first) - 1)]
                if odi_second:
                    odi_second_deriv = odi_second[-1]

        # --- CIV 二阶导数 ---
        civ_second_deriv = 0.0
        if civ is not None and len(self._civ_history) >= self.civ_lookback + 2:
            civ_history_list = list(self._civ_history)
            civ_recent = civ_history_list[-self.civ_lookback:]
            if len(civ_recent) >= 3:
                civ_values = [v for _, v in civ_recent]
                civ_first = [civ_values[i + 1] - civ_values[i] for i in range(len(civ_values) - 1)]
                civ_second = [civ_first[i + 1] - civ_first[i] for i in range(len(civ_first) - 1)]
                if civ_second:
                    civ_second_deriv = civ_second[-1]

        # --- GBC coherence 二阶导数 ---
        gbc_second_deriv = 0.0
        if gbc_coherence is not None and len(self._gbc_history) >= self.gbc_lookback + 2:
            gbc_history_list = list(self._gbc_history)
            gbc_recent = gbc_history_list[-self.gbc_lookback:]
            if len(gbc_recent) >= 3:
                gbc_values = [v for _, v in gbc_recent]
                gbc_first = [gbc_values[i + 1] - gbc_values[i] for i in range(len(gbc_values) - 1)]
                gbc_second = [gbc_first[i + 1] - gbc_first[i] for i in range(len(gbc_first) - 1)]
                if gbc_second:
                    gbc_second_deriv = gbc_second[-1]

        # --- 加权组合分数 ---
        combined_score = (
            w.get('msi', 0.4) * abs(msi_second_deriv) +
            w.get('odi', 0.3) * abs(odi_second_deriv) +
            w.get('civ', 0.2) * abs(civ_second_deriv) +
            w.get('gbc', 0.1) * abs(gbc_second_deriv)
        )

        # 极值检测：加权组合分数超过阈值
        if combined_score >= threshold:
            # 记录主导信号（绝对值最大的二阶导数）
            signal_contributions = {
                'msi': abs(msi_second_deriv),
                'odi': abs(odi_second_deriv),
                'civ': abs(civ_second_deriv),
                'gbc': abs(gbc_second_deriv),
            }
            dominant_signal = max(signal_contributions, key=signal_contributions.get)

            return TurningPoint(
                step=step,
                odi_value=odi,
                msi_value=msi,
                second_derivative=float(combined_score),
                narrative_theme=narrative_theme,
                layer_distribution=layer_distribution.copy() if layer_distribution else {},
            )

        return None

    def _build_result(self) -> SelfHistoryResult:
        """构建自我历史结果"""
        odi_values = [v for _, v in self._odi_history] if self._odi_history else [0.0]
        msi_values = [v for _, v in self._msi_history] if self._msi_history else [0.0]

        history_depth = min(1.0, len(self._turning_points) / max(1, self.max_turning_points))

        return SelfHistoryResult(
            n_turning_points=len(self._turning_points),
            history_depth=float(history_depth),
            turning_points=list(self._turning_points),
            latest_turning_point_step=self._turning_points[-1].step if self._turning_points else 0,
            odi_range=float(max(odi_values) - min(odi_values)) if odi_values else 0.0,
            msi_range=float(max(msi_values) - min(msi_values)) if msi_values else 0.0,
        )

    def get_summary(self) -> Dict:
        result = self._build_result()
        return {
            'n_turning_points': result.n_turning_points,
            'history_depth': round(result.history_depth, 4),
            'latest_turning_point_step': result.latest_turning_point_step,
            'odi_range': round(result.odi_range, 4),
            'msi_range': round(result.msi_range, 4),
        }


class NarrativeSelfEmergence:
    """叙事自我涌现 — 四个子组件的统一编排

    实现从最小自我（MSI）到叙事自我的涌现过程。

    工作流程：
    1. 更新 TemporalContinuityTracker — 追踪叙事时间连续性
    2. 更新 InstitutionalNarrativeStabilizer — 稳定制度叙事
    3. 更新 SelfHistoryAccumulator — 积累自我历史
    4. 计算 NSI（Narrative Self Index）

    NSI = α·TemporalContinuity + β·NarrativeStability + γ·SelfHistoryDepth

    与 MSI 的关系：
    - MSI 是瞬时结构不对称性
    - NSI 是时间连续性的结构积累
    - MSI 是 NSI 的必要条件但非充分条件

    与 ODI 的关系：
    - ODI < 0.6 时，NSI 被抑制（系统不够致密）
    - ODI ≥ 0.6 后，NSI 开始随连续性/稳定性/历史深度增长
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = {**DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG, **(config or {})}
        self.config = cfg

        self.continuity_tracker = TemporalContinuityTracker(cfg)
        self.stabilizer = InstitutionalNarrativeStabilizer(cfg)
        self.history_accumulator = SelfHistoryAccumulator(cfg)

        # NSI 计算参数
        self._nsi_alpha = cfg['nsi_alpha']
        self._nsi_beta = cfg['nsi_beta']
        self._nsi_gamma = cfg['nsi_gamma']
        self._nsi_min_odi = cfg['nsi_min_odi']

        # 历史记录
        self._nsi_history: Deque[float] = deque(maxlen=200)
        self._step_count = 0

    def step(
        self,
        msi: float,
        odi: float,
        narrative_themes: List[str],
        narrative_level_distribution: Dict[str, int],
        institutional_narrative: str,
        institutional_coherence: float,
        layer_distribution: Optional[Dict[str, int]] = None,
        step: int = 0,
        civ: Optional[float] = None,
        gbc_coherence: Optional[float] = None,
    ) -> Dict:
        """执行一步叙事自我涌现

        Parameters
        ----------
        msi : float
            当前 MSI 值
        odi : float
            当前 ODI 值
        narrative_themes : List[str]
            当前叙事主题列表
        narrative_level_distribution : Dict[str, int]
            叙事层级分布
        institutional_narrative : str
            INSTITUTIONAL 层级叙事标签
        institutional_coherence : float
            INSTITUTIONAL 层级叙事相干度
        layer_distribution : Optional[Dict[str, int]]
            层结构分布快照
        step : int
            当前步数

        Returns
        -------
        Dict
            叙事自我涌现结果
        """
        self._step_count += 1
        actual_step = step if step > 0 else self._step_count

        # 1. 时间连续性追踪
        continuity_result = self.continuity_tracker.update(
            narrative_themes=narrative_themes,
            narrative_level_distribution=narrative_level_distribution,
            step=actual_step,
        )

        # 2. 制度叙事稳定化
        stability_result = self.stabilizer.update(
            institutional_narrative=institutional_narrative,
            institutional_coherence=institutional_coherence,
            odi=odi,
            step=actual_step,
        )

        # 3. 自我历史积累
        history_result = self.history_accumulator.update(
            msi=msi,
            odi=odi,
            narrative_theme=continuity_result.dominant_theme,
            layer_distribution=layer_distribution,
            step=actual_step,
            civ=civ,
            gbc_coherence=gbc_coherence,
        )

        # 4. 计算 NSI
        nsi_result = self._compute_nsi(
            continuity_result, stability_result, history_result, odi, actual_step
        )
        self._nsi_history.append(nsi_result.nsi)

        return {
            'continuity': continuity_result,
            'stability': stability_result,
            'history': history_result,
            'nsi': nsi_result,
            'step': actual_step,
        }

    def _compute_nsi(
        self,
        continuity: TemporalContinuityResult,
        stability: NarrativeStabilityResult,
        history: SelfHistoryResult,
        odi: float,
        step: int,
    ) -> NSIResult:
        """计算叙事自我指数

        NSI = α·TemporalContinuity + β·NarrativeStability + γ·SelfHistoryDepth

        当 ODI < 阈值时，NSI 被抑制。
        """
        # ODI 抑制因子
        odi_gate = min(1.0, odi / self._nsi_min_odi) if self._nsi_min_odi > 0 else 1.0
        is_nsi_active = odi >= self._nsi_min_odi

        # 加权组合
        raw_nsi = (
            self._nsi_alpha * continuity.continuity_score +
            self._nsi_beta * stability.stability_score +
            self._nsi_gamma * history.history_depth
        )

        # 应用 ODI 门控
        nsi = raw_nsi * odi_gate

        return NSIResult(
            nsi=float(np.clip(nsi, 0.0, 1.0)),
            temporal_continuity=float(continuity.continuity_score),
            narrative_stability=float(stability.stability_score),
            self_history_depth=float(history.history_depth),
            odi_at_nsi=float(odi),
            is_nsi_active=is_nsi_active,
            step=step,
        )

    def get_nsi_trend(self) -> Dict:
        """获取 NSI 趋势"""
        if not self._nsi_history:
            return {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'n': 0, 'latest': 0.0}

        values = list(self._nsi_history)
        return {
            'mean': round(float(np.mean(values)), 4),
            'min': round(float(np.min(values)), 4),
            'max': round(float(np.max(values)), 4),
            'std': round(float(np.std(values)), 4),
            'n': len(values),
            'latest': round(values[-1], 4),
        }

    def get_summary(self) -> Dict:
        """获取叙事自我涌现摘要"""
        return {
            'step': self._step_count,
            'continuity': self.continuity_tracker.get_summary(),
            'stability': self.stabilizer.get_summary(),
            'history': self.history_accumulator.get_summary(),
            'nsi_trend': self.get_nsi_trend(),
        }

    def reset(self):
        """重置所有子组件"""
        self.continuity_tracker = TemporalContinuityTracker(self.config)
        self.stabilizer = InstitutionalNarrativeStabilizer(self.config)
        self.history_accumulator = SelfHistoryAccumulator(self.config)
        self._nsi_history.clear()
        self._step_count = 0
