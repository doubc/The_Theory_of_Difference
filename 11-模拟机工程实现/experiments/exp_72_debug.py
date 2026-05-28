"""Quick debug: check what keys are in phase2_step_results"""
import sys, os, json
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch, numpy as np
from engine.hierarchical_evolver import HierarchicalEvolver
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence

torch.manual_seed(42)
np.random.seed(42)

psc = PreSubjectivityConvergence(coupling_threshold=0.30, coupling_mode="functional")
evolver = HierarchicalEvolver(
    N0=72, steps_per_layer=200, sample_interval=50, max_layers=1,
    p1_eval_interval=50,
    persistent_bias_memory=PersistentBiasMemory(),
    cumulative_selector=CumulativeSelector(),
    six_threshold_detector=SixThresholdDetector(),
    pre_subjectivity_convergence=psc,
    phase2_verbose=True,
)

run_result = evolver.run()
layer_results = run_result.get("layer_results", [])

for lr in layer_results:
    step_results = lr.get("phase2_step_results", [])
    print(f"Total phase2_step_results: {len(step_results)}")
    if step_results:
        print(f"Keys in first entry: {list(step_results[0].keys())}")
        # Check a few entries for functional_signals
        for sr in step_results[:5]:
            fs = sr.get("functional_signals")
            conv = sr.get("convergence", {})
            print(f"  step={sr.get('step')}: has_fs={fs is not None}, conv={conv}")
        # Check last few
        print("  ...")
        for sr in step_results[-3:]:
            fs = sr.get("functional_signals")
            conv = sr.get("convergence", {})
            print(f"  step={sr.get('step')}: has_fs={fs is not None}, conv={conv}")
