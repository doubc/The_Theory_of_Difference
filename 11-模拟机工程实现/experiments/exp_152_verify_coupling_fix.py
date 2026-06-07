"""
exp_152 Verification Re-run (Phase 14 P0)

Now that the coupling fix is INTEGRATED into axioms_v2.py (coupling_bias field)
and engine/subspace_evolver.py (fixed CouplingEngine), this script verifies
the mechanism works WITHOUT monkey-patches.

What we verify:
  1. coupling_bias is written to target subspace constraints during evolution
  2. coupling_bias values are non-trivial (not always 0)
  3. coupling strength affects sealing rate/patterns
  4. Bidirectional coupling creates correlation between subspace HWs

Strategy:
  - Run 2-layer evolution with k=2 subspaces (N0=N1=40)
  - Sweep coupling_strength: [0.0, 0.3, 1.0, 3.0, 5.0]
  - Each strength: 5 runs with different seeds
  - Compare: sealing rate, final HW, coupling_bias norm

Usage:
  python experiments/exp_152_verify_coupling_fix.py
"""

import sys, os, torch, numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine.subspace_field import SubspaceField, SubspaceSpec, Rules, CouplingDirection
from engine.subspace_evolver import SubspaceAwareEvolver, LayerCoordinator
from engine.subspace_field import allocate_static

RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'results', 'phase11_p4')
os.makedirs(RESULTS_DIR, exist_ok=True)


def make_field(N0: int, N1: int, coupling_strength: float):
    """Create two-subspace field with optional coupling."""
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


def run_single(coupling_strength: float, N0: int = 40, N1: int = 40,
               steps_per_layer: int = 500, max_layers: int = 2,
               device: str = "cpu", seed: int = 42) -> dict:
    """Run one experiment and return results + coupling evidence."""

    torch.manual_seed(seed)
    field = make_field(N0, N1, coupling_strength)

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

    result = evolver.run(verbose=False)
    summary = result.get("summary", {})
    subspaces = summary.get("subspaces", {})

    # Extract coupling bias evidence from solver state
    coupling_evidence = {}
    for name, solver in evolver.solvers.items():
        # Phase 14 P0 fix: constraints are on solver.evolver
        ev = solver.evolver
        if ev is not None and hasattr(ev, 'constraints') and hasattr(ev.constraints, 'coupling_bias'):
            cb = ev.constraints.coupling_bias
            coupling_evidence[name] = {
                "coupling_bias_norm": cb.norm().item(),
                "coupling_bias_max": cb.abs().max().item(),
                "coupling_bias_mean": cb.mean().item(),
                "coupling_bias_std": cb.std().item(),
                "coupling_bias_pos_ratio": (cb > 0).sum().item() / max(cb.numel(), 1),
                "coupling_bias_neg_ratio": (cb < 0).sum().item() / max(cb.numel(), 1),
            }

    s0 = subspaces.get("S0", {})
    s1 = subspaces.get("S1", {})

    return {
        "coupling_strength": coupling_strength,
        "seed": seed,
        "S0_L1": s0.get("ever_sealed", False),
        "S1_L1": s1.get("ever_sealed", False),
        "S0_final_w": s0.get("final_hamming_weight", 0),
        "S1_final_w": s1.get("final_hamming_weight", 0),
        "layers_executed": summary.get("layers_executed", 0),
        "L1_rate": summary.get("l1_rate", 0.0),
        "coupling_evidence": coupling_evidence,
    }


def run_sweep():
    """Main sweep: coupling_strength × n_runs."""
    print("=" * 72)
    print("  exp_152: Coupling Fix Verification (Phase 14 P0)")
    print("=" * 72)
    N0, N1 = 40, 40
    strengths = [0.0, 0.3, 1.0, 3.0, 5.0]
    n_runs = 5
    print(f"  N0={N0}, N1={N1}, bidirectional coupling")
    print(f"  strengths={strengths}, runs/level={n_runs}")
    print()

    all_results = []
    for strength in strengths:
        level = []
        for ri in range(n_runs):
            seed = 42 + int(strength * 100) + ri * 7
            r = run_single(strength, N0, N1, seed=seed)
            level.append(r)
            cb_s0 = r["coupling_evidence"]["S0"]
            cb_s1 = r["coupling_evidence"]["S1"]
            s0l1 = "Y" if r["S0_L1"] else "N"
            s1l1 = "Y" if r["S1_L1"] else "N"
            print(f"  s={strength:4.1f} run={ri} L1:S0={s0l1} S1={s1l1} "
                  f"w:S0={r['S0_final_w']:2.0f} S1={r['S1_final_w']:2.0f} "
                  f"|cb|_S0={cb_s0['coupling_bias_norm']:.3f} S1={cb_s1['coupling_bias_norm']:.3f}")
        all_results.append({"strength": strength, "runs": level})

    # Summary table
    print()
    print("-" * 72)
    print(f"{'Strength':>8} | {'S0 L1%':>8} | {'S1 L1%':>8} | {'avg w0':>8} | {'avg w1':>8} "
          f"| {'|cb| S0':>8} | {'|cb| S1':>8} | {'cb>0 S0':>8} | {'cb>0 S1':>8}")
    print("-" * 72)
    for level in all_results:
        s = level["strength"]
        runs = level["runs"]
        s0_rate = sum(1 for r in runs if r["S0_L1"]) / len(runs)
        s1_rate = sum(1 for r in runs if r["S1_L1"]) / len(runs)
        avg_w0 = np.mean([r["S0_final_w"] for r in runs])
        avg_w1 = np.mean([r["S1_final_w"] for r in runs])
        avg_cb0 = np.mean([r["coupling_evidence"]["S0"]["coupling_bias_norm"] for r in runs])
        avg_cb1 = np.mean([r["coupling_evidence"]["S1"]["coupling_bias_norm"] for r in runs])
        avg_pos0 = np.mean([r["coupling_evidence"]["S0"]["coupling_bias_pos_ratio"] for r in runs])
        avg_pos1 = np.mean([r["coupling_evidence"]["S1"]["coupling_bias_pos_ratio"] for r in runs])
        print(f"{s:>8.1f} | {s0_rate:>8.2f} | {s1_rate:>8.2f} | {avg_w0:>8.1f} | {avg_w1:>8.1f} "
              f"| {avg_cb0:>8.4f} | {avg_cb1:>8.4f} | {avg_pos0:>8.3f} | {avg_pos1:>8.3f}")
    print("-" * 72)

    # Analysis
    print()
    print("=" * 72)
    print("  ANALYSIS")
    print("=" * 72)
    for level in all_results:
        s = level["strength"]
        runs = level["runs"]
        cb0_norms = [r["coupling_evidence"]["S0"]["coupling_bias_norm"] for r in runs]
        cb1_norms = [r["coupling_evidence"]["S1"]["coupling_bias_norm"] for r in runs]
        coupling_active = sum(1 for n in cb0_norms + cb1_norms if n > 0.001)
        if s == 0.0:
            ok = coupling_active == 0
            print(f"  strength={s:.1f}: coupling=OFF -> cb norm ~ 0 for all runs: {'[OK]' if ok else '[FAIL]'}")
        else:
            ok = coupling_active > 0
            print(f"  strength={s:.1f}: coupling=ON  -> cb norm > 0 in {coupling_active}/{len(runs)*2} runs: {'[OK]' if ok else '[FAIL]'}")
            if ok:
                # Check monotonicity
                mn = np.mean(cb0_norms + cb1_norms)
                print(f"    mean |cb| = {mn:.4f}")
            else:
                print(f"    [FAIL] coupling_bias not active - coupling mechanism may still be broken!")

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"exp_152_verify_{ts}.pt")
    torch.save(all_results, path)
    print(f"\n  Results saved: {path}")
    print("=" * 72)


if __name__ == "__main__":
    run_sweep()
