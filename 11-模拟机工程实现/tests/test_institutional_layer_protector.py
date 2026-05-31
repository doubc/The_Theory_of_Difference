"""
tests/test_institutional_layer_protector.py — InstitutionalLayerProtector 单元测试

覆盖：
- AccumulationGuard：保护级别判定、消耗速率限制、冷却机制
- TransitionGate：转换门控评估、冷却机制、开放度计算
- DiversityEnforcer：多样性追踪、熵计算、补偿信号
- InstitutionalLayerProtector：集成行为
"""

import pytest
import numpy as np

from engine.institutional_layer_protector import (
    AccumulationGuard,
    TransitionGate,
    DiversityEnforcer,
    InstitutionalLayerProtector,
    DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG,
)


# ─── AccumulationGuard ───

class TestAccumulationGuard:

    def test_empty_state_no_protection(self):
        """初始状态：无保护"""
        guard = AccumulationGuard()
        rate, level, should = guard.step(100)
        assert level == 'none'
        assert should

    def test_below_floor_strong_protection(self):
        """低于地板值 → 强保护"""
        guard = AccumulationGuard()
        rate, level, should = guard.step(10)
        assert level == 'strong'
        assert not should
        assert rate < 0.02

    def test_below_threshold_weak_protection(self):
        """低于阈值但高于地板 → 弱保护"""
        guard = AccumulationGuard()
        # threshold=35, floor=20, so use value in [20, 35)
        rate, level, should = guard.step(28)
        assert level == 'weak'

    def test_above_threshold_no_protection(self):
        """高于阈值 → 无保护"""
        guard = AccumulationGuard()
        rate, level, should = guard.step(60)
        assert level == 'none'

    def test_consumption_cooldown(self):
        """消耗后冷却期内不允许再次消耗"""
        guard = AccumulationGuard({'consumption_cooldown_steps': 10})
        # 第一次：允许消耗
        _, _, should1 = guard.step(60)
        assert should1
        # 记录消耗
        guard.record_consumption(1)
        # 冷却期内（steps 2-10, 共9步）：不允许
        for i in range(2, 11):
            _, _, should = guard.step(60)
            assert not should, f"Step {i}: should not consume during cooldown"
        # 冷却期后（step 11, 距消耗步数=10 >= cooldown=10）：允许
        _, _, should_after = guard.step(60)
        assert should_after

    def test_rate_limit_bounds(self):
        """消耗速率限制在合理范围内"""
        guard = AccumulationGuard()
        # max_consumption_rate_per_step=0.10 (exp_92 update)
        for count in [5, 15, 30, 40, 50, 60, 100]:
            rate, _, _ = guard.step(count)
            assert 0.0 <= rate <= 0.10, f"count={count}: rate={rate} out of bounds"

    def test_trend_positive(self):
        """INSTITUTIONAL 增长 → 正趋势"""
        guard = AccumulationGuard()
        for i in range(10):
            guard.step(10 + i * 5)
        trend = guard.get_trend()
        assert trend > 0

    def test_trend_negative(self):
        """INSTITUTIONAL 减少 → 负趋势"""
        guard = AccumulationGuard()
        for i in range(10):
            guard.step(100 - i * 5)
        trend = guard.get_trend()
        assert trend < 0


# ─── TransitionGate ───

class TestTransitionGate:

    def test_all_conditions_met(self):
        """所有条件满足 → 允许转换"""
        gate = TransitionGate({'transition_cooldown_steps': 0})
        allowed, openness = gate.evaluate(
            institutional_count=50,
            n_categories=4,
            current_odi=0.6,
            step=1,
        )
        assert allowed
        assert openness > 0.8

    def test_below_institutional_threshold(self):
        """INSTITUTIONAL 不足 → 不允许转换"""
        gate = TransitionGate({'transition_cooldown_steps': 0})
        allowed, openness = gate.evaluate(
            institutional_count=20,
            n_categories=4,
            current_odi=0.6,
            step=1,
        )
        assert not allowed

    def test_below_diversity_threshold(self):
        """多样性不足 → 不允许转换"""
        gate = TransitionGate({'transition_cooldown_steps': 0})
        allowed, openness = gate.evaluate(
            institutional_count=50,
            n_categories=1,
            current_odi=0.6,
            step=1,
        )
        assert not allowed

    def test_below_odi_threshold(self):
        """ODI 不足 → 不允许转换"""
        gate = TransitionGate({'transition_cooldown_steps': 0})
        # min_odi=0.15, so 0.1 < 0.15 → odi_ok=False
        allowed, openness = gate.evaluate(
            institutional_count=50,
            n_categories=4,
            current_odi=0.1,
            step=1,
        )
        assert not allowed

    def test_transition_cooldown(self):
        """转换后冷却期内不允许再次转换"""
        gate = TransitionGate({'transition_cooldown_steps': 10})
        # 第一次允许
        allowed1, _ = gate.evaluate(50, 4, 0.6, step=1)
        assert allowed1
        # 冷却期内不允许（steps 2-10）
        for i in range(2, 11):
            allowed, _ = gate.evaluate(50, 4, 0.6, step=i)
            assert not allowed, f"Step {i}: should not allow during cooldown"
        # 冷却期后允许（step 11, 距上次转换=10 >= cooldown=10）
        allowed_after, _ = gate.evaluate(50, 4, 0.6, step=11)
        assert allowed_after

    def test_openness_continuous(self):
        """开放度是连续值 [0, 1]"""
        gate = TransitionGate({'transition_cooldown_steps': 0})
        _, openness = gate.evaluate(25, 2, 0.3, step=1)
        assert 0.0 <= openness <= 1.0

    def test_openness_increases_with_conditions(self):
        """条件越好 → 开放度越高"""
        gate = TransitionGate({'transition_cooldown_steps': 0})
        _, o1 = gate.evaluate(20, 1, 0.2, step=1)
        _, o2 = gate.evaluate(50, 4, 0.8, step=2)
        assert o2 > o1

    def test_n_transitions_tracking(self):
        """转换次数正确追踪"""
        gate = TransitionGate({'transition_cooldown_steps': 0})
        gate.evaluate(50, 4, 0.6, step=1)
        gate.evaluate(50, 4, 0.6, step=2)
        assert gate.get_n_transitions() == 2


# ─── DiversityEnforcer ───

class TestDiversityEnforcer:

    def test_empty_diversity_is_zero(self):
        """无数据时多样性为 0"""
        enforcer = DiversityEnforcer()
        n_cats, sufficient = enforcer.get_diversity()
        assert n_cats == 0
        assert not sufficient

    def test_single_category(self):
        """单一类别"""
        enforcer = DiversityEnforcer()
        enforcer.record({'cat_A': 10})
        n_cats, sufficient = enforcer.get_diversity()
        assert n_cats == 1
        assert not sufficient

    def test_multiple_categories_sufficient(self):
        """多个类别 → 多样性充足"""
        enforcer = DiversityEnforcer()
        for _ in range(10):
            enforcer.record({'cat_A': 5, 'cat_B': 3, 'cat_C': 2})
        n_cats, sufficient = enforcer.get_diversity()
        assert n_cats == 3
        assert sufficient

    def test_entropy_single_category(self):
        """单一类别 → 熵为 0"""
        enforcer = DiversityEnforcer()
        enforcer.record({'cat_A': 10})
        entropy = enforcer.get_diversity_entropy()
        assert entropy == 0.0

    def test_entropy_uniform(self):
        """均匀分布 → 高熵"""
        enforcer = DiversityEnforcer()
        for _ in range(10):
            enforcer.record({'cat_A': 1, 'cat_B': 1, 'cat_C': 1, 'cat_D': 1})
        entropy = enforcer.get_diversity_entropy()
        assert entropy > 0.9

    def test_compensation_signal_deficit(self):
        """多样性不足 → 正补偿信号"""
        enforcer = DiversityEnforcer()
        enforcer.record({'cat_A': 10})
        signal = enforcer.get_compensation_signal()
        assert signal > 0

    def test_compensation_signal_sufficient(self):
        """多样性充足 → 零补偿信号"""
        enforcer = DiversityEnforcer()
        for _ in range(10):
            enforcer.record({'cat_A': 3, 'cat_B': 3, 'cat_C': 3})
        signal = enforcer.get_compensation_signal()
        assert signal == 0.0


# ─── InstitutionalLayerProtector ───

class TestInstitutionalLayerProtector:

    def test_default_result_fields(self):
        """结果对象包含所有必要字段"""
        protector = InstitutionalLayerProtector()
        result = protector.step(
            institutional_count=50,
            institutional_categories={'cat_A': 10, 'cat_B': 5, 'cat_C': 3},
            current_odi=0.6,
        )
        assert hasattr(result, 'institutional_count')
        assert hasattr(result, 'institutional_floor')
        assert hasattr(result, 'consumption_rate_limit')
        assert hasattr(result, 'transition_allowed')
        assert hasattr(result, 'transition_openness')
        assert hasattr(result, 'n_categories')
        assert hasattr(result, 'diversity_sufficient')
        assert hasattr(result, 'protection_level')
        assert hasattr(result, 'should_consume')
        assert hasattr(result, 'step')
        assert hasattr(result, 'state')

    def test_strong_protection_when_low(self):
        """INSTITUTIONAL 极低 → 强保护"""
        protector = InstitutionalLayerProtector()
        result = protector.step(
            institutional_count=10,
            institutional_categories={'cat_A': 10},
            current_odi=0.3,
        )
        assert result.protection_level == 'strong'
        assert not result.should_consume
        assert result.consumption_rate_limit < 0.02

    def test_weak_protection_when_moderate(self):
        """INSTITUTIONAL 中等 → 弱保护"""
        protector = InstitutionalLayerProtector()
        # threshold=35, floor=20, so 28 is in [20, 35)
        result = protector.step(
            institutional_count=28,
            institutional_categories={'cat_A': 15, 'cat_B': 13},
            current_odi=0.5,
        )
        assert result.protection_level == 'weak', \
            f"expected weak, got {result.protection_level} (count=28)"

    def test_no_protection_when_abundant(self):
        """INSTITUTIONAL 充足 → 无保护"""
        protector = InstitutionalLayerProtector()
        result = protector.step(
            institutional_count=80,
            institutional_categories={'cat_A': 20, 'cat_B': 20, 'cat_C': 20, 'cat_D': 20},
            current_odi=0.7,
        )
        assert result.protection_level == 'none'

    def test_transition_blocked_by_diversity(self):
        """多样性不足 → 转换被阻止"""
        protector = InstitutionalLayerProtector()
        result = protector.step(
            institutional_count=60,
            institutional_categories={'cat_A': 60},  # 单一类别
            current_odi=0.7,
        )
        assert not result.transition_allowed
        assert not result.diversity_sufficient

    def test_transition_allowed_when_ready(self):
        """条件满足 → 转换被允许"""
        protector = InstitutionalLayerProtector({
            'transition_cooldown_steps': 0,
            'transition_min_institutional': 40,
            'transition_min_diversity': 3,
            'transition_min_odi': 0.5,
        })
        result = protector.step(
            institutional_count=50,
            institutional_categories={'cat_A': 20, 'cat_B': 15, 'cat_C': 15},
            current_odi=0.6,
        )
        assert result.transition_allowed

    def test_floor_adapts_to_diversity(self):
        """多样性不足时地板升高"""
        protector = InstitutionalLayerProtector()
        initial_floor = result = protector.step(
            institutional_count=60,
            institutional_categories={'cat_A': 60},
            current_odi=0.7,
        ).institutional_floor
        # 多步后地板应升高
        for i in range(20):
            result = protector.step(
                institutional_count=60,
                institutional_categories={'cat_A': 60},
                current_odi=0.7,
            )
        assert result.institutional_floor >= initial_floor

    def test_history_tracking(self):
        """历史追踪正常工作"""
        protector = InstitutionalLayerProtector()
        for i in range(20):
            protector.step(
                institutional_count=50 + i,
                institutional_categories={'cat_A': 10, 'cat_B': 10, 'cat_C': 10},
                current_odi=0.5 + i * 0.01,
            )
        history = protector.get_history()
        assert history['step_count'] == 20
        assert 'accumulation_trend' in history
        assert 'n_categories' in history
        assert 'diversity_entropy' in history

    def test_reset(self):
        """重置后状态恢复"""
        protector = InstitutionalLayerProtector()
        for i in range(20):
            protector.step(
                institutional_count=50,
                institutional_categories={'cat_A': 10, 'cat_B': 10, 'cat_C': 10},
                current_odi=0.6,
            )
        protector.reset()
        history = protector.get_history()
        assert history['step_count'] == 0

    def test_record_consumption(self):
        """记录消耗事件"""
        protector = InstitutionalLayerProtector()
        result = protector.step(
            institutional_count=80,
            institutional_categories={'cat_A': 20, 'cat_B': 20, 'cat_C': 20, 'cat_D': 20},
            current_odi=0.7,
        )
        assert result.should_consume
        protector.record_consumption()
        # 冷却期内不应允许消耗
        result2 = protector.step(
            institutional_count=80,
            institutional_categories={'cat_A': 20, 'cat_B': 20, 'cat_C': 20, 'cat_D': 20},
            current_odi=0.7,
        )
        assert not result2.should_consume

    def test_empty_categories(self):
        """空类别不崩溃"""
        protector = InstitutionalLayerProtector()
        result = protector.step(
            institutional_count=50,
            institutional_categories=None,
            current_odi=0.6,
        )
        assert result.n_categories == 0

    def test_consumption_rate_bounded(self):
        """消耗速率始终有界"""
        protector = InstitutionalLayerProtector()
        # max_consumption_rate_per_step=0.10 (exp_92 update)
        for count in [5, 15, 25, 35, 45, 55, 65, 75, 85, 95]:
            result = protector.step(
                institutional_count=count,
                institutional_categories={'cat_A': count},
                current_odi=0.5,
            )
            assert 0.0 <= result.consumption_rate_limit <= 0.10 + 1e-8, \
                f"count={count}: rate={result.consumption_rate_limit} out of bounds"


# ─── 集成行为测试 ───

class TestInstitutionalLayerProtectorIntegration:

    def test_protection_recovery_cycle(self):
        """保护-恢复周期：消耗后保护触发，恢复后保护解除"""
        protector = InstitutionalLayerProtector({
            'consumption_cooldown_steps': 5,
            'protection_response_delay': 2,
        })

        # 阶段 1：充足 → 无保护
        for i in range(5):
            result = protector.step(
                institutional_count=80,
                institutional_categories={'cat_A': 20, 'cat_B': 20, 'cat_C': 20, 'cat_D': 20},
                current_odi=0.7,
            )
        assert result.protection_level == 'none'

        # 阶段 2：模拟消耗 → INSTITUTIONAL 骤降
        for i in range(3):
            result = protector.step(
                institutional_count=20,
                institutional_categories={'cat_A': 10, 'cat_B': 5, 'cat_C': 5},
                current_odi=0.4,
            )
        assert result.protection_level in ('weak', 'strong')

        # 阶段 3：恢复 → 保护逐渐解除
        for i in range(20):
            count = 20 + i * 3
            result = protector.step(
                institutional_count=min(count, 80),
                institutional_categories={'cat_A': count // 4, 'cat_B': count // 4,
                                         'cat_C': count // 4, 'cat_D': count // 4},
                current_odi=0.4 + i * 0.02,
            )
        assert result.protection_level == 'none'

    def test_transition_gate_integration(self):
        """转换门控集成：从不允许到允许"""
        protector = InstitutionalLayerProtector({
            'transition_cooldown_steps': 0,
            'transition_min_institutional': 40,
            'transition_min_diversity': 3,
            'transition_min_odi': 0.5,
        })

        # 初始：条件不足
        result = protector.step(
            institutional_count=20,
            institutional_categories={'cat_A': 20},
            current_odi=0.3,
        )
        assert not result.transition_allowed

        # 逐步满足条件
        for i in range(30):
            result = protector.step(
                institutional_count=20 + i * 2,
                institutional_categories={
                    'cat_A': 10 + i,
                    'cat_B': 5 + i // 2,
                    'cat_C': 5 + i // 3,
                },
                current_odi=0.3 + i * 0.02,
            )

        # 最终应该允许
        assert result.transition_allowed
        assert result.transition_openness > 0.8

    def test_diversity_floor_interaction(self):
        """多样性不足 → 地板升高 → 保护增强"""
        protector = InstitutionalLayerProtector({
            'min_institutional_floor': 30,
            'min_institutional_threshold': 50,
        })

        # 多样性不足持续多步
        floors = []
        for i in range(30):
            result = protector.step(
                institutional_count=55,  # 高于阈值
                institutional_categories={'cat_A': 55},  # 单一类别
                current_odi=0.6,
            )
            floors.append(result.institutional_floor)

        # 地板应该随时间升高
        assert floors[-1] > floors[0], f"Expected floor to rise: {floors[0]} -> {floors[-1]}"
