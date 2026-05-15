"""
exp_13_emergence.py — 涌现实验

运行长程演化 + 涌现探测器 + 对照实验。
这是核心实验：检测九公理约束下的演化是否涌现物理结构。

流程：
1. 运行4种条件（实验组 + 3个对照组）
2. 对每种条件计算6个统计量
3. 对比分析：哪些信号只在实验组出现
4. 输出报告
"""
import torch
import sys, os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layers.hamming_layer import HammingLattice, SourceSinkConfig
from engine.long_range_evolver import LongRangeEvolver
from engine.detectors.mutual_info import MutualInfoDetector
from engine.detectors.statistics import (
    HammingDistributionDetector,
    ReturnTimeDetector,
    BitClusteringDetector,
    DAGDirectionDetector,
    EffectiveDOFDetector,
)


def run_condition(name: str, N: int, total_steps: int,
                  use_axioms: bool, use_flux: bool,
                  sample_interval: int = 100,
                  device: str = "cpu") -> dict:
    """运行单一条件"""
    print(f"\n{'='*60}")
    print(f"Condition: {name}")
    print(f"  N={N}, T={total_steps}, axioms={use_axioms}, flux={use_flux}")
    print(f"{'='*60}")

    if use_flux:
        config = SourceSinkConfig(n_sources=2, n_sinks=2,
                                  source_strength=2, sink_strength=2,
                                  dynamic_position=use_axioms)
    else:
        config = SourceSinkConfig(n_sources=0, n_sinks=0,
                                  source_strength=0, sink_strength=0)

    layer = HammingLattice(N=N, device=device,
                           use_strict_axioms=use_axioms,
                           dag_enabled=use_axioms,
                           source_sink_config=config)

    evolver = LongRangeEvolver(layer, total_steps, sample_interval, device)
    result = evolver.run(verbose=True)

    # 探测器分析
    print(f"\n  Running detectors...")
    flip_seq = evolver.get_flip_sequence()
    weight_seq = evolver.get_hamming_weight_sequence()
    traj = evolver.get_trajectory_tensor()

    detectors = {
        'mutual_info': MutualInfoDetector(N),
        'hamming_dist': HammingDistributionDetector(N),
        'return_time': ReturnTimeDetector(N),
        'bit_cluster': BitClusteringDetector(N),
        'dag_dir': DAGDirectionDetector(N),
        'eff_dof': EffectiveDOFDetector(N),
    }

    analysis = {}
    print(f"  1/6 Mutual Information...")
    analysis['mutual_info'] = detectors['mutual_info'].compute(flip_seq)

    print(f"  2/6 Hamming Distribution...")
    analysis['hamming_dist'] = detectors['hamming_dist'].compute(weight_seq)

    print(f"  3/6 Return Time...")
    analysis['return_time'] = detectors['return_time'].compute(flip_seq)

    print(f"  4/6 Bit Clustering...")
    analysis['bit_cluster'] = detectors['bit_cluster'].compute(flip_seq)

    print(f"  5/6 DAG Direction...")
    if traj.shape[0] > 10:
        analysis['dag_dir'] = detectors['dag_dir'].compute(flip_seq, traj)
    else:
        analysis['dag_dir'] = {'error': 'no trajectory'}

    print(f"  6/6 Effective DOF...")
    if traj.shape[0] > 10:
        analysis['eff_dof'] = detectors['eff_dof'].compute(traj)
    else:
        analysis['eff_dof'] = {'error': 'no trajectory'}

    # 汇总信号
    signals = {}
    mi = analysis.get('mutual_info', {})
    signals['mi_decay'] = mi.get('decay_detected', False)

    hd = analysis.get('hamming_dist', {})
    signals['symmetry_breaking'] = hd.get('symmetry_breaking', False)
    signals['narrow_dist'] = hd.get('narrow_distribution', False)

    rt = analysis.get('return_time', {})
    signals['power_law'] = rt.get('power_law_like', False)

    bc = analysis.get('bit_cluster', {})
    signals['clustering'] = bc.get('significant_clusters', False)

    dd = analysis.get('dag_dir', {})
    signals['time_arrow'] = dd.get('time_arrow_detected', False)

    ed = analysis.get('eff_dof', {})
    signals['low_dimensional'] = ed.get('low_dimensional', False)

    n_signals = sum(1 for v in signals.values() if v)

    print(f"\n  Signals detected: {n_signals}/6")
    for k, v in signals.items():
        print(f"    {k}: {'YES' if v else 'no'}")

    return {
        'name': name,
        'config': {'N': N, 'total_steps': total_steps,
                    'use_axioms': use_axioms, 'use_flux': use_flux},
        'result': result,
        'analysis': analysis,
        'signals': signals,
        'n_signals': n_signals,
    }


def compare_results(all_results: list):
    """对比4种条件的结果"""
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    signal_names = ['mi_decay', 'symmetry_breaking', 'narrow_dist',
                    'power_law', 'clustering', 'time_arrow', 'low_dimensional']

    # 表头
    names = [r['name'] for r in all_results]
    print(f"\n  {'Signal':<25} | " + " | ".join(f"{n:>12}" for n in names))
    print(f"  {'-'*25}-+-" + "-+-".join("-"*12 for _ in names))

    for sig in signal_names:
        row = f"  {sig:<25} |"
        for r in all_results:
            val = r['signals'].get(sig, False)
            row += f" {'YES' if val else 'no':>12} |"
        print(row)

    # 独有信号分析
    print(f"\n  Unique signals (only in experimental):")
    exp_result = None
    for r in all_results:
        if r['name'] == 'Experimental':
            exp_result = r
            break

    if exp_result:
        for sig in signal_names:
            if exp_result['signals'].get(sig, False):
                # 检查其他条件是否有这个信号
                others_have = any(
                    r['signals'].get(sig, False)
                    for r in all_results if r['name'] != 'Experimental'
                )
                if not others_have:
                    print(f"    *** {sig} (UNIQUE to experimental)")
                else:
                    print(f"        {sig} (also in control)")


if __name__ == "__main__":
    torch.manual_seed(42)

    N = 16
    total_steps = 10000  # 先用10000步快速测试
    sample_interval = 100

    all_results = []

    # 条件1：实验组
    r1 = run_condition("Experimental", N, total_steps,
                       use_axioms=True, use_flux=True,
                       sample_interval=sample_interval)
    all_results.append(r1)

    # 条件2：无公理 + 通量
    r2 = run_condition("No Axioms", N, total_steps,
                       use_axioms=False, use_flux=True,
                       sample_interval=sample_interval)
    all_results.append(r2)

    # 条件3：公理 + 无通量
    r3 = run_condition("No Flux", N, total_steps,
                       use_axioms=True, use_flux=False,
                       sample_interval=sample_interval)
    all_results.append(r3)

    # 条件4：无公理 + 无通量
    r4 = run_condition("Random Closed", N, total_steps,
                       use_axioms=False, use_flux=False,
                       sample_interval=sample_interval)
    all_results.append(r4)

    # 对比
    compare_results(all_results)

    # 保存结果
    output_path = os.path.join(os.path.dirname(__file__),
                                'exp_13_results.json')
    serializable = []
    for r in all_results:
        sr = {
            'name': r['name'],
            'config': r['config'],
            'signals': r['signals'],
            'n_signals': r['n_signals'],
        }
        # 只保存可序列化的分析结果
        for k, v in r['analysis'].items():
            if isinstance(v, dict):
                sr[k] = {kk: vv for kk, vv in v.items()
                         if not isinstance(vv, torch.Tensor)}
        serializable.append(sr)

    with open(output_path, 'w') as f:
        json.dump(serializable, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")
