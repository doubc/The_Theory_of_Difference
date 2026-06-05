"""
experiments/exp_147_p3_phase_transition_scan.py

Phase 9 P3: High-Resolution Phase Transition Scan at N0 ~ 30

Purpose:
  exp_145 revealed a striking non-monotonic structure in the L1 formation
  boundary (P3-A):
    N0:  24  26  28  30  32  34  36
    L1:   0   0   0  15   1   1  16   (out of 16 seeds)

  The sharp peak at N0=30 (15/16) surrounded by suppression at 32-34 (1/16)
  is NOT a simple percolation threshold. This experiment performs a
  step-1 scan from N0=26 to 34 to resolve the fine structure of this
  transition and determine whether:

  (a) N0=30 is a sharp resonance (symmetry breaking at a critical point),
  (b) The transition has sub-structure (multiple critical points),
  (c) The suppression at 32-34 is a finite-size artifact.

  This is a phase transition in the symmetry breaking sense (破缺): the
  system transitions from a symmetric phase (no L1, disordered) to a
  broken-symmetry phase (L1 formed, ordered). This is distinct from
  "最近稳态" (nearest steady state) and "最小变易" (minimal variation) --
  it is a qualitative structural change at a critical parameter value.

Config:
  N0 = [26, 27, 28, 29, 30, 31, 32, 33, 34]  # 9 points, step 1
  seeds = 16 per point
  Total runs: 9 * 16 = 144
  max_steps = 2000
  max_layers = 2
  partial_sealing = True

Metrics per N0:
  - L1 formation rate (out of 16 seeds)
  - Mean and std of seal step (for seeds that form L1)
  - Mean seal ratio (from PerLayerMetricsCollector)
  - Average binding strength
  - Number of organizations (clusters)
  - Number of layers formed
  - Finite-size scaling sharpness estimate
"""

import sys, os, time, json
from datetime import datetime
from collections import OrderedDict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')
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
    NarrativeRecursionOperator, NarrativeLevel,
    AdaptiveMomentumConnector, CIVRateLimiter,
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
from engine.narrative_recursive_closure import NarrativeRecursiveClosure
from engine.civ_floor import NarrativeLevelBooster
from engine.per_layer_metrics import PerLayerMetricsCollector


# ── Phase 9 Baseline Config ────────────────────────────────────────────

P9_CSC_CONFIG = {
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
    'l2_stability_floor': 0.15,
}


# ── Narrative Operator (same as exp_145) ───────────────────────────────

class CIVRateLimiterV2P3Scan(CIVRateLimiter):
    """Ensures at least min_civ_guarantee CIV events."""
    def __init__(self, window_size=50, max_civ_rate=0.12,
                 cooldown_steps=12, min_civ_guarantee=3):
        super().__init__(
            window_size=window_size, max_civ_rate=max_civ_rate,
            cooldown_steps=cooldown_steps,
        )
        self.min_civ_guarantee = min_civ_guarantee

    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            if self._total_civ_seen < self.min_civ_guarantee:
                return level
            if self.should_downgrade(step):
                self._total_downgrades += 1
                return NarrativeLevel.INSTITUTIONAL
        return level


class MomentumNarrativeOperatorV4P3Scan(NarrativeRecursionOperator):
    """Momentum-based narrative evolution (Phase 9 baseline)."""
    def __init__(self, bias_dimension=128, filter_magnitude_threshold=0.02,
                 connector_strength_threshold=0.1,
                 verifier_consistency_threshold=0.3,
                 narrative_decay_rate=0.9, momentum_decay=0.95,
                 momentum_bonus=0.3):
        from models.narrative_self import (
            NarrativeFilter, NarrativeNamer, NarrativeActionizer,
            NarrativeVerifier,
        )
        self.filter = NarrativeFilter(
            magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(
            strength_threshold=connector_strength_threshold,
            momentum_decay=momentum_decay, momentum_bonus=momentum_bonus)
        self.actionizer = NarrativeActionizer(
            bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(
            consistency_threshold=verifier_consistency_threshold)
        self.narrative_decay_rate = narrative_decay_rate
        self._records = []
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P3Scan(
            window_size=50, max_civ_rate=0.12, cooldown_steps=12,
            min_civ_guarantee=3)

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


# ── Experiment Config ──────────────────────────────────────────────────

N0_SWEEP = [26, 27, 28, 29, 30, 31, 32, 33, 34]
SEEDS = [42, 142, 242, 342, 442, 542, 642, 742,
         842, 942, 1042, 1142, 1242, 1342, 1442, 1542]
STEPS = 2000
SI = 10
GSN = 0.2
ML = 2


# ── Seal Step Estimation ──────────────────────────────────────────────

def estimate_first_seal_step(layer_results, target_layer=1):
    """Estimate the first step where L1 sealing occurred."""
    if target_layer < len(layer_results):
        lr = layer_results[target_layer]
        if lr.get('sealed', False):
            sr = lr.get('phase2_step_results', [])
            for i, step in enumerate(sr):
                unseal = step.get('unsealing', {})
                if unseal.get('level', 0) >= 3:
                    return i * 10
            return 0
    return -1


# ── Single Seed Runner ─────────────────────────────────────────────────

def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    max_layers=2):
    """Run one seed with full Phase 9 architecture at given N0.

    Returns dict with:
      - l1_formed (bool)
      - seal_step (int, -1 if not sealed)
      - seal_ratio (float, mean L1 sealing ratio)
      - n_layers (int)
      - n_organizations (int, clusters at final state)
      - avg_binding (float, mean abs binding strength)
      - nsi_max, civ_max, odi_max
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    csc_config = dict(P9_CSC_CONFIG)

    rfc = ReturnFlowChannel(
        anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    us = UnsealingMechanism(
        l1_coupling_threshold=0.008,
        l1_stability_threshold=0.02,
        l2_coupling_threshold=0.04,
        l2_stability_threshold=0.08)
    psc = PreSubjectivityConvergence(
        coupling_threshold=0.25, stability_threshold=0.40,
        dynamic_threshold=True)
    odi = OrganizationalDensityIndex(
        temporal_window=10, densification_threshold=0.005,
        use_refined_zones=True)
    msi = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35,
        'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3,
        'history_window': 8, 'history_dependency_threshold': 0.15,
        'min_history_depth': 5,
        'self_reference_window': 8, 'self_reference_threshold': 0.05,
        'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20,
        'msi_emergence_threshold': 0.35, 'min_active_conditions': 1})
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5, balance_threshold=0.3,
        min_mechanisms_required=4, geometric_weighting=True)
    nro = MomentumNarrativeOperatorV4P3Scan(
        bias_dimension=128, filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1,
        verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3)
    abe = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01})
    cfe = CounterfactualEngine(
        config={'divergence_threshold': 0.1, 'max_branches': 4})
    std = SixThresholdDetector()
    csc = CrossScaleCoupling(config=csc_config)
    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg.update({
        'history_multi_signal': True,
        'history_second_deriv_threshold': 0.02,
        'history_signal_weights': {
            'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1,
        },
        'history_max_turning_points': 25,
    })
    nse = NarrativeSelfEmergence(config=nse_cfg)
    nrc = NarrativeRecursiveClosure(
        event_window=20, collapse_threshold=0.15, settling_rate=0.3,
        r0_weight=0.4, r1_weight=0.35, r2_weight=0.25,
        r2_threshold_nsi=0.85, r2_cooldown=200,
        r2_tension_threshold=1.0, r2_use_tension=True, verbose=False)
    booster = NarrativeLevelBooster(min_civ=3)
    collector = PerLayerMetricsCollector(
        config={
            'nsi_rolling_window': 500, 'civ_rolling_window': 500,
            'theme_jaccard_window': 500,
        })

    evolver = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=max_layers,
        partial_sealing=True,  # Track B7: partial sealing mode
        p1_eval_interval=sample_interval,
        phase2_verbose=False, phase3_verbose=False, phase4_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi,
        six_threshold_detector=std,
        unsealing_mechanism=us,
        return_flow_channel=rfc,
        pre_subjectivity_convergence=psc,
        minimal_self_detector=msi,
        anticipatory_bias_engine=abe,
        counterfactual_engine=cfe,
        narrative_recursion_operator=nro,
        global_bias_constraint=gbc,
        gbc_soft_nudge=gbc_soft_nudge,
        cross_scale_coupling=csc,
        narrative_self_emergence=nse,
        adaptive_momentum_controller=None,
        institutional_layer_protector=None,
        narrative_level_booster=booster,
        narrative_recursive_closure=nrc)

    start = time.time()
    result = evolver.run(tracking_callback=collector.step)
    elapsed = time.time() - start

    # ── Extract metrics from result ──
    layer_results = result.get('layer_results', [])
    n_layers = len(layer_results)
    l0 = layer_results[0] if layer_results else {}
    l1_formed = n_layers >= 2
    l0_sealed = l0.get('sealed', False)

    # Seal step estimation
    seal_step = estimate_first_seal_step(layer_results, target_layer=1)
    if seal_step < 0 and l1_formed:
        # Fallback: look for L0 seal step from collector
        seal_step = getattr(collector, '_l0_seal_step', -1)

    # Seal ratio from collector's L1 sealing ratios
    l1_sealing_ratios = getattr(collector, '_l1_sealing_ratios', [])
    seal_ratio = float(np.mean(l1_sealing_ratios)) if l1_sealing_ratios else 0.0

    # Number of organizations (clusters) from L0
    clusters = l0.get('clusters', [])
    n_organizations = len(clusters) if clusters else 0

    # Average binding strength from L0
    binding = l0.get('binding_strength', None)
    if binding is not None and hasattr(binding, 'abs'):
        # Use upper triangle mean (exclude diagonal)
        n = binding.size(0)
        if n > 1:
            mask = ~torch.eye(n, dtype=torch.bool)
            avg_binding = float(binding.abs()[mask].mean().item())
        else:
            avg_binding = 0.0
    else:
        avg_binding = 0.0

    # NSI / CIV / ODI from phase2 step results
    sr = l0.get('phase2_step_results', [])
    nsi_vals = [
        x.get('narrative_self_emergence', {}).get('nsi', 0.0)
        for x in sr if 'narrative_self_emergence' in x]
    nsi_max = float(np.max(nsi_vals)) if nsi_vals else 0.0

    civ_vals = [
        x.get('narrative_self_emergence', {}).get('civ_count', 0)
        for x in sr
        if 'civ_count' in x.get('narrative_self_emergence', {})]
    civ_max = int(np.max(civ_vals)) if civ_vals else 0

    odi_vals = [
        x['odi']['value'] for x in sr
        if 'odi' in x and x.get('odi', {}).get('value') is not None]
    odi_max = float(np.max(odi_vals)) if odi_vals else 0.0

    l1_sealed = (
        layer_results[1].get('sealed', False)
        if len(layer_results) >= 2 else False)

    return {
        'N0': N0, 'seed': seed, 'elapsed': elapsed,
        'l1_formed': l1_formed,
        'l0_sealed': l0_sealed,
        'l1_sealed': l1_sealed,
        'seal_step': seal_step,
        'seal_ratio': seal_ratio,
        'n_layers': n_layers,
        'n_organizations': n_organizations,
        'avg_binding': avg_binding,
        'nsi_max': nsi_max,
        'civ_max': civ_max,
        'odi_max': odi_max,
    }


# ── Aggregate Analysis ─────────────────────────────────────────────────

def analyze_transition(results_by_n0):
    """Compute per-N0 aggregate metrics and transition sharpness."""
    n0_list = sorted(results_by_n0.keys())
    summary = OrderedDict()

    for n0 in n0_list:
        seeds_data = results_by_n0[n0]
        n_seeds = len(seeds_data)

        l1_count = sum(1 for r in seeds_data if r['l1_formed'])
        l1_rate = l1_count / n_seeds

        # Seal step stats (only for seeds that formed L1)
        seal_steps = [r['seal_step'] for r in seeds_data
                      if r['l1_formed'] and r['seal_step'] >= 0]
        seal_step_mean = float(np.mean(seal_steps)) if seal_steps else -1.0
        seal_step_std = float(np.std(seal_steps)) if seal_steps else 0.0

        # Seal ratio stats (all seeds)
        seal_ratios = [r['seal_ratio'] for r in seeds_data]
        seal_ratio_mean = float(np.mean(seal_ratios))
        seal_ratio_std = float(np.std(seal_ratios))

        # Organization count
        n_orgs = [r['n_organizations'] for r in seeds_data]
        n_orgs_mean = float(np.mean(n_orgs))

        # Average binding
        avg_bindings = [r['avg_binding'] for r in seeds_data]
        avg_binding_mean = float(np.mean(avg_bindings))
        avg_binding_std = float(np.std(avg_bindings))

        # Layer count
        n_layers_list = [r['n_layers'] for r in seeds_data]
        n_layers_mean = float(np.mean(n_layers_list))

        # NSI / CIV
        nsi_vals = [r['nsi_max'] for r in seeds_data]
        civ_vals = [r['civ_max'] for r in seeds_data]

        summary[n0] = {
            'l1_rate': l1_rate,
            'l1_count': l1_count,
            'n_seeds': n_seeds,
            'seal_step_mean': seal_step_mean,
            'seal_step_std': seal_step_std,
            'seal_ratio_mean': seal_ratio_mean,
            'seal_ratio_std': seal_ratio_std,
            'n_organizations_mean': n_orgs_mean,
            'avg_binding_mean': avg_binding_mean,
            'avg_binding_std': avg_binding_std,
            'n_layers_mean': n_layers_mean,
            'nsi_max_mean': float(np.mean(nsi_vals)),
            'nsi_max_std': float(np.std(nsi_vals)),
            'civ_max_mean': float(np.mean(civ_vals)),
        }

    # ── Transition sharpness (finite-size scaling estimate) ──
    rates = [summary[n0]['l1_rate'] for n0 in n0_list]
    max_rate = max(rates)
    min_rate = min(rates)

    # Find the steepest adjacent transition
    max_gradient = 0.0
    steepest_pair = None
    for i in range(len(n0_list) - 1):
        gradient = abs(rates[i + 1] - rates[i])
        if gradient > max_gradient:
            max_gradient = gradient
            steepest_pair = (n0_list[i], n0_list[i + 1],
                             rates[i], rates[i + 1])

    # Check for resonance-like peak (non-monotonic)
    # A peak is where rate goes up then down
    peak_n0 = None
    peak_rate = 0.0
    for i in range(1, len(n0_list) - 1):
        if rates[i] > rates[i - 1] and rates[i] > rates[i + 1]:
            if rates[i] > peak_rate:
                peak_rate = rates[i]
                peak_n0 = n0_list[i]

    # Critical threshold estimate: N0 where rate first exceeds 0.5
    critical_n0 = None
    for i, n0 in enumerate(n0_list):
        if rates[i] >= 0.5:
            critical_n0 = n0
            break

    # Order parameter: max - min formation rate
    order_parameter = max_rate - min_rate

    # Transition width: range of N0 where 0.1 < rate < 0.9
    transition_width = None
    low_n0 = None
    high_n0 = None
    for i, n0 in enumerate(n0_list):
        if rates[i] > 0.1 and low_n0 is None:
            low_n0 = n0
        if rates[i] < 0.9 and low_n0 is not None:
            high_n0 = n0
    if low_n0 is not None and high_n0 is not None:
        transition_width = high_n0 - low_n0

    sharpness = {
        'max_gradient': max_gradient,
        'steepest_pair': steepest_pair,
        'peak_n0': peak_n0,
        'peak_rate': peak_rate,
        'critical_n0': critical_n0,
        'order_parameter': order_parameter,
        'transition_width': transition_width,
        'is_resonance': peak_n0 is not None and peak_rate >= 0.8,
        'is_first_order': max_gradient >= 0.5,
    }

    return summary, sharpness


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print('=' * 75)
    print('exp_147: P3 HIGH-RESOLUTION PHASE TRANSITION SCAN')
    print('=' * 75)
    print(f'  N0 sweep: {N0_SWEEP}  (step 1)')
    print(f'  Seeds per point: {len(SEEDS)}')
    print(f'  Total runs: {len(N0_SWEEP) * len(SEEDS)}')
    print(f'  Steps: {STEPS}, MaxLayers: {ML}')
    print(f'  partial_sealing: True')
    print(f'  Architecture: Full Phase 9 (CSC + NSE + NRC + Booster)')
    print()
    print(f'  exp_145 reference (step 2):')
    print(f'    N0: 24  26  28  30  32  34  36')
    print(f'    L1:  0   0   0  15   1   1  16')
    print()
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('=' * 75)

    # ── Run experiments ──
    results_by_n0 = {n0: [] for n0 in N0_SWEEP}
    total = len(N0_SWEEP) * len(SEEDS)
    done = 0
    t_total = time.time()

    for n0 in N0_SWEEP:
        print(f'\n  --- N0={n0} ---')
        for s, seed in enumerate(SEEDS):
            try:
                result = run_single_seed(
                    n0, STEPS, seed, SI, GSN, ML)
            except Exception as e:
                print(f'    [{done+1}/{total}] seed={seed}: FAILED -- {e}',
                      flush=True)
                import traceback
                traceback.print_exc()
                result = {
                    'N0': n0, 'seed': seed, 'elapsed': 0,
                    'l1_formed': False, 'l0_sealed': False,
                    'l1_sealed': False, 'seal_step': -1,
                    'seal_ratio': 0.0, 'n_layers': 0,
                    'n_organizations': 0, 'avg_binding': 0.0,
                    'nsi_max': 0.0, 'civ_max': 0, 'odi_max': 0.0,
                    'error': str(e),
                }
            results_by_n0[n0].append(result)
            done += 1
            l1ok = 'L1' if result['l1_formed'] else '--'
            print(f'    [{done}/{total}] seed={seed}: {l1ok} '
                  f'seal@{result["seal_step"]:>5} '
                  f'ratio={result["seal_ratio"]:.3f} '
                  f'orgs={result["n_organizations"]} '
                  f'bind={result["avg_binding"]:.4f} '
                  f'[{result["elapsed"]:.0f}s]',
                  flush=True)

    elapsed_total = time.time() - t_total

    # ── Analyze ──
    summary, sharpness = analyze_transition(results_by_n0)

    # ── Report ──
    print(f'\n{"=" * 75}')
    print('  PHASE TRANSITION SCAN RESULTS')
    print(f'{"=" * 75}')
    print(f'  Total runtime: {elapsed_total:.0f}s ({elapsed_total/60:.1f}min)')
    print()

    # Per-N0 summary table
    print(f'  {"N0":>4} {"L1/16":>6} {"rate":>6} {"seal_step":>10} '
          f'{"seal_ratio":>11} {"orgs":>5} {"binding":>8} {"nsi":>6}')
    print(f'  {"-"*4} {"-"*6} {"-"*6} {"-"*10} '
          f'{"-"*11} {"-"*5} {"-"*8} {"-"*6}')
    for n0 in N0_SWEEP:
        s = summary[n0]
        seal_str = (f'{s["seal_step_mean"]:.0f}+/-{s["seal_step_std"]:.0f}'
                    if s['seal_step_mean'] >= 0 else '--')
        print(f'  {n0:>4} {s["l1_count"]:>6} {s["l1_rate"]:>6.3f} '
              f'{seal_str:>10} '
              f'{s["seal_ratio_mean"]:>7.3f}+/-{s["seal_ratio_std"]:.3f} '
              f'{s["n_organizations_mean"]:>5.1f} '
              f'{s["avg_binding_mean"]:>8.5f} '
              f'{s["nsi_max_mean"]:>6.3f}')

    # Transition sharpness
    print(f'\n{"=" * 75}')
    print('  TRANSITION SHARPNESS ANALYSIS')
    print(f'{"=" * 75}')
    print(f'  Max adjacent gradient: {sharpness["max_gradient"]:.3f}')
    if sharpness['steepest_pair']:
        a, b, ra, rb = sharpness['steepest_pair']
        print(f'  Steepest pair: N0={a}->{b}  ({ra:.3f} -> {rb:.3f})')
    if sharpness['peak_n0'] is not None:
        print(f'  Resonance peak: N0={sharpness["peak_n0"]} '
              f'(rate={sharpness["peak_rate"]:.3f})')
    else:
        print(f'  No resonance peak detected (monotonic or flat)')
    if sharpness['critical_n0'] is not None:
        print(f'  Critical N0 (rate >= 0.5): {sharpness["critical_n0"]}')
    else:
        print(f'  No critical N0 found (rate never exceeds 0.5)')
    print(f'  Order parameter (max-min rate): {sharpness["order_parameter"]:.3f}')
    if sharpness['transition_width'] is not None:
        print(f'  Transition width (0.1 < rate < 0.9): '
              f'{sharpness["transition_width"]} N0 units')
    print(f'  Resonance-like: {"YES" if sharpness["is_resonance"] else "NO"}')
    print(f'  First-order-like: {"YES" if sharpness["is_first_order"] else "NO"}')

    # Comparison with exp_145
    print(f'\n{"=" * 75}')
    print('  COMPARISON WITH EXP_145')
    print(f'{"=" * 75}')
    exp145_data = {26: 0, 28: 0, 30: 15, 32: 1, 34: 1}
    for n0 in [26, 28, 30, 32, 34]:
        s = summary[n0]
        e145 = exp145_data.get(n0, -1)
        print(f'  N0={n0}: exp_147={s["l1_count"]}/16  '
              f'exp_145={e145}/16  '
              f'{"MATCH" if abs(s["l1_count"] - e145) <= 2 else "DIFFER"}')

    # ── Save results ──
    results_dir = os.path.join(PROJECT_ROOT, 'experiments', 'results')
    os.makedirs(results_dir, exist_ok=True)

    save_data = {
        'experiment': 'exp_147_p3_phase_transition_scan',
        'datetime': datetime.now().isoformat(),
        'config': {
            'N0_sweep': N0_SWEEP,
            'n_seeds': len(SEEDS),
            'steps': STEPS,
            'max_layers': ML,
            'partial_sealing': True,
            'gbc_soft_nudge': GSN,
        },
        'elapsed_total_s': elapsed_total,
        'per_N0_summary': {str(k): v for k, v in summary.items()},
        'sharpness': sharpness,
        'per_seed_results': {},
    }

    for n0 in N0_SWEEP:
        save_data['per_seed_results'][str(n0)] = []
        for r in results_by_n0[n0]:
            save_data['per_seed_results'][str(n0)].append({
                'seed': r['seed'],
                'l1_formed': r['l1_formed'],
                'l0_sealed': r['l0_sealed'],
                'l1_sealed': r['l1_sealed'],
                'seal_step': r['seal_step'],
                'seal_ratio': r['seal_ratio'],
                'n_layers': r['n_layers'],
                'n_organizations': r['n_organizations'],
                'avg_binding': r['avg_binding'],
                'nsi_max': r['nsi_max'],
                'civ_max': r['civ_max'],
                'odi_max': r['odi_max'],
                'elapsed': r['elapsed'],
                'error': r.get('error', None),
            })

    rf = os.path.join(results_dir, 'exp_147_p3_scan_results.json')
    with open(rf, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f'\n  Results saved: {rf}')

    # Also save with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    rf2 = os.path.join(results_dir,
                        f'exp_147_p3_scan_results_{timestamp}.json')
    with open(rf2, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f'  Also saved: {rf2}')

    return save_data


if __name__ == '__main__':
    main()
