"""Quick diagnostic: test N0=100, 300 with self_ref=False/True"""
import sys
import os
base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base)
sys.path.insert(0, os.path.join(base, '..'))
from diffsim.world_v2 import RecursiveWorld, Params
from diffsim.entropy import EntropyConfig

for N0 in [48, 100, 300]:
    for self_ref in [False, True]:
        try:
            cfg = dict(
                N0=N0, params=Params(max_steps=400),
                entropy_cfg=EntropyConfig(use_memory=False),
                seed=42, self_encapsulate=self_ref,
            )
            world = RecursiveWorld(**cfg)
            result = world.run(max_layers=12, verbose=False)
            print(f'N0={N0}, self_ref={self_ref}: depth={result["depth"]}, n_layers={result["n_layers"]}')
        except Exception as e:
            print(f'N0={N0}, self_ref={self_ref}: ERROR {type(e).__name__}: {e}')
            import traceback; traceback.print_exc()