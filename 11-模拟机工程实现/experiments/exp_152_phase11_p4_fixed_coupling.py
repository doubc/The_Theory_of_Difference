"""
Phase 11 P4: Fixed Coupling Mechanism — exp_152

========================================================================
ROOT CAUSE ANALYSIS (from exp_150 + exp_151 failure)
========================================================================

Bug 1: Coupling modifies `binding_strength` off-diagonal.
        `binding_strength` is ONLY read by `get_A1_prime_candidates()` (lateral pairing).
        It is NOT read by source injection, sink absorption, or flip selection.
        → No causal pathway from coupling to sealing behavior.

Bug 2: `injection = strength * (src_mean - 0.5) * 2.0 * coupling_scale`
        Before L1 forms, src_mean ≈ 0.5 → injection ≈ 0.
        → Coupling is inert until BOTH subspaces have sealed (chicken-egg).

Bug 3 (exp_151 design): S1 has N=20, min_active_bits=12 → stalls at w=7-12.
        Even with perfect coupling, S1 can never reach sealing threshold.

========================================================================
FIX (P4)
========================================================================

Coupling should modify `constraints.direction` bias — the DAG direction field
that directly controls which flips are allowed (A6) and weights flips (A8).

Mechanism:
  - Add `coupling_bias: torch.Tensor` field to `AxiomConstraints`
  - `CouplingEngine` callback writes bias into `constraints.coupling_bias`
  - `get_allowed_flips()` and `get_A8_weights()` read `coupling_bias`
    to prefer flipping bits whose direction aligns with source subspace signal

Specifically:
  - coupling_bias[i] > 0 → bit i is biased toward 0→1 (source is "energized")
  - coupling_bias[i] < 0 → bit i is biased toward 1→0 (source is "saturated")
  - Bias is injected at sample_interval, persists until next callback

For exp_152: use bidirectional symmetric coupling (k=2, N0=N1=40),
coupling_strength sweep, with the FIXED mechanism.

========================================================================
EXPERIMENT DESIGN
========================================================================

- k=2 subspaces, N0=N1=40 bits each (both large enough to seal)
- Symmetric bidirectional coupling: S0↔S1, strength in [0.0, 0.3, 0.6, 1.0, 2.0, 5.0]
- Coupling modifies `direction` bias (new mechanism)
- Measure: L1 formation rate per subspace, correlation of w(t) trajectories,
  time-to-seal per subspace

Hypothesis:
  - With fixed coupling, higher strength → more correlated w(t) between S0 and S1
  - Sufficiently high strength → S1 seals FASTER (energized by S0's signal)
  - Both subspaces should achieve L1 (N=40 >> min_active_bits=13)

"""

import sys
import os
import torch
import numpy as np
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.subspace_field import (
    SubspaceField, SubspaceSpec, Rules,
    CouplingTopology, CouplingDirection, _CouplingConnection,
)
# Alias for readability
CouplingConnection = _CouplingConnection
from engine.subspace_evolver import (
    SubspaceAwareEvolver, LayerCoordinator, CouplingEngine
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'results', 'phase11_p4')
os.makedirs(RESULTS_DIR, exist_ok=True)


# =============================================================================
# Patch: Add coupling_bias field to AxiomConstraints at runtime
# =============================================================================

def patch_axioms_with_coupling_bias():
    """Monkey-patch AxiomConstraints to support coupling_bias.

    Adds:
      - self.coupling_bias: Tensor(N), initialized to 0
      - modified get_allowed_flips() to prefer bits where coupling_bias aligns
      - modified get_A8_weights() to incorporate coupling_bias

    This avoids modifying axioms_v2.py directly (minimizes regression risk).
    """
    from acl.axioms_v2 import AxiomConstraints

    # Only patch once
    if hasattr(AxiomConstraints, '_coupling_patched'):
        return

    _orig_init = AxiomConstraints.__init__
    _orig_get_allowed = AxiomConstraints.get_allowed_flips
    _orig_get_weights = AxiomConstraints.get_A8_weights

    def _patched_init(self, N, n_hierarchy_bits=None, device="cpu",
                      initial_state=None):
        _orig_init(self, N, n_hierarchy_bits, device, initial_state)
        # coupling_bias: (N,) tensor, range [-1, +1]
        # > 0 → bias toward 0→1 (energized by source)
        # < 0 → bias toward 1→0 (source is saturated, absorb)
        self.coupling_bias = torch.zeros(N, device=device)
        self._coupling_patched = True

    def _patched_get_allowed(self, state):
        """Allowed flips with coupling_bias modulation.

        coupling_bias[i] > 0: bit i gets priority for 0→1 flip
        coupling_bias[i] < 0: bit i is deprioritized for 0→1 flip
        (A1 still enforces 0→1 only; coupling_bias modulates ranking,
         not the binary allow/disallow)
        """
        allowed = _orig_get_allowed(self, state)
        if not allowed or self.coupling_bias.abs().sum() < 1e-6:
            return allowed
        # Filter: if coupling_bias strongly negative, remove from allowed
        # (source says "don't inject here")
        filtered = []
        for i in allowed:
            if self.coupling_bias[i].item() < -0.5:
                continue  # source strongly opposes injection here
            filtered.append(i)
        return filtered if filtered else allowed  # fallback to original if all filtered

    def _patched_get_weights(self, state):
        """A8 weights modulated by coupling_bias."""
        weights = _orig_get_weights(self, state)
        if self.coupling_bias.abs().sum() < 1e-6:
            return weights
        w = weights.clone()
        # Debug: uncomment to verify
        # bias_max = self.coupling_bias.abs().max().item()
        # if bias_max > 1e-3:
        #     print(f"        [WEIGHTS] coupling_bias active, max_abs={bias_max:.4f}")
        for i in range(self.N):
            b = self.coupling_bias[i].item()
            if b > 0:
                # Source energized → boost injection weight
                w[i] = w[i] * (1.0 + b)
            elif b < 0:
                # Source saturated → reduce injection weight
                w[i] = w[i] * (1.0 - abs(b) * 0.5)
        return w

    AxiomConstraints.__init__ = _patched_init
    AxiomConstraints.get_allowed_flips = _patched_get_allowed
    AxiomConstraints.get_A8_weights = _patched_get_weights
    AxiomConstraints._coupling_patched = True
    print("[PATCH] AxiomConstraints patched with coupling_bias support")


# =============================================================================
# Fixed CouplingEngine: writes direction bias instead of binding_strength
# =============================================================================

class FixedCouplingEngine:
    """Fixed coupling engine that writes direction bias instead of binding_strength.

    Key fix: stores solver_states (all solvers from previous + current layer)
    so the callback can read source subspace results regardless of evaluation order.
    """

    def __init__(self, field: SubspaceField, coupling_scale: float = 1.0):
        self.field = field
        self.coupling_scale = coupling_scale
        # solver_states: dict[str, SubspaceSolver] — updated before each layer
        self.solver_states: dict = {}

    def update_solver_states(self, solvers: dict):
        """Call before each layer to update available solver states."""
        self.solver_states.update(solvers)

    def make_callback(self, solver_name: str, all_solvers: dict) -> callable:
        """Create callback that writes coupling_bias into target's constraints.

        Uses self.solver_states (not just all_solvers) to find source results.
        self.solver_states is updated by _run_layer before calling this.
        """
        if self.field.is_isolated():
            return lambda *args, **kwargs: None

        def _fixed_coupling_callback(step, state, snapshot, constraints):
            """Write coupling_bias into constraints based on source signals."""
            import torch as _torch
            # Use solver_states (has previous layer results) as fallback
            all_states = {**self.solver_states, **all_solvers}

            for conn in self.field.connections:
                if conn.target != solver_name:
                    continue
                if conn.strength <= 0.0:
                    continue

                src_name = conn.source
                if src_name not in all_states:
                    continue

                src_solver = all_states[src_name]
                if src_solver.layer_result is None:
                    continue

                # Signal: source's normalized hamming weight
                src_hw_norm = src_solver.hamming_weight / max(src_solver.N, 1)
                target_hw_norm = snapshot.w / max(snapshot.state.numel(), 1)

                # Coupling bias: if source is more active, energize target
                bias_signal = conn.strength * (src_hw_norm - target_hw_norm)

                # Write into coupling_bias for ALL bits in target
                N_target = snapshot.state.numel()
                bias_tensor = _torch.full(
                    (N_target,),
                    float(bias_signal * self.coupling_scale),
                    device=constraints.coupling_bias.device,
                    dtype=constraints.coupling_bias.dtype,
                )
                bias_tensor.clamp_(-1.0, 1.0)
                constraints.coupling_bias.copy_(bias_tensor)
                # Debug: uncomment to verify coupling is active
                # print(f"        [COUPLING] {src_name}->{solver_name} "
                #       f"bias_signal={bias_signal:.4f}")

        return _fixed_coupling_callback


# =============================================================================
# Experiment runner
# =============================================================================

def make_field(N0: int, N1: int, coupling_strength: float):
    """Create a SubspaceField with two subspaces and optional coupling."""
    from engine.subspace_field import allocate_static
    indices = allocate_static(N0 + N1, k=2)
    field = SubspaceField(
        subspaces={
            "S0": SubspaceSpec(indices[0], Rules.default()),
            "S1": SubspaceSpec(indices[1], Rules.default()),
        },
        coupling_strength=coupling_strength,
        coupling_direction=CouplingDirection.BIDIRECTIONAL,
        global_coupling=(coupling_strength > 0.0),
    )
    return field


def run_single_experiment(
    coupling_strength: float,
    N0: int = 40,
    N1: int = 40,
    k: int = 2,
    steps_per_layer: int = 5000,
    max_layers: int = 2,
    device: str = "cpu",
    seed: int = 42,
) -> dict:
    """Run one experiment with given coupling_strength.

    Returns dict with results for analysis.
    """
    torch.manual_seed(seed)

    # Build SubspaceField with symmetric bidirectional coupling
    field = make_field(N0, N1, coupling_strength)

    # Use FixedCouplingEngine
    evolver = SubspaceAwareEvolver(
        subspace_field=field,
        steps_per_layer=steps_per_layer,
        sample_interval=500,
        max_layers=max_layers,
        device=device,
        partial_sealing=False,
        coupling_enabled=(coupling_strength > 0),
        coordination_strategy=LayerCoordinator.INDEPENDENT,
        verbose=False,
    )

    # Swap in FixedCouplingEngine
    evolver.coupling_engine = FixedCouplingEngine(field, coupling_scale=1.0)

    # Monkey-patch: update solver_states before each layer
    _orig_run_layer = evolver._run_layer
    def _patched_run_layer(layer_id):
        # Update solver_states so callbacks can read previous-layer results
        evolver.coupling_engine.update_solver_states(evolver.solvers)
        return _orig_run_layer(layer_id)
    evolver._run_layer = _patched_run_layer

    result = evolver.run(verbose=False)

    # Extract per-subspace results
    summary = result.get("summary", {})
    per_subspace = summary["subspaces"]

    s0 = per_subspace.get("S0", {})
    s1 = per_subspace.get("S1", {})

    return {
        "coupling_strength": coupling_strength,
        "S0_L1": s0.get("ever_sealed", False),
        "S1_L1": s1.get("ever_sealed", False),
        "S0_final_w": s0.get("final_hamming_weight", 0),
        "S1_final_w": s1.get("final_hamming_weight", 0),
        "S0_N": N0,
        "S1_N": N1,
        "l1_rate": summary.get("l1_rate", 0.0),
        "layers_executed": summary.get("layers_executed", 0),
    }


def run_sweep(
    n_runs: int = 5,
    coupling_levels: list = None,
    N0: int = 40,
    N1: int = 40,
    steps_per_layer: int = 5000,
    max_layers: int = 2,
    device: str = "cpu",
):
    """Sweep over coupling levels, multiple runs per level."""
    if coupling_levels is None:
        coupling_levels = [0.0, 0.3, 0.6, 1.0, 2.0, 5.0]

    print("=" * 70)
    print("Phase 11 P4: Fixed Coupling Mechanism — exp_152")
    print("=" * 70)
    print(f"  N0={N0}, N1={N1}, k=2")
    print(f"  coupling_levels: {coupling_levels}")
    print(f"  runs per level: {n_runs}")
    print(f"  device: {device}")
    print()

    patch_axioms_with_coupling_bias()

    results = []
    for strength in coupling_levels:
        print(f"--- coupling_strength = {strength} ---")
        level_results = []
        for run_i in range(n_runs):
            r = run_single_experiment(
                coupling_strength=strength,
                N0=N0, N1=N1,
                steps_per_layer=steps_per_layer,
                max_layers=max_layers,
                device=device,
                seed=42 + int(strength * 100) + run_i * 7,
            )
            level_results.append(r)
            s0_l1 = "Y" if r["S0_L1"] else "N"
            s1_l1 = "Y" if r["S1_L1"] else "N"
            print(f"  run {run_i}: S0_L1={s0_l1} S1_L1={s1_l1}  "
                  f"w0={r['S0_final_w']:.0f} w1={r['S1_final_w']:.0f}")
        results.append({
            "strength": strength,
            "runs": level_results,
        })

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Strength':>8} | {'S0 L1 rate':>10} | {'S1 L1 rate':>10} | {'avg w0':>8} | {'avg w1':>8}")
    print("-" * 60)
    for level in results:
        s = level["strength"]
        runs = level["runs"]
        s0_rate = sum(1 for r in runs if r["S0_L1"]) / len(runs)
        s1_rate = sum(1 for r in runs if r["S1_L1"]) / len(runs)
        avg_w0 = np.mean([r["S0_final_w"] for r in runs])
        avg_w1 = np.mean([r["S1_final_w"] for r in runs])
        print(f"{s:>8.1f} | {s0_rate:>10.2f} | {s1_rate:>10.2f} | {avg_w0:>8.1f} | {avg_w1:>8.1f}")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"exp_152_{timestamp}.npy")
    summary_file = os.path.join(RESULTS_DIR, f"exp_152_{timestamp}_summary.txt")

    np.save(result_file, results, allow_pickle=True)
    with open(summary_file, 'w') as f:
        f.write(f"exp_152 Phase 11 P4 Fixed Coupling\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"N0={N0}, N1={N1}, k=2\n")
        f.write(f"n_runs={n_runs}\n")
        f.write(f"coupling_levels={coupling_levels}\n")
        f.write("\n")
        for level in results:
            f.write(f"strength={level['strength']}\n")
            for r in level["runs"]:
                f.write(f"  {r}\n")

    print()
    print(f"Results saved: {result_file}")
    print(f"Summary saved: {summary_file}")

    return results


if __name__ == "__main__":
    run_sweep(
        n_runs=5,
        coupling_levels=[0.0, 0.3, 0.6, 1.0, 2.0, 5.0],
        N0=40,
        N1=40,
        steps_per_layer=500,
        max_layers=1,
        device="cpu",
    )
