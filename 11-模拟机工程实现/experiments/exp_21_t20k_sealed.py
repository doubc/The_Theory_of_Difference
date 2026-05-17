"""exp_21_t20k_sealed.py - T=20000 实验，观察 A9 封口"""
import torch, sys, os, json, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.long_range_evolver_v2 import LongRangeEvolverV2

torch.manual_seed(42)

N = 48
total_steps = 20000
sample_interval = 1000

evolver = LongRangeEvolverV2(
    N=N, total_steps=total_steps,
    sample_interval=sample_interval,
    n_hierarchy_bits=N // 3
)

result = evolver.run(verbose=True)
c = evolver.constraints

print('\n' + '='*60)
print('A5 Conservation')
print('='*60)
# 使用 record_inject/record_absorb 的实际计数
inj = result.get('total_injected', evolver.constraints.total_injected)
abso = result.get('total_absorbed', evolver.constraints.total_absorbed)
print(f'Inject: {inj}, Absorb: {abso}, Net: {inj-abso}')
print(f'Ratio: {abso/max(inj,1):.2f}x')

print('\n' + '='*60)
print('A7 Cycle')
print('='*60)
print(f'Cycle states: {result["cycle_states"]}')
print(f'Visited states: {len(c.visited_states)}')
print(f'Cycle ratio: {result["cycle_states"]/max(len(c.visited_states),1):.4f}')

print('\n' + '='*60)
print('A9 Freedom Seal')
print('='*60)
print(f'Sealed: {result["sealed"]}')
print(f'Sealed bits: {result["sealed_bits"]}/{N}')
print(f'Sealed ratio: {result["sealed_ratio"]:.2f}')
print(f'Active bits: {result["active_bits"]}/{N}')

if result['sealed']:
    print(f'\nSealed bit indices: {sorted(c.sealed_bits)}')
    print(f'Remaining active: {sorted(c.active_bits - c.sealed_bits)}')

print('\n' + '='*60)
print('DAG')
print('='*60)
d = result['direction']
print(f'+1: {(d>0).sum().item()}, -1: {(d<0).sum().item()}, 0: {(d==0).sum().item()}')

print('\n' + '='*60)
print('Clusters')
print('='*60)
clusters = result['clusters']
print(f'Number of clusters: {len(clusters)}')
for i, cl in enumerate(clusters):
    print(f'  Cluster {i+1}: {cl} (size={len(cl)})')

# 保存结果
output = {
    'N': N,
    'total_steps': total_steps,
    'A5_inject': inj,
    'A5_absorb': abso,
    'A5_net': inj - abso,
    'A7_cycles': result['cycle_states'],
    'A7_visited': len(c.visited_states),
    'A9_sealed': result['sealed'],
    'A9_sealed_bits': result['sealed_bits'],
    'A9_sealed_ratio': result['sealed_ratio'],
    'DAG_pos': (d>0).sum().item(),
    'DAG_neg': (d<0).sum().item(),
    'DAG_zero': (d==0).sum().item(),
    'n_clusters': len(clusters),
    'max_cluster_size': max(len(cl) for cl in clusters) if clusters else 0,
    'clusters': clusters,
}

output_path = os.path.join(os.path.dirname(__file__), 'exp_21_results.json')
with open(output_path, 'w') as f:
    json.dump(output, f, indent=2, default=str)
print(f'\nSaved to {output_path}')
