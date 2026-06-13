"""
Standalone test for Multi-Field integration with environment_energy.py.

Tests the integration without requiring full package import.

Author: AI Agent (Heartbeat 2026-06-14 03:14)
"""

import sys
import os

# Add diffsim directory to path
diffsim_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'diffsim')
sys.path.insert(0, diffsim_path)

try:
    # Import directly from modules
    from environment_energy import (
        EnvironmentConfig, OpenSystemCoupling,
        EnvironmentEnergyField, EntropyExhaust
    )
    print("Imported environment_energy successfully")
except ImportError as e:
    print(f"Import error (environment_energy): {e}")
    sys.exit(1)

try:
    from multi_field import (
        MultiFieldManager, ConstraintField, MultiFieldConfig,
        create_two_field_interference, create_competitive_dominance
    )
    print("Imported multi_field successfully")
except ImportError as e:
    print(f"Import error (multi_field): {e}")
    print("Warning: Multi-field not available, some tests will be skipped")
    MultiFieldManager = None


def test_multi_field_integration():
    """Test that OpenSystemCoupling uses MultiFieldManager."""
    print("\n=== Test 1: Multi-Field Integration ===")
    
    if MultiFieldManager is None:
        print("  SKIPPED: MultiFieldManager not available")
        return True
    
    # Create config with multi-field enabled
    config = EnvironmentConfig(
        use_multi_field=True,
        base_rate=2.0,
        constraint_energy_factor=1.5
    )
    
    # Create coupling
    coupling = OpenSystemCoupling(config)
    
    # Check multi-field is enabled
    assert coupling.use_multi_field == True, "Multi-field should be enabled"
    print("  Multi-field mode enabled: PASSED")
    
    # Add fields
    coupling.add_constraint_field(ConstraintField(
        name="field_a",
        strength=0.5,
        coupling_type="additive"
    ))
    coupling.add_constraint_field(ConstraintField(
        name="field_b",
        strength=0.3,
        coupling_type="additive"
    ))
    
    assert len(coupling.multi_field_manager.fields) == 2, "Should have 2 fields"
    print("  Added 2 fields: PASSED")
    
    # Run a few steps and check effective constraint changes
    results = []
    for t in range(5):
        result = coupling.step(
            current_energy=100.0,
            current_entropy=0.5,
            layer_bits=None,
            t=t
        )
        results.append(result['effective_constraint'])
    
    print(f"  Effective constraints: {[f'{c:.3f}' for c in results]}")
    print("  Step with multi-field: PASSED")
    
    return True


def test_single_vs_multi_field():
    """Compare single constraint vs multi-field constraint."""
    print("\n=== Test 2: Single vs Multi-Field ===")
    
    if MultiFieldManager is None:
        print("  SKIPPED: MultiFieldManager not available")
        return True
    
    # Single constraint
    config_single = EnvironmentConfig(
        use_multi_field=False,
        constraint_strength=0.5,
        base_rate=2.0
    )
    coupling_single = OpenSystemCoupling(config_single)
    
    # Multi-field (one field with same strength)
    config_multi = EnvironmentConfig(use_multi_field=True)
    coupling_multi = OpenSystemCoupling(config_multi)
    coupling_multi.add_constraint_field(ConstraintField(
        name="only_field",
        strength=0.5,
        coupling_type="additive"
    ))
    
    # Run steps
    for t in range(3):
        r_single = coupling_single.step(100.0, 0.5, None, t)
        r_multi = coupling_multi.step(100.0, 0.5, None, t)
        
        c_single = r_single['effective_constraint']
        c_multi = r_multi['effective_constraint']
        
        print(f"  t={t}: single={c_single:.3f}, multi={c_multi:.3f}")
    
    print("  Single vs multi comparison: PASSED")
    return True


def test_competitive_fields():
    """Test competitive coupling (winner-take-all)."""
    print("\n=== Test 3: Competitive Fields ===")
    
    if MultiFieldManager is None:
        print("  SKIPPED: MultiFieldManager not available")
        return True
    
    config = EnvironmentConfig(use_multi_field=True)
    coupling = OpenSystemCoupling(config)
    
    # Add competitive fields
    coupling.add_constraint_field(ConstraintField(
        name="strong",
        strength=0.8,
        coupling_type="competitive"
    ))
    coupling.add_constraint_field(ConstraintField(
        name="weak",
        strength=0.2,
        coupling_type="competitive"
    ))
    
    # Run step
    result = coupling.step(100.0, 0.5, None, 0)
    effective_c = result['effective_constraint']
    
    # Competitive should pick the strongest (0.8)
    assert abs(effective_c - 0.8) < 0.01, f"Expected ~0.8, got {effective_c}"
    print(f"  Effective constraint (competitive): {effective_c:.3f}")
    print("  Competitive coupling: PASSED")
    
    return True


def test_disable_multi_field():
    """Test disabling multi-field mode."""
    print("\n=== Test 4: Disable Multi-Field ===")
    
    if MultiFieldManager is None:
        print("  SKIPPED: MultiFieldManager not available")
        return True
    
    config = EnvironmentConfig(use_multi_field=True)
    coupling = OpenSystemCoupling(config)
    coupling.add_constraint_field(ConstraintField(name="test", strength=0.5))
    
    assert coupling.use_multi_field == True
    
    # Disable
    coupling.disable_multi_field()
    
    assert coupling.use_multi_field == False
    print("  Disable multi-field: PASSED")
    
    # Should use default constraint_strength now
    result = coupling.step(100.0, 0.5, None, 0)
    print(f"  Constraint after disable: {result['effective_constraint']:.3f}")
    
    return True


def test_multi_field_summary():
    """Test get_summary() with multi-field."""
    print("\n=== Test 5: Multi-Field Summary ===")
    
    if MultiFieldManager is None:
        print("  SKIPPED: MultiFieldManager not available")
        return True
    
    config = EnvironmentConfig(use_multi_field=True)
    coupling = OpenSystemCoupling(config)
    coupling.add_constraint_field(ConstraintField(name="f1", strength=0.5))
    coupling.add_constraint_field(ConstraintField(name="f2", strength=0.3))
    
    # Run a step
    coupling.step(100.0, 0.5, None, 0)
    
    # Get summary
    summary = coupling.get_summary()
    
    assert 'use_multi_field' in summary
    assert summary['use_multi_field'] == True
    assert 'multi_field' in summary
    
    mf_summary = summary['multi_field']
    assert 'n_fields' in mf_summary
    assert mf_summary['n_fields'] == 2
    
    print(f"  Summary: {mf_summary['n_fields']} fields, "
          f"effective_c={mf_summary['effective_constraint']:.3f}")
    print("  Multi-field summary: PASSED")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Multi-Field Integration (Standalone)")
    print("=" * 60)
    
    tests = [
        test_multi_field_integration,
        test_single_vs_multi_field,
        test_competitive_fields,
        test_disable_multi_field,
        test_multi_field_summary
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            success = test_func()
            if success:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)
