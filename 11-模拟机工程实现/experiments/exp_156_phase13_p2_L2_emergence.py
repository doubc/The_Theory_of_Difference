"""
exp_156 — Phase 13 P2: L2 涌现 — 密封后的第二层组织

科学问题：
  Phase 12 确认了密封是一次相变（cascade）。密封后，sealed bits 形成稳定结构。
  这个稳定结构本身是否成为新的"基底"，使得第二层组织现象浮现？

  L0 = bit-flip 基元动力学
  L1 = 密封（相变，cascade）
  L2 = 密封后，unsealed bits 在 sealed 结构"背景"上是否形成更高级的模式？

假设：
  H156-1 (L2 空间聚类): 密封后，unsealed active bits 的空间分布不是随机的，
            而是围绕 sealed bits 形成可测量的聚类结构。
            → 度量：unsealed-1 到最近 sealed-1 的平均距离 < 随机基线

  H156-2 (L2 序参数 — HW 方差收缩): 密封后 HW 的波动（方差）显著小于密封前。
            → 密封不仅在均值上固定了 HW，还抑制了其涨落（自发有序）

  H156-3 (L2 相关性长度): 密封后，空间相关函数 C(r) 的衰减长度 > 密封前。
            → sealed bits 作为"序参量"，将相关性传递到更长尺度

  H156-4 (L2 时间记忆): 密封后的动力学对初始密封构型有持久记忆——
            不同的随机种子（不同密封构型）导致不同的后密封轨迹，
            且这种差异不随时间衰减到零。
            → 度量：不同种子后密封轨迹的 KL 散度随时间是否收敛到 0

实验设计：
  对每个运行：
    1. 运行至密封（记录密封步数、密封构型）
    2. 继续运行 POST_SEAL_STEPS 步，记录每步的完整状态和 3D 坐标
    3. 分别计算密封前和密封后的：
       - 空间聚类指标（平均最近邻距离）
       - HW 方差
       - 空间相关函数 C(r)
       - 轨迹对初始条件的敏感性（跨种子比较）

用法：
  python experiments/exp_156_phase13_p2_L2_emergence.py
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
TOTAL_STEPS = 1000
POST_SEAL_STEPS = 2000
N_RUNS = 20
RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))

# 空间相关函数计算参数
R_BINS = 20          # 空间距离分桶数
MAX_R = 1.0          # 归一化最大距离（3D 空间对角线 = sqrt(3)*eps*n ≈ 可计算）


# ============================================================
# 空间度量工具函数
# ============================================================

def compute_coords_3d(N, n, epsilon):
    """计算所有 bits 的 3D 坐标 (N, 3)"""
    coords = np.zeros((N, 3))
    for i in range(N):
        group = i // n
        idx_in = i % n
        coords[i, group] = epsilon * (idx_in + 0.5)
    return coords


def mean_nearest_neighbor_distance(indices_A: np.ndarray, indices_B: np.ndarray,
                                   coords: np.ndarray) -> float:
    """计算 A 中每个点到 B 中最近点的平均距离。
    若 A 或 B 为空，返回 np.nan。
    """
    if len(indices_A) == 0 or len(indices_B) == 0:
        return np.nan
    A = coords[indices_A]
    B = coords[indices_B]
    dists = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)  # (|A|, |B|)
    min_dists = dists.min(axis=1)
    return float(min_dists.mean())


def spatial_correlation_fn(state: np.ndarray, coords: np.ndarray,
                           r_bins: int = R_BINS) -> np.ndarray:
    """计算空间相关函数 C(r) = <(s_i - <s>)(s_j - <s>)> for |r_i - r_j| in bin r

    返回 (r_centers, C_r) 两个数组。
    若状态全 0 或全 1，返回全零。
    """
    N = len(state)
    if N < 2:
        return np.array([]), np.array([])

    s_mean = state.mean()
    if abs(s_mean - 0.0) < 1e-10 or abs(s_mean - 1.0) < 1e-10:
        # 全 0 或全 1，无涨落
        r_edges = np.linspace(0, 1, r_bins + 1)
        r_centers = (r_edges[:-1] + r_edges[1:]) / 2
        return r_centers, np.zeros(r_bins)

    # 归一化坐标到 [0, 1] 范围（按每维最大值）
    coords_norm = coords.copy()
    for dim in range(3):
        cmin, cmax = coords[:, dim].min(), coords[:, dim].max()
        if cmax - cmin > 1e-10:
            coords_norm[:, dim] = (coords[:, dim] - cmin) / (cmax - cmin)

    dists = np.linalg.norm(coords_norm[:, None, :] - coords_norm[None, :, :], axis=2)
    fluct = state - s_mean

    # 只取上三角（不含对角线）
    iu = np.triu_indices(N, k=1)
    d_flat = dists[iu]
    c_flat = fluct[iu[0]] * fluct[iu[1]]   # (s_i - <s>)(s_j - <s>)

    # 分桶平均
    r_edges = np.linspace(0, 1, r_bins + 1)
    r_centers = (r_edges[:-1] + r_edges[1:]) / 2
    C_r = np.zeros(r_bins)

    for b in range(r_bins):
        mask = (d_flat >= r_edges[b]) & (d_flat < r_edges[b + 1])
        if mask.sum() > 0:
            C_r[b] = c_flat[mask].mean()
        else:
            C_r[b] = 0.0

    return r_centers, C_r


def correlation_length(r_centers: np.ndarray, C_r: np.ndarray) -> float:
    """从 C(r) 估计相关性长度 ξ：C(r) ~ exp(-r/ξ)，取 C(r) 衰减到 1/e 时的 r。
    若 C(r) 不衰减（长程有序），返回 np.inf。
    """
    if len(C_r) < 2:
        return 0.0
    # 归一化 C(r) 使 C(0) = 1
    C0 = C_r[0] if C_r[0] != 0 else 1.0
    C_norm = C_r / abs(C0)

    # 找第一个 C_norm < 1/e 的位置
    threshold = 1.0 / np.e
    idx = np.where(C_norm < threshold)[0]
    if len(idx) == 0:
        return float('inf')   # 不衰减
    xi = r_centers[idx[0]]
    return float(xi)


def random_baseline_distance(N, n_sealed, n_active, coords, rng=None):
    """随机基线：随机选 n_active 个位置，计算到最近 sealed 的平均距离"""
    if rng is None:
        rng = np.random.RandomState()
    if n_sealed == 0 or n_active == 0:
        return np.nan
    sealed = rng.choice(N, size=n_sealed, replace=False)
    active = rng.choice([i for i in range(N) if i not in sealed], size=n_active, replace=False)
    return mean_nearest_neighbor_distance(active, sealed, coords)


# ============================================================
# 单次运行
# ============================================================
def run_single(run_id: int) -> dict:
    """单次实验运行，返回密封前后的详细空间/统计指标。"""

    rng = np.random.RandomState(run_id * 31337 + 7)
    torch.manual_seed(run_id * 137 + 53)

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
        post_seal_config={},
        post_seal_steps=POST_SEAL_STEPS,
    )

    # 记录密封前后快照
    pre_seal_states = []    # [(step, state_np, hw)]
    post_seal_states = []    # [(step, state_np, hw)]
    seal_step = -1

    def _capture(state, step, is_post):
        s_np = state.cpu().numpy().copy()
        hw = int(s_np.sum())
        if is_post:
            post_seal_states.append((step, s_np, hw))
        else:
            pre_seal_states.append((step, s_np, hw))

    # 用 evolver.run 并手动捕获中间状态
    # 由于 evolver 内部不直接暴露 pre/post 拆分钩子，
    # 这里用 snapshot 机制来区分
    result = evolver.run(initial_state=initial, verbose=False)
    seal_step = evolver.seal_step

    # 从 evolver.snapshots 拆分 pre/post
    pre_snaps = [s for s in evolver.snapshots if s.step < seal_step] if seal_step >= 0 else evolver.snapshots
    post_snaps = [s for s in evolver.snapshots if s.step >= seal_step] if seal_step >= 0 else []

    if seal_step < 0 or len(post_snaps) == 0:
        # 未密封，跳过 L2 分析
        return {
            'run_id': run_id,
            'sealed': False,
            'skip_reason': 'not_sealed',
        }

    # ============================================================
    # 计算坐标
    # ============================================================
    N = evolver.N
    n = N // 3
    epsilon = evolver.spatial_layer.epsilon
    coords = compute_coords_3d(N, n, epsilon)

    # ============================================================
    # H156-1: 空间聚类 — unsealed active bits 到 sealed bits 的距离
    # ============================================================
    final_state = post_snaps[-1].state.cpu().numpy().copy()
    sealed_bits = np.array(list(evolver.constraints.sealed_bits), dtype=int)
    unsealed_bits = np.array([i for i in range(N) if i not in evolver.constraints.sealed_bits], dtype=int)

    active_unsealed = unsealed_bits[final_state[unsealed_bits] > 0.5]
    sealed_active = sealed_bits[final_state[sealed_bits] > 0.5]

    # 平均最近邻距离：active_unsealed → sealed_active
    d_actual = mean_nearest_neighbor_distance(active_unsealed, sealed_active, coords)

    # 随机基线（多次抽样取平均）
    n_baseline_samples = 50
    d_baselines = []
    for _ in range(n_baseline_samples):
        b = random_baseline_distance(N, len(sealed_active),
                                     max(1, len(active_unsealed)),
                                     coords, rng=rng)
        d_baselines.append(b)
    d_baseline = np.nanmean(d_baselines)

    clustering_ratio = d_actual / d_baseline if (d_actual is not np.nan and d_baseline > 0) else np.nan

    # ============================================================
    # H156-2: HW 方差收缩
    # ============================================================
    pre_hw = np.array([s.w for s in pre_snaps]) if pre_snaps else np.array([])
    post_hw = np.array([s.w for s in post_snaps]) if post_snaps else np.array([])

    hw_var_pre = float(pre_hw.var()) if len(pre_hw) > 1 else np.nan
    hw_var_post = float(post_hw.var()) if len(post_hw) > 1 else np.nan
    hw_var_ratio = hw_var_post / hw_var_pre if (hw_var_pre is not np.nan and hw_var_pre > 0) else np.nan

    # ============================================================
    # H156-3: 空间相关性长度
    # ============================================================
    # 取密封前最后 5 个快照和密封后最后 5 个快照，分别算 C(r)
    n_sample = min(5, len(pre_snaps), len(post_snaps))

    xi_pre_list = []
    xi_post_list = []

    for snap in pre_snaps[-n_sample:]:
        s_np = snap.state.cpu().numpy().copy()
        r_c, C_r = spatial_correlation_fn(s_np, coords)
        xi = correlation_length(r_c, C_r)
        if xi != float('inf') and not np.isnan(xi):
            xi_pre_list.append(xi)

    for snap in post_snaps[-n_sample:]:
        s_np = snap.state.cpu().numpy().copy()
        r_c, C_r = spatial_correlation_fn(s_np, coords)
        xi = correlation_length(r_c, C_r)
        if xi != float('inf') and not np.isnan(xi):
            xi_post_list.append(xi)
        if xi != float('inf') and not np.isnan(xi):
            xi_post_list.append(xi)

    xi_pre_mean = float(np.mean(xi_pre_list)) if xi_pre_list else np.nan
    xi_post_mean = float(np.mean(xi_post_list)) if xi_post_list else np.nan
    xi_ratio = xi_post_mean / xi_pre_mean if (xi_pre_mean is not np.nan and xi_pre_mean > 0) else np.nan

    # ============================================================
    # H156-4: 时间记忆（需要跨种子比较，在 analyze_results 中做）
    # 这里只记录密封构型指纹和 post-seal 轨迹，供后续分析
    # ============================================================
    seal_config_fingerprint = hash(tuple(final_state[sealed_bits].tolist())) % 1000000

    # post-seal HW 轨迹（最后 100 步，降采样）
    post_hw_traj = post_hw[-100:].tolist() if len(post_hw) >= 100 else post_hw.tolist()

    return {
        'run_id': run_id,
        'sealed': True,
        'seal_step': seal_step,
        'N': N,
        'n_sealed': len(evolver.constraints.sealed_bits),
        'sealed_ratio': evolver.constraints.get_sealed_ratio(),

        # H156-1
        'd_actual': d_actual,
        'd_baseline': d_baseline,
        'clustering_ratio': clustering_ratio,   # < 1 表示聚类（比随机更近）

        # H156-2
        'hw_var_pre': hw_var_pre,
        'hw_var_post': hw_var_post,
        'hw_var_ratio': hw_var_ratio,   # < 1 表示方差收缩

        # H156-3
        'xi_pre_mean': xi_pre_mean,
        'xi_post_mean': xi_post_mean,
        'xi_ratio': xi_ratio,            # > 1 表示相关性长度增加

        # H156-4 (raw data for cross-run analysis)
        'seal_config_fingerprint': seal_config_fingerprint,
        'post_hw_traj': post_hw_traj,
        'post_seal_len': len(post_snaps),

        # 辅助
        'hw_pre_mean': float(pre_hw.mean()) if len(pre_hw) > 0 else np.nan,
        'hw_post_mean': float(post_hw.mean()) if len(post_hw) > 0 else np.nan,
    }


# ============================================================
# 跨种子分析 (H156-4)
# ============================================================
def analyze_cross_run_memory(all_metrics: list) -> dict:
    """H156-4: 密封后轨迹对初始密封构型的记忆

    方法：计算不同 run 之间 post-seal HW 轨迹的 JS 散度。
    若记忆持久，相似密封构型 → 相似轨迹（比随机配对更相似）。
    """
    sealed_metrics = [m for m in all_metrics if m.get('sealed', False)]
    if len(sealed_metrics) < 2:
        return {'memory_score': np.nan, 'note': 'insufficient_sealed_runs'}

    # 构建 HW 轨迹矩阵 (n_runs, traj_len)
    max_len = max(len(m['post_hw_traj']) for m in sealed_metrics)
    traj_matrix = []
    fps = []
    for m in sealed_metrics:
        traj = m['post_hw_traj'] + [m['post_hw_traj'][-1]] * (max_len - len(m['post_hw_traj']))
        traj_matrix.append(traj)
        fps.append(m['seal_config_fingerprint'])

    traj_matrix = np.array(traj_matrix)

    # 计算两两 JS 散度（用直方图近似）
    from scipy.stats import entropy

    n = len(sealed_metrics)
    js_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            p = np.array(traj_matrix[i])
            q = np.array(traj_matrix[j])
            # 归一化为分布（直方图）
            p_hist, _ = np.histogram(p, bins=20, density=True)
            q_hist, _ = np.histogram(q, bins=20, density=True)
            # 避免零
            p_hist = p_hist + 1e-10
            q_hist = q_hist + 1e-10
            m = 0.5 * (p_hist + q_hist)
            js = 0.5 * entropy(p_hist, m) + 0.5 * entropy(q_hist, m)
            js_matrix[i, j] = js
            js_matrix[j, i] = js

    # 相同 fingerprint 的对 vs 不同 fingerprint 的对
    same_fp_js = []
    diff_fp_js = []
    for i in range(n):
        for j in range(i + 1, n):
            if fps[i] == fps[j]:
                same_fp_js.append(js_matrix[i, j])
            else:
                diff_fp_js.append(js_matrix[i, j])

    memory_score = np.nan
    if same_fp_js and diff_fp_js:
        memory_score = float(np.mean(diff_fp_js) - np.mean(same_fp_js))

    return {
        'memory_score': memory_score,   # > 0 表示相同构型更相似（有记忆）
        'same_fp_js_mean': float(np.mean(same_fp_js)) if same_fp_js else np.nan,
        'diff_fp_js_mean': float(np.mean(diff_fp_js)) if diff_fp_js else np.nan,
        'n_same_fp_pairs': len(same_fp_js),
        'n_diff_fp_pairs': len(diff_fp_js),
    }


# ============================================================
# 主分析
# ============================================================
def analyze_results(all_metrics: list) -> dict:
    sealed = [m for m in all_metrics if m.get('sealed', False)]
    n_total = len(all_metrics)
    n_sealed = len(sealed)

    if n_sealed == 0:
        return {'error': 'no_sealed_runs', 'n_total': n_total}

    analysis = {
        'n_total': n_total,
        'n_sealed': n_sealed,
        'seal_rate': n_sealed / n_total,
    }

    # ---- H156-1 ----
    cr = np.array([m['clustering_ratio'] for m in sealed if not np.isnan(m['clustering_ratio'])])
    analysis['H156_1_clustering'] = {
        'n_valid': len(cr),
        'clustering_ratio_mean': float(cr.mean()) if len(cr) > 0 else np.nan,
        'clustering_ratio_std': float(cr.std()) if len(cr) > 0 else np.nan,
        'ratio_lt_1_count': int((cr < 1.0).sum()),
        'ratio_lt_1_pct': float((cr < 1.0).mean()) if len(cr) > 0 else np.nan,
    }

    # ---- H156-2 ----
    vr = np.array([m['hw_var_ratio'] for m in sealed if not np.isnan(m['hw_var_ratio'])])
    analysis['H156_2_hw_variance'] = {
        'n_valid': len(vr),
        'hw_var_ratio_mean': float(vr.mean()) if len(vr) > 0 else np.nan,
        'hw_var_ratio_std': float(vr.std()) if len(vr) > 0 else np.nan,
        'var_contraction_count': int((vr < 1.0).sum()),   # 方差收缩
        'var_contraction_pct': float((vr < 1.0).mean()) if len(vr) > 0 else np.nan,
    }

    # ---- H156-3 ----
    xir = np.array([m['xi_ratio'] for m in sealed if not np.isnan(m['xi_ratio'])])
    analysis['H156_3_correlation_length'] = {
        'n_valid': len(xir),
        'xi_ratio_mean': float(xir.mean()) if len(xir) > 0 else np.nan,
        'xi_ratio_std': float(xir.std()) if len(xir) > 0 else np.nan,
        'xi_increased_count': int((xir > 1.0).sum()),
        'xi_increased_pct': float((xir > 1.0).mean()) if len(xir) > 0 else np.nan,
    }

    # ---- H156-4 ----
    memory_result = analyze_cross_run_memory(all_metrics)
    analysis['H156_4_temporal_memory'] = memory_result

    # ---- 综合判断 ----
    verdict = ""
    n_confirmed = 0
    if analysis['H156_1_clustering'].get('ratio_lt_1_pct', 0) > 0.7:
        verdict += "H156-1: CONFIRMED (clustering) | "
        n_confirmed += 1
    else:
        verdict += "H156-1: REJECTED | "

    if analysis['H156_2_hw_variance'].get('var_contraction_pct', 0) > 0.7:
        verdict += "H156-2: CONFIRMED (var contraction) | "
        n_confirmed += 1
    else:
        verdict += "H156-2: REJECTED | "

    if analysis['H156_3_correlation_length'].get('xi_increased_pct', 0) > 0.6:
        verdict += "H156-3: CONFIRMED (xi increased) | "
        n_confirmed += 1
    else:
        verdict += "H156-3: REJECTED | "

    if memory_result.get('memory_score', 0) > 0.1:
        verdict += "H156-4: CONFIRMED (memory) | "
        n_confirmed += 1
    else:
        verdict += "H156-4: REJECTED | "

    analysis['verdict'] = verdict
    analysis['n_confirmed'] = n_confirmed
    analysis['L2_emergence'] = n_confirmed >= 2   # 至少 2/4 假设确认 → L2 涌现

    return analysis


# ============================================================
# 主运行
# ============================================================
def run_experiment():
    print("=" * 70)
    print("Phase 13 P2: L2 涌现 — 密封后的第二层组织 (exp_156)")
    print("=" * 70)
    print(f"  N={N_BASE}, total_steps={TOTAL_STEPS}, post_seal_steps={POST_SEAL_STEPS}")
    print(f"  N_RUNS={N_RUNS}")
    print(f"  假设：H156-1 (空间聚类) | H156-2 (HW方差收缩) | "
          f"H156-3 (相关性长度) | H156-4 (时间记忆)")
    print("=" * 70)

    all_metrics = []
    t_start = time.time()

    for run_id in range(N_RUNS):
        m = run_single(run_id)
        all_metrics.append(m)

        if (run_id + 1) % 5 == 0:
            sealed_so_far = sum(1 for m in all_metrics if m.get('sealed', False))
            print(f"  ... {run_id+1}/{N_RUNS} runs, {sealed_so_far} sealed")

    t_total = time.time() - t_start
    print(f"\n总时间: {t_total:.0f}s ({t_total/60:.1f}min)")

    # ---- 分析 ----
    print(f"\n{'=' * 70}")
    print("分析结果")
    print("=" * 70)

    analysis = analyze_results(all_metrics)

    if 'error' in analysis:
        print(f"  ⚠️ {analysis['error']}")
        return all_metrics

    print(f"\n密封率: {analysis['seal_rate']*100:.1f}% ({analysis['n_sealed']}/{analysis['n_total']})")

    # H156-1
    h1 = analysis['H156_1_clustering']
    print(f"\n[H156-1] 空间聚类 (clustering_ratio < 1 = 聚类)")
    print(f"  有效样本: {h1['n_valid']}")
    print(f"  clustering_ratio: {h1.get('clustering_ratio_mean', float('nan')):.3f} "
          f"± {h1.get('clustering_ratio_std', float('nan')):.3f}")
    print(f"  < 1 的比例: {h1.get('ratio_lt_1_pct', 0)*100:.1f}%")
    bar1 = '#' * int(max(0, 20 - h1.get('clustering_ratio_mean', 1) * 20))
    print(f"  聚类强度: {bar1}")

    # H156-2
    h2 = analysis['H156_2_hw_variance']
    print(f"\n[H156-2] HW 方差收缩 (hw_var_ratio < 1 = 收缩)")
    print(f"  有效样本: {h2['n_valid']}")
    print(f"  hw_var_ratio: {h2.get('hw_var_ratio_mean', float('nan')):.3f} "
          f"± {h2.get('hw_var_ratio_std', float('nan')):.3f}")
    print(f"  收缩比例: {h2.get('var_contraction_pct', 0)*100:.1f}%")
    bar2 = '#' * int(min(40, max(0, (1 - h2.get('hw_var_ratio_mean', 1)) * 40)))
    print(f"  收缩强度: {bar2}")

    # H156-3
    h3 = analysis['H156_3_correlation_length']
    print(f"\n[H156-3] 相关性长度 (xi_ratio > 1 = 增加)")
    print(f"  有效样本: {h3['n_valid']}")
    print(f"  xi_ratio: {h3.get('xi_ratio_mean', float('nan')):.3f} "
          f"± {h3.get('xi_ratio_std', float('nan')):.3f}")
    print(f"  增加比例: {h3.get('xi_increased_pct', 0)*100:.1f}%")

    # H156-4
    h4 = analysis['H156_4_temporal_memory']
    print(f"\n[H156-4] 时间记忆 (memory_score > 0 = 有记忆)")
    print(f"  memory_score: {h4.get('memory_score', float('nan')):.4f}")
    print(f"  same_fp_JS: {h4.get('same_fp_js_mean', float('nan')):.4f}")
    print(f"  diff_fp_JS: {h4.get('diff_fp_js_mean', float('nan')):.4f}")

    # 总结
    print(f"\n{'=' * 70}")
    print(f"L2 涌现判断: {'YES' if analysis.get('L2_emergence') else 'NO'}")
    print(f"  确认假设数: {analysis.get('n_confirmed', 0)}/4")
    print(f"  结论: {analysis.get('verdict', '')}")
    print("=" * 70)

    # ---- 保存 ----
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"exp156_phase13_p2_L2_emergence_{timestamp}.json")

    save_data = {
        'params': {
            'N_base': N_BASE,
            'total_steps': TOTAL_STEPS,
            'post_seal_steps': POST_SEAL_STEPS,
            'n_runs': N_RUNS,
            'timestamp': timestamp,
            'experiment': 'exp_156_phase13_p2_L2_emergence',
        },
        'analysis': analysis,
        'metrics': all_metrics,
    }

    try:
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, default=str)
        print(f"\n结果保存至: {result_file}")
    except Exception as e:
        print(f"\n⚠️ 保存失败: {e}")

    return save_data


if __name__ == '__main__':
    run_experiment()
