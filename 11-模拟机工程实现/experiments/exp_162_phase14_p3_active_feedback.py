"""
exp_162 — Phase 14 P3: Active Constraint Shaping (Feedback)

科学问题：
  Phase 14 P1 (exp_158, 时间结构化注入) 和 P2 (exp_159, 竞争核) 均未能打破死秩序。
  P3 探索密封结构是否可以通过主动修改约束景观来产生新层。

核心假设：
  H14-7（反馈假设）：密封结构主动修改约束（coupling_bias）后，
    非密封比特的翻转活性显著提升。

  H14-8（密度依赖假设）：短程强反馈（decay_length=1, feedback_strength≥1.0）
    最有利于产生边界聚集和可能的二次密封。

反馈机制：
  密封后，密封比特向附近非密封比特发射「约束信号」：
    coupling_bias[i] = feedback_strength * exp(-distance_to_nearest_sealed / decay_length)
  正值 bias 意味着该比特从源获得更多注入能量（更容易 0→1）。

实验设计：
  Part A: 单核（N=48），5 种 feedback_strength × 4 种 decay_length = 20 条件 × 4 runs = 80 runs
  Part B (若 Part A 有信号): 双核（N=96），最佳参数 + 基线对比

测量指标：
  - 密封后非密封比特的翻转速率（flip_rate）
  - 翻转活性的空间分布（距密封结构的距离函数）
  - 方向场梯度（direction field 的空间模式）
  - 二次密封事件（密封后有新比特被密封）
  - HW 方差时间序列
  - 相关性长度 ξ

用法：
  python experiments/exp_162_phase14_p3_active_feedback.py
"""

import sys, os, math, json, datetime, time
import numpy as np
import torch
import contextlib


@contextlib.contextmanager
def suppress_stdout():
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        yield
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


# ============================================================
# 参数
# ============================================================
N = 48
TOTAL_STEPS = 800              # 含 200 步密封后窗口
SAMPLE_INTERVAL = 20
N_RUNS = 4                     # 每条件运行次数
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 反馈条件（Part A: 单核）
# ============================================================
FEEDBACK_STRENGTHS = [0.0, 0.1, 0.3, 1.0, 3.0]
DECAY_LENGTHS = [1, 3, 10, N]  # 1=最近邻, N=全局

FEEDBACK_CONDITIONS = []
for fs in FEEDBACK_STRENGTHS:
    for dl in DECAY_LENGTHS:
        FEEDBACK_CONDITIONS.append({
            'label': f'fs{fs}_dl{dl}',
            'feedback_strength': fs,
            'decay_length': dl,
        })

# baseline (no feedback, fs=0.0 is already included; keep explicit)
FEEDBACK_CONDITIONS.insert(0, {
    'label': 'baseline',
    'feedback_strength': 0.0,
    'decay_length': 0,
})


# ============================================================
# 反馈回调工厂
# ============================================================
def make_feedback_callback(feedback_strength: float, decay_length: int):
    """创建主动反馈 step_callback

    密封后，密封比特向附近非密封比特发射约束信号。
    信号强度：feedback_strength * exp(-dist/decay_length)
    范围：[0, feedback_strength]，钳位到 [-1.0, 1.0]
    """
    def _callback(step: int, state: torch.Tensor,
                  snapshot: object, constraints: object) -> None:
        if not constraints.sealed or len(constraints.sealed_bits) == 0:
            constraints.coupling_bias.zero_()
            return
        if feedback_strength <= 0.0:
            constraints.coupling_bias.zero_()
            return

        N = state.numel()
        sealed_set = constraints.sealed_bits

        bias = torch.zeros(N, device=constraints.coupling_bias.device,
                           dtype=constraints.coupling_bias.dtype)

        for i in range(N):
            if i in sealed_set:
                continue
            # distance to nearest sealed bit (circular/linear)
            min_dist = min(abs(i - j) for j in sealed_set)
            bias[i] = feedback_strength * math.exp(-min_dist / max(decay_length, 1))

        bias.clamp_(-1.0, 1.0)
        constraints.coupling_bias.copy_(bias)

    return _callback


# ============================================================
# 单次运行
# ============================================================
def run_single(condition: dict, run_id: int, verbose: bool = False) -> dict:
    label = condition['label']
    fs = condition['feedback_strength']
    dl = condition['decay_length']

    seed = run_id * 31337 + 17 + hash(label) % 100000
    rng = np.random.RandomState(seed % (2**31))
    torch.manual_seed(seed % (2**31))

    # 初始状态：~6 个 1
    initial = torch.zeros(N)
    n_ones = rng.randint(4, min(10, N // 2))
    indices = rng.choice(N, size=n_ones, replace=False)
    initial[indices] = 1.0

    callback = make_feedback_callback(fs, dl)

    evolver = SpatialLongRangeEvolver(
        N=N,
        total_steps=TOTAL_STEPS,
        sample_interval=SAMPLE_INTERVAL,
        partial_sealing=False,
    )

    t0 = time.time()
    with contextlib.redirect_stdout(open(os.devnull, 'w')):
        result = evolver.run(initial_state=initial, verbose=False,
                             step_callback=callback)
    elapsed = time.time() - t0

    # ---- 提取轨迹 ----
    hw_traj = np.array(evolver.hamming_weight_history)
    seal_step = evolver.seal_step if evolver.seal_step >= 0 else len(hw_traj) // 2

    # 密封前的翻转历史
    flip_arr = np.array(evolver.flip_history)
    flip_arr = flip_arr[flip_arr >= 0]  # valid indices

    # ---- 密封后分析 ----
    sealed_bits = evolver.constraints.sealed_bits
    n_sealed = len(sealed_bits)

    # 密封后翻转（>= seal_step）
    if len(flip_arr) > 0:
        post_seal_flips = flip_arr[flip_arr >= 0]  # all valid flips
        # 用 step 跟踪：flip_history 记录翻转时的 index，但不知道步数
        # 改为用 snapshots 的密封时间过滤
    else:
        post_seal_flips = np.array([])

    # ---- 从 snapshots 提取密封后数据 ----
    # 找到密封后的 snapshot 索引
    seal_snap_idx = None
    for idx, snap in enumerate(evolver.snapshots):
        if snap.step >= seal_step:
            seal_snap_idx = idx
            break
    if seal_snap_idx is None:
        seal_snap_idx = len(evolver.snapshots) // 2

    # 密封后的 HW 轨迹（全局）
    post_hw = hw_traj[seal_snap_idx:] if seal_snap_idx < len(hw_traj) else hw_traj[-50:]
    post_hw_var = float(post_hw.var()) if len(post_hw) > 1 else 0.0

    # ---- 密封后翻转统计 ----
    # 由于 flip_history 不记录步数，我们用 snapshots 前后的 state diff 来统计翻转
    # 方法：对比连续 snapshots 的状态，统计每次翻转的位置
    post_seal_flip_positions = []
    for i in range(seal_snap_idx, len(evolver.snapshots) - 1):
        s1 = evolver.snapshots[i].state
        s2 = evolver.snapshots[i + 1].state
        diff = (s2 - s1).abs()
        flipped = torch.where(diff > 0.5)[0].tolist()
        post_seal_flip_positions.extend(flipped)

    # 密封后翻转的空间分布：距最近密封比特的距离
    if n_sealed > 0 and len(post_seal_flip_positions) > 0:
        sealed_array = np.array(sorted(sealed_bits))
        dists = []
        for fp in post_seal_flip_positions:
            if fp not in sealed_bits:
                dist = min(abs(fp - s) for s in sealed_array)
                dists.append(dist)
        dists = np.array(dists)
        mean_flip_dist = float(dists.mean()) if len(dists) > 0 else N
        n_near_sealed = int(np.sum(dists <= 3)) if len(dists) > 0 else 0
    else:
        mean_flip_dist = N
        n_near_sealed = 0

    n_post_flips = len(post_seal_flip_positions)

    # ---- 方向场分析（密封后方向变化） ----
    direction = evolver.constraints.direction.cpu().numpy()
    n_direction_pos = int(np.sum(direction > 0))
    n_direction_neg = int(np.sum(direction < 0))

    # 方向梯度：密封比特附近的方向同质性
    if n_sealed > 0:
        sealed_dir_vals = [direction[i] for i in sealed_bits]
        pos_near_sealed = sum(1 for i in sealed_bits if direction[i] > 0)
        neg_near_sealed = sum(1 for i in sealed_bits if direction[i] < 0)
        sealed_dir_balance = abs(pos_near_sealed - neg_near_sealed) / max(n_sealed, 1)
    else:
        sealed_dir_balance = 0.0

    # ---- 二次密封检测 ----
    # 密封后是否又有新的比特被封? 检查密封后是否有新比特加入 sealed_bits
    # 如果 sealed_bits 比 seal_step 时的多，说明有二次密封
    n_sealed_at_seal = min(n_sealed, int(0.40 * N))  # approximate

    return {
        'condition_label': label,
        'feedback_strength': fs,
        'decay_length': dl,
        'run_id': run_id,
        'seed': seed,

        # 密封信息
        'sealed': evolver.constraints.sealed,
        'n_sealed': n_sealed,
        'sealed_ratio': n_sealed / N,
        'seal_step': seal_step,
        'post_seal_steps': len(hw_traj) - seal_step,

        # HW 密封后统计
        'post_hw_mean': float(post_hw.mean()) if len(post_hw) > 0 else 0.0,
        'post_hw_var': post_hw_var,

        # 翻转统计
        'n_post_flips': n_post_flips,
        'post_flip_rate': n_post_flips / max(len(hw_traj) - seal_step, 1),
        'mean_flip_dist_to_sealed': mean_flip_dist,
        'n_flips_near_sealed': n_near_sealed,
        'near_sealed_ratio': n_near_sealed / max(n_post_flips, 1),

        # 方向场
        'n_direction_pos': n_direction_pos,
        'n_direction_neg': n_direction_neg,
        'sealed_dir_balance': sealed_dir_balance,

        # 性能
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

        # 密封率
        sealed_rates = [m['sealed'] for m in group]
        seal_ratio = sum(1 for s in sealed_rates if s) / n_total

        # 密封后翻转
        post_flip_rates = [m['post_flip_rate'] for m in group]
        n_post_flips_list = [m['n_post_flips'] for m in group]
        mean_flip_dists = [m['mean_flip_dist_to_sealed'] for m in group]
        near_sealed_ratios = [m['near_sealed_ratio'] for m in group]

        # 密封后 HW 方差
        post_hw_vars = [m['post_hw_var'] for m in group]

        # 方向场
        dir_balances = [m['sealed_dir_balance'] for m in group]

        # 二次密封：sealed_ratio > 0.40 的（超过正常密封比例）
        n_over_sealed = sum(1 for m in group if m['sealed_ratio'] > 0.45)
        over_sealed_rate = n_over_sealed / n_total

        cs = {
            'n_runs': n_total,
            'seal_ratio': seal_ratio,
            'post_flip_rate_mean': float(np.mean(post_flip_rates)) if post_flip_rates else 0.0,
            'post_flip_rate_std': float(np.std(post_flip_rates)) if len(post_flip_rates) > 1 else 0.0,
            'n_post_flips_mean': float(np.mean(n_post_flips_list)) if n_post_flips_list else 0.0,
            'mean_flip_dist_mean': float(np.mean(mean_flip_dists)) if mean_flip_dists else N,
            'near_sealed_ratio_mean': float(np.mean(near_sealed_ratios)) if near_sealed_ratios else 0.0,
            'near_sealed_ratio_std': float(np.std(near_sealed_ratios)) if len(near_sealed_ratios) > 1 else 0.0,
            'post_hw_var_mean': float(np.mean(post_hw_vars)) if post_hw_vars else 0.0,
            'post_hw_var_std': float(np.std(post_hw_vars)) if len(post_hw_vars) > 1 else 0.0,
            'dir_balance_mean': float(np.mean(dir_balances)) if dir_balances else 0.0,
            'over_sealed_rate': over_sealed_rate,
        }
        analysis['by_condition'][label] = cs

    # 排序：按密封后翻转率降序
    sorted_conds = sorted(analysis['by_condition'].items(),
                          key=lambda x: x[1]['post_flip_rate_mean'],
                          reverse=True)
    analysis['ranked_by_activity'] = [
        (label, cs['post_flip_rate_mean'], cs['near_sealed_ratio_mean'])
        for label, cs in sorted_conds
    ]

    return analysis


# ============================================================
# 打印结果
# ============================================================
def print_results(analysis: dict):
    print(f"\n{'=' * 100}")
    print("Phase 14 P3: 主动约束塑造 — 结果分析 (exp_162)")
    print("=" * 100)

    by_cond = analysis['by_condition']
    ranked = analysis['ranked_by_activity']

    # 排名表
    header = f"{'Condition':28s} {'Seal':>6s} {'FlipRate':>8s} {'#Flips':>7s} {'Dist':>6s} {'Near%':>7s}"
    header += f" {'HWvar':>7s} {'OverS':>6s} {'DirBal':>7s}"
    print(f"\n{header}")
    print("-" * 100)

    for label, flip_rate, near_ratio in ranked:
        cs = by_cond[label]
        se = f"{cs['seal_ratio']*100:4.0f}%" if 'seal_ratio' in cs else 'N/A'
        fr = f"{cs['post_flip_rate_mean']:.4f}"
        nf = f"{cs['n_post_flips_mean']:.0f}"
        dd = f"{cs['mean_flip_dist_mean']:.1f}"
        nr = f"{cs['near_sealed_ratio_mean']*100:5.1f}%"
        hv = f"{cs['post_hw_var_mean']:.3f}"
        os = f"{cs['over_sealed_rate']*100:4.0f}%"
        db = f"{cs['dir_balance_mean']:.3f}"
        print(f"  {label:28s} {se:>6s} {fr:>8s} {nf:>7s} {dd:>6s} {nr:>7s} {hv:>7s} {os:>6s} {db:>7s}")

    # 结论
    print(f"\n{'=' * 100}")
    print("Conclusions")
    print("=" * 100)

    baseline = by_cond.get('baseline', {})
    bl_flip_rate = baseline.get('post_flip_rate_mean', 0.0)
    bl_near_ratio = baseline.get('near_sealed_ratio_mean', 0.0)
    bl_var = baseline.get('post_hw_var_mean', 0.0)

    # 找出最好的反馈条件（按翻转率提升）
    best_cond = ranked[0] if ranked else ('None', 0, 0)
    best_label = best_cond[0]
    best_flip_rate = best_cond[1] if len(best_cond) > 1 else 0.0
    best_near = best_cond[2] if len(best_cond) > 2 else 0.0

    print(f"\n  基线 (no feedback): flip_rate={bl_flip_rate:.4f}, near_ratio={bl_near_ratio*100:.1f}%, HWvar={bl_var:.3f}")
    print(f"  最佳条件 ({best_label}): flip_rate={best_flip_rate:.4f}, near_ratio={best_near*100:.1f}%")

    if best_flip_rate > bl_flip_rate * 1.5 and best_near > bl_near_ratio * 1.2:
        print(f"\n  [OK] H14-7 (feedback): FEEDBACK ENHANCES ACTIVITY — flip_rate {best_flip_rate:.4f} vs {bl_flip_rate:.4f} (+{((best_flip_rate/bl_flip_rate)-1)*100:.0f}%)")
    else:
        print(f"\n  [NO] H14-7 (feedback): Feedback does NOT significantly enhance activity")

    # 检查短程强反馈
    short_strong_label = 'fs3.0_dl1'
    if short_strong_label in by_cond:
        ss = by_cond[short_strong_label]
        ss_flip = ss.get('post_flip_rate_mean', 0.0)
        ss_near = ss.get('near_sealed_ratio_mean', 0.0)
        ss_over = ss.get('over_sealed_rate', 0.0)
        print(f"\n  短程强反馈 ({short_strong_label}): flip_rate={ss_flip:.4f}, near_ratio={ss_near*100:.1f}%, over_sealed={ss_over*100:.0f}%")
        if ss_flip > bl_flip_rate * 2 and ss_near > 0.3:
            print(f"  [OK] H14-8 (short-strong): Short-range strong feedback produces localized activity")
        else:
            print(f"  [NO] H14-8 (short-strong): Short-range strong feedback fails to produce localized activity")

    # 总体结论
    print(f"\n  已密封 runs: {sum(1 for cs in by_cond.values() for _ in range(cs['n_runs']) if cs.get('seal_ratio', 0) > 0)}")
    print(f"  过密封 runs (二次密封): 最大率={max(cs.get('over_sealed_rate', 0) for cs in by_cond.values())*100:.0f}%")

    if max(cs.get('over_sealed_rate', 0) for cs in by_cond.values()) > 0.2:
        print(f"  [OK] 二次密封事件检测到 — 约束塑造有效")
    else:
        print(f"  [NO] 无二次密封事件 — 约束塑造不足以产生新密封")

    max_var_cond = max(by_cond.items(), key=lambda x: x[1]['post_hw_var_mean'])
    print(f"  最大 HW 方差: {max_var_cond[0]} — var={max_var_cond[1]['post_hw_var_mean']:.4f}")


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    print("=" * 100)
    print("Phase 14 P3: 主动约束塑造 (exp_162) — Part A: Single Nucleus")
    print("=" * 100)
    print(f"  N={N}, steps={TOTAL_STEPS}")
    print(f"  Runs per condition: {N_RUNS}")
    print(f"  Conditions: {len(FEEDBACK_CONDITIONS)}")
    print(f"  Total runs: {len(FEEDBACK_CONDITIONS) * N_RUNS}")
    print("=" * 100)

    print("\n反馈条件:")
    for i, cond in enumerate(FEEDBACK_CONDITIONS):
        print(f"  [{i+1}] {cond['label']}")

    all_metrics = []
    t_start = time.time()
    total_runs = len(FEEDBACK_CONDITIONS) * N_RUNS
    run_count = 0

    for cond in FEEDBACK_CONDITIONS:
        label = cond['label']
        print(f"\n--- {label} ---")

        for run_id in range(N_RUNS):
            metrics = run_single(cond, run_id)
            all_metrics.append(metrics)
            run_count += 1

            if (run_id + 1) % 2 == 0 or run_id == N_RUNS - 1:
                pct = run_count / total_runs * 100
                n_flips_avg = np.mean([m.get('n_post_flips', 0) for m in all_metrics[-N_RUNS:]])
                elapsed_so_far = time.time() - t_start
                rate = run_count / max(1, elapsed_so_far)
                eta = (total_runs - run_count) / max(rate, 0.001)
                print(f"    {run_id+1}/{N_RUNS} runs | total {run_count}/{total_runs} "
                      f"({pct:.0f}%) | avg_flips:{n_flips_avg:.1f} | "
                      f"{elapsed_so_far:.0f}s elapsed, ~{eta:.0f}s remaining")

    t_total = time.time() - t_start
    print(f"\nTotal time: {t_total:.0f}s ({t_total/60:.1f}min)")

    # ---- 分析 ----
    analysis = analyze_results(all_metrics)

    # ---- 保存 ----
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR,
                               f"exp162_phase14_p3_feedback_{timestamp}.json")

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
            'n_conditions': len(FEEDBACK_CONDITIONS),
            'feedback_strengths': FEEDBACK_STRENGTHS,
            'decay_lengths': DECAY_LENGTHS,
            'timestamp': timestamp,
            'experiment': 'exp_162_phase14_p3_feedback_partA',
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

    # ---- 打印 ----
    try:
        print_results(analysis)
    except UnicodeEncodeError:
        import io
        _buf = io.StringIO()
        _old = sys.stdout
        sys.stdout = _buf
        print_results(analysis)
        sys.stdout = _old
        _safe = _buf.getvalue().encode('ascii', 'replace').decode('ascii')
        print(_safe)

    return save_data, result_file


if __name__ == '__main__':
    run_experiment()