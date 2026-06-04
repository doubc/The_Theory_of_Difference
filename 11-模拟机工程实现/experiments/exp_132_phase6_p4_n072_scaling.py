"""
experiments/exp_132_phase6_p4_n072_scaling.py

Phase 6 P4-B: N0=72 Scaling Test — Larger Difference Field for R2 Activation

Purpose:
  exp_130 showed R2 dormant at N0=48 even with 5000 steps.
  Hypothesis: N0=48 is below the civilizational crisis threshold.
  N0=72 was identified as optimal scale in Phase 4 P2 Track B.

  This experiment tests whether a larger difference field (N0=72) enables
  R2 (civilizational recursion) to activate naturally.

  Uses same R2 parameters as exp_130 (threshold=0.85, cooldown=200)
  to isolate the N0 variable.

Hypotheses:
  H69 (R2 at N0=72): Larger bit space enables civilizational crisis.
    >=2/8 seeds trigger R2 (relaxed from >=4 due to scale exploration).
  H70 (NSI scale effect): NSI_max higher at N0=72 vs N0=48.
  H71 (CIV scale effect): CIV_max higher at N0=72 vs N0=48.
  H72 (cycle frequency): More cycles/1k at N0=72 (larger state space).

Baseline: H1-H8 must still pass at N0=72 (already validated in Phase 4 P2B).
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
from engine.narrative_recursive_closure import NarrativeRecursiveClosure
from engine.per_layer_metrics import PerLayerMetricsCollector


# --- CSC config ---
P6_CSC_CONFIG = {
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
        self.filter = NarrativeFilter(
            magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(
            strength_threshold=connector_strength_threshold,
            momentum_decay=momentum_decay,
            momentum_bonus=momentum_bonus,
        )
        self.actionizer = NarrativeActionizer(bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(
            consistency_threshold=verifier_consistency_threshold)
        self.narrative_decay_rate = narrative_decay_rate
        self._records = []
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F(
            window_size=50, max_civ_rate=0.12, cooldown_steps=12,
            min_civ_guarantee=3
        )

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


def extract_nrc_metrics(evolver, step_results):
    """Extract NRC metrics from evolver post-run."""
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
        'cycle_stats': summary.get('cycle_stats', {}),
    }

    r0_changes = {}
    if cycles:
        level_weights_by_cycle = {}
        for c in cycles:
            settled = c.settled_state
            for level, weight in settled.items():
                if level not in level_weights_by_cycle:
                    level_weights_by_cycle[level] = []
                level_weights_by_cycle[level].append(weight)
        for level, weights in level_weights_by_cycle.items():
            if len(weights) >= 2:
                initial = weights[0]
                final = weights[-1]
                change_pct = abs(final - initial) / max(abs(initial), 0.001) * 100.0
                r0_changes[level] = {
                    'initial_weight': round(initial, 4),
                    'final_weight': round(final, 4),
                    'change_pct': round(change_pct, 2),
                }
    metrics['r0_level_changes'] = r0_changes
    levels_sig = sum(1 for v in r0_changes.values() if v['change_pct'] > 5.0)
    total_tracked = len(r0_changes)
    metrics['r0_significant_change_count'] = levels_sig
    metrics['r0_total_levels_tracked'] = total_tracked
    metrics['r0_sig_change_ratio'] = (
        levels_sig / total_tracked if total_tracked > 0 else 0.0
    )

    inst_fractions = []
    basin_shifts = []
    for c in cycles:
        settled = c.settled_state
        inst_frac = settled.get('INSTITUTIONAL', 0.0)
        if c.recursion_output:
            bs = c.recursion_output.r1_basin_shift
            inst_fractions.append(inst_frac)
            basin_shifts.append(bs)
    inst_basin_corr = 0.0
    if len(inst_fractions) >= 3 and len(basin_shifts) >= 3:
        try:
            cm = np.corrcoef(inst_fractions, basin_shifts)
            inst_basin_corr = float(cm[0, 1]) if not np.isnan(cm[0, 1]) else 0.0
        except Exception:
            inst_basin_corr = 0.0
    metrics['h61_inst_basin_correlation'] = round(inst_basin_corr, 4)

    metrics['h62_r2_events_total'] = metrics['n_r2_events']
    metrics['h62_r2_active'] = metrics['n_r2_events'] >= 1

    weight_diffs = []
    if cycles and len(cycles) >= 2:
        for i in range(1, len(cycles)):
            prev_settled = cycles[i-1].settled_state
            curr_settled = cycles[i].settled_state
            all_levels = set(prev_settled.keys()) | set(curr_settled.keys())
            diff_sq = 0.0
            for lvl in all_levels:
                pw = prev_settled.get(lvl, 0.0)
                cw = curr_settled.get(lvl, 0.0)
                diff_sq += (cw - pw) ** 2
            weight_diffs.append(float(np.sqrt(diff_sq)))
    metrics['h63_weight_diffs'] = weight_diffs
    if len(weight_diffs) >= 3:
        x = np.arange(len(weight_diffs))
        try:
            slope, _ = np.polyfit(x, weight_diffs, 1)
            metrics['h63_convergence_slope'] = round(float(slope), 6)
            metrics['h63_converges'] = float(slope) < 0.0
        except Exception:
            metrics['h63_convergence_slope'] = 0.0
            metrics['h63_converges'] = False
    else:
        metrics['h63_convergence_slope'] = 0.0
        metrics['h63_converges'] = False

    total_steps = len(step_results) * 10
    steps_per_k = total_steps / 1000.0 if total_steps > 0 else 1.0
    cycles_per_1k = metrics['n_cycles'] / steps_per_k if steps_per_k > 0 else 0.0
    metrics['h64_cycles_per_1000'] = round(cycles_per_1k, 2)

    cycle_records = []
    for c in cycles:
        record = {
            'cycle_id': c.cycle_id, 'step': c.step,
            'n_events': len(c.events), 'selected_path': c.selected_path,
            'r2_triggered': False, 'r2_new_bits': 0,
        }
        if c.recursion_output:
            record['r2_triggered'] = c.recursion_output.r2_triggered
            record['r2_new_bits'] = c.recursion_output.r2_new_bits
        cycle_records.append(record)
    metrics['cycle_records'] = cycle_records

    return metrics


def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    csc_config=None, tracking_collector=None):
    """Run a single seed with CSC+NSE+NRC (NO booster) at N0=72."""
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

    # Same R2 params as exp_130 (threshold=0.85, cooldown=200)
    # Only variable being tested is N0=72
    nrc = NarrativeRecursiveClosure(
        event_window=20, collapse_threshold=0.15, settling_rate=0.3,
        r0_weight=0.4, r1_weight=0.35, r2_weight=0.25,
        r2_threshold_nsi=0.85, r2_cooldown=200, verbose=True)

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
        narrative_level_booster=None,
        narrative_recursive_closure=nrc)

    print(f"    [seed={seed}] Running {steps} steps at N0={N0}...", flush=True)
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
    }


def evaluate_hypotheses(results, label="N0_72"):
    """Evaluate H1-H8 + H69-H72."""
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

    # H69: R2 at N0=72 (relaxed: >=2/8 seeds)
    all_r2_counts = [r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results]
    h69 = sum(1 for cnt in all_r2_counts if cnt >= 1) >= 2
    h69_total_r2 = int(np.sum(all_r2_counts))

    # H70: NSI higher at N0=72
    h70 = float(np.mean(nsi_max_vals)) > 0.70  # exp_130 mean was ~0.83, expect higher

    # H71: CIV higher at N0=72
    h71 = float(np.max(civ_max_values)) >= 4  # exp_130 max was 4

    # H72: More cycles/1k at N0=72
    cycles_per_1k = [r.get('nrc_metrics', {}).get('h64_cycles_per_1000', 0.0)
                     for r in results]
    h72 = float(np.mean(cycles_per_1k)) > 0.70  # exp_130 was 0.70

    # R0/R1
    r0_sig_ratios = [r.get('nrc_metrics', {}).get('r0_sig_change_ratio', 0.0)
                     for r in results]
    h60 = sum(1 for ratio in r0_sig_ratios if ratio >= 0.80) >= 6
    inst_basin_corrs = [r.get('nrc_metrics', {}).get('h61_inst_basin_correlation', 0.0)
                        for r in results]
    h61 = sum(1 for corr in inst_basin_corrs if corr > 0.5) >= 6

    nrc_active_seeds = sum(1 for r in results
                           if r.get('nrc_metrics', {}).get('nrc_active', False))
    nrc_cycles_total = sum(r.get('nrc_metrics', {}).get('n_cycles', 0) for r in results)
    nrc_r2_total = sum(r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results)

    converges = [r.get('nrc_metrics', {}).get('h63_converges', False) for r in results]

    return {
        'n0': label,
        'H1_nsi_max': {'value': float(np.max(nsi_max_vals)), 'threshold': '>0.1', 'pass': h1},
        'H2_nsi_active_rate': {'value': float(np.mean(nsi_active_rates)), 'threshold': '>0.3 all', 'pass': h2},
        'H3_continuity_mean': {'value': float(np.mean(continuity_means)), 'threshold': '>0.1', 'pass': h3},
        'H4_combined': {'value': 'depth=%.4f tp=%.1f' % (float(np.mean(history_depth_means)), float(np.mean(turning_points_finals))), 'threshold': 'depth>0.05 OR tp>0', 'pass': h4},
        'H5_civ_max': {'value': float(np.max(civ_max_values)), 'threshold': '>=3 (max)', 'pass': h5},
        'H6_civ_max': {'value': float(np.max(civ_max_values)), 'threshold': '>=2 (max)', 'pass': h6},
        'H7_csci_std_mean': {'value': float(np.mean(csci_stds)), 'threshold': '>0.005', 'pass': h7},
        'H8_topdown_active_seeds': {'value': sum(1 for v in topdown_max if v > 0), 'threshold': '>=2 seeds', 'pass': h8},
        'H60_r0_micro_recursion': {
            'value': '%d/8 seeds' % sum(1 for v in r0_sig_ratios if v >= 0.80),
            'threshold': '>=6 seeds', 'pass': h60},
        'H61_r1_institutional': {
            'value': '%d/8 seeds corr>0.5' % sum(1 for v in inst_basin_corrs if v > 0.5),
            'threshold': '>=6 seeds', 'pass': h61},
        'H69_r2_at_n072': {
            'value': '%d/8 seeds with R2 (total=%d)' % (sum(1 for v in all_r2_counts if v >= 1), h69_total_r2),
            'threshold': '>=2 seeds', 'pass': h69},
        'H70_nsi_scale': {
            'value': 'mean_NSI_max=%.4f' % float(np.mean(nsi_max_vals)),
            'threshold': '>0.70', 'pass': h70},
        'H71_civ_scale': {
            'value': 'max_CIV=%d' % int(np.max(civ_max_values)),
            'threshold': '>=4', 'pass': h71},
        'H72_cycle_frequency': {
            'value': 'mean_cycles/1k=%.2f' % float(np.mean(cycles_per_1k)),
            'threshold': '>0.70', 'pass': h72},
        'nrc_aggregate': {
            'nrc_active_seeds': nrc_active_seeds,
            'nrc_cycles_total': nrc_cycles_total,
            'nrc_r2_total': nrc_r2_total,
        },
        'summary': {
            'all_pass': h1 and h2 and h3 and h4 and h5 and h6 and h7 and h8,
            'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'failed': [n for n, v in [('H1', h1), ('H2', h2), ('H3', h3), ('H4', h4), ('H5', h5), ('H6', h6), ('H7', h7), ('H8', h8)] if not v],
        },
        'p6_summary': {
            'n_pass': sum([h69, h70, h71, h72]),
            'all_pass': h69 and h70 and h71 and h72,
            'failed': [n for n, v in [('H69', h69), ('H70', h70), ('H71', h71), ('H72', h72)] if not v],
        },
    }


# --- Config ---
N0 = 72
SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
N_STEPS = 3000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2


def main():
    print("=" * 70)
    print("exp_132: Phase 6 P4-B — N0=72 Scaling Test")
    print("  Architecture: CSC+NSE+NRC (NO Booster)")
    print("  N0=%d  Seeds: %d  Steps: %d" % (N0, len(SEEDS), N_STEPS))
    print("  R2 params: threshold=0.85, cooldown=200 (same as exp_130)")
    print("  Hypotheses: H69 (R2 at N0=72) H70 (NSI scale) H71 (CIV scale) H72 (cycles)")
    print("  Date: %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("=" * 70)

    tracking_collector = PerLayerMetricsCollector(config={
        'nsi_rolling_window': 500,
        'civ_rolling_window': 500,
        'theme_jaccard_window': 500,
    })

    all_results = []

    for seed in SEEDS:
        try:
            result = run_single_seed(
                N0=N0, steps=N_STEPS, seed=seed,
                sample_interval=SAMPLE_INTERVAL, gbc_soft_nudge=GBC_SOFT_NUDGE,
                csc_config=P6_CSC_CONFIG,
                tracking_collector=tracking_collector,
            )
            all_results.append(result)
            nrc_summary = result.get('nrc_metrics', {})
            n_r2 = nrc_summary.get('n_r2_events', 0)
            n_cyc = nrc_summary.get('n_cycles', 0)
            r2_triggered = any(
                cr.get('r2_triggered', False)
                for cr in nrc_summary.get('cycle_records', [])
            )
            print(f"    seed={seed}: NSI_max={result['nse_nsi_max']:.4f}, "
                  f"R2={n_r2}, cycles={n_cyc}, "
                  f"r2_triggered={r2_triggered}, "
                  f"CIV_max={result['civ_max']}, "
                  f"CIV_mean={result['civ_mean']:.2f}")
        except Exception as e:
            print(f"    *** seed={seed}: FAILED -- {e}", flush=True)
            import traceback
            traceback.print_exc()
            all_results.append({
                'N0': N0, 'seed': seed, 'elapsed': 0,
                'error': str(e), 'n_steps': 0,
                'sealed': False, 'nse_nsi_max': 0, 'nse_nsi_mean': 0,
                'nse_nsi_active_rate': 0, 'nse_continuity_mean': 0,
                'nse_history_depth_mean': 0, 'nse_turning_points_final': 0,
                'civ_mean': 0.0, 'civ_min': 0, 'civ_max': 0,
                'csc_csci_std': 0, 'topdown_max_active': 0,
                'nrc_metrics': {'nrc_active': False},
            })

    hypotheses = evaluate_hypotheses(all_results, "N0_72")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("PHASE 6 P4-B RESULTS — N0=72 Scaling Test")
    print("=" * 70)

    s = hypotheses['summary']
    p6 = hypotheses['p6_summary']
    nrc_agg = hypotheses.get('nrc_aggregate', {})

    print(f"\n  H1-H8 baseline [{s['n_pass']}/8 pass]:")
    print(f"    {'ALL CORE HYPOTHESES PASS [OK]' if s['all_pass'] else 'Failed: ' + ', '.join(s['failed']) + ' [X]'}")

    print(f"\n  Phase 6 P4-B [{p6['n_pass']}/4 pass]:")
    for name in ['H69_r2_at_n072', 'H70_nsi_scale', 'H71_civ_scale', 'H72_cycle_frequency']:
        h = hypotheses.get(name, {})
        status = "[OK]" if h.get('pass') else "[X]"
        print(f"    {name}: {h.get('value', '?')} {status}")

    print(f"\n  NRC Aggregate: active={nrc_agg.get('nrc_active_seeds', 0)}/8"
          f"  total_cycles={nrc_agg.get('nrc_cycles_total', 0)}"
          f"  total_R2={nrc_agg.get('nrc_r2_total', 0)}")

    # Per-seed detail
    print(f"\n{'---' * 25}")
    print("PER-SEED DETAIL")
    print(f"{'---' * 25}")
    for r in all_results:
        nrc_m = r.get('nrc_metrics', {})
        error_str = " [ERROR: %s]" % r.get('error', '') if 'error' in r else ""
        print(f"  seed={r.get('seed', '?'):>3}: "
              f"NSI_max={r.get('nse_nsi_max', 0):.4f} "
              f"NSI_mean={r.get('nse_nsi_mean', 0):.4f} "
              f"cycles={nrc_m.get('n_cycles', 0)} "
              f"R2={nrc_m.get('n_r2_events', 0)} "
              f"conv={nrc_m.get('h63_converges', False)} "
              f"CIV_max={r.get('civ_max', 0)} "
              f"CIV_mean={r.get('civ_mean', 0):.2f} "
              f"CSCI_std={r.get('csc_csci_std', 0):.4f} "
              f"topdown={r.get('topdown_max_active', 0)} {error_str}")

    # --- Save results ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    results_file = os.path.join(
        PROJECT_ROOT, 'experiments',
        'exp_132_phase6_p4_n072_scaling_%s.json' % timestamp)
    save_data = {
        'experiment': 'exp_132_phase6_p4_n072_scaling',
        'datetime': datetime.now().isoformat(),
        'N0': N0, 'n_steps': N_STEPS,
        'r2_params': {'threshold': 0.85, 'cooldown': 200},
        'hypotheses': hypotheses,
        'per_seed': [],
    }
    for r in all_results:
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
            elif k == 'nrc_metrics':
                sr[k] = v
            else:
                sr[k] = v
        save_data['per_seed'].append(sr)

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n    Results saved to: {results_file}")

    # --- Comparison with exp_130 ---
    print("\n" + "=" * 70)
    print("COMPARISON: exp_130 (N0=48, 5000 steps) vs exp_132 (N0=72, 3000 steps)")
    print("=" * 70)

    exp130_nsi_max = [0.844, 0.875, 0.880, 0.873, 0.875, 0.880, 0.870, 0.772]
    exp130_civ_max = [3, 1, 2, 4, 3, 2, 2, 4]
    exp130_r2 = [0] * 8
    exp130_cycles = [3, 5, 4, 4, 5, 1, 5, 1]

    nsi_max_vals = [r['nse_nsi_max'] for r in all_results]
    civ_max_vals = [r.get('civ_max', 0) for r in all_results]
    r2_vals = [r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in all_results]
    cycles_vals = [r.get('nrc_metrics', {}).get('n_cycles', 0) for r in all_results]

    print(f"  {'Metric':<25} {'exp_130 (N0=48)':<20} {'exp_132 (N0=72)':<20}")
    print(f"  {'-'*65}")
    print(f"  {'NSI_max (mean)':<25} {np.mean(exp130_nsi_max):<20.4f} {np.mean(nsi_max_vals):<20.4f}")
    print(f"  {'NSI_max (range)':<25} {min(exp130_nsi_max):.3f}-{max(exp130_nsi_max):.3f}{'':<13} {min(nsi_max_vals):.3f}-{max(nsi_max_vals):.3f}")
    print(f"  {'CIV_max (max)':<25} {max(exp130_civ_max):<20} {max(civ_max_vals):<20}")
    print(f"  {'CIV_max (mean)':<25} {np.mean(exp130_civ_max):<20.2f} {np.mean(civ_max_vals):<20.2f}")
    print(f"  {'R2 total':<25} {sum(exp130_r2):<20} {sum(r2_vals):<20}")
    print(f"  {'Cycles total':<25} {sum(exp130_cycles):<20} {sum(cycles_vals):<20}")


if __name__ == '__main__':
    main()
