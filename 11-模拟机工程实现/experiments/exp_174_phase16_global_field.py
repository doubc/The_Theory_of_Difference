"""
exp_174_phase16_global_field.py -- Phase 16 Path B2: Global Field Experiment

Hypothesis H16-B2: Global field enables L1 structure to reflect L0 global features.

Rationale:
  Current difference theory uses local interaction + serial evolution = "dead order".
  A global field carries system-wide average state; every bit senses the global trend.
  This may break locality constraints, enabling cross-layer structure reflection.

Design:
  At each timestep, compute global_field = mean(state).
  Each bit is pulled toward the global mean:
    flip_prob = alpha * |global_field - state[i]|
  Configs: alpha = 0.0 (baseline), 0.1, 0.3, 0.5, 0.7, 0.9

Usage:
    python exp_174_phase16_global_field.py [--alpha 0.3] [--n_runs 5] [--all_alpha]
"""

import sys
import os
import json
import time
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import torch

# -- Project root --
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver, SpatialSnapshot
from engine.cross_layer_evolver import CrossLayerMapper, Layer1Evolver, L1Constraints
from acl.axioms_v2 import AxiomConstraints


# ============================================================
# GlobalFieldEvolver
# ============================================================

class GlobalFieldEvolver(SpatialLongRangeEvolver):
    """Spatial evolver with global mean field bias.

    Mechanism:
      At each sampling step, compute global_field = mean(state).
      Each bit is pulled toward the global mean with probability:
        alpha * |global_field - state[i]|
      (delta > 0 -> flip to 1; delta < 0 -> flip to 0)

      Effect: all bits simultaneously sense the global trend,
      breaking purely local information flow.
    """

    def __init__(self,
                 global_field_alpha: float = 0.0,
                 **kwargs):
        super().__init__(**kwargs)
        self.global_field_alpha = global_field_alpha
        self.global_field_history: List[float] = []

        if global_field_alpha > 1e-6:
            print(f"[GlobalFieldEvolver] alpha={global_field_alpha:.1f}, N={self.N}")

    def _apply_global_field(self, state: torch.Tensor):
        if self.global_field_alpha <= 1e-6:
            return

        global_field = state.mean().item()
        self.global_field_history.append(global_field)

        alpha_eff = self.global_field_alpha * 0.02  # gentle per-callback strength

        for i in range(self.N):
            si = state[i].item()
            delta = global_field - si
            flip_prob = alpha_eff * abs(delta)
            if flip_prob > 0 and torch.rand(1).item() < flip_prob:
                state[i] = 1.0 if delta > 0 else 0.0

    def run(self,
            initial_state=None,
            verbose=True,
            step_callback=None,
            post_seal_callback=None):
        if self.global_field_alpha <= 1e-6:
            return super().run(
                initial_state=initial_state,
                verbose=verbose,
                step_callback=step_callback,
                post_seal_callback=post_seal_callback,
            )

        self.global_field_history = []
        orig_cb = step_callback

        def _gf_callback(step, state, snapshot, constraints):
            self._apply_global_field(state)
            if orig_cb is not None:
                orig_cb(step, state, snapshot, constraints)

        return super().run(
            initial_state=initial_state,
            verbose=verbose,
            step_callback=_gf_callback,
            post_seal_callback=post_seal_callback,
        )


# ============================================================
# Experiment configs
# ============================================================

ALPHA_CONFIGS = [
    {'alpha': 0.0, 'label': 'baseline'},
    {'alpha': 0.1, 'label': 'a01_weak'},
    {'alpha': 0.3, 'label': 'a03_medium'},
    {'alpha': 0.5, 'label': 'a05_moderate'},
    {'alpha': 0.7, 'label': 'a07_strong'},
    {'alpha': 0.9, 'label': 'a09_max'},
]

N = 48
L0_STEPS = 3000
L1_STEPS = 2000
SAMPLE_INTERVAL = 25
N_RUNS = 5


# ============================================================
# Single trial
# ============================================================

@dataclass
class ExperimentResult:
    config_label: str = ''
    alpha: float = 0.0
    trial: int = 0
    l0_sealed: bool = False
    l0_seal_step: int = -1
    l0_hw_final: int = 0
    l0_hw_history: List[int] = field(default_factory=list)
    l0_n_clusters: int = 0
    l0_cluster_sizes: List[int] = field(default_factory=list)
    gf_mean: float = 0.0
    gf_std: float = 0.0
    l1_sealed: bool = False
    l1_seal_step: int = -1
    l1_hw_final: int = 0
    l1_hw_history: List[int] = field(default_factory=list)
    reflection_score: float = 0.0
    l1_structure_entropy: float = 0.0
    elapsed_sec: float = 0.0
    error: Optional[str] = None


def compute_structure_reflection(l0_result: Dict, l1_result: Dict) -> float:
    l0_clusters = l0_result.get('clusters', [])
    if not l0_clusters or len(l0_clusters) < 2:
        return 0.0
    l1_constraints = l1_result.get('l0_constraints', None)
    if l1_constraints is None:
        return 0.0
    hierarchy_map = l1_constraints.hierarchy_map
    l1_final = l1_result.get('final_state', None)
    if l1_final is None:
        return 0.0
    l1_state = l1_final.cpu().numpy() if torch.is_tensor(l1_final) else l1_final
    if len(l1_state) != len(hierarchy_map):
        return 0.0
    n_clusters = len(l0_clusters)
    group_hws = {cid: [] for cid in range(n_clusters)}
    for i, cid in enumerate(hierarchy_map):
        if cid >= 0 and cid < n_clusters:
            group_hws[cid].append(1.0 if l1_state[i] > 0.5 else 0.0)
    group_ratios = []
    for cid, states in group_hws.items():
        if states:
            ratio = sum(states) / len(states)
            group_ratios.append(ratio)
    if len(group_ratios) < 2:
        return 0.0
    variance = float(np.var(group_ratios))
    return max(0.0, 1.0 - variance / 0.25)


def compute_structure_entropy(l0_result: Dict, l1_result: Dict) -> float:
    l1_constraints = l1_result.get('l0_constraints', None)
    if l1_constraints is None:
        return 1.0
    hierarchy_map = l1_constraints.hierarchy_map
    l1_final = l1_result.get('final_state', None)
    if l1_final is None:
        return 1.0
    l1_state = l1_final.cpu().numpy() if torch.is_tensor(l1_final) else l1_final
    if len(l1_state) != len(hierarchy_map):
        return 1.0
    l0_clusters = l0_result.get('clusters', [])
    n_clusters = len(l0_clusters) if l0_clusters else 1
    group_ratios = []
    for cid in range(n_clusters):
        states = []
        for i, hcid in enumerate(hierarchy_map):
            if hcid == cid:
                states.append(1.0 if l1_state[i] > 0.5 else 0.0)
        if states:
            ratio = sum(states) / len(states)
            group_ratios.append(ratio)
    if len(group_ratios) < 2:
        return 1.0
    ratios = np.array(group_ratios)
    ratios = np.clip(ratios, 0.001, 0.999)
    entropy = -np.mean(ratios * np.log(ratios) + (1-ratios)*np.log(1-ratios))
    max_entropy = -0.5*np.log(0.5) - 0.5*np.log(0.5)
    return float(entropy / max_entropy) if max_entropy > 0 else 1.0


def run_single_trial(alpha: float, trial_idx: int = 0, label: str = '') -> ExperimentResult:
    result = ExperimentResult(config_label=label, alpha=alpha, trial=trial_idx)
    t0 = time.time()

    try:
        # Phase 1: L0 evolution with global field
        l0_evolver = GlobalFieldEvolver(
            N=N, total_steps=L0_STEPS, sample_interval=SAMPLE_INTERVAL,
            device='cpu', global_field_alpha=alpha,
        )
        l0_result = l0_evolver.run(verbose=False)

        result.l0_sealed = l0_result.get('sealed', False)
        result.l0_seal_step = l0_evolver.seal_step
        hw_hist = l0_result.get('hamming_weight_history', [])
        result.l0_hw_history = hw_hist
        if hw_hist:
            result.l0_hw_final = hw_hist[-1]
        clusters_raw = l0_result.get('clusters', [])
        if clusters_raw:
            result.l0_n_clusters = len(clusters_raw)
            result.l0_cluster_sizes = [len(c) for c in clusters_raw]

        if hasattr(l0_evolver, 'global_field_history') and l0_evolver.global_field_history:
            gf = np.array(l0_evolver.global_field_history)
            result.gf_mean = float(gf.mean())
            result.gf_std = float(gf.std())

        if not result.l0_sealed:
            result.error = 'L0 did not seal'
            result.elapsed_sec = time.time() - t0
            return result

        # Phase 2: L0 -> L1 constraint mapping
        mapper = CrossLayerMapper(N0=N, N1=N, device='cpu')
        l1_constraints = mapper.map_from_l0_result(l0_evolver=l0_evolver, l0_result=l0_result)

        # Phase 3: L1 evolution
        l1_evolver = Layer1Evolver(
            N1=N, total_steps=L1_STEPS, sample_interval=SAMPLE_INTERVAL,
            device='cpu', l0_constraints=l1_constraints, feedback_from_l0=False,
        )
        l1_evolver._install_constraint_callback()
        l1_result = l1_evolver.run()

        result.l1_sealed = l1_result.get('sealed', False)
        result.l1_seal_step = l1_result.get('seal_step', -1)
        l1_hw = l1_result.get('hw_history', [])
        result.l1_hw_history = l1_hw
        if l1_hw:
            result.l1_hw_final = l1_hw[-1]

        l1_result['l0_constraints'] = l1_constraints
        l1_result['clusters'] = clusters_raw

        # Phase 4: Structure analysis
        result.reflection_score = compute_structure_reflection(l0_result, l1_result)
        result.structure_entropy = compute_structure_entropy(l0_result, l1_result)

        result.elapsed_sec = time.time() - t0

    except Exception as e:
        import traceback
        result.error = f"{type(e).__name__}: {e}"
        result.elapsed_sec = time.time() - t0
        print(f"    ERROR trial {trial_idx}: {e}")
        traceback.print_exc()

    return result


# ============================================================
# Analysis
# ============================================================

def run_experiment_for_alpha(alpha: float, label: str, n_runs: int = N_RUNS) -> List[ExperimentResult]:
    print(f"\n{'=' * 50}")
    print(f"Config: {label} (alpha={alpha:.1f}), {n_runs} trials")
    results = []
    for trial in range(n_runs):
        print(f"  Trial {trial+1}/{n_runs}...", end=' ', flush=True)
        r = run_single_trial(alpha, trial, label)
        results.append(r)
        print(f"L0_seal={r.l0_sealed}, L1_seal={r.l1_sealed}, "
              f"reflection={r.reflection_score:.3f} "
              f"(gf_mean={r.gf_mean:.3f}) ({r.elapsed_sec:.1f}s)")
        if r.error:
            print(f"    !! {r.error}")
    return results


def analyze_results(all_results: Dict[str, List[ExperimentResult]]):
    print(f"\n{'=' * 70}")
    print("EXP_174 STATISTICAL SUMMARY - Global Field")
    print(f"{'=' * 70}")

    for label, results in all_results.items():
        valid = [r for r in results if not r.error]
        if not valid:
            print(f"\n  {label}: No valid trials")
            continue

        l0_sealed = [r for r in valid if r.l0_sealed]
        print(f"\n  {label} (alpha={results[0].alpha}): "
              f"L0 seal={len(l0_sealed)}/{len(valid)} ({len(l0_sealed)/len(valid)*100:.0f}%)")

        if l0_sealed:
            steps = [r.l0_seal_step for r in l0_sealed]
            hw = [r.l0_hw_final for r in l0_sealed]
            nc = [r.l0_n_clusters for r in l0_sealed]
            print(f"    L0 seal step: {np.mean(steps):.1f}+-{np.std(steps):.1f}")
            print(f"    L0 HW final:  {np.mean(hw):.1f}+-{np.std(hw):.1f}")
            print(f"    L0 clusters:  {np.mean(nc):.1f}+-{np.std(nc):.1f}")
            print(f"    GF mean: {np.mean([r.gf_mean for r in l0_sealed]):.3f} "
                  f"GF std: {np.mean([r.gf_std for r in l0_sealed]):.3f}")

        l1_sealed = [r for r in valid if r.l1_sealed]
        if l1_sealed:
            print(f"    L1 seal: {len(l1_sealed)}/{len(valid)} ({len(l1_sealed)/len(valid)*100:.0f}%)")
            steps = [r.l1_seal_step for r in l1_sealed]
            hw = [r.l1_hw_final for r in l1_sealed]
            print(f"    L1 seal step: {np.mean(steps):.1f}+-{np.std(steps):.1f}")
            print(f"    L1 HW final:  {np.mean(hw):.1f}+-{np.std(hw):.1f}")
            scores = [r.reflection_score for r in l1_sealed]
            print(f"    Reflection:   {np.mean(scores):.3f}+-{np.std(scores):.3f}")
            ents = [r.structure_entropy for r in l1_sealed]
            print(f"    Structure entropy: {np.mean(ents):.3f}+-{np.std(ents):.3f}")


def save_results(all_results: Dict[str, List[ExperimentResult]], timestamp: str):
    results_dir = PROJECT_ROOT / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    serializable = {}
    for label, results in all_results.items():
        serializable[label] = []
        for r in results:
            serializable[label].append({
                'config_label': r.config_label, 'alpha': r.alpha, 'trial': r.trial,
                'l0_sealed': r.l0_sealed, 'l0_seal_step': r.l0_seal_step,
                'l0_hw_final': r.l0_hw_final, 'l0_n_clusters': r.l0_n_clusters,
                'gf_mean': r.gf_mean, 'gf_std': r.gf_std,
                'l1_sealed': r.l1_sealed, 'l1_seal_step': r.l1_seal_step,
                'l1_hw_final': r.l1_hw_final,
                'reflection_score': r.reflection_score,
                'structure_entropy': r.l1_structure_entropy,
                'elapsed_sec': r.elapsed_sec, 'error': r.error,
            })
    result_file = results_dir / f'exp_174_results_{timestamp}.json'
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {result_file}")
    return result_file


# ============================================================
# Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='exp_174: Global Field (Phase 16 Path B2)')
    parser.add_argument('--alpha', type=float, default=None)
    parser.add_argument('--n_runs', type=int, default=N_RUNS)
    parser.add_argument('--all_alpha', action='store_true')
    parser.add_argument('--fast', action='store_true')
    args = parser.parse_args()

    n_runs = 2 if args.fast else args.n_runs

    if args.all_alpha:
        configs_to_run = ALPHA_CONFIGS
    elif args.alpha is not None:
        matching = [c for c in ALPHA_CONFIGS if abs(c['alpha'] - args.alpha) < 1e-6]
        if not matching:
            print(f"Unknown alpha={args.alpha}. Options: {[c['alpha'] for c in ALPHA_CONFIGS]}")
            return
        configs_to_run = matching
    else:
        configs_to_run = ALPHA_CONFIGS

    print("=" * 70)
    print("exp_174 -- Phase 16 Path B2: Global Field")
    print("=" * 70)
    print(f"  N={N}, L0_steps={L0_STEPS}, L1_steps={L1_STEPS}")
    print(f"  sample_interval={SAMPLE_INTERVAL}, n_runs={n_runs}")
    print(f"  Configs: {[c['label'] for c in configs_to_run]}")
    print(f"  Total experiments: {len(configs_to_run) * n_runs}")
    print("=" * 70)

    t_start = time.time()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    all_results: Dict[str, List[ExperimentResult]] = {}

    for cfg in configs_to_run:
        results = run_experiment_for_alpha(alpha=cfg['alpha'], label=cfg['label'], n_runs=n_runs)
        all_results[cfg['label']] = results

    total_elapsed = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"{'=' * 70}")
    analyze_results(all_results)
    save_results(all_results, timestamp)


if __name__ == '__main__':
    main()