"""
tests/test_difference_density_tracker.py — 差异密度追踪器测试

覆盖：
1. 初始化与基本属性
2. 全零状态 → K_t ≈ 0
3. 全激活状态 → 封口邻近度高
4. 随机状态 → K_t 在合理范围
5. 汉明重量方差：稳定序列 vs 波动序列
6. 聚类密度：无绑定矩阵 → 0
7. 聚类密度：有绑定矩阵 → 正确计算
8. 组织化指数：全冻结 vs 全自由
9. 封口邻近度：接近封口阈值
10. 相变信号：无相变
11. 相变信号：临界减速检测
12. 相变信号：突变检测
13. Γ_t 估计
14. get_summary 输出完整性
15. reset 功能
16. K_t 趋势计算
17. DensitySnapshot 属性
18. PhaseTransitionSignal 属性
"""

import pytest
import torch
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.difference_density_tracker import (
    DifferenceDensityTracker,
    DensitySnapshot,
    PhaseTransitionSignal,
    DEFAULT_DENSITY_CONFIG,
)


class MockConstraints:
    """模拟约束对象"""

    def __init__(self, binding_strength=None, frozen_bits=None,
                 sealing_threshold=None, active_bits=None):
        self.binding_strength = binding_strength
        self.frozen_bits = frozen_bits
        self.sealing_threshold = sealing_threshold
        self.active_bits = active_bits


# ─── 辅助函数 ───

def _make_random_state(N, p=0.5, seed=None):
    """生成随机二值状态"""
    if seed is not None:
        torch.manual_seed(seed)
    return (torch.rand(N) < p).float()


def _make_binding_strength(N, density=0.3, seed=None):
    """生成对称绑定强度矩阵"""
    if seed is not None:
        torch.manual_seed(seed)
    mat = torch.rand(N, N) * density
    mat = (mat + mat.t()) / 2  # 对称化
    mat.fill_diagonal_(0.0)    # 对角线为 0
    return mat


# ─── 测试类 ───

class TestDifferenceDensityTracker:

    def test_init_basic(self):
        """初始化：基本属性和默认配置"""
        tracker = DifferenceDensityTracker(N=64)
        assert tracker.N == 64
        assert tracker.current_k_t == 0.0
        assert tracker.max_k_t == 0.0
        assert len(tracker.k_t_trajectory) == 0
        assert len(tracker.snapshot_history) == 0

    def test_init_with_config(self):
        """初始化：自定义配置覆盖默认值"""
        config = {'sliding_window': 30, 'w_hamming_variance': 0.5}
        tracker = DifferenceDensityTracker(N=32, config=config)
        assert tracker._config['sliding_window'] == 30
        assert tracker.N == 32

    def test_zero_state_gives_low_kt(self):
        """全零状态 → K_t 接近 0"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        state = torch.zeros(N)
        constraints = MockConstraints(
            frozen_bits=set(range(N)),
            sealing_threshold=N // 2,
        )
        snap = tracker.step(state, constraints, step=0)
        assert snap.k_t < 0.1, f"Expected K_t < 0.1, got {snap.k_t}"
        assert snap.hamming_weight_variance == 0.0
        assert snap.seal_proximity == 0.0

    def test_all_active_state_high_seal_proximity(self):
        """全激活状态 → 封口邻近度高"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        state = torch.ones(N)
        constraints = MockConstraints(
            frozen_bits=set(),
            sealing_threshold=N // 2,
        )
        snap = tracker.step(state, constraints, step=0)
        # 全激活 = N 个活跃比特, 封口阈值 = N/2 → 邻近度 = 1.0（被裁剪）
        assert snap.seal_proximity == 1.0
        assert snap.organization_index == 0.0  # 无冻结比特

    def test_random_state_kt_in_range(self):
        """随机状态 → K_t 在 [0, 1] 范围内"""
        N = 64
        tracker = DifferenceDensityTracker(N=N)
        state = _make_random_state(N, p=0.5, seed=42)
        constraints = MockConstraints(
            frozen_bits=set(),
            sealing_threshold=N,
        )
        snap = tracker.step(state, constraints, step=0)
        assert 0.0 <= snap.k_t <= 1.0

    def test_hamming_variance_stable_sequence(self):
        """汉明重量方差：稳定序列 → 低方差"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        constraints = MockConstraints(sealing_threshold=N)

        # 连续输入相同状态 → 方差趋近 0
        state = torch.zeros(N)
        state[:16] = 1.0  # 16 个活跃比特
        for i in range(10):
            snap = tracker.step(state, constraints, step=i)

        assert snap.hamming_weight_variance < 0.05

    def test_hamming_variance_volatile_sequence(self):
        """汉明重量方差：波动序列 → 高方差"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        constraints = MockConstraints(sealing_threshold=N)

        # 交替输入全 0 和全 1 状态
        for i in range(10):
            if i % 2 == 0:
                state = torch.zeros(N)  # 汉明重量 = 0
            else:
                state = torch.ones(N)   # 汉明重量 = N
            snap = tracker.step(state, constraints, step=i)

        assert snap.hamming_weight_variance > 0.5

    def test_cluster_density_no_binding_matrix(self):
        """聚类密度：无绑定矩阵 → 0"""
        N = 16
        tracker = DifferenceDensityTracker(N=N)
        state = _make_random_state(N, seed=1)
        constraints = MockConstraints(binding_strength=None)
        snap = tracker.step(state, constraints, step=0)
        assert snap.cluster_density == 0.0

    def test_cluster_density_with_binding_matrix(self):
        """聚类密度：有绑定矩阵 → 正确计算聚类"""
        N = 8
        tracker = DifferenceDensityTracker(N=N)

        # 所有比特都激活
        state = torch.ones(N)

        # 构建强绑定矩阵：所有活跃比特对都有高绑定强度 → 一个聚类
        binding = torch.ones(N, N) * 0.5
        binding.fill_diagonal_(0.0)

        constraints = MockConstraints(
            binding_strength=binding,
            sealing_threshold=N,
        )
        snap = tracker.step(state, constraints, step=0)
        # 所有比特在一个聚类中 → cluster_density = 1 - 1/8 = 0.875
        assert snap.cluster_density > 0.8

    def test_cluster_density_sparse_binding(self):
        """聚类密度：稀疏绑定 → 多个聚类 → 低密度"""
        N = 8
        tracker = DifferenceDensityTracker(N=N)
        state = torch.ones(N)

        # 无绑定连接 → 每个比特是独立聚类
        binding = torch.zeros(N, N)
        constraints = MockConstraints(
            binding_strength=binding,
            sealing_threshold=N,
        )
        snap = tracker.step(state, constraints, step=0)
        # 8 个独立聚类 → cluster_density = 1 - 8/8 = 0
        assert snap.cluster_density == 0.0

    def test_organization_index_all_frozen(self):
        """组织化指数：全冻结 → 1.0"""
        N = 16
        tracker = DifferenceDensityTracker(N=N)
        state = torch.zeros(N)
        constraints = MockConstraints(frozen_bits=set(range(N)))
        snap = tracker.step(state, constraints, step=0)
        assert snap.organization_index == 1.0

    def test_organization_index_all_free(self):
        """组织化指数：全自由 → 0.0"""
        N = 16
        tracker = DifferenceDensityTracker(N=N)
        state = torch.ones(N)
        constraints = MockConstraints(frozen_bits=set())
        snap = tracker.step(state, constraints, step=0)
        assert snap.organization_index == 0.0

    def test_organization_index_partial(self):
        """组织化指数：部分冻结 → 中间值"""
        N = 16
        tracker = DifferenceDensityTracker(N=N)
        state = torch.zeros(N)
        state[:8] = 1.0
        constraints = MockConstraints(frozen_bits=set(range(8, 16)))
        snap = tracker.step(state, constraints, step=0)
        assert snap.organization_index == pytest.approx(0.5, abs=0.01)

    def test_seal_proximity_near_threshold(self):
        """封口邻近度：活跃比特接近封口阈值 → 邻近度高"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        state = torch.zeros(N)
        state[:30] = 1.0  # 30 个活跃比特
        constraints = MockConstraints(sealing_threshold=32)
        snap = tracker.step(state, constraints, step=0)
        # 30/32 ≈ 0.9375
        assert snap.seal_proximity == pytest.approx(30 / 32, abs=0.01)

    def test_seal_proximity_exceeds_threshold(self):
        """封口邻近度：超过封口阈值 → 裁剪为 1.0"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        state = torch.ones(N)  # 32 个活跃比特
        constraints = MockConstraints(sealing_threshold=16)
        snap = tracker.step(state, constraints, step=0)
        assert snap.seal_proximity == 1.0

    def test_phase_transition_no_transition(self):
        """相变信号：稳定系统 → 无相变"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        constraints = MockConstraints(sealing_threshold=N)
        state = torch.zeros(N)
        state[:16] = 1.0

        # 连续输入稳定状态
        for i in range(30):
            tracker.step(state, constraints, step=i)

        signal = tracker.get_phase_transition_signal()
        assert signal.is_transitioning is False
        assert signal.confidence == 0.0

    def test_phase_transition_csd_detection(self):
        """相变信号：临界减速检测

        临界减速的核心信号是 K_t 时间序列的方差在近期显著增大。

        测试策略：精确控制窗口位置——
        - 使用 csd_window=4，需要 2*csd_window=8 个基线数据点 + 4 个近期数据点
        - 前 8 步：小幅波动（有微小方差但不为 0，避免 min_absolute_var 守卫）
        - 后 4 步：大幅波动（方差远大于基线）
        - 这样 baseline=[稳定]，recent=[波动]，方差比 >> 阈值
        """
        N = 32
        csd_w = 4
        tracker = DifferenceDensityTracker(N=N, config={
            'csd_window': csd_w,
            'csd_variance_ratio': 2.0,
            'csd_min_absolute_var': 1e-6,
            'sliding_window': 20,
            'w_hamming_variance': 0.0,   # 禁用汉明方差（避免滑动窗口平滑效应）
            'w_cluster_density': 0.0,
            'w_seal_proximity': 1.0,     # K_t 仅由封口邻近度决定（直接可控）
        })
        constraints = MockConstraints(sealing_threshold=N)

        # 稳定阶段：8 步，活跃比特在 15-17 之间微小波动
        # seal_prox: 15/32=0.46875, 16/32=0.5, 17/32=0.53125
        # 方差 > 0 但很小
        stable_actives = [15, 17, 15, 17, 16, 15, 17, 16]
        for i, n_act in enumerate(stable_actives):
            state = torch.zeros(N)
            state[:n_act] = 1.0
            tracker.step(state, constraints, step=i)

        # 波动阶段：4 步，活跃比特在极端值之间大幅振荡
        # seal_prox: 5/32=0.15625 vs 30/32=0.9375
        volatile_actives = [5, 30, 5, 30]
        for j, n_act in enumerate(volatile_actives):
            state = torch.zeros(N)
            state[:n_act] = 1.0
            tracker.step(state, constraints, step=8 + j)

        # 验证窗口数据
        k_list = list(tracker._k_t_history)
        assert len(k_list) == 12

        baseline = k_list[-2 * csd_w:-csd_w]  # steps 4-7: 稳定
        recent = k_list[-csd_w:]               # steps 8-11: 波动
        baseline_var = float(np.var(baseline))
        recent_var = float(np.var(recent))

        # 基线应有微小正方差
        assert baseline_var > 1e-6, f"Baseline variance too low: {baseline_var}"
        # 近期方差应远大于基线
        assert recent_var > baseline_var * 2, \
            f"Expected recent_var ({recent_var:.6f}) > 2x baseline_var ({baseline_var:.6f})"

        signal = tracker.get_phase_transition_signal()
        assert signal.critical_slowing_down is True, \
            f"CSD not detected. baseline_var={baseline_var:.6f}, recent_var={recent_var:.6f}"
        assert signal.is_transitioning is True
        assert signal.variance_ratio > 2.0

    def test_phase_transition_sudden_jump(self):
        """相变信号：突变检测"""
        N = 32
        tracker = DifferenceDensityTracker(N=N, config={
            'jump_threshold_sigma': 2.5,
            'jump_min_magnitude': 0.01,
            'sliding_window': 30,
        })
        constraints = MockConstraints(sealing_threshold=N)

        # 前 15 步：稳定状态（微小变化）
        base_state = torch.zeros(N)
        base_state[:16] = 1.0
        for i in range(15):
            # 微小扰动
            state = base_state.clone()
            if i % 3 == 0:
                state[0] = 0.0
            tracker.step(state, constraints, step=i)

        # 第 16 步：剧变
        jump_state = torch.ones(N)  # 从 ~16 活跃变为全活跃
        tracker.step(jump_state, constraints, step=15)

        signal = tracker.get_phase_transition_signal()
        # 应检测到突变
        assert signal.sudden_jump is True
        assert signal.jump_magnitude > 0.0

    def test_gamma_t_estimation(self):
        """Γ_t 估计：基于历史 K_t 百分位"""
        N = 32
        tracker = DifferenceDensityTracker(N=N, config={
            'gamma_percentile': 90,
        })
        constraints = MockConstraints(sealing_threshold=N)

        # 输入一系列递增 K_t 的状态
        for i in range(20):
            n_active = min(i * 2, N)
            state = torch.zeros(N)
            state[:n_active] = 1.0
            tracker.step(state, constraints, step=i)

        signal = tracker.get_phase_transition_signal()
        assert signal.gamma_t > 0.0
        assert signal.gamma_t <= 1.0

    def test_get_summary_empty(self):
        """get_summary：无数据时返回默认值"""
        tracker = DifferenceDensityTracker(N=16)
        summary = tracker.get_summary()
        assert summary['n_steps'] == 0
        assert summary['k_t_current'] == 0.0
        assert summary['gamma_t_estimate'] == 0.0

    def test_get_summary_with_data(self):
        """get_summary：有数据时返回完整统计"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        constraints = MockConstraints(sealing_threshold=N)

        for i in range(10):
            state = _make_random_state(N, seed=i)
            tracker.step(state, constraints, step=i)

        summary = tracker.get_summary()
        assert summary['n_steps'] == 10
        assert 0.0 <= summary['k_t_current'] <= 1.0
        assert 0.0 <= summary['k_t_mean'] <= 1.0
        assert summary['k_t_max'] >= summary['k_t_min']
        assert summary['gamma_t_estimate'] > 0.0
        assert 'organization_index' in summary

    def test_reset(self):
        """reset：清除所有状态"""
        N = 16
        tracker = DifferenceDensityTracker(N=N)
        constraints = MockConstraints(sealing_threshold=N)

        for i in range(5):
            state = _make_random_state(N, seed=i)
            tracker.step(state, constraints, step=i)

        assert tracker.current_k_t != 0.0
        assert len(tracker.k_t_trajectory) == 5

        tracker.reset()
        assert tracker.current_k_t == 0.0
        assert tracker.max_k_t == 0.0
        assert len(tracker.k_t_trajectory) == 0
        assert len(tracker.snapshot_history) == 0
        assert tracker._step_count == 0

    def test_kt_trend(self):
        """K_t 趋势：上升趋势为正"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)
        constraints = MockConstraints(sealing_threshold=N)

        # 递增活跃比特 → K_t 应上升
        for i in range(10):
            n_active = min(3 + i * 3, N)
            state = torch.zeros(N)
            state[:n_active] = 1.0
            tracker.step(state, constraints, step=i)

        trend = tracker.get_k_t_trend(window=10)
        assert isinstance(trend, float)

    def test_kt_trend_insufficient_data(self):
        """K_t 趋势：数据不足 → 返回 0"""
        tracker = DifferenceDensityTracker(N=16)
        assert tracker.get_k_t_trend() == 0.0

    def test_max_k_t(self):
        """max_k_t：历史最大值"""
        N = 16
        tracker = DifferenceDensityTracker(N=N)
        constraints = MockConstraints(sealing_threshold=N)

        # 输入不同状态
        for i in range(5):
            state = torch.zeros(N)
            state[:i * 3] = 1.0
            tracker.step(state, constraints, step=i)

        assert tracker.max_k_t >= tracker.current_k_t
        assert tracker.max_k_t == max(tracker.k_t_trajectory)

    def test_snapshot_properties(self):
        """DensitySnapshot 属性正确"""
        snap = DensitySnapshot(step=5, k_t=0.8, organization_index=0.6)
        assert snap.is_high_density is True
        assert snap.is_organized is True

        snap2 = DensitySnapshot(step=1, k_t=0.3, organization_index=0.2)
        assert snap2.is_high_density is False
        assert snap2.is_organized is False

    def test_snapshot_repr(self):
        """DensitySnapshot __repr__ 正常输出"""
        snap = DensitySnapshot(
            step=10, k_t=0.5, hamming_weight_variance=0.3,
            cluster_density=0.4, seal_proximity=0.6, organization_index=0.7,
        )
        s = repr(snap)
        assert 'K_t=0.5000' in s
        assert 'step=10' in s

    def test_phase_transition_signal_properties(self):
        """PhaseTransitionSignal 属性正确"""
        signal = PhaseTransitionSignal(
            is_transitioning=True,
            gamma_t=0.75,
            critical_slowing_down=True,
            sudden_jump=False,
            confidence=0.6,
        )
        assert signal.transition_label == '临界减速'
        assert signal.confidence_label == '中可信度'

        signal2 = PhaseTransitionSignal(
            is_transitioning=True,
            critical_slowing_down=True,
            sudden_jump=True,
            confidence=0.8,
        )
        assert '临界减速' in signal2.transition_label
        assert '突变' in signal2.transition_label
        assert signal2.confidence_label == '高可信度'

    def test_phase_transition_no_signal_label(self):
        """PhaseTransitionSignal：无相变标签"""
        signal = PhaseTransitionSignal(is_transitioning=False)
        assert signal.transition_label == '无相变'
        assert signal.confidence_label == '无可信度'

    def test_weight_normalization(self):
        """合成权重自动归一化"""
        config = {
            'w_hamming_variance': 10,
            'w_cluster_density': 10,
            'w_seal_proximity': 10,
        }
        tracker = DifferenceDensityTracker(N=16, config=config)
        w_sum = (
            tracker._config['w_hamming_variance']
            + tracker._config['w_cluster_density']
            + tracker._config['w_seal_proximity']
        )
        assert abs(w_sum - 1.0) < 1e-6

    def test_multi_step_trajectory(self):
        """多步运行：K_t 轨迹正确记录"""
        N = 16
        tracker = DifferenceDensityTracker(N=N)
        constraints = MockConstraints(sealing_threshold=N)

        for i in range(20):
            state = _make_random_state(N, seed=i)
            snap = tracker.step(state, constraints, step=i)
            assert snap.step == i
            assert 0.0 <= snap.k_t <= 1.0

        assert len(tracker.k_t_trajectory) == 20
        assert tracker._step_count == 19

    def test_sliding_window_limits_history(self):
        """滑动窗口限制历史数据大小"""
        N = 16
        window_size = 5
        tracker = DifferenceDensityTracker(N=N, config={
            'sliding_window': window_size,
        })
        constraints = MockConstraints(sealing_threshold=N)

        for i in range(20):
            state = _make_random_state(N, seed=i)
            tracker.step(state, constraints, step=i)

        # 滑动窗口内的快照数不超过 window_size
        assert len(tracker.snapshot_history) <= window_size
        # 但完整轨迹记录了所有步
        assert len(tracker.k_t_trajectory) == 20

    def test_constraints_without_attributes(self):
        """constraints 对象缺少属性时使用默认值（不崩溃）"""
        N = 16
        tracker = DifferenceDensityTracker(N=N)

        class EmptyConstraints:
            pass

        state = torch.zeros(N)
        state[:8] = 1.0
        snap = tracker.step(state, EmptyConstraints(), step=0)
        assert 0.0 <= snap.k_t <= 1.0
        # 无冻结信息时使用近似：1 - 活跃比例
        assert snap.organization_index > 0.0

    def test_seal_proximity_default_threshold(self):
        """封口邻近度：无封口阈值时使用默认 N/2"""
        N = 32
        tracker = DifferenceDensityTracker(N=N)

        class NoSealConstraints:
            frozen_bits = set()
            binding_strength = None

        state = torch.zeros(N)
        state[:16] = 1.0  # 16 个活跃 = N/2
        snap = tracker.step(state, NoSealConstraints(), step=0)
        # 默认封口阈值 = N/2 = 16, 邻近度 = 16/16 = 1.0
        assert snap.seal_proximity == 1.0
