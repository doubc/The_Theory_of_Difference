"""
experiments/exp_115_phase5_b2_serial_coupling.py

Phase 5 Track B2: Serial CSC Coupling (L0→L1→L2)

Purpose: Validate that serial coupling mode decouples L1 and L2 narrative
    trajectories, reducing L1↔L2 correlation from r≈0.98 (parallel) to r<0.7.

Background:
  exp_114 (Track B1) found L1↔L2 NSI correlation = 0.976 ± 0.003 because
  both layers read from the same L0 source in parallel. Theory predicts
  that true hierarchy requires serial coupling: L2 should derive from L1's
  institutional output, not from L0's clusters directly.

  Theory: "层级不是权力意义上的高低先行，而是结构生成中的组织分层" (差异论 §2.2)

Method:
  - 8 seeds (same as Phase 4/5 baseline)
  - Single config: coupling_mode='serial', N0=72, steps=2000
  - Total: 8 seeds x 1 config = 8 runs
  - Architecture: CSC(serial)+NSE+LNT (no AMC/ILP)

Hypotheses:
  H30 (layer decoupling): L1↔L2 NSI Pearson r < 0.7
      Rationale: In serial mode, L2 derives from L1 with attenuation and
      noise, breaking the near-perfect parallel coupling. The threshold
      of 0.7 allows meaningful but imperfect coupling.

  H31 (hierarchical delay): L0→L1 delay + L1→L2 delay > L0→L2 direct delay
      Rationale: Serial coupling introduces additive delays: L0 must first
      affect L1, then L1 affects L2. The total chain should be longer than
      any single-hop delay.

  Also tracks H1-H8 (baseline) to verify serial coupling doesn't break
  core dynamics.

Invoke modes:
  Batch:  python exp_115_phase5_b2_serial_coupling.py
  Single: python exp_115_phase5_b2_serial_coupling.py <seed>
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

# ─── P5 Track B2: Serial CSC config ───
# Based on P5 baseline but with coupling_mode='serial'
P5_SERIAL_CSC_CONFIG = {
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
    # ── Track B2: Serial coupling ──
    'coupling_mode': 'serial',
    'serial_l1_to_l2_delay': 15,
    'serial_l1_to_l2_attenuation': 0.5,
    'serial_l1_to_l2_noise': 0.15,
}

# ─── Experiment parameters ───
N0 = 72
STEPS = 2000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.5

FIXED_OUTPUT = os.path.join(
    PROJECT_ROOT, 'experiments',
    'exp_115_b2_results_final.json')


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
    """Build HierarchicalEvolver with CSC(serial)+NSE+LNT."""
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

    # Track B2: Serial CSC
    csc = CrossScaleCoupling(config=dict(P5_SERIAL_CSC_CONFIG))

    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {
        'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    # Track B1/B2: LayerNarrativeTracker
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
        layer_narrative_tracker=lnt)
    ev._lnt = lnt
    return ev


def extract_step_metrics(step_results):
    """Extract metrics from step results."""
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


def evaluate_h30_h31(lnt, step_results):
    """Evaluate H30 (L1-L2 decoupling) and H31 (hierarchical delay)."""
    h28_result = lnt.get_inter_layer_correlation()
    h29_result = lnt.get_conduction_delay()

    # H30: L1↔L2 correlation < 0.7
    l1_l2_corr = h28_result.pairwise_correlations.get(
        'INSTITUTIONAL→CIVILIZATION', None)
    if l1_l2_corr is None:
        # Try reverse key
        l1_l2_corr = h28_result.pairwise_correlations.get(
            'CIVILIZATION→INSTITUTIONAL', 0.0)
    h30_pass = l1_l2_corr is not None and abs(l1_l2_corr) < 0.7

    # H31: L0→L1 delay + L1→L2 delay > L0→L2 delay
    l0_l1 = h29_result.l0_to_l1_delay
    l1_l2 = h29_result.l1_to_l2_delay
    l0_l2 = h29_result.l0_to_l2_delay

    if l0_l1 is not None and l1_l2 is not None and l0_l2 is not None:
        h31_pass = (l0_l1 + l1_l2) > l0_l2
    else:
        h31_pass = False

    # Also compute actual conduction delay from NSI histories
    all_nsi_histories = lnt.get_all_nsi_histories()
    actual_delay = compute_actual_conduction_delay(all_nsi_histories)

    # Per-layer NSI stats
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

    # All pairwise correlations
    all_corrs = h28_result.pairwise_correlations

    result = {
        'H30': {
            'passing': h30_pass,
            'l1_l2_correlation': l1_l2_corr,
            'threshold': 0.7,
            'all_pairwise': all_corrs,
        },
        'H31': {
            'passing': h31_pass,
            'l0_to_l1_delay': l0_l1,
            'l1_to_l2_delay': l1_l2,
            'l0_to_l2_delay': l0_l2,
            'l0_l1_plus_l1_l2': (l0_l1 or 0) + (l1_l2 or 0) if l0_l1 is not None and l1_l2 is not None else None,
            'delay_mode': h29_result.delay_mode,
        },
        'H29_actual_delay': actual_delay,
        'per_layer_nsi': per_layer_stats,
        'layer_activity': activity_profile,
        # Also include full H28/H29 for reference
        'H28_full': {
            'passing': h28_result.passing,
            'pairwise_correlations': h28_result.pairwise_correlations,
            'all_below_threshold': h28_result.all_below_threshold,
            'threshold': h28_result.threshold,
            'n_samples': h28_result.n_samples,
        },
        'H29_full': {
            'passing': h29_result.passing,
            'l0_to_l2_delay': h29_result.l0_to_l2_delay,
            'l0_to_l1_delay': h29_result.l0_to_l1_delay,
            'l1_to_l2_delay': h29_result.l1_to_l2_delay,
            'delay_mode': h29_result.delay_mode,
            'n_detection_events': h29_result.n_detection_events,
            'reason': h29_result.passing_reason,
        },
    }

    return result


def compute_actual_conduction_delay(nsi_histories):
    """Post-hoc computation of actual conduction delays."""
    l0 = nsi_histories.get('MINI', [])
    l1 = nsi_histories.get('INSTITUTIONAL', [])
    l2 = nsi_histories.get('CIVILIZATION', [])

    if not l0 or not l2:
        return {'error': 'insufficient_data'}

    def find_first_rise(seq, threshold=0.05):
        for i, val in enumerate(seq):
            if val > threshold:
                return i
        return None

    def find_first_deriv_peak(seq, min_gradient=0.02):
        for i in range(1, len(seq)):
            grad = seq[i] - seq[i - 1]
            if grad > min_gradient:
                return i
        return None

    def find_variance_onset(seq, window=5, std_mult=3.0):
        if len(seq) < window * 2:
            return None
        baseline_vals = [v for v in seq[:window] if v < 0.01]
        baseline_std = np.std(baseline_vals) if baseline_vals else 0.0
        for i in range(window, len(seq)):
            window_vals = seq[max(0, i - window):i + 1]
            if np.std(window_vals) > max(0.001, baseline_std * std_mult):
                return i
        return None

    first_rise = {}
    for name, seq in [('L0', l0), ('L1', l1), ('L2', l2)]:
        first_rise[name] = find_first_rise(seq)
    first_grad = {}
    for name, seq in [('L0', l0), ('L1', l1), ('L2', l2)]:
        first_grad[name] = find_first_deriv_peak(seq)

    # Compute all delays
    delays = {}
    for method, data in [('rise', first_rise), ('gradient', first_grad)]:
        d_l0_l1 = None
        d_l1_l2 = None
        d_l0_l2 = None
        if data.get('L0') is not None and data.get('L1') is not None:
            d_l0_l1 = data['L1'] - data['L0']
        if data.get('L1') is not None and data.get('L2') is not None:
            d_l1_l2 = data['L2'] - data['L1']
        if data.get('L0') is not None and data.get('L2') is not None:
            d_l0_l2 = data['L2'] - data['L0']
        delays[method] = {
            'l0_l1': d_l0_l1,
            'l1_l2': d_l1_l2,
            'l0_l2': d_l0_l2,
            'hierarchical_sum': (d_l0_l1 or 0) + (d_l1_l2 or 0)
            if d_l0_l1 is not None and d_l1_l2 is not None else None,
        }

    return delays


def run_single(seed, N0=N0, steps=STEPS, sample_interval=SAMPLE_INTERVAL,
               gbc_soft_nudge=GBC_SOFT_NUDGE):
    """Run a single seed with serial CSC and evaluate H30/H31."""
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

    # Track B2 metrics (H30-H31)
    lnt = evolver._lnt
    b2_metrics = evaluate_h30_h31(lnt, step_results)

    # Per-layer NSI history for time-series
    layer_nsi_histories = lnt.get_all_nsi_histories()
    sampled_histories = {}
    for level, hist in layer_nsi_histories.items():
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
        'b2_metrics': b2_metrics,
        'layer_nsi_histories_sampled': sampled_histories,
    }


def evaluate_h30_h31_aggregate(all_results):
    """Aggregate evaluation of H30 and H31 across all seeds."""
    valid = [r for r in all_results if 'error' not in r]

    # H30: L1↔L2 correlation < 0.7
    h30_pass_count = sum(
        1 for r in valid if r['b2_metrics']['H30']['passing'])
    h30_pass_rate = h30_pass_count / max(1, len(valid))
    h30_overall_pass = h30_pass_rate >= 0.875  # 7/8 seeds

    # Collect L1-L2 correlations
    l1_l2_corrs = [
        r['b2_metrics']['H30']['l1_l2_correlation']
        for r in valid
        if r['b2_metrics']['H30']['l1_l2_correlation'] is not None
    ]

    # Collect all pairwise correlations
    all_pairwise = {}
    for r in valid:
        for pair, corr in r['b2_metrics']['H30']['all_pairwise'].items():
            if pair not in all_pairwise:
                all_pairwise[pair] = []
            all_pairwise[pair].append(corr)

    # H31: hierarchical delay
    h31_pass_count = sum(
        1 for r in valid if r['b2_metrics']['H31']['passing'])
    h31_pass_rate = h31_pass_count / max(1, len(valid))
    h31_overall_pass = h31_pass_rate >= 0.875

    # Collect delays
    l0_l1_delays = [r['b2_metrics']['H31']['l0_to_l1_delay']
                    for r in valid
                    if r['b2_metrics']['H31']['l0_to_l1_delay'] is not None]
    l1_l2_delays = [r['b2_metrics']['H31']['l1_to_l2_delay']
                    for r in valid
                    if r['b2_metrics']['H31']['l1_to_l2_delay'] is not None]
    l0_l2_delays = [r['b2_metrics']['H31']['l0_to_l2_delay']
                    for r in valid
                    if r['b2_metrics']['H31']['l0_to_l2_delay'] is not None]

    # Per-layer NSI aggregate
    layer_nsi_means = {}
    for level in ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']:
        vals = [r['b2_metrics']['per_layer_nsi'][level]['mean']
                for r in valid]
        layer_nsi_means[level] = {
            'mean': float(np.mean(vals)) if vals else 0.0,
            'std': float(np.std(vals)) if vals else 0.0,
            'min': float(np.min(vals)) if vals else 0.0,
            'max': float(np.max(vals)) if vals else 0.0,
        }

    return {
        'H30': {
            'pass': h30_overall_pass,
            'pass_rate': h30_pass_rate,
            'n_pass': h30_pass_count,
            'n_total': len(valid),
            'l1_l2_correlation_stats': {
                'mean': float(np.mean(l1_l2_corrs)) if l1_l2_corrs else None,
                'std': float(np.std(l1_l2_corrs)) if l1_l2_corrs else None,
                'min': float(np.min(l1_l2_corrs)) if l1_l2_corrs else None,
                'max': float(np.max(l1_l2_corrs)) if l1_l2_corrs else None,
                'all_values': [round(v, 4) for v in l1_l2_corrs],
            },
            'per_pair_correlations': {
                pair: {
                    'mean': float(np.mean(vals)),
                    'std': float(np.std(vals)),
                    'min': float(np.min(vals)),
                    'max': float(np.max(vals)),
                    'all_values': [round(v, 4) for v in vals],
                }
                for pair, vals in all_pairwise.items()
            },
        },
        'H31': {
            'pass': h31_overall_pass,
            'pass_rate': h31_pass_rate,
            'n_pass': h31_pass_count,
            'n_total': len(valid),
            'delay_stats': {
                'l0_l1': {
                    'mean': float(np.mean(l0_l1_delays)) if l0_l1_delays else None,
                    'all': l0_l1_delays,
                },
                'l1_l2': {
                    'mean': float(np.mean(l1_l2_delays)) if l1_l2_delays else None,
                    'all': l1_l2_delays,
                },
                'l0_l2': {
                    'mean': float(np.mean(l0_l2_delays)) if l0_l2_delays else None,
                    'all': l0_l2_delays,
                },
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
        PROJECT_ROOT, 'experiments', 'exp_115_b2_results_*.json')
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
            final_analysis = evaluate_h30_h31_aggregate(all_results)
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
            h30_pass = result['b2_metrics']['H30']['passing']
            h31_pass = result['b2_metrics']['H31']['passing']
            h1h8_pass = result['h1h8']['all_pass']
            l1_l2_corr = result['b2_metrics']['H30']['l1_l2_correlation']
            print(f"  Seed {seed}: H1-H8={'PASS' if h1h8_pass else 'FAIL'}, "
                  f"H30={'PASS' if h30_pass else 'FAIL'} (r={l1_l2_corr:.4f}), "
                  f"H31={'PASS' if h31_pass else 'FAIL'}")
            print(f"  NSI per-layer: ", end="")
            for level in ['MINI', 'INSTITUTIONAL', 'CIVILIZATION']:
                mean_nsi = result['b2_metrics']['per_layer_nsi'][level]['mean']
                print(f"{level}={mean_nsi:.4f} ", end="")
            print()
            print(f"  All correlations: "
                  f"{result['b2_metrics']['H30']['all_pairwise']}")
            h31 = result['b2_metrics']['H31']
            print(f"  Delays: L0→L1={h31['l0_to_l1_delay']} "
                  f"L1→L2={h31['l1_to_l2_delay']} "
                  f"L0→L2={h31['l0_to_l2_delay']}")
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
            'experiment': 'exp_115_phase5_b2_serial_coupling',
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'v': 1,
            'architecture': 'CSC(serial)+NSE+LNT (L0→L1→L2)',
            'config': {
                'seeds': ALL_SEEDS,
                'coupling_mode': 'serial',
                'serial_l1_to_l2_delay': P5_SERIAL_CSC_CONFIG['serial_l1_to_l2_delay'],
                'serial_l1_to_l2_attenuation': P5_SERIAL_CSC_CONFIG['serial_l1_to_l2_attenuation'],
                'serial_l1_to_l2_noise': P5_SERIAL_CSC_CONFIG['serial_l1_to_l2_noise'],
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
            f"exp_115_b2_results_{output['timestamp']}.json")
        with open(ts_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        gc.collect()

    # Final analysis
    valid = [r for r in all_results if 'error' not in r]
    final_analysis = evaluate_h30_h31_aggregate(valid)

    print("\n" + "=" * 70)
    print("EXP_115 FINAL RESULTS — Track B2: Serial CSC Coupling (L0→L1→L2)")
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
        h30_pass = r['b2_metrics']['H30']['passing']
        h31_pass = r['b2_metrics']['H31']['passing']
        h1h8_ok = r['h1h8']['all_pass']
        l1_l2 = r['b2_metrics']['H30']['l1_l2_correlation']
        corrs = r['b2_metrics']['H30']['all_pairwise']
        h31 = r['b2_metrics']['H31']
        l0_mean = r['b2_metrics']['per_layer_nsi']['MINI']['mean']
        l1_mean = r['b2_metrics']['per_layer_nsi']['INSTITUTIONAL']['mean']
        l2_mean = r['b2_metrics']['per_layer_nsi']['CIVILIZATION']['mean']

        print(f"  seed={r['seed']:>5}: "
              f"base={'PASS' if h1h8_ok else 'FAIL'} "
              f"H30={'PASS' if h30_pass else 'FAIL'}(r={l1_l2:.3f}) "
              f"H31={'PASS' if h31_pass else 'FAIL'}  "
              f"NSI(L0={l0_mean:.3f} L1={l1_mean:.3f} L2={l2_mean:.3f})  "
              f"delays(L0→L1={h31['l0_to_l1_delay']} L1→L2={h31['l1_to_l2_delay']} L0→L2={h31['l0_to_l2_delay']})")

    # H30
    print("\n--- H30 (Layer Decoupling: L1↔L2 r < 0.7) ---")
    h30_info = final_analysis['H30']
    print(f"  Result: {'PASS' if h30_info['pass'] else 'FAIL'}")
    print(f"  Pass rate: {h30_info['pass_rate']:.1%} "
          f"({h30_info['n_pass']}/{h30_info['n_total']})")
    l1_l2_stats = h30_info['l1_l2_correlation_stats']
    if l1_l2_stats['mean'] is not None:
        print(f"  L1↔L2 correlation: {l1_l2_stats['mean']:.4f} ± {l1_l2_stats['std']:.4f}  "
              f"[{l1_l2_stats['min']:.4f}, {l1_l2_stats['max']:.4f}]")
        print(f"  All values: {l1_l2_stats['all_values']}")
    print(f"\n  Per-pair correlations (mean ± std):")
    for pair, stats in h30_info['per_pair_correlations'].items():
        print(f"    {pair}: {stats['mean']:.4f} ± {stats['std']:.4f}  "
              f"[{stats['min']:.4f}, {stats['max']:.4f}]")

    # Comparison with B1
    print(f"\n  Comparison with B1 (parallel):")
    print(f"    B1 L1↔L2: r = 0.976 ± 0.003 (near-perfect coupling)")
    if l1_l2_stats['mean'] is not None:
        print(f"    B2 L1↔L2: r = {l1_l2_stats['mean']:.4f} ± {l1_l2_stats['std']:.4f} (serial coupling)")
        reduction = (1.0 - l1_l2_stats['mean'] / 0.976) * 100
        print(f"    Correlation reduction: {reduction:.1f}%")

    # H31
    print("\n--- H31 (Hierarchical Delay: L0→L1 + L1→L2 > L0→L2) ---")
    h31_info = final_analysis['H31']
    print(f"  Result: {'PASS' if h31_info['pass'] else 'FAIL'}")
    print(f"  Pass rate: {h31_info['pass_rate']:.1%} "
          f"({h31_info['n_pass']}/{h31_info['n_total']})")
    ds = h31_info['delay_stats']
    if ds['l0_l1']['mean'] is not None:
        print(f"  L0→L1 delay: {ds['l0_l1']['mean']:.1f} steps  {ds['l0_l1']['all']}")
    else:
        print(f"  L0→L1 delay: insufficient data")
    if ds['l1_l2']['mean'] is not None:
        print(f"  L1→L2 delay: {ds['l1_l2']['mean']:.1f} steps  {ds['l1_l2']['all']}")
    else:
        print(f"  L1→L2 delay: insufficient data")
    if ds['l0_l2']['mean'] is not None:
        print(f"  L0→L2 delay: {ds['l0_l2']['mean']:.1f} steps  {ds['l0_l2']['all']}")
    else:
        print(f"  L0→L2 delay: insufficient data")

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
        print(json.dumps(result, indent=2, default=str))
    else:
        run_batch()
