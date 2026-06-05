"""
experiments/exp_145_phase9_p3_phase_transition.py

Phase 9 P3: Phase Transition Map — P3-A (N0 Collapse Boundary)

Purpose:
  P0 showed a sharp transition in L1 formation between N0=24 (0/8) and N0=36 (8/8).
  P3-A maps this boundary at higher resolution (N0 step=2) with 16 seeds per point
  to determine whether the transition is sharp (percolation-like) or graded (logistic).

Config:
  N0 = [24, 26, 28, 30, 32, 34, 36]   # 7 points
  seeds = 16                             # 16 per point
  max_steps = 2000
  max_layers = 2

Total runs: 7 x 16 = 112
Estimated runtime: ~1h (similar per-seed cost to P0/P1)

Hypotheses:

  H110: N0 transition is sharp (>= 12/16 within 2 adjacent N0 values)
        Formation rate goes from <= 3/16 to >= 13/16 across <= 2 N0 steps.

  H111 (fallback): If graded, formation probability fits logistic:
        P(formation) = 1 / (1 + exp(-k(N0 - N0_0))), R^2 >= 0.85

  H112: NSI at N0=24 is artifact of missing L1 constraint.
        NSI(24) > NSI(36) but structural metrics (Continuity, CIV) are lower.

Conditional experiments P3-B (noise collapse) and P3-C (seal hysteresis)
will be added in a separate update after P2 (exp_144) results are analyzed.
"""

import sys, os, time, json, copy
from datetime import datetime
from collections import OrderedDict

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

# ── Baseline P9 Config (identical to exp_144) ──────────────────────────

BASE_CSC_CONFIG = {
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


class CIVRateLimiterV2P3(CIVRateLimiter):
    """Ensures at least min_civ_guarantee CIV events (identical to P2)."""
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


class MomentumNarrativeOperatorV4P3(NarrativeRecursionOperator):
    """Momentum-based narrative evolution (identical to P2)."""
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
        self.civ_rate_limiter = CIVRateLimiterV2P3(
            window_size=50, max_civ_rate=0.12, cooldown_steps=12,
            min_civ_guarantee=3)

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


# ── Metrics Extraction (shimmed from exp_144) ──────────────────────────

def extract_l1_passive_metrics(collector):
    """Extract L1 metrics for passive constraint evaluation."""
    l1_theme = collector._theme_trackers.get('L1')
    l1_nsi = collector._nsi_trackers.get('L1')
    l1_civ = collector._civ_trackers.get('L1')
    metrics = {
        'l1_formed': False, 'l1_nsi_samples': 0, 'l1_civ_samples': 0,
        'l1_theme_jaccard_mean': 0.0, 'l1_seal_ratio': 0.0,
        'l1_mean_nsi': 0.0, 'l1_mean_civ': 0.0,
        'l0_l1_theme_divergence': 0.0,
    }
    if l1_nsi:
        hist = getattr(l1_nsi, '_nsi_output_history', [])
        if hist:
            metrics['l1_nsi_samples'] = len(hist)
            metrics['l1_mean_nsi'] = float(np.mean([v for _, v in hist]))
            metrics['l1_formed'] = True
    if l1_civ:
        hist = getattr(l1_civ, '_hamming_history', [])
        if hist:
            metrics['l1_civ_samples'] = len(hist)
            metrics['l1_mean_civ'] = float(np.mean([v for _, v in hist]))
    analysis = collector.analyze(post_seal_only=False)
    l1_data = analysis.get('per_layer', {}).get('L1', {})
    if l1_data and 'sealing' in l1_data:
        metrics['l1_seal_ratio'] = l1_data['sealing'].get('seal_ratio', 0.0)
        if l1_data['sealing'].get('n_snapshots', 0) > 0:
            metrics['l1_formed'] = True
    l0_theme = collector._theme_trackers.get('L0')
    if l0_theme and l1_theme:
        l0_hist = getattr(l0_theme, '_identity_history', [])
        l1_hist = getattr(l1_theme, '_identity_history', [])
        if l0_hist and l1_hist:
            l0_set = l0_hist[-1][1] if len(l0_hist[-1]) > 1 else set()
            l1_set = l1_hist[-1][1] if len(l1_hist[-1]) > 1 else set()
            if l0_set and l1_set:
                metrics['l0_l1_theme_divergence'] = (
                    1.0 - (len(l0_set & l1_set) / len(l0_set | l1_set)))
    return metrics


def extract_nrc_metrics(evolver):
    nrc = getattr(evolver, 'narrative_recursive_closure', None)
    if nrc is None:
        return {'nrc_active': False, 'error': 'no_nrc'}
    s = nrc.get_summary()
    return {
        'nrc_active': True,
        'n_cycles': s.get('n_cycles', 0),
        'n_r2_events': s.get('n_r2_events', 0),
        'n_rewrites': s.get('n_rewrites', 0),
        'cumulative_tension': s.get('cumulative_tension', 0.0),
        'peak_nsi': s.get('peak_nsi', 0.0),
    }


def estimate_first_seal_step(layer_results, target_layer=1):
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
    """Run one seed with baseline P9 parameters at given N0."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    csc_config = dict(BASE_CSC_CONFIG)

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
    nro = MomentumNarrativeOperatorV4P3(
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

    print(f"    [seed={seed}] N0={N0} Running {steps} steps...", flush=True)
    start = time.time()
    result = evolver.run(tracking_callback=collector.step)
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    n_layers_formed = len(result.get('layer_results', []))
    print(f"    [seed={seed}] Layers formed: {n_layers_formed}", flush=True)

    layer_results_all = result.get('layer_results', [])
    layer_0 = layer_results_all[0] if layer_results_all else {}
    sr = layer_0.get('phase2_step_results', [])

    # ── Extract scalar metrics ──
    odi_max = float(np.max([
        x['odi']['value'] for x in sr
        if 'odi' in x and x.get('odi', {}).get('value') is not None
    ])) if sr else 0.0

    csc_csci = [
        x.get('cross_scale_coupling', {}).get('csci', 0.0)
        for x in sr if 'cross_scale_coupling' in x]
    csc_csci_std = float(np.std(csc_csci)) if csc_csci else 0.0

    td_active = [
        x.get('cross_scale_coupling', {}).get('topdown_n_active', 0)
        for x in sr if 'cross_scale_coupling' in x]
    td_max = int(np.max(td_active)) if td_active else 0

    nse_nsi = [
        x.get('narrative_self_emergence', {}).get('nsi', 0.0)
        for x in sr if 'narrative_self_emergence' in x]
    nsi_max = float(np.max(nse_nsi)) if nse_nsi else 0.0
    nsi_mean = float(np.mean(nse_nsi)) if nse_nsi else 0.0
    nsi_active = sum(1 for x in sr
                     if x.get('narrative_self_emergence', {}).get('nsi_active', False))
    nsi_active_rate = nsi_active / len(sr) if sr else 0.0

    cont = [
        x.get('narrative_self_emergence', {}).get('continuity_score', 0.0)
        for x in sr if 'narrative_self_emergence' in x]
    cont_mean = float(np.mean(cont)) if cont else 0.0

    hd = [
        x.get('narrative_self_emergence', {}).get('self_history_depth', 0.0)
        for x in sr if 'narrative_self_emergence' in x]
    hd_mean = float(np.mean(hd)) if hd else 0.0

    tp = [
        x.get('narrative_self_emergence', {}).get('n_turning_points', 0)
        for x in sr if 'narrative_self_emergence' in x]
    tp_final = tp[-1] if tp else 0

    civ_vals = [
        x.get('narrative_self_emergence', {}).get('civ_count', 0)
        for x in sr
        if 'civ_count' in x.get('narrative_self_emergence', {})]
    civ_max = int(np.max(civ_vals)) if civ_vals else 0
    civ_mean = float(np.mean(civ_vals)) if civ_vals else 0.0

    nrc_m = extract_nrc_metrics(evolver)
    l1_m = extract_l1_passive_metrics(collector)
    first_seal = estimate_first_seal_step(layer_results_all, target_layer=1)
    l1_sealed = (
        layer_results_all[1].get('sealed', False)
        if len(layer_results_all) >= 2 else False)

    return {
        'N0': N0, 'steps': steps, 'seed': seed, 'elapsed': elapsed,
        'n_steps': len(sr),
        'sealed': layer_0.get('sealed', False),
        'l1_sealed': l1_sealed,
        'n_layers_formed': n_layers_formed,
        'first_seal_step': first_seal,
        'odi_max': odi_max,
        'csc_csci_std': csc_csci_std,
        'topdown_max_active': td_max,
        'nse_nsi_max': nsi_max,
        'nse_nsi_mean': nsi_mean,
        'nse_nsi_active_rate': nsi_active_rate,
        'nse_continuity_mean': cont_mean,
        'nse_history_depth_mean': hd_mean,
        'nse_turning_points_final': tp_final,
        'civ_mean': civ_mean,
        'civ_max': civ_max,
        'nrc_metrics': nrc_m,
        'l1_metrics': l1_m,
    }


# ── Experiment Configuration ──────────────────────────────────────────

N0_SWEEP = [24, 26, 28, 30, 32, 34, 36]
SEEDS = [42, 142, 242, 342, 442, 542, 642, 742,
         842, 942, 1042, 1142, 1242, 1342, 1442, 1542]
STEPS = 2000
SI = 10
GSN = 0.2
ML = 2


# ── Analysis ──────────────────────────────────────────────────────────

def fit_logistic(N0_values, formed_rates):
    """
    Fit a logistic function P = 1 / (1 + exp(-k(N0 - N0_0)))
    Returns (k, N0_0, R2) or None if fitting fails.
    """
    from scipy.optimize import curve_fit
    x = np.array(N0_values, dtype=float)
    y = np.array(formed_rates, dtype=float)

    def logistic(x, k, x0):
        return 1.0 / (1.0 + np.exp(-k * (x - x0)))

    # Initial guess: steepness=1, midpoint=30
    try:
        popt, pcov = curve_fit(logistic, x, y, p0=[1.0, 30.0],
                               bounds=([0.0, 24.0], [5.0, 36.0]),
                               maxfev=10000)
        k, x0 = popt
        y_pred = logistic(x, k, x0)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1.0 - ss_res / max(ss_tot, 1e-10)
        return (float(k), float(x0), float(r2))
    except Exception:
        return None


def evaluate_N0_boundary(results_by_n0):
    """
    Evaluate H110-H112 for the N0 collapse boundary.

    Returns dict with hypothesis results and supporting stats.
    """
    n0_list = sorted(results_by_n0.keys())
    formed_by_n0 = OrderedDict()
    for n0 in n0_list:
        seeds_data = results_by_n0[n0]
        formed = sum(
            1 for r in seeds_data
            if r.get('l1_metrics', {}).get('l1_formed', False)
        )
        formed_by_n0[n0] = formed

    # ── H110: Sharp transition ──
    # Find max formation across any 2 adjacent N0 values
    h110_pass = False
    sharp_window = None
    window_min = 999
    window_max = -1
    for i in range(len(n0_list) - 1):
        a, b = n0_list[i], n0_list[i + 1]
        f_a, f_b = formed_by_n0[a], formed_by_n0[b]
        total_in_window = f_a + f_b
        # Transition is sharp if low end <= 3/16 and high end >= 13/16
        # across a 2-step window
        if max(f_a, f_b) >= 13 and min(f_a, f_b) <= 3:
            h110_pass = True
            sharp_window = (a, b, f_a, f_b)
        if f_a < window_min:
            window_min = f_a
        if f_b > window_max:
            window_max = f_b
    # Also check if the total swing across any 2 adjacent is >= 10
    max_swing = 0
    for i in range(len(n0_list) - 1):
        swing = abs(formed_by_n0[n0_list[i]] - formed_by_n0[n0_list[i + 1]])
        if swing > max_swing:
            max_swing = swing

    # ── H111 (fallback): Logistic fit if not sharp ──
    formed_rates = [
        formed_by_n0[n0] / len(results_by_n0[n0]) for n0 in n0_list]
    logistic_fit = None
    if not h110_pass:
        logistic_fit = fit_logistic(n0_list, formed_rates)

    # ── H112: NSI at N0=24 is artifact ──
    n0_24 = results_by_n0.get(24, [])
    n0_36 = results_by_n0.get(36, [])

    nsi_24 = np.mean([r.get('nse_nsi_max', 0) for r in n0_24]) if n0_24 else 0
    nsi_36 = np.mean([r.get('nse_nsi_max', 0) for r in n0_36]) if n0_36 else 0
    cont_24 = np.mean(
        [r.get('nse_continuity_mean', 0) for r in n0_24]) if n0_24 else 0
    cont_36 = np.mean(
        [r.get('nse_continuity_mean', 0) for r in n0_36]) if n0_36 else 0
    civ_24 = np.mean(
        [r.get('civ_max', 0) for r in n0_24]) if n0_24 else 0
    civ_36 = np.mean(
        [r.get('civ_max', 0) for r in n0_36]) if n0_36 else 0

    h112_pass = bool(
        nsi_24 > nsi_36 and cont_24 < cont_36 and civ_24 < civ_36)

    return {
        'n0_list': n0_list,
        'formed_by_n0': {str(k): v for k, v in formed_by_n0.items()},
        'formed_rates': formed_rates,
        'H110': {
            'pass': h110_pass,
            'max_swing_adjacent': max_swing,
            'sharp_window': sharp_window,
            'n_seeds_per_point': 16,
        },
        'H111': {
            'pass': bool(logistic_fit and logistic_fit[2] >= 0.85),
            'logistic_fit': logistic_fit,
        },
        'H112': {
            'pass': h112_pass,
            'nsi_24_mean': float(nsi_24),
            'nsi_36_mean': float(nsi_36),
            'cont_24_mean': float(cont_24),
            'cont_36_mean': float(cont_36),
            'civ_24_mean': float(civ_24),
            'civ_36_mean': float(civ_36),
        },
        'n_hypotheses_passed': sum([h110_pass, h112_pass]),
    }


# ── Main ──────────────────────────────────────────────────────────────

def main():
    """Run P3-A: N0 collapse boundary mapping."""
    print('=' * 75)
    print('exp_145: PHASE 9 P3-A -- N0 Collapse Boundary Map')
    print('=' * 75)
    print(f'  N0 sweep: {N0_SWEEP}')
    print(f'  Seeds per point: {len(SEEDS)}')
    print(f'  Total runs: {len(N0_SWEEP) * len(SEEDS)}')
    print(f'  Steps: {STEPS}, MaxLayers: {ML}')
    print()
    print('  H110: Sharp transition (>=12/16 swing within 2 N0 steps)')
    print('  H111: Logistic fit (fallback if graded, R2>=0.85)')
    print('  H112: NSI(24) > NSI(36) but continuity/civ lower')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    h111 = evaluation['H111']
    if h111['logistic_fit']:
        k, x0, r2 = h111['logistic_fit']
        pass_str = 'PASS' if h111['pass'] else 'FAIL'
        print(f'\n  H111 (Logistic fit R2>=0.85): {pass_str}')
        print(f'    k={k:.3f}, N0_0={x0:.1f}, R2={r2:.3f}')
    else:
        print(f'\n  H111 (Logistic fit): SKIP (H110 already PASS or fit failed)')

    # H112
    h112 = evaluation['H112']
    pass_str = 'PASS' if h112['pass'] else 'FAIL'
    print(f'\n  H112 (NSI artifact at N0=24): {pass_str}')
    print(f'    NSI: N0=24 mean={h112["nsi_24_mean"]:.3f} vs N0=36 mean={h112["nsi_36_mean"]:.3f}')
    print(f'    Continuity: N0=24 mean={h112["cont_24_mean"]:.3f} vs N0=36 mean={h112["cont_36_mean"]:.3f}')
    print(f'    CIV_max: N0=24 mean={h112["civ_24_mean"]:.1f} vs N0=36 mean={h112["civ_36_mean"]:.1f}')

    n_pass = evaluation['n_hypotheses_passed']
    print(f'\n  Phase 9 P3-A: {n_pass}/2 PASS (H111 conditional fallback)')

    # ── Save results ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    rf = os.path.join(PROJECT_ROOT, 'experiments',
                      f'exp_145_phase9_p3_n0_boundary_{timestamp}.json')

    # Raw seed-level results (lightweight — omit large per-step traces)
    raw_seeds = {}
    for n0 in N0_SWEEP:
        raw_seeds[str(n0)] = []
        for r in results_by_n0[n0]:
            raw_seeds[str(n0)].append({
                k: v for k, v in r.items()
                if k not in ('nrc_metrics', 'l1_metrics')
            })
        # Add summary metrics
        for r in results_by_n0[n0]:
            raw_seeds[str(n0)][-1]['l1_formed'] = r.get('l1_metrics', {}).get('l1_formed', False)
            raw_seeds[str(n0)][-1]['l0_l1_divergence'] = r.get('l1_metrics', {}).get('l0_l1_theme_divergence', 0.0)
            raw_seeds[str(n0)][-1]['n_r2_events'] = r.get('nrc_metrics', {}).get('n_r2_events', 0)

    with open(rf, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_145_phase9_p3a',
            'datetime': datetime.now().isoformat(),
            'config': {
                'N0_sweep': N0_SWEEP,
                'n_seeds': len(SEEDS),
                'steps': STEPS,
                'max_layers': ML,
            },
            'hypotheses': {
                'H110': {
                    'pass': h110['pass'],
                    'max_swing_adjacent': h110['max_swing_adjacent'],
                    'sharp_window': h110['sharp_window'],
                },
                'H111': {
                    'pass': h111['pass'],
                    'logistic_fit': h111['logistic_fit'],
                },
                'H112': {
                    'pass': h112['pass'],
                    'nsi_24_mean': h112['nsi_24_mean'],
                    'nsi_36_mean': h112['nsi_36_mean'],
                    'cont_24_mean': h112['cont_24_mean'],
                    'cont_36_mean': h112['cont_36_mean'],
                    'civ_24_mean': h112['civ_24_mean'],
                    'civ_36_mean': h112['civ_36_mean'],
                },
                'n_pass': n_pass,
            },
            'formed_by_N0': {str(k): v for k, v in evaluation['formed_by_n0'].items()},
            'per_seed': raw_seeds,
        }, f, indent=2, default=str)

    print(f"\n  Results saved: {rf}")
    print(f"\n  Phase 9 P3-A: {n_pass}/2 PASS")


if __name__ == '__main__':
    main()
