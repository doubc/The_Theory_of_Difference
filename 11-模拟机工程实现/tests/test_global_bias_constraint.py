"""
Unit tests for GlobalBiasConstraint

Tests cover:
  1. Basic evaluate() with consistent biases → PASS
  2. Conflicting biases → FAIL with correct violating mechanisms
  3. Insufficient valid biases → FAIL
  4. Geometric vs arithmetic mean
  5. Coupling strength weighting
  6. History tracking and query interfaces
  7. Threshold edge cases
"""

import pytest
import torch
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.global_bias_constraint import GlobalBiasConstraint, GlobalBiasConstraintResult


class TestGlobalBiasConstraintBasic:
    """基础功能测试"""

    def test_consistent_biases_pass(self):
        """所有偏置方向一致 → 应通过"""
        gbc = GlobalBiasConstraint()
        # 创建 6 个方向基本一致的偏置向量
        base = torch.tensor([1.0, 0.1, 0.05, -0.02, 0.03, 0.01] * 12)  # 72 维
        local_biases = {
            'boundary': base + torch.randn(72) * 0.05,
            'self_sustaining': base + torch.randn(72) * 0.05,
            'memory': base + torch.randn(72) * 0.05,
            'replication': base + torch.randn(72) * 0.05,
            'selection': base + torch.randn(72) * 0.05,
            'function': base + torch.randn(72) * 0.05,
        }
        result = gbc.evaluate(local_biases)
        assert result.passed is True
        assert result.coherence > 0.6
        assert result.balance > 0.5
        assert len(result.violating_mechanisms) == 0

    def test_conflicting_bias_fails(self):
        """一个偏置方向完全相反 → 应检测为违反"""
        # 5 个机制方向一致，1 个完全相反 → avg coherence = 4/6 ≈ 0.667
        # 使用更高阈值确保能检测到不一致
        gbc = GlobalBiasConstraint(coherence_threshold=0.8)
        base = torch.ones(72)
        local_biases = {
            'boundary': base,
            'self_sustaining': base,
            'memory': base,
            'replication': -base,  # 完全相反！
            'selection': base,
            'function': base,
        }
        result = gbc.evaluate(local_biases)
        assert result.passed is False
        assert 'replication' in result.violating_mechanisms
        assert result.coherence < 0.8

    def test_insufficient_biases(self):
        """有效偏置不足 4 个 → 应失败"""
        gbc = GlobalBiasConstraint(min_mechanisms_required=4)
        local_biases = {
            'boundary': torch.ones(72),
            'memory': torch.ones(72) * 0.5,
            # 其他 4 个机制缺失
        }
        result = gbc.evaluate(local_biases)
        assert result.passed is False
        assert "有效偏置数量不足" in result.description
        assert len(result.violating_mechanisms) == 4


class TestGlobalBiasConstraintWeighting:
    """加权方式测试"""

    def test_coupling_strength_weighting(self):
        """使用耦合强度加权"""
        gbc = GlobalBiasConstraint()
        base = torch.ones(72)
        local_biases = {
            'boundary': base * 2.0,
            'self_sustaining': base * 1.0,
            'memory': base * 1.5,
            'replication': base * 1.2,
            'selection': base * 0.8,
            'function': base * 1.1,
        }
        coupling = {
            'boundary': 0.9,
            'self_sustaining': 0.5,
            'memory': 0.7,
            'replication': 0.6,
            'selection': 0.4,
            'function': 0.55,
        }
        result_weighted = gbc.evaluate(local_biases, coupling_strengths=coupling)
        result_uniform = gbc.evaluate(local_biases)

        # 加权后的全局偏置应与均匀加权不同
        assert not torch.allclose(result_weighted.global_bias, result_uniform.global_bias, atol=1e-6)

    def test_geometric_vs_arithmetic_mean(self):
        """几何平均与算术平均应产生不同结果"""
        # 当向量方向有明显差异时，两种平均方式结果不同
        # 几何平均归一化到单位球面再平均，算术平均直接加权求和
        gbc_geo = GlobalBiasConstraint(geometric_weighting=True)
        gbc_arith = GlobalBiasConstraint(geometric_weighting=False)

        # 创建方向差异明显的向量（不同基方向）
        local_biases = {
            'boundary': torch.tensor([2.0, 0.0, 0.0, 0.0, 0.0, 0.0] * 12),
            'self_sustaining': torch.tensor([0.0, 2.0, 0.0, 0.0, 0.0, 0.0] * 12),
            'memory': torch.tensor([0.0, 0.0, 2.0, 0.0, 0.0, 0.0] * 12),
            'replication': torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 0.0] * 12),
            'selection': torch.tensor([1.0, 0.0, 1.0, 0.0, 0.0, 0.0] * 12),
            'function': torch.tensor([0.0, 1.0, 1.0, 0.0, 0.0, 0.0] * 12),
        }

        result_geo = gbc_geo.evaluate(local_biases)
        result_arith = gbc_arith.evaluate(local_biases)

        # 两种平均方式结果应不同（尤其在方向有差异时）
        # 几何平均会归一化方向，算术平均会保留强度差异
        assert not torch.allclose(result_geo.global_bias, result_arith.global_bias, atol=1e-3)


class TestGlobalBiasConstraintThresholds:
    """阈值边界测试"""

    def test_coherence_at_threshold(self):
        """一致性恰好在阈值边界"""
        gbc = GlobalBiasConstraint(coherence_threshold=0.6, balance_threshold=0.5)
        base = torch.ones(72)
        # 创建一个略高于阈值的偏置
        slightly_off = base * 0.61  # 余弦相似度约 0.61
        local_biases = {
            'boundary': base,
            'self_sustaining': base,
            'memory': base,
            'replication': base,
            'selection': slightly_off,
            'function': base,
        }
        result = gbc.evaluate(local_biases)
        # 应该通过（略高于阈值）
        assert result.coherence >= 0.6

    def test_balance_below_threshold(self):
        """强度平衡度低于阈值应失败"""
        gbc = GlobalBiasConstraint(balance_threshold=0.5)
        # 创建一个强度极端不平衡的情况（log-scale需要更大差异）
        # 5个机制强度=1.0，1个机制强度=0.001（1000倍差异）
        # log10(0.001)=-3, log10(1.0)=0, std≈1.44, balance=1-1.44/2≈0.28<0.5
        local_biases = {
            'boundary': torch.ones(72) * 1.0,
            'self_sustaining': torch.ones(72) * 1.0,
            'memory': torch.ones(72) * 1.0,
            'replication': torch.ones(72) * 0.001,  # 强度只有 0.1%（极端不平衡）
            'selection': torch.ones(72) * 1.0,
            'function': torch.ones(72) * 1.0,
        }
        result = gbc.evaluate(local_biases)
        # log-scale balance: 1 - std(log_intensities) / 2.0
        # 5个log10(1)=0, 1个log10(0.001)=-3, std≈1.44, balance≈0.28
        assert result.balance < 0.5
        assert result.passed is False

    def test_zero_bias_filtered(self):
        """零向量偏置应被过滤"""
        gbc = GlobalBiasConstraint(min_mechanisms_required=3)
        local_biases = {
            'boundary': torch.ones(72),
            'self_sustaining': torch.zeros(72),  # 零向量
            'memory': torch.ones(72),
            'replication': torch.ones(72),
            'selection': torch.ones(72),
            'function': torch.zeros(72),  # 零向量
        }
        result = gbc.evaluate(local_biases)
        # 应该只有 4 个有效偏置
        assert len(result.local_biases) == 4
        assert 'self_sustaining' not in result.local_biases
        assert 'function' not in result.local_biases


class TestGlobalBiasConstraintHistory:
    """历史追踪接口测试"""

    def test_history_tracking(self):
        """历史记录应正确累积"""
        gbc = GlobalBiasConstraint()
        base = torch.ones(72)
        local_biases = {
            'boundary': base,
            'self_sustaining': base,
            'memory': base,
            'replication': base,
            'selection': base,
            'function': base,
        }

        for i in range(5):
            gbc.evaluate(local_biases)

        history = gbc.get_history()
        assert len(history) == 5

        trend_coh = gbc.get_coherence_trend()
        assert len(trend_coh) == 5

        trend_bal = gbc.get_balance_trend()
        assert len(trend_bal) == 5

        assert gbc.get_pass_rate() == 1.0

    def test_history_limit(self):
        """get_history 应支持 limit 参数"""
        gbc = GlobalBiasConstraint()
        base = torch.ones(72)
        local_biases = {
            'boundary': base,
            'self_sustaining': base,
            'memory': base,
            'replication': base,
            'selection': base,
            'function': base,
        }

        for _ in range(10):
            gbc.evaluate(local_biases)

        assert len(gbc.get_history(limit=3)) == 3
        assert len(gbc.get_history(limit=100)) == 10

    def test_reset_clears_history(self):
        """reset 应清空历史"""
        gbc = GlobalBiasConstraint()
        base = torch.ones(72)
        local_biases = {
            'boundary': base,
            'self_sustaining': base,
            'memory': base,
            'replication': base,
            'selection': base,
            'function': base,
        }

        for _ in range(5):
            gbc.evaluate(local_biases)

        gbc.reset()
        assert len(gbc.get_history()) == 0
        assert gbc.get_pass_rate() == 0.0
        assert repr(gbc) == "GlobalBiasConstraint[empty]"


class TestGlobalBiasConstraintRepr:
    """字符串表示测试"""

    def test_repr_empty(self):
        assert repr(GlobalBiasConstraint()) == "GlobalBiasConstraint[empty]"

    def test_repr_with_results(self):
        gbc = GlobalBiasConstraint()
        base = torch.ones(72)
        local_biases = {
            'boundary': base,
            'self_sustaining': base,
            'memory': base,
            'replication': base,
            'selection': base,
            'function': base,
        }
        gbc.evaluate(local_biases)
        r = repr(gbc)
        assert "GlobalBiasConstraint" in r
        assert "PASS" in r or "FAIL" in r
        assert "coh=" in r
        assert "bal=" in r


class TestGlobalBiasConstraintResult:
    """结果对象测试"""

    def test_result_dataclass_fields(self):
        """结果对象应包含所有必需字段"""
        gbc = GlobalBiasConstraint()
        base = torch.ones(72)
        local_biases = {
            'boundary': base,
            'self_sustaining': base,
            'memory': base,
            'replication': base,
            'selection': base,
            'function': base,
        }
        result = gbc.evaluate(local_biases)

        assert isinstance(result, GlobalBiasConstraintResult)
        assert isinstance(result.passed, bool)
        assert isinstance(result.coherence, float)
        assert isinstance(result.balance, float)
        assert isinstance(result.global_bias, torch.Tensor)
        assert isinstance(result.local_biases, dict)
        assert isinstance(result.coherence_by_mechanism, dict)
        assert isinstance(result.violating_mechanisms, list)
        assert isinstance(result.description, str)

        assert 0 <= result.coherence <= 1.01  # 允许浮点误差略超 1.0
        assert 0 <= result.balance <= 1.01
        assert result.global_bias.shape[0] == 72


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
