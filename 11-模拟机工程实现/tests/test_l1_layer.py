"""
test_l1_layer.py — L1 抽象层测试

验证 L1 层的基本功能：状态空间、差异度量、守恒量、稳定性检测。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
import pytest
from layers.L1_abstract_layer import L1AbstractLayer


class TestL1AbstractLayer:
    """L1 抽象层测试"""

    def setup_method(self):
        self.layer = L1AbstractLayer(block_size=4, l1_shape=(4, 4))

    def test_initial_state_shape(self):
        """初始状态形状应正确"""
        state = self.layer.initial_state()
        assert state.shape == (1, 1, 4, 4)

    def test_initial_state_range(self):
        """初始状态应在 [0, 1] 范围内"""
        state = self.layer.initial_state()
        assert state.min() >= 0.0
        assert state.max() <= 1.0

    def test_project_state(self):
        """投影应裁剪到 [0, 1]"""
        raw = torch.tensor([[[[1.5, -0.5, 0.5, 0.0]]]])
        projected = self.layer.project_state(raw)
        assert projected.min() >= 0.0
        assert projected.max() <= 1.0

    def test_valid_state(self):
        """合法状态应通过验证"""
        state = torch.rand(1, 1, 4, 4)
        assert self.layer.valid_state(state) is True

    def test_invalid_state_nan(self):
        """NaN 状态应不合法"""
        state = torch.tensor([[[[float('nan'), 0.5, 0.5, 0.5]]]])
        assert self.layer.valid_state(state) is False

    def test_measure_difference(self):
        """差异度量应返回正确形状"""
        state = torch.rand(1, 1, 4, 4)
        diff = self.layer.measure_difference(state)
        assert diff.shape == state.shape

    def test_measure_difference_uniform(self):
        """均匀状态的差异应为零"""
        state = torch.ones(1, 1, 4, 4) * 0.5
        diff = self.layer.measure_difference(state)
        assert torch.allclose(diff, torch.zeros_like(diff), atol=1e-6)

    def test_measure_invariant(self):
        """守恒量应返回正确形状"""
        state = torch.rand(1, 1, 4, 4)
        inv = self.layer.measure_invariant(state)
        assert inv.shape == (1, 1, 1, 1)

    def test_transition_cost(self):
        """转换成本应为非负"""
        state = torch.rand(1, 1, 4, 4)
        next_state = torch.rand(1, 1, 4, 4)
        cost = self.layer.transition_cost(state, next_state)
        assert cost.min() >= 0.0

    def test_discreteness_violation(self):
        """离散性违背应为标量"""
        state = torch.rand(1, 1, 4, 4)
        violation = self.layer.discreteness_violation(state)
        assert violation.dim() == 0  # 标量

    def test_inject_difference(self):
        """注入差异应改变状态"""
        state = torch.rand(1, 1, 4, 4) * 0.5
        injected = self.layer.inject_difference(state, source_strength=1.0)
        # 边界值应增加
        assert injected[0, 0, 0, 0] >= state[0, 0, 0, 0]

    def test_absorb_difference(self):
        """吸收差异应改变状态"""
        state = torch.rand(1, 1, 4, 4) * 0.5 + 0.3
        absorbed = self.layer.absorb_difference(state, sink_strength=1.0)
        # 边界值应减少
        assert absorbed[0, 0, 0, -1] <= state[0, 0, 0, -1]

    def test_stability_violation(self):
        """稳定性违背应为非负标量"""
        history = [torch.rand(1, 1, 4, 4) for _ in range(8)]
        violation = self.layer.stability_violation(history)
        assert violation.dim() == 0
        assert violation >= 0.0

    def test_detect_stable_structures(self):
        """稳定结构检测应返回列表"""
        # 创建稳定的历史（值变化很小）
        base = torch.ones(1, 1, 4, 4) * 0.5
        history = [base + torch.randn(1, 1, 4, 4) * 0.01 for _ in range(16)]

        structures = self.layer.detect_stable_structures(history)
        assert isinstance(structures, list)

    def test_detect_stable_structures_insufficient_history(self):
        """历史不足时应返回空列表"""
        history = [torch.rand(1, 1, 4, 4) for _ in range(3)]
        structures = self.layer.detect_stable_structures(history)
        assert structures == []

    def test_coarse_grain_not_implemented(self):
        """L1 → L2 粗粒化暂未实现"""
        result = self.layer.coarse_grain([])
        assert result is None

    def test_measure_ascent_pressure(self):
        """升维压力应为非负浮点数"""
        history = [torch.rand(1, 1, 4, 4) for _ in range(8)]
        structures = []
        pressure = self.layer.measure_ascent_pressure(history, structures)
        assert isinstance(pressure, float)
        assert pressure >= 0.0

    def test_get_axiom_weight(self):
        """公理权重应为正数"""
        w = self.layer.get_axiom_weight("A7_stability")
        assert w > 0

    def test_name(self):
        """层名应正确"""
        assert self.layer.name == "L1_abstract"
