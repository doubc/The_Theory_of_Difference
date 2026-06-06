"""Debug: verify coupling callback actually modifies binding_strength."""
import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch, numpy as np
from engine.subspace_field import make_static_field
from engine.subspace_evolver import SubspaceAwareEvolver

# Create field with coupling
torch.manual_seed(42); np.random.seed(42)
field = make_static_field(N0=108, k=3, coupling_strength=0.5)
print(field.summary())

# Run with verbose to see coupling messages
evolver = SubspaceAwareEvolver(
    subspace_field=field,
    steps_per_layer=500,
    max_layers=1,
    coupling_enabled=True,
    verbose=True,
)
result = evolver.run()
print("\nFinal layer summaries:")
for ls in result["layer_summaries"]:
    cm = ls.get("coupling_metrics", {})
    for k, v in cm.items():
        print(f"  {k}: {v}")
print("\nSummary subspaces:")
for name, data in result["summary"]["subspaces"].items():
    print(f"  {name}: {data}")
