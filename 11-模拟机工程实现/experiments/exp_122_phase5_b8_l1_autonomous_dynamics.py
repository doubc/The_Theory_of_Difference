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
  H48 (L1 sealing potential): >= 3/8 seeds reach L1 sealing ratio > 0.4
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
from engine.per_layer_metrics import (
    PerLayerMetricsCollector, DEFAULT_PER_LAYER_METRICS_CONFIG,
    H46Result, H47Result, H48Result, H49Result,
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
    'sample_interval': 10,  # dense sampling for per-layer metrics
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

    # Create hierarchical evolver with dense sampling
    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=total_steps,
        sample_interval=config.get('sample_interval', 10),
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

    # Initialize per-layer metrics collector for H46-H49
    plm_config = DEFAULT_PER_LAYER_METRICS_CONFIG.copy()
    collector = PerLayerMetricsCollector(plm_config)

    # Run with step-level monitoring via tracking callback
    start_time = time.time()
    result = evolver.run(verbose=False, tracking_callback=collector.step)
    elapsed = time.time() - start_time

    # Extract layer results
    layer_results = result['layer_results']
    l0_sealed = layer_results[0]['sealed'] if len(layer_results) >= 1 else False
    l1_formed = len(layer_results) >= 2
    snapshots = result.get('snapshots', [])

    # Get seal/formation steps from collector (tracked during step callback)
    l0_seal_step = collector._l0_seal_step
    l1_formed_step = collector._l1_formed_step

    # If collector seal_step is not set (e.g. -1), estimate from hierarchy
    if l0_seal_step <= 0 and l0_sealed:
        # Use first snapshot step where sealed appears
        for snap in snapshots:
            if snap.layer == 0 and snap.sealed:
                l0_seal_step = snap.step
                break
        if l0_seal_step <= 0:
            l0_seal_step = snapshots[-1].step if snapshots else 0

    # Get active bits from final layer state
    l0_active_final = set(layer_results[0].get('active_bits', [])) if len(layer_results) >= 1 else set()
    l1_active_final = set(layer_results[1].get('active_bits', [])) if len(layer_results) >= 2 else set()

    # Analyze per-layer metrics for H46-H49
    plm_analysis = collector.analyze(post_seal_only=True)
    h46 = plm_analysis['h46']
    h47 = plm_analysis['h47']
    h48 = plm_analysis['h48']
    h49 = plm_analysis['h49']

    # Get per-layer NSI/CIV series from analysis
    l0_nsi_series = plm_analysis.get('l0_nsi_history', [])
    l1_nsi_series = plm_analysis.get('l1_nsi_history', [])
    l0_civ_series = plm_analysis.get('l0_civ_history', [])
    l1_civ_series = plm_analysis.get('l1_civ_history', [])

    # Compute NSI from per-layer metrics collector data
    # Use L0's NSI (from PLM tracker) as global NSI proxy
    # Fallback to ODI-based heuristic if NSE not active
    if h46.rolling_correlations:
        # Use L0 NSI from per-layer metrics if available
        l0_nsi_vals = [v for _, v in plm_analysis.get('l0_nsi_history', [])]
        global_nsi = float(np.mean(l0_nsi_vals)) if l0_nsi_vals else 0.0
    else:
        # ODI-based approximation
        hierarchy = result.get('hierarchy_summary', {})
        layers_info = hierarchy.get('layers', [])
        if layers_info:
            l0 = layers_info[0]
            n_total = l0.get('N', N0)
            n_active = l0.get('active', 0)
            odi_approx = n_active / n_total if n_total > 0 else 0.0
            msi = result.get('phase3_summary', {}).get('msi', 0.0)
            nsi_alpha, nsi_beta, nsi_min_odi = 0.4, 0.3, 0.6
            continuity_approx = min(1.0, msi)
            stability_approx = min(1.0, odi_approx)
            odi_gate = min(1.0, odi_approx / nsi_min_odi) if nsi_min_odi > 0 else 1.0
            raw_nsi = nsi_alpha * continuity_approx + nsi_beta * stability_approx
            global_nsi = float(np.clip(raw_nsi * odi_gate, 0.0, 1.0))
        else:
            global_nsi = 0.0

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
        # H46: NSI autonomy
        'h46_mean_corr': h46.mean_corr,
        'h46_min_corr': h46.min_corr,
        'h46_max_corr': h46.max_corr,
        'h46_pass_rate': h46.pass_count,
        'h46_passing': h46.passing,
        # H47: CIV independence
        'h47_rolling_corr_mean': h47.mean_corr,
        'h47_rolling_corr_min': h47.min_corr,
        'h47_rolling_corr_max': h47.max_corr,
        'h47_passing': h47.passing,
        # H48: L1 sealing potential
        'l1_sealing_ratio': h48.mean_ratio,
        'l1_sealing_max_ratio': h48.max_ratio,
        'h48_passing': h48.passing,
        # H49: Theme divergence
        'h49_jaccard_mean': h49.mean_jaccard,
        'h49_jaccard_min': h49.min_jaccard,
        'h49_passing': h49.passing,
        'global_nsi': round(global_nsi, 4),
        'snapshots_count': len(snapshots),
        # Raw time series for plotting
        'l0_nsi_series': plm_analysis.get('l0_nsi_history', []),
        'l1_nsi_series': plm_analysis.get('l1_nsi_history', []),
        'l0_civ_series': plm_analysis.get('l0_civ_history', []),
        'l1_civ_series': plm_analysis.get('l1_civ_history', []),
    }


def analyze_results(results: list) -> dict:
    """Analyze batch results and check B8 hypotheses."""
    n = len(results)

    # H46: L1 NSI autonomy (rolling corr < 0.5) — from PerLayerMetricsCollector
    h46_pass_count = 0
    h46_details = []
    for r in results:
        corr = r.get('h46_mean_corr')
        if corr is not None:
            if abs(corr) < 0.5:
                h46_pass_count += 1
            h46_details.append(corr)

    # H47: L1 CIV independence (hamming corr < 0.6)
    h47_pass_count = 0
    h47_details = []
    for r in results:
        corr = r.get('h47_rolling_corr_mean')
        if corr is not None:
            if abs(corr) < 0.6:
                h47_pass_count += 1
            h47_details.append(corr)

    # H48: L1 sealing potential (ratio > 0.4, adjusted for partial sealing)
    h48_pass_count = 0
    h48_details = []
    for r in results:
        ratio = r.get('l1_sealing_ratio', 0)
        if ratio > 0.4:
            h48_pass_count += 1
        h48_details.append(ratio)

    # H49: L1 theme divergence (Jaccard < 0.4)
    h49_pass_count = 0
    h49_details = []
    for r in results:
        j = r.get('h49_jaccard_mean')
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
            'name': 'L1 Sealing Potential (ratio > 0.4)',
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
          f"{'H46 NSI r':>9} | {'H47 CIV r':>9} | {'H49 Jac':>7} | {'L1 seal%':>8} | {'NSI':>6}")
    print("-" * 95)
    for r in results:
        l0_sealed = 'SEALED' if r['l0_sealed'] else 'no'
        seal_step = str(r['l0_seal_step']) if r['l0_seal_step'] > 0 else 'N/A'
        l1_formed = 'yes' if r['l1_formed'] else 'no'
        h46_corr = f"{r['h46_mean_corr']:.3f}" if r.get('h46_mean_corr') is not None else 'N/A'
        h47_corr = f"{r['h47_rolling_corr_mean']:.3f}" if r.get('h47_rolling_corr_mean') is not None else 'N/A'
        jacc = f"{r['h49_jaccard_mean']:.3f}" if r.get('h49_jaccard_mean') is not None else 'N/A'
        seal_pct = f"{r['l1_sealing_ratio']*100:.1f}%" if r.get('l1_sealing_ratio') else 'N/A'
        nsi = f"{r['global_nsi']:.3f}"
        print(f"{r['seed']:4d} | {l0_sealed:>9} | {seal_step:>9} | {l1_formed:>9} | "
              f"{h46_corr:>9} | {h47_corr:>9} | {jacc:>7} | {seal_pct:>8} | {nsi:>6}")

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
