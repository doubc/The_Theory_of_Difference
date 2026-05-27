"""
engine/anticipatory_bias_engine.py — 预期偏置引擎 (AnticipatoryBiasEngine)

Phase 3 P1 组件

职责：基于历史偏置序列外推未来差异分布，实现前摄性偏置。
这是从"回溯性偏置"（PersistentBiasMemory）到"前摄性偏置"的关键扩展。

理论依据：
- 《差异论》高语义层：当结构不仅能保留路径，还能基于路径偏置对未来
  差异分布产生预期时，"预期"就涌现了
- 《象界》第四章：痕迹 → 记忆 → 预期（记忆的前摄性延伸）
- ABA §4.4：前主体态是一个"范围"，预期能力随 ODI 增长而增强

核心区分：
- PersistentBiasMemory：过去以偏置形式影响当下（回溯性）
- AnticipatoryBiasEngine：当下基于历史模式对未来产生预期偏置（前摄性）

预期不是"猜测"，而是历史路径依赖的统计外推。
预期不能引入"意图"或"目的"——它只是结构对自身路径依赖的延伸。

ODI 门控：
- ODI < 0.3：预期被完全抑制（结构尚未准备好）
- 0.3 <= ODI < 0.5：预期被部分抑制（confidence *= odi_factor）
- ODI >= 0.5：预期正常运行

语义防火墙：
- "预期" ≠ "预测未来"（没有目的论）
- "预期" ≠ "期望"（没有心理状态）
- "预期" = "基于历史路径依赖的统计外推"
"""

import math
from typing import Dict, List, Optional, Tuple, Deque
from dataclasses import dataclass, field
from collections import deque

import torch
import numpy as np

from engine.persistent_bias_memory import PersistentBiasMemory, BiasEntry
from engine.organizational_density_index import DensityIndexResult


# ─── 默认配置 ───
DEFAULT_ANTICIPATION_CONFIG = {
    # 外推参数
    'history_window': 10,               # 历史偏置窗口大小
    'min_history_length': 3,            # 最少历史长度（少于此值无法外推）
    'max_horizon': 5,                   # 最大预期视野（步数）
    'default_horizon': 1,               # 默认预期视野

    # 方法选择阈值
    'direction_variance_low': 0.1,      # 方向方差低阈值（低于此用线性外推）
    'direction_variance_high': 0.4,     # 方向方差高阈值（高于此用加权外推）

    # 置信度参数
    'base_confidence': 0.5,             # 基础置信度
    'confidence_decay': 0.1,            # 历史权重衰减率
    'min_confidence': 0.05,             # 最低置信度
    'max_confidence': 0.95,             # 最高置信度

    # ODI 门控
    'odi_suppress_threshold': 0.3,      # ODI 低于此值完全抑制
    'odi_partial_threshold': 0.5,       # ODI 低于此值部分抑制
    'odi_gate_steepness': 10.0,         # ODI 门控 sigmoid 陡度

    # 可靠性判定
    'reliability_confidence_threshold': 0.3,  # 置信度 > 此值认为可靠
    'reliability_min_predictions': 5,   # 最少预测次数才判定可靠性

    # 误差追踪
    'error_window': 20,                 # 误差历史窗口
    'error_trend_window': 10,           # 误差趋势窗口
}


# ─── 数据类 ───

@dataclass
class ExpectationField:
    """预期差异场 — 对未来差异分布的结构性预偏置

    与 BiasField 对偶：
    - BiasField：当前差异的偏置（同步、当下）
    - ExpectationField：未来差异的预期（前摄、未来）
    """
    source_layer: int                   # 来源层
    target_layer: int                   # 目标层
    expected_vector: torch.Tensor       # 预期差异方向
    confidence: float                   # 预期置信度 [0, 1]
    horizon: int                        # 预期视野（步数）
    timestamp: int                      # 生成时间戳
    method: str                         # 外推方法标识
    metadata: Dict = field(default_factory=dict)  # 附加信息

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= DEFAULT_ANTICIPATION_CONFIG['reliability_confidence_threshold']

    @property
    def expected_magnitude(self) -> float:
        """预期差异的范数"""
        return float(self.expected_vector.norm().item())

    def __repr__(self):
        return (f"ExpectationField(L{self.source_layer}->L{self.target_layer}, "
                f"conf={self.confidence:.3f}, h={self.horizon}, method={self.method})")


@dataclass
class PredictionError:
    """单次预测误差记录"""
    timestamp: int
    predicted: torch.Tensor             # 预测值
    actual: torch.Tensor                # 实际值
    error_magnitude: float              # 误差范数
    relative_error: float               # 相对误差
    horizon: int                        # 预测视野

    def __repr__(self):
        return (f"PredictionError(t={self.timestamp}, "
                f"err={self.error_magnitude:.4f}, rel={self.rel_error:.4f}, h={self.horizon})")


@dataclass
class AnticipationResult:
    """预期偏置引擎的输出"""
    expectation: ExpectationField       # 预期场
    confidence: float                   # 综合置信度
    error_trend: float                  # 误差趋势（负=改善，正=恶化）
    n_predictions: int                  # 历史预测次数
    mean_error: float                   # 平均预测误差
    is_reliable: bool                   # 预期是否可靠
    odi_gated: bool                     # 是否被 ODI 门控
    timestamp: int

    def __repr__(self):
        return (f"AnticipationResult(conf={self.confidence:.3f}, "
                f"trend={self.error_trend:+.4f}, "
                f"n_pred={self.n_predictions}, "
                f"reliable={self.is_reliable}, odi_gated={self.odi_gated})")


# ─── PatternExtrapolator ───

class PatternExtrapolator:
    """从历史偏置序列外推未来差异分布

    三种外推方法：
    1. 线性外推（一阶）：偏置方向稳定时使用
    2. 加速度外推（二阶）：偏置方向加速变化时使用
    3. 置信度加权外推：偏置方向不稳定时使用

    方法选择策略：
    - 方向方差 < low_threshold → 线性外推
    - 方向方差 > high_threshold → 置信度加权外推
    - 否则 → 加速度外推
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_ANTICIPATION_CONFIG, **(config or {})}

    def extrapolate(
        self,
        history: List[Tuple[int, torch.Tensor]],
        horizon: int = 1,
        timestamp: int = 0,
    ) -> Tuple[torch.Tensor, float, str]:
        """从历史偏置序列外推未来差异分布

        Parameters
        ----------
        history : List[Tuple[int, torch.Tensor]]
            历史偏置序列 [(t_1, v_1), ..., (t_n, v_n)]
        horizon : int
            预期视野（步数）
        timestamp : int
            当前时间戳

        Returns
        -------
        (expected_vector, confidence, method) : Tuple[torch.Tensor, float, str]
            外推向量、置信度、方法标识
        """
        if len(history) < self.config['min_history_length']:
            # 历史不足：返回零向量 + 最低置信度
            if len(history) > 0:
                dim = history[-1][1].shape[0]
            else:
                dim = 1
            return (
                torch.zeros(dim),
                self.config['min_confidence'],
                'insufficient_history',
            )

        # 选择外推方法
        method = self._select_method(history)

        if method == 'linear':
            return self._linear_extrapolate(history, horizon, timestamp)
        elif method == 'acceleration':
            return self._acceleration_extrapolate(history, horizon, timestamp)
        else:  # 'weighted'
            return self._weighted_extrapolate(history, horizon, timestamp)

    def _select_method(self, history: List[Tuple[int, torch.Tensor]]) -> str:
        """根据历史偏置方向方差选择外推方法"""
        if len(history) < 3:
            return 'linear'

        # 计算相邻偏置向量的方向余弦相似度
        vectors = [v for _, v in history]
        cos_sims = []
        for i in range(1, len(vectors)):
            v_prev = vectors[i - 1]
            v_curr = vectors[i]
            norm_prev = v_prev.norm().item()
            norm_curr = v_curr.norm().item()
            if norm_prev < 1e-8 or norm_curr < 1e-8:
                cos_sims.append(1.0)  # 零向量视为方向一致
            else:
                cos_sim = torch.dot(v_prev, v_curr).item() / (norm_prev * norm_curr)
                cos_sims.append(cos_sim)

        # 方向方差 = 1 - 平均余弦相似度
        direction_variance = 1.0 - float(np.mean(cos_sims))

        low = self.config['direction_variance_low']
        high = self.config['direction_variance_high']

        if direction_variance < low:
            return 'linear'
        elif direction_variance > high:
            return 'weighted'
        else:
            return 'acceleration'

    def _linear_extrapolate(
        self,
        history: List[Tuple[int, torch.Tensor]],
        horizon: int,
        timestamp: int,
    ) -> Tuple[torch.Tensor, float, str]:
        """线性外推（一阶）

        v_predicted = v_n + (v_n - v_{n-1}) * horizon
        """
        v_n = history[-1][1]
        v_n1 = history[-2][1]
        trend = v_n - v_n1
        predicted = v_n + trend * horizon

        # 置信度基于历史一致性
        confidence = self._compute_confidence(history, method='linear')

        return predicted, confidence, 'linear'

    def _acceleration_extrapolate(
        self,
        history: List[Tuple[int, torch.Tensor]],
        horizon: int,
        timestamp: int,
    ) -> Tuple[torch.Tensor, float, str]:
        """加速度外推（二阶）

        a = (v_n - v_{n-1}) - (v_{n-1} - v_{n-2})
        v_predicted = v_n + (v_n - v_{n-1}) * horizon + 0.5 * a * horizon^2
        """
        v_n = history[-1][1]
        v_n1 = history[-2][1]
        v_n2 = history[-3][1]

        velocity = v_n - v_n1
        acceleration = (v_n - v_n1) - (v_n1 - v_n2)
        predicted = v_n + velocity * horizon + 0.5 * acceleration * (horizon ** 2)

        confidence = self._compute_confidence(history, method='acceleration')

        return predicted, confidence, 'acceleration'

    def _weighted_extrapolate(
        self,
        history: List[Tuple[int, torch.Tensor]],
        horizon: int,
        timestamp: int,
    ) -> Tuple[torch.Tensor, float, str]:
        """置信度加权外推

        w_i = confidence_i * exp(-decay * (n - i))
        v_predicted = weighted_mean(H, w) + trend * horizon
        """
        n = len(history)
        decay = self.config['confidence_decay']

        # 计算权重（近期偏置权重更高）
        weights = []
        for i in range(n):
            recency_weight = math.exp(-decay * (n - 1 - i))
            weights.append(recency_weight)

        # 加权平均向量
        total_weight = sum(weights)
        weighted_sum = torch.zeros_like(history[0][1])
        for i in range(n):
            weighted_sum += weights[i] * history[i][1]
        weighted_mean = weighted_sum / total_weight

        # 趋势 = 最近两个偏置的差分
        trend = history[-1][1] - history[-2][1]

        predicted = weighted_mean + trend * horizon

        # 加权外推的置信度较低（因为方向不稳定）
        confidence = self._compute_confidence(history, method='weighted') * 0.8

        return predicted, confidence, 'weighted'

    def _compute_confidence(
        self,
        history: List[Tuple[int, torch.Tensor]],
        method: str,
    ) -> float:
        """计算外推置信度

        confidence = base_confidence * stability_factor

        - base_confidence: 基于历史长度的基础置信度
        - stability_factor: 偏置方向稳定性
        """
        cfg = self.config

        # 基础置信度：历史越长，置信度越高（对数增长）
        n = len(history)
        max_win = cfg['history_window']
        base_confidence = cfg['base_confidence'] + (1.0 - cfg['base_confidence']) * min(1.0, n / max_win)

        # 稳定性因子：方向越稳定，置信度越高
        if n >= 2:
            vectors = [v for _, v in history]
            cos_sims = []
            for i in range(1, len(vectors)):
                v_prev = vectors[i - 1]
                v_curr = vectors[i]
                norm_prev = v_prev.norm().item()
                norm_curr = v_curr.norm().item()
                if norm_prev < 1e-8 or norm_curr < 1e-8:
                    cos_sims.append(1.0)
                else:
                    cos_sim = torch.dot(v_prev, v_curr).item() / (norm_prev * norm_curr)
                    cos_sims.append(cos_sim)
            stability_factor = float(np.mean(cos_sims))
        else:
            stability_factor = 0.5

        confidence = base_confidence * max(0.1, stability_factor)

        # 方法惩罚：加速度外推略降置信度
        if method == 'acceleration':
            confidence *= 0.9

        return float(np.clip(confidence, cfg['min_confidence'], cfg['max_confidence']))


# ─── PredictionErrorTracker ───

class PredictionErrorTracker:
    """预测误差追踪器

    追踪预期偏置引擎的预测误差历史，计算误差趋势。
    误差趋势为负表示预测在改善，为正表示预测在恶化。
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_ANTICIPATION_CONFIG, **(config or {})}
        self.error_history: Deque[PredictionError] = deque(
            maxlen=self.config['error_window']
        )

    def record_error(
        self,
        predicted: torch.Tensor,
        actual: torch.Tensor,
        timestamp: int,
        horizon: int = 1,
    ) -> PredictionError:
        """记录一次预测误差"""
        error_vec = actual - predicted
        error_magnitude = float(error_vec.norm().item())
        actual_magnitude = float(actual.norm().item())
        relative_error = error_magnitude / max(actual_magnitude, 1e-8)

        record = PredictionError(
            timestamp=timestamp,
            predicted=predicted.detach().clone(),
            actual=actual.detach().clone(),
            error_magnitude=error_magnitude,
            relative_error=relative_error,
            horizon=horizon,
        )
        self.error_history.append(record)
        return record

    def get_error_trend(self) -> float:
        """计算误差趋势

        Returns
        --------
        float
            误差趋势值：负=改善，正=恶化，0=无数据或无变化
        """
        if len(self.error_history) < 2:
            return 0.0

        trend_window = self.config['error_trend_window']
        recent_errors = list(self.error_history)[-trend_window:]
        if len(recent_errors) < 2:
            return 0.0

        # 简单线性回归斜率
        x = np.arange(len(recent_errors))
        y = np.array([e.error_magnitude for e in recent_errors])
        slope = float(np.polyfit(x, y, 1)[0])

        return slope

    def get_mean_error(self) -> float:
        """获取平均预测误差"""
        if not self.error_history:
            return 0.0
        return float(np.mean([e.error_magnitude for e in self.error_history]))

    def get_mean_relative_error(self) -> float:
        """获取平均相对误差"""
        if not self.error_history:
            return 0.0
        return float(np.mean([e.relative_error for e in self.error_history]))

    @property
    def n_predictions(self) -> int:
        return len(self.error_history)

    def is_learning(self) -> bool:
        """预测是否在改善（误差趋势为负）"""
        return self.get_error_trend() < -1e-6

    def is_degrading(self) -> bool:
        """预测是否在恶化（误差趋势为正）"""
        return self.get_error_trend() > 1e-6


# ─── AnticipationConfidence ───

class AnticipationConfidence:
    """预期置信度综合评估

    综合三个因素：
    1. 历史预测准确率
    2. 历史偏置稳定性
    3. ODI 值（高 ODI → 更稳定的预期）
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_ANTICIPATION_CONFIG, **(config or {})}

    def compute(
        self,
        error_tracker: PredictionErrorTracker,
        history_stability: float,
        odi_result: Optional[DensityIndexResult] = None,
    ) -> float:
        """计算综合置信度

        Parameters
        ----------
        error_tracker : PredictionErrorTracker
            预测误差追踪器
        history_stability : float
            历史偏置稳定性 [0, 1]
        odi_result : Optional[DensityIndexResult]
            ODI 结果（用于门控）

        Returns
        -------
        float
            综合置信度 [0, 1]
        """
        cfg = self.config

        # 1. 基于历史预测准确率
        if error_tracker.n_predictions > 0:
            mean_rel_error = error_tracker.get_mean_relative_error()
            accuracy_confidence = 1.0 - min(1.0, mean_rel_error)
        else:
            accuracy_confidence = cfg['base_confidence']

        # 2. 基于历史偏置稳定性
        stability_confidence = history_stability

        # 3. 综合（几何平均）
        combined = math.sqrt(accuracy_confidence * max(0.01, stability_confidence))

        # 4. ODI 门控
        odi_factor = self._odi_gate(odi_result)
        gated = combined * odi_factor

        return float(np.clip(gated, cfg['min_confidence'], cfg['max_confidence']))

    def _odi_gate(self, odi_result: Optional[DensityIndexResult]) -> float:
        """ODI 门控因子

        - ODI < 0.3: 完全抑制 → 0
        - 0.3 <= ODI < 0.5: 部分抑制 → sigmoid 过渡
        - ODI >= 0.5: 正常 → 1
        """
        cfg = self.config

        if odi_result is None:
            return 1.0  # 无 ODI 信息时不门控

        odi = odi_result.odi if hasattr(odi_result, 'odi') else float(odi_result)

        suppress = cfg['odi_suppress_threshold']
        partial = cfg['odi_partial_threshold']
        steepness = cfg['odi_gate_steepness']

        if odi < suppress:
            return 0.0
        elif odi >= partial:
            return 1.0
        else:
            # Sigmoid 过渡
            x = (odi - suppress) / (partial - suppress) * steepness - steepness / 2
            return 1.0 / (1.0 + math.exp(-x))


# ─── AnticipatoryBiasEngine ───

class AnticipatoryBiasEngine:
    """预期偏置引擎

    基于历史偏置序列外推未来差异分布，实现前摄性偏置。

    工作流程：
    1. 从 PersistentBiasMemory 读取历史偏置
    2. PatternExtrapolator 外推未来差异分布
    3. 生成 ExpectationField
    4. 用实际差异更新 PredictionErrorTracker
    5. AnticipationConfidence 综合评估置信度

    语义防火墙：
    - "预期" ≠ "预测未来"（没有目的论）
    - "预期" ≠ "期望"（没有心理状态）
    - "预期" = "基于历史路径依赖的统计外推"
    """

    def __init__(
        self,
        memory: PersistentBiasMemory,
        config: Optional[Dict] = None,
    ):
        self.config = {**DEFAULT_ANTICIPATION_CONFIG, **(config or {})}
        self.memory = memory
        self.extrapolator = PatternExtrapolator(self.config)
        self.error_tracker = PredictionErrorTracker(self.config)
        self.confidence_evaluator = AnticipationConfidence(self.config)

        # 缓存的预期场（按目标层索引）
        self._expectation_fields: Dict[int, ExpectationField] = {}

    def predict(
        self,
        target_layer: int,
        horizon: int = 1,
        timestamp: int = 0,
        odi_result: Optional[DensityIndexResult] = None,
    ) -> AnticipationResult:
        """基于历史偏置外推未来差异分布

        Parameters
        ----------
        target_layer : int
            目标层
        horizon : int
            预期视野（步数）
        timestamp : int
            当前时间戳
        odi_result : Optional[DensityIndexResult]
            ODI 结果（用于门控）

        Returns
        -------
        AnticipationResult
            预期结果
        """
        cfg = self.config

        # 1. 从 PersistentBiasMemory 读取历史偏置
        history = self._get_history(target_layer)

        # 2. 外推
        expected_vector, extrapolation_confidence, method = self.extrapolator.extrapolate(
            history=history,
            horizon=horizon,
            timestamp=timestamp,
        )

        # 3. 计算历史稳定性
        history_stability = self._compute_history_stability(history)

        # 4. 综合置信度
        confidence = self.confidence_evaluator.compute(
            error_tracker=self.error_tracker,
            history_stability=history_stability,
            odi_result=odi_result,
        )

        # 外推置信度与综合置信度的混合
        confidence = 0.6 * confidence + 0.4 * extrapolation_confidence

        # 5. ODI 门控
        odi_gated = False
        if odi_result is not None:
            odi = odi_result.odi if hasattr(odi_result, 'odi') else float(odi_result)
            if odi < cfg['odi_suppress_threshold']:
                confidence = cfg['min_confidence']
                odi_gated = True
            elif odi < cfg['odi_partial_threshold']:
                odi_gated = True

        # 6. 构建预期场
        source_layer = self._infer_source_layer(target_layer)
        expectation = ExpectationField(
            source_layer=source_layer,
            target_layer=target_layer,
            expected_vector=expected_vector,
            confidence=confidence,
            horizon=horizon,
            timestamp=timestamp,
            method=method,
            metadata={
                'history_length': len(history),
                'odi_gated': odi_gated,
                'extrapolation_confidence': extrapolation_confidence,
            },
        )

        # 7. 缓存
        self._expectation_fields[target_layer] = expectation

        # 8. 构建结果
        result = AnticipationResult(
            expectation=expectation,
            confidence=confidence,
            error_trend=self.error_tracker.get_error_trend(),
            n_predictions=self.error_tracker.n_predictions,
            mean_error=self.error_tracker.get_mean_error(),
            is_reliable=(
                confidence > cfg['reliability_confidence_threshold']
                and self.error_tracker.n_predictions >= cfg['reliability_min_predictions']
            ),
            odi_gated=odi_gated,
            timestamp=timestamp,
        )

        return result

    def update(
        self,
        actual: torch.Tensor,
        timestamp: int,
        horizon: int = 1,
    ) -> Optional[PredictionError]:
        """用实际差异更新预测误差追踪

        将最近一次预测与实际差异比较，记录误差。

        Parameters
        ----------
        actual : torch.Tensor
            实际差异向量
        timestamp : int
            当前时间戳
        horizon : int
            预测视野

        Returns
        -------
        Optional[PredictionError]
            预测误差记录（无缓存预测时返回 None）
        """
        # 使用最近缓存的预期场
        if not self._expectation_fields:
            return None

        # 取最新的预期场
        latest_target = max(self._expectation_fields.keys())
        expectation = self._expectation_fields[latest_target]

        error = self.error_tracker.record_error(
            predicted=expectation.expected_vector,
            actual=actual,
            timestamp=timestamp,
            horizon=horizon,
        )

        return error

    def get_expectation_field(self, target_layer: int) -> Optional[ExpectationField]:
        """获取当前预期场"""
        return self._expectation_fields.get(target_layer)

    def get_prediction_accuracy(self) -> float:
        """获取历史预测准确率（1 - 平均相对误差）"""
        if self.error_tracker.n_predictions == 0:
            return 0.0
        return 1.0 - self.error_tracker.get_mean_relative_error()

    def get_error_stats(self) -> Dict:
        """获取误差统计信息"""
        return {
            'n_predictions': self.error_tracker.n_predictions,
            'mean_error': self.error_tracker.get_mean_error(),
            'mean_relative_error': self.error_tracker.get_mean_relative_error(),
            'error_trend': self.error_tracker.get_error_trend(),
            'is_learning': self.error_tracker.is_learning(),
            'is_degrading': self.error_tracker.is_degrading(),
        }

    # ─── 内部方法 ───

    def _get_history(self, target_layer: int) -> List[Tuple[int, torch.Tensor]]:
        """从 PersistentBiasMemory 获取目标层的历史偏置序列

        使用 get_historical() 接口获取历史偏置向量列表，
        并附带合成时间戳（基于索引）。
        """
        vectors = self.memory.get_historical(target_layer, depth=self.config['history_window'])
        history = []
        for i, v in enumerate(vectors):
            history.append((i, v.detach().clone() if isinstance(v, torch.Tensor) else torch.tensor(v)))
        # 截取窗口
        window = self.config['history_window']
        if len(history) > window:
            history = history[-window:]
        return history

    def _compute_history_stability(self, history: List[Tuple[int, torch.Tensor]]) -> float:
        """计算历史偏置稳定性 [0, 1]"""
        if len(history) < 2:
            return 0.5  # 历史不足时返回中性值

        vectors = [v for _, v in history]
        cos_sims = []
        for i in range(1, len(vectors)):
            v_prev = vectors[i - 1]
            v_curr = vectors[i]
            norm_prev = v_prev.norm().item()
            norm_curr = v_curr.norm().item()
            if norm_prev < 1e-8 or norm_curr < 1e-8:
                cos_sims.append(1.0)
            else:
                cos_sim = torch.dot(v_prev, v_curr).item() / (norm_prev * norm_curr)
                cos_sims.append(cos_sim)

        return float(np.mean(cos_sims))

    def _infer_source_layer(self, target_layer: int) -> int:
        """推断来源层（目标层的上一层）"""
        return max(0, target_layer - 1)
