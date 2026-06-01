"""experiments/exp_109_track_b_scaling.py

Phase 4 Experiment 19: Track B — Scaling Test

Purpose: Test whether H1-H8 hypotheses hold across different system sizes (N0),
using the simplified CSC+NSE architecture identified by Track A ablation study.

Track A ablation findings:
  - CSC is the keystone component (removing it causes H7/H8 to fail)
  - NSE is the diagnostic/measurement layer (removing it causes H1-H4 to fail)
  - AMC and ILP are redundant (removing either has zero effect)

Therefore, Track B uses the simplified CSC+NSE stack (no AMC, no ILP).

Scaling configurations:
  B1 (small):  N0=48, steps=1600, seeds=[42, 142, 742]
  B0 (baseline): N0=72, steps=1600, seeds=[42, 142, 742]  — replicate exp_107 subset
  B2 (large):  N0=96, steps=1600, seeds=[42, 142, 742]

New hypotheses:
  H13 (scale robustness): H1-H8 all pass at N0=48 and N0=96
  H14 (NSI scales with N0): NSI mean increases with N0 (larger systems = richer narrative self)
  H15 (CIV scales sub-linearly): CIV count scales sub-linearly with N0 (diminishing returns)

Theory background (from phase4_p2_track_b_theory_note.md):
  - Small system (N0=48): Common contrast pressure is lower, internal differences dominate
  - Medium system (N0=72): Baseline, common contrast and internal differences balanced
  - Large system (N0=96): Common contrast pressure increases, clustering more stable
  - Clustering reorganizes differences rather than eliminating them
  - CSC corresponds to "cross-scale organization of differences"
  - NSE corresponds to "narrative manifestation of differences"
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


# ─── CSC config: same as exp_107/exp_108 (proven stable) ───
TRACK_B_CSC_CONFIG = {
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
    """Same limiter as exp_107 P1-F (proven stable across P0+P1)."""

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
    """V4 P1-F: CIVRateLimiterV2P1F (same as exp_107/exp_108)."""

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

    # CSC: ON (simplified stack — CSC is the keystone)
    csc_cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
    if csc_config:
        csc_cfg.update(csc_config)
    csc = CrossScaleCoupling(config=csc_cfg)

    # NSE: ON (simplified stack — NSE is the diagnostic layer)
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


def evaluate_hypotheses(results):
    """Evaluate H1-H8 across all seeds. H6 threshold >=2 (P1-F standard)."""
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


def evaluate_scaling_hypotheses(config_results):
    """Evaluate H13-H15 scaling hypotheses across N0 configurations.

    config_results: dict mapping config_name -> evaluate_hypotheses output
    """
    b1 = config_results.get('B1_small', {}).get('summary', {})
    b0 = config_results.get('B0_baseline', {}).get('summary', {})
    b2 = config_results.get('B2_large', {}).get('summary', {})

    # Extract per-config metric means for scaling analysis
    b1_nsi = config_results.get('B1_small', {}).get('H2_nsi_active_rate', {}).get('value', 0)
    b0_nsi = config_results.get('B0_baseline', {}).get('H2_nsi_active_rate', {}).get('value', 0)
    b2_nsi = config_results.get('B2_large', {}).get('H2_nsi_active_rate', {}).get('value', 0)

    b1_civ = config_results.get('B1_small', {}).get('H5_civ_mean', {}).get('value', 0)
    b0_civ = config_results.get('B0_baseline', {}).get('H5_civ_mean', {}).get('value', 0)
    b2_civ = config_results.get('B2_large', {}).get('H5_civ_mean', {}).get('value', 0)

    # H13: H1-H8 all pass at N0=48 and N0=96
    h13 = b1.get('all_pass', False) and b2.get('all_pass', False)

    # H14: NSI mean increases with N0 (larger systems = richer narrative self)
    # Check: N0=48 < N0=72 < N0=96 in NSI active rate
    h14 = b1_nsi < b0_nsi < b2_nsi

    # H15: CIV scales sub-linearly with N0
    # If linear: B1(48) : B2(96) = 1:2. Sub-linear means ratio < 2x
    if b1_civ > 0:
        ratio_b2_b1 = b2_civ / b1_civ
        ratio_n0 = 96 / 48  # = 2.0
        h15 = ratio_b2_b1 < ratio_n0
    else:
        h15 = False

    return {
        'H13_scale_robustness': {
            'description': 'H1-H8 all pass at N0=48 and N0=96',
            'pass': h13,
            'B1_pass': b1.get('all_pass', False),
            'B1_n_pass': b1.get('n_pass', 0),
            'B1_failed': b1.get('failed', []),
            'B2_pass': b2.get('all_pass', False),
            'B2_n_pass': b2.get('n_pass', 0),
            'B2_failed': b2.get('failed', []),
        },
        'H14_nsi_scales_with_N0': {
            'description': 'NSI mean increases with N0 (48 < 72 < 96)',
            'pass': h14,
            'B1_nsi_active_rate': b1_nsi,
            'B0_nsi_active_rate': b0_nsi,
            'B2_nsi_active_rate': b2_nsi,
        },
        'H15_civ_sublinear_scaling': {
            'description': 'CIV count scales sub-linearly with N0',
            'pass': h15,
            'B1_civ_mean': b1_civ,
            'B0_civ_mean': b0_civ,
            'B2_civ_mean': b2_civ,
            'ratio_B2_B1': b2_civ / b1_civ if b1_civ > 0 else float('inf'),
            'linear_ratio_N0': 2.0,
        },
    }


# ─── Scaling configurations ───
SCALING_CONFIGS = {
    'B1_small':  {'N0': 48, 'steps': 1600, 'seeds': [42, 142, 742]},
    'B0_baseline': {'N0': 72, 'steps': 1600, 'seeds': [42, 142, 742]},
    'B2_large':  {'N0': 96, 'steps': 1600, 'seeds': [42, 142, 742]},
}

SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2


def main():
    print("=" * 70)
    print("exp_109: Phase 4 P2 Track B — Scaling Test")
    print(f"  Architecture: CSC+NSE (simplified, no AMC/ILP)")
    print(f"  3 configs x 3 seeds = 9 runs")
    print("=" * 70)

    all_config_results = {}
    config_hypotheses = {}

    for config_name, cfg in SCALING_CONFIGS.items():
        N0 = cfg['N0']
        steps = cfg['steps']
        seeds = cfg['seeds']

        print(f"\n{'─' * 60}")
        print(f"Config {config_name}: N0={N0}, steps={steps}, seeds={seeds}")
        print(f"{'─' * 60}")

        all_seed_results = []
        for seed in seeds:
            result = run_single_seed(
                N0=N0, steps=steps, seed=seed,
                sample_interval=SAMPLE_INTERVAL,
                gbc_soft_nudge=GBC_SOFT_NUDGE,
                csc_config=TRACK_B_CSC_CONFIG,
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

        hypotheses = evaluate_hypotheses(all_seed_results)
        config_hypotheses[config_name] = hypotheses
        all_config_results[config_name] = {
            'per_seed': all_seed_results,
            'hypotheses': hypotheses,
        }

        summary = hypotheses['summary']
        print(f"\n  >> {config_name}: {summary['n_pass']}/8 pass", end="")
        if summary['all_pass']:
            print(" — ALL PASS")
        else:
            print(f" — Failed: {', '.join(summary['failed'])}")

    # Evaluate scaling hypotheses
    scaling_hyp = evaluate_scaling_hypotheses(config_hypotheses)

    # ─── Summary table ───
    print("\n" + "=" * 70)
    print("SCALING SUMMARY")
    print("=" * 70)
    print(f"  {'Config':<15} | {'N0':>4} | {'Pass':>6} | {'Failed':<20} | {'CIV':>5} | {'NSI':>8}")
    print(f"  {'─' * 15} | {'─' * 4} | {'─' * 6} | {'─' * 20} | {'─' * 5} | {'─' * 8}")
    for config_name, cfg in SCALING_CONFIGS.items():
        h = config_hypotheses[config_name]['summary']
        failed_str = ', '.join(h['failed']) if h['failed'] else '—'
        civ_mean = config_hypotheses[config_name]['H5_civ_mean']['value']
        nsi_mean = config_hypotheses[config_name]['H2_nsi_active_rate']['value']
        print(f"  {config_name:<15} | {cfg['N0']:>4} | "
              f"{h['n_pass']:>3}/8 | {failed_str:<20} | "
              f"{civ_mean:>5.1f} | {nsi_mean:>8.4f}")

    print("\n" + "─" * 70)
    print("SCALING HYPOTHESES (H13-H15)")
    print("─" * 70)
    for h_name, h_info in scaling_hyp.items():
        status = "PASS" if h_info['pass'] else "FAIL"
        print(f"  {h_name}: {status} — {h_info['description']}")

    # ─── Per-seed detail table ───
    print("\n" + "─" * 70)
    print("PER-SEED DETAIL")
    print("─" * 70)
    for config_name in SCALING_CONFIGS:
        print(f"\n  {config_name}:")
        for r in all_config_results[config_name]['per_seed']:
            print(f"    seed={r['seed']:>3}: civ={r['civ_count']:>3}, "
                  f"nsi_max={r['nse_nsi_max']:.4f}, "
                  f"nsi_mean={r['nse_nsi_mean']:.4f}, "
                  f"cont={r['nse_continuity_mean']:.4f}, "
                  f"depth={r['nse_history_depth_mean']:.4f}, "
                  f"tp={r['nse_turning_points_final']:>3}, "
                  f"csci_std={r['csc_csci_std']:.4f}, "
                  f"td={r['topdown_max_active']:>3}, "
                  f"sealed={str(r['sealed']):>5}")

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output = {
        'experiment': 'exp_109_track_b_scaling',
        'timestamp': timestamp,
        'note': 'Phase 4 P2 Track B — Scaling test with simplified CSC+NSE stack',
        'architecture': 'CSC+NSE (AMC and ILP removed — redundant per Track A ablation)',
        'config': {
            'scaling_configs': {k: {'N0': v['N0'], 'steps': v['steps'],
                                    'seeds': v['seeds']}
                                for k, v in SCALING_CONFIGS.items()},
            'sample_interval': SAMPLE_INTERVAL,
            'gbc_soft_nudge': GBC_SOFT_NUDGE,
            'csc': 'ON (Track_B_CSC_CONFIG)',
            'nse': 'ON (history_multi_signal, max_tp=25, odi=0.4, msi=0.3)',
            'amc': 'OFF (redundant per Track A)',
            'ilp': 'OFF (redundant per Track A)',
        },
        'results': {
            name: {
                'per_seed': all_config_results[name]['per_seed'],
                'hypotheses': config_hypotheses[name],
            }
            for name in SCALING_CONFIGS
        },
        'scaling_hypotheses': scaling_hyp,
    }

    output_dir = os.path.join(PROJECT_ROOT, 'experiments')
    output_path = os.path.join(output_dir, f'exp_109_results_{timestamp}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")

    return output_path


if __name__ == '__main__':
    main()
