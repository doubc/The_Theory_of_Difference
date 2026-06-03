"""
experiments/exp_128_phase5_d1_long_term_evolution.py

Phase 5 Track D1: Long-Term Evolution (超长运行测试)

Purpose:
  Run the Phase 5 architecture (CSC+NSE+NarrativeLevelBooster) for 5000 steps
  (3x the baseline 1600-step window) to test:
  1. Does the system remain stable? (H36: H1-H8 still pass at step 5000)
  2. Are there secondary phase transitions? (H37: NSI second jump 2000-5000)
  3. How does CIV evolve beyond the narrative construction period?
  4. Does NSI plateau, drift, or show new patterns?

Background:
  Phase 4 P3 (exp_110) ran 2000 steps and showed:
  - "narrative maturity" — CIV front-loaded, system transitions to continuity mode
  - NSI continues growing slowly even after 2000 steps
  
  Phase 5 Track B/C work has added:
  - NarrativeLevelBooster (Track C2) for CIV baseline
  - PerLayerMetricsCollector for multi-layer tracking
  - Partial sealing (B7) for consistent L1 formation
  
  Key question: Is the "narrative maturity" transition at ~1500 steps a true
  phase transition, or does a secondary transition occur at longer timescales?

Architecture:
  - CSC+NSE+NarrativeLevelBooster (simplified Phase 5, no AMC/ILP)
  - N0=48 (proven with booster from Track C2)
  - 8 seeds × 5000 steps = 40 runs
  - PerLayerMetricsCollector tracking callback

Hypotheses:
  H36 (long-term stability): H1-H8 all pass at T=5000 (measured from final
    snapshot step_{4999}). If the architecture is robust, core narrative
    mechanisms should persist at 3x baseline.
    
  H37 (secondary phase transition): NSI shows >10% increase between the
    mean of [2000-3000] and mean of [4000-4999]. This would indicate a
    second narrative "maturation" beyond the initial construction period.
    
  H38 (narrative maturity pattern): ≥70% of CIV events (non-zero CIV steps)
    occur in the first 2500 steps. The system transitions from "construction"
    to "maintenance" mode.
    
  H39 (NSI stability envelope): Final step NSI within ±15% of step-2000 NSI.
    No collapse (< -15%) and no explosion (> +15%) — narrative self is stable.

  H-D1-1 (multi-layer persistence): PerLayerMetricsCollector shows L1/L2
    active bit flux (Jaccard) remains active throughout 5000 steps.
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
from engine.civ_floor import NarrativeLevelBooster
from engine.per_layer_metrics import PerLayerMetricsCollector


# ─── CSC config: same proven config from exp_107/exp_109/exp_127 ───
TRACK_D_CSC_CONFIG = {
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
    """Same limiter as exp_125/exp_127 (proven stable)."""

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
    """V4 P1-F: CIVRateLimiterV2P1F (same as exp_125/exp_127)."""

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


def compute_nsi_trajectory_phases(step_results):
    """
    Compute NSI trajectory broken into 3 phases:
    - Phase 1: steps 0-1666 (early construction)
    - Phase 2: steps 1667-3333 (mid stabilization)
    - Phase 3: steps 3334-4999 (late maturity)

    Returns dict with mean NSI per phase, and whether H37 (secondary
    phase transition) is detected.
    """
    nsi_values = []
    for sr in step_results:
        nse_entry = sr.get('narrative_self_emergence', {})
        if nse_entry:
            nsi_values.append(nse_entry.get('nsi', 0.0))

    total = len(nsi_values)
    if total < 3:
        return {'error': 'insufficient_data'}

    # Split into 3 equal phases
    phase_size = total // 3
    phase1 = nsi_values[:phase_size]
    phase2 = nsi_values[phase_size:2*phase_size]
    phase3 = nsi_values[2*phase_size:]

    # Secondary transition: NSI in phase3 > phase2 by >10%
    mean_p2 = float(np.mean(phase2)) if phase2 else 0.0
    mean_p3 = float(np.mean(phase3)) if phase3 else 0.0
    secondary_transition = False
    transition_pct = 0.0
    if mean_p2 > 0.0:
        transition_pct = ((mean_p3 - mean_p2) / mean_p2) * 100.0
        secondary_transition = transition_pct > 10.0

    return {
        'nsi_phase1_mean': float(np.mean(phase1)) if phase1 else 0.0,
        'nsi_phase2_mean': mean_p2,
        'nsi_phase3_mean': mean_p3,
        'nsi_phase1_max': float(np.max(phase1)) if phase1 else 0.0,
        'nsi_phase2_max': float(np.max(phase2)) if phase2 else 0.0,
        'nsi_phase3_max': float(np.max(phase3)) if phase3 else 0.0,
        'nsi_phase1_std': float(np.std(phase1)) if phase1 else 0.0,
        'nsi_phase3_std': float(np.std(phase3)) if phase3 else 0.0,
        'nsi_all_max': float(np.max(nsi_values)),
        'nsi_all_mean': float(np.mean(nsi_values)),
        'secondary_transition_pct': transition_pct,
        'secondary_transition': secondary_transition,
        'nsi_final': float(nsi_values[-1]) if nsi_values else 0.0,
        'nsi_step_2000': float(nsi_values[min(len(nsi_values)-1, int(total * 2000/5000))]),
    }


def compute_civ_timeline(step_results):
    """
    Track CIV events across the 5000-step timeline.
    Compute % of CIV events in first half (0-2500) vs second half (2501-5000).
    """
    total = len(step_results)
    if total < 2:
        return {'error': 'insufficient_data'}

    midpoint = total // 2

    first_half_civ = 0
    second_half_civ = 0
    first_half_steps = 0
    second_half_steps = 0

    for i, sr in enumerate(step_results):
        nse_entry = sr.get('narrative_self_emergence', {})
        civ_val = nse_entry.get('civ_count', 0)
        if i < midpoint:
            first_half_civ += civ_val
            first_half_steps += 1
        else:
            second_half_civ += civ_val
            second_half_steps += 1

    total_civ = first_half_civ + second_half_civ
    pct_first = (first_half_civ / total_civ * 100.0) if total_civ > 0 else 0.0
    pct_second = (second_half_civ / total_civ * 100.0) if total_civ > 0 else 0.0

    # Also count non-zero CIV step count
    first_civ_steps = 0
    second_civ_steps = 0
    for i, sr in enumerate(step_results):
        nse_entry = sr.get('narrative_self_emergence', {})
        civ_val = nse_entry.get('civ_count', 0)
        if civ_val > 0:
            if i < midpoint:
                first_civ_steps += 1
            else:
                second_civ_steps += 1

    total_civ_steps = first_civ_steps + second_civ_steps
    pct_first_steps = (first_civ_steps / total_civ_steps * 100.0) if total_civ_steps > 0 else 0.0

    return {
        'total_civ_sum': total_civ,
        'first_half_civ': first_half_civ,
        'second_half_civ': second_half_civ,
        'pct_first_half': pct_first,
        'pct_second_half': pct_second,
        'total_civ_steps': total_civ_steps,
        'first_half_civ_steps': first_civ_steps,
        'second_half_civ_steps': second_civ_steps,
        'pct_first_half_steps': pct_first_steps,
        'narrative_maturity': pct_first >= 70.0,  # H38
    }


def compute_nsi_stability(nsi_phase, nsi_step_2000):
    """
    Check if final NSI is within ±15% of step-2000 NSI (H39).
    """
    if nsi_step_2000 <= 0.0:
        return {
            'ns_stability_pass': False,
            'ns_drift_pct': 0.0,
            'reason': 'step_2000_nsi_zero',
        }
    drift_pct = ((nsi_phase - nsi_step_2000) / nsi_step_2000) * 100.0
    return {
        'ns_drift_pct': drift_pct,
        'ns_stability_pass': abs(drift_pct) <= 15.0,
        'nsi_step_2000': nsi_step_2000,
        'nsi_final': nsi_phase,
    }


def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    csc_config=None, tracking_collector=None):
    """Run a single seed with CSC+NSE+NarrativeLevelBooster stack."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10,
    )
    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40, l2_stability_threshold=0.55,
    )
    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True,
    )
    odi = OrganizationalDensityIndex(
        temporal_window=10, densification_threshold=0.005, use_refined_zones=True,
    )
    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3, 'history_window': 8, 'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8,
        'self_reference_threshold': 0.05, 'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20, 'msi_emergence_threshold': 0.35,
        'min_active_conditions': 1,
    })
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5, balance_threshold=0.3,
        min_mechanisms_required=4, geometric_weighting=True,
    )
    narrative = MomentumNarrativeOperatorV4P1F(
        bias_dimension=128, filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3,
    )
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01},
    )
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1, 'max_branches': 4,
    })
    six_threshold = SixThresholdDetector()

    # CSC: ON (keystone component)
    csc_cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
    if csc_config:
        csc_cfg.update(csc_config)
    csc = CrossScaleCoupling(config=csc_cfg)

    # NSE: ON (diagnostic layer)
    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {
        'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1,
    }
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    # NarrativeLevelBooster: NRO-level CIV guarantee
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
        cross_scale_coupling=csc,
        narrative_self_emergence=nse,
        adaptive_momentum_controller=None,
        institutional_layer_protector=None,
        narrative_level_booster=narrative_level_booster,
    )

    print(f"    [seed={seed}] Running 5000 steps...", flush=True)
    start = time.time()
    evolver_tracking_cb = tracking_collector.step if tracking_collector is not None else None
    result = evolver.run(tracking_callback=evolver_tracking_cb)
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    # ─── Standard metrics (same as exp_127) ───
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

    # ─── CIV counting (post-boost, from NSE step results) ───
    boosted_civ_values = []
    for sr in step_results:
        nse_entry = sr.get('narrative_self_emergence', {})
        if 'civ_count' in nse_entry:
            boosted_civ_values.append(nse_entry['civ_count'])

    if boosted_civ_values:
        civ_mean_boosted = float(np.mean(boosted_civ_values)) if boosted_civ_values else 0.0
        civ_min_boosted = int(np.min(boosted_civ_values)) if boosted_civ_values else 0
        civ_max_boosted = int(np.max(boosted_civ_values)) if boosted_civ_values else 0
    else:
        civ_mean_boosted = 0.0
        civ_min_boosted = 0
        civ_max_boosted = 0

    boost_events = 0
    for sr in step_results:
        nse_entry = sr.get('narrative_self_emergence', {})
        boosted = nse_entry.get('civ_count', 0)
        pre_boost = nse_entry.get('civ_raw', 0)
        if boosted > pre_boost:
            boost_events += 1

    civ_limiter_summary = narrative.civ_rate_limiter.get_summary()

    # ─── Track D1 specific: NSI trajectory phases ───
    nsi_traj = compute_nsi_trajectory_phases(step_results)

    # ─── Track D1 specific: CIV timeline ───
    civ_timeline = compute_civ_timeline(step_results)

    # ─── Track D1 specific: NSI stability ───
    ns_stability = compute_nsi_stability(
        nsi_traj.get('nsi_final', 0.0),
        nsi_traj.get('nsi_step_2000', 0.0)
    )

    # ─── PerLayerMetrics analysis ───
    multi_layer_active = False
    if tracking_collector is not None:
        try:
            analysis = tracking_collector.analyze()
            multi_layer_active = analysis.get('layers_tracked', 0) > 0
        except Exception:
            multi_layer_active = False

    return {
        'N0': N0,
        'seed': seed,
        'elapsed': elapsed,
        'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'odi_max': odi_max,
        'gbc_coherence_mean': gbc_coherence_mean,
        'gbc_pass_rate': gbc_pass_rate,
        'csc_csci_std': csc_csci_std,
        'topdown_max_active': topdown_max_active,
        'nse_nsi_max': nse_nsi_max,
        'nse_nsi_mean': nse_nsi_mean,
        'nse_nsi_active_rate': nse_nsi_active_rate,
        'nse_continuity_mean': nse_continuity_mean,
        'nse_history_depth_mean': nse_history_depth_mean,
        'nse_turning_points_final': nse_turning_points_final,
        'civ_mean_boosted': civ_mean_boosted,
        'civ_min_boosted': civ_min_boosted,
        'civ_max_boosted': civ_max_boosted,
        'boost_events': boost_events,
        'civ_limiter_total_seen': civ_limiter_summary['total_civ_seen'],
        # Track D1 metrics
        'nsi_trajectory': nsi_traj,
        'civ_timeline': civ_timeline,
        'ns_stability': ns_stability,
        'multi_layer_active': multi_layer_active,
    }


def evaluate_hypotheses(results, n0_label="unknown"):
    """Evaluate H1-H8 + Track D1 hypotheses (H36-H39, H-D1-1)."""
    if not results:
        return {'summary': {'all_pass': False, 'n_pass': 0, 'failed': ['no_data']}}

    nsi_max_vals = [r['nse_nsi_max'] for r in results]
    nsi_active_rates = [r['nse_nsi_active_rate'] for r in results]
    continuity_means = [r['nse_continuity_mean'] for r in results]
    history_depth_means = [r['nse_history_depth_mean'] for r in results]
    turning_points_finals = [r['nse_turning_points_final'] for r in results]
    civ_values = [r['civ_mean_boosted'] for r in results]
    csci_stds = [r['csc_csci_std'] for r in results]
    topdown_max = [r['topdown_max_active'] for r in results]
    civ_max_values = [r.get('civ_max_boosted', r['civ_mean_boosted']) for r in results]

    # ─── H1-H8 (same thresholds as exp_127 Track C2) ───
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

    # ─── H36: H1-H8 all pass at 5000 steps ───
    h36 = h1 and h2 and h3 and h4 and h5 and h6 and h7 and h8

    # ─── H37: secondary phase transition ───
    secondary_transition_seeds = [
        r.get('nsi_trajectory', {}).get('secondary_transition', False)
        for r in results
    ]
    h37 = sum(secondary_transition_seeds) >= 4  # ≥50% seeds show secondary transition

    # ─── H38: narrative maturity (≥70% CIV in first half) ───
    narrative_maturity_seeds = [
        r.get('civ_timeline', {}).get('narrative_maturity', False)
        for r in results
    ]
    h38 = sum(narrative_maturity_seeds) >= 6  # ≥75% seeds show maturity pattern

    # ─── H39: NSI stability (±15% drift from step-2000) ───
    stability_pass_seeds = [
        r.get('ns_stability', {}).get('ns_stability_pass', False)
        for r in results
    ]
    h39 = sum(stability_pass_seeds) >= 6  # ≥75% seeds within stability envelope

    # ─── H-D1-1: multi-layer persistence ───
    multi_layer_active_seeds = sum(1 for r in results if r.get('multi_layer_active', False))
    h_d1_1 = multi_layer_active_seeds >= 4  # ≥50% seeds show multi-layer activity

    # Mean NSI by phase (for summary)
    phase1_means = [r.get('nsi_trajectory', {}).get('nsi_phase1_mean', 0.0) for r in results]
    phase2_means = [r.get('nsi_trajectory', {}).get('nsi_phase2_mean', 0.0) for r in results]
    phase3_means = [r.get('nsi_trajectory', {}).get('nsi_phase3_mean', 0.0) for r in results]

    return {
        'n0': n0_label,
        'H1_nsi_max': {'value': float(np.max(nsi_max_vals)), 'threshold': '>0.1', 'pass': h1},
        'H2_nsi_active_rate': {'value': float(np.mean(nsi_active_rates)), 'threshold': '>0.3 all', 'pass': h2},
        'H3_continuity_mean': {'value': float(np.mean(continuity_means)), 'threshold': '>0.1', 'pass': h3},
        'H4_combined': {
            'value': f"depth={float(np.mean(history_depth_means)):.4f}, tp={float(np.mean(turning_points_finals)):.1f}",
            'threshold': 'depth>0.05 OR tp>0', 'pass': h4},
        'H5_civ_max': {'value': float(np.max(civ_max_values)), 'threshold': '>=3 (max)', 'pass': h5},
        'H6_civ_max': {'value': float(np.max(civ_max_values)), 'threshold': '>=2 (max)', 'pass': h6},
        'H7_csci_std_mean': {'value': float(np.mean(csci_stds)), 'threshold': '>0.005', 'pass': h7},
        'H8_topdown_active_seeds': {'value': sum(1 for v in topdown_max if v > 0), 'threshold': '>=2 seeds', 'pass': h8},
        # Track D1 hypotheses
        'H36_long_term_stability': {
            'value': 'pass' if h36 else 'fail',
            'threshold': 'H1-H8 all pass at 5000 steps',
            'pass': h36},
        'H37_secondary_transition': {
            'value': f"{sum(secondary_transition_seeds)}/{len(results)} seeds",
            'threshold': '≥4 seeds with >10% NSI increase in phase 3',
            'pass': h37},
        'H38_narrative_maturity': {
            'value': f"{sum(narrative_maturity_seeds)}/{len(results)} seeds",
            'threshold': '≥6 seeds with ≥70% CIV in first 2500 steps',
            'pass': h38},
        'H39_nsi_stability': {
            'value': f"{sum(stability_pass_seeds)}/{len(results)} seeds",
            'threshold': '≥6 seeds with NSI drift ±15% from step-2000',
            'pass': h39},
        'H_D1_1_multi_layer_persistence': {
            'value': f"{multi_layer_active_seeds}/{len(results)} seeds",
            'threshold': '≥4 seeds with active PerLayerMetrics',
            'pass': h_d1_1},
        # NSI trajectory summary
        'nsi_phase_means': {
            'phase1': float(np.mean(phase1_means)),
            'phase2': float(np.mean(phase2_means)),
            'phase3': float(np.mean(phase3_means)),
        },
        'summary': {
            'all_pass': h1 and h2 and h3 and h4 and h5 and h6 and h7 and h8,
            'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'failed': [name for name, val in
                       [('H1', h1), ('H2', h2), ('H3', h3), ('H4', h4),
                        ('H5', h5), ('H6', h6), ('H7', h7), ('H8', h8)] if not val],
        },
        'track_d1_summary': {
            'n_pass': sum([h36, h37, h38, h39, h_d1_1]),
            'all_pass': h36 and h37 and h38 and h39 and h_d1_1,
            'failed': [name for name, val in
                       [('H36', h36), ('H37', h37), ('H38', h38), ('H39', h39),
                        ('H_D1_1', h_d1_1)] if not val],
        },
    }


# ─── Main config ───
N0_CONFIG = {'label': 'N0_48_track_d1', 'N0': 48, 'description': 'Track D1: 5000 steps at N0=48'}
SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
N_STEPS = 5000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2


def main():
    print("=" * 70)
    print("exp_128: Phase 5 Track D1 — Long-Term Evolution (5000 steps)")
    print(f"  Architecture: CSC+NSE+NarrativeLevelBooster (no AMC/ILP)")
    print(f"  N0={N0_CONFIG['N0']}  Seeds: {len(SEEDS)}   Steps: {N_STEPS} (3x baseline)")
    print(f"  Hypotheses: H36 (stability) H37 (phase transition) H38 (maturity) H39 (drift)")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Create PerLayerMetricsCollector as tracking callback
    tracking_collector = PerLayerMetricsCollector(config={
        'nsi_rolling_window': 500,
        'civ_rolling_window': 500,
        'theme_jaccard_window': 500,
    })

    all_results = []

    for seed in SEEDS:
        try:
            result = run_single_seed(
                N0=N0_CONFIG['N0'], steps=N_STEPS, seed=seed,
                sample_interval=SAMPLE_INTERVAL,
                gbc_soft_nudge=GBC_SOFT_NUDGE,
                csc_config=TRACK_D_CSC_CONFIG,
                tracking_collector=tracking_collector,
            )
            all_results.append(result)
            nsi_phases = result.get('nsi_trajectory', {})
            civ_tl = result.get('civ_timeline', {})
            ns_stab = result.get('ns_stability', {})
            print(f"    seed={seed}: NSI_max={result['nse_nsi_max']:.4f}, "
                  f"NSI_mean={result['nse_nsi_mean']:.4f}, "
                  f"P1={nsi_phases.get('nsi_phase1_mean', 0):.4f}, "
                  f"P2={nsi_phases.get('nsi_phase2_mean', 0):.4f}, "
                  f"P3={nsi_phases.get('nsi_phase3_mean', 0):.4f}, "
                  f"CIV%1st={civ_tl.get('pct_first_half_steps', 0):.0f}%, "
                  f"drift={ns_stab.get('ns_drift_pct', 0):.1f}%, "
                  f"cont={result['nse_continuity_mean']:.4f}, "
                  f"depth={result['nse_history_depth_mean']:.4f}, "
                  f"tp={result['nse_turning_points_final']}, "
                  f"CIV={result['civ_max_boosted']}, "
                  f"sealed={result['sealed']}")
        except Exception as e:
            print(f"    *** seed={seed}: FAILED — {e}", flush=True)
            import traceback
            traceback.print_exc()
            all_results.append({
                'N0': N0_CONFIG['N0'], 'seed': seed, 'elapsed': 0,
                'error': str(e), 'n_steps': 0,
                'sealed': False, 'odi_max': 0, 'gbc_coherence_mean': 0,
                'gbc_pass_rate': 0, 'csc_csci_std': 0, 'topdown_max_active': 0,
                'nse_nsi_max': 0, 'nse_nsi_mean': 0, 'nse_nsi_active_rate': 0,
                'nse_continuity_mean': 0, 'nse_history_depth_mean': 0,
                'nse_turning_points_final': 0, 'civ_mean_boosted': 0.0,
                'civ_min_boosted': 0, 'civ_max_boosted': 0,
                'boost_events': 0, 'civ_limiter_total_seen': 0,
                'nsi_trajectory': {}, 'civ_timeline': {}, 'ns_stability': {},
                'multi_layer_active': False,
            })

    hypotheses = evaluate_hypotheses(all_results, N0_CONFIG['label'])

    # ─── Summary ───
    print("\n" + "=" * 70)
    print("TRACK D1 RESULTS — Long-Term Evolution (5000 steps)")
    print("=" * 70)

    summary = hypotheses['summary']
    print(f"\n  H1-H8 at step 5000 [{summary['n_pass']}/8 pass]:")
    if summary['all_pass']:
        print(f"    ALL CORE HYPOTHESES PASS [OK]")
    else:
        print(f"    Failed: {', '.join(summary['failed'])} [X]")

    d1_summary = hypotheses['track_d1_summary']
    print(f"\n  Track D1 [{d1_summary['n_pass']}/5 pass]:")
    for name in ['H36_long_term_stability', 'H37_secondary_transition',
                 'H38_narrative_maturity', 'H39_nsi_stability',
                 'H_D1_1_multi_layer_persistence']:
        h = hypotheses.get(name, {})
        status = "[OK]" if h.get('pass') else "[X]"
        print(f"    {name}: {h.get('value', '?')} {status}")

    # NSI trajectory
    phases = hypotheses.get('nsi_phase_means', {})
    print(f"\n  NSI Trajectory:")
    print(f"    Phase 1 (0-1666): mean={phases.get('phase1', 0):.4f}")
    print(f"    Phase 2 (1667-3333): mean={phases.get('phase2', 0):.4f}")
    print(f"    Phase 3 (3334-4999): mean={phases.get('phase3', 0):.4f}")

    # Per-seed detail
    print(f"\n{'─' * 70}")
    print("PER-SEED DETAIL")
    print(f"{'─' * 70}")
    for r in all_results:
        nsi_traj = r.get('nsi_trajectory', {})
        civ_tl = r.get('civ_timeline', {})
        ns = r.get('ns_stability', {})
        error_str = f" [ERROR: {r.get('error', '')}]" if 'error' in r else ""
        print(f"  seed={r.get('seed', '?'):>3}: "
              f"NSI_p1={nsi_traj.get('nsi_phase1_mean', 0):.4f} "
              f"p2={nsi_traj.get('nsi_phase2_mean', 0):.4f} "
              f"p3={nsi_traj.get('nsi_phase3_mean', 0):.4f} "
              f"final={nsi_traj.get('nsi_final', 0):.4f} "
              f"transition={nsi_traj.get('secondary_transition', False)} "
              f"CIV_1st={civ_tl.get('pct_first_half', 0):.0f}% "
              f"drift={ns.get('ns_drift_pct', 0):.1f}% "
              f"CIV_max={r.get('civ_max_boosted', 0)} {error_str}")

    # ─── Save results ───
    results_file = os.path.join(PROJECT_ROOT, 'experiments',
                                f'exp_128_d1_results_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
    save_data = {
        'experiment': 'exp_128_phase5_d1_long_term_evolution',
        'datetime': datetime.now().isoformat(),
        'config': N0_CONFIG,
        'seeds': SEEDS,
        'n_steps': N_STEPS,
        'narrative_level_booster_params': {'min_civ': 3},
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
            else:
                sr[k] = v
        save_data['per_seed'].append(sr)

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n    Results saved to: {results_file}")

    # ─── Final verdict ───
    print("\n" + "=" * 70)
    print("TRACK D1 VERDICT")
    print("=" * 70)

    h36_pass = hypotheses.get('H36_long_term_stability', {}).get('pass', False)
    h37_pass = hypotheses.get('H37_secondary_transition', {}).get('pass', False)
    h38_pass = hypotheses.get('H38_narrative_maturity', {}).get('pass', False)
    h39_pass = hypotheses.get('H39_nsi_stability', {}).get('pass', False)
    h_d1_pass = hypotheses.get('H_D1_1_multi_layer_persistence', {}).get('pass', False)

    track_d1_n_pass = sum([h36_pass, h37_pass, h38_pass, h39_pass, h_d1_pass])
    print(f"\n  Track D1: {track_d1_n_pass}/5 PASS")
    print(f"    H36 (long-term stability): {'PASS [OK]' if h36_pass else 'FAIL [X]'}")
    print(f"    H37 (secondary transition): {'PASS [OK]' if h37_pass else 'FAIL [X]'}")
    print(f"    H38 (narrative maturity): {'PASS [OK]' if h38_pass else 'FAIL [X]'}")
    print(f"    H39 (NSI stability): {'PASS [OK]' if h39_pass else 'FAIL [X]'}")
    print(f"    H-D1-1 (multi-layer): {'PASS [OK]' if h_d1_pass else 'FAIL [X]'}")

    core_pass = summary['n_pass']
    print(f"\n  Core H1-H8 at 5000 steps: {core_pass}/8")
    if core_pass >= 6:
        print(f"    → Long-term architecture STABLE [OK]")
    else:
        print(f"    → Long-term architecture DEGRADED ⚠️")


if __name__ == '__main__':
    main()
