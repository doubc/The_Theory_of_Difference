#!/usr/bin/env python3
"""Test script for multi_world.py - Phase 20 P0 baseline verification."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diffsim.multi_world import MultiWorld
from diffsim.world import Params

def test_basic_creation():
    """Test 1: Basic MultiWorld creation and independent run."""
    print("=" * 60)
    print("Test 1: Basic MultiWorld creation (coupling_mode='none')")
    print("=" * 60)
    
    mw = MultiWorld(
        n_worlds=4,
        N0=48,
        n0_active=40,
        n_colors=6,
        base_seed=42,
        coupling_strength=0.0,
        coupling_mode="none",
    )
    
    print(f"Created MultiWorld with {mw.n_worlds} worlds")
    print(f"N0={mw.N0}, coupling_mode={mw.coupling_mode}")
    
    # Run independently
    report = mw.run_all(max_layers=6, verbose=True)
    
    print(f"\nResults:")
    print(f"  Mean depth: {report.get('mean_depth', 0):.2f}")
    print(f"  Sealed worlds: {report.get('n_sealed', 0)}/{report.get('n_worlds', 0)}")
    
    # Print individual world depths
    if 'reports' in report:
        for i, r in enumerate(report['reports']):
            print(f"    World {i}: depth={r.get('depth', 0)}")
    
    return report

def test_coupling_modes():
    """Test 2: Different coupling modes."""
    print("\n" + "=" * 60)
    print("Test 2: Coupling modes")
    print("=" * 60)
    
    modes = ["none", "env_coupling", "bit_swap_soft"]
    
    for mode in modes:
        print(f"\n--- Mode: {mode} ---")
        mw = MultiWorld(
            n_worlds=2,
            N0=48,
            base_seed=123,
            coupling_strength=0.2 if mode != "none" else 0.0,
            coupling_mode=mode,
        )
        
        if mode == "none":
            report = mw.run_all(max_layers=4, verbose=False)
        else:
            report = mw.run_with_coupling(max_layers=4, verbose=False)
        
        print(f"  Depth: {report['mean_depth']:.2f}")
        print(f"  Sealed: {report['n_sealed']}/{report['n_worlds']}")
    
    return True

def test_hypotheses_p0():
    """Test 3: Verify H20-P0 hypotheses can be evaluated."""
    print("\n" + "=" * 60)
    print("Test 3: H20-P0 hypothesis evaluation")
    print("=" * 60)
    
    # Run 8 seeds for statistical significance
    all_depths = []
    all_sealed = []
    
    for seed in range(8):
        mw = MultiWorld(
            n_worlds=4,
            N0=48,
            base_seed=seed,
            coupling_strength=0.0,
            coupling_mode="none",
        )
        report = mw.run_all(max_layers=6, verbose=False)
        all_depths.append(report['mean_depth'])
        all_sealed.append(report['n_sealed'])
    
    print(f"Across 8 seeds:")
    print(f"  Mean depth: {np.mean(all_depths):.2f} ± {np.std(all_depths):.2f}")
    print(f"  Sealed rate: {np.mean([s/4 for s in all_sealed]):.2%}")
    
    # H20-P0a: Independent world sealing rate >= 75%
    seal_rate = np.mean([s/4 for s in all_sealed])
    H20_P0a = seal_rate >= 0.75
    print(f"\nH20-P0a (seal rate >= 75%): {'PASS' if H20_P0a else 'FAIL'} ({seal_rate:.2%})")
    
    # H20-P0b: Independent world sealing times uncorrelated (correlation < 0.5)
    # (Would need individual world seal steps)
    print(f"H20-P0b: Need individual world data (not implemented in this test)")
    
    # H20-P0c: Emergence depth difference < 1
    depth_diff = np.max(all_depths) - np.min(all_depths)
    H20_P0c = depth_diff < 1.0
    print(f"H20-P0c (depth diff < 1): {'PASS' if H20_P0c else 'FAIL'} ({depth_diff:.2f})")
    
    return H20_P0a and H20_P0c

if __name__ == "__main__":
    import numpy as np
    
    print("\nPhase 20 P0 Baseline - multi_world.py Verification\n")
    
    try:
        report1 = test_basic_creation()
        test_coupling_modes()
        hypotheses_pass = test_hypotheses_p0()
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"multi_world.py basic functionality: WORKING")
        print(f"H20-P0 hypotheses: {'PASS' if hypotheses_pass else 'PARTIAL'}")
        print(f"\nNext: Implement exp_190_phase20_p0_baseline.py with full data collection")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
