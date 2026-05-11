"""
test_property_coarse_grain.py — 粗粒化一致性性质测试

审计报告 Section 7.3：
验证粗粒化前后守恒量在允许误差内一致。
核心性质：L0 → L1 映射不应凭空创造或消灭差异。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
import pytest

from layers.L0_binary_lattice import L0BinaryLattice
from layers.coarse_grain import (
    coarse_grain_state,
    coarse_grain_measure_invariant,
)


class TestCoarseGrainConsistency:
    """粗粒化一致性：守恒量在 L0 → L1 映射中近似保持"""

    @pytest.mark.parametrize("block_size", [2, 4])
    def test_conservation_pattern_preserved(self, block_size):
        """粗粒化后激活分布模式应保持（不同区域的比例关系）。"""
        layer = L0BinaryLattice(shape=(8, 8), device="cpu")

        # 创建有差异的 state：左半区域值高，右半区域值低
        state = torch.zeros(1, 1, 8, 8)
        state[:, :, :, :4] = 0.8  # 左半
        state[:, :, :, 4:] = 0.2  # 右半
        mask = torch.ones(8, 8)

        # L0 区域比例：左/右 = 0.8/0.2 = 4.0
        l0_left = state[:, :, :, :4].mean().item()
        l0_right = state[:, :, :, 4:].mean().item()
        l0_ratio = l0_left / max(l0_right, 1e-6)

        # 粗粒化
        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=block_size)

        # L1 区域比例：重新分组
        # block_size=2: 8x8 → 4x4，左半=2x4，右半=2x4
        # block_size=4: 8x8 → 2x4，左半=1x4，右半=1x4
        h, w = l1_state.shape[-2:]
        mid_w = w // 2
        l1_left = l1_state[:, :, :, :mid_w].mean().item()
        l1_right = l1_state[:, :, :, mid_w:].mean().item()
        l1_ratio = l1_left / max(l1_right, 1e-6)

        # 比例应在 50% 容差内保持
        assert abs(l1_ratio - l0_ratio) / l0_ratio < 0.5, (
            f"Pattern not preserved: L0 ratio={l0_ratio:.2f}, L1 ratio={l1_ratio:.2f}"
        )

    def test_coarse_grain_output_shape(self):
        """粗粒化后尺寸应缩小为 H/block_size x W/block_size"""
        layer = L0BinaryLattice(shape=(8, 8), device="cpu")
        state = layer.initial_state()
        mask = torch.ones(8, 8)

        for block_size in [2, 4]:
            l1_state, l1_mask = coarse_grain_state(state, mask, block_size=block_size)
            expected_h = 8 // block_size
            expected_w = 8 // block_size
            assert l1_state.shape[-2:] == (expected_h, expected_w), (
                f"Shape mismatch: expected ({expected_h}, {expected_w}), "
                f"got {l1_state.shape[-2:]}"
            )

    def test_zero_input_gives_zero_output(self):
        """全零状态粗粒化后仍为零"""
        state = torch.zeros(1, 1, 8, 8)
        mask = torch.ones(8, 8)

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=4)

        assert l1_state.sum().item() == 0.0, (
            f"Zero input should produce zero output, got {l1_state.sum().item()}"
        )

    @pytest.mark.parametrize("value", [0.3, 0.5, 0.7, 1.0])
    def test_uniform_state_preserved(self, value):
        """均匀状态粗粒化后值近似保持"""
        state = torch.ones(1, 1, 8, 8) * value
        mask = torch.ones(8, 8)

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=4)

        # 均匀值 → 每个块的均值应等于原值
        assert l1_state.max().item() == pytest.approx(value, abs=0.01), (
            f"Uniform state not preserved: max={l1_state.max().item():.4f}, "
            f"expected={value}"
        )

    def test_partial_mask_pattern(self):
        """部分掩码下，粗粒化应保留内部相对结构"""
        layer = L0BinaryLattice(shape=(8, 8), device="cpu")

        # 创建有差异的 state
        state = torch.ones(1, 1, 8, 8) * 0.5
        state[:, :, :4, :4] = 0.8  # 左上高
        state[:, :, :4, 4:] = 0.2  # 右上低

        # 只取上半部分
        mask = torch.zeros(8, 8)
        mask[:4, :] = 1.0

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=2)

        # 检查内部比例：左上和右上的比值应保持
        h, w = l1_state.shape[-2:]
        mid_w = w // 2
        l1_top_left = l1_state[:, :, :h//2, :mid_w].mean().item()
        l1_top_right = l1_state[:, :, :h//2, mid_w:].mean().item()

        # 如果 l1_mask 有激活区域
        if l1_top_left + l1_top_right > 0:
            ratio = l1_top_left / max(l1_top_right, 1e-6)
            # 原始比例 0.8/0.2 = 4.0，粗粒化后应接近
            assert ratio > 1.0, (
                f"Top-left should have higher activation than top-right after coarse-grain"
            )

    def test_coarse_grain_idempotent_approx(self):
        """多次粗粒化应近似幂等（再粗粒化一次，值域不爆炸）"""
        state = torch.ones(1, 1, 8, 8) * 0.5
        mask = torch.ones(8, 8)

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=2)
        # 二次粗粒化（l1_state 已经是 4x4，用 block_size=2）
        l2_state, l2_mask = coarse_grain_state(l1_state, l1_mask.squeeze(0).squeeze(0), block_size=2)

        # 二次粗粒化后值不应爆炸（应在 [0, 1] 范围内）
        assert l2_state.min() >= -0.1, f"L2 min={l2_state.min().item():.4f} < 0"
        assert l2_state.max() <= 1.1, f"L2 max={l2_state.max().item():.4f} > 1"
