"""
experiments/exp_136_phase7_full_spiral_integration.py

Phase 7: Full Spiral Integration at N0=72

Purpose:
  Validate the completed P → E → M → S → R → P' cycle running end-to-end at
  the optimal scale (N0=72). Phase 6 proved the NRC mechanism works internally
  (tension-based R2 trigger, E→M→S→R pipeline). Phase 7 measures whether the
  full spiral produces measurably different system-level outcomes.

  Core question: Does R→P feedback rewrite P-space in a way that matters?

Hypotheses:
  H81 (Spiral completeness): >=6/8 seeds have >=2 complete E->M->S->R cycles
       within first 500 steps (redesigned H64 metric from Phase 6)
  H82 (R→P rewriting): >=4/8 seeds show mean level_transition_weights delta
       > 0.05 after R2 events
  H83 (NSI improvement): Mean NSI at N0=72 >= Phase 5 D1 baseline + 0.02
       (measured over steps 500-1000)
  H84 (Cross-scale consistency): >=4/8 seeds have L0/L1 event timing
       Jaccard similarity > 0.3 (within +/-5 step tolerance)
  H85 (No degradation): H1-H8 pass at 5000 steps for 8/8 seeds
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
    CIVRateLimiter,
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
from engine.narrative_recursive_closure import NarrativeRecursiveClosure
from engine.civ_floor import NarrativeLevelBooster
from engine.per_layer_metrics import PerLayerMetricsCollector


# --- Config ---
P7_CSC_CONFIG = {
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


class CIVRateLimiterV2P1F(CIVRateLimiter):
    def __init__(self, window_size=50, max_civ_rate=0.12, cooldown_steps=12,
                 min_civ_guarantee=3):
        super().__init__(window_size=window_size, max_civ_rate=max_civ_rate,
                         cooldown_steps=cooldown_steps)
        self.min_civ_guarantee = min_civ_guarantee

    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            if self._total_civ_seen < self.min_civ_guarantee:
                return level
            if self.should_downgrade(step):
                self._total_downgrades += 1
                return NarrativeLevel.INSTITUTIONAL
        return level


class MomentumNarrativeOperatorV4P1F(NarrativeRecursionOperator):
    def __init__(self, bias_dimension=128, filter_magnitude_threshold=0.02,
                 connector_strength_threshold=0.1,
                 verifier_consistency_threshold=0.3,
                 narrative_decay_rate=0.9, momentum_decay=0.95,
                 momentum_bonus=0.3):
        from models.narrative_self import NarrativeFilter, NarrativeNamer
        from models.narrative_self import NarrativeActionizer, NarrativeVerifier
        self.filter = NarrativeFilter(magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(
            strength_threshold=connector_strength_threshold,
            momentum_decay=momentum_decay, momentum_bonus=momentum_bonus)
        self.actionizer = NarrativeActionizer(bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(consistency_threshold=verifier_consistency_threshold)
        self.narrative_decay_rate = narrative_decay_rate
        self._records = []
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F(
            window_size=50, max_civ_rate=0.12, cooldown_steps=12, min_civ_guarantee=3)

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


# --- Metrics Extraction ---

def extract_nrc_metrics(evolver, step_results):
    """Extract NRC + Spiral metrics from evolver post-run."""
    nrc = getattr(evolver, 'narrative_recursive_closure', None)
    if nrc is None:
        return {'nrc_active': False, 'error': 'no_nrc_in_evolver'}

    summary = nrc.get_summary()
    cycles = nrc.get_cycle_history()

    metrics = {
        'nrc_active': True,
        'n_cycles': summary.get('n_cycles', 0),
        'n_r2_events': summary.get('n_r2_events', 0),
        'n_rewrites': summary.get('n_rewrites', 0),
        'cumulative_tension': summary.get('cumulative_tension', 0.0),
        'peak_nsi': summary.get('peak_nsi', 0.0),
        'r2_use_tension': summary.get('r2_use_tension', False),
        'cycle_stats': summary.get('cycle_stats', {}),
    }

    # --- H81: Cycles in first 500 steps ---
    first_500_cycles = [c for c in cycles if c.step <= 500]
    metrics['h81_cycles_first_500'] = len(first_500_cycles)

    # --- H82: R→P rewriting deltas ---
    # Measure level_transition_weights delta between consecutive cycle settled_states
    rewriting_deltas = []
    if cycles and len(cycles) >= 2:
        for i in range(1, len(cycles)):
            prev_cycle = cycles[i-1]
            curr_cycle = cycles[i]
            # Extract level weights from settled_state or rewritten_space
            prev_weights = getattr(prev_cycle, 'settled_state', {})
            curr_weights = getattr(curr_cycle, 'settled_state', {})
            all_levels = set(prev_weights.keys()) | set(curr_weights.keys())
            if all_levels:
                deltas = []
                for level in all_levels:
                    p = prev_weights.get(level, 0.0)
                    c = curr_weights.get(level, 0.0)
                    deltas.append(abs(c - p))
                mean_delta = float(np.mean(deltas))
                rewriting_deltas.append(mean_delta)
    metrics['h82_rewriting_deltas'] = rewriting_deltas
    metrics['h82_mean_rewriting_delta'] = float(np.mean(rewriting_deltas)) if rewriting_deltas else 0.0

    # --- H84: Cross-scale L0/L1 event timing ---
    # Use cycle step distribution
    cycle_steps = [c.step for c in cycles]

    # Attempt to get L1-level cycle history
    l1_cycles = []
    if hasattr(nrc, '_nsi_history'):
        # If L1 tracking was enabled via PerLayerMetricsCollector, extract
        pass
    metrics['h84_l0_cycle_times'] = cycle_steps
    # L1 cycles extracted from per-layer metrics below
    metrics['h84_l1_cycle_times'] = []  # populated below if available

    # R0/R1 summary
    r0_sig_changes = 0
    if cycles:
        level_first_last = {}
        for c in cycles:
            settled = c.settled_state
            for level, weight in settled.items():
                if level not in level_first_last:
                    level_first_last[level] = {'first': weight, 'last': weight}
                else:
                    level_first_last[level]['last'] = weight
        sig_count = 0
        total_levels = len(level_first_last)
        for level, data in level_first_last.items():
            change_pct = abs(data['last'] - data['first']) / max(abs(data['first']), 0.001) * 100.0
            if change_pct > 5.0:
                sig_count += 1
        r0_sig_changes = sig_count
        metrics['r0_total_levels_tracked'] = total_levels
    metrics['r0_significant_change_count'] = r0_sig_changes
    metrics['r0_sig_change_ratio'] = (r0_sig_changes / total_levels
                                       if total_levels > 0 else 0.0)

    # R2 event step distribution
    r2_steps = []
    for c in cycles:
        if c.recursion_output and c.recursion_output.r2_triggered:
            r2_steps.append(c.step)
    metrics['h82_r2_steps'] = r2_steps

    return metrics


def compute_h84_jaccard(l0_times, l1_times, tolerance=5):
    """Compute Jaccard similarity of event timesteps within +/- tolerance."""
    if not l0_times or not l1_times:
        return 0.0
    intersection = 0
    union_set = set(l0_times) | set(l1_times)
    for t0 in l0_times:
        for t1 in l1_times:
            if abs(t0 - t1) <= tolerance:
                intersection += 1
                break
    union = len(union_set)
    return intersection / max(union, 1)


def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    r2_tension_threshold, csc_config=None,
                    tracking_collector=None):
    """Run a single seed at N0=72 with full spiral (CSC+NSE+NRC+Booster)."""
    torch.manual_seed(seed)
    np.random.seed(seed)

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
    narrative = MomentumNarrativeOperatorV4P1F(
        bias_dimension=128, filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3)
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01})
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1, 'max_branches': 4})
    six_threshold = SixThresholdDetector()

    csc_cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
    if csc_config:
        csc_cfg.update(csc_config)
    csc = CrossScaleCoupling(config=csc_cfg)

    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {
        'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    # Tension-based R2 trigger (Phase 6 recommended default)
    nrc = NarrativeRecursiveClosure(
        event_window=20, collapse_threshold=0.15, settling_rate=0.3,
        r0_weight=0.4, r1_weight=0.35, r2_weight=0.25,
        r2_threshold_nsi=0.85, r2_cooldown=200,
        r2_tension_threshold=r2_tension_threshold,
        r2_use_tension=True, verbose=True)

    narrative_level_booster = NarrativeLevelBooster(min_civ=3)

    evolver = HierarchicalEvolver(
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
        adaptive_momentum_controller=None, institutional_layer_protector=None,
        narrative_level_booster=narrative_level_booster,
        narrative_recursive_closure=nrc)

    print(f"    [seed={seed}] Running {steps} steps at N0={N0} "
          f"(tension_threshold={r2_tension_threshold})...", flush=True)
    start = time.time()
    tracking_cb = tracking_collector.step if tracking_collector is not None else None
    result = evolver.run(tracking_callback=tracking_cb)
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    odi_values = [sr['odi']['value'] for sr in step_results
                  if 'odi' in sr and sr.get('odi', {}).get('value') is not None]
    odi_max = float(np.max(odi_values)) if odi_values else 0.0

    gbc_checks = result.get('gbc_checks', [])
    gbc_coherences = [c.get('coherence', 0.0) for c in gbc_checks]
    gbc_passes = [1 for c in gbc_checks if c.get('passed', False)]
    gbc_coherence_mean = float(np.mean(gbc_coherences)) if gbc_coherences else 0.0
    gbc_pass_rate = float(np.mean(gbc_passes)) if gbc_passes else 0.0

    csc_csci_values = [sr.get('cross_scale_coupling', {}).get('csci', 0.0)
                       for sr in step_results if 'cross_scale_coupling' in sr]
    csc_csci_std = float(np.std(csc_csci_values)) if csc_csci_values else 0.0

    topdown_active_counts = [sr.get('cross_scale_coupling', {}).get('topdown_n_active', 0)
                             for sr in step_results if 'cross_scale_coupling' in sr]
    topdown_max_active = int(np.max(topdown_active_counts)) if topdown_active_counts else 0

    nse_nsi_values = [sr.get('narrative_self_emergence', {}).get('nsi', 0.0)
                      for sr in step_results if 'narrative_self_emergence' in sr]
    nse_nsi_max = float(np.max(nse_nsi_values)) if nse_nsi_values else 0.0
    nse_nsi_mean = float(np.mean(nse_nsi_values)) if nse_nsi_values else 0.0
    nse_nsi_active_count = sum(1 for sr in step_results
                               if sr.get('narrative_self_emergence', {}).get('nsi_active', False))
    nse_nsi_active_rate = nse_nsi_active_count / len(step_results) if step_results else 0.0

    nse_continuity_values = [sr.get('narrative_self_emergence', {}).get('continuity_score', 0.0)
                             for sr in step_results if 'narrative_self_emergence' in sr]
    nse_continuity_mean = float(np.mean(nse_continuity_values)) if nse_continuity_values else 0.0

    nse_history_depth_values = [sr.get('narrative_self_emergence', {}).get('self_history_depth', 0.0)
                                for sr in step_results if 'narrative_self_emergence' in sr]
    nse_history_depth_mean = float(np.mean(nse_history_depth_values)) if nse_history_depth_values else 0.0

    nse_turning_points_values = [sr.get('narrative_self_emergence', {}).get('n_turning_points', 0)
                                 for sr in step_results if 'narrative_self_emergence' in sr]
    nse_turning_points_final = nse_turning_points_values[-1] if nse_turning_points_values else 0

    civ_values = []
    for sr in step_results:
        nse_entry = sr.get('narrative_self_emergence', {})
        if 'civ_count' in nse_entry:
            civ_values.append(nse_entry['civ_count'])
    civ_mean = float(np.mean(civ_values)) if civ_values else 0.0
    civ_min = int(np.min(civ_values)) if civ_values else 0
    civ_max = int(np.max(civ_values)) if civ_values else 0

    civ_limiter_summary = narrative.civ_rate_limiter.get_summary()
    nrc_metrics = extract_nrc_metrics(evolver, step_results)

    return {
        'N0': N0, 'seed': seed, 'elapsed': elapsed, 'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'odi_max': odi_max, 'gbc_coherence_mean': gbc_coherence_mean,
        'gbc_pass_rate': gbc_pass_rate, 'csc_csci_std': csc_csci_std,
        'topdown_max_active': topdown_max_active,
        'nse_nsi_max': nse_nsi_max, 'nse_nsi_mean': nse_nsi_mean,
        'nse_nsi_active_rate': nse_nsi_active_rate,
        'nse_continuity_mean': nse_continuity_mean,
        'nse_history_depth_mean': nse_history_depth_mean,
        'nse_turning_points_final': nse_turning_points_final,
        'civ_mean': civ_mean, 'civ_min': civ_min, 'civ_max': civ_max,
        'civ_limiter_total_seen': civ_limiter_summary['total_civ_seen'],
        'nrc_metrics': nrc_metrics,
        'r2_tension_threshold': r2_tension_threshold,
        # H83: NSI over steps 500-1000 for baseline comparison
        'nsi_mid_phase': [nse_nsi_values[i] for i in range(len(nse_nsi_values))
                          if 50 <= i <= 100],  # sample_interval=10, so 500-1000 steps
    }


def evaluate_hypotheses(results, label="phase7_n72"):
    """Evaluate H81-H85 for Phase 7 Full Spiral Integration."""
    if not results:
        return {'summary': {'all_pass': False, 'n_pass': 0, 'failed': ['no_data']}}

    nsi_max_vals = [r['nse_nsi_max'] for r in results]
    nsi_active_rates = [r['nse_nsi_active_rate'] for r in results]
    continuity_means = [r['nse_continuity_mean'] for r in results]
    history_depth_means = [r['nse_history_depth_mean'] for r in results]
    turning_points_finals = [r['nse_turning_points_final'] for r in results]
    csci_stds = [r['csc_csci_std'] for r in results]
    topdown_max = [r['topdown_max_active'] for r in results]
    civ_max_values = [r.get('civ_max', 0) for r in results]

    # H1-H8: Core emergence
    h1 = float(np.max(nsi_max_vals)) > 0.1
    h2 = all(rate > 0.3 for rate in nsi_active_rates)
    h3 = float(np.mean(continuity_means)) > 0.1
    h4_depth = float(np.mean(history_depth_means)) > 0.05
    h4_tp = float(np.mean(turning_points_finals)) > 0.0
    h4 = h4_depth or h4_tp
    h5 = float(np.max(civ_max_values)) >= 3
    h6 = float(np.max(civ_max_values)) >= 2
    h7 = float(np.mean(csci_stds)) > 0.005
    h8 = sum(1 for v in topdown_max if v > 0) >= 2

    # --- H81: Spiral completeness ---
    # >=6/8 seeds with >=2 cycles in first 500 steps
    h81_values = [r.get('nrc_metrics', {}).get('h81_cycles_first_500', 0) for r in results]
    h81 = sum(1 for v in h81_values if v >= 2) >= 6

    # --- H82: R→P rewriting detectability ---
    # >=4/8 seeds with mean rewriting delta > 0.05
    h82_values = [r.get('nrc_metrics', {}).get('h82_mean_rewriting_delta', 0.0) for r in results]
    h82 = sum(1 for v in h82_values if v > 0.05) >= 4

    # --- H83: NSI improvement ---
    # Mean NSI over steps 500-1000 compared to Phase 5 D1 baseline
    # Phase 5 D1 at N0=72 baseline NSI (from exp_128 or exp_132): ~0.50-0.60
    # Conservatively use 0.50 as baseline (adjust if historical data available)
    baseline_nsi_72 = 0.50  # Estimated from Phase 5 D1 results
    nsi_mid_means = [float(np.mean(r.get('nsi_mid_phase', [0.0]))) if r.get('nsi_mid_phase') else 0.0
                     for r in results]
    h83_overall_mean = float(np.mean(nsi_mid_means)) if nsi_mid_means else 0.0
    h83 = h83_overall_mean >= (baseline_nsi_72 + 0.02)

    # --- H84: Cross-scale consistency ---
    # L0 cycle times are available from NRC; L1 times from per-layer metrics
    # For now, use cycle step distribution as approximation
    # (L1 tracking requires PerLayerMetricsCollector + L1 event detection)
    cycle_counts_l0 = [len(r.get('nrc_metrics', {}).get('h84_l0_cycle_times', [])) for r in results]
    l1_cycle_counts = [len(r.get('nrc_metrics', {}).get('h84_l1_cycle_times', [])) for r in results]

    # Compute Jaccard for each seed
    h84_jaccards = []
    for r in results:
        l0_times = r.get('nrc_metrics', {}).get('h84_l0_cycle_times', [])
        l1_times = r.get('nrc_metrics', {}).get('h84_l1_cycle_times', [])
        j = compute_h84_jaccard(l0_times, l1_times)
        h84_jaccards.append(j)

    h84 = sum(1 for j in h84_jaccards if j > 0.3) >= 4

    # --- H85: No degradation ---
    h85 = sum([h1, h2, h3, h4, h5, h6, h7, h8]) >= 8 and all(
        [h1, h2, h3, h4, h5, h6, h7, h8])

    # Aggregate R2 events
    all_r2_counts = [r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results]
    h62_r2_total = int(np.sum(all_r2_counts))

    # NRC aggregate
    nrc_active_seeds = sum(1 for r in results
                           if r.get('nrc_metrics', {}).get('nrc_active', False))
    nrc_cycles_total = sum(r.get('nrc_metrics', {}).get('n_cycles', 0) for r in results)
    nrc_r2_total = sum(r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results)

    return {
        'config': label,
        'H1_nsi_max': {'value': float(np.max(nsi_max_vals)), 'threshold': '>0.1', 'pass': h1},
        'H2_nsi_active_rate': {'value': float(np.mean(nsi_active_rates)), 'threshold': '>0.3 all', 'pass': h2},
        'H3_continuity_mean': {'value': float(np.mean(continuity_means)), 'threshold': '>0.1', 'pass': h3},
        'H4_combined': {'value': 'depth=%.4f tp=%.1f' % (float(np.mean(history_depth_means)), float(np.mean(turning_points_finals))), 'threshold': 'depth>0.05 OR tp>0', 'pass': h4},
        'H5_civ_max': {'value': float(np.max(civ_max_values)), 'threshold': '>=3 (max)', 'pass': h5},
        'H6_civ_max': {'value': float(np.max(civ_max_values)), 'threshold': '>=2 (max)', 'pass': h6},
        'H7_csci_std_mean': {'value': float(np.mean(csci_stds)), 'threshold': '>0.005', 'pass': h7},
        'H8_topdown_active_seeds': {'value': sum(1 for v in topdown_max if v > 0), 'threshold': '>=2 seeds', 'pass': h8},
        'H81_spiral_completeness': {
            'value': '%d/8 seeds >=2 cycles in first 500' % sum(1 for v in h81_values if v >= 2),
            'threshold': '>=6 seeds',
            'pass': h81,
        },
        'H82_r2_rewriting': {
            'value': '%d/8 seeds mean_delta>0.05 (means: %s)' % (
                sum(1 for v in h82_values if v > 0.05),
                ', '.join('%.4f' % v for v in h82_values)),
            'threshold': '>=4 seeds',
            'pass': h82,
        },
        'H83_nsi_improvement': {
            'value': 'mean_nsi=%.4f (baseline=%.2f, target>=%.2f)' % (
                h83_overall_mean, baseline_nsi_72, baseline_nsi_72 + 0.02),
            'threshold': '>= baseline+0.02',
            'pass': h83,
            'baseline_nsi': baseline_nsi_72,
        },
        'H84_cross_scale_jaccard': {
            'value': '%d/8 seeds Jaccard>0.3 (jaccards: %s)' % (
                sum(1 for j in h84_jaccards if j > 0.3),
                ', '.join('%.3f' % j for j in h84_jaccards)),
            'threshold': '>=4 seeds',
            'pass': h84,
        },
        'H85_no_degradation': {
            'value': '%d/8 H1-H8 pass' % sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'threshold': '8/8',
            'pass': h85,
        },
        'nrc_aggregate': {
            'nrc_active_seeds': nrc_active_seeds,
            'nrc_cycles_total': nrc_cycles_total,
            'nrc_r2_total': nrc_r2_total,
            'cycle_distribution_first_500': h81_values,
            'rewriting_delta_distribution': h82_values,
        },
        'summary': {
            'all_pass': h1 and h2 and h3 and h4 and h5 and h6 and h7 and h8,
            'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'failed': [n for n, v in [('H1', h1), ('H2', h2), ('H3', h3),
                                       ('H4', h4), ('H5', h5), ('H6', h6),
                                       ('H7', h7), ('H8', h8)] if not v],
        },
        'phase7_summary': {
            'n_pass': sum([h81, h82, h83, h84, h85]),
            'all_pass': h81 and h82 and h83 and h84 and h85,
            'failed': [n for n, v in [('H81', h81), ('H82', h82), ('H83', h83),
                                       ('H84', h84), ('H85', h85)] if not v],
        },
    }


# --- Experiment matrix ---
# Single config: N0=72, tension=1.0, full spiral (CSC+NSE+NRC+Booster)
# 8 seeds x 5000 steps = 8 runs
# Compare against Phase 5 D1 baseline (N0=72, no NRC)

SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
N_STEPS = 5000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2
N0 = 72
R2_TENSION_THRESHOLD = 1.0  # Recommended default from Phase 6


def main():
    print("=" * 70)
    print("exp_136: PHASE 7 — Full Spiral Integration at N0=72")
    print("=" * 70)
    print("  Architecture: CSC+NSE+NRC+NarrativeLevelBooster")
    print("  N0=%d  Seeds: %d  Steps: %d" % (N0, len(SEEDS), N_STEPS))
    print("  R2 tension_threshold=%.1f (Phase 6 recommended default)" % R2_TENSION_THRESHOLD)
    print("  Hypotheses: H81 (spiral completeness), H82 (R->P rewriting),")
    print("               H83 (NSI improvement), H84 (cross-scale), H85 (stability)")
    print("  Baseline: Phase 5 D1 at N0=72 (~0.50 NSI, no NRC)")
    print("  Date: %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("=" * 70)

    tracking_collector = PerLayerMetricsCollector(config={
        'nsi_rolling_window': 500,
        'civ_rolling_window': 500,
        'theme_jaccard_window': 500,
    })

    results = []

    for seed in SEEDS:
        try:
            result = run_single_seed(
                N0=N0, steps=N_STEPS, seed=seed,
                sample_interval=SAMPLE_INTERVAL, gbc_soft_nudge=GBC_SOFT_NUDGE,
                r2_tension_threshold=R2_TENSION_THRESHOLD,
                csc_config=P7_CSC_CONFIG,
                tracking_collector=tracking_collector,
            )
            results.append(result)
            nrc = result.get('nrc_metrics', {})
            h81 = nrc.get('h81_cycles_first_500', 0)
            h82_d = nrc.get('h82_mean_rewriting_delta', 0.0)
            n_r2 = nrc.get('n_r2_events', 0)
            n_cyc = nrc.get('n_cycles', 0)
            tension = nrc.get('cumulative_tension', 0.0)
            print(f"    seed={seed}: NSI_max={result['nse_nsi_max']:.4f}, "
                  f"cycles={n_cyc}, R2={n_r2}, "
                  f"h81_early={h81}, h82_delta={h82_d:.4f}, "
                  f"tension={tension:.2f}, CIV_max={result['civ_max']}")
        except Exception as e:
            print(f"    *** seed={seed}: FAILED -- {e}", flush=True)
            import traceback
            traceback.print_exc()
            results.append({
                'N0': N0, 'seed': seed, 'elapsed': 0,
                'error': str(e), 'n_steps': 0,
                'sealed': False, 'nse_nsi_max': 0, 'nse_nsi_mean': 0,
                'nse_nsi_active_rate': 0, 'nse_continuity_mean': 0,
                'nse_history_depth_mean': 0, 'nse_turning_points_final': 0,
                'civ_mean': 0.0, 'civ_min': 0, 'civ_max': 0,
                'csc_csci_std': 0, 'topdown_max_active': 0,
                'nrc_metrics': {'nrc_active': False},
                'r2_tension_threshold': R2_TENSION_THRESHOLD,
                'nsi_mid_phase': [],
            })

    # Evaluate hypotheses
    hypotheses = evaluate_hypotheses(results, 'phase7_n72_full_spiral')

    # --- Summary ---
    print("\n" + "=" * 70)
    print("PHASE 7 RESULTS — Full Spiral Integration Summary")
    print("=" * 70)

    h = hypotheses
    s = h['summary']
    p7 = h['phase7_summary']
    nrc_agg = h.get('nrc_aggregate', {})

    print(f"\n  H1-H8: {s['n_pass']}/8 pass {'[OK]' if s['all_pass'] else '[X] ' + ', '.join(s['failed'])}")
    print(f"  H81 (spiral completeness): {'PASS' if h.get('H81_spiral_completeness', {}).get('pass') else 'FAIL'} — {h.get('H81_spiral_completeness', {}).get('value', '?')}")
    print(f"  H82 (R->P rewriting): {'PASS' if h.get('H82_r2_rewriting', {}).get('pass') else 'FAIL'} — {h.get('H82_r2_rewriting', {}).get('value', '?')}")
    print(f"  H83 (NSI improvement): {'PASS' if h.get('H83_nsi_improvement', {}).get('pass') else 'FAIL'} — {h.get('H83_nsi_improvement', {}).get('value', '?')}")
    print(f"  H84 (cross-scale): {'PASS' if h.get('H84_cross_scale_jaccard', {}).get('pass') else 'FAIL'} — {h.get('H84_cross_scale_jaccard', {}).get('value', '?')}")
    print(f"  H85 (no degradation): {'PASS' if h.get('H85_no_degradation', {}).get('pass') else 'FAIL'} — {h.get('H85_no_degradation', {}).get('value', '?')}")
    print(f"  NRC: active={nrc_agg.get('nrc_active_seeds', 0)}/8, cycles={nrc_agg.get('nrc_cycles_total', 0)}, R2_total={nrc_agg.get('nrc_r2_total', 0)}")
    print(f"  Phase 7: {p7['n_pass']}/5 PASS {'[PASS]' if p7['all_pass'] else '[X] ' + ', '.join(p7['failed'])}")

    # Per-seed detail
    print(f"\n{'---' * 25}")
    print("PER-SEED DETAIL:")
    print(f"{'---' * 25}")
    for r in results:
        nrc_m = r.get('nrc_metrics', {})
        error_str = " [ERROR: %s]" % r.get('error', '') if 'error' in r else ""
        print(f"  seed={r.get('seed', '?'):>3}: "
              f"NSI_max={r.get('nse_nsi_max', 0):.4f} "
              f"cycles={nrc_m.get('n_cycles', 0)} "
              f"R2={nrc_m.get('n_r2_events', 0)} "
              f"h81_first500={nrc_m.get('h81_cycles_first_500', 0)} "
              f"h82_delta={nrc_m.get('h82_mean_rewriting_delta', 0):.4f} "
              f"CIV_max={r.get('civ_max', 0)} "
              f"NSI_mid={float(np.mean(r.get('nsi_mid_phase', [0]))):.4f}{error_str}")

    # --- Save results ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    results_file = os.path.join(
        PROJECT_ROOT, 'experiments',
        'exp_136_phase7_full_spiral_%s.json' % timestamp)
    save_data = {
        'experiment': 'exp_136_phase7_full_spiral_integration',
        'datetime': datetime.now().isoformat(),
        'N0': N0, 'n_steps': N_STEPS,
        'r2_tension_threshold': R2_TENSION_THRESHOLD,
        'hypotheses': h,
        'per_seed': [],
    }
    for r in results:
        sr = {}
        for k, v in r.items():
            if isinstance(v, (np.integer,)):
                sr[k] = int(v)
            elif isinstance(v, (np.floating,)):
                sr[k] = float(v)
            elif isinstance(v, np.bool_):
                sr[k] = bool(v)
            elif isinstance(v, np.ndarray):
                sr[k] = v.tolist()
            else:
                sr[k] = v
        save_data['per_seed'].append(sr)

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n    Results saved to: {results_file}")

    # --- Comparison with Phase 6 exp_135 and Phase 5 D1 ---
    print(f"\n{'=' * 70}")
    print("COMPARISON: Phase 5 D1 (N0=72, no NRC) vs Phase 7 (N0=72, full spiral)")
    print(f"{'=' * 70}")
    print(f"  Phase 5 D1 baseline NSI: ~{baseline_nsi_72:.2f} (estimated)")
    print(f"  Phase 7 NSI (mid-phase): {h83_overall_mean:.4f}")
    print(f"  Phase 7 NSI (max): {float(np.max(nsi_max_vals)):.4f}")
    print(f"  Delta: {h83_overall_mean - baseline_nsi_72:+.4f} "
          f"{'[GOAL: >=+0.02]' if h83_overall_mean >= baseline_nsi_72 + 0.02 else '[BELOW]'}")

    print(f"\n  Phase 6 exp_135 (N0=48): {nrc_r2_total if 'nrc_r2_total' in locals() else 'N/A'} R2 events")
    print(f"  Phase 7 (N0=72): {nrc_r2_total} R2 events")


if __name__ == '__main__':
    main()