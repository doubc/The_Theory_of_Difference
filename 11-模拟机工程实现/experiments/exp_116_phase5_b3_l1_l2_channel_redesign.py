"""
experiments/exp_116_phase5_b3_l1_l2_channel_redesign.py

Phase 5 Track B3: L1→L2 信息通道重构 — 噪声注入 + 层内自生动力学

Purpose: Address B2 failures by redesigning the L1→L2 information channel
    with (1) stronger combined noise (absolute + relative), (2) lower
    attenuation, (3) L2 autonomous decay, and (4) intrinsic L2 perturbation.

Background:
  exp_115 (Track B2) found that serial coupling alone was insufficient:
    - H30 (L1↔L2 r < 0.7): 1/8 pass, mean r = 0.86
    - H31 (hierarchical delay): 0/8 detected L0->L1 delay
    - H8 (TopDown): 0/8 activated

  Root causes identified:
    1. Noise (0.05) too weak relative to L1 signal (~0.61 stability)
    2. Attenuation (0.7) too high — L2 still mirrors L1
    3. L2 completely passive — no intrinsic dynamics
    4. L1 self-stabilization suppresses L0->L1 signal

Method:
  - 8 seeds (same as B1/B2 for direct comparison)
  - Single config: B3 serial coupling with enhanced parameters
  - Total: 8 seeds x 1 config = 8 runs
  - Architecture: CSC(serial, B3)+NSE+LNT (no AMC/ILP)

B3 Parameter Changes vs B2:
  | Parameter                      | B2     | B3     | Change    |
  | serial_l1_to_l2_attenuation    | 0.7    | 0.3    | ↓ 57%     |
  | serial_l1_to_l2_noise          | 0.05   | 0.1+0.3| ↑ 6x      |
  | serial_l1_to_l2_odi_factor     | 0.8    | 0.5    | ↓ 37.5%   |
  | serial_l2_intrinsic_perturb_*  | —      | 0.02   | 新增      |
  | serial_l2_autonomous_decay     | —      | 0.98   | 新增      |

Hypotheses:
  H30 (layer decoupling): L1↔L2 NSI Pearson r < 0.7
      B2: 1/8 (12.5%), mean r = 0.86
      B3 target: ≥ 5/8 (62.5%)

  H31 (hierarchical delay): L0->L1 delay detected
      B2: 0/8 detected
      B3 target: ≥ 4/8 detected

  H32 (L2 autonomy): L2 narrative differs from L1 narrative
      New hypothesis: L2 autonomy index (1 - narrative similarity) > 0.3
      Target: ≥ 5/8 seeds pass

  Also tracks H1-H8 (baseline) to verify B3 doesn't break core dynamics.

Invoke modes:
  Batch:  python exp_116_phase5_b3_l1_l2_channel_redesign.py
  Single: python exp_116_phase5_b3_l1_l2_channel_redesign.py <seed>
"""

import sys
import os
import gc
import time
import json
import glob
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
from engine.layer_narrative_tracker import (
    LayerNarrativeTracker, DEFAULT_LAYER_NARRATIVE_CONFIG,
)


# ─── 8 baseline seeds (same as B1/B2) ───
ALL_SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]

# ─── P5 Track B3: Serial CSC config (B3 redesign) ───
P5_B3_SERIAL_CSC_CONFIG = {
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
    # ── Track B2: Serial coupling base ──
    'coupling_mode': 'serial',
    'serial_l1_to_l2_delay': 15,
    # ── Track B3: Enhanced L1→L2 channel ──
    'serial_l1_to_l2_attenuation': 0.3,        # B3: 0.7→0.3 (大幅降低镜像)
    'serial_l1_to_l2_noise_abs': 0.1,           # B3: 绝对噪声基底
    'serial_l1_to_l2_noise_rel': 0.3,           # B3: 相对噪声（L1 信号强度的 30%）
    'serial_l1_to_l2_odi_factor': 0.5,          # B3: L2 ODI 额外衰减（B2 为 0.8）
    # ── Track B3: L2 层内自生动力学 ──
    'serial_l2_intrinsic_perturbation_rate': 0.02,
    'serial_l2_intrinsic_perturbation_magnitude': 0.15,
    'serial_l2_autonomous_decay': 0.98,
    # ── Track B3: L0->L1 信号增强 ──
    'serial_l0_to_l1_signal_weight': 0.4,
}

# ─── Experiment parameters ───
N0 = 72
STEPS = 2000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.5

FIXED_OUTPUT = os.path.join(
    PROJECT_ROOT, 'experiments',
    'exp_116_b3_results.json')


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


class CIVRateLimiterV2P1F(CIVRateLimiter):
    def __init__(self):
        super().__init__(window_size=50, max_civ_rate=0.12, cooldown_steps=12)
        self.min_civ_guarantee = 3

    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            if self._total_civ_seen < self.min_civ_guarantee:
                return level
            if self.should_downgrade(step):
                self._total_downgrades += 1
                return NarrativeLevel.INSTITUTIONAL
        return level


class MomentumNarrativeOperatorV4P1F(NarrativeRecursionOperator):
    def __init__(self):
        from models.narrative_self import NarrativeFilter, NarrativeNamer
        from models.narrative_self import NarrativeActionizer, NarrativeVerifier
        self.filter = NarrativeFilter(magnitude_threshold=0.02)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(
            strength_threshold=0.1, momentum_decay=0.95, momentum_bonus=0.3)
        self.actionizer = NarrativeActionizer(bias_dimension=128)
        self.verifier = NarrativeVerifier(consistency_threshold=0.3)
        self.narrative_decay_rate = 0.9
        self._records = []
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F()

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


def build_evolver(N0, steps, sample_interval, gbc_soft_nudge, seed):
    """Build HierarchicalEvolver with CSC(serial, B3)+NSE+LNT."""
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

    # Track B3: Serial CSC with B3 parameters
    csc = CrossScaleCoupling(config=dict(P5_B3_SERIAL_CSC_CONFIG))

    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {
        'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    # Track B3: LayerNarrativeTracker
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
    """Extract metrics from step results (same as exp_115)."""
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
    from math import isnan
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


def evaluate_h30_h31_b3(lnt, step_results):
    """Evaluate H30 (L1-L2 decoupling) and H31 (hierarchical delay) for B3."""
    h28_result = lnt.get_inter_layer_correlation()
    h29_result = lnt.get_conduction_delay()

    # H30: L1↔L2 correlation < 0.7
    l1_l2_corr = h28_result.pairwise_correlations.get(
        'INSTITUTIONAL→CIVILIZATION', None)
    if l1_l2_corr is None:
        l1_l2_corr = h28_result.pairwise_correlations.get(
            'CIVILIZATION→INSTITUTIONAL', 0.0)
    h30_pass = l1_l2_corr is not None and abs(l1_l2_corr) < 0.7

    # H31: L0->L1 delay detected
    l0_l1 = h29_result.l0_to_l1_delay
    l1_l2 = h29_result.l1_to_l2_delay
    l0_l2 = h29_result.l0_to_l2_delay
    h31_pass = l0_l1 is not None and l0_l1 > 0

    # H32: L2 autonomy from narrative histories
    all_nsi_histories = lnt.get_all_nsi_histories()
    layer_activity = lnt.get_layer_activity_profile()
    all_pairwise = h28_result.pairwise_correlations

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
            'passing': None,  # computed separately
            'layer_activity': layer_activity,
        },
        'all_pairwise_correlations': all_pairwise,
        'layer_nsi_histories': {k: list(v) if hasattr(v, '__iter__') else v for k, v in all_nsi_histories.items()},
    }


def run_seed(seed):
    """Run a single seed with B3 serial CSC and evaluate H30-H32."""
    print(f"\n{'='*60}")
    print(f"  exp_116 Track B3 | Seed {seed} | N0={N0} | Steps={STEPS}")
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

    # Track B3 metrics (H30-H32)
    lnt = ev._lnt
    b3_metrics = evaluate_h30_h31_b3(lnt, step_results)

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
    b3_metrics['H32']['passing'] = h32_pass
    b3_metrics['H32']['autonomy_index'] = l2_autonomy_index
    b3_metrics['H32']['narrative_similarity'] = narrative_similarity
    b3_metrics['H32']['inst_narratives'] = list(inst_narratives)
    b3_metrics['H32']['civ_narratives'] = list(civ_narratives)

    # Per-layer NSI stats
    all_nsi = b3_metrics['layer_nsi_histories']
    inst_hist = all_nsi.get('INSTITUTIONAL', [])
    civ_hist = all_nsi.get('CIVILIZATION', [])
    mini_hist = all_nsi.get('MINI', [])

    return {
        'seed': seed,
        'config': 'B3_serial_enhanced',
        'elapsed_seconds': elapsed,
        'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'h1h8': h1h8,
        'h30_pass': b3_metrics['H30']['passing'],
        'h30_l1_l2_corr': b3_metrics['H30']['l1_l2_correlation'],
        'h31_pass': b3_metrics['H31']['passing'],
        'h31_l0_l1_delay': b3_metrics['H31']['l0_l1_delay'],
        'h31_l1_l2_delay': b3_metrics['H31']['l1_l2_delay'],
        'h31_l0_l2_delay': b3_metrics['H31']['l0_l2_delay'],
        'h32_pass': h32_pass,
        'h32_l2_autonomy_index': l2_autonomy_index,
        'h32_narrative_similarity': narrative_similarity,
        'h32_inst_narratives': list(inst_narratives),
        'h32_civ_narratives': list(civ_narratives),
        'all_pairwise_correlations': b3_metrics['all_pairwise_correlations'],
        'inst_nsi_mean': float(np.mean(inst_hist)) if inst_hist else 0,
        'inst_nsi_std': float(np.std(inst_hist)) if inst_hist else 0,
        'inst_nsi_max': float(np.max(inst_hist)) if inst_hist else 0,
        'civ_nsi_mean': float(np.mean(civ_hist)) if civ_hist else 0,
        'civ_nsi_std': float(np.std(civ_hist)) if civ_hist else 0,
        'civ_nsi_max': float(np.max(civ_hist)) if civ_hist else 0,
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
        print(f"  H30 (L1<->L2 r): {result['h30_l1_l2_corr']:.4f} {h30_status}")
        print(f"  H31 (L0->L1 delay): {result['h31_l0_l1_delay']} {h31_status}")
        print(f"  H32 (L2 autonomy): {result['h32_l2_autonomy_index']:.3f} {h32_status}")
        passed = [k for k in ['h1','h2','h3','h4','h5','h6','h7','h8'] if result['h1h8'].get(k, False)]
        print(f"  H1-H8: {passed} ({len(passed)}/8)")

    # Aggregate
    if all_results:
        h30_pass_count = sum(1 for r in all_results if r['h30_pass'])
        h31_pass_count = sum(1 for r in all_results if r['h31_pass'])
        h32_pass_count = sum(1 for r in all_results if r['h32_pass'])
        h30_mean_r = np.mean([r['h30_l1_l2_corr'] for r in all_results])
        h30_std_r = np.std([r['h30_l1_l2_corr'] for r in all_results])

        print(f"\n{'='*60}")
        print(f"  exp_116 Track B3 — Aggregate Results ({len(all_results)} seeds)")
        print(f"{'='*60}")
        print(f"  H30: {h30_pass_count}/{len(all_results)} pass | mean r = {h30_mean_r:.4f} ± {h30_std_r:.4f}")
        print(f"  H31: {h31_pass_count}/{len(all_results)} pass (L0->L1 delay detected)")
        print(f"  H32: {h32_pass_count}/{len(all_results)} pass (L2 autonomy > 0.3)")

    # Save results
    os.makedirs(os.path.dirname(FIXED_OUTPUT), exist_ok=True)
    with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to: {FIXED_OUTPUT}")


if __name__ == '__main__':
    main()
