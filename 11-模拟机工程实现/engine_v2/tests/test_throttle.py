#!/usr/bin/env python3
"""Test script to verify throttle mechanism implementation.

Phase 21 P1: Energy-mechanism coupling verification

Test objectives:
1. EnergyManager.throttle_factor() returns correct values
2. Mechanism functions accept throttle parameter
3. Verify the integration in Layer.run_until_seal()
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diffsim.energy import EnergyManager, EnergyConfig
from diffsim.mechanisms import m1_clustering, m5_minimal_variation, m6_breaking
import numpy as np
import inspect


def test_throttle_factor():
    """Test throttle_factor() calculation correctness."""
    print("=" * 60)
    print("Test 1: EnergyManager.throttle_factor()")
    print("=" * 60)
    
    config = EnergyConfig(initial_budget=100.0, decay_rate=0.01, injection_rate=0.5)
    em = EnergyManager(config)
    
    # Test throttle at different budget ratios
    test_cases = [
        (100.0, 1.0),   # 100% budget -> throttle = 1.0
        (80.0, 1.0),    # 80% -> still >= 0.5 -> 1.0
        (50.0, 1.0),    # 50% -> exactly 0.5 -> 1.0
        (30.0, 0.5),    # 30% -> (0.3-0.1)/0.4 = 0.5
        (10.0, 0.0),    # 10% -> <= 0.1 -> 0.0
        (5.0, 0.0),     # 5% -> <= 0.1 -> 0.0
    ]
    
    all_pass = True
    for budget, expected in test_cases:
        em.budget = budget
        actual = em.throttle_factor()
        status = "[PASS]" if abs(actual - expected) < 0.01 else "[FAIL]"
        if status == "[FAIL]":
            all_pass = False
        print(f"  budget={budget:6.1f} ({budget/100:.1%}) -> throttle={actual:.3f} (expected={expected:.3f}) {status}")
    
    print(f"\nResult: {'ALL PASS' if all_pass else 'SOME FAILED'}\n")
    return all_pass


def test_mechanism_throttle_signature():
    """Test mechanism function signatures (whether they accept throttle param)."""
    print("=" * 60)
    print("Test 2: Mechanism Function Signatures")
    print("=" * 60)
    
    mechanisms = [
        ("m1_clustering", m1_clustering),
        ("m5_minimal_variation", m5_minimal_variation),
        ("m6_breaking", m6_breaking),
    ]
    
    all_pass = True
    for name, func in mechanisms:
        sig = inspect.signature(func)
        has_throttle = 'throttle' in sig.parameters
        status = "[PASS]" if has_throttle else "[FAIL]"
        if not has_throttle:
            all_pass = False
        print(f"  {name:30s} throttle param: {has_throttle} {status}")
    
    print(f"\nResult: {'ALL PASS' if all_pass else 'SOME FAILED'}\n")
    return all_pass


def test_world_import():
    """Test that world.py can be imported and Layer class exists."""
    print("=" * 60)
    print("Test 3: World Module Import")
    print("=" * 60)
    
    try:
        from diffsim.world import Layer, Params
        print("  [PASS] Successfully imported Layer, Params")
        
        # Check that Layer.run_until_seal exists and has energy integration
        if hasattr(Layer, 'run_until_seal'):
            print("  [PASS] Layer.run_until_seal() method exists")
            
            # Read the source to verify throttle integration
            import inspect
            source = inspect.getsource(Layer.run_until_seal)
            
            checks = [
                ('throttle_factor()', 'throttle_factor()' in source),
                ('throttle parameter', 'throttle' in source),
                ('m1_clustering(self, throttle)', 'm1_clustering(self, throttle)' in source or 'm1_clustering(self, throttle)' in source),
            ]
            
            for desc, passed in checks:
                status = "[PASS]" if passed else "[FAIL]"
                print(f"  {desc:40s} {status}")
            
            all_pass = all(passed for _, passed in checks)
        else:
            print("  [FAIL] Layer.run_until_seal() method not found")
            all_pass = False
            
    except Exception as e:
        print(f"  [FAIL] Import failed: {e}")
        all_pass = False
    
    print(f"\nResult: {'ALL PASS' if all_pass else 'SOME FAILED'}\n")
    return all_pass


def test_syntax_check():
    """Verify modified files have correct Python syntax."""
    print("=" * 60)
    print("Test 4: Syntax Check")
    print("=" * 60)
    
    import py_compile
    
    files_to_check = [
        "diffsim/energy.py",
        "diffsim/mechanisms.py",
        "diffsim/world.py",
    ]
    
    all_pass = True
    for filepath in files_to_check:
        full_path = os.path.join(os.path.dirname(__file__), filepath)
        try:
            py_compile.compile(full_path, doraise=True)
            print(f"  {filepath:40s} [PASS]")
        except py_compile.PyCompileError as e:
            print(f"  {filepath:40s} [FAIL] {e}")
            all_pass = False
    
    print(f"\nResult: {'ALL PASS' if all_pass else 'SOME FAILED'}\n")
    return all_pass


def main():
    print("\n" + "=" * 60)
    print("Phase 21 P1: Throttle Mechanism Verification")
    print("=" * 60 + "\n")
    
    results = []
    results.append(("Test 1: throttle_factor()", test_throttle_factor()))
    results.append(("Test 2: Mechanism signatures", test_mechanism_throttle_signature()))
    results.append(("Test 3: World module import", test_world_import()))
    results.append(("Test 4: Syntax check", test_syntax_check()))
    
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {name:40s} {status}")
    
    all_pass = all(passed for _, passed in results)
    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILED'}\n")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
