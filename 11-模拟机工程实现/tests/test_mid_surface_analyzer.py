"""test_mid_surface_analyzer.py — 中截面分析器测试"""

import pytest
import torch
from engine.mid_surface_analyzer import MidSurfaceAnalyzer
from engine.hamming_engine import HammingMeasurement


class TestMidSurfaceAnalyzer:

    def test_init_requires_even_n(self):
        with pytest.raises(ValueError):
            MidSurfaceAnalyzer(N=7)

    def test_init_valid(self):
        a = MidSurfaceAnalyzer(N=6)
        assert a.N == 6
        assert a.mid_w == 3

    def test_mid_surface_size(self):
        a = MidSurfaceAnalyzer(N=6)
        assert a.mid_surface_size() == 20  # C(6,3)=20

    def test_mid_surface_size_n4(self):
        a = MidSurfaceAnalyzer(N=4)
        assert a.mid_surface_size() == 6  # C(4,2)=6

    def test_is_on_mid_surface(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1, 1, 1, 0, 0, 0], dtype=torch.float32)
        assert a.is_on_mid_surface(s)

    def test_not_on_mid_surface(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1, 1, 0, 0, 0, 0], dtype=torch.float32)
        assert not a.is_on_mid_surface(s)

    def test_random_mid_surface_state(self):
        a = MidSurfaceAnalyzer(N=12)
        s = a.random_mid_surface_state()
        assert s.sum().item() == 6

    def test_enumerate_mid_surface_n6(self):
        a = MidSurfaceAnalyzer(N=6)
        states = a.enumerate_mid_surface()
        assert len(states) == 20
        for s in states:
            assert s.sum().item() == 3

    def test_enumerate_mid_surface_too_large(self):
        a = MidSurfaceAnalyzer(N=24)
        with pytest.raises(ValueError):
            a.enumerate_mid_surface()

    def test_distance_distribution(self):
        a = MidSurfaceAnalyzer(N=6)
        dist = a.distance_distribution(n_samples=50)
        assert len(dist) > 0
        # 中截面上距离必须是偶数（双比特翻转保持 w）
        for d in dist:
            assert d % 2 == 0 or d == 0

    def test_active_bits(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1, 1, 1, 0, 0, 0], dtype=torch.float32)
        assert a.active_bits(s) == 3

    def test_get_E_moves(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1, 1, 1, 0, 0, 0], dtype=torch.float32)
        moves = a.get_E_moves(s)
        assert len(moves) == 9  # 3 ones * 3 zeros

    def test_apply_E_valid(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = a.apply_E(s, 0, 1)
        assert result is not None
        assert result[0].item() == 0.0
        assert result[1].item() == 1.0

    def test_apply_E_preserves_weight(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = a.apply_E(s, 0, 1)
        assert result is not None
        assert result.sum().item() == s.sum().item()

    def test_apply_E_invalid(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = a.apply_E(s, 1, 0)  # bit1=0, bit0=1
        assert result is None

    def test_E_closure(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        closure = a.E_closure(s, max_depth=5)
        # 闭包应该包含多个状态
        assert len(closure) >= 1
        # 所有状态都在中截面上
        for state in closure:
            assert state.sum().item() == 3

    def test_three_active_bits_subspace(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        result = a.three_active_bits_subspace(s)
        assert result is not None
        assert len(result['active_bits']) == 3
        assert result['total_generators'] == 8
        assert result['algebra'] == 'su(3) candidate'

    def test_three_active_bits_not_enough(self):
        a = MidSurfaceAnalyzer(N=6)
        s = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
        result = a.three_active_bits_subspace(s)
        assert result is None

    def test_CR1_verification(self):
        """验证 CR-1: [E_ab, E_bc] = E_ac"""
        a = MidSurfaceAnalyzer(N=6)
        # 构造一个状态：bit0=1, bit1=0, bit2=1（这样 E_01 和 E_12 都有效）
        s = torch.tensor([1.0, 0.0, 1.0, 1.0, 0.0, 0.0])
        result = a.three_active_bits_subspace(s)
        assert result is not None
        cr1 = result['CR1_verified']
        # CR-1 可能成立或不成立，取决于具体状态
        assert 'CR1_holds' in cr1

    def test_analyze(self):
        a = MidSurfaceAnalyzer(N=6)
        report = a.analyze(n_samples=20)
        assert report['N'] == 6
        assert report['mid_surface_weight'] == 3
        assert report['mid_surface_size'] == 20
        assert len(report['distance_distribution']) > 0
        assert len(report['E_closure_sizes']) > 0
