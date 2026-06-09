"""Quick debug test for exp_156 run_single"""
import sys, os, time
sys.path.insert(0, '.')
from experiments.exp_156_phase13_p2_L2_emergence import run_single

print('[test] Starting run_single(0)...')
t0 = time.time()
m = run_single(0)
elapsed = time.time() - t0
print(f'[test] Done in {elapsed:.2f}s')
print(f'[test] Result: sealed={m.get("sealed")}, seal_step={m.get("seal_step")}')
if m.get('sealed'):
    print(f'[test] H156-1 clustering_ratio={m.get("clustering_ratio"):.4f}')
    print(f'[test] H156-2 hw_var_ratio={m.get("hw_var_ratio"):.4f}')
    print(f'[test] H156-3 xi_ratio={m.get("xi_ratio"):.4f}')
