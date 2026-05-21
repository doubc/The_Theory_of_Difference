"""Test cross-layer gravity modulation import"""
import sys
sys.path.insert(0, '.')

try:
    from engine.hierarchical_evolver import HierarchicalEvolver, HierarchicalSnapshot
    print("Import OK")
    
    # Test instantiation
    ev = HierarchicalEvolver(N0=48, steps_per_layer=100, verbose_gravity=True)
    print(f"HierarchicalEvolver created: N0={ev.N0}, _verbose_gravity={ev._verbose_gravity}")
    
    # Check if _compute_cross_layer_gravity exists
    assert hasattr(ev, '_compute_cross_layer_gravity'), "Missing _compute_cross_layer_gravity"
    assert hasattr(ev, '_apply_cross_layer_gravity_modulation'), "Missing _apply_cross_layer_gravity_modulation"
    print("Cross-layer gravity methods present")
    
    print("All checks passed!")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
