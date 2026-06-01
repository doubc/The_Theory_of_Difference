"""experiments/exp_108b_ablation_continued.py

Phase 4 P2 Track A — Continuation after exp_108 was killed.
Runs only A3 (no CSC) and A4 (no NSE) — the two configs not yet completed.

Uses same setup as exp_108.
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


EXP_CSC_CONFIG = {
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
            momentum_decay=momentum_decay, momentum_bonus=momentum_bonus,
        )
        self.actionizer = NarrativeActionizer(bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(consistency_threshold=verifier_consistency_threshold)
        self.narrative_decay_rate = narrative_decay_rate
        self._records = []
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F(
            window_size=50, max_civ_rate=0.12, cooldown_steps=12, min_civ_guarantee=3
        )

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    use_csc, use_nse, use_amc, use_ilp, csc_config=None):
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
        config={'default_horizon': 5, 'learning_rate': 0.01})
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1, 'max_branches': 4})
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
            'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
        nse_cfg['history_max_turning_points'] = 25
        nse = NarrativeSelfEmergence(config=nse_cfg)

    amc = None
    if use_amc:
        amc = AdaptiveMomentumController(config=dict(DEFAULT_ADAPTIVE_MOMENTUM_CONFIG))

    ilp = None
    if use_ilp:
        ilp = InstitutionalLayerProtector(config=dict(DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG))

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
                level = narr_history[-1].get('narrative_level', 'MINI_NARRATIVE') if narr_history else 'MINI'
            except Exception:
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
        'seed': seed, 'elapsed': elapsed, 'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'odi_max': odi_max,
        'gbc_coherence_mean': gbc_coherence_mean, 'gbc_pass_rate': gbc_pass_rate,
        'csc_csci_std': csc_csci_std, 'topdown_max_active': topdown_max_active,
        'nse_nsi_max': nse_nsi_max, 'nse_nsi_active_rate': nse_nsi_active_rate,
        'nse_continuity_mean': nse_continuity_mean,
        'nse_history_depth_mean': nse_history_depth_mean,
        'nse_turning_points_final': nse_turning_points_final,
        'civ_count': civ_count,
        'civ_limiter_total_seen': civ_limiter_summary['total_civ_seen'],
    }


def evaluate_hypotheses(results):
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
    h4 = float(np.mean(history_depth_means)) > 0.05 or float(np.mean(turning_points_finals)) > 0.0
    h5 = 3.0 <= civ_mean <= 15.0
    h6 = civ_min >= 2
    h7 = float(np.mean(csci_stds)) > 0.005
    h8 = sum(1 for v in topdown_max if v > 0) >= 2

    return {
        'H1': h1, 'H2': h2, 'H3': h3, 'H4': h4,
        'H5': h5, 'H6': h6, 'H7': h7, 'H8': h8,
        'summary': {
            'all_pass': all([h1, h2, h3, h4, h5, h6, h7, h8]),
            'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'failed': [n for n, v in [('H1', h1), ('H2', h2), ('H3', h3), ('H4', h4),
                                       ('H5', h5), ('H6', h6), ('H7', h7), ('H8', h8)] if not v],
            'civ_mean': civ_mean, 'civ_min': civ_min,
        }
    }


# Only run A3 and A4 (A0-A2 already completed in exp_108 partial run)
CONFIGS = {
    'A3_no_csc': {'use_amc': True,  'use_ilp': True,  'use_csc': False, 'use_nse': True},
    'A4_no_nse': {'use_amc': True,  'use_ilp': True,  'use_csc': True,  'use_nse': False},
}

SEEDS = [42, 142, 242, 742]
N0 = 72
STEPS = 1600
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2

print("exp_108b: Ablation Continuation (A3 no CSC, A4 no NSE)")
print(f"  N0={N0}, steps={STEPS}, seeds={SEEDS}")
print()

all_results = {}
for config_name, cfg in CONFIGS.items():
    print(f"{'─' * 60}")
    print(f"Config {config_name}: AMC={cfg['use_amc']}, ILP={cfg['use_ilp']}, "
          f"CSC={cfg['use_csc']}, NSE={cfg['use_nse']}")
    print(f"{'─' * 60}")

    seed_results = []
    for seed in SEEDS:
        r = run_single_seed(
            N0=N0, steps=STEPS, seed=seed, sample_interval=SAMPLE_INTERVAL,
            gbc_soft_nudge=GBC_SOFT_NUDGE,
            use_csc=cfg['use_csc'], use_nse=cfg['use_nse'],
            use_amc=cfg['use_amc'], use_ilp=cfg['use_ilp'],
            csc_config=EXP_CSC_CONFIG if cfg['use_csc'] else None,
        )
        seed_results.append(r)
        print(f"    seed={seed}: NSI={r['nse_nsi_max']:.4f}, cont={r['nse_continuity_mean']:.4f}, "
              f"depth={r['nse_history_depth_mean']:.4f}, tp={r['nse_turning_points_final']}, "
              f"CSCI={r['csc_csci_std']:.4f}, td={r['topdown_max_active']}, civ={r['civ_count']}")

    hyp = evaluate_hypotheses(seed_results)
    all_results[config_name] = {'per_seed': seed_results, 'hypotheses': hyp}
    s = hyp['summary']
    print(f"\n  >> {config_name}: {s['n_pass']}/8 pass", end="")
    print(" — ALL PASS" if s['all_pass'] else f" — Failed: {', '.join(s['failed'])}")
    print()

# Save results
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output = {
    'experiment': 'exp_108b_ablation_continuation',
    'timestamp': timestamp,
    'note': 'A0-A2 results from exp_108 partial run. This file contains A3 and A4 only.',
    'results': {
        name: {
            'per_seed': all_results[name]['per_seed'],
            'hypotheses': {
                k: v for k, v in all_results[name]['hypotheses'].items()
                if k != 'summary'
            },
            'summary': all_results[name]['hypotheses']['summary'],
        }
        for name in CONFIGS
    },
    # Include known A0-A2 results from exp_108 partial run
    'from_exp_108_partial': {
        'A0_baseline': {'n_pass': 8, 'all_pass': True, 'failed': [],
                        'note': '8/8 ALL PASS — baseline replication confirmed'},
        'A1_no_amc': {'n_pass': 8, 'all_pass': True, 'failed': [],
                      'note': '8/8 ALL PASS — AMC removal has NO effect on H1-H8'},
        'A2_no_ilp': {'n_pass': 8, 'all_pass': True, 'failed': [],
                      'note': '8/8 ALL PASS — ILP removal has NO effect on H1-H8'},
    },
}

output_dir = os.path.join(PROJECT_ROOT, 'experiments')
output_path = os.path.join(output_dir, f'exp_108b_results_{timestamp}.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"Results saved to: {output_path}")
