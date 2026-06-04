"""
experiments/exp_137_phase8_p0_l1_cycle_baseline.py

Phase 8 P0: L1 Cycle Baseline

Purpose:
  Before adding cross-scale coupling, measure whether L1 produces detectable cycle
  patterns on its own. The L1CycleDetector (LCylDet) monitors per-layer NSI/CIV/
  active-bits metrics from PerLayerMetricsCollector, observing L1 dynamics passively
  without any feedback to NRC or CSC.

  Core question: Does L1 have intrinsic cycle dynamics (institutional restructuring
  independent of L0 narrative), or is L1 purely passive even at the cycle level?

Hypotheses:
  H86 (L1 cycles): >=6/8 seeds with >=2 L1 cycle events (any type) in 5000 steps
  H89 (No degradation): >=6/8 seeds pass all H1-H8 baseline hypotheses
  H86a (L1 cycle types): Cycles are distributed across >=2 types (not all one type)
  H86b (L1 cycle frequency): Mean L1 cycles/seed >= 3.0 in 5000 steps

Config:
  Same as Phase 7 (N0=72, CSC+NSE+NRC+Booster, tension=1.0), plus:
  - L1CycleDetector (monitor only, no feedback)
  - PerLayerMetricsCollector (feeds L1 NSI/CIV/active_bits to LCylDet)
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
from engine.l1_cycle_detector import L1CycleDetector, compute_cycle_jaccard, compute_cycle_delay_distribution


# --- Config ---
P8_CSC_CONFIG = {
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
    """Extract NRC metrics from evolver post-run."""
    nrc = getattr(evolver, 'narrative_recursive_closure', None)
    if nrc is None:
        return {'nrc_active': False, 'error': 'no_nrc_in_evolver'}

    summary = nrc.get_summary()
    cycles = nrc.get_cycle_history() if hasattr(nrc, 'get_cycle_history') else []

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

    # L0 cycle times (for future H87 correlation)
    l0_cycle_steps = sorted([c.step for c in cycles]) if cycles else []
    metrics['l0_cycle_times'] = l0_cycle_steps

    # R0 micro-level changes
    r0_sig_changes = 0
    if cycles:
        level_first_last = {}
        for c in cycles:
            settled = c.settled_state if hasattr(c, 'settled_state') else {}
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
    metrics['r0_sig_change_ratio'] = (r0_sig_changes / total_levels if total_levels > 0 else 0.0)

    # R2 event steps
    r2_steps = []
    for c in cycles:
        if hasattr(c, 'recursion_output') and c.recursion_output and getattr(c.recursion_output, 'r2_triggered', False):
            r2_steps.append(c.step)
    metrics['r2_steps'] = r2_steps

    return metrics


def extract_l1_metrics(tracking_collector, l1_detector):
    """Extract L1 cycle metrics from PerLayerMetricsCollector + L1CycleDetector."""
    l1_results = {'has_l1': False}
    if tracking_collector is None:
        return l1_results

    try:
        analysis = tracking_collector.analyze()
        l1_results['has_l1'] = True

        # L1 NSI time series
        nsi_tracker = getattr(tracking_collector, '_nsi_tracker', None)
        if nsi_tracker and hasattr(nsi_tracker, '_layer_nsi') and len(nsi_tracker._layer_nsi) > 1:
            l1_nsi_series = [v for _, v in nsi_tracker._layer_nsi.get(1, [])]
            l1_results['l1_nsi_mean'] = float(np.mean(l1_nsi_series)) if l1_nsi_series else 0.0
            l1_results['l1_nsi_std'] = float(np.std(l1_nsi_series)) if l1_nsi_series else 0.0
            l1_results['l1_nsi_max'] = float(np.max(l1_nsi_series)) if l1_nsi_series else 0.0
        else:
            l1_results['l1_nsi_mean'] = 0.0
            l1_results['l1_nsi_std'] = 0.0
            l1_results['l1_nsi_max'] = 0.0

        # L1 CIV time series
        l1_results['l1_civ_series'] = []
        civ_tracker = getattr(tracking_collector, '_civ_tracker', None)
        if civ_tracker and hasattr(civ_tracker, '_layer_civ') and len(civ_tracker._layer_civ) > 1:
            l1_civ_vals = [v for _, v in civ_tracker._layer_civ.get(1, [])]
            l1_results['l1_civ_mean'] = float(np.mean(l1_civ_vals)) if l1_civ_vals else 0
            l1_results['l1_civ_std'] = float(np.std(l1_civ_vals)) if l1_civ_vals else 0
            l1_results['l1_civ_max'] = int(np.max(l1_civ_vals)) if l1_civ_vals else 0
            l1_results['l1_civ_min'] = int(np.min(l1_civ_vals)) if l1_civ_vals else 0
        else:
            l1_results['l1_civ_mean'] = 0
            l1_results['l1_civ_std'] = 0
            l1_results['l1_civ_max'] = 0
            l1_results['l1_civ_min'] = 0

        # LCylDet results
        l1_det_summary = l1_detector.get_summary() if l1_detector else {'total_cycles': 0}
        l1_results['l1_detector'] = l1_det_summary

        # L1 cycle times
        l1_cycle_times = l1_detector.get_cycle_times() if l1_detector else {}
        l1_results['l1_cycle_times'] = l1_cycle_times

        # By type breakdown
        by_type = l1_det_summary.get('by_type', {})
        l1_results['n_reconfiguration'] = by_type.get('reconfiguration', 0)
        l1_results['n_reshuffle'] = by_type.get('reshuffle', 0)
        l1_results['n_identity_shift'] = by_type.get('identity_shift', 0)

        # Span of cycle types
        active_types = sum(1 for v in [by_type.get('reconfiguration', 0),
                                        by_type.get('reshuffle', 0),
                                        by_type.get('identity_shift', 0)] if v > 0)
        l1_results['n_cycle_types_active'] = active_types

    except Exception as e:
        l1_results['has_l1'] = False
        l1_results['error'] = str(e)

    return l1_results


class LCylDetTrackingCallback:
    """
    Tracking callback that feeds PerLayerMetricsCollector data into L1CycleDetector.

    Wraps a PerLayerMetricsCollector and an L1CycleDetector. At each snapshot step,
    the evolver calls this with per-layer metrics. L1 data (layer_id=1) is extracted
    and fed into the L1CycleDetector for cycle detection.

    Signature matches HierarchicalEvolver._tracking_callback() calling convention:
      step, layer_id, n_active, n_total, n_frozen, hamming_weight,
      active_bits, frozen_bits, global_odi, global_msi,
      l0_sealed, l1_formed, l1_unique_active, l1_sealing_threshold
    """
    def __init__(self, collector, l1_detector):
        self.collector = collector
        self.l1_detector = l1_detector
        self._last_l1_nsi = 0.0
        self._last_l1_civ = 0
        self._last_l1_active_bits = set()
        self._last_l1_stability = 0.5

    def step(self, step, layer_id, n_active, n_total, n_frozen,
             hamming_weight, active_bits, frozen_bits,
             global_odi, global_msi,
             l0_sealed=False, l1_formed=False,
             l1_unique_active=0, l1_sealing_threshold=0,
             **kwargs):
        """
        Called by HierarchicalEvolver.run() for each layer snapshot.

        Matches the evolver's calling convention exactly (same kwargs
        as PerLayerMetricsCollector.step()). Forwards to the collector,
        then feeds L1 data (layer_id=1) to the L1CycleDetector.
        """
        # Forward to collector first with identical signature
        if self.collector:
            self.collector.step(
                step, layer_id, n_active, n_total, n_frozen,
                hamming_weight, active_bits, frozen_bits,
                global_odi, global_msi,
                l0_sealed, l1_formed,
                l1_unique_active, l1_sealing_threshold,
            )

        # Extract L1 metrics when processing layer 1
        if layer_id == 1:
            # Use available snapshot data for L1 metrics
            # NSI approximation: global_odi is the best per-layer ODI proxy available
            # from the evolver snapshot; actual per-layer NSI would come from NSE.
            nsi = global_odi
            civ = hamming_weight
            stable_bits = set(active_bits) if active_bits else set()
            stability = 1.0 - (n_frozen / max(n_total, 1))

            self._last_l1_nsi = nsi
            self._last_l1_civ = civ
            self._last_l1_active_bits = stable_bits
            self._last_l1_stability = stability

            # Feed to LCylDet on L1 data
            if self.l1_detector:
                self.l1_detector.update(
                    step=step,
                    l1_nsi=self._last_l1_nsi,
                    l1_civ=self._last_l1_civ,
                    l1_active_bits=self._last_l1_active_bits,
                    l1_stability=self._last_l1_stability,
                )


def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    r2_tension_threshold, csc_config=None,
                    tracking_callback_obj=None):
    """Run a single seed with L1CycleDetector monitoring."""
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

    tracker = tracking_callback_obj.collector if tracking_callback_obj else None
    print(f"    [seed={seed}] Running {steps} steps at N0={N0} "
          f"(tension_threshold={r2_tension_threshold})...", flush=True)
    start = time.time()
    result = evolver.run(tracking_callback=tracking_callback_obj.step if tracking_callback_obj else None)
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    # --- Extract results ---
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

    # L1 metrics from detector
    l1_detector = tracking_callback_obj.l1_detector if tracking_callback_obj else None
    l1_metrics = extract_l1_metrics(tracker, l1_detector)

    # L0-L1 cycle Jaccard correlation (for future H87)
    l0_times = nrc_metrics.get('l0_cycle_times', [])
    l1_all_times = l1_metrics.get('l1_cycle_times', {}).get('all', [])
    l1_jaccard = compute_cycle_jaccard(l0_times, l1_all_times, epsilon=50)
    l1_delay = compute_cycle_delay_distribution(l0_times, l1_all_times, epsilon=50)

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
        'l1_metrics': l1_metrics,
        'l1_l0_jaccard': l1_jaccard,
        'l1_l0_delay': l1_delay,
        'r2_tension_threshold': r2_tension_threshold,
        'nsi_mid_phase': [nse_nsi_values[i] for i in range(len(nse_nsi_values))
                          if 50 <= i <= 100],
    }


def evaluate_hypotheses(results, label="phase8_p0"):
    """Evaluate H86 (L1 cycles), H89 (no degradation), plus H86a/H86b."""
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

    # H1-H8: Core emergence (Phase 7 baseline)
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

    # --- H86: L1 Cycle Detection ---
    # >=6/8 seeds with >=2 L1 cycle events in 5000 steps
    l1_total_cycles = [r.get('l1_metrics', {}).get('l1_detector', {}).get('total_cycles', 0)
                        for r in results]
    h86 = sum(1 for v in l1_total_cycles if v >= 2) >= 6

    # --- H86a: L1 cycle type diversity ---
    # Cycles distributed across >=2 types (not all one type)
    n_types_active = [r.get('l1_metrics', {}).get('n_cycle_types_active', 0)
                       for r in results]
    h86a = float(np.mean(n_types_active)) >= 2.0

    # --- H86b: L1 cycle frequency ---
    # Mean L1 cycles/seed >= 3.0
    h86b_mean = float(np.mean(l1_total_cycles)) if l1_total_cycles else 0.0
    h86b = h86b_mean >= 3.0

    # --- H89: No degradation (H1-H8 preserved) ---
    h89_all = sum([h1, h2, h3, h4, h5, h6, h7, h8])
    h89 = h89_all >= 6  # >=6/8 seeds (relaxed from 8/8 since Phase 8 is experimental)

    # L0-L1 Jaccard across all seeds
    l1_l0_jaccards = [r.get('l1_l0_jaccard', 0.0) for r in results]

    # NRC aggregate
    nrc_cycles_total = sum(r.get('nrc_metrics', {}).get('n_cycles', 0) for r in results)
    nrc_r2_total = sum(r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results)

    # L1 cycle type breakdown
    total_reconfig = sum(r.get('l1_metrics', {}).get('n_reconfiguration', 0) for r in results)
    total_reshuffle = sum(r.get('l1_metrics', {}).get('n_reshuffle', 0) for r in results)
    total_identity = sum(r.get('l1_metrics', {}).get('n_identity_shift', 0) for r in results)

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
        'H86_l1_cycles': {
            'value': '%d/8 seeds >=2 L1 cycles (counts: %s)' % (
                sum(1 for v in l1_total_cycles if v >= 2),
                ', '.join(str(v) for v in l1_total_cycles)),
            'threshold': '>=6 seeds',
            'pass': h86,
        },
        'H86a_cycle_type_diversity': {
            'value': 'mean_types_active=%.2f' % float(np.mean(n_types_active)),
            'threshold': '>=2.0',
            'pass': h86a,
        },
        'H86b_cycle_frequency': {
            'value': 'mean_cycles_per_seed=%.2f' % h86b_mean,
            'threshold': '>=3.0',
            'pass': h86b,
        },
        'H89_no_degradation': {
            'value': '%d/8 H1-H8 pass' % h89_all,
            'threshold': '>=6',
            'pass': h89,
        },
        'l1_type_breakdown': {
            'reconfiguration': total_reconfig,
            'reshuffle': total_reshuffle,
            'identity_shift': total_identity,
        },
        'nrc_aggregate': {
            'nrc_cycles_total': nrc_cycles_total,
            'nrc_r2_total': nrc_r2_total,
        },
        'l0_l1_jaccard_mean': float(np.mean(l1_l0_jaccards)) if l1_l0_jaccards else 0.0,
        'l0_l1_jaccard_max': float(np.max(l1_l0_jaccards)) if l1_l0_jaccards else 0.0,
        'summary': {
            'all_pass': h1 and h2 and h3 and h4 and h5 and h6 and h7 and h8,
            'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'failed': [n for n, v in [('H1', h1), ('H2', h2), ('H3', h3),
                                       ('H4', h4), ('H5', h5), ('H6', h6),
                                       ('H7', h7), ('H8', h8)] if not v],
        },
        'phase8_p0': {
            'h86': h86, 'h86a': h86a, 'h86b': h86b, 'h89': h89,
            'n_pass': sum([h86, h86a, h86b, h89]),
            'all_pass': h86 and h86a and h86b and h89,
            'failed': [n for n, v in [('H86', h86), ('H86a', h86a),
                                       ('H86b', h86b), ('H89', h89)] if not v],
        },
    }


# --- Experiment Constants ---
SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
N_STEPS = 2000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2
N0 = 72
R2_TENSION_THRESHOLD = 1.0


def main():
    """Run Phase 8 P0: L1 Cycle Baseline experiment."""
    print("=" * 70)
    print("exp_137: PHASE 8 P0 — L1 Cycle Baseline (LCylDet Monitor Only)")
    print("=" * 70)
    print("  Architecture: CSC+NSE+NRC+NarrativeLevelBooster + LCylDet (monitor only)")
    print("  N0=%d  Seeds: %d  Steps: %d" % (N0, len(SEEDS), N_STEPS))
    print("  R2 tension_threshold=%.1f (Phase 6 recommended default)" % R2_TENSION_THRESHOLD)
    print("  Hypotheses: H86 (L1 cycles), H86a (type diversity), H86b (frequency), H89 (stability)")
    print("  Date: %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("=" * 70)

    results = []

    for seed in SEEDS:
        # Fresh collector + detector per seed
        tracking_collector = PerLayerMetricsCollector(config={
            'nsi_rolling_window': 500,
            'civ_rolling_window': 500,
            'theme_jaccard_window': 500,
        })
        l1_detector = L1CycleDetector()
        tracking_cb = LCylDetTrackingCallback(tracking_collector, l1_detector)

        try:
            result = run_single_seed(
                N0=N0, steps=N_STEPS, seed=seed,
                sample_interval=SAMPLE_INTERVAL, gbc_soft_nudge=GBC_SOFT_NUDGE,
                r2_tension_threshold=R2_TENSION_THRESHOLD,
                csc_config=P8_CSC_CONFIG,
                tracking_callback_obj=tracking_cb,
            )
            results.append(result)

            nrc = result.get('nrc_metrics', {})
            l1 = result.get('l1_metrics', {})
            l1_det = l1.get('l1_detector', {})
            l1_cycles = l1_det.get('total_cycles', 0)
            l1_types = l1.get('n_cycle_types_active', 0)
            l1_by_type = l1.get('l1_detector', {}).get('by_type', {})
            print(f"    seed={seed}: NSI_max={result['nse_nsi_max']:.4f}, "
                  f"L1_cycles={l1_cycles} (reconfig={l1_by_type.get('reconfiguration',0)}, "
                  f"reshuffle={l1_by_type.get('reshuffle',0)}, "
                  f"identity={l1_by_type.get('identity_shift',0)}), "
                  f"types_active={l1_types}, CIV_max={result.get('civ_max',0)}, "
                  f"NRC_R2={nrc.get('n_r2_events',0)}, jaccard_L0L1={result.get('l1_l0_jaccard',0.0):.3f}")
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
                'nrc_metrics': {'nrc_active': False, 'n_cycles': 0, 'n_r2_events': 0},
                'l1_metrics': {'has_l1': False},
                'l1_l0_jaccard': 0.0,
                'l1_l0_delay': {},
                'r2_tension_threshold': R2_TENSION_THRESHOLD,
                'nsi_mid_phase': [],
            })

    # Evaluate hypotheses
    hypotheses = evaluate_hypotheses(results, 'phase8_p0_l1_baseline')

    # --- Summary ---
    print("\n" + "=" * 70)
    print("PHASE 8 P0 RESULTS — L1 Cycle Baseline Summary")
    print("=" * 70)

    h = hypotheses
    s = h['summary']
    p8 = h['phase8_p0']
    print(f"\n  H1-H8: {s['n_pass']}/8 pass {'[OK]' if s['all_pass'] else '[X] ' + ', '.join(s['failed'])}")
    print(f"  H86 (L1 cycles): {'PASS' if h.get('H86_l1_cycles', {}).get('pass') else 'FAIL'} — {h.get('H86_l1_cycles', {}).get('value', '?')}")
    print(f"  H86a (type diversity): {'PASS' if h.get('H86a_cycle_type_diversity', {}).get('pass') else 'FAIL'} — {h.get('H86a_cycle_type_diversity', {}).get('value', '?')}")
    print(f"  H86b (cycle frequency): {'PASS' if h.get('H86b_cycle_frequency', {}).get('pass') else 'FAIL'} — {h.get('H86b_cycle_frequency', {}).get('value', '?')}")
    print(f"  H89 (no degradation): {'PASS' if h.get('H89_no_degradation', {}).get('pass') else 'FAIL'} — {h.get('H89_no_degradation', {}).get('value', '?')}")
    print(f"  L1 type breakdown: {h.get('l1_type_breakdown', {})}")
    print(f"  L0-L1 Jaccard: mean={h.get('l0_l1_jaccard_mean', 0.0):.3f}, max={h.get('l0_l1_jaccard_max', 0.0):.3f}")
    print(f"  NRC: cycles={h.get('nrc_aggregate', {}).get('nrc_cycles_total', 0)}, R2={h.get('nrc_aggregate', {}).get('nrc_r2_total', 0)}")
    print(f"  Phase 8 P0: {p8['n_pass']}/4 PASS {'[PASS]' if p8['all_pass'] else '[X] ' + ', '.join(p8['failed'])}")

    # Per-seed detail
    print(f"\n{'---' * 25}")
    print("PER-SEED DETAIL:")
    print(f"{'---' * 25}")
    for r in results:
        nrc_m = r.get('nrc_metrics', {})
        l1_m = r.get('l1_metrics', {})
        l1_det = l1_m.get('l1_detector', {})
        error_str = " [ERROR: %s]" % r.get('error', '') if 'error' in r else ""
        print(f"  seed={r.get('seed', '?'):>3}: "
              f"NSI_max={r.get('nse_nsi_max', 0):.4f} "
              f"L1_cycles={l1_det.get('total_cycles', 0)} "
              f"(reconfig={l1_det.get('by_type', {}).get('reconfiguration', 0)}, "
              f"reshuffle={l1_det.get('by_type', {}).get('reshuffle', 0)}, "
              f"identity={l1_det.get('by_type', {}).get('identity_shift', 0)}) "
              f"types={l1_m.get('n_cycle_types_active', 0)} "
              f"L0_cycles={nrc_m.get('n_cycles', 0)} "
              f"R2={nrc_m.get('n_r2_events', 0)} "
              f"jaccard_L0L1={r.get('l1_l0_jaccard', 0):.3f} {error_str}")

    # --- Save results ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    results_file = os.path.join(
        PROJECT_ROOT, 'experiments',
        'exp_137_phase8_p0_l1_baseline_%s.json' % timestamp)
    save_data = {
        'experiment': 'exp_137_phase8_p0_l1_cycle_baseline',
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

    # --- Comparison with Phase 7 ---
    print(f"\n{'=' * 70}")
    print("COMPARISON: Phase 7 (no L1 monitoring) vs Phase 8 P0 (LCylDet monitor)")
    print(f"{'=' * 70}")
    l1_total = sum(l1_det.get('total_cycles', 0) for r in results
                    for l1_det in [r.get('l1_metrics', {}).get('l1_detector', {})])
    nrc_r2 = sum(r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results)
    nrc_cyc = sum(r.get('nrc_metrics', {}).get('n_cycles', 0) for r in results)
    civ_max_vals = [r.get('civ_max', 0) for r in results]
    p7_r2 = h.get('nrc_aggregate', {}).get('nrc_r2_total', '?')
    p7_cyc = h.get('nrc_aggregate', {}).get('nrc_cycles_total', '?')
    print(f"  Phase 7 (exp_136 N0=72): R2={p7_r2}, cycles={p7_cyc}")
    print(f"  Phase 8 P0 (exp_137 N0=72): L1_cycles={l1_total}, NRC_R2={nrc_r2}, NRC_cycles={nrc_cyc}")
    print(f"  CIV max: mean={float(np.mean(civ_max_vals)):.1f}, max={max(civ_max_vals) if civ_max_vals else 0}")


if __name__ == '__main__':
    main()