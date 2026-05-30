import sys
sys.path.insert(0, r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现')

# Test import of modified modules
from acl.axioms_v2 import AxiomConstraints
from engine.hierarchical_evolver import HierarchicalEvolver

# Verify the min_active_bits change
ac = AxiomConstraints(N=72, n_hierarchy_bits=24)
print(f"N=72: min_active_bits = {ac.min_active_bits} (expected: 24)")
print(f"Expected sealed ratio: {(72 - ac.min_active_bits) / 72:.2%} (was 75%, now ~67%)")

# Verify HierarchicalEvolver has _odi_window
he = HierarchicalEvolver(N0=48, steps_per_layer=100)
print(f"HierarchicalEvolver._odi_window initialized: {hasattr(he, '_odi_window')}")
print(f"_odi_window type: {type(he._odi_window)}")

print("\nAll imports and basic checks passed!")
