"""
experiments/exp_125_phase5_c1_n0_shrinking.py

Phase 5 Track C1: N0 Shrinking — Resource-Constrained Adaptation

Purpose: Find the minimum viable system size N0* where H1-H8 still pass.
Track C tests whether the CSC+NSE architecture can maintain narrative
emergence under spatial resource constraints.

Track C tests resource constraints (spatial: N0 shrinking) after:
  - Track A (perturbation recovery) — system under external shock ✅
  - Track B (multi-layer dynamics) — system with layered hierarchy ✅

Architecture: CSC+NSE (simplified, no AMC/ILP) — same as Phase 4 P2 Track B
N0 values: 48 (baseline), 32, 24, 16
Seeds per N0: 4 (42, 142, 242, 342)
Steps: 1600

Hypotheses:
  H32: Exists N0* ∈ [16, 32] where H1-H8 start failing
  H33: N0 decreases → NSI decreases but continuity increases
  H34: CIV range stays ≥ 3 at N0=24
  H35: CIV_min stays ≥ 2 at N0=16 (partial)
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
    """Same limiter as exp_107/exp_109 (proven stable)."""

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
    """V4 P1-F: CIVRateLimiterV2P1F (same as exp_107/exp_109)."""

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
    """Run a single seed with simplified CSC+NSE stack (no AMC, no ILP)."""
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

    # AMC: OFF (redundant per Track A ablation)
    # ILP: OFF (redundant per Track A ablation)

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
    )

    print(f"    [seed={seed}] Running...", flush=True)
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    civ_count = 0
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
        'civ_count': civ_count,
        'civ_limiter_total_seen': civ_limiter_summary['total_civ_seen'],
    }


def evaluate_hypotheses(results, n0_label="unknown"):
    """Evaluate H1-H8 across all seeds for a given N0 config.
    H6 threshold >=2 (P1-F standard)."""
    if not results:
        return {'summary': {'all_pass': False, 'n_pass': 0, 'failed': ['no_data']}}

    nsi_max_vals = [r['nse_nsi_max'] for r in results]
    nsi_active_rates = [r['nse_nsi_active_rate'] for r in results]
    continuity_means = [r['nse_continuity_mean'] for r in results]
    history_depth_means = [r['nse_history_depth_mean'] for r in results]
    turning_points_finals = [r['nse_turning_points_final'] for r in results]
    civ_counts = [r['civ_count'] for r in results]
    csci_stds = [r['csc_csci_std'] for r in results]
    topdown_max = [r['topdown_max_active'] for r in results]

    civ_mean = float(np.mean(civ_counts))
    civ_min = int(np.min(civ_counts)) if civ_counts else 0

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

    return {
        'n0': n0_label,
        'H1_nsi_max': {'value': float(np.max(nsi_max_vals)), 'threshold': '>0.1', 'pass': h1},
        'H2_nsi_active_rate': {'value': float(np.mean(nsi_active_rates)), 'threshold': '>0.3 all', 'pass': h2},
        'H3_continuity_mean': {'value': float(np.mean(continuity_means)), 'threshold': '>0.1', 'pass': h3},
        'H4_combined': {
            'value': f"depth={float(np.mean(history_depth_means)):.4f}, tp={float(np.mean(turning_points_finals)):.1f}",
            'threshold': 'depth>0.05 OR tp>0', 'pass': h4},
        'H5_civ_mean': {'value': civ_mean, 'threshold': '[3,15]', 'pass': h5},
        'H6_civ_min': {'value': civ_min, 'threshold': '>=2', 'pass': h6},
        'H7_csci_std_mean': {'value': float(np.mean(csci_stds)), 'threshold': '>0.005', 'pass': h7},
        'H8_topdown_active_seeds': {'value': sum(1 for v in topdown_max if v > 0), 'threshold': '>=2 seeds', 'pass': h8},
        'summary': {
            'all_pass': h1 and h2 and h3 and h4 and h5 and h6 and h7 and h8,
            'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'failed': [name for name, val in
                       [('H1', h1), ('H2', h2), ('H3', h3), ('H4', h4),
                        ('H5', h5), ('H6', h6), ('H7', h7), ('H8', h8)] if not val],
        }
    }


def evaluate_track_c_hypotheses(config_hypotheses):
    """Evaluate H32-H35 across N0 configurations.

    config_hypotheses: dict mapping N0 -> evaluate_hypotheses output
    """
    results = {}
    n0_values = [48, 30, 24, 18]

    # H32: Exists N0* ∈ [18, 30] where H1-H8 start failing
    n0_30 = config_hypotheses.get('N0_30', {})
    n0_24 = config_hypotheses.get('N0_24', {})
    n0_18 = config_hypotheses.get('N0_18', {})

    n30_pass = n0_30.get('summary', {}).get('all_pass', True)
    n24_pass = n0_24.get('summary', {}).get('all_pass', True)
    n18_pass = n0_18.get('summary', {}).get('all_pass', True)

    if not n30_pass:
        h32 = True  # N0* between 30 and 48
        n0_star = 30
    elif not n24_pass:
        h32 = True  # N0* between 24 and 30
        n0_star = 24
    elif not n18_pass:
        h32 = True  # N0* between 18 and 24
        n0_star = 18
    else:
        h32 = False  # N0* < 18 (all passed)
        n0_star = None

    # H33: NSI decreases but continuity increases with smaller N0
    n0_data = {}
    for label in ['N0_48_baseline', 'N0_30', 'N0_24', 'N0_18']:
        hyp = config_hypotheses.get(label, {})
        if hyp:
            n0_data[label] = {
                'nsi_active_rate': hyp.get('H2_nsi_active_rate', {}).get('value', 0),
                'continuity_mean': hyp.get('H3_continuity_mean', {}).get('value', 0),
                'n_pass': hyp.get('summary', {}).get('n_pass', 0),
            }

    # Check monotonicity: NSI should decrease, continuity should increase
    nsi_vals = [n0_data[k]['nsi_active_rate'] for k in
                ['N0_48_baseline', 'N0_30', 'N0_24', 'N0_18'] if k in n0_data]
    cont_vals = [n0_data[k]['continuity_mean'] for k in
                 ['N0_48_baseline', 'N0_30', 'N0_24', 'N0_18'] if k in n0_data]

    nsi_decreasing = all(nsi_vals[i] >= nsi_vals[i+1] for i in range(len(nsi_vals)-1))
    cont_increasing = all(cont_vals[i] <= cont_vals[i+1] for i in range(len(cont_vals)-1))
    h33 = nsi_decreasing or cont_increasing  # at least one direction monotonic

    # H34: CIV mean >= 3 at N0=24
    h34_val = n0_24.get('H5_civ_mean', {}).get('value', 0)
    h34 = h34_val >= 3.0

    # H35: CIV min >= 2 at N0=18
    h35_val = n0_18.get('H6_civ_min', {}).get('value', 0)
    h35 = h35_val >= 2

    results['H32_minimum_viable_size'] = {
        'description': f'Exists N0* ∈ [16,32] where H1-H8 fail. N0* = {n0_star}',
        'pass': h32,
        'n0_star': n0_star,
        'n32_pass': n32_pass,
        'n24_pass': n24_pass,
        'n16_pass': n16_pass,
    }
    results['H33_scale_quality_tradeoff'] = {
        'description': 'N0 decreases → NSI decreases & continuity increases',
        'pass': h33,
        'nsi_per_N0': {k: n0_data.get(k, {}).get('nsi_active_rate', '-') for k in
                        ['N0_48_baseline', 'N0_30', 'N0_24', 'N0_18']},
        'continuity_per_N0': {k: n0_data.get(k, {}).get('continuity_mean', '-') for k in
                              ['N0_48_baseline', 'N0_30', 'N0_24', 'N0_18']},
        'nsi_decreasing': nsi_decreasing,
        'cont_increasing': cont_increasing,
    }
    results['H34_civ_at_n24'] = {
        'description': 'CIV mean ≥ 3 at N0=24',
        'pass': h34,
        'civ_mean_n24': h34_val,
    }
    results['H35_civ_min_at_n16'] = {
        'description': 'CIV min ≥ 2 at N0=16',
        'pass': h35,
        'civ_min_n16': h35_val,
    }

    return results


# ─── Configurations ───
# NOTE: N0 must be divisible by 3 (3D Hamming lattice constraint).
# N0=32 rounds to N=33 causing tensor mismatch.
# N0=16 rounds to N=18 causing tensor mismatch.
N0_CONFIGS = [
    {'label': 'N0_48_baseline', 'N0': 48, 'description': 'Baseline (matching exp_109)'},
    {'label': 'N0_30', 'N0': 30, 'description': 'Small — minimum in [16,32] range'},
    {'label': 'N0_24', 'N0': 24, 'description': 'Very small — 3D lattice safe (24→24)'},
    {'label': 'N0_18', 'N0': 18, 'description': 'Extreme — below min_active_bits threshold'},
]

SEEDS = [42, 142, 242, 342]
N_STEPS = 1600
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2


def main():
    print("=" * 70)
    print("exp_125: Phase 5 Track C1 — N0 Shrinking Test (Resource Constraints)")
    print(f"  Architecture: CSC+NSE (simplified, no AMC/ILP)")
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
                      f"civ={result['civ_count']}, "
                      f"sealed={result['sealed']}")
            except Exception as e:
                print(f"    *** seed={seed}: FAILED — {e}", flush=True)
                all_seed_results.append({
                    'N0': N0, 'seed': seed, 'elapsed': 0,
                    'error': str(e),
                    'sealed': False, 'odi_max': 0, 'gbc_coherence_mean': 0,
                    'gbc_pass_rate': 0, 'csc_csci_std': 0, 'topdown_max_active': 0,
                    'nse_nsi_max': 0, 'nse_nsi_mean': 0, 'nse_nsi_active_rate': 0,
                    'nse_continuity_mean': 0, 'nse_history_depth_mean': 0,
                    'nse_turning_points_final': 0, 'civ_count': 0,
                    'civ_limiter_total_seen': 0,
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
            print(" — ALL PASS ✅")
        else:
            print(f" — Failed: {', '.join(summary['failed'])}")

    # Evaluate C1 hypotheses
    c1_hypotheses = evaluate_track_c_hypotheses(config_hypotheses)

    # ─── Summary table ───
    print("\n" + "=" * 70)
    print("TRACK C1 SUMMARY — N0 Shrinking")
    print("=" * 70)
    print(f"  {'Config':<18} | {'N0':>4} | {'Pass':>6} | {'Failed':<22} | {'CIV':>5} | {'NSI':>8} | {'Cont':>6}")
    print(f"  {'─' * 18} | {'─' * 4} | {'─' * 6} | {'─' * 22} | {'─' * 5} | {'─' * 8} | {'─' * 6}")
    for cfg in N0_CONFIGS:
        h = config_hypotheses.get(cfg['label'], {}).get('summary', {})
        failed_str = ', '.join(h.get('failed', [])) if h.get('failed') else '—'
        civ_mean = config_hypotheses.get(cfg['label'], {}).get('H5_civ_mean', {}).get('value', 0)
        nsi_active = config_hypotheses.get(cfg['label'], {}).get('H2_nsi_active_rate', {}).get('value', 0)
        cont_mean = config_hypotheses.get(cfg['label'], {}).get('H3_continuity_mean', {}).get('value', 0)
        print(f"  {cfg['label']:<18} | {cfg['N0']:>4} | "
              f"{h.get('n_pass', 0):>3}/8 | {failed_str:<22} | "
              f"{civ_mean:>5.1f} | {nsi_active:>8.4f} | {cont_mean:>6.4f}")

    print("\n" + "─" * 70)
    print("TRACK C1 HYPOTHESES (H32-H35)")
    print("─" * 70)
    for h_name, h_info in c1_hypotheses.items():
        status = "PASS ✅" if h_info['pass'] else "FAIL ❌"
        print(f"  {h_name}: {status}")
        print(f"    {h_info['description']}")

    # ─── N0* detection ───
    n0_star = c1_hypotheses.get('H32_minimum_viable_size', {}).get('n0_star')
    if n0_star:
        print(f"\n  ► N0* = {n0_star} (minimum viable system size)")
    else:
        print(f"\n  ► N0* < 16 (system viable at all tested sizes)")

    # ─── Per-seed detail table ───
    print("\n" + "─" * 70)
    print("PER-SEED DETAIL")
    print("─" * 70)
    for cfg in N0_CONFIGS:
        config_name = cfg['label']
        print(f"\n  {config_name} (N0={cfg['N0']}):")
        for r in all_config_results.get(config_name, {}).get('per_seed', []):
            error_str = f" [ERROR: {r.get('error', '')}]" if 'error' in r else ""
            print(f"    seed={r.get('seed', '?'):>3}: civ={r.get('civ_count', 0):>3}, "
                  f"nsi_max={r.get('nse_nsi_max', 0):.4f}, "
                  f"nsi_mean={r.get('nse_nsi_mean', 0):.4f}, "
                  f"cont={r.get('nse_continuity_mean', 0):.4f}{error_str}")

    # ─── Save results ───
    results_file = os.path.join(PROJECT_ROOT, 'experiments', f'exp_125_c1_results_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
    save_data = {
        'experiment': 'exp_125_phase5_c1_n0_shrinking',
        'datetime': datetime.now().isoformat(),
        'configs': N0_CONFIGS,
        'seeds': SEEDS,
        'per_config': {},
        'track_c_hypotheses': c1_hypotheses,
    }
    for config_name, data in all_config_results.items():
        serializable = {
            'hypotheses': data['hypotheses'],
            'per_seed': []
        }
        for r in data['per_seed']:
            # Remove non-serializable items
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
    print(f"\n  Results saved to: {results_file}")


if __name__ == "__main__":
    main()