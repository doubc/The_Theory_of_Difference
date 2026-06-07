"""
exp_154 — Phase 12 P2: N-sweep around phase boundary

目标：
  1. 确定相变点 N0* 的精确位置（通过密封率从 0→1 的转变）
  2. 测量 cascade 大小随 N 的标度关系（cascade_size ~ N^α？）
  3. 接近相变点是否出现"临界涨落"（cascade size 方差增大、密封时间分散）
  4. 单次 cascade 事件的性质是否在所有 N 下成立？

核心假设（来自 exp_153 的发现）：
  - N=48 时 cascade 是单次事件（48/49 runs），size≈19≈40%的 N
  - 这是否是普遍规律？cascade 是否始终是单次且 size 与 N 成比例？
  - 接近 N0* 时，是否出现多次 cascade 事件？

设计：
  - N ∈ [24, 28, 30, 32, 34, 36, 40, 48, 56, 64, 80, 96]
  - runs per N: 30（远点 N 可减少到 20，近相变 N 保持 30）
  - 记录：密封率、密封步、cascade 大小、cascade 事件数、bit 角色统计

用法：
  python experiments/exp_154_phase12_p2_n_sweep.py
"""

import sys, os, json, datetime, time
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observations.temporal_trace import TemporalTrace


# ============================================================
# 参数
# ============================================================
# N 值列表：跨越相变点 N0*≈30.5
# 近相变区密集采样，远点稀疏采样
# 仅使用 3 的倍数（SpatialLongRangeEvolver 自动对齐到 3 倍数，
# 但 initial_state 不会自动 resize，导致 index out of bounds）
N_VALUES = [24, 30, 36, 42, 48, 54, 60, 72, 84, 96]

# runs per N: 远点可少跑，近相变点多跑
BASE_RUNS = 5
EXTRA_RUNS = {24: 10, 30: 12, 36: 10, 48: 8}  # 近相变更多 runs

TOTAL_STEPS = 5000
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')


# ============================================================
# 辅助函数
# ============================================================
def get_n_runs(N: int) -> int:
    """根据 N 返回需要的运行次数"""
    if N in EXTRA_RUNS:
        return EXTRA_RUNS[N]
    return BASE_RUNS


def run_single(N: int, run_id: int) -> dict:
    """单次 N 参数下的实验运行"""
    torch.manual_seed(run_id * 137 + 42 + N)

    # 随机初始状态
    initial = torch.zeros(N)
    n_ones = max(3, torch.randint(4, min(12, N//2) + 1, (1,)).item())
    indices = torch.randperm(N)[:n_ones]
    initial[indices] = 1.0

    trace = TemporalTrace(
        N=N,
        sample_interval=1,
        total_steps=TOTAL_STEPS,
        verbose=False,
    )

    result = trace.run(initial_state=initial, verbose=False)

    summary = trace.get_summary()
    seal_order = trace.get_seal_order()
    cascade = trace.get_cascade_series()
    step_map = trace.get_seal_step_map()

    # 计算冻结 bit 分布（bit 被冻结的比例）
    n_sealed = len(step_map)
    seal_fraction = n_sealed / N if N > 0 else 0

    # 检测 cascade 模式
    cascade_sizes = [c for c in cascade if c > 0]
    n_cascade_events = sum(1 for c in cascade if c > 1)

    # 密封持续时间（从第 1 个到最后一个冻结的步数）
    if seal_order:
        first_step = min(step_map.values())
        last_step = max(step_map.values())
        seal_duration = last_step - first_step
    else:
        seal_duration = 0

    metrics = {
        'N': N,
        'run_id': run_id,
        'n_initial_ones': n_ones,
        'sealed': trace.sealed,
        'seal_step': trace.seal_step,
        'n_sealed_bits': n_sealed,
        'seal_fraction': seal_fraction,
        'total_steps_taken': len(trace.history),
        'n_cascade_events': summary['cascade_events'],
        'max_cascade_size': summary['max_cascade_size'],
        'mean_cascade_size': summary['mean_cascade_size'],
        'cascade_positive_events': n_cascade_events,
        'seal_duration': seal_duration,
        'final_weight': summary['final_weight'],
        'seal_order': seal_order,
        'seal_step_map': {str(k): v for k, v in step_map.items()},
        'cascade_series': cascade,
    }

    return metrics


def analyze_results(all_metrics: list) -> dict:
    """批量分析"""
    analysis = {}

    # 按 N 分组
    by_n = {}
    for m in all_metrics:
        n = m['N']
        if n not in by_n:
            by_n[n] = []
        by_n[n].append(m)

    analysis['by_N'] = {}
    for n in sorted(by_n.keys()):
        group = by_n[n]
        n_runs = len(group)
        sealed = [m for m in group if m['sealed']]
        n_sealed = len(sealed)
        seal_rate = n_sealed / n_runs if n_runs > 0 else 0

        ns = {
            'n_runs': n_runs,
            'n_sealed': n_sealed,
            'seal_rate': seal_rate,
        }

        if n_sealed > 0:
            seal_steps = [m['seal_step'] for m in sealed]
            cascade_sizes = [m['max_cascade_size'] for m in sealed]
            cascade_events = [m['n_cascade_events'] for m in sealed]
            seal_durations = [m['seal_duration'] for m in sealed]
            seal_fractions = [m['seal_fraction'] for m in sealed]

            ns.update({
                'seal_step_mean': float(np.mean(seal_steps)),
                'seal_step_std': float(np.std(seal_steps)),
                'seal_step_min': int(min(seal_steps)),
                'seal_step_max': int(max(seal_steps)),
                'cascade_size_mean': float(np.mean(cascade_sizes)),
                'cascade_size_std': float(np.std(cascade_sizes)),
                'cascade_size_min': int(min(cascade_sizes)),
                'cascade_size_max': int(max(cascade_sizes)),
                'cascade_events_mean': float(np.mean(cascade_events)),
                'seal_duration_mean': float(np.mean(seal_durations)),
                'seal_duration_std': float(np.std(seal_durations)),
                'seal_fraction_mean': float(np.mean(seal_fractions)),
                'seal_fraction_std': float(np.std(seal_fractions)),

                # 单次 cascade 事件的比例（统计相变的"纯粹性"）
                'single_event_ratio': sum(1 for m in sealed if m['cascade_positive_events'] <= 1) / n_sealed,
            })

            # 特殊分析：fast seal (<10 steps) vs normal
            fast = sum(1 for m in sealed if m['seal_step'] < 10)
            ns['fast_seal_ratio'] = fast / n_sealed

        analysis['by_N'][n] = ns

    # 全局统计
    total_runs = len(all_metrics)
    total_sealed = sum(1 for m in all_metrics if m['sealed'])
    analysis['global'] = {
        'total_runs': total_runs,
        'total_sealed': total_sealed,
        'total_N_values': len(by_n),
        'seal_rate_range': [
            min(ns['seal_rate'] for ns in analysis['by_N'].values()),
            max(ns['seal_rate'] for ns in analysis['by_N'].values()),
        ],
    }

    return analysis


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    """运行 N-sweep 实验"""
    print(f"{'=' * 70}")
    print(f"Phase 12 P2: N-sweep around phase boundary (exp_154)")
    print(f"{'=' * 70}")
    print(f"  N values: {N_VALUES}")
    runs_plan = {n: get_n_runs(n) for n in N_VALUES}
    print(f"  Runs per N: {runs_plan}")
    print(f"  Total runs: {sum(runs_plan.values())}")
    print(f"  Est. time: ~{sum(runs_plan.values()) * 38 / 60:.0f} min (at ~38s/run)")
    print(f"{'=' * 70}")

    all_metrics = []
    t_start = time.time()

    for idx, N in enumerate(N_VALUES):
        n_runs = get_n_runs(N)
        n_sealed = 0
        t_n_start = time.time()

        print(f"\n[{'#' * ((idx+1)*3//len(N_VALUES)):{'#'}^{3}}] N={N}: {n_runs} runs ", end='', flush=True)

        for run_id in range(n_runs):
            metrics = run_single(N, run_id)
            all_metrics.append(metrics)

            if metrics['sealed']:
                n_sealed += 1

            if (run_id + 1) % 10 == 0 or run_id == n_runs - 1:
                t_elapsed = time.time() - t_n_start
                print(f"", end='')

        t_elapsed = time.time() - t_n_start
        seal_rate = n_sealed / n_runs * 100
        per_run = t_elapsed / n_runs
        print(f"  {n_sealed}/{n_runs} sealed ({seal_rate:.0f}%), {t_elapsed:.0f}s ({per_run:.1f}s/run)")

    t_total = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"运行完成! 总时间: {t_total:.0f}s ({t_total/60:.1f}min)")

    # ============================================================
    # 分析
    # ============================================================
    print(f"\n{'=' * 70}")
    print(f"N-Sweep 分析结果")
    print(f"{'=' * 70}")

    analysis = analyze_results(all_metrics)

    print(f"\n-- 密封率 vs N --")
    for n in sorted(analysis['by_N'].keys()):
        ns = analysis['by_N'][n]
        bar = '#' * int(ns['seal_rate'] * 20)
        print(f"  N={n:3d}: {ns['seal_rate']*100:5.1f}% {bar}")

    print(f"\n-- Cascade 大小 vs N --")
    for n in sorted(analysis['by_N'].keys()):
        ns = analysis['by_N'][n]
        if ns['n_sealed'] > 0:
            c_mean = ns['cascade_size_mean']
            c_std = ns['cascade_size_std']
            frac = ns['seal_fraction_mean']
            bar = '#' * int(c_mean / 2)
            print(f"  N={n:3d}: cascade={c_mean:5.1f}±{c_std:4.1f}  (seal_frac={frac:.2f}) {bar}")

    print(f"\n-- 单次 cascade 比例 vs N --")
    for n in sorted(analysis['by_N'].keys()):
        ns = analysis['by_N'][n]
        if ns['n_sealed'] > 0:
            se_ratio = ns['single_event_ratio']
            fast_ratio = ns['fast_seal_ratio']
            print(f"  N={n:3d}: single_event={se_ratio:.2f}, fast_seal(<10)={fast_ratio:.2f}")

    print(f"\n-- 密封时序 vs N --")
    for n in sorted(analysis['by_N'].keys()):
        ns = analysis['by_N'][n]
        if ns['n_sealed'] > 0:
            print(f"  N={n:3d}: step_mean={ns['seal_step_mean']:5.1f}±{ns['seal_step_std']:4.1f}, "
                  f"range=[{ns['seal_step_min']:4d},{ns['seal_step_max']:4d}], "
                  f"duration={ns['seal_duration_mean']:4.1f}")

    # ============================================================
    # 保存结果
    # ============================================================
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"exp154_phase12_p2_nsweep_{timestamp}.json")

    save_data = {
        'params': {
            'N_values': N_VALUES,
            'runs_plan': runs_plan,
            'total_steps': TOTAL_STEPS,
            'timestamp': timestamp,
            'experiment': 'exp_154_phase12_p2_n_sweep',
        },
        'analysis': analysis,
        'metrics': all_metrics,
    }

    with open(result_file, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)

    print(f"\n结果保存至: {result_file}")
    return save_data


if __name__ == '__main__':
    run_experiment()
