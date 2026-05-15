"""test_hamming_layer.py — 汉明格点层测试"""

import pytest
import torch
from layers.hamming_layer import HammingLattice


class TestHammingLattice:

    def test_initial_state_binary(self):
        """初始状态是二值的"""
        layer = HammingLattice(N=16)
        state = layer.initial_state()
        unique = torch.unique(state)
        assert all(v in [0.0, 1.0] for v in unique.tolist())

    def test_initial_state_shape(self):
        """初始状态形状正确"""
        layer = HammingLattice(N=16)
        state = layer.initial_state(batch_size=4)
        assert state.shape == (4, 16)

    def test_project_state(self):
        """投影到 {0,1}"""
        layer = HammingLattice(N=8)
        raw = torch.tensor([0.1, 0.9, 0.4, 0.6, 0.0, 1.0, 0.3, 0.7])
        projected = layer.project_state(raw)
        assert projected.tolist() == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]

    def test_measure_invariant(self):
        """守恒量 = 汉明重量"""
        layer = HammingLattice(N=8)
        state = torch.tensor([1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0])
        inv = layer.measure_invariant(state)
        assert inv.item() == 4.0

    def test_transition_cost(self):
        """过渡成本 = 汉明距离"""
        layer = HammingLattice(N=4)
        state = torch.tensor([1.0, 0.0, 0.0, 0.0])
        next_state = torch.tensor([1.0, 1.0, 0.0, 0.0])
        cost = layer.transition_cost(state, next_state)
        assert cost.item() == 1.0

    def test_discreteness_violation(self):
        """离散性违背"""
        layer = HammingLattice(N=4)
        # 纯二值状态
        binary = torch.tensor([1.0, 0.0, 1.0, 0.0])
        assert layer.discreteness_violation(binary).item() == 0.0
        # 模糊状态
        fuzzy = torch.tensor([0.5, 0.5, 0.5, 0.5])
        assert layer.discreteness_violation(fuzzy).item() > 0.2

    def test_locality_violation_always_zero(self):
        """汉明格点的局域性违背恒为0"""
        layer = HammingLattice(N=8)
        state = torch.zeros(8)
        next_state = torch.ones(8)
        assert layer.locality_violation(state, next_state).item() == 0.0

    def test_inject_difference(self):
        """注入差异：0→1（动态位置选择）"""
        layer = HammingLattice(N=8)
        state = torch.zeros(8)
        result = layer.inject_difference(state, source_strength=3)
        # 注入后应该有至少 1 个 1（动态选择可能少于 3 个如果位置重复）
        assert result.sum().item() >= 1.0
        assert result.sum().item() <= 3.0

    def test_absorb_difference(self):
        """吸收差异：1→0（动态位置选择）"""
        layer = HammingLattice(N=8)
        state = torch.ones(8)
        result = layer.absorb_difference(state, sink_strength=3)
        # 吸收后应该有至多 5 个 1
        assert result.sum().item() >= 5.0
        assert result.sum().item() <= 7.0

    def test_apply_boundary_flow(self):
        """边界流：注入+吸收"""
        layer = HammingLattice(N=8)
        state = torch.zeros(8)
        result, injected, absorbed = layer.apply_boundary_flow(
            state, source_strength=2.0, sink_strength=1.0
        )
        assert result.sum().item() >= 0.0
        assert injected.sum().item() > 0.0

    def test_stability_violation(self):
        """稳定性违背"""
        layer = HammingLattice(N=8)
        # 恒定状态
        state = torch.ones(8) * 0.5
        window = [state.clone() for _ in range(10)]
        v = layer.stability_violation(window)
        assert v.item() >= 0.0

    def test_detect_stable_structures(self):
        """稳定结构检测"""
        layer = HammingLattice(N=8, stability_window=4)
        state = torch.tensor([1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0])
        history = [state.clone() for _ in range(10)]
        structures = layer.detect_stable_structures(history)
        assert len(structures) >= 1

    def test_coarse_grain(self):
        """粗粒化"""
        layer = HammingLattice(N=16, stability_window=4)
        state = torch.ones(16)
        history = [state.clone() for _ in range(10)]
        structures = layer.detect_stable_structures(history)
        new_layer = layer.coarse_grain(structures)
        assert new_layer is not None
        assert new_layer.N == 8

    def test_coarse_grain_empty(self):
        """无结构时粗粒化返回 None"""
        layer = HammingLattice(N=16)
        result = layer.coarse_grain([])
        assert result is None

    def test_measure_ascent_pressure(self):
        """升维压力"""
        layer = HammingLattice(N=8)
        state = torch.ones(8) * 0.5
        history = [state.clone() for _ in range(5)]
        structures = layer.detect_stable_structures(history)
        pressure = layer.measure_ascent_pressure(history, structures)
        assert pressure >= 0.0

    def test_step_hamming(self):
        """汉明演化一步"""
        layer = HammingLattice(N=8)
        state = torch.zeros(8)
        new_state, idx = layer.step_hamming(state)
        # 恰好翻转1位
        diff = (new_state != state).sum().item()
        assert diff == 1
        assert 0 <= idx < 8

    def test_step_hamming_batch(self):
        """批量汉明演化"""
        layer = HammingLattice(N=8)
        state = torch.zeros(4, 8)
        new_state, indices = layer.step_hamming(state)
        assert new_state.shape == (4, 8)
        # 每行恰好翻转1位
        for b in range(4):
            diff = (new_state[b] != state[b]).sum().item()
            assert diff == 1

    def test_step_hamming_with_weights(self):
        """带权重的汉明演化"""
        layer = HammingLattice(N=8)
        state = torch.zeros(8)
        weights = torch.tensor([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        new_state, idx = layer.step_hamming(state, weights)
        # 应该只翻转 bit 0
        assert idx == 0

    def test_evaluate_axioms(self):
        """严格化公理评估"""
        layer = HammingLattice(N=8, use_strict_axioms=True)
        state = torch.zeros(8)
        next_state = torch.zeros(8)
        next_state[0] = 1.0
        reports = layer.evaluate_axioms(state, next_state, [state])
        assert len(reports) == 8  # A1, A2, A4, A5, A6, A7, A8, A9

    def test_compute_axiom_loss(self):
        """严格化公理损失"""
        layer = HammingLattice(N=8, use_strict_axioms=True)
        state = torch.zeros(8)
        next_state = torch.zeros(8)
        next_state[0] = 1.0
        loss = layer.compute_axiom_loss(state, next_state, [state])
        assert loss.item() >= 0.0

    def test_reset(self):
        """重置"""
        layer = HammingLattice(N=8)
        layer._struct_registry = {0: {"test": 1}}
        layer._next_struct_id = 5
        layer.reset()
        assert len(layer._struct_registry) == 0
        assert layer._next_struct_id == 0

    def test_get_axiom_weight(self):
        """公理权重"""
        layer = HammingLattice(N=8)
        assert layer.get_axiom_weight("A2_discrete_encoding") == 1.0
        assert layer.get_axiom_weight("nonexistent") == 0.0

    def test_valid_state(self):
        """状态合法性检查"""
        layer = HammingLattice(N=8)
        assert layer.valid_state(torch.zeros(8))
        assert not layer.valid_state(torch.zeros(10))
