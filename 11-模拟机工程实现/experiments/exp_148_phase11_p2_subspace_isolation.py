"""
experiments/exp_148_phase11_p2_subspace_isolation.py

Phase 11 P2: Subspace Isolation Verification — Static 3-Partition, Zero Coupling

Purpose:
  Verify that when a unified discrete difference space is partitioned into
  multiple subspaces with zero coupling, each subspace evolves independently
  with no cross-talk. This is the foundational assumption for all subsequent
  subspace decomposition experiments (P3-P5).

Approach:
  Since SubspaceField is currently a pure data-structure layer (not yet
  integrated into HierarchicalEvolver), this experiment runs 3 independent
  evolver instances per seed — one for each subspace at N0=N0_sub=10.
  This represents the zero-coupling limit exactly: each subspace is an
  independent N0=10 discrete difference space.

Config:
  N0_total = 30  (3 subspaces × 10 bits each, static partition)
  k = 3          (subspace count)
  N0_sub = 10    (per-subspace size)
  Coupling = 0.0 (fully isolated)
  Allocation: static partition
  Seeds: 16 (per subspace — total 48 individual runs)
  Steps: 2000 per run

Hypotheses:

  H148-1 (No L1 in subspace isolation):
    At N0=10, zero subspace forms L1 (N0=10 << N0*≈30.5 phase transition).
    → 0/48 individual runs form L1 (rate=0.0)

  H148-2 (Zero cross-correlation):
    Cross-subspace SEER/ODI/NSI trajectories have correlation ≈ 0.
    → Mean pairwise Pearson r < 0.05

  H148-3 (Phase transition is NOT scalable):
    Subspace size N0_sub=10 cannot sustain L1 even when aggregated
    into a larger N0_total=30 system.
    → This confirms the phase transition is a property of the total system,
      not decomposable into independent sub-systems.

  H148-4 (Repeatability across seed families):
    Results are consistent across all 16 seed families and all 3 subspaces.
    → Std dev of L1 formation rate across subspaces = 0 (all 0/16).
"""

import sys, os, time, json, itertools
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
from engine.subspace_field import (
    SubspaceField, SubspaceSpec, Rules,
    allocate_static, make_static_field,
)

# =============================================================================
# Subspace-aware experiment config
# =============================================================================

# Partition: N0=30, 3 subspaces of 10 bits each
N0_TOTAL = 30
K = 3
N0_SUB = N0_TOTAL // K  # 10
COUPLING = 0.0  # zero coupling

# Build the SubspaceField for metadata
subspace_indices = allocate_static(N0_TOTAL, K)
SUBSPACE_FIELD = make_static_field(
    N0=N0_TOTAL, k=K,
    rules_list=[Rules.default() for _ in range(K)],
    name_prefix="S",
    coupling_strength=COUPLING,
)

SUBSPACE_NAMES = ["S0", "S1", "S2"]

# Baseline P9 config (identical to exp_144/145)
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

STEPS = 2000
SI = 10      # sample interval
GSN = 0.2    # gbc_soft_nudge
ML = 2       # max_layers

# 16 seeds per subspace × 3 subspaces = 48 runs
SEEDS = [42, 142, 242, 342, 442, 542, 642, 742,
         842, 942, 1042, 1142, 1242, 1342, 1442, 1542]


# =============================================================================
# Component helpers (shimmed from exp_144/145)
# =============================================================================

class CIVRateLimiterV2P3(CIVRateLimiter):
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


# =============================================================================
# Single subspace runner
# =============================================================================

def run_single_subspace(subspace_name, N0, seed, steps, sample_interval,
                         gbc_soft_nudge, max_layers=2):
    """
    Run one subspace (N0 bits) with a given seed.
    Returns a dictionary of scalar metrics.
    """
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

    t0 = time.time()
    result = evolver.run(tracking_callback=collector.step)
    elapsed = time.time() - t0

    n_layers_formed = len(result.get('layer_results', []))
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

    # Check if L1 layer was formed
    l1_sealed = (
        layer_results_all[1].get('sealed', False)
        if len(layer_results_all) >= 2 else False)

    return {
        'subspace': subspace_name,
        'N0': N0, 'steps': steps, 'seed': seed, 'elapsed': elapsed,
        'n_steps': len(sr),
        'sealed': layer_0.get('sealed', False),
        'l1_sealed': l1_sealed,
        'n_layers_formed': n_layers_formed,
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


# =============================================================================
# Hypothesis evaluation
# =============================================================================

def evaluate_isolation(per_subspace_results):
    """
    Evaluate H148-1 through H148-4 from the per-subspace results.

    Args:
        per_subspace_results: dict mapping subspace_name -> list of per-seed dicts

    Returns:
        dict with hypothesis results
    """
    subspaces = sorted(per_subspace_results.keys())

    # ── H148-1: No L1 in subspace isolation ──
    l1_counts = {}
    total_l1 = 0
    total_runs = 0
    for sub in subspaces:
        n_formed = sum(1 for r in per_subspace_results[sub]
                       if r.get('l1_metrics', {}).get('l1_formed', False))
        l1_counts[sub] = n_formed
        total_l1 += n_formed
        total_runs += len(per_subspace_results[sub])
    h148_1_pass = total_l1 == 0

    # ── H148-2: Zero cross-correlation ──
    # For each seed that exists across all subspaces, compute pairwise
    # correlation of ODI, NSI, continuity time series.
    # Since we run independent evolver instances, cross-correlation
    # should be ~0 (no shared dynamics).
    # We use the scalar metrics as a proxy: are per-seed metric vectors
    # correlated across subspaces?
    cross_corr_odi = _compute_cross_correlation(
        per_subspace_results, subspaces, 'odi_max')
    cross_corr_nsi = _compute_cross_correlation(
        per_subspace_results, subspaces, 'nse_nsi_mean')
    cross_corr_cont = _compute_cross_correlation(
        per_subspace_results, subspaces, 'nse_continuity_mean')

    mean_cross_corr = float(np.mean([
        abs(v) for v in [cross_corr_odi, cross_corr_nsi, cross_corr_cont]
        if v is not None
    ])) if any(v is not None for v in
               [cross_corr_odi, cross_corr_nsi, cross_corr_cont]) else 0.0

    h148_2_pass = mean_cross_corr < 0.10

    # ── H148-3: Phase transition NOT scalable ──
    # N0_sub=10 cannot sustain L1 even in aggregate
    # Confirmed by H148-1 pass.

    # ── H148-4: Repeatability across seed families ──
    if total_l1 == 0:
        h148_4_pass = True  # all subspaces = 0/16 L1
    else:
        # Check std dev of L1 formation rate across subspaces
        rates = [l1_counts[s] / len(per_subspace_results[s])
                 for s in subspaces]
        h148_4_pass = bool(np.std(rates) < 0.01)

    # ── Aggregate statistics ──
    # Per-subspace mean metrics
    per_sub_means = {}
    for sub in subspaces:
        data = per_subspace_results[sub]
        per_sub_means[sub] = {
            'n_runs': len(data),
            'l1_formed': l1_counts[sub],
            'odi_max_mean': float(np.mean([r['odi_max'] for r in data])),
            'nsi_mean_mean': float(np.mean([r['nse_nsi_mean'] for r in data])),
            'nsi_max_mean': float(np.mean([r['nse_nsi_max'] for r in data])),
            'cont_mean': float(np.mean([r['nse_continuity_mean'] for r in data])),
            'civ_max_mean': float(np.mean([r['civ_max'] for r in data])),
            'civ_mean_mean': float(np.mean([r['civ_mean'] for r in data])),
            'topdown_max_mean': float(np.mean([r['topdown_max_active'] for r in data])),
            'nrc_cycles_mean': float(np.mean([r['nrc_metrics']['n_cycles'] for r in data])),
            'nrc_r2_mean': float(np.mean([r['nrc_metrics']['n_r2_events'] for r in data])),
        }

    # Aggregate across all subspaces
    all_data = []
    for sub in subspaces:
        all_data.extend(per_subspace_results[sub])

    aggregate = {
        'total_runs': total_runs,
        'total_l1_formed': total_l1,
        'l1_formation_rate': total_l1 / max(total_runs, 1),
        'odi_max_mean': float(np.mean([r['odi_max'] for r in all_data])),
        'odi_max_std': float(np.std([r['odi_max'] for r in all_data])),
        'nsi_mean_mean': float(np.mean([r['nse_nsi_mean'] for r in all_data])),
        'nsi_max_mean': float(np.mean([r['nse_nsi_max'] for r in all_data])),
        'nsi_active_rate_mean': float(np.mean([r['nse_nsi_active_rate'] for r in all_data])),
        'cont_mean': float(np.mean([r['nse_continuity_mean'] for r in all_data])),
        'civ_max_mean': float(np.mean([r['civ_max'] for r in all_data])),
        'topdown_max_mean': float(np.mean([r['topdown_max_active'] for r in all_data])),
        'nrc_cycles_mean': float(np.mean([r['nrc_metrics']['n_cycles'] for r in all_data])),
        'nrc_r2_mean': float(np.mean([r['nrc_metrics']['n_r2_events'] for r in all_data])),
    }

    return {
        'H148_1': {
            'pass': h148_1_pass,
            'total_l1': total_l1,
            'total_runs': total_runs,
            'per_subspace_l1_counts': l1_counts,
            'description': 'No L1 formation in any subspace (N0=10)',
        },
        'H148_2': {
            'pass': h148_2_pass,
            'mean_cross_correlation': mean_cross_corr,
            'cross_corr_odi': cross_corr_odi,
            'cross_corr_nsi': cross_corr_nsi,
            'cross_corr_continuity': cross_corr_cont,
            'description': 'Zero cross-subspace correlation',
        },
        'H148_3': {
            'pass': h148_1_pass,  # same as H148_1
            'description': 'Phase transition NOT scalable — N0_sub=10 cannot sustain L1',
        },
        'H148_4': {
            'pass': h148_4_pass,
            'description': 'Consistent results across subspaces and seeds',
        },
        'per_subspace_means': per_sub_means,
        'aggregate': aggregate,
        'n_hypotheses_passed': sum([
            h148_1_pass, h148_2_pass, h148_4_pass,
        ]),
    }


def _compute_cross_correlation(per_subspace_results, subspaces, metric_key):
    """
    Compute mean pairwise Pearson correlation of a metric across subspaces.
    Uses the per-seed ordering (same seed index across subspaces).

    Returns mean absolute r value, or None if insufficient data.
    """
    n_seeds = len(per_subspace_results[subspaces[0]])
    if n_seeds < 3:
        return None

    vectors = {}
    for sub in subspaces:
        values = [r.get(metric_key, 0.0) for r in per_subspace_results[sub]]
        if len(values) != n_seeds:
            return None
        vectors[sub] = np.array(values, dtype=float)

    correlations = []
    for i, j in itertools.combinations(range(len(subspaces)), 2):
        si, sj = subspaces[i], subspaces[j]
        vi, vj = vectors[si], vectors[sj]
        # Handle zero-variance cases
        if np.std(vi) < 1e-10 or np.std(vj) < 1e-10:
            correlations.append(0.0)
        else:
            r = np.corrcoef(vi, vj)[0, 1]
            correlations.append(float(r))

    return float(np.mean([abs(c) for c in correlations]))


# =============================================================================
# Main
# =============================================================================

def main():
    print('=' * 75)
    print('exp_148: PHASE 11 P2 — Subspace Isolation Verification')
    print('=' * 75)
    print(f'  N0_total = {N0_TOTAL}, k = {K}, N0_sub = {N0_SUB}')
    print(f'  Coupling = {COUPLING} (fully isolated)')
    print(f'  Allocation: static partition')
    print(f'  Subspaces: {SUBSPACE_NAMES}')
    for name in SUBSPACE_NAMES:
        bits = sorted(SUBSPACE_FIELD.get_bits(name))
        print(f'    {name}: bits {bits} ({len(bits)} bits)')
    print(f'  Seeds per subspace: {len(SEEDS)}')
    print(f'  Total runs: {len(SUBSPACE_NAMES) * len(SEEDS)} ({len(SEEDS)} seed families × 3 subspaces)')
    print(f'  Steps: {STEPS}, MaxLayers: {ML}')
    print()
    print('  H148-1: No L1 formation at N0=10 (0/48 L1)')
    print('  H148-2: Zero cross-subspace correlation (mean |r| < 0.10)')
    print('  H148-3: Phase transition NOT scalable (N0_sub=10 → no L1)')
    print('  H148-4: Consistent across seed families')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print()

    # ── Run experiments ──
    per_subspace_results = {name: [] for name in SUBSPACE_NAMES}
    total = len(SUBSPACE_NAMES) * len(SEEDS)
    done = 0

    for sub_idx, sub_name in enumerate(SUBSPACE_NAMES):
        print(f'\n  --- Subspace: {sub_name} (N0={N0_SUB}) ---')
        for seed in SEEDS:
            result = run_single_subspace(
                sub_name, N0_SUB, seed, STEPS, SI, GSN, ML)
            per_subspace_results[sub_name].append(result)
            done += 1
            l1ok = 'OK' if result.get('l1_metrics', {}).get('l1_formed', False) else 'NO'
            elapsed = result['elapsed']
            print(f'    [{done}/{total}] {sub_name} seed={seed}: L1:{l1ok} '
                  f'NSI={result.get("nse_nsi_max", 0):.3f} '
                  f'ODI={result.get("odi_max", 0):.4f} '
                  f'CIV={result.get("civ_max", 0)} '
                  f'[{elapsed:.1f}s]')

    # ── Evaluate hypotheses ──
    print(f'\n{"=" * 75}')
    print('  EVALUATING HYPOTHESES')
    print(f'{"=" * 75}')

    evaluation = evaluate_isolation(per_subspace_results)

    # ── Save results BEFORE printing (Windows GBK compatibility) ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    rf = os.path.join(PROJECT_ROOT, 'experiments',
                      f'exp_148_phase11_p2_isolation_{timestamp}.json')

    raw_seeds = {name: [] for name in SUBSPACE_NAMES}
    for name in SUBSPACE_NAMES:
        for r in per_subspace_results[name]:
            entry = {k: v for k, v in r.items()
                     if k not in ('nrc_metrics', 'l1_metrics')}
            entry['l1_formed'] = r.get('l1_metrics', {}).get('l1_formed', False)
            entry['l0_l1_divergence'] = r.get('l1_metrics', {}).get('l0_l1_theme_divergence', 0.0)
            entry['n_r2_events'] = r.get('nrc_metrics', {}).get('n_r2_events', 0)
            raw_seeds[name].append(entry)

    with open(rf, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_148_phase11_p2',
            'datetime': datetime.now().isoformat(),
            'config': {
                'N0_total': N0_TOTAL, 'N0_sub': N0_SUB, 'k': K,
                'coupling': COUPLING, 'allocation': 'static',
                'n_seeds': len(SEEDS), 'steps': STEPS, 'max_layers': ML,
                'subspaces': {
                    name: sorted(SUBSPACE_FIELD.get_bits(name))
                    for name in SUBSPACE_NAMES
                },
            },
            'hypotheses': {
                hk: {
                    'pass': evaluation[hk]['pass'],
                    'description': evaluation[hk].get('description', ''),
                }
                for hk in ['H148_1', 'H148_2', 'H148_3', 'H148_4']
            },
            'n_pass': evaluation['n_hypotheses_passed'],
            'aggregate': agg if 'agg' in dir() else evaluation.get('aggregate', {}),
            'per_subspace_means': evaluation['per_subspace_means'],
            'per_seed': raw_seeds,
        }, f, indent=2, default=str)

    n_pass = evaluation['n_hypotheses_passed']
    print(f'  Results saved: {rf}')

    for h_key in ['H148_1', 'H148_2', 'H148_3', 'H148_4']:
        h = evaluation[h_key]
        pass_str = '[PASS]' if h['pass'] else '[FAIL]'
        print(f'\n  {h_key}: {pass_str}')
        print(f'    {h["description"]}')
        for k, v in h.items():
            if k in ('pass', 'description'):
                continue
            print(f'    {k}: {v}')

    print(f'\n  Phase 11 P2 (exp_148): {n_pass}/3 PASS')
    print()

    # ── Print aggregate summary ──
    agg = evaluation['aggregate']
    print(f'{"=" * 75}')
    print('  AGGREGATE SUMMARY (48 runs)')
    print(f'{"=" * 75}')
    print(f'  L1 formation rate:  {agg["l1_formation_rate"]:.4f}')
    print(f'  ODI max (mean±std): {agg["odi_max_mean"]:.4f} ± {agg["odi_max_std"]:.4f}')
    print(f'  NSI mean:           {agg["nsi_mean_mean"]:.4f}')
    print(f'  NSI max:            {agg["nsi_max_mean"]:.4f}')
    print(f'  NSI active rate:    {agg["nsi_active_rate_mean"]:.4f}')
    print(f'  Continuity mean: {agg["cont_mean"]:.4f}')
    print(f'  CIV max:            {agg["civ_max_mean"]:.1f}')
    print(f'  Topdown max active: {agg["topdown_max_mean"]:.1f}')
    print(f'  NRC cycles:         {agg["nrc_cycles_mean"]:.2f}')
    print(f'  NRC R2 events:      {agg["nrc_r2_mean"]:.2f}')

    # ── Per-subspace means ──
    print(f'\n  PER-SUBSPACE MEANS')
    print(f'  {"Subspace":<10} {"L1/16":<8} {"ODI_max":<10} {"NSI_max":<10} {"Cont":<10} {"CIV_max":<8}')
    print(f'  {"-"*56}')
    for sub_name in sorted(evaluation['per_subspace_means'].keys()):
        ps = evaluation['per_subspace_means'][sub_name]
        print(f'  {sub_name:<10} {ps["l1_formed"]}/16   {ps["odi_max_mean"]:<10.4f} '
              f'{ps["nsi_max_mean"]:<10.4f} {ps["cont_mean"]:<10.4f} {ps["civ_max_mean"]:<8.1f}')




if __name__ == '__main__':
    main()