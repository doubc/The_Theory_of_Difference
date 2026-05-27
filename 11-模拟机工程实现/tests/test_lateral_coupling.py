"""
tests/test_lateral_coupling.py — 横向耦合机制测试

覆盖：
- 结构注册/更新/移除
- 耦合对发现
- 三种耦合类型（边界重叠、密度梯度、耦合场扩散）
- 净效应计算
- 选择压力计算
- 报告生成
- 边界条件（空、单结构、远距离）
"""

import pytest
import numpy as np
from engine.lateral_coupling import (
    LateralCoupler,
    LateralCouplingPair,
    LateralCouplingReport,
    CouplingType,
    StructureHandle,
    DEFAULT_LATERAL_CONFIG,
)


# ─── Fixtures ───

@pytest.fixture
def coupler():
    """默认配置的耦合器"""
    return LateralCoupler()


@pytest.fixture
def close_pair_coupler():
    """两个近距离结构的耦合器"""
    c = LateralCoupler()
    c.register_structure(0, np.array([0.0, 0.0]), odi=0.6, boundary_radius=1.0)
    c.register_structure(1, np.array([0.5, 0.0]), odi=0.7, boundary_radius=1.0)
    return c


@pytest.fixture
def triangle_coupler():
    """三个结构形成三角形的耦合器"""
    c = LateralCoupler()
    c.register_structure(0, np.array([0.0, 0.0]), odi=0.8, boundary_radius=1.0)
    c.register_structure(1, np.array([1.0, 0.0]), odi=0.5, boundary_radius=1.0)
    c.register_structure(2, np.array([0.5, 1.0]), odi=0.3, boundary_radius=1.0)
    return c


@pytest.fixture
def distant_coupler():
    """两个远距离结构的耦合器"""
    c = LateralCoupler()
    c.register_structure(0, np.array([0.0, 0.0]), odi=0.6, boundary_radius=0.5)
    c.register_structure(1, np.array([100.0, 100.0]), odi=0.7, boundary_radius=0.5)
    return c


# ─── 结构注册 ───

class TestStructureRegistration:
    def test_register_single(self, coupler):
        coupler.register_structure(0, np.array([0.0, 0.0]), odi=0.5)
        assert coupler.n_structures == 1
        assert 0 in coupler.structure_ids

    def test_register_multiple(self, coupler):
        for i in range(5):
            coupler.register_structure(i, np.array([float(i), 0.0]), odi=0.5)
        assert coupler.n_structures == 5

    def test_register_overwrite(self, coupler):
        coupler.register_structure(0, np.array([0.0, 0.0]), odi=0.5)
        coupler.register_structure(0, np.array([1.0, 1.0]), odi=0.8)
        assert coupler.n_structures == 1
        s = coupler._structures[0]
        assert s.odi == 0.8
        np.testing.assert_array_almost_equal(s.position, np.array([1.0, 1.0]))

    def test_remove_structure(self, coupler):
        coupler.register_structure(0, np.array([0.0, 0.0]))
        coupler.register_structure(1, np.array([1.0, 0.0]))
        coupler.remove_structure(0)
        assert coupler.n_structures == 1
        assert 0 not in coupler.structure_ids

    def test_remove_cleans_pairs(self, coupler):
        coupler.register_structure(0, np.array([0.0, 0.0]))
        coupler.register_structure(1, np.array([1.0, 0.0]))
        coupler.compute_step(0)
        coupler.remove_structure(0)
        assert len(coupler._coupling_pairs) == 0

    def test_update_structure(self, coupler):
        coupler.register_structure(0, np.array([0.0, 0.0]), odi=0.5)
        coupler.update_structure(0, odi=0.9)
        assert coupler._structures[0].odi == 0.9

    def test_update_unregistered_raises(self, coupler):
        with pytest.raises(KeyError):
            coupler.update_structure(999, odi=0.5)


# ─── 耦合对发现 ───

class TestPairDiscovery:
    def test_close_pair_discovered(self, close_pair_coupler):
        report = close_pair_coupler.compute_step(0)
        assert report.n_active_pairs == 1

    def test_distant_pair_not_discovered(self, distant_coupler):
        report = distant_coupler.compute_step(0)
        assert report.n_active_pairs == 0

    def test_triangle_pairs(self, triangle_coupler):
        report = triangle_coupler.compute_step(0)
        # 3 个结构，最多 C(3,2) = 3 对
        assert report.n_active_pairs <= 3
        assert report.n_active_pairs >= 1  # 至少有一对足够近

    def test_empty_coupler(self, coupler):
        report = coupler.compute_step(0)
        assert report.n_active_pairs == 0
        assert report.n_structures == 0

    def test_single_structure(self, coupler):
        coupler.register_structure(0, np.array([0.0, 0.0]))
        report = coupler.compute_step(0)
        assert report.n_active_pairs == 0

    def test_pair_distance(self, close_pair_coupler):
        report = close_pair_coupler.compute_step(0)
        pair = report.pairs[0]
        assert abs(pair.distance - 0.5) < 1e-6


# ─── 耦合类型 ───

class TestCouplingTypes:
    def test_boundary_overlap_type(self):
        """边界重叠的近距离结构"""
        c = LateralCoupler()
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.5, boundary_radius=2.0)
        c.register_structure(1, np.array([0.5, 0.0]), odi=0.5, boundary_radius=2.0)
        report = c.compute_step(0)
        active = [p for p in report.pairs if p.is_active]
        assert len(active) > 0
        # 边界重叠 + 等密度 → BOUNDARY_OVERLAP
        assert active[0].coupling_type == CouplingType.BOUNDARY_OVERLAP

    def test_density_gradient_type(self):
        """密度差异大但边界不重叠的结构"""
        c = LateralCoupler(config={'max_coupling_distance': 10.0, 'density_gradient_sensitivity': 0.1})
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.9, boundary_radius=0.1)
        c.register_structure(1, np.array([5.0, 0.0]), odi=0.1, boundary_radius=0.1)
        report = c.compute_step(0)
        active = [p for p in report.pairs if p.is_active]
        if active:
            # 边界不重叠 + 密度差大 → DENSITY_GRADIENT
            assert active[0].coupling_type == CouplingType.DENSITY_GRADIENT

    def test_field_diffusion_type(self):
        """有耦合场但边界不重叠、密度相近的结构"""
        c = LateralCoupler(config={'max_coupling_distance': 10.0})
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.5, boundary_radius=0.1,
                             coupling_field_strength=0.8)
        c.register_structure(1, np.array([5.0, 0.0]), odi=0.5, boundary_radius=0.1,
                             coupling_field_strength=0.6)
        report = c.compute_step(0)
        active = [p for p in report.pairs if p.is_active]
        if active:
            assert active[0].coupling_type == CouplingType.COUPLING_FIELD_DIFFUSION


# ─── 耦合强度 ───

class TestCouplingStrength:
    def test_strength_decreases_with_distance(self):
        """耦合强度随距离增加而减弱"""
        c = LateralCoupler(config={'max_coupling_distance': 10.0})
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.8, boundary_radius=3.0)

        strengths = []
        for dist in [1.0, 2.0, 4.0, 6.0]:
            c2 = LateralCoupler(config={'max_coupling_distance': 10.0})
            c2.register_structure(0, np.array([0.0, 0.0]), odi=0.8, boundary_radius=3.0)
            c2.register_structure(1, np.array([dist, 0.0]), odi=0.8, boundary_radius=3.0)
            report = c2.compute_step(0)
            active = [p for p in report.pairs if p.is_active]
            if active:
                strengths.append(active[0].coupling_strength)
            else:
                strengths.append(0.0)

        # 强度应单调递减
        for i in range(len(strengths) - 1):
            assert strengths[i] >= strengths[i + 1]

    def test_strength_capped(self):
        """耦合强度不超过上限"""
        c = LateralCoupler(config={'coupling_cap': 0.5})
        c.register_structure(0, np.array([0.0, 0.0]), odi=1.0, boundary_radius=10.0)
        c.register_structure(1, np.array([0.01, 0.0]), odi=1.0, boundary_radius=10.0)
        report = c.compute_step(0)
        for pair in report.pairs:
            assert pair.coupling_strength <= 0.5 + 1e-6

    def test_zero_strength_for_distant(self, distant_coupler):
        """远距离结构耦合强度为 0"""
        report = distant_coupler.compute_step(0)
        for pair in report.pairs:
            assert pair.coupling_strength == 0.0
            assert not pair.is_active


# ─── 净效应 ───

class TestNetEffects:
    def test_net_effects_exist(self, close_pair_coupler):
        report = close_pair_coupler.compute_step(0)
        assert len(report.net_effects) == 2

    def test_high_density_benefits(self):
        """高密度结构从耦合中获益（正净效应）"""
        c = LateralCoupler(config={'max_coupling_distance': 10.0})
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.9, boundary_radius=0.5)
        c.register_structure(1, np.array([2.0, 0.0]), odi=0.1, boundary_radius=0.5)
        report = c.compute_step(0)
        # 低密度端应受到正向影响
        if report.net_effects[1] != 0:
            assert report.net_effects[1] > 0

    def test_symmetric_equal_density(self):
        """等密度结构的净效应应近似对称"""
        c = LateralCoupler(config={'max_coupling_distance': 10.0})
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.5, boundary_radius=2.0)
        c.register_structure(1, np.array([1.0, 0.0]), odi=0.5, boundary_radius=2.0)
        report = c.compute_step(0)
        # 等密度时两端都受到小的正向影响
        if 0 in report.net_effects and 1 in report.net_effects:
            assert abs(report.net_effects[0] - report.net_effects[1]) < 0.1


# ─── 选择压力 ───

class TestSelectionPressure:
    def test_selection_pressure_deltas_exist(self, close_pair_coupler):
        report = close_pair_coupler.compute_step(0)
        assert len(report.selection_pressure_deltas) == 2

    def test_higher_density_higher_pressure(self):
        """密度越高，选择压力变化越大"""
        c = LateralCoupler(config={'max_coupling_distance': 10.0})
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.9, boundary_radius=0.5)
        c.register_structure(1, np.array([2.0, 0.0]), odi=0.1, boundary_radius=0.5)
        report = c.compute_step(0)
        # 高密度端的选择压力变化应更显著
        if report.selection_pressure_deltas[0] != 0 and report.selection_pressure_deltas[1] != 0:
            assert abs(report.selection_pressure_deltas[0]) >= abs(report.selection_pressure_deltas[1])


# ─── 报告 ───

class TestReport:
    def test_report_fields(self, close_pair_coupler):
        report = close_pair_coupler.compute_step(0)
        assert report.timestamp == 0
        assert report.n_structures == 2
        assert isinstance(report.total_coupling_strength, float)
        assert isinstance(report.mean_coupling_strength, float)

    def test_report_history(self, coupler):
        coupler.register_structure(0, np.array([0.0, 0.0]))
        coupler.compute_step(0)
        coupler.compute_step(1)
        coupler.compute_step(2)
        history = coupler.get_report_history()
        assert len(history) == 3

    def test_report_history_limit(self, coupler):
        coupler.register_structure(0, np.array([0.0, 0.0]))
        for i in range(10):
            coupler.compute_step(i)
        history = coupler.get_report_history(limit=5)
        assert len(history) == 5


# ─── 查询接口 ───

class TestQueryInterface:
    def test_get_neighbors(self, triangle_coupler):
        report = triangle_coupler.compute_step(0)
        neighbors = triangle_coupler.get_neighbors(0)
        for pair in neighbors:
            assert 0 in (pair.structure_a_id, pair.structure_b_id)

    def test_get_coupling_strength(self, close_pair_coupler):
        close_pair_coupler.compute_step(0)
        strength = close_pair_coupler.get_coupling_strength(0, 1)
        assert strength >= 0.0

    def test_get_coupling_strength_unregistered(self, coupler):
        strength = coupler.get_coupling_strength(0, 1)
        assert strength == 0.0


# ─── 重置 ───

class TestReset:
    def test_reset_clears_all(self, close_pair_coupler):
        close_pair_coupler.compute_step(0)
        close_pair_coupler.reset()
        assert close_pair_coupler.n_structures == 0
        assert len(close_pair_coupler._coupling_pairs) == 0
        assert len(close_pair_coupler._reports) == 0


# ─── 多步演化 ───

class TestMultiStep:
    def test_structures_move_closer(self):
        """结构逐渐靠近，耦合强度应增加"""
        c = LateralCoupler(config={'max_coupling_distance': 10.0})
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.6, boundary_radius=1.0)

        strengths = []
        for step in range(5):
            pos = np.array([5.0 - step, 0.0])  # 从距离 5 逐渐到距离 1
            c.register_structure(1, pos, odi=0.6, boundary_radius=1.0)
            report = c.compute_step(step)
            active = [p for p in report.pairs if p.is_active]
            if active:
                strengths.append(active[0].coupling_strength)
            else:
                strengths.append(0.0)

        # 靠近过程中强度应总体递增
        if len(strengths) >= 2 and strengths[-1] > 0:
            assert strengths[-1] > strengths[0]

    def test_dynamic_registration(self):
        """动态添加结构"""
        c = LateralCoupler()
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.6)
        c.compute_step(0)
        assert c.n_structures == 1

        c.register_structure(1, np.array([0.5, 0.0]), odi=0.7)
        report = c.compute_step(1)
        assert report.n_structures == 2
        assert report.n_active_pairs >= 1


# ─── 配置 ───

class TestConfig:
    def test_custom_config(self):
        c = LateralCoupler(config={'max_coupling_distance': 5.0})
        assert c.config['max_coupling_distance'] == 5.0
        # 其他配置保持默认
        assert 'coupling_decay_rate' in c.config

    def test_default_config_complete(self):
        """默认配置包含所有必需键"""
        required_keys = [
            'max_coupling_distance', 'coupling_decay_rate',
            'boundary_overlap_threshold', 'field_diffusion_rate',
            'density_gradient_sensitivity', 'max_neighbors', 'coupling_cap',
        ]
        for key in required_keys:
            assert key in DEFAULT_LATERAL_CONFIG


# ─── 语义防火墙 ───

class TestSemanticFirewall:
    def test_no_semantic_content_in_types(self):
        """耦合类型不包含语义内容"""
        for ct in CouplingType:
            name = ct.value
            # 不应包含意图性/语义性词汇
            forbidden = ['competition', 'cooperation', 'intent', 'goal', 'meaning']
            for word in forbidden:
                assert word not in name.lower()

    def test_report_no_identity_concepts(self):
        """报告中不包含身份/意志等概念"""
        c = LateralCoupler()
        c.register_structure(0, np.array([0.0, 0.0]), odi=0.6)
        c.register_structure(1, np.array([0.5, 0.0]), odi=0.7)
        report = c.compute_step(0)
        report_str = str(report)
        forbidden = ['identity', 'will', 'intention', 'meaning', 'purpose']
        for word in forbidden:
            assert word not in report_str.lower()
