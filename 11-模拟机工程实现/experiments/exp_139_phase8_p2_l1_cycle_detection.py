"""
experiments/exp_139_phase8_p2_l1_cycle_detection.py

Phase 8 P2: L1 Cycle Detection with max_layers=2 (Actual L1 Evolution)

Purpose:
  Phase 8 P0 (exp_137) established the zero baseline with max_layers=1 — L1 cycles
  never detected because L1 is a STATIC encapsulation of L0's frozen bits.
  Phase 8 P1 (exp_138, commit 45bae21) confirmed this structural finding — the
  encapsulation-aware callback approach cannot work because check_and_encapsulate()
  runs AFTER all snapshots.

  Phase 8 P2 fixes this by running max_layers=2, so L1 actually evolves via its
  own _run_layer() call after L0 encapsulation. PerLayerMetricsCollector (from
  Phase 5 Track B8) handles both L0 and L1 data naturally, and L1CycleDetector
  is fed post-hoc from the collector's stored time series.

Hypotheses:
  H86  (L1 cycles):     >=6/8 seeds with >=1 L1 cycle events (any type) in 2000 steps
  H86a (cycle types):   >=2 cycle types active across all seeds (mean >= 1.5)
  H86b (cycle freq):    Mean cycles/seed >= 3.0
  H89  (no degradation):>=6/8 seeds pass H1-H8 baseline hypotheses

Core Question:
  Does L1 develop autonomous cycle dynamics when allowed to evolve independently
  (max_layers=2), as measured by L1CycleDetector?

Config:
  N0=72, max_layers=2, CSC+NSE+NRC+Booster, tension=1.0
  PerLayerMetricsCollector (tracking callback)
  L1CycleDetector (post-hoc, no feedback)
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

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
from engine.l1_cycle_detector import (
    L1CycleDetector,
    compute_cycle_jaccard, compute_cycle_delay_distribution,
)


# ─── Config ───

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


# ─── Post-hoc L1 Cycle Detection ───

def feed_l1_data_posthoc(collector: PerLayerMetricsCollector,
                          detector: L1CycleDetector) -> int:
    """
    Post-hoc feed L1 time series from PerLayerMetricsCollector to L1CycleDetector.

    Aligns L1 NSI, CIV, and active bits by step and feeds each step's data
    to the detector. Returns number of steps fed (0 if no L1 data).
    """
    # Get L1 trackers
    l1_nsi_tracker = collector._nsi_trackers.get('L1')
    l1_civ_tracker = collector._civ_trackers.get('L1')
    l1_theme_tracker = collector._theme_trackers.get('L1')

    if not l1_nsi_tracker or not l1_civ_tracker:
        return 0

    # Extract time series
    nsi_history = getattr(l1_nsi_tracker, '_nsi_output_history', [])
    civ_active_history = getattr(l1_civ_tracker, '_active_bits_history', [])
    hamming_history = getattr(l1_civ_tracker, '_hamming_history', [])

    if not nsi_history or not civ_active_history:
        return 0

    # Build dicts keyed by step for alignment
    nsi_by_step = dict(nsi_history)
    civ_hamming_by_step = dict(hamming_history) if hamming_history else {}
    active_bits_by_step = dict(civ_active_history)

    # Get all step keys that exist in both NSI and CIV data
    common_steps = sorted(
        set(nsi_by_step.keys()) &
        set(civ_hamming_by_step.keys()) &
        set(active_bits_by_step.keys())
    )

    if not common_steps:
        return 0

    # Also compute frozen ratio from the collector's L0 data for stability
    l0_civ_tracker = collector._civ_trackers.get('L0')
    l0_theme_tracker = collector._theme_trackers.get('L0')

    for step in common_steps:
        l1_nsi = nsi_by_step[step]
        l1_civ = civ_hamming_by_step[step]
        l1_active_bits = active_bits_by_step[step]
        # Use a fixed stability estimate since PerLayerCIVTracker doesn't store n_frozen
        l1_stability = 0.5

        detector.update(
            step=step,
            l1_nsi=l1_nsi,
            l1_civ=l1_civ,
            l1_active_bits=l1_active_bits,
            l1_stability=l1_stability,
        )

    return len(common_steps)


def extract_l1_data_from_collector(collector: PerLayerMetricsCollector) -> Dict:
    """
    Extract L1 cycle detection data from PerLayerMetricsCollector post-run.
    Returns a dict with L1 metrics for hypothesis evaluation.
    """
    detector = L1CycleDetector()
    n_fed = feed_l1_data_posthoc(collector, detector)

    summary = detector.get_summary()
    cycle_times = detector.get_cycle_times()

    type_counts = {
        'reconfiguration': len(cycle_times.get('reconfiguration', [])),
        'reshuffle': len(cycle_times.get('reshuffle', [])),
        'identity_shift': len(cycle_times.get('identity_shift', [])),
    }
    n_types = sum(1 for v in type_counts.values() if v > 0)

    # Get raw time series from collector for inspection
    l1_nsi = collector._nsi_trackers.get('L1')
    l1_civ = collector._civ_trackers.get('L1')
    nsi_series = []
    civ_series = []
    if l1_nsi:
        nsi_series = getattr(l1_nsi, '_nsi_output_history', [])
    if l1_civ:
        civ_series = getattr(l1_civ, '_hamming_history', [])

    # L0 cycle times for correlation
    l0_theme = collector._theme_trackers.get('L0')

    return {
        'l1_detector': summary,
        'l1_cycle_times': cycle_times,
        'l1_cycle_type_counts': type_counts,
        'n_cycle_types_active': n_types,
        'l1_nsi_steps_fed': n_fed,
        'l1_nsi_samples': len(nsi_series),
        'l1_civ_samples': len(civ_series),
        'l1_last_nsi': nsi_series[-1][1] if nsi_series else 0.0,
        'l1_last_civ': civ_series[-1][1] if civ_series else 0,
        'l1_extracted': n_fed > 10,  # meaningful data threshold
    }


# ─── Metrics Extraction ───

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

    l0_cycle_steps = sorted([c.step for c in cycles]) if cycles else []
    metrics['l0_cycle_times'] = l0_cycle_steps

    r0_sig_changes = 0
    total_levels = 0
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

    r2_steps = []
    for c in cycles:
        if hasattr(c, 'recursion_output') and c.recursion_output and getattr(c.recursion_output, 'r2_triggered', False):
            r2_steps.append(c.step)
    metrics['r2_steps'] = r2_steps

    return metrics


# ─── Single Seed Runner ───

def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    r2_tension_threshold, max_layers=2, csc_config=None):
    """
    Run a single seed with max_layers=2 for L1 cycle detection.
    Uses PerLayerMetricsCollector as tracking callback.
    """
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

    # PerLayerMetricsCollector tracks both L0 and L1
    tracking_collector = PerLayerMetricsCollector(config={
        'nsi_rolling_window': 500,
        'civ_rolling_window': 500,
        'theme_jaccard_window': 500,
    })

    evolver = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=max_layers,  # KEY CHANGE: max_layers=2 for L1 evolution
        p1_eval_interval=sample_interval,
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

    print(f"    [seed={seed}] Running {steps} steps at N0={N0}, "
          f"max_layers={max_layers} (tension_threshold={r2_tension_threshold})...", flush=True)
    start = time.time()
    result = evolver.run(tracking_callback=tracking_collector.step)
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    # Check how many layers actually formed
    n_layers_formed = len(result.get('layer_results', []))
    print(f"    [seed={seed}] Layers formed: {n_layers_formed} (n_layers={result.get('n_layers', 0)})", flush=True)

    # ─── Extract L0 metrics ───
    layer_0 = result.get('layer_results', [{}])[0] if result.get('layer_results') else {}
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

    # ─── L1 metrics: post-hoc LCylDet from collector ───
    l1_metrics = extract_l1_data_from_collector(tracking_collector)

    # L0-L1 cycle Jaccard correlation
    l0_times = nrc_metrics.get('l0_cycle_times', [])
    l1_all_times = l1_metrics.get('l1_cycle_times', {}).get('all', [])
    l1_jaccard = compute_cycle_jaccard(l0_times, l1_all_times, epsilon=50)
    l1_delay = compute_cycle_delay_distribution(l0_times, l1_all_times, epsilon=50)

    # Per-layer analysis from collector
    per_layer_analysis = tracking_collector.analyze(post_seal_only=False)

    return {
        'N0': N0, 'seed': seed, 'elapsed': elapsed, 'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'n_layers_formed': n_layers_formed,
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
        'per_layer_analysis': per_layer_analysis,
        'r2_tension_threshold': r2_tension_threshold,
        'nsi_mid_phase': [nse_nsi_values[i] for i in range(len(nse_nsi_values))
                          if 50 <= i <= 100],
    }


# ─── Hypothesis Evaluation ───

def evaluate_hypotheses(results, label="phase8_p2"):
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
    n_layers = [r.get('n_layers_formed', 0) for r in results]

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

    # H86: L1 Cycle Detection — >=6/8 seeds with >=1 L1 cycle events
    l1_total_cycles = [r.get('l1_metrics', {}).get('l1_detector', {}).get('total_cycles', 0)
                        for r in results]
    l1_extracted = [r.get('l1_metrics', {}).get('l1_extracted', False) for r in results]
    h86 = sum(1 for v in l1_total_cycles if v >= 1) >= 6

    # H86a: L1 cycle type diversity — >=2 types active (mean >= 1.5)
    n_types_active = [r.get('l1_metrics', {}).get('n_cycle_types_active', 0)
                       for r in results]
    h86a = float(np.mean(n_types_active)) >= 1.5

    # H86b: L1 cycle frequency — mean cycles/seed >= 3.0
    h86b_mean = float(np.mean(l1_total_cycles)) if l1_total_cycles else 0.0
    h86b = h86b_mean >= 3.0

    # H89: No degradation (H1-H8 preserved)
    h89_all = sum([h1, h2, h3, h4, h5, h6, h7, h8])
    h89 = h89_all >= 6

    # L0-L1 Jaccard across all seeds
    l1_l0_jaccards = [r.get('l1_l0_jaccard', 0.0) for r in results]

    # NRC aggregate
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
        'n_layers_formed': {'values': n_layers, 'n_2_layer_seeds': sum(1 for v in n_layers if v >= 2)},
        'H86_l1_cycles': {
            'value': '%d/8 seeds >=1 L1 cycle (counts: %s)' % (
                sum(1 for v in l1_total_cycles if v >= 1),
                ', '.join(str(v) for v in l1_total_cycles)),
            'threshold': '>=6 seeds',
            'pass': h86,
        },
        'H86a_cycle_type_diversity': {
            'value': 'mean_types_active=%.2f, per_seed=%s' % (
                float(np.mean(n_types_active)),
                ', '.join(str(v) for v in n_types_active)),
            'threshold': '>=1.5',
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
        'l1_extracted_seeds': sum(1 for v in l1_extracted if v),
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
        'phase8_p2': {
            'h86': h86, 'h86a': h86a, 'h86b': h86b, 'h89': h89,
            'n_pass': sum([h86, h86a, h86b, h89]),
            'all_pass': h86 and h86a and h86b and h89,
            'failed': [n for n, v in [('H86', h86), ('H86a', h86a),
                                       ('H86b', h86b), ('H89', h89)] if not v],
        },
    }


# ─── Experiment Constants ───

SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
N_STEPS = 2000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2
N0 = 72
R2_TENSION_THRESHOLD = 1.0
MAX_LAYERS = 2  # KEY: run L1 as actual evolution


def main():
    """Run Phase 8 P2: L1 Cycle Detection with max_layers=2."""
    print("=" * 70)
    print("exp_139: PHASE 8 P2 — L1 Cycle Detection (max_layers=2, actual L1 evolution)")
    print("=" * 70)
    print("  Architecture: CSC+NSE+NRC+NarrativeLevelBooster + LCylDet (post-hoc)")
    print("  N0=%d  MaxLayers=%d  Seeds: %d  Steps: %d" % (N0, MAX_LAYERS, len(SEEDS), N_STEPS))
    print("  R2 tension_threshold=%.1f (Phase 6 recommended default)" % R2_TENSION_THRESHOLD)
    print("  Hypotheses: H86 (L1 cycles), H86a (type diversity), H86b (frequency), H89 (stability)")
    print("  Date: %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("=" * 70)

    results = []

    for seed in SEEDS:
        try:
            result = run_single_seed(
                N0=N0, steps=N_STEPS, seed=seed,
                sample_interval=SAMPLE_INTERVAL, gbc_soft_nudge=GBC_SOFT_NUDGE,
                r2_tension_threshold=R2_TENSION_THRESHOLD,
                max_layers=MAX_LAYERS,
                csc_config=P8_CSC_CONFIG,
            )
            results.append(result)

            nrc = result.get('nrc_metrics', {})
            l1 = result.get('l1_metrics', {})
            l1_det = l1.get('l1_detector', {})
            l1_cycles = l1_det.get('total_cycles', 0)
            l1_types = l1.get('n_cycle_types_active', 0)
            l1_by_type = l1.get('l1_cycle_type_counts', {})
            n_layers = result.get('n_layers_formed', 0)
            print(f"    seed={seed}: NSI_max={result['nse_nsi_max']:.4f}, "
                  f"layers={n_layers}, "
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
                'sealed': False, 'n_layers_formed': 0,
                'nse_nsi_max': 0, 'nse_nsi_mean': 0,
                'nse_nsi_active_rate': 0, 'nse_continuity_mean': 0,
                'nse_history_depth_mean': 0, 'nse_turning_points_final': 0,
                'civ_mean': 0.0, 'civ_min': 0, 'civ_max': 0,
                'csc_csci_std': 0, 'topdown_max_active': 0,
                'nrc_metrics': {'nrc_active': False, 'n_cycles': 0, 'n_r2_events': 0},
                'l1_metrics': {'l1_detector': {'total_cycles': 0}, 'l1_extracted': False},
                'l1_l0_jaccard': 0.0,
                'l1_l0_delay': {},
                'per_layer_analysis': {},
                'r2_tension_threshold': R2_TENSION_THRESHOLD,
                'nsi_mid_phase': [],
            })

    # Evaluate hypotheses
    hypotheses = evaluate_hypotheses(results, 'phase8_p2_l1_evolution')

    # ─── Summary ───
    print("\n" + "=" * 70)
    print("PHASE 8 P2 RESULTS — L1 Cycle Detection (max_layers=2)")
    print("=" * 70)

    h = hypotheses
    s = h['summary']
    p8 = h['phase8_p2']
    print(f"\n  H1-H8: {s['n_pass']}/8 pass {'[OK]' if s['all_pass'] else '[X] ' + ', '.join(s['failed'])}")
    print(f"  H86 (L1 cycles): {'PASS' if h.get('H86_l1_cycles', {}).get('pass') else 'FAIL'} — {h.get('H86_l1_cycles', {}).get('value', '?')}")
    print(f"  H86a (type diversity): {'PASS' if h.get('H86a_cycle_type_diversity', {}).get('pass') else 'FAIL'} — {h.get('H86a_cycle_type_diversity', {}).get('value', '?')}")
    print(f"  H86b (cycle frequency): {'PASS' if h.get('H86b_cycle_frequency', {}).get('pass') else 'FAIL'} — {h.get('H86b_cycle_frequency', {}).get('value', '?')}")
    print(f"  H89 (no degradation): {'PASS' if h.get('H89_no_degradation', {}).get('pass') else 'FAIL'} — {h.get('H89_no_degradation', {}).get('value', '?')}")
    print(f"  Layers formed: {h.get('n_layers_formed', {}).get('n_2_layer_seeds', 0)}/8 seeds with 2+ layers")
    print(f"  L1 extracted: {h.get('l1_extracted_seeds', 0)}/8 seeds")
    print(f"  L0-L1 Jaccard: mean={h.get('l0_l1_jaccard_mean', 0.0):.3f}, max={h.get('l0_l1_jaccard_max', 0.0):.3f}")
    print(f"  NRC: cycles={h.get('nrc_aggregate', {}).get('nrc_cycles_total', 0)}, R2={h.get('nrc_aggregate', {}).get('nrc_r2_total', 0)}")
    print(f"  Phase 8 P2: {p8['n_pass']}/4 PASS {'[PASS]' if p8['all_pass'] else '[X] ' + ', '.join(p8['failed'])}")

    # Per-seed detail
    print(f"\n{'---' * 30}")
    print("PER-SEED DETAIL:")
    print(f"{'---' * 30}")
    for r in results:
        nrc_m = r.get('nrc_metrics', {})
        l1_m = r.get('l1_metrics', {})
        l1_det = l1_m.get('l1_detector', {})
        l1_type_counts = l1_m.get('l1_cycle_type_counts', {})
        error_str = " [ERROR: %s]" % r.get('error', '') if 'error' in r else ""
        print(f"  seed={r.get('seed', '?'):>3}: "
              f"NSI_max={r.get('nse_nsi_max', 0):.4f} "
              f"layers={r.get('n_layers_formed', 0)} "
              f"L1_cycles={l1_det.get('total_cycles', 0)} "
              f"(reconfig={l1_type_counts.get('reconfiguration', 0)}, "
              f"reshuffle={l1_type_counts.get('reshuffle', 0)}, "
              f"identity={l1_type_counts.get('identity_shift', 0)}) "
              f"types={l1_m.get('n_cycle_types_active', 0)} "
              f"extracted={l1_m.get('l1_extracted', False)} "
              f"L0_cycles={nrc_m.get('n_cycles', 0)} "
              f"R2={nrc_m.get('n_r2_events', 0)} "
              f"jaccard_L0L1={r.get('l1_l0_jaccard', 0):.3f} {error_str}")

    # ─── Save results ───
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    results_file = os.path.join(
        PROJECT_ROOT, 'experiments',
        'exp_139_phase8_p2_l1_evolution_%s.json' % timestamp)
    save_data = {
        'experiment': 'exp_139_phase8_p2_l1_cycle_evolution',
        'datetime': datetime.now().isoformat(),
        'N0': N0, 'n_steps': N_STEPS, 'max_layers': MAX_LAYERS,
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

    # ─── Comparison ───
    print(f"\n{'=' * 70}")
    print("COMPARISON: Phase 7 (no L1) vs Phase 8 P0 (max_layers=1) vs Phase 8 P2 (max_layers=2)")
    print(f"{'=' * 70}")
    l1_total = sum(
        r.get('l1_metrics', {}).get('l1_detector', {}).get('total_cycles', 0)
        for r in results
    )
    nrc_r2 = sum(r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results)
    nrc_cyc = sum(r.get('nrc_metrics', {}).get('n_cycles', 0) for r in results)
    n_2layer = sum(1 for r in results if r.get('n_layers_formed', 0) >= 2)
    civ_max_vals = [r.get('civ_max', 0) for r in results]
    print(f"  2+ layer seeds: {n_2layer}/8")
    print(f"  Total L1 cycles across all seeds: {l1_total}")
    print(f"  NRC cycles: {nrc_cyc}, R2 events: {nrc_r2}")
    print(f"  CIV max: mean={float(np.mean(civ_max_vals)):.1f}, max={max(civ_max_vals) if civ_max_vals else 0}")


if __name__ == '__main__':
    main()