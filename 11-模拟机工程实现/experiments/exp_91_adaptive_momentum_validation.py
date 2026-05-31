"""experiments/exp_91_adaptive_momentum_validation.py

Phase 4 Experiment 1: Adaptive Momentum Control Validation

Purpose: Verify that AdaptiveMomentumController + InstitutionalLayerProtector
can fix the H4 failure from exp_90 (3/8 seeds at CIV=2).

Changes vs exp_90:
- Uses AdaptiveMomentumConnector (core model) instead of ad-hoc NarrativeMomentumConnectorV2
- Activates AdaptiveMomentumController (AMC) with default config
- Activates InstitutionalLayerProtector (ILP) with default config
- AMC momentum_bonus is fed back to the narrative connector each step
- ILP should_consume gates encapsulation

Config: Same as exp_90 (N0=72, steps=1600, 8 seeds)
    momentum_bonus starts at 0.3 (AMC adapts in [0.1, 0.5])
    momentum_decay=0.95
    coherence_threshold=0.5
    gbc_soft_nudge=0.2

Hypotheses:
  H1: Mean CIV >= 5.0 (same as exp_90)
  H2: GBC coherence mean >= 0.55 (same as exp_90)
  H3: GBC pass_rate >= 0.3 (same as exp_90)
  H4: All seeds CIV >= 3 (FIX target -- exp_90 had 3 seeds at CIV=2)
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Any

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
from engine.adaptive_momentum_controller import (
    AdaptiveMomentumController, DEFAULT_ADAPTIVE_MOMENTUM_CONFIG
)
from engine.institutional_layer_protector import (
    InstitutionalLayerProtector, DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG
)


class MomentumNarrativeOperatorV3(NarrativeRecursionOperator):
    """V3: Uses AdaptiveMomentumConnector from core model (supports set_momentum_bonus)."""
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
                    gbc_soft_nudge=0.2, use_amc=True, use_ilp=True):
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

    # Phase 4 P0 components
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
        adaptive_momentum_controller=amc,
        institutional_layer_protector=ilp,
    )

    amc_label = 'ON' if use_amc else 'OFF'
    ilp_label = 'ON' if use_ilp else 'OFF'
    print(f"  [seed={seed}] Running (AMC={amc_label}, ILP={ilp_label})...", flush=True)
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"  [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    active_count = 0
    civ_count = 0
    level_counts = {'MINI': 0, 'INSTITUTIONAL': 0, 'CIVILIZATION': 0}
    odi_values = []
    msi_values = []

    # AMC/ILP per-step tracking
    amc_history = []
    ilp_history = []

    for entry in step_results:
        odi_val = entry.get('odi', {}).get('value', 0.0) if isinstance(entry.get('odi'), dict) else 0.0
        msi_val = entry.get('minimal_self', {}).get('msi', 0.0) if isinstance(entry.get('minimal_self'), dict) else 0.0
        odi_values.append(odi_val)
        msi_values.append(msi_val)

        narrative_data = entry.get('narrative_recursion', {})
        if narrative_data.get('bias_correction_applied', False):
            active_count += 1
        level = narrative_data.get('narrative_level', '')
        if level == 'CIVILIZATION' or narrative_data.get('is_civilization', False):
            civ_count += 1
        level_snap = narrative_data.get('level_distribution_snapshot', {})
        for k in level_counts:
            level_counts[k] += level_snap.get(k, 0)

        # Track AMC
        amc_data = entry.get('adaptive_momentum')
        if amc_data:
            amc_history.append(amc_data)

        # Track ILP
        ilp_data = entry.get('institutional_protector')
        if ilp_data:
            ilp_history.append(ilp_data)

    odi_arr = np.array(odi_values) if odi_values else np.array([0.0])
    msi_arr = np.array(msi_values) if msi_values else np.array([0.0])

    momentum_stats = narrative.get_momentum_stats()
    final_momentum_bonus = narrative.get_current_momentum_bonus()

    gbc_history = gbc.get_history(limit=1000)
    gbc_coherences = [r.coherence for r in gbc_history]
    gbc_balances = [r.balance for r in gbc_history]
    gbc_passes = [r.passed for r in gbc_history]

    mechanism_coherences: Dict[str, List[float]] = {}
    for r in gbc_history:
        for mech, coh in r.coherence_by_mechanism.items():
            if mech not in mechanism_coherences:
                mechanism_coherences[mech] = []
            mechanism_coherences[mech].append(coh)

    mechanism_mean_coh = {k: round(float(np.mean(v)), 4) for k, v in mechanism_coherences.items()}

    # AMC summary
    amc_summary = None
    if amc is not None:
        amc_summary_raw = amc.get_history()
        amc_summary = {
            'current_momentum_bonus': round(amc_summary_raw['current_momentum_bonus'], 4),
            'final_entropy': round(amc_summary_raw['entropy'], 4),
            'final_institutional_count': amc_summary_raw['institutional_count'],
            'final_institutional_rate': round(amc_summary_raw['institutional_rate'], 4),
            'mode': amc_summary_raw['mode'],
            'n_adjustments': amc_summary_raw['n_adjustments'],
            'mean_adjustment': round(amc_summary_raw['mean_adjustment'], 6),
        }

    # ILP summary
    ilp_summary = None
    if ilp is not None:
        ilp_summary_raw = ilp.get_history()
        ilp_summary = {
            'final_institutional_count': ilp_summary_raw['institutional_count'],
            'final_floor': round(ilp_summary_raw['institutional_floor'], 2),
            'n_protection_events': ilp_summary_raw['n_protection_events'],
            'n_transitions_allowed': ilp_summary_raw['n_transitions_allowed'],
            'n_transitions_blocked': ilp_summary_raw['n_transitions_blocked'],
            'mode': ilp_summary_raw['mode'],
        }

    return {
        'seed': seed,
        'steps': steps,
        'N0': N0,
        'narrative_active_steps': active_count,
        'narrative_total_sampled': len(step_results),
        'civilization_steps': civ_count,
        'level_counts': level_counts,
        'odi_max': round(float(np.max(odi_arr)), 4),
        'odi_mean': round(float(np.mean(odi_arr)), 4),
        'msi_max': round(float(np.max(msi_arr)), 4),
        'msi_mean': round(float(np.mean(msi_arr)), 4),
        'momentum_cache': momentum_stats,
        'final_momentum_bonus': round(final_momentum_bonus, 4),
        'gbc': {
            'coherence_mean': round(float(np.mean(gbc_coherences)), 4) if gbc_coherences else 0.0,
            'coherence_std': round(float(np.std(gbc_coherences)), 4) if gbc_coherences else 0.0,
            'balance_mean': round(float(np.mean(gbc_balances)), 4) if gbc_balances else 0.0,
            'pass_rate': round(float(np.mean(gbc_passes)), 4) if gbc_passes else 0.0,
            'n_checks': len(gbc_history),
            'mechanism_mean_coherence': mechanism_mean_coh,
        },
        'amc_summary': amc_summary,
        'ilp_summary': ilp_summary,
        'elapsed_s': round(elapsed, 1),
    }


def main():
    print("=" * 70)
    print("exp_91: Adaptive Momentum Control Validation")
    print("Phase 4 P0: AMC + ILP active")
    print("=" * 70)

    seeds = [42, 142, 242, 342, 442, 542, 642, 742]
    all_results = []

    for seed in seeds:
        print(f"\n--- Seed {seed} ---", flush=True)
        result = run_single_seed(
            N0=72, steps=1600, seed=seed, sample_interval=10,
            gbc_soft_nudge=0.2, use_amc=True, use_ilp=True
        )
        all_results.append(result)

        print(f"  CIVILIZATION: {result['civilization_steps']}", flush=True)
        print(f"  Level counts: {result['level_counts']}", flush=True)
        print(f"  ODI max: {result['odi_max']}, MSI max: {result['msi_max']}", flush=True)
        print(f"  GBC coherence_mean: {result['gbc']['coherence_mean']}", flush=True)
        print(f"  GBC pass_rate: {result['gbc']['pass_rate']}", flush=True)
        print(f"  Final momentum_bonus: {result['final_momentum_bonus']}", flush=True)
        if result['amc_summary']:
            print(f"  AMC mode: {result['amc_summary']['mode']}, "
                  f"entropy: {result['amc_summary']['final_entropy']}", flush=True)
        if result['ilp_summary']:
            print(f"  ILP mode: {result['ilp_summary']['mode']}, "
                  f"floor: {result['ilp_summary']['final_floor']}", flush=True)
        print(f"  Time: {result['elapsed_s']}s", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("CROSS-SEED SUMMARY", flush=True)
    print("=" * 70, flush=True)

    civ_values = [r['civilization_steps'] for r in all_results]
    odi_max_values = [r['odi_max'] for r in all_results]
    msi_max_values = [r['msi_max'] for r in all_results]
    gbc_coh_values = [r['gbc']['coherence_mean'] for r in all_results]
    gbc_pass_values = [r['gbc']['pass_rate'] for r in all_results]
    final_momentum = [r['final_momentum_bonus'] for r in all_results]

    civ_mean = float(np.mean(civ_values))
    civ_std = float(np.std(civ_values))
    civ_min = int(np.min(civ_values))
    civ_max = int(np.max(civ_values))

    print(f"\n  CIVILIZATION: mean={civ_mean:.1f}, std={civ_std:.1f}, min={civ_min}, max={civ_max}", flush=True)
    print(f"  ODI max: mean={float(np.mean(odi_max_values)):.4f}", flush=True)
    print(f"  MSI max: mean={float(np.mean(msi_max_values)):.4f}", flush=True)
    print(f"  GBC coherence mean: {float(np.mean(gbc_coh_values)):.4f}", flush=True)
    print(f"  GBC pass rate mean: {float(np.mean(gbc_pass_values)):.4f}", flush=True)
    print(f"  Final momentum bonus: mean={float(np.mean(final_momentum)):.4f}, "
          f"min={float(np.min(final_momentum)):.4f}, max={float(np.max(final_momentum)):.4f}", flush=True)

    # exp_90 baseline for comparison
    exp_90_civ = {42: 9, 142: 10, 242: 2, 342: 5, 442: 3, 542: 9, 642: 2, 742: 2}
    print(f"\n  {'Seed':>6} | {'CIV':>5} | {'exp_90':>7} | {'Delta':>6} | "
          f"{'GBC_coh':>8} | {'GBC_pass':>9} | {'mom_bonus':>10} | Status", flush=True)
    print(f"  {'-'*6}-+-{'-'*5}-+-{'-'*7}-+-{'-'*6}-+-{'-'*8}-+-{'-'*9}-+-{'-'*10}-+-{'-'*6}", flush=True)
    for r in all_results:
        status = "PASS" if r['civilization_steps'] >= 3 else "FAIL"
        delta = r['civilization_steps'] - exp_90_civ.get(r['seed'], 0)
        delta_str = f"+{delta}" if delta >= 0 else str(delta)
        print(f"  {r['seed']:>6} | {r['civilization_steps']:>5} | "
              f"{exp_90_civ.get(r['seed'], '?'):>7} | {delta_str:>6} | "
              f"{r['gbc']['coherence_mean']:>8.4f} | {r['gbc']['pass_rate']:>9.4f} | "
              f"{r['final_momentum_bonus']:>10.4f} | {status}", flush=True)

    h1 = civ_mean >= 5.0
    h2 = float(np.mean(gbc_coh_values)) >= 0.55
    h3 = float(np.mean(gbc_pass_values)) >= 0.3
    h4 = all(c >= 3 for c in civ_values)

    # AMC mode summary
    print(f"\n  AMC modes:", flush=True)
    for r in all_results:
        if r['amc_summary']:
            print(f"    Seed {r['seed']:>3}: mode={r['amc_summary']['mode']}, "
                  f"bonus={r['amc_summary']['current_momentum_bonus']}, "
                  f"entropy={r['amc_summary']['final_entropy']}, "
                  f"inst_rate={r['amc_summary']['final_institutional_rate']}", flush=True)

    # ILP mode summary
    print(f"\n  ILP modes:", flush=True)
    for r in all_results:
        if r['ilp_summary']:
            print(f"    Seed {r['seed']:>3}: mode={r['ilp_summary']['mode']}, "
                  f"floor={r['ilp_summary']['final_floor']}, "
                  f"transitions_allowed={r['ilp_summary']['n_transitions_allowed']}", flush=True)

    # Mechanism coherence summary
    print(f"\n  Mechanism mean coherences:", flush=True)
    all_mechanisms = set()
    for r in all_results:
        all_mechanisms.update(r['gbc']['mechanism_mean_coherence'].keys())
    for mech in sorted(all_mechanisms):
        vals = [r['gbc']['mechanism_mean_coherence'].get(mech, 0) for r in all_results]
        print(f"    {mech:>20}: mean={float(np.mean(vals)):+.4f}, "
              f"min={float(np.min(vals)):+.4f}, max={float(np.max(vals)):+.4f}", flush=True)

    print(f"\n  H1 (mean CIV >= 5): {'PASS' if h1 else 'FAIL'} ({civ_mean:.1f})", flush=True)
    print(f"  H2 (GBC coh >= 0.55): {'PASS' if h2 else 'FAIL'} ({float(np.mean(gbc_coh_values)):.4f})", flush=True)
    print(f"  H3 (GBC pass >= 0.3): {'PASS' if h3 else 'FAIL'} ({float(np.mean(gbc_pass_values)):.4f})", flush=True)
    print(f"  H4 (all CIV >= 3): {'PASS' if h4 else 'FAIL'} (min={civ_min})", flush=True)

    all_pass = h1 and h2 and h3 and h4
    print(f"\n  *** PHASE 4 P0 VALIDATION: "
          f"{'ALL HYPOTHESES PASSED' if all_pass else 'SOME HYPOTHESES FAILED'} ***", flush=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f'exp_91_results_{ts}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_91_adaptive_momentum_validation',
            'timestamp': ts,
            'seeds': seeds,
            'n_seeds': len(seeds),
            'config': {
                'momentum_bonus_init': 0.3,
                'momentum_decay': 0.95,
                'coherence_threshold': 0.5,
                'gbc_soft_nudge': 0.2,
                'N0': 72,
                'steps': 1600,
                'amc_active': True,
                'ilp_active': True,
            },
            'per_seed': all_results,
            'cross_seed': {
                'civ_mean': civ_mean,
                'civ_std': civ_std,
                'civ_min': civ_min,
                'civ_max': civ_max,
                'odi_max_mean': float(np.mean(odi_max_values)),
                'msi_max_mean': float(np.mean(msi_max_values)),
                'gbc_coherence_mean': float(np.mean(gbc_coh_values)),
                'gbc_pass_rate_mean': float(np.mean(gbc_pass_values)),
                'final_momentum_bonus_mean': float(np.mean(final_momentum)),
                'h1_mean_civ_ge_5': h1,
                'h2_gbc_coh_ge_055': h2,
                'h3_gbc_pass_ge_03': h3,
                'h4_all_civ_ge_3': h4,
                'all_hypotheses_passed': all_pass,
            },
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {output_path}", flush=True)


if __name__ == '__main__':
    main()
