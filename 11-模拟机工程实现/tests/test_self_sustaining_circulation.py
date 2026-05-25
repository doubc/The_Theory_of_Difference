"""
tests/test_self_sustaining_circulation.py — 自维持循环测试

Phase 2 P2 组件 #1 测试
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.self_sustaining_circulation import (
    SelfSustainingCirculation, CirculationState, RebuildAttempt
)


class TestSelfSustainingCirculation:
    """SelfSustainingCirculation 测试套件"""

    def setup_method(self):
        self.ssc = SelfSustainingCirculation(
            robustness_threshold=0.5,
            similarity_threshold=0.7,
            window_size=10,
            max_rebuild_steps=50,
        )
        self.state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])

    def test_initial_state(self):
        """初始状态：未设置参考，非自维持"""
        assert not self.ssc.is_self_sustaining
        assert self.ssc.robustness == 0.0
        assert self.ssc.state.is_self_sustaining is False

    def test_set_reference(self):
        """设置参考状态"""
        self.ssc.set_reference(self.state)
        assert self.ssc._reference_state is not None
        assert torch.equal(self.ssc._reference_state, self.state)

    def test_perturbation_noise(self):
        """噪声扰动模式"""
        perturbed = self.ssc.apply_perturbation(self.state, magnitude=0.1, mode="noise")
        assert perturbed.shape == self.state.shape
        assert not torch.equal(perturbed, self.state)

    def test_perturbation_flip(self):
        """比特翻转扰动模式"""
        perturbed = self.ssc.apply_perturbation(self.state, magnitude=0.5, mode="flip")
        assert perturbed.shape == self.state.shape

    def test_perturbation_dropout(self):
        """置零扰动模式"""
        perturbed = self.ssc.apply_perturbation(self.state, magnitude=0.5, mode="dropout")
        assert perturbed.shape == self.state.shape
        assert (perturbed == 0.0).sum().item() > 0

    def test_perturbation_invalid_mode(self):
        """无效扰动模式应抛出异常"""
        with pytest.raises(ValueError):
            self.ssc.apply_perturbation(self.state, mode="invalid")

    def test_evaluate_rebuild_first_call(self):
        """首次调用 evaluate_rebuild 设置参考状态"""
        result = self.ssc.evaluate_rebuild(
            self.state, lambda s: s)
        assert result.success
        assert result.similarity == 1.0

    def test_evaluate_rebuild_identity_evolution(self):
        """恒等演化函数：状态不变，应成功重建"""
        self.ssc.set_reference(self.state)
        result = self.ssc.evaluate_rebuild(
            self.state, lambda s: s, perturbation_magnitude=0.0)
        assert result.success

    def test_evaluate_batch(self):
        """批量评估"""
        self.ssc.set_reference(self.state)
        batch_result = self.ssc.evaluate_batch(
            self.state,
            lambda s: s,
            n_perturbations=5,
            magnitude=0.0,
        )
        assert batch_result['n_perturbations'] == 5
        assert batch_result['n_success'] == 5
        assert batch_result['success_rate'] == 1.0

    def test_robustness_updates(self):
        """稳健性状态更新"""
        self.ssc.set_reference(self.state)
        for _ in range(5):
            self.ssc.evaluate_rebuild(
                self.state, lambda s: s, perturbation_magnitude=0.0)
        assert self.ssc.state.n_perturbations >= 5

    def test_self_sustaining_threshold(self):
        """自维持阈值判定"""
        ssc = SelfSustainingCirculation(
            robustness_threshold=0.3,
            similarity_threshold=0.5,
        )
        ssc.set_reference(self.state)
        for _ in range(10):
            ssc.evaluate_rebuild(
                self.state, lambda s: s, perturbation_magnitude=0.0)
        assert ssc.is_self_sustaining

    def test_summary(self):
        """摘要信息"""
        self.ssc.set_reference(self.state)
        self.ssc.evaluate_rebuild(self.state, lambda s: s, perturbation_magnitude=0.0)
        summary = self.ssc.get_summary()
        assert 'is_self_sustaining' in summary
        assert 'robustness' in summary
        assert 'n_perturbations' in summary
        assert 'trend' in summary

    def test_reset(self):
        """重置状态"""
        self.ssc.set_reference(self.state)
        self.ssc.evaluate_rebuild(self.state, lambda s: s, perturbation_magnitude=0.0)
        self.ssc.reset()
        assert not self.ssc.is_self_sustaining
        assert self.ssc.robustness == 0.0
        assert len(self.ssc._rebuild_history) == 0

    def test_trend_improving(self):
        """趋势改善检测"""
        ssc = SelfSustainingCirculation(window_size=10)
        ssc.set_reference(self.state)

        for _ in range(5):
            ssc.evaluate_rebuild(
                self.state,
                lambda s: torch.zeros_like(s),
                perturbation_magnitude=0.5,
            )

        ssc.set_reference(torch.zeros_like(self.state))

        for _ in range(5):
            ssc.evaluate_rebuild(
                torch.zeros_like(self.state),
                lambda s: s,
                perturbation_magnitude=0.0,
            )

        assert ssc.state.trend in ("improving", "stable")

    def test_perturbation_magnitude_effect(self):
        """扰动强度影响"""
        ssc = SelfSustainingCirculation(
            similarity_threshold=0.8,
            max_rebuild_steps=10,
        )
        ssc.set_reference(self.state)
        result_high = ssc.evaluate_rebuild(
            self.state,
            lambda s: s,
            perturbation_magnitude=0.5,
        )
        assert result_high.similarity < 1.0

    def test_max_rebuild_steps(self):
        """最大重建步数限制"""
        ssc = SelfSustainingCirculation(
            max_rebuild_steps=5,
            similarity_threshold=0.99,
        )
        ssc.set_reference(self.state)
        result = ssc.evaluate_rebuild(
            self.state,
            lambda s: torch.zeros_like(s),
            perturbation_magnitude=0.5,
        )
        assert not result.success
        assert result.rebuild_steps == 5

    def test_state_dataclass(self):
        """CirculationState 数据类"""
        state = CirculationState(
            is_self_sustaining=True,
            robustness=0.8,
            trend="improving",
        )
        assert state.is_self_sustaining
        assert state.robustness == 0.8
        assert state.trend == "improving"

    def test_rebuild_attempt_dataclass(self):
        """RebuildAttempt 数据类"""
        attempt = RebuildAttempt(
            perturbation_step=1,
            success=True,
            rebuild_steps=5,
            similarity=0.9,
        )
        assert attempt.success
        assert attempt.rebuild_steps == 5


class TestSelfSustainingCirculationEdgeCases:
    """边界情况测试"""

    def setup_method(self):
        self.ssc = SelfSustainingCirculation(
            robustness_threshold=0.5,
            similarity_threshold=0.7,
            window_size=10,
            max_rebuild_steps=50,
        )
        self.state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])

    def test_empty_state(self):
        """空状态"""
        empty = torch.tensor([])
        result = self.ssc.evaluate_rebuild(empty, lambda s: s)
        assert result.success

    def test_single_element_state(self):
        """单元素状态"""
        state = torch.tensor([1.0])
        self.ssc.set_reference(state)
        result = self.ssc.evaluate_rebuild(state, lambda s: s, perturbation_magnitude=0.0)
        assert result.success

    def test_large_state(self):
        """大状态"""
        state = torch.randn(1000)
        self.ssc.set_reference(state)
        result = self.ssc.evaluate_rebuild(state, lambda s: s, perturbation_magnitude=0.0)
        assert result.success

    def test_zero_perturbation(self):
        """零扰动"""
        state = torch.tensor([1.0, 0.0, 1.0])
        self.ssc.set_reference(state)
        result = self.ssc.evaluate_rebuild(state, lambda s: s, perturbation_magnitude=0.0)
        assert result.success
        assert abs(result.similarity - 1.0) < 1e-6

    def test_summary_before_any_rebuild(self):
        """重建前获取摘要"""
        summary = self.ssc.get_summary()
        assert summary['n_perturbations'] == 0
        assert summary['recent_success_rate'] == 0.0
