"""
exp_165 — Phase 15 Path A3: Cooperative Binding (Quadratic Decay Feedback)

科学问题：
  exp_163 (Sigmoid) 和 exp_164 (Step) 均无法产生二次密封。
  两种非线性均未能打破死秩序的拓扑不变性。
  
  一个未被探索的方向是**协同反馈** — 多个密封集群的约束场叠加，
  或者约束强度随距离非线性增强，但呈「近程强、远程弱」的模式。

核心假设：
  H15-A5 (Cooperative): 二次衰减的约束信号 (bias = fs * max(0, 1 - dist/L)²)
    能产生比指数衰减更强的近距离约束和更明确的「禁入区」。
    
  H15-A6 (Multi-cluster synergy): 当系统拥有多个密封集群时，
    约束场叠加可能创造群际张力区，打破集群间的死寂。

反馈机制：
  bias[i] = fs * max(0, 1 - dist / decay_length) ** 2
  
  二次衰减与指数衰减的关键区别：
  - 指数衰减: e^(-dist/L) — 在 dist=0 处斜率为 -1/L，无限逼近 0
  - 二次衰减: (1 - dist/L)² — 在 dist=0 处斜率为 -2/L，在 dist=L 处精确为 0
  - 结果：二次衰减在近距离约束更强，在远距离约束更快为 0

实验设计：
  - 4 种 decay_length × 2 种 feedback_strength = 8 条件 + 1 baseline = 9 条件
  - 每条件 1 次运行 = 9 runs
  - N=48, 总步数 1200

测量指标：
  - 二次密封率
  - 群际翻转 (inter-cluster flips): 两个不同密封集群之间是否出现翻转
  - 约束剖面 (constraint profile): 实际 bias 的空间分布

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference\11-模拟机工程实现
  python experiments/exp_165_phase15_a3_cooperative_binding.py
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
# 二次衰减反馈条件
# ============================================================
# decay_length: 约束场的有效作用距离
#   - 小 (4): 紧贴密封边界，远距离无影响
#   - 中 (8): 与指数衰减的 decay_length 一致（直接对比）
#   - 大 (16): 覆盖半个系统
#   - 极大 (32): 覆盖整个系统（几乎所有比特都受影响）
# feedback_strength: 场强
#   - 1.0: 基线强度（直接与指数衰减对比）
#   - 3.0: 强约束（与 Sigmoid/Step 的强条件一致）
DECAY_LENGTHS = [4, 8, 16, 32]
FEEDBACK_STRENGTHS = [1.0, 3.0]

FEEDBACK_CONDITIONS = []
for dl in DECAY_LENGTHS:
    for fs in FEEDBACK_STRENGTHS:
        FEEDBACK_CONDITIONS.append({
            'label': f'quad_dl{dl}_fs{fs}',
            'decay_length': dl,
            'feedback_strength': fs,
        })

# Baseline (no feedback)
FEEDBACK_CONDITIONS.insert(0, {
    'label': 'baseline',
    'decay_length': 0,
    'feedback_strength': 0.0,
})

print(f"Total conditions: {len(FEEDBACK_CONDITIONS)} (including baseline)")
print(f"Total runs: {len(FEEDBACK_CONDITIONS) * N_RUNS}")


# ============================================================
# 二次衰减反馈回调
# ============================================================
def make_quadratic_callback(decay_length: int, feedback_strength: float):
    """创建二次衰减型主动反馈 step_callback

    bias[i] = fs * max(0, 1 - dist / decay_length) ** 2

    物理意义：
      密封结构周围的约束场按二次衰减。
      与指数衰减不同，二次衰减在 dist=0 处斜率为 -2/dl（指数为 -1/dl），
      在 dist=dl 处精确归零（指数是渐近逼近）。

    这产生了更明确的「禁入区」：
      近距离 (dist < dl/2): bias > fs/4 的强约束区
      中距离 (dist ≈ dl): bias ≈ 0，约束精确为零
      远距离 (dist > dl): bias = 0，完全无约束
    """
    def _callback(step: int, state: torch.Tensor,
                  snapshot: object, constraints: object) -> None:
        if not constraints.sealed or len(constraints.sealed_bits) == 0:
            constraints.coupling_bias.zero_()
            return
        if feedback_strength <= 0.0:
            constraints.coupling_bias.zero_()
            return

        N_state = state.numel()
        sealed_set = constraints.sealed_bits

        bias = torch.zeros(N_state, device=constraints.coupling_bias.device,
                           dtype=constraints.coupling_bias.dtype)

        # 获取密封集群
        sealed_array = np.array(sorted(sealed_set))

        # 计算每个非密封比特到最近密封比特的距离
        for i in range(N_state):
            if i in sealed_set:
                continue

            # 线性距离
            min_dist = min(abs(i - j) for j in sealed_set)

            # 二次衰减: fs * max(0, 1 - dist/decay_length)²
            if decay_length > 0:
                ratio = 1.0 - min_dist / decay_length
                if ratio > 0:
                    bias[i] = feedback_strength * ratio * ratio
                # else: bias[i] = 0

        bias.clamp_(-1.0, 1.0)
        constraints.coupling_bias.copy_(bias)

    return _callback


# ============================================================
# 单次运行
# ============================================================
def run_single(condition: dict, run_id: int) -> dict:
    label = condition['label']
    dl = condition['decay_length']
    fs = condition['feedback_strength']

    seed = run_id * 31337 + 165 + hash(label) % 100000
    rng = np.random.RandomState(seed % (2**31))
    torch.manual_seed(seed % (2**31))

    # 初始状态：~6 个 1
    initial = torch.zeros(N)
    n_ones = rng.randint(4, min(10, N // 2))
    indices = rng.choice(N, size=n_ones, replace=False)
    initial[indices] = 1.0

    callback = make_quadratic_callback(dl, fs)

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

    # 空间分布
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

        # 群际翻转检测: 翻转到不同密封集群的距离
        # 如果 flip 发生在空间上远离所有密封集群的位置 → 可能是集群间的活动
        n_far = int(np.sum(dists > 5)) if len(dists) > 0 else 0
        far_ratio = n_far / max(len(dists), 1)
    else:
        mean_flip_dist = N
        n_boundary = 0
        n_non_boundary = 0
        n_far = 0
        far_ratio = 0.0

    n_post_flips = len(post_seal_flip_positions)

    # ---- 方向场分析 ----
    direction = evolver.constraints.direction.cpu().numpy()
    n_dir_pos = int(np.sum(direction > 0))
    n_dir_neg = int(np.sum(direction < 0))
    total_dir = n_dir_pos + n_dir_neg
    dir_balance = abs(n_dir_pos - n_dir_neg) / max(total_dir, 1) if total_dir > 0 else 0.0

    if n_sealed > 0:
        sealed_dir_pos = sum(1 for i in sealed_bits if direction[i] > 0)
        sealed_dir_neg = sum(1 for i in sealed_bits if direction[i] < 0)
        sealed_dir_balance = abs(sealed_dir_pos - sealed_dir_neg) / max(n_sealed, 1)
    else:
        sealed_dir_balance = 0.0

    # ---- 二次密封检测 ----
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

    return {
        'condition_label': label,
        'decay_length': dl,
        'feedback_strength': fs,
        'run_id': run_id,
        'seed': seed,

        'sealed': evolver.constraints.sealed,
        'n_sealed': n_sealed,
        'sealed_ratio': sealed_ratio,
        'is_over_sealed': is_over_sealed,
        'seal_step': seal_step,
        'post_seal_steps': len(hw_traj) - seal_step,

        'post_hw_mean': post_hw_mean,
        'post_hw_var': post_hw_var,

        'n_post_flips': n_post_flips,
        'post_flip_rate': n_post_flips / max(len(hw_traj) - seal_step, 1),
        'mean_flip_dist_to_sealed': mean_flip_dist,
        'n_boundary_flips': n_boundary,
        'n_non_boundary_flips': n_non_boundary,
        'boundary_flip_ratio': n_boundary / max(n_post_flips, 1),
        'n_far_flips': n_far,
        'far_flip_ratio': far_ratio,

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
        sealed_dir_balances = [m['sealed_dir_balance'] for m in group]
        over_sealed = [m['is_over_sealed'] for m in group]
        corr_lengths = [m['correlation_length'] for m in group]
        pulses = [m['is_pulse'] for m in group]
        far_ratios = [m['far_flip_ratio'] for m in group]

        cs = {
            'n_runs': n_total,
            'seal_ratio': float(np.mean(sealed_count)),
            'post_flip_rate_mean': float(np.mean(post_flip_rates)) if post_flip_rates else 0.0,
            'post_flip_rate_std': float(np.std(post_flip_rates)) if len(post_flip_rates) > 1 else 0.0,
            'n_post_flips_mean': float(np.mean(n_post_flips_list)) if n_post_flips_list else 0.0,
            'boundary_flip_ratio_mean': float(np.mean(boundary_ratios)) if boundary_ratios else 0.0,
            'boundary_flip_ratio_std': float(np.std(boundary_ratios)) if len(boundary_ratios) > 1 else 0.0,
            'mean_flip_dist_mean': float(np.mean(mean_flip_dists)) if mean_flip_dists else N,
            'post_hw_var_mean': float(np.mean(post_hw_vars)) if post_hw_vars else 0.0,
            'post_hw_var_std': float(np.std(post_hw_vars)) if len(post_hw_vars) > 1 else 0.0,
            'dir_balance_mean': float(np.mean(dir_balances)) if dir_balances else 0.0,
            'sealed_dir_balance_mean': float(np.mean(sealed_dir_balances)) if sealed_dir_balances else 0.0,
            'over_sealed_rate': float(np.mean(over_sealed)),
            'correlation_length_mean': float(np.mean(corr_lengths)) if corr_lengths else 0.0,
            'pulse_rate': float(np.mean(pulses)),
            'far_flip_ratio_mean': float(np.mean(far_ratios)) if far_ratios else 0.0,
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
         'pulse_rate': cs['pulse_rate'],
         'far_flip_ratio': cs['far_flip_ratio_mean']}
        for label, cs in sorted_conds
    ]

    return analysis


# ============================================================
# 打印结果
# ============================================================
def print_results(analysis: dict):
    print(f"\n{'=' * 110}")
    print("Phase 15 Path A3: Cooperative Binding (Quadratic) — Results (exp_165)")
    print("=" * 110)

    by_cond = analysis['by_condition']
    ranked = analysis['ranked_by_activity']

    header = (f"{'Condition':24s} {'Seal':>6s} {'FlipRate':>8s} {'Bound%':>7s} "
              f"{'Dist':>5s} {'Far%':>6s} {'HWvar':>7s} {'OverS':>6s} {'Pulse':>6s}")
    print(f"\n{header}")
    print("-" * 110)

    for item in ranked:
        label = item['label']
        cs = by_cond[label]
        se = f"{cs['seal_ratio']*100:4.0f}%" if 'seal_ratio' in cs else 'N/A'
        fr = f"{cs['post_flip_rate_mean']:.4f}"
        br = f"{cs['boundary_flip_ratio_mean']*100:5.1f}%"
        dd = f"{cs['mean_flip_dist_mean']:.1f}"
        ff = f"{cs['far_flip_ratio_mean']*100:4.0f}%"
        hv = f"{cs['post_hw_var_mean']:.3f}"
        os_ = f"{cs['over_sealed_rate']*100:4.0f}%"
        pu = f"{cs['pulse_rate']*100:4.0f}%"
        print(f"  {label:24s} {se:>6s} {fr:>8s} {br:>7s} {dd:>5s} {ff:>6s} {hv:>7s} {os_:>6s} {pu:>6s}")

    # Analysis
    print(f"\n{'=' * 110}")
    print("Analysis")
    print("=" * 110)

    baseline = by_cond.get('baseline', {})
    bl_flip = baseline.get('post_flip_rate_mean', 0.0)
    bl_bound = baseline.get('boundary_flip_ratio_mean', 0.0)
    bl_var = baseline.get('post_hw_var_mean', 0.0)
    bl_over = baseline.get('over_sealed_rate', 0.0)
    bl_far = baseline.get('far_flip_ratio_mean', 0.0)

    print(f"\n  Baseline (no feedback):")
    print(f"    flip_rate={bl_flip:.4f}, boundary%={bl_bound*100:.1f}%, "
          f"far%={bl_far*100:.0f}%, HWvar={bl_var:.3f}, over_sealed={bl_over*100:.0f}%")

    # By decay_length
    print(f"\n  --- By Decay Length ---")
    for dl in DECAY_LENGTHS:
        dl_conds = [cs for lbl, cs in by_cond.items()
                    if lbl.startswith(f'quad_dl{dl}_')]
        if not dl_conds:
            continue
        avg_flip = np.mean([c['post_flip_rate_mean'] for c in dl_conds])
        avg_bound = np.mean([c['boundary_flip_ratio_mean'] for c in dl_conds])
        avg_over = np.mean([c['over_sealed_rate'] for c in dl_conds])
        avg_hwvar = np.mean([c['post_hw_var_mean'] for c in dl_conds])
        avg_far = np.mean([c['far_flip_ratio_mean'] for c in dl_conds])
        print(f"    decay_length={dl:2d}: flip_rate={avg_flip:.4f}, "
              f"boundary%={avg_bound*100:.1f}%, far%={avg_far*100:.0f}%, "
              f"over_sealed%={avg_over*100:.0f}%, HWvar={avg_hwvar:.3f}")

    # By feedback_strength
    print(f"\n  --- By Feedback Strength ---")
    for fs in FEEDBACK_STRENGTHS:
        fs_conds = [cs for lbl, cs in by_cond.items()
                    if lbl.endswith(f'_fs{fs}')]
        if not fs_conds:
            continue
        avg_flip = np.mean([c['post_flip_rate_mean'] for c in fs_conds])
        avg_bound = np.mean([c['boundary_flip_ratio_mean'] for c in fs_conds])
        avg_over = np.mean([c['over_sealed_rate'] for c in fs_conds])
        avg_far = np.mean([c['far_flip_ratio_mean'] for c in fs_conds])
        print(f"    fs={fs:.1f}: flip_rate={avg_flip:.4f}, "
              f"boundary%={avg_bound*100:.1f}%, far%={avg_far*100:.0f}%, "
              f"over_sealed%={avg_over*100:.0f}%")

    # Best vs baseline
    best = ranked[0] if ranked else {'label': 'None', 'post_flip_rate': 0}
    best_label = best['label']
    best_flip = best['post_flip_rate']
    best_bound = by_cond.get(best_label, {}).get('boundary_flip_ratio_mean', 0)
    best_over = by_cond.get(best_label, {}).get('over_sealed_rate', 0)
    best_hwvar = by_cond.get(best_label, {}).get('post_hw_var_mean', 0)
    best_far = by_cond.get(best_label, {}).get('far_flip_ratio_mean', 0)

    print(f"\n  Best condition: {best_label}")
    print(f"    flip_rate={best_flip:.4f} vs baseline={bl_flip:.4f} "
          f"(+{((best_flip/max(bl_flip,1e-10))-1)*100:.0f}%)")
    print(f"    boundary%={best_bound*100:.1f}%, far%={best_far*100:.0f}%")
    print(f"    over_sealed={best_over*100:.0f}%")

    # Hypothesis verdict
    print(f"\n  {'=' * 60}")
    print(f"  Hypothesis Verdict")
    print(f"  {'=' * 60}")

    max_over = max(cs['over_sealed_rate'] for cs in by_cond.values())
    if max_over > 0.2:
        print(f"  [STRONG] H15-A5 (Cooperative): OVER-SEALED DETECTED — "
              f"max_over_sealed_rate={max_over*100:.0f}%")
    else:
        print(f"  [NO] H15-A5 (Cooperative): No secondary sealing detected — "
              f"max_over_sealed_rate={max_over*100:.0f}%")

    max_far = max(cs['far_flip_ratio_mean'] for cs in by_cond.values())
    if max_far > bl_far * 3 and max_far > 0.05:
        print(f"  [MEDIUM] H15-A6 (Multi-cluster synergy): Far-flip enrichment detected — "
              f"max_far={max_far*100:.1f}% vs baseline {bl_far*100:.0f}%")
    else:
        print(f"  [NO] H15-A6 (Multi-cluster): No significant far-flip enrichment — "
              f"max_far={max_far*100:.1f}% vs baseline {bl_far*100:.0f}%")

    max_dir_dev = max(abs(cs['dir_balance_mean'] - 0.5) for cs in by_cond.values())
    if max_dir_dev >= 0.1:
        print(f"  [WEAK] Direction field gradient detected — "
              f"max_dir_dev={max_dir_dev:.3f}")
    else:
        print(f"  [WEAK] No direction field gradient — "
              f"max_dir_dev={max_dir_dev:.3f}")

    all_no = (max_over <= 0.2 and max_far <= max(bl_far * 3, 0.05) and max_dir_dev < 0.1)
    if all_no:
        print(f"\n  === FINAL: Path A3 REJECTED — Quadratic binding fails to break dead order ===")
        print(f"  → Proceeding to Path B (Information Injection)")
    else:
        print(f"\n  === FINAL: Path A3 SHOWS SIGNAL — further investigation warranted ===")

    print(f"\n  Ran {sum(cs['n_runs'] for cs in by_cond.values())} runs across "
          f"{len(by_cond)} conditions")


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    print("=" * 110)
    print("Phase 15 Path A3: Cooperative Binding — Quadratic Decay (exp_165)")
    print("=" * 110)
    print(f"  N={N}, steps={TOTAL_STEPS}, sample_interval={SAMPLE_INTERVAL}")
    print(f"  Runs per condition: {N_RUNS}")
    print(f"  Conditions: {len(FEEDBACK_CONDITIONS)} (1 baseline + {len(FEEDBACK_CONDITIONS)-1} quad)")
    print(f"  Total runs: {len(FEEDBACK_CONDITIONS) * N_RUNS}")
    print(f"  Quadratic: bias = fs * max(0, 1 - dist/dl)^2")
    print(f"  decay_length ∈ {DECAY_LENGTHS}  fs ∈ {FEEDBACK_STRENGTHS}")
    print("=" * 110)

    all_metrics = []
    t_start = time.time()
    total_runs = len(FEEDBACK_CONDITIONS) * N_RUNS
    run_count = 0

    baseline_cond = [c for c in FEEDBACK_CONDITIONS if c['label'] == 'baseline']
    quad_conds = [c for c in FEEDBACK_CONDITIONS if c['label'] != 'baseline']

    for cond in baseline_cond + quad_conds:
        label = cond['label']
        print(f"\n--- {label} ---")

        for run_id in range(N_RUNS):
            metrics = run_single(cond, run_id)
            all_metrics.append(metrics)
            run_count += 1

            if (run_id + 1) % 1 == 0:
                pct = run_count / total_runs * 100
                nf_val = metrics.get('n_post_flips', 0)
                elapsed_so_far = time.time() - t_start
                rate = run_count / max(1, elapsed_so_far)
                eta = (total_runs - run_count) / max(rate, 0.001)
                print(f"    run {run_id+1}/{N_RUNS} | total {run_count}/{total_runs} "
                      f"({pct:.0f}%) | flips={nf_val} | "
                      f"{elapsed_so_far:.0f}s elapsed, ~{eta:.0f}s remaining")

    t_total = time.time() - t_start
    print(f"\nTotal time: {t_total:.0f}s ({t_total/60:.1f}min)")

    analysis = analyze_results(all_metrics)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR,
                               f"exp165_phase15_a3_quadratic_{timestamp}.json")

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
            'decay_lengths': DECAY_LENGTHS,
            'feedback_strengths': FEEDBACK_STRENGTHS,
            'timestamp': timestamp,
            'experiment': 'exp_165_phase15_a3_quadratic',
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
