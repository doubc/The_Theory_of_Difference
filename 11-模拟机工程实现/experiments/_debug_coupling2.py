"""Debug: trace injection values and binding_strength changes."""
import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch, numpy as np
from engine.subspace_field import make_static_field
from engine.subspace_field import Rules, SubspaceSpec
from engine.subspace_evolver import SubspaceAwareEvolver, CouplingEngine, SubspaceSolver
from engine.subspace_field import _CouplingConnection, CouplingDirection

# Test the coupling callback directly
field = make_static_field(N0=108, k=3, coupling_strength=1.0)

# Create mock solvers with dummy direction data
rules = Rules()
mock_layer_result = {
    "direction": torch.tensor([-1, 1, 1, 1, -1, 1], dtype=torch.long),  # 4/6 = 0.67
}
spec0 = SubspaceSpec({0,1,2,3,4,5}, rules, "S0")
s0 = SubspaceSolver(name="S0", subspace=spec0, N=6)
s0.layer_result = mock_layer_result

spec1 = SubspaceSpec({6,7,8,9,10,11}, rules, "S1")
s1 = SubspaceSolver(name="S1", subspace=spec1, N=6)
# S1 gets no layer_result initially (hasn't run yet)

solvers = {"S0": s0, "S1": s1}

# Create coupling engine and get callback for S1
engine = CouplingEngine(field)
cb = engine.make_callback("S1", solvers)

# Create mock constraints with real binding_strength
from acl.axioms_v2 import AxiomConstraints
cons = AxiomConstraints(N=6)
print(f"Before callback: bs mean={cons.binding_strength.mean().item():.6f}, "
      f"diag={cons.binding_strength.diag().tolist()}")
print(f"Source direction mean: {mock_layer_result['direction'].float().mean().item():.4f}")

# Simulate callback at step 0
cb(0, None, None, cons)
print(f"After callback: bs mean={cons.binding_strength.mean().item():.6f}, "
      f"diag={cons.binding_strength.diag().tolist()}")
print(f"After callback: bs[0,1]={cons.binding_strength[0,1].item():.6f} (was about 0.01)")

# Second callback
cb(500, None, None, cons)
print(f"After 2nd callback: bs mean={cons.binding_strength.mean().item():.6f}")
print(f"After 2nd callback: bs[0,1]={cons.binding_strength[0,1].item():.6f}")
print("\nConclusion: If bs[0,1] changed, coupling modifies off-diagonal elements.")
