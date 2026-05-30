"""
GlobalBiasConstraint 单元测试

覆盖场景：
1. 基础功能：几何平均、算术平均、余弦相似度
2. 约束检测：方向一致性、强度平衡度
3. 边界条件：偏置不足、零向量、单机制
4. 历史查询：趋势、通过率、重置
5. 降级场景：违反机制检测
"""

from typing import List

import pytest
import torch
import numpy as np
from engine.global_bias_constraint import (
    GlobalBiasConstraint,
    GlobalBiasConstraintResult,
)


# ─── 辅助函数 ───

def make_bias(direction: List[float], magnitude: float = 1.0) -> torch.Tensor:
    """创建一个指定方向和幅度的偏置向量"""
    d = torch.tensor(direction, dtype=torch.float32)
    d = d / (d.norm() + 1e-10) * magnitude
    return d


# ─── 1. 基础功能测试 ───

class TestGlobalBiasConstraintBasics:
    """基础功能测试"""

    def test_geometric_mean_same_direction(self):
        """所有偏置方向相同时，几何平均应接近该方向"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.2),
            'memory': make_bias([1.0, 0.0, 0.0], 0.9),
            'replication': make_bias([1.0, 0.0, 0.0], 1.1),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)
        assert result.passed
        assert result.coherence > 0.99
        assert result.global_bias.norm() > 0.9

    def test_geometric_mean_opposite_directions(self):
        """偏置方向相反时，几何平均的范数应显著降低"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([-1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([-1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([0.0, 1.0, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)
        # 方向不一致时，一致性应较低
        assert result.coherence < 0.7
        # 应该不通过
        assert not result.passed

    def test_arithmetic_mean_option(self):
        """算术平均选项应产生不同结果"""
        gbc_geo = GlobalBiasConstraint(geometric_weighting=True)
        gbc_arith = GlobalBiasConstraint(geometric_weighting=False)

        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([0.0, 1.0, 0.0], 1.0),
            'memory': make_bias([1.0, 1.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.5, 0.0], 1.0),
            'selection': make_bias([0.5, 1.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.8, 0.0], 1.0),
        }

        result_geo = gbc_geo.evaluate(biases)
        result_arith = gbc_arith.evaluate(biases)

        # 两种平均方式应产生不同的全局偏置
        diff = (result_geo.global_bias - result_arith.global_bias).norm().item()
        assert diff > 0.01

    def test_cosine_similarity_perfect(self):
        """完全相同方向的余弦相似度应为 1"""
        a = make_bias([1.0, 0.0, 0.0], 1.0)
        b = make_bias([1.0, 0.0, 0.0], 2.0)
        sim = GlobalBiasConstraint._cosine_similarity(a, b)
        assert abs(sim - 1.0) < 1e-5

    def test_cosine_similarity_opposite(self):
        """完全相反方向的余弦相似度应为 -1"""
        a = make_bias([1.0, 0.0, 0.0], 1.0)
        b = make_bias([-1.0, 0.0, 0.0], 1.0)
        sim = GlobalBiasConstraint._cosine_similarity(a, b)
        assert abs(sim - (-1.0)) < 1e-5

    def test_cosine_similarity_orthogonal(self):
        """垂直方向的余弦相似度应为 0"""
        a = make_bias([1.0, 0.0, 0.0], 1.0)
        b = make_bias([0.0, 1.0, 0.0], 1.0)
        sim = GlobalBiasConstraint._cosine_similarity(a, b)
        assert abs(sim - 0.0) < 1e-5


# ─── 2. 约束检测测试 ───

class TestGlobalBiasConstraintEvaluation:
    """约束检测测试"""

    def test_all_pass(self):
        """所有机制方向一致时应通过"""
        gbc = GlobalBiasConstraint(coherence_threshold=0.6, balance_threshold=0.5)
        biases = {
            'boundary': make_bias([1.0, 0.01, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.01, 0.0], 1.0),
            'memory': make_bias([1.0, 0.01, 0.0], 1.0),
            'replication': make_bias([1.0, 0.01, 0.0], 1.0),
            'selection': make_bias([1.0, 0.01, 0.0], 1.0),
            'function': make_bias([1.0, 0.01, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)
        assert result.passed
        assert result.coherence > 0.99
        assert result.balance > 0.99

    def test_coherence_failure(self):
        """方向一致性不足时应失败"""
        gbc = GlobalBiasConstraint(coherence_threshold=0.8, balance_threshold=0.3)
        # 三组正交方向，全局偏置在中间，各机制与全局夹角余弦约 0.577
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([0.0, 1.0, 0.0], 1.0),
            'memory': make_bias([0.0, 0.0, 1.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([0.0, 1.0, 0.0], 1.0),
            'function': make_bias([0.0, 0.0, 1.0], 1.0),
        }
        result = gbc.evaluate(biases)
        assert not result.passed
        assert result.coherence < 0.7
        assert len(result.violating_mechanisms) > 0

    def test_balance_failure(self):
        """强度不平衡时应失败"""
        gbc = GlobalBiasConstraint(coherence_threshold=0.3, balance_threshold=0.8)
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 10.0),  # 远强于其他
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)
        assert not result.passed
        assert result.balance < 0.8

    def test_coupling_strengths_weighting(self):
        """耦合强度应影响权重分配"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([0.0, 1.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        # boundary 权重极高，应拉向 [1,0,0]
        result = gbc.evaluate(
            biases,
            coupling_strengths={'boundary': 10.0, 'self_sustaining': 0.1},
        )
        # 全局偏置应主要沿 x 轴
        assert result.global_bias[0].item() > abs(result.global_bias[1].item())

    def test_violating_mechanisms_identified(self):
        """应正确识别违反约束的机制"""
        gbc = GlobalBiasConstraint(coherence_threshold=0.7)
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([0.0, 1.0, 0.0], 1.0),  # 偏离
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)
        assert 'memory' in result.violating_mechanisms


# ─── 3. 边界条件测试 ───

class TestGlobalBiasConstraintEdgeCases:
    """边界条件测试"""

    def test_insufficient_mechanisms(self):
        """有效偏置不足时应失败"""
        gbc = GlobalBiasConstraint(min_mechanisms_required=4)
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([0.0, 0.0, 0.0], 0.0),  # 零向量
            'memory': make_bias([0.0, 0.0, 0.0], 0.0),
            'replication': make_bias([0.0, 0.0, 0.0], 0.0),
            'selection': make_bias([0.0, 0.0, 0.0], 0.0),
            'function': make_bias([0.0, 0.0, 0.0], 0.0),
        }
        result = gbc.evaluate(biases)
        assert not result.passed
        assert "有效偏置数量不足" in result.description

    def test_zero_vector_filtered(self):
        """零向量应被过滤"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': torch.zeros(3),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)
        assert 'memory' not in result.local_biases
        assert result.passed

    def test_custom_thresholds(self):
        """自定义阈值应生效"""
        gbc = GlobalBiasConstraint(coherence_threshold=0.95, balance_threshold=0.99)
        biases = {
            'boundary': make_bias([1.0, 0.1, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.05, 0.0], 1.1),
            'memory': make_bias([1.0, 0.08, 0.0], 0.95),
            'replication': make_bias([1.0, 0.02, 0.0], 1.05),
            'selection': make_bias([1.0, 0.07, 0.0], 1.0),
            'function': make_bias([1.0, 0.03, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)
        # 高阈值下可能不通过
        assert result.coherence < 1.0  # 有轻微方向偏差


# ─── 4. 历史查询测试 ───

class TestGlobalBiasConstraintHistory:
    """历史查询测试"""

    def test_history_accumulates(self):
        """历史记录应累积"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        for i in range(5):
            gbc.evaluate(biases)

        history = gbc.get_history()
        assert len(history) == 5

    def test_get_history_limit(self):
        """get_history 应支持限制数量"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        for _ in range(10):
            gbc.evaluate(biases)

        assert len(gbc.get_history(limit=3)) == 3

    def test_coherence_trend(self):
        """一致性趋势应正确返回"""
        gbc = GlobalBiasConstraint()
        biases_good = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        biases_bad = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([0.0, 1.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([0.0, 1.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([0.0, 1.0, 0.0], 1.0),
        }

        gbc.evaluate(biases_good)
        gbc.evaluate(biases_bad)
        gbc.evaluate(biases_good)

        trend = gbc.get_coherence_trend()
        assert len(trend) == 3
        assert trend[0] > trend[1]  # 好的 > 坏的
        assert trend[2] > trend[1]  # 好的 > 坏的

    def test_balance_trend(self):
        """平衡度趋势应正确返回"""
        gbc = GlobalBiasConstraint()
        biases_balanced = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        biases_unbalanced = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 10.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }

        gbc.evaluate(biases_balanced)
        gbc.evaluate(biases_unbalanced)

        trend = gbc.get_balance_trend()
        assert trend[0] > trend[1]  # 平衡 > 不平衡

    def test_pass_rate(self):
        """通过率应正确计算"""
        # 使用严格阈值确保 bad 配置会失败
        gbc = GlobalBiasConstraint(coherence_threshold=0.9, balance_threshold=0.9)
        biases_good = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        biases_bad = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([0.0, 1.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([0.0, 1.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([0.0, 1.0, 0.0], 1.0),
        }

        for _ in range(3):
            gbc.evaluate(biases_good)
        for _ in range(2):
            gbc.evaluate(biases_bad)

        assert abs(gbc.get_pass_rate() - 0.6) < 0.01

    def test_reset(self):
        """重置应清空历史"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        for _ in range(5):
            gbc.evaluate(biases)

        gbc.reset()
        assert len(gbc.get_history()) == 0
        assert gbc.get_pass_rate() == 0.0

    def test_repr_empty(self):
        """空状态 repr 应正确"""
        gbc = GlobalBiasConstraint()
        assert "empty" in repr(gbc)

    def test_repr_with_history(self):
        """有历史时 repr 应包含状态"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        gbc.evaluate(biases)
        r = repr(gbc)
        assert "PASS" in r or "FAIL" in r
        assert "coh=" in r
        assert "bal=" in r


# ─── 5. 结果数据结构测试 ───

class TestGlobalBiasConstraintResult:
    """结果数据结构测试"""

    def test_result_fields(self):
        """结果应包含所有必要字段"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.0, 0.0], 1.0),
            'memory': make_bias([1.0, 0.0, 0.0], 1.0),
            'replication': make_bias([1.0, 0.0, 0.0], 1.0),
            'selection': make_bias([1.0, 0.0, 0.0], 1.0),
            'function': make_bias([1.0, 0.0, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)

        assert isinstance(result.passed, bool)
        assert 0 <= result.coherence <= 1
        assert 0 <= result.balance <= 1
        assert isinstance(result.global_bias, torch.Tensor)
        assert isinstance(result.local_biases, dict)
        assert isinstance(result.coherence_by_mechanism, dict)
        assert isinstance(result.violating_mechanisms, list)
        assert isinstance(result.description, str)

    def test_coherence_by_mechanism_values(self):
        """各机制一致性值应在合理范围内"""
        gbc = GlobalBiasConstraint()
        biases = {
            'boundary': make_bias([1.0, 0.0, 0.0], 1.0),
            'self_sustaining': make_bias([1.0, 0.1, 0.0], 1.0),
            'memory': make_bias([1.0, -0.05, 0.0], 1.0),
            'replication': make_bias([1.0, 0.02, 0.0], 1.0),
            'selection': make_bias([1.0, 0.08, 0.0], 1.0),
            'function': make_bias([1.0, 0.03, 0.0], 1.0),
        }
        result = gbc.evaluate(biases)

        for name, cos_sim in result.coherence_by_mechanism.items():
            # 允许浮点误差
            assert -1.0 - 1e-5 <= cos_sim <= 1.0 + 1e-5
