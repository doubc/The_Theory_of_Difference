"""experiments/exp_72_extended_functional_coupling.py

Phase 2 P2: Extended Functional Signal Coupling Experiment.

exp_71 showed that functional signals were all zero at steps=300 because
Phase 2 components (cumulative_selector, persistent_bias_memory, etc.)
had not accumulated enough structure. This experiment extends steps to 2000
and adds per-step functional signal diagnostic logging.

Configurations:
  A: baseline - positional weighted coupling (weighted, 0.30, N72, steps=2000)
  B: functional coupling (functional mode, 0.30, N72, steps=2000)
  C: functional + lower threshold (functional mode, 0.15, N72, steps=2000)
  D: functional + diagnostic logging (functional mode, 0.30, N72, steps=2000, verbose=True)

Key additions over exp_71:
  - Extended steps: 2000 (from 300)
  - Functional signal diagnostics logged every 100 steps
  - Warmup tracking: signals during first 500 steps vs. later steps
  - Per-signal breakdown in results
"""

import sys
import os
import time
import json
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.functional_signal_coupling import (
    extract_functional_signals, compute_functional_coupling_matrix,
    FunctionalSignalSet,
)


# NOTE: p1_eval_interval is counted in callback invocations (not raw steps).
# The callback fires every sample_interval steps.
# So P1 evaluation fires every sample_interval * p1_eval_interval raw steps.
# With sample_interval=50 and p1_eval_interval=1, P1 fires every 50 raw steps.
CONFIGS = {
    "A_baseline_positional_2000": {
        "N0": 72, "steps": 2000, "sample_interval": 50, "p1_eval_interval": 1,
        "coupling_mode": "weighted", "coupling_threshold": 0.30,
        "description": "Baseline: positional weighted, threshold=0.30, N72, steps=2000",
    },
    "B_functional_030_2000": {
        "N0": 72, "steps": 2000, "sample_interval": 50, "p1_eval_interval": 1,
        "coupling_mode": "functional", "coupling_threshold": 0.30,
        "description": "Functional coupling, threshold=0.30, N72, steps=2000",
    },
    "C_functional_015_2000": {
        "N0": 72, "steps": 2000, "sample_interval": 50, "p1_eval_interval": 1,
        "coupling_mode": "functional", "coupling_threshold": 0.15,
        "description": "Functional coupling, threshold=0.15, N72, steps=2000",
    },
    "D_functional_030_diag_2000": {
        "N0": 72, "steps": 2000, "sample_interval": 50, "p1_eval_interval": 1,
        "coupling_mode": "functional", "coupling_threshold": 0.30,
        "description": "Functional + diagnostics, threshold=0.30, N72, steps=2000",
        "diagnostic": True,
    },
}


def run_config(name, cfg, n_runs=3):
    results = []
    for run_id in range(n_runs):
        print(f"  [{name}] Run {run_id+1}/{n_runs}...")
        torch.manual_seed(42 + run_id)
        np.random.seed(42 + run_id)

        psc = PreSubjectivityConvergence(
            coupling_threshold=cfg["coupling_threshold"],
            coupling_mode=cfg["coupling_mode"],
        )

        evolver = HierarchicalEvolver(
            N0=cfg["N0"],
            steps_per_layer=cfg["steps"],
            sample_interval=cfg["sample_interval"],
            max_layers=1,
            p1_eval_interval=cfg["p1_eval_interval"],
            persistent_bias_memory=PersistentBiasMemory(),
            cumulative_selector=CumulativeSelector(),
            six_threshold_detector=SixThresholdDetector(),
            pre_subjectivity_convergence=psc,
            phase2_verbose=cfg.get("diagnostic", False),
        )

        run_result = evolver.run()

        # Extract results from phase2_step_results
        layer_results = run_result.get("layer_results", [])
        converged_count = 0
        total_evaluations = 0
        conv_step = None
        odi_values = []
        coupling_values = []
        convergence_values = []

        # Functional signal diagnostics
        functional_signal_history = []
        warmup_signals = []  # steps 0-499
        late_signals = []    # steps 500+

        for lr in layer_results:
            for sr in lr.get("phase2_step_results", []):
                total_evaluations += 1
                conv = sr.get("convergence", {})
                if conv.get("converged", False):
                    converged_count += 1
                    if conv_step is None:
                        conv_step = sr.get("step", 0)
                odi_val = 0.0
                if isinstance(sr.get("odi"), dict):
                    odi_val = sr["odi"].get("value", 0.0)
                odi_values.append(odi_val)
                coupling_values.append(1 if conv.get("coupling_met", False) else 0)
                convergence_values.append(1 if conv.get("converged", False) else 0)

                # Collect functional signal diagnostics if available
                fs = sr.get("functional_signals")
                if fs is not None:
                    step_num = sr.get("step", 0)
                    sig_vals = fs if isinstance(fs, dict) else {}
                    entry = {"step": step_num}
                    for k in FunctionalSignalSet.mechanism_names():
                        entry[k] = sig_vals.get(k, 0.0)
                    functional_signal_history.append(entry)
                    if step_num < 500:
                        warmup_signals.append(entry)
                    else:
                        late_signals.append(entry)

        convergence_rate = converged_count / max(1, total_evaluations)
        avg_odi = float(np.mean(odi_values)) if odi_values else 0.0
        max_odi = float(np.max(odi_values)) if odi_values else 0.0
        coupling_rate = float(np.mean(coupling_values)) if coupling_values else 0.0

        # Compute functional signal statistics
        sig_stats = {}
        if functional_signal_history:
            for k in FunctionalSignalSet.mechanism_names():
                vals = [e[k] for e in functional_signal_history if k in e]
                if vals:
                    sig_stats[k] = {
                        "mean": float(np.mean(vals)),
                        "max": float(np.max(vals)),
                        "nonzero_rate": float(np.mean([1 if v > 0.01 else 0 for v in vals])),
                    }
                else:
                    sig_stats[k] = {"mean": 0.0, "max": 0.0, "nonzero_rate": 0.0}

        # Warmup vs late comparison
        warmup_late_comparison = {}
        if warmup_signals and late_signals:
            for k in FunctionalSignalSet.mechanism_names():
                warmup_vals = [e[k] for e in warmup_signals if k in e]
                late_vals = [e[k] for e in late_signals if k in e]
                warmup_late_comparison[k] = {
                    "warmup_mean": float(np.mean(warmup_vals)) if warmup_vals else 0.0,
                    "late_mean": float(np.mean(late_vals)) if late_vals else 0.0,
                    "growth_factor": (float(np.mean(late_vals)) / max(1e-8, float(np.mean(warmup_vals))))
                        if warmup_vals and late_vals and float(np.mean(warmup_vals)) > 1e-8 else 0.0,
                }

        result = {
            "config": name, "run_id": run_id,
            "convergence_rate": convergence_rate,
            "converged_count": converged_count,
            "total_evaluations": total_evaluations,
            "first_conv_step": conv_step,
            "avg_odi": avg_odi, "max_odi": max_odi,
            "coupling_rate": coupling_rate,
            "functional_signal_stats": sig_stats,
            "warmup_late_comparison": warmup_late_comparison,
            "n_functional_signal_entries": len(functional_signal_history),
        }
        results.append(result)
        print(f"    conv_rate={convergence_rate:.1%}, avg_odi={avg_odi:.3f}, max_odi={max_odi:.3f}")
        if sig_stats:
            sig_summary = ", ".join(f"{k[:4]}={v['mean']:.3f}" for k, v in sig_stats.items())
            print(f"    signals: {sig_summary}")
    return results


def main():
    print("=" * 60)
    print("exp_72: Extended Functional Signal Coupling Experiment")
    print("  steps=2000 (vs 300 in exp_71)")
    print("  with functional signal diagnostic logging")
    print("=" * 60)
    start_time = time.time()

    all_results = {}
    for name, cfg in CONFIGS.items():
        print(f"\nConfig: {name}")
        print(f"  {cfg['description']}")
        results = run_config(name, cfg, n_runs=3)
        all_results[name] = results

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Config':<35} {'Conv%':>8} {'AvgODI':>8} {'MaxODI':>8} {'CplRate':>8}")
    print("-" * 60)
    for name, results in all_results.items():
        conv_rates = [r["convergence_rate"] for r in results]
        avg_odis = [r["avg_odi"] for r in results]
        max_odis = [r["max_odi"] for r in results]
        cpl_rates = [r["coupling_rate"] for r in results]
        print(f"{name:<35} {np.mean(conv_rates)*100:>7.1f}% {np.mean(avg_odis):>8.3f} {np.mean(max_odis):>8.3f} {np.mean(cpl_rates)*100:>7.1f}%")

    # Print functional signal comparison
    print("\n" + "=" * 60)
    print("FUNCTIONAL SIGNAL DIAGNOSTICS (Config D)")
    print("=" * 60)
    diag_results = all_results.get("D_functional_030_diag_2000", [])
    if diag_results:
        for r in diag_results:
            print(f"\n  Run {r['run_id']+1}:")
            sig_stats = r.get("functional_signal_stats", {})
            for k, v in sig_stats.items():
                print(f"    {k:<30} mean={v['mean']:.4f} max={v['max']:.4f} nonzero={v['nonzero_rate']:.1%}")
            wlc = r.get("warmup_late_comparison", {})
            if wlc:
                print(f"    --- Warmup (0-499) vs Late (500+) ---")
                for k, v in wlc.items():
                    print(f"    {k:<30} warmup={v['warmup_mean']:.4f} late={v['late_mean']:.4f} growth={v['growth_factor']:.2f}x")

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(PROJECT_ROOT, "experiments", f"exp_72_results_{timestamp}.json")
    with open(output_path, "w") as f:
        json.dump({"experiment": "exp_72", "timestamp": timestamp,
                   "elapsed_seconds": elapsed, "results": all_results},
                  f, indent=2, default=str)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
