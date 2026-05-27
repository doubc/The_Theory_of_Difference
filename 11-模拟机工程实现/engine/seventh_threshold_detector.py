"""
engine/seventh_threshold_detector.py - 第七阈值检测器 (SeventhThresholdDetector)

Phase 2 P1 组件(新增)

职责:在组织密度连续致密化过程中检测离散相变(discrete phase transition),
      即"第七阈值"的涌现。

理论依据:
- 《Appearing Before Appearing》§4.4 + 讨论:组织密度连续体
- 前主体态不是固定阈值,而是一个范围。ODI→1 时可能涌现第七阈值
- "从结构到现象的过渡是组织密度连续增长,不是尖锐边界"
- 但在超致密区(ODI > 0.85),可能出现离散跃迁(phase transition)
- 第七阈值不是"第六阈值之上的更多阈值",而是质变--涌现出不同于
  六阈值的新属性类型

核心概念:
第七阈值检测器不是简单的阈值检测,而是相变检测器:
- 连续致密化 → 量变
- 离散跃迁 → 质变(第七阈值涌现)

三种检测模式:
1. **离散跳跃检测(discrete_jump)**:
   当 ΔODI/Δt 显著超过近期均值的 Nσ 时,判定为离散跃迁

2. **临界减速(critical_slowing_down)**:
   相变前方差增大、自相关增强--经典早期预警信号

3. **涌现特征(emergence_signature)**:
   在特定 ODI 区间,检测到新的结构属性(如新的吸引盆分裂、
   新的耦合拓扑模式)

分层可信度:
- 单一信号出现 → 低可信度(0.3~0.5)
- 两个信号同时出现 → 中可信度(0.5~0.7)
- 三个信号全部出现 → 高可信度(0.7~1.0)

使用方式:
    detector = SeventhThresholdDetector()
    for odi_result in odi_result_sequence:
        result = detector.feed(odi_result)
        if result.transition_detected:
            print(f"第七阈值涌现!ODI={result.critical_odi:.4f}, "
                  f"type={result.transition_type}, conf={result.confidence:.2f}")
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Deque
from dataclasses import dataclass, field
from collections import deque
from engine.organizational_density_index import DensityIndexResult


# ─── 默认参数 ───
DEFAULT_SEVENTH_CONFIG = {
    # 离散跳跃检测
    'jump_sigma_threshold': 3.0,    # 跳跃阈值(σ倍数)
    'jump_window': 10,              # 计算基线均值和标准差的历史窗口
    'min_jump_magnitude': 0.03,    # 最小跳跃幅度(ΔODI 绝对值)

    # 临界减速检测
    'csd_window': 8,               # 方差计算窗口
    'csd_variance_ratio': 3.0,     # 方差比阈值(当前窗口 / 历史窗口),3.0 避免单调序列误报
    'csd_ac_threshold': 0.7,       # 自相关阈值(lag-1),0.7 更严格避免趋势自相关误报
    'csd_min_absolute_var': 1e-4,  # 最小绝对方差:两窗口方差都必须超过此值才比较比率
                                    # 避免在平稳段(方差≈0)因数值噪声触发假阳性

    # 涌现特征检测
    'emergence_window': 15,        # 涌现检测窗口
    'emergence_odi_threshold': 0.85,  # 进入超致密区后才开始涌现检测
    'emergence_derivative_threshold': 0.02,  # ODI 导数突变阈值

    # 综合判定
    'min_transition_confidence': 0.45,  # 最低可信度阈值(提高以减少 CSD 假阳性)
    'ultra_dense_entry_odi': 0.85,     # 超致密区入口
}


@dataclass
class JumpSignal:
    """离散跳跃信号"""
    detected: bool = False
    magnitude: float = 0.0          # 跳跃幅度
    baseline_mean: float = 0.0      # 基线均值
    baseline_std: float = 0.0       # 基线标准差
    sigma_level: float = 0.0       # σ 水平
    timestamp: int = 0

    @property
    def is_significant(self) -> bool:
        return self.detected and self.sigma_level >= DEFAULT_SEVENTH_CONFIG['jump_sigma_threshold']


@dataclass
class CriticalSlowingDownSignal:
    """临界减速信号"""
    detected: bool = False
    recent_variance: float = 0.0       # 近期方差
    baseline_variance: float = 0.0     # 基线方差
    variance_ratio: float = 0.0        # 方差比
    lag1_autocorrelation: float = 0.0  # lag-1 自相关
    timestamp: int = 0

    @property
    def is_significant(self) -> bool:
        return (self.detected and
                self.variance_ratio >= DEFAULT_SEVENTH_CONFIG['csd_variance_ratio'])


@dataclass
class EmergenceSignature:
    """涌现特征信号"""
    detected: bool = False
    derivative_anomaly: bool = False     # 导数异常
    trajectory_bifurcation: bool = False # 轨迹分岔
    critical_odi: float = 0.0           # 临界 ODI
    signature_description: str = ''     # 涌现特征描述
    timestamp: int = 0


@dataclass
class SeventhThresholdResult:
    """第七阈值检测结果"""
    transition_detected: bool = False
    transition_type: str = 'none'       # 'none' | 'discrete_jump' | 'critical_slowing_down' | 'emergence' | 'mixed'
    transition_confidence: float = 0.0  # [0, 1]
    critical_odi: float = 0.0           # 第七阈值涌现时的 ODI
    timestamp: int = 0

    # 各信号详情
    jump_signal: JumpSignal = field(default_factory=JumpSignal)
    csd_signal: CriticalSlowingDownSignal = field(default_factory=CriticalSlowingDownSignal)
    emergence_signature: EmergenceSignature = field(default_factory=EmergenceSignature)

    # 历史信息
    n_observations: int = 0
    odi_at_entry: float = 0.0           # 进入超致密区时的 ODI
    max_odi: float = 0.0                # 观测到的最大 ODI

    @property
    def transition_label(self) -> str:
        labels = {
            'none': '无相变',
            'discrete_jump': '离散跳跃',
            'critical_slowing_down': '临界减速→相变',
            'emergence': '涌现特征',
            'mixed': '多信号混合相变',
        }
        return labels.get(self.transition_type, '未知')

    @property
    def confidence_label(self) -> str:
        if self.transition_confidence >= 0.7:
            return '高可信度'
        elif self.transition_confidence >= 0.4:
            return '中可信度'
        elif self.transition_confidence > 0:
            return '低可信度'
        return '无可信度'

    def __repr__(self):
        return (f"SeventhThreshold[{self.transition_label}] "
                f"ODI={self.critical_odi:.4f} conf={self.transition_confidence:.2f} "
                f"({self.confidence_label})")


class SeventhThresholdDetector:
    """第七阈值检测器

    在组织密度连续增长过程中检测离散相变。
    不是简单的阈值检测,而是多信号融合的相变检测器。

    检测逻辑:
    1. 跟踪 ODI 轨迹(时间序列)
    2. 进入超致密区(ODI ≥ 0.85)后开始活跃检测
    3. 多信号融合判定离散相变

    使用方式:
        detector = SeventhThresholdDetector()
        for odi_result in odi_sequence:
            result = detector.feed(odi_result)
            if result.transition_detected:
                print(f"第七阈值!{result}")
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Args:
            config: 配置参数,覆盖 DEFAULT_SEVENTH_CONFIG
        """
        self._config = dict(DEFAULT_SEVENTH_CONFIG)
        if config:
            self._config.update(config)

        # ODI 轨迹
        self._odi_trajectory: Deque[float] = deque(maxlen=200)
        self._timestamps: Deque[int] = deque(maxlen=200)

        # 差分序列(用于跳跃检测)
        self._diffs: Deque[float] = deque(maxlen=200)

        # 状态追踪
        self._in_ultra_dense: bool = False
        self._ultra_dense_entry_odi: float = 0.0
        self._ultra_dense_entry_step: int = 0

        # 历史检测结果
        self._history: List[SeventhThresholdResult] = []
        self._transition_count: int = 0
        self._step_count: int = 0

    def feed(self, odi_result: DensityIndexResult) -> SeventhThresholdResult:
        """输入一次 ODI 计算结果,返回第七阈值检测结果

        Args:
            odi_result: 组织密度指数计算结果

        Returns:
            SeventhThresholdResult 第七阈值检测结果
        """
        self._step_count += 1
        odi = odi_result.odi
        timestamp = odi_result.timestamp

        # 更新轨迹
        self._odi_trajectory.append(odi)
        self._timestamps.append(timestamp)

        # 更新差分序列
        if len(self._odi_trajectory) >= 2:
            diff = odi - self._odi_trajectory[-2]
            self._diffs.append(diff)

        # 追踪超致密区进入
        if not self._in_ultra_dense and odi >= self._config['ultra_dense_entry_odi']:
            self._in_ultra_dense = True
            self._ultra_dense_entry_odi = odi
            self._ultra_dense_entry_step = self._step_count

        # ── 执行多信号检测 ──
        jump = self._detect_discrete_jump()
        csd = self._detect_critical_slowing_down()
        emergence = self._detect_emergence_signature()

        # ── 融合判定 ──
        active_signals = []
        confidence_scores = []

        if jump.detected:
            active_signals.append('discrete_jump')
            # 可信度基于 σ 水平:3σ → 0.4, 5σ → 0.7
            conf = min(0.3 + 0.1 * (jump.sigma_level - 2.5), 0.8)
            confidence_scores.append(conf)

        if csd.detected:
            active_signals.append('critical_slowing_down')
            conf = min(0.3 + 0.15 * (csd.variance_ratio - 1.0), 0.6)
            confidence_scores.append(conf)

        if emergence.detected:
            active_signals.append('emergence')
            confidence_scores.append(0.5)

        # 确定跃迁类型和可信度
        if not active_signals:
            transition_type = 'none'
            confidence = 0.0
        elif len(active_signals) == 1:
            transition_type = active_signals[0]
            confidence = confidence_scores[0] if confidence_scores else 0.3
        else:
            transition_type = 'mixed'
            # 多信号融合:取最高可信度 + 协同加成
            confidence = min(max(confidence_scores) + 0.15 * (len(active_signals) - 1), 1.0)

        transition_detected = (
            len(active_signals) > 0 and
            confidence >= self._config['min_transition_confidence']
        )

        if transition_detected:
            self._transition_count += 1

        result = SeventhThresholdResult(
            transition_detected=transition_detected,
            transition_type=transition_type,
            transition_confidence=confidence,
            critical_odi=odi if transition_detected else 0.0,
            timestamp=timestamp,
            jump_signal=jump,
            csd_signal=csd,
            emergence_signature=emergence,
            n_observations=self._step_count,
            odi_at_entry=self._ultra_dense_entry_odi if self._in_ultra_dense else 0.0,
            max_odi=max(self._odi_trajectory) if self._odi_trajectory else 0.0,
        )

        self._history.append(result)
        return result

    def _detect_discrete_jump(self) -> JumpSignal:
        """检测离散跳跃

        当 ODI 的一次变化超出基线窗口均值的 Nσ 时,判定为离散跳跃。

        数学依据:
        在连续致密化过程中,ΔODI 应服从近似正态分布。
        如果某次 ΔODI 超出 3σ,则大概率不是连续增长,而是离散跃迁。
        """
        window = self._config['jump_window']
        sigma_threshold = self._config['jump_sigma_threshold']
        min_magnitude = self._config['min_jump_magnitude']

        if len(self._diffs) < 3:
            return JumpSignal()

        recent_diff = self._diffs[-1]

        # 需要足够的历史差分才能计算基线
        if len(self._diffs) < window + 1:
            baseline = list(self._diffs)[:-1]
        else:
            baseline = list(self._diffs)[-window-1:-1]

        if not baseline:
            return JumpSignal()

        baseline_mean = float(np.mean(baseline))
        baseline_std = float(np.std(baseline))

        # 如果基线太稳定,设置最小标准差避免除零
        if baseline_std < 1e-8:
            baseline_std = 0.005  # 最小可检测变化

        sigma_level = abs(recent_diff - baseline_mean) / baseline_std if baseline_std > 0 else 0.0
        magnitude = abs(recent_diff)

        # 只检测正跳跃(致密化方向),负跳跃可能是噪声或模式切换
        is_positive_jump = recent_diff > baseline_mean

        detected = (
            sigma_level >= sigma_threshold and
            magnitude >= min_magnitude and
            is_positive_jump and
            self._in_ultra_dense  # 只在超致密区检测
        )

        return JumpSignal(
            detected=detected,
            magnitude=magnitude,
            baseline_mean=baseline_mean,
            baseline_std=baseline_std,
            sigma_level=sigma_level,
            timestamp=self._timestamps[-1] if self._timestamps else 0,
        )

    def _detect_critical_slowing_down(self) -> CriticalSlowingDownSignal:
        """检测临界减速 (Critical Slowing Down)

        经典相变预警信号:系统接近相变点时,恢复速率减慢,
        表现为方差增大、自相关增强。

        检测方法:
        1. 将最近 CSD_WINDOW 的方差与更早窗口的方差比较
        2. 计算 lag-1 自相关
        3. 两者同时异常 → 临界减速信号
        """
        window = self._config['csd_window']
        var_ratio = self._config['csd_variance_ratio']
        ac_threshold = self._config['csd_ac_threshold']

        # 需要至少 2*window 个数据点
        if len(self._odi_trajectory) < 2 * window:
            return CriticalSlowingDownSignal()

        odi_list = list(self._odi_trajectory)

        # 近期窗口(最近 window 个点)
        recent = odi_list[-window:]
        # 基线窗口(更早的 window 个点)
        baseline = odi_list[-2*window:-window]

        recent_var = float(np.var(recent))
        baseline_var = float(np.var(baseline))

        var_ratio_val = recent_var / baseline_var if baseline_var > 1e-10 else 1.0

        # Lag-1 自相关(近期窗口)
        if len(recent) >= 2:
            x = np.array(recent[:-1])
            y = np.array(recent[1:])
            x_mean = x.mean()
            y_mean = y.mean()
            numerator = np.sum((x - x_mean) * (y - y_mean))
            denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))
            ac = float(numerator / denominator) if denominator > 1e-10 else 0.0
        else:
            ac = 0.0

        # 临界减速 = 方差**增大**（系统变不稳定）+ 自相关增强
        # 方差减小不是临界减速
        is_variance_increasing = recent_var > baseline_var

        # 两窗口都必须有足够大的绝对方差，避免在平稳段因数值噪声误报
        min_abs_var = self._config['csd_min_absolute_var']
        has_significant_variance = (
            recent_var >= min_abs_var and baseline_var >= min_abs_var
        )

        detected = (
            has_significant_variance and
            is_variance_increasing and
            var_ratio_val >= var_ratio and
            ac >= ac_threshold and
            self._in_ultra_dense
        )

        return CriticalSlowingDownSignal(
            detected=detected,
            recent_variance=recent_var,
            baseline_variance=baseline_var,
            variance_ratio=var_ratio_val,
            lag1_autocorrelation=ac,
            timestamp=self._timestamps[-1] if self._timestamps else 0,
        )

    def _detect_emergence_signature(self) -> EmergenceSignature:
        """检测涌现特征

        在超致密区中检测 ODI 导数突变和轨迹分岔,
        这些是涌现的统计特征。

        检测方法:
        1. 导数异常:ODI 的局部导数超出历史范围
        2. 轨迹分岔:轨迹分裂为不同模式

        返回:
            EmergenceSignature 涌现特征信号
        """
        emergence_odi = self._config['emergence_odi_threshold']
        emergence_window = self._config['emergence_window']
        deriv_threshold = self._config['emergence_derivative_threshold']

        if (not self._in_ultra_dense or
            len(self._odi_trajectory) < emergence_window):
            return EmergenceSignature()

        odi_list = list(self._odi_trajectory)

        # 导数异常检测
        if len(odi_list) >= 4:
            recent_derivs = [
                odi_list[i+1] - odi_list[i]
                for i in range(-4, -1)
            ]
            deriv_mean = float(np.mean(recent_derivs))
            deriv_std = float(np.std(recent_derivs)) if len(recent_derivs) > 1 else 0.001

            latest_deriv = odi_list[-1] - odi_list[-2]

            deriv_anomaly = (
                abs(latest_deriv - deriv_mean) > deriv_threshold and
                deriv_std > 0
            )
        else:
            deriv_anomaly = False

        # 轨迹分岔检测:检查是否出现多模式
        if len(odi_list) >= emergence_window:
            recent = np.array(odi_list[-emergence_window:])
            # 使用自举法检测多模态:
            # 如果轨迹的峰度(kurtosis)显著偏离正态分布,
            # 可能意味着多模式(分岔)
            n = len(recent)
            if n >= 4:
                z = (recent - recent.mean()) / (recent.std() + 1e-10)
                kurtosis = float(np.mean(z**4))
                # 正态分布峰度=3,偏离程度表示多模态可能
                bifurcation = abs(kurtosis - 3) > 1.5
            else:
                bifurcation = False
        else:
            bifurcation = False

        # 涌现需要多信号共同出现才可信
        # 单一信号可能是噪声,两者同时出现才是涌现
        detected = deriv_anomaly and bifurcation and self._in_ultra_dense

        # 构建描述
        parts = []
        if deriv_anomaly:
            parts.append('ODI导数突变')
        if bifurcation:
            parts.append('轨迹分岔(可能多模式)')

        return EmergenceSignature(
            detected=detected,
            derivative_anomaly=deriv_anomaly,
            trajectory_bifurcation=bifurcation,
            critical_odi=odi_list[-1] if odi_list else 0.0,
            signature_description='; '.join(parts) if parts else '',
            timestamp=self._timestamps[-1] if self._timestamps else 0,
        )

    # ─── 分析属性 ───

    @property
    def odi_trajectory(self) -> List[float]:
        """ODI 轨迹"""
        return list(self._odi_trajectory)

    @property
    def diffs_trajectory(self) -> List[float]:
        """差分轨迹"""
        return list(self._diffs)

    @property
    def in_ultra_dense(self) -> bool:
        """是否处于超致密区"""
        return self._in_ultra_dense

    @property
    def transition_count(self) -> int:
        """检测到的相变次数"""
        return self._transition_count

    @property
    def latest_result(self) -> Optional[SeventhThresholdResult]:
        """最近一次检测结果"""
        return self._history[-1] if self._history else None

    @property
    def has_transition_occurred(self) -> bool:
        """是否至少发生过一次相变"""
        return self._transition_count > 0

    def get_transition_history(self) -> List[SeventhThresholdResult]:
        """获取所有检测到的相变"""
        return [r for r in self._history if r.transition_detected]

    def get_trajectory_summary(self) -> Dict:
        """获取轨迹摘要"""
        if not self._odi_trajectory:
            return {'n_points': 0}

        odi_arr = np.array(self._odi_trajectory)
        return {
            'n_points': len(odi_arr),
            'odi_min': float(odi_arr.min()),
            'odi_max': float(odi_arr.max()),
            'odi_mean': float(odi_arr.mean()),
            'odi_std': float(odi_arr.std()),
            'current_odi': float(odi_arr[-1]),
            'in_ultra_dense': self._in_ultra_dense,
            'transition_count': self._transition_count,
            'total_change': float(odi_arr[-1] - odi_arr[0]) if len(odi_arr) > 1 else 0.0,
        }

    def feed_batch(self,
                   odi_results: List[DensityIndexResult]) -> List[SeventhThresholdResult]:
        """批量输入 ODI 结果

        Args:
            odi_results: ODI 计算结果列表

        Returns:
            检测结果列表
        """
        results = []
        for r in odi_results:
            results.append(self.feed(r))
        return results

    def reset(self):
        """重置检测器状态"""
        self._odi_trajectory.clear()
        self._timestamps.clear()
        self._diffs.clear()
        self._in_ultra_dense = False
        self._ultra_dense_entry_odi = 0.0
        self._ultra_dense_entry_step = 0
        self._history.clear()
        self._transition_count = 0
        self._step_count = 0