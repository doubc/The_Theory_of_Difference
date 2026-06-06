"""Smoke test: verify coupling fix actually changes dynamics."""
import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch, numpy as np
from engine.subspace_field import make_static_field
from engine.subspace_evolver import run_subspace_experiment

for cs in [0.0, 1.0]:
    torch.manual_seed(42); np.random.seed(42)
    field = make_static_field(N0=72, k=3, coupling_strength=cs)
    t0 = time.time()
    result = run_subspace_experiment(field, steps_per_layer=1000, max_layers=2,
                                      coupling_enabled=True, verbose=False)
    s = result["summary"]
    subs = s["subspaces"]
    hws = {k: v["final_hamming_weight"] for k, v in subs.items()}
    print(f"cs={cs:.1f}: HW={hws}, L1={s['l1_formed']}/{s['num_subspaces']}, "
          f"elapsed={time.time()-t0:.1f}s")

# Check for different results
print("\n---\nIf cs=0.0 and cs=1.0 show different HW values, coupling fix works.")
