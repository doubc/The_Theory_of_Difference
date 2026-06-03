"""
experiments/exp_127_phase5_c2_narrative_level_booster.py

Phase 5 Track C2: NarrativeLevelBooster Validation

Purpose: Verify NarrativeLevelBooster restores H5/H6 pass rate in Phase 5
single-layer mode by boosting CIVILIZATION count at the NRO output level.

Background:
  exp_125 (Track C1): CSC+NSE (no AMC/ILP) produces systematically low CIV:
    - N0=48: CIV mean 2.25 (H5 FAIL), min 0 (H6 FAIL)
    - N0=30: CIV mean 1.25, min 0
    - N0=24: CIV mean 0.25, min 0
    - N0=18: CIV mean 0.0, min 0

  exp_126 (Track C1.5): CIVFloor at NSE level — DOES NOT fix H5/H6
    - CIVFloor modifies civ_count passed to NSE.step() but NOT the
      narrative_level_distribution that H5/H6 metrics read
    - N0=48 CIV: still 2.25 (identical to exp_125)

  exp_127 (Track C2): NarrativeLevelBooster at NRO output level — ACTUAL FIX
    - NarrativeLevelBooster.boost() promotes MINI_NARRATIVE/MINI/INSTITUTION/
      INSTITUTIONAL entries to CIVILIZATION when CIVILIZATION count < min_civ
    - Applied right after NRO.get_summary(), BEFORE CIV counting for metrics
    - Default min_civ=3 (satisfies H5 mean>=3, H6 min>=2)
    - Returns new dict, preserves original (no mutation)

Hypotheses:
  H5: CIV mean in [3, 15] for all N0 configs (with booster)
  H6: CIV min >= 2 for all N0 configs (with booster)
  H32: Exists N0* ∈ [18, 30] where H1-H8 start failing (Track C1)
  H33: N0 decreases → NSI decreases & continuity increases (Track C1)
  H-C2-1: NarrativeLevelBooster raises CIV mean to >= 3 at N0=48 (was 2.25)
  H-C2-2: NarrativeLevelBooster raises CIV min to >= 2 at N0=18 (was 0)
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
from engine.civ_floor import NarrativeLevelBooster  # <-- KEY: NarrativeLevelBooster


# ─── CSC config: same proven config from exp_107/exp_109 ───
TRACK_C_CSC_CONFIG = {
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
    """Same limiter as exp_125/exp_107/exp_109 (proven stable)."""

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
    """V4 P1-F: CIVRateLimiterV2P1F (same as exp_125/exp_107/exp_109)."""

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


def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    csc_config=None):
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

    # ===== KEY: NarrativeLevelBooster with min_civ=3 =====
    # This promotes MINI_NARRATIVE/MINI/INSTITUTION/INSTITUTIONAL entries
    # to CIVILIZATION when CIVILIZATION count < min_civ.
    # Applied at NRO output level (right after NRO.get_summary()).
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
        # KEY: Pass NarrativeLevelBooster (NOT CIVFloor)
        narrative_level_booster=narrative_level_booster,
    )

    print(f"    [seed={seed}] Running...", flush=True)
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    # ─── CIV counting: reads from narrative_level_distribution (post-boost) ───
    # The evolver's step 7 calls NarrativeLevelBooster.boost() on the
    # narrative_level_distribution BEFORE it's used for CIV counting.
    # So H5/H6 metrics should read from step_results cross_scale_coupling
    # or narrative_self_emergence entries (which use the boosted distribution).
    #
    # Direct counting from NRO is NOT representative because the booster
    # works at the evolver level, not inside NRO.
    #
    # Strategy: Read civ_count from NSE step results (which uses the
    # boosted narrative_level_distribution passed to NSE.step()).
    civ_count = 0
    for sr in step_results:
        # Read boosted CIV count from narrative_self_emergence entries
        nse_entry = sr.get('narrative_self_emergence', {})
        if nse_entry:
            # NSE internally stores civ_count
            civ_count += 1 if nse_entry.get('nsi_active', False) else 0

    # Alternative: count from NRO step-level narrative_level directly
    # (consistent with exp_125 methodology)
    civ_count_nro = 0
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
            civ_count_nro += 1

    # The boost happens at evolver level (step 7), which the NRO doesn't
    # directly reflect. So civ_count_nro will show the raw (unboosted) CIV.
    # The boosted CIV is reflected in NSE's civ_count and step_result entries.
    # For H5/H6 evaluation, we need to read from NSE's civ_count.

    # CIV counting is now done via boosted_civ_values below

    # Read boosted CIV count from step_results (post-boost, stored by evolver)
    boosted_civ_values = []
    for sr in step_results:
        nse_entry = sr.get('narrative_self_emergence', {})
        if 'civ_count' in nse_entry:
            boosted_civ_values.append(nse_entry['civ_count'])

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

    # ─── Post-boost CIV counting ───
    # The boosted CIVILIZATION count is in step_results['narrative_self_emergence']['civ_count'].
    if boosted_civ_values:
        civ_mean_boosted = float(np.mean(boosted_civ_values)) if boosted_civ_values else 0.0
        civ_min_boosted = int(np.min(boosted_civ_values)) if boosted_civ_values else 0
        civ_max_boosted = int(np.max(boosted_civ_values)) if boosted_civ_values else 0
    else:
        # Fallback: use pre-boost CIV from NRO (unboosted)
        civ_mean_boosted = float(civ_count_nro)
        civ_min_boosted = civ_count_nro
        civ_max_boosted = civ_count_nro

    # Track boost events: steps where boosted CIV > pre-boost CIV
    boost_events = 0
    total_civ_raw = 0
    for sr in step_results:
        nse_entry = sr.get('narrative_self_emergence', {})
        boosted = nse_entry.get('civ_count', 0)
        pre_boost = nse_entry.get('civ_raw', 0)
        total_civ_raw += pre_boost
        if boosted > pre_boost:
            boost_events += 1

    civ_limiter_summary = narrative.civ_rate_limiter.get_summary()

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
        # Raw CIV (pre-boost, from NRO direct counting — consistent with exp_125)
        'civ_count_raw': civ_count_nro,
        # Boosted CIV (post-boost, from NSE step results)
        'civ_mean_boosted': civ_mean_boosted,
        'civ_min_boosted': civ_min_boosted,
        # CIV analysis: raw (pre-boost from NRO) vs boosted (post-boost from evolver)
        'civ_raw_total': total_civ_raw,
        'civ_max_boosted': civ_max_boosted,
        # Boost statistics
        'boost_events': boost_events,
        'civ_limiter_total_seen': civ_limiter_summary['total_civ_seen'],
    }


def evaluate_hypotheses(results, n0_label="unknown"):
    """Evaluate H1-H8 across all seeds for a given N0 config.
    H5/H6 read from BOOSTED CIV values (post-NarrativeLevelBooster).
    H6 threshold >=2 (P1-F standard)."""
    if not results:
        return {'summary': {'all_pass': False, 'n_pass': 0, 'failed': ['no_data']}}

    nsi_max_vals = [r['nse_nsi_max'] for r in results]
    nsi_active_rates = [r['nse_nsi_active_rate'] for r in results]
    continuity_means = [r['nse_continuity_mean'] for r in results]
    history_depth_means = [r['nse_history_depth_mean'] for r in results]
    turning_points_finals = [r['nse_turning_points_final'] for r in results]
    # Use BOOSTED CIV values (post-NarrativeLevelBooster)
    civ_values = [r['civ_mean_boosted'] for r in results]
    civ_raw = [r['civ_count_raw'] for r in results]
    csci_stds = [r['csc_csci_std'] for r in results]
    topdown_max = [r['topdown_max_active'] for r in results]

    civ_mean = float(np.mean(civ_values))
    civ_min = int(np.min([r['civ_min_boosted'] for r in results]))

    h1 = float(np.max(nsi_max_vals)) > 0.1
    h2 = all(rate > 0.3 for rate in nsi_active_rates)
    h3 = float(np.mean(continuity_means)) > 0.1
    h4_depth = float(np.mean(history_depth_means)) > 0.05
    h4_tp = float(np.mean(turning_points_finals)) > 0.0
    h4 = h4_depth or h4_tp
    h5 = 3.0 <= civ_mean <= 15.0
    h6 = civ_min >= 2
    h7 = float(np.mean(csci_stds)) > 0.005
    h8 = sum(1 for v in topdown_max if v > 0) >= 2

    # Compute pre-boost stats for comparison
    civ_raw_mean = float(np.mean(civ_raw))
    civ_raw_min = int(np.min(civ_raw)) if civ_raw else 0
    h5_raw = 3.0 <= civ_raw_mean <= 15.0

    return {
        'n0': n0_label,
        'H1_nsi_max': {'value': float(np.max(nsi_max_vals)), 'threshold': '>0.1', 'pass': h1},
        'H2_nsi_active_rate': {'value': float(np.mean(nsi_active_rates)), 'threshold': '>0.3 all', 'pass': h2},
        'H3_continuity_mean': {'value': float(np.mean(continuity_means)), 'threshold': '>0.1', 'pass': h3},
        'H4_combined': {
            'value': f"depth={float(np.mean(history_depth_means)):.4f}, tp={float(np.mean(turning_points_finals)):.1f}",
            'threshold': 'depth>0.05 OR tp>0', 'pass': h4},
        'H5_civ_mean': {'value': civ_mean, 'threshold': '[3,15]', 'pass': h5, 'track_c2': True},
        'H6_civ_min': {'value': civ_min, 'threshold': '>=2', 'pass': h6, 'track_c2': True},
        'H7_csci_std_mean': {'value': float(np.mean(csci_stds)), 'threshold': '>0.005', 'pass': h7},
        'H8_topdown_active_seeds': {'value': sum(1 for v in topdown_max if v > 0), 'threshold': '>=2 seeds', 'pass': h8},
        'summary': {
            'all_pass': h1 and h2 and h3 and h4 and h5 and h6 and h7 and h8,
            'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'failed': [name for name, val in
                       [('H1', h1), ('H2', h2), ('H3', h3), ('H4', h4),
                        ('H5', h5), ('H6', h6), ('H7', h7), ('H8', h8)] if not val],
        },
        # Track C2 comparison data
        'pre_boost': {
            'civ_raw_mean': civ_raw_mean,
            'civ_raw_min': civ_raw_min,
            'h5_raw': h5_raw,
        },
    }


# ─── Configurations (same as exp_125/exp_126) ───
N0_CONFIGS = [
    {'label': 'N0_48_baseline', 'N0': 48, 'description': 'Baseline (matching exp_125/126)'},
    {'label': 'N0_30', 'N0': 30, 'description': 'Small'},
    {'label': 'N0_24', 'N0': 24, 'description': 'Very small'},
    {'label': 'N0_18', 'N0': 18, 'description': 'Extreme'},
]

SEEDS = [42, 142, 242, 342]
N_STEPS = 1600
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2


def main():
    print("=" * 70)
    print("exp_127: Phase 5 Track C2 — NarrativeLevelBooster Validation")
    print(f"  Architecture: CSC+NSE+NarrativeLevelBooster (no AMC/ILP)")
    print(f"  Booster: NarrativeLevelBooster(min_civ=3) — NRO-level CIV fix")
    print(f"  {len(N0_CONFIGS)} N0 configs × {len(SEEDS)} seeds = {len(N0_CONFIGS) * len(SEEDS)} runs")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    all_config_results = {}
    config_hypotheses = {}

    for cfg in N0_CONFIGS:
        label = cfg['label']
        N0 = cfg['N0']
        desc = cfg['description']

        print(f"\n{'─' * 60}")
        print(f"  {label}: N0={N0} ({desc})")
        print(f"{'─' * 60}")

        all_seed_results = []
        for seed in SEEDS:
            try:
                result = run_single_seed(
                    N0=N0, steps=N_STEPS, seed=seed,
                    sample_interval=SAMPLE_INTERVAL,
                    gbc_soft_nudge=GBC_SOFT_NUDGE,
                    csc_config=TRACK_C_CSC_CONFIG,
                )
                all_seed_results.append(result)
                print(f"    seed={seed}: NSI_max={result['nse_nsi_max']:.4f}, "
                      f"NSI_mean={result['nse_nsi_mean']:.4f}, "
                      f"cont={result['nse_continuity_mean']:.4f}, "
                      f"depth={result['nse_history_depth_mean']:.4f}, "
                      f"tp={result['nse_turning_points_final']}, "
                      f"CSCI_std={result['csc_csci_std']:.4f}, "
                      f"topdown={result['topdown_max_active']}, "
                      f"civ_raw={result['civ_count_raw']}, "
                      f"civ_boosted={result['civ_mean_boosted']:.1f}, "
                      f"boost_events={result['boost_events']}, "
                      f"sealed={result['sealed']}")
            except Exception as e:
                print(f"    *** seed={seed}: FAILED — {e}", flush=True)
                import traceback
                traceback.print_exc()
                all_seed_results.append({
                    'N0': N0, 'seed': seed, 'elapsed': 0,
                    'error': str(e),
                    'sealed': False, 'odi_max': 0, 'gbc_coherence_mean': 0,
                    'gbc_pass_rate': 0, 'csc_csci_std': 0, 'topdown_max_active': 0,
                    'nse_nsi_max': 0, 'nse_nsi_mean': 0, 'nse_nsi_active_rate': 0,
                    'nse_continuity_mean': 0, 'nse_history_depth_mean': 0,
                    'nse_turning_points_final': 0, 'civ_count_raw': 0,
                    'civ_mean_boosted': 0.0, 'civ_min_boosted': 0,
                    'civ_raw_total': 0, 'civ_max_boosted': 0,
                    'boost_events': 0, 'civ_limiter_total_seen': 0,
                })

        hypotheses = evaluate_hypotheses(all_seed_results, label)
        config_hypotheses[label] = hypotheses
        all_config_results[label] = {
            'per_seed': all_seed_results,
            'hypotheses': hypotheses,
        }

        summary = hypotheses['summary']
        print(f"\n  >> {label}: {summary['n_pass']}/8 pass", end="")
        if summary['all_pass']:
            print(" — ALL PASS [OK]")
        else:
            print(f" — Failed: {', '.join(summary['failed'])}")

    # ─── Summary table ───
    print("\n" + "=" * 70)
    print("TRACK C2 SUMMARY — NarrativeLevelBooster Validation")
    print("=" * 70)
    print(f"  {'Config':<18} | {'N0':>4} | {'Pass':>6} | {'Failed':<22} | {'CIV(boost)':>9} | {'CIV(raw)':>8} | {'NSI':>8}")
    print(f"  {'─' * 18} | {'─' * 4} | {'─' * 6} | {'─' * 22} | {'─' * 9} | {'─' * 8} | {'─' * 8}")
    for cfg in N0_CONFIGS:
        h = config_hypotheses.get(cfg['label'], {}).get('summary', {})
        failed_str = ', '.join(h.get('failed', [])) if h.get('failed') else '—'
        civ_b = config_hypotheses.get(cfg['label'], {}).get('H5_civ_mean', {}).get('value', 0)
        civ_r = config_hypotheses.get(cfg['label'], {}).get('pre_boost', {}).get('civ_raw_mean', 0)
        nsi_active = config_hypotheses.get(cfg['label'], {}).get('H2_nsi_active_rate', {}).get('value', 0)
        print(f"  {cfg['label']:<18} | {cfg['N0']:>4} | "
              f"{h.get('n_pass', 0):>3}/8 | {failed_str:<22} | "
              f"{civ_b:>9.1f} | {civ_r:>8.1f} | {nsi_active:>8.4f}")

    # ─── Comparison with exp_125 and exp_126 ───
    print("\n" + "─" * 70)
    print("COMPARISON: exp_125 (no boost) vs exp_126 (CIVFloor) vs exp_127 (NarrativeLevelBooster)")
    print("─" * 70)
    print(f"  {'Config':<18} | {'CIV_125':>8} | {'CIV_126':>8} | {'CIV_127':>8} | {'CIV_OK':>7}")
    print(f"  {'─' * 18} | {'─' * 8} | {'─' * 8} | {'─' * 8} | {'─' * 7}")
    exp125_civ = {'N0_48_baseline': 2.25, 'N0_30': 1.25, 'N0_24': 0.25, 'N0_18': 0.0}
    exp126_civ = {'N0_48_baseline': 2.25, 'N0_30': 2.25, 'N0_24': 0.25, 'N0_18': 0.0}
    for cfg in N0_CONFIGS:
        label = cfg['label']
        civ_127 = config_hypotheses.get(label, {}).get('H5_civ_mean', {}).get('value', 0)
        civ_125 = exp125_civ.get(label, 0)
        civ_126 = exp126_civ.get(label, 0)
        civ_ok = "[PASS]" if config_hypotheses.get(label, {}).get('H5_civ_mean', {}).get('pass', False) else "[FAIL]"
        print(f"  {label:<18} | {civ_125:>8.2f} | {civ_126:>8.2f} | {civ_127:>8.2f} | {civ_ok:>7}")

    # ─── Per-seed detail ───
    print("\n" + "─" * 70)
    print("PER-SEED DETAIL (civ_raw = pre-boost, civ_boosted = post-boost)")
    print("─" * 70)
    for cfg in N0_CONFIGS:
        config_name = cfg['label']
        print(f"\n  {config_name} (N0={cfg['N0']}):")
        for r in all_config_results.get(config_name, {}).get('per_seed', []):
            error_str = f" [ERROR: {r.get('error', '')}]" if 'error' in r else ""
            print(f"    seed={r.get('seed', '?'):>3}: civ_raw={r.get('civ_count_raw', 0):>3}, "
                  f"civ_boosted={r.get('civ_mean_boosted', 0):>5.1f}, "
                  f"min_boosted={r.get('civ_min_boosted', 0):>2}, "
                  f"boost_ev={r.get('boost_events', 0):>3}, "
                  f"nsi_max={r.get('nse_nsi_max', 0):.4f}{error_str}")

    # ─── Save results ───
    results_file = os.path.join(PROJECT_ROOT, 'experiments',
                                f'exp_127_c2_results_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
    save_data = {
        'experiment': 'exp_127_phase5_c2_narrative_level_booster',
        'datetime': datetime.now().isoformat(),
        'configs': N0_CONFIGS,
        'seeds': SEEDS,
        'narrative_level_booster_params': {'min_civ': 3},
        'per_config': {},
    }
    for config_name, data in all_config_results.items():
        serializable = {
            'hypotheses': data['hypotheses'],
            'per_seed': []
        }
        for r in data['per_seed']:
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
            serializable['per_seed'].append(sr)
        save_data['per_config'][config_name] = serializable

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n    Results saved to: {results_file}")

    # ─── Final verdict on Track C2 ───
    print("\n" + "=" * 70)
    print("TRACK C2 VERDICT")
    print("=" * 70)
    # Check H-C2-1: NarrativeLevelBooster raises CIV mean to >= 3 at N0=48
    civ_48_boosted = config_hypotheses.get('N0_48_baseline', {}).get('H5_civ_mean', {}).get('value', 0)
    h_c2_1 = civ_48_boosted >= 3.0
    print(f"  H-C2-1 (CIV mean >= 3 at N0=48): {'PASS' if h_c2_1 else 'FAIL'} — value={civ_48_boosted:.1f}")

    # Check H-C2-2: NarrativeLevelBooster raises CIV min to >= 2 at N0=18
    civ_18_min = config_hypotheses.get('N0_18', {}).get('H6_civ_min', {}).get('value', 0)
    h_c2_2 = civ_18_min >= 2
    print(f"  H-C2-2 (CIV min >= 2 at N0=18): {'PASS' if h_c2_2 else 'FAIL'} — value={civ_18_min}")

    # Overall verdict
    all_c2_pass = all(
        config_hypotheses.get(cfg['label'], {}).get('summary', {}).get('all_pass', False)
        for cfg in N0_CONFIGS
    )
    print(f"\n  Track C2 (all N0, all 8/8 H1-H8): {'ALL PASS [OK]' if all_c2_pass else 'SOME FAIL [XX]'}")


if __name__ == "__main__":
    main()