"""Quick check: does N=36 seal at 5000 steps with default params?"""
import sys, os, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch, numpy as np
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver

torch.manual_seed(42); np.random.seed(42)
evo = SpatialLongRangeEvolver(N=36, total_steps=5000, sample_interval=500)
t0 = time.time()
result = evo.run(verbose=False)
elapsed = time.time() - t0
print(f"N=36, 5000 steps: sealed={result.get('sealed', False)}, "
      f"sealed_ratio={result.get('sealed_ratio', 0):.3f}, "
      f"hw={result['hamming_weight_history'][-1]}, "
      f"t={elapsed:.1f}s")