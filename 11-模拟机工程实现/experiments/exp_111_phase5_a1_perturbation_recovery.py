"""
experiments/exp_111_phase5_a1_perturbation_recovery.py

Phase 5 Track A1: Narrative Continuity Interruption Experiment (v4)

Memory-optimized: runs incrementally, saves after each run.
Resumes from previous results automatically.

Invoke modes:
  Batch:  python exp_111_phase5_a1_perturbation_recovery.py
  Single: python exp_111_phase5_a1_perturbation_recovery.py <seed> <pert_type>
"""

import sys
import os
import gc
import time
import json
import glob
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.return_flow_channel import ReturnFlowChannel
from engine.unsealing_mechanism import UnsealingMechanism
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.minimal_self_detector import MinimalSelfDetector
from engine.global_bias_constraint import GlobalBiasConstraint
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from models.narrative_self import (
    NarrativeRecursionOperator, NarrativeLevel, AdaptiveMomentumConnector,
    NarrativeNode, CausalChain, CIVRateLimiter,
)
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.six_threshold_detector import SixThresholdDetector
from engine.cross_scale_coupling import (
    CrossScaleCoupling, DEFAULT_CROSS_SCALE_COUPLING_CONFIG,
)
from engine.narrative_self_emergence import (
    NarrativeSelfEmergence, DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG,
)


P5_CSC_CONFIG = {
    'topdown_max_constraint_strength': 0.10, 'topdown_min_constraint_strength': 0.01,
    'topdown_response_delay': 20, 'topdown_decay_rate': 0.98, 'topdown_propagation_depth': 2,
    'topdown_stability_threshold': 0.05, 'emergence_min_stability_steps': 50,
    'emergence_stability_threshold': 0.6, 'emergence_min_odi': 0.25, 'emergence_cooldown_steps': 30,
    'narrative_bridge_window': 100, 'narrative_min_coherence': 0.2, 'narrative_integration_rate': 0.05,
    'csci_alpha': 0.4, 'csci_beta': 0.3, 'csci_gamma': 0.3,
}


class CIVRateLimiterV2P1F(CIVRateLimiter):
    def __init__(self):
        super().__init__(window_size=50, max_civ_rate=0.12, cooldown_steps=12)
        self.min_civ_guarantee = 3
    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            if self._total_civ_seen < self.min_civ_guarantee: return level
            if self.should_downgrade(step):
                self._total_downgrades += 1
                return NarrativeLevel.INSTITUTIONAL
        return level

class MomentumNarrativeOperatorV4P1F(NarrativeRecursionOperator):
    def __init__(self):
        from models.narrative_self import NarrativeFilter, NarrativeNamer, NarrativeActionizer, NarrativeVerifier
        self.filter = NarrativeFilter(magnitude_threshold=0.02)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(strength_threshold=0.1, momentum_decay=0.95, momentum_bonus=0.3)
        self.actionizer = NarrativeActionizer(bias_dimension=128)
        self.verifier = NarrativeVerifier(consistency_threshold=0.3)
        self.narrative_decay_rate = 0.9
        self._records = []; self._active_narratives = {}; self._record_count = 0
        self._total_actions = 0; self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F()
    def get_momentum_stats(self): return self.connector.get_cache_stats()
    def get_current_momentum_bonus(self): return self.connector.get_momentum_bonus()


def build_evolver(N0, steps, sample_interval, gbc_soft_nudge, csc_config=None):
    return_flow_channel = ReturnFlowChannel(anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    unsealing_mechanism = UnsealingMechanism(l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40, l2_stability_threshold=0.55)
    pre_subjectivity = PreSubjectivityConvergence(coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True)
    odi = OrganizationalDensityIndex(temporal_window=10, densification_threshold=0.005, use_refined_zones=True)
    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70, 'asymmetry_window': 10,
        'asymmetry_threshold': 0.15, 'min_parts': 3, 'history_window': 8, 'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8, 'self_reference_threshold': 0.05,
        'baseline_correlation_threshold': 0.2, 'msi_activation_threshold': 0.20, 'msi_emergence_threshold': 0.35,
        'min_active_conditions': 1})
    gbc = GlobalBiasConstraint(coherence_threshold=0.5, balance_threshold=0.3, min_mechanisms_required=4, geometric_weighting=True)
    narrative = MomentumNarrativeOperatorV4P1F()
    anticipatory = AnticipatoryBiasEngine(memory=PersistentBiasMemory(), config={'default_horizon': 5, 'learning_rate': 0.01})
    counterfactual = CounterfactualEngine(config={'divergence_threshold': 0.1, 'max_branches': 4})
    six_threshold = SixThresholdDetector()
    csc_cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
    if csc_config: csc_cfg.update(csc_config)
    csc = CrossScaleCoupling(config=csc_cfg)
    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    return HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval, max_layers=1,
        p1_eval_interval=sample_interval, phase2_verbose=False, phase3_verbose=False, phase4_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi, six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism, return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity, minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory, counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative, global_bias_constraint=gbc, gbc_soft_nudge=gbc_soft_nudge,
        cross_scale_coupling=csc, narrative_self_emergence=nse,
        adaptive_momentum_controller=None, institutional_layer_protector=None)


def extract_step_metrics(step_results):
    metrics = {'nsi_vals': [], 'nsi_active': [], 'continuity_vals': [], 'depth_vals': [],
               'tp_vals': [], 'csci_vals': [], 'td_vals': [], 'civ_events': []}
    for sr in step_results:
        nse = sr.get('narrative_self_emergence', {})
        if nse:
            metrics['nsi_vals'].append(nse.get('nsi', 0.0))
            metrics['nsi_active'].append(nse.get('nsi_active', False))
            metrics['continuity_vals'].append(nse.get('continuity_score', 0.0))
            metrics['depth_vals'].append(nse.get('self_history_depth', 0.0))
            metrics['tp_vals'].append(nse.get('n_turning_points', 0))
        csc = sr.get('cross_scale_coupling', {})
        if csc:
            metrics['csci_vals'].append(csc.get('csci', 0.0))
            metrics['td_vals'].append(csc.get('topdown_n_active', 0))
        narr_info = sr.get('narrative_recursion', {})
        if narr_info:
            level = narr_info.get('narrative_level', 'MINI')
            metrics['civ_events'].append(1 if level == 'CIVILIZATION' else 0)
    return metrics


def apply_perturbation_type1(evolver, flip_fraction=0.05):
    layer = evolver.hierarchy.get_layer(0)
    state = layer.state.clone()
    n_bits = state.shape[0]
    n_flip = max(1, int(n_bits * flip_fraction))
    indices = torch.randperm(n_bits)[:n_flip]
    for idx in indices:
        state[idx] = 1.0 - state[idx]
    layer.state = state
    return {'type': 1, 'n_flipped': n_flip, 'indices': indices.tolist()}

def apply_perturbation_type2(evolver, reset_fraction=0.5):
    if evolver.unsealing_mechanism is None:
        return {'type': 2, 'n_reset': 0, 'reason': 'no unsealing mechanism'}
    levels = evolver.unsealing_mechanism._unsealing_levels
    if not levels:
        return {'type': 2, 'n_reset': 0, 'reason': 'no unsealed structures'}
    n_reset = max(1, int(len(levels) * reset_fraction))
    sids = list(levels.keys())
    np.random.shuffle(sids)
    for sid in sids[:n_reset]:
        levels[sid] = 0
    return {'type': 2, 'n_reset': n_reset}

def apply_perturbation_type3(evolver):
    if evolver.narrative_self_emergence is None:
        return {'type': 3, 'reason': 'no NSE mechanism'}
    evolver.narrative_self_emergence.reset()
    return {'type': 3, 'reset': True}


def run_single_seed(seed, perturbation_type, N0=72, total_steps=2000, perturbation_step=1000,
                    sample_interval=10, gbc_soft_nudge=0.2):
    pre_steps = perturbation_step
    post_steps = total_steps - perturbation_step

    evolver = build_evolver(N0, pre_steps, sample_interval, gbc_soft_nudge, P5_CSC_CONFIG)
    torch.manual_seed(seed)
    np.random.seed(seed)

    print(f"  Phase 1: {pre_steps} steps to maturity...", flush=True)
    result_pre = evolver.run(verbose=False)

    layer_0 = result_pre.get('layer_results', [{}])[0]
    pre_step_results = layer_0.get('phase2_step_results', [])
    pre_metrics = extract_step_metrics(pre_step_results)
    pre_nsi_mean = float(np.mean(pre_metrics['nsi_vals'][-50:])) if pre_metrics['nsi_vals'] else 0.0
    pre_nsi_max = float(np.max(pre_metrics['nsi_vals'])) if pre_metrics['nsi_vals'] else 0.0
    print(f"  Pre: nsi_mean={pre_nsi_mean:.4f}, nsi_max={pre_nsi_max:.4f}", flush=True)

    if perturbation_type == 1:
        pert_info = apply_perturbation_type1(evolver)
    elif perturbation_type == 2:
        pert_info = apply_perturbation_type2(evolver)
    elif perturbation_type == 3:
        pert_info = apply_perturbation_type3(evolver)
    else:
        pert_info = {'type': 0}
    print(f"  Perturbation: {pert_info}", flush=True)

    n_pre = len(pre_step_results)
    print(f"  Phase 2: {post_steps} steps post-perturbation...", flush=True)
    evolver._run_layer(layer_id=0, steps=post_steps, verbose=False)

    if 0 in evolver._phase2_layer_results:
        post_step_results = evolver._phase2_layer_results[0][n_pre:]
    else:
        post_step_results = []

    post_metrics = extract_step_metrics(post_step_results)
    post_nsi_vals = post_metrics['nsi_vals']

    recovery_steps = -1
    for i, v in enumerate(post_nsi_vals):
        if v >= 0.5:
            recovery_steps = i
            break

    post_nsi_max = float(np.max(post_nsi_vals)) if post_nsi_vals else 0.0
    post_nsi_final = float(post_nsi_vals[-1]) if post_nsi_vals else 0.0
    recovered = recovery_steps >= 0

    print(f"  Post: nsi_max={post_nsi_max:.4f}, recovery_steps={recovery_steps}, recovered={recovered}", flush=True)

    return {
        'seed': seed, 'perturbation_type': perturbation_type, 'perturbation_info': pert_info,
        'pre_nsi_mean': pre_nsi_mean, 'pre_nsi_max': pre_nsi_max,
        'recovery_steps': recovery_steps, 'recovered': recovered,
        'post_nsi_max': post_nsi_max, 'post_nsi_final': post_nsi_final,
        'post_nsi_mean': float(np.mean(post_nsi_vals)) if post_nsi_vals else 0.0,
        'n_pre_steps': n_pre, 'n_post_steps': len(post_step_results),
    }


# ─── Configuration ───
ALL_SEEDS = [42, 142, 242, 342]
ALL_TYPES = [0, 1, 2, 3]
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2
FIXED_OUTPUT = os.path.join(PROJECT_ROOT, 'experiments', 'exp_111_results.json')


def load_existing_results():
    """Load results from fixed output file, or from most recent timestamped backup."""
    # Try fixed file first
    if os.path.exists(FIXED_OUTPUT):
        with open(FIXED_OUTPUT, 'r') as f:
            d = json.load(f)
            return d, FIXED_OUTPUT

    # Try most recent timestamped file
    pattern = os.path.join(PROJECT_ROOT, 'experiments', 'exp_111_results_*.json')
    files = sorted(glob.glob(pattern), reverse=True)
    if files:
        with open(files[0], 'r') as f:
            d = json.load(f)
            return d, files[0]

    return None, None


def run_batch():
    """Run all seeds x types incrementally, saving after each run."""
    existing, src_path = load_existing_results()

    all_results = []
    if existing:
        all_results = existing.get('results', {}).get('per_run', [])
        print(f"Loaded {len(all_results)} existing results from {src_path}")

    done = set((r['seed'], r['perturbation_type']) for r in all_results if 'error' not in r)
    total = len(ALL_SEEDS) * len(ALL_TYPES)
    run_idx = len(done)

    print(f"exp_111 v4: {run_idx}/{total} done, {total - run_idx} remaining")

    for pert_type in ALL_TYPES:
        for seed in ALL_SEEDS:
            if (seed, pert_type) in done:
                type_name = {0: 'control', 1: 'mild', 2: 'moderate', 3: 'severe'}[pert_type]
                print(f"  Skipping seed={seed} type={type_name} (done)")
                continue

            run_idx += 1
            gc.collect()
            type_name = {0: 'control', 1: 'mild', 2: 'moderate', 3: 'severe'}[pert_type]
            print(f"\n[{run_idx}/{total}] seed={seed} type={type_name}({pert_type})")

            try:
                result = run_single_seed(seed, pert_type)
                all_results.append(result)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                import traceback
                traceback.print_exc()
                all_results.append({'seed': seed, 'perturbation_type': pert_type, 'error': str(e)})

            # Save after each run (to fixed file + timestamped backup)
            output = {
                'experiment': 'exp_111_phase5_a1_perturbation_recovery',
                'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
                'v': 4,
                'architecture': 'CSC+NSE (simplified)',
                'config': {'N0': 72, 'total_steps': 2000, 'perturbation_step': 1000,
                           'seeds': ALL_SEEDS, 'perturbation_types': {0: 'control', 1: 'mild', 2: 'moderate', 3: 'severe'},
                           'sample_interval': SAMPLE_INTERVAL, 'gbc_soft_nudge': GBC_SOFT_NUDGE},
                'results': {'per_run': all_results},
            }
            with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            # Also save timestamped backup
            ts_path = os.path.join(PROJECT_ROOT, 'experiments', f"exp_111_results_{output['timestamp']}.json")
            with open(ts_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"  Saved to {FIXED_OUTPUT}")

            gc.collect()

    # Final analysis
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    for pert_type in ALL_TYPES:
        type_results = [r for r in all_results if r.get('perturbation_type') == pert_type and 'error' not in r]
        if not type_results:
            continue
        type_name = {0: 'control', 1: 'mild', 2: 'moderate', 3: 'severe'}[pert_type]
        pre_nsi = [r['pre_nsi_mean'] for r in type_results]
        post_nsi = [r['post_nsi_max'] for r in type_results]
        recovered = [r for r in type_results if r['recovered']]
        recovery_steps = [r['recovery_steps'] for r in recovered]

        print(f"\n  {type_name} (n={len(type_results)}):")
        print(f"    Pre NSI: mean={np.mean(pre_nsi):.4f}, std={np.std(pre_nsi):.4f}")
        print(f"    Post NSI max: mean={np.mean(post_nsi):.4f}, std={np.std(post_nsi):.4f}")
        print(f"    Recovered: {len(recovered)}/{len(type_results)}")
        if recovery_steps:
            print(f"    Recovery steps: mean={np.mean(recovery_steps):.1f}")
        for r in type_results:
            print(f"    seed={r['seed']}: pre={r['pre_nsi_mean']:.3f} post={r['post_nsi_max']:.3f} "
                  f"recov={r['recovery_steps']} ok={r['recovered']}")

    # Evaluate hypotheses
    t1 = [r for r in all_results if r.get('perturbation_type') == 1 and 'error' not in r]
    t2 = [r for r in all_results if r.get('perturbation_type') == 2 and 'error' not in r]
    t3 = [r for r in all_results if r.get('perturbation_type') == 3 and 'error' not in r]

    h21 = len([r for r in t1 if r['recovered'] and r['recovery_steps'] <= 200]) >= len(t1) * 0.75 if t1 else False
    h22 = len([r for r in t2 if r['recovered'] and r['recovery_steps'] <= 500]) >= len(t2) * 0.75 if t2 else False
    h23 = len([r for r in t3 if r['post_nsi_max'] < r['pre_nsi_mean'] * 0.8]) >= len(t3) * 0.5 if t3 else False

    print(f"\n  H21 (mild recovery): {'PASS' if h21 else 'FAIL'}")
    print(f"  H22 (moderate recovery): {'PASS' if h22 else 'FAIL'}")
    print(f"  H23 (severe irreversibility): {'PASS' if h23 else 'FAIL'}")

    return FIXED_OUTPUT


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        seed = int(sys.argv[1])
        pert_type = int(sys.argv[2])
        result = run_single_seed(seed, pert_type)
        print(json.dumps(result, indent=2))
    else:
        run_batch()
