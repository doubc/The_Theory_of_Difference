"""Deep diagnostic: check MSD internal state."""
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np
from engine.minimal_self_detector import MinimalSelfDetector
from engine.organizational_density_index import OrganizationalDensityIndex

msd = MinimalSelfDetector()
odi = OrganizationalDensityIndex()

# Simulate 20 feed cycles with realistic data
np.random.seed(42)
for i in range(20):
    # Sensitivity map: 18 active bits with direction values
    # Scenario A: uniform directions (low asymmetry)
    sensitivity_uniform = {f"bit_{j}": 0.5 + np.random.normal(0, 0.05) for j in range(18)}
    # Scenario B: non-uniform directions (high asymmetry)
    sensitivity_skewed = {f"bit_{j}": np.random.exponential(0.3) for j in range(18)}

    # Response history: bias memory entries
    response_history = {
        f"t{i}_{k}": [float(np.random.normal(0.5, 0.1))] for k in range(3)
    }

    # Compute ODI
    from engine.six_threshold_detector import SixThresholdResult
    tr = SixThresholdResult(n_met=5, all_met=False, bottleneck="3.5")
    import torch as th
    coupling = {}
    for ma in ['interface_regulation', 'self_sustaining', 'retention', 'replication', 'selection', 'functional_differentiation']:
        coupling[ma] = {}
        for mb in ['interface_regulation', 'self_sustaining', 'retention', 'replication', 'selection', 'functional_differentiation']:
            coupling[ma][mb] = float(np.random.uniform(0.3, 0.7))
    odi_result = odi.compute(
        threshold_result=tr,
        coupling_matrix=coupling,
        stability_score=0.6,
        timestamp=i,
    )

    # Feed with uniform sensitivity
    result_u = msd.feed(
        sensitivity_map=sensitivity_uniform,
        response_history=response_history,
        baseline_shift=float(np.random.normal(0, 0.1)),
        odi_result=odi_result,
        timestamp=i,
    )

    print(f"Step {i}: ODI={odi_result.odi:.3f}, "
          f"MSI={result_u.msi:.4f}, "
          f"detected={result_u.minimal_self_detected}, "
          f"n_cond={result_u.n_active_conditions}, "
          f"asym={result_u.asymmetry_index:.4f}, "
          f"hist={result_u.history_dependency_index:.4f}, "
          f"self={result_u.self_reference_index:.4f}")

print("\n--- Now with skewed sensitivity ---")
msd2 = MinimalSelfDetector()
odi2 = OrganizationalDensityIndex()
for i in range(20):
    sensitivity_skewed = {f"bit_{j}": np.random.exponential(0.3) for j in range(18)}
    response_history = {
        f"t{i}_{k}": [float(np.random.normal(0.5, 0.1))] for k in range(3)
    }
    tr = SixThresholdResult(n_met=5, all_met=False, bottleneck="3.5")
    coupling = {}
    for ma in ['interface_regulation', 'self_sustaining', 'retention', 'replication', 'selection', 'functional_differentiation']:
        coupling[ma] = {}
        for mb in ['interface_regulation', 'self_sustaining', 'retention', 'replication', 'selection', 'functional_differentiation']:
            coupling[ma][mb] = float(np.random.uniform(0.3, 0.7))
    odi_result = odi2.compute(
        threshold_result=tr,
        coupling_matrix=coupling,
        stability_score=0.6,
        timestamp=i,
    )
    result_s = msd2.feed(
        sensitivity_map=sensitivity_skewed,
        response_history=response_history,
        baseline_shift=float(np.random.normal(0, 0.1)),
        odi_result=odi_result,
        timestamp=i,
    )
    print(f"Step {i}: ODI={odi_result.odi:.3f}, "
          f"MSI={result_s.msi:.4f}, "
          f"detected={result_s.minimal_self_detected}, "
          f"n_cond={result_s.n_active_conditions}, "
          f"asym={result_s.asymmetry_index:.4f}, "
          f"hist={result_s.history_dependency_index:.4f}, "
          f"self={result_s.self_reference_index:.4f}")
