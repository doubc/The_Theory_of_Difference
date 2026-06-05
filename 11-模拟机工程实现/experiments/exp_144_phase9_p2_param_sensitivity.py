"""
experiments/exp_144_phase9_p2_param_sensitivity.py

Phase 9 P2: Parameter Sensitivity (Pass 1 — Coarse Sweep)

Purpose:
  All Phase 4-8 experiments ran with the same parameter ranges.
  This experiment sweeps 4 critical parameters independently to find
  stability boundaries and sensitivity regions.

Strategy (Pass 1 only):
  4 parameters × 3 values each = 12 configurations
  8 seeds × 2000 steps per config = 96 total runs
  Each parameter swept independently; others held at baseline.

Parameters (mapped to actual code):

  1. L1_COUPLING_THRESHOLD (seal_threshold)
     - Controls: UnsealingMechanism.l1_coupling_threshold
     - Baseline: 0.008 (P1 calibration; code default 0.3)
     - Range: [0.005, 0.02, 0.10]
     - Too low → premature seal; too high → never seals

  2. COUPLING_STRENGTH (topdown_max_constraint_strength)
     - Controls: P9_CSC_CONFIG['topdown_max_constraint_strength']
     - Baseline: 0.10 (P9 config; code default 0.15)
     - Range: [0.05, 0.15, 0.40]
     - Too low → weak L0→L1 constraint; too high → L1 dominates

  3. R2_TENSION_THRESHOLD
     - Controls: NRC's r2_tension_threshold (civilizational recursion)
     - Baseline: 1.0 (P0/P1; code default 1.5)
     - Range: [0.50, 1.50, 3.00]
     - Too low → frequent R2; too high → R2 never fires

  4. L2_STABILITY_FLOOR
     - Controls: P9_CSC_CONFIG['l2_stability_floor']
     - Baseline: 0.15 (code default)
     - Range: [0.05, 0.15, 0.40]
     - Too low → L2 unstable; too high → L2 frozen

Hypotheses (P2):

  H100: L1_COUPLING_THRESHOLD has stable plateau in [0.005, 0.10]
        (layer formation >= 6/8 across full range)
  H101: COUPLING_STRENGTH ≥ 0.40 causes H1-H8 degradation (over-constraint)
        (H1-H8 drops below 6/8 at coupling >= 0.40)
  H102: L2_STABILITY_FLOOR ≤ 0.05 causes H5/H6 degradation (CIV collapse)
        (mean CIV_max < 3 at floor <= 0.05)
  H103: R2_TENSION_THRESHOLD ≥ 3.00 eliminates R2 events
        (n_r2_events == 0 at threshold == 3.00)

Expected: 3/4 PASS (H101 borderline)

Note: The original Phase 9 plan listed 8 parameters and 24 experiments.
This Pass 1 reduces to 4 most critical. Pass 2 (fine resolution) is
conditional on Pass 1 results showing narrow stability basins.
"""

import sys, os, time, json, copy
from datetime import datetime
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch, numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.return_flow_channel import ReturnFlowChannel
from engine.unsealing_mechanism import UnsealingMechanism
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.minimal_self_detector import MinimalSelfDetector
from engine.global_bias_constraint import GlobalBiasConstraint
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from models.narrative_self import (NarrativeRecursionOperator, NarrativeLevel,
    AdaptiveMomentumConnector, CIVRateLimiter)
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.six_threshold_detector import SixThresholdDetector
from engine.cross_scale_coupling import (CrossScaleCoupling, DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
from engine.narrative_self_emergence import (NarrativeSelfEmergence, DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
from engine.narrative_recursive_closure import NarrativeRecursiveClosure
from engine.civ_floor import NarrativeLevelBooster
from engine.per_layer_metrics import PerLayerMetricsCollector

# ── Baseline P9 Config ──────────────────────────────────────────────────

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


class CIVRateLimiterV2P2(CIVRateLimiter):
    """Same as P1 — ensures at least min_civ_guarantee CIV events."""
    def __init__(self, window_size=50, max_civ_rate=0.12, cooldown_steps=12, min_civ_guarantee=3):
        super().__init__(window_size=window_size, max_civ_rate=max_civ_rate, cooldown_steps=cooldown_steps)
        self.min_civ_guarantee = min_civ_guarantee

    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            if self._total_civ_seen < self.min_civ_guarantee:
                return level
            if self.should_downgrade(step):
                self._total_downgrades += 1
                return NarrativeLevel.INSTITUTIONAL
        return level


class MomentumNarrativeOperatorV4P2(NarrativeRecursionOperator):
    """Same as P1 — momentum-based narrative evolution."""
    def __init__(self, bias_dimension=128, filter_magnitude_threshold=0.02,
                 connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
                 narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3):
        from models.narrative_self import NarrativeFilter, NarrativeNamer, NarrativeActionizer, NarrativeVerifier
        self.filter = NarrativeFilter(magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(
            strength_threshold=connector_strength_threshold,
            momentum_decay=momentum_decay, momentum_bonus=momentum_bonus)
        self.actionizer = NarrativeActionizer(bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(consistency_threshold=verifier_consistency_threshold)
        self.narrative_decay_rate = narrative_decay_rate
        self._records = []
        self._active_narratives = {}
        self._record_count = 0
        self._total_actions = 0
        self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P2(
            window_size=50, max_civ_rate=0.12, cooldown_steps=12, min_civ_guarantee=3)

    def get_momentum_stats(self):
        return self.connector.get_cache_stats()

    def get_current_momentum_bonus(self):
        return self.connector.get_momentum_bonus()


# ── Shared Metrics / Helpers ───────────────────────────────────────────

def extract_l1_passive_metrics(collector):
    """Extract L1 metrics for passive constraint evaluation."""
    l1_theme = collector._theme_trackers.get('L1')
    l1_nsi = collector._nsi_trackers.get('L1')
    l1_civ = collector._civ_trackers.get('L1')
    metrics = {'l1_formed': False, 'l1_nsi_samples': 0, 'l1_civ_samples': 0,
               'l1_theme_jaccard_mean': 0.0, 'l1_seal_ratio': 0.0,
               'l1_mean_nsi': 0.0, 'l1_mean_civ': 0.0, 'l0_l1_theme_divergence': 0.0}
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
                metrics['l0_l1_theme_divergence'] = 1.0 - (len(l0_set & l1_set) / len(l0_set | l1_set))
    return metrics


def extract_nrc_metrics(evolver):
    nrc = getattr(evolver, 'narrative_recursive_closure', None)
    if nrc is None:
        return {'nrc_active': False, 'error': 'no_nrc'}
    s = nrc.get_summary()
    return {'nrc_active': True, 'n_cycles': s.get('n_cycles', 0),
            'n_r2_events': s.get('n_r2_events', 0),
            'n_rewrites': s.get('n_rewrites', 0),
            'cumulative_tension': s.get('cumulative_tension', 0.0),
            'peak_nsi': s.get('peak_nsi', 0.0)}


def estimate_first_seal_step(layer_results, target_layer=1):
    """Estimate the first step where L1 sealing occurred.
    
    Reads layer_result['sealed'] at the correct index (1 for L1).
    """
    if target_layer < len(layer_results):
        lr = layer_results[target_layer]
        if lr.get('sealed', False):
            sr = lr.get('phase2_step_results', [])
            for i, step in enumerate(sr):
                unseal = step.get('unsealing', {})
                if unseal.get('level', 0) >= 3:
                    return i * 10
            return 0  # sealed at unknown step
    return -1


# ── Single Seed Runner ─────────────────────────────────────────────────

def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    l1_coupling_threshold, coupling_strength,
                    r2_tension_threshold, l2_stability_floor,
                    max_layers=2):
    """Run one seed with given parameter values."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Build CSC config (start from base, override)
    csc_config = dict(BASE_CSC_CONFIG)
    csc_config['topdown_max_constraint_strength'] = coupling_strength
    csc_config['l2_stability_floor'] = l2_stability_floor

    rfc = ReturnFlowChannel(anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    us = UnsealingMechanism(
        l1_coupling_threshold=l1_coupling_threshold,
        l1_stability_threshold=0.02,  # Fixed — not in scope for P2 pass 1
        l2_coupling_threshold=0.04,
        l2_stability_threshold=0.08)
    psc = PreSubjectivityConvergence(coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True)
    odi = OrganizationalDensityIndex(temporal_window=10, densification_threshold=0.005, use_refined_zones=True)
    msi = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15, 'min_parts': 3,
        'history_window': 8, 'history_dependency_threshold': 0.15, 'min_history_depth': 5,
        'self_reference_window': 8, 'self_reference_threshold': 0.05,
        'baseline_correlation_threshold': 0.2, 'msi_activation_threshold': 0.20,
        'msi_emergence_threshold': 0.35, 'min_active_conditions': 1})
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5, balance_threshold=0.3,
        min_mechanisms_required=4, geometric_weighting=True)
    nro = MomentumNarrativeOperatorV4P2(
        bias_dimension=128, filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3)
    abe = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01})
    cfe = CounterfactualEngine(config={'divergence_threshold': 0.1, 'max_branches': 4})
    std = SixThresholdDetector()
    csc = CrossScaleCoupling(config=csc_config)
    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg.update({
        'history_multi_signal': True,
        'history_second_deriv_threshold': 0.02,
        'history_signal_weights': {'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1},
        'history_max_turning_points': 25})
    nse = NarrativeSelfEmergence(config=nse_cfg)
    nrc = NarrativeRecursiveClosure(
        event_window=20, collapse_threshold=0.15, settling_rate=0.3,
        r0_weight=0.4, r1_weight=0.35, r2_weight=0.25,
        r2_threshold_nsi=0.85, r2_cooldown=200,
        r2_tension_threshold=r2_tension_threshold,
        r2_use_tension=True, verbose=False)
    booster = NarrativeLevelBooster(min_civ=3)
    collector = PerLayerMetricsCollector(
        config={'nsi_rolling_window': 500, 'civ_rolling_window': 500,
                'theme_jaccard_window': 500})

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

    print(f"    [seed={seed}] Running {steps} steps, coupling={coupling_strength:.3f}, "
          f"l1_coupling={l1_coupling_threshold:.4f}, "
          f"r2_tension={r2_tension_threshold:.2f}, "
          f"stability_floor={l2_stability_floor:.2f}...", flush=True)
    start = time.time()
    result = evolver.run(tracking_callback=collector.step)
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)
    n_layers_formed = len(result.get('layer_results', []))
    print(f"    [seed={seed}] Layers formed: {n_layers_formed}", flush=True)

    layer_results_all = result.get('layer_results', [])
    layer_0 = layer_results_all[0] if layer_results_all else {}
    sr = layer_0.get('phase2_step_results', [])

    odi_max = float(np.max([x['odi']['value'] for x in sr
                           if 'odi' in x and x.get('odi', {}).get('value') is not None])) if sr else 0.0
    csc_csci = [x.get('cross_scale_coupling', {}).get('csci', 0.0)
                for x in sr if 'cross_scale_coupling' in x]
    csc_csci_std = float(np.std(csc_csci)) if csc_csci else 0.0
    td_active = [x.get('cross_scale_coupling', {}).get('topdown_n_active', 0)
                 for x in sr if 'cross_scale_coupling' in x]
    td_max = int(np.max(td_active)) if td_active else 0
    nse_nsi = [x.get('narrative_self_emergence', {}).get('nsi', 0.0)
               for x in sr if 'narrative_self_emergence' in x]
    nsi_max = float(np.max(nse_nsi)) if nse_nsi else 0.0
    nsi_mean = float(np.mean(nse_nsi)) if nse_nsi else 0.0
    nsi_active = sum(1 for x in sr
                     if x.get('narrative_self_emergence', {}).get('nsi_active', False))
    nsi_active_rate = nsi_active / len(sr) if sr else 0.0
    cont = [x.get('narrative_self_emergence', {}).get('continuity_score', 0.0)
            for x in sr if 'narrative_self_emergence' in x]
    cont_mean = float(np.mean(cont)) if cont else 0.0
    hd = [x.get('narrative_self_emergence', {}).get('self_history_depth', 0.0)
          for x in sr if 'narrative_self_emergence' in x]
    hd_mean = float(np.mean(hd)) if hd else 0.0
    tp = [x.get('narrative_self_emergence', {}).get('n_turning_points', 0)
          for x in sr if 'narrative_self_emergence' in x]
    tp_final = tp[-1] if tp else 0
    civ_vals = [x.get('narrative_self_emergence', {}).get('civ_count', 0)
                for x in sr if 'civ_count' in x.get('narrative_self_emergence', {})]
    civ_max = int(np.max(civ_vals)) if civ_vals else 0
    civ_mean = float(np.mean(civ_vals)) if civ_vals else 0.0

    nrc_m = extract_nrc_metrics(evolver)
    l1_m = extract_l1_passive_metrics(collector)
    first_seal = estimate_first_seal_step(layer_results_all, target_layer=1)
    l1_sealed = layer_results_all[1].get('sealed', False) if len(layer_results_all) >= 2 else False

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
        # store the actual param values used
        '_param_l1_coupling': l1_coupling_threshold,
        '_param_coupling_strength': coupling_strength,
        '_param_r2_tension': r2_tension_threshold,
        '_param_l2_floor': l2_stability_floor,
    }


# ── Configuration Builder ──────────────────────────────────────────────

PARAM_SWEEP = {
    'l1_coupling_threshold': {
        'label': 'seal_threshold',
        'baseline': 0.008,
        'values': [0.005, 0.02, 0.10],
        'description': 'UnsealingMechanism L1 coupling threshold',
    },
    'coupling_strength': {
        'label': 'topdown_constraint',
        'baseline': 0.10,
        'values': [0.05, 0.15, 0.40],
        'description': 'CSC topdown_max_constraint_strength',
    },
    'r2_tension_threshold': {
        'label': 'r2_tension',
        'baseline': 1.0,
        'values': [0.50, 1.50, 3.00],
        'description': 'NRC R2 tension threshold',
    },
    'l2_stability_floor': {
        'label': 'stability_floor',
        'baseline': 0.15,
        'values': [0.05, 0.15, 0.40],
        'description': 'CSC l2_stability_floor',
    },
}

BASELINE_PARAMS = {
    'l1_coupling_threshold': 0.008,
    'coupling_strength': 0.10,
    'r2_tension_threshold': 1.0,
    'l2_stability_floor': 0.15,
}

SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
N0 = 72
STEPS = 2000
SI = 10  # sample_interval
GSN = 0.2  # gbc_soft_nudge
ML = 2  # max_layers


def build_configs():
    """Build all P2 configurations: baseline + one-param-at-a-time sweeps."""
    configs = []

    # Baseline (all params at default)
    configs.append({
        'name': 'BASELINE',
        'l1_coupling_threshold': BASELINE_PARAMS['l1_coupling_threshold'],
        'coupling_strength': BASELINE_PARAMS['coupling_strength'],
        'r2_tension_threshold': BASELINE_PARAMS['r2_tension_threshold'],
        'l2_stability_floor': BASELINE_PARAMS['l2_stability_floor'],
    })

    # One-param-at-a-time sweeps
    for param_name, spec in PARAM_SWEEP.items():
        for val in spec['values']:
            if val == spec['baseline']:
                continue  # skip duplicates (baseline covers it)
            params = dict(BASELINE_PARAMS)
            params[param_name] = val
            configs.append({
                'name': f"{spec['label']}={val}",
                **params,
            })

    return configs


# ── Evaluation ─────────────────────────────────────────────────────────

def evaluate_config(results_list):
    """Evaluate H1-H8 and metrics for one config's 8 seed results."""
    if not results_list:
        return {'n_completed': 0, 'error': 'no_data'}

    a = lambda k: [r[k] for r in results_list if not r.get('error')]
    nsi_max = a('nse_nsi_max')
    nsi_rate = a('nse_nsi_active_rate')
    cont = a('nse_continuity_mean')
    hd = a('nse_history_depth_mean')
    tp = a('nse_turning_points_final')
    csci = a('csc_csci_std')
    td = a('topdown_max_active')
    civ = a('civ_max')

    h1 = max(nsi_max) > 0.1
    h2 = all(v > 0.3 for v in nsi_rate) if nsi_rate else False
    h3 = np.mean(cont) > 0.1 if cont else False
    h4 = np.mean(hd) > 0.05 or np.mean(tp) > 0.0 if (hd and tp) else False
    h5 = max(civ) >= 3 if civ else False
    h6 = max(civ) >= 2 if civ else False
    h7 = np.mean(csci) > 0.005 if csci else False
    h8 = sum(1 for v in td if v > 0) >= 2 if td else False

    formed = [r.get('l1_metrics', {}).get('l1_formed', False)
              for r in results_list if not r.get('error')]
    n_formed = sum(1 for v in formed)

    seals_steps = [r.get('first_seal_step', -1)
                   for r in results_list if not r.get('error')
                   and r.get('first_seal_step', -1) >= 0]
    first_seal_mean = float(np.mean(seals_steps)) if seals_steps else -1.0

    r2_events = [r.get('nrc_metrics', {}).get('n_r2_events', 0)
                 for r in results_list if not r.get('error')]
    r2_mean = float(np.mean(r2_events)) if r2_events else 0.0

    divergence_vals = [r.get('l1_metrics', {}).get('l0_l1_theme_divergence', 0.0)
                       for r in results_list if not r.get('error')]
    divergence_mean = float(np.mean(divergence_vals)) if divergence_vals else 0.0

    return {
        'n_completed': len([r for r in results_list if not r.get('error')]),
        'n_errors': len([r for r in results_list if r.get('error')]),
        'H1': bool(h1), 'H2': bool(h2), 'H3': bool(h3), 'H4': bool(h4),
        'H5': bool(h5), 'H6': bool(h6), 'H7': bool(h7), 'H8': bool(h8),

        'h89_n': int(sum([h1, h2, h3, h4, h5, h6, h7, h8])),
        'l1_formed': n_formed,
        'mean_nsi_max': float(np.mean(nsi_max)) if nsi_max else 0.0,
        'mean_nsi_active_rate': float(np.mean(nsi_rate)) if nsi_rate else 0.0,
        'mean_civ_max': float(np.mean(civ)) if civ else 0.0,
        'mean_csci_std': float(np.mean(csci)) if csci else 0.0,
        'mean_first_seal_step': first_seal_mean,
        'mean_r2_events': r2_mean,
        'mean_divergence': divergence_mean,
        'n_percent_formed': n_formed / max(len(results_list), 1) * 100.0,
    }


def main():
    """Run all P2 configs."""
    configs = build_configs()

    print('=' * 75)
    print('exp_144: PHASE 9 P2 -- Parameter Sensitivity (Pass 1)')
    print('=' * 75)
    print(f'  N0={N0}, Steps={STEPS}, Seeds per config: {len(SEEDS)}, MaxLayers: {ML}')
    print(f'  Configs: {len(configs)} (baseline + 4 params x 3 values)')
    print(f'  Total runs: {len(configs) * len(SEEDS)}')
    print()
    print('  H100: seal_threshold plateau [0.005, 0.10] -> >=6/8 formed')
    print('  H101: coupling_strength >= 0.40 -> H1-H8 degrades below 6/8')
    print('  H102: stability_floor <= 0.05 -> CIV_max < 3')
    print('  H103: r2_tension>=3.00 -> no R2 events')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('=' * 75)

    results_by_config = {}
    all_results = {}

    for cfg in configs:
        name = cfg['name']
        l1_ct = cfg['l1_coupling_threshold']
        cs = cfg['coupling_strength']
        r2_t = cfg['r2_tension_threshold']
        l2_sf = cfg['l2_stability_floor']

        print(f"\n{'=' * 60}")
        print(f'  Config: {name}')
        print(f'    l1_coupling={l1_ct}, coupling_strength={cs}, r2_tension={r2_t}, floor={l2_sf}')
        print(f"{'=' * 60}")

        results_by_config[name] = []
        for seed in SEEDS:
            try:
                r = run_single_seed(
                    N0=N0, steps=STEPS, seed=seed, sample_interval=SI,
                    gbc_soft_nudge=GSN,
                    l1_coupling_threshold=l1_ct,
                    coupling_strength=cs,
                    r2_tension_threshold=r2_t,
                    l2_stability_floor=l2_sf,
                    max_layers=ML)
                l1 = r['l1_metrics']
                nrc = r['nrc_metrics']
                s = '[OK]' if l1['l1_formed'] else '[--]'
                seal_step = r.get('first_seal_step', -1)
                seal_info = f"seal@{seal_step}" if seal_step >= 0 else 'unsealed'
                print(f'  seed={seed}: NSI_max={r["nse_nsi_max"]:.3f} '
                      f'layers={r["n_layers_formed"]} L1:{s} {seal_info} '
                      f'CIV_max={r["civ_max"]} R2={nrc["n_r2_events"]} '
                      f'[elapsed={r["elapsed"]:.0f}s]', flush=True)
                results_by_config[name].append(r)
                all_results[f"{name}_{seed}"] = r
            except Exception as e:
                print(f'  *** seed={seed}: FAILED -- {e}', flush=True)
                import traceback
                traceback.print_exc()
                err_rec = {'N0': N0, 'steps': STEPS, 'seed': seed, 'error': str(e),
                           'n_layers_formed': 0,
                           'nse_nsi_max': 0, 'nse_nsi_active_rate': 0,
                           'nse_continuity_mean': 0, 'nse_history_depth_mean': 0,
                           'nse_turning_points_final': 0,
                           'civ_mean': 0, 'civ_max': 0, 'csc_csci_std': 0,
                           'topdown_max_active': 0, 'odi_max': 0,
                           'first_seal_step': -1,
                           'nrc_metrics': {'nrc_active': False, 'n_cycles': 0,
                                           'n_r2_events': 0},
                           'l1_metrics': {'l1_formed': False,
                                          'l0_l1_theme_divergence': 0.0,
                                          'l1_seal_ratio': 0.0},
                           'sealed': False}
                results_by_config[name].append(err_rec)
                all_results[f"{name}_{seed}"] = err_rec

    # Evaluate per config
    config_eval = {name: evaluate_config(results)
                   for name, results in results_by_config.items()}

    print("\n" + "=" * 75)
    print('RESULTS BY CONFIG')
    print("=" * 75)
    for cfg in configs:
        name = cfg['name']
        ev = config_eval.get(name, {})
        if not ev or ev.get('error'):
            print(f"\n  {name}: NO DATA or ERROR")
            continue
        n_ok = ev.get('n_completed', 0)
        n_err = ev.get('n_errors', 0)
        err_str = f' ({n_err} errors)' if n_err else ''
        print(f"\n  {name}: {n_ok}/{len(SEEDS)} completed{err_str}")
        print(f"    L1 formed: {ev['l1_formed']}/{len(SEEDS)}")
        print(f"    H1-H8: {ev['h89_n']}/8")
        print(f"    Mean NSI_max: {ev.get('mean_nsi_max', 0):.3f}")
        print(f"    Mean CIV_max: {ev.get('mean_civ_max', 0):.1f}")
        print(f"    Mean CSCI_std: {ev.get('mean_csci_std', 0):.4f}")
        print(f"    Mean R2 events: {ev.get('mean_r2_events', 0):.1f}")
        print(f"    Mean divergence: {ev.get('mean_divergence', 0):.4f}")
        print(f"    Mean seal step: {ev.get('mean_first_seal_step', -1):.0f}")

    # Overall hypothesis evaluation
    print("\n" + "=" * 75)
    print('OVERALL HYPOTHESES (P2 Pass 1)')
    print("=" * 75)

    # H100: seal threshold plateau
    seal_formed = {}
    for cfg in configs:
        ev = config_eval.get(cfg['name'], {})
        if ev:
            seal_formed[cfg['name']] = ev.get('l1_formed', 0)
    h100_seal_low = seal_formed.get('seal_threshold=0.005', 0)
    h100_seal_mid = seal_formed.get('seal_threshold=0.02', 0)
    h100_seal_high = seal_formed.get('seal_threshold=0.10', 0)
    h100_vals = [v for v in [h100_seal_low, h100_seal_mid, h100_seal_high] if v is not None]
    h100_pass = all(v >= 6 for v in h100_vals) if len(h100_vals) >= 2 else False
    baseline_formed_baseline = seal_formed.get('BASELINE', 0)
    pass_str = 'PASS' if h100_pass else 'FAIL'
    print(f'  H100 (L1 seal threshold plateau [0.005, 0.10] >=6/8): {pass_str}')
    print(f'    seal=0.005: {h100_seal_low}/8  seal=0.02: {h100_seal_mid}/8  '
          f'seal=0.10: {h100_seal_high}/8  baseline: {baseline_formed_baseline}/8')

    # H101: coupling strength >= 0.40 -> H1-H8 degrades below 6/8
    cs_h89 = {}
    for cfg in configs:
        ev = config_eval.get(cfg['name'], {})
        if ev:
            cs_h89[cfg['name']] = ev.get('h89_n', 8)
    h101_cs_high = cs_h89.get('topdown_constraint=0.40', 8)
    h101_pass = h101_cs_high < 6
    pass_str = 'PASS' if h101_pass else 'FAIL'
    print(f'  H101 (coupling=0.40 degrades H1-H8 below 6/8): {pass_str}')
    print(f'    coupling=0.05: {cs_h89.get("topdown_constraint=0.05", "?")}/8  '
          f'coupling=0.15: {cs_h89.get("topdown_constraint=0.15", "?")}/8  '
          f'coupling=0.40: {h101_cs_high}/8  baseline: {cs_h89.get("BASELINE", "?")}/8')

    # H102: stability floor <= 0.05 -> CIV_max < 3
    sf_civ = {}
    for cfg in configs:
        ev = config_eval.get(cfg['name'], {})
        if ev:
            sf_civ[cfg['name']] = ev.get('mean_civ_max', 0)
    h102_sf_low = sf_civ.get('stability_floor=0.05', 0)
    h102_pass = h102_sf_low < 3.0
    pass_str = 'PASS' if h102_pass else 'FAIL'
    print(f'  H102 (stable floor=0.05 causes CIV_max < 3): {pass_str}')
    print(f'    floor=0.05: CIV_max={h102_sf_low:.1f}  '
          f'floor=0.15: {sf_civ.get("stability_floor=0.15", 0):.1f}  '
          f'floor=0.40: {sf_civ.get("stability_floor=0.40", 0):.1f}')

    # H103: r2_tension >= 3.00 -> no R2 events
    r2_counts = {}
    for cfg in configs:
        ev = config_eval.get(cfg['name'], {})
        if ev:
            r2_counts[cfg['name']] = ev.get('mean_r2_events', 0)
    h103_r2_high = r2_counts.get('r2_tension=3.00', -1)
    h103_pass = h103_r2_high == 0.0
    pass_str = 'PASS' if h103_pass else 'FAIL'
    print(f'  H103 (r2_tension=3.00 eliminates R2 events): {pass_str}')
    print(f'    r2=0.50: {r2_counts.get("r2_tension=0.50", 0):.2f}  '
          f'r2=1.50: {r2_counts.get("r2_tension=1.50", 0):.2f}  '
          f'r2=3.00: {h103_r2_high:.2f}')

    n_pass = sum([h100_pass, h101_pass, h102_pass, h103_pass])
    print(f"\n  Phase 9 P2 Pass 1: {n_pass}/4 PASS")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    rf = os.path.join(PROJECT_ROOT, 'experiments',
                      f'exp_144_phase9_p2_params_{timestamp}.json')

    def convert_val(v):
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    with open(rf, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_144_phase9_p2',
            'datetime': datetime.now().isoformat(),
            'configs': [{'name': c['name'],
                         'l1_coupling_threshold': c['l1_coupling_threshold'],
                         'coupling_strength': c['coupling_strength'],
                         'r2_tension_threshold': c['r2_tension_threshold'],
                         'l2_stability_floor': c['l2_stability_floor']}
                        for c in configs],
            'hypotheses': {
                'H100': h100_pass,
                'H101': h101_pass,
                'H102': h102_pass,
                'H103': h103_pass,
                'n_pass': n_pass,
            },
            'by_config': {name: {k: convert_val(v) for k, v in ev.items()}
                          for name, ev in config_eval.items()},
        }, f, indent=2, default=str)
    print(f"\n  Results saved: {rf}")
    print(f"\n  Phase 9 P2 Pass 1: {n_pass}/4 PASS")


if __name__ == '__main__':
    main()
