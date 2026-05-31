"""
tests/test_adaptive_momentum_controller.py — AdaptiveMomentumController 单元测试

覆盖：
- MomentumEntropyTracker：熵计算
- InstitutionalDensityMonitor：积累速率追踪
- AdaptiveMomentumController：模式检测、调节约束、响应延迟
- 两种失败模式的响应策略
"""

import pytest
import numpy as np

from engine.adaptive_momentum_controller import (
    AdaptiveMomentumController,
    MomentumEntropyTracker,
    InstitutionalDensityMonitor,
    DEFAULT_ADAPTIVE_MOMENTUM_CONFIG,
)


# ─── MomentumEntropyTracker ───

class TestMomentumEntropyTracker:

    def test_empty_entropy_is_neutral(self):
        """无数据时返回中性熵 0.5"""
        tracker = MomentumEntropyTracker()
        assert tracker.compute_entropy() == 0.5

    def test_single_category_max_concentration(self):
        """单一范畴 → 熵接近 0（极度集中）"""
        tracker = MomentumEntropyTracker()
        for _ in range(10):
            tracker.record({'cat_A': 1.0})
        entropy = tracker.compute_entropy()
        assert entropy < 0.1, f"Expected near-0 entropy, got {entropy}"

    def test_uniform_distribution_high_entropy(self):
        """均匀分布 → 熵接近 1"""
        tracker = MomentumEntropyTracker()
        for _ in range(20):
            tracker.record({'cat_A': 1.0, 'cat_B': 1.0, 'cat_C': 1.0, 'cat_D': 1.0})
        entropy = tracker.compute_entropy()
        assert entropy > 0.9, f"Expected near-1 entropy, got {entropy}"

    def test_two_categories_moderate_entropy(self):
        """两个范畴 → 中等熵"""
        tracker = MomentumEntropyTracker()
        for _ in range(20):
            tracker.record({'cat_A': 1.0, 'cat_B': 1.0})
        entropy = tracker.compute_entropy()
        assert 0.5 < entropy <= 1.0, f"Expected moderate entropy, got {entropy}"

    def test_imbalanced_two_categories(self):
        """两个范畴但比例悬殊 → 熵低于均匀"""
        tracker = MomentumEntropyTracker()
        for _ in range(20):
            tracker.record({'cat_A': 10.0, 'cat_B': 0.1})
        entropy = tracker.compute_entropy()
        assert entropy < 0.8, f"Expected lower entropy for imbalanced, got {entropy}"

    def test_window_size_respected(self):
        """窗口大小限制被遵守"""
        tracker = MomentumEntropyTracker({'entropy_window': 5})
        for i in range(20):
            tracker.record({f'cat_{i}': 1.0})
        assert tracker.n_records == 5


# ─── InstitutionalDensityMonitor ───

class TestInstitutionalDensityMonitor:

    def test_empty_count_is_zero(self):
        """无数据时返回 0"""
        monitor = InstitutionalDensityMonitor()
        assert monitor.get_current_count() == 0
        assert monitor.get_accumulation_rate() == 0.0

    def test_accumulation_rate_positive(self):
        """INSTITUTIONAL 积累 → 正速率"""
        monitor = InstitutionalDensityMonitor()
        monitor.record(10, step=0)
        monitor.record(60, step=100)
        rate = monitor.get_accumulation_rate()
        assert rate > 0.0, f"Expected positive rate, got {rate}"
        assert abs(rate - 0.5) < 0.01, f"Expected ~0.5, got {rate}"

    def test_accumulation_rate_zero(self):
        """INSTITUTIONAL 不积累 → 零速率"""
        monitor = InstitutionalDensityMonitor()
        monitor.record(10, step=0)
        monitor.record(10, step=100)
        rate = monitor.get_accumulation_rate()
        assert abs(rate) < 1e-6, f"Expected ~0, got {rate}"

    def test_under_accumulated(self):
        """INSTITUTIONAL < min → under_accumulated"""
        monitor = InstitutionalDensityMonitor()
        monitor.record(10, step=0)
        assert monitor.is_under_accumulated()

    def test_not_under_accumulated(self):
        """INSTITUTIONAL >= min → not under_accumulated"""
        monitor = InstitutionalDensityMonitor()
        monitor.record(60, step=0)
        assert not monitor.is_under_accumulated()

    def test_over_accumulated(self):
        """INSTITUTIONAL > 3*min → over_accumulated"""
        monitor = InstitutionalDensityMonitor()
        monitor.record(200, step=0)
        assert monitor.is_over_accumulated()


# ─── AdaptiveMomentumController ───

class TestAdaptiveMomentumController:

    def test_default_momentum_bonus(self):
        """默认动量加成"""
        ctrl = AdaptiveMomentumController()
        assert ctrl.momentum_bonus == pytest.approx(0.3)

    def test_response_delay_no_adjustment(self):
        """响应延迟内不调节"""
        ctrl = AdaptiveMomentumController({'response_delay_steps': 20})
        for i in range(20):
            result = ctrl.step({'cat_A': 1.0}, institutional_count=5, civilization_count=0)
        # 前 20 步不应有调节
        assert result.adjustment == pytest.approx(0.0)

    def test_adjustment_after_delay(self):
        """响应延迟后开始调节"""
        ctrl = AdaptiveMomentumController({'response_delay_steps': 5})
        for i in range(6):
            result = ctrl.step({'cat_A': 1.0}, institutional_count=5, civilization_count=0)
        # 第 6 步开始可能有调节（取决于熵偏差）
        # 单一范畴 → 熵低 → 调节量应为负（扩散）
        # 注意：第 6 步是延迟后的第一步
        history = ctrl.get_history()
        assert history['step_count'] == 6

    def test_adjustment_bounded_per_step(self):
        """每步调节幅度有界"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 0,
            'max_adjustment_per_step': 0.05,
        })
        # 使用极端输入
        for i in range(50):
            result = ctrl.step({'cat_A': 100.0}, institutional_count=0, civilization_count=0)
            assert abs(result.adjustment) <= 0.05 + 1e-8, \
                f"Step {i}: adjustment={result.adjustment} exceeds bound"

    def test_momentum_bonus_bounded(self):
        """动量加成始终在 [min, max] 范围内"""
        ctrl = AdaptiveMomentumController({
            'min_momentum_bonus': 0.1,
            'max_momentum_bonus': 0.5,
            'response_delay_steps': 0,
        })
        # 运行 200 步，使用各种输入
        for i in range(200):
            if i % 2 == 0:
                result = ctrl.step({'cat_A': 100.0}, institutional_count=0, civilization_count=0)
            else:
                result = ctrl.step(
                    {f'cat_{j}': 1.0 for j in range(10)},
                    institutional_count=200, civilization_count=10,
                )
            assert 0.1 - 1e-8 <= result.momentum_bonus <= 0.5 + 1e-8, \
                f"Step {i}: momentum_bonus={result.momentum_bonus} out of bounds"

    def test_stability_trap_mode_detection(self):
        """模式 A 检测：INSTITUTIONAL 高但 CIV 低"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 0,
            'stability_trap_threshold': 0.8,
        })
        # INSTITUTIONAL > 50*0.8=40, CIV < 3
        for i in range(30):
            result = ctrl.step({'cat_A': 1.0}, institutional_count=50, civilization_count=1)
        assert result.mode == 'stability_trap'

    def test_fragmentation_mode_detection(self):
        """模式 B 检测：动量高但 INSTITUTIONAL 极低"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 0,
            'fragmentation_threshold': 0.2,
        })
        # 先让动量升高
        ctrl._current_momentum_bonus = 0.4
        # INSTITUTIONAL < 50*0.2=10
        for i in range(30):
            result = ctrl.step({'cat_A': 5.0, 'cat_B': 5.0}, institutional_count=5, civilization_count=0)
        assert result.mode == 'fragmentation'

    def test_normal_mode(self):
        """正常模式：INSTITUTIONAL 适中，CIV 适中"""
        ctrl = AdaptiveMomentumController({'response_delay_steps': 0})
        for i in range(30):
            result = ctrl.step(
                {'cat_A': 1.0, 'cat_B': 1.0, 'cat_C': 1.0},
                institutional_count=60, civilization_count=5,
            )
        assert result.mode == 'normal'

    def test_stability_trap_increases_momentum(self):
        """模式 A → 动量增加（帮助跨越到 CIVILIZATION）"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 0,
            'default_momentum_bonus': 0.3,
        })
        initial = ctrl.momentum_bonus
        # 模拟模式 A：INSTITUTIONAL 高但 CIV 低
        for i in range(50):
            result = ctrl.step({'cat_A': 1.0}, institutional_count=60, civilization_count=1)
        # 动量应该增加
        assert result.momentum_bonus > initial, \
            f"Expected momentum increase, got {result.momentum_bonus} <= {initial}"

    def test_fragmentation_decreases_momentum(self):
        """模式 B → 动量减少（防止进一步碎片化）"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 0,
            'default_momentum_bonus': 0.4,
        })
        initial = ctrl.momentum_bonus
        # 模拟模式 B：INSTITUTIONAL 极低
        for i in range(50):
            result = ctrl.step({'cat_A': 5.0, 'cat_B': 5.0}, institutional_count=5, civilization_count=0)
        # 动量应该减少
        assert result.momentum_bonus < initial, \
            f"Expected momentum decrease, got {result.momentum_bonus} >= {initial}"

    def test_low_entropy_triggers_diffuse(self):
        """熵过低 → should_diffuse"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 0,
            'entropy_low_threshold': 0.3,
        })
        for i in range(20):
            result = ctrl.step({'cat_A': 100.0}, institutional_count=50, civilization_count=2)
        assert result.should_diffuse

    def test_high_entropy_triggers_focus(self):
        """熵过高 → should_focus"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 0,
            'entropy_high_threshold': 0.7,
        })
        for i in range(20):
            result = ctrl.step(
                {f'cat_{j}': 1.0 for j in range(20)},
                institutional_count=50, civilization_count=2,
            )
        assert result.should_focus

    def test_reset(self):
        """重置后状态恢复默认"""
        ctrl = AdaptiveMomentumController({'response_delay_steps': 0})
        for i in range(50):
            ctrl.step({'cat_A': 1.0}, institutional_count=5, civilization_count=0)
        ctrl.reset()
        assert ctrl.momentum_bonus == pytest.approx(0.3)
        assert ctrl.get_history()['step_count'] == 0

    def test_history_tracking(self):
        """历史追踪正常工作"""
        ctrl = AdaptiveMomentumController({'response_delay_steps': 0})
        for i in range(30):
            ctrl.step({'cat_A': 1.0}, institutional_count=10, civilization_count=0)
        history = ctrl.get_history()
        assert history['step_count'] == 30
        assert history['n_adjustments'] > 0
        assert 'mean_adjustment' in history
        assert 'entropy' in history
        assert 'institutional_count' in history
        assert 'institutional_rate' in history

    def test_empty_category_heats(self):
        """空范畴热度不崩溃"""
        ctrl = AdaptiveMomentumController({'response_delay_steps': 0})
        result = ctrl.step({}, institutional_count=50, civilization_count=2)
        assert result.momentum_bonus is not None

    def test_single_step_result_fields(self):
        """结果对象包含所有必要字段"""
        ctrl = AdaptiveMomentumController({'response_delay_steps': 0})
        result = ctrl.step({'cat_A': 1.0}, institutional_count=50, civilization_count=2)
        assert hasattr(result, 'momentum_bonus')
        assert hasattr(result, 'entropy')
        assert hasattr(result, 'institutional_count')
        assert hasattr(result, 'institutional_rate')
        assert hasattr(result, 'adjustment')
        assert hasattr(result, 'mode')
        assert hasattr(result, 'should_diffuse')
        assert hasattr(result, 'should_focus')
        assert hasattr(result, 'step')
        assert hasattr(result, 'state')


# ─── 集成行为测试 ───

class TestAdaptiveMomentumControllerIntegration:

    def test_convergence_from_stability_trap(self):
        """模式 A 场景：动量应逐步增加直到离开陷阱"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 5,
            'default_momentum_bonus': 0.15,  # 从低动量开始
            'max_adjustment_per_step': 0.05,
        })
        trajectory = []
        for i in range(100):
            result = ctrl.step(
                {'cat_A': 1.0, 'cat_B': 0.8},  # 略偏 cat_A
                institutional_count=60,  # INSTITUTIONAL 丰富
                civilization_count=1,    # CIV 低 → 陷阱
            )
            trajectory.append(result.momentum_bonus)

        # 动量应该总体呈上升趋势
        early_mean = np.mean(trajectory[5:25])
        late_mean = np.mean(trajectory[75:100])
        assert late_mean > early_mean, \
            f"Expected momentum to increase: early={early_mean:.4f} late={late_mean:.4f}"

    def test_convergence_from_fragmentation(self):
        """模式 B 场景：动量应逐步减少以恢复结构"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 5,
            'default_momentum_bonus': 0.45,  # 从高动量开始
            'max_adjustment_per_step': 0.05,
        })
        trajectory = []
        for i in range(100):
            result = ctrl.step(
                {f'cat_{j}': float(j + 1) for j in range(5)},  # 分散热度
                institutional_count=5,  # INSTITUTIONAL 极低
                civilization_count=0,
            )
            trajectory.append(result.momentum_bonus)

        # 动量应该总体呈下降趋势
        early_mean = np.mean(trajectory[5:25])
        late_mean = np.mean(trajectory[75:100])
        assert late_mean < early_mean, \
            f"Expected momentum to decrease: early={early_mean:.4f} late={late_mean:.4f}"

    def test_normal_mode_stable_momentum(self):
        """正常模式：动量应保持相对稳定"""
        ctrl = AdaptiveMomentumController({
            'response_delay_steps': 5,
            'default_momentum_bonus': 0.3,
        })
        trajectory = []
        for i in range(100):
            result = ctrl.step(
                {'cat_A': 1.0, 'cat_B': 1.0, 'cat_C': 1.0},
                institutional_count=60,
                civilization_count=5,
            )
            trajectory.append(result.momentum_bonus)

        # 动量变化应较小（标准差 < 0.1）
        std = np.std(trajectory[10:])
        assert std < 0.1, f"Expected stable momentum, got std={std:.4f}"
