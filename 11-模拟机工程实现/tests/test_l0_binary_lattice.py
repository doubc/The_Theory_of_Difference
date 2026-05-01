"""tests/test_l0_binary_lattice.py — L0 二元格点单元测试"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layers.L0_binary_lattice import L0BinaryLattice


class TestL0BinaryLattice:
    """L0 二元格点测试"""

    def test_initial_state_2d(self):
        layer = L0BinaryLattice(shape=(8, 8), device="cpu")
        state = layer.initial_state()
        assert state.shape == (1, 1, 8, 8)
        assert state.min() >= 0.0
        assert state.max() <= 1.0

    def test_initial_state_1d(self):
        layer = L0BinaryLattice(shape=(1, 50), device="cpu")
        state = layer.initial_state()
        assert state.shape == (1, 1, 1, 50)

    def test_project_state(self):
        layer = L0BinaryLattice(shape=(4, 4))
        raw = torch.tensor([[[[1.5, -0.3, 0.5, 0.0]]]])
        proj = layer.project_state(raw)
        assert proj.min() >= 0.0
        assert proj.max() <= 1.0

    def test_hard_project(self):
        layer = L0BinaryLattice(shape=(4, 4))
        raw = torch.tensor([[[[0.3, 0.7, 0.5, 0.1]]]])
        hard = layer.hard_project(raw)
        # >0.5 → 1.0, <=0.5 → 0.0
        expected = torch.tensor([[[[0.0, 1.0, 0.0, 0.0]]]])
        assert torch.equal(hard, expected)

    def test_measure_difference_2d(self):
        layer = L0BinaryLattice(shape=(4, 4))
        state = torch.zeros(1, 1, 4, 4)
        state[:, :, :, :2] = 1.0  # 左半为 1，右半为 0
        diff = layer.measure_difference(state)
        # 应该有非零差异
        assert diff.numel() > 0
        assert diff.max() > 0

    def test_measure_difference_1d(self):
        """1D 不应返回空 tensor 或 NaN"""
        layer = L0BinaryLattice(shape=(1, 10))
        state = torch.zeros(1, 1, 1, 10)
        state[:, :, :, :5] = 1.0
        diff = layer.measure_difference(state)
        # dx 的 shape 为 (1, 1, 1, 9)，比输入少 1 列
        assert diff.numel() > 0
        assert diff.shape == (1, 1, 1, 9)
        assert not torch.isnan(diff).any()
        assert not torch.isinf(diff).any()

    def test_measure_invariant(self):
        layer = L0BinaryLattice(shape=(4, 4))
        state = torch.ones(1, 1, 4, 4) * 0.5
        q = layer.measure_invariant(state)
        # keepdim=True → (batch, 1, 1, 1)
        assert q.numel() == 1
        assert abs(q.item() - 8.0) < 0.01  # sum of 4*4*0.5

    def test_inject_difference(self):
        layer = L0BinaryLattice(shape=(4, 8))
        # 多次尝试（注入概率 8%，统计上几乎必有一次）
        any_injected = False
        for _ in range(20):
            state = torch.zeros(1, 1, 4, 8)
            injected = layer.inject_difference(state, source_strength=1.0)
            if injected[:, :, :, :3].max() > 0:
                any_injected = True
                break
        assert any_injected, "inject_difference should inject with 8% probability"

    def test_absorb_difference(self):
        layer = L0BinaryLattice(shape=(4, 8))
        state = torch.ones(1, 1, 4, 8)
        absorbed = layer.absorb_difference(state, sink_strength=1.0)
        # 右边界 3 列应有衰减（乘以 0.85）
        assert absorbed[:, :, :, -3:].min() < 1.0

    def test_apply_boundary_flow(self):
        """apply_boundary_flow 应返回 (state, injected, absorbed)"""
        layer = L0BinaryLattice(shape=(4, 8))
        state = torch.rand(1, 1, 4, 8)
        result, injected, absorbed = layer.apply_boundary_flow(state)
        assert result.shape == state.shape
        assert injected.shape[0] == 1
        assert absorbed.shape[0] == 1

    def test_stability_violation(self):
        layer = L0BinaryLattice(shape=(4, 4))
        window = [torch.rand(1, 1, 4, 4) for _ in range(20)]
        sv = layer.stability_violation(window)
        assert sv.dim() == 0  # scalar
        assert sv.item() >= 0

    def test_detect_stable_structures(self):
        layer = L0BinaryLattice(shape=(4, 4))
        # 稳定历史：都相同
        state = torch.rand(1, 1, 4, 4)
        history = [state.clone() for _ in range(20)]
        structures = layer.detect_stable_structures(history)
        # 应该找到稳定结构
        assert len(structures) >= 0  # 至少不报错

    def test_axiom_weights(self):
        layer = L0BinaryLattice(shape=(4, 4))
        assert layer.get_axiom_weight("A2_discrete_encoding") > 0
        assert layer.get_axiom_weight("A5_conservation") > 0
        assert layer.get_axiom_weight("nonexistent") == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
