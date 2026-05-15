"""exp_16_binding_clustering.py - 绑定聚类实验"""
import torch, sys, os, json, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.long_range_evolver_v2 import LongRangeEvolverV2

torch.manual_seed(42)

N = 24
total_steps = 10000
sample_interval = 500

conditions = [
    ('Axioms',    True,  8),
    ('NoAxioms',  False, 24),  # 无公理时所有比特都是层级
]

all_results = []

for name, use_axioms, n_hierarchy in conditions:
    print(f'\n=== {name} ===')
    t0 = time.time()

    evolver = LongRangeEvolverV2(
        N=N, total_steps=total_steps,
        sample_interval=sample_interval,
        n_hierarchy_bits=n_hierarchy
    )

    if not use_axioms:
        evolver.constraints.direction = torch.zeros(N, dtype=torch.long)
        # 无公理时绑定强度不累积
        evolver.constraints.binding_strength = torch.zeros(N, N)

    result = evolver.run(verbose=False)

    clusters = result['clusters']
    binding = result['binding_strength']
    elapsed = time.time() - t0

    # 聚类统计
    n_clusters = len(clusters)
    max_cluster_size = max(len(c) for c in clusters) if clusters else 0
    avg_cluster_size = sum(len(c) for c in clusters) / n_clusters if clusters else 0
    cluster_coverage = sum(len(c) for c in clusters) / N if clusters else 0

    # 绑定强度统计
    triu_mask = torch.triu(torch.ones_like(binding), diagonal=1).bool()
    binding_vals = binding[triu_mask]

    all_results.append({
        'name': name,
        'elapsed_s': elapsed,
        'final_weight': result['final_state'].sum().item(),
        'cycles': result['cycle_states'],
        'n_clusters': n_clusters,
        'max_cluster_size': max_cluster_size,
        'avg_cluster_size': avg_cluster_size,
        'cluster_coverage': cluster_coverage,
        'binding_mean': binding_vals.mean().item(),
        'binding_max': binding_vals.max().item(),
        'binding_std': binding_vals.std().item(),
        'clusters': clusters,
    })

    print(f'  {elapsed:.1f}s')
    print(f'  Weight: {result["final_state"].sum().item()}')
    print(f'  Cycles: {result["cycle_states"]}')
    print(f'  Clusters: {n_clusters} (max={max_cluster_size}, coverage={cluster_coverage:.2f})')
    print(f'  Binding: mean={binding_vals.mean():.2f}, max={binding_vals.max():.2f}')

# 对比
print('\n=== COMPARISON ===')
a = all_results[0]
n = all_results[1]
print(f'Clusters: {a["n_clusters"]} vs {n["n_clusters"]}')
print(f'Max cluster: {a["max_cluster_size"]} vs {n["max_cluster_size"]}')
print(f'Coverage: {a["cluster_coverage"]:.2f} vs {n["cluster_coverage"]:.2f}')
print(f'Binding max: {a["binding_max"]:.2f} vs {n["binding_max"]:.2f}')
print(f'Binding std: {a["binding_std"]:.2f} vs {n["binding_std"]:.2f}')

output_path = os.path.join(os.path.dirname(__file__), 'exp_16_results.json')
with open(output_path, 'w') as f:
    json.dump(all_results, f, indent=2, default=str)
print(f'\nSaved to {output_path}')
