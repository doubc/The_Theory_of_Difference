"""experiments/exp_73_retention_validation.py

Phase 2 P1: Retention Depth Validation Experiment.

Validates that the retention signal fix (commit b7f5a18) works end-to-end:
- PersistentBiasMemory reconstruction cycle tracking is properly wired into
  HierarchicalEvolver's Phase 2 callback
- retention_depth grows from 0 as evolution proceeds
- n_cycles_tracked increments with each Phase 2 step
- reinvocation_results are recorded per step

Key metric: aggregate_retention_depth should increase over time,
reaching > 0 within the first few hundred steps.

Configurations:
  A: functional coupling, threshold=0.30, N72, steps=1000 (validation run)
  B: functional coupling, threshold=0.15, N72, steps=1000 (lower threshold)
  C: positional baseline, threshold=0.30, N72, steps=1000 (control)
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


CONFIGS = {
    "A_functional_030_1000": {
        "N0": 72, "steps": 1000, "sample_interval": 20, "p1_eval_interval": 1,
        "coupling_mode": "functional", "coupling_threshold": 0.30,
        "description": "Functional coupling, threshold=0.30, N72, steps=1000 — retention validation",
    },
    "B_functional_015_1000": {
        "N0": 72, "steps": 1000, "sample_interval": 20, "p1_eval_interval": 1,
        "coupling_mode": "functional", "coupling_threshold": 0.15,
        "description": "Functional coupling, threshold=0.15, N72, steps=1000 — lower threshold",
    },
    "C_positional_030_1000": {
        "N0": 72, "steps": 1000, "sample_interval": 20, "p1_eval_interval": 1,
        "coupling_mode": "weighted", "coupling_threshold": 0.30,
        "description": "Positional baseline, threshold=0.30, N72, steps=1000 — control",
    },
}


def run_config(name, cfg, n_runs=2):
    """Run a single config and collect retention diagnostics."""
    results = []
    for run_id in range(n_runs):
        print(f"  [{name}] Run {run_id+1}/{n_runs}...")
        torch.manual_seed(42 + run_id)
        np.random.seed(42 + run_id)

        N = cfg["N0"]
        steps = cfg["steps"]
        sample_interval = cfg["sample_interval"]
        p1_eval_interval = cfg["p1_eval_interval"]
        coupling_mode = cfg["coupling_mode"]
        coupling_threshold = cfg["coupling_threshold"]

        # ── Build Phase 2 components ──
        psc = PreSubjectivityConvergence(
            coupling_threshold=coupling_threshold,
            coupling_mode=coupling_mode,
        )

        pbm = PersistentBiasMemory()

        evolver = HierarchicalEvolver(
            N0=N,
            steps_per_layer=steps,
            sample_interval=sample_interval,
            max_layers=1,
            p1_eval_interval=p1_eval_interval,
            persistent_bias_memory=pbm,
            cumulative_selector=CumulativeSelector(),
            six_threshold_detector=SixThresholdDetector(),
            pre_subjectivity_convergence=psc,
            phase2_verbose=cfg.get("diagnostic", False),
        )

        # ── Run evolution ──
        t0 = time.time()
        run_result_raw = evolver.run()
        elapsed = time.time() - t0

        # ── Collect final retention stats ──
        final_pbm_summary = None
        if pbm is not None:
            final_pbm_summary = {
                'n_entries': pbm.n_entries,
                'n_active': pbm.n_active_entries,
                'n_frozen': pbm.n_frozen_entries,
                'n_cycles_tracked': pbm.n_cycles_tracked,
                'aggregate_retention_depth': pbm.get_aggregate_retention_depth(),
                'deep_retention_entries': pbm.get_deep_retention_entries(),
                'all_retention_stats': pbm.get_all_retention_stats(),
            }

        # ── Extract functional signals from results ──
        signal_summary = {}
        layer_results = run_result_raw.get("layer_results", [])
        functional_signal_history = []
        for lr in layer_results:
            for sr in lr.get("phase2_step_results", []):
                fs = sr.get("functional_signals")
                if fs and isinstance(fs, dict):
                    entry = {"step": sr.get("step", 0)}
                    for k in FunctionalSignalSet.mechanism_names():
                        entry[k] = fs.get(k, 0.0)
                    functional_signal_history.append(entry)

        for k in FunctionalSignalSet.mechanism_names():
            vals = [e[k] for e in functional_signal_history if k in e]
            if vals:
                signal_summary[k] = {
                    'final': vals[-1],
                    'mean': float(np.mean(vals)),
                    'max': float(np.max(vals)),
                    'first_nonzero': next((i for i, v in enumerate(vals) if v > 1e-8), -1),
                }

        run_result = {
            'config': name,
            'run_id': run_id,
            'elapsed_seconds': round(elapsed, 1),
            'final_pbm_summary': final_pbm_summary,
            'signal_summary': signal_summary,
            'functional_signal_history': functional_signal_history,
        }
        results.append(run_result)

        # ── Print retention diagnostics ──
        print(f"\n  === Retention Validation Results ===")
        if final_pbm_summary:
            print(f"  n_entries: {final_pbm_summary['n_entries']}")
            print(f"  n_active: {final_pbm_summary['n_active']}")
            print(f"  n_cycles_tracked: {final_pbm_summary['n_cycles_tracked']}")
            print(f"  aggregate_retention_depth: {final_pbm_summary['aggregate_retention_depth']:.4f}")
            print(f"  deep_retention_entries: {final_pbm_summary['deep_retention_entries']}")

            # Check: did retention_depth grow from 0?
            if final_pbm_summary['aggregate_retention_depth'] > 0:
                print(f"  [PASS] retention_depth > 0 - fix is working!")
            else:
                print(f"  [FAIL] retention_depth still 0 - fix may not be effective")

        # Signal check
        if signal_summary.get('retention'):
            r = signal_summary['retention']
            print(f"  Retention signal: final={r['final']:.4f}, "
                  f"mean={r['mean']:.4f}, first_nonzero_step={r['first_nonzero']}")
        if signal_summary.get('coupling'):
            r = signal_summary['coupling']
            print(f"  Coupling signal: final={r['final']:.4f}, "
                  f"mean={r['mean']:.4f}, first_nonzero_step={r['first_nonzero']}")

    return results


def main():
    print("=" * 60)
    print("exp_73: Retention Depth Validation")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    all_results = {}
    for name, cfg in CONFIGS.items():
        print(f"\n--- {name} ---")
        print(f"  {cfg['description']}")
        results = run_config(name, cfg, n_runs=2)
        all_results[name] = results

    # ── Save results ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"exp_73_results_{timestamp}.json"
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n\nResults saved to: {output_path}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for cfg_name, runs in all_results.items():
        for r in runs:
            pbm = r['final_pbm_summary']
            if pbm:
                status = "PASS" if pbm['aggregate_retention_depth'] > 0 else "FAIL"
                print(f"  {cfg_name} (run {r['run_id']}): {status} — "
                      f"retention_depth={pbm['aggregate_retention_depth']:.4f}, "
                      f"n_cycles={pbm['n_cycles_tracked']}")


if __name__ == "__main__":
    main()
