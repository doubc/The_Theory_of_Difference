"""
test_coarse_grain.py — 粗粒化映射测试

验证 L0 → L1 粗粒化：分块均值、掩码传播、守恒量。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
import pytest
from layers.coarse_grain import (
    coarse_grain_state,
    coarse_grain_measure_invariant,
    compute_block_boundary_map,
    compute_block_turnover,
)


class TestCoarseGrain:
    """粗粒化映射测试"""

    def test_coarse_grain_shape(self):
        """粗粒化后形状应正确缩小"""
        state = torch.rand(1, 1, 16, 16)
        mask = torch.ones(1, 1, 16, 16, dtype=torch.bool)

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=4)

        assert l1_state.shape == (1, 1, 4, 4)
        assert l1_mask.shape == (1, 1, 4, 4)

    def test_coarse_grain_preserves_values(self):
        """均匀状态粗粒化后值应保持"""
        state = torch.ones(1, 1, 16, 16) * 0.5
        mask = torch.ones(1, 1, 16, 16, dtype=torch.bool)

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=4)

        assert torch.allclose(l1_state, torch.ones(1, 1, 4, 4) * 0.5, atol=1e-6)

    def test_coarse_grain_mask_partial(self):
        """部分掩码应正确传播"""
        state = torch.ones(1, 1, 16, 16) * 0.5
        mask = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask[:, :, :8, :8] = True  # 左上角 2x2 块被标记

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=4)

        assert l1_mask[0, 0, 0, 0] == 1.0  # 左上块 (rows 0:4, cols 0:4)
        assert l1_mask[0, 0, 0, 1] == 1.0  # 右上块 (rows 0:4, cols 4:8)
        assert l1_mask[0, 0, 2, 0] == 0.0  # 左下块未标记
        assert l1_mask[0, 0, 2, 2] == 0.0  # 右下块未标记

    def test_coarse_grain_2d_mask(self):
        """2D 掩码应自动扩展维度"""
        state = torch.rand(1, 1, 8, 8)
        mask = torch.ones(8, 8, dtype=torch.bool)

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=4)

        assert l1_state.shape == (1, 1, 2, 2)

    def test_measure_invariant(self):
        """守恒量应为被标记区域的总激活量"""
        l1_state = torch.ones(1, 1, 4, 4) * 0.5
        l1_mask = torch.ones(1, 1, 4, 4)

        inv = coarse_grain_measure_invariant(l1_state, l1_mask)

        assert inv.shape == (1, 1, 1, 1)
        assert torch.allclose(inv, torch.tensor([[[[8.0]]]]), atol=1e-6)  # 4*4*0.5=8

    def test_measure_invariant_partial_mask(self):
        """部分掩码的守恒量应只计算被标记区域"""
        l1_state = torch.ones(1, 1, 4, 4) * 0.5
        l1_mask = torch.zeros(1, 1, 4, 4)
        l1_mask[:, :, :2, :2] = 1.0  # 只有左上角

        inv = coarse_grain_measure_invariant(l1_state, l1_mask)

        assert torch.allclose(inv, torch.tensor([[[[2.0]]]]), atol=1e-6)  # 2*2*0.5=2

    def test_boundary_map(self):
        """边界图应检测掩码边缘"""
        mask = torch.zeros(1, 1, 8, 8)
        mask[:, :, 2:6, 2:6] = 1.0  # 中心矩形

        boundary = compute_block_boundary_map(mask)

        # 边界应存在于掩码边缘（mask 内且有非 mask 邻居）
        assert boundary[0, 0, 2, 3] == 1.0  # 上边界（邻居 (1,3) 不在 mask 内）
        assert boundary[0, 0, 5, 3] == 1.0  # 下边界（邻居 (6,3) 不在 mask 内）
        assert boundary[0, 0, 3, 2] == 1.0  # 左边界（邻居 (3,1) 不在 mask 内）
        assert boundary[0, 0, 3, 5] == 1.0  # 右边界（邻居 (3,6) 不在 mask 内）
        # 中心不应是边界（所有邻居都在 mask 内）
        assert boundary[0, 0, 4, 4] == 0.0
        # mask 外的点不应是边界
        assert boundary[0, 0, 0, 0] == 0.0

    def test_coarse_grain_different_block_sizes(self):
        """不同分块大小应产生不同形状"""
        state = torch.rand(1, 1, 16, 16)
        mask = torch.ones(1, 1, 16, 16, dtype=torch.bool)

        l1_2, _ = coarse_grain_state(state, mask, block_size=2)
        l1_4, _ = coarse_grain_state(state, mask, block_size=4)
        l1_8, _ = coarse_grain_state(state, mask, block_size=8)

        assert l1_2.shape == (1, 1, 8, 8)
        assert l1_4.shape == (1, 1, 4, 4)
        assert l1_8.shape == (1, 1, 2, 2)

    def test_coarse_grain_non_square(self):
        """非方形网格应正确处理"""
        state = torch.rand(1, 1, 8, 16)
        mask = torch.ones(1, 1, 8, 16, dtype=torch.bool)

        l1_state, l1_mask = coarse_grain_state(state, mask, block_size=4)

        assert l1_state.shape == (1, 1, 2, 4)
