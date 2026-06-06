"""
Tests for engine/subspace_field.py — Phase 11 P1 subspace infrastructure.
"""

import pytest

from engine.subspace_field import (
    Rules, SubspaceSpec, SubspaceField,
    allocate_static, allocate_interleaved, allocate_random,
    make_uniform_field, make_static_field, make_interleaved_field, make_random_field,
    CouplingTopology, CouplingDirection,
)


# =============================================================================
# Rules 测试
# =============================================================================

class TestRules:
    def test_default(self):
        r = Rules.default()
        assert r.binding_multiplier == 1.0
        assert r.direction_bias == 0.5
        assert r.conservation_tightness == 0.05
        assert r.seal_threshold_multiplier == 1.0

    def test_custom(self):
        r = Rules(
            binding_multiplier=2.5,
            direction_bias=0.8,
            conservation_tightness=0.01,
            seal_threshold_multiplier=0.7,
        )
        assert r.binding_multiplier == 2.5
        r.check()

    def test_boundary_values(self):
        # Extremes that should pass
        Rules(binding_multiplier=0.2).check()
        Rules(binding_multiplier=5.0).check()
        Rules(direction_bias=0.0).check()
        Rules(direction_bias=1.0).check()
        Rules(conservation_tightness=0.01).check()
        Rules(conservation_tightness=0.1).check()
        Rules(seal_threshold_multiplier=0.5).check()
        Rules(seal_threshold_multiplier=2.0).check()

    def test_invalid_values(self):
        with pytest.raises(AssertionError):
            Rules(binding_multiplier=0.1).check()
        with pytest.raises(AssertionError):
            Rules(binding_multiplier=5.1).check()
        with pytest.raises(AssertionError):
            Rules(direction_bias=-0.1).check()
        with pytest.raises(AssertionError):
            Rules(direction_bias=1.1).check()
        with pytest.raises(AssertionError):
            Rules(conservation_tightness=0.0).check()
        with pytest.raises(AssertionError):
            Rules(conservation_tightness=0.11).check()


# =============================================================================
# 分配策略测试
# =============================================================================

class TestAllocation:
    def test_static_balanced(self):
        """N0 可被 k 整除时，各子空间大小相等。"""
        result = allocate_static(30, 3)
        assert len(result) == 3
        for s in result:
            assert len(s) == 10
        # 验证并集覆盖全部
        union = set.union(*result)
        assert union == set(range(30))

    def test_static_unbalanced(self):
        """N0 不可被 k 整除时，前 N0%k 个子空间多一个比特。"""
        result = allocate_static(32, 3)
        assert len(result) == 3
        sizes = [len(s) for s in result]
        assert sizes == [11, 11, 10]  # 32 = 11+11+10
        union = set.union(*result)
        assert union == set(range(32))

    def test_static_single(self):
        """k=1 → 只有一个子空间包含所有比特。"""
        result = allocate_static(40, 1)
        assert len(result) == 1
        assert result[0] == set(range(40))

    def test_static_k_equals_N0(self):
        """k=N0 → 每个子空间恰好一个比特。"""
        result = allocate_static(10, 10)
        assert len(result) == 10
        for s in result:
            assert len(s) == 1
        union = set.union(*result)
        assert union == set(range(10))

    def test_interleaved_balanced(self):
        """交错分配：每个子空间均匀分布。"""
        result = allocate_interleaved(12, 3)
        assert len(result) == 3
        assert result[0] == {0, 3, 6, 9}
        assert result[1] == {1, 4, 7, 10}
        assert result[2] == {2, 5, 8, 11}
        union = set.union(*result)
        assert union == set(range(12))

    def test_interleaved_single(self):
        result = allocate_interleaved(20, 1)
        assert len(result) == 1
        assert result[0] == set(range(20))

    def test_random_reproducible(self):
        """相同 seed 产生相同结果。"""
        a = allocate_random(30, 3, seed=42)
        b = allocate_random(30, 3, seed=42)
        for sa, sb in zip(a, b):
            assert sa == sb

    def test_random_different_seed(self):
        """不同 seed 产生不同结果。"""
        a = allocate_random(30, 3, seed=42)
        b = allocate_random(30, 3, seed=99)
        # 至少一个子空间不同（概率极大）
        differs = any(sa != sb for sa, sb in zip(a, b))
        assert differs

    def test_random_coverage(self):
        """随机分区仍覆盖所有比特。"""
        result = allocate_random(30, 3, seed=42)
        union = set.union(*result)
        assert union == set(range(30))

    def test_invalid_args(self):
        with pytest.raises(AssertionError):
            allocate_static(0, 1)
        with pytest.raises(AssertionError):
            allocate_static(10, 0)
        with pytest.raises(AssertionError):
            allocate_static(10, 11)
        with pytest.raises(AssertionError):
            allocate_interleaved(0, 1)
        with pytest.raises(AssertionError):
            allocate_random(10, 0)


# =============================================================================
# SubspaceSpec 测试
# =============================================================================

class TestSubspaceSpec:
    def test_minimal(self):
        spec = SubspaceSpec(bit_indices={0, 1, 2})
        assert spec.size == 3
        assert spec.name.startswith("subspace_")
        assert spec.rules == Rules.default()

    def test_named(self):
        spec = SubspaceSpec(
            bit_indices=set(range(10)),
            rules=Rules(binding_multiplier=2.0),
            name="strong",
        )
        assert spec.name == "strong"
        assert spec.size == 10

    def test_invalid_rules_triggers_check(self):
        """无效规则应在 __post_init__ 时触发断言。"""
        with pytest.raises(AssertionError):
            SubspaceSpec(bit_indices={0}, rules=Rules(binding_multiplier=0.1))


# =============================================================================
# SubspaceField 测试
# =============================================================================

class TestSubspaceField:
    def test_single_subspace(self):
        """一个子空间 = 原始统一空间模式。"""
        field = SubspaceField({
            "U": SubspaceSpec(set(range(30)), name="U"),
        })
        assert field.num_subspaces == 1
        assert field.total_bits == 30
        assert field.is_single()
        assert field.is_isolated()

    def test_three_subspaces(self):
        indices = allocate_static(60, 3)
        field = SubspaceField({
            "S0": SubspaceSpec(indices[0], name="S0"),
            "S1": SubspaceSpec(indices[1], name="S1"),
            "S2": SubspaceSpec(indices[2], name="S2"),
        })
        assert field.num_subspaces == 3
        assert field.total_bits == 60

    def test_bit_assignment_lookup(self):
        indices = allocate_static(30, 3)
        field = SubspaceField({
            "S0": SubspaceSpec(indices[0], name="S0"),
            "S1": SubspaceSpec(indices[1], name="S1"),
            "S2": SubspaceSpec(indices[2], name="S2"),
        })
        assert field.subspace_of_bit(0) == "S0"
        assert field.subspace_of_bit(9) == "S0"
        assert field.subspace_of_bit(10) == "S1"
        assert field.subspace_of_bit(29) == "S2"
        with pytest.raises(KeyError):
            field.subspace_of_bit(99)

    def test_overlapping_bits_raises(self):
        """重叠的比特分配应抛出 ValueError。"""
        with pytest.raises(ValueError):
            SubspaceField({
                "A": SubspaceSpec({0, 1, 2}),
                "B": SubspaceSpec({2, 3, 4}),  # bit 2 重叠！
            })

    def test_coupling_strength(self):
        indices = allocate_static(30, 3)
        field = SubspaceField(
            {"S0": SubspaceSpec(indices[0]), "S1": SubspaceSpec(indices[1])},
            coupling_strength=0.5,
        )
        assert field.coupling_strength_between("S0", "S1") == 0.5
        assert field.coupling_strength_between("S1", "S0") == 0.5

    def test_isolated_zero_coupling(self):
        indices = allocate_static(30, 3)
        field = SubspaceField(
            {"S0": SubspaceSpec(indices[0]), "S1": SubspaceSpec(indices[1])},
            coupling_strength=0.0,
        )
        assert field.is_isolated()
        assert field.coupling_strength_between("S0", "S1") == 0.0

    def test_coupled_pairs(self):
        indices = allocate_static(30, 3)
        field = SubspaceField(
            {
                "S0": SubspaceSpec(indices[0]),
                "S1": SubspaceSpec(indices[1]),
                "S2": SubspaceSpec(indices[2]),
            },
            coupling_strength=0.3,
        )
        pairs = field.coupled_pairs()
        assert len(pairs) == 3  # C(3,2) = 3
        strengths = [s for _, _, s in pairs]
        assert all(s == 0.3 for s in strengths)

    def test_get_bits(self):
        indices = allocate_static(30, 3)
        field = SubspaceField({
            "S0": SubspaceSpec(indices[0]),
        })
        assert field.get_bits("S0") == indices[0]
        assert isinstance(field.get_bits("S0"), set)

    def test_connection_unique(self):
        """全局耦合模式下，每对子空间只有一条连接。"""
        indices = allocate_static(30, 3)
        field = SubspaceField(
            {
                "a": SubspaceSpec(indices[0]),
                "b": SubspaceSpec(indices[1]),
                "c": SubspaceSpec(indices[2]),
            },
            coupling_strength=0.5,
        )
        assert len(field.connections) == 3  # C(3,2) 不重复

    def test_summary(self):
        field = SubspaceField(
            {"S0": SubspaceSpec(set(range(30)))},
            coupling_strength=0.0,
        )
        summary = field.summary()
        assert summary["num_subspaces"] == 1
        assert summary["total_bits"] == 30
        assert summary["isolated"] is True

    def test_ten_subspaces_static(self):
        """k=10, N0=100 的较大规模测试。"""
        field = make_static_field(N0=100, k=10)
        assert field.num_subspaces == 10
        assert field.total_bits == 100
        # 每个子空间 10 比特
        for name in field.space_names:
            assert len(field.get_bits(name)) == 10


# =============================================================================
# 工厂函数测试
# =============================================================================

class TestFactories:
    def test_make_uniform_field(self):
        field = make_uniform_field(N0=40)
        assert field.num_subspaces == 1
        assert field.total_bits == 40
        assert field.is_single()

    def test_make_static_field(self):
        field = make_static_field(N0=30, k=3, coupling_strength=0.2)
        assert field.num_subspaces == 3
        assert field.total_bits == 30
        for name in field.space_names:
            assert len(field.get_bits(name)) == 10
        assert not field.is_isolated()

    def test_make_static_field_with_rules(self):
        rules = [
            Rules(binding_multiplier=0.5),
            Rules(binding_multiplier=1.0),
            Rules(binding_multiplier=3.0),
        ]
        field = make_static_field(N0=60, k=3, rules_list=rules)
        assert field.get_spec("S0").rules.binding_multiplier == 0.5
        assert field.get_spec("S1").rules.binding_multiplier == 1.0
        assert field.get_spec("S2").rules.binding_multiplier == 3.0

    def test_make_interleaved_field(self):
        field = make_interleaved_field(N0=12, k=3)
        assert field.num_subspaces == 3
        assert field.get_spec("I0").bit_indices == {0, 3, 6, 9}

    def test_make_random_field(self):
        field = make_random_field(N0=30, k=3, seed=42)
        assert field.num_subspaces == 3
        assert field.total_bits == 30

    def test_random_reproducible_field(self):
        """相同 seed → 相同分配。"""
        a = make_random_field(N0=30, k=3, seed=42)
        b = make_random_field(N0=30, k=3, seed=42)
        for name in a.space_names:
            assert a.get_bits(name) == b.get_bits(name)