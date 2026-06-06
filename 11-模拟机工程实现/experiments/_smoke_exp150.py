"""Quick smoke test for SubspaceAwareEvolver — single run at N0=72, k=3."""
import sys, os, time, json
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
import torch, numpy as np
from engine.subspace_field import make_static_field
from engine.subspace_evolver import run_subspace_experiment

torch.manual_seed(42); np.random.seed(42)
field = make_static_field(N0=72, k=3, coupling_strength=0.0)
t0 = time.time()
result = run_subspace_experiment(field, steps_per_layer=500, max_layers=2, coupling_enabled=True, verbose=False)
elapsed = time.time() - t0

summary = result.get("summary", {})
l1 = summary.get("l1_formed", 0)
ns = summary.get("num_subspaces", 0)
print(f"Layers executed: {summary.get('layers_executed', 0)}")
print(f"L1 formed: {l1}/{ns}")
print(f"Subspaces: {json.dumps({k: v for k,v in summary.get('subspaces', {}).items()}, indent=2)}")
print(f"Time: {elapsed:.1f}s")
