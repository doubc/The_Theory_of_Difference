# -*- coding: utf-8 -*-
"""
experiments/exp_119_phase5_b6_true_multilayer.py

Phase 5 Track B6: True Multi-Layer Evolution + Independent L2 Coupling

Purpose: Fix the architectural limitation of B5 — Layer 0 never seals at N0=72.
    Combine B5's independent L2 coupling with parameters that enable actual sealing:
    1. More steps: 5000 (vs 3000 in B5)
    2. Lower binding threshold: 0.05 (vs 0.1 in B5)
    3. Lower ILP institutional floor: 15 (vs 20 in B5)
    4. Higher consumption rate: 0.10 (vs 0.05 in B5)
    5. Add L1-L2 ODI correlation tracking to IndependentL2Coupling

Background:
  B5 (exp_118): Core claim validated — L2 genuinely decoupled AND active.
    But Layer 0 never seals → no true multi-layer evolution → H31/H33/H37/H1-H8 all fail.
    Root cause: N0=72 + binding_threshold=0.1 + ILP floor=20 → sealing condition never reached.

  B6 design: Keep B5's independent coupling, adjust sealing-enabling parameters.
    If sealing still fails at 5000 steps, this confirms N0=72 is fundamentally too large
    for the current sealing mechanism, and we need a different approach (e.g., N0=48 for L0).

Hypotheses:
  H30 (decoupling): L1<->L2 stability r < 0.7 — maintain B5's 8/8 PASS
  H31 (delay): L0->L1 delay detected — NEW target: >=4/8 (true multi-layer!)
  H32 (autonomy): L2 narrative differs from L1 — maintain >=6/8
  H33 (ODI indep): L1-L2 ODI corr < 0.8 — NEW: add tracking, target >=4/8
  H35 (floor): L2 min stability >= 0.10 — maintain 8/8
  H36 (narr auto): L2 autonomy index > 0.1 — maintain >=6/8
  H37 (intrinsic): L2 intrinsic dynamics — target >=4/8
  H1 (NSI): CIV NSI > 0.5 — target >=4/8
  H3 (CIV range): CIV in [3, 20] — target >=4/8 (actual CIV layer!)
  H5 (CIV relaxed): CIV in [2, 25] — target >=4/8
  H6 (CIV min): CIV >= 2 — target >=4/8
  H8 (TopDown): TopDown active — target >=4/8

  PRIMARY: Sealing rate >= 4/8 seeds (L0 seals within 5000 steps)

Invoke:
  Batch:  python exp_119_phase5_b6_true_multilayer.py
  Single: python exp_119_phase5_b6_true_multilayer.py <seed>
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
    LayerNarrativeSummary, PerLayerNSIResult,
)
from engine.seventh_threshold_detector import SeventhThresholdDetector
from engine.cooperative_emergence_detector import CooperativeEmergenceDetector
from engine.xiang_detector import XiàngDetector
from engine.institutional_layer_protector import (
    InstitutionalLayerProtector, DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG,
)


# ─── 8 baseline seeds (same as B1-B5) ───
ALL_SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]

# ─── P5 Track B6: Independent L2 CSC config (B5 config + L1-L2 ODI tracking) ───
P5_B6_INDEPENDENT_CSC_CONFIG = {
    # Base CSC params
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
    # ── Track B5/B6: Independent L2 Coupling Mode ──
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
    # ── Track B6: L1-L2 ODI correlation tracking ──
    'track_l1_l2_odi_correlation': True,
    'l1_l2_odi_window': 200,
}

# ─── Experiment parameters (B6: more steps, lower binding threshold) ───
N0 = 72
STEPS = 5000  # B6: increased from 3000 (B5) to give more time for sealing
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.5

# B6: Lower binding threshold to encourage earlier encapsulation
BINDING_THRESHOLD = 0.05  # B5: 0.1

# B6: ILP config — lower floor, higher consumption rate
ILP_CONFIG = {
    **DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG,
    'min_institutional_floor': 15,       # B5: 20
    'min_institutional_threshold': 30,   # B5: 35
    'max_consumption_rate_per_step': 0.10,  # B5: 0.05
    'transition_min_institutional': 20,  # B5: 25
    'transition_min_diversity': 2,
    'transition_min_odi': 0.15,
}

FIXED_OUTPUT = os.path.join(
    PROJECT_ROOT, 'experiments',
    'exp_119_b6_results.json')


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
    """Run one seed with B6 parameters."""
    if verbose:
        print(f"\n{'='*60}")
        print(f"  Seed {seed} — Phase 5 Track B6: True Multi-Layer + Independent L2")
        print(f"  Steps={STEPS}, binding_threshold={BINDING_THRESHOLD}, ILP floor={ILP_CONFIG['min_institutional_floor']}")
        print(f"{'='*60}")

    rng = np.random.RandomState(seed)
    torch.manual_seed(seed)

    # ── Build components ──
    pm = PersistentBiasMemory(max_history_depth=300, snapshot_interval=10)

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

    # B6: Updated CSC config with L1-L2 ODI tracking
    csc = CrossScaleCoupling(config=P5_B6_INDEPENDENT_CSC_CONFIG)

    nse = NarrativeSelfEmergence(
        config={**DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG, **{'verbose': False}},
    )

    # B6: Updated ILP config
    ilp = InstitutionalLayerProtector(config=ILP_CONFIG)

    # ── Build evolver (B6: lower binding threshold, more steps) ──
    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=STEPS,
        sample_interval=SAMPLE_INTERVAL,
        max_layers=3,
        device="cpu",
        binding_threshold=BINDING_THRESHOLD,  # B6: 0.05 (B5: 0.1)
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
        institutional_layer_protector=ilp,  # B6: add ILP with relaxed params
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

    # ── Extract layer sealing info ──
    sealing_info = {}
    for layer_id in range(evolver.hierarchy.n_layers):
        layer = evolver.hierarchy.get_layer(layer_id)
        sealing_info[f"layer_{layer_id}"] = {
            'sealed': layer.constraints.sealed if hasattr(layer.constraints, 'sealed') else False,
            'n_sealed_bits': len(layer.constraints.sealed_bits) if hasattr(layer.constraints, 'sealed_bits') else 0,
            'n_active_bits': len(layer.active_bits) if hasattr(layer, 'active_bits') else 0,
            'n_bits': layer.n_bits,
            'is_sealed': layer.is_sealed,
            'step_count': layer.step_count,
        }

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
        abs(l1_l2_corr) < 0.7 and
        l2_stability_mean > 0.1
    )
    hypotheses['H30'] = {
        'pass': h30_pass,
        'l1_l2_correlation': round(l1_l2_corr, 4) if l1_l2_corr is not None else None,
        'l2_stability_mean': round(l2_stability_mean, 4),
        'l2_stability_min': round(l2_stability_min, 4),
    }

    # H31: L0->L1 delay detected
    l0_l1_delay = lnt_summary.conduction_delay.l0_to_l1_delay if lnt_summary.conduction_delay else None
    h31_pass = l0_l1_delay is not None and l0_l1_delay >= 5
    hypotheses['H31'] = {
        'pass': h31_pass,
        'l0_l1_delay': l0_l1_delay,
    }

    # H32: L2 narrative autonomy
    l1_nsi = lnt_summary.per_layer.get('L1', PerLayerNSIResult('L1', 0, 0, 0, 0, False, 0)).nsi if lnt_summary.per_layer else 0.0
    l2_nsi = lnt_summary.per_layer.get('L2', PerLayerNSIResult('L2', 0, 0, 0, 0, False, 0)).nsi if lnt_summary.per_layer else 0.0
    autonomy_idx = abs(l1_nsi - l2_nsi) / max(l1_nsi, l2_nsi, 1e-10)
    h32_pass = autonomy_idx > 0.1
    hypotheses['H32'] = {
        'pass': h32_pass,
        'l1_nsi': round(l1_nsi, 4),
        'l2_nsi': round(l2_nsi, 4),
        'autonomy_index': round(autonomy_idx, 4),
    }

    # H33: L1-L2 ODI correlation (NEW for B6)
    l1_l2_odi_corr = ind_l2_summary.get('l1_l2_odi_correlation')
    h33_pass = (
        l1_l2_odi_corr is not None and
        abs(l1_l2_odi_corr) < 0.8
    )
    hypotheses['H33'] = {
        'pass': h33_pass,
        'l1_l2_odi_correlation': round(l1_l2_odi_corr, 4) if l1_l2_odi_corr is not None else None,
    }

    # H35: L2 stability floor
    h35_pass = l2_stability_min >= 0.10
    hypotheses['H35'] = {
        'pass': h35_pass,
        'l2_stability_min': round(l2_stability_min, 4),
    }

    # H36: L2 autonomy index
    h36_pass = autonomy_idx > 0.1
    hypotheses['H36'] = {
        'pass': h36_pass,
        'autonomy_index': round(autonomy_idx, 4),
    }

    # H37: L2 intrinsic dynamics
    l2_nsi_std = ind_l2_summary.get('l2_nsi_std', 0.0)
    h37_pass = l2_nsi_std > 0.01
    hypotheses['H37'] = {
        'pass': h37_pass,
        'l2_nsi_std': round(l2_nsi_std, 4),
    }

    # Sealing check (needed for H3-H6)
    l0_sealed = sealing_info.get('layer_0', {}).get('sealed', False)
    l0_sealed_bits = sealing_info.get('layer_0', {}).get('n_sealed_bits', 0)

    # Baseline H1-H8
    # Helper: get CIV layer result from per_layer dict
    def _civ_nsi_result():
        if lnt_summary.per_layer and 'CIVILIZATION' in lnt_summary.per_layer:
            return lnt_summary.per_layer['CIVILIZATION']
        return None

    civ_result = _civ_nsi_result()
    civ_nsi = civ_result.nsi if civ_result else 0.0
    h1_pass = civ_nsi > 0.5
    hypotheses['H1'] = {'pass': h1_pass, 'civ_nsi': round(civ_nsi, 4)}

    # H2: NSI trend — compute from CIV NSI history
    civ_hist = lnt_summary.nsi_history.get('CIVILIZATION', [])
    if len(civ_hist) >= 10:
        first_half = np.mean(civ_hist[:len(civ_hist)//2])
        second_half = np.mean(civ_hist[len(civ_hist)//2:])
        if second_half > first_half * 1.2:
            nsi_trend = 'increasing'
        elif second_half > 0.3:
            nsi_trend = 'stable_high'
        else:
            nsi_trend = 'low'
    else:
        nsi_trend = 'unknown'
    h2_pass = nsi_trend in ['increasing', 'stable_high']
    hypotheses['H2'] = {'pass': h2_pass, 'nsi_trend': nsi_trend}

    # H3: CIV range [3, 20] — from L0 sealed bits
    civ_count = l0_sealed_bits
    h3_pass = 3 <= civ_count <= 20
    hypotheses['H3'] = {'pass': h3_pass, 'civ_count': civ_count}

    # H4: Turning points — from CIV history tracker
    if lnt_summary.per_layer and 'CIVILIZATION' in lnt_summary.per_layer:
        # Use narrative stability as turning point proxy
        turning_points = int(civ_result.narrative_stability * 10) if civ_result else 0
    else:
        turning_points = 0
    h4_pass = turning_points >= 3
    hypotheses['H4'] = {'pass': h4_pass, 'turning_points': turning_points}

    # H5: CIV relaxed [2, 25]
    h5_pass = 2 <= civ_count <= 25
    hypotheses['H5'] = {'pass': h5_pass, 'civ_count': civ_count}

    # H6: CIV min >= 2
    h6_pass = civ_count >= 2
    hypotheses['H6'] = {'pass': h6_pass, 'civ_count': civ_count}

    # H7: History depth
    history_depth = civ_result.self_history_depth if civ_result else 0.0
    h7_pass = history_depth > 0.05
    hypotheses['H7'] = {'pass': h7_pass, 'history_depth': round(history_depth, 4)}

    # H8: TopDown active
    topdown_summary = csc_summary.get('top_down', {})
    topdown_active = topdown_summary.get('active', False) if isinstance(topdown_summary, dict) else False
    h8_pass = topdown_active
    hypotheses['H8'] = {'pass': h8_pass, 'topdown_active': topdown_active}

    # Count passes
    track_b_passes = sum(1 for h in ['H30', 'H31', 'H32', 'H33', 'H35', 'H36', 'H37'] if hypotheses[h]['pass'])
    baseline_passes = sum(1 for h in ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8'] if hypotheses[h]['pass'])

    if verbose:
        print(f"\n  Sealing: L0 sealed={l0_sealed}, sealed_bits={l0_sealed_bits}")
        print(f"  Track B: {track_b_passes}/7 PASS")
        print(f"  Baseline: {baseline_passes}/8 PASS")
        for hid, hdata in hypotheses.items():
            status = "PASS" if hdata['pass'] else "FAIL"
            print(f"    {hid}: {status}")

    return {
        'seed': seed,
        'elapsed': round(elapsed, 1),
        'hypotheses': hypotheses,
        'track_b_passes': f"{track_b_passes}/7",
        'baseline_passes': f"{baseline_passes}/8",
        'sealing_info': sealing_info,
    }


def main():
    """Run full batch or single seed."""
    os.makedirs(os.path.dirname(FIXED_OUTPUT), exist_ok=True)

    # Load previous results if exists
    previous_results = {}
    if os.path.exists(FIXED_OUTPUT):
        with open(FIXED_OUTPUT) as f:
            previous_results = json.load(f)

    seeds_to_run = ALL_SEEDS
    if len(sys.argv) > 1:
        seed = int(sys.argv[1])
        seeds_to_run = [seed]

    all_results = {}
    for seed in seeds_to_run:
        result = run_single_seed(seed, verbose=True)
        all_results[str(seed)] = result
        gc.collect()

    # ── Write results ──
    output = {
        'experiment': 'exp_119_phase5_b6_true_multilayer',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'N0': N0,
            'steps': STEPS,
            'binding_threshold': BINDING_THRESHOLD,
            'coupling_mode': 'independent',
            'l2_stability_floor': 0.15,
            'ilp_min_institutional_floor': ILP_CONFIG['min_institutional_floor'],
            'ilp_max_consumption_rate': ILP_CONFIG['max_consumption_rate_per_step'],
        },
        'seeds': all_results,
        'summary': {
            'total_seeds': len(seeds_to_run),
            'sealing_rate': sum(
                1 for r in all_results.values()
                if r.get('sealing_info', {}).get('layer_0', {}).get('sealed', False)
            ) / len(seeds_to_run),
            'track_b_pass_rates': {},
            'baseline_pass_rates': {},
        },
    }

    # Compute pass rates
    for hid in ['H30', 'H31', 'H32', 'H33', 'H35', 'H36', 'H37']:
        passes = sum(1 for r in all_results.values() if r['hypotheses'][hid]['pass'])
        output['summary']['track_b_pass_rates'][hid] = f"{passes}/{len(seeds_to_run)}"

    for hid in ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8']:
        passes = sum(1 for r in all_results.values() if r['hypotheses'][hid]['pass'])
        output['summary']['baseline_pass_rates'][hid] = f"{passes}/{len(seeds_to_run)}"

    with open(FIXED_OUTPUT, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  Results written to {FIXED_OUTPUT}")
    print(f"  Sealing rate: {output['summary']['sealing_rate']:.2%}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
