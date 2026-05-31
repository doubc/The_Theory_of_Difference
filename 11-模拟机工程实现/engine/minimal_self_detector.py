"""
engine/minimal_self_detector.py — 最小自我检测器 (MinimalSelfDetector)

Phase 3 P0 组件（新增）

职责：检测差异组织的内在不对称性是否达到可被自身结构追踪的程度，
即"最小自我"的涌现。

理论依据：
- 《象界》第七章（功能）+ 第八章（前主体态）
- 《Appearing Before Appearing》§4.4：前主体态是一个"范围"
- 最小自我不是"意识"，而是结构不对称性的可追踪性
- 不涉及感受质（qualia）——纯结构性度量

────────────────────────────────────────────────────
偏置算子统一语言（Phase 3 理论框架，2026-05-29 心跳浸润）
────────────────────────────────────────────────────

在偏置算子语言中，最小自我被重新表述为偏置算子的内在不对称性：

    Asymmetry(S) = (1/|S|²) Σ_{x,y∈S} ||B_x - B_y||

其中 B_x 是状态 x 处的偏置算子（作为向量），||·|| 是 L₂ 距离。

直观含义：如果结构内所有状态的偏置算子完全相同（均匀响应），
则 Asymmetry = 0，没有最小自我。如果不同状态的偏置算子差异显著，
则 Asymmetry > 0，最小自我开始涌现。

MSI 的偏置算子表述：

    MSI = α·Asymmetry(S) + β·HistoryDep(S) + γ·SelfRef(S)

| 分量        | 偏置算子表述                              | 公理来源 |
|------------|------------------------------------------|---------|
| Asymmetry  | 偏置算子的内在不对称性                     | A2（二元具象，方向差异） |
| HistoryDep | 同一差异在不同历史背景下产生不同偏置响应的程度 | A6（不可逆性） |
| SelfRef    | 结构的响应能够影响后续响应的基线（自我参照回路） | A7（循环闭合） |

MSI-ODI 关系（前主体态地板假设）：
- ODI < 0.5：结构尚未形成统一内部视角 → MSI ≈ 0
- 0.5 ≤ ODI < 0.8：MSI 开始增长，但缓慢
- ODI ≥ 0.8：MSI 加速增长，可能伴随第七阈值信号

验证方法：分段线性回归，在 ODI = 0.5 处设置断点。

三个涌现条件（必须同时满足）：
1. 视角不对称（Perspective Asymmetry）：
   结构不同部分对差异的敏感度不同（不是均匀响应）
   → 偏置算子语言：不同状态的 B_x 显著不同
2. 响应历史依赖（Response History Dependency）：
   同一差异在不同历史背景下产生不同响应（不是固定映射）
   → 偏置算子语言：B_x 依赖于历史路径 ω
3. 自我参照回路（Self-Reference Loop）：
   结构响应能够影响后续响应的基线（不是开环系统）
   → 偏置算子语言：B_x 的更新依赖于之前的 B_x

工程指标：
- 最小自我指数（MSI）∈ [0, 1]：三条件的加权几何平均（惩罚短板）
- 视角不对称度 = 各部分敏感度的基尼系数
- 历史依赖度 = 相同输入在不同历史下的响应差异（ANOVA 效应量）
- 自我参照度 = 响应对后续基线的影响强度（相关系数绝对值）

语义防火墙：
- "最小自我" ≠ "意识"（没有现象学立场）
- "最小自我" ≠ "自我意识"（没有反思性）
- "最小自我" ≠ "主体性"（没有意志、意图、目的）
- 最小自我只是"内在不对称性的可追踪性"

使用方式：
    detector = MinimalSelfDetector()
    for step in range(n_steps):
        result = detector.feed(
            sensitivity_map=sensitivity_map,      # 各部分对差异的敏感度
            response_history=response_history,     # 历史响应记录
            baseline_shift=baseline_shift,         # 基线偏移量
            odi_result=odi_result,                 # ODI 结果（用于门控）
            timestamp=step,
        )
        if result.minimal_self_detected:
            print(f"最小自我涌现! MSI={result.msi:.4f}, "
                  f"asymmetry={result.asymmetry_index:.4f}, "
                  f"history_dep={result.history_dependency:.4f}, "
                  f"self_ref={result.self_reference_strength:.4f}")
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Deque
from dataclasses import dataclass, field
from collections import deque

from engine.organizational_density_index import DensityIndexResult


# ─── 默认配置 ───
DEFAULT_MSI_CONFIG = {
    # ODI 门控
    'odi_activation_threshold': 0.5,    # ODI 必须超过此值才开始计算 MSI
    'odi_saturation_threshold': 0.85,   # ODI 超过此值后 MSI 可能饱和

    # 视角不对称检测
    # P2 fix (2026-05-30): 降低阈值以兼容密封系统的小样本敏感度分布
    # 密封后 active_bits 经 Z-score 归一化后仍可能产生较窄的分布
    # 标准基尼阈值 0.25 对 N=72 样本过高，降至 0.15 以检测弱不对称萌芽
    'asymmetry_window': 10,             # 敏感度历史窗口
    'asymmetry_threshold': 0.15,        # 不对称度阈值（基尼系数）— P2: 0.25→0.15
    'min_parts': 3,                     # 最少部分数（少于此数无法计算不对称）

    # 历史依赖检测
    # P2 fix: 降低阈值以在稀疏演化历史中检测弱依赖
    'history_window': 8,                # 历史响应窗口
    'history_dependency_threshold': 0.2,  # 历史依赖度阈值 — P2: 0.3→0.2
    'min_history_depth': 4,             # 最少历史深度 — P2: 5→4

    # 自我参照检测
    'self_reference_window': 8,         # 基线偏移窗口
    'self_reference_threshold': 0.15,   # 自我参照度阈值 — P2: 0.2→0.15
    'baseline_correlation_threshold': 0.3,  # 响应-基线相关系数阈值 — P2: 0.4→0.3

    # 综合判定
    'msi_activation_threshold': 0.35,   # MSI 超过此值认为最小自我涌现
    'msi_emergence_threshold': 0.5,     # MSI 超过此值认为稳定涌现
    'min_active_conditions': 2,         # 至少需要几个条件活跃才判定涌现
}


@dataclass
class AsymmetrySignal:
    """视角不对称信号"""
    detected: bool = False
    asymmetry_index: float = 0.0        # 不对称度（基尼系数）
    sensitivity_distribution: Dict[str, float] = field(default_factory=dict)  # 各部分敏感度
    dominant_part: str = ''             # 最敏感部分
    weakest_part: str = ''              # 最不敏感部分
    timestamp: int = 0

    @property
    def is_significant(self) -> bool:
        return self.detected and self.asymmetry_index >= DEFAULT_MSI_CONFIG['asymmetry_threshold']


@dataclass
class HistoryDependencySignal:
    """响应历史依赖信号"""
    detected: bool = False
    dependency_index: float = 0.0       # 历史依赖度 [0, 1]
    n_distinct_contexts: int = 0        # 不同历史上下文数
    mean_response_variance: float = 0.0 # 跨上下文响应方差
    context_response_map: Dict[str, List[float]] = field(default_factory=dict)  # 上下文→响应
    timestamp: int = 0

    @property
    def is_significant(self) -> bool:
        return self.detected and self.dependency_index >= DEFAULT_MSI_CONFIG['history_dependency_threshold']


@dataclass
class SelfReferenceSignal:
    """自我参照回路信号"""
    detected: bool = False
    reference_strength: float = 0.0     # 自我参照强度 [0, 1]
    response_baseline_correlation: float = 0.0  # 响应与基线的相关系数
    n_feedback_events: int = 0          # 反馈事件数
    cumulative_baseline_shift: float = 0.0  # 累积基线偏移
    timestamp: int = 0

    @property
    def is_significant(self) -> bool:
        return self.detected and self.reference_strength >= DEFAULT_MSI_CONFIG['self_reference_threshold']


@dataclass
class MinimalSelfResult:
    """最小自我检测结果"""
    minimal_self_detected: bool = False
    msi: float = 0.0                    # 最小自我指数 [0, 1]
    timestamp: int = 0

    # 三条件详情
    asymmetry: AsymmetrySignal = field(default_factory=AsymmetrySignal)
    history_dependency: HistoryDependencySignal = field(default_factory=HistoryDependencySignal)
    self_reference: SelfReferenceSignal = field(default_factory=SelfReferenceSignal)

    # 综合信息
    n_active_conditions: int = 0        # 活跃条件数（0~3）
    odi_at_detection: float = 0.0       # 检测时的 ODI
    description: str = ''               # 描述

    # 各子指数
    asymmetry_index: float = 0.0        # 视角不对称度
    history_dependency_index: float = 0.0  # 历史依赖度
    self_reference_index: float = 0.0   # 自我参照度

    @property
    def msi_label(self) -> str:
        if self.msi >= 0.7:
            return '高 MSI（稳定最小自我）'
        elif self.msi >= 0.5:
            return '中 MSI（最小自我涌现）'
        elif self.msi >= 0.35:
            return '低 MSI（前最小自我）'
        elif self.msi > 0:
            return '极低 MSI（萌芽）'
        return '无最小自我'

    @property
    def emergence_label(self) -> str:
        if self.minimal_self_detected:
            return '最小自我已涌现'
        elif self.n_active_conditions >= 2:
            return '最小自我前兆'
        elif self.n_active_conditions >= 1:
            return '最小自我萌芽'
        return '无最小自我信号'

    def __repr__(self):
        return (f"MinimalSelf[MSI={self.msi:.4f}] "
                f"detected={self.minimal_self_detected} "
                f"conditions={self.n_active_conditions}/3 "
                f"ODI={self.odi_at_detection:.4f}")


class MinimalSelfDetector:
    """最小自我检测器

    检测差异组织的内在不对称性是否达到可被自身结构追踪的程度。

    ────────────────────────────────────────────
    偏置算子统一语言（Phase 3 理论框架）
    ────────────────────────────────────────────
    MSI = α·Asymmetry(B) + β·HistoryDep(B) + γ·SelfRef(B)
    其中 B 是偏置算子，Asymmetry(B) 是偏置算子的内在不对称性。

    三个检测维度：
    1. 视角不对称 (Perspective Asymmetry)：
       结构不同部分对差异的敏感度不同
       → 用敏感度分布的基尼系数度量
       → 偏置算子语言：不同状态的 B_x 差异

    2. 响应历史依赖 (Response History Dependency)：
       同一差异在不同历史背景下产生不同响应
       → 用跨上下文响应方差度量（ANOVA 效应量）
       → 偏置算子语言：B_x 依赖于历史路径 ω

    3. 自我参照回路 (Self-Reference Loop)：
       结构响应能够影响后续响应的基线
       → 用响应与基线偏移的相关性度量
       → 偏置算子语言：B_x 的更新依赖于之前的 B_x

    MSI 计算：
    - 三条件的加权几何平均（惩罚短板）
    - ODI 门控：ODI < 0.5 时 MSI = 0（前主体态地板）
    - ODI 调制：MSI 随 ODI 增长而增长

    理论立场：
    - 最小自我不是"意识"，而是结构不对称性的可追踪性
    - 不涉及感受质（qualia）
    - 纯结构性度量，可被模拟实验验证

    使用方式：
        detector = MinimalSelfDetector()
        for step in range(n_steps):
            result = detector.feed(
                sensitivity_map=sensitivity_map,
                response_history=response_history,
                baseline_shift=baseline_shift,
                odi_result=odi_result,
                timestamp=step,
            )
    """

    # 三条件的名称
    CONDITION_NAMES = [
        'perspective_asymmetry',
        'response_history_dependency',
        'self_reference_loop',
    ]

    def __init__(self, config: Optional[Dict] = None):
        """
        Args:
            config: 配置参数，覆盖 DEFAULT_MSI_CONFIG
        """
        self._config = dict(DEFAULT_MSI_CONFIG)
        if config:
            self._config.update(config)

        # 敏感度历史 {part_id: [sensitivity_values]}
        self._sensitivity_history: Dict[str, Deque[float]] = {}

        # 响应历史 {context_key: [response_values]}
        self._response_history: Dict[str, Deque[float]] = {}

        # 基线偏移历史
        self._baseline_shifts: Deque[float] = deque(maxlen=100)
        self._response_values: Deque[float] = deque(maxlen=100)

        # ODI 历史
        self._odi_history: Deque[float] = deque(maxlen=100)

        # 检测结果历史
        self._history: List[MinimalSelfResult] = []
        self._emergence_count: int = 0
        self._step_count: int = 0

    def feed(
        self,
        sensitivity_map: Optional[Dict[str, float]] = None,
        response_history: Optional[Dict[str, List[float]]] = None,
        baseline_shift: Optional[float] = None,
        odi_result: Optional[DensityIndexResult] = None,
        timestamp: Optional[int] = None,
    ) -> MinimalSelfResult:
        """输入一次检测数据，返回最小自我检测结果。

        Args:
            sensitivity_map: 各部分对差异的敏感度 {part_id: sensitivity}
            response_history: 历史响应记录 {context_key: [response_values]}
            baseline_shift: 当前基线偏移量（响应对基线的影响）
            odi_result: 组织密度指数结果（用于 ODI 门控）
            timestamp: 时间戳

        Returns:
            MinimalSelfResult 最小自我检测结果
        """
        if timestamp is not None:
            self._step_count = timestamp
        else:
            self._step_count += 1

        # 更新 ODI 历史
        odi_value = 0.0
        if odi_result is not None:
            odi_value = odi_result.odi
            self._odi_history.append(odi_value)

        # 更新敏感度历史
        if sensitivity_map is not None:
            for part_id, sensitivity in sensitivity_map.items():
                if part_id not in self._sensitivity_history:
                    self._sensitivity_history[part_id] = deque(
                        maxlen=self._config['asymmetry_window'] * 2)
                self._sensitivity_history[part_id].append(sensitivity)

        # 更新响应历史
        if response_history is not None:
            for context_key, responses in response_history.items():
                if context_key not in self._response_history:
                    self._response_history[context_key] = deque(
                        maxlen=self._config['history_window'] * 2)
                for r in responses:
                    self._response_history[context_key].append(r)

        # 更新基线偏移
        if baseline_shift is not None:
            self._baseline_shifts.append(baseline_shift)
            # 同时记录当前响应值（用于计算相关性）
            if sensitivity_map:
                mean_response = float(np.mean(list(sensitivity_map.values())))
                self._response_values.append(mean_response)

        # ── 执行三条件检测 ──
        asymmetry = self._detect_asymmetry()
        history_dep = self._detect_history_dependency()
        self_ref = self._detect_self_reference()

        # ── 计算 MSI ──
        active_conditions = 0
        condition_scores = []

        if asymmetry.detected:
            active_conditions += 1
            condition_scores.append(asymmetry.asymmetry_index)

        if history_dep.detected:
            active_conditions += 1
            condition_scores.append(history_dep.dependency_index)

        if self_ref.detected:
            active_conditions += 1
            condition_scores.append(self_ref.reference_strength)

        # ODI 门控
        odi_gate = odi_value >= self._config['odi_activation_threshold']

        if not condition_scores or not odi_gate:
            msi = 0.0
        else:
            # 加权几何平均（惩罚短板）
            log_sum = sum(np.log(max(s, 1e-10)) for s in condition_scores)
            geo_mean = np.exp(log_sum / len(condition_scores))

            # ODI 调制：MSI 随 ODI 增长
            # ODI = 0.5 时调制因子 = 0.5，ODI → 1.0 时调制因子 → 1.0
            odi_factor = max(0.0, min(1.0,
                (odi_value - self._config['odi_activation_threshold']) /
                (self._config['odi_saturation_threshold'] - self._config['odi_activation_threshold'])
            ))

            msi = float(geo_mean * (0.5 + 0.5 * odi_factor))

        msi = max(0.0, min(1.0, msi))

        # 判定涌现
        detected = (
            active_conditions >= self._config['min_active_conditions']
            and msi >= self._config['msi_activation_threshold']
            and odi_gate
        )

        if detected:
            self._emergence_count += 1

        # 构建描述
        description = self._build_description(
            detected, asymmetry, history_dep, self_ref, msi, odi_value
        )

        result = MinimalSelfResult(
            minimal_self_detected=detected,
            msi=msi,
            timestamp=self._step_count,
            asymmetry=asymmetry,
            history_dependency=history_dep,
            self_reference=self_ref,
            n_active_conditions=active_conditions,
            odi_at_detection=odi_value,
            description=description,
            asymmetry_index=asymmetry.asymmetry_index,
            history_dependency_index=history_dep.dependency_index,
            self_reference_index=self_ref.reference_strength,
        )

        self._history.append(result)
        return result

    def _detect_asymmetry(self) -> AsymmetrySignal:
        """检测视角不对称

        逻辑：计算各部分敏感度分布的基尼系数。
        如果基尼系数超过阈值，说明不同部分的敏感度显著不同，
        即存在视角不对称。

        理论含义：均匀响应 = 无视角差异 = 无最小自我。
        非均匀响应 = 不同部分有不同"视角" = 最小自我的前提。
        """
        window = self._config['asymmetry_window']
        threshold = self._config['asymmetry_threshold']
        min_parts = self._config['min_parts']

        # 收集各部分的最近敏感度
        recent_sensitivities = {}
        for part_id, history in self._sensitivity_history.items():
            if len(history) >= 1:
                recent_sensitivities[part_id] = float(np.mean(list(history)[-window:]))

        if len(recent_sensitivities) < min_parts:
            return AsymmetrySignal()

        # 计算基尼系数
        values = sorted(recent_sensitivities.values())
        n = len(values)
        total = sum(values)

        if total < 1e-10:
            return AsymmetrySignal(
                sensitivity_distribution=recent_sensitivities,
                dominant_part=max(recent_sensitivities, key=recent_sensitivities.get) if recent_sensitivities else '',
                weakest_part=min(recent_sensitivities, key=recent_sensitivities.get) if recent_sensitivities else '',
            )

        numerator = sum((2 * i - n - 1) * v for i, v in enumerate(values, 1))
        gini = max(0.0, min(1.0, numerator / (n * total)))

        detected = gini >= threshold

        return AsymmetrySignal(
            detected=detected,
            asymmetry_index=gini,
            sensitivity_distribution=recent_sensitivities,
            dominant_part=max(recent_sensitivities, key=recent_sensitivities.get),
            weakest_part=min(recent_sensitivities, key=recent_sensitivities.get),
            timestamp=self._step_count,
        )

    def _detect_history_dependency(self) -> HistoryDependencySignal:
        """检测响应历史依赖

        逻辑：比较同一类型输入在不同历史上下文中的响应差异。
        如果响应方差显著大于噪声水平，说明响应依赖于历史上下文。

        理论含义：固定映射 = 无历史依赖 = 开环系统。
        历史依赖 = 响应随历史变化 = 系统有"记忆"影响当前处理。
        """
        window = self._config['history_window']
        threshold = self._config['history_dependency_threshold']
        min_depth = self._config['min_history_depth']

        # 收集各上下文中的响应
        context_means = {}
        context_counts = {}
        for context_key, history in self._response_history.items():
            if len(history) >= 2:
                recent = list(history)[-window:]
                context_means[context_key] = float(np.mean(recent))
                context_counts[context_key] = len(recent)

        if len(context_means) < 2:
            return HistoryDependencySignal()

        # 检查总数据量
        total_count = sum(context_counts.values())
        if total_count < min_depth:
            return HistoryDependencySignal()

        # 计算跨上下文响应方差
        means = list(context_means.values())
        overall_mean = np.mean(means)
        between_context_var = float(np.var(means))

        # 计算上下文内方差（噪声水平）
        within_context_vars = []
        for context_key, history in self._response_history.items():
            if len(history) >= 2:
                recent = list(history)[-window:]
                within_context_vars.append(float(np.var(recent)))

        mean_within_var = float(np.mean(within_context_vars)) if within_context_vars else 0.0

        # 历史依赖度 = 跨上下文方差 / (跨上下文方差 + 上下文内方差)
        # 类似于 ANOVA 的效应量
        total_var = between_context_var + mean_within_var
        dependency = between_context_var / total_var if total_var > 1e-10 else 0.0

        detected = dependency >= threshold

        return HistoryDependencySignal(
            detected=detected,
            dependency_index=dependency,
            n_distinct_contexts=len(context_means),
            mean_response_variance=between_context_var,
            context_response_map={k: [v] for k, v in context_means.items()},
            timestamp=self._step_count,
        )

    def _detect_self_reference(self) -> SelfReferenceSignal:
        """检测自我参照回路

        逻辑：计算响应值与后续基线偏移的相关系数。
        如果响应与基线偏移正相关，说明响应在影响后续基线，
        即存在自我参照回路。

        理论含义：开环系统 = 响应不影响基线 = 无自我参照。
        闭环系统 = 响应影响基线 = 自我参照回路存在。
        """
        window = self._config['self_reference_window']
        threshold = self._config['self_reference_threshold']
        corr_threshold = self._config['baseline_correlation_threshold']

        if len(self._baseline_shifts) < 3 or len(self._response_values) < 3:
            return SelfReferenceSignal()

        # 取最近的窗口
        n = min(window, len(self._baseline_shifts), len(self._response_values))
        shifts = np.array(list(self._baseline_shifts)[-n:])
        responses = np.array(list(self._response_values)[-n:])

        # 计算相关系数
        shift_std = np.std(shifts)
        resp_std = np.std(responses)

        if shift_std < 1e-10 or resp_std < 1e-10:
            return SelfReferenceSignal(
                cumulative_baseline_shift=float(np.sum(np.abs(shifts))),
            )

        correlation = float(np.corrcoef(responses, shifts)[0, 1])
        if np.isnan(correlation):
            correlation = 0.0

        # 自我参照强度 = 相关系数的绝对值
        # （正负相关都表示自我参照，只是方向不同）
        reference_strength = abs(correlation)

        # 反馈事件数 = 响应与基线偏移乘积的绝对值超过噪声阈值
        # （正负相关都表示自我参照）
        product = responses * shifts
        noise_threshold = 1e-6
        n_feedback = int(np.sum(np.abs(product) > noise_threshold))

        # 累积基线偏移
        cumulative_shift = float(np.sum(np.abs(shifts)))

        detected = (
            reference_strength >= corr_threshold
            and n_feedback >= 2
        )

        return SelfReferenceSignal(
            detected=detected,
            reference_strength=reference_strength,
            response_baseline_correlation=correlation,
            n_feedback_events=n_feedback,
            cumulative_baseline_shift=cumulative_shift,
            timestamp=self._step_count,
        )

    def _build_description(
        self,
        detected: bool,
        asymmetry: AsymmetrySignal,
        history_dep: HistoryDependencySignal,
        self_ref: SelfReferenceSignal,
        msi: float,
        odi: float,
    ) -> str:
        """构建检测结果描述"""
        if not detected:
            parts = []
            if not asymmetry.detected:
                parts.append(f"视角不对称不足({asymmetry.asymmetry_index:.3f})")
            if not history_dep.detected:
                parts.append(f"历史依赖不足({history_dep.dependency_index:.3f})")
            if not self_ref.detected:
                parts.append(f"自我参照不足({self_ref.reference_strength:.3f})")
            parts.append(f"ODI={odi:.4f}")
            return "无最小自我: " + "; ".join(parts)

        parts = []
        if asymmetry.detected:
            parts.append(
                f"视角不对称: {asymmetry.asymmetry_index:.3f} "
                f"(主导={asymmetry.dominant_part}, 最弱={asymmetry.weakest_part})"
            )
        if history_dep.detected:
            parts.append(
                f"历史依赖: {history_dep.dependency_index:.3f} "
                f"({history_dep.n_distinct_contexts}个上下文)"
            )
        if self_ref.detected:
            parts.append(
                f"自我参照: {self_ref.reference_strength:.3f} "
                f"(r={self_ref.response_baseline_correlation:.3f})"
            )
        parts.append(f"MSI={msi:.4f}, ODI={odi:.4f}")
        return "最小自我涌现: " + "; ".join(parts)

    # ─── 查询接口 ───

    @property
    def emergence_count(self) -> int:
        """检测到的最小自我涌现次数"""
        return self._emergence_count

    @property
    def latest_result(self) -> Optional[MinimalSelfResult]:
        """最近一次检测结果"""
        return self._history[-1] if self._history else None

    @property
    def has_minimal_self(self) -> bool:
        """是否至少检测到一次最小自我"""
        return self._emergence_count > 0

    @property
    def current_msi(self) -> float:
        """当前 MSI 值"""
        if not self._history:
            return 0.0
        return self._history[-1].msi

    def get_emergence_history(self) -> List[MinimalSelfResult]:
        """获取所有检测到的最小自我事件"""
        return [r for r in self._history if r.minimal_self_detected]

    def get_msi_trajectory(self) -> List[float]:
        """获取 MSI 时间序列"""
        return [r.msi for r in self._history]

    def get_signal_summary(self) -> Dict:
        """获取各信号的触发统计"""
        if not self._history:
            return {'n_evaluations': 0}

        asym_count = sum(1 for r in self._history if r.asymmetry.detected)
        hist_count = sum(1 for r in self._history if r.history_dependency.detected)
        self_ref_count = sum(1 for r in self._history if r.self_reference.detected)

        return {
            'n_evaluations': len(self._history),
            'n_emergence': self._emergence_count,
            'asymmetry_triggers': asym_count,
            'history_dependency_triggers': hist_count,
            'self_reference_triggers': self_ref_count,
            'current_msi': self.current_msi,
            'max_msi': max((r.msi for r in self._history), default=0.0),
        }

    def reset(self):
        """重置所有状态"""
        self._sensitivity_history.clear()
        self._response_history.clear()
        self._baseline_shifts.clear()
        self._response_values.clear()
        self._odi_history.clear()
        self._history.clear()
        self._emergence_count = 0
        self._step_count = 0
