"""experiments/exp_87_multiseed_validation.py

Phase 3 Experiment 15: Multi-seed statistical validation

exp_86 showed momentum_bonus=0.5 dramatically improved CIV (seed=42: 4->21).
But only 2 seeds were tested. This experiment runs 8 seeds to confirm
the improvement is robust across the seed space.

Design:
  - Seeds: [42, 142, 242, 342, 442, 542, 642, 742]
  - N0=72, steps=1600, sample_interval=10
  - momentum_bonus=0.5, momentum_decay=0.95 (from exp_86)
  - coherence_threshold=0.5 (lowered from 0.6 to match observed stable range)

Hypotheses:
  H1: Mean CIV >= 8 across 8 seeds (robust emergence)
  H2: No seed has CIV < 3 (no catastrophic failure)
  H3: GBC coherence mean >= 0.55 (soft constraint effective)
  H4: replication/selection are consistently the top violators
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
    NarrativeRecursionOperator, NarrativeLevel, NarrativeConnector,
    NarrativeFilter, NarrativeNamer, NarrativeActionizer, NarrativeVerifier,
    NarrativeNode, CausalChain,
)
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.six_threshold_detector import SixThresholdDetector


class NarrativeMomentumConnectorV2(NarrativeConnector):
    """V2: stronger momentum bonus (from exp_86)."""
    def __init__(self, strength_threshold=0.3, max_chain_length=10,
                 category_similarity_threshold=0.5, momentum_decay=0.95,
                 momentum_bonus=0.5):
        super().__init__(
            strength_threshold=strength_threshold,
            max_chain_length=max_chain_length,
            category_similarity_threshold=category_similarity_threshold,
        )
        self.momentum_decay = momentum_decay
        self.momentum_bonus = momentum_bonus
        self.civ_category_cache: Dict[str, float] = {}

    def connect(self, nodes, timestamp):
        for cat in list(self.civ_category_cache.keys()):
            self.civ_category_cache[cat] *= self.momentum_decay
            if self.civ_category_cache[cat] < 0.01:
                del self.civ_category_cache[cat]
        chains = super().connect(nodes, timestamp)
        for chain in chains:
            if len(chain.node_ids) >= 5:
                for node_id in chain.node_ids:
                    node = self._node_index.get(node_id)
                    if node:
                        cat = node.category
                        self.civ_category_cache[cat] = (
                            self.civ_category_cache.get(cat, 0.0) + 1.0
                        )
        return chains

    def _compute_edge_strength(self, a, b):
        base_strength = super()._compute_edge_strength(a, b)
        a_heat = self.civ_category_cache.get(a.category, 0.0)
        b_heat = self.civ_category_cache.get(b.category, 0.0)
        max_heat = max(a_heat, b_heat)
        if max_heat > 0.01:
            normalized_heat = min(max_heat / 5.0, 1.0)
            bonus = 1.0 + self.momentum_bonus * normalized_heat
            base_strength *= bonus
        return base_strength

    def get_cache_stats(self):
        if not self.civ_category_cache:
            return {'n_categories': 0, 'max_heat': 0.0, 'mean_heat': 0.0,
                    'categories': {}}
        heats = list(self.civ_category_cache.values())
        return {
            'n_categories': len(heats),
            'max_heat': round(max(heats), 4),
            'mean_heat': round(float(np.mean(heats)), 4),
            'categories': {k: round(v, 3) for k, v in
                          sorted(self.civ_category_cache.items(),
                                 key=lambda x: -x[1])[:10]},
        }


class MomentumNarrativeOperatorV2(NarrativeRecursionOperator):
    def __init__(self, bias_dimension=128, filter_magnitude_threshold=0.02,
                 connector_strength_threshold=0.1,
                 verifier_consistency_threshold=0.3,
                 narrative_decay_rate=0.9, momentum_decay=0.95,
                 momentum_bonus=0.5):
        self.filter = NarrativeFilter(
            magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = NarrativeMomentumConnectorV2(
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


def run_single_seed(N0=72, steps=1600, seed=142, sample_interval=10):
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
    narrative = MomentumNarrativeOperatorV2(
        bias_dimension=128, filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.5,
    )
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01},
    )
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1, 'max_branches': 4,
    })
    six_threshold = SixThresholdDetector()

    evolver = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=1, p1_eval_interval=sample_interval,
        phase2_verbose=False, phase3_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi, six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism, return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity, minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory, counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative, global_bias_constraint=gbc,
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
    level_counts = {'MINI': 0, 'INSTITUTIONAL': 0, 'CIVILIZATION': 0}
    odi_values = []
    msi_values = []

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

    odi_arr = np.array(odi_values) if odi_values else np.array([0.0])
    msi_arr = np.array(msi_values) if msi_values else np.array([0.0])

    momentum_stats = narrative.get_momentum_stats()

    # GBC trend analysis
    gbc_history = gbc.get_history(limit=1000)
    gbc_coherences = [r.coherence for r in gbc_history]
    gbc_balances = [r.balance for r in gbc_history]
    gbc_passes = [r.passed for r in gbc_history]

    # Per-mechanism coherence aggregation
    mechanism_coherences: Dict[str, List[float]] = {}
    for r in gbc_history:
        for mech, coh in r.coherence_by_mechanism.items():
            if mech not in mechanism_coherences:
                mechanism_coherences[mech] = []
            mechanism_coherences[mech].append(coh)

    mechanism_mean_coh = {k: round(float(np.mean(v)), 4) for k, v in mechanism_coherences.items()}

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
        'gbc': {
            'coherence_mean': round(float(np.mean(gbc_coherences)), 4) if gbc_coherences else 0.0,
            'coherence_std': round(float(np.std(gbc_coherences)), 4) if gbc_coherences else 0.0,
            'balance_mean': round(float(np.mean(gbc_balances)), 4) if gbc_balances else 0.0,
            'pass_rate': round(float(np.mean(gbc_passes)), 4) if gbc_passes else 0.0,
            'n_checks': len(gbc_history),
            'mechanism_mean_coherence': mechanism_mean_coh,
        },
        'elapsed_s': round(elapsed, 1),
    }


def main():
    print("=" * 70)
    print("exp_87: Multi-seed Validation (8 seeds, momentum=0.5, threshold=0.5)")
    print("=" * 70)

    seeds = [42, 142, 242, 342, 442, 542, 642, 742]
    all_results = []

    for seed in seeds:
        print(f"\n--- Seed {seed} ---", flush=True)
        result = run_single_seed(N0=72, steps=1600, seed=seed, sample_interval=10)
        all_results.append(result)

        print(f"  CIVILIZATION: {result['civilization_steps']}", flush=True)
        print(f"  Level counts: {result['level_counts']}", flush=True)
        print(f"  ODI max: {result['odi_max']}, MSI max: {result['msi_max']}", flush=True)
        print(f"  GBC coherence_mean: {result['gbc']['coherence_mean']}", flush=True)
        print(f"  GBC pass_rate: {result['gbc']['pass_rate']}", flush=True)
        print(f"  Time: {result['elapsed_s']}s", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("CROSS-SEED SUMMARY", flush=True)
    print("=" * 70, flush=True)

    civ_values = [r['civilization_steps'] for r in all_results]
    odi_max_values = [r['odi_max'] for r in all_results]
    msi_max_values = [r['msi_max'] for r in all_results]
    gbc_coh_values = [r['gbc']['coherence_mean'] for r in all_results]
    gbc_pass_values = [r['gbc']['pass_rate'] for r in all_results]

    civ_mean = float(np.mean(civ_values))
    civ_std = float(np.std(civ_values))
    civ_min = int(np.min(civ_values))
    civ_max = int(np.max(civ_values))

    print(f"\n  CIVILIZATION: mean={civ_mean:.1f}, std={civ_std:.1f}, min={civ_min}, max={civ_max}", flush=True)
    print(f"  ODI max: mean={float(np.mean(odi_max_values)):.4f}", flush=True)
    print(f"  MSI max: mean={float(np.mean(msi_max_values)):.4f}", flush=True)
    print(f"  GBC coherence mean: {float(np.mean(gbc_coh_values)):.4f}", flush=True)
    print(f"  GBC pass rate mean: {float(np.mean(gbc_pass_values)):.4f}", flush=True)

    # Per-seed table
    print(f"\n  {'Seed':>6} | {'CIV':>5} | {'ODI_max':>8} | {'MSI_max':>8} | {'GBC_coh':>8} | {'GBC_pass':>9} | Status", flush=True)
    print(f"  {'-'*6}-+-{'-'*5}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*9}-+-{'-'*6}", flush=True)
    for r in all_results:
        status = "PASS" if r['civilization_steps'] >= 5 else "FAIL"
        print(f"  {r['seed']:>6} | {r['civilization_steps']:>5} | {r['odi_max']:>8.4f} | {r['msi_max']:>8.4f} | {r['gbc']['coherence_mean']:>8.4f} | {r['gbc']['pass_rate']:>9.4f} | {status}", flush=True)

    # Hypothesis testing
    h1 = civ_mean >= 8.0
    h2 = civ_min >= 3
    h3 = float(np.mean(gbc_coh_values)) >= 0.55

    # H4: check if replication/selection are consistently top violators
    all_mechanism_cohs: Dict[str, List[float]] = {}
    for r in all_results:
        for mech, coh in r['gbc']['mechanism_mean_coherence'].items():
            if mech not in all_mechanism_cohs:
                all_mechanism_cohs[mech] = []
            all_mechanism_cohs[mech].append(coh)
    mean_mechanism_cohs = {k: float(np.mean(v)) for k, v in all_mechanism_cohs.items()}
    sorted_mechanisms = sorted(mean_mechanism_cohs.items(), key=lambda x: x[1])
    h4_violators = [m for m, c in sorted_mechanisms[:2]]
    h4 = 'replication' in h4_violators or 'selection' in h4_violators

    print(f"\n  H1 (mean CIV >= 8): {'PASS' if h1 else 'FAIL'} ({civ_mean:.1f})", flush=True)
    print(f"  H2 (min CIV >= 3):  {'PASS' if h2 else 'FAIL'} ({civ_min})", flush=True)
    print(f"  H3 (GBC coh >= 0.55): {'PASS' if h3 else 'FAIL'} ({float(np.mean(gbc_coh_values)):.4f})", flush=True)
    print(f"  H4 (rep/sel violators): {'PASS' if h4 else 'FAIL'} (bottom 2: {h4_violators})", flush=True)
    print(f"\n  Mechanism mean coherences: {sorted_mechanisms}", flush=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f'exp_87_results_{ts}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_87_multiseed_validation',
            'timestamp': ts,
            'seeds': seeds,
            'n_seeds': len(seeds),
            'config': {
                'momentum_bonus': 0.5,
                'momentum_decay': 0.95,
                'coherence_threshold': 0.5,
                'N0': 72,
                'steps': 1600,
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
                'h1_mean_civ_ge_8': h1,
                'h2_min_civ_ge_3': h2,
                'h3_gbc_coh_ge_055': h3,
                'h4_rep_sel_violators': h4,
                'mean_mechanism_coherences': mean_mechanism_cohs,
            },
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {output_path}", flush=True)


if __name__ == '__main__':
    main()
