"""Smoke test: verify coupling fix at N0=108 (36 bits/subspace)."""
import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch, numpy as np
from engine.subspace_field import make_static_field
from engine.subspace_evolver import run_subspace_experiment

for cs in [0.0, 0.5, 1.0]:
    torch.manual_seed(42); np.random.seed(42)
    field = make_static_field(N0=108, k=3, coupling_strength=cs)
    t0 = time.time()
    result = run_subspace_experiment(field, steps_per_layer=2000, max_layers=2,
                                      coupling_enabled=True, verbose=False)
    s = result["summary"]
    subs = s["subspaces"]
    hws = {k: v["final_hamming_weight"] for k, v in subs.items()}
    sealed = {k: v["ever_sealed"] for k, v in subs.items()}
    print(f"cs={cs:.1f}: HW={hws}, Sealed={sealed}, L1={s['l1_formed']}/{s['num_subspaces']}, t={time.time()-t0:.1f}s")
print("\nIf cs values produce different sealed patterns, coupling fix works at N0=108.")