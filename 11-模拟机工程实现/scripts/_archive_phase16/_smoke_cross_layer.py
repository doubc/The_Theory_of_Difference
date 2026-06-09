#!/usr/bin/env python
"""Smoke test for CrossLayerEvolver."""
import sys, os
sys.path.insert(0, 'C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现')

from engine.cross_layer_evolver import CrossLayerEvolver

print("=== CrossLayerEvolver Smoke Test ===")
ev = CrossLayerEvolver(
    N0=48,
    N1=48,
    L0_steps=5000,
    L1_steps=5000,
    device="cpu",
)
results = ev.run()
print(f"L0 sealed: {results.get('l0_sealed')} at step {results.get('l0_seal_step')}")
print(f"L1 sealed: {results.get('l1_sealed')} at step {results.get('l1_seal_step')}")
print(f"N clusters: {results.get('n_clusters', 'N/A')}")
print("=== Test Complete ===")
