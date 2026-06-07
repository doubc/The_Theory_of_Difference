"""
exp_155 — Phase 13 P1: 密封后持久性动力学

概述：
  Phase 12 验证了密封是一次性相变（单次 cascade，100% 在 Phase 12 P1 中）。
  现在的问题是：密封之后，系统是否还会继续演化？

核心假设：
  H155-1: 密封后继续运行 L0（保持 A1 持续 +1），sealed bits 不会重新激活
           → 密封是单向不可逆的
  H155-2: 密封后若增加差异密度（N 扩张），系统恢复活动——差异可"重新激活"
  H155-3: 密封后维持注入（A8 源强度维持），unsealed bits 可能被"拖动"进入 seal

实验条件：
  A: 密封后注入强度不变，继续运行 2000 步（对照）
  B: 密封后源注入强度提高 2x/5x/10x
  C: 密封后 N 扩张（48→72, 48→96），增加新 bits 作为额外差异源

用法：
  python experiments/exp_155_phase13_p1_post_seal_persistence.py
"""

import sys, os, json, datetime, time
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


# ============================================================
# 参数
# ============================================================
N_BASE = 48
TOTAL_STEPS = 1000           # 密封前的主运行
POST_SEAL_STEPS = 2000       # 密封后继续运行步数
N_RUNS = 30                  # 每个条件运行次数
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# 实验条件
CONDITIONS = {
    'A_control': {           # H155-1：不变对照
        'post_seal_config': {},
    },
    'B_inject_2x': {         # H155-3：2x 注入
        'post_seal_config': {'source_multiplier': 2.0},
    },
    'C_expand_72': {         # H155-2：N 扩张至 72
        'post_seal_config': {'expand_N': 72},
    },
    'C_expand_96': {         # H155-2：N 扩张至 96
        'post_seal_config': {'expand_N': 96},
    },
}


# ============================================================
# 单次运行
# ============================================================
def run_single(cond_name: str, config: dict, run_id: int, verbose: bool = False) -> dict:
    """单次实验运行

    返回密封前后的指标对比。
    """
    torch.manual_seed(run_id * 137 + 53 + sum(ord(c) for c in cond_name))

    # 随机初始状态
    initial = torch.zeros(N_BASE)
    n_ones = max(3, torch.randint(4, min(12, N_BASE // 2) + 1, (1,)).item())
    indices = torch.randperm(N_BASE)[:n_ones]
    initial[indices] = 1.0

    # 密封前的演化步数（使用 post_seal_steps 让 evolver 在密封后继续运行）
    post_cfg = config.get('post_seal_config', {})

    evolver = SpatialLongRangeEvolver(
        N=N_BASE,
        total_steps=TOTAL_STEPS,
        sample_interval=50,
        partial_sealing=False,
        post_seal_config=post_cfg,
        post_seal_steps=POST_SEAL_STEPS,
    )

    # 密封后回调：记录密封时的状态
    seal_info = {}
    def _on_post_seal(step, state, ev):
        nonlocal seal_info
        seal_info = {
            'seal_step': step,
            'sealed_bits_at_seal': len(ev.constraints.sealed_bits),
            'hw_at_seal': int(state.sum().item()),
        }

    t0 = time.time()
    result = evolver.run(initial_state=initial, verbose=False, post_seal_callback=_on_post_seal)
    elapsed = time.time() - t0

    # ---- 提取密封前指标 ----
    hw_history = evolver.hamming_weight_history
    snapshots = evolver.snapshots
    seal_step = evolver.seal_step
    sealed_ratio = evolver.constraints.get_sealed_ratio()
    n_sealed_bits = len(evolver.constraints.sealed_bits)

    # ---- 提取密封后指标 ----
    # 从 snapshots 中分离密封前和密封后的部分
    pre_seal_snapshots = [s for s in snapshots if s.step < seal_step] if seal_step >= 0 else snapshots
    post_seal_snapshots = [s for s in snapshots if s.step >= seal_step] if seal_step >= 0 else []

    # 密封后活动性：任何非零 flip/inject/lateral?
    post_seal_injects = [s.n_inject for s in post_seal_snapshots] if post_seal_snapshots else [0]
    post_seal_flips = [1 if s.flip_idx >= 0 else 0 for s in post_seal_snapshots] if post_seal_snapshots else [0]
    post_seal_laterals = [s.n_lateral for s in post_seal_snapshots] if post_seal_snapshots else [0]

    # HW 变化（密封后 vs 密封时）
    hw_pre_seal = int(hw_history[seal_step]) if seal_step >= 0 and seal_step < len(hw_history) else int(hw_history[-1])
    hw_final = int(result['final_state'].sum().item())

    # 是否经历了密封后的"二次激活"（HW 增加 > 1）
    hw_change_post_seal = hw_final - hw_pre_seal

    # 密封后是否有 unsealed bits 被 seal？
    # (受限于当前 evolver，post_seal 配置尚不支持 expand_N — 后续完善)
    has_post_seal_activity = (
        sum(post_seal_injects) > 0
        or sum(post_seal_flips) > 0
        or sum(post_seal_laterals) > 0
    )

    # 最终状态快照
    final_snapshot = snapshots[-1] if snapshots else None

    metrics = {
        'cond_name': cond_name,
        'run_id': run_id,
        'n_initial_ones': n_ones,
        'sealed': evolver.constraints.sealed,
        'seal_step': seal_step,
        'n_sealed_bits': n_sealed_bits,
        'sealed_ratio': sealed_ratio,
        'hw_pre_seal': hw_pre_seal,
        'hw_final': hw_final,
        'hw_change_post_seal': hw_change_post_seal,
        'has_post_seal_activity': has_post_seal_activity,
        'post_seal_inject_total': int(sum(post_seal_injects)),
        'post_seal_flip_total': int(sum(post_seal_flips)),
        'post_seal_lateral_total': int(sum(post_seal_laterals)),
        'n_post_seal_snapshots': len(post_seal_snapshots),
        'elapsed_sec': round(elapsed, 2),
    }

    return metrics


def analyze_results(all_metrics: list) -> dict:
    """批量分析"""
    analysis = {}

    # 按条件分组
    by_cond = {}
    for m in all_metrics:
        c = m['cond_name']
        if c not in by_cond:
            by_cond[c] = []
        by_cond[c].append(m)

    analysis['by_condition'] = {}
    for cond in sorted(by_cond.keys()):
        group = by_cond[cond]
        n_runs = len(group)

        sealed_runs = [m for m in group if m['sealed']]
        n_sealed = len(sealed_runs)
        seal_rate = n_sealed / n_runs if n_runs > 0 else 0

        active_runs = [m for m in group if m['has_post_seal_activity']]
        n_active = len(active_runs)

        hw_changes = [m['hw_change_post_seal'] for m in group]
        seal_steps = [m['seal_step'] for m in sealed_runs]

        cs = {
            'n_runs': n_runs,
            'n_sealed': n_sealed,
            'seal_rate': seal_rate,
            'n_post_seal_active': n_active,
            'post_seal_active_ratio': n_active / n_runs if n_runs > 0 else 0,
            'hw_change_mean': float(np.mean(hw_changes)),
            'hw_change_std': float(np.std(hw_changes)),
            'seal_step_mean': float(np.mean(seal_steps)) if seal_steps else -1,
            'seal_step_std': float(np.std(seal_steps)) if seal_steps else 0,
        }

        analysis['by_condition'][cond] = cs

    # 全局统计
    analysis['global'] = {
        'total_runs': len(all_metrics),
        'n_conditions': len(by_cond),
    }

    return analysis


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    print("=" * 70)
    print("Phase 13 P1: 密封后持久性动力学 (exp_155)")
    print("=" * 70)
    print(f"  N={N_BASE}, total_steps={TOTAL_STEPS}, post_seal_steps={POST_SEAL_STEPS}")
    print(f"  Runs per condition: {N_RUNS}")
    print(f"  Conditions: {list(CONDITIONS.keys())}")
    print(f"  Total runs: {len(CONDITIONS) * N_RUNS}")
    print("=" * 70)

    all_metrics = []
    t_start = time.time()

    for cond_idx, (cond_name, config) in enumerate(CONDITIONS.items()):
        print(f"\n[{cond_name}] ", end="", flush=True)
        t_cond_start = time.time()

        for run_id in range(N_RUNS):
            metrics = run_single(cond_name, config, run_id)
            all_metrics.append(metrics)

        t_cond = time.time() - t_cond_start
        per_run = t_cond / N_RUNS
        print(f"{N_RUNS} runs, {t_cond:.0f}s ({per_run:.1f}s/run)")

    t_total = time.time() - t_start
    print(f"\n总时间: {t_total:.0f}s ({t_total/60:.1f}min)")

    # ---- 分析 ----
    print(f"\n{'=' * 70}")
    print("分析结果")
    print("=" * 70)

    analysis = analyze_results(all_metrics)

    print(f"\n-- 密封率 vs 条件 --")
    for cond in sorted(analysis['by_condition'].keys()):
        cs = analysis['by_condition'][cond]
        print(f"  {cond:20s}: seal_rate={cs['seal_rate']*100:5.1f}%, "
              f"post_seal_active={cs['post_seal_active_ratio']*100:5.1f}%")

    print(f"\n-- Hamming Weight 密封后变化 --")
    for cond in sorted(analysis['by_condition'].keys()):
        cs = analysis['by_condition'][cond]
        bar = '#' * max(0, min(int(abs(cs['hw_change_mean']) * 2), 40))
        sign = "+" if cs['hw_change_mean'] > 0 else ""
        print(f"  {cond:20s}: \u0394HW={sign}{cs['hw_change_mean']:.2f}\u00b1{cs['hw_change_std']:.2f} {bar}")

    print(f"\n-- 密封时序 --")
    for cond in sorted(analysis['by_condition'].keys()):
        cs = analysis['by_condition'][cond]
        if cs['seal_step_mean'] >= 0:
            print(f"  {cond:20s}: seal_step={cs['seal_step_mean']:.0f}\u00b1{cs['seal_step_std']:.0f}")

    # ---- 保存 ----
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"exp155_phase13_p1_post_seal_{timestamp}.json")

    save_data = {
        'params': {
            'N_base': N_BASE,
            'total_steps': TOTAL_STEPS,
            'post_seal_steps': POST_SEAL_STEPS,
            'n_runs': N_RUNS,
            'conditions': CONDITIONS,
            'timestamp': timestamp,
            'experiment': 'exp_155_phase13_p1_post_seal_persistence',
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
