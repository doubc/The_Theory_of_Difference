"""
exp_158 — Phase 14 P1: 时间结构化注入

科学问题：空间模板（隔离密封、模板增长）不是 L2 涌现的充分条件。
          时间结构化的差异注入是否可以打破死秩序？

背景：
  Phase 13 发现密封产生「死秩序」—— HW 稳定、方差为零、无记忆信号。
  三种被动策略均失败：被动等待（exp_156）、N 扩张（exp_156 H2）、空间模板（exp_157）。

核心假设：
  H14-1（脉冲假设）：脉冲式差异注入（短时 burst + 静默交替）比恒定注入更有利于 L2 涌现。
           脉冲创造「差异密度梯度」，使系统可以「感受」密度变化。

  H14-2（频率假设）：L2 涌现存在最理想的脉冲频率——太快退化为恒定注入，
           太慢系统退化回 L0。

  H14-3（幅度假设）：脉冲幅度超过某个阈值才能触发 L2——小幅度被密封结构吸收，
           大幅度突破密封。

  H14-4（结构记忆假设）：脉冲注入后，系统残留的活跃度模式（HW 轨迹）不是随机噪声，
           而是受密封结构调制的结构化响应。

实验设计：
  单子空间（N=48），运行至密封，然后切换注入模式。

用法：
  python experiments/exp_158_phase14_p1_time_structured_injection.py
"""

import sys, os, json, datetime, time
import numpy as np
import torch
import contextlib


@contextlib.contextmanager
def suppress_stdout():
    """上下文管理器：临时抑制 stdout 输出"""
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
N_BASE = 48
TOTAL_STEPS = 400            # 密封前的主运行
POST_SEAL_STEPS = 400        # 密封后继续运行步数
N_RUNS = 8                   # 每个模式/参数组合运行次数
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 注入模式定义
# ============================================================
# 每个模式是一个 (name, post_seal_config) 元组
# 对照：恒定注入（标准 A8 驱动）
# 脉冲：burst 步数 + silent 步数交替
# 斜坡：从 0 线性增至 max 再骤降
# 随机：Poisson 过程

INJECTION_MODES = [
    # 对照
    {'injection_mode': 'constant'},
    # 脉冲 — 核心频率扫描
    {'injection_mode': 'pulse', 'burst_steps': 5,  'silent_steps': 10},   # 高频
    {'injection_mode': 'pulse', 'burst_steps': 5,  'silent_steps': 50},   # 短 burst 长静默
    {'injection_mode': 'pulse', 'burst_steps': 20, 'silent_steps': 20},   # 对称中等
    {'injection_mode': 'pulse', 'burst_steps': 20, 'silent_steps': 100},  # 长周期
    # 斜坡
    {'injection_mode': 'ramp', 'ramp_period': 100, 'ramp_max_mult': 3.0},
    # 随机（Poisson）
    {'injection_mode': 'random', 'avg_interval': 3},
    {'injection_mode': 'random', 'avg_interval': 30},
]


def mode_label(config: dict) -> str:
    """生成可读的模式标签"""
    mode = config.get('injection_mode', 'unknown')
    if mode == 'constant':
        return 'constant'
    elif mode == 'pulse':
        return f"pulse_b{config['burst_steps']}s{config['silent_steps']}"
    elif mode == 'ramp':
        return f"ramp_p{config['ramp_period']}m{config['ramp_max_mult']}"
    elif mode == 'random':
        return f"random_avg{config['avg_interval']}"
    return mode


# ============================================================
# 度量工具函数
# ============================================================

def compute_coords_3d(N, n, epsilon):
    """计算所有 bits 的 3D 坐标"""
    coords = np.zeros((N, 3))
    for i in range(N):
        group = i // n
        idx_in = i % n
        coords[i, group] = epsilon * (idx_in + 0.5)
    return coords


def spatial_correlation_fn(state: np.ndarray, coords: np.ndarray,
                           r_bins: int = 20) -> tuple:
    """空间相关函数 C(r)"""
    N = len(state)
    if N < 2:
        return np.array([]), np.array([])

    s_mean = state.mean()
    if abs(s_mean - 0.0) < 1e-10 or abs(s_mean - 1.0) < 1e-10:
        r_edges = np.linspace(0, 1, r_bins + 1)
        r_centers = (r_edges[:-1] + r_edges[1:]) / 2
        return r_centers, np.zeros(r_bins)

    coords_norm = coords.copy()
    for dim in range(3):
        cmin, cmax = coords[:, dim].min(), coords[:, dim].max()
        if cmax - cmin > 1e-10:
            coords_norm[:, dim] = (coords[:, dim] - cmin) / (cmax - cmin)

    dists = np.linalg.norm(coords_norm[:, None, :] - coords_norm[None, :, :], axis=2)
    fluct = state - s_mean

    iu = np.triu_indices(N, k=1)
    d_flat = dists[iu]
    c_flat = fluct[iu[0]] * fluct[iu[1]]

    r_edges = np.linspace(0, 1, r_bins + 1)
    r_centers = (r_edges[:-1] + r_edges[1:]) / 2
    C_r = np.zeros(r_bins)

    for b in range(r_bins):
        mask = (d_flat >= r_edges[b]) & (d_flat < r_edges[b + 1])
        if mask.sum() > 0:
            C_r[b] = c_flat[mask].mean()

    return r_centers, C_r


def correlation_length(r_centers: np.ndarray, C_r: np.ndarray) -> float:
    """从 C(r) 估计相关性长度 ξ"""
    if len(C_r) < 2:
        return 0.0
    C0 = C_r[0] if C_r[0] != 0 else 1.0
    C_norm = C_r / abs(C0)
    threshold = 1.0 / np.e
    idx = np.where(C_norm < threshold)[0]
    if len(idx) == 0:
        return float('inf')
    return float(r_centers[idx[0]])


def find_reactivation_windows(hw_traj: np.ndarray, window_size: int = 50,
                              threshold_std: float = 1.5) -> list:
    """在 HW 轨迹中找到重新激活窗口（HW 方差显著增大的时间段）

    Returns: [(start_step, end_step, mean_hw, var_hw), ...]
    """
    if len(hw_traj) < window_size * 3:
        return []

    # 滑动窗口方差
    windows = []
    for i in range(0, len(hw_traj) - window_size, window_size // 2):
        seg = hw_traj[i:i + window_size]
        seg_var = seg.var()
        seg_mean = seg.mean()
        windows.append((i, i + window_size, seg_mean, seg_var))

    # 整体方差作为基线
    global_var = hw_traj.var()

    reactivations = []
    for start, end, mean, var in windows:
        if var > global_var * threshold_std and var > 0.5:
            reactivations.append((start, end, float(mean), float(var)))

    return reactivations


def detect_L2_signal(hw_post: np.ndarray, hw_pre_last: np.ndarray,
                     var_post: float) -> dict:
    """检测 L2 信号（基于三个指标）

    Args:
        hw_post: 密封后的 HW 轨迹
        hw_pre_last: 密封前的 HW 轨迹（最后一段）
        var_post: 密封后 HW 方差

    Returns:
        dict with L2 signal indicators
    """
    n_windows = find_reactivation_windows(hw_post)

    # 指标 1: 方差比（post_seal var / pre_seal var）
    # 密封前最后 200 步的方差作为基线
    pre_var = hw_pre_last.var() if len(hw_pre_last) > 5 else 0.1
    var_ratio = var_post / max(pre_var, 1e-6)

    # 指标 2: 重新激活窗口数量
    n_active_windows = len(n_windows)

    # 指标 3: 最大方差窗口的强度
    max_window_var = max([v for (_, _, _, v) in n_windows], default=0.0)

    # 综合信号
    has_L2_signal = (
        n_active_windows >= 2
        and var_ratio > 2.0
        and max_window_var > 1.0
    )

    return {
        'var_ratio': float(var_ratio),
        'n_reactivation_windows': n_active_windows,
        'max_window_var': float(max_window_var),
        'has_L2_signal': has_L2_signal,
    }


# ============================================================
# 单次运行
# ============================================================
def run_single(config: dict, run_id: int, verbose: bool = False) -> dict:
    """单次实验运行

    Args:
        config: post_seal_config（包含 injection_mode 等）
        run_id: 随机种子
    """
    label = mode_label(config)
    seed = run_id * 31337 + 7 + hash(label) % 100000
    rng = np.random.RandomState(seed % (2**31))
    torch.manual_seed(seed % (2**31))

    # 随机初始状态
    initial = torch.zeros(N_BASE)
    n_ones = max(3, rng.randint(4, min(12, N_BASE // 2)))
    indices = rng.choice(N_BASE, size=n_ones, replace=False)
    initial[indices] = 1.0

    evolver = SpatialLongRangeEvolver(
        N=N_BASE,
        total_steps=TOTAL_STEPS,
        sample_interval=50,
        partial_sealing=False,
        post_seal_config=config,
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
    with suppress_stdout():
        result = evolver.run(initial_state=initial, verbose=False,
                             post_seal_callback=_on_post_seal)
    elapsed = time.time() - t0

    # ---- 提取数据 ----
    snapshots = evolver.snapshots
    seal_step = evolver.seal_step
    sealed = evolver.constraints.sealed
    n_sealed_bits = len(evolver.constraints.sealed_bits)
    sealed_ratio = evolver.constraints.get_sealed_ratio()

    # HW 历史
    hw_history = np.array(evolver.hamming_weight_history)

    # 密封前 vs 密封后
    if seal_step >= 0:
        pre_hw = hw_history[:seal_step]
        post_hw = hw_history[seal_step:]
    else:
        pre_hw = hw_history
        post_hw = np.array([])

    # 密封前最后 200 步（用于方差基线）
    pre_last_200 = pre_hw[-200:] if len(pre_hw) > 200 else pre_hw[-50:] if len(pre_hw) > 50 else pre_hw

    # 密封后 HW 统计
    post_hw_mean = float(post_hw.mean()) if len(post_hw) > 0 else np.nan
    post_hw_var = float(post_hw.var()) if len(post_hw) > 1 else np.nan
    post_hw_max = float(post_hw.max()) if len(post_hw) > 0 else np.nan
    post_hw_min = float(post_hw.min()) if len(post_hw) > 0 else np.nan
    post_hw_range = post_hw_max - post_hw_min if not np.isnan(post_hw_max) else np.nan

    # 密封后最后 200 步的方差（衰减测量）
    post_last_200 = post_hw[-200:] if len(post_hw) > 200 else post_hw
    post_last_var = float(post_last_200.var()) if len(post_last_200) > 1 else np.nan

    # ---- L2 信号检测 ----
    l2_signal = detect_L2_signal(post_hw, pre_last_200, post_hw_var)

    # ---- 空间相关函数演化 ----
    # 取密封前最后 3 个快照和密封后均匀采样 5 个快照
    N_ev = evolver.N
    n = N_ev // 3
    epsilon = evolver.spatial_layer.epsilon
    coords = compute_coords_3d(N_ev, n, epsilon)

    pre_snaps = [s for s in snapshots if s.step < seal_step] if seal_step >= 0 else snapshots[:3]
    post_snaps = [s for s in snapshots if s.step >= seal_step] if seal_step >= 0 else []

    # 平均相关性长度
    xi_pre_vals = []
    for snap in pre_snaps[-3:]:
        s_np = snap.state.cpu().numpy().copy()
        r_c, Cr = spatial_correlation_fn(s_np, coords)
        xi = correlation_length(r_c, Cr)
        if xi != float('inf') and not np.isnan(xi):
            xi_pre_vals.append(xi)

    # 密封后相关性长度的时间演化（分段计算）
    xi_post_evolution = []
    if len(post_snaps) > 3:
        n_xi_samples = min(10, len(post_snaps))
        sample_idx = np.linspace(0, len(post_snaps) - 1, n_xi_samples, dtype=int)
        for si in sample_idx:
            snap = post_snaps[si]
            s_np = snap.state.cpu().numpy().copy()
            r_c, Cr = spatial_correlation_fn(s_np, coords)
            xi = correlation_length(r_c, Cr)
            xi_post_evolution.append(float(xi) if xi != float('inf') and not np.isnan(xi) else 0.0)

    xi_pre_mean = float(np.mean(xi_pre_vals)) if xi_pre_vals else 0.0
    xi_post_mean = float(np.mean(xi_post_evolution)) if xi_post_evolution else 0.0

    # ---- 最终状态密封情况 ----
    final_state = result['final_state'].cpu().numpy()
    # 密封后是否有新的 sealed bits（A9）
    # （通过约束器的 sealed_bits 列表，已经在 evolver.run 后更新）
    final_sealed_count = len(evolver.constraints.sealed_bits)
    new_sealed_post = final_sealed_count - seal_info.get('sealed_bits_at_seal', 0) if seal_info else 0

    return {
        'mode_label': label,
        'config': config,
        'run_id': run_id,
        'seed': seed,

        # 密封信息
        'sealed': sealed,
        'seal_step': seal_step,
        'n_sealed_bits': n_sealed_bits,
        'sealed_ratio': sealed_ratio,
        'final_sealed_count': final_sealed_count,
        'new_sealed_post': new_sealed_post,

        # HW 统计
        'post_hw_mean': post_hw_mean,
        'post_hw_var': post_hw_var,
        'post_hw_max': post_hw_max,
        'post_hw_min': post_hw_min,
        'post_hw_range': post_hw_range,
        'post_last_var': post_last_var,

        # L2 信号
        'L2_signal': l2_signal,

        # 空间相关性
        'xi_pre_mean': xi_pre_mean,
        'xi_post_mean': xi_post_mean,

        # 性能
        'elapsed_sec': round(elapsed, 2),
    }


# ============================================================
# 分析
# ============================================================
def analyze_results(all_metrics: list) -> dict:
    """批量分析所有模式的结果"""
    # 按模式分组
    by_mode = {}
    for m in all_metrics:
        label = m['mode_label']
        if label not in by_mode:
            by_mode[label] = []
        by_mode[label].append(m)

    analysis = {'by_mode': {}}

    for label in sorted(by_mode.keys()):
        group = by_mode[label]
        sealed_group = [m for m in group if m['sealed']]
        n_sealed = len(sealed_group)
        n_total = len(group)

        # L2 信号统计
        l2_sigs = [m['L2_signal'] for m in group]
        n_l2 = sum(1 for s in l2_sigs if s.get('has_L2_signal', False))

        # HW 方差
        post_vars = [m['post_hw_var'] for m in group if not np.isnan(m['post_hw_var'])]
        post_means = [m['post_hw_mean'] for m in group if not np.isnan(m['post_hw_mean'])]
        post_ranges = [m['post_hw_range'] for m in group if not np.isnan(m['post_hw_range'])]
        post_last_vars = [m['post_last_var'] for m in group if not np.isnan(m['post_last_var'])]
        var_ratios = [s.get('var_ratio', np.nan) for s in l2_sigs]

        # 重新激活窗口数
        n_windows = [s.get('n_reactivation_windows', 0) for s in l2_sigs]

        # 相关性长度
        xi_post = [m['xi_post_mean'] for m in group if m['xi_post_mean'] > 1e-6]

        # 持续活跃度：最后 200 步方差 > 0.5 的比例
        persistent_active = sum(1 for v in post_last_vars if v > 0.5)

        cs = {
            'n_runs': n_total,
            'n_sealed': n_sealed,
            'seal_rate': n_sealed / n_total if n_total > 0 else 0,
            'n_L2_signal': n_l2,
            'L2_rate': n_l2 / n_total if n_total > 0 else 0,
            'hw_var_mean': float(np.mean(post_vars)) if post_vars else np.nan,
            'hw_var_std': float(np.std(post_vars)) if post_vars else np.nan,
            'hw_mean': float(np.mean(post_means)) if post_means else np.nan,
            'hw_range_mean': float(np.mean(post_ranges)) if post_ranges else np.nan,
            'hw_last_var_mean': float(np.mean(post_last_vars)) if post_last_vars else np.nan,
            'var_ratio_mean': float(np.nanmean(var_ratios)) if var_ratios else np.nan,
            'n_windows_mean': float(np.mean(n_windows)) if n_windows else np.nan,
            'xi_post_mean': float(np.mean(xi_post)) if xi_post else np.nan,
            'persistent_active_ratio': persistent_active / n_total if n_total > 0 else 0,
            'max_window_var_mean': float(np.mean([s.get('max_window_var', 0) for s in l2_sigs])),
        }

        analysis['by_mode'][label] = cs

    # 综合排序：按 L2 率排序
    sorted_modes = sorted(analysis['by_mode'].items(),
                          key=lambda x: x[1]['L2_rate'],
                          reverse=True)
    analysis['ranked_by_L2'] = [(label, cs['L2_rate']) for label, cs in sorted_modes]

    return analysis


# ============================================================
# 打印结果
# ============================================================
def print_results(analysis: dict):
    """打印分析结果到控制台"""
    print(f"\n{'=' * 80}")
    print("Phase 14 P1: 时间结构化注入 — 结果分析")
    print("=" * 80)

    by_mode = analysis['by_mode']
    ranked = analysis.get('ranked_by_L2', [])

    # 排名表
    print(f"\n{'模式':40s} {'L2率':>8s} {'HW方差':>8s} {'HW极差':>8s} {'持续活跃':>8s} {'窗口数':>8s}")
    print("-" * 80)

    for label, _ in ranked:
        cs = by_mode[label]
        n_bar = int(cs['L2_rate'] * 30)
        bar = '#' * n_bar + ' ' * (30 - n_bar)

        l2_str = f"{cs['L2_rate']*100:5.1f}%"
        var_str = f"{cs['hw_var_mean']:.2f}" if not np.isnan(cs['hw_var_mean']) else '  N/A'
        range_str = f"{cs['hw_range_mean']:.1f}" if not np.isnan(cs['hw_range_mean']) else '  N/A'
        persist_str = f"{cs['persistent_active_ratio']*100:5.1f}%"
        win_str = f"{cs['n_windows_mean']:.2f}"

        print(f"  {label:38s} {l2_str:>8s} {var_str:>8s} {range_str:>8s} {persist_str:>8s} {win_str:>8s}")
        print(f"  {'':38s} {bar}")

    # 最佳与最差
    print(f"\n{'=' * 80}")
    if ranked:
        best_label, best_rate = ranked[0]
        print(f"** 最佳 L2 率: {best_label} = {best_rate*100:.1f}%")

        # 找到对照组的 L2 率
        constant_rate = by_mode.get('constant', {}).get('L2_rate', 0)
        print(f"** 对照(恒定) L2 率: {constant_rate*100:.1f}%")

        # 最佳 vs 对照的比率
        if constant_rate > 0:
            ratio = best_rate / constant_rate
            print(f"** 最佳/对照比率: {ratio:.2f}x")
        elif best_rate > 0:
            print(f"** 恒定注入无 L2 信号，脉冲模式产生了信号")

    # 脉冲模式的频率分析
    pulse_modes = [(l, cs) for l, cs in by_mode.items() if l.startswith('pulse')]
    if pulse_modes:
        print(f"\n{'=' * 80}")
        print("脉冲频率分析")
        print("-" * 80)
        for label, cs in sorted(pulse_modes, key=lambda x: x[1]['L2_rate'], reverse=True):
            # 解析 burst/silent 参数
            parts = label.replace('pulse_b', '').split('s')
            if len(parts) == 2:
                burst, silent = parts
                period = int(burst) + int(silent)
                duty = int(burst) / period * 100
                total_plot = int(cs['L2_rate'] * 20)
                bar = '#' * total_plot
                print(f"  {label:30s} duty={duty:5.1f}% L2={cs['L2_rate']*100:5.1f}% {bar}")

    # 结论总结
    print(f"\n{'=' * 80}")
    print("结论")
    print("=" * 80)

    if ranked:
        best_rate = ranked[0][1]
        constant_rate = by_mode.get('constant', {}).get('L2_rate', 0)

        if best_rate > constant_rate + 0.1:
            print("✅ H14-1 (脉冲假设): 确认 — 某些脉冲模式优于恒定注入")
        else:
            print("❌ H14-1 (脉冲假设): 未确认 — 脉冲不优于恒定注入")

        # 检查有没有任何模式的 L2 率 > 30%
        any_high = any(cs['L2_rate'] > 0.3 for _, cs in by_mode.items())
        if any_high:
            print("✅ H14-2 ~ H14-4: 部分确认 — 某些模式产生了显著的 L2 信号")
        else:
            print("❌ H14-2 ~ H14-4: 未确认 — 时间结构本身不足以产生 L2")


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    print("=" * 80)
    print("Phase 14 P1: 时间结构化注入 (exp_158)")
    print("=" * 80)
    print(f"  N={N_BASE}, total_steps={TOTAL_STEPS}, post_seal_steps={POST_SEAL_STEPS}")
    print(f"  Runs per mode: {N_RUNS}")
    print(f"  Modes: {len(INJECTION_MODES)}")
    print(f"  Total runs: {len(INJECTION_MODES) * N_RUNS}")
    print("=" * 80)

    # 打印模式列表
    print("\n注入模式:")
    for i, config in enumerate(INJECTION_MODES):
        label = mode_label(config)
        print(f"  [{i+1}] {label}")

    all_metrics = []
    t_start = time.time()
    total_runs = len(INJECTION_MODES) * N_RUNS
    run_count = 0

    t_mode_start = time.time()

    for config in INJECTION_MODES:
        label = mode_label(config)
        print(f"\n--- {label} ---")

        for run_id in range(N_RUNS):
            metrics = run_single(config, run_id)
            all_metrics.append(metrics)
            run_count += 1

            # 进度（每 2 次或最后 1 次）
            if (run_id + 1) % 2 == 0 or run_id == N_RUNS - 1:
                pct = run_count / total_runs * 100
                l2_count = sum(1 for m in all_metrics
                               if m.get('L2_signal', {}).get('has_L2_signal', False))
                elapsed_so_far = time.time() - t_start
                rate = run_count / max(1, elapsed_so_far)
                eta = (total_runs - run_count) / max(rate, 0.001)
                print(f"    {run_id+1}/{N_RUNS} runs | total {run_count}/{total_runs} "
                      f"({pct:.0f}%) | L2:{l2_count} | "
                      f"{elapsed_so_far:.0f}s elapsed, ~{eta:.0f}s remaining")

        mode_elapsed = time.time() - t_mode_start
        print(f"    mode done in {mode_elapsed:.0f}s")

    t_total = time.time() - t_start
    print(f"\n总时间: {t_total:.0f}s ({t_total/60:.1f}min)")

    # ---- 分析 ----
    analysis = analyze_results(all_metrics)
    print_results(analysis)

    # ---- 保存 ----
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR,
                               f"exp158_phase14_p1_injection_{timestamp}.json")

    # 去除大型 numpy/torch 对象后再保存
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
            elif isinstance(v, dict):
                sm[k] = {sk: float(sv) if isinstance(sv, (np.floating,)) else
                         int(sv) if isinstance(sv, (np.integer,)) else
                         sv for sk, sv in v.items()}
            else:
                sm[k] = v
        save_metrics.append(sm)

    save_data = {
        'params': {
            'N_base': N_BASE,
            'total_steps': TOTAL_STEPS,
            'post_seal_steps': POST_SEAL_STEPS,
            'n_runs': N_RUNS,
            'timestamp': timestamp,
            'experiment': 'exp_158_phase14_p1_time_structured_injection',
        },
        'analysis': {
            'by_mode': {k: {sk: sv for sk, sv in v.items()}
                       for k, v in analysis['by_mode'].items()},
            'ranked_by_L2': analysis['ranked_by_L2'],
        },
        'metrics': save_metrics,
    }

    try:
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, default=str)
        print(f"\n结果保存至: {result_file}")
    except Exception as e:
        print(f"\n⚠️ 保存失败: {e}")
        backup_file = os.path.join(os.path.expanduser('~'),
                                   f'exp158_backup_{timestamp}.json')
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, default=str)
            print(f"  已保存到备用位置: {backup_file}")
        except Exception as e2:
            print(f"  备用保存也失败: {e2}")

    return save_data


if __name__ == '__main__':
    run_experiment()
