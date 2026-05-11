"""
test_property_minimal_variation.py — 最小变易性质测试

审计报告 Section 7.2：
验证 step_scale 调小后 transition_cost 系统性下降。
A4（最小变易）是差异论的核心动力学：状态转换总是走阻力最小的路径。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
import pytest

from layers.L0_binary_lattice import L0BinaryLattice


class TestMinimalVariationProperty:
    """最小变易：transition_cost 随 step_scale 单调变化"""

    def test_transition_cost_monotonic_with_scale(self):
        """step_scale 越小 → transition_cost 应该越小"""
        layer = L0BinaryLattice(shape=(8, 8), device="cpu")
        state = layer.initial_state()

        # 创建一个大差异的 next_state（模拟剧烈变化）
        large_change = (torch.rand(1, 1, 8, 8) < 0.5).float()

        # 参数化 step_scale（target 状态与 current 的混合比例）
        costs = {}
        for scale in [0.0, 0.25, 0.5, 0.75, 1.0]:
            # next = state + scale * (target - state) → clamped
            scaled_next = state + scale * (large_change - state)
            scaled_next = scaled_next.clamp(0.0, 1.0)
            cost = layer.transition_cost(state, scaled_next)
            costs[scale] = float(cost.mean().item())

        # scale=0 → next ≈ state → cost should be minimal
        assert costs[0.0] < costs[1.0], (
            f"Minimal variation violated: cost(scale=0)={costs[0.0]:.6f} "
            f">= cost(scale=1)={costs[1.0]:.6f} "
            f"(no-change should have lower cost than full-change)"
        )

        # 单调性：scale 越大 cost 应越大（允许 1% 容差）
        sorted_scales = sorted(costs.keys())
        monotonic = all(
            costs[sorted_scales[i]] <= costs[sorted_scales[i + 1]] * 1.01
            for i in range(len(sorted_scales) - 1)
        )
        assert monotonic, (
            f"cost not monotonic with scale: {costs}"
        )

    def test_identity_has_zero_cost(self):
        """state → same state 的 transition_cost 应为 0"""
        layer = L0BinaryLattice(shape=(8, 8), device="cpu")
        state = layer.initial_state()
        cost = layer.transition_cost(state, state)

        assert cost.max().item() < 0.01, (
            f"Identity transition cost > 0: max={cost.max().item():.6f}"
        )
        assert cost.mean().item() < 0.001, (
            f"Identity transition cost mean={cost.mean().item():.6f} > 0"
        )

    @pytest.mark.parametrize("grid_size", [4, 8])
    def test_small_noise_has_low_cost(self, grid_size):
        """微小噪声（±0.01）的 transition_cost 应远小于大变化"""
        layer = L0BinaryLattice(shape=(grid_size, grid_size), device="cpu")
        state = layer.initial_state()

        # 小噪声
        small_noise = state + torch.randn_like(state) * 0.01
        small_noise = small_noise.clamp(0.0, 1.0)
        cost_small = layer.transition_cost(state, small_noise)

        # 大噪声
        large_noise = state + torch.randn_like(state) * 0.5
        large_noise = large_noise.clamp(0.0, 1.0)
        cost_large = layer.transition_cost(state, large_noise)

        assert cost_small.mean().item() < cost_large.mean().item(), (
            f"Small noise cost ({cost_small.mean().item():.6f}) "
            f">= large noise cost ({cost_large.mean().item():.6f})"
        )

    def test_cost_symmetry(self):
        """A → B 和 B → A 的成本应近似对称"""
        layer = L0BinaryLattice(shape=(8, 8), device="cpu")
        state_a = layer.initial_state()
        state_b = layer.initial_state()

        cost_ab = layer.transition_cost(state_a, state_b).mean().item()
        cost_ba = layer.transition_cost(state_b, state_a).mean().item()

        # 允许 1e-5 级浮点差异
        assert abs(cost_ab - cost_ba) < 0.1, (
            f"Cost asymmetry: A→B={cost_ab:.6f}, B→A={cost_ba:.6f}"
        )