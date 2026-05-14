"""test_hamming.py — 汉明几何引擎测试"""

import pytest
import torch
from engine.hamming_engine import HammingState, HammingTransition, HammingMeasurement


class TestHammingState:

    def test_from_continuous(self):
        continuous = torch.tensor([0.1, 0.9, 0.3, 0.8])
        hs = HammingState.from_continuous(continuous)
        assert hs.binary.tolist() == [0.0, 1.0, 0.0, 1.0]

    def test_hamming_weight(self):
        hs = HammingState(torch.tensor([1.0, 0.0, 1.0, 1.0]))
        assert hs.hamming_weight.item() == 3.0

    def test_hamming_weight_normalized(self):
        hs = HammingState(torch.tensor([1.0, 0.0, 1.0, 1.0]))
        assert hs.hamming_weight_normalized.item() == 0.75

    def test_mid_surface_ratio(self):
        hs_empty = HammingState(torch.zeros(8))
        assert hs_empty.mid_surface_ratio == 0.0
        hs_half = HammingState(torch.tensor([1, 1, 1, 1, 0, 0, 0, 0]).float())
        assert hs_half.mid_surface_ratio == pytest.approx(1.0, abs=0.01)

    def test_hard_project(self):
        hs = HammingState(torch.tensor([0.3, 0.7, 0.1, 0.9]))
        projected = hs.hard_project()
        assert projected.tolist() == [0.0, 1.0, 0.0, 1.0]


class TestHammingTransition:

    def test_single_bit_flip(self):
        trans = HammingTransition(N=4)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0])
        new_state = trans.single_bit_flip(state, 1)
        assert new_state.tolist() == [1.0, 1.0, 1.0, 0.0]

    def test_random_flip_changes_exactly_one(self):
        trans = HammingTransition(N=8)
        state = torch.zeros(8)
        new_state, idx = trans.random_flip(state)
        diff = (new_state != state).sum().item()
        assert diff == 1
        assert 0 <= idx < 8

    def test_dag_blocks_reverse(self):
        trans = HammingTransition(N=4, dag_enabled=True)
        trans.set_dag_direction(torch.tensor([1.0, 0.0, 0.0, 0.0]))
        state = torch.tensor([1.0, 0.0, 0.0, 0.0])
        allowed = trans.get_allowed_flips(state)
        assert allowed[0].item() == False
        assert allowed[1].item() == True

    def test_dag_allows_forward(self):
        trans = HammingTransition(N=4, dag_enabled=True)
        trans.set_dag_direction(torch.tensor([1.0, -1.0, 0.0, 0.0]))
        state = torch.tensor([0.0, 1.0, 0.0, 0.0])
        allowed = trans.get_allowed_flips(state)
        assert allowed[0].item() == True
        assert allowed[1].item() == True

    def test_batch_flip(self):
        trans = HammingTransition(N=4)
        state = torch.tensor([[1.0, 0.0, 0.0, 0.0],
                              [0.0, 1.0, 0.0, 0.0]])
        flip_indices = torch.tensor([1, 0])
        new_state = trans.batch_flip(state, flip_indices)
        assert new_state[0].tolist() == [1.0, 1.0, 0.0, 0.0]
        assert new_state[1].tolist() == [1.0, 1.0, 0.0, 0.0]

    def test_no_allowed_flips(self):
        trans = HammingTransition(N=2, dag_enabled=True)
        trans.set_dag_direction(torch.tensor([1.0, -1.0]))
        state = torch.tensor([1.0, 0.0])
        allowed = trans.get_allowed_flips(state)
        assert not allowed.any()
        new_state, idx = trans.random_flip(state)
        assert idx == -1
        assert new_state.tolist() == state.tolist()


class TestHammingMeasurement:

    def test_hamming_distance(self):
        a = torch.tensor([1, 0, 1, 0])
        b = torch.tensor([1, 1, 0, 0])
        assert HammingMeasurement.hamming_distance(a, b) == 2

    def test_hamming_distance_zero(self):
        a = torch.tensor([1, 0, 1, 0])
        assert HammingMeasurement.hamming_distance(a, a) == 0

    def test_hamming_weight(self):
        state = torch.tensor([1, 0, 1, 1, 0])
        assert HammingMeasurement.hamming_weight(state) == 3

    def test_normalized_hamming_weight(self):
        state = torch.tensor([1, 1, 0, 0])
        assert HammingMeasurement.normalized_hamming_weight(state) == 0.5

    def test_surface_distance(self):
        ref = torch.zeros(4)
        state = torch.tensor([1, 0, 0, 0])
        d = HammingMeasurement.surface_distance(state, ref)
        assert d == 1.0

    def test_symmetry_weight_max_at_half(self):
        N = 6
        weights = [HammingMeasurement.symmetry_weight(w, N) for w in range(N + 1)]
        assert weights[3] == max(weights)

    def test_symmetry_weight_symmetric(self):
        N = 6
        for w in range(N + 1):
            assert HammingMeasurement.symmetry_weight(w, N) == \
                   HammingMeasurement.symmetry_weight(N - w, N)

    def test_symmetry_weight_vector(self):
        N = 4
        weights = HammingMeasurement.symmetry_weight_vector(N)
        assert weights.shape == (5,)
        assert weights[2] == weights.max()

    def test_mid_surface_proximity(self):
        N = 8
        half = torch.tensor([1, 1, 1, 1, 0, 0, 0, 0]).float()
        assert HammingMeasurement.mid_surface_proximity(half) == pytest.approx(1.0)
        empty = torch.zeros(N)
        assert HammingMeasurement.mid_surface_proximity(empty) == 0.0

    def test_level_depth(self):
        state = torch.tensor([1, 1, 0, 1, 0])
        assert HammingMeasurement.level_depth(state) == 3

    def test_is_ascending(self):
        state_from = torch.tensor([1, 0, 0, 0])
        state_to = torch.tensor([1, 1, 0, 0])
        assert HammingMeasurement.is_ascending(state_from, state_to)

    def test_is_not_ascending(self):
        state_from = torch.tensor([1, 1, 0, 0])
        state_to = torch.tensor([1, 0, 0, 0])
        assert not HammingMeasurement.is_ascending(state_from, state_to)
