"""
exp_153 — Phase 12 P1: 单空间聚簇时序实验

目标：
  1. 密封顺序：bits 密封是否有结构性的先后顺序？
  2. 凝聚速度：从第一个 sealed bit 到最后一个，过程中是否有爆发期（cascade）？
  3. 预密封活动：bits 在密封前是否有可观测的"趋近"行为？
  4. Cascade 分布：cascade size 服从什么分布？

设计：
  - N0=48（>> N0*≈30.5，确保 L1 形成）
  - k=1（单子空间，聚焦聚簇本身）
  - 50 runs for statistics
  - 记录每步状态，事后分析 seal_order、cascade、预密封活动

用法：
  python experiments/exp_153_phase12_p1_temporal_clustering.py
"""

import sys, os, json, datetime
import numpy as np
import torch

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observations.temporal_trace import TemporalTrace


# ============================================================
# 参数
# ============================================================
N = 48
N_RUNS = 50
TOTAL_STEPS = 1000  # N=48 should seal well within 1000 steps
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)


# ============================================================
# 单次运行
# ============================================================
def run_single(run_id: int) -> dict:
    """运行单次实验并提取时序指标"""
    # 随机初始状态（少量 ones 触发演化）
    torch.manual_seed(run_id * 137 + 42)
    initial = torch.zeros(N)
    n_ones = torch.randint(4, 12, (1,)).item()
    indices = torch.randperm(N)[:n_ones]
    initial[indices] = 1.0

    trace = TemporalTrace(
        N=N,
        sample_interval=1,
        total_steps=TOTAL_STEPS,
        verbose=False,
    )

    result = trace.run(initial_state=initial, verbose=False)

    # 提取时序指标
    summary = trace.get_summary()
    seal_order = trace.get_seal_order()
    step_map = trace.get_seal_step_map()
    cascade = trace.get_cascade_series()
    convergence = trace.get_convergence_trace()
    pre_seal = trace.get_pre_seal_activity(lookback=30)

    metrics = {
        'run_id': run_id,
        'n_initial_ones': n_ones,
        'sealed': trace.sealed,
        'seal_step': trace.seal_step,
        'n_sealed_bits': len(trace._seal_step_per_bit),
        'total_steps_taken': len(trace.history),
        'n_cascade_events': summary['cascade_events'],
        'max_cascade_size': summary['max_cascade_size'],
        'mean_cascade_size': summary['mean_cascade_size'],
        'final_weight': summary['final_weight'],
        'weight_range': summary['weight_range'],
        'seal_order': seal_order,
        'seal_step_map': {str(k): v for k, v in step_map.items()},
        'cascade_series': cascade,
        'convergence_series': convergence.tolist(),
    }

    return metrics


# ============================================================
# 批量运行
# ============================================================
def run_batch():
    """运行批量实验"""
    all_metrics = []
    sealed_metrics = []

    print(f"Phase 12 P1: 单空间聚簇时序 (exp_153)")
    print(f"  N={N}, N_RUNS={N_RUNS}, TOTAL_STEPS={TOTAL_STEPS}")
    print(f"  Sealing threshold: max(0.75*{N}, 30) = {max(int(0.75*N), 30)}")
    print("=" * 60)

    for run_id in range(N_RUNS):
        metrics = run_single(run_id)
        all_metrics.append(metrics)

        status = f"[{'Y' if metrics['sealed'] else 'N'}] run {run_id:3d}: "
        if metrics['sealed']:
            status += f"seal_step={metrics['seal_step']:4d}, "
            status += f"n_sealed={metrics['n_sealed_bits']:2d}, "
            status += f"cascade_max={metrics['max_cascade_size']:2d}"
            sealed_metrics.append(metrics)
        else:
            status += f"NOT SEALED (final_w={metrics['final_weight']:2d})"

        if run_id % 10 == 9 or run_id == N_RUNS - 1:
            print(status)

    # ============================================================
    # 分析
    # ============================================================
    n_sealed = len(sealed_metrics)

    print(f"\n{'=' * 60}")
    print(f"结果分析")
    print(f"{'=' * 60}")
    print(f"密封率: {n_sealed}/{N_RUNS} ({100*n_sealed/N_RUNS:.1f}%)")

    if n_sealed > 0:
        seal_steps = [m['seal_step'] for m in sealed_metrics]
        cascade_maxes = [m['max_cascade_size'] for m in sealed_metrics]
        cascade_events = [m['n_cascade_events'] for m in sealed_metrics]

        print(f"\n-- 密封时序 --")
        print(f"  平均密封步: {np.mean(seal_steps):.1f} ± {np.std(seal_steps):.1f}")
        print(f"  密封步范围: [{min(seal_steps)}, {max(seal_steps)}]")

        print(f"\n-- Cascade 分析 --")
        print(f"  平均 max cascade: {np.mean(cascade_maxes):.1f} ± {np.std(cascade_maxes):.1f}")
        print(f"  平均 cascade events: {np.mean(cascade_events):.1f} ± {np.std(cascade_events):.1f}")

        # 合并所有 cascade 分布
        all_cascade_sizes = []
        for m in sealed_metrics:
            all_cascade_sizes.extend(m['cascade_series'])
        all_cascade_sizes = np.array(all_cascade_sizes)
        non_zero = all_cascade_sizes[all_cascade_sizes > 0]
        print(f"\n  总 cascade 事件: {len(non_zero)}")
        print(f"  Cascade size 分布:")
        if len(non_zero) > 0:
            for size in sorted(set(non_zero)):
                count = (non_zero == size).sum()
                print(f"    size={size}: {count} events ({100*count/len(non_zero):.1f}%)")

        # 权重收敛
        final_weights = [m['final_weight'] for m in sealed_metrics]
        print(f"\n-- 权重收敛 --")
        print(f"  平均最终权重: {np.mean(final_weights):.1f}")

    # ============================================================
    # 保存结果
    # ============================================================
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"exp153_phase12_p1_{timestamp}.npz")

    # 只保存可序列化的摘要
    save_data = {
        'params': {
            'N': N,
            'n_runs': N_RUNS,
            'total_steps': TOTAL_STEPS,
            'sealing_threshold': max(int(0.75*N), 30),
            'timestamp': timestamp,
        },
        'summary': {
            'n_sealed': n_sealed,
            'mean_seal_step': float(np.mean(seal_steps)) if n_sealed > 0 else None,
            'std_seal_step': float(np.std(seal_steps)) if n_sealed > 0 else None,
            'mean_max_cascade': float(np.mean(cascade_maxes)) if n_sealed > 0 else None,
            'mean_cascade_events': float(np.mean(cascade_events)) if n_sealed > 0 else None,
        },
        'metrics': all_metrics,
    }

    import json
    with open(result_file.replace('.npz', '.json'), 'w') as f:
        json.dump(save_data, f, indent=2, default=str)

    print(f"\n结果保存至: {result_file.replace('.npz', '.json')}")
    return save_data


if __name__ == '__main__':
    run_batch()
