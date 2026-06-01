"""
experiments/exp_110_phase4_p3_long_run_stability.py

Phase 4 Experiment 110: P3 — Long-Run Stability Test

Purpose: Verify that H1-H8 remain stable over extended simulation time (2000 steps),
using the proven CSC+NSE architecture at optimal scale (N0=72).

P0+P1 established stability at steps=1600 (exp_101 through exp_107).
P2 confirmed scale robustness at steps=1600 (exp_108/108b/109).
P3 tests whether the system remains stable at ~1.25x the standard duration.

Key question: Does the narrative self (NSE) maintain continuity over time?
Does cross-scale coupling (CSC) remain coherent? Or do metrics degrade?

Architecture: CSC+NSE (simplified, no AMC/ILP per Track A ablation)
  - CSC config: TRACK_B_CSC_CONFIG (proven stable across P0+P1+P2)
  - NSE config: same as exp_109 (history_multi_signal, max_tp=25)
  - CIVRateLimiterV2P1F: min_civ_guarantee=3

Hypotheses:
  H16 (long-run NSI stability): NSI mean at steps 1600-3200 >= NSI mean at steps 0-1600
  H17 (long-run CIV stability): CIV count at steps 1600-3200 >= 50% of CIV count at steps 0-1600
  H18 (long-run CSCI stability): CSCI std does not collapse to 0 in second half
  H19 (long-run TopDown persistence): TopDown activates in both halves
  H20 (no metric collapse): All H1-H8 pass at step 2000 (same thresholds)

Configuration:
  N0=72 (optimal per P2 Track B), steps=2000, seeds=[42, 142, 242]
  sample_interval=10 (same as P2)
"""

import sys
import os
import gc
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


# ─── CSC config: same proven config from P2 Track B ───
P3_CSC_CONFIG = {
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
    """V4 P1-F: proven stable across P0+P1+P2."""

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
    """Run a single seed with simplified CSC+NSE stack for long-run stability test."""
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

    # CSC: ON
    csc_cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
    if csc_config:
        csc_cfg.update(csc_config)
    csc = CrossScaleCoupling(config=csc_cfg)

    # NSE: ON
    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {
        'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1,
    }
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    # AMC: OFF, ILP: OFF (redundant per Track A)

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

    print(f"    [seed={seed}] Running {steps} steps...", flush=True)
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])
    n_steps = len(step_results)

    # Split into first half and second half for stability comparison
    mid = n_steps // 2
    first_half = step_results[:mid]
    second_half = step_results[mid:]

    def extract_metrics(sr_list):
        """Extract all metrics from a list of step results."""
        nsi_vals = [sr.get('narrative_self_emergence', {}).get('nsi', 0.0)
                    for sr in sr_list if 'narrative_self_emergence' in sr]
        nsi_active = [sr.get('narrative_self_emergence', {}).get('nsi_active', False)
                      for sr in sr_list if 'narrative_self_emergence' in sr]
        continuity_vals = [sr.get('narrative_self_emergence', {}).get('continuity_score', 0.0)
                           for sr in sr_list if 'narrative_self_emergence' in sr]
        depth_vals = [sr.get('narrative_self_emergence', {}).get('self_history_depth', 0.0)
                      for sr in sr_list if 'narrative_self_emergence' in sr]
        tp_vals = [sr.get('narrative_self_emergence', {}).get('n_turning_points', 0)
                   for sr in sr_list if 'narrative_self_emergence' in sr]

        csci_vals = [sr.get('cross_scale_coupling', {}).get('csci', 0.0)
                     for sr in sr_list if 'cross_scale_coupling' in sr]
        td_vals = [sr.get('cross_scale_coupling', {}).get('topdown_n_active', 0)
                   for sr in sr_list if 'cross_scale_coupling' in sr]

        # CIV count
        civ_count = 0
        for sr in sr_list:
            narr_info = sr.get('narrative_recursion', {})
            if narr_info and narr_info.get('narrative_level'):
                level = narr_info.get('narrative_level', 'MINI_NARRATIVE')
            else:
                level = sr.get('level', 'MINI')
            if level == 'MINI_NARRATIVE':
                level = 'MINI'
            if level == 'CIVILIZATION':
                civ_count += 1

        return {
            'nsi_vals': nsi_vals,
            'nsi_active': nsi_active,
            'continuity_vals': continuity_vals,
            'depth_vals': depth_vals,
            'tp_vals': tp_vals,
            'csci_vals': csci_vals,
            'td_vals': td_vals,
            'civ_count': civ_count,
        }

    def safe_mean(vals):
        return float(np.mean(vals)) if vals else 0.0

    def safe_max(vals):
        return float(np.max(vals)) if vals else 0.0

    def safe_std(vals):
        return float(np.std(vals)) if vals else 0.0

    fh = extract_metrics(first_half)
    sh = extract_metrics(second_half)

    return {
        'seed': seed,
        'elapsed': elapsed,
        'n_steps': n_steps,
        'sealed': layer_0.get('sealed', False),
        # First half metrics
        'fh_nsi_max': safe_max(fh['nsi_vals']),
        'fh_nsi_mean': safe_mean(fh['nsi_vals']),
        'fh_nsi_active_rate': float(np.mean(fh['nsi_active'])) if fh['nsi_active'] else 0.0,
        'fh_continuity_mean': safe_mean(fh['continuity_vals']),
        'fh_history_depth_mean': safe_mean(fh['depth_vals']),
        'fh_turning_points': fh['tp_vals'][-1] if fh['tp_vals'] else 0,
        'fh_csci_std': safe_std(fh['csci_vals']),
        'fh_topdown_max': int(safe_max(fh['td_vals'])),
        'fh_civ_count': fh['civ_count'],
        # Second half metrics
        'sh_nsi_max': safe_max(sh['nsi_vals']),
        'sh_nsi_mean': safe_mean(sh['nsi_vals']),
        'sh_nsi_active_rate': float(np.mean(sh['nsi_active'])) if sh['nsi_active'] else 0.0,
        'sh_continuity_mean': safe_mean(sh['continuity_vals']),
        'sh_history_depth_mean': safe_mean(sh['depth_vals']),
        'sh_turning_points': sh['tp_vals'][-1] if sh['tp_vals'] else 0,
        'sh_csci_std': safe_std(sh['csci_vals']),
        'sh_topdown_max': int(safe_max(sh['td_vals'])),
        'sh_civ_count': sh['civ_count'],
        # Full run metrics (for H1-H8 evaluation)
        'full_nsi_max': max(safe_max(fh['nsi_vals']), safe_max(sh['nsi_vals'])),
        'full_nsi_active_rate': float(np.mean(fh['nsi_active'] + sh['nsi_active'])) if (fh['nsi_active'] + sh['nsi_active']) else 0.0,
        'full_continuity_mean': safe_mean(fh['continuity_vals'] + sh['continuity_vals']),
        'full_history_depth_mean': safe_mean(fh['depth_vals'] + sh['depth_vals']),
        'full_turning_points': (fh['tp_vals'][-1] if fh['tp_vals'] else 0) + (sh['tp_vals'][-1] if sh['tp_vals'] else 0),
        'full_civ_count': fh['civ_count'] + sh['civ_count'],
        'full_csci_std': safe_std(fh['csci_vals'] + sh['csci_vals']),
        'full_topdown_max': max(int(safe_max(fh['td_vals'])), int(safe_max(sh['td_vals']))),
    }


def evaluate_hypotheses(results):
    """Evaluate H1-H8 across all seeds (same thresholds as P2)."""
    nsi_max_vals = [r['full_nsi_max'] for r in results]
    nsi_active_rates = [r['full_nsi_active_rate'] for r in results]
    continuity_means = [r['full_continuity_mean'] for r in results]
    history_depth_means = [r['full_history_depth_mean'] for r in results]
    turning_points_finals = [r['full_turning_points'] for r in results]
    civ_counts = [r['full_civ_count'] for r in results]
    csci_stds = [r['full_csci_std'] for r in results]
    topdown_max = [r['full_topdown_max'] for r in results]

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
        'H1_nsi_max': {'value': float(np.max(nsi_max_vals)), 'threshold': '>0.1', 'pass': h1},
        'H2_nsi_active_rate': {'value': float(np.mean(nsi_active_rates)), 'threshold': '>0.3 all', 'pass': h2},
        'H3_continuity_mean': {'value': float(np.mean(continuity_means)), 'threshold': '>0.1', 'pass': h3},
        'H4_combined': {
            'value': f'depth={float(np.mean(history_depth_means)):.4f}, tp={float(np.mean(turning_points_finals)):.1f}',
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


def evaluate_stability_hypotheses(results):
    """Evaluate H16-H20 long-run stability hypotheses.

    H16 (long-run NSI stability): NSI mean in second half >= NSI mean in first half
    H17 (long-run CIV stability): CIV count in second half >= 50% of CIV count in first half
    H18 (long-run CSCI stability): CSCI std in second half > 0 (does not collapse)
    H19 (long-run TopDown persistence): TopDown activates in both halves
    H20 (no metric collapse): All H1-H8 pass at step 2000
    """
    fh_nsi_means = [r['fh_nsi_mean'] for r in results]
    sh_nsi_means = [r['sh_nsi_mean'] for r in results]
    fh_civ_counts = [r['fh_civ_count'] for r in results]
    sh_civ_counts = [r['sh_civ_count'] for r in results]
    fh_csci_stds = [r['fh_csci_std'] for r in results]
    sh_csci_stds = [r['sh_csci_std'] for r in results]
    fh_topdown = [r['fh_topdown_max'] for r in results]
    sh_topdown = [r['sh_topdown_max'] for r in results]

    # H16: NSI mean second half >= NSI mean first half (avg across seeds)
    h16 = float(np.mean(sh_nsi_means)) >= float(np.mean(fh_nsi_means))

    # H17: CIV second half >= 50% of CIV first half (avg across seeds)
    fh_civ_mean = float(np.mean(fh_civ_counts))
    sh_civ_mean = float(np.mean(sh_civ_counts))
    h17 = sh_civ_mean >= 0.5 * fh_civ_mean if fh_civ_mean > 0 else False

    # H18: CSCI std does not collapse to 0 in second half
    h18 = float(np.mean(sh_csci_stds)) > 0.0

    # H19: TopDown activates in both halves
    fh_td_active = sum(1 for v in fh_topdown if v > 0)
    sh_td_active = sum(1 for v in sh_topdown if v > 0)
    h19 = fh_td_active >= 1 and sh_td_active >= 1

    # H20: All H1-H8 pass (from evaluate_hypotheses)
    h20_result = evaluate_hypotheses(results)
    h20 = h20_result['summary']['all_pass']

    return {
        'H16_nsi_stability': {
            'description': 'NSI mean in second half >= NSI mean in first half',
            'pass': h16,
            'fh_nsi_mean': float(np.mean(fh_nsi_means)),
            'sh_nsi_mean': float(np.mean(sh_nsi_means)),
        },
        'H17_civ_stability': {
            'description': 'CIV count in second half >= 50% of first half',
            'pass': h17,
            'fh_civ_mean': fh_civ_mean,
            'sh_civ_mean': sh_civ_mean,
            'ratio': sh_civ_mean / fh_civ_mean if fh_civ_mean > 0 else 0.0,
        },
        'H18_csci_stability': {
            'description': 'CSCI std does not collapse to 0 in second half',
            'pass': h18,
            'fh_csci_std_mean': float(np.mean(fh_csci_stds)),
            'sh_csci_std_mean': float(np.mean(sh_csci_stds)),
        },
        'H19_topdown_persistence': {
            'description': 'TopDown activates in both halves',
            'pass': h19,
            'fh_topdown_active_seeds': fh_td_active,
            'sh_topdown_active_seeds': sh_td_active,
        },
        'H20_no_collapse': {
            'description': 'All H1-H8 pass at step 2000',
            'pass': h20,
            'h1h8_result': h20_result['summary'],
        },
    }


# ─── Long-run stability configuration ───
# Note: Reduced from 3200 to 2000 steps to avoid OOM on 4GB machine.
P3_CONFIG = {
    'N0': 72,
    'steps': 2000,
    'seeds': [42, 142, 242],
}

SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2


def main():
    print("=" * 70)
    print("exp_110: Phase 4 P3 — Long-Run Stability Test")
    print(f"  Architecture: CSC+NSE (simplified, no AMC/ILP)")
    print(f"  N0={P3_CONFIG['N0']}, steps={P3_CONFIG['steps']}, seeds={P3_CONFIG['seeds']}")
    print(f"  {len(P3_CONFIG['seeds'])} seeds x {P3_CONFIG['steps']} steps = {len(P3_CONFIG['seeds'])} long runs")
    print("=" * 70)

    all_seed_results = []
    for seed in P3_CONFIG['seeds']:
        # Aggressive GC before each seed to maximize free memory
        gc.collect()

        result = run_single_seed(
            N0=P3_CONFIG['N0'], steps=P3_CONFIG['steps'], seed=seed,
            sample_interval=SAMPLE_INTERVAL,
            gbc_soft_nudge=GBC_SOFT_NUDGE,
            csc_config=P3_CSC_CONFIG,
        )
        all_seed_results.append(result)
        print(f"    seed={seed}: full_nsi_max={result['full_nsi_max']:.4f}, "
              f"full_civ={result['full_civ_count']}, "
              f"fh_civ={result['fh_civ_count']}, sh_civ={result['sh_civ_count']}, "
              f"fh_nsi_mean={result['fh_nsi_mean']:.4f}, sh_nsi_mean={result['sh_nsi_mean']:.4f}")

        # Aggressive cleanup after each seed
        gc.collect()

    # Evaluate H1-H8
    h1h8 = evaluate_hypotheses(all_seed_results)

    # Evaluate H16-H20 stability hypotheses
    stability = evaluate_stability_hypotheses(all_seed_results)

    # ─── Summary ───
    print("\n" + "=" * 70)
    print("H1-H8 RESULTS (at step 3200)")
    print("=" * 70)
    for h_name in ['H1_nsi_max', 'H2_nsi_active_rate', 'H3_continuity_mean',
                   'H4_combined', 'H5_civ_mean', 'H6_civ_min',
                   'H7_csci_std_mean', 'H8_topdown_active_seeds']:
        info = h1h8[h_name]
        status = "PASS" if info['pass'] else "FAIL"
        print(f"  {h_name}: {status} — value={info['value']}, threshold={info['threshold']}")

    summary = h1h8['summary']
    print(f"\n  >> H1-H8: {summary['n_pass']}/8 pass", end="")
    if summary['all_pass']:
        print(" — ALL PASS")
    else:
        print(f" — Failed: {', '.join(summary['failed'])}")

    print("\n" + "=" * 70)
    print("STABILITY HYPOTHESES (H16-H20)")
    print("=" * 70)
    for h_name, info in stability.items():
        status = "PASS" if info['pass'] else "FAIL"
        print(f"  {h_name}: {status} — {info['description']}")

    all_stability_pass = all(info['pass'] for info in stability.values())
    print(f"\n  >> H16-H20: {'ALL PASS' if all_stability_pass else 'SOME FAILED'}")

    # ─── Per-seed detail ───
    print("\n" + "=" * 70)
    print("PER-SEED DETAIL (first half vs second half)")
    print("=" * 70)
    for r in all_seed_results:
        print(f"\n  seed={r['seed']}:")
        print(f"    First half:  nsi_mean={r['fh_nsi_mean']:.4f}, civ={r['fh_civ_count']}, "
              f"csci_std={r['fh_csci_std']:.4f}, td={r['fh_topdown_max']}")
        print(f"    Second half: nsi_mean={r['sh_nsi_mean']:.4f}, civ={r['sh_civ_count']}, "
              f"csci_std={r['sh_csci_std']:.4f}, td={r['sh_topdown_max']}")
        print(f"    Full:        nsi_max={r['full_nsi_max']:.4f}, civ={r['full_civ_count']}, "
              f"sealed={r['sealed']}")

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output = {
        'experiment': 'exp_110_phase4_p3_long_run_stability',
        'timestamp': timestamp,
        'note': 'Phase 4 P3 — Long-run stability test at 2000 steps with CSC+NSE (reduced from 3200 due to OOM)',
        'architecture': 'CSC+NSE (AMC and ILP removed — redundant per Track A ablation)',
        'config': {
            'N0': P3_CONFIG['N0'],
            'steps': P3_CONFIG['steps'],
            'seeds': P3_CONFIG['seeds'],
            'sample_interval': SAMPLE_INTERVAL,
            'gbc_soft_nudge': GBC_SOFT_NUDGE,
            'csc': 'ON (P3_CSC_CONFIG)',
            'nse': 'ON (history_multi_signal, max_tp=25, odi=0.4, msi=0.3)',
            'amc': 'OFF (redundant per Track A)',
            'ilp': 'OFF (redundant per Track A)',
        },
        'results': {
            'per_seed': all_seed_results,
            'h1h8': h1h8,
            'stability_hypotheses': stability,
        },
    }

    output_dir = os.path.join(PROJECT_ROOT, 'experiments')
    output_path = os.path.join(output_dir, f'exp_110_results_{timestamp}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")

    return output_path


if __name__ == '__main__':
    main()
