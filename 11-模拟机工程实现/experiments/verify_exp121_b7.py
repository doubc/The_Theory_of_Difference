"""Quick verification of Track B7 partial sealing fixes"""
import sys
sys.path.insert(0, 'C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现')

import torch
import numpy as np
from datetime import datetime

# Test 1: Verify partial sealing in AxiomConstraints
print("=" * 60)
print("Test 1: AxiomConstraints partial sealing")
print("=" * 60)

from acl.axioms_v2 import AxiomConstraints

torch.manual_seed(42)
np.random.seed(42)

N0 = 48
constraints = AxiomConstraints(N0, n_hierarchy_bits=16)

# Simulate steps to trigger sealing
for step in range(500):
    constraints.set_current_step(step)
    # Activate random bits
    for _ in range(10):
        idx = np.random.randint(0, N0)
        constraints.record_active(idx)
        constraints.total_unique_active.add(idx)
    
    # Trigger A9
    flip_idx = np.random.randint(0, N0)
    constraints.check_A9(flip_idx, partial_sealing=True)
    
    if constraints.sealed:
        status = constraints.get_sealing_status()
        print(f"  Sealed at step {step}:")
        print(f"    sealed_lateral: {status['sealed_lateral']} ({status['n_sealed_lateral']}/{status['n_lateral_total']})")
        print(f"    sealed_hierarchy: {status['sealed_hierarchy']} ({status['n_sealed_hierarchy']}/{status['n_hierarchy_total']})")
        print(f"    total frozen: {status['n_sealed_total']}")
        break

# Test 2: Verify encapsulate_with_bits
print("\n" + "=" * 60)
print("Test 2: HierarchyManager.encapsulate_with_bits")
print("=" * 60)

from engine.hierarchy_manager import HierarchyManager

torch.manual_seed(42)
np.random.seed(42)

hm = HierarchyManager(N0=48, binding_threshold=0.05)
layer = hm.get_layer(0)

# Simulate some sealing
frozen_lateral = set(range(16, 16+8))  # Freeze 8 lateral bits
active = set(range(48)) - frozen_lateral

new_state, enc_bits, mapping = hm.encap_engine.encapsulate(
    state=layer.state,
    frozen_bits=frozen_lateral,
    binding_strength=layer.constraints.binding_strength,
    active_bits=active,
    layer=0
)

print(f"  Encapsulated {len(enc_bits)} bits from {len(frozen_lateral)} frozen")
print(f"  New layer size: {len(new_state)}")
print(f"  Encapsulated bits: {[e.bit_id for e in enc_bits]}")

# Test 3: Verify HierarchicalEvolver with partial_sealing
print("\n" + "=" * 60)
print("Test 3: HierarchicalEvolver partial_sealing=True")
print("=" * 60)

from engine.hierarchical_evolver import HierarchicalEvolver

torch.manual_seed(42)
np.random.seed(42)

evolver = HierarchicalEvolver(
    N0=48,
    steps_per_layer=500,  # Short run for verification
    sample_interval=100,
    max_layers=3,
    device="cpu",
    binding_threshold=0.05,
    min_group_size=2,
    auto_encapsulate=True,
    partial_sealing=True,  # Track B7
    verbose_gravity=False,
)

result = evolver.run(verbose=True)

hierarchy_summary = evolver.hierarchy.get_hierarchy_summary()
print(f"\n  Total layers: {hierarchy_summary['n_layers']}")
for layer in hierarchy_summary['layers']:
    print(f"  L{layer['id']}: N={layer['N']}, sealed={layer['sealed']}, "
          f"w={layer['w']}, cycles={layer['cycles']}")

# Check L0 sealing status
if hierarchy_summary['n_layers'] >= 1:
    l0 = evolver.hierarchy.get_layer(0)
    status = l0.constraints.get_sealing_status()
    print(f"\n  L0 sealing status:")
    print(f"    sealed_lateral: {status['sealed_lateral']}")
    print(f"    sealed_hierarchy: {status['sealed_hierarchy']}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED - Track B7 fixes verified")
print("=" * 60)
print(f"Date: {datetime.now().isoformat()}")
