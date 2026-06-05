"""
engine/difference_density_tracker.py — 差异密度追踪器 (DifferenceDensityTracker)

差异论 V1.7 核心指标追踪模块

职责：逐拍追踪系统的"差异密度" K_t，并检测相变信号。

理论依据：
- 差异论 V1.7：K_t（差异密度）表示系统中差异的集中/分散程度
- 当 K_t 达到临界阈值 Γ_t 时，系统发生相变
- K_t 的三维代理度量：
  1. 汉明重量方差（Hamming weight variance）：比特激活分布的方差
  2. 聚类能量密度（cluster density）：绑定强度矩阵中的聚类数
  3. 封口邻近度（seal proximity）：系统距封口条件的接近程度
- 组织化指数（organization index）：冻结比特占比，度量系统从自由到组织化的程度

核心概念：
- K_t = f(hamming_weight_variance, cluster_density, seal_proximity)
  三维加权合成，作为差异密度的连续代理
- 相变检测：通过 K_t 时间序列分析临界减速和突变信号
- 临界减速（critical slowing down）：系统接近相变点时方差增大
- 突变检测（sudden jump）：|K_t - K_{t-1}| 超过阈值

设计原则：
- 纯观测模块，不修改系统状态
- 使用滑动窗口控制内存占用
- 与 OrganizationalDensityIndex（ODI）互补：ODI 度量组织密度，
  DifferenceDensityTracker 度量差异密度
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque


# ─── 默认参数 ───
DEFAULT_DENSITY_CONFIG = {
    # 滑动窗口大小（步数）
    'sliding_window': 20,

    # K_t 合成权重（三项之和为 1.0）
    'w_hamming_variance': 0.40,     # 汉明重量方差权重
    'w_cluster_density': 0.30,      # 聚类密度权重
    'w_seal_proximity': 0.30,       # 封口邻近度权重

    # 聚类检测参数
    'binding_threshold': 0.1,       # 绑定强度阈值（高于此值视为连通）

    # 相变检测参数
    'csd_window': 10,               # 临界减速检测窗口
    'csd_variance_ratio': 2.5,      # 方差比阈值（近期 / 基线）
    'csd_min_absolute_var': 1e-6,   # 最小绝对方差（避免数值噪声触发）
    'jump_threshold_sigma': 3.0,    # 突变检测 σ 倍数
    'jump_min_magnitude': 0.02,     # 最小突变幅度

    # γ_t 估计参数
    'gamma_window': 15,             # γ_t 估计的历史窗口
    'gamma_percentile': 90,         # γ_t 取 K_t 历史百分位
}


@dataclass
class DensitySnapshot:
    """差异密度快照 — 单步计算结果

    记录当前步的差异密度三维度量及合成 K_t 值。
    """
    step: int = 0                            # 当前步数
    hamming_weight_variance: float = 0.0     # 汉明重量方差（K_t 代理 1）
    cluster_density: float = 0.0             # 聚类密度（K_t 代理 2）
    seal_proximity: float = 0.0              # 封口邻近度（K_t 代理 3）
    organization_index: float = 0.0          # 组织化指数 [0, 1]
    k_t: float = 0.0                         # 合成差异密度 K_t

    @property
    def is_high_density(self) -> bool:
        """K_t 是否处于高密度区（超过 0.7）"""
        return self.k_t > 0.7

    @property
    def is_organized(self) -> bool:
        """组织化指数是否超过 0.5（半数以上比特被冻结）"""
        return self.organization_index > 0.5

    def __repr__(self):
        return (
            f"DensitySnapshot[step={self.step}] "
            f"K_t={self.k_t:.4f} "
            f"hamming_var={self.hamming_weight_variance:.4f} "
            f"cluster_d={self.cluster_density:.4f} "
            f"seal_prox={self.seal_proximity:.4f} "
            f"org_idx={self.organization_index:.4f}"
        )


@dataclass
class PhaseTransitionSignal:
    """相变信号 — K_t 时间序列分析结果

    综合临界减速和突变两种检测模式，判断系统是否正在经历相变。
    """
    is_transitioning: bool = False           # 是否正在发生相变
    gamma_t: float = 0.0                     # 估计的临界值 Γ_t
    critical_slowing_down: bool = False      # 是否检测到临界减速
    sudden_jump: bool = False                # 是否检测到突变
    variance_ratio: float = 0.0              # 方差比（近期 / 基线）
    jump_magnitude: float = 0.0              # 突变幅度 |K_t - K_{t-1}|
    confidence: float = 0.0                  # 相变信号可信度 [0, 1]
    step: int = 0

    @property
    def transition_label(self) -> str:
        """相变类型中文标签"""
        if not self.is_transitioning:
            return '无相变'
        parts = []
        if self.critical_slowing_down:
            parts.append('临界减速')
        if self.sudden_jump:
            parts.append('突变')
        return '+'.join(parts) if parts else '未知'

    @property
    def confidence_label(self) -> str:
        """可信度中文标签"""
        if self.confidence >= 0.7:
            return '高可信度'
        elif self.confidence >= 0.4:
            return '中可信度'
        elif self.confidence > 0:
            return '低可信度'
        return '无可信度'

    def __repr__(self):
        return (
            f"PhaseTransition[{self.transition_label}] "
            f"gamma_t={self.gamma_t:.4f} conf={self.confidence:.2f} "
            f"({self.confidence_label})"
        )


class DifferenceDensityTracker:
    """差异密度追踪器

    逐拍追踪系统的差异密度 K_t，并分析相变信号。

    K_t 由三维代理度量加权合成：
    1. 汉明重量方差：滑动窗口内比特激活分布的方差
    2. 聚类密度：绑定强度矩阵中的聚类数 / 系统体积
    3. 封口邻近度：活跃比特数 / 封口阈值

    相变检测：
    - 临界减速（CSD）：K_t 近期方差相对基线方差显著增大
    - 突变检测：|K_t - K_{t-1}| 超出历史基线的 Nσ

    使用方式：
        tracker = DifferenceDensityTracker(N=64)
        for step in range(max_steps):
            snapshot = tracker.step(state, constraints, step)
            signal = tracker.get_phase_transition_signal()
            if signal.is_transitioning:
                print(f"相变! K_t={snapshot.k_t:.4f}, Γ_t={signal.gamma_t:.4f}")
    """

    def __init__(self, N: int, config: Optional[Dict] = None):
        """初始化差异密度追踪器

        Args:
            N: 系统大小（比特数）
            config: 配置参数，覆盖 DEFAULT_DENSITY_CONFIG
        """
        self.N = N

        self._config = dict(DEFAULT_DENSITY_CONFIG)
        if config:
            self._config.update(config)

        # 归一化合成权重
        w_total = (
            self._config['w_hamming_variance']
            + self._config['w_cluster_density']
            + self._config['w_seal_proximity']
        )
        if w_total > 0:
            self._config['w_hamming_variance'] /= w_total
            self._config['w_cluster_density'] /= w_total
            self._config['w_seal_proximity'] /= w_total

        # 滑动窗口大小
        window = self._config['sliding_window']

        # 历史数据（滑动窗口）
        self._k_t_history: deque = deque(maxlen=window)
        self._snapshot_history: deque = deque(maxlen=window)
        self._state_window: deque = deque(maxlen=window)

        # 全量 K_t 轨迹（不受窗口限制，用于 γ_t 估计）
        self._k_t_trajectory: List[float] = []

        # 步计数
        self._step_count: int = 0

    def step(self, state: torch.Tensor, constraints, step: int) -> DensitySnapshot:
        """单步计算差异密度快照

        在每个模拟步调用，计算当前步的三维度量和合成 K_t。

        Args:
            state: 当前系统状态 (N,)，二值张量（0/1）
            constraints: 约束对象，期望包含以下属性（均为可选）：
                - binding_strength: torch.Tensor (N, N) 绑定强度矩阵
                - frozen_bits: set 冻结比特索引集合
                - sealing_threshold: int 封口阈值（活跃比特数低于此值触发封口）
                - active_bits: set 活跃比特索引集合
            step: 当前步数

        Returns:
            DensitySnapshot 差异密度快照
        """
        self._step_count = step

        # 先将当前状态加入滑动窗口（确保方差计算包含当前步）
        self._state_window.append(state.clone())

        # ── 1. 汉明重量方差 ──
        hamming_var = self._compute_hamming_weight_variance(state)

        # ── 2. 聚类密度 ──
        cluster_d = self._compute_cluster_density(state, constraints)

        # ── 3. 封口邻近度 ──
        seal_prox = self._compute_seal_proximity(state, constraints)

        # ── 4. 组织化指数 ──
        org_idx = self._compute_organization_index(state, constraints)

        # ── 5. 合成 K_t ──
        k_t = (
            self._config['w_hamming_variance'] * hamming_var
            + self._config['w_cluster_density'] * cluster_d
            + self._config['w_seal_proximity'] * seal_prox
        )
        k_t = float(np.clip(k_t, 0.0, 1.0))

        snapshot = DensitySnapshot(
            step=step,
            hamming_weight_variance=hamming_var,
            cluster_density=cluster_d,
            seal_proximity=seal_prox,
            organization_index=org_idx,
            k_t=k_t,
        )

        # 更新历史
        self._k_t_history.append(k_t)
        self._snapshot_history.append(snapshot)
        self._k_t_trajectory.append(k_t)

        return snapshot

    def get_phase_transition_signal(self) -> PhaseTransitionSignal:
        """分析 K_t 时间序列，检测相变信号

        综合两种检测模式：
        1. 临界减速（CSD）：近期 K_t 方差相对基线显著增大
        2. 突变检测：最近一步 |K_t - K_{t-1}| 超出历史基线 Nσ

        Returns:
            PhaseTransitionSignal 相变信号
        """
        csd = self._detect_critical_slowing_down()
        jump = self._detect_sudden_jump()

        # γ_t 估计：取 K_t 历史轨迹的高百分位
        gamma_t = self._estimate_gamma_t()

        # 融合判定
        active_signals = []
        confidence_scores = []

        if csd['detected']:
            active_signals.append('csd')
            # 方差比越大越可信
            conf = min(0.3 + 0.1 * (csd['variance_ratio'] - 1.0), 0.7)
            confidence_scores.append(conf)

        if jump['detected']:
            active_signals.append('jump')
            # σ 水平越高越可信
            conf = min(0.3 + 0.1 * (jump['sigma_level'] - 2.0), 0.8)
            confidence_scores.append(conf)

        if not active_signals:
            return PhaseTransitionSignal(
                is_transitioning=False,
                gamma_t=gamma_t,
                step=self._step_count,
            )

        is_csd = 'csd' in active_signals
        is_jump = 'jump' in active_signals

        # 多信号融合加成
        base_conf = max(confidence_scores) if confidence_scores else 0.0
        if len(active_signals) > 1:
            confidence = min(base_conf + 0.15, 1.0)
        else:
            confidence = base_conf

        # 突变幅度
        jump_mag = jump.get('magnitude', 0.0)

        return PhaseTransitionSignal(
            is_transitioning=True,
            gamma_t=gamma_t,
            critical_slowing_down=is_csd,
            sudden_jump=is_jump,
            variance_ratio=csd.get('variance_ratio', 0.0),
            jump_magnitude=jump_mag,
            confidence=confidence,
            step=self._step_count,
        )

    def get_summary(self) -> dict:
        """返回差异密度追踪器的摘要统计

        Returns:
            包含 K_t 统计信息、当前状态、相变历史的字典
        """
        if not self._k_t_trajectory:
            return {
                'n_steps': 0,
                'k_t_current': 0.0,
                'k_t_mean': 0.0,
                'k_t_std': 0.0,
                'k_t_max': 0.0,
                'k_t_min': 0.0,
                'gamma_t_estimate': 0.0,
                'organization_index': 0.0,
            }

        k_arr = np.array(self._k_t_trajectory)

        # 最新快照
        latest = self._snapshot_history[-1] if self._snapshot_history else None
        org_idx = latest.organization_index if latest else 0.0

        return {
            'n_steps': len(self._k_t_trajectory),
            'k_t_current': float(k_arr[-1]),
            'k_t_mean': float(k_arr.mean()),
            'k_t_std': float(k_arr.std()),
            'k_t_max': float(k_arr.max()),
            'k_t_min': float(k_arr.min()),
            'gamma_t_estimate': self._estimate_gamma_t(),
            'organization_index': org_idx,
        }

    # ────────────────────────────────────────────────────────
    # 内部计算方法
    # ────────────────────────────────────────────────────────

    def _compute_hamming_weight_variance(self, state: torch.Tensor) -> float:
        """计算汉明重量方差（滑动窗口内）

        汉明重量 = 状态中 1 的个数。
        在滑动窗口内计算各步汉明重量的方差，作为 K_t 的第一代理。
        方差越大，表示系统比特激活模式越不稳定 → 差异密度越高。

        归一化：方差 / (N/4)，使随机二值序列的归一化方差约为 1.0
        （二项分布 B(N, 0.5) 的方差为 N/4）。

        Args:
            state: 当前系统状态 (N,)

        Returns:
            归一化汉明重量方差 [0, 1]
        """
        # 从滑动窗口中提取各步的汉明重量
        # （当前步的状态已在 step() 开头被追加到窗口中）
        weights = []
        for s in self._state_window:
            weights.append(float(s.sum().item()))

        if len(weights) < 2:
            return 0.0

        var = float(np.var(weights))

        # 归一化
        max_expected_var = self.N / 4.0  # 二项分布 B(N, 0.5) 的方差
        if max_expected_var > 0:
            normalized_var = var / max_expected_var
        else:
            normalized_var = 0.0

        return float(np.clip(normalized_var, 0.0, 1.0))

    def _compute_cluster_density(self, state: torch.Tensor, constraints) -> float:
        """计算聚类密度

        使用绑定强度矩阵，通过 Union-Find 计算连通分量（聚类）数，
        然后除以系统体积 N 归一化。

        聚类密度高 → 系统中差异集中在少数密集簇 → K_t 高。

        Args:
            state: 当前系统状态 (N,)
            constraints: 约束对象

        Returns:
            归一化聚类密度 [0, 1]
        """
        binding_strength = getattr(constraints, 'binding_strength', None)

        if binding_strength is None or not isinstance(binding_strength, torch.Tensor):
            return 0.0

        N = state.shape[0]
        if N == 0:
            return 0.0

        threshold = self._config['binding_threshold']

        # 获取活跃比特索引
        active_indices = torch.where(state > 0.5)[0].tolist()
        n_active = len(active_indices)

        if n_active < 2:
            # 活跃比特不足 2 个，无法形成聚类
            return 0.0

        # Union-Find 聚类
        parent = list(range(n_active))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        # 在活跃比特之间建立连通关系
        for i_idx in range(n_active):
            for j_idx in range(i_idx + 1, n_active):
                i_global = active_indices[i_idx]
                j_global = active_indices[j_idx]
                if (i_global < binding_strength.shape[0]
                        and j_global < binding_strength.shape[1]):
                    if binding_strength[i_global][j_global].item() > threshold:
                        union(i_idx, j_idx)

        # 统计连通分量数
        roots = set()
        for i in range(n_active):
            roots.add(find(i))
        n_clusters = len(roots)

        # 归一化：聚类数 / 活跃比特数
        # 当每个活跃比特都是独立聚类时，密度 = 1/N（最大分散）
        # 当所有活跃比特形成一个聚类时，密度 = 1/N（最集中）
        # 我们使用 1 - (n_clusters / n_active) 使聚类越集中值越高
        if n_active > 0:
            cluster_d = 1.0 - (n_clusters / n_active)
        else:
            cluster_d = 0.0

        return float(np.clip(cluster_d, 0.0, 1.0))

    def _compute_seal_proximity(self, state: torch.Tensor, constraints) -> float:
        """计算封口邻近度

        封口邻近度 = 活跃比特数 / 封口阈值。
        当活跃比特数接近封口阈值时，邻近度趋近 1.0。
        超过阈值时裁剪为 1.0。

        理论含义：系统越接近封口条件，差异被"锁定"的可能性越高 → K_t 升高。

        Args:
            state: 当前系统状态 (N,)
            constraints: 约束对象

        Returns:
            封口邻近度 [0, 1]
        """
        sealing_threshold = getattr(constraints, 'sealing_threshold', None)

        if sealing_threshold is None or sealing_threshold <= 0:
            # 无封口阈值信息，使用默认值：N 的一半
            sealing_threshold = max(self.N // 2, 1)

        # 活跃比特数
        active_count = float(state.sum().item()) if state.numel() > 0 else 0.0

        # 邻近度 = 活跃比特数 / 封口阈值
        proximity = active_count / sealing_threshold

        return float(np.clip(proximity, 0.0, 1.0))

    def _compute_organization_index(self, state: torch.Tensor, constraints) -> float:
        """计算组织化指数

        组织化指数 = 冻结比特数 / 总比特数 N。
        0 = 全自由（无冻结比特），1 = 全组织化（全部冻结）。

        如果 constraints 中无 frozen_bits 信息，
        则使用 (1 - 活跃比例) 作为近似。

        Args:
            state: 当前系统状态 (N,)
            constraints: 约束对象

        Returns:
            组织化指数 [0, 1]
        """
        frozen_bits = getattr(constraints, 'frozen_bits', None)

        if frozen_bits is not None and isinstance(frozen_bits, (set, frozenset, list)):
            n_frozen = len(frozen_bits)
            return float(np.clip(n_frozen / max(self.N, 1), 0.0, 1.0))

        # 近似：冻结比特 = 状态为 0 的比特
        # （在某些实现中，冻结比特保持固定值，这里用 0 作为默认）
        n_total = state.numel() if state.numel() > 0 else self.N
        n_active = float(state.sum().item()) if state.numel() > 0 else 0.0
        n_frozen_approx = n_total - n_active

        return float(np.clip(n_frozen_approx / max(n_total, 1), 0.0, 1.0))

    # ────────────────────────────────────────────────────────
    # 相变检测内部方法
    # ────────────────────────────────────────────────────────

    def _detect_critical_slowing_down(self) -> Dict:
        """检测临界减速（CSD）

        将 K_t 时间序列分为近期窗口和基线窗口，比较方差。
        方差比超过阈值 → 检测到临界减速。

        Returns:
            {'detected': bool, 'variance_ratio': float,
             'recent_var': float, 'baseline_var': float}
        """
        csd_window = self._config['csd_window']
        var_ratio_threshold = self._config['csd_variance_ratio']
        min_abs_var = self._config['csd_min_absolute_var']

        if len(self._k_t_history) < 2 * csd_window:
            return {'detected': False, 'variance_ratio': 0.0,
                    'recent_var': 0.0, 'baseline_var': 0.0}

        k_list = list(self._k_t_history)
        recent = k_list[-csd_window:]
        baseline = k_list[-2 * csd_window:-csd_window]

        recent_var = float(np.var(recent))
        baseline_var = float(np.var(baseline))

        # 避免除零
        if baseline_var < min_abs_var:
            return {'detected': False, 'variance_ratio': 0.0,
                    'recent_var': recent_var, 'baseline_var': baseline_var}

        var_ratio = recent_var / baseline_var

        # 临界减速：方差**增大**（系统变不稳定）
        detected = (
            recent_var >= min_abs_var
            and recent_var > baseline_var
            and var_ratio >= var_ratio_threshold
        )

        return {
            'detected': detected,
            'variance_ratio': var_ratio,
            'recent_var': recent_var,
            'baseline_var': baseline_var,
        }

    def _detect_sudden_jump(self) -> Dict:
        """检测 K_t 突变

        计算最近一步的 |K_t - K_{t-1}|，与历史差分序列的均值和标准差比较。
        超出 Nσ 且幅度超过最小阈值 → 检测到突变。

        Returns:
            {'detected': bool, 'magnitude': float, 'sigma_level': float}
        """
        sigma_threshold = self._config['jump_threshold_sigma']
        min_magnitude = self._config['jump_min_magnitude']

        if len(self._k_t_history) < 4:
            return {'detected': False, 'magnitude': 0.0, 'sigma_level': 0.0}

        k_list = list(self._k_t_history)

        # 最近一步的变化
        latest_diff = abs(k_list[-1] - k_list[-2])

        # 历史差分序列
        diffs = [abs(k_list[i] - k_list[i - 1]) for i in range(1, len(k_list) - 1)]
        if not diffs:
            return {'detected': False, 'magnitude': latest_diff, 'sigma_level': 0.0}

        diff_mean = float(np.mean(diffs))
        diff_std = float(np.std(diffs))

        # 防止除零
        if diff_std < 1e-8:
            diff_std = 0.005

        sigma_level = abs(latest_diff - diff_mean) / diff_std

        detected = (
            sigma_level >= sigma_threshold
            and latest_diff >= min_magnitude
        )

        return {
            'detected': detected,
            'magnitude': latest_diff,
            'sigma_level': sigma_level,
        }

    def _estimate_gamma_t(self) -> float:
        """估计临界阈值 Γ_t

        使用 K_t 全量轨迹的高百分位作为 Γ_t 的估计。
        随着数据积累，估计逐渐收敛。

        Returns:
            估计的 Γ_t 值
        """
        gamma_window = self._config['gamma_window']
        percentile = self._config['gamma_percentile']

        if not self._k_t_trajectory:
            return 0.0

        # 使用最近 gamma_window 个数据点（或全部，取较小者）
        recent = self._k_t_trajectory[-gamma_window:]
        if len(recent) < 3:
            return float(max(recent))

        gamma = float(np.percentile(recent, percentile))
        return gamma

    # ────────────────────────────────────────────────────────
    # 属性与工具方法
    # ────────────────────────────────────────────────────────

    @property
    def current_k_t(self) -> float:
        """当前 K_t 值"""
        if not self._k_t_trajectory:
            return 0.0
        return self._k_t_trajectory[-1]

    @property
    def max_k_t(self) -> float:
        """历史最大 K_t 值"""
        if not self._k_t_trajectory:
            return 0.0
        return max(self._k_t_trajectory)

    @property
    def k_t_trajectory(self) -> List[float]:
        """完整 K_t 轨迹"""
        return list(self._k_t_trajectory)

    @property
    def snapshot_history(self) -> List[DensitySnapshot]:
        """快照历史（滑动窗口内）"""
        return list(self._snapshot_history)

    def get_k_t_trend(self, window: int = 10) -> float:
        """K_t 趋势：最近 N 步的线性回归斜率

        Args:
            window: 回归窗口大小

        Returns:
            斜率值（正 = K_t 上升，负 = K_t 下降）
        """
        if len(self._k_t_trajectory) < 2:
            return 0.0

        recent = self._k_t_trajectory[-window:]
        if len(recent) < 2:
            return 0.0

        x = np.arange(len(recent))
        slope = float(np.polyfit(x, recent, 1)[0])
        return slope

    def reset(self):
        """重置追踪器状态"""
        self._k_t_history.clear()
        self._snapshot_history.clear()
        self._state_window.clear()
        self._k_t_trajectory.clear()
        self._step_count = 0
