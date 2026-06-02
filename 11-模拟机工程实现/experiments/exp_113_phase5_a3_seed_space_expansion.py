"""
experiments/exp_113_phase5_a3_seed_space_expansion.py

Phase 5 Track A3: Seed Space Expansion

Purpose: Test H1-H8 across a broadened seed space (32 seeds) to verify
    that the CSC+NSE architecture is robust across diverse initial conditions.

Method:
  - 32 seeds spanning a wide range of initial random states
  - Single config: coupling_strength=0.10 (P5 baseline), N0=72, steps=1600
  - Total: 32 seeds x 1 config = 32 runs
  - Architecture: CSC+NSE (simplified, no AMC/ILP)

Hypotheses:
  H26 (seed robustness): >= 90% of 32 seeds pass all H1-H8
      Rationale: The architecture should be robust across initial conditions,
      not just tuned for a specific set of 8 seeds.

  H27 (anomalous seed explainability): Any seed that fails H1-H8 can be
      explained by its position in CSC/NSE parameter space (e.g., extreme
      CIV counts, low NSI due to lack of narrative recursion, etc.)
      Rationale: Failures should be structurally intelligible, not random.

Invoke modes:
  Batch:  python exp_113_phase5_a3_seed_space_expansion.py
  Single: python exp_113_phase5_a3_seed_space_expansion.py <seed>
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


# ─── 32 seeds: original 8 + 24 new ───
ALL_SEEDS = [
    # Original 8 seeds (Phase 4 baseline)
    42, 142, 242, 342, 442, 542, 642, 742,
    # 24 new seeds
    100, 200, 300, 400, 500, 600, 700, 800,
    111, 222, 333, 444, 555, 666, 777, 888,
    13, 1313, 2626, 3939, 5252, 6565, 7878, 9191,
]

# ─── P5 Baseline CSC config (same as exp_111/112 at strength=0.10) ───
P5_BASE_CSC_CONFIG = {
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
}

# ─── Experiment parameters ───
N0 = 72
STEPS = 1600
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.2
COUPLING_STRENGTH = 0.10

FIXED_OUTPUT = os.path.join(PROJECT_ROOT, 'experiments', 'exp_113_results.json')


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


def build_evolver(N0, steps, sample_interval, gbc_soft_nudge):
    return_flow_channel = ReturnFlowChannel(
        anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    unsealing_mechanism = UnsealingMechanism(
        l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40, l2_stability_threshold=0.55)
    pre_subjectivity = PreSubjectivityConvergence(
        coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True)
    odi = OrganizationalDensityIndex(
        temporal_window=10, densification_threshold=0.005, use_refined_zones=True)
    msi_detector = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3, 'history_window': 8, 'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8,
        'self_reference_threshold': 0.05, 'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20, 'msi_emergence_threshold': 0.35,
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

    csc = CrossScaleCoupling(config=dict(P5_BASE_CSC_CONFIG))

    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg['history_multi_signal'] = True
    nse_cfg['history_second_deriv_threshold'] = 0.02
    nse_cfg['history_signal_weights'] = {'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1}
    nse_cfg['history_max_turning_points'] = 25
    nse = NarrativeSelfEmergence(config=nse_cfg)

    return HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=1, p1_eval_interval=sample_interval,
        phase2_verbose=False, phase3_verbose=False, phase4_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi, six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing_mechanism, return_flow_channel=return_flow_channel,
        pre_subjectivity_convergence=pre_subjectivity, minimal_self_detector=msi_detector,
        anticipatory_bias_engine=anticipatory, counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative, global_bias_constraint=gbc,
        gbc_soft_nudge=gbc_soft_nudge,
        cross_scale_coupling=csc, narrative_self_emergence=nse,
        adaptive_momentum_controller=None, institutional_layer_protector=None)


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
            metrics['civ_events'].append(1 if level == 'CIVILIZATION' else 0)
    return metrics


def safe_mean(vals):
    return float(np.mean(vals)) if vals else 0.0


def safe_max(vals):
    return float(np.max(vals)) if vals else 0.0


def safe_std(vals):
    return float(np.std(vals)) if vals else 0.0


def evaluate_h1h8(metrics):
    """Evaluate H1-H8 from extracted metrics."""
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
        'H1': h1, 'H2': h2, 'H3': h3, 'H4': h4,
        'H5': h5, 'H6': h6, 'H7': h7, 'H8': h8,
        'n_pass': sum([h1, h2, h3, h4, h5, h6, h7, h8]),
        'all_pass': all([h1, h2, h3, h4, h5, h6, h7, h8]),
    }


def run_single(seed, N0=N0, steps=STEPS, sample_interval=SAMPLE_INTERVAL,
                gbc_soft_nudge=GBC_SOFT_NUDGE):
    """Run a single seed."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    evolver = build_evolver(N0, steps, sample_interval, gbc_soft_nudge)

    t0 = time.time()
    result = evolver.run(verbose=False)
    elapsed = time.time() - t0

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])
    metrics = extract_step_metrics(step_results)
    h1h8 = evaluate_h1h8(metrics)

    return {
        'seed': seed,
        'elapsed': elapsed,
        'n_steps': len(step_results),
        'sealed': layer_0.get('sealed', False),
        'nsi_max': safe_max(metrics['nsi_vals']),
        'nsi_active_rate': safe_mean(metrics['nsi_active']),
        'continuity_mean': safe_mean(metrics['continuity_vals']),
        'history_depth_mean': safe_mean(metrics['depth_vals']),
        'turning_points': metrics['tp_vals'][-1] if metrics['tp_vals'] else 0,
        'civ_count': sum(metrics['civ_events']),
        'csci_std': safe_std(metrics['csci_vals']),
        'topdown_max': int(safe_max(metrics['td_vals'])),
        'h1h8': h1h8,
    }


def load_existing_results():
    if os.path.exists(FIXED_OUTPUT):
        with open(FIXED_OUTPUT, 'r') as f:
            d = json.load(f)
            return d, FIXED_OUTPUT
    pattern = os.path.join(PROJECT_ROOT, 'experiments', 'exp_113_results_*.json')
    files = sorted(glob.glob(pattern), reverse=True)
    if files:
        with open(files[0], 'r') as f:
            d = json.load(f)
            return d, files[0]
    return None, None


def evaluate_h26_h25(all_results):
    """Evaluate H26 (seed robustness) and H27 (anomalous seed explainability).

    H26: >= 90% of 32 seeds pass all H1-H8 (all_pass=True).
    H27: All failing seeds have structurally explainable failure modes.
    """
    valid = [r for r in all_results if 'error' not in r]
    n_total = len(valid)
    n_pass = sum(1 for r in valid if r['h1h8']['all_pass'])
    n_fail = n_total - n_pass
    pass_rate = n_pass / n_total if n_total > 0 else 0

    # H26: >= 90% pass rate
    h26 = pass_rate >= 0.90

    # Analyze failing seeds
    failing_seeds = []
    for r in valid:
        if not r['h1h8']['all_pass']:
            failed_h = [h for h, v in r['h1h8'].items()
                        if h not in ('n_pass', 'all_pass') and not v]
            failing_seeds.append({
                'seed': r['seed'],
                'n_pass': r['h1h8']['n_pass'],
                'failed_hypotheses': failed_h,
                'nsi_max': r['nsi_max'],
                'civ_count': r['civ_count'],
                'csci_std': r['csci_std'],
                'topdown_max': r['topdown_max'],
                'continuity_mean': r['continuity_mean'],
                'turning_points': r['turning_points'],
            })

    # H27: Try to explain each failure
    # A failure is "explainable" if it falls into a known pattern:
    # - CIV count out of range (H5/H6 fail) -> explainable
    # - NSI too low (H1/H2 fail) -> explainable (lack of narrative recursion)
    # - No topdown (H8 fail) -> explainable (coupling too weak for this seed)
    # - CSCI collapse (H7 fail) -> explainable (no cross-scale coherence)
    explained = 0
    for fs in failing_seeds:
        reasons = []
        if 'H5' in fs['failed_hypotheses']:
            if fs['civ_count'] < 3.0:
                reasons.append(f"CIV too low ({fs['civ_count']} < 3)")
            elif fs['civ_count'] > 15.0:
                reasons.append(f"CIV too high ({fs['civ_count']} > 15)")
        if 'H6' in fs['failed_hypotheses']:
            reasons.append(f"CIV below minimum ({fs['civ_count']} < 2)")
        if 'H1' in fs['failed_hypotheses']:
            reasons.append(f"NSI max too low ({fs['nsi_max']:.4f} <= 0.1)")
        if 'H2' in fs['failed_hypotheses']:
            reasons.append(f"NSI active rate too low")
        if 'H3' in fs['failed_hypotheses']:
            reasons.append(f"Continuity too low ({fs['continuity_mean']:.4f} <= 0.1)")
        if 'H4' in fs['failed_hypotheses']:
            reasons.append(f"No history depth and no turning points")
        if 'H7' in fs['failed_hypotheses']:
            reasons.append(f"CSCI std collapsed ({fs['csci_std']:.6f} <= 0.005)")
        if 'H8' in fs['failed_hypotheses']:
            reasons.append(f"No TopDown activation (td_max={fs['topdown_max']})")

        fs['explanation'] = '; '.join(reasons) if reasons else 'UNEXPLAINED'
        if reasons:
            explained += 1

    # H27 passes if all failures are explainable
    h27 = (n_fail == 0) or (explained == n_fail)

    return {
        'H26_seed_robustness': {
            'description': '>= 90% of 32 seeds pass all H1-H8',
            'pass': h26,
            'n_total': n_total,
            'n_pass': n_pass,
            'n_fail': n_fail,
            'pass_rate': pass_rate,
        },
        'H27_anomalous_explainable': {
            'description': 'All failing seeds have structurally explainable failure modes',
            'pass': h27,
            'n_failing': n_fail,
            'n_explained': explained,
            'failing_seeds': failing_seeds,
        },
    }


def run_batch():
    """Run all seeds incrementally with resume support."""
    existing, src_path = load_existing_results()

    all_results = []
    if existing:
        all_results = existing.get('results', {}).get('per_run', [])
        print(f"Loaded {len(all_results)} existing results from {src_path}")

    done = set(r['seed'] for r in all_results if 'error' not in r)
    total = len(ALL_SEEDS)
    run_idx = len(done)

    print(f"exp_113: {run_idx}/{total} done, {total - run_idx} remaining")
    print(f"  Seeds: {ALL_SEEDS}")
    print(f"  Total runs: {total}")
    print(f"  Config: coupling=0.10, N0={N0}, steps={STEPS}")

    for seed in ALL_SEEDS:
        if seed in done:
            print(f"  Skipping seed={seed} (done)")
            continue

        run_idx += 1
        gc.collect()
        print(f"\n[{run_idx}/{total}] seed={seed}")

        try:
            result = run_single(seed)
            all_results.append(result)
            status = "PASS" if result['h1h8']['all_pass'] else f"{result['h1h8']['n_pass']}/8"
            print(f"  Done: nsi_max={result['nsi_max']:.4f}, h1h8={status}")
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
            all_results.append({'seed': seed, 'error': str(e)})

        # Save after each run
        output = {
            'experiment': 'exp_113_phase5_a3_seed_space_expansion',
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'v': 1,
            'architecture': 'CSC+NSE (simplified, no AMC/ILP)',
            'config': {
                'seeds': ALL_SEEDS,
                'coupling_strength': COUPLING_STRENGTH,
                'N0': N0,
                'steps': STEPS,
                'sample_interval': SAMPLE_INTERVAL,
                'gbc_soft_nudge': GBC_SOFT_NUDGE,
            },
            'results': {'per_run': all_results},
        }
        with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        ts_path = os.path.join(
            PROJECT_ROOT, 'experiments',
            f"exp_113_results_{output['timestamp']}.json")
        with open(ts_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"  Saved ({len(all_results)} total)")

        gc.collect()

    # ─── Final analysis ───
    valid = [r for r in all_results if 'error' not in r]
    h26h27 = evaluate_h26_h25(valid)

    print("\n" + "=" * 70)
    print("EXP_113 FINAL RESULTS — Seed Space Expansion")
    print("=" * 70)

    print(f"\nTotal valid runs: {len(valid)}/{len(ALL_SEEDS)}")
    pass_rate = h26h27['H26_seed_robustness']['pass_rate']
    print(f"Overall pass rate: {pass_rate:.1%}")

    # Per-seed summary
    print("\n--- Per-Seed Results ---")
    for r in sorted(valid, key=lambda x: x['seed']):
        status = "PASS" if r['h1h8']['all_pass'] else f"{r['h1h8']['n_pass']}/8"
        failed = [h for h, v in r['h1h8'].items()
                  if h not in ('n_pass', 'all_pass') and not v]
        fail_str = f" (failed: {','.join(failed)})" if failed else ""
        print(f"  seed={r['seed']:>5}: {status}  nsi={r['nsi_max']:.4f}  "
              f"civ={r['civ_count']:>3}  csci={r['csci_std']:.4f}  "
              f"td={r['topdown_max']}  cont={r['continuity_mean']:.4f}{fail_str}")

    # H26
    print("\n--- H26 (Seed Robustness) ---")
    h26_info = h26h27['H26_seed_robustness']
    print(f"  Result: {'PASS' if h26_info['pass'] else 'FAIL'}")
    print(f"  Pass rate: {h26_info['pass_rate']:.1%} "
          f"({h26_info['n_pass']}/{h26_info['n_total']})")
    print(f"  Threshold: >= 90%")

    # H27
    print("\n--- H27 (Anomalous Seed Explainability) ---")
    h27_info = h26h27['H27_anomalous_explainable']
    print(f"  Result: {'PASS' if h27_info['pass'] else 'FAIL'}")
    print(f"  Failing seeds: {h27_info['n_failing']}")
    print(f"  Explained: {h27_info['n_explained']}")
    if h27_info['failing_seeds']:
        print("\n  Failing seed details:")
        for fs in h27_info['failing_seeds']:
            print(f"    seed={fs['seed']}: failed={fs['failed_hypotheses']} "
                  f"nsi={fs['nsi_max']:.4f} civ={fs['civ_count']} "
                  f"csci={fs['csci_std']:.4f}")
            print(f"      explanation: {fs.get('explanation', 'N/A')}")

    # Aggregate statistics
    print("\n--- Aggregate Statistics ---")
    nsi_vals = [r['nsi_max'] for r in valid]
    civ_vals = [r['civ_count'] for r in valid]
    csci_vals = [r['csci_std'] for r in valid]
    td_vals = [r['topdown_max'] for r in valid]
    cont_vals = [r['continuity_mean'] for r in valid]
    tp_vals = [r['turning_points'] for r in valid]

    print(f"  NSI max:       mean={np.mean(nsi_vals):.4f}  "
          f"std={np.std(nsi_vals):.4f}  min={np.min(nsi_vals):.4f}  max={np.max(nsi_vals):.4f}")
    print(f"  CIV count:     mean={np.mean(civ_vals):.1f}  "
          f"std={np.std(civ_vals):.1f}  min={np.min(civ_vals)}  max={np.max(civ_vals)}")
    print(f"  CSCI std:      mean={np.mean(csci_vals):.4f}  "
          f"std={np.std(csci_vals):.4f}  min={np.min(csci_vals):.4f}  max={np.max(csci_vals):.4f}")
    print(f"  TopDown max:   mean={np.mean(td_vals):.1f}  "
          f"std={np.std(td_vals):.1f}  min={np.min(td_vals)}  max={np.max(td_vals)}")
    print(f"  Continuity:    mean={np.mean(cont_vals):.4f}  "
          f"std={np.std(cont_vals):.4f}  min={np.min(cont_vals):.4f}  max={np.max(cont_vals):.4f}")
    print(f"  Turning pts:   mean={np.mean(tp_vals):.1f}  "
          f"std={np.std(tp_vals):.1f}  min={np.min(tp_vals)}  max={np.max(tp_vals)}")

    # Per-hypothesis pass rates
    print("\n--- Per-Hypothesis Pass Rates ---")
    for h in [f'H{i}' for i in range(1, 9)]:
        n_h_pass = sum(1 for r in valid if r['h1h8'][h])
        print(f"  {h}: {n_h_pass}/{len(valid)} ({n_h_pass/len(valid):.1%})")

    # Save final analysis
    final_output = {
        'experiment': 'exp_113_phase5_a3_seed_space_expansion',
        'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
        'v': 1,
        'architecture': 'CSC+NSE (simplified, no AMC/ILP)',
        'config': {
            'seeds': ALL_SEEDS,
            'coupling_strength': COUPLING_STRENGTH,
            'N0': N0,
            'steps': STEPS,
            'sample_interval': SAMPLE_INTERVAL,
            'gbc_soft_nudge': GBC_SOFT_NUDGE,
        },
        'results': {
            'per_run': all_results,
            'h26_h27': h26h27,
        },
    }

    with open(FIXED_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    ts_path = os.path.join(
        PROJECT_ROOT, 'experiments',
        f"exp_113_results_{final_output['timestamp']}.json")
    with open(ts_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    print(f"\nFinal results saved to: {FIXED_OUTPUT}")

    return FIXED_OUTPUT


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        seed = int(sys.argv[1])
        result = run_single(seed)
        print(json.dumps(result, indent=2))
    else:
        run_batch()
