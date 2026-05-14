"""test_three_dim_hamming.py — 三维汉明格点测试"""

import pytest
import torch
from layers.three_dim_hamming import ThreeDimHammingLattice


class TestThreeDimHammingLattice:

    def test_init_requires_multiple_of_3(self):
        with pytest.raises(ValueError):
            ThreeDimHammingLattice(N=7)

    def test_init_valid(self):
        layer = ThreeDimHammingLattice(N=24)
        assert layer.N == 24
        assert layer.n == 8
        assert layer.epsilon == 1.0 / 8

    def test_group_indices(self):
        layer = ThreeDimHammingLattice(N=12)
        assert layer.group_indices(0) == (0, 4)
        assert layer.group_indices(1) == (4, 8)
        assert layer.group_indices(2) == (8, 12)

    def test_embed_3d_single(self):
        layer = ThreeDimHammingLattice(N=6, L=1.0)
        state = torch.tensor([1, 0, 1, 0, 1, 0])  # x:1, y:1, z:1
        coords = layer.embed_3d(state)
        assert coords.shape == (3,)
        assert coords[0].item() == pytest.approx(0.5)  # 1 * 1/2
        assert coords[1].item() == pytest.approx(0.5)
        assert coords[2].item() == pytest.approx(0.5)

    def test_embed_3d_batch(self):
        layer = ThreeDimHammingLattice(N=6)
        states = torch.tensor([[1, 0, 0, 0, 0, 0],
                               [0, 0, 0, 1, 0, 0]])
        coords = layer.embed_3d(states)
        assert coords.shape == (2, 3)

    def test_embed_3d_all_zeros(self):
        layer = ThreeDimHammingLattice(N=6)
        state = torch.zeros(6)
        coords = layer.embed_3d(state)
        assert coords.tolist() == [0.0, 0.0, 0.0]

    def test_embed_3d_all_ones(self):
        layer = ThreeDimHammingLattice(N=6, L=3.0)
        state = torch.ones(6)
        coords = layer.embed_3d(state)
        n = 2
        eps = 3.0 / 2
        expected = eps * 2  # 每个组 2 个 1
        assert coords[0].item() == pytest.approx(expected)

    def test_euclidean_distance(self):
        layer = ThreeDimHammingLattice(N=6, L=1.0)
        s1 = torch.zeros(6)
        s2 = torch.ones(6)
        d = layer.euclidean_distance(s1, s2)
        assert d > 0.0

    def test_hamming_distance_3d(self):
        layer = ThreeDimHammingLattice(N=6)
        s1 = torch.tensor([1, 0, 0, 0, 0, 0])
        s2 = torch.tensor([0, 0, 1, 0, 0, 0])
        dx, dy, dz, total = layer.hamming_distance_3d(s1, s2)
        assert dx == 1
        assert dy == 1
        assert dz == 0
        assert total == 2

    def test_mid_surface_weight(self):
        layer = ThreeDimHammingLattice(N=12)
        assert layer.mid_surface_weight() == 6

    def test_is_on_mid_surface(self):
        layer = ThreeDimHammingLattice(N=6)
        state = torch.tensor([1, 1, 1, 0, 0, 0])  # w=3=N/2
        assert layer.is_on_mid_surface(state)

    def test_not_on_mid_surface(self):
        layer = ThreeDimHammingLattice(N=6)
        state = torch.tensor([1, 1, 0, 0, 0, 0])  # w=2
        assert not layer.is_on_mid_surface(state)

    def test_random_mid_surface_state(self):
        layer = ThreeDimHammingLattice(N=12)
        state = layer.random_mid_surface_state()
        assert state.sum().item() == 6

    def test_random_mid_surface_batch(self):
        layer = ThreeDimHammingLattice(N=12)
        states = layer.random_mid_surface_state(batch_size=10)
        assert states.shape == (10, 12)
        for i in range(10):
            assert states[i].sum().item() == 6

    def test_mid_surface_size(self):
        layer = ThreeDimHammingLattice(N=6)
        assert layer.mid_surface_size() == 20  # C(6,3)=20

    def test_enumerate_mid_surface(self):
        layer = ThreeDimHammingLattice(N=6)
        states = layer.enumerate_mid_surface()
        assert len(states) == 20
        for s in states:
            assert s.sum().item() == 3

    def test_enumerate_mid_surface_too_large(self):
        layer = ThreeDimHammingLattice(N=24)
        with pytest.raises(ValueError):
            layer.enumerate_mid_surface()

    def test_potential_at(self):
        layer = ThreeDimHammingLattice(N=6)
        source = torch.ones(6)
        state = torch.zeros(6)
        phi = layer.potential_at(state, [source])
        assert phi < 0.0  # 负势（吸引）

    def test_potential_3d_at(self):
        layer = ThreeDimHammingLattice(N=6, L=1.0)
        source = torch.ones(6)
        state = torch.zeros(6)
        phi = layer.potential_3d_at(state, [source])
        assert phi < 0.0

    def test_potential_distance_scaling(self):
        """验证势场随距离衰减"""
        layer = ThreeDimHammingLattice(N=12, L=1.0)
        source = torch.ones(12)

        # 近距离状态
        near = torch.zeros(12)
        near[:4] = 1.0  # 4 个 1，距离源 8
        phi_near = layer.potential_at(near, [source])

        # 远距离状态
        far = torch.zeros(12)
        far[:2] = 1.0  # 2 个 1，距离源 10
        phi_far = layer.potential_at(far, [source])

        # 近距离势更强（更负）
        assert phi_near < phi_far

    def test_apply_E_ij_valid(self):
        layer = ThreeDimHammingLattice(N=6)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = layer.apply_E_ij(state, 0, 1)  # bit0=1, bit1=0
        assert result is not None
        assert result[0].item() == 0.0
        assert result[1].item() == 1.0
        assert result.sum().item() == state.sum().item()  # w 不变

    def test_apply_E_ij_invalid(self):
        layer = ThreeDimHammingLattice(N=6)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = layer.apply_E_ij(state, 1, 0)  # bit1=0, bit0=1 -> 无效
        assert result is None

    def test_apply_E_ij_preserves_weight(self):
        """E_ij 保持汉明重量不变"""
        layer = ThreeDimHammingLattice(N=12)
        state = layer.random_mid_surface_state()
        w_before = state.sum().item()

        moves = layer.get_valid_E_moves(state)
        if moves:
            i, j = moves[0]
            new_state = layer.apply_E_ij(state, i, j)
            assert new_state is not None
            w_after = new_state.sum().item()
            assert w_before == w_after

    def test_get_valid_E_moves(self):
        layer = ThreeDimHammingLattice(N=6)
        state = torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        moves = layer.get_valid_E_moves(state)
        # 3 个 1，3 个 0 -> 3*3=9 种移动
        assert len(moves) == 9

    def test_stats(self):
        layer = ThreeDimHammingLattice(N=6)
        state = torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        s = layer.stats(state)
        assert s['hamming_weight'] == 3
        assert s['on_mid_surface'] == True
        assert len(s['coords_3d']) == 3
        assert len(s['group_weights']) == 3
