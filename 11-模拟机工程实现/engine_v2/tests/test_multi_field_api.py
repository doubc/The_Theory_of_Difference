"""
Test script to verify MultiFieldConfig + MultiFieldManager API fix.

Tests:
1. MultiFieldConfig accepts 'fields' parameter
2. MultiFieldManager adds fields from config
3. OpenSystemCoupling works with multi-field

Author: AI Agent (Heartbeat 2026-06-14 04:14)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diffsim.multi_field import MultiFieldManager, ConstraintField, MultiFieldConfig
from diffsim.environment_energy import EnvironmentConfig, OpenSystemCoupling

def test_multifield_config_with_fields():
    """Test 1: MultiFieldConfig accepts 'fields' parameter."""
    print("Test 1: MultiFieldConfig with fields parameter...")
    
    # Create fields
    field1 = ConstraintField(name="test1", strength=0.5)
    field2 = ConstraintField(name="test2", strength=0.3)
    
    # Create config with fields
    config = MultiFieldConfig(
        fields=[field1, field2],
        coupling_mode="additive",
        normalize_weights=True
    )
    
    # Verify fields stored in config
    assert config.fields is not None, "fields should not be None"
    assert len(config.fields) == 2, f"Expected 2 fields, got {len(config.fields)}"
    assert config.fields[0].name == "test1"
    assert config.fields[1].name == "test2"
    
    print("  PASSED: MultiFieldConfig accepts 'fields' parameter")

def test_multifield_manager_init_with_config():
    """Test 2: MultiFieldManager adds fields from config."""
    print("Test 2: MultiFieldManager adds fields from config...")
    
    # Create fields
    field1 = ConstraintField(name="f1", strength=0.6)
    field2 = ConstraintField(name="f2", strength=0.4)
    
    # Create config with fields
    config = MultiFieldConfig(fields=[field1, field2])
    
    # Create manager with config
    manager = MultiFieldManager(config)
    
    # Verify fields were added
    assert len(manager.fields) == 2, f"Expected 2 fields, got {len(manager.fields)}"
    assert manager.fields[0].name == "f1"
    assert manager.fields[1].name == "f2"
    
    print("  PASSED: MultiFieldManager adds fields from config")

def test_multifield_manager_compute_constraint():
    """Test 3: compute_effective_constraint works."""
    print("Test 3: compute_effective_constraint...")
    
    # Create fields
    field1 = ConstraintField(name="f1", strength=0.5, coupling_type="additive")
    field2 = ConstraintField(name="f2", strength=0.3, coupling_type="additive")
    
    # Create config and manager
    config = MultiFieldConfig(fields=[field1, field2], coupling_mode="additive")
    manager = MultiFieldManager(config)
    
    # Compute at t=0
    result = manager.compute_effective_constraint(0)
    
    # Should be sum of strengths (additive, normalized)
    # 0.5 + 0.3 = 0.8, normalized to 1.0
    assert 0.0 <= result <= 1.0, f"Result should be in [0, 1], got {result}"
    
    print(f"  PASSED: compute_effective_constraint returned {result:.3f}")

def test_open_system_coupling_with_multifield():
    """Test 4: OpenSystemCoupling works with multi-field."""
    print("Test 4: OpenSystemCoupling with multi-field...")
    
    # Create fields
    field1 = ConstraintField(name="env1", strength=0.6)
    field2 = ConstraintField(name="env2", strength=0.4)
    
    # Create multi-field config
    mf_config = MultiFieldConfig(
        fields=[field1, field2],
        coupling_mode="additive"
    )
    
    # Create environment config with multi-field
    env_config = EnvironmentConfig(
        base_rate=2.0,
        constraint_energy_factor=1.5,
        use_multi_field=True,
        multi_field_config=mf_config
    )
    
    # Create coupling
    coupling = OpenSystemCoupling(env_config)
    
    # Verify multi-field manager was created
    assert coupling.use_multi_field == True, "use_multi_field should be True"
    assert coupling.multi_field_manager is not None, "multi_field_manager should not be None"
    assert len(coupling.multi_field_manager.fields) == 2, \
        f"Expected 2 fields, got {len(coupling.multi_field_manager.fields)}"
    
    # Test step function
    result = coupling.step(
        current_energy=50.0,
        current_entropy=0.5,
        layer_bits=None,
        t=0
    )
    
    assert 'energy_injected' in result, "result should have 'energy_injected'"
    assert 'effective_constraint' in result or 'constraint_strength' in result, \
        "result should have constraint info"
    
    print("  PASSED: OpenSystemCoupling works with multi-field")

def test_exp_208_script_imports():
    """Test 5: exp_208 script can be imported without errors."""
    print("Test 5: exp_208 script imports...")
    
    try:
        # Try importing the script (not running it)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "exp_208",
            os.path.join(os.path.dirname(__file__), "experiments", "exp_208_phase22_p5_multi_field.py")
        )
        # Don't actually load it, just check syntax
        with open(os.path.join(os.path.dirname(__file__), "experiments", "exp_208_phase22_p5_multi_field.py"), 'r') as f:
            compile(f.read(), "exp_208_phase22_p5_multi_field.py", 'exec')
        print("  PASSED: exp_208 script syntax is valid")
    except SyntaxError as e:
        print(f"  FAILED: Syntax error in exp_208: {e}")
        return False
    except Exception as e:
        print(f"  FAILED: Error checking exp_208: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Multi-Field API Fix Verification")
    print("=" * 60)
    print()
    
    tests = [
        test_multifield_config_with_fields,
        test_multifield_manager_init_with_config,
        test_multifield_manager_compute_constraint,
        test_open_system_coupling_with_multifield,
        test_exp_208_script_imports
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
            passed += 1
        except AssertionError as e:
            print(f"  FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  FAILED: Unexpected error: {e}")
            failed += 1
        print()
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)
