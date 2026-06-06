"""
Phase 11 P3: SubspaceField → HierarchicalEvolver Engine Integration — subspace_evolver.py

Integrates SubspaceField (data structure from P1) with SpatialLongRangeEvolver
(P1 runtime) to enable multi-subspace evolution with controlled coupling.

Architecture (Multi-Evolver):
  SubspaceAwareEvolver
  ├── SubspaceField          # from subspace_field.py (bit assignment + rules + topology)
  ├── SubspaceSolver[]       # k per-subspace evolver state wrappers
  ├── CouplingEngine         # bias injection for cross-subspace coupling
  ├── LayerCoordinator       # seal/next-layer coordination
  └── Metrics                # per-subspace + cross-subspace metrics

Design doc: docs/phase11_p3_engine_integration_design.md

Usage:
    from engine.subspace_field import make_static_field
    from engine.subspace_evolver import SubspaceAwareEvolver

    field = make_static_field(N0=72, k=2, coupling_strength=0.3)
    evolver = SubspaceAwareEvolver(field, steps_per_layer=2000, max_layers=2)
    results = evolver.run()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

import torch

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
from engine.subspace_field import (
    SubspaceField, SubspaceSpec, Rules,
    CouplingTopology, CouplingDirection,
)


# =============================================================================
# SubspaceSolver: per-subspace evolver state wrapper
# =============================================================================

@dataclass
class SubspaceSolver:
    """Wraps the state and metadata for one subspace's evolver.

    This is a lightweight state container. The actual evolution is done
    by SpatialLongRangeEvolver.run(), and results are written back here.
    """
    name: str                        # subspace name, e.g. "S0", "S1"
    subspace: SubspaceSpec           # bit assignment + rules
    N: int                           # number of bits in this subspace
    device: str = "cpu"
    current_layer: int = 0
    is_sealed: bool = False
    has_ever_sealed: bool = False
    step_count: int = 0
    hamming_weight: float = 0.0
    final_state: Optional[torch.Tensor] = None
    layer_result: Optional[Dict] = None
    evolver: Optional[SpatialLongRangeEvolver] = None

    def get_summary(self) -> Dict:
        return {
            "name": self.name,
            "N": self.N,
            "layer": self.current_layer,
            "sealed": self.is_sealed,
            "ever_sealed": self.has_ever_sealed,
            "hamming_weight": self.hamming_weight,
            "step_count": self.step_count,
            "subspace_rules": {
                "binding_multiplier": self.subspace.rules.binding_multiplier,
                "direction_bias": self.subspace.rules.direction_bias,
                "conservation_tightness": self.subspace.rules.conservation_tightness,
                "seal_threshold_multiplier": self.subspace.rules.seal_threshold_multiplier,
            },
        }


# =============================================================================
# CouplingEngine: cross-subspace bias injection via step_callback
# =============================================================================

class CouplingEngine:
    """Applies cross-subspace coupling at each sample interval.

    Mechanism: During a subspace's evolution, the step_callback is called
    every sample_interval steps. At that point, CouplingEngine injects
    a bias derived from other subspaces' direction fields into this
    subspace's binding_strength diagonal.

    This creates a slow modulation: coupling influences accumulate across
    sample intervals rather than every single step. For P3 this is
    sufficient — coupling is a meta-parameter that shifts the effective
    dynamics, not a per-step fine-tuning.
    """

    def __init__(self, field: SubspaceField, coupling_scale: float = 0.1):
        self.field = field
        self.coupling_scale = coupling_scale
        self._step_counter: Dict[str, int] = {}

    def make_callback(
        self,
        solver_name: str,
        all_solvers: Dict[str, SubspaceSolver],
    ) -> Callable:
        """Create a step_callback for a subspace that applies coupling.

        Returns a function with signature:
            callback(step, state, snapshot, constraints) -> None

        This callback is passed to SpatialLongRangeEvolver.run().
        """
        if self.field.is_isolated():
            return lambda *args, **kwargs: None  # no-op

        def _coupling_callback(
            step: int,
            state: torch.Tensor,
            snapshot: object,
            constraints: object,
        ) -> None:
            """Modify target subspace's constraints based on source signals.

            For each incoming connection to this subspace:
                bias += connection.strength * source_mean_direction * scale_factor
            The bias is applied to the diagonal of binding_strength.
            """
            for conn in self.field.connections:
                if conn.target != solver_name:
                    continue
                if conn.strength <= 0.0:
                    continue

                src_name = conn.source
                if src_name not in all_solvers:
                    continue

                src_solver = all_solvers[src_name]
                if src_solver.layer_result is None:
                    continue  # source hasn't run yet this layer

                # Read source's final direction mean
                src_dir = src_solver.layer_result.get("direction")
                if src_dir is None:
                    continue

                src_mean = float(src_dir.to(dtype=torch.float32).mean().item())
                # Normalize to [-1, 1] and scale
                # coupling_scale: configurable (default 0.1 for backward compat;
                #   increase to 1.0+ for stronger coupling, per exp_150 analysis)
                injection = conn.strength * (src_mean - 0.5) * 2.0 * self.coupling_scale

                # Apply to target's binding_strength OFF-DIAGONAL
                # (original code modified diagonal which is always 0 and never read)
                bs = constraints.binding_strength
                if bs is not None and bs.numel() > 0:
                    # Add injection uniformly to ALL elements, then zero diagonal
                    bs.add_(injection)
                    bs.fill_diagonal_(0)

        return _coupling_callback

    @staticmethod
    def compute_coupling_metrics(
        solvers: Dict[str, SubspaceSolver],
        field: SubspaceField,
    ) -> Dict:
        """Compute cross-subspace coupling metrics for diagnostics.

        Returns per-connection hamming distance correlations.
        """
        metrics = {}
        for conn in field.connections:
            src, tgt = conn.source, conn.target
            if src in solvers and tgt in solvers:
                key = f"{src}→{tgt}"
                s_src = solvers[src]
                s_tgt = solvers[tgt]
                metrics[key] = {
                    "strength": conn.strength,
                    "w_src": s_src.hamming_weight,
                    "w_tgt": s_tgt.hamming_weight,
                    "w_diff": abs(s_src.hamming_weight - s_tgt.hamming_weight),
                }
        return metrics


# =============================================================================
# LayerCoordinator: seal/next-layer coordination
# =============================================================================

class LayerCoordinator:
    """Coordinates per-subspace sealing and layer progression.

    Strategies:
        ALL_SEALED:      All subspaces must seal before advancing (conservative)
        MAJORITY_SEALED: Advance when >50% of non-empty subspaces sealed (default)
        INDEPENDENT:     Each subspace progresses independently (maximum freedom)

    For P3 exploration, MAJORITY_SEALED is the recommended default.
    """

    ALL_SEALED = "all_sealed"
    MAJORITY_SEALED = "majority_sealed"
    INDEPENDENT = "independent"

    def __init__(self, strategy: str = MAJORITY_SEALED,
                 step_timeout: int = 10000):
        assert strategy in (self.ALL_SEALED, self.MAJORITY_SEALED,
                           self.INDEPENDENT), f"Unknown strategy: {strategy}"
        self.strategy = strategy
        self.step_timeout = step_timeout

    def should_advance(self, solvers: Dict[str, SubspaceSolver],
                       max_layers: int) -> Tuple[bool, Optional[int]]:
        """Check if the system should advance to the next layer.

        Returns:
            (should_advance, next_layer_id)
        """
        if self.strategy == self.ALL_SEALED:
            all_sealed = all(s.is_sealed for s in solvers.values())
            if all_sealed:
                next_layer = max(s.current_layer for s in solvers.values()) + 1
                if next_layer < max_layers:
                    return True, next_layer
        elif self.strategy == self.MAJORITY_SEALED:
            total = len(solvers)
            sealed_count = sum(1 for s in solvers.values() if s.is_sealed)
            if sealed_count > total / 2:
                next_layer = max(s.current_layer for s in solvers.values()) + 1
                if next_layer < max_layers:
                    return True, next_layer
        elif self.strategy == self.INDEPENDENT:
            for s in solvers.values():
                if s.is_sealed and s.current_layer + 1 < max_layers:
                    return True, s.current_layer + 1

        return False, None

    def all_sealed(self, solvers: Dict[str, SubspaceSolver]) -> bool:
        """Quick check: are all subspaces sealed?"""
        return all(s.is_sealed for s in solvers.values())


# =============================================================================
# SubspaceAwareEvolver: top-level orchestrator
# =============================================================================

class SubspaceAwareEvolver:
    """Top-level orchestrator for multi-subspace evolution.

    Manages k independent SpatialLongRangeEvolver instances (one per subspace),
    applies cross-subspace coupling via step callbacks, and coordinates
    layer progression.

    Each layer:
      1. For each subspace: create SpatialLongRangeEvolver, apply Rules scaling
      2. Run each subspace's evolution (full steps_per_layer or until sealed)
      3. Apply coupling between subspace runs (via callback on subsequent runs)
      4. Check coordination condition; if met, advance to next layer
    """

    def __init__(
        self,
        subspace_field: SubspaceField,
        steps_per_layer: int = 5000,
        sample_interval: int = 500,
        max_layers: int = 3,
        device: str = "cpu",
        partial_sealing: bool = False,
        coupling_enabled: bool = True,
        coordination_strategy: str = LayerCoordinator.MAJORITY_SEALED,
        verbose: bool = True,
    ):
        """
        Args:
            subspace_field: SubspaceField with subspaces, rules, and coupling topology
            steps_per_layer: Maximum steps per layer per subspace
            sample_interval: Interval for metric snapshots and coupling injection
            max_layers: Maximum hierarchical layers
            device: Torch device
            partial_sealing: Enable B7 partial sealing
            coupling_enabled: If False, disable all cross-subspace coupling
            coordination_strategy: LayerCoordinator strategy
            verbose: Print progress
        """
        self.field = subspace_field
        self.steps_per_layer = steps_per_layer
        self.sample_interval = sample_interval
        self.max_layers = max_layers
        self.device = device
        self.partial_sealing = partial_sealing
        self.coupling_enabled = coupling_enabled
        self.verbose = verbose

        # coupling_scale: 0.1 = original (weak), 1.0 = stronger (per exp_150 finding)
        self.coupling_engine = CouplingEngine(subspace_field,
                                                 coupling_scale=1.0)
        self.coordinator = LayerCoordinator(strategy=coordination_strategy,
                                             step_timeout=steps_per_layer)

        # Runtime state
        self.solvers: Dict[str, SubspaceSolver] = {}
        self.snapshots: List[Dict] = []
        self.layer_summaries: List[Dict] = []

    # ── Per-Subspace Evolver Creation ──────────────────────────

    def _create_evolver(self, name: str, N_sub: int,
                        layer_id: int) -> SpatialLongRangeEvolver:
        """Create a SpatialLongRangeEvolver for one subspace.

        Sets up the evolver with proper hierarchy/lateral bit ratio
        (default N//3 hierarchy bits) and rules-scaled constraints.
        """
        evolver = SpatialLongRangeEvolver(
            N=N_sub,
            total_steps=self.steps_per_layer,
            sample_interval=self.sample_interval,
            device=self.device,
            n_hierarchy_bits=None,  # default N//3 hierarchy bits
            L=1.0,
            partial_sealing=self.partial_sealing,
        )
        return evolver

    def _apply_rules(self, evolver: SpatialLongRangeEvolver,
                     rules: Rules) -> None:
        """Apply Rules scaling to an initialized evolver's constraints."""
        if rules == Rules.default():
            return  # no scaling needed

        if evolver.constraints is not None:
            bs = evolver.constraints.binding_strength
            if bs is not None and rules.binding_multiplier != 1.0:
                evolver.constraints.binding_strength = bs * rules.binding_multiplier

            d = evolver.constraints.direction
            if d is not None and rules.direction_bias != 0.5:
                evolver.constraints.direction = d * (rules.direction_bias * 2.0)

    # ── Layer Execution ─────────────────────────────────────────

    def _run_layer(self, layer_id: int) -> Dict[str, SubspaceSolver]:
        """Run one layer: evolve each subspace, apply coupling, return solvers.

        For each subspace:
          1. Create SpatialLongRangeEvolver with constraints
          2. Apply Rules scaling
          3. If coupling enabled and source data exists, create coupling callback
          4. Run evolver
          5. Extract final state and sealing status into SubspaceSolver

        Returns: {subspace_name: SubspaceSolver}
        """
        layer_solvers: Dict[str, SubspaceSolver] = {}

        for order, name in enumerate(self.field.space_names):
            spec = self.field.get_spec(name)
            N_sub = spec.size

            if N_sub < 3:
                if self.verbose:
                    print(f"  [WARN] Subspace {name}: N={N_sub} < 3, skipping")
                continue

            # Create evolver
            evolver = self._create_evolver(name, N_sub, layer_id)

            # Apply Rules scaling
            self._apply_rules(evolver, spec.rules)

            # Create coupling callback (only for non-first subspaces in coupled mode)
            coupling_callback = None
            if self.coupling_enabled and not self.field.is_isolated() and order > 0:
                # Only later subspaces receive coupling from earlier ones in this layer
                coupling_callback = self.coupling_engine.make_callback(
                    name, layer_solvers  # layer_solvers contains already-completed subspaces
                )

            # Run evolver
            if self.verbose:
                print(f"    Subspace {name}: N={N_sub}, "
                      f"rules=({spec.rules.binding_multiplier:.1f}, "
                      f"{spec.rules.direction_bias:.1f}), "
                      f"{'coupled' if coupling_callback else 'isolated'}")

            # Initial state: for layer 0, start from zeros; for deeper layers,
            # pass previous final state as initial state
            initial_state = None
            if layer_id > 0 and name in self.solvers:
                prev = self.solvers[name]
                if prev.final_state is not None and prev.final_state.numel() == N_sub:
                    initial_state = prev.final_state

            result = evolver.run(
                verbose=False,
                step_callback=coupling_callback,
            )

            # Extract state
            final_state = result["final_state"] if "final_state" in result else None
            is_sealed = result.get("sealed", False)
            hw = result["hamming_weight_history"][-1] if result.get("hamming_weight_history") else 0

            # Create solver
            solver = SubspaceSolver(
                name=name,
                subspace=spec,
                N=N_sub,
                device=self.device,
                current_layer=layer_id,
                is_sealed=is_sealed,
                has_ever_sealed=is_sealed or (
                    self.solvers[name].has_ever_sealed
                    if name in self.solvers
                    else is_sealed
                ),
                step_count=result.get("total_steps", 0),
                hamming_weight=float(hw),
                final_state=final_state,
                layer_result=result,
                evolver=evolver,
            )
            layer_solvers[name] = solver

        return layer_solvers

    # ── Main Run ────────────────────────────────────────────────

    def run(self, verbose: Optional[bool] = None) -> Dict:
        """Run the multi-subspace evolution.

        Layer loop:
          1. Run each subspace through one layer
          2. Check coordination condition
          3. If met, advance; otherwise stop

        Returns: Dict with full results, trajectories, and summary
        """
        if verbose is None:
            verbose = self.verbose
        self.verbose = verbose

        overall_start = time.time()
        self.snapshots = []
        self.layer_summaries = []
        self.solvers = {}  # reset for fresh run

        if verbose:
            print("=" * 70)
            print(f"SubspaceAwareEvolver: "
                  f"{self.field.num_subspaces} subspaces, "
                  f"{self.field.total_bits} total bits, "
                  f"{'coupled' if not self.field.is_isolated() else 'isolated'}")
            print(f"  Strategy: {self.coordinator.strategy}, "
                  f"max_layers={self.max_layers}")
            if not self.field.is_isolated():
                print(f"  Coupling connections:")
                for c in self.field.connections:
                    print(f"    {c.source} → {c.target} "
                          f"(strength={c.strength:.2f}, {c.direction.name})")
            print("=" * 70)

        layer_id = 0
        while layer_id < self.max_layers:
            if verbose:
                print(f"\n  --- Layer {layer_id} ---")

            layer_start = time.time()
            layer_solvers = self._run_layer(layer_id)
            layer_elapsed = time.time() - layer_start

            if not layer_solvers:
                if verbose:
                    print(f"  No solvers could be initialized, stopping")
                break

            # Update persistent solvers
            for name, solver in layer_solvers.items():
                self.solvers[name] = solver

            # Layer summary
            sealed_str = ", ".join(
                f"{n}: {'✓' if s.is_sealed else '✗'}"
                for n, s in layer_solvers.items()
            )
            layer_summary = {
                "layer_id": layer_id,
                "elapsed": layer_elapsed,
                "subspaces": {n: s.get_summary() for n, s in layer_solvers.items()},
                "coupling_metrics": (
                    CouplingEngine.compute_coupling_metrics(layer_solvers, self.field)
                    if not self.field.is_isolated()
                    else {}
                ),
            }
            self.layer_summaries.append(layer_summary)

            if verbose:
                print(f"  Layer {layer_id} done ({layer_elapsed:.1f}s): {sealed_str}")

            # Check coordination for next layer
            should_advance, next_layer = self.coordinator.should_advance(
                layer_solvers, self.max_layers
            )
            if not should_advance:
                if verbose:
                    print(f"  Coordination condition not met for next layer, stopping")
                break

            layer_id = next_layer

        overall_elapsed = time.time() - overall_start

        # Build final results
        results = self._build_results(layer_id, overall_elapsed)
        return results

    def _build_results(self, final_layer: int, elapsed: float) -> Dict:
        """Build the full results dictionary."""
        per_subspace = {}
        for name in self.field.space_names:
            solver = self.solvers.get(name)
            if solver is None:
                per_subspace[name] = {
                    "error": "not_initialized",
                    "layers": [ls["subspaces"].get(name, {})
                               for ls in self.layer_summaries],
                }
            else:
                layer_data = [ls["subspaces"].get(name, {})
                              for ls in self.layer_summaries]
                per_subspace[name] = {
                    "N": solver.N,
                    "layers": layer_data,
                    "final_sealed": solver.is_sealed,
                    "ever_sealed": solver.has_ever_sealed,
                    "final_hamming_weight": solver.hamming_weight,
                }

        l1_count = sum(
            1 for ps in per_subspace.values()
            if ps.get("ever_sealed", False)
        )

        summary = {
            "num_subspaces": self.field.num_subspaces,
            "total_bits": self.field.total_bits,
            "layers_executed": len(self.layer_summaries),
            "total_steps_per_layer": self.steps_per_layer,
            "max_layers": self.max_layers,
            "elapsed": elapsed,
            "elapsed_per_layer": [ls["elapsed"] for ls in self.layer_summaries],
            "subspaces": per_subspace,
            "l1_formed": l1_count,
            "l1_rate": l1_count / max(self.field.num_subspaces, 1),
            "coordination_strategy": self.coordinator.strategy,
            "coupling_enabled": self.coupling_enabled,
            "coupling_strength": (
                self.field._global_strength
                if hasattr(self.field, '_global_coupling') and self.field._global_coupling
                else None
            ),
        }

        return {
            "summary": summary,
            "layer_summaries": self.layer_summaries,
            "field": self.field,
            "config": {
                "num_subspaces": self.field.num_subspaces,
                "total_bits": self.field.total_bits,
                "steps_per_layer": self.steps_per_layer,
                "max_layers": self.max_layers,
                "coupling_enabled": self.coupling_enabled,
                "coordination_strategy": self.coordinator.strategy,
                "partial_sealing": self.partial_sealing,
            },
        }

    def print_results(self) -> None:
        """Print results summary."""
        s = self.layer_summaries[-1]["subspaces"] if self.layer_summaries else {}
        print("=" * 70)
        print("SubspaceAwareEvolver Results")
        print("=" * 70)
        print(f"  Subspaces: {self.field.num_subspaces}")
        print(f"  Total bits: {self.field.total_bits}")
        print(f"  Layers executed: {len(self.layer_summaries)}")
        print(f"  Coupling: {'ON' if self.coupling_enabled else 'OFF'}")
        print()
        for name in self.field.space_names:
            solver = self.solvers.get(name)
            if solver:
                print(f"  Subspace {name}: N={solver.N}, "
                      f"sealed={solver.is_sealed}, "
                      f"w={solver.hamming_weight:.0f}")
                print(f"    Rules: binding={solver.subspace.rules.binding_multiplier:.1f}, "
                      f"direction={solver.subspace.rules.direction_bias:.1f}")


# =============================================================================
# Convenience runner
# =============================================================================

def run_subspace_experiment(
    field: SubspaceField,
    steps_per_layer: int = 3000,
    max_layers: int = 2,
    coupling_enabled: bool = True,
    coordination_strategy: str = LayerCoordinator.MAJORITY_SEALED,
    verbose: bool = True,
    **kwargs,
) -> Dict:
    """Run a subspace evolution experiment with a single function call.

    Args:
        field: Pre-configured SubspaceField
        steps_per_layer: Steps per layer per subspace
        max_layers: Maximum hierarchy depth
        coupling_enabled: Enable cross-subspace coupling
        coordination_strategy: Layer advancement strategy
        verbose: Print progress
        **kwargs: Additional args passed to SubspaceAwareEvolver

    Returns:
        Full results dict from SubspaceAwareEvolver.run()
    """
    evolver = SubspaceAwareEvolver(
        subspace_field=field,
        steps_per_layer=steps_per_layer,
        max_layers=max_layers,
        coupling_enabled=coupling_enabled,
        coordination_strategy=coordination_strategy,
        verbose=verbose,
        **kwargs,
    )
    return evolver.run()