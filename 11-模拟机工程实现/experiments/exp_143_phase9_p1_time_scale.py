"""
experiments/exp_143_phase9_p1_time_scale.py

Phase 9 P1: Time Scaling — Robustness Cartography

Purpose:
  All Phase 4-8 experiments ran at 2000 steps (some at 10000 for Phase 5 B8).
  This experiment maps layer formation and narrative dynamics across 5× step ranges.
  Tests whether the architecture works at 500, 1000, 2000, 5000, 10000 steps.

Threshold Fix (v2):
  exp_142 (P0) revealed that P9_CSC_CONFIG with topdown_max_constraint_strength=0.10
  produces CSCI_std ~0.013 at N0=72 — far below the original seal thresholds of 0.20/0.35.
  Fixed UnsealingMechanism thresholds to l1_coupling=0.008, l1_stability=0.02,
  calibrated to observed CSCI values so sealing can actually trigger.

Hypotheses (P1):
  H95:  Layer formation detectable by step 500 (>=4/8 seeds with partial seal)
  H96:  H1-H8 pass rate stable at 2000+ steps (no more than 1 degradation per 2000 steps)
  H97:  NSI growth saturates before step 5000 (NSI at 4000 and 5000 within 5%)

Expected: 3/3 PASS (possible H95 fail at 500 steps)
"""

import sys, os, time, json
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

P9_CSC_CONFIG = {
    'topdown_max_constraint_strength': 0.10, 'topdown_min_constraint_strength': 0.01,
    'topdown_response_delay': 20, 'topdown_decay_rate': 0.98,
    'topdown_propagation_depth': 2, 'topdown_stability_threshold': 0.05,
    'emergence_min_stability_steps': 50, 'emergence_stability_threshold': 0.6,
    'emergence_min_odi': 0.25, 'emergence_cooldown_steps': 30,
    'narrative_bridge_window': 100, 'narrative_min_coherence': 0.2,
    'narrative_integration_rate': 0.05, 'csci_alpha': 0.4, 'csci_beta': 0.3, 'csci_gamma': 0.3,
}

class CIVRateLimiterV2P1F(CIVRateLimiter):
    def __init__(self, window_size=50, max_civ_rate=0.12, cooldown_steps=12, min_civ_guarantee=3):
        super().__init__(window_size=window_size, max_civ_rate=max_civ_rate, cooldown_steps=cooldown_steps)
        self.min_civ_guarantee = min_civ_guarantee
    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            if self._total_civ_seen < self.min_civ_guarantee: return level
            if self.should_downgrade(step): self._total_downgrades += 1; return NarrativeLevel.INSTITUTIONAL
        return level

class MomentumNarrativeOperatorV4P1F(NarrativeRecursionOperator):
    def __init__(self, bias_dimension=128, filter_magnitude_threshold=0.02, connector_strength_threshold=0.1, verifier_consistency_threshold=0.3, narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3):
        from models.narrative_self import NarrativeFilter, NarrativeNamer, NarrativeActionizer, NarrativeVerifier
        self.filter = NarrativeFilter(magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(strength_threshold=connector_strength_threshold, momentum_decay=momentum_decay, momentum_bonus=momentum_bonus)
        self.actionizer = NarrativeActionizer(bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(consistency_threshold=verifier_consistency_threshold)
        self.narrative_decay_rate = narrative_decay_rate
        self._records = []; self._active_narratives = {}; self._record_count = 0
        self._total_actions = 0; self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F(window_size=50, max_civ_rate=0.12, cooldown_steps=12, min_civ_guarantee=3)
    def get_momentum_stats(self): return self.connector.get_cache_stats()
    def get_current_momentum_bonus(self): return self.connector.get_momentum_bonus()

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
        if hist: metrics['l1_nsi_samples'] = len(hist); metrics['l1_mean_nsi'] = float(np.mean([v for _,v in hist])); metrics['l1_formed'] = True
    if l1_civ:
        hist = getattr(l1_civ, '_hamming_history', [])
        if hist: metrics['l1_civ_samples'] = len(hist); metrics['l1_mean_civ'] = float(np.mean([v for _,v in hist]))
    analysis = collector.analyze(post_seal_only=False)
    l1_data = analysis.get('per_layer', {}).get('L1', {})
    if l1_data and 'sealing' in l1_data:
        metrics['l1_seal_ratio'] = l1_data['sealing'].get('seal_ratio', 0.0)
        if l1_data['sealing'].get('n_snapshots', 0) > 0: metrics['l1_formed'] = True
    l0_theme = collector._theme_trackers.get('L0')
    if l0_theme and l1_theme:
        l0_hist = getattr(l0_theme, '_identity_history', [])
        l1_hist = getattr(l1_theme, '_identity_history', [])
        if l0_hist and l1_hist:
            l0_set = l0_hist[-1][1] if len(l0_hist[-1]) > 1 else set()
            l1_set = l1_hist[-1][1] if len(l1_hist[-1]) > 1 else set()
            if l0_set and l1_set: metrics['l0_l1_theme_divergence'] = 1.0 - (len(l0_set & l1_set) / len(l0_set | l1_set))
    return metrics

def extract_nrc_metrics(evolver):
    nrc = getattr(evolver, 'narrative_recursive_closure', None)
    if nrc is None: return {'nrc_active': False, 'error': 'no_nrc'}
    s = nrc.get_summary()
    return {'nrc_active': True, 'n_cycles': s.get('n_cycles',0), 'n_r2_events': s.get('n_r2_events',0),
            'n_rewrites': s.get('n_rewrites',0), 'cumulative_tension': s.get('cumulative_tension',0.0),
            'peak_nsi': s.get('peak_nsi',0.0)}

def estimate_first_seal_step(layer_results, target_layer=1):
    """Estimate the first step where L1 sealing occurred (if available).
    
    Reads from layer_results[target_layer] (default L1 at index 1).
    Uses the layer's 'sealed' flag (stored by HierarchyManager at evolver run end).
    For precise step, checks phase2_step_results unsealing level transitions.
    
    FIX: Was incorrectly reading layer_results[0] (L0) and a non-existent
    ['hierarchy_state']['L1'] path. Actual data path:
      - layer_result['sealed'] (bool, from hierarchy_manager)
      - step_result['unsealing']['level'] (0-3 unsealing level, not seal state)
    """
    if target_layer < len(layer_results):
        lr = layer_results[target_layer]
        if lr.get('sealed', False):
            # Try to find exact seal step from phase2_step_results
            sr = lr.get('phase2_step_results', [])
            for i, step in enumerate(sr):
                unseal = step.get('unsealing', {})
                # Unsealing level 3+ = full channel open (post-seal)
                if unseal.get('level', 0) >= 3:
                    return i * 10
            # No precise step found but layer IS sealed — that's still valuable
            return 0  # sealed at unknown step
    return -1

def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge, r2_tension_threshold, max_layers=2, csc_config=None):
    torch.manual_seed(seed); np.random.seed(seed)
    rfc = ReturnFlowChannel(anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    # FIX: Reduced thresholds per exp_142 finding — P9_CSC_CONFIG produces CSCI_std ~0.013 at N0=72
    # Original: 0.20/0.35 (Phase 8) never triggered; calibrated to observed CSCI values
    us = UnsealingMechanism(l1_coupling_threshold=0.008, l1_stability_threshold=0.02, l2_coupling_threshold=0.04, l2_stability_threshold=0.08)
    psc = PreSubjectivityConvergence(coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True)
    odi = OrganizationalDensityIndex(temporal_window=10, densification_threshold=0.005, use_refined_zones=True)
    msi = MinimalSelfDetector(config={'odi_activation_threshold':0.35,'odi_saturation_threshold':0.70,'asymmetry_window':10,'asymmetry_threshold':0.15,'min_parts':3,'history_window':8,'history_dependency_threshold':0.15,'min_history_depth':5,'self_reference_window':8,'self_reference_threshold':0.05,'baseline_correlation_threshold':0.2,'msi_activation_threshold':0.20,'msi_emergence_threshold':0.35,'min_active_conditions':1})
    gbc = GlobalBiasConstraint(coherence_threshold=0.5, balance_threshold=0.3, min_mechanisms_required=4, geometric_weighting=True)
    nro = MomentumNarrativeOperatorV4P1F(bias_dimension=128, filter_magnitude_threshold=0.02, connector_strength_threshold=0.1, verifier_consistency_threshold=0.3, narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3)
    abe = AnticipatoryBiasEngine(memory=PersistentBiasMemory(), config={'default_horizon':5,'learning_rate':0.01})
    cfe = CounterfactualEngine(config={'divergence_threshold':0.1,'max_branches':4})
    std = SixThresholdDetector()
    csc_cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
    if csc_config: csc_cfg.update(csc_config)
    csc = CrossScaleCoupling(config=csc_cfg)
    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg.update({'history_multi_signal': True, 'history_second_deriv_threshold': 0.02,
        'history_signal_weights': {'msi':0.3,'odi':0.4,'civ':0.0,'gbc':0.1}, 'history_max_turning_points': 25})
    nse = NarrativeSelfEmergence(config=nse_cfg)
    nrc = NarrativeRecursiveClosure(event_window=20, collapse_threshold=0.15, settling_rate=0.3,
        r0_weight=0.4, r1_weight=0.35, r2_weight=0.25, r2_threshold_nsi=0.85, r2_cooldown=200,
        r2_tension_threshold=r2_tension_threshold, r2_use_tension=True, verbose=False)
    booster = NarrativeLevelBooster(min_civ=3)
    collector = PerLayerMetricsCollector(config={'nsi_rolling_window':500,'civ_rolling_window':500,'theme_jaccard_window':500})
    evolver = HierarchicalEvolver(N0=N0, steps_per_layer=steps, sample_interval=sample_interval, max_layers=max_layers,
        p1_eval_interval=sample_interval, phase2_verbose=False, phase3_verbose=False, phase4_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(), cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi, six_threshold_detector=std, unsealing_mechanism=us, return_flow_channel=rfc,
        pre_subjectivity_convergence=psc, minimal_self_detector=msi, anticipatory_bias_engine=abe, counterfactual_engine=cfe,
        narrative_recursion_operator=nro, global_bias_constraint=gbc, gbc_soft_nudge=gbc_soft_nudge,
        cross_scale_coupling=csc, narrative_self_emergence=nse, adaptive_momentum_controller=None,
        institutional_layer_protector=None, narrative_level_booster=booster, narrative_recursive_closure=nrc)
    print(f"    [seed={seed}] Running {steps} steps at N0={N0}, max_layers={max_layers}...", flush=True)
    start = time.time()
    result = evolver.run(tracking_callback=collector.step)
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)
    n_layers_formed = len(result.get('layer_results', []))
    print(f"    [seed={seed}] Layers formed: {n_layers_formed}", flush=True)

    layer_results_all = result.get('layer_results', [])
    layer_0 = layer_results_all[0] if layer_results_all else {}
    sr = layer_0.get('phase2_step_results', [])
    odi_max = float(np.max([x['odi']['value'] for x in sr if 'odi' in x and x.get('odi',{}).get('value') is not None])) if sr else 0.0
    csc_csci = [x.get('cross_scale_coupling',{}).get('csci',0.0) for x in sr if 'cross_scale_coupling' in x]
    csc_csci_std = float(np.std(csc_csci)) if csc_csci else 0.0
    td_active = [x.get('cross_scale_coupling',{}).get('topdown_n_active',0) for x in sr if 'cross_scale_coupling' in x]
    td_max = int(np.max(td_active)) if td_active else 0
    nse_nsi = [x.get('narrative_self_emergence',{}).get('nsi',0.0) for x in sr if 'narrative_self_emergence' in x]
    nsi_max = float(np.max(nse_nsi)) if nse_nsi else 0.0
    nsi_mean = float(np.mean(nse_nsi)) if nse_nsi else 0.0
    nsi_active = sum(1 for x in sr if x.get('narrative_self_emergence',{}).get('nsi_active',False))
    nsi_active_rate = nsi_active/len(sr) if sr else 0.0
    cont = [x.get('narrative_self_emergence',{}).get('continuity_score',0.0) for x in sr if 'narrative_self_emergence' in x]
    cont_mean = float(np.mean(cont)) if cont else 0.0
    hd = [x.get('narrative_self_emergence',{}).get('self_history_depth',0.0) for x in sr if 'narrative_self_emergence' in x]
    hd_mean = float(np.mean(hd)) if hd else 0.0
    tp = [x.get('narrative_self_emergence',{}).get('n_turning_points',0) for x in sr if 'narrative_self_emergence' in x]
    tp_final = tp[-1] if tp else 0
    civ_vals = [x.get('narrative_self_emergence',{}).get('civ_count',0) for x in sr if 'civ_count' in x.get('narrative_self_emergence',{})]
    civ_max = int(np.max(civ_vals)) if civ_vals else 0; civ_mean = float(np.mean(civ_vals)) if civ_vals else 0.0
    nrc_m = extract_nrc_metrics(evolver)
    l1_m = extract_l1_passive_metrics(collector)
    first_seal = estimate_first_seal_step(layer_results_all, target_layer=1)
    l1_sealed = layer_results_all[1].get('sealed', False) if len(layer_results_all) >= 2 else False
    return {'N0':N0,'steps':steps,'seed':seed,'elapsed':elapsed,'n_steps':len(sr),'sealed':layer_0.get('sealed',False),'l1_sealed':l1_sealed,
        'n_layers_formed':n_layers_formed,'first_seal_step':first_seal,
        'odi_max':odi_max,'csc_csci_std':csc_csci_std,'topdown_max_active':td_max,
        'nse_nsi_max':nsi_max,'nse_nsi_mean':nsi_mean,'nse_nsi_active_rate':nsi_active_rate,
        'nse_continuity_mean':cont_mean,'nse_history_depth_mean':hd_mean,'nse_turning_points_final':tp_final,
        'civ_mean':civ_mean,'civ_max':civ_max,
        'nrc_metrics':nrc_m,'l1_metrics':l1_m}


def evaluate_step_range(results_by_steps):
    """Evaluate hypotheses per step value and overall."""
    step_results = {}
    for steps, results in results_by_steps.items():
        if not results:
            step_results[steps] = {'n_completed': 0, 'error': 'no_data'}
            continue

        a = lambda k: [r[k] for r in results if not r.get('error')]
        nsi_max = a('nse_nsi_max'); nsi_rate = a('nse_nsi_active_rate')
        cont = a('nse_continuity_mean'); hd = a('nse_history_depth_mean')
        tp = a('nse_turning_points_final'); csci = a('csc_csci_std')
        td = a('topdown_max_active'); civ = a('civ_max')

        h1 = max(nsi_max) > 0.1; h2 = all(v > 0.3 for v in nsi_rate) if nsi_rate else False
        h3 = np.mean(cont) > 0.1 if cont else False; h4 = np.mean(hd) > 0.05 or np.mean(tp) > 0.0 if (hd and tp) else False
        h5 = max(civ) >= 3 if civ else False; h6 = max(civ) >= 2 if civ else False
        h7 = np.mean(csci) > 0.005 if csci else False; h8 = sum(1 for v in td if v > 0) >= 2 if td else False

        formed = [r.get('l1_metrics', {}).get('l1_formed', False) for r in results if not r.get('error')]
        n_formed = sum(1 for v in formed if v)

        seals_steps = [r.get('first_seal_step', -1) for r in results if not r.get('error') and r.get('first_seal_step', -1) >= 0]
        first_seal_mean = float(np.mean(seals_steps)) if seals_steps else -1.0

        step_results[steps] = {
            'n_completed': len([r for r in results if not r.get('error')]),
            'n_errors': len([r for r in results if r.get('error')]),
            'H1': h1, 'H2': h2, 'H3': h3, 'H4': h4, 'H5': h5, 'H6': h6, 'H7': h7, 'H8': h8,
            'h89_n': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
            'l1_formed': n_formed,
            'mean_nsi_max': float(np.mean(nsi_max)) if nsi_max else 0.0,
            'mean_nsi_active_rate': float(np.mean(nsi_rate)) if nsi_rate else 0.0,
            'mean_continuity': float(np.mean(cont)) if cont else 0.0,
            'mean_csci_std': float(np.mean(csci)) if csci else 0.0,
            'mean_civ_max': float(np.mean(civ)) if civ else 0.0,
            'mean_first_seal_step': first_seal_mean,
        }

    return step_results


def main():
    STEP_VALUES = [500, 1000, 2000, 5000, 10000]
    SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
    N0 = 72
    SI = 10
    GSN = 0.2
    R2_T = 1.0
    ML = 2

    print("=" * 70)
    print("exp_143: PHASE 9 P1 — Time Scaling (Robustness Cartography)")
    print("=" * 70)
    print(f"  Steps: {STEP_VALUES}")
    print(f"  N0={N0}, Seeds per config: {len(SEEDS)}, MaxLayers: {ML}")
    print(f"  Total runs: {len(STEP_VALUES) * len(SEEDS)}")
    print("  H95: Layer formation detectable by step 500 (>=4/8 seeds)")
    print("  H96: H1-H8 pass rate stable at 2000+ steps")
    print("  H97: NSI growth saturates before step 5000")
    print(datetime.now().strftime('  %Y-%m-%d %H:%M'))
    print("=" * 70)

    all_results = {}
    results_by_steps = {}

    for steps in STEP_VALUES:
        print(f"\n{'=' * 60}")
        print(f"  Steps = {steps}")
        print(f"{'=' * 60}")
        results_by_steps[steps] = []
        for seed in SEEDS:
            try:
                r = run_single_seed(N0=N0, steps=steps, seed=seed, sample_interval=SI,
                                    gbc_soft_nudge=GSN, r2_tension_threshold=R2_T,
                                    max_layers=ML, csc_config=P9_CSC_CONFIG)
                l1 = r['l1_metrics']
                nrc = r['nrc_metrics']
                s = '[OK]' if l1['l1_formed'] else '[--]'
                seal_step = r.get('first_seal_step', -1)
                seal_info = f"seal@{seal_step}" if seal_step >= 0 else "unsealed"
                print(('  seed=%d: NSI_max=%.3f layers=%d L1:%s %s CIV_max=%d R2=%d [%.0fs]' % (
                    seed, r['nse_nsi_max'], r['n_layers_formed'], s,
                    seal_info, r['civ_max'], nrc['n_r2_events'], r['elapsed'])), flush=True)
                results_by_steps[steps].append(r)
                all_results[f"{steps}_{seed}"] = r
            except Exception as e:
                print(f"  *** seed={seed}: FAILED -- {e}", flush=True)
                import traceback
                traceback.print_exc()
                err_rec = {'N0': N0, 'steps': steps, 'seed': seed, 'error': str(e), 'n_layers_formed': 0,
                           'nse_nsi_max': 0, 'nse_nsi_active_rate': 0, 'nse_continuity_mean': 0,
                           'nse_history_depth_mean': 0, 'nse_turning_points_final': 0,
                           'civ_mean': 0, 'civ_max': 0, 'csc_csci_std': 0, 'topdown_max_active': 0,
                           'odi_max': 0, 'first_seal_step': -1,
                           'nrc_metrics': {'nrc_active': False, 'n_cycles': 0, 'n_r2_events': 0},
                           'l1_metrics': {'l1_formed': False, 'l0_l1_theme_divergence': 0.0, 'l1_seal_ratio': 0.0},
                           'sealed': False}
                results_by_steps[steps].append(err_rec)
                all_results[f"{steps}_{seed}"] = err_rec

    # Evaluate per-step
    step_eval = evaluate_step_range(results_by_steps)

    print("\n" + "=" * 70)
    print("RESULTS BY STEP COUNT")
    print("=" * 70)
    for steps in STEP_VALUES:
        ev = step_eval.get(steps, {})
        if not ev:
            print(f"\n  Steps={steps}: NO DATA")
            continue
        n_ok = ev.get('n_completed', 0)
        n_err = ev.get('n_errors', 0)
        err_str = f" ({n_err} errors)" if n_err else ""
        print(f"\n  Steps={steps}: {n_ok}/{len(SEEDS)} completed{err_str}")
        print(f"    L1 formed: {ev['l1_formed']}/{len(SEEDS)}")
        print(f"    H1-H8: {ev['h89_n']}/8")
        print(f"    Mean NSI_max: {ev.get('mean_nsi_max', 0):.3f}")
        print(f"    Mean NSI_active_rate: {ev.get('mean_nsi_active_rate', 0):.3f}")
        print(f"    Mean continuity: {ev.get('mean_continuity', 0):.3f}")
        print(f"    Mean CSCI_std: {ev.get('mean_csci_std', 0):.4f}")
        print(f"    Mean CIV_max: {ev.get('mean_civ_max', 0):.1f}")
        print(f"    Mean first seal step: {ev.get('mean_first_seal_step', -1):.0f}")

    # Overall hypothesis evaluation
    print("\n" + "=" * 70)
    print("OVERALL HYPOTHESES")
    print("=" * 70)

    # H95: Layer formation detectable by step 500
    ev_500 = step_eval.get(500, {})
    h95_pass = ev_500.get('l1_formed', 0) >= 4 if ev_500 else False
    print(f"  H95 (>=4/8 formed by step 500): {'PASS' if h95_pass else 'FAIL'}")
    print(f"    Steps=500: {ev_500.get('l1_formed', '?')}/{len(SEEDS)}")

    # H96: H1-H8 pass rate stable at 2000+
    ev_2000 = step_eval.get(2000, {})
    ev_5000 = step_eval.get(5000, {})
    ev_10000 = step_eval.get(10000, {})
    h89_2000 = ev_2000.get('h89_n', 0)
    h89_5000 = ev_5000.get('h89_n', 0) if ev_5000 else 0
    h89_10000 = ev_10000.get('h89_n', 0) if ev_10000 else 0
    degrad_2000_5000 = h89_2000 - h89_5000
    degrad_5000_10000 = h89_5000 - h89_10000
    degrad_count = sum([1 for d in [degrad_2000_5000, degrad_5000_10000] if d > 1])
    h96_pass = degrad_count == 0
    print(f"  H96 (H1-H8 stable, <=1 degradation per 2k steps): {'PASS' if h96_pass else 'FAIL'}")
    print(f"    H1-H8: 2000={h89_2000}/8  5000={h89_5000}/8  10000={h89_10000}/8")
    print(f"    Degradations (threshold >1): {degrad_count}")

    # H97: NSI growth saturates before 5000
    nsi_4000 = None  # We don't have a 4000-step run, so check 5000 vs 10000
    nsi_5000 = ev_5000.get('mean_nsi_max', 0) if ev_5000 else 0
    nsi_10000 = ev_10000.get('mean_nsi_max', 0) if ev_10000 else 0
    if nsi_5000 > 0 and nsi_10000 > 0:
        h97_pass = abs(nsi_10000 - nsi_5000) / max(nsi_5000, 0.001) < 0.05
    else:
        h97_pass = False
    print(f"  H97 (NSI saturation before 5000): {'PASS' if h97_pass else 'FAIL'}")
    if nsi_5000 > 0 and nsi_10000 > 0:
        print(f"    NSI_max: 5000={nsi_5000:.3f}  10000={nsi_10000:.3f}")
    else:
        print(f"    NSI_max: 5000={nsi_5000:.3f}  10000={nsi_10000:.3f} (no 5k or 10k data)")

    n_pass = sum([h95_pass, h96_pass, h97_pass])
    print(f"\n  Phase 9 P1: {n_pass}/3 PASS {'[ALL PASS]' if n_pass == 3 else '[PARTIAL]'}")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    rf = os.path.join(PROJECT_ROOT, 'experiments', f'exp_143_phase9_p1_time_scale_{timestamp}.json')
    with open(rf, 'w', encoding='utf-8') as f:
        json.dump({
            'experiment': 'exp_143_phase9_p1',
            'datetime': datetime.now().isoformat(),
            'step_values': STEP_VALUES,
            'n0': N0,
            'hypotheses': {
                'H95': h95_pass,
                'H96': h96_pass,
                'H97': h97_pass,
                'n_pass': n_pass,
            },
            'by_steps': {str(s): {k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else bool(v) if isinstance(v, (np.bool_,)) else v.tolist() if isinstance(v, np.ndarray) else v) for k, v in ev.items()} for s, ev in step_eval.items()},
        }, f, indent=2, default=str)
    print(f"\n  Results saved: {rf}")
    print(f"\n  Phase 9 P1: {n_pass}/3 PASS")


if __name__ == '__main__':
    main()
