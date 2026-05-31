"""experiments/exp_85_category_diversity_fix.py

Phase 3 Experiment 13: Validate cache diversity fix (exp_84 root cause)

Root cause (exp_84): All DifferenceSignal objects have source_layer==target_layer,
so _assign_category() always returns internal_layer_0 for all nodes. The momentum
cache therefore has only 1 category.

Fix: _assign_category() now calls _subcategorize_same_layer() which
differentiates signals based on active bit positions (4 regions) and
magnitude (3 levels), yielding up to 12 sub-categories per layer.

Design:
  - Seeds: [42, 142, 242, 342] (same as exp_84 for direct comparison)
  - N0=72, steps=1600, sample_interval=10
  - Same NarrativeMomentumConnector (momentum_decay=0.95, momentum_bonus=0.3)

Hypotheses:
  H1: Cache diversity improves (n_categories >= 3 per seed, vs exp_84: 1)
  H2: CIVILIZATION activation maintained or improved (CIV >= 5 per seed)
  H3: ODI/MSI/GBC metrics remain stable
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


class NarrativeMomentumConnector(NarrativeConnector):
    def __init__(self, strength_threshold=0.3, max_chain_length=10,
                 category_similarity_threshold=0.5, momentum_decay=0.95,
                 momentum_bonus=0.3):
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


class MomentumNarrativeOperator(NarrativeRecursionOperator):
    def __init__(self, bias_dimension=128, filter_magnitude_threshold=0.02,
                 connector_strength_threshold=0.1,
                 verifier_consistency_threshold=0.3,
                 narrative_decay_rate=0.9, momentum_decay=0.95,
                 momentum_bonus=0.3):
        self.filter = NarrativeFilter(
            magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = NarrativeMomentumConnector(
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
    narrative = MomentumNarrativeOperator(
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
    print("exp_85: Category Diversity Fix Validation")
    print("=" * 70)

    seeds = [42, 142, 242, 342]
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

    civ_values = [r['civilization_steps'] for r in all_results]
    cache_div_values = [r['momentum_cache']['n_categories'] for r in all_results]

    print("\n" + "=" * 70, flush=True)
    print("CROSS-SEED SUMMARY", flush=True)
    print("=" * 70, flush=True)
    print(f"  CIV: mean={np.mean(civ_values):.1f}, std={np.std(civ_values):.2f}, range=[{min(civ_values)}, {max(civ_values)}]", flush=True)
    print(f"  Cache diversity: mean={np.mean(cache_div_values):.1f}, range=[{min(cache_div_values)}, {max(cache_div_values)}]", flush=True)

    h1 = all(d >= 3 for d in cache_div_values)
    h2 = all(c >= 5 for c in civ_values)

    print(f"\n  H1 (cache diversity >= 3): {'PASS' if h1 else 'FAIL'}", flush=True)
    print(f"  H2 (CIV >= 5 all seeds): {'PASS' if h2 else 'FAIL'}", flush=True)

    print(f"\n  vs exp_84 baseline:", flush=True)
    print(f"    CIV: exp_84=6.0 -> exp_85={np.mean(civ_values):.1f}", flush=True)
    print(f"    Cache div: exp_84=1 -> exp_85={np.mean(cache_div_values):.1f}", flush=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f'exp_85_results_{ts}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_85_category_diversity_fix',
            'timestamp': ts,
            'seeds': seeds,
            'per_seed': all_results,
            'cross_seed': {
                'civ_mean': round(float(np.mean(civ_values)), 2),
                'civ_std': round(float(np.std(civ_values)), 2),
                'cache_diversity_mean': round(float(np.mean(cache_div_values)), 2),
                'h1_cache_diversity': h1,
                'h2_civ_maintained': h2,
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {output_path}", flush=True)


if __name__ == '__main__':
    main()
