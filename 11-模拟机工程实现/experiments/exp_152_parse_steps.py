"""exp_152: Parse A9 seal steps from verbose stdout.

Clean approach: run each experiment with verbose=True, 
capture stdout via redirect_stdout, parse A9 lines in order.
S0 always prints first (subspace dict iteration order), 
"""

import sys, os, io, re, contextlib, numpy as np
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.exp_152_phase11_p4_fixed_coupling import (
    patch_axioms_with_coupling_bias, run_single_experiment
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'results', 'phase11_p4')
os.makedirs(RESULTS_DIR, exist_ok=True)


def run_one_and_parse(strength, seed, N0=40, N1=40,
                      steps_per_layer=5000, max_layers=2):
    """Run one experiment, parse A9 seal steps from verbose output."""
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

    # Parse all [A9] Sealed lines, in order
    # They come in pairs: S0 line, then S1 line (per run)
    a9_lines = re.findall(
        r'\[A9\] Sealed at step (\d+):',
        output
    )
    steps = [int(x) for x in a9_lines]

    # In bidirectional coupling with 2 subspaces and max_layers=1:
    # Each run produces 2 A9 lines: [S0_step, S1_step]
    # With n_runs=5: 10 lines total, even indices = S0, odd = S1
    seal = {}
    if len(steps) >= 1:
        seal['S0'] = steps[0]
    if len(steps) >= 2:
        seal['S1'] = steps[1]

    return {
        **r,
        'S0_seal_step': seal.get('S0', -1),
        'S1_seal_step': seal.get('S1', -1),
    }


def run_sweep(n_runs=5, coupling_levels=None, N0=40, N1=40,
              steps_per_layer=5000, max_layers=2, device="cpu"):
    if coupling_levels is None:
        coupling_levels = [0.0, 0.3, 0.6, 1.0, 2.0, 5.0]

    print("=" * 70)
    print("exp_152: Seal-step analysis (parsing verbose A9 output)")
    print("=" * 70)
    patch_axioms_with_coupling_bias()

    results = []
    for strength in coupling_levels:
        print(f"\n--- coupling_strength = {strength} ---")
        level_results = []
        for run_i in range(n_runs):
            seed = 42 + int(strength * 100) + run_i * 7
            r = run_one_and_parse(
                strength, seed=seed, N0=N0, N1=N1,
                steps_per_layer=steps_per_layer,
                max_layers=max_layers,
            )
            level_results.append(r)
            s0_l1 = "Y" if r["S0_L1"] else "N"
            s1_l1 = "Y" if r["S1_L1"] else "N"
            print(f"  run {run_i}: S0={s0_l1}(step={r['S0_seal_step']}) "
                  f"S1={s1_l1}(step={r['S1_seal_step']}) "
                  f"w0={r['S0_final_w']:.0f} w1={r['S1_final_w']:.0f}")
        results.append({"strength": strength, "runs": level_results})

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY: Effect of coupling strength on S1 seal speed")
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
