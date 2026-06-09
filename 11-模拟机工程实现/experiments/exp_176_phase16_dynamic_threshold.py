"""
exp_176_phase16_dynamic_threshold.py -- Phase 16 Path C1: Dynamic Sealing Threshold

Hypothesis H16-C1: Dynamic sealing threshold enables L0 to continue evolving after sealing,
producing multiple seal/unseal cycles and potentially L2 emergence.

Rationale:
  Current difference theory seals permanently when HW >= sealing_threshold.
  In biological/physical systems, thresholds are dynamic — they change with conditions.
  By making the sealing threshold decay in response to system order, sealed layers can
  "re-open" and continue evolving toward new configurations.

Mechanism (step_callback-based, no evolver modification):
  1. After sealing (detected in callback), compute system order = HW / N
  2. Decay threshold: θ(t+1) = max(θ_min, θ(t) - α * (1 - order(t)))
  3. When θ drops and HW is low enough, force-unseal by resetting:
     - constraints.sealed = False
     - constraints.sealed_bits = set()
     - constraints.total_unique_active = set() (triggers fresh sealing)
  4. Allow re-sealing (back to original logic)
  5. Track seal/unseal cycles

Configs: alpha = 0.0 (baseline), 0.01, 0.05, 0.10, 0.20, 0.50

Usage:
    python exp_176_phase16_dynamic_threshold.py [--alpha 0.05] [--n_runs 5] [--all_alpha]
"""

import sys
import os
import json
import time
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
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
# DynamicThresholdEvolver
# ============================================================

class DynamicThresholdEvolver(SpatialLongRangeEvolver):
    """Spatial evolver with dynamic sealing threshold.

    Mechanism:
      After the system seals, start a threshold decay process.
      The threshold decreases when the system is highly ordered (stable).
      When the threshold drops low enough, force-unseal by resetting
      constraint sealing state, allowing a new cycle of evolution.

      Each seal/unseal cycle potentially produces a different fixed point.
    """

    def __init__(self,
                 alpha: float = 0.0,          # threshold decay rate
                 theta_min_ratio: float = 0.3, # minimum threshold as fraction of N
                 **kwargs):
        # Ensure enough post_seal_steps for dynamic behavior
        kwargs.setdefault('post_seal_steps', kwargs.get('total_steps', 3000))
        super().__init__(**kwargs)
        self.dt_alpha = alpha
        self.theta_min_ratio = theta_min_ratio
        self.theta_min = max(1, int(self.N * theta_min_ratio))
        self.current_threshold = self.N

        # Cycle tracking
        self.seal_unseal_cycles = 0           # number of seal/unseal cycles
        self.unseal_events: List[int] = []     # steps at which unsealing occurred
        self.reseal_events: List[int] = []    # steps at which re-sealing occurred
        self.cycle_hw_history: List[List[float]] = []  # HW per cycle segment
        self._cycle_hw_buffer: List[float] = []
        self.unseal_history: List[Dict] = []   # detailed unseal event records
        self._order_history: List[float] = []  # order (HW/N) over time

        if alpha > 1e-6:
            print(f"[DynamicThresholdEvolver] alpha={alpha:.4f}, "
                  f"theta_min={self.theta_min} (ratio={theta_min_ratio:.2f})")

    def _reset_constraints_seal(self, step: int):
        """Force-unseal by resetting constraint sealing state."""
        # Reset sealing flag
        self.constraints.sealed = False
        # Reset sealed bits (unfreeze everything)
        self.constraints.sealed_bits = set()
        # Reset unique active tracking so fresh sealing can occur
        self.constraints.total_unique_active = set()
        # Also clear the active_bits dict so sliding window is fresh
        self.constraints.active_bits = {}
        # Reset the evolver's seal trigger so post-seal logic can re-fire
        self._seal_triggered = False
        # Reset seal_step to allow detecting the next seal
        self.seal_step = -1

        # Record
        self.seal_unseal_cycles += 1
        self.unseal_events.append(step)
        if self._cycle_hw_buffer:
            self.cycle_hw_history.append(self._cycle_hw_buffer.copy())
            self._cycle_hw_buffer = []

        # Avoid infinite rapid seal/unseal cycles — enforce a cooldown
        # by temporarily raising sealing_activation_threshold
        self.constraints.sealing_activation_threshold = max(
            int(0.85 * self.N), 30
        )

    def _step_callback_with_dt(self, step: int, state: torch.Tensor,
                                snapshot: SpatialSnapshot,
                                constraints: AxiomConstraints):
        """Callback that implements dynamic threshold logic."""
        if self.dt_alpha <= 1e-6:
            # Baseline: no dynamic threshold
            return

        current_hw = int(state.sum().item())
        order = current_hw / self.N
        self._order_history.append(order)

        # Track HW during sealed phase
        if constraints.sealed:
            self._cycle_hw_buffer.append(current_hw)

            # Decay the threshold
            # θ(t+1) = max(θ_min, θ(t) - α * (1 - order))
            decay = self.dt_alpha * max(0.0, 1.0 - order)
            self.current_threshold = max(
                self.theta_min,
                self.current_threshold - decay
            )

            # Unseal condition: HW significantly below the decaying threshold
            # OR sustained silence (no change for many steps)
            if self.current_threshold <= self.theta_min + 2:
                # Threshold has decayed to minimum — check if HW is low enough
                # HW must be below N * 0.7 to avoid immediate re-seal
                if current_hw < int(self.N * 0.7):
                    print(f"  [DT] Unseal at step {step}: HW={current_hw}, "
                          f"θ={self.current_threshold:.1f}, cycle={self.seal_unseal_cycles+1}")
                    self._reset_constraints_seal(step)

    def run(self,
            initial_state=None,
            verbose=True,
            step_callback=None,
            post_seal_callback=None):
        if self.dt_alpha <= 1e-6:
            return super().run(
                initial_state=initial_state,
                verbose=verbose,
                step_callback=step_callback,
                post_seal_callback=post_seal_callback,
            )

        # Reset tracking state for fresh run
        self.seal_unseal_cycles = 0
        self.unseal_events = []
        self.reseal_events = []
        self.cycle_hw_history = []
        self._cycle_hw_buffer = []
        self.unseal_history = []
        self._order_history = []
        self.current_threshold = self.N

        orig_cb = step_callback

        def _combined_callback(step, state, snapshot, constraints):
            self._step_callback_with_dt(step, state, snapshot, constraints)
            if orig_cb is not None:
                orig_cb(step, state, snapshot, constraints)

        result = super().run(
            initial_state=initial_state,
            verbose=verbose,
            step_callback=_combined_callback,
            post_seal_callback=post_seal_callback,
        )

        # Save cycle info
        if self._cycle_hw_buffer:
            self.cycle_hw_history.append(self._cycle_hw_buffer.copy())

        result['dt_cycles'] = self.seal_unseal_cycles
        result['dt_unseal_events'] = self.unseal_events
        result['dt_reseal_events'] = self.reseal_events
        result['dt_cycle_hw_histories'] = [list(h) for h in self.cycle_hw_history]
        result['dt_final_threshold'] = self.current_threshold
        result['dt_theta_min'] = self.theta_min

        return result


# ============================================================
# Experiment configs
# ============================================================

# Based on theoretical analysis:
# alpha = decay rate, theta_min_ratio = minimum threshold as fraction of N
ALPHA_CONFIGS = [
    {'alpha': 0.0,   'theta_min_ratio': 1.0, 'label': 'baseline'},      # no decay
    {'alpha': 0.01,  'theta_min_ratio': 0.7, 'label': 'a01_weak'},
    {'alpha': 0.05,  'theta_min_ratio': 0.5, 'label': 'a03_medium'},
    {'alpha': 0.10,  'theta_min_ratio': 0.4, 'label': 'a05_strong'},
    {'alpha': 0.20,  'theta_min_ratio': 0.3, 'label': 'a07_aggressive'},
    {'alpha': 0.50,  'theta_min_ratio': 0.2, 'label': 'a09_max'},
]

N = 48
L0_STEPS = 3000
L1_STEPS = 2000
SAMPLE_INTERVAL = 25
N_RUNS = 5

# L0 needs enough post_seal_steps for unsealing cycles
L0_POST_SEAL_STEPS = 5000  # extra steps for unsealing dynamics


# ============================================================
# Single trial
# ============================================================

@dataclass
class ExperimentResult:
    config_label: str = ''
    alpha: float = 0.0
    theta_min_ratio: float = 1.0
    trial: int = 0
    l0_sealed: bool = False
    l0_seal_step: int = -1
    l0_hw_final: int = 0
    l0_hw_history: List[int] = field(default_factory=list)
    l0_n_clusters: int = 0
    l0_cluster_sizes: List[int] = field(default_factory=list)
    dt_cycles: int = 0
    dt_unseal_events: List[int] = field(default_factory=list)
    dt_final_threshold: float = 0.0
    l1_sealed: bool = False
    l1_seal_step: int = -1
    l1_hw_final: int = 0
    l1_hw_history: List[int] = field(default_factory=list)
    l1_reflection: float = 0.0
    l1_structure_entropy: float = 0.0
    elapsed_sec: float = 0.0
    error: Optional[str] = None
    # Extra per-cycle L1 results (if cycles produced different L0 configs)
    cycle_l1_results: List[Dict] = field(default_factory=list)


def compute_reflection(l0_result: Dict, l1_result: Dict) -> float:
    """Compute how well L1 structure reflects L0's cluster structure."""
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


def compute_entropy(l0_result: Dict, l1_result: Dict) -> float:
    """Compute normalized structure entropy of L1 relative to L0."""
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


def run_single_trial(alpha: float, theta_min_ratio: float,
                     trial_idx: int = 0, label: str = '') -> ExperimentResult:
    result = ExperimentResult(
        config_label=label, alpha=alpha,
        theta_min_ratio=theta_min_ratio, trial=trial_idx,
    )
    t0 = time.time()

    try:
        # Phase 1: L0 evolution with dynamic threshold
        l0_evolver = DynamicThresholdEvolver(
            N=N,
            total_steps=L0_STEPS,
            post_seal_steps=L0_POST_SEAL_STEPS,
            sample_interval=SAMPLE_INTERVAL,
            device='cpu',
            alpha=alpha,
            theta_min_ratio=theta_min_ratio,
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

        # Phase 1.5: Record dynamic threshold tracking
        result.dt_cycles = l0_result.get('dt_cycles', 0)
        result.dt_unseal_events = l0_result.get('dt_unseal_events', [])
        result.dt_final_threshold = l0_result.get('dt_final_threshold', 0.0)

        if not result.l0_sealed:
            result.error = 'L0 did not seal (final state)'
            result.elapsed_sec = time.time() - t0
            return result

        # Phase 2: L0 -> L1 constraint mapping
        mapper = CrossLayerMapper(N0=N, N1=N, device='cpu')
        l1_constraints = mapper.map_from_l0_result(
            l0_evolver=l0_evolver, l0_result=l0_result,
        )

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
        result.l1_reflection = compute_reflection(l0_result, l1_result)
        result.l1_structure_entropy = compute_entropy(l0_result, l1_result)

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

def run_experiment_for_config(alpha: float, theta_min_ratio: float,
                              label: str,
                              n_runs: int = N_RUNS) -> List[ExperimentResult]:
    print(f"\n{'=' * 50}")
    print(f"Config: {label} (alpha={alpha:.4f}, θ_min_ratio={theta_min_ratio:.2f})")
    results = []
    for trial in range(n_runs):
        print(f"  Trial {trial+1}/{n_runs}...", end=' ', flush=True)
        r = run_single_trial(alpha, theta_min_ratio, trial, label)
        results.append(r)
        cyc = r.dt_cycles
        print(f"L0_seal={r.l0_sealed}, L1_seal={r.l1_sealed}, "
              f"cycles={cyc}, unseal={r.dt_unseal_events}, "
              f"reflection={r.l1_reflection:.3f} ({r.elapsed_sec:.1f}s)")
        if r.error:
            print(f"    !! {r.error}")
    return results


def analyze_results(all_results: Dict[str, List[ExperimentResult]]):
    print(f"\n{'=' * 70}")
    print("EXP_176 STATISTICAL SUMMARY - Dynamic Threshold (Path C1)")
    print(f"{'=' * 70}")
    print(f"  N={N}, L0_steps={L0_STEPS}, L0_post_seal={L0_POST_SEAL_STEPS}, L1_steps={L1_STEPS}")
    print(f"  Configs: {len(all_results)}, Total trials: "
          f"{sum(len(v) for v in all_results.values())}")
    print(f"  Expected runtime: ~{(L0_STEPS + L0_POST_SEAL_STEPS + L1_STEPS) * len(all_results) * N_RUNS / 10000:.0f}s")
    print(f"{'=' * 70}")

    for label, results in all_results.items():
        valid = [r for r in results if not r.error]
        if not valid:
            print(f"\n  {label}: No valid trials")
            continue

        l0_sealed = [r for r in valid if r.l0_sealed]
        print(f"\n  {label} (α={results[0].alpha:.4f}, θ_min={results[0].theta_min_ratio:.2f}):")
        print(f"    L0 seal: {len(l0_sealed)}/{len(valid)} "
              f"({len(l0_sealed)/len(valid)*100:.0f}%)")

        if l0_sealed:
            steps = [r.l0_seal_step for r in l0_sealed]
            hw = [r.l0_hw_final for r in l0_sealed]
            nc = [r.l0_n_clusters for r in l0_sealed]
            print(f"    L0 seal step: {np.mean(steps):.1f}+-{np.std(steps):.1f}")
            print(f"    L0 HW final:  {np.mean(hw):.1f}+-{np.std(hw):.1f}")
            print(f"    L0 clusters:  {np.mean(nc):.1f}+-{np.std(nc):.1f}")

            # Dynamic threshold cycles
            cycles = [r.dt_cycles for r in l0_sealed]
            n_unseal = [len(r.dt_unseal_events) for r in l0_sealed]
            print(f"    DT cycles:    {np.mean(cycles):.2f}+-{np.std(cycles):.2f} "
                  f"[min={min(cycles)}, max={max(cycles)}]")
            print(f"    DT unseals:   {np.mean(n_unseal):.1f}+-{np.std(n_unseal):.1f}")
            unseal_steps_all = []
            for r in l0_sealed:
                unseal_steps_all.extend(r.dt_unseal_events)
            if unseal_steps_all:
                print(f"    Unseal steps: {unseal_steps_all}")
            else:
                print(f"    Unseal steps: (none)")

        l1_sealed = [r for r in valid if r.l1_sealed]
        if l1_sealed:
            print(f"    L1 seal: {len(l1_sealed)}/{len(valid)} ({len(l1_sealed)/len(valid)*100:.0f}%)")
            steps = [r.l1_seal_step for r in l1_sealed]
            hw = [r.l1_hw_final for r in l1_sealed]
            print(f"    L1 seal step: {np.mean(steps):.1f}+-{np.std(steps):.1f}")
            print(f"    L1 HW final:  {np.mean(hw):.1f}+-{np.std(hw):.1f}")
            scores = [r.l1_reflection for r in l1_sealed]
            print(f"    Reflection:   {np.mean(scores):.3f}+-{np.std(scores):.3f}")
            ents = [r.l1_structure_entropy for r in l1_sealed]
            print(f"    Struct entropy: {np.mean(ents):.3f}+-{np.std(ents):.3f}")

        # Summary of cycle distribution
        num_unseal = sum(len(r.dt_unseal_events) for r in valid)
        num_any_cycle = sum(1 for r in valid if r.dt_cycles > 0)
        print(f"    Trials with unsealing: {num_any_cycle}/{len(valid)} "
              f"({num_any_cycle/len(valid)*100:.0f}%)")
        print(f"    Total unseal events: {num_unseal}")


def save_results(all_results: Dict[str, List[ExperimentResult]], timestamp: str):
    results_dir = PROJECT_ROOT / 'experiments' / 'results'
    results_dir.mkdir(exist_ok=True)
    serializable = {}
    for label, results in all_results.items():
        serializable[label] = []
        for r in results:
            serializable[label].append({
                'config_label': r.config_label,
                'alpha': r.alpha,
                'theta_min_ratio': r.theta_min_ratio,
                'trial': r.trial,
                'l0_sealed': r.l0_sealed,
                'l0_seal_step': r.l0_seal_step,
                'l0_hw_final': r.l0_hw_final,
                'l0_n_clusters': r.l0_n_clusters,
                'dt_cycles': r.dt_cycles,
                'dt_unseal_events': r.dt_unseal_events,
                'dt_final_threshold': r.dt_final_threshold,
                'l1_sealed': r.l1_sealed,
                'l1_seal_step': r.l1_seal_step,
                'l1_hw_final': r.l1_hw_final,
                'l1_reflection': r.l1_reflection,
                'l1_structure_entropy': r.l1_structure_entropy,
                'elapsed_sec': r.elapsed_sec,
                'error': r.error,
            })
    result_file = results_dir / f'exp_176_results_{timestamp}.json'
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {result_file}")
    return result_file


# ============================================================
# Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='exp_176: Dynamic Sealing Threshold (Phase 16 Path C1)'
    )
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
    print("exp_176 -- Phase 16 Path C1: Dynamic Sealing Threshold")
    print("=" * 70)
    print(f"  N={N}, L0_steps={L0_STEPS}, L0_post_seal={L0_POST_SEAL_STEPS}")
    print(f"  L1_steps={L1_STEPS}, sample_interval={SAMPLE_INTERVAL}")
    print(f"  n_runs={n_runs}")
    print(f"  Configs: {[c['label'] for c in configs_to_run]}")
    print(f"  Total experiments: {len(configs_to_run) * n_runs}")
    print(f"  Expected runtime: ~{(L0_STEPS + L0_POST_SEAL_STEPS + L1_STEPS) * len(configs_to_run) * n_runs // 10000:.0f}s")
    print("=" * 70)

    t_start = time.time()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    all_results: Dict[str, List[ExperimentResult]] = {}

    for cfg in configs_to_run:
        results = run_experiment_for_config(
            alpha=cfg['alpha'],
            theta_min_ratio=cfg['theta_min_ratio'],
            label=cfg['label'],
            n_runs=n_runs,
        )
        all_results[cfg['label']] = results

    total_elapsed = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"{'=' * 70}")
    analyze_results(all_results)
    save_results(all_results, timestamp)


if __name__ == '__main__':
    main()