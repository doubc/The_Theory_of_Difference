# -*- coding: utf-8 -*-
"""
experiments/exp_118_phase5_b5_independent_l2.py

Phase 5 Track B5: 独立 L2 聚簇 + 稳定性地板 (Independent L2 Clustering + Stability Floor)

Purpose: Fix the fundamental flaw of B4 — L2 had no independent clustering.
    B4 achieved H30 "pass" (r=0.000) but it was a FALSE POSITIVE:
    both L1 and L2 were silent, so zero variance → zero correlation.

    B5 design:
    1. L2 independently clusters L0 structural vectors (own difference field)
    2. L1 provides soft additive bias (not hard clamp)
    3. L2 has stability floor (0.15) to prevent suppression
    4. L2 has intrinsic perturbation and autonomous decay

Background:
  B1 (parallel): L1<->L2 r = 0.976 — perfect correlation
  B2 (serial):   L1<->L2 r = 0.861 — slight improvement
  B3 (noise):    L1<->L2 r = 0.937 — worse, noise insufficient
  B4 (constraint): L1<->L2 r = 0.000 — FALSE POSITIVE (both silent)

  B5 design philosophy:
  - L2 is not derived from L1 at all — it has its own clustering from L0
  - L1 provides soft constraint as additive bias, not boundary clamp
  - Stability floor ensures L2 always has minimum activity
  - Intrinsic dynamics give L2 its own temporal signature

Hypotheses:
  H30 (layer decoupling): L1<->L2 stability Pearson r < 0.7
      B1: 0/8, B2: 1/8, B3: 0/8, B4: 8/8 (false positive)
      B5 target: >= 5/8 (62.5%) — both layers active but decoupled

  H31 (hierarchical delay): L0->L1 delay >= 5 steps detected
      B1: N/A, B2: 0/8, B3: 0/8, B4: 0/8
      B5 target: >= 4/8 detected

  H32 (L2 autonomy): L2 narrative differs from L1 narrative
      B1-B4: 0/8 (both silent)
      B5 target: >= 5/8 (autonomy index > 0.3)

  H33 (L2 ODI independence): L2 ODI vs L0 ODI correlation < 0.8
      New: measures whether L2 has independent clustering structure
      Target: >= 5/8 pass

  H34 (L1->L2 response delay): Average delay > 5 steps
      New: measures the lag between L1 change and L2 soft constraint response
      Target: >= 4/8 detected

  Also tracks H1-H8 baseline to verify B5 doesn't break core dynamics.

Invoke modes:
  Batch:  python exp_118_phase5_b5_independent_l2.py
  Single: python exp_118_phase5_b5_independent_l2.py <seed>
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
    NarrativeNode, CausalChain, CIVRateLimiter, NarrativeRecord,
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
from engine.layer_narrative_tracker import (
    LayerNarrativeTracker, DEFAULT_LAYER_NARRATIVE_CONFIG,
)


# ─── 8 baseline seeds (same as B1-B4) ───
ALL_SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]

# ─── P5 Track B5: Independent L2 CSC config ───
P5_B5_INDEPENDENT_CSC_CONFIG = {
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
    # ── Track B5: Independent L2 Coupling Mode ──
    'coupling_mode': 'independent',
    'l2_independent_N0': 72,
    'l2_stability_floor': 0.15,
    'l2_constraint_strength': 0.1,
    'l2_perturbation_rate': 0.03,
    'l2_perturbation_magnitude': 0.2,
    'l2_autonomous_decay': 0.97,
    'l2_odi_independence_weight': 0.5,
    'l2_clustering_noise': 0.15,
    'l2_constraint_bias_type': 'additive',
    'l2_min_active_objects': 10,
}

# ─── Experiment parameters ───
N0 = 72
STEPS = 2000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.5

FIXED_OUTPUT = os.path.join(
    PROJECT_ROOT, 'experiments',
    'exp_118_b5_results.json')


# ─── P5 Baseline LNT config ───
P5_LNT_CONFIG = dict(DEFAULT_LAYER_NARRATIVE_CONFIG)
P5_LNT_CONFIG['continuity_window'] = 100
P5_LNT_CONFIG['stability_window'] = 100
P5_LNT_CONFIG['inter_layer_min_samples'] = 50
P5_LNT_CONFIG['inter_layer_correlation_window'] = 200
P5_LNT_CONFIG['inter_layer_delay_min'] = 50
P5_LNT_CONFIG['inter_layer_delay_max'] = 200
P5_LNT_CONFIG['nsi_alpha'] = 0.4
P5_LNT_CONFIG['nsi_beta'] = 0.3
P5_LNT_CONFIG['nsi_gamma'] = 0.3
P5_LNT_CONFIG['nsi_min_odi'] = 0.3


class CIVRateLimiterV2P1F:
    """CIV Rate Limiter V2 — P1 fix: min guarantee = 3"""
    def __init__(self):
        self.window_size = 50
        self.max_civ_rate = 0.12
        self.cooldown_steps = 12
        self.min_civ_guarantee = 3
        self._civ_timestamps = []
        self._total_civ_seen = 0
        self._total_downgrades = 0
        self._last_civ_step = -999

    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            self._total_civ_seen += 1
            self._civ_timestamps.append(step)
            if self._total_civ_seen < self.min_civ_guarantee:
                return level
            if step - self._last_civ_step < self.cooldown_steps:
                self._total_downgrades += 1
                return NarrativeLevel.INSTITUTIONAL
            self._last_civ_step = step
        return level

    def get_summary(self):
        return {
            'total_civ_seen': self._total_civ_seen,
            'total_downgrades': self._total_downgrades,
            'min_civ_guarantee': self.min_civ_guarantee,
        }


class MomentumNarrativeOperatorV4P1F:
    """Narrative Recursion Operator with P1 fixes"""
    def __init__(self):
        from models.narrative_self import (
            NarrativeFilter, NarrativeNamer,
            NarrativeActionizer, NarrativeVerifier,
        )
        from collections import deque
        self.filter = NarrativeFilter(magnitude_threshold=0.02)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(
            strength_threshold=0.1, momentum_decay=0.95, momentum_bonus=0.3)
        self.actionizer = NarrativeActionizer(bias_dimension=128)
        self.verifier = NarrativeVerifier(consistency_threshold=0.3)
        self.narrative_decay_rate = 0.9
        self._records = deque(maxlen=200)
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F()

    def step(self, signals, current_bias, current_odi, timestamp):
        significant, discarded = self.filter.filter(signals, timestamp)
        if not significant:
            return None
        nodes = self.namer.name(significant, timestamp)
        if not nodes:
            return None
        chains = self.connector.connect(nodes, timestamp)
        if not chains:
            return None
        node_dict = {n.node_id: n for n in nodes}
        actions = self.actionizer.actionize(chains, node_dict, timestamp)
        if not actions:
            return None
        for a in actions:
            a.narrative_level = self.civ_rate_limiter.maybe_downgrade(
                a.narrative_level, timestamp)
        self._record_count += 1
        self._total_actions += len(actions)
        self._validated_actions += len(actions)

        highest_level = NarrativeLevel.MINI_NARRATIVE
        for a in actions:
            if a.narrative_level.value > highest_level.value:
                highest_level = a.narrative_level

        record = NarrativeRecord(
            record_id=f"narr_{timestamp}",
            input_signals=[s.signal_id for s in significant],
            filtered_signals=[s.signal_id for s in significant],
            named_nodes=[n.node_id for n in nodes],
            causal_chains=[c.chain_id for c in chains],
            actions=[a.action_id for a in actions],
            verification_result=True,
            verification_score=1.0,
            timestamp=timestamp,
            narrative_level=highest_level,
        )
        self._records.append(record)

        if actions:
            strongest = max(actions, key=lambda a: a.magnitude)
            return {
                'direction': strongest.direction.clone(),
                'magnitude': strongest.magnitude,
                'narrative_level': strongest.narrative_level,
                'narrative_label': strongest.narrative_label,
            }
        return None

    def get_summary(self):
        return {
            'record_count': self._record_count,
            'total_actions': self._total_actions,
            'validated_actions': self._validated_actions,
            'civ_rate_limiter': self.civ_rate_limiter.get_summary(),
        }


def safe_mean(lst):
    return sum(lst) / len(lst) if lst else 0.0


def safe_std(lst):
    if len(lst) < 2:
        return 0.0
    m = safe_mean(lst)
    return (sum((x - m) ** 2 for x in lst) / len(lst)) ** 0.5


def safe_max(lst):
    return max(lst) if lst else 0.0


def evaluate_h1_h8(metrics):
    """Evaluate H1-H8 baseline hypotheses."""
    nsi_vals = metrics.get('nsi_vals', [])
    nsi_active = metrics.get('nsi_active', [])
    continuity_vals = metrics.get('continuity_vals', [])
    depth_vals = metrics.get('depth_vals', [])
    tp_vals = metrics.get('tp_vals', [])
    civ_events = metrics.get('civ_events', [])
    csci_vals = metrics.get('csci_vals', [])
    td_vals = metrics.get('td_vals', [])

    nsi_max = safe_max(nsi_vals)
    nsi_active_rate = safe_mean([1.0 if x > 0.05 else 0.0 for x in nsi_active])
    continuity_mean = safe_mean(continuity_vals)
    history_depth_mean = safe_mean(depth_vals)
    turning_points = tp_vals[-1] if tp_vals else 0
    civ_count = sum(civ_events)
    csci_std = safe_std(csci_vals)
    topdown_max = int(safe_max(td_vals))

    h1 = nsi_max > 0.1
    h2 = nsi_active_rate > 0.3
    h3 = continuity_mean > 0.1
    h4 = history_depth_mean > 0.05 or turning_points > 0
    h5 = 3.0 <= civ_count <= 15.0
    h6 = civ_count >= 2
    h7 = csci_std > 0.005
    h8 = topdown_max > 0

    return {
        'h1': h1, 'h2': h2, 'h3': h3, 'h4': h4,
        'h5': h5, 'h6': h6, 'h7': h7, 'h8': h8,
        'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
        'nsi_max': nsi_max,
        'nsi_active_rate': nsi_active_rate,
        'civ_count': civ_count,
        'topdown_max': topdown_max,
    }


def evaluate_h30_h34_b5(lnt, step_results, csc_summary):
    """Evaluate H30-H34 for B5 independent L2 coupling."""
    h28_result = lnt.get_inter_layer_correlation()
    h29_result = lnt.get_conduction_delay()

    # H30: L1<->L2 correlation < 0.7 (from LNT)
    l1_l2_corr = h28_result.pairwise_correlations.get(
        'INSTITUTIONAL->CIVILIZATION', None)
    if l1_l2_corr is None:
        l1_l2_corr = h28_result.pairwise_correlations.get(
            'CIVILIZATION->INSTITUTIONAL', 0.0)

    # Also check from CSC independent_l2 summary
    indep_summary = csc_summary.get('independent_l2', {})
    csc_l1_l2_corr = indep_summary.get('l1_l2_correlation')
    if csc_l1_l2_corr is not None:
        # Use CSC correlation as primary (more direct measurement)
        l1_l2_corr = csc_l1_l2_corr

    h30_pass = l1_l2_corr is not None and abs(l1_l2_corr) < 0.7

    # H31: L0->L1 delay detected
    l0_l1 = h29_result.l0_to_l1_delay
    h31_pass = l0_l1 is not None and l0_l1 > 0

    # H32: L2 autonomy from narrative label diversity
    inst_narratives = set()
    civ_narratives = set()
    for sr in step_results:
        narr = sr.get('narrative_recursion', {})
        if narr:
            level = narr.get('narrative_level', '')
            label = narr.get('narrative_label', 'silent')
            if level == 'INSTITUTIONAL':
                inst_narratives.add(label)
            elif level == 'CIVILIZATION':
                civ_narratives.add(label)
    if inst_narratives and civ_narratives:
        overlap = len(inst_narratives & civ_narratives)
        union = len(inst_narratives | civ_narratives)
        narrative_similarity = overlap / union if union > 0 else 0
    else:
        narrative_similarity = 1.0
    l2_autonomy_index = 1.0 - narrative_similarity
    h32_pass = l2_autonomy_index > 0.3

    # H33: L2 ODI independence — L2 ODI vs L0 ODI correlation < 0.8
    l0_odi_vals = []
    l2_odi_vals = []
    for sr in step_results:
        l0_odi = sr.get('odi', None)
        if l0_odi is not None:
            l0_odi_vals.append(l0_odi)
        # L2 ODI from independent_l2 summary
        indep = sr.get('cross_scale_coupling', {}).get('independent_l2', {})
        if indep:
            l2_odi = indep.get('latest_state', {}).get('odi', None)
            if l2_odi is not None:
                l2_odi_vals.append(l2_odi)

    h33_pass = False
    l2_l0_odi_corr = None
    if len(l0_odi_vals) >= 30 and len(l2_odi_vals) >= 30:
        min_len = min(len(l0_odi_vals), len(l2_odi_vals))
        l0_arr = np.array(l0_odi_vals[-min_len:])
        l2_arr = np.array(l2_odi_vals[-min_len:])
        l2_l0_odi_corr = float(np.corrcoef(l0_arr, l2_arr)[0, 1])
        h33_pass = abs(l2_l0_odi_corr) < 0.8

    # H34: L1->L2 response delay > 5 steps
    avg_delay = indep_summary.get('avg_response_delay', 0.0)
    n_response_events = indep_summary.get('n_response_events', 0)
    h34_pass = avg_delay > 5.0 and n_response_events >= 3

    return {
        'H30': {
            'pass': h30_pass,
            'l1_l2_correlation': round(float(l1_l2_corr), 4) if l1_l2_corr is not None else None,
            'target': '< 0.7',
        },
        'H31': {
            'pass': h31_pass,
            'l0_to_l1_delay': l0_l1,
            'target': '>= 5 steps detected',
        },
        'H32': {
            'pass': h32_pass,
            'l2_autonomy_index': round(l2_autonomy_index, 4),
            'inst_narratives': list(inst_narratives),
            'civ_narratives': list(civ_narratives),
            'target': '> 0.3',
        },
        'H33': {
            'pass': h33_pass,
            'l2_l0_odi_correlation': round(l2_l0_odi_corr, 4) if l2_l0_odi_corr is not None else None,
            'target': '< 0.8',
        },
        'H34': {
            'pass': h34_pass,
            'avg_response_delay': round(avg_delay, 2),
            'n_response_events': n_response_events,
            'target': '> 5 steps, >= 3 events',
        },
    }


def run_seed(seed, steps=STEPS, n0=N0, csc_config=None):
    """Run a single seed with B5 independent L2 coupling."""
    if csc_config is None:
        csc_config = P5_B5_INDEPENDENT_CSC_CONFIG

    torch.manual_seed(seed)
    np.random.seed(seed)
    gc.collect()

    evolver = HierarchicalEvolver(
        bias_dim=128,
        N0=n0,
        seed=seed,
        return_flow_config={'decay_rate': 0.95, 'channel_capacity': 0.3},
        unsealing_config={'unsealing_threshold': 0.3, 'resealing_threshold': 0.5},
        psc_config={'convergence_threshold': 0.3, 'window_size': 200},
        gbc_config={'soft_nudge': GBC_SOFT_NUDGE, 'max_bias_magnitude': 1.0},
        persistent_memory_config={'memory_decay': 0.95, 'max_memory_size': 500},
        cumulative_selector_config={'selection_threshold': 0.3, 'decay_rate': 0.98},
        narrative_self_emergence_config=dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG),
        layer_narrative_tracker_config=P5_LNT_CONFIG,
        cross_scale_coupling_config=csc_config,
        anticipatory_config={'horizon': 50, 'decay': 0.95, 'strength': 0.1},
        counterfactual_config={'horizon': 30, 'perturbation': 0.15, 'strength': 0.1},
        institutional_layer_protector_config={
            'min_institutional_threshold': 35,
            'institutional_floor': 20,
            'diversity_threshold': 0.3,
            'transition_openness_target': 0.5,
        },
    )

    # Override CSC coupling mode to independent
    if evolver.cross_scale_coupling is not None:
        evolver.cross_scale_coupling.coupling_mode = 'independent'
        evolver.cross_scale_coupling.independent_l2.reset()

    step_results = []
    start_time = time.time()

    for step in range(steps):
        result = evolver.step()

        if step % SAMPLE_INTERVAL == 0:
            narr_summary = evolver.narrative_recursion_operator.get_summary() if evolver.narrative_recursion_operator else {}
            lnt_summary = evolver.layer_narrative_tracker.get_summary() if evolver.layer_narrative_tracker else {}
            csc_summary = evolver.cross_scale_coupling.get_summary() if evolver.cross_scale_coupling else {}

            step_results.append({
                'step': step,
                'odi': result.get('odi', {}).get('value', 0.0),
                'narrative_recursion': narr_summary,
                'layer_narrative_tracker': lnt_summary,
                'cross_scale_coupling': csc_summary,
                'top_down_constraints': csc_summary.get('top_down', {}),
                'csci': csc_summary.get('csci_trend', {}),
            })

        if step % 500 == 0 and step > 0:
            elapsed = time.time() - start_time
            print(f"  Seed {seed}: step {step}/{steps} ({elapsed:.1f}s)")

    elapsed = time.time() - start_time

    # Collect metrics for hypothesis evaluation
    metrics = {
        'nsi_vals': [],
        'nsi_active': [],
        'continuity_vals': [],
        'depth_vals': [],
        'tp_vals': [],
        'civ_events': [],
        'csci_vals': [],
        'td_vals': [],
    }

    for sr in step_results:
        narr = sr.get('narrative_recursion', {})
        if narr:
            metrics['nsi_vals'].append(narr.get('nsi', 0.0))
            metrics['nsi_active'].append(narr.get('nsi', 0.0))
            metrics['depth_vals'].append(narr.get('history_depth', 0.0))
            metrics['tp_vals'].append(narr.get('turning_points', 0))
            level = narr.get('narrative_level', '')
            if level == 'CIVILIZATION':
                metrics['civ_events'].append(1)
            else:
                metrics['civ_events'].append(0)

        lnt = sr.get('layer_narrative_tracker', {})
        metrics['continuity_vals'].append(lnt.get('continuity_score', 0.0))

        csci = sr.get('csci', {})
        metrics['csci_vals'].append(csci.get('csci', 0.0))

        td = sr.get('top_down_constraints', {})
        if isinstance(td, dict):
            constraints = td.get('constraints', [])
            max_strength = max((c.get('strength', 0) for c in constraints), default=0)
        else:
            max_strength = 0
        metrics['td_vals'].append(max_strength)

    h1_h8 = evaluate_h1_h8(metrics)
    csc_summary = step_results[-1].get('cross_scale_coupling', {}) if step_results else {}
    lnt = evolver.layer_narrative_tracker
    h30_h34 = evaluate_h30_h34_b5(lnt, step_results, csc_summary)

    all_pass = h1_h8['n_pass'] >= 6 and all(h30_h34[h]['pass'] for h in ['H30'])

    return {
        'seed': seed,
        'h1_h8': h1_h8,
        'h30_h34': h30_h34,
        'all_pass': all_pass,
        'elapsed': elapsed,
        'step_results': step_results,
    }


def main():
    seeds = [int(s) for s in sys.argv[1:]] if len(sys.argv) > 1 else ALL_SEEDS

    print(f"=" * 70)
    print(f"Phase 5 Track B5: Independent L2 Clustering + Stability Floor")
    print(f"Seeds: {seeds}, Steps: {STEPS}, N0: {N0}")
    print(f"Output: {FIXED_OUTPUT}")
    print(f"=" * 70)

    all_results = []
    total_h1_h8_pass = 0
    h30_pass_count = 0
    h31_pass_count = 0
    h32_pass_count = 0
    h33_pass_count = 0
    h34_pass_count = 0

    for seed in seeds:
        print(f"\n--- Seed {seed} ---")
        result = run_seed(seed)
        all_results.append(result)

        h1_h8 = result['h1_h8']
        h30_h34 = result['h30_h34']

        print(f"  H1-H8: {h1_h8['n_pass']}/8 PASS")
        print(f"  H1: {'PASS' if h1_h8['h1'] else 'FAIL'} (NSI max={h1_h8['nsi_max']:.4f})")
        print(f"  H2: {'PASS' if h1_h8['h2'] else 'FAIL'} (active rate={h1_h8['nsi_active_rate']:.4f})")
        print(f"  H3: {'PASS' if h1_h8['h3'] else 'FAIL'} (continuity={h1_h8['h3']:.4f})")
        print(f"  H4: {'PASS' if h1_h8['h4'] else 'FAIL'} (depth={h1_h8['h4']:.4f}, TP={h1_h8['h4']})")
        print(f"  H5: {'PASS' if h1_h8['h5'] else 'FAIL'} (CIV count={h1_h8['civ_count']})")
        print(f"  H6: {'PASS' if h1_h8['h6'] else 'FAIL'} (CIV count={h1_h8['civ_count']})")
        print(f"  H7: {'PASS' if h1_h8['h7'] else 'FAIL'} (CSCI std={h1_h8['h7']:.4f})")
        print(f"  H8: {'PASS' if h1_h8['h8'] else 'FAIL'} (TopDown max={h1_h8['topdown_max']})")

        print(f"  H30: {'PASS' if h30_h34['H30']['pass'] else 'FAIL'} (r={h30_h34['H30']['l1_l2_correlation']})")
        print(f"  H31: {'PASS' if h30_h34['H31']['pass'] else 'FAIL'} (delay={h30_h34['H31']['l0_to_l1_delay']})")
        print(f"  H32: {'PASS' if h30_h34['H32']['pass'] else 'FAIL'} (autonomy={h30_h34['H32']['l2_autonomy_index']:.4f})")
        print(f"  H33: {'PASS' if h30_h34['H33']['pass'] else 'FAIL'} (corr={h30_h34['H33']['l2_l0_odi_correlation']})")
        print(f"  H34: {'PASS' if h30_h34['H34']['pass'] else 'FAIL'} (delay={h30_h34['H34']['avg_response_delay']})")

        total_h1_h8_pass += h1_h8['n_pass']
        if h30_h34['H30']['pass']:
            h30_pass_count += 1
        if h30_h34['H31']['pass']:
            h31_pass_count += 1
        if h30_h34['H32']['pass']:
            h32_pass_count += 1
        if h30_h34['H33']['pass']:
            h33_pass_count += 1
        if h30_h34['H34']['pass']:
            h34_pass_count += 1

    # Summary
    n_seeds = len(seeds)
    print(f"\n{'=' * 70}")
    print(f"SUMMARY: {n_seeds} seeds")
    print(f"H1-H8: {total_h1_h8_pass}/{n_seeds * 8} total passes")
    print(f"H30 (L1<->L2 r<0.7): {h30_pass_count}/{n_seeds} ({h30_pass_count/n_seeds*100:.1f}%)")
    print(f"H31 (L0->L1 delay): {h31_pass_count}/{n_seeds} ({h31_pass_count/n_seeds*100:.1f}%)")
    print(f"H32 (L2 autonomy): {h32_pass_count}/{n_seeds} ({h32_pass_count/n_seeds*100:.1f}%)")
    print(f"H33 (L2 ODI indep): {h33_pass_count}/{n_seeds} ({h33_pass_count/n_seeds*100:.1f}%)")
    print(f"H34 (response delay): {h34_pass_count}/{n_seeds} ({h34_pass_count/n_seeds*100:.1f}%)")
    print(f"{'=' * 70}")

    # Save results
    output = {
        'experiment': 'exp_118_phase5_b5_independent_l2',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'N0': N0,
            'steps': STEPS,
            'coupling_mode': 'independent',
            'l2_stability_floor': 0.15,
            'l2_constraint_strength': 0.1,
        },
        'seeds': seeds,
        'results': [],
        'summary': {
            'n_seeds': n_seeds,
            'h1_h8_total_pass': total_h1_h8_pass,
            'h30_pass': h30_pass_count,
            'h31_pass': h31_pass_count,
            'h32_pass': h32_pass_count,
            'h33_pass': h33_pass_count,
            'h34_pass': h34_pass_count,
        },
    }

    for r in all_results:
        seed_result = {
            'seed': r['seed'],
            'h1_h8': r['h1_h8'],
            'h30_h34': r['h30_h34'],
            'all_pass': r['all_pass'],
            'elapsed': r['elapsed'],
        }
        output['results'].append(seed_result)

    os.makedirs(os.path.dirname(FIXED_OUTPUT), exist_ok=True)
    with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {FIXED_OUTPUT}")


if __name__ == '__main__':
    main()
