"""experiments/exp_92_ilp_relaxed_validation.py

Phase 4 Experiment 2: ILP Relaxed + AMC Threshold Adjusted

Purpose: Balance H4 fix (min CIV >= 3) with H2/H3 recovery (GBC coh >= 0.55,
pass_rate >= 0.30). exp_91 proved ILP fixes H4 but degrades H2/H3 to zero.
exp_92 relaxes ILP thresholds and adjusts AMC mode detection to find a balance.

Changes vs exp_91:
- ILP: Lower transition thresholds (inst: 40->25, ODI: 0.5->0.15, diversity: 3->2)
- ILP: Shorter cooldowns (transition: 30->15, consumption: 20->10)
- ILP: Higher consumption rate (0.05->0.10), lower floor (30->20, threshold: 50->35)
- AMC: Lower mode detection thresholds (stability_trap: 0.8->0.4, fragmentation: 0.2->0.16)
- AMC: Mode-aware entropy feedback (prevents entropy/institutional signal cancellation)

Config: Same as exp_90/exp_91 (N0=72, steps=1600, 8 seeds)
    momentum_bonus starts at 0.3 (AMC adapts in [0.1, 0.5])
    momentum_decay=0.95
    gbc_soft_nudge=0.2

Hypotheses:
  H1: Mean CIV >= 5.0 (same as exp_90)
  H2: GBC coherence mean >= 0.55 (recover from exp_91's 0.5465)
  H3: GBC pass_rate >= 0.30 (recover from exp_91's 0.0911)
  H4: All seeds CIV >= 3 (maintain exp_91's fix, min CIV was 5)

Expected: H4 maintained, H2/H3 partially or fully recovered.
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


# ─── exp_92 配置覆盖 ───
EXP92_ILP_CONFIG = {
    # 转换门控（大幅降低门槛）
    'transition_min_institutional': 25,
    'transition_min_diversity': 2,
    'transition_min_odi': 0.15,
    'transition_cooldown_steps': 15,
    # 积累保护（降低地板和阈值）
    'min_institutional_floor': 20,
    'min_institutional_threshold': 35,
    # 消耗速率（翻倍）
    'max_consumption_rate_per_step': 0.10,
    'consumption_cooldown_steps': 10,
    # 多样性（降低要求）
    'min_categories_for_transition': 2,
}

EXP92_AMC_CONFIG = {
    # 模式检测阈值（降低以匹配实际数据分布）
    'stability_trap_threshold': 0.4,
    'fragmentation_threshold': 0.16,
}


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
                    gbc_soft_nudge=0.2, use_amc=True, use_ilp=True,
                    ilp_config=None, amc_config=None):
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

    # Phase 4 P0 components with exp_92 config overrides
    amc = None
    if use_amc:
        amc_cfg = dict(DEFAULT_ADAPTIVE_MOMENTUM_CONFIG)
        if amc_config:
            amc_cfg.update(amc_config)
        amc = AdaptiveMomentumController(config=amc_cfg)

    ilp = None
    if use_ilp:
        ilp_cfg = dict(DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG)
        if ilp_config:
            ilp_cfg.update(ilp_config)
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
    inst_count = 0
    mini_count = 0

    for sr in step_results:
        level = sr.get('level', 'MINI')
        if level == 'CIVILIZATION':
            civ_count += 1
        elif level == 'INSTITUTIONAL':
            inst_count += 1
        elif level == 'MINI':
            mini_count += 1
        if sr.get('narrative_active', False):
            active_count += 1

    # GBC summary
    gbc_checks = result.get('gbc_checks', [])
    gbc_coherences = [c.get('coherence', 0.0) for c in gbc_checks]
    gbc_passes = [1 for c in gbc_checks if c.get('passed', False)]
    gbc_coherence_mean = float(np.mean(gbc_coherences)) if gbc_coherences else 0.0
    gbc_pass_rate = float(np.mean(gbc_passes)) if gbc_passes else 0.0

    # GBC mechanism coherence
    mechanism_coherences = {}
    for c in gbc_checks:
        for mech in ['boundary', 'self_sustaining', 'memory', 'replication', 'selection', 'function']:
            val = c.get(f'{mech}_coherence', None)
            if val is not None:
                if mech not in mechanism_coherences:
                    mechanism_coherences[mech] = []
                mechanism_coherences[mech].append(val)
    mechanism_mean_coherence = {
        m: float(np.mean(v)) for m, v in mechanism_coherences.items()
    }

    # AMC summary
    amc_summary = {}
    if amc:
        amc_hist = amc.get_history()
        amc_summary = {
            'current_momentum_bonus': amc_hist['current_momentum_bonus'],
            'final_entropy': amc_hist['entropy'],
            'final_institutional_count': amc_hist['institutional_count'],
            'final_institutional_rate': amc_hist['institutional_rate'],
            'mode': amc_hist['mode'],
            'n_adjustments': amc_hist['n_adjustments'],
            'mean_adjustment': amc_hist['mean_adjustment'],
        }

    # ILP summary
    ilp_summary = {}
    if ilp:
        ilp_hist = ilp.get_history()
        ilp_summary = {
            'final_institutional_count': ilp_hist['institutional_count'],
            'final_floor': ilp_hist['institutional_floor'],
            'n_protection_events': ilp_hist['n_protection_events'],
            'n_transitions_allowed': ilp_hist['n_transitions'],
            'n_transitions_blocked': ilp_hist['n_transitions_blocked'],
            'mode': ilp_hist['mode'],
        }

    # Narrative connector stats
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
        'odi_max': float(result.get('odi_max', 0.0)),
        'odi_mean': float(result.get('odi_mean', 0.0)),
        'msi_max': float(result.get('msi_max', 0.0)),
        'msi_mean': float(result.get('msi_mean', 0.0)),
        'momentum_cache': connector_stats,
        'final_momentum_bonus': amc_summary.get('current_momentum_bonus', 0.3),
        'gbc': {
            'coherence_mean': gbc_coherence_mean,
            'coherence_std': float(np.std(gbc_coherences)) if gbc_coherences else 0.0,
            'balance_mean': float(np.mean([c.get('balance', 0.0) for c in gbc_checks])) if gbc_checks else 0.0,
            'pass_rate': gbc_pass_rate,
            'n_checks': len(gbc_checks),
            'mechanism_mean_coherence': mechanism_mean_coherence,
        },
        'amc_summary': amc_summary,
        'ilp_summary': ilp_summary,
        'elapsed_s': elapsed,
    }


def main():
    seeds = [42, 142, 242, 342, 442, 542, 642, 742]
    N0 = 72
    steps = 1600

    print("=" * 70)
    print("exp_92: ILP Relaxed + AMC Threshold Adjusted")
    print("=" * 70)
    print(f"Seeds: {seeds}")
    print(f"N0={N0}, steps={steps}")
    print(f"ILP config overrides: {EXP92_ILP_CONFIG}")
    print(f"AMC config overrides: {EXP92_AMC_CONFIG}")
    print(f"GBC soft nudge: 0.2")
    print("=" * 70)

    all_results = []
    for seed in seeds:
        result = run_single_seed(
            N0=N0, steps=steps, seed=seed,
            ilp_config=EXP92_ILP_CONFIG,
            amc_config=EXP92_AMC_CONFIG,
        )
        all_results.append(result)

    # Aggregate
    civ_values = [r['civilization_steps'] for r in all_results]
    gbc_coh = [r['gbc']['coherence_mean'] for r in all_results]
    gbc_pr = [r['gbc']['pass_rate'] for r in all_results]

    print("\n" + "=" * 70)
    print("exp_92 Results Summary")
    print("=" * 70)
    print(f"\nPer-seed CIV: {civ_values}")
    print(f"CIV mean: {np.mean(civ_values):.2f}, std: {np.std(civ_values):.2f}, min: {min(civ_values)}, max: {max(civ_values)}")
    print(f"\nGBC coherence mean: {np.mean(gbc_coh):.4f} (std: {np.std(gbc_coh):.4f})")
    print(f"GBC pass_rate mean: {np.mean(gbc_pr):.4f}")

    # Hypothesis tests
    print("\n--- Hypothesis Tests ---")
    h1_pass = np.mean(civ_values) >= 5.0
    h2_pass = np.mean(gbc_coh) >= 0.55
    h3_pass = np.mean(gbc_pr) >= 0.30
    h4_pass = min(civ_values) >= 3

    print(f"H1 (mean CIV >= 5):  {'PASS' if h1_pass else 'FAIL'} ({np.mean(civ_values):.2f})")
    print(f"H2 (GBC coh >= 0.55): {'PASS' if h2_pass else 'FAIL'} ({np.mean(gbc_coh):.4f})")
    print(f"H3 (GBC pass >= 0.30): {'PASS' if h3_pass else 'FAIL'} ({np.mean(gbc_pr):.4f})")
    print(f"H4 (min CIV >= 3):    {'PASS' if h4_pass else 'FAIL'} (min={min(civ_values)})")

    # exp_91 comparison
    print("\n--- vs exp_91 ---")
    print(f"CIV mean:    {np.mean(civ_values):.2f} (exp_91: 13.9)")
    print(f"GBC coh:     {np.mean(gbc_coh):.4f} (exp_91: 0.5465)")
    print(f"GBC pass:    {np.mean(gbc_pr):.4f} (exp_91: 0.0911)")
    print(f"H4 min CIV:  {min(civ_values)} (exp_91: 5)")

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(
        PROJECT_ROOT, 'experiments', f'exp_92_results_{timestamp}.json'
    )
    output = {
        'experiment': 'exp_92_ilp_relaxed_validation',
        'timestamp': timestamp,
        'seeds': seeds,
        'n_seeds': len(seeds),
        'config': {
            'momentum_bonus_init': 0.3,
            'momentum_decay': 0.95,
            'gbc_soft_nudge': 0.2,
            'N0': N0,
            'steps': steps,
            'amc_active': True,
            'ilp_active': True,
            'ilp_overrides': EXP92_ILP_CONFIG,
            'amc_overrides': EXP92_AMC_CONFIG,
        },
        'per_seed': all_results,
        'summary': {
            'civ_mean': float(np.mean(civ_values)),
            'civ_std': float(np.std(civ_values)),
            'civ_min': int(min(civ_values)),
            'civ_max': int(max(civ_values)),
            'gbc_coh_mean': float(np.mean(gbc_coh)),
            'gbc_pr_mean': float(np.mean(gbc_pr)),
            'h1_pass': h1_pass,
            'h2_pass': h2_pass,
            'h3_pass': h3_pass,
            'h4_pass': h4_pass,
        },
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
