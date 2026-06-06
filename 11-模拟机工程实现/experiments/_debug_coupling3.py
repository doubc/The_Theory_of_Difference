"""Debug: trace injection across multiple coupling levels."""
import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch, numpy as np
from engine.subspace_field import make_static_field
from engine.subspace_field import Rules, SubspaceSpec
from engine.subspace_evolver import SubspaceAwareEvolver, CouplingEngine, SubspaceSolver
from acl.axioms_v2 import AxiomConstraints

# Simulate actual run: run S0, see its direction, then see coupling to S1
torch.manual_seed(42); np.random.seed(42)

field = make_static_field(N0=108, k=3, coupling_strength=1.0)

# Run S0 isolated first
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver
evo0 = SpatialLongRangeEvolver(N=36, total_steps=500, sample_interval=500)
result0 = evo0.run(verbose=False)
print(f"S0 final direction mean: {result0['direction'].float().mean().item():.4f}")
print(f"S0 direction unique values: {result0['direction'].unique().tolist()}")
print(f"  # positive: {(result0['direction'] > 0).sum().item()}/{result0['direction'].numel()}")

# Compute injection
src_mean = float(result0['direction'].float().mean().item())
cs = 1.0
injection = cs * (src_mean - 0.5) * 2.0 * 0.1
print(f"  Injection per callback: {injection:.6f}")

# Check S1's binding_strength after one callback
spec0 = SubspaceSpec(set(range(36)), Rules(), "S0")
s0 = SubspaceSolver(name="S0", subspace=spec0, N=36)
s0.layer_result = result0
s0.hamming_weight = float(result0["hamming_weight_history"][-1]) if result0.get("hamming_weight_history") else 0

spec1 = SubspaceSpec(set(range(36,72)), Rules(), "S1")
s1 = SubspaceSolver(name="S1", subspace=spec1, N=36)

solvers = {"S0": s0, "S1": s1}
engine = CouplingEngine(field)
cb = engine.make_callback("S1", solvers)

cons = AxiomConstraints(N=36)
bs_before = cons.binding_strength[0,1].item()
cb(0, None, None, cons)
bs_after = cons.binding_strength[0,1].item()
print(f"\nS1 binding_strength[0,1]: {bs_before:.6f} -> {bs_after:.6f} (delta={bs_after-bs_before:.6f})")
print(f"S1 bs mean (all): {cons.binding_strength.mean().item():.6f}")
print(f"\nWith 10 callbacks (5000/500): cumulative = {injection * 10:.4f} per off-diagonal element")
