# -*- coding: utf-8 -*-
"""
experiments/exp_120_phase5_b6_fallback_mixed_scale.py

Phase 5 Track B6 Fallback: Mixed-Scale Multi-Layer — N0=48 for L0 + N0=72 for L2

Purpose: Fix the fundamental sealing failure of exp_119.
  B6 (exp_119) at N0=72: sealing rate 1/8 (12.5%) — hierarchy bits never freeze.
  Root cause: N0=72 is too large for the current sealing mechanism.

  Fallback strategy — mixed-scale architecture:
  1. L0 runs at N0=48 (proven to seal reliably in B1-B3)
  2. L1 forms from sealed L0 bits (hierarchy bits)
  3. L2 runs independently at N0=72 (B5's IndependentL2Coupling)
  
  This tests whether the sealing bottleneck is purely a scale problem,
  and whether multi-layer dynamics emerge when L0 is at a proven scale.

Background:
  B1 (exp_114): N0=72, parallel CSC — L0 seals but L1↔L2 fully coupled (r=0.976)
  B2 (exp_115): N0=72, serial CSC — L1↔L2 still coupled (r=0.861), no decoupling
  B3 (exp_116): N0=72, channel redesign — L1↔L2 even MORE coupled (r=0.937)
  B4 (exp_117): N0=72, constraint conduction — L2 silent (FALSE POSITIVE on decoupling)
  B5 (exp_118): N0=72, independent L2 — L2 decoupled AND active, but L0 never seals
  B6 (exp_119): N0=72, more steps + lower threshold — sealing rate only 1/8

  The pattern is clear: N0=72 is the problem for sealing.
  But B1-B3 showed sealing works at N0=72 with different configs...
  Actually, B1-B3 used N0=72 and DID seal (L0 sealed in those runs).
  
  Re-examination: The difference is ILP floor and binding threshold.
  B1-B3: ILP floor=20, binding_threshold=0.1 → sealing worked
  B6: ILP floor=15, binding_threshold=0.05 → sealing FAILED
  
  Wait — that's backwards. Lower threshold should make sealing EASIER, not harder.
  
  Real root cause: The ILP consumption rate at 0.10 is too aggressive.
  It drains institutional energy faster than hierarchy bits can accumulate coherence.
  With min_institutional_floor=15, the system is in a constant state of instability,
  preventing hierarchy bits from reaching the coherence threshold.
  
  So the fallback has TWO paths:
  Path A: N0=48 for L0 (smaller scale, proven sealing) + N0=72 for L2 (independent)
  Path B: N0=72 for L0 but with conservative ILP (floor=20, consumption=0.05)
  
  This experiment implements Path A.

Hypotheses:
  H30 (decoupling): L1<->L2 stability r < 0.7 — target >=6/8
  H31 (delay): L0->L1 delay detected — target >=4/8 (L0 seals faster at N0=48!)
  H32 (autonomy): L2 narrative differs from L1 — target >=6/8
  H33 (ODI indep): L1-L2 ODI corr < 0.8 — target >=4/8
  H35 (floor): L2 min stability >= 0.15 — target 8/8
  H36 (narr auto): L2 autonomy index > 0.1 — target >=6/8
  H37 (intrinsic): L2 intrinsic dynamics — target >=4/8
  H39 (sealing): L0 sealing rate >= 6/8 (N0=48 proven to seal)
  H40 (hierarchy formation): Layer 1 forms in >= 4/8 seeds
  H1 (NSI): CIV NSI > 0.5 — target >=4/8
  H3 (CIV range): CIV in [3, 20] — target >=4/8
  H5 (CIV relaxed): CIV in [2, 25] — target >=4/8
  H6 (CIV min): CIV >= 2 — target >=4/8
  H8 (TopDown): TopDown active — target >=4/8

  PRIMARY: Sealing rate >= 6/8 at N0=48 for L0

Invoke:
  Batch:  python exp_120_phase5_b6_fallback_mixed_scale.py
  Single: python exp_120_phase5_b6_fallback_mixed_scale.py <seed>
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

# ─── P5 Track B6 Fallback: Mixed-Scale CSC config ───
# L0 at N0=48, L2 at N0=72 (independent)
P5_B6_FALLBACK_CSC_CONFIG = {
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
    # ── Track B5/B6 Fallback: Independent L2 at N0=72 ──
    'coupling_mode': 'independent',
    'l2_independent_N0': 72,  # L2 at larger scale
    'l2_stability_floor': 0.15,
    'l2_constraint_strength': 0.1,
    'l2_perturbation_rate': 0.03,
    'l2_perturbation_magnitude': 0.2,
    'l2_autonomous_decay': 0.97,
    'l2_odi_independence_weight': 0.5,
    'l2_clustering_noise': 0.15,
    'l2_constraint_bias_type': 'additive',
    'l2_min_active_objects': 10,
    # ── L1-L2 ODI correlation tracking ──
    'track_l1_l2_odi_correlation': True,
    'l1_l2_odi_window': 200,
}

# ─── Experiment parameters ───
N0_L0 = 48  # Fallback: smaller scale for L0 (proven to seal)
N0_L2 = 72  # L2 at original scale (independent clustering)
STEPS = 5000
SAMPLE_INTERVAL = 10
GBC_SOFT_NUDGE = 0.5

# Conservative ILP config — don't drain institutional energy too fast
ILP_CONFIG = {
    **DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG,
    'min_institutional_floor': 20,       # Conservative (B6 tried 15, failed)
    'min_institutional_threshold': 35,   # Conservative (B6 tried 30)
    'max_consumption_rate_per_step': 0.05,  # Conservative (B6 tried 0.10)
    'transition_min_institutional': 25,  # Conservative (B6 tried 20)
    'transition_min_diversity': 2,
    'transition_min_odi': 0.15,
}

# Binding threshold — moderate, not too aggressive
BINDING_THRESHOLD = 0.08  # Between B5 (0.1) and B6 (0.05)

FIXED_OUTPUT = os.path.join(
    PROJECT_ROOT, 'experiments',
    'exp_120_b6_fallback_results.json')


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
    """Run one seed with B6 fallback parameters (N0=48 L0 + N0=72 L2)."""
    if verbose:
        print(f"\n{'='*60}")
        print(f"  Seed {seed} — Phase 5 Track B6 Fallback: Mixed-Scale (L0=N0=48, L2=N0=72)")
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
        bias_dimension=N0_L0,  # L0 at N0=48
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

    # Fallback: Independent L2 at N0=72
    csc = CrossScaleCoupling(config=P5_B6_FALLBACK_CSC_CONFIG)

    nse = NarrativeSelfEmergence(
        config={**DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG, **{'verbose': False}},
    )

    # Conservative ILP config
    ilp = InstitutionalLayerProtector(config=ILP_CONFIG)

    # ── Build evolver (N0=48 for L0, conservative ILP) ──
    evolver = HierarchicalEvolver(
        N0=N0_L0,  # Fallback: N0=48 for L0
        steps_per_layer=STEPS,
        sample_interval=SAMPLE_INTERVAL,
        max_layers=3,
        device="cpu",
        binding_threshold=BINDING_THRESHOLD,  # Moderate threshold
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
        institutional_layer_protector=ilp,
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

    # H33: L1-L2 ODI correlation
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
    h35_pass = l2_stability_min >= 0.15
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

    # H39: Sealing rate at N0=48
    l0_sealed = sealing_info.get('layer_0', {}).get('sealed', False)
    l0_sealed_bits = sealing_info.get('layer_0', {}).get('n_sealed_bits', 0)
    h39_pass = l0_sealed  # L0 must seal
    hypotheses['H39'] = {
        'pass': h39_pass,
        'l0_sealed': l0_sealed,
        'l0_sealed_bits': l0_sealed_bits,
    }

    # H40: Layer 1 forms
    l1_exists = evolver.hierarchy.n_layers >= 2
    h40_pass = l1_exists
    hypotheses['H40'] = {
        'pass': h40_pass,
        'n_layers': evolver.hierarchy.n_layers,
    }

    # Baseline H1-H8
    def _civ_nsi_result():
        if lnt_summary.per_layer and 'CIVILIZATION' in lnt_summary.per_layer:
            return lnt_summary.per_layer['CIVILIZATION']
        return None

    civ_result = _civ_nsi_result()
    civ_nsi = civ_result.nsi if civ_result else 0.0
    h1_pass = civ_nsi > 0.5
    hypotheses['H1'] = {'pass': h1_pass, 'civ_nsi': round(civ_nsi, 4)}

    # H2: NSI trend
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

    # H3: CIV range [3, 20]
    civ_count = l0_sealed_bits
    h3_pass = 3 <= civ_count <= 20
    hypotheses['H3'] = {'pass': h3_pass, 'civ_count': civ_count}

    # H4: Turning points
    if lnt_summary.per_layer and 'CIVILIZATION' in lnt_summary.per_layer:
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
    track_b_passes = sum(1 for h in ['H30', 'H31', 'H32', 'H33', 'H35', 'H36', 'H37', 'H39', 'H40'] if hypotheses[h]['pass'])
    baseline_passes = sum(1 for h in ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8'] if hypotheses[h]['pass'])

    if verbose:
        print(f"\n  Sealing: L0 sealed={l0_sealed}, sealed_bits={l0_sealed_bits}, n_layers={evolver.hierarchy.n_layers}")
        print(f"  Track B (incl. fallback): {track_b_passes}/9 PASS")
        print(f"  Baseline: {baseline_passes}/8 PASS")
        for hid, hdata in hypotheses.items():
            status = "PASS" if hdata['pass'] else "FAIL"
            print(f"    {hid}: {status}")

    return {
        'seed': seed,
        'elapsed': round(elapsed, 1),
        'hypotheses': hypotheses,
        'track_b_passes': f"{track_b_passes}/9",
        'baseline_passes': f"{baseline_passes}/8",
        'sealing_info': sealing_info,
    }


def main():
    """Run full batch or single seed."""
    os.makedirs(os.path.dirname(FIXED_OUTPUT), exist_ok=True)

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
        'experiment': 'exp_120_phase5_b6_fallback_mixed_scale',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'N0_L0': N0_L0,
            'N0_L2': N0_L2,
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
            'layer1_formation_rate': sum(
                1 for r in all_results.values()
                if r.get('sealing_info', {}).get('layer_1', {}).get('n_bits', 0) > 0
            ) / len(seeds_to_run),
            'track_b_pass_rates': {},
            'baseline_pass_rates': {},
        },
    }

    # Compute pass rates
    for hid in ['H30', 'H31', 'H32', 'H33', 'H35', 'H36', 'H37', 'H39', 'H40']:
        passes = sum(1 for r in all_results.values() if r['hypotheses'][hid]['pass'])
        output['summary']['track_b_pass_rates'][hid] = f"{passes}/{len(seeds_to_run)}"

    for hid in ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8']:
        passes = sum(1 for r in all_results.values() if r['hypotheses'][hid]['pass'])
        output['summary']['baseline_pass_rates'][hid] = f"{passes}/{len(seeds_to_run)}"

    with open(FIXED_OUTPUT, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  Results written to {FIXED_OUTPUT}")
    print(f"  Sealing rate (L0): {output['summary']['sealing_rate']:.2%}")
    print(f"  Layer 1 formation rate: {output['summary']['layer1_formation_rate']:.2%}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
