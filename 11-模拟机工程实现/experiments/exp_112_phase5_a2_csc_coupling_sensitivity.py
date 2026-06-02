"""
experiments/exp_112_phase5_a2_csc_coupling_sensitivity.py

Phase 5 Track A2: CSC Coupling Strength Sensitivity Test

Purpose: Systematically vary the CSC top-down coupling strength to identify
the critical coupling threshold (H24) and over-coupling damage point (H25).

Method:
  - Sweep topdown_max_constraint_strength across 7 values:
    [0.05, 0.10 (baseline), 0.20, 0.30, 0.50, 0.70, 0.90]
  - 4 seeds per config: [42, 142, 242, 342]
  - 1600 steps per run (same as Phase 4 baseline)
  - Total: 7 configs x 4 seeds = 28 runs

Architecture: CSC+NSE (simplified, no AMC/ILP — same as Track A1)
  - Only the topdown_max_constraint_strength varies across configs
  - All other CSC/NSE parameters fixed at P5_CSC_CONFIG baseline

Hypotheses:
  H24 (CSC critical coupling): Exists threshold c* in [0.05, 0.30] where
    topdown_max_constraint_strength < c* causes H7 (CSCI) and H8 (TopDown) to fail.
    Rationale: Too-weak coupling cannot establish cross-scale coherence.

  H25 (over-coupling damage): At strength > 0.70, H1 (NSI max) and H2 (NSI active)
    fail because low-level autonomy is suppressed by excessive top-down constraint.
    Rationale: Excessive top-down pressure prevents bottom-up narrative emergence.

Invoke modes:
  Batch:  python exp_112_phase5_a2_csc_coupling_sensitivity.py
  Single: python exp_112_phase5_a2_csc_coupling_sensitivity.py <config_idx> <seed>
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


# ─── Baseline CSC config (same as P5 / exp_111) ───
P5_BASE_CSC_CONFIG = {
    'topdown_max_constraint_strength': 0.10,
    'topdown_min_constraint_strength': 0.01,
    'topdown_response_delay': 20,
    'topdown_decay_rate': 0.98,
    'topdown_propagation_depth': 2,
    'topdown_stability_threshold': 0.05,
    'emergence_min_stability_steps': 50,
    'emergence_stability_threshold': 0.6,
    'emergence_min_odi': 0.25,
    'emergence_cooldown_steps': 30,
    'narrative_bridge_window': 100,
    'narrative_min_coherence': 0.2,
    'narrative_integration_rate': 0.05,
    'csci_alpha': 0.4,
    'csci_beta': 0.3,
    'csci_gamma': 0.3,
}


# ─── Coupling strength sweep values ───
COUPLING_STRENGTHS = [0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 0.90]

# ─── Config labels ───
CONFIG_LABELS = [
    f"c{s:.2f}" for s in COUPLING_STRENGTHS
]


def make_csc_config(strength):
    """Create a CSC config with the given topdown_max_constraint_strength."""
    cfg = dict(P5_BASE_CSC_CONFIG)
    cfg['topdown_max_constraint_strength'] = strength
    return cfg


class CIVRateLimiterV2P1F(CIVRateLimiter):
    def __init__(self):
        super().__init__(window_size=50, max_civ_rate=0.12, cooldown_steps=12)
        self.min_civ_guarantee = 3

    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            if self._total_civ_seen < self.min_civ_guarantee:
                return level
            if self.should_downgrade(step):
                self._total_downgrades += 1
                return NarrativeLevel.INSTITUTIONAL
        return level


class MomentumNarrativeOperatorV4P1F(NarrativeRecursionOperator):
    def __init__(self):
        from models.narrative_self import NarrativeFilter, NarrativeNamer
        from models.narrative_self import NarrativeActionizer, NarrativeVerifier
        self.filter = NarrativeFilter(magnitude_threshold=0.02)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(
            strength_threshold=0.1, momentum_decay=0.95, momentum_bonus=0.3)
        self.actionizer = NarrativeActionizer(bias_dimension=128)
        self.verifier = NarrativeVerifier(consistency_threshold=0.3)
        self.narrative_decay_rate = 0.9
        self._records = []
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F()

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


def build_evolver(N0, steps, sample_interval, gbc_soft_nudge, csc_config):
    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40, l2_stability_threshold=0.55)
    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True)
    odi = OrganizationalDensityIndex(
        temporal_window=10, densification_threshold=0.005, use_refined_zones=True)
    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3, 'history_window': 8, 'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8,
        'self_reference_threshold': 0.05, 'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20, 'msi_emergence_threshold': 0.35,
        'min_active_conditions': 1})
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5, balance_threshold=0.3,
        min_mechanisms_required=4, geometric_weighting=True)
    narrative = MomentumNarrativeOperatorV4P1F()
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01})
    counterfactual = CounterfactualEngine(
        config={'divergence_threshold': 0.1, 'max_branches': 4})
    six_threshold = SixThresholdDetector()

    csc_cfg = make_csc_config(csc_config)
    csc = CrossScaleCoupling(config=csc_cfg)

    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    return HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=1, p1_eval_interval=sample_interval,
        phase2_verbose=False, phase3_verbose=False, phase4_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi, six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism, return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity, minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory, counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative, global_bias_constraint=gbc,
        gbc_soft_nudge=gbc_soft_nudge,
        cross_scale_coupling=csc, narrative_self_emergence=nse,
        adaptive_momentum_controller=None, institutional_layer_protector=None)


def extract_step_metrics(step_results):
    """Extract metrics from step results (same as exp_111)."""
    metrics = {
        'nsi_vals': [], 'nsi_active': [], 'continuity_vals': [],
        'depth_vals': [], 'tp_vals': [], 'csci_vals': [],
        'td_vals': [], 'civ_events': [],
    }
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


def safe_mean(vals):
    return float(np.mean(vals)) if vals else 0.0


def safe_max(vals):
    return float(np.max(vals)) if vals else 0.0


def safe_std(vals):
    return float(np.std(vals)) if vals else 0.0


def evaluate_h1h8(metrics):
    """Evaluate H1-H8 from extracted metrics (same thresholds as Phase 4)."""
    nsi_max = safe_max(metrics['nsi_vals'])
    nsi_active_rate = safe_mean(metrics['nsi_active'])
    continuity_mean = safe_mean(metrics['continuity_vals'])
    history_depth_mean = safe_mean(metrics['depth_vals'])
    turning_points = metrics['tp_vals'][-1] if metrics['tp_vals'] else 0
    civ_count = sum(metrics['civ_events'])
    csci_std = safe_std(metrics['csci_vals'])
    topdown_max = int(safe_max(metrics['td_vals']))

    h1 = nsi_max > 0.1
    h2 = nsi_active_rate > 0.3
    h3 = continuity_mean > 0.1
    h4 = history_depth_mean > 0.05 or turning_points > 0
    h5 = 3.0 <= civ_count <= 15.0
    h6 = civ_count >= 2
    h7 = csci_std > 0.005
    h8 = topdown_max > 0

    return {
        'H1': h1, 'H2': h2, 'H3': h3, 'H4': h4,
        'H5': h5, 'H6': h6, 'H7': h7, 'H8': h8,
        'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
        'all_pass': all([h1, h2, h3, h4, h5, h6, h7, h8]),
    }


def run_single(coupling_strength, seed, N0=72, steps=1600, sample_interval=10,
                gbc_soft_nudge=0.2):
    """Run a single seed at a given coupling strength."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    evolver = build_evolver(N0, steps, sample_interval, gbc_soft_nudge,
                            coupling_strength)

    t0 = time.time()
    result = evolver.run(verbose=False)
    elapsed = time.time() - t0

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])
    metrics = extract_step_metrics(step_results)
    h1h8 = evaluate_h1h8(metrics)

    return {
        'seed': seed,
        'coupling_strength': coupling_strength,
        'elapsed': elapsed,
        'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'nsi_max': safe_max(metrics['nsi_vals']),
        'nsi_active_rate': safe_mean(metrics['nsi_active']),
        'continuity_mean': safe_mean(metrics['continuity_vals']),
        'history_depth_mean': safe_mean(metrics['depth_vals']),
        'turning_points': metrics['tp_vals'][-1] if metrics['tp_vals'] else 0,
        'civ_count': sum(metrics['civ_events']),
        'csci_std': safe_std(metrics['csci_vals']),
        'topdown_max': int(safe_max(metrics['td_vals'])),
        'h1h8': h1h8,
    }


# ─── Experiment configuration ───
ALL_SEEDS = [42, 142, 242, 342]
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2
FIXED_OUTPUT = os.path.join(PROJECT_ROOT, 'experiments', 'exp_112_results.json')


def load_existing_results():
    if os.path.exists(FIXED_OUTPUT):
        with open(FIXED_OUTPUT, 'r') as f:
            d = json.load(f)
            return d, FIXED_OUTPUT
    pattern = os.path.join(PROJECT_ROOT, 'experiments', 'exp_112_results_*.json')
    files = sorted(glob.glob(pattern), reverse=True)
    if files:
        with open(files[0], 'r') as f:
            d = json.load(f)
            return d, files[0]
    return None, None


def evaluate_h24_h25(all_results):
    """Evaluate H24 (critical coupling) and H25 (over-coupling damage).

    H24: There exists a critical value c* in [0.05, 0.30] such that
          when topdown_max_constraint_strength < c*, H7 and H8 fail.
    H25: When topdown_max_constraint_strength > 0.70, H1 and H2 fail
          (low-level autonomy suppressed).
    """
    # Group by coupling strength
    by_strength = {}
    for r in all_results:
        s = r['coupling_strength']
        if s not in by_strength:
            by_strength[s] = []
        by_strength[s].append(r)

    # For each strength, compute pass rates for each hypothesis
    strength_summary = {}
    for strength in sorted(by_strength.keys()):
        runs = by_strength[strength]
        n = len(runs)
        h_pass = {f'H{i}': 0 for i in range(1, 9)}
        for r in runs:
            for h, passed in r['h1h8'].items():
                if h in ('n_pass', 'all_pass'):
                    continue
                if passed:
                    h_pass[h] += 1
        strength_summary[strength] = {
            'n_seeds': n,
            'h_pass_rates': {h: v / n for h, v in h_pass.items()},
            'h_pass_counts': h_pass,
        }

    # H24: Check if H7/H8 pass rate drops below 50% at low coupling strengths
    # but is above 50% at higher strengths
    h7_rates = {s: strength_summary[s]['h_pass_rates']['H7']
                for s in sorted(strength_summary.keys())}
    h8_rates = {s: strength_summary[s]['h_pass_rates']['H8']
                for s in sorted(strength_summary.keys())}

    # Find critical threshold: lowest strength where both H7 and H8 pass >= 50%
    critical_threshold = None
    for s in sorted(strength_summary.keys()):
        if strength_summary[s]['h_pass_rates']['H7'] >= 0.5 and \
           strength_summary[s]['h_pass_rates']['H8'] >= 0.5:
            critical_threshold = s
            break

    # H24 passes if there IS a clear threshold separating fail/pass
    h24 = critical_threshold is not None and critical_threshold > min(COUPLING_STRENGTHS)

    # H25: Check if H1/H2 pass rate drops at high coupling (> 0.70)
    low_strengths = [s for s in sorted(strength_summary.keys()) if s <= 0.50]
    high_strengths = [s for s in sorted(strength_summary.keys()) if s > 0.50]

    h1_low = np.mean([strength_summary[s]['h_pass_rates']['H1'] for s in low_strengths]) if low_strengths else 0
    h1_high = np.mean([strength_summary[s]['h_pass_rates']['H1'] for s in high_strengths]) if high_strengths else 0
    h2_low = np.mean([strength_summary[s]['h_pass_rates']['H2'] for s in low_strengths]) if low_strengths else 0
    h2_high = np.mean([strength_summary[s]['h_pass_rates']['H2'] for s in high_strengths]) if high_strengths else 0

    # H25 passes if H1/H2 are significantly worse at high coupling
    h25 = h1_high < h1_low - 0.2 or h2_high < h2_low - 0.2

    return {
        'H24_critical_coupling': {
            'description': 'Exists c* where H7/H8 fail below c*',
            'pass': h24,
            'critical_threshold': critical_threshold,
            'h7_rates': h7_rates,
            'h8_rates': h8_rates,
        },
        'H25_over_coupling_damage': {
            'description': 'H1/H2 degrade at high coupling (>0.50)',
            'pass': h25,
            'h1_low_strength_mean': float(h1_low),
            'h1_high_strength_mean': float(h1_high),
            'h2_low_strength_mean': float(h2_low),
            'h2_high_strength_mean': float(h2_high),
        },
        'strength_summary': strength_summary,
    }


def run_batch():
    """Run all configs x seeds incrementally with resume support."""
    existing, src_path = load_existing_results()

    all_results = []
    if existing:
        all_results = existing.get('results', {}).get('per_run', [])
        print(f"Loaded {len(all_results)} existing results from {src_path}")

    done = set((r['coupling_strength'], r['seed']) for r in all_results if 'error' not in r)
    total = len(COUPLING_STRENGTHS) * len(ALL_SEEDS)
    run_idx = len(done)

    print(f"exp_112: {run_idx}/{total} done, {total - run_idx} remaining")
    print(f"  Coupling strengths: {COUPLING_STRENGTHS}")
    print(f"  Seeds: {ALL_SEEDS}")
    print(f"  Total runs: {total}")

    for strength in COUPLING_STRENGTHS:
        for seed in ALL_SEEDS:
            if (strength, seed) in done:
                print(f"  Skipping strength={strength} seed={seed} (done)")
                continue

            run_idx += 1
            gc.collect()
            print(f"\n[{run_idx}/{total}] strength={strength} seed={seed}")

            try:
                result = run_single(strength, seed)
                all_results.append(result)
                print(f"  Done: nsi_max={result['nsi_max']:.4f}, "
                      f"h1h8={result['h1h8']['n_pass']}/8")
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
                import traceback
                traceback.print_exc()
                all_results.append({
                    'coupling_strength': strength, 'seed': seed, 'error': str(e),
                })

            # Save after each run
            output = {
                'experiment': 'exp_112_phase5_a2_csc_coupling_sensitivity',
                'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
                'v': 1,
                'architecture': 'CSC+NSE (simplified, no AMC/ILP)',
                'config': {
                    'coupling_strengths': COUPLING_STRENGTHS,
                    'seeds': ALL_SEEDS,
                    'N0': 72,
                    'steps': 1600,
                    'sample_interval': SAMPLE_INTERVAL,
                    'gbc_soft_nudge': GBC_SOFT_NUDGE,
                },
                'results': {'per_run': all_results},
            }
            with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            ts_path = os.path.join(
                PROJECT_ROOT, 'experiments',
                f"exp_112_results_{output['timestamp']}.json")
            with open(ts_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"  Saved ({len(all_results)} total)")

            gc.collect()

    # ─── Final analysis ───
    valid = [r for r in all_results if 'error' not in r]
    h24h25 = evaluate_h24_h25(valid)

    print("\n" + "=" * 70)
    print("EXP_112 FINAL RESULTS — CSC Coupling Sensitivity")
    print("=" * 70)

    # Per-strength summary
    for strength in COUPLING_STRENGTHS:
        runs = [r for r in valid if r['coupling_strength'] == strength]
        if not runs:
            continue
        n_pass = [r['h1h8']['n_pass'] for r in runs]
        print(f"\n  strength={strength:.2f} ({len(runs)} seeds):")
        print(f"    H1-H8 pass counts: {n_pass}")
        print(f"    Mean nsi_max: {np.mean([r['nsi_max'] for r in runs]):.4f}")
        print(f"    Mean nsi_active_rate: {np.mean([r['nsi_active_rate'] for r in runs]):.4f}")
        print(f"    Mean csci_std: {np.mean([r['csci_std'] for r in runs]):.4f}")
        print(f"    Mean topdown_max: {np.mean([r['topdown_max'] for r in runs]):.1f}")
        print(f"    Mean civ_count: {np.mean([r['civ_count'] for r in runs]):.1f}")

    # H24/H25
    print("\n" + "-" * 70)
    print("H24 (critical coupling):")
    h24_info = h24h25['H24_critical_coupling']
    print(f"  Result: {'PASS' if h24_info['pass'] else 'FAIL'}")
    print(f"  Critical threshold: {h24_info['critical_threshold']}")
    print(f"  H7 rates: {h24_info['h7_rates']}")
    print(f"  H8 rates: {h24_info['h8_rates']}")

    print("\nH25 (over-coupling damage):")
    h25_info = h24h25['H25_over_coupling_damage']
    print(f"  Result: {'PASS' if h25_info['pass'] else 'FAIL'}")
    print(f"  H1 low-strength mean: {h25_info['h1_low_strength_mean']:.3f}")
    print(f"  H1 high-strength mean: {h25_info['h1_high_strength_mean']:.3f}")
    print(f"  H2 low-strength mean: {h25_info['h2_low_strength_mean']:.3f}")
    print(f"  H2 high-strength mean: {h25_info['h2_high_strength_mean']:.3f}")

    # Save final analysis
    final_output = {
        'experiment': 'exp_112_phase5_a2_csc_coupling_sensitivity',
        'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
        'v': 1,
        'architecture': 'CSC+NSE (simplified, no AMC/ILP)',
        'config': {
            'coupling_strengths': COUPLING_STRENGTHS,
            'seeds': ALL_SEEDS,
            'N0': 72,
            'steps': 1600,
            'sample_interval': SAMPLE_INTERVAL,
            'gbc_soft_nudge': GBC_SOFT_NUDGE,
        },
        'results': {
            'per_run': all_results,
            'h24_h25': h24h25,
        },
    }

    with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    ts_path = os.path.join(
        PROJECT_ROOT, 'experiments',
        f"exp_112_results_{final_output['timestamp']}.json")
    with open(ts_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    print(f"\nFinal results saved to: {FIXED_OUTPUT}")

    return FIXED_OUTPUT


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        config_idx = int(sys.argv[1])
        seed = int(sys.argv[2])
        strength = COUPLING_STRENGTHS[config_idx]
        result = run_single(strength, seed)
        print(json.dumps(result, indent=2))
    else:
        run_batch()
