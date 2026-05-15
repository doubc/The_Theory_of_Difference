"""exp_14_emergence_v2.py - 涌现实验 v2（新公理约束）"""
import torch
import sys, os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.long_range_evolver_v2 import LongRangeEvolverV2
from engine.detectors.mutual_info import MutualInfoDetector
from engine.detectors.statistics import (
    HammingDistributionDetector,
    ReturnTimeDetector,
    BitClusteringDetector,
    DAGDirectionDetector,
    EffectiveDOFDetector,
)

torch.manual_seed(42)

N = 24
total_steps = 20000
sample_interval = 200
n_hierarchy = 8  # 层级比特数

conditions = [
    ('Experimental',  True),
    ('No Axioms',     False),
]

all_results = []

for name, use_axioms in conditions:
    print('\n' + '='*60)
    print(f'Condition: {name}')
    print('='*60)

    t0 = time.time()

    nh = n_hierarchy if use_axioms else N  # 无公理时所有比特都是层级
    evolver = LongRangeEvolverV2(
        N=N, total_steps=total_steps,
        sample_interval=sample_interval,
        n_hierarchy_bits=nh
    )

    # 无公理时关闭 DAG 约束
    if not use_axioms:
        evolver.constraints.direction = torch.zeros(N, dtype=torch.long)  # 允许双向

    result = evolver.run(verbose=True)

    flip_seq = evolver.get_flip_sequence()
    weight_seq = evolver.get_hamming_weight_sequence()
    traj = evolver.get_trajectory_tensor()

    print('  Running detectors...')
    mi_r = MutualInfoDetector(N).compute(flip_seq)
    hd_r = HammingDistributionDetector(N).compute(weight_seq)
    rt_r = ReturnTimeDetector(N).compute(flip_seq)
    bc_r = BitClusteringDetector(N).compute(flip_seq)
    dd_r = DAGDirectionDetector(N).compute(flip_seq, traj) if traj.shape[0] > 10 else {}
    ed_r = EffectiveDOFDetector(N).compute(traj) if traj.shape[0] > 10 else {}

    signals = {
        'mi_decay': mi_r.get('decay_detected', False),
        'symmetry_breaking': hd_r.get('symmetry_breaking', False),
        'narrow_dist': hd_r.get('narrow_distribution', False),
        'power_law': rt_r.get('power_law_like', False),
        'clustering': bc_r.get('significant_clusters', False),
        'time_arrow': dd_r.get('time_arrow_detected', False),
        'low_dimensional': ed_r.get('low_dimensional', False),
    }
    n_signals = sum(1 for v in signals.values() if v)
    elapsed = time.time() - t0

    print(f'  Done in {elapsed:.1f}s. Signals: {n_signals}/7')
    for k, v in signals.items():
        print(f'    {k}: {"YES" if v else "no"}')

    all_results.append({
        'name': name,
        'config': {'N': N, 'total_steps': total_steps, 'use_axioms': use_axioms},
        'signals': signals, 'n_signals': n_signals, 'elapsed_s': elapsed,
        'mi_mean': mi_r.get('mean_mi', 0),
        'mi_decay_slope': mi_r.get('decay_slope', 0),
        'hd_mean': hd_r.get('mean', 0), 'hd_std': hd_r.get('std', 0),
        'hd_peak_ratio': hd_r.get('peak_ratio', 0),
        'rt_mean': rt_r.get('mean_return_time', 0),
        'rt_power_law_slope': rt_r.get('power_law_slope', 0),
        'bc_n_clusters': bc_r.get('n_clusters', 0),
        'bc_max_cluster': bc_r.get('max_cluster_size', 0),
        'bc_cluster_ratio': bc_r.get('cluster_ratio', 0),
        'dd_avg_consistency': dd_r.get('avg_consistency', 0),
        'ed_n_dof_90': ed_r.get('n_dof_90', 0),
        'ed_compression': ed_r.get('compression_ratio', 0),
        'cycle_states': result['cycle_states'],
        'active_bits': result['active_bits'],
        'final_weight': result['final_state'].sum().item(),
        'total_inject': sum(result['inject_history']),
        'total_absorb': sum(result['absorb_history']),
        'direction_pos': (result['direction'] > 0).sum().item(),
        'direction_neg': (result['direction'] < 0).sum().item(),
        'direction_zero': (result['direction'] == 0).sum().item(),
    })

# 对比
print('\n' + '='*60)
print('COMPARISON')
print('='*60)

signal_names = ['mi_decay', 'symmetry_breaking', 'narrow_dist',
                'power_law', 'clustering', 'time_arrow', 'low_dimensional']

for sig in signal_names:
    row = f"  {sig:<25}"
    for r in all_results:
        val = r['signals'].get(sig, False)
        row += f"{'YES' if val else 'no':>16}"
    print(row)

print('\n=== Numerical Comparison ===')
for r in all_results:
    print(f"\n{r['name']} ({r['elapsed_s']:.1f}s):")
    print(f"  Final weight: {r['final_weight']}")
    print(f"  Cycles: {r['cycle_states']}, Active bits: {r['active_bits']}")
    print(f"  Inject: {r['total_inject']}, Absorb: {r['total_absorb']}, Net: {r['total_inject'] - r['total_absorb']}")
    print(f"  Direction: +{r['direction_pos']}/-{r['direction_neg']}/0{r['direction_zero']}")
    print(f"  MI mean={r['mi_mean']:.6f}, decay_slope={r['mi_decay_slope']:.4f}")
    print(f"  HD mean={r['hd_mean']:.2f}, std={r['hd_std']:.2f}, peak_ratio={r['hd_peak_ratio']:.2f}")
    print(f"  RT mean={r['rt_mean']:.1f}, power_law_slope={r['rt_power_law_slope']:.3f}")
    print(f"  BC clusters={r['bc_n_clusters']}, max={r['bc_max_cluster']}, ratio={r['bc_cluster_ratio']:.3f}")
    print(f"  DD consistency={r['dd_avg_consistency']:.3f}")
    print(f"  EDOF n_dof_90={r['ed_n_dof_90']}, compression={r['ed_compression']:.3f}")

output_path = os.path.join(os.path.dirname(__file__), 'exp_14_results.json')
with open(output_path, 'w') as f:
    json.dump(all_results, f, indent=2, default=str)
print(f'\nResults saved to {output_path}')
