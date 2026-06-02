# -*- coding: utf-8 -*-
"""
experiments/exp_117_phase5_b4_constraint_conduction.py

Phase 5 Track B4: 层间约束传导 (Constraint Conduction)

Purpose: Replace "state derivation" (B1-B3) with "constraint conduction"
    - L2 has INDEPENDENT clustering from L0 (not derived from L1)
    - L1 provides SOFT BOUNDARY constraints (clamp), not hard derivation
    - L2 has its own difference field and dynamics

Background:
  B1 (parallel): L1<->L2 r = 0.976 — perfect correlation, no decoupling
  B2 (serial):   L1<->L2 r = 0.861 — slight improvement, still too high
  B3 (noise):    L1<->L2 r = 0.937 — actually WORSE, noise insufficient

  Root cause: All three modes are "state derivation" — L2 state is a function
  of L1 state. Noise can add variance but cannot break structural correlation.

  B4 design philosophy:
  - L2 clusters independently from L0 (different N0 or same N0 but independent)
  - L1 provides constraints as soft boundaries: L2 in [L1*(1-tol), L1*(1+tol)]
  - L2 autonomous dynamics + L0 direct input + L1 constraint = final L2

Hypotheses:
  H30 (layer decoupling): L1<->L2 NSI Pearson r < 0.7
      B1: 0/8, B2: 1/8, B3: 0/8
      B4 target: >= 5/8 (62.5%)

  H31 (hierarchical delay): L0->L1 delay detected
      B1: N/A, B2: 0/8, B3: 0/8
      B4 target: >= 4/8 detected

  H32 (L2 autonomy): L2 narrative differs from L1 narrative
      B1-B3: 0/8 (both silent)
      B4 target: >= 5/8 (autonomy index > 0.3)

  H33 (independent clustering): L2 ODI vs L1 ODI correlation < 0.8
      New: measures whether L2 has independent clustering structure
      Target: >= 5/8 pass

  H34 (constraint response delay): Average L2 response to L1 constraint > 5 steps
      New: measures the lag between L1 change and L2 response
      Target: >= 4/8 detected

  Also tracks H1-H8 baseline to verify B4 doesn't break core dynamics.

Invoke modes:
  Batch:  python exp_117_phase5_b4_constraint_conduction.py
  Single: python exp_117_phase5_b4_constraint_conduction.py <seed>
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


# ─── 8 baseline seeds (same as B1/B2/B3) ───
ALL_SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]

# ─── P5 Track B4: Constraint Conduction CSC config ───
P5_B4_CONSTRAINT_CSC_CONFIG = {
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
    # ── Track B4: Constraint Conduction Mode ──
    'coupling_mode': 'constraint',
    'l2_N0': 72,
    'constraint_stability_weight': 0.2,
    'constraint_activity_weight': 0.15,
    'constraint_structure_weight': 0.1,
    'constraint_tolerance': 0.3,
    'l0_direct_to_l2_weight': 0.4,
    'l0_to_l1_signal_weight': 0.5,
    'l1_autonomous_stability_weight': 0.5,
    'l0_to_l1_response_delay': 10,
    'l2_narrative_threshold': 0.01,
    'constraint_response_tracking_window': 200,
}

# ─── Experiment parameters ───
N0 = 72
STEPS = 2000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.5

FIXED_OUTPUT = os.path.join(
    PROJECT_ROOT, 'experiments',
    'exp_117_b4_results.json')


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
        # 1. Filter signals
        significant, discarded = self.filter.filter(signals, timestamp)
        if not significant:
            return None

        # 2. Name narratives
        nodes = self.namer.name(significant, timestamp)
        if not nodes:
            return None

        # 3. Connect (momentum connector)
        chains = self.connector.connect(nodes, timestamp)
        if not chains:
            return None

        # 4. Actionize
        node_dict = {n.node_id: n for n in nodes}
        actions = self.actionizer.actionize(chains, node_dict, timestamp)
        if not actions:
            return None

        # 4b. Rate limit CIV
        for a in actions:
            a.narrative_level = self.civ_rate_limiter.maybe_downgrade(
                a.narrative_level, timestamp)

        # 5. Record narrative event (simplified - no verifier)
        self._record_count += 1
        self._total_actions += len(actions)
        self._validated_actions += len(actions)
        
        # Determine highest narrative level from actions
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

        # Update bias
        total = sum(a.action_strength for a in actions)
        if total > 0:
            direction = sum(a.bias_correction for a in actions) / total
            correction = direction * self.narrative_decay_rate
            return correction

        return None

    def get_narrative_history(self, n=10):
        """Get recent N narrative event records."""
        recent = list(self._records)[-n:]
        return [
            {
                'record_id': r.record_id,
                'timestamp': r.timestamp,
                'narrative_level': r.narrative_level.name,
                'n_input_signals': len(r.input_signals),
                'n_filtered_signals': len(r.filtered_signals),
                'n_causal_chains': len(r.causal_chains),
                'n_actions': len(r.actions),
                'verification_result': r.verification_result,
                'verification_score': r.verification_score,
            }
            for r in recent
        ]

    def get_summary(self):
        return {
            'n_records': self._record_count,
            'total_actions': self._total_actions,
            'validated_actions': self._validated_actions,
            'civ_limiter': self.civ_rate_limiter.get_summary(),
        }


def build_evolver(N0, steps, sample_interval, gbc_soft_nudge, seed):
    """Build HierarchicalEvolver with CSC(constraint, B4)+NSE+LNT."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    odi = OrganizationalDensityIndex(
        temporal_window=10, densification_threshold=0.005, use_refined_zones=True)
    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40, l2_stability_threshold=0.55)
    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True)
    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3, 'history_window': 8,
        'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8,
        'self_reference_threshold': 0.05,
        'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20,
        'msi_emergence_threshold': 0.35,
        'min_active_conditions': 1})
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5, balance_threshold=0.3,
        min_mechanisms_required=4, geometric_weighting=True)
    narrative = MomentumNarrativeOperatorV4P1F()
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01})
    counterfactual = CounterfactualEngine(
        config={'divergence_threshold': 0.1, 'max_branches': 4})
    six_threshold = SixThresholdDetector()

    # Track B4: Constraint CSC with B4 parameters
    csc = CrossScaleCoupling(config=dict(P5_B4_CONSTRAINT_CSC_CONFIG))

    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {
        'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    # Track B4: LayerNarrativeTracker
    lnt = LayerNarrativeTracker(config=dict(P5_LNT_CONFIG))

    ev = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=1, p1_eval_interval=sample_interval,
        phase2_verbose=False, phase3_verbose=False, phase4_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi,
        six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism,
        return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity,
        minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory,
        counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative,
        global_bias_constraint=gbc,
        gbc_soft_nudge=gbc_soft_nudge,
        cross_scale_coupling=csc,
        narrative_self_emergence=nse,
        adaptive_momentum_controller=None,
        institutional_layer_protector=None,
        layer_narrative_tracker=lnt)
    ev._lnt = lnt
    return ev


def extract_step_metrics(step_results):
    """Extract metrics from step results."""
    metrics = {
        'nsi_vals': [], 'nsi_active': [], 'continuity_vals': [],
        'depth_vals': [], 'tp_vals': [], 'csci_vals': [],
        'td_vals': [], 'civ_events': [],
    }
    for sr in step_results:
        nse = sr.get('narrative_self_emergence', {})
        if nse:
            metrics['nsi_vals'].append(nse.get('nsi', 0.0))
            metrics['nsi_active'].append(nse.get('nsi_active', False))
            metrics['continuity_vals'].append(nse.get('continuity_score', 0.0))
            metrics['depth_vals'].append(nse.get('self_history_depth', 0.0))
            metrics['tp_vals'].append(nse.get('n_turning_points', 0))
        csc = sr.get('cross_scale_coupling', {})
        if csc:
            metrics['csci_vals'].append(csc.get('csci', 0.0))
            metrics['td_vals'].append(csc.get('topdown_n_active', 0))
        narr_info = sr.get('narrative_recursion', {})
        if narr_info:
            level = narr_info.get('narrative_level', 'MINI')
            metrics['civ_events'].append(
                1 if level == 'CIVILIZATION' else 0)
    return metrics


def evaluate_h1h8(metrics):
    """Evaluate H1-H8 from extracted metrics."""
    def safe_mean(vals):
        return float(np.mean(vals)) if vals else 0.0
    def safe_max(vals):
        return float(np.max(vals)) if vals else 0.0
    def safe_std(vals):
        return float(np.std(vals)) if vals else 0.0

    nsi_max = safe_max(metrics['nsi_vals'])
    nsi_active_rate = safe_mean(metrics['nsi_active'])
    continuity_mean = safe_mean(metrics['continuity_vals'])
    history_depth_mean = safe_mean(metrics['depth_vals'])
    turning_points = metrics['tp_vals'][-1] if metrics['tp_vals'] else 0
    civ_count = sum(metrics['civ_events'])
    csci_std = safe_std(metrics['csci_vals'])
    topdown_max = int(safe_max(metrics['td_vals']))

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


def evaluate_h30_h34(lnt, step_results, csc_summary):
    """Evaluate H30-H34 for B4 constraint conduction."""
    h28_result = lnt.get_inter_layer_correlation()
    h29_result = lnt.get_conduction_delay()

    # H30: L1<->L2 correlation < 0.7
    l1_l2_corr = h28_result.pairwise_correlations.get(
        'INSTITUTIONAL->CIVILIZATION', None)
    if l1_l2_corr is None:
        l1_l2_corr = h28_result.pairwise_correlations.get(
            'CIVILIZATION->INSTITUTIONAL', 0.0)
    h30_pass = l1_l2_corr is not None and abs(l1_l2_corr) < 0.7

    # H31: L0->L1 delay detected
    l0_l1 = h29_result.l0_to_l1_delay
    l1_l2 = h29_result.l1_to_l2_delay
    l0_l2 = h29_result.l0_to_l2_delay
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

    # H33: L2 independent clustering — L2 ODI vs L1 ODI correlation < 0.8
    # Extract L1 and L2 ODI time series from step results
    l1_odi_vals = []
    l2_odi_vals = []
    for sr in step_results:
        l1_odi = sr.get('institutional_protector', {}).get('current_odi', None)
        if l1_odi is None:
            l1_odi = sr.get('odi', None)
        if l1_odi is not None:
            l1_odi_vals.append(l1_odi)
        # L2 ODI from constraint conduction
        cc = sr.get('cross_scale_coupling', {}).get('constraint_conduction', {})
        if cc:
            l2_odi = cc.get('latest_state', {}).get('l2_independent_odi', None)
            if l2_odi is not None:
                l2_odi_vals.append(l2_odi)

    h33_pass = False
    l2_l1_odi_corr = None
    if len(l1_odi_vals) >= 30 and len(l2_odi_vals) >= 30:
        min_len = min(len(l1_odi_vals), len(l2_odi_vals))
        l1_arr = np.array(l1_odi_vals[-min_len:])
        l2_arr = np.array(l2_odi_vals[-min_len:])
        l2_l1_odi_corr = float(np.corrcoef(l1_arr, l2_arr)[0, 1])
        h33_pass = abs(l2_l1_odi_corr) < 0.8

    # H34: Constraint response delay > 5 steps
    cc_summary = csc_summary.get('constraint_conduction', {})
    avg_delay = cc_summary.get('avg_response_delay', 0.0)
    n_response_events = cc_summary.get('n_response_events', 0)
    h34_pass = avg_delay > 5.0 and n_response_events >= 3

    return {
        'H30': {
            'passing': h30_pass,
            'l1_l2_correlation': float(l1_l2_corr) if l1_l2_corr is not None else None,
        },
        'H31': {
            'passing': h31_pass,
            'l0_l1_delay': l0_l1,
            'l1_l2_delay': l1_l2,
            'l0_l2_delay': l0_l2,
        },
        'H32': {
            'passing': h32_pass,
            'autonomy_index': l2_autonomy_index,
            'narrative_similarity': narrative_similarity,
            'inst_narratives': list(inst_narratives),
            'civ_narratives': list(civ_narratives),
        },
        'H33': {
            'passing': h33_pass,
            'l2_l1_odi_correlation': l2_l1_odi_corr,
            'l1_odi_samples': len(l1_odi_vals),
            'l2_odi_samples': len(l2_odi_vals),
        },
        'H34': {
            'passing': h34_pass,
            'avg_response_delay': avg_delay,
            'n_response_events': n_response_events,
        },
        'all_pairwise_correlations': h28_result.pairwise_correlations,
        'constraint_conduction_summary': cc_summary,
    }


def run_seed(seed):
    """Run a single seed with B4 constraint conduction CSC and evaluate H30-H34."""
    print(f"\n{'='*60}")
    print(f"  exp_117 Track B4 | Seed {seed} | N0={N0} | Steps={STEPS}")
    print(f"  Mode: constraint conduction (L2 independent + L1 soft boundary)")
    print(f"{'='*60}")

    ev = build_evolver(N0, STEPS, SAMPLE_INTERVAL, GBC_SOFT_NUDGE, seed)

    t0 = time.time()
    result = ev.run(verbose=False)
    elapsed = time.time() - t0

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])

    print(f"  Completed in {elapsed:.1f}s ({len(step_results)} steps)")

    # Base metrics (H1-H8)
    metrics = extract_step_metrics(step_results)
    h1h8 = evaluate_h1h8(metrics)

    # Track B4 metrics (H30-H34)
    lnt = ev._lnt
    csc = ev.cross_scale_coupling
    csc_summary = csc.get_summary() if csc else {}
    b4_metrics = evaluate_h30_h34(lnt, step_results, csc_summary)

    # Per-layer NSI stats
    all_nsi = b4_metrics.get('all_pairwise_correlations', {})
    layer_nsi_histories = lnt.get_all_nsi_histories() if lnt else {}
    inst_hist = layer_nsi_histories.get('INSTITUTIONAL', [])
    civ_hist = layer_nsi_histories.get('CIVILIZATION', [])
    mini_hist = layer_nsi_histories.get('MINI', [])

    return {
        'seed': seed,
        'config': 'B4_constraint_conduction',
        'elapsed_seconds': elapsed,
        'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'h1h8': h1h8,
        'h30_pass': b4_metrics['H30']['passing'],
        'h30_l1_l2_corr': b4_metrics['H30']['l1_l2_correlation'],
        'h31_pass': b4_metrics['H31']['passing'],
        'h31_l0_l1_delay': b4_metrics['H31']['l0_l1_delay'],
        'h31_l1_l2_delay': b4_metrics['H31']['l1_l2_delay'],
        'h31_l0_l2_delay': b4_metrics['H31']['l0_l2_delay'],
        'h32_pass': b4_metrics['H32']['passing'],
        'h32_l2_autonomy_index': b4_metrics['H32']['autonomy_index'],
        'h32_narrative_similarity': b4_metrics['H32']['narrative_similarity'],
        'h32_inst_narratives': b4_metrics['H32']['inst_narratives'],
        'h32_civ_narratives': b4_metrics['H32']['civ_narratives'],
        'h33_pass': b4_metrics['H33']['passing'],
        'h33_l2_l1_odi_corr': b4_metrics['H33']['l2_l1_odi_correlation'],
        'h34_pass': b4_metrics['H34']['passing'],
        'h34_avg_delay': b4_metrics['H34']['avg_response_delay'],
        'h34_n_events': b4_metrics['H34']['n_response_events'],
        'constraint_conduction': b4_metrics['constraint_conduction_summary'],
        'inst_nsi_mean': float(np.mean(inst_hist)) if inst_hist else 0,
        'inst_nsi_std': float(np.std(inst_hist)) if inst_hist else 0,
        'civ_nsi_mean': float(np.mean(civ_hist)) if civ_hist else 0,
        'civ_nsi_std': float(np.std(civ_hist)) if civ_hist else 0,
        'civ_count': h1h8['civ_count'],
        'topdown_max': h1h8['topdown_max'],
    }


def main():
    seeds = [int(s) for s in sys.argv[1:]] if len(sys.argv) > 1 else ALL_SEEDS

    all_results = []
    for seed in seeds:
        result = run_seed(seed)
        all_results.append(result)

        # Print summary
        print(f"\n  --- Seed {seed} Summary ---")
        h30_status = 'PASS' if result['h30_pass'] else 'FAIL'
        h31_status = 'PASS' if result['h31_pass'] else 'FAIL'
        h32_status = 'PASS' if result['h32_pass'] else 'FAIL'
        h33_status = 'PASS' if result['h33_pass'] else 'FAIL'
        h34_status = 'PASS' if result['h34_pass'] else 'FAIL'
        print(f"  H30 (L1<->L2 r): {result['h30_l1_l2_corr']:.4f} {h30_status}")
        print(f"  H31 (L0->L1 delay): {result['h31_l0_l1_delay']} {h31_status}")
        print(f"  H32 (L2 autonomy): {result['h32_l2_autonomy_index']:.3f} {h32_status}")
        h33_corr = result['h33_l2_l1_odi_corr']
        h33_corr_str = f"{h33_corr:.4f}" if h33_corr is not None else "N/A"
        print(f"  H33 (L2 ODI indep): {h33_corr_str} {h33_status}")
        print(f"  H34 (response delay): {result['h34_avg_delay']:.1f} ({result['h34_n_events']} events) {h34_status}")
        passed = [k for k in ['h1','h2','h3','h4','h5','h6','h7','h8'] if result['h1h8'].get(k, False)]
        print(f"  H1-H8: {passed} ({len(passed)}/8)")

    # Aggregate
    if all_results:
        h30_pass_count = sum(1 for r in all_results if r['h30_pass'])
        h31_pass_count = sum(1 for r in all_results if r['h31_pass'])
        h32_pass_count = sum(1 for r in all_results if r['h32_pass'])
        h33_pass_count = sum(1 for r in all_results if r['h33_pass'])
        h34_pass_count = sum(1 for r in all_results if r['h34_pass'])
        h30_mean_r = np.mean([r['h30_l1_l2_corr'] for r in all_results if r['h30_l1_l2_corr'] is not None])
        h30_std_r = np.std([r['h30_l1_l2_corr'] for r in all_results if r['h30_l1_l2_corr'] is not None])

        print(f"\n{'='*60}")
        print(f"  exp_117 Track B4 — Aggregate Results ({len(all_results)} seeds)")
        print(f"{'='*60}")
        print(f"  H30: {h30_pass_count}/{len(all_results)} pass | mean r = {h30_mean_r:.4f} +/- {h30_std_r:.4f}")
        print(f"  H31: {h31_pass_count}/{len(all_results)} pass (L0->L1 delay detected)")
        print(f"  H32: {h32_pass_count}/{len(all_results)} pass (L2 autonomy > 0.3)")
        print(f"  H33: {h33_pass_count}/{len(all_results)} pass (L2 ODI indep < 0.8)")
        print(f"  H34: {h34_pass_count}/{len(all_results)} pass (response delay > 5)")

        # Compare with B1/B2/B3
        print(f"\n  --- Historical Comparison ---")
        print(f"  B1 (parallel): H30 = 0/8 (r=0.976)")
        print(f"  B2 (serial):   H30 = 1/8 (r=0.861)")
        print(f"  B3 (noise):    H30 = 0/8 (r=0.937)")
        print(f"  B4 (constraint): H30 = {h30_pass_count}/{len(all_results)} (r={h30_mean_r:.4f})")

    # Save results
    os.makedirs(os.path.dirname(FIXED_OUTPUT), exist_ok=True)
    with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to: {FIXED_OUTPUT}")


if __name__ == '__main__':
    main()
