"""exp_152 Phase 11 P4: Fixed Coupling Mechanism (instrumented version)

Same as exp_152_phase11_p4_fixed_coupling.py but records seal_step per subspace.
"""

import sys, os, torch, numpy as np, time
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.subspace_field import (
    SubspaceField, SubspaceSpec, Rules,
    CouplingTopology, CouplingDirection, _CouplingConnection,
)
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
    from acl.axioms_v2 import AxiomConstraints

    if hasattr(AxiomConstraints, '_coupling_patched'):
        return

    _orig_init = AxiomConstraints.__init__
    _orig_get_allowed = AxiomConstraints.get_allowed_flips
    _orig_get_weights = AxiomConstraints.get_A8_weights

    def _patched_init(self, N, n_hierarchy_bits=None, device="cpu",
                      initial_state=None):
        _orig_init(self, N, n_hierarchy_bits, device, initial_state)
        self.coupling_bias = torch.zeros(N, device=device)
        self._coupling_patched = True

    def _patched_get_allowed(self, state):
        allowed = _orig_get_allowed(self, state)
        if not allowed or self.coupling_bias.abs().sum() < 1e-6:
            return allowed
        filtered = [i for i in allowed if self.coupling_bias[i].item() >= -0.5]
        return filtered if filtered else allowed

    def _patched_get_weights(self, state):
        weights = _orig_get_weights(self, state)
        if self.coupling_bias.abs().sum() < 1e-6:
            return weights
        w = weights.clone()
        for i in range(self.N):
            b = self.coupling_bias[i].item()
            if b > 0:
                w[i] = w[i] * (1.0 + b)
            elif b < 0:
                w[i] = w[i] * (1.0 - abs(b) * 0.5)
        return w

    AxiomConstraints.__init__ = _patched_init
    AxiomConstraints.get_allowed_flips = _patched_get_allowed
    AxiomConstraints.get_A8_weights = _patched_get_weights
    AxiomConstraints._coupling_patched = True


# =============================================================================
# Fixed CouplingEngine: writes direction bias
# =============================================================================

class FixedCouplingEngine:
    def __init__(self, field, coupling_scale=1.0):
        self.field = field
        self.coupling_scale = coupling_scale
        self.solver_states = {}

    def update_solver_states(self, solvers):
        self.solver_states.update(solvers)

    def make_callback(self, solver_name, all_solvers):
        if self.field.is_isolated():
            return lambda *args, **kwargs: None

        def _fixed_coupling_callback(step, state, snapshot, constraints):
            import torch as _torch
            all_states = {**self.solver_states, **all_solvers}
            for conn in self.field.connections:
                if conn.target != solver_name or conn.strength <= 0.0:
                    continue
                src_name = conn.source
                if src_name not in all_states:
                    continue
                src_solver = all_states[src_name]
                if src_solver.layer_result is None:
                    continue
                src_hw_norm = src_solver.hamming_weight / max(src_solver.N, 1)
                target_hw_norm = snapshot.w / max(snapshot.state.numel(), 1)
                bias_signal = conn.strength * (src_hw_norm - target_hw_norm)
                N_target = snapshot.state.numel()
                bias_tensor = _torch.full(
                    (N_target,),
                    float(bias_signal * self.coupling_scale),
                    device=constraints.coupling_bias.device,
                    dtype=constraints.coupling_bias.dtype,
                )
                bias_tensor.clamp_(-1.0, 1.0)
                constraints.coupling_bias.copy_(bias_tensor)
        return _fixed_coupling_callback


# =============================================================================
# Instrumented runner: captures A9 seal steps
# =============================================================================

def run_single_experiment_instrumented(
    coupling_strength,
    N0=40, N1=40, k=2,
    steps_per_layer=5000, max_layers=2,
    device="cpu", seed=42,
):
    """Like run_single_experiment     Returns dict with seal_step_S0, seal_step_S1, etc.
    """
    torch.manual_seed(seed)

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
    evolver.coupling_engine = FixedCouplingEngine(field, coupling_scale=1.0)

    _orig_run_layer = evolver._run_layer
    def _patched_run_layer(layer_id):
        evolver.coupling_engine.update_solver_states(evolver.solvers)
        return _orig_run_layer(layer_id)
    evolver._run_layer = _patched_run_layer

    # === MONKEY-PATCH: capture A9 seal steps ===
    # We patch SpatialLongRangeEvolver to record seal_step
    from engine.long_range_evolver_v2 import SpatialLongRangeEvolver
    seal_steps = {}  # solver_name -> step when A9 fired

    _orig_SRE_init = SpatialLongRangeEvolver.__init__
    def _patched_SRE_init(self, *a, **kw):
        _orig_SRE_init(self, *a, **kw)
        _orig_check = self.check_constraints
        def _patched_check(*a2, **kw2):
            result = _orig_check(*a2, **kw2)
            sr = self.layer_result
            if sr and sr.get('sealed') and self.name not in seal_steps:
                seal_steps[self.name] = sr.get('seal_step', -1)
            return result
        self.check_constraints = _patched_check
    SpatialLongRangeEvolver.__init__ = _patched_SRE_init

    result = evolver.run(verbose=False)

    # Restore
    SpatialLongRangeEvolver.__init__ = _orig_SRE_init

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
        "S0_seal_step": seal_steps.get("S0", -1),
        "S1_seal_step": seal_steps.get("S1", -1),
        "S0_N": N0,
        "S1_N": N1,
    }


def run_sweep(n_runs=5, coupling_levels=None, N0=40, N1=40,
              steps_per_layer=5000, max_layers=2, device="cpu"):
    if coupling_levels is None:
        coupling_levels = [0.0, 0.3, 0.6, 1.0, 2.0, 5.0]

    print("=" * 70)
    print("Phase 11 P4: Fixed Coupling Mechanism — exp_152 (instrumented)")
    print("=" * 70)
    print(f"  N0={N0}, N1={N1}, k=2")
    print(f"  coupling_levels: {coupling_levels}")
    print(f"  runs per level: {n_runs}")
    print()

    patch_axioms_with_coupling_bias()

    results = []
    for strength in coupling_levels:
        print(f"--- coupling_strength = {strength} ---")
        level_results = []
        for run_i in range(n_runs):
            r = run_single_experiment_instrumented(
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
                  f"w0={r['S0_final_w']:.0f} w1={r['S1_final_w']:.0f}  "
                  f"step0={r.get('S0_seal_step','?')} step1={r.get('S1_seal_step','?')}")
        results.append({"strength": strength, "runs": level_results})

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY (with seal steps)")
    print("=" * 70)
    print(f"{'Strength':>8} | {'S1_L1':>6} | {'avg w1':>7} | {'avg step1':>10}")
    print("-" * 50)
    for level in results:
        s = level["strength"]
        runs = level["runs"]
        s1_rate = sum(1 for r in runs if r["S1_L1"]) / len(runs)
        avg_w1 = np.mean([r["S1_final_w"] for r in runs])
        steps1 = [r.get("S1_seal_step", -1) for r in runs if r.get("S1_seal_step", -1) > 0]
        avg_step1 = np.mean(steps1) if steps1 else -1
        print(f"{s:>8.1f} | {s1_rate:>6.2f} | {avg_w1:>7.1f} | {avg_step1:>10.1f}")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"exp_152_inst_{timestamp}.npy")
    np.save(result_file, results, allow_pickle=True)
    print(f"\nResults saved: {result_file}")

    return results


if __name__ == "__main__":
    run_sweep(
        n_runs=5,
        coupling_levels=[0.0, 0.3, 0.6, 1.0, 2.0, 5.0],
        N0=40, N1=40,
        steps_per_layer=500,
        max_layers=1,
        device="cpu",
    )
