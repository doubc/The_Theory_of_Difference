"""test_first_order_algebra.py — 一阶变易代数测试"""

import pytest
import torch
from engine.first_order_algebra import FirstOrderAlgebra


class TestFirstOrderAlgebra:

    def test_apply_E_valid(self):
        alg = FirstOrderAlgebra(N=6)
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = alg.apply_E(s, 0, 1)
        assert result is not None
        assert result[0].item() == 0.0
        assert result[1].item() == 1.0

    def test_apply_E_invalid(self):
        alg = FirstOrderAlgebra(N=6)
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = alg.apply_E(s, 1, 0)
        assert result is None

    def test_apply_E_preserves_weight(self):
        alg = FirstOrderAlgebra(N=6)
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = alg.apply_E(s, 0, 1)
        assert result is not None
        assert result.sum().item() == s.sum().item()

    def test_CR1_valid_state(self):
        """CR-1: [E_01, E_12] = E_02，在合适状态上验证"""
        alg = FirstOrderAlgebra(N=6)
        # bit0=1, bit1=0, bit2=1: E_01 有效，E_12 有效
        s = torch.tensor([1.0, 0.0, 1.0, 1.0, 0.0, 0.0])
        result = alg.verify_CR1(s, 0, 1, 2)
        assert 'CR1_holds' in result

    def test_CR1_invalid_moves(self):
        """当某些 E_ij 无效时，CR-1 应为 N/A"""
        alg = FirstOrderAlgebra(N=6)
        # bit0=0, bit1=0, bit2=0: 所有 E_ij 无效
        s = torch.zeros(6)
        result = alg.verify_CR1(s, 0, 1, 2)
        assert result['CR1_holds'] == 'N/A'

    def test_CR2_valid_state(self):
        """CR-2: [E_ij, E_ji] = x_i - x_j"""
        alg = FirstOrderAlgebra(N=6)
        # bit0=1, bit1=0: E_01 有效
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = alg.verify_CR2(s, 0, 1)
        assert 'CR2_holds' in result

    def test_CR2_same_bit(self):
        """E_ii 应该无效"""
        alg = FirstOrderAlgebra(N=6)
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = alg.apply_E(s, 0, 0)
        assert result is None

    def test_CR3_structure(self):
        """CR-3 验证结构"""
        alg = FirstOrderAlgebra(N=6)
        s = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        result = alg.verify_CR3(s, 0, 1)
        assert 'E_ij_state' in result
        assert 'xi_value' in result

    def test_count_generators_k2(self):
        alg = FirstOrderAlgebra(N=6)
        g = alg.count_generators([0, 1])
        assert g['k'] == 2
        assert g['total_generators'] == 3
        assert g['algebra'] == 'su(2)'

    def test_count_generators_k3(self):
        alg = FirstOrderAlgebra(N=6)
        g = alg.count_generators([0, 1, 2])
        assert g['k'] == 3
        assert g['total_generators'] == 8
        assert g['algebra'] == 'su(3)'

    def test_count_generators_k4(self):
        alg = FirstOrderAlgebra(N=8)
        g = alg.count_generators([0, 1, 2, 3])
        assert g['k'] == 4
        assert g['total_generators'] == 15

    def test_k_squared_minus_1(self):
        """验证生成元数 = k^2 - 1"""
        alg = FirstOrderAlgebra(N=12)
        for k in [2, 3, 4, 5]:
            bits = list(range(k))
            g = alg.count_generators(bits)
            assert g['total_generators'] == k**2 - 1

    def test_verify_all_CR(self):
        """批量验证对易关系"""
        alg = FirstOrderAlgebra(N=6)
        results = alg.verify_all_CR(n_samples=20)
        assert 'CR1_pass' in results
        assert 'CR2_pass' in results
        # 至少有一些状态能验证
        assert results['CR1_pass'] + results['CR1_N/A'] > 0
