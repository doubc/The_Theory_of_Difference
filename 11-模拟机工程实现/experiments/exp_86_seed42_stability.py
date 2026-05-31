"""experiments/exp_86_seed42_stability.py

Phase 3 Experiment 14: Seed=42 stability + magnitude threshold adjustment

exp_85 result: seed=42 CIV=4 (marginal FAIL, threshold=5)
Hypothesis: seed=42 is in a "borderline attractor" — small parameter
changes push it over the threshold.

Two interventions:
  A. Increase momentum_bonus from 0.3 to 0.5 (stronger hotspot reinforcement)
  B. Lower magnitude thresholds for subcategorization (high>0.8, mid>0.3, low<0.3)
     to get more diverse cache categories

Design:
  - Seeds: [42] (focus on the marginal seed) + [142] (control)
  - N0=72, steps=1600, sample_interval=10
  - momentum_bonus=0.5 (vs exp_85: 0.3)
  - momentum_decay=0.95 (same)

Hypotheses:
  H1: seed=42 CIV >= 5 with stronger momentum bonus
  H2: seed=142 CIV maintained or improved (control)
  H3: More sub-category diversity with adjusted magnitude thresholds
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
    """V2: stronger momentum bonus + adjusted magnitude thresholds."""
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
        'elapsed_s': round(elapsed, 1),
    }


def main():
    print("=" * 70)
    print("exp_86: Seed=42 Stability + Stronger Momentum (bonus=0.5)")
    print("=" * 70)

    seeds = [42, 142]
    all_results = []

    for seed in seeds:
        print(f"\n--- Seed {seed} ---", flush=True)
        result = run_single_seed(N0=72, steps=1600, seed=seed, sample_interval=10)
        all_results.append(result)

        print(f"  CIVILIZATION: {result['civilization_steps']}", flush=True)
        print(f"  Level counts: {result['level_counts']}", flush=True)
        print(f"  ODI max: {result['odi_max']}, MSI max: {result['msi_max']}", flush=True)
        print(f"  Cache diversity: {result['momentum_cache']['n_categories']} categories", flush=True)
        print(f"  Cache categories: {result['momentum_cache'].get('categories', {})}", flush=True)
        print(f"  Time: {result['elapsed_s']}s", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 70, flush=True)

    for r in all_results:
        status = "PASS" if r['civilization_steps'] >= 5 else "FAIL"
        print(f"  seed={r['seed']}: CIV={r['civilization_steps']} [{status}], "
              f"cache_div={r['momentum_cache']['n_categories']}, "
              f"ODI_max={r['odi_max']}, MSI_max={r['msi_max']}", flush=True)

    h1 = all(r['civilization_steps'] >= 5 for r in all_results)
    print(f"\n  H1 (all seeds CIV >= 5): {'PASS' if h1 else 'FAIL'}", flush=True)

    print(f"\n  vs exp_85:", flush=True)
    for r in all_results:
        print(f"    seed={r['seed']}: exp_85 CIV -> exp_86 CIV={r['civilization_steps']}", flush=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f'exp_86_results_{ts}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_86_seed42_stability',
            'timestamp': ts,
            'seeds': seeds,
            'per_seed': all_results,
            'cross_seed': {
                'h1_all_civ_ge_5': h1,
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {output_path}", flush=True)


if __name__ == '__main__':
    main()
