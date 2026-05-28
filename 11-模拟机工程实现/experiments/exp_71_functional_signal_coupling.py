"""experiments/exp_71_functional_signal_coupling.py

Phase 2 P2: Functional Signal Coupling Experiment.

Tests whether coupling computed from functional signals (extracted from
Phase 2 component outputs) outperforms positional coupling (bit_id % 6).

Configurations:
  A: baseline - positional weighted coupling (weighted, 0.30, N72)
  B: functional coupling (functional mode, 0.30, N72)
  C: functional + lower threshold (functional mode, 0.15, N72)
  D: functional + even lower threshold (functional mode, 0.10, N72)
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
    extract_functional_signals, compute_functional_coupling_matrix
)


CONFIGS = {
    "A_baseline_positional": {
        "N0": 72, "steps": 300, "sample_interval": 5, "p1_eval_interval": 5,
        "coupling_mode": "weighted", "coupling_threshold": 0.30,
        "description": "Baseline: positional weighted, threshold=0.30, N72",
    },
    "B_functional_030": {
        "N0": 72, "steps": 300, "sample_interval": 5, "p1_eval_interval": 5,
        "coupling_mode": "functional", "coupling_threshold": 0.30,
        "description": "Functional coupling, threshold=0.30, N72",
    },
    "C_functional_015": {
        "N0": 72, "steps": 300, "sample_interval": 5, "p1_eval_interval": 5,
        "coupling_mode": "functional", "coupling_threshold": 0.15,
        "description": "Functional coupling, threshold=0.15, N72",
    },
    "D_functional_010": {
        "N0": 72, "steps": 300, "sample_interval": 5, "p1_eval_interval": 5,
        "coupling_mode": "functional", "coupling_threshold": 0.10,
        "description": "Functional coupling, threshold=0.10, N72",
    },
}


def run_config(name, cfg, n_runs=4):
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
            phase2_verbose=False,
        )

        run_result = evolver.run()

        # Extract results from phase2_step_results
        layer_results = run_result.get("layer_results", [])
        converged_count = 0
        total_evaluations = 0
        conv_step = None
        odi_values = []
        coupling_values = []

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

        convergence_rate = converged_count / max(1, total_evaluations)
        avg_odi = float(np.mean(odi_values)) if odi_values else 0.0
        max_odi = float(np.max(odi_values)) if odi_values else 0.0
        coupling_rate = float(np.mean(coupling_values)) if coupling_values else 0.0

        result = {
            "config": name, "run_id": run_id,
            "convergence_rate": convergence_rate,
            "converged_count": converged_count,
            "total_evaluations": total_evaluations,
            "first_conv_step": conv_step,
            "avg_odi": avg_odi, "max_odi": max_odi,
            "coupling_rate": coupling_rate,
        }
        results.append(result)
        print(f"    conv_rate={convergence_rate:.1%}, avg_odi={avg_odi:.3f}, max_odi={max_odi:.3f}")
    return results


def main():
    print("=" * 60)
    print("exp_71: Functional Signal Coupling Experiment")
    print("=" * 60)
    start_time = time.time()

    all_results = {}
    for name, cfg in CONFIGS.items():
        print(f"\nConfig: {name}")
        print(f"  {cfg["description"]}")
        results = run_config(name, cfg, n_runs=4)
        all_results[name] = results

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Config':<30} {'Conv%':>8} {'AvgODI':>8} {'MaxODI':>8} {'CplRate':>8}")
    print("-" * 60)
    for name, results in all_results.items():
        conv_rates = [r["convergence_rate"] for r in results]
        avg_odis = [r["avg_odi"] for r in results]
        max_odis = [r["max_odi"] for r in results]
        cpl_rates = [r["coupling_rate"] for r in results]
        print(f"{name:<30} {np.mean(conv_rates)*100:>7.1f}% {np.mean(avg_odis):>8.3f} {np.mean(max_odis):>8.3f} {np.mean(cpl_rates)*100:>7.1f}%")

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(PROJECT_ROOT, "experiments", f"exp_71_results_{timestamp}.json")
    with open(output_path, "w") as f:
        json.dump({"experiment": "exp_71", "timestamp": timestamp,
                   "elapsed_seconds": elapsed, "results": all_results},
                  f, indent=2, default=str)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
