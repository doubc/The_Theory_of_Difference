"""experiments/exp_96_narrative_self_emergence_validation.py

Phase 4 Experiment 6: NarrativeSelfEmergence Validation

Purpose: Validate that the NarrativeSelfEmergence (NSE) component produces
meaningful Narrative Self Index (NSI) signals when integrated into the full
evolver loop, building on the stable exp_95 base configuration.

Background:
- exp_95: CSC + GBC (random direction init) → H1-H5 ALL PASS, CIV mean=6.5
- NSE component (commit 4537e8a): 29 unit tests pass, integrated into evolver
  but never validated in a full experiment run.
- NSE has 4 subcomponents: TemporalContinuityTracker, InstitutionalNarrativeStabilizer,
  SelfHistoryAccumulator, and NSI (Narrative Self Index).
- NSI formula: 0.4*continuity + 0.3*stability + 0.3*history_depth, gated by ODI >= 0.6

Config: Same as exp_95 (N0=72, steps=1600, 8 seeds)
    CSC: ON (same config as exp_95)
    GBC: ON (random direction init, soft nudge=0.2)
    ILP: OFF
    AMC: OFF
    NSE: ON (default config)

Hypotheses:
  H1: NSI max > 0.1 (NSE produces non-trivial signal)
  H2: NSI active rate > 0.3 (NSI activates in >30% of sampled steps)
  H3: Temporal continuity score mean > 0.1 (narrative themes persist over time)
  H4: Self history depth > 0.05 (at least some turning points detected)
  H5: CIV mean in [3, 15] (exp_95 baseline stability preserved with NSE)
  H6: min CIV >= 3 (no seed collapses)
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
    NarrativeNode, CausalChain,
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


EXP95_CSC_CONFIG = {
    'topdown_max_constraint_strength': 0.10,
    'topdown_min_constraint_strength': 0.01,
    'topdown_response_delay': 20,
    'topdown_decay_rate': 0.98,
    'topdown_propagation_depth': 2,
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


class MomentumNarrativeOperatorV3(NarrativeRecursionOperator):
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

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


def run_single_seed(N0=72, steps=1600, seed=142, sample_interval=10,
                    gbc_soft_nudge=0.2, use_csc=True, csc_config=None,
                    use_nse=True):
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
    narrative = MomentumNarrativeOperatorV3(
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
        nse = NarrativeSelfEmergence(config=DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)

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
    )

    csc_label = 'ON' if use_csc else 'OFF'
    nse_label = 'ON' if use_nse else 'OFF'
    print(f"  [seed={seed}] Running (CSC={csc_label}, NSE={nse_label})...", flush=True)
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

    csc_steps = []
    csc_csci_values = []
    csc_narrative_coh_values = []
    csc_topdown_active_count = 0
    csc_emergence_count_total = 0

    for sr in step_results:
        csc_info = sr.get('cross_scale_coupling')
        if csc_info:
            csc_steps.append(sr.get('step', 0))
            csc_csci_values.append(csc_info.get('csci', 0.0))
            csc_narrative_coh_values.append(csc_info.get('narrative_bridge_coherence', 0.0))
            if csc_info.get('csci_coherent', False):
                csc_topdown_active_count += 1
            csc_emergence_count_total += csc_info.get('emergence_count', 0)

    csc_summary = {
        'n_steps_with_csc': len(csc_steps),
        'csci_mean': float(np.mean(csc_csci_values)) if csc_csci_values else 0.0,
        'csci_std': float(np.std(csc_csci_values)) if len(csc_csci_values) > 1 else 0.0,
        'csci_min': float(np.min(csc_csci_values)) if csc_csci_values else 0.0,
        'csci_max': float(np.max(csc_csci_values)) if csc_csci_values else 0.0,
        'csci_coherent_rate': csc_topdown_active_count / len(csc_steps) if csc_steps else 0.0,
        'narrative_coherence_mean': float(np.mean(csc_narrative_coh_values)) if csc_narrative_coh_values else 0.0,
        'emergence_events_total': csc_emergence_count_total,
    }

    # ── NSE metrics ──
    nse_summary = result.get('phase4_summary', {}).get('nse_summary')
    nse_nsi_trend = result.get('phase4_summary', {}).get('nse_nsi_trend')

    nsi_values = []
    nsi_active_count = 0
    continuity_values = []
    stability_values = []
    history_depth_values = []
    turning_point_counts = []

    for sr in step_results:
        nse_info = sr.get('narrative_self_emergence')
        if nse_info:
            nsi_val = nse_info.get('nsi', 0.0)
            nsi_values.append(nsi_val)
            if nse_info.get('nsi_active', False):
                nsi_active_count += 1
            continuity_values.append(nse_info.get('continuity_score', 0.0))
            stability_values.append(nse_info.get('stability_score', 0.0))
            history_depth_values.append(nse_info.get('self_history_depth', 0.0))
            turning_point_counts.append(nse_info.get('n_turning_points', 0))

    n_total_sampled = len(step_results)
    nse_metrics = {
        'nsi_values': nsi_values,
        'nsi_max': float(np.max(nsi_values)) if nsi_values else 0.0,
        'nsi_mean': float(np.mean(nsi_values)) if nsi_values else 0.0,
        'nsi_active_count': nsi_active_count,
        'nsi_active_rate': nsi_active_count / n_total_sampled if n_total_sampled > 0 else 0.0,
        'continuity_mean': float(np.mean(continuity_values)) if continuity_values else 0.0,
        'stability_mean': float(np.mean(stability_values)) if stability_values else 0.0,
        'history_depth_mean': float(np.mean(history_depth_values)) if history_depth_values else 0.0,
        'history_depth_max': float(np.max(history_depth_values)) if history_depth_values else 0.0,
        'turning_points_max': int(np.max(turning_point_counts)) if turning_point_counts else 0,
        'turning_points_final': int(turning_point_counts[-1]) if turning_point_counts else 0,
        'nse_summary_from_evolver': nse_summary,
        'nse_nsi_trend': nse_nsi_trend,
    }

    connector_stats = narrative.get_momentum_stats()

    return {
        'seed': seed,
        'steps': steps,
        'N0': N0,
        'narrative_active_steps': active_count,
        'narrative_total_sampled': len(step_results),
        'civilization_steps': civ_count,
        'level_counts': {
            'MINI': mini_count,
            'INSTITUTIONAL': inst_count,
            'CIVILIZATION': civ_count,
        },
        'odi_max': odi_max,
        'odi_mean': odi_mean,
        'msi_max': msi_max,
        'msi_mean': msi_mean,
        'six_threshold_pass_rate': six_pass_rate,
        'momentum_cache': connector_stats,
        'final_momentum_bonus': 0.3,
        'gbc': {
            'coherence_mean': gbc_coherence_mean,
            'coherence_std': float(np.std(gbc_coherences)) if gbc_coherences else 0.0,
            'balance_mean': float(np.mean([c.get('balance', 0.0) for c in gbc_checks])) if gbc_checks else 0.0,
            'pass_rate': gbc_pass_rate,
            'n_checks': len(gbc_checks),
        },
        'csc': csc_summary,
        'nse': nse_metrics,
        'elapsed_s': elapsed,
    }


def main():
    seeds = [42, 142, 242, 342, 442, 542, 642, 742]
    N0 = 72
    steps = 1600

    print("=" * 70)
    print("exp_96: NarrativeSelfEmergence Validation")
    print("=" * 70)
    print(f"Seeds: {seeds}")
    print(f"N0={N0}, steps={steps}")
    print(f"CSC: ON, NSE: ON, ILP: OFF, AMC: OFF")
    print(f"GBC soft nudge: 0.2")
    print("=" * 70)

    all_results = []
    for seed in seeds:
        result = run_single_seed(
            N0=N0, steps=steps, seed=seed,
            csc_config=EXP95_CSC_CONFIG,
            use_nse=True,
        )
        all_results.append(result)

    civ_values = [r['civilization_steps'] for r in all_results]
    gbc_coh = [r['gbc']['coherence_mean'] for r in all_results]
    gbc_pr = [r['gbc']['pass_rate'] for r in all_results]
    gbc_n = [r['gbc']['n_checks'] for r in all_results]
    csc_csci = [r['csc']['csci_mean'] for r in all_results]
    csc_narr = [r['csc']['narrative_coherence_mean'] for r in all_results]
    nsi_max = [r['nse']['nsi_max'] for r in all_results]
    nsi_mean = [r['nse']['nsi_mean'] for r in all_results]
    nsi_active_rate = [r['nse']['nsi_active_rate'] for r in all_results]
    continuity_mean = [r['nse']['continuity_mean'] for r in all_results]
    history_depth_max = [r['nse']['history_depth_max'] for r in all_results]
    turning_points_final = [r['nse']['turning_points_final'] for r in all_results]

    print("\n" + "=" * 70)
    print("exp_96 Results Summary")
    print("=" * 70)
    print(f"\nPer-seed CIV: {civ_values}")
    print(f"CIV mean: {np.mean(civ_values):.2f}, std: {np.std(civ_values):.2f}, min: {min(civ_values)}, max: {max(civ_values)}")
    print(f"\nGBC n_checks per seed: {gbc_n}")
    print(f"GBC coherence mean: {np.mean(gbc_coh):.4f}")
    print(f"GBC pass_rate mean: {np.mean(gbc_pr):.4f}")
    print(f"\nCSC CSCI mean: {np.mean(csc_csci):.4f} (std: {np.std(csc_csci):.4f})")
    print(f"CSC narrative coherence mean: {np.mean(csc_narr):.4f}")
    print(f"\n--- NSE Metrics ---")
    print(f"NSI max per seed: {[round(v, 4) for v in nsi_max]}")
    print(f"NSI max mean: {np.mean(nsi_max):.4f}")
    print(f"NSI mean per seed: {[round(v, 4) for v in nsi_mean]}")
    print(f"NSI active rate per seed: {[round(v, 4) for v in nsi_active_rate]}")
    print(f"Continuity mean per seed: {[round(v, 4) for v in continuity_mean]}")
    print(f"History depth max per seed: {[round(v, 4) for v in history_depth_max]}")
    print(f"Turning points final per seed: {turning_points_final}")

    print("\n--- Hypothesis Tests ---")
    h1_pass = np.mean(nsi_max) > 0.1
    h2_pass = np.mean(nsi_active_rate) > 0.3
    h3_pass = np.mean(continuity_mean) > 0.1
    h4_pass = np.mean(history_depth_max) > 0.05
    h5_pass = 3 <= np.mean(civ_values) <= 15
    h6_pass = min(civ_values) >= 3

    print(f"H1 (NSI max > 0.1):              {'PASS' if h1_pass else 'FAIL'} ({np.mean(nsi_max):.4f})")
    print(f"H2 (NSI active rate > 0.3):       {'PASS' if h2_pass else 'FAIL'} ({np.mean(nsi_active_rate):.4f})")
    print(f"H3 (Continuity mean > 0.1):       {'PASS' if h3_pass else 'FAIL'} ({np.mean(continuity_mean):.4f})")
    print(f"H4 (History depth max > 0.05):   {'PASS' if h4_pass else 'FAIL'} ({np.mean(history_depth_max):.4f})")
    print(f"H5 (CIV mean in [3,15]):          {'PASS' if h5_pass else 'FAIL'} ({np.mean(civ_values):.2f})")
    print(f"H6 (min CIV >= 3):                {'PASS' if h6_pass else 'FAIL'} (min={min(civ_values)})")

    all_pass = all([h1_pass, h2_pass, h3_pass, h4_pass, h5_pass, h6_pass])
    print(f"\n{'=' * 70}")
    print(f"OVERALL: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    print(f"{'=' * 70}")

    print("\n--- vs exp_95 ---")
    print(f"CIV mean:    {np.mean(civ_values):.2f} (exp_95: 6.5)")
    print(f"CIV min:     {min(civ_values)} (exp_95: 4)")
    print(f"GBC coh:     {np.mean(gbc_coh):.4f} (exp_95: 0.537)")
    print(f"CSC CSCI:    {np.mean(csc_csci):.4f} (exp_95: 0.669)")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(
        PROJECT_ROOT, 'experiments', f'exp_96_results_{timestamp}.json'
    )
    output = {
        'experiment': 'exp_96_narrative_self_emergence_validation',
        'timestamp': timestamp,
        'seeds': seeds,
        'n_seeds': len(seeds),
        'config': {
            'momentum_bonus_init': 0.3,
            'momentum_decay': 0.95,
            'gbc_soft_nudge': 0.2,
            'N0': N0,
            'steps': steps,
            'csc_active': True,
            'csc_config': EXP95_CSC_CONFIG,
            'nse_active': True,
            'nse_config': DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG,
        },
        'per_seed': all_results,
        'summary': {
            'civ_mean': float(np.mean(civ_values)),
            'civ_std': float(np.std(civ_values)),
            'civ_min': int(min(civ_values)),
            'civ_max': int(max(civ_values)),
            'gbc_n_checks_mean': float(np.mean(gbc_n)),
            'gbc_coh_mean': float(np.mean(gbc_coh)),
            'gbc_pr_mean': float(np.mean(gbc_pr)),
            'csc_csci_mean': float(np.mean(csc_csci)),
            'csc_narr_mean': float(np.mean(csc_narr)),
            'nsi_max_mean': float(np.mean(nsi_max)),
            'nsi_mean_mean': float(np.mean(nsi_mean)),
            'nsi_active_rate_mean': float(np.mean(nsi_active_rate)),
            'continuity_mean_mean': float(np.mean(continuity_mean)),
            'history_depth_max_mean': float(np.mean(history_depth_max)),
            'h1_pass': bool(h1_pass),
            'h2_pass': bool(h2_pass),
            'h3_pass': bool(h3_pass),
            'h4_pass': bool(h4_pass),
            'h5_pass': bool(h5_pass),
            'h6_pass': bool(h6_pass),
            'all_pass': bool(all_pass),
        },
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
