"""
experiments/exp_114_phase5_b1_layered_narrative.py

Phase 5 Track B1: Layered Narrative Tracking

Purpose: Validate H28 (inter-layer NSI correlation < 0.5) and H29 (L0→L2
    conduction delay 50-200 steps) using the LayerNarrativeTracker.

Method:
  - 8 seeds (same as Phase 4/5 baseline)
  - Single config: coupling_strength=0.10 (P5 baseline), N0=72, steps=2000
  - Total: 8 seeds x 1 config = 8 runs
  - Architecture: CSC+NSE + LayerNarrativeTracker (no AMC/ILP)

Hypotheses:
  H28 (layer narrative independence): Inter-layer NSI Pearson r < 0.5
      Rationale: Each layer (MINI/L0, INSTITUTIONAL/L1, CIVILIZATION/L2)
      should have its own narrative trajectory driven by its own structural
      dynamics, not merely inheriting/echoing another layer's narrative.

  H29 (conduction delay): L0→L2 narrative conduction delay ∈ [50, 200] steps
      Rationale: Changes in L0's difference organization propagate upward
      through L1's institutional constraints before reaching L2's narrative
      self. This structural propagation should take measurable time.

  Also tracks H1-H8 (baseline) to verify Track B1 doesn't break core dynamics.

Invoke modes:
  Batch:  python exp_114_phase5_b1_layered_narrative.py
  Single: python exp_114_phase5_b1_layered_narrative.py <seed>
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
from engine.layer_narrative_tracker import (
    LayerNarrativeTracker, DEFAULT_LAYER_NARRATIVE_CONFIG,
)


# ─── 8 baseline seeds ───
ALL_SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]

# ─── P5 Baseline CSC config (same as exp_111/112/113) ───
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

# ─── Experiment parameters ───
N0 = 72
STEPS = 2000               # B1 uses 2000 steps (per plan)
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.5

FIXED_OUTPUT = os.path.join(
    PROJECT_ROOT, 'experiments',
    'exp_114_b1_results_final.json')


# ─── P5 Baseline LNT config ───
P5_LNT_CONFIG = dict(DEFAULT_LAYER_NARRATIVE_CONFIG)
P5_LNT_CONFIG['continuity_window'] = 100
P5_LNT_CONFIG['stability_window'] = 100
P5_LNT_CONFIG['inter_layer_min_samples'] = 50
P5_LNT_CONFIG['inter_layer_correlation_window'] = 200
P5_LNT_CONFIG['inter_layer_delay_min'] = 50
P5_LNT_CONFIG['inter_layer_delay_max'] = 200
P5_LNT_CONFIG['nsi_alpha'] = 0.4
P5_LNT_CONFIG['nsi_beta'] = 0.3
P5_LNT_CONFIG['nsi_gamma'] = 0.3
P5_LNT_CONFIG['nsi_min_odi'] = 0.3


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


def build_evolver(N0, steps, sample_interval, gbc_soft_nudge, seed):
    """Build HierarchicalEvolver with CSC+NSE+LNT (no AMC/ILP)."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    odi = OrganizationalDensityIndex(
        temporal_window=10, densification_threshold=0.005, use_refined_zones=True)
    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40, l2_stability_threshold=0.55)
    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True)
    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3, 'history_window': 8,
        'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8,
        'self_reference_threshold': 0.05,
        'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20,
        'msi_emergence_threshold': 0.35,
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

    csc = CrossScaleCoupling(config=dict(P5_BASE_CSC_CONFIG))

    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {
        'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    # Track B1: LayerNarrativeTracker
    lnt = LayerNarrativeTracker(config=dict(P5_LNT_CONFIG))

    ev = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=1, p1_eval_interval=sample_interval,
        phase2_verbose=False, phase3_verbose=False, phase4_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi,
        six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism,
        return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity,
        minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory,
        counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative,
        global_bias_constraint=gbc,
        gbc_soft_nudge=gbc_soft_nudge,
        cross_scale_coupling=csc,
        narrative_self_emergence=nse,
        adaptive_momentum_controller=None,
        institutional_layer_protector=None,
        # Phase 5 Track B1
        layer_narrative_tracker=lnt)
    # Store lnt reference for post-hoc analysis
    ev._lnt = lnt
    return ev


def extract_step_metrics(step_results):
    """Extract metrics from step results (same as exp_113)."""
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
            metrics['civ_events'].append(
                1 if level == 'CIVILIZATION' else 0)
    return metrics


def safe_mean(vals):
    return float(np.mean(vals)) if vals else 0.0


def safe_max(vals):
    return float(np.max(vals)) if vals else 0.0


def safe_std(vals):
    return float(np.std(vals)) if vals else 0.0


def evaluate_h1h8(metrics):
    """Evaluate H1-H8 from extracted metrics."""
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
        'nsi_max': nsi_max,
        'nsi_active_rate': nsi_active_rate,
        'continuity_mean': continuity_mean,
        'history_depth_mean': history_depth_mean,
        'turning_points': turning_points,
        'civ_count': civ_count,
        'csci_std': csci_std,
        'topdown_max': topdown_max,
    }


def evaluate_h28_h29(lnt, step_results):
    """Evaluate H28 (layer independence) and H29 (conduction delay)."""
    h28_result = lnt.get_inter_layer_correlation()
    h29_result = lnt.get_conduction_delay()

    # Post-hoc actual conduction delay
    all_nsi_histories_raw = lnt.get_all_nsi_histories()
    actual_delay = compute_actual_conduction_delay(all_nsi_histories_raw)

    # Detailed per-layer NSI stats
    all_nsi_histories = lnt.get_all_nsi_histories()
    per_layer_stats = {}
    for level, history in all_nsi_histories.items():
        if history:
            per_layer_stats[level] = {
                'mean': float(np.mean(history)),
                'std': float(np.std(history)),
                'max': float(np.max(history)),
                'min': float(np.min(history)),
                'final': float(history[-1]) if history else 0.0,
                'n_samples': len(history),
            }
        else:
            per_layer_stats[level] = {
                'mean': 0.0, 'std': 0.0, 'max': 0.0,
                'min': 0.0, 'final': 0.0, 'n_samples': 0,
            }

    # Layer activity profile
    activity_profile = lnt.get_layer_activity_profile()

    result = {
        'H28': {
            'passing': h28_result.passing,
            'pairwise_correlations': h28_result.pairwise_correlations,
            'all_below_threshold': h28_result.all_below_threshold,
            'threshold': h28_result.threshold,
            'n_samples': h28_result.n_samples,
        },
        'H29': {
            'passing': h29_result.passing,
            'l0_to_l2_delay': h29_result.l0_to_l2_delay,
            'l0_to_l1_delay': h29_result.l0_to_l1_delay,
            'l1_to_l2_delay': h29_result.l1_to_l2_delay,
            'delay_mode': h29_result.delay_mode,
            'n_detection_events': h29_result.n_detection_events,
            'reason': h29_result.passing_reason,
        },
        'H29_actual_delay': actual_delay,
        'per_layer_nsi': per_layer_stats,
        'layer_activity': activity_profile,
    }

    return result


def compute_actual_conduction_delay(nsi_histories):
    """
    Post-hoc computation of actual L0->L2 conduction delay.

    Uses the first-derivative method: find when each layer's NSI
    rises above its baseline (first substantial increase after zero).

    Returns dict with first_rise times and delays.
    """
    l0 = nsi_histories.get('MINI', [])
    l2 = nsi_histories.get('CIVILIZATION', [])

    if not l0 or not l2:
        return {'error': 'insufficient_data'}

    def find_first_rise(seq, threshold=0.05):
        """Find first step where NSI crosses above threshold."""
        for i, val in enumerate(seq):
            if val > threshold:
                return i
        return None

    def find_first_deriv_peak(seq, min_gradient=0.02):
        """
        Find first step where the gradient exceeds min_gradient.
        Uses forward difference.
        """
        for i in range(1, len(seq)):
            grad = seq[i] - seq[i-1]
            if grad > min_gradient:
                return i
        return None

    def find_variance_onset(seq, window=5, std_mult=3.0):
        """
        Find where the rolling std exceeds baseline std * std_mult.
        """
        if len(seq) < window * 2:
            return None
        baseline_vals = [v for v in seq[:window] if v < 0.01]
        baseline_std = np.std(baseline_vals) if baseline_vals else 0.0
        for i in range(window, len(seq)):
            window_vals = seq[max(0,i-window):i+1]
            if np.std(window_vals) > max(0.001, baseline_std * std_mult):
                return i
        return None

    first_rise_l0 = find_first_rise(l0)
    first_rise_l2 = find_first_rise(l2)
    first_grad_l0 = find_first_deriv_peak(l0)
    first_grad_l2 = find_first_deriv_peak(l2)
    first_var_l0 = find_variance_onset(l0)
    first_var_l2 = find_variance_onset(l2)

    # Compute delays
    delay_rise = None
    if first_rise_l0 is not None and first_rise_l2 is not None:
        delay_rise = first_rise_l2 - first_rise_l0

    delay_grad = None
    if first_grad_l0 is not None and first_grad_l2 is not None:
        delay_grad = first_grad_l2 - first_grad_l0

    delay_var = None
    if first_var_l0 is not None and first_var_l2 is not None:
        delay_var = first_var_l2 - first_var_l0

    # Also compute L0 to L1 delay
    l1 = nsi_histories.get('INSTITUTIONAL', [])
    delay_rise_l1 = None
    delay_grad_l1 = None
    if l1:
        fr1 = find_first_rise(l1)
        fg1 = find_first_deriv_peak(l1)
        if first_rise_l0 is not None and fr1 is not None:
            delay_rise_l1 = fr1 - first_rise_l0
        if first_grad_l0 is not None and fg1 is not None:
            delay_grad_l1 = fg1 - first_grad_l0

    return {
        'l0_first_rise': first_rise_l0,
        'l2_first_rise': first_rise_l2,
        'l0_l2_delay_rise': delay_rise,
        'l0_l2_delay_gradient': delay_grad,
        'l0_l2_delay_variance': delay_var,
        'l1_first_rise': find_first_rise(l1) if l1 else None,
        'l0_l1_delay_rise': delay_rise_l1,
        'l0_l1_delay_gradient': delay_grad_l1,
    }


def run_single(seed, N0=N0, steps=STEPS, sample_interval=SAMPLE_INTERVAL,
               gbc_soft_nudge=GBC_SOFT_NUDGE):
    """Run a single seed with LayerNarrativeTracker and evaluate H28/H29."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    evolver = build_evolver(N0, steps, sample_interval, gbc_soft_nudge, seed)

    t0 = time.time()
    result = evolver.run(verbose=False)
    elapsed = time.time() - t0

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    # Base metrics (H1-H8)
    metrics = extract_step_metrics(step_results)
    h1h8 = evaluate_h1h8(metrics)

    # Track B1 metrics (H28-H29)
    lnt = evolver._lnt
    b1_metrics = evaluate_h28_h29(lnt, step_results)

    # Also extract per-layer NSI history from LNT for time-series
    layer_nsi_histories = lnt.get_all_nsi_histories()
    # Trim to reasonable size for JSON storage
    sampled_histories = {}
    for level, hist in layer_nsi_histories.items():
        # Sample every 10th point to keep file size manageable
        if len(hist) > 200:
            sampled_histories[level] = hist[::10]
        else:
            sampled_histories[level] = hist

    return {
        'seed': seed,
        'elapsed': elapsed,
        'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'h1h8': h1h8,
        'b1_metrics': b1_metrics,
        'layer_nsi_histories_sampled': sampled_histories,
    }


def evaluate_h28_h29_aggregate(all_results):
    """Aggregate evaluation of H28 and H29 across all seeds."""
    valid = [r for r in all_results if 'error' not in r]

    h28_pass_count = sum(
        1 for r in valid if r['b1_metrics']['H28']['passing'])
    h29_pass_count = sum(
        1 for r in valid if r['b1_metrics']['H29']['passing'])

    # H28: all > 80% seeds should have pairwise correlations < 0.5
    h28_pass_rate = h28_pass_count / max(1, len(valid))
    h28_overall_pass = h28_pass_rate >= 0.875  # 7/8 seeds

    # H29: all > 80% seeds should have L0→L2 delay ∈ [50, 200]
    h29_pass_rate = h29_pass_count / max(1, len(valid))
    h29_overall_pass = h29_pass_rate >= 0.875  # 7/8 seeds

    # Collect all pairwise correlations for analysis
    all_corrs = {f"{a}→{b}": []
                 for a in ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']
                 for b in ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']
                 if a != b}
    # Actually only get the ones that exist
    all_corrs_actual = {}
    for r in valid:
        for pair, corr in r['b1_metrics']['H28']['pairwise_correlations'].items():
            if pair not in all_corrs_actual:
                all_corrs_actual[pair] = []
            all_corrs_actual[pair].append(corr)

    # Collect delays
    all_delays = [
        r['b1_metrics']['H29']['l0_to_l2_delay']
        for r in valid
        if r['b1_metrics']['H29']['l0_to_l2_delay'] is not None
    ]

    # Collect per-layer NSI stats
    layer_nsi_means = {}
    for level in ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']:
        vals = [r['b1_metrics']['per_layer_nsi'][level]['mean']
                for r in valid]
        layer_nsi_means[level] = {
            'mean': float(np.mean(vals)) if vals else 0.0,
            'std': float(np.std(vals)) if vals else 0.0,
            'min': float(np.min(vals)) if vals else 0.0,
            'max': float(np.max(vals)) if vals else 0.0,
        }

    return {
        'H28': {
            'pass': h28_overall_pass,
            'pass_rate': h28_pass_rate,
            'n_pass': h28_pass_count,
            'n_total': len(valid),
            'per_pair_correlations': {
                pair: {
                    'mean': float(np.mean(vals)),
                    'std': float(np.std(vals)),
                    'min': float(np.min(vals)),
                    'max': float(np.max(vals)),
                    'all_values': [round(v, 4) for v in vals],
                }
                for pair, vals in all_corrs_actual.items()
            },
        },
        'H29': {
            'pass': h29_overall_pass,
            'pass_rate': h29_pass_rate,
            'n_pass': h29_pass_count,
            'n_total': len(valid),
            'all_delays': [int(d) if d is not None else None
                           for d in all_delays],
            'delay_stats': {
                'mean': float(np.mean(all_delays)) if all_delays else None,
                'std': float(np.std(all_delays)) if all_delays else None,
                'min': int(np.min(all_delays)) if all_delays else None,
                'max': int(np.max(all_delays)) if all_delays else None,
            },
        },
        'per_layer_nsi_aggregate': layer_nsi_means,
    }


def load_existing_results():
    if os.path.exists(FIXED_OUTPUT):
        with open(FIXED_OUTPUT, 'r') as f:
            d = json.load(f)
            return d, FIXED_OUTPUT
    pattern = os.path.join(
        PROJECT_ROOT, 'experiments', 'exp_114_b1_results_*.json')
    files = sorted(glob.glob(pattern), reverse=True)
    if files:
        with open(files[0], 'r') as f:
            d = json.load(f)
            return d, files[0]
    return None, None


def run_batch():
    """Run all seeds in batch."""
    existing_data, _ = load_existing_results()
    completed_seeds = set()
    all_results = []

    if existing_data and 'results' in existing_data:
        for r in existing_data['results'].get('per_run', []):
            if 'error' not in r:
                completed_seeds.add(r['seed'])
                all_results.append(r)
        print(f"Loaded {len(completed_seeds)} existing results: "
              f"{sorted(completed_seeds)}")
        if len(completed_seeds) >= len(ALL_SEEDS):
            print("All seeds already completed. Running final analysis...")
            final_analysis = evaluate_h28_h29_aggregate(all_results)
            print_analysis(final_analysis, all_results)
            return FIXED_OUTPUT

    remaining = [s for s in ALL_SEEDS if s not in completed_seeds]
    print(f"Remaining seeds: {remaining}")

    for seed in remaining:
        print(f"\n{'=' * 60}")
        print(f"Running seed={seed} ({remaining.index(seed) + 1}/"
              f"{len(remaining)})")
        print(f"{'=' * 60}")

        try:
            result = run_single(seed)
            all_results.append(result)
            # Print brief summary
            h28_pass = result['b1_metrics']['H28']['passing']
            h29_pass = result['b1_metrics']['H29']['passing']
            h1h8_pass = result['h1h8']['all_pass']
            print(f"  Seed {seed}: H1-H8={'PASS' if h1h8_pass else 'FAIL'}, "
                  f"H28={'PASS' if h28_pass else 'FAIL'}, "
                  f"H29={'PASS' if h29_pass else 'FAIL'}")
            print(f"  NSI per-layer: ", end="")
            for level in ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']:
                mean_nsi = result['b1_metrics']['per_layer_nsi'][level]['mean']
                print(f"{level}={mean_nsi:.4f} ", end="")
            print()
            print(f"  Correlations: "
                  f"{result['b1_metrics']['H28']['pairwise_correlations']}")
            ad = result['b1_metrics'].get('H29_actual_delay', {})
            if ad and 'l0_l2_delay_rise' in ad and ad['l0_l2_delay_rise'] is not None:
                print(f"  L0→L2 delay: LNT={result['b1_metrics']['H29']['l0_to_l2_delay']} steps  "
                      f"actual_rise={ad['l0_l2_delay_rise']} steps  "
                      f"actual_grad={ad['l0_l2_delay_gradient']} steps")
            else:
                print(f"  L0→L2 delay: {result['b1_metrics']['H29']['l0_to_l2_delay']} steps")
        except Exception as e:
            print(f"  ERROR seed={seed}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                'seed': seed, 'error': str(e),
                'elapsed': 0.0,
            })

        # Save intermediate results
        output = {
            'experiment': 'exp_114_phase5_b1_layered_narrative',
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'v': 1,
            'architecture': 'CSC+NSE+LNT (simplified, no AMC/ILP)',
            'config': {
                'seeds': ALL_SEEDS,
                'coupling_strength': P5_BASE_CSC_CONFIG[
                    'topdown_max_constraint_strength'],
                'N0': N0,
                'steps': STEPS,
                'sample_interval': SAMPLE_INTERVAL,
                'gbc_soft_nudge': GBC_SOFT_NUDGE,
                'lnt_config': {
                    k: v for k, v in P5_LNT_CONFIG.items()
                    if not k.startswith('_')
                },
            },
            'results': {
                'per_run': all_results,
                'n_completed': len([r for r in all_results
                                   if 'error' not in r]),
                'n_errors': len([r for r in all_results if 'error' in r]),
            },
        }

        with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        ts_path = os.path.join(
            PROJECT_ROOT, 'experiments',
            f"exp_114_b1_results_{output['timestamp']}.json")
        with open(ts_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        gc.collect()

    # Final analysis
    valid = [r for r in all_results if 'error' not in r]
    final_analysis = evaluate_h28_h29_aggregate(valid)

    print("\n" + "=" * 70)
    print("EXP_114 FINAL RESULTS — Track B1: Layered Narrative Tracking")
    print("=" * 70)

    print_analysis(final_analysis, valid)

    # Add final analysis to output
    if os.path.exists(FIXED_OUTPUT):
        with open(FIXED_OUTPUT, 'r') as f:
            output = json.load(f)
        output['results']['final_analysis'] = final_analysis
        with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    return FIXED_OUTPUT


def print_analysis(final_analysis, valid):
    """Print detailed analysis results."""
    print(f"\nTotal valid runs: {len(valid)}/{len(ALL_SEEDS)}")

    # H1-H8 summary
    h1h8_pass_count = sum(1 for r in valid if r['h1h8']['all_pass'])
    print(f"\n--- H1-H8 (Baseline) ---")
    print(f"  Pass rate: {h1h8_pass_count}/{len(valid)} "
          f"({h1h8_pass_count / max(1, len(valid)):.1%})")
    for h in [f'H{i}' for i in range(1, 9)]:
        n_pass = sum(1 for r in valid if r['h1h8'][h])
        print(f"  {h}: {n_pass}/{len(valid)} "
              f"({n_pass / max(1, len(valid)):.1%})")

    # Per-seed summary
    print("\n--- Per-Seed Results ---")
    for r in sorted(valid, key=lambda x: x['seed']):
        h28_pass = r['b1_metrics']['H28']['passing']
        h29_pass = r['b1_metrics']['H29']['passing']
        h1h8_ok = r['h1h8']['all_pass']
        corrs = r['b1_metrics']['H28']['pairwise_correlations']
        delay = r['b1_metrics']['H29']['l0_to_l2_delay']
        l0_mean = r['b1_metrics']['per_layer_nsi']['MINI']['mean']
        l1_mean = r['b1_metrics']['per_layer_nsi']['INSTITUTIONAL']['mean']
        l2_mean = r['b1_metrics']['per_layer_nsi']['CIVILIZATION']['mean']
        ad = r['b1_metrics'].get('H29_actual_delay', {})
        actual_delay_str = f"(rise={ad.get('l0_l2_delay_rise','?')} grad={ad.get('l0_l2_delay_gradient','?')})" if ad else ""

        print(f"  seed={r['seed']:>5}: "
              f"base={'PASS' if h1h8_ok else 'FAIL'} "
              f"H28={'PASS' if h28_pass else 'FAIL'} "
              f"H29={'PASS' if h29_pass else 'FAIL'}  "
              f"NSI(L0={l0_mean:.3f} L1={l1_mean:.3f} L2={l2_mean:.3f})  "
              f"corr={corrs}  delay={delay} {actual_delay_str}")

    # H28
    print("\n--- H28 (Layer Narrative Independence) ---")
    h28_info = final_analysis['H28']
    print(f"  Result: {'PASS' if h28_info['pass'] else 'FAIL'}")
    print(f"  Pass rate: {h28_info['pass_rate']:.1%} "
          f"({h28_info['n_pass']}/{h28_info['n_total']})")
    print(f"  Threshold: >= 87.5% seeds have all pairwise r < 0.5")
    print(f"\n  Per-pair correlations (mean ± std):")
    for pair, stats in h28_info['per_pair_correlations'].items():
        print(f"    {pair}: {stats['mean']:.4f} ± {stats['std']:.4f}  "
              f"[{stats['min']:.4f}, {stats['max']:.4f}]")

    # H29
    print("\n--- H29 (Conduction Delay) ---")
    h29_info = final_analysis['H29']
    print(f"  Result: {'PASS' if h29_info['pass'] else 'FAIL'}")
    print(f"  Pass rate: {h29_info['pass_rate']:.1%} "
          f"({h29_info['n_pass']}/{h29_info['n_total']})")
    print(f"  Threshold: >= 87.5% seeds have L0→L2 delay ∈ [50, 200]")
    ds = h29_info.get('delay_stats')
    if ds and ds.get('mean') is not None:
        print(f"  Delay stats: mean={ds['mean']:.1f} "
              f"std={ds['std']:.1f} "
              f"min={ds['min']} max={ds['max']} steps")
    else:
        print(f"  Delay stats: insufficient data (all delays=None)")
    print(f"  All delays: {h29_info['all_delays']}")

    # Per-layer NSI aggregate
    print("\n--- Per-Layer NSI (Aggregate) ---")
    for level, stats in final_analysis['per_layer_nsi_aggregate'].items():
        print(f"  {level}: mean={stats['mean']:.4f} ± {stats['std']:.4f}  "
              f"[{stats['min']:.4f}, {stats['max']:.4f}]")

    print()


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        seed = int(sys.argv[1])
        result = run_single(seed)
        print(json.dumps(result, indent=2))
    else:
        run_batch()
