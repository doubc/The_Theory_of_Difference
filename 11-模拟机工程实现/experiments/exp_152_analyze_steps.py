"""exp_152 analysis: parse A9 seal steps from verbose stdout."""

import sys, os, io, re, numpy as np
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.exp_152_phase11_p4_fixed_coupling import (
    patch_axioms_with_coupling_bias, make_field, run_single_experiment
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'results', 'phase11_p4')
os.makedirs(RESULTS_DIR, exist_ok=True)


def run_and_capture(strength, N0=40, N1=40, seed=42,
                     steps_per_layer=5000, max_layers=2):
    """Run one experiment, capture A9 seal steps from verbose output."""
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = run_single_experiment(
            coupling_strength=strength,
            N0=N0, N1=N1,
            steps_per_layer=steps_per_layer,
            max_layers=max_layers,
            device="cpu",
            seed=seed,
        )
    output = buf.getvalue()

    # Parse A9 seal steps: "[A9] Sealed at step NN"
    # Lines look like:
    #   [A9] Sealed at step 99: 30 active...
    # We need to attribute lines to S0 vs S1.
    # Simple heuristic: lines alternate S0/S1 within a run,
    # - or: check which subspace has which solver name in output
    # Actually: the verbose output prints solver name in other places.
    # Simpler: just collect all A9 steps, pair them sequentially S0/S1.
    a9_lines = re.findall(
        r'\[A9\] Sealed at step (\d+).*?('
        r'keeping\s+(\d+)\s*,\s*freezing\s*(\d+)',
        output
    )
    # Actually let's just parse step numbers and pair them
    steps = [int(x) for x in re.findall(r'\[A9\] Sealed at step (\d+)', output)]
    # The output interleaves S0 and S1. In bidirectional coupling,
    # S0 always runs first (it's listed first in subspaces dict).
    # So steps[0] = S0 seal, steps[1] = S1 seal, etc.
    seal_steps = {}
    if len(steps) >= 1:
        seal_steps['S0'] = steps[0]
    if len(steps) >= 2:
        seal_steps['S1'] = steps[1]

    r['S0_seal_step'] = seal_steps.get('S0', -1)
    r['S1_seal_step'] = seal_steps.get('S1', -1)
    return r, output


def run_sweep(n_runs=5, coupling_levels=None, N0=40, N1=40,
              steps_per_layer=5000, max_layers=2, device="cpu"):
    if coupling_levels is None:
        coupling_levels = [0.0, 0.3, 0.6, 1.0, 2.0, 5.0]

    print("=" * 70)
    print("exp_152 (verbose parse): seal step analysis")
    print("=" * 70)
    patch_axioms_with_coupling_bias()

    results = []
    for strength in coupling_levels:
        print(f"\n--- coupling_strength = {strength} ---")
        level_results = []
        for run_i in range(n_runs):
            seed = 42 + int(strength * 100) + run_i * 7
            r, output = run_and_capture(
                strength, N0=N0, N1=N1, seed=seed,
                steps_per_layer=steps_per_layer,
                max_layers=max_layers,
            )
            r['seed'] = seed
            level_results.append(r)
            s0_l1 = "Y" if r["S0_L1"] else "N"
            s1_l1 = "Y" if r["S1_L1"] else "N"
            print(f"  run {run_i}: S0={s0_l1}(step={r['S0_seal_step']}) "
                  f"S1={s1_l1}(step={r['S1_seal_step']}) "
                  f"w0={r['S0_final_w']:.0f} w1={r['S1_final_w']:.0f}")
        results.append({"strength": strength, "runs": level_results})

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY: Effect of coupling on S1 seal speed")
    print("=" * 70)
    print(f"{'Strength':>8} | {'S1_L1_rate':>12} | {'avg_S1_step':>13} | {'avg_w1':>8}")
    print("-" * 60)
    for level in results:
        s = level["strength"]
        runs = level["runs"]
        s1_rate = sum(1 for r in runs if r["S1_L1"]) / len(runs)
        s1_steps = [r['S1_seal_step'] for r in runs if r['S1_seal_step'] > 0]
        avg_step = np.mean(s1_steps) if s1_steps else -1
        avg_w1 = np.mean([r['S1_final_w'] for r in runs])
        print(f"{s:>8.1f} | {s1_rate:>12.2f} | {avg_step:>13.1f} | {avg_w1:>8.1f}")

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"exp_152_steps_{timestamp}.npy")
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
