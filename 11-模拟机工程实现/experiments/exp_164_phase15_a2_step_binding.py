"""
exp_164 — Phase 15 Path A2: Step Binding (Hard-Threshold Nonlinearity)

科学问题：
  exp_163 证明 Sigmoid 型非线性绑定的平滑相变区无法打破死秩序。
  一个更极端的假设是：需要**不连续的跳变**——即真正的阶跃函数。

核心假设：
  H15-A3 (Step)：硬阈值 (step) 约束信号能在密封边界产生不连续跳变，
    触发二次密封。最不连续的函数 = 最强非线性响应。

  H15-A4 (Range)：最有效的阈值范围在 decay_length (≈8) 附近，
    因为指数衰减约束和硬阈值约束在相同的尺度上竞争。

反馈机制：
  bias[i] = feedback_strength if dist <= threshold else 0.0

  这完全消除了平滑衰减。约束场在 threshold 距离处具有
  「存在/不存在」的二元性，类比于量子测量中的波包坍缩。

实验设计：
  - 5 种 threshold × 4 种 feedback_strength = 20 条件 + 1 baseline = 21 条件
  - 每条件 1 次运行 = 21 runs
  - N=48, 总步数 1200 (密封在 ~100 步，1200 步足够观测后密封动力学)

测量指标：
  - 二次密封率 (sealed_ratio > 0.45 → over_sealed)
  - 翻转富集度 (边界区域 vs 非边界区域的 flip 密度)
  - 方向场梯度 (sealed_dir_balance)
  - 相关性长度 ξ
  - 脉冲响应: step 函数可能产生「一次性」的边界冲击而非持续活动

用法：
  cd C:/Users/Administrator/Documents/the_theory_of_difference\11-模拟机工程实现
  python experiments/exp_164_phase15_a2_step_binding.py
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
TOTAL_STEPS = 1200  # 密封很快发生(~100步)，1200步足够
SAMPLE_INTERVAL = 50
N_RUNS = 1          # 每条件运行次数（21 runs 总计）
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# Step 反馈条件
# ============================================================
# threshold: 硬阈值距离（密封比特的线性距离）
#   小 threshold (2): 紧贴密封边界，只有极近距离的比特受到约束
#   中等 threshold (4-8): 与 decay_length 竞争
#   大 threshold (12-16): 远距离约束，几乎所有比特都被影响
# feedback_strength: 约束强度
#   1.0: 弱约束（指数衰减基线的同等强度）
#   2.0: 中等约束
#   3.0: 强约束（与 Sigmoid 一致）
#   5.0: 极强约束（测试饱和效应）
THRESHOLDS = [2, 4, 8, 12, 16]
FEEDBACK_STRENGTHS = [1.0, 2.0, 3.0, 5.0]

FEEDBACK_CONDITIONS = []
for th in THRESHOLDS:
    for fs in FEEDBACK_STRENGTHS:
        FEEDBACK_CONDITIONS.append({
            'label': f'step_th{th}_fs{fs}',
            'threshold': th,
            'feedback_strength': fs,
        })

# Baseline (no feedback)
FEEDBACK_CONDITIONS.insert(0, {
    'label': 'baseline',
    'threshold': 0,
    'feedback_strength': 0.0,
})

print(f"Total conditions: {len(FEEDBACK_CONDITIONS)} (including baseline)")
print(f"Total runs: {len(FEEDBACK_CONDITIONS) * N_RUNS}")


# ============================================================
# Step 反馈回调
# ============================================================
def make_step_callback(threshold: int, feedback_strength: float):
    """创建硬阈值 Step 型主动反馈 step_callback

    bias[i] = fs if dist <= threshold else 0.0

    这是所有非线性中最不连续的选择：
    - 信号在 threshold 处从 '有' 突变到 '无'
    - 这种突变可能产生密封边界的「冲击波」

    与 Sigmoid 的关键区别：
    - Sigmoid: 连续过渡 → 约束场平滑变化
    - Step: 不连续跳变 → 约束场在边界处阶跃
    
    与指数衰减的关键区别：
    - 指数衰减: bias 随 dist 单调递减
    - Step: bias 在 threshold 内恒定，之外为 0
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

        for i in range(N_state):
            if i in sealed_set:
                continue
            # 线性距离
            min_dist = min(abs(i - j) for j in sealed_set)

            # Step: fs if dist <= threshold else 0.0
            if min_dist <= threshold:
                bias[i] = feedback_strength

        bias.clamp_(-1.0, 1.0)
        constraints.coupling_bias.copy_(bias)

    return _callback


# ============================================================
# 单次运行
# ============================================================
def run_single(condition: dict, run_id: int) -> dict:
    label = condition['label']
    th = condition['threshold']
    fs = condition['feedback_strength']

    seed = run_id * 31337 + 164 + hash(label) % 100000
    rng = np.random.RandomState(seed % (2**31))
    torch.manual_seed(seed % (2**31))

    # 初始状态：~6 个 1
    initial = torch.zeros(N)
    n_ones = rng.randint(4, min(10, N // 2))
    indices = rng.choice(N, size=n_ones, replace=False)
    initial[indices] = 1.0

    callback = make_step_callback(th, fs)

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

    # ---- 找到密封后的 snapshot 索引 ----
    seal_snap_idx = None
    for idx, snap in enumerate(evolver.snapshots):
        if snap.step >= seal_step:
            seal_snap_idx = idx
            break
    if seal_snap_idx is None:
        seal_snap_idx = len(evolver.snapshots) // 2

    # ---- 密封后 HW 统计 ----
    post_hw = hw_traj[seal_snap_idx:] if seal_snap_idx < len(hw_traj) else hw_traj[-50:]
    post_hw_mean = float(post_hw.mean()) if len(post_hw) > 0 else 0.0
    post_hw_var = float(post_hw.var()) if len(post_hw) > 1 else 0.0

    # ---- 密封后翻转统计 ----
    post_seal_flip_positions = []
    for i in range(seal_snap_idx, len(evolver.snapshots) - 1):
        s1 = evolver.snapshots[i].state
        s2 = evolver.snapshots[i + 1].state
        diff = (s2 - s1).abs()
        flipped = torch.where(diff > 0.5)[0].tolist()
        post_seal_flip_positions.extend(flipped)

    # 翻转的空间分布
    if n_sealed > 0 and len(post_seal_flip_positions) > 0:
        sealed_array = np.array(sorted(sealed_bits))
        dists = []
        for fp in post_seal_flip_positions:
            if fp not in sealed_bits:
                dist = min(abs(fp - s) for s in sealed_array)
                dists.append(dist)
        dists = np.array(dists)
        mean_flip_dist = float(dists.mean()) if len(dists) > 0 else N

        # 边界区域 (dist ≤ 3) vs 非边界区域 (dist > 3) 的翻转计数
        n_boundary = int(np.sum(dists <= 3)) if len(dists) > 0 else 0
        n_non_boundary = int(np.sum(dists > 3)) if len(dists) > 0 else 0
    else:
        mean_flip_dist = N
        n_boundary = 0
        n_non_boundary = 0

    n_post_flips = len(post_seal_flip_positions)

    # ---- 方向场分析 ----
    direction = evolver.constraints.direction.cpu().numpy()
    n_dir_pos = int(np.sum(direction > 0))
    n_dir_neg = int(np.sum(direction < 0))
    total_dir = n_dir_pos + n_dir_neg
    dir_balance = abs(n_dir_pos - n_dir_neg) / max(total_dir, 1) if total_dir > 0 else 0.0

    # 密封比特附近的方向同质性
    if n_sealed > 0:
        sealed_dir_pos = sum(1 for i in sealed_bits if direction[i] > 0)
        sealed_dir_neg = sum(1 for i in sealed_bits if direction[i] < 0)
        sealed_dir_balance = abs(sealed_dir_pos - sealed_dir_neg) / max(n_sealed, 1)
    else:
        sealed_dir_balance = 0.0

    # ---- 二次密封检测 (sealed_ratio > 0.45 的视为过密封) ----
    sealed_ratio = n_sealed / N
    is_over_sealed = sealed_ratio > 0.45

    # ---- 脉冲检测 ----
    # Step 函数可能产生「一次性」的边界冲击而非持续活动。
    # 检测方法：如果翻转数 > 0 但集中在前几步，后续完全静默
    if len(post_hw) > 5:
        early_var = float(post_hw[:max(3, len(post_hw)//3)].var())
        late_var = float(post_hw[-max(3, len(post_hw)//3):].var())
        is_pulse = (early_var > 0.1 and late_var < 0.01)
    else:
        early_var = 0.0
        late_var = 0.0
        is_pulse = False

    # ---- 相关性长度 ξ 近似 ----
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
        'threshold': th,
        'feedback_strength': fs,
        'run_id': run_id,
        'seed': seed,

        # 密封信息
        'sealed': evolver.constraints.sealed,
        'n_sealed': n_sealed,
        'sealed_ratio': sealed_ratio,
        'is_over_sealed': is_over_sealed,
        'seal_step': seal_step,
        'post_seal_steps': len(hw_traj) - seal_step,

        # HW 统计
        'post_hw_mean': post_hw_mean,
        'post_hw_var': post_hw_var,

        # 翻转统计
        'n_post_flips': n_post_flips,
        'post_flip_rate': n_post_flips / max(len(hw_traj) - seal_step, 1),
        'mean_flip_dist_to_sealed': mean_flip_dist,
        'n_boundary_flips': n_boundary,
        'n_non_boundary_flips': n_non_boundary,
        'boundary_flip_ratio': n_boundary / max(n_post_flips, 1),

        # 方向场
        'n_dir_pos': n_dir_pos,
        'n_dir_neg': n_dir_neg,
        'dir_balance': float(dir_balance),
        'sealed_dir_balance': sealed_dir_balance,

        # 脉冲响应
        'early_hw_var': float(early_var),
        'late_hw_var': float(late_var),
        'is_pulse': is_pulse,

        # 慢度指标
        'correlation_length': correlation_length,

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
        early_hw_vars = [m['early_hw_var'] for m in group]
        late_hw_vars = [m['late_hw_var'] for m in group]

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
            'early_hw_var_mean': float(np.mean(early_hw_vars)) if early_hw_vars else 0.0,
            'late_hw_var_mean': float(np.mean(late_hw_vars)) if late_hw_vars else 0.0,
        }
        analysis['by_condition'][label] = cs

    # 排序 (按 post_flip_rate)
    sorted_conds = sorted(analysis['by_condition'].items(),
                          key=lambda x: x[1]['post_flip_rate_mean'],
                          reverse=True)
    analysis['ranked_by_activity'] = [
        {'label': label,
         'post_flip_rate': cs['post_flip_rate_mean'],
         'boundary_ratio': cs['boundary_flip_ratio_mean'],
         'over_sealed_rate': cs['over_sealed_rate'],
         'hw_var': cs['post_hw_var_mean'],
         'pulse_rate': cs['pulse_rate']}
        for label, cs in sorted_conds
    ]

    return analysis


# ============================================================
# 打印结果
# ============================================================
def print_results(analysis: dict):
    print(f"\n{'=' * 110}")
    print("Phase 15 Path A2: Step Binding — 结果分析 (exp_164)")
    print("=" * 110)

    by_cond = analysis['by_condition']
    ranked = analysis['ranked_by_activity']

    # 排名表
    header = (f"{'Condition':24s} {'Seal':>6s} {'FlipRate':>8s} {'Bound%':>7s} "
              f"{'Dist':>5s} {'HWvar':>7s} {'OverS':>6s} {'Pulse':>6s} {'ξ':>5s}")
    print(f"\n{header}")
    print("-" * 110)

    for item in ranked:
        label = item['label']
        cs = by_cond[label]
        se = f"{cs['seal_ratio']*100:4.0f}%" if 'seal_ratio' in cs else 'N/A'
        fr = f"{cs['post_flip_rate_mean']:.4f}"
        br = f"{cs['boundary_flip_ratio_mean']*100:5.1f}%"
        dd = f"{cs['mean_flip_dist_mean']:.1f}"
        hv = f"{cs['post_hw_var_mean']:.3f}"
        os_ = f"{cs['over_sealed_rate']*100:4.0f}%"
        pu = f"{cs['pulse_rate']*100:4.0f}%"
        xi = f"{cs['correlation_length_mean']:.0f}"
        print(f"  {label:24s} {se:>6s} {fr:>8s} {br:>7s} {dd:>5s} {hv:>7s} {os_:>6s} {pu:>6s} {xi:>5s}")

    # 分析
    print(f"\n{'=' * 110}")
    print("Analysis")
    print("=" * 110)

    baseline = by_cond.get('baseline', {})
    bl_flip = baseline.get('post_flip_rate_mean', 0.0)
    bl_bound = baseline.get('boundary_flip_ratio_mean', 0.0)
    bl_var = baseline.get('post_hw_var_mean', 0.0)
    bl_over = baseline.get('over_sealed_rate', 0.0)

    print(f"\n  Baseline (no feedback):")
    print(f"    flip_rate={bl_flip:.4f}, boundary%={bl_bound*100:.1f}%, "
          f"HWvar={bl_var:.3f}, over_sealed={bl_over*100:.0f}%")

    # 按 threshold 分组分析
    print(f"\n  --- By Threshold ---")
    for th in THRESHOLDS:
        th_conds = [cs for lbl, cs in by_cond.items()
                    if lbl.startswith(f'step_th{th}_')]
        if not th_conds:
            continue
        avg_flip = np.mean([c['post_flip_rate_mean'] for c in th_conds])
        avg_bound = np.mean([c['boundary_flip_ratio_mean'] for c in th_conds])
        avg_over = np.mean([c['over_sealed_rate'] for c in th_conds])
        avg_hwvar = np.mean([c['post_hw_var_mean'] for c in th_conds])
        avg_pulse = np.mean([c['pulse_rate'] for c in th_conds])
        print(f"    threshold={th:2d}: flip_rate={avg_flip:.4f}, "
              f"boundary%={avg_bound*100:.1f}%, "
              f"over_sealed%={avg_over*100:.0f}%, HWvar={avg_hwvar:.3f}, "
              f"pulse%={avg_pulse*100:.0f}%")

    # 按 feedback_strength 分组分析
    print(f"\n  --- By Feedback Strength ---")
    for fs in FEEDBACK_STRENGTHS:
        fs_conds = [cs for lbl, cs in by_cond.items()
                    if lbl.endswith(f'_fs{fs}')]
        if not fs_conds:
            continue
        avg_flip = np.mean([c['post_flip_rate_mean'] for c in fs_conds])
        avg_bound = np.mean([c['boundary_flip_ratio_mean'] for c in fs_conds])
        avg_over = np.mean([c['over_sealed_rate'] for c in fs_conds])
        avg_pulse = np.mean([c['pulse_rate'] for c in fs_conds])
        print(f"    fs={fs:.1f}: flip_rate={avg_flip:.4f}, "
              f"boundary%={avg_bound*100:.1f}%, "
              f"over_sealed%={avg_over*100:.0f}%, pulse%={avg_pulse*100:.0f}%")

    # 最佳条件对比
    best = ranked[0] if ranked else {'label': 'None', 'post_flip_rate': 0}
    best_label = best['label']
    best_flip = best['post_flip_rate']
    best_bound = by_cond.get(best_label, {}).get('boundary_flip_ratio_mean', 0)
    best_over = by_cond.get(best_label, {}).get('over_sealed_rate', 0)
    best_hwvar = by_cond.get(best_label, {}).get('post_hw_var_mean', 0)
    best_pulse = by_cond.get(best_label, {}).get('pulse_rate', 0)

    print(f"\n  Best condition: {best_label}")
    print(f"    flip_rate={best_flip:.4f} vs baseline={bl_flip:.4f} "
          f"(+{((best_flip/max(bl_flip,1e-10))-1)*100:.0f}%)")
    print(f"    boundary%={best_bound*100:.1f}% vs baseline={bl_bound*100:.1f}%")
    print(f"    over_sealed={best_over*100:.0f}% vs baseline={bl_over*100:.0f}%")
    print(f"    HWvar={best_hwvar:.3f} vs baseline={bl_var:.3f}")
    print(f"    pulse%={best_pulse*100:.0f}%")

    # 最差条件（可能完全抑制了所有活动）
    worst = ranked[-1] if len(ranked) > 1 else best
    print(f"\n  Worst (most suppressed): {worst['label']}")
    print(f"    flip_rate={worst['post_flip_rate']:.4f}")

    # 成功判断
    print(f"\n  {'=' * 60}")
    print(f"  Hypothesis Verdict")
    print(f"  {'=' * 60}")

    # 强成功: 出现至少 1 次二次密封事件
    max_over = max(cs['over_sealed_rate'] for cs in by_cond.values())
    if max_over > 0.2:
        print(f"  [STRONG] H15-A3 (Step): OVER-SEALED DETECTED — "
              f"max_over_sealed_rate={max_over*100:.0f}%")
    else:
        print(f"  [NO] H15-A3 (Step): No secondary sealing detected — "
              f"max_over_sealed_rate={max_over*100:.0f}%")

    # 中等成功: boundary flip ratio 差异 > 2σ vs baseline
    best_bound_z = (best_bound - bl_bound) / max(
        by_cond.get(best_label, {}).get('boundary_flip_ratio_std', 0.1), 0.01)
    if best_bound_z > 2.0:
        print(f"  [MEDIUM] H15-A4 (Range): Boundary enrichment detected — "
              f"z={best_bound_z:.2f}")
    else:
        print(f"  [NO] H15-A4 (Range): No significant boundary enrichment — "
              f"z={best_bound_z:.2f}")

    # 弱成功: dir_balance 偏离 0.5
    max_dir_dev = max(abs(cs['dir_balance_mean'] - 0.5) for cs in by_cond.values())
    if max_dir_dev >= 0.1:
        print(f"  [WEAK] Direction field gradient detected — "
              f"max_dir_dev={max_dir_dev:.3f}")
    else:
        print(f"  [WEAK] No direction field gradient — "
              f"max_dir_dev={max_dir_dev:.3f}")

    # 脉冲检测
    max_pulse_rate = max(cs['pulse_rate'] for cs in by_cond.values())
    if max_pulse_rate > 0:
        print(f"  [PULSE] Step-induced pulses detected — "
              f"max_pulse_rate={max_pulse_rate*100:.0f}%")

    # 综合结论
    all_no = (max_over <= 0.2 and best_bound_z <= 2.0 and max_dir_dev < 0.1 and max_pulse_rate == 0)
    if all_no:
        print(f"\n  === FINAL: Path A2 REJECTED — Step binding fails to break dead order ===")
        print(f"  Implication: Even the most discontinuous nonlinearity (hard threshold)")
        print(f"  cannot overcome the topological invariance of dead order.")
        print(f"  → Proceeding to Path A3 (Cooperative Binding / exp_165)")
    else:
        print(f"\n  === FINAL: Path A2 SHOWS SIGNAL — further investigation warranted ===")

    print(f"\n  Ran {sum(cs['n_runs'] for cs in by_cond.values())} runs across "
          f"{len(by_cond)} conditions")


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    print("=" * 110)
    print("Phase 15 Path A2: Step Binding (exp_164)")
    print("=" * 110)
    print(f"  N={N}, steps={TOTAL_STEPS}, sample_interval={SAMPLE_INTERVAL}")
    print(f"  Runs per condition: {N_RUNS}")
    print(f"  Conditions: {len(FEEDBACK_CONDITIONS)} (1 baseline + {len(FEEDBACK_CONDITIONS)-1} step)")
    print(f"  Total runs: {len(FEEDBACK_CONDITIONS) * N_RUNS}")
    print(f"  Step: bias[i] = fs if dist <= threshold else 0.0")
    print(f"  thresholds ∈ {THRESHOLDS}  fs ∈ {FEEDBACK_STRENGTHS}")
    print("=" * 110)

    all_metrics = []
    t_start = time.time()
    total_runs = len(FEEDBACK_CONDITIONS) * N_RUNS
    run_count = 0

    # 先 baseline，再 step 条件
    baseline_cond = [c for c in FEEDBACK_CONDITIONS if c['label'] == 'baseline']
    step_conds = [c for c in FEEDBACK_CONDITIONS if c['label'] != 'baseline']

    for cond in baseline_cond + step_conds:
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

    # ---- 分析 ----
    analysis = analyze_results(all_metrics)

    # ---- 保存 ----
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR,
                               f"exp164_phase15_a2_step_{timestamp}.json")

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
            'thresholds': THRESHOLDS,
            'feedback_strengths': FEEDBACK_STRENGTHS,
            'timestamp': timestamp,
            'experiment': 'exp_164_phase15_a2_step_binding',
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
    print_results(analysis)

    return save_data, result_file


if __name__ == '__main__':
    run_experiment()
