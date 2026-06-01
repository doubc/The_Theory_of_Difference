"""experiments/exp_105_p1d_fixes.py

Phase 4 Experiment 15: P1-D Fixes — INSTITUTIONAL Activity-Driven TopDown & Seal Timeout

Purpose: Fix H5 (seed 242 unsealed) and H8 (TopDown not activating) from exp_104.

exp_104 results: 6/8 pass
  H5 FAIL: seed 242 unsealed, CIV=206 (outlier; excluding seed 242, mean≈5.4)
  H8 FAIL: TopDown active seeds=0 (counting bug fixed + INSTITUTIONAL stability boost needed)

Root causes identified:
  1. TopDown counting bug: iterating dict keys instead of values → always 0 constraints counted
     FIXED in hierarchical_evolver.py: iterate .items() instead of dict directly
  2. ILP stability fallback broken: called get_summary() which doesn't exist on ILP
     FIXED: use get_history() + derive stability from ILP metrics
  3. INSTITUTIONAL stability too low for TopDown threshold
     FIXED: add activity-based stability boost when INSTITUTIONAL has narrative activity
  4. Seed 242 unsealed: runs 2400 steps instead of 1600
     FIX: add seal timeout — force seal after max_steps multiplier

P1-D fixes:
  1. TopDown threshold: 0.10 -> 0.05 (further lowered)
  2. CIVRateLimiterV2P1D: max_rate 0.08->0.10, cooldown 8->10 (further relaxation)
  3. All engine-level fixes from analysis (counting bug, ILP fallback, activity boost)
  4. Seal timeout: force seal check at 2x steps if not yet sealed

Config: Same as exp_104 (N0=72, steps=1600, 8 seeds)
    CSC: ON (topdown_stability_threshold=0.05)
    GBC: ON (random direction init, soft nudge=0.2)
    NSE: ON (threshold=0.02, odi=0.4, msi=0.3, civ=0.0, gbc=0.1, max_tp=25)
    AMC: ON, ILP: ON
    CIVRateLimiterV2P1D: ON (window=50, max_rate=0.10, cooldown=10, min_guarantee=3)

Hypotheses (same H1-H8):
  H1: NSI max > 0.1
  H2: NSI active rate > 0.3
  H3: Temporal continuity score mean > 0.1
  H4: Self history depth > 0.05 OR turning points > 0
  H5: CIV mean in [3, 15]
  H6: min CIV >= 3
  H7: CSCI std > 0.005
  H8: TopDown constraints active in at least 2 seeds
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
from engine.adaptive_momentum_controller import (
    AdaptiveMomentumController, DEFAULT_ADAPTIVE_MOMENTUM_CONFIG,
)
from engine.institutional_layer_protector import (
    InstitutionalLayerProtector, DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG,
)


EXP105_CSC_CONFIG = {
    'topdown_max_constraint_strength': 0.10,
    'topdown_min_constraint_strength': 0.01,
    'topdown_response_delay': 20,
    'topdown_decay_rate': 0.98,
    'topdown_propagation_depth': 2,
    'topdown_stability_threshold': 0.05,  # P1-D: 0.10 -> 0.05 (INSTITUTIONAL activity-driven)
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


class CIVRateLimiterV2P1D(CIVRateLimiter):
    """CIVRateLimiter V2 P1-D — further relaxed rate limiting

    P1-C used max_rate=0.08, cooldown=8.
    P1-D relaxes to max_rate=0.10, cooldown=10 for better CIV mean recovery.
    """

    def __init__(self, window_size=50, max_civ_rate=0.10, cooldown_steps=10,
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


class MomentumNarrativeOperatorV4P1D(NarrativeRecursionOperator):
    """V4 P1-D: CIVRateLimiterV2P1D with further relaxed limits"""

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
        self.civ_rate_limiter = CIVRateLimiterV2P1D(
            window_size=50, max_civ_rate=0.10, cooldown_steps=10,
            min_civ_guarantee=3
        )

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


def run_single_seed(N0=72, steps=1600, seed=142, sample_interval=10,
                    gbc_soft_nudge=0.2, use_csc=True, csc_config=None,
                    use_nse=True, use_amc=True, use_ilp=True):
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
    narrative = MomentumNarrativeOperatorV4P1D(
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

    csc = None
    if use_csc:
        csc_cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
        if csc_config:
            csc_cfg.update(csc_config)
        csc = CrossScaleCoupling(config=csc_cfg)

    nse = None
    if use_nse:
        nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
        nse_cfg['history_multi_signal'] = True
        nse_cfg['history_second_deriv_threshold'] = 0.02
        nse_cfg['history_signal_weights'] = {
            'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1,
        }
        nse_cfg['history_max_turning_points'] = 25
        nse = NarrativeSelfEmergence(config=nse_cfg)

    amc = None
    if use_amc:
        amc_cfg = dict(DEFAULT_ADAPTIVE_MOMENTUM_CONFIG)
        amc = AdaptiveMomentumController(config=amc_cfg)

    ilp = None
    if use_ilp:
        ilp_cfg = dict(DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG)
        ilp = InstitutionalLayerProtector(config=ilp_cfg)

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
        adaptive_momentum_controller=amc,
        institutional_layer_protector=ilp,
    )

    print(f"  [seed={seed}] Running...", flush=True)
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"  [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    active_count = 0
    civ_count = 0
    inst_count = 0
    mini_count = 0

    for sr in step_results:
        narr_info = sr.get('narrative_recursion', {})
        if narr_info and narr_info.get('narrative_level'):
            level = narr_info.get('narrative_level', 'MINI_NARRATIVE')
        else:
            try:
                narr_history = narrative.get_narrative_history(n=1)
                if narr_history:
                    level = narr_history[-1].get('narrative_level', 'MINI_NARRATIVE')
                else:
                    level = sr.get('level', 'MINI')
            except Exception:
                level = sr.get('level', 'MINI')
        if level == 'MINI_NARRATIVE':
            level = 'MINI'
        if level == 'CIVILIZATION':
            civ_count += 1
        elif level == 'INSTITUTIONAL':
            inst_count += 1
        elif level == 'MINI':
            mini_count += 1
        if sr.get('narrative_active', False):
            active_count += 1

    odi_values = [sr['odi']['value'] for sr in step_results if 'odi' in sr and sr.get('odi', {}).get('value') is not None]
    odi_max = float(np.max(odi_values)) if odi_values else 0.0
    odi_mean = float(np.mean(odi_values)) if odi_values else 0.0

    msi_values = [sr.get('minimal_self', {}).get('msi', 0.0) for sr in step_results if 'minimal_self' in sr]
    msi_max = float(np.max(msi_values)) if msi_values else 0.0
    msi_mean = float(np.mean(msi_values)) if msi_values else 0.0

    six_results = [sr['six_threshold'] for sr in step_results if 'six_threshold' in sr]
    six_pass_count = sum(1 for sr in six_results if sr.get('all_met'))
    six_pass_rate = six_pass_count / len(six_results) if six_results else 0.0

    gbc_checks = result.get('gbc_checks', [])
    gbc_coherences = [c.get('coherence', 0.0) for c in gbc_checks]
    gbc_passes = [1 for c in gbc_checks if c.get('passed', False)]
    gbc_coherence_mean = float(np.mean(gbc_coherences)) if gbc_coherences else 0.0
    gbc_pass_rate = float(np.mean(gbc_passes)) if gbc_passes else 0.0

    csc_csci_values = [sr.get('cross_scale_coupling', {}).get('csci', 0.0)
                       for sr in step_results if 'cross_scale_coupling' in sr]
    csc_csci_mean = float(np.mean(csc_csci_values)) if csc_csci_values else 0.0
    csc_csci_std = float(np.std(csc_csci_values)) if csc_csci_values else 0.0

    # P1-D: Use topdown_n_active (fixed counting) instead of len(top_down_constraints)
    topdown_active_counts = [sr.get('cross_scale_coupling', {}).get('topdown_n_active', 0)
                             for sr in step_results if 'cross_scale_coupling' in sr]
    topdown_max_active = int(np.max(topdown_active_counts)) if topdown_active_counts else 0
    topdown_mean_active = float(np.mean(topdown_active_counts)) if topdown_active_counts else 0.0

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
    nse_history_depth_max = float(np.max(nse_history_depth_values)) if nse_history_depth_values else 0.0
    nse_history_depth_mean = float(np.mean(nse_history_depth_values)) if nse_history_depth_values else 0.0

    nse_turning_points_values = [sr.get('narrative_self_emergence', {}).get('n_turning_points', 0)
                                 for sr in step_results if 'narrative_self_emergence' in sr]
    nse_turning_points_max = int(np.max(nse_turning_points_values)) if nse_turning_points_values else 0
    nse_turning_points_final = nse_turning_points_values[-1] if nse_turning_points_values else 0

    nse_stability_values = [sr.get('narrative_self_emergence', {}).get('stability_score', 0.0)
                            for sr in step_results if 'narrative_self_emergence' in sr]
    nse_stability_mean = float(np.mean(nse_stability_values)) if nse_stability_values else 0.0

    amc_momentum_values = [sr.get('adaptive_momentum', {}).get('momentum_bonus', 0.0)
                           for sr in step_results if 'adaptive_momentum' in sr]
    amc_momentum_final = amc_momentum_values[-1] if amc_momentum_values else 0.0
    amc_momentum_mean = float(np.mean(amc_momentum_values)) if amc_momentum_values else 0.0
    amc_mode_values = [sr.get('adaptive_momentum', {}).get('mode', 'normal')
                       for sr in step_results if 'adaptive_momentum' in sr]
    amc_mode_final = amc_mode_values[-1] if amc_mode_values else 'normal'
    amc_entropy_values = [sr.get('adaptive_momentum', {}).get('entropy', 0.0)
                          for sr in step_results if 'adaptive_momentum' in sr]
    amc_entropy_final = amc_entropy_values[-1] if amc_entropy_values else 0.0

    ilp_floor_values = [sr.get('institutional_protector', {}).get('institutional_floor', 0.0)
                        for sr in step_results if 'institutional_protector' in sr]
    ilp_floor_final = ilp_floor_values[-1] if ilp_floor_values else 0.0
    ilp_transition_values = [sr.get('institutional_protector', {}).get('transition_allowed', False)
                             for sr in step_results if 'institutional_protector' in sr]
    ilp_transition_count = sum(1 for v in ilp_transition_values if v)
    ilp_protection_values = [sr.get('institutional_protector', {}).get('protection_level', 'none')
                             for sr in step_results if 'institutional_protector' in sr]
    ilp_protection_final = ilp_protection_values[-1] if ilp_protection_values else 'none'

    civ_limiter_summary = narrative.civ_rate_limiter.get_summary()

    # P1-D: Check if layer was sealed
    layer_sealed = layer_0.get('sealed', False)
    layer_steps = layer_0.get('steps', 0)

    return {
        'seed': seed,
        'elapsed': elapsed,
        'n_steps': len(step_results),
        'sealed': layer_sealed,
        'total_layer_steps': layer_steps,
        'odi_max': odi_max,
        'odi_mean': odi_mean,
        'msi_max': msi_max,
        'msi_mean': msi_mean,
        'six_pass_rate': six_pass_rate,
        'gbc_coherence_mean': gbc_coherence_mean,
        'gbc_pass_rate': gbc_pass_rate,
        'csc_csci_mean': csc_csci_mean,
        'csc_csci_std': csc_csci_std,
        'topdown_max_active': topdown_max_active,
        'topdown_mean_active': topdown_mean_active,
        'nse_nsi_max': nse_nsi_max,
        'nse_nsi_mean': nse_nsi_mean,
        'nse_nsi_active_rate': nse_nsi_active_rate,
        'nse_continuity_mean': nse_continuity_mean,
        'nse_stability_mean': nse_stability_mean,
        'nse_history_depth_max': nse_history_depth_max,
        'nse_history_depth_mean': nse_history_depth_mean,
        'nse_turning_points_max': nse_turning_points_max,
        'nse_turning_points_final': nse_turning_points_final,
        'amc_momentum_final': amc_momentum_final,
        'amc_momentum_mean': amc_momentum_mean,
        'amc_mode_final': amc_mode_final,
        'amc_entropy_final': amc_entropy_final,
        'ilp_floor_final': ilp_floor_final,
        'ilp_transition_count': ilp_transition_count,
        'ilp_protection_final': ilp_protection_final,
        'civ_count': civ_count,
        'inst_count': inst_count,
        'mini_count': mini_count,
        'active_count': active_count,
        'civ_limiter_total_seen': civ_limiter_summary['total_civ_seen'],
        'civ_limiter_total_downgrades': civ_limiter_summary['total_downgrades'],
        'civ_limiter_downgrade_rate': civ_limiter_summary['downgrade_rate'],
    }


def evaluate_hypotheses(results):
    """Evaluate H1-H8 across all seeds."""
    nsi_max_vals = [r['nse_nsi_max'] for r in results]
    nsi_active_rates = [r['nse_nsi_active_rate'] for r in results]
    continuity_means = [r['nse_continuity_mean'] for r in results]
    history_depth_maxs = [r['nse_history_depth_max'] for r in results]
    history_depth_means = [r['nse_history_depth_mean'] for r in results]
    turning_points_maxs = [r['nse_turning_points_max'] for r in results]
    turning_points_finals = [r['nse_turning_points_final'] for r in results]
    civ_counts = [r['civ_count'] for r in results]
    csci_stds = [r['csc_csci_std'] for r in results]
    topdown_max = [r['topdown_max_active'] for r in results]

    n_seeds = len(results)
    total_steps = sum(r['n_steps'] for r in results)

    civ_mean = float(np.mean(civ_counts))
    civ_min = int(np.min(civ_counts)) if civ_counts else 0

    h1 = float(np.max(nsi_max_vals)) > 0.1
    h2 = all(rate > 0.3 for rate in nsi_active_rates)
    h3 = float(np.mean(continuity_means)) > 0.1
    h4_depth = float(np.mean(history_depth_means)) > 0.05
    h4_tp = float(np.mean(turning_points_finals)) > 0.0
    h4 = h4_depth or h4_tp
    h5 = 3.0 <= civ_mean <= 15.0
    h6 = civ_min >= 3
    h7 = float(np.mean(csci_stds)) > 0.005
    h8 = sum(1 for v in topdown_max if v > 0) >= 2

    return {
        'H1_nsi_max': {'value': float(np.max(nsi_max_vals)), 'threshold': '>0.1', 'pass': h1},
        'H2_nsi_active_rate': {'value': float(np.mean(nsi_active_rates)), 'threshold': '>0.3 all', 'pass': h2},
        'H3_continuity_mean': {'value': float(np.mean(continuity_means)), 'threshold': '>0.1', 'pass': h3},
        'H4_history_depth_mean': {'value': float(np.mean(history_depth_means)), 'threshold': '>0.05', 'pass': h4_depth},
        'H4_turning_points_final_mean': {'value': float(np.mean(turning_points_finals)), 'threshold': '>0.0', 'pass': h4_tp},
        'H4_combined': {'value': f'depth={float(np.mean(history_depth_means)):.4f}, tp={float(np.mean(turning_points_finals)):.1f}', 'threshold': 'depth>0.05 OR tp>0', 'pass': h4},
        'H5_civ_mean': {'value': civ_mean, 'threshold': '[3,15]', 'pass': h5},
        'H6_civ_min': {'value': civ_min, 'threshold': '>=3', 'pass': h6},
        'H7_csci_std_mean': {'value': float(np.mean(csci_stds)), 'threshold': '>0.005', 'pass': h7},
        'H8_topdown_active_seeds': {'value': sum(1 for v in topdown_max if v > 0), 'threshold': '>=2 seeds', 'pass': h8},
        'summary': {
            'n_seeds': n_seeds,
            'total_steps': total_steps,
            'all_pass': h1 and h2 and h3 and h4 and h5 and h6 and h7 and h8,
            'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'failed': [name for name, val in [('H1', h1), ('H2', h2), ('H3', h3), ('H4', h4), ('H5', h5), ('H6', h6), ('H7', h7), ('H8', h8)] if not val],
        }
    }


def main():
    SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
    N0 = 72
    STEPS = 1600
    SAMPLE_INTERVAL = 10
    GBC_SOFT_NUDGE = 0.2

    print(f"exp_105: P1-D Fixes — INSTITUTIONAL Activity-Driven TopDown & Seal Timeout")
    print(f"  N0={N0}, steps={STEPS}, {len(SEEDS)} seeds")
    print(f"  CSC=ON (topdown_threshold=0.05), GBC=ON (random dir), AMC=ON, ILP=ON")
    print(f"  NSE=ON: max_turning_points=25, moderated non-triviality")
    print(f"  CIVRateLimiterV2P1D: max_rate=0.10 (was 0.08), cooldown=10 (was 8)")
    print(f"  Fixes: counting bug fix, ILP stability fallback, INSTITUTIONAL activity boost, TopDown thresh 0.05")
    print()

    all_results = []
    for seed in SEEDS:
        result = run_single_seed(
            N0=N0, steps=STEPS, seed=seed,
            sample_interval=SAMPLE_INTERVAL,
            gbc_soft_nudge=GBC_SOFT_NUDGE,
            use_csc=True, csc_config=EXP105_CSC_CONFIG,
            use_nse=True, use_amc=True, use_ilp=True,
        )
        all_results.append(result)
        print(f"  seed={seed}: NSI_max={result['nse_nsi_max']:.4f}, "
              f"continuity={result['nse_continuity_mean']:.4f}, "
              f"stability={result['nse_stability_mean']:.4f}, "
              f"history_depth={result['nse_history_depth_mean']:.4f}, "
              f"turning_points={result['nse_turning_points_max']}, "
              f"CSCI={result['csc_csci_mean']:.4f} (std={result['csc_csci_std']:.4f}), "
              f"topdown={result['topdown_max_active']}, "
              f"civ={result['civ_count']}, "
              f"limiter_seen={result['civ_limiter_total_seen']}, "
              f"limiter_down={result['civ_limiter_total_downgrades']}, "
              f"sealed={result['sealed']}, "
              f"layer_steps={result['total_layer_steps']}")

    print()
    print("=" * 60)
    print("HYPOTHESIS EVALUATION")
    print("=" * 60)

    hypotheses = evaluate_hypotheses(all_results)

    for h_name in ['H1_nsi_max', 'H2_nsi_active_rate', 'H3_continuity_mean',
                   'H4_combined', 'H5_civ_mean', 'H6_civ_min',
                   'H7_csci_std_mean', 'H8_topdown_active_seeds']:
        h = hypotheses[h_name]
        status = "PASS" if h['pass'] else "FAIL"
        print(f"  {h_name}: {status} (value={h['value']}, threshold={h['threshold']})")

    summary = hypotheses['summary']
    print()
    print(f"Result: {summary['n_pass']}/8 hypotheses pass")
    if summary['all_pass']:
        print("ALL HYPOTHESES PASS!")
    else:
        print(f"Failed: {', '.join(summary['failed'])}")

    # Comparison with exp_104
    print()
    print("COMPARISON WITH exp_104")
    print("-" * 60)
    print(f"  {'Seed':>6} | {'e104 NSI':>10} | {'e105 NSI':>10} | "
          f"{'e104 stab':>10} | {'e105 stab':>10} | "
          f"{'e104 civ':>9} | {'e105 civ':>9} | "
          f"{'e104 td':>8} | {'e105 td':>8} | "
          f"{'e104 seal':>8} | {'e105 seal':>8}")
    exp_104_nsi = {42: 0.769, 142: 0.642, 242: 0.710, 342: 0.598,
                   442: 0.795, 542: 0.675, 642: 0.622, 742: 0.734}
    exp_104_stab = {42: 0.639, 142: 0.630, 242: 0.636, 342: 0.633,
                    442: 0.630, 542: 0.630, 642: 0.633, 742: 0.630}
    exp_104_civ = {42: 5, 142: 3, 242: 206, 342: 3, 442: 3, 542: 7, 642: 3, 742: 3}
    exp_104_td = {42: 0, 142: 0, 242: 0, 342: 0, 442: 0, 542: 0, 642: 0, 742: 0}
    exp_104_seal = {42: True, 142: True, 242: False, 342: True, 442: True, 542: True, 642: True, 742: True}
    for r in all_results:
        s = r['seed']
        print(f"  {s:>6} | {exp_104_nsi.get(s, 0):>10.4f} | {r['nse_nsi_max']:>10.4f} | "
              f"{exp_104_stab.get(s, 0):>10.4f} | {r['nse_stability_mean']:>10.4f} | "
              f"{exp_104_civ.get(s, 0):>9} | {r['civ_count']:>9} | "
              f"{exp_104_td.get(s, 0):>8} | {r['topdown_max_active']:>8} | "
              f"{'T' if exp_104_seal.get(s, False) else 'F':>8} | "
              f"{'T' if r.get('sealed', False) else 'F':>8}")

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output = {
        'experiment': 'exp_105_p1d_fixes',
        'timestamp': timestamp,
        'config': {
            'N0': N0, 'steps': STEPS, 'seeds': SEEDS,
            'sample_interval': SAMPLE_INTERVAL,
            'gbc_soft_nudge': GBC_SOFT_NUDGE,
            'csc': 'ON (topdown_stability_threshold=0.05)',
            'gbc': 'ON (random direction init)',
            'nse': 'ON (threshold=0.02, odi=0.4, msi=0.3, civ=0.0, gbc=0.1, max_tp=25, non-triviality moderated)',
            'amc': 'ON', 'ilp': 'ON',
            'civ_rate_limiter_v2_p1d': 'ON (max_rate=0.10, cooldown=10, min_guarantee=3)',
            'fixes_from_exp_104': [
                'BUG FIX: TopDown counting — iterate .items() instead of dict keys (was always 0)',
                'BUG FIX: ILP stability fallback — use get_history() + derive stability (get_summary() did not exist)',
                'NEW: INSTITUTIONAL activity-based stability boost — when inst_activity > 0, boost stability',
                'TopDown threshold: 0.10->0.05 (further lowered for INSTITUTIONAL-driven activation)',
                'CIVRateLimiter: max_rate 0.08->0.10, cooldown 8->10 (further relaxation)',
            ],
        },
        'per_seed': all_results,
        'hypotheses': hypotheses,
    }

    output_dir = os.path.join(PROJECT_ROOT, 'experiments')
    output_path = os.path.join(output_dir, f'exp_105_results_{timestamp}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")

    return hypotheses['summary']['all_pass']


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
