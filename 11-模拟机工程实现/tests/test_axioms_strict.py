"""test_axioms_strict.py — 九公理严格化测试"""

import pytest
import torch
from acl.axioms_strict import (
    A1_DifferenceSourceStrict,
    A2_DiscreteEncodingStrict,
    A4_MinimalVariationStrict,
    A6_DAGConstraint,
    A7_CycleClosure,
    A8_SymmetryPreference,
    A9_MinimalRealization,
    AxiomEngineStrict,
)


class MockLayer:
    """模拟 layer 接口"""

    def measure_invariant(self, state):
        return state.sum(dim=(-1, -2), keepdim=True)

    def stability_violation(self, window):
        return torch.tensor(0.0)


class TestA1Strict:

    def test_level_drop_penalized(self):
        a1 = A1_DifferenceSourceStrict()
        state = torch.ones(4, 4) * 0.8
        next_state = torch.ones(4, 4) * 0.3  # 层级下降
        report = a1.violation(state, next_state, None, [])
        assert report.raw_violation > 0.0

    def test_level_rise_no_penalty(self):
        a1 = A1_DifferenceSourceStrict()
        state = torch.ones(4, 4) * 0.3
        next_state = torch.ones(4, 4) * 0.8  # 层级上升
        report = a1.violation(state, next_state, None, [])
        assert report.raw_violation == pytest.approx(0.0, abs=1e-6)


class TestA2Strict:

    def test_binary_state_low_violation(self):
        a2 = A2_DiscreteEncodingStrict()
        state = torch.tensor([0.0, 1.0, 0.0, 1.0])
        next_state = torch.tensor([0.01, 0.99, 0.02, 0.98])
        report = a2.violation(state, next_state, None, [])
        assert report.raw_violation < 0.1

    def test_fuzzy_state_high_violation(self):
        a2 = A2_DiscreteEncodingStrict()
        state = torch.tensor([0.0, 1.0, 0.0, 1.0])
        next_state = torch.tensor([0.5, 0.5, 0.5, 0.5])
        report = a2.violation(state, next_state, None, [])
        assert report.raw_violation > 0.1


class TestA4Strict:

    def test_single_flip_low_violation(self):
        a4 = A4_MinimalVariationStrict()
        state = torch.tensor([1.0, 0.0, 0.0, 0.0])
        next_state = torch.tensor([1.0, 1.0, 0.0, 0.0])  # 翻转1位
        report = a4.violation(state, next_state, None, [])
        assert report.raw_violation < 0.1

    def test_multi_flip_high_violation(self):
        a4 = A4_MinimalVariationStrict()
        state = torch.tensor([1.0, 0.0, 0.0, 0.0])
        next_state = torch.tensor([1.0, 1.0, 1.0, 1.0])  # 翻转3位
        report = a4.violation(state, next_state, None, [])
        assert report.raw_violation > 1.0


class TestA6Strict:

    def test_reverse_transition_penalized(self):
        a6 = A6_DAGConstraint()
        state = torch.tensor([1.0, 0.0, 0.0, 0.0])
        next_state = torch.tensor([1.0, 1.0, 0.0, 0.0])  # bit 1: 0→1
        # 第一次：正向，无惩罚
        report1 = a6.violation(state, next_state, None, [])
        # 第二次：逆向 1→0，应被惩罚
        report2 = a6.violation(next_state, state, None, [])
        assert report2.raw_violation > report1.raw_violation

    def test_reset_clears_direction(self):
        a6 = A6_DAGConstraint()
        state = torch.tensor([0.0, 0.0])
        next_state = torch.tensor([1.0, 0.0])
        a6.violation(state, next_state, None, [])
        a6.reset()
        # 重置后应该可以逆向
        report = a6.violation(next_state, state, None, [])
        assert report.raw_violation == pytest.approx(0.0, abs=1e-6)


class TestA7Strict:

    def test_cycle_detected(self):
        a7 = A7_CycleClosure(min_cycle_length=2)
        state = torch.ones(4, 4) * 0.8
        next_state = torch.ones(4, 4) * 0.8
        # 创建一个循环历史
        history = [state.clone() for _ in range(4)] + [state.clone() for _ in range(4)]
        report = a7.violation(state, next_state, None, history)
        assert report.metadata["cycle_found"] == True

    def test_no_cycle(self):
        a7 = A7_CycleClosure(min_cycle_length=4)
        state = torch.ones(4, 4) * 0.8
        next_state = torch.ones(4, 4) * 0.8
        # 历史太短
        history = [state.clone() for _ in range(3)]
        report = a7.violation(state, next_state, None, history)
        assert report.raw_violation == 0.0  # 历史不足，不惩罚


class TestA8Strict:

    def test_mid_weight_preferred(self):
        N = 8
        a8 = A8_SymmetryPreference(N=N)
        # w=4 (N/2) 应该 violation 最低
        state_mid = torch.tensor([1, 1, 1, 1, 0, 0, 0, 0]).float() * 0.8
        state_low = torch.tensor([1, 0, 0, 0, 0, 0, 0, 0]).float() * 0.8
        report_mid = a8.violation(None, state_mid, None, [])
        report_low = a8.violation(None, state_low, None, [])
        assert report_mid.raw_violation < report_low.raw_violation

    def test_symmetry_around_half(self):
        N = 6
        a8 = A8_SymmetryPreference(N=N)
        # 直接用正确的汉明重量构造状态
        # w=1: 1个1, w=5: 5个1 -> 对称
        state_1 = torch.zeros(N)
        state_1[0] = 1.0  # w=1
        state_5 = torch.ones(N)
        state_5[0] = 0.0  # w=5
        report_1 = a8.violation(None, state_1, None, [])
        report_5 = a8.violation(None, state_5, None, [])
        assert report_1.raw_violation == pytest.approx(report_5.raw_violation, abs=0.01)


class TestA9Strict:

    def test_excess_dof_penalized(self):
        a9 = A9_MinimalRealization(expected_dof=2)
        layer = MockLayer()
        state = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])  # 3 个独特模式
        next_state = state.clone()
        report = a9.violation(state, next_state, layer, [])
        assert report.raw_violation > 0.0


class TestAxiomEngineStrict:

    def test_total_loss(self):
        engine = AxiomEngineStrict(N=8)
        layer = MockLayer()
        state = torch.ones(1, 1, 4, 4) * 0.5
        next_state = torch.ones(1, 1, 4, 4) * 0.6
        loss = engine.total_loss(state, next_state, layer, [])
        assert loss.item() >= 0.0

    def test_evaluate_all(self):
        engine = AxiomEngineStrict(N=8)
        layer = MockLayer()
        state = torch.ones(1, 1, 4, 4) * 0.5
        next_state = torch.ones(1, 1, 4, 4) * 0.6
        reports = engine.evaluate(state, next_state, layer, [])
        assert len(reports) == 8  # A1, A2, A4, A5, A6, A7, A8, A9
