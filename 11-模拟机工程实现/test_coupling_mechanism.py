"""
Quick diagnostic: verify that FixedCouplingEngine's callback
actually writes non-zero coupling_bias during a real run.
"""
import sys
sys.path.insert(0, '.')

import torch
from acl.axioms_v2 import AxiomConstraints
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
from experiments.exp_152_phase11_p4_fixed_coupling import (
    patch_axioms_with_coupling_bias,
    FixedCouplingEngine,
    make_field,
)

patch_axioms_with_coupling_bias()

# ================================================================
# Test 1: Does the callback write non-zero coupling_bias?
# ================================================================
print("=" * 60)
print("Test 1: Callback writes coupling_bias")
print("=" * 60)

N = 12
ev = SpatialLongRangeEvolver(N=N, total_steps=300, sample_interval=50, device='cpu')

# Create a fake "source solver" result
fake_result = {
    "final_state": torch.randn(N),
    "hamming_weight": 6.0,
    "direction": torch.ones(N) * 0.5,  # all slightly energized
}
# We can't easily fake the full SubspaceSolver, so instead
# directly test that the callback logic works by mocking.
# Let's just verify the patched AxiomConstraints has coupling_bias.

print(f"  constraints has coupling_bias: {hasattr(ev.constraints, 'coupling_bias')}")
print(f"  coupling_bias (init): {ev.constraints.coupling_bias.abs().sum().item():.4f}")

# Now run with a callback that simulates coupling
import numpy as np

def sim_coupling_callback(step, state, snapshot, constraints):
    # Simulate what FixedCouplingEngine does:
    # source has high activity → write positive bias
    fake_src_hw_norm = 0.7  # source is 70% active
    target_hw_norm = snapshot.w / max(snapshot.state.numel(), 1)
    bias_signal = 1.0 * (fake_src_hw_norm - target_hw_norm)  # strength=1.0
    bias_tensor = torch.full(
        (snapshot.state.numel(),),
        float(bias_signal),
        device=constraints.coupling_bias.device,
    )
    bias_tensor.clamp_(-1.0, 1.0)
    constraints.coupling_bias.copy_(bias_tensor)

print("\n  Running with simulated coupling callback...")
result = ev.run(verbose=False, step_callback=sim_coupling_callback)

# Check if coupling_bias was non-zero at any point
# (We can't easily intercept it mid-run without more plumbing)
print(f"  Final coupling_bias norm: {ev.constraints.coupling_bias.abs().sum().item():.4f}")
print(f"  Final sealed: {result['sealed']}")
print()

# ================================================================
# Test 2: Full two-subspace run with FixedCouplingEngine
# ================================================================
print("=" * 60)
print("Test 2: Full two-subspace run")
print("=" * 60)

from engine.subspace_evolver import SubspaceAwareEvolver, LayerCoordinator

torch.manual_seed(42)
field = make_field(12, 12, coupling_strength=2.0)

evolver = SubspaceAwareEvolver(
    subspace_field=field,
    steps_per_layer=500,
    sample_interval=50,
    max_layers=2,
    device='cpu',
    partial_sealing=False,
    coupling_enabled=True,
    coordination_strategy=LayerCoordinator.INDEPENDENT,
    verbose=False,
)
evolver.coupling_engine = FixedCouplingEngine(field, coupling_scale=1.0)

# Diagnostic: patch callback to print when it fires
_orig_make = evolver.coupling_engine.make_callback

def diagnostic_make_callback(solver_name, all_solvers):
    real_callback = _orig_make(solver_name, all_solvers)
    def wrapped(step, state, snapshot, constraints):
        print(f"    [{solver_name}] callback step={step}, "
              f"coupling_bias_norm={constraints.coupling_bias.abs().sum().item():.4f}")
        return real_callback(step, state, snapshot, constraints)
    return wrapped

evolver.coupling_engine.make_callback = diagnostic_make_callback

print("  Running SubspaceAwareEvolver with coupling_strength=2.0...")
result = evolver.run(verbose=True)
print(f"  L1 rate: {result['summary']['l1_rate']:.2f}")
print()

# ================================================================
# Test 3: Compare coupled vs isolated (different seeds)
# ================================================================
print("=" * 60)
print("Test 3: Coupled vs Isolated — different trajectories?")
print("=" * 60)

from experiments.exp_152_phase11_p4_fixed_coupling import run_single_experiment

print("  Running isolated (strength=0.0, seed=42)...")
r0 = run_single_experiment(
    coupling_strength=0.0, N0=12, N1=12,
    steps_per_layer=500, seed=42
)
print(f"  Result: {r0}")

print("  Running coupled (strength=2.0, seed=42)...")
r2 = run_single_experiment(
    coupling_strength=2.0, N0=12, N1=12,
    steps_per_layer=500, seed=42
)
print(f"  Result: {r2}")

print()
if r0['S0_final_w'] != r2['S0_final_w'] or r0['S1_final_w'] != r2['S1_final_w']:
    print("  ✓ Coupling produces DIFFERENT trajectories (good!)")
else:
    print("  ✗ Coupling produces SAME trajectories (still broken!)")
