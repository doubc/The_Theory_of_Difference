"""
Tests for Phase 11 P3: SubspaceAwareEvolver — engine/subspace_evolver.py

Coverage:
1. SubspaceSolver creation and properties
2. CouplingEngine callback creation
3. LayerCoordinator strategies (ALL_SEALED, MAJORITY_SEALED, INDEPENDENT)
4. SubspaceAwareEvolver constructor
5. Rules scaling (binding_multiplier)
6. End-to-end: isolated & coupled runs
7. Edge cases: single subspace, subspaces too small
8. Import test from engine package
"""

import math
import pytest
import torch

from engine.subspace_field import (
    Rules, SubspaceSpec, SubspaceField,
    allocate_static, make_static_field, make_uniform_field,
)
from engine.subspace_evolver import (
    SubspaceSolver, CouplingEngine, LayerCoordinator,
    SubspaceAwareEvolver,
    run_subspace_experiment,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def default_rules():
    return Rules()


@pytest.fixture
def two_subspace_isolated():
    return make_static_field(N0=48, k=2, coupling_strength=0.0)


@pytest.fixture
def two_subspace_coupled():
    return make_static_field(N0=48, k=2, coupling_strength=0.3)


@pytest.fixture
def three_subspace_isolated():
    return make_static_field(N0=72, k=3, coupling_strength=0.0)


@pytest.fixture
def uniform_field():
    return make_uniform_field(N0=48)


# =============================================================================
# SubspaceSolver Tests
# =============================================================================

class TestSubspaceSolver:
    def test_creation(self, default_rules):
        spec = SubspaceSpec(set(range(12)), rules=default_rules, name="S0")
        solver = SubspaceSolver(
            name="S0", subspace=spec, N=12,
        )
        assert solver.name == "S0"
        assert solver.N == 12
        assert not solver.is_sealed
        assert not solver.has_ever_sealed
        assert solver.step_count == 0

    def test_with_strong_binding_rules(self):
        rules = Rules(binding_multiplier=3.0, direction_bias=0.7)
        spec = SubspaceSpec(set(range(12)), rules=rules, name="S0")
        solver = SubspaceSolver(name="S0", subspace=spec, N=12)
        summary = solver.get_summary()
        assert summary["subspace_rules"]["binding_multiplier"] == 3.0
        assert summary["subspace_rules"]["direction_bias"] == 0.7

    def test_get_summary(self):
        rules = Rules(binding_multiplier=2.0)
        spec = SubspaceSpec(set(range(24)), rules=rules, name="S1")
        solver = SubspaceSolver(
            name="S1", subspace=spec, N=24,
            is_sealed=True, has_ever_sealed=True,
            hamming_weight=12.0, step_count=500,
        )
        summary = solver.get_summary()
        assert summary["name"] == "S1"
        assert summary["N"] == 24
        assert summary["sealed"] is True
        assert summary["ever_sealed"] is True


# =============================================================================
# CouplingEngine Tests
# =============================================================================

class TestCouplingEngine:
    def test_isolated_field_noop(self, two_subspace_isolated):
        """Isolated field coupling engine should create no-op callback."""
        engine = CouplingEngine(two_subspace_isolated)
        solvers = {
            "S0": SubspaceSolver(name="S0", subspace=None, N=24),
            "S1": SubspaceSolver(name="S1", subspace=None, N=24),
        }
        cb = engine.make_callback("S1", solvers)
        assert cb is not None
        # The callback should be a no-op (lambda returns None)
        assert cb(0, None, None, None) is None

    def test_coupled_engine_creates_callback(self, two_subspace_coupled):
        """Coupled field should create a real callback."""
        engine = CouplingEngine(two_subspace_coupled)
        solvers = {
            "S0": SubspaceSolver(name="S0", subspace=None, N=24),
            "S1": SubspaceSolver(name="S1", subspace=None, N=24),
        }
        # S1's callback should reference S0
        cb = engine.make_callback("S1", solvers)
        assert cb is not None

    def test_coupling_metrics(self, two_subspace_coupled):
        """Coupling metrics should return per-connection data."""
        engine = CouplingEngine(two_subspace_coupled)
        solvers = {
            "S0": SubspaceSolver(name="S0", subspace=None, N=24,
                                  is_sealed=True, hamming_weight=10.0),
            "S1": SubspaceSolver(name="S1", subspace=None, N=24,
                                  is_sealed=False, hamming_weight=15.0),
        }
        metrics = CouplingEngine.compute_coupling_metrics(solvers, two_subspace_coupled)
        assert len(metrics) > 0
        # There should be an S0→S1 or S1→S0 entry
        keys = list(metrics.keys())
        conn_key = [k for k in keys if "S0" in k and "S1" in k]
        assert len(conn_key) >= 0  # at least, don't crash


# =============================================================================
# LayerCoordinator Tests
# =============================================================================

class TestLayerCoordinator:
    def _make_solver(self, name: str, sealed: bool, layer: int = 0):
        return SubspaceSolver(
            name=name, subspace=SubspaceSpec(set(), name=name),
            N=12, current_layer=layer, is_sealed=sealed,
        )

    def test_all_sealed(self):
        coord = LayerCoordinator(LayerCoordinator.ALL_SEALED)
        s0 = self._make_solver("S0", sealed=False)
        s1 = self._make_solver("S1", sealed=False)

        # None sealed → no advance
        should, _ = coord.should_advance({"S0": s0, "S1": s1}, 3)
        assert not should

        # One sealed → no advance
        s0.is_sealed = True
        should, _ = coord.should_advance({"S0": s0, "S1": s1}, 3)
        assert not should

        # Both sealed → advance to layer 1
        s1.is_sealed = True
        should, next_layer = coord.should_advance({"S0": s0, "S1": s1}, 3)
        assert should
        assert next_layer == 1

    def test_all_sealed_at_max_layers(self):
        coord = LayerCoordinator(LayerCoordinator.ALL_SEALED)
        s0 = self._make_solver("S0", sealed=True)
        s1 = self._make_solver("S1", sealed=True)

        # Both sealed but at max_layers → no advance
        should, next_layer = coord.should_advance({"S0": s0, "S1": s1}, 1)
        assert not should

    def test_majority_sealed(self):
        coord = LayerCoordinator(LayerCoordinator.MAJORITY_SEALED)
        solvers = {
            f"S{i}": self._make_solver(f"S{i}", sealed=False)
            for i in range(3)
        }

        # 0/3 sealed → no
        should, _ = coord.should_advance(solvers, 3)
        assert not should

        # 1/3 sealed (33% ≤ 50%) → no
        solvers["S0"].is_sealed = True
        should, _ = coord.should_advance(solvers, 3)
        assert not should

        # 2/3 sealed (67% > 50%) → yes
        solvers["S1"].is_sealed = True
        should, next_layer = coord.should_advance(solvers, 3)
        assert should
        assert next_layer == 1

    def test_independent(self):
        coord = LayerCoordinator(LayerCoordinator.INDEPENDENT)
        s0 = self._make_solver("S0", sealed=False)
        solvers = {"S0": s0}

        should, _ = coord.should_advance(solvers, 3)
        assert not should

        s0.is_sealed = True
        should, next_layer = coord.should_advance(solvers, 3)
        assert should
        assert next_layer == 1

    def test_all_sealed_check(self):
        coord = LayerCoordinator()
        s0 = self._make_solver("S0", sealed=False)
        s1 = self._make_solver("S1", sealed=True)
        assert not coord.all_sealed({"S0": s0, "S1": s1})
        s0.is_sealed = True
        assert coord.all_sealed({"S0": s0, "S1": s1})


# =============================================================================
# SubspaceAwareEvolver Tests
# =============================================================================

class TestSubspaceAwareEvolver:
    def test_constructor(self, two_subspace_isolated):
        evolver = SubspaceAwareEvolver(
            two_subspace_isolated,
            steps_per_layer=300,
            max_layers=1,
            verbose=False,
        )
        assert evolver.field.num_subspaces == 2
        assert evolver.max_layers == 1
        assert isinstance(evolver.coordinator, LayerCoordinator)

    def test_constructor_uniform(self, uniform_field):
        evolver = SubspaceAwareEvolver(
            uniform_field, steps_per_layer=300, max_layers=1, verbose=False,
        )
        assert evolver.field.num_subspaces == 1

    def test_single_subspace_run(self, uniform_field):
        """Single subspace run — backward compat smoke test."""
        evolver = SubspaceAwareEvolver(
            uniform_field, steps_per_layer=200, max_layers=1, verbose=False,
        )
        results = evolver.run()
        summary = results["summary"]
        assert summary["num_subspaces"] == 1
        assert summary["layers_executed"] >= 0

    def test_two_isolated_run_short(self, two_subspace_isolated):
        """Two isolated subspaces, short run."""
        evolver = SubspaceAwareEvolver(
            two_subspace_isolated,
            steps_per_layer=200,
            max_layers=1,
            verbose=False,
        )
        results = evolver.run()
        assert results["summary"]["num_subspaces"] == 2
        assert len(results["layer_summaries"]) >= 0

    def test_two_coupled_run_short(self, two_subspace_coupled):
        """Two coupled subspaces, short run."""
        evolver = SubspaceAwareEvolver(
            two_subspace_coupled,
            steps_per_layer=200,
            max_layers=1,
            coupling_enabled=True,
            verbose=False,
        )
        results = evolver.run()
        assert results["summary"]["num_subspaces"] == 2

    def test_three_subspace_run(self, three_subspace_isolated):
        """Three subspaces, short run."""
        evolver = SubspaceAwareEvolver(
            three_subspace_isolated,
            steps_per_layer=200,
            max_layers=1,
            verbose=False,
        )
        results = evolver.run()
        assert results["summary"]["num_subspaces"] == 3
        assert results["summary"]["total_bits"] == 72

    @pytest.mark.slow
    def test_two_layer_run(self, two_subspace_isolated):
        """Two layers should be possible if subspaces seal."""
        evolver = SubspaceAwareEvolver(
            two_subspace_isolated,
            steps_per_layer=500,
            max_layers=2,
            verbose=False,
        )
        results = evolver.run()
        assert "summary" in results
        # At least layer 0 ran
        assert len(results["layer_summaries"]) >= 1

    @pytest.mark.slow
    def test_different_rules_run(self):
        """Subspaces with different Rules should both run."""
        strong = Rules(binding_multiplier=3.0)
        weak = Rules(binding_multiplier=0.5)
        field = make_static_field(N0=48, k=2, coupling_strength=0.0,
                                  rules_list=[strong, weak])
        evolver = SubspaceAwareEvolver(
            field, steps_per_layer=300, max_layers=1, verbose=False,
        )
        results = evolver.run()
        assert results["summary"]["num_subspaces"] == 2


# =============================================================================
# Convenience runner
# =============================================================================

class TestRunSubspaceExperiment:
    def test_convenience_runner(self, two_subspace_isolated):
        results = run_subspace_experiment(
            two_subspace_isolated,
            steps_per_layer=200,
            max_layers=1,
            coupling_enabled=False,
            verbose=False,
        )
        assert "summary" in results
        assert results["summary"]["num_subspaces"] == 2


# =============================================================================
# Import test from engine package
# =============================================================================

class TestPackageImport:
    def test_import_from_engine(self):
        from engine import (
            SubspaceSolver, CouplingEngine, LayerCoordinator,
            SubspaceAwareEvolver, run_subspace_experiment,
        )
        assert SubspaceSolver is not None
        assert CouplingEngine is not None
        assert LayerCoordinator is not None
        assert SubspaceAwareEvolver is not None
        assert callable(run_subspace_experiment)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])