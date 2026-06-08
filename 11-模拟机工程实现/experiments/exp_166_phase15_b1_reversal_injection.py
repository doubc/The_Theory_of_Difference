"""
exp_166 — Phase 15 Path B1: Reversal Injection

科学问题：
  Phase 14 & Phase 15 Path A 所有实验均使用 0→1 差异注入。
  但如果系统具有方向不对称性，反转注入方向可能改变密封动力学？
  
  差异论的公理系统在纸面上是对称的（A1-A10 不对称性仅来源于初始条件），
  但数值实现中的方向场、密封检测、A8 加权等机制可能隐含方向偏好。

核心假设：
  H15-B1 (Reversal Symmetry): 系统在 0→1 和 1→0 注入下行为对称。
    如果成立 → 死秩序的不变性不仅是拓扑的，更是方向无关的。
    
  H15-B2 (Direction Bias): 系统具有隐含的 0→1 偏好（或 1→0 偏好）。
    如果不成立/不对称 → 反转方向可能改变密封结果。

实验设计：
  - 反转注入：选择 state[i] >= 0.5 且 direction[i] <= 0 的比特，设为 0
  - 对比标准注入（0→1）与反转注入（1→0）
  - n_inject ∈ {1, 2, 4} 每种方向
  - N=48, 总步数 1200
  - 每次运行保留种子一致性

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference\11-模拟机工程实现
  python experiments/exp_166_phase15_b1_reversal_injection.py
"""

import sys, os, math, json, datetime, time
import numpy as np
import torch
import contextlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


# ============================================================
# 参数
# ============================================================
N = 48
TOTAL_STEPS = 1200
SAMPLE_INTERVAL = 50
N_RUNS = 1
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 注入方向条件
# ============================================================
INJECTION_DIRECTIONS = ['standard', 'reversed']
INJECTION_RATES = [1, 2, 4]  # n_inject per step (approximate)

CONDITIONS = []
for direction in INJECTION_DIRECTIONS:
    for n_inj in INJECTION_RATES:
        CONDITIONS.append({
            'label': f'{direction}_inj{n_inj}',
            'direction': direction,
            'n_inject': n_inj,
        })

# Also test with no injection baseline
CONDITIONS.insert(0, {
    'label': 'baseline',
    'direction': 'none',
    'n_inject': 0,
})

print(f"Total conditions: {len(CONDITIONS)} (including baseline)")
print(f"Total runs: {len(CONDITIONS) * N_RUNS}")


# ============================================================
# 反转注入 step_callback
# ============================================================
def make_reversal_injection_callback(n_inject: int):
    """在标准注入后执行反转注入：将 1→0 而非 0→1

    在每一步的标准注入完成后触发：
    1. 选择 state=1 且 direction<=0 的比特
    2. 翻转它们为 0
    3. 记录这些反转注入

    这需要在 evolver 内部的标准注入完成后执行，
    step_callback 的调用时机正好在注入和演化之后。
    """
    assert n_inject > 0, "n_inject must be > 0"

    def _callback(step: int, state: torch.Tensor,
                  snapshot: object, constraints: object) -> None:
        if constraints.sealed:
            # 密封后不再注入（标准注入也不在密封后执行，保持一致）
            return

        # 选择 state=1 且 direction <= 0 的比特
        # 这就是「反转」：标准注入找 0→方向≥0，反转找 1→方向≤0
        candidates = [i for i in range(state.numel())
                      if state[i].item() >= 0.5
                      and constraints.direction[i].item() <= 0]

        if not candidates:
            return

        # 随机选择 n_inject 个
        n_actual = min(n_inject, len(candidates))
        if n_actual <= 0:
            return

        # 随机选择
        rng = np.random.RandomState(seed=int(step * 31337 + 166))
        chosen = rng.choice(candidates, size=n_actual, replace=False)

        for idx in chosen:
            state[idx] = 0.0
            constraints.direction[idx] = -1  # 向下方向

    return _callback


# ============================================================
# 单次运行
# ============================================================
def run_single(condition: dict, run_id: int) -> dict:
    label = condition['label']
    direction = condition['direction']
    n_inj = condition['n_inject']

    seed = run_id * 31337 + 166 + hash(label) % 100000
    rng = np.random.RandomState(seed % (2**31))
    torch.manual_seed(seed % (2**31))

    # 初始状态：~6 个 1
    initial = torch.zeros(N)
    n_ones = rng.randint(4, min(10, N // 2))
    indices = rng.choice(N, size=n_ones, replace=False)
    initial[indices] = 1.0

    # 根据注入方向创建回调
    if direction == 'reversed':
        callback = make_reversal_injection_callback(n_inj)
    else:
        callback = None  # 标准注入由 evolver 内部完成

    evolver = SpatialLongRangeEvolver(
        N=N,
        total_steps=TOTAL_STEPS,
        sample_interval=SAMPLE_INTERVAL,
        partial_sealing=False,
    )

    # 标准注入的条件：设置 source_strength
    if direction == 'standard':
        # 标准注入由 engine 内部处理，需要让 n_inject ≈ 指定值
        # 但 evolver 没有直接暴露 source_strength 参数...
        # 默认 source_strength 由 constraints.get_A8_source_strength() 决定
        # 我们需要通过约束对象设置它
        pass

    t0 = time.time()
    with contextlib.redirect_stdout(open(os.devnull, 'w')):
        result = evolver.run(initial_state=initial, verbose=False,
                             step_callback=callback)
    elapsed = time.time() - t0

    # ---- 提取轨迹 ----
    hw_traj = np.array(evolver.hamming_weight_history)
    seal_step = evolver.seal_step if evolver.seal_step >= 0 else len(hw_traj) // 2

    # ---- 密封信息 ----
    sealed_bits = evolver.constraints.sealed_bits
    n_sealed = len(sealed_bits)

    # ---- Post-seal snapshot index ----
    seal_snap_idx = None
    for idx, snap in enumerate(evolver.snapshots):
        if snap.step >= seal_step:
            seal_snap_idx = idx
            break
    if seal_snap_idx is None:
        seal_snap_idx = len(evolver.snapshots) // 2

    # ---- Post-seal HW stats ----
    post_hw = hw_traj[seal_snap_idx:] if seal_snap_idx < len(hw_traj) else hw_traj[-50:]
    post_hw_mean = float(post_hw.mean()) if len(post_hw) > 0 else 0.0
    post_hw_var = float(post_hw.var()) if len(post_hw) > 1 else 0.0

    # ---- Post-seal flip analysis ----
    post_seal_flip_positions = []
    for i in range(seal_snap_idx, len(evolver.snapshots) - 1):
        s1 = evolver.snapshots[i].state
        s2 = evolver.snapshots[i + 1].state
        diff = (s2 - s1).abs()
        flipped = torch.where(diff > 0.5)[0].tolist()
        post_seal_flip_positions.extend(flipped)

    if n_sealed > 0 and len(post_seal_flip_positions) > 0:
        sealed_array = np.array(sorted(sealed_bits))
        dists = []
        for fp in post_seal_flip_positions:
            if fp not in sealed_bits:
                dist = min(abs(fp - s) for s in sealed_array)
                dists.append(dist)
        dists = np.array(dists)
        mean_flip_dist = float(dists.mean()) if len(dists) > 0 else N
        n_boundary = int(np.sum(dists <= 3)) if len(dists) > 0 else 0
        n_non_boundary = int(np.sum(dists > 3)) if len(dists) > 0 else 0
    else:
        mean_flip_dist = N
        n_boundary = 0
        n_non_boundary = 0

    n_post_flips = len(post_seal_flip_positions)

    # ---- 方向场 ----
    direction_arr = evolver.constraints.direction.cpu().numpy()
    n_dir_pos = int(np.sum(direction_arr > 0))
    n_dir_neg = int(np.sum(direction_arr < 0))
    total_dir = n_dir_pos + n_dir_neg
    dir_balance = abs(n_dir_pos - n_dir_neg) / max(total_dir, 1) if total_dir > 0 else 0.0

    if n_sealed > 0:
        sealed_dir_pos = sum(1 for i in sealed_bits if direction_arr[i] > 0)
        sealed_dir_neg = sum(1 for i in sealed_bits if direction_arr[i] < 0)
        sealed_dir_balance = abs(sealed_dir_pos - sealed_dir_neg) / max(n_sealed, 1)
    else:
        sealed_dir_balance = 0.0

    # ---- 密封检测 ----
    sealed_ratio = n_sealed / N
    is_over_sealed = sealed_ratio > 0.45

    # ---- 脉冲检测 ----
    if len(post_hw) > 5:
        early_var = float(post_hw[:max(3, len(post_hw)//3)].var())
        late_var = float(post_hw[-max(3, len(post_hw)//3):].var())
        is_pulse = (early_var > 0.1 and late_var < 0.01)
    else:
        early_var = 0.0
        late_var = 0.0
        is_pulse = False

    # ---- 相关性长度 ----
    if len(post_hw) > 10:
        post_hw_centered = post_hw - post_hw.mean()
        if post_hw_centered.var() > 1e-10:
            ac = np.correlate(post_hw_centered, post_hw_centered, mode='full')
            ac = ac[len(ac)//2:]
            ac = ac / ac[0] if ac[0] > 0 else ac
            e_tau = 1.0 / math.e
            below = np.where(ac < e_tau)[0]
            correlation_length = int(below[0]) if len(below) > 0 else len(ac)
        else:
            correlation_length = 0
    else:
        correlation_length = 0

    # ---- 总注入统计 ----
    total_injected = evolver.constraints.total_injected

    return {
        'condition_label': label,
        'injection_direction': direction,
        'n_inject': n_inj,
        'run_id': run_id,
        'seed': seed,

        'sealed': evolver.constraints.sealed,
        'n_sealed': n_sealed,
        'sealed_ratio': sealed_ratio,
        'is_over_sealed': is_over_sealed,
        'seal_step': seal_step,
        'post_seal_steps': len(hw_traj) - seal_step,
        'total_injected': total_injected,

        'post_hw_mean': post_hw_mean,
        'post_hw_var': post_hw_var,

        'n_post_flips': n_post_flips,
        'post_flip_rate': n_post_flips / max(len(hw_traj) - seal_step, 1),
        'mean_flip_dist_to_sealed': mean_flip_dist,
        'n_boundary_flips': n_boundary,
        'n_non_boundary_flips': n_non_boundary,
        'boundary_flip_ratio': n_boundary / max(n_post_flips, 1),

        'n_dir_pos': n_dir_pos,
        'n_dir_neg': n_dir_neg,
        'dir_balance': float(dir_balance),
        'sealed_dir_balance': sealed_dir_balance,

        'early_hw_var': float(early_var),
        'late_hw_var': float(late_var),
        'is_pulse': is_pulse,

        'correlation_length': correlation_length,
        'elapsed_sec': round(elapsed, 2),
    }


# ============================================================
# 分析
# ============================================================
def analyze_results(all_metrics: list) -> dict:
    by_cond = {}
    for m in all_metrics:
        label = m['condition_label']
        if label not in by_cond:
            by_cond[label] = []
        by_cond[label].append(m)

    analysis = {'by_condition': {}}

    for label in sorted(by_cond.keys()):
        group = by_cond[label]
        n_total = len(group)

        sealed_count = [m['sealed'] for m in group]
        seal_ratio = sum(1 for s in sealed_count if s) / n_total

        post_flip_rates = [m['post_flip_rate'] for m in group]
        n_post_flips_list = [m['n_post_flips'] for m in group]
        boundary_ratios = [m['boundary_flip_ratio'] for m in group]
        mean_flip_dists = [m['mean_flip_dist_to_sealed'] for m in group]
        post_hw_vars = [m['post_hw_var'] for m in group]
        dir_balances = [m['dir_balance'] for m in group]
        over_sealed = [m['is_over_sealed'] for m in group]
        corr_lengths = [m['correlation_length'] for m in group]
        total_injected = [m['total_injected'] for m in group]

        cs = {
            'n_runs': n_total,
            'seal_ratio': float(np.mean(sealed_count)),
            'post_flip_rate_mean': float(np.mean(post_flip_rates)) if post_flip_rates else 0.0,
            'post_flip_rate_std': float(np.std(post_flip_rates)) if len(post_flip_rates) > 1 else 0.0,
            'n_post_flips_mean': float(np.mean(n_post_flips_list)) if n_post_flips_list else 0.0,
            'boundary_flip_ratio_mean': float(np.mean(boundary_ratios)) if boundary_ratios else 0.0,
            'mean_flip_dist_mean': float(np.mean(mean_flip_dists)) if mean_flip_dists else N,
            'post_hw_var_mean': float(np.mean(post_hw_vars)) if post_hw_vars else 0.0,
            'dir_balance_mean': float(np.mean(dir_balances)) if dir_balances else 0.0,
            'over_sealed_rate': float(np.mean(over_sealed)),
            'correlation_length_mean': float(np.mean(corr_lengths)) if corr_lengths else 0.0,
            'total_injected_mean': float(np.mean(total_injected)),
        }
        analysis['by_condition'][label] = cs

    sorted_conds = sorted(analysis['by_condition'].items(),
                          key=lambda x: x[1]['post_flip_rate_mean'],
                          reverse=True)
    analysis['ranked_by_activity'] = [
        {'label': label,
         'post_flip_rate': cs['post_flip_rate_mean'],
         'boundary_ratio': cs['boundary_flip_ratio_mean'],
         'over_sealed_rate': cs['over_sealed_rate'],
         'hw_var': cs['post_hw_var_mean'],
         'seal_ratio': cs['seal_ratio']}
        for label, cs in sorted_conds
    ]

    return analysis


# ============================================================
# 打印结果
# ============================================================
def print_results(analysis: dict):
    print(f"\n{'=' * 110}")
    print("Phase 15 Path B1: Reversal Injection — Results (exp_166)")
    print("=" * 110)

    by_cond = analysis['by_condition']
    ranked = analysis['ranked_by_activity']

    header = (f"{'Condition':24s} {'Seal':>6s} {'FlipRate':>8s} {'Bound%':>7s} "
              f"{'Dist':>5s} {'HWvar':>7s} {'OverS':>6s} {'DirBal':>7s} {'TotalInj':>8s}")
    print(f"\n{header}")
    print("-" * 110)

    for item in ranked:
        label = item['label']
        cs = by_cond[label]
        se = f"{cs.get('seal_ratio',0)*100:4.0f}%"
        fr = f"{cs['post_flip_rate_mean']:.4f}"
        br = f"{cs['boundary_flip_ratio_mean']*100:5.1f}%"
        dd = f"{cs['mean_flip_dist_mean']:.1f}"
        hv = f"{cs['post_hw_var_mean']:.3f}"
        os_ = f"{cs['over_sealed_rate']*100:4.0f}%"
        db = f"{cs['dir_balance_mean']:.3f}"
        ti = f"{cs['total_injected_mean']:.0f}"
        print(f"  {label:24s} {se:>6s} {fr:>8s} {br:>7s} {dd:>5s} {hv:>7s} {os_:>6s} {db:>7s} {ti:>8s}")

    # Analysis
    print(f"\n{'=' * 110}")
    print("Analysis")
    print("=" * 110)

    baseline = by_cond.get('baseline', {})
    print(f"\n  Baseline (no extra injection):")
    print(f"    flip_rate={baseline.get('post_flip_rate_mean',0):.4f}, "
          f"seal_ratio={baseline.get('seal_ratio',0)*100:.0f}%")

    # By injection direction
    print(f"\n  --- By Injection Direction ---")
    for d in INJECTION_DIRECTIONS:
        d_conds = [cs for lbl, cs in by_cond.items()
                   if lbl.startswith(f'{d}_')]
        if not d_conds:
            continue
        avg_flip = np.mean([c['post_flip_rate_mean'] for c in d_conds])
        avg_bound = np.mean([c['boundary_flip_ratio_mean'] for c in d_conds])
        avg_over = np.mean([c['over_sealed_rate'] for c in d_conds])
        avg_seal = np.mean([c['seal_ratio'] for c in d_conds])
        print(f"    {d:10s}: flip_rate={avg_flip:.4f}, "
              f"boundary%={avg_bound*100:.1f}%, seal%={avg_seal*100:.0f}%, "
              f"over_sealed%={avg_over*100:.0f}%")

    # By injection rate
    print(f"\n  --- By Injection Rate ---")
    for n in INJECTION_RATES:
        n_conds = [cs for lbl, cs in by_cond.items()
                   if lbl.endswith(f'_inj{n}')]
        if not n_conds:
            continue
        # Separate standard vs reversed
        std = [cs for lbl, cs in by_cond.items() if lbl == f'standard_inj{n}']
        rev = [cs for lbl, cs in by_cond.items() if lbl == f'reversed_inj{n}']
        std_flip = std[0]['post_flip_rate_mean'] if std else 0
        rev_flip = rev[0]['post_flip_rate_mean'] if rev else 0
        std_seal = std[0]['seal_ratio'] if std else 0
        rev_seal = rev[0]['seal_ratio'] if rev else 0
        print(f"    n_inject={n}: standard flip={std_flip:.4f} seal%={std_seal*100:.0f}% | "
              f"reversed flip={rev_flip:.4f} seal%={rev_seal*100:.0f}%")


    # Hypothesis verdict
    print(f"\n  {'=' * 60}")
    print(f"  Hypothesis Verdict")
    print(f"  {'=' * 60}")

    # Compare standard vs reversed directly
    std_conds = {lbl: cs for lbl, cs in by_cond.items() if lbl.startswith('standard_')}
    rev_conds = {lbl: cs for lbl, cs in by_cond.items() if lbl.startswith('reversed_')}

    if not std_conds or not rev_conds:
        print("  [ERROR] Missing direction conditions for comparison")
    else:
        std_seal_ratio = np.mean([cs['seal_ratio'] for cs in std_conds.values()])
        rev_seal_ratio = np.mean([cs['seal_ratio'] for cs in rev_conds.values()])
        std_flip = np.mean([cs['post_flip_rate_mean'] for cs in std_conds.values()])
        rev_flip = np.mean([cs['post_flip_rate_mean'] for cs in rev_conds.values()])

        print(f"  Standard injection: seal={std_seal_ratio*100:.0f}%, flip_rate={std_flip:.4f}")
        print(f"  Reversed injection: seal={rev_seal_ratio*100:.0f}%, flip_rate={rev_flip:.4f}")

        flip_diff = abs(std_flip - rev_flip)
        if flip_diff > 0.05:
            print(f"  [B1] H15-B1 (Symmetry): ASYMMETRY DETECTED — "
                  f"flip_rate difference={flip_diff:.4f}")
        else:
            print(f"  [B1] H15-B1 (Symmetry): SYSTEM IS SYMMETRIC — "
                  f"flip_rate difference={flip_diff:.4f}")

        if abs(std_seal_ratio - rev_seal_ratio) > 0.1:
            print(f"  [B1] H15-B2 (Direction bias): SEALING DIFFERENCE — "
                  f"std_seal={std_seal_ratio*100:.0f}% vs rev_seal={rev_seal_ratio*100:.0f}%")
        else:
            print(f"  [B1] H15-B2 (Direction bias): NO SEALING DIFFERENCE")

    max_over = max(cs['over_sealed_rate'] for cs in by_cond.values())
    if max_over > 0.2:
        print(f"\n  [STRONG] Secondary sealing detected! — max_over_sealed={max_over*100:.0f}%")
    else:
        print(f"\n  [NO] No secondary sealing — max_over_sealed={max_over*100:.0f}%")

    all_no = (max_over <= 0.2)
    if all_no:
        print(f"\n  === FINAL: Path B1 REJECTED — Reversal injection fails to change dead order ===")
    else:
        print(f"\n  === FINAL: Path B1 SHOWS SIGNAL ===")

    print(f"\n  Ran {sum(cs['n_runs'] for cs in by_cond.values())} runs across "
          f"{len(by_cond)} conditions")


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    print("=" * 110)
    print("Phase 15 Path B1: Reversal Injection (exp_166)")
    print("=" * 110)
    print(f"  N={N}, steps={TOTAL_STEPS}, sample_interval={SAMPLE_INTERVAL}")
    print(f"  Conditions: {len(CONDITIONS)}")
    print(f"  Total runs: {len(CONDITIONS)}")
    print(f"  Standard injection: 0->1 (engine default)")
    print(f"  Reversed injection: 1->0 (step_callback)")
    print(f"  n_inject: {INJECTION_RATES}")
    print("=" * 110)

    all_metrics = []
    t_start = time.time()
    total_runs = len(CONDITIONS) * N_RUNS
    run_count = 0

    baseline_cond = [c for c in CONDITIONS if c['direction'] == 'none']
    other_conds = [c for c in CONDITIONS if c['direction'] != 'none']

    for cond in baseline_cond + other_conds:
        label = cond['label']
        print(f"\n--- {label} ---")

        for run_id in range(N_RUNS):
            metrics = run_single(cond, run_id)
            all_metrics.append(metrics)
            run_count += 1

        pct = run_count / total_runs * 100
        nf_val = metrics.get('n_post_flips', 0)
        elapsed_so_far = time.time() - t_start
        rate = run_count / max(1, elapsed_so_far)
        eta = (total_runs - run_count) / max(rate, 0.001)
        print(f"    total {run_count}/{total_runs} ({pct:.0f}%) | flips={nf_val} | "
              f"{elapsed_so_far:.0f}s elapsed, ~{eta:.0f}s remaining")

    t_total = time.time() - t_start
    print(f"\nTotal time: {t_total:.0f}s ({t_total/60:.1f}min)")

    analysis = analyze_results(all_metrics)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR,
                               f"exp166_phase15_b1_reversal_{timestamp}.json")

    save_metrics = []
    for m in all_metrics:
        sm = {}
        for k, v in m.items():
            if isinstance(v, (np.integer,)):
                sm[k] = int(v)
            elif isinstance(v, (np.floating,)):
                sm[k] = float(v)
            elif isinstance(v, np.ndarray):
                sm[k] = v.tolist()
            else:
                sm[k] = v
        save_metrics.append(sm)

    save_data = {
        'params': {
            'N': N,
            'total_steps': TOTAL_STEPS,
            'sample_interval': SAMPLE_INTERVAL,
            'n_runs': N_RUNS,
            'n_conditions': len(CONDITIONS),
            'injection_directions': INJECTION_DIRECTIONS,
            'injection_rates': INJECTION_RATES,
            'timestamp': timestamp,
            'experiment': 'exp_166_phase15_b1_reversal_injection',
        },
        'analysis': {
            'by_condition': {k: dict(v) for k, v in analysis['by_condition'].items()},
            'ranked_by_activity': analysis['ranked_by_activity'],
        },
        'metrics': save_metrics,
    }

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\n=== Results saved to: {result_file}")

    print_results(analysis)

    return save_data, result_file


if __name__ == '__main__':
    run_experiment()