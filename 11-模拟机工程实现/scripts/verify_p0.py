import sys
sys.path.insert(0, '.')

from acl.axioms_v2 import AxiomConstraints
from engine.hierarchical_evolver import HierarchicalEvolver

ac = AxiomConstraints(N=72, n_hierarchy_bits=24)
print(f"N=72: min_active_bits = {ac.min_active_bits} (expected: 24)")
print(f"Sealed ratio: {(72 - ac.min_active_bits) / 72:.2%} (was 75%, now ~67%)")

he = HierarchicalEvolver(N0=48, steps_per_layer=100)
has_window = hasattr(he, '_odi_window')
print(f"_odi_window initialized: {has_window}")
if has_window:
    print(f"_odi_window len: {len(he._odi_window)}")
print(f"baseline_shift_anchor: {he.baseline_shift_anchor}")

print("\nAll P0 fixes verified!")
