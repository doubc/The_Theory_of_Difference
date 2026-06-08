#!/usr/bin/env python
"""Quick smoke test for CrossLayerEvolver."""

import sys
sys.path.insert(0, '.')

from engine.cross_layer_evolver import CrossLayerEvolver

print('=== CrossLayerEvolver Smoke Test ===')
print('Import OK')

ev = CrossLayerEvolver(N0=24, N1=24, L0_steps=2000, L1_steps=2000, device='cpu')
print('Init OK')

results = ev.run()
print(f"L0 sealed: {results['l0_sealed']} at step {results['l0_seal_step']}")
print(f"L1 sealed: {results['l1_sealed']} at step {results['l1_seal_step']}")
print(f"N clusters: {results.get('n_clusters', 'N/A')}")
print('=== Test Complete ===')
