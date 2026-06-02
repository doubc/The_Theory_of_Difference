# -*- coding: utf-8 -*-
"""
experiments/exp_121_phase5_b7_sealing_fix.py

Phase 5 Track B7: Fix A9 Sealing Mechanism + Layer 1 Auto-Creation

Purpose: Fix the two root causes of exp_120's sealing failure:
  1. A9 sealing trigger was too strict: active_in_window >= N required ALL bits
     to be active within the sliding window simultaneously. Early-active bits that
     slid out of the window could never help reach the threshold.
     FIX: Use total_unique_active (all-time) to trigger sealing; sliding window
     only decides WHICH bits to freeze, not WHETHER to seal.

  2. Layer 1 auto-creation: After L0 seals, encapsulate_current_layer() creates L1,
     but the evolver's layer progression loop needed to handle the case where L0
     seals but L1 never forms (because sealing never triggered).
     FIX: With #1 fixed, sealing should trigger reliably; layer progression already
     handles post-seal L1 creation correctly.

Hypotheses:
  H41 (sealing rate): >= 6/8 seeds seal L0 within 5000 steps (was 3/8 in exp_120)
  H42 (sealing step): mean sealing step < 3000
  H43 (L1 formation): >= 4/8 seeds form L1 after L0 seal (was 0/8 in exp_120)
  H44 (partial freeze): sealed bits are a proper subset (not all or nothing)
  H45 (CIV range): CIV in [2, 20] for sealed seeds

Config: N0=48, steps=5000, binding_threshold=0.05, ILP floor=15
        Same as exp_120 but with the A9 total_unique_active fix.

Invoke:
  Batch: python exp_121_phase5_b7_sealing_fix.py
  Single: python exp_121_phase5_b7_sealing_fix.py <seed>
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
from engine.institutional_layer_protector import (
    InstitutionalLayerProtector, DEFAULT_INSTITUTIONAL_PROTECTOR_CONFIG,
)


# ─── 8 baseline seeds ───
ALL_SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]

# ─── Config ───
CONFIG = {
    'N0': 48,
    'total_steps': 5000,
    'binding_threshold': 0.05,
    'ilp_floor': 15,
    'ilp_consumption_rate': 0.10,
}


def run_single_seed(seed: int, config: dict) -> dict:
    """Run a single seed and return results."""
    np.random.seed(seed)
    torch.random.manual_seed(seed)

    N0 = config['N0']
    total_steps = config['total_steps']

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

    # Run
    start_time = time.time()
    result = evolver.run(verbose=False)
    elapsed = time.time() - start_time

    # Extract results
    layer_results = result['layer_results']
    l0_sealed = layer_results[0]['sealed'] if len(layer_results) >= 1 else False
    l1_formed = len(layer_results) >= 2
    sealed_bits_count = 0
    if len(layer_results) >= 1:
        l0 = layer_results[0]
        sealed_bits_count = l0.get('N', N0) - l0.get('w', N0)  # approximate

    # Check A9 total_unique_active
    total_unique = len(constraints.total_unique_active)
    active_window = constraints._count_active_in_window(
        constraints._step_counter())
    sealing_threshold = getattr(constraints, 'sealing_activation_threshold', N0)

    # CIV from constraints cycle states (approximate)
    civ_approx = len(constraints.cycle_states) if hasattr(constraints, 'cycle_states') else 0

    return {
        'seed': seed,
        'N0': N0,
        'total_steps': total_steps,
        'elapsed_s': round(elapsed, 1),
        'l0_sealed': l0_sealed,
        'l1_formed': l1_formed,
        'sealed_bits_count': sealed_bits_count,
        'total_unique_active': total_unique,
        'active_in_window': active_window,
        'sealing_threshold': sealing_threshold,
        'civ_approx': civ_approx,
        'n_layers': result['n_layers'],
        'final_layer': result['hierarchy_summary'].get('final_layer', 0),
    }


def analyze_results(results: list) -> dict:
    """Analyze batch results and check hypotheses."""
    n = len(results)
    sealed_seeds = [r for r in results if r['l0_sealed']]
    l1_seeds = [r for r in results if r['l1_formed']]

    # H41: sealing rate >= 6/8
    h41_pass = len(sealed_seeds) >= 6
    # H43: L1 formation >= 4/8
    h43_pass = len(l1_seeds) >= 4
    # H44: partial freeze (sealed_bits > 0 and < N0)
    partial_freeze = [r for r in sealed_seeds
                      if 0 < r['sealed_bits_count'] < r['N0']]
    h44_pass = len(partial_freeze) >= max(1, len(sealed_seeds) // 2)
    # H45: CIV in [2, 20] for sealed seeds
    civ_ok = [r for r in sealed_seeds
              if 2 <= r['civ_approx'] <= 20]
    h45_pass = len(civ_ok) >= max(1, len(sealed_seeds) // 2)

    return {
        'total_seeds': n,
        'sealed_count': len(sealed_seeds),
        'sealed_rate': f"{len(sealed_seeds)}/{n} = {len(sealed_seeds)/n*100:.1f}%",
        'l1_formed_count': len(l1_seeds),
        'l1_formed_rate': f"{len(l1_seeds)}/{n} = {len(l1_seeds)/n*100:.1f}%",
        'partial_freeze_count': len(partial_freeze),
        'h41_pass': h41_pass,
        'h43_pass': h43_pass,
        'h44_pass': h44_pass,
        'h45_pass': h45_pass,
        'sealed_seeds': [r['seed'] for r in sealed_seeds],
        'details': results,
    }


def main():
    print("=" * 70)
    print("Phase 5 Track B7: A9 Sealing Fix + Layer 1 Auto-Creation")
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
    print("TRACK B7 RESULTS")
    print("=" * 70)
    h41_mark = '[PASS]' if analysis['h41_pass'] else '[FAIL]'
    h43_mark = '[PASS]' if analysis['h43_pass'] else '[FAIL]'
    h44_mark = '[PASS]' if analysis['h44_pass'] else '[FAIL]'
    h45_mark = '[PASS]' if analysis['h45_pass'] else '[FAIL]'
    print(f"Sealing rate (H41): {analysis['sealed_rate']} {h41_mark}")
    print(f"L1 formation (H43): {analysis['l1_formed_rate']} {h43_mark}")
    print(f"Partial freeze (H44): {analysis['partial_freeze_count']}/{analysis['total_seeds']} {h44_mark}")
    print(f"CIV range [2,20] (H45): {h45_mark}")
    print(f"\nSealed seeds: {analysis['sealed_seeds']}")

    # Per-seed detail
    for r in results:
        status = "SEALED" if r['l0_sealed'] else "NOT SEALED"
        l1 = "L1 formed" if r['l1_formed'] else "no L1"
        thresh = r.get('sealing_threshold', r['N0'])
        print(f"  Seed {r['seed']:3d}: {status:10s} | {l1:10s} | "
              f"unique={r['total_unique_active']:2d}/{thresh:2d} | "
              f"window={r['active_in_window']:2d} | "
              f"layers={r['n_layers']} | "
              f"civ≈{r['civ_approx']}")

    # Save results
    output = {
        'experiment': 'exp_121_phase5_b7_sealing_fix',
        'timestamp': datetime.now().isoformat(),
        'config': CONFIG,
        'analysis': analysis,
        'results': results,
    }
    output_path = os.path.join(
        os.path.dirname(__file__), 'exp_121_b7_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_path}")


if __name__ == '__main__':
    main()
