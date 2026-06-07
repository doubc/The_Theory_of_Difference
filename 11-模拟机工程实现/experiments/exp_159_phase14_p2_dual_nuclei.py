"""
exp_159 — Phase 14 P2: Dual-Nuclei Boundary Coupling

科学问题：
  Phase 14 P1 (exp_158) 确认时间结构化注入不足以打破死秩序。
  P2 探索多个密封核通过耦合相互作用时，边界区域是否产生新的活性。

核心假设：
  H14-4（边界假设）：两个独立密封的子空间通过耦合相互作用时，
    边界区域（子空间交界附近）会产生比单核系统更高的差异活跃度。

  H14-5（不对称假设）：不对称耦合（单向）比对称耦合（双向）
    产生更强的边界效应，因为方向性创造了梯度。

实验设计：
  单个 SpatialLongRangeEvolver N=96（两个连续块：A=0-47, B=48-95）。
  通过 step_callback 实现耦合：基于对方 HW 状态写入 coupling_bias。
  耦合强度扫描 + 方向扫描。

测量指标：
  - 边界区域（index 43-52）的 HW 方差 vs 内部区域
  - 各半密封时间
  - 耦合 vs 非耦合的密封率差异
  - 边界区域的 flip 统计

用法：
  python experiments/exp_159_phase14_p2_dual_nuclei.py
"""

import sys, os, json, datetime, time
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
N_TOTAL = 96                # 48 + 48 = 96 总比特
N_HALF = N_TOTAL // 2       # 每个子空间大小
TOTAL_STEPS = 600            # 总步数（密封在~100-200步，足够后密封分析窗口）
SAMPLE_INTERVAL = 25
N_RUNS = 4                   # 每条件运行次数
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# 子空间边界定义
BOUNDARY_RADIUS = 5
BOUNDARY_INDICES = list(range(N_HALF - BOUNDARY_RADIUS, N_HALF + BOUNDARY_RADIUS))
INTERIOR_A = list(range(0, N_HALF - BOUNDARY_RADIUS))
INTERIOR_B = list(range(N_HALF + BOUNDARY_RADIUS, N_TOTAL))

# ============================================================
# 耦合条件定义
# ============================================================
# 6 个条件: 3 耦合强度 × 2 方向

COUPLING_MODES = []

# isolated (无耦合基线)
COUPLING_MODES.append({
    'label': 'isolated',
    'strength': 0.0,
    'bidirectional': False,
})

# bidirectional coupling
for strength in [0.3, 1.0, 3.0]:
    COUPLING_MODES.append({
        'label': f'bidirectional_{strength}',
        'strength': strength,
        'bidirectional': True,
    })

# unidirectional (A→B only)
for strength in [0.3, 1.0, 3.0]:
    COUPLING_MODES.append({
        'label': f'unidirectional_{strength}',
        'strength': strength,
        'bidirectional': False,
    })


# ============================================================
# 度量工具函数
# ============================================================

def compute_boundary_activity(hw_traj_a: np.ndarray, hw_traj_b: np.ndarray,
                               half_indices: list) -> dict:
    """计算边界活性指标

    Args:
        hw_traj_a: 子空间 A 的 HW 历史
        hw_traj_b: 子空间 B 的 HW 历史
        half_indices: 子空间 A 的索引范围

    Returns:
        dict with boundary metrics
    """
    # 密封检测: HW 稳定在 24 附近（~N/2 的 50%）
    def _find_seal_step(hw: np.ndarray, target: float = 24.0,
                        window: int = 50, tol: float = 2.0) -> int:
        for i in range(len(hw) - window):
            seg = hw[i:i + window]
            if abs(seg.mean() - target) < tol and seg.var() < 1.0:
                return i + window // 2
        return -1

    seal_step_a = _find_seal_step(hw_traj_a)
    seal_step_b = _find_seal_step(hw_traj_b)

    # 密封后的方差
    post_seal_a = hw_traj_a[seal_step_a:] if seal_step_a >= 0 else hw_traj_a[-200:]
    post_seal_b = hw_traj_b[seal_step_b:] if seal_step_b >= 0 else hw_traj_b[-200:]

    post_var_a = float(post_seal_a.var()) if len(post_seal_a) > 1 else 0.0
    post_var_b = float(post_seal_b.var()) if len(post_seal_b) > 1 else 0.0

    # 密封时间差（异步性）
    seal_time_diff = abs(seal_step_a - seal_step_b) if seal_step_a >= 0 and seal_step_b >= 0 else -1

    # 交叉相关性（两个半段的 HW 相关性）
    min_len = min(len(hw_traj_a), len(hw_traj_b))
    if min_len > 10:
        cross_corr = float(np.corrcoef(hw_traj_a[:min_len], hw_traj_b[:min_len])[0, 1])
        if np.isnan(cross_corr):
            cross_corr = 0.0
    else:
        cross_corr = 0.0

    return {
        'seal_step_a': seal_step_a,
        'seal_step_b': seal_step_b,
        'seal_time_diff': seal_time_diff,
        'post_var_a': post_var_a,
        'post_var_b': post_var_b,
        'cross_correlation': cross_corr,
    }


def compute_xi_traj(local_hw: np.ndarray, global_hw: np.ndarray,
                     window: int = 50) -> float:
    """估计相关性长度（基于局部 vs 全局 HW 方差的比值）

    当边界区域 HW 方差显著大于内部区域方差时，ξ 增大。
    """
    min_len = min(len(local_hw), len(global_hw))
    if min_len < window * 3:
        return 0.0
    local_var = local_hw[-200:].var() if len(local_hw) > 200 else local_hw.var()
    global_var = global_hw[-200:].var() if len(global_hw) > 200 else global_hw.var()

    if global_var < 1e-6:
        return 0.0
    # ξ 估计: 局部/全局方差比 * 边界宽度
    return min(10.0, (local_var / global_var) * BOUNDARY_RADIUS * 2)


# ============================================================
# 耦合回调工厂
# ============================================================
def make_coupling_callback(strength: float, bidirectional: bool):
    """创建耦合 step_callback。

    耦合机制（Phase 11 P4 fix 样式）：
    - 计算 A 和 B 的归一化 HW
    - coupling_bias[A] = strength * (hw_B_norm - hw_A_norm)
    - coupling_bias[B] = strength * (hw_A_norm - hw_B_norm)  (仅 bidirectional)
    """
    def _callback(step: int, state: torch.Tensor,
                  snapshot: object, constraints: object) -> None:
        if strength <= 0.0:
            return

        N = state.numel()
        half = N // 2

        hw_a = state[:half].sum().float().item()
        hw_b = state[half:].sum().float().item()
        hw_a_norm = hw_a / half
        hw_b_norm = hw_b / half

        # 写入 coupling_bias
        bias = torch.zeros(N, device=constraints.coupling_bias.device,
                           dtype=constraints.coupling_bias.dtype)

        # A 的 bias: B 比 A 活跃时 A 获得正 bias（被激活）
        bias_a = strength * (hw_b_norm - hw_a_norm)
        bias[:half] = bias_a

        if bidirectional:
            # B 的 bias: A 比 B 活跃时 B 获得正 bias
            bias_b = strength * (hw_a_norm - hw_b_norm)
            bias[half:] = bias_b
        else:
            # unidirectional A→B: B 始终被激活
            bias[half:] = strength * (hw_a_norm - hw_b_norm) * 1.0

        bias.clamp_(-1.0, 1.0)
        constraints.coupling_bias.copy_(bias)

    return _callback


# ============================================================
# 单次运行
# ============================================================
def run_single(mode: dict, run_id: int, verbose: bool = False) -> dict:
    """单次实验运行"""
    label = mode['label']
    strength = mode['strength']
    bidirectional = mode['bidirectional']

    seed = run_id * 31337 + 17 + hash(label) % 100000
    rng = np.random.RandomState(seed % (2**31))
    torch.manual_seed(seed % (2**31))

    # 初始化: 每个半段有 ~8 个 1
    initial = torch.zeros(N_TOTAL)
    for half_start in [0, N_HALF]:
        n_ones = max(3, rng.randint(4, min(10, N_HALF // 2)))
        indices = rng.choice(N_HALF, size=n_ones, replace=False)
        initial[indices + half_start] = 1.0

    # 创建回调
    callback = make_coupling_callback(strength, bidirectional)

    evolver = SpatialLongRangeEvolver(
        N=N_TOTAL,
        total_steps=TOTAL_STEPS,
        sample_interval=SAMPLE_INTERVAL,
        partial_sealing=False,
    )

    t0 = time.time()
    # with suppress_stdout():
    # 注意: 在 -u (unbuffered) 模式下使用 suppress_stdout 可能导致 stdout 缓冲区问题
    # 改用自定义 -q 参数或直接运行
    with contextlib.redirect_stdout(open(os.devnull, 'w')):
        result = evolver.run(initial_state=initial, verbose=False,
                             step_callback=callback)
    elapsed = time.time() - t0

    # ---- 提取按半段的数据 ----
    hw_traj = np.array(evolver.hamming_weight_history)  # (T,) 全局 HW

    # 从 snapshots 获取每个半段的 HW
    hw_a_traj = []
    hw_b_traj = []
    for snap in evolver.snapshots:
        s = snap.state
        hw_a_traj.append(int(s[:N_HALF].sum().item()))
        hw_b_traj.append(int(s[N_HALF:].sum().item()))
    hw_a_traj = np.array(hw_a_traj)
    hw_b_traj = np.array(hw_b_traj)

    # 边界活动: 从 snapshots 中计算边界区域 HW
    boundary_hw_traj = []
    interior_a_hw_traj = []
    interior_b_hw_traj = []
    for snap in evolver.snapshots:
        s = snap.state
        boundary_hw = s[BOUNDARY_INDICES].sum().item()
        int_a_hw = s[INTERIOR_A].sum().item() if INTERIOR_A else 0
        int_b_hw = s[INTERIOR_B].sum().item() if INTERIOR_B else 0
        boundary_hw_traj.append(int(boundary_hw))
        interior_a_hw_traj.append(int(int_a_hw))
        interior_b_hw_traj.append(int(int_b_hw))

    boundary_hw_traj = np.array(boundary_hw_traj)
    interior_a_hw_traj = np.array(interior_a_hw_traj)
    interior_b_hw_traj = np.array(interior_b_hw_traj)

    # ---- 度量 ----
    # 各半段的密封分析（基于全局 HW 轨迹映射到子空间）
    half_metrics = compute_boundary_activity(hw_a_traj, hw_b_traj, list(range(N_HALF)))

    # 边界 vs 内部方差（密封后最后三分之一）
    n_third = len(boundary_hw_traj) // 3
    last_third_boundary = boundary_hw_traj[-n_third:] if n_third > 0 else boundary_hw_traj
    last_third_int_a = interior_a_hw_traj[-n_third:] if n_third > 0 and len(interior_a_hw_traj) > 0 else np.array([0.0])
    last_third_int_b = interior_b_hw_traj[-n_third:] if n_third > 0 and len(interior_b_hw_traj) > 0 else np.array([0.0])

    boundary_var = float(last_third_boundary.var()) if len(last_third_boundary) > 1 else 0.0
    interior_var_a = float(last_third_int_a.var()) if len(last_third_int_a) > 1 else 0.0
    interior_var_b = float(last_third_int_b.var()) if len(last_third_int_b) > 1 else 0.0
    interior_var_mean = (interior_var_a + interior_var_b) / 2

    # 边界/内部方差比
    var_ratio = boundary_var / max(interior_var_mean, 1e-6)

    # 边界 HW 平均值
    boundary_mean = float(last_third_boundary.mean()) if len(last_third_boundary) > 0 else 0.0

    # 相关性长度估计
    xi_est = compute_xi_traj(
        boundary_hw_traj,
        (interior_a_hw_traj + interior_b_hw_traj) / 2 if len(interior_a_hw_traj) > 0 and len(interior_b_hw_traj) > 0 else boundary_hw_traj
    )

    # 密封率（两个半段都密封）
    both_sealed = half_metrics['seal_step_a'] >= 0 and half_metrics['seal_step_b'] >= 0

    # 最终状态密封情况
    sealed = evolver.constraints.sealed
    n_sealed_bits = len(evolver.constraints.sealed_bits)

    # ---- flip 在边界区域的密度 ----
    # (从 flip_history 中统计边界 flip 占比)
    # flip_history 记录了每次 flip 的 index
    flip_arr = np.array(evolver.flip_history)
    n_boundary_flips = np.sum((flip_arr >= (N_HALF - BOUNDARY_RADIUS)) &
                               (flip_arr < (N_HALF + BOUNDARY_RADIUS)))
    total_flips = len(flip_arr[flip_arr >= 0])
    boundary_flip_ratio = n_boundary_flips / max(total_flips, 1)
    # 边界区域占比: (2*BOUNDARY_RADIUS) / N_TOTAL
    expected_boundary_ratio = (2 * BOUNDARY_RADIUS) / N_TOTAL
    flip_enrichment = boundary_flip_ratio / max(expected_boundary_ratio, 1e-6)

    return {
        'mode_label': label,
        'strength': strength,
        'bidirectional': bidirectional,
        'run_id': run_id,
        'seed': seed,

        # 密封信息
        'sealed': sealed,
        'n_sealed_bits': n_sealed_bits,
        'both_sealed': both_sealed,
        'seal_step_a': half_metrics['seal_step_a'],
        'seal_step_b': half_metrics['seal_step_b'],
        'seal_time_diff': half_metrics['seal_time_diff'],

        # 边界 vs 内部差异
        'boundary_var': boundary_var,
        'interior_var_a': interior_var_a,
        'interior_var_b': interior_var_b,
        'interior_var_mean': interior_var_mean,
        'var_ratio': var_ratio,
        'boundary_mean': boundary_mean,
        'xi_est': xi_est,

        # 交叉相关性
        'cross_correlation': half_metrics['cross_correlation'],

        # Flip 统计
        'n_boundary_flips': int(n_boundary_flips),
        'total_flips': total_flips,
        'boundary_flip_ratio': float(boundary_flip_ratio),
        'flip_enrichment': float(flip_enrichment),

        # 性能
        'elapsed_sec': round(elapsed, 2),
    }


# ============================================================
# 分析
# ============================================================
def analyze_results(all_metrics: list) -> dict:
    """批量分析所有条件的结果"""
    by_mode = {}
    for m in all_metrics:
        label = m['mode_label']
        if label not in by_mode:
            by_mode[label] = []
        by_mode[label].append(m)

    analysis = {'by_mode': {}}

    for label in sorted(by_mode.keys()):
        group = by_mode[label]
        n_total = len(group)

        both_sealed = sum(1 for m in group if m['both_sealed'])
        both_sealed_rate = both_sealed / n_total

        var_ratios = [m['var_ratio'] for m in group]
        boundary_vars = [m['boundary_var'] for m in group]
        interior_vars = [m['interior_var_mean'] for m in group]
        flip_enrichments = [m['flip_enrichment'] for m in group]
        cross_corrs = [m['cross_correlation'] for m in group]
        seal_time_diffs = [m['seal_time_diff'] for m in group if m['seal_time_diff'] >= 0]
        xi_ests = [m['xi_est'] for m in group]
        n_boundary_flips = [m['n_boundary_flips'] for m in group]

        # 边界增强检测: var_ratio > 2.0
        n_boundary_enhanced = sum(1 for v in var_ratios if v > 2.0)
        enhancement_rate = n_boundary_enhanced / n_total

        # Flip 富集检测: flip_enrichment > 1.5
        n_flip_enhanced = sum(1 for f in flip_enrichments if f > 1.5)
        flip_enhancement_rate = n_flip_enhanced / n_total

        cs = {
            'n_runs': n_total,
            'both_sealed_rate': both_sealed_rate,
            'boundary_var_mean': float(np.mean(boundary_vars)) if boundary_vars else np.nan,
            'interior_var_mean': float(np.mean(interior_vars)) if interior_vars else np.nan,
            'var_ratio_mean': float(np.mean(var_ratios)) if var_ratios else np.nan,
            'var_ratio_std': float(np.std(var_ratios)) if var_ratios else np.nan,
            'boundary_enhancement_rate': enhancement_rate,
            'flip_enrichment_mean': float(np.mean(flip_enrichments)) if flip_enrichments else np.nan,
            'flip_enrichment_std': float(np.std(flip_enrichments)) if flip_enrichments else np.nan,
            'flip_enhancement_rate': flip_enhancement_rate,
            'n_boundary_flips_mean': float(np.mean(n_boundary_flips)) if n_boundary_flips else 0,
            'cross_corr_mean': float(np.mean(cross_corrs)) if cross_corrs else np.nan,
            'seal_time_diff_mean': float(np.mean(seal_time_diffs)) if seal_time_diffs else np.nan,
            'xi_est_mean': float(np.mean(xi_ests)) if xi_ests else np.nan,
        }
        analysis['by_mode'][label] = cs

    # 排序: 按边界增强率降序
    sorted_modes = sorted(analysis['by_mode'].items(),
                          key=lambda x: x[1]['boundary_enhancement_rate'],
                          reverse=True)
    analysis['ranked_by_boundary_activity'] = [
        (label, cs['boundary_enhancement_rate'], cs['var_ratio_mean'])
        for label, cs in sorted_modes
    ]

    return analysis


# ============================================================
# 打印结果
# ============================================================
def print_results(analysis: dict):
    """打印分析结果"""
    print(f"\n{'=' * 90}")
    print("Phase 14 P2: 双核边界耦合 — 结果分析 (exp_159)")
    print("=" * 90)

    by_mode = analysis['by_mode']
    ranked = analysis['ranked_by_boundary_activity']

    # 排名表
    header = f"{'Condition':28s} {'BothSeal':>8s} {'BdryVar':>8s} {'IntVar':>8s} {'VarRat':>8s} {'EnhRate':>8s}"
    header += f" {'FlipEnr':>8s} {'CCorr':>8s}"
    print(f"\n{header}")
    print("-" * 90)

    for label, enh_rate, var_ratio in ranked:
        cs = by_mode[label]
        both_str = f"{cs['both_sealed_rate']*100:5.1f}%"
        bv_str = f"{cs['boundary_var_mean']:.3f}" if not np.isnan(cs['boundary_var_mean']) else '  N/A'
        iv_str = f"{cs['interior_var_mean']:.3f}" if not np.isnan(cs['interior_var_mean']) else '  N/A'
        vr_str = f"{cs['var_ratio_mean']:.2f}" if not np.isnan(cs['var_ratio_mean']) else '  N/A'
        en_str = f"{enh_rate*100:5.1f}%"
        fl_str = f"{cs['flip_enrichment_mean']:.2f}" if not np.isnan(cs['flip_enrichment_mean']) else '  N/A'
        cc_str = f"{cs['cross_corr_mean']:.3f}" if not np.isnan(cs['cross_corr_mean']) else '  N/A'

        print(f"  {label:28s} {both_str:>8s} {bv_str:>8s} {iv_str:>8s} {vr_str:>8s} {en_str:>8s} {fl_str:>8s} {cc_str:>8s}")

    # 结论
    print(f"\n{'=' * 90}")
    print("Conclusions")
    print("=" * 90)

    # 找对照组的边界增强率
    isolated_enh = by_mode.get('isolated', {}).get('boundary_enhancement_rate', 0)
    isolated_var = by_mode.get('isolated', {}).get('var_ratio_mean', 1.0)

    # 检查是否有耦合条件 > 对照
    best_coupled_enh = max([cs['boundary_enhancement_rate']
                           for label, cs in by_mode.items()
                           if label != 'isolated'],
                          default=0.0)
    best_coupled_var = max([cs['var_ratio_mean']
                           for label, cs in by_mode.items()
                           if label != 'isolated' and not np.isnan(cs['var_ratio_mean'])],
                          default=0.0)

    if best_coupled_enh > isolated_enh + 0.2:
        print(f"[OK] H14-4 (boundary enhancement): CONFIRMED — coupling enhances boundary activity")
        print(f"   Best coupled enhancement: {best_coupled_enh*100:.1f}% vs isolated: {isolated_enh*100:.1f}%")
        print(f"   Best coupled var_ratio: {best_coupled_var:.2f} vs isolated: {isolated_var:.2f}")
    else:
        print(f"[NO] H14-4 (boundary enhancement): NOT CONFIRMED — coupling does not significantly enhance boundary activity")
        print(f"   Best coupled enhancement: {best_coupled_enh*100:.1f}% vs isolated: {isolated_enh*100:.1f}%")

    # 双向 vs 单向
    bidir_rates = [cs['boundary_enhancement_rate']
                   for label, cs in by_mode.items() if 'bidirectional' in label]
    unidir_rates = [cs['boundary_enhancement_rate']
                    for label, cs in by_mode.items() if 'unidirectional' in label]

    if bidir_rates and unidir_rates:
        avg_bidir = np.mean(bidir_rates)
        avg_unidir = np.mean(unidir_rates)
        if avg_bidir > avg_unidir + 0.1:
            print(f"[OK] H14-5 (direction): Bidirectional stronger ({avg_bidir*100:.1f}% > {avg_unidir*100:.1f}%)")
        elif avg_unidir > avg_bidir + 0.1:
            print(f"[OK] H14-5 (direction): Unidirectional stronger ({avg_unidir*100:.1f}% > {avg_bidir*100:.1f}%)")
        else:
            print(f"[NO] H14-5 (direction): No significant difference ({avg_bidir*100:.1f}% vs {avg_unidir*100:.1f}%)")

    # 总体结论
    all_enh_rates = [cs['boundary_enhancement_rate'] for cs in by_mode.values()]
    max_enh = max(all_enh_rates)
    if max_enh > 0.5:
        print(f"\n[OK] Dual-nuclei boundary: significant activity enhancement (max {max_enh*100:.1f}%)")
        print("  -> Continue P2: asymmetric nuclei experiment (exp_160)")
    elif max_enh > 0.2:
        print(f"\n[WARN] Dual-nuclei boundary: mild activity enhancement (max {max_enh*100:.1f}%)")
        print("  -> Continue P2: but adjust parameters or asymmetry")
    else:
        print(f"\n[NO] Dual-nuclei boundary: NO significant activity enhancement (max {max_enh*100:.1f}%)")
        print("  -> Consider advancing to P3: active constraint shaping")


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    print("=" * 90)
    print("Phase 14 P2: 双核边界耦合 (exp_159)")
    print("=" * 90)
    print(f"  N={N_TOTAL} (2×{N_HALF}), steps={TOTAL_STEPS}")
    print(f"  Boundary radius: {BOUNDARY_RADIUS} bits on each side")
    print(f"  Runs per condition: {N_RUNS}")
    print(f"  Conditions: {len(COUPLING_MODES)}")
    print(f"  Total runs: {len(COUPLING_MODES) * N_RUNS}")
    print("=" * 90)

    print("\n耦合条件:")
    for i, mode in enumerate(COUPLING_MODES):
        extra = " (baseline)" if mode['strength'] == 0 else ""
        print(f"  [{i+1}] {mode['label']}{extra}")

    all_metrics = []
    t_start = time.time()
    total_runs = len(COUPLING_MODES) * N_RUNS
    run_count = 0

    for mode in COUPLING_MODES:
        label = mode['label']
        print(f"\n--- {label} ---")

        for run_id in range(N_RUNS):
            metrics = run_single(mode, run_id)
            all_metrics.append(metrics)
            run_count += 1

            if (run_id + 1) % 2 == 0 or run_id == N_RUNS - 1:
                pct = run_count / total_runs * 100
                enhanced = sum(1 for m in all_metrics
                               if m.get('var_ratio', 0) > 2.0)
                elapsed_so_far = time.time() - t_start
                rate = run_count / max(1, elapsed_so_far)
                eta = (total_runs - run_count) / max(rate, 0.001)
                print(f"    {run_id+1}/{N_RUNS} runs | total {run_count}/{total_runs} "
                      f"({pct:.0f}%) | enhanced:{enhanced} | "
                      f"{elapsed_so_far:.0f}s elapsed, ~{eta:.0f}s remaining")

    t_total = time.time() - t_start
    print(f"\nTotal time: {t_total:.0f}s ({t_total/60:.1f}min)")

    # ---- 分析 ----
    analysis = analyze_results(all_metrics)

    # ---- Save FIRST ---- (before print, avoid data loss on encoding crash)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR,
                               f"exp159_phase14_p2_dual_nuclei_{timestamp}.json")

    save_metrics = []
    import json as _json
    for m in all_metrics:
        sm = {}
        for k, v in m.items():
            if isinstance(v, (np.integer,)):
                sm[k] = int(v)
            elif isinstance(v, (np.floating,)):
                sm[k] = float(v)
            elif isinstance(v, np.ndarray):
                sm[k] = v.tolist()
            elif isinstance(v, dict):
                sm[k] = {sk: float(sv) if isinstance(sv, (np.floating,)) else
                         int(sv) if isinstance(sv, (np.integer,)) else
                         sv for sk, sv in v.items()}
            else:
                sm[k] = v
        save_metrics.append(sm)

    save_data = {
        'params': {
            'N_total': N_TOTAL,
            'N_half': N_HALF,
            'total_steps': TOTAL_STEPS,
            'sample_interval': SAMPLE_INTERVAL,
            'n_runs': N_RUNS,
            'boundary_radius': BOUNDARY_RADIUS,
            'timestamp': timestamp,
            'experiment': 'exp_159_phase14_p2_dual_nuclei',
        },
        'analysis': {
            'by_mode': {k: {sk: sv for sk, sv in v.items()}
                       for k, v in analysis['by_mode'].items()},
            'ranked_by_boundary_activity': analysis['ranked_by_boundary_activity'],
        },
        'metrics': save_metrics,
    }

    try:
        with open(result_file, 'w', encoding='utf-8') as f:
            _json.dump(save_data, f, indent=2, default=str)
        print(f"\n=== Results saved to: {result_file}")
    except Exception as e:
        print(f"\n[WARN] Save failed: {e}")
        backup_file = os.path.join(os.path.expanduser('~'),
                                   f'exp159_backup_{timestamp}.json')
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                _json.dump(save_data, f, indent=2, default=str)
            print(f"  Fallback saved to: {backup_file}")
        except Exception as e2:
            print(f"  Fallback also failed: {e2}")

    # ---- Print results ---- (after save, with encoding fallback)
    try:
        print_results(analysis)
    except UnicodeEncodeError:
        # Fallback: capture and ASCII-encode output
        import io
        _buf = io.StringIO()
        _old = sys.stdout
        sys.stdout = _buf
        print_results(analysis)
        sys.stdout = _old
        _text = _buf.getvalue()
        _safe = _text.encode('ascii', 'replace').decode('ascii')
        print(_safe)
    
    return save_data


if __name__ == '__main__':
    run_experiment()