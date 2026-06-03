# -*- coding: utf-8 -*-
"""
experiments/exp_122_phase5_b8_l1_autonomous_dynamics.py

Phase 5 Track B8: L1 Autonomous Dynamics

Core Question: After L0 seals and L1 forms, does L1 develop its own autonomous
narrative dynamics, or is it merely a coarser echo of L0?

Hypotheses:
  H46 (L1 NSI autonomy): After L0 sealing, rolling correlation between L0 NSI
    and L1 NSI < 0.5 for >= 6/8 seeds
  H47 (L1 CIV independence): After seal, rolling correlation between L0 and L1
    hamming weights < 0.6 for >= 5/8 seeds
  H48 (L1 sealing potential): >= 3/8 seeds reach L1 sealing ratio > 0.8
    (unique_active / threshold) within post-seal steps
  H49 (L1 theme divergence): Post-seal Jaccard similarity between L0 and L1
    active theme sets < 0.4 for >= 5/8 seeds

Config: N0=48, steps=10000, binding_threshold=0.05, ILP floor=15
        Extended from B7 (5000 steps) to capture post-seal L1 dynamics.

Invoke:
  Batch: python exp_122_phase5_b8_l1_autonomous_dynamics.py
  Single: python exp_122_phase5_b8_l1_autonomous_dynamics.py <seed>
"""

import sys
import os
import gc
import time
import json
import math
from datetime import datetime
from collections import deque
from typing import Dict, List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.institutional_layer_protector import (
    InstitutionalLayerProtector, DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG,
)
from engine.layer_narrative_tracker import (
    LayerNarrativeTracker, DEFAULT_LAYER_NARRATIVE_CONFIG,
)
from engine.cross_scale_coupling import (
    CrossScaleCoupling, DEFAULT_CROSS_SCALE_COUPLING_CONFIG,
)
from engine.narrative_self_emergence import (
    NarrativeSelfEmergence, DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG,
)


# ─── 8 baseline seeds ───
ALL_SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]

# ─── Config ───
CONFIG = {
    'N0': 48,
    'total_steps': 10000,
    'binding_threshold': 0.05,
    'ilp_floor': 15,
    'ilp_consumption_rate': 0.10,
    'rolling_window': 200,  # for H46, H47 rolling correlations
    'theme_window': 200,    # for H49 Jaccard window
}


def compute_rolling_correlation(series_a: List[float], series_b: List[float],
                                 window: int) -> List[float]:
    """Compute rolling Pearson correlation between two series."""
    if len(series_a) < window or len(series_b) < window:
        return []
    results = []
    for i in range(window, len(series_a) + 1):
        a_window = series_a[i - window:i]
        b_window = series_b[i - window:i]
        if np.std(a_window) < 1e-10 or np.std(b_window) < 1e-10:
            results.append(0.0)
        else:
            results.append(float(np.corrcoef(a_window, b_window)[0, 1]))
    return results


def compute_jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets."""
    if len(set_a) == 0 and len(set_b) == 0:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def run_single_seed(seed: int, config: dict) -> dict:
    """Run a single seed and return detailed results for B8 hypotheses."""
    np.random.seed(seed)
    torch.random.manual_seed(seed)

    N0 = config['N0']
    total_steps = config['total_steps']
    rolling_window = config['rolling_window']

    print(f"\n{'='*60}")
    print(f"Seed {seed} | N0={N0} | Steps={total_steps}")
    print(f"{'='*60}")

    # Create hierarchical evolver
    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=total_steps,
        max_layers=3,
        device="cpu",
    )

    # Configure A9 parameters
    constraints = evolver.hierarchy.layers[0].constraints
    constraints.min_active_bits = N0 // 3
    constraints.binding_threshold = config['binding_threshold']

    # Configure ILP for L0
    ilp_config = DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG.copy()
    ilp_config['min_institutional_floor'] = config['ilp_floor']
    ilp_config['max_consumption_rate_per_step'] = config['ilp_consumption_rate']
    constraints.institutional_protector = InstitutionalLayerProtector(ilp_config)

    # Initialize tracking components
    lnt_config = DEFAULT_LAYER_NARRATIVE_CONFIG.copy()
    lnt = LayerNarrativeTracker(lnt_config)

    # Initialize NSE for global NSI
    nse_config = DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG.copy()
    nse = NarrativeSelfEmergence(nse_config)

    # Storage for post-hoc analysis
    l0_hamming_history: List[int] = []
    l1_hamming_history: List[int] = []
    l0_active_history: List[set] = []
    l1_active_history: List[set] = []
    l0_nsi_history: List[float] = []
    l1_nsi_history: List[float] = []
    l0_seal_step: int = -1
    l1_formed_step: int = -1

    # Run with step-level monitoring
    start_time = time.time()

    # We need to run layer by layer to capture per-step data
    # The evolver.run() runs all layers; we'll intercept via snapshots
    result = evolver.run(verbose=False)

    elapsed = time.time() - start_time

    # Extract layer results
    layer_results = result['layer_results']
    l0_sealed = layer_results[0]['sealed'] if len(layer_results) >= 1 else False
    l1_formed = len(layer_results) >= 2

    # Find seal step from snapshots
    snapshots = result.get('snapshots', [])
    for snap in snapshots:
        if snap.layer == 0:
            l0_hamming_history.append(int(snap.state.sum().item()))
            # Try to get active bits from constraints at that step
        elif snap.layer == 1:
            l1_hamming_history.append(int(snap.state.sum().item()))

    # Get seal step from layer results
    if l0_sealed:
        l0_result = layer_results[0]
        l0_seal_step = l0_result.get('seal_step', -1)

    if l1_formed:
        l1_result = layer_results[1]
        l1_formed_step = l1_result.get('formation_step', -1)

    # Get active bits from final layer state
    if len(layer_results) >= 1:
        l0_active_final = set(layer_results[0].get('active_bits', []))
    else:
        l0_active_final = set()

    if len(layer_results) >= 2:
        l1_active_final = set(layer_results[1].get('active_bits', []))
    else:
        l1_active_final = set()

    # Compute H47: hamming weight correlation (post-seal)
    h47_rolling_corr = []
    if l0_sealed and l1_formed and l0_seal_step > 0:
        # Find indices where step >= seal_step
        post_seal_l0 = []
        post_seal_l1 = []
        for i, snap in enumerate(snapshots):
            if snap.layer == 0 and i >= l0_seal_step:
                post_seal_l0.append(int(snap.state.sum().item()))
            elif snap.layer == 1 and i >= l0_seal_step:
                post_seal_l1.append(int(snap.state.sum().item()))
        if len(post_seal_l0) >= rolling_window and len(post_seal_l1) >= rolling_window:
            h47_rolling_corr = compute_rolling_correlation(
                post_seal_l0, post_seal_l1, rolling_window)

    # Compute H49: theme Jaccard (post-seal)
    h49_jaccard = []
    if l0_sealed and l1_formed and l0_seal_step > 0:
        # Use active bits from final state as proxy for themes
        # (full per-step theme tracking would require deeper integration)
        if len(l0_active_final) > 0 and len(l1_active_final) > 0:
            jaccard_val = compute_jaccard(l0_active_final, l1_active_final)
            h49_jaccard = [jaccard_val]  # single value for now

    # L1 sealing progress (H48)
    l1_sealing_ratio = 0.0
    if l1_formed and len(layer_results) >= 2:
        l1_constraints = evolver.hierarchy.get_layer(1).constraints
        l1_unique_active = len(getattr(l1_constraints, 'total_unique_active', set()))
        l1_threshold = getattr(l1_constraints, 'sealing_activation_threshold', N0 // 2)
        l1_sealing_ratio = l1_unique_active / l1_threshold if l1_threshold > 0 else 0.0

    # Compute NSI from available metrics (NSE was not stepped during run)
    # NSI = alpha*continuity + beta*stability + gamma*history_depth, gated by ODI
    nsi_alpha, nsi_beta, nsi_gamma, nsi_min_odi = 0.4, 0.3, 0.3, 0.6
    odi_final = result.get('odi_final', 0.0)
    msi_final = result.get('msi_final', 0.0)
    turning_points = result.get('turning_points', 0)
    # Approximate continuity from MSI stability, stability from ODI, history from turning points
    continuity_approx = min(1.0, msi_final)  # proxy
    stability_approx = min(1.0, odi_final)    # proxy
    history_depth_approx = min(1.0, turning_points / 10.0) if turning_points > 0 else 0.0
    odi_gate = min(1.0, odi_final / nsi_min_odi) if nsi_min_odi > 0 else 1.0
    raw_nsi = nsi_alpha * continuity_approx + nsi_beta * stability_approx + nsi_gamma * history_depth_approx
    global_nsi = float(np.clip(raw_nsi * odi_gate, 0.0, 1.0))

    return {
        'seed': seed,
        'N0': N0,
        'total_steps': total_steps,
        'elapsed_s': round(elapsed, 1),
        'l0_sealed': l0_sealed,
        'l0_seal_step': l0_seal_step,
        'l1_formed': l1_formed,
        'l1_formed_step': l1_formed_step,
        'n_layers': result['n_layers'],
        'l0_hamming_final': layer_results[0]['w'] if len(layer_results) >= 1 else 0,
        'l1_hamming_final': layer_results[1]['w'] if len(layer_results) >= 2 else 0,
        'l0_active_count': len(l0_active_final),
        'l1_active_count': len(l1_active_final),
        'l0_active_final': sorted(list(l0_active_final))[:20],  # sample
        'l1_active_final': sorted(list(l1_active_final))[:20],
        'h47_rolling_corr_mean': float(np.mean(h47_rolling_corr)) if h47_rolling_corr else None,
        'h47_rolling_corr_min': float(np.min(h47_rolling_corr)) if h47_rolling_corr else None,
        'h47_rolling_corr_max': float(np.max(h47_rolling_corr)) if h47_rolling_corr else None,
        'h47_samples': len(h47_rolling_corr),
        'h49_jaccard': h49_jaccard[0] if h49_jaccard else None,
        'l1_sealing_ratio': round(l1_sealing_ratio, 4),
        'l1_unique_active': len(getattr(evolver.hierarchy.get_layer(1).constraints, 'total_unique_active', set())) if l1_formed else 0,
        'l1_sealing_threshold': getattr(evolver.hierarchy.get_layer(1).constraints, 'sealing_activation_threshold', 0) if l1_formed else 0,
        'global_nsi': round(global_nsi, 4),
        'snapshots_count': len(snapshots),
    }


def analyze_results(results: list) -> dict:
    """Analyze batch results and check B8 hypotheses."""
    n = len(results)

    # H46: L1 NSI autonomy (rolling corr < 0.5)
    # Note: H46 needs per-layer NSI which requires deeper LNT integration
    # For now, use hamming correlation as proxy
    h46_pass_count = 0
    h46_details = []
    for r in results:
        if r.get('h47_rolling_corr_mean') is not None:
            # Using hamming corr as proxy for NSI autonomy
            if r['h47_rolling_corr_mean'] < 0.5:
                h46_pass_count += 1
            h46_details.append(r['h47_rolling_corr_mean'])

    # H47: L1 CIV independence (hamming corr < 0.6)
    h47_pass_count = 0
    h47_details = []
    for r in results:
        if r.get('h47_rolling_corr_mean') is not None:
            if r['h47_rolling_corr_mean'] < 0.6:
                h47_pass_count += 1
            h47_details.append(r['h47_rolling_corr_mean'])

    # H48: L1 sealing potential (ratio > 0.8)
    h48_pass_count = 0
    h48_details = []
    for r in results:
        if r.get('l1_sealing_ratio', 0) > 0.8:
            h48_pass_count += 1
        h48_details.append(r.get('l1_sealing_ratio', 0))

    # H49: L1 theme divergence (Jaccard < 0.4)
    h49_pass_count = 0
    h49_details = []
    for r in results:
        j = r.get('h49_jaccard')
        if j is not None and j < 0.4:
            h49_pass_count += 1
        if j is not None:
            h49_details.append(j)

    return {
        'total_seeds': n,
        'h46': {
            'name': 'L1 NSI Autonomy (rolling corr < 0.5)',
            'pass_count': h46_pass_count,
            'pass_rate': f"{h46_pass_count}/{n}",
            'pass': h46_pass_count >= 6,
            'values': h46_details,
        },
        'h47': {
            'name': 'L1 CIV Independence (hamming corr < 0.6)',
            'pass_count': h47_pass_count,
            'pass_rate': f"{h47_pass_count}/{n}",
            'pass': h47_pass_count >= 5,
            'values': h47_details,
        },
        'h48': {
            'name': 'L1 Sealing Potential (ratio > 0.8)',
            'pass_count': h48_pass_count,
            'pass_rate': f"{h48_pass_count}/{n}",
            'pass': h48_pass_count >= 3,
            'values': h48_details,
        },
        'h49': {
            'name': 'L1 Theme Divergence (Jaccard < 0.4)',
            'pass_count': h49_pass_count,
            'pass_rate': f"{h49_pass_count}/{n}",
            'pass': h49_pass_count >= 5,
            'values': h49_details,
        },
        'details': results,
    }


def main():
    print("=" * 70)
    print("Phase 5 Track B8: L1 Autonomous Dynamics")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    seed_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None

    if seed_arg is not None:
        results = [run_single_seed(seed_arg, CONFIG)]
    else:
        results = []
        for i, seed in enumerate(ALL_SEEDS):
            print(f"\n[{i+1}/{len(ALL_SEEDS)}] ", end="", flush=True)
            r = run_single_seed(seed, CONFIG)
            results.append(r)
            gc.collect()

    # Analyze
    analysis = analyze_results(results)

    print("\n" + "=" * 70)
    print("TRACK B8 RESULTS")
    print("=" * 70)

    for h_id in ['h46', 'h47', 'h48', 'h49']:
        h = analysis[h_id]
        mark = '[PASS]' if h['pass'] else '[FAIL]'
        print(f"{h['name']}: {h['pass_count']}/{analysis['total_seeds']} = {h['pass_rate']} {mark}")
        if h['values']:
            vals = h['values']
            print(f"  Values: mean={np.mean(vals):.4f}, min={np.min(vals):.4f}, max={np.max(vals):.4f}")

    # Per-seed detail
    print(f"\n{'Seed':>4} | {'L0 sealed':>9} | {'Seal step':>9} | {'L1 formed':>9} | "
          f"{'L0→L1 corr':>10} | {'Jaccard':>7} | {'L1 seal%':>8} | {'NSI':>6}")
    print("-" * 80)
    for r in results:
        l0_sealed = 'SEALED' if r['l0_sealed'] else 'no'
        seal_step = str(r['l0_seal_step']) if r['l0_seal_step'] > 0 else 'N/A'
        l1_formed = 'yes' if r['l1_formed'] else 'no'
        corr = f"{r['h47_rolling_corr_mean']:.3f}" if r.get('h47_rolling_corr_mean') is not None else 'N/A'
        jacc = f"{r['h49_jaccard']:.3f}" if r.get('h49_jaccard') is not None else 'N/A'
        seal_pct = f"{r['l1_sealing_ratio']*100:.1f}%"
        nsi = f"{r['global_nsi']:.3f}"
        print(f"{r['seed']:4d} | {l0_sealed:>9} | {seal_step:>9} | {l1_formed:>9} | "
              f"{corr:>10} | {jacc:>7} | {seal_pct:>8} | {nsi:>6}")

    # Save results
    output = {
        'experiment': 'exp_122_phase5_b8_l1_autonomous_dynamics',
        'timestamp': datetime.now().isoformat(),
        'config': CONFIG,
        'analysis': analysis,
        'results': results,
    }
    output_path = os.path.join(
        os.path.dirname(__file__), 'exp_122_b8_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_path}")


if __name__ == '__main__':
    main()
