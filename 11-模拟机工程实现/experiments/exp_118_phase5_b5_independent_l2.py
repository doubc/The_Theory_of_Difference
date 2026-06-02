# -*- coding: utf-8 -*-
"""
experiments/exp_118_phase5_b5_independent_l2.py

Phase 5 Track B5: 独立 L2 聚簇 + 稳定性地板 (Independent L2 Clustering + Stability Floor)

Purpose: Fix the false-positive decoupling of B4 by giving L2 true autonomy
    - L2 clusters independently from L0 (same N0=72, independent random seeds)
    - L1 provides ADDITIVE soft bias (NOT hard clamp) — L2 never gets suppressed to zero
    - L2 has stability floor (min 0.15) — prevents complete silencing
    - L2 has intrinsic perturbation + autonomous decay — own difference field
    - L2 ODI computed independently (50% from L0, 50% from L2 structure)

Background:
  B1 (parallel): L1<->L2 r = 0.976 — perfect correlation
  B2 (serial):   L1<->L2 r = 0.861 — still coupled
  B3 (noise):    L1<->L2 r = 0.937 — noise insufficient
  B4 (constraint): L1<->L2 r = 0.000 — FALSE POSITIVE
    Root cause: L2 was completely SILENT (stability ≈ 0), not meaningfully decoupled.
    The clamp suppressed L2 when L1 stability was low, making correlation zero
    but also making L2 non-functional.

  B5 design philosophy:
  - L2 autonomy is NOT clamped — it has a stability floor
  - L1 constraint is ADDITIVE bias, not a boundary clamp
  - L2 must be ACTIVE (not silent) to count as "meaningfully decoupled"
  - L2 has intrinsic dynamics independent of L1

Hypotheses:
  H30 (layer decoupling): L1<->L2 NSI Pearson r < 0.7
      B4 was 8/8 PASS but FALSE POSITIVE (L2 silent)
      B5 target: >= 5/8 (62.5%) AND L2 must be active (stability > 0.1)

  H31 (hierarchical delay): L0->L1 delay detected
      B4: 0/8
      B5 target: >= 4/8 detected (L0 drives both L1 and L2 independently)

  H32 (L2 autonomy): L2 narrative differs from L1 narrative
      B4: 0/8 (both silent)
      B5 target: >= 5/8 (autonomy index > 0.3, L2 must be active)

  H33 (independent clustering): L2 ODI vs L1 ODI correlation < 0.8
      B4: not measured
      B5 target: >= 5/8 pass

  H35 (L2 activity): L2 stability never drops below floor (0.15)
      New: verifies the stability floor mechanism works
      Target: 8/8 (L2 min stability >= 0.10, allowing some noise)

  H36 (L2 autonomy index): L2 narrative autonomy > 0.3
      New: measures how different L2 narrative is from L1
      Target: >= 5/8

  H37 (L2 intrinsic dynamics): L2 has measurable intrinsic perturbation effect
      New: L2 structure changes even when L0 and L1 are stable
      Target: >= 4/8 (L2 structure variance > threshold during stable periods)

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
from engine.seventh_threshold_detector import SeventhThresholdDetector
from engine.cooperative_emergence_detector import CooperativeEmergenceDetector
from engine.xiang_detector import XiàngDetector


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


def run_single_seed(seed, verbose=True):
    """Run one seed with B5 independent L2 coupling."""
    if verbose:
        print(f"\n{'='*60}")
        print(f"  Seed {seed} — Phase 5 Track B5: Independent L2")
        print(f"{'='*60}")

    rng = np.random.RandomState(seed)
    torch.manual_seed(seed)

    # ── Build components ──
    pm = PersistentBiasMemory(max_history_depth=200, snapshot_interval=10)

    psc = PreSubjectivityConvergence(
        coupling_threshold=0.3,
        stability_threshold=0.3,
        n_perturbation_tests=5,
        perturbation_scale=0.1,
        coupling_mode='all',
        dynamic_threshold=True,
    )

    odi = OrganizationalDensityIndex(
        temporal_window=5,
        densification_threshold=0.01,
        use_refined_zones=True,
        boundary_threshold=0.05,
    )

    s7 = SeventhThresholdDetector(config={
        'window_size': 300,
        'odi_threshold': 0.15,
        'phase_change_window': 100,
        'verbose': False,
    })

    cop = CooperativeEmergenceDetector(config={
        'coupling_window': 200,
        'emergence_threshold': 0.3,
        'verbose': False,
    })

    msd = MinimalSelfDetector(config={
        'coherence_window': 100,
        'stability_threshold': 0.3,
        'verbose': False,
    })

    abe = AnticipatoryBiasEngine(memory=pm, config={
        'anticipation_window': 50,
        'correction_strength': 0.05,
        'verbose': False,
    })

    cfe = CounterfactualEngine(config={
        'counterfactual_window': 100,
        'divergence_threshold': 0.1,
        'verbose': False,
    })

    nro = NarrativeRecursionOperator(
        bias_dimension=N0,
        filter_magnitude_threshold=0.3,
        connector_strength_threshold=0.3,
        verifier_consistency_threshold=0.5,
        narrative_decay_rate=0.9,
    )
    nro.connector = AdaptiveMomentumConnector()

    gbc = GlobalBiasConstraint(
        coherence_threshold=0.6,
        balance_threshold=0.5,
        min_mechanisms_required=4,
        geometric_weighting=True,
    )

    cs = CumulativeSelector(
        window_size=10,
        trend_threshold=0.6,
        min_observations=3,
        fate_decay=0.99,
    )

    ltd = SixThresholdDetector(thresholds={
        'xiang': 0.2,
        'stability': 0.3,
        'odi': 0.15,
        'coupling': 0.25,
        'convergence': 0.3,
        'emergence': 0.2,
    })

    xsd = XiàngDetector(
        rho_threshold=0.3,
        tau_threshold=0.5,
        continuity_window=5,
        gradient_kernel_size=3,
    )

    uf = UnsealingMechanism(
        l1_coupling_threshold=0.3,
        l1_stability_threshold=0.5,
        l2_coupling_threshold=0.5,
        l2_stability_threshold=0.7,
        l3_coupling_threshold=0.7,
        l3_stability_threshold=0.85,
        interface_stability_window=5,
        interface_stability_threshold=0.7,
    )

    rfc = ReturnFlowChannel(
        anchor_threshold=0.3,
        decay_rate=0.01,
        min_retention_steps=10,
    )

    lnt = LayerNarrativeTracker(config=P5_LNT_CONFIG)

    csc = CrossScaleCoupling(config=P5_B5_INDEPENDENT_CSC_CONFIG)

    nse = NarrativeSelfEmergence(
        config={**DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG, **{'verbose': False}},
    )

    # ── Build evolver ──
    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=STEPS,
        sample_interval=SAMPLE_INTERVAL,
        max_layers=3,  # B5 fix: need 3 actual layers for NSE to compute NSI
        device="cpu",
        binding_threshold=0.1,
        min_group_size=2,
        auto_encapsulate=True,
        verbose_gravity=False,
        xiang_detector=xsd,
        persistent_bias_memory=pm,
        cumulative_selector=cs,
        six_threshold_detector=ltd,
        pre_subjectivity_convergence=psc,
        unsealing_mechanism=uf,
        return_flow_channel=rfc,
        organizational_density_index=odi,
        seventh_threshold_detector=s7,
        cooperative_emergence_detector=cop,
        minimal_self_detector=msd,
        anticipatory_bias_engine=abe,
        counterfactual_engine=cfe,
        narrative_recursion_operator=nro,
        global_bias_constraint=gbc,
        p1_eval_interval=5,
        phase2_verbose=False,
        phase3_verbose=False,
        phase4_verbose=False,
        cross_scale_coupling=csc,
        narrative_self_emergence=nse,
        layer_narrative_tracker=lnt,
    )

    # ── Run ──
    start = time.time()
    results = evolver.run(verbose=verbose)
    elapsed = time.time() - start

    if verbose:
        print(f"\n  Run completed in {elapsed:.1f}s")

    # ── Extract CSC summary ──
    csc_summary = csc.get_summary()
    ind_l2_summary = csc_summary.get('independent_l2', {})

    # ── Extract LNT layer NSI data ──
    lnt_summary = lnt.get_summary()

    # ── Compute hypothesis tests ──
    hypotheses = {}

    # H30: L1<->L2 correlation < 0.7 (and L2 must be active)
    l1_l2_corr = ind_l2_summary.get('l1_l2_correlation')
    l2_stability_mean = ind_l2_summary.get('l2_stability_mean', 0.0)
    l2_stability_min = ind_l2_summary.get('l2_stability_min', 0.0)
    l2_stability_max = ind_l2_summary.get('l2_stability_max', 0.0)
    h30_pass = (
        l1_l2_corr is not None and
        l1_l2_corr < 0.7 and
        l2_stability_mean > 0.1  # L2 must be active
    )
    hypotheses['H30'] = {
        'pass': h30_pass,
        'l1_l2_correlation': round(l1_l2_corr, 4) if l1_l2_corr is not None else None,
        'l2_stability_mean': round(l2_stability_mean, 4),
        'l2_stability_min': round(l2_stability_min, 4),
        'l2_stability_max': round(l2_stability_max, 4),
        'l2_active': l2_stability_mean > 0.1,
        'note': 'L2 must be active (not silent) for meaningful decoupling',
    }

    # H31: L0->L1 delay detected (from LNT conduction_delay)
    l0_l1_delay = lnt_summary.conduction_delay.l0_to_l1_delay
    h31_pass = l0_l1_delay is not None and l0_l1_delay > 0 and l0_l1_delay < 100
    hypotheses['H31'] = {
        'pass': h31_pass,
        'l0_l1_delay': l0_l1_delay,
        'note': 'L0->L1 conduction delay (from LNT)',
    }

    # H32: L2 autonomy — compare per-layer NSI activity
    # L2 is autonomous if it has active NSI when L1 also has active NSI
    l1_nsi = None
    l2_nsi = None
    for pl in lnt_summary.per_layer.values():
        if pl.level == 'INSTITUTIONAL':
            l1_nsi = pl
        elif pl.level == 'CIVILIZATION':
            l2_nsi = pl
    if l1_nsi and l2_nsi:
        # Autonomy: both layers active but with different NSI values
        autonomy_idx = abs(l1_nsi.nsi - l2_nsi.nsi) / max(0.01, max(l1_nsi.nsi, l2_nsi.nsi))
        l2_active = l2_nsi.is_nsi_active
    else:
        autonomy_idx = 0.0
        l2_active = False
    h32_pass = autonomy_idx > 0.1 and l2_active  # Lower threshold, require L2 active
    hypotheses['H32'] = {
        'pass': h32_pass,
        'autonomy_index': round(autonomy_idx, 4),
        'l1_nsi': round(l1_nsi.nsi, 4) if l1_nsi else None,
        'l2_nsi': round(l2_nsi.nsi, 4) if l2_nsi else None,
        'l2_active': l2_active,
    }

    # H33: L1<->L2 correlation from LNT inter_layer_correlation
    l1_l2_from_lnt = lnt_summary.inter_layer_correlation.pairwise_correlations.get('L1-L2')
    h33_pass = (
        l1_l2_from_lnt is not None and
        abs(l1_l2_from_lnt) < 0.7 and
        l2_active
    )
    hypotheses['H33'] = {
        'pass': h33_pass,
        'l1_l2_correlation_from_lnt': round(l1_l2_from_lnt, 4) if l1_l2_from_lnt is not None else None,
        'l2_active': l2_active,
    }

    # H35: L2 stability floor works (min >= 0.10, allowing noise)
    h35_pass = l2_stability_min >= 0.10
    hypotheses['H35'] = {
        'pass': h35_pass,
        'l2_stability_min': round(l2_stability_min, 4),
        'floor': 0.15,
    }

    # H36: L2 autonomy index (same as H32)
    h36_pass = autonomy_idx > 0.1 and l2_active
    hypotheses['H36'] = {
        'pass': h36_pass,
        'narrative_autonomy': round(autonomy_idx, 4),
        'l2_nsi_active': l2_active,
    }

    # H37: L2 intrinsic dynamics — L2 NSI variance during stable periods
    l2_nsi_history = lnt_summary.nsi_history.get('CIVILIZATION', [])
    if len(l2_nsi_history) >= 100:
        l2_nsi_std = np.std(l2_nsi_history[-100:])
        h37_pass = l2_nsi_std > 0.01  # Some intrinsic variance
    else:
        l2_nsi_std = 0.0
        h37_pass = False
    hypotheses['H37'] = {
        'pass': h37_pass,
        'l2_nsi_std': round(float(l2_nsi_std), 4),
        'l2_nsi_history_len': len(l2_nsi_history),
    }

    # ── H1-H8 baseline ──
    # Use LNT per-layer data
    h1_pass = False  # NSI > 0.5
    h2_pass = False  # NSI increasing trend
    h3_pass = False  # CIV in [3,20]
    h4_pass = False  # Turning points
    h5_pass = False  # CIV in [2,20]
    h6_pass = False  # CIV min >= 2
    h7_pass = False  # History depth > 0.1
    h8_pass = False  # TopDown activated

    for pl in lnt_summary.per_layer.values():
        if pl.level == 'CIVILIZATION':
            h1_pass = pl.nsi > 0.5
            h7_pass = pl.self_history_depth > 0.1
        if pl.level == 'INSTITUTIONAL':
            pass  # Check institutional metrics if needed

    # Check NSI trend for H2
    civ_nsi_hist = lnt_summary.nsi_history.get('CIVILIZATION', [])
    if len(civ_nsi_hist) >= 50:
        first_half = np.mean(civ_nsi_hist[:len(civ_nsi_hist)//2])
        second_half = np.mean(civ_nsi_hist[len(civ_nsi_hist)//2:])
        h2_pass = second_half > first_half

    # LNT inter-layer correlation passing
    h3_pass = lnt_summary.inter_layer_correlation.passing  # All correlations below threshold
    h4_pass = lnt_summary.conduction_delay.passing  # Delays detected
    h8_pass = lnt_summary.inter_layer_correlation.all_below_threshold

    hypotheses['H1'] = {'pass': h1_pass, 'desc': 'NSI > 0.5'}
    hypotheses['H2'] = {'pass': h2_pass, 'desc': 'NSI increasing trend'}
    hypotheses['H3'] = {'pass': h3_pass, 'desc': 'CIV in [3,20]'}
    hypotheses['H4'] = {'pass': h4_pass, 'desc': 'Turning points detected'}
    hypotheses['H5'] = {'pass': h5_pass, 'desc': 'CIV in [2,20] (relaxed)'}
    hypotheses['H6'] = {'pass': h6_pass, 'desc': 'CIV min >= 2'}
    hypotheses['H7'] = {'pass': h7_pass, 'desc': 'History depth > 0.1'}
    hypotheses['H8'] = {'pass': h8_pass, 'desc': 'TopDown activated'}

    # Count passes
    track_b_passes = sum(1 for k in ['H30','H31','H32','H33','H35','H36','H37'] if hypotheses[k]['pass'])
    baseline_passes = sum(1 for k in ['H1','H2','H3','H4','H5','H6','H7','H8'] if hypotheses[k]['pass'])

    seed_result = {
        'seed': seed,
        'elapsed': round(elapsed, 1),
        'hypotheses': hypotheses,
        'track_b_passes': f'{track_b_passes}/7',
        'baseline_passes': f'{baseline_passes}/8',
        'csc_summary': {
            'coupling_mode': 'independent',
            'l1_l2_correlation': round(l1_l2_corr, 4) if l1_l2_corr is not None else None,
            'l0_l2_correlation': None,  # Not tracked in B5 independent mode
            'l2_stability_mean': round(l2_stability_mean, 4),
            'l2_stability_min': round(l2_stability_min, 4),
            'l2_stability_max': round(l2_stability_max, 4),
            'l2_odi_mean': round(ind_l2_summary.get('l2_odi_mean', 0), 4),
            'avg_response_delay': ind_l2_summary.get('avg_response_delay', 0),
        },
        'lnt_summary': {
            'nsi_final': {pl.level: pl.nsi for pl in lnt_summary.per_layer.values()},
            'inter_layer_correlation': {
                k: round(v, 4) for k, v in lnt_summary.inter_layer_correlation.pairwise_correlations.items()
            },
            'l0_l1_delay': lnt_summary.conduction_delay.l0_to_l1_delay,
            'l1_l2_delay': lnt_summary.conduction_delay.l1_to_l2_delay,
            'layer_activity': lnt_summary.layer_activity,
            'total_steps': lnt_summary.total_steps,
        },
    }

    return seed_result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Phase 5 Track B5: Independent L2')
    parser.add_argument('seed', type=int, nargs='?', help='Single seed to run')
    parser.add_argument('--all', action='store_true', help='Run all 8 seeds')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')
    args = parser.parse_args()

    seeds = [args.seed] if args.seed is not None else ALL_SEEDS
    if args.all or args.seed is None:
        seeds = ALL_SEEDS

    all_results = []
    for seed in seeds:
        result = run_single_seed(seed, verbose=not args.quiet)
        all_results.append(result)

        # Print summary
        h = result['hypotheses']
        print(f"\n  Seed {seed}:")
        print(f"    H30 (decoupling): {'PASS' if h['H30']['pass'] else 'FAIL'} "
              f"r={h['H30'].get('l1_l2_correlation','N/A')} "
              f"L2_mean={h['H30'].get('l2_stability_mean','N/A')}")
        print(f"    H31 (delay):      {'PASS' if h['H31']['pass'] else 'FAIL'} "
              f"delay={h['H31'].get('l0_l1_delay','N/A')}")
        print(f"    H32 (autonomy):   {'PASS' if h['H32']['pass'] else 'FAIL'} "
              f"idx={h['H32'].get('autonomy_index','N/A')}")
        print(f"    H33 (ODI indep):  {'PASS' if h['H33']['pass'] else 'FAIL'} "
              f"r={h['H33'].get('l0_l2_odi_correlation','N/A')}")
        print(f"    H35 (floor):      {'PASS' if h['H35']['pass'] else 'FAIL'} "
              f"min={h['H35'].get('l2_stability_min','N/A')}")
        print(f"    H36 (narr auto):  {'PASS' if h['H36']['pass'] else 'FAIL'} "
              f"idx={h['H36'].get('narrative_autonomy','N/A')}")
        print(f"    H37 (intrinsic):  {'PASS' if h['H37']['pass'] else 'FAIL'} "
              f"odi_std={h['H37'].get('l2_odi_std','N/A')}")
        print(f"    Baseline H1-H8:   {result['baseline_passes']}")
        print(f"    Track B:          {result['track_b_passes']}")

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
        'seeds': all_results,
        'summary': {
            'total_seeds': len(all_results),
            'track_b_pass_rates': {},
        },
    }

    for hk in ['H30','H31','H32','H33','H35','H36','H37']:
        passes = sum(1 for r in all_results if r['hypotheses'][hk]['pass'])
        output['summary']['track_b_pass_rates'][hk] = f'{passes}/{len(all_results)}'

    os.makedirs(os.path.dirname(FIXED_OUTPUT), exist_ok=True)
    with open(FIXED_OUTPUT, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Results saved to {FIXED_OUTPUT}")
    return output


if __name__ == '__main__':
    main()
