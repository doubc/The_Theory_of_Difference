"""
tests/test_cross_layer_gravity_integration.py — 跨层级引力调制集成测试

验证 CrossLayerGravityModulator 的正确集成：
1. 引力场计算：冻结激活比特作为质量源产生引力势
2. 引力投影：通过封装映射正确投影到上一层
3. 多层调制：中间层同时接收上下层引力（compute_modulation）
4. 引力衰减：随时间衰减
5. Evolver 集成：gravity_modulator 正确注册

注意：HierarchicalEvolver 只在 run() 过程中动态创建高层（通过封装），
因此集成测试主要验证 modulator 本身，以及 evolver 的初始化注册。
"""

import pytest
import torch
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.cross_layer_gravity import CrossLayerGravityModulator, GravityField
from engine.encapsulation_engine import EncapsulationEngine
from engine.hierarchical_evolver import HierarchicalEvolver


# ─── Fixtures ───

@pytest.fixture
def modulator():
    return CrossLayerGravityModulator(
        gravity_decay=0.5,
        modulation_strength=0.1,
        distance_exponent=2.0
    )


# ─── Unit: GravityModulator standalone ───

class TestGravityModulatorStandalone:
    """CrossLayerGravityModulator 核心功能单元测试"""

    def test_compute_field_with_mass_sources(self, modulator):
        """有质量源时产生非零引力势"""
        state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        frozen = {0, 1}
        active = set(range(8))

        field = modulator.compute_gravity_field(
            layer_id=0, state=state, frozen_bits=frozen,
            active_bits=active, step=0
        )

        assert field.total_mass == 2
        assert field.potential.abs().sum() > 0
        # 质量源位置应有最高引力势
        assert field.potential[0] > field.potential[7]

    def test_compute_field_no_mass_sources(self, modulator):
        """无质量源时返回零场"""
        state = torch.zeros(8)
        frozen = {0, 1}
        active = set(range(8))

        field = modulator.compute_gravity_field(
            layer_id=0, state=state, frozen_bits=frozen,
            active_bits=active, step=0
        )

        assert field.total_mass == 0
        assert field.potential.abs().max() == 0

    def test_project_up_with_encapsulation(self, modulator):
        """通过封装映射向上投影"""
        state = torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        frozen = {0, 1, 2}
        active = set(range(8))
        binding = torch.ones(8, 8) * 0.5

        encap = EncapsulationEngine(binding_threshold=0.3, min_group_size=2)
        new_state, enc_bits, mapping = encap.encapsulate(
            state=state, frozen_bits=frozen, binding_strength=binding,
            active_bits=active, layer=0
        )

        field = modulator.compute_gravity_field(
            layer_id=0, state=state, frozen_bits=frozen,
            active_bits=active, binding_strength=binding, step=0
        )

        projected = modulator.project_gravity_up(
            source_layer_id=0, source_field=field,
            target_N=len(new_state), encap_engine=encap, source_layer=0
        )

        assert projected.shape == (len(new_state),)
        # 投影后应应用衰减
        assert projected.abs().max() <= 1.0

    def test_compute_modulation_multi_layer(self, modulator):
        """多层调制：中间层同时接收上下层引力"""
        field_l0 = GravityField(
            layer_id=0,
            potential=torch.tensor([0.8, 0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6]),
            mass_sources=[0, 1],
            generation_step=0
        )
        field_l2 = GravityField(
            layer_id=2,
            potential=torch.tensor([0.5, 0.3, 0.1, -0.1, -0.3, -0.5]),
            mass_sources=[0],
            generation_step=0
        )

        result = modulator.compute_modulation(
            layer_id=1,
            lower_fields=[field_l0],
            upper_fields=[field_l2],
            target_state=torch.zeros(8)
        )

        assert 'modulation_vector' in result
        assert result['n_lower_fields'] == 1
        assert result['n_upper_fields'] == 1
        # 调制向量应有非零值
        assert result['modulation_vector'].abs().sum() > 0

    def test_gravity_decay_over_time(self, modulator):
        """引力势随时间衰减"""
        state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        frozen = {0, 1}
        active = set(range(8))

        field = modulator.compute_gravity_field(
            layer_id=0, state=state, frozen_bits=frozen,
            active_bits=active, step=0
        )

        initial_max = field.potential.abs().max().item()
        field.decay(steps_elapsed=50, decay_rate=0.98)
        after_decay_max = field.potential.abs().max().item()

        assert after_decay_max < initial_max

    def test_project_gravity_down(self, modulator):
        """高层引力向下投影到低层"""
        field_high = GravityField(
            layer_id=2,
            potential=torch.tensor([0.8, 0.4, -0.4, -0.8]),
            mass_sources=[0],
            generation_step=0
        )

        projected = modulator.project_gravity_down(
            source_field=field_high, target_N=8, decay_factor=0.5
        )

        assert projected.shape == (8,)
        # 衰减后不超过 0.5
        assert projected.abs().max() <= 0.5

    def test_injection_modulation_scores(self, modulator):
        """引力调制对注入候选者的影响评分"""
        field_l0 = GravityField(
            layer_id=0,
            potential=torch.tensor([0.9, 0.7, 0.5, 0.3, 0.1, -0.1, -0.3, -0.5]),
            mass_sources=[0, 1],
            generation_step=0
        )

        all_fields = {0: [field_l0]}
        candidates = [0, 1, 2, 3, 4]

        scores = modulator.get_modulation_for_injection(
            layer_id=1, candidates=candidates, all_fields=all_fields
        )

        # 正引力势区域应获得更高评分
        assert scores[0] > scores[4]

    def test_clear_old_fields(self, modulator):
        """清除过老的引力场"""
        state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        frozen = {0, 1}
        active = set(range(8))

        # 生成多个场
        for step in range(5):
            modulator.compute_gravity_field(
                layer_id=0, state=state, frozen_bits=frozen,
                active_bits=active, step=step
            )

        assert len(modulator.gravity_fields[0]) == 5

        # 清除超过 2 步的场
        modulator.clear_old_fields(max_age_steps=2, current_step=5)

        assert len(modulator.gravity_fields[0]) <= 3

    def test_get_summary(self, modulator):
        """获取引力调制摘要"""
        state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        frozen = {0, 1}
        active = set(range(8))

        modulator.compute_gravity_field(
            layer_id=0, state=state, frozen_bits=frozen,
            active_bits=active, step=0
        )

        summary = modulator.get_summary()

        assert summary['n_layers'] == 3
        assert summary['fields_per_layer'][0] == 1
        assert summary['total_modulation_events'] == 0


# ─── Integration: Evolver registration ───

class TestEvolverGravityRegistration:
    """HierarchicalEvolver 中 gravity_modulator 的注册测试"""

    def test_modulator_registered_in_evolver(self):
        """Evolver 正确初始化 gravity_modulator"""
        evolver = HierarchicalEvolver(
            N0=8,
            max_layers=3,
            device='cpu',
            steps_per_layer=100,
        )

        assert hasattr(evolver, 'gravity_modulator')
        assert isinstance(evolver.gravity_modulator, CrossLayerGravityModulator)
        # n_layers 应与 max_layers 一致
        assert len(evolver.gravity_modulator.gravity_fields) == 3

    def test_evolver_gravity_fields_initialized(self):
        """Evolver 的 gravity_fields 字典正确初始化"""
        evolver = HierarchicalEvolver(
            N0=8,
            max_layers=3,
            device='cpu',
            steps_per_layer=100,
        )

        for layer_id in range(3):
            assert layer_id in evolver.gravity_modulator.gravity_fields
            assert isinstance(evolver.gravity_modulator.gravity_fields[layer_id], list)


# ─── Regression: Multi-layer gravity baseline ───

class TestMultiLayerGravityBaseline:
    """多层引力调制基准测试

    当前 HierarchicalEvolver._compute_cross_layer_gravity 只计算单层投影。
    此测试记录 modulator 本身的多层能力，为未来 evolver 扩展到多层调制提供基准。
    """

    def test_modulator_full_multi_layer_chain(self, modulator):
        """modulator 支持完整的三层引力调制链"""
        # L0: 8 bits, 2 个质量源
        field_l0 = GravityField(
            layer_id=0,
            potential=torch.tensor([0.8, 0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6]),
            mass_sources=[0, 1],
            generation_step=0
        )
        # L1: 4 bits, 1 个质量源
        field_l1 = GravityField(
            layer_id=1,
            potential=torch.tensor([0.5, 0.3, -0.3, -0.5]),
            mass_sources=[0],
            generation_step=0
        )
        # L2: 2 bits, 1 个质量源
        field_l2 = GravityField(
            layer_id=2,
            potential=torch.tensor([0.7, -0.7]),
            mass_sources=[0],
            generation_step=0
        )

        # L1 接收 L0(向上) 和 L2(向下) 的调制
        result_l1 = modulator.compute_modulation(
            layer_id=1,
            lower_fields=[field_l0],
            upper_fields=[field_l2],
            target_state=torch.zeros(4)
        )

        assert result_l1['modulation_vector'].shape == (4,)
        assert result_l1['n_lower_fields'] == 1
        assert result_l1['n_upper_fields'] == 1

        # L0 只接收 L1(向下) 的约束
        result_l0 = modulator.compute_modulation(
            layer_id=0,
            lower_fields=[],
            upper_fields=[field_l1],
            target_state=torch.zeros(8)
        )

        assert result_l0['n_lower_fields'] == 0
        assert result_l0['n_upper_fields'] == 1

    def test_gravity_field_repr(self, modulator):
        """GravityField 的字符串表示包含关键信息"""
        state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        frozen = {0, 1}
        active = set(range(8))

        field = modulator.compute_gravity_field(
            layer_id=0, state=state, frozen_bits=frozen,
            active_bits=active, step=0
        )

        repr_str = repr(field)
        assert 'L0' in repr_str
        assert 'mass=2' in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
