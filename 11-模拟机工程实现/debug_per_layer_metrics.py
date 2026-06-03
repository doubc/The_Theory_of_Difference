#!/usr/bin/env python3
"""Quick debug: test PerLayerMetricsCollector integration with HierarchicalEvolver."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
from engine.hierarchical_evolver import HierarchicalEvolver
from engine.per_layer_metrics import PerLayerMetricsCollector, DEFAULT_PER_LAYER_METRICS_CONFIG

seed = 42
np.random.seed(seed)
torch.random.manual_seed(seed)

N0 = 48
total_steps = 500  # Short run for debugging

evolver = HierarchicalEvolver(
    N0=N0,
    steps_per_layer=total_steps,
    sample_interval=10,
    max_layers=3,
    device="cpu",
)

# Configure A9
constraints = evolver.hierarchy.layers[0].constraints
constraints.min_active_bits = N0 // 3
constraints.binding_threshold = 0.05

# Per-layer metrics collector
plm_config = DEFAULT_PER_LAYER_METRICS_CONFIG.copy()
collector = PerLayerMetricsCollector(plm_config)

# Run
result = evolver.run(verbose=True, tracking_callback=collector.step)

print(f"\n=== STATUS ===")
print(f"Layers: {evolver.hierarchy.n_layers}")
print(f"L0 sealed: {result['layer_results'][0]['sealed'] if len(result['layer_results']) >= 1 else 'N/A'}")
print(f"L1 formed: {len(result['layer_results']) >= 2}")
print(f"Snapshots: {len(result.get('snapshots', []))}")

# Check collector internal state
print(f"\n=== COLLECTOR STATE ===")
print(f"_l0_seal_step: {collector._l0_seal_step}")
print(f"_l1_formed_step: {collector._l1_formed_step}")
print(f"global_odi samples: {len(collector._global_odi_history)}")
print(f"global_msi samples: {len(collector._global_msi_history)}")

# Check per-layer trackers
for name in ['L0', 'L1']:
    if name in collector._nsi_trackers:
        tracker = collector._nsi_trackers[name]
        hist = tracker.get_nsi_history()
        print(f"\n{name} NSI history: {len(hist)} points")
        if hist:
            vals = [v for _, v in hist]
            print(f"  Unique values: {len(set(round(v,6) for v in vals))}")
            print(f"  Range: {min(vals):.6f} - {max(vals):.6f}")
            print(f"  Mean: {np.mean(vals):.6f}")
            print(f"  First 5: {vals[:5]}")
            print(f"  Last 5: {vals[-5:]}")
    if name in collector._civ_trackers:
        tracker = collector._civ_trackers[name]
        ham = tracker.get_hamming_history()
        print(f"{name} CIV history: {len(ham)} points")
        if ham:
            print(f"  Unique values: {len(set(ham))}")
            print(f"  Range: {min(ham)} - {max(ham)}")
    if name in collector._theme_trackers:
        tracker = collector._theme_trackers[name]
        themes = tracker._theme_history
        print(f"{name} theme history: {len(themes)}")

# Analyze
analysis = collector.analyze(post_seal_only=True)
print(f"\n=== ANALYSIS ===")
print(f"H46 (NSI autonomy): mean_corr={analysis['h46'].mean_corr:.4f}, passing={analysis['h46'].passing}")
print(f"H47 (CIV independence): mean_corr={analysis['h47'].mean_corr:.4f}")
print(f"H48 (L1 sealing): mean_ratio={analysis['h48'].mean_ratio:.4f}")
print(f"H49 (theme divergence): mean_jaccard={analysis['h49'].mean_jaccard:.4f}")

# Check H46 raw data
l0_nsi = collector._nsi_trackers['L0']
l1_nsi = collector._nsi_trackers['L1']
l0_raw = l0_nsi.get_nsi_history()
l1_raw = l1_nsi.get_nsi_history()
print(f"\n=== RAW NSI SERIES (first 10) ===")
print("L0:", [(s, round(v,4)) for s, v in l0_raw[:10]])
print("L1:", [(s, round(v,4)) for s, v in l1_raw[:10]])
print("L0 (last 10):", [(s, round(v,4)) for s, v in l0_raw[-10:]])
print("L1 (last 10):", [(s, round(v,4)) for s, v in l1_raw[-10:]])
