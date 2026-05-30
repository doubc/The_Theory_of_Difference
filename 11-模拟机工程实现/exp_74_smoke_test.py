"""exp_74 smoke test - short run to verify P0 fixes have effect"""
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np
import time
from datetime import datetime

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.minimal_self_detector import MinimalSelfDetector
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from models.narrative_self import NarrativeRecursionOperator

print("=" * 60)
print("exp_74 SMOKE TEST - P0 Fix Effect Verification")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

N0 = 72
steps = 200
sample_interval = 5
p1_eval_interval = 5

# MSI config (same as exp_74 B_low_threshold)
msi_config = {
    'odi_activation_threshold': 0.35,
    'odi_saturation_threshold': 0.70,
    'asymmetry_window': 10,
    'asymmetry_threshold': 0.25,
    'min_parts': 3,
    'history_window': 8,
    'history_dependency_threshold': 0.3,
    'min_history_depth': 5,
    'self_reference_window': 8,
    'self_reference_threshold': 0.2,
    'baseline_correlation_threshold': 0.4,
    'msi_activation_threshold': 0.20,
    'msi_emergence_threshold': 0.35,
    'min_active_conditions': 1,
}

torch.manual_seed(42)
np.random.seed(42)

narrative_op = NarrativeRecursionOperator(
    bias_dimension=72,
    filter_magnitude_threshold=0.05,
    connector_strength_threshold=0.2,
    verifier_consistency_threshold=0.4,
    narrative_decay_rate=0.9,
)

mini_detector = MinimalSelfDetector(config=msi_config)
anticipatory_engine = AnticipatoryBiasEngine(
    memory=PersistentBiasMemory(),
    config={'default_horizon': 5, 'learning_rate': 0.01},
)
counterfactual_engine = CounterfactualEngine(config=None)

evolver = HierarchicalEvolver(
    N0=N0,
    steps_per_layer=steps,
    sample_interval=sample_interval,
    max_layers=1,
    p1_eval_interval=p1_eval_interval,
    persistent_bias_memory=PersistentBiasMemory(),
    cumulative_selector=CumulativeSelector(window_size=20),
    minimal_self_detector=mini_detector,
    anticipatory_bias_engine=anticipatory_engine,
    counterfactual_engine=counterfactual_engine,
    narrative_recursion_operator=narrative_op,
    organizational_density_index=OrganizationalDensityIndex(),
    phase3_verbose=False,
)

print(f"\nRunning {steps} steps (N={N0})...")
start = time.time()
evolver_result = evolver.run()
elapsed = time.time() - start
print(f"Completed in {elapsed:.1f}s")

# Extract data
phase2 = evolver_result.get('layer_results', [{}])[0].get('phase2_step_results', [])
odi_values = [r.get('odi', {}).get('value', 0) for r in phase2]
msi_values = [r.get('minimal_self', {}).get('msi', 0) for r in phase2]
p3_active = [r.get('p3_active', False) for r in phase2]

odi_mean = np.mean(odi_values) if odi_values else 0
odi_max = np.max(odi_values) if odi_values else 0
msi_mean = np.mean(msi_values) if msi_values else 0
msi_max = np.max(msi_values) if msi_values else 0
msi_positive = sum(1 for v in msi_values if v > 0)
p3_count = sum(p3_active)

print(f"\n--- Results (N={N0}, steps={steps}) ---")
print(f"ODI:  mean={odi_mean:.4f}, max={odi_max:.4f}")
print(f"MSI:  mean={msi_mean:.4f}, max={msi_max:.4f}")
print(f"MSI>0 steps: {msi_positive}/{len(msi_values)} ({msi_positive/len(msi_values)*100:.1f}%)")
print(f"Phase 3 active: {p3_count}/{len(phase2)}")

# ODI subindex diagnostics
layer0 = evolver_result.get('layer_results', [{}])[0]
odi_sub = layer0.get('odi', {}).get('subindices', {})
if odi_sub:
    print(f"\nODI Sub-indices (final):")
    for k, v in odi_sub.items():
        print(f"  {k}: {v:.4f}")

print(f"\n--- Comparison vs Pre-Fix Baseline ---")
print(f"ODI mean: {odi_mean:.4f} (baseline ~0.10) -> {'IMPROVED' if odi_mean > 0.12 else 'NEEDS MORE STEPS'}")
print(f"MSI max:  {msi_max:.4f} (baseline 0.00) -> {'ACTIVATED' if msi_max > 0.01 else 'STILL LOW'}")
print(f"MSI>0:    {msi_positive/len(msi_values)*100:.1f}% (baseline 0%)")

effect = 'POSITIVE' if (odi_mean > 0.12 or msi_max > 0.01) else 'NEEDS_MORE_STEPS'
print(f"\n[P0 FIX EFFECT: {effect}]")
