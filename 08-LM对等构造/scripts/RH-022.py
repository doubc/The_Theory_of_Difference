import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# RH-022 修复版 v2
# 修正：
#   1. analyze_operator 返回 None 时跳过赋值
#   2. 转移矩阵只保留 k=1,2,3（k 大时谱退化）
#   3. 热核扫描是主线，t 从 0.05 到 50 对数均匀采样
#   4. 增加谱统计的"展开（unfold）"步骤，消除态密度非均匀性
# ============================================================

DIM = 3

def get_grid(L_max):
    pts = list(product(range(L_max + 1), repeat=DIM))
    idx = {p: i for i, p in enumerate(pts)}
    return pts, idx

def phi_asymmetric(u):
    return -1.0 / (u[0]*1 + u[1]*2 + u[2]*3 + 0.5)

def get_g_diag(u, L_max):
    phi_u = phi_asymmetric(u)
    main  = 1.0 - 2.0 * phi_u
    g = np.zeros(DIM)
    for k in range(DIM):
        ul = list(u)
        up = ul[k] + 1; um = ul[k] - 1
        if up > L_max: up = 2*L_max - up
        if um < 0:     um = -um
        u_pk = tuple(ul[:k] + [up] + ul[k+1:])
        u_mk = tuple(ul[:k] + [um] + ul[k+1:])
        d2phi = phi_asymmetric(u_pk) - 2*phi_u + phi_asymmetric(u_mk)
        g[k] = main + 2.0 * d2phi
    return g

def build_edge_weights(pts, idx, L_max):
    N = len(pts)
    g_cache = {u: get_g_diag(u, L_max) for u in pts}
    W = np.zeros((N, N))
    for i, u in enumerate(pts):
        g_u = g_cache[u]
        for k in range(DIM):
            ul = list(u)
            nxt = ul[k] + 1
            if 0 <= nxt <= L_max:
                v = tuple(ul[:k] + [nxt] + ul[k+1:])
                j = idx[v]
                gkk_u = g_u[k]
                gkk_v = g_cache[v][k]
                if gkk_u > 0 and gkk_v > 0:
                    w = 0.5 * (1.0/gkk_u + 1.0/gkk_v)
                    W[i, j] += w
                    W[j, i] += w
    return W, g_cache

def build_heat_kernel(W, t):
    """K(t) = exp(-t * L_graph)，正半定保证。"""
    D_mat = np.diag(W.sum(axis=1))
    L_mat = D_mat - W
    eigvals, eigvecs = np.linalg.eigh(L_mat)
    exp_eigs = np.exp(-t * eigvals)
    K = eigvecs @ np.diag(exp_eigs) @ eigvecs.T
    return (K + K.T) / 2.0

def build_transfer_sym(W, k_steps=1):
    """对称化转移矩阵的 k 步幂次。"""
    row_sums = W.sum(axis=1)
    row_sums = np.where(row_sums > 0, row_sums, 1.0)
    T  = W / row_sums[:, np.newaxis]
    pi = row_sums / row_sums.sum()
    D_sqrt     = np.diag(np.sqrt(pi))
    D_inv_sqrt = np.diag(1.0 / np.sqrt(pi))
    S = D_sqrt @ T @ D_inv_sqrt
    S = (S + S.T) / 2.0
    if k_steps > 1:
        S = np.linalg.matrix_power(S, k_steps)
        S = (S + S.T) / 2.0
    return S

# ============================================================
# 核心：带展开（unfold）的谱统计
# ============================================================

def unfold_spectrum(eigs, poly_deg=5):
    """
    用多项式拟合累积态密度 N(lambda)，展开本征值。
    展开后间距的均值 = 1（消除态密度非均匀性）。
    """
    N = len(eigs)
    ranks = np.arange(1, N + 1, dtype=float)
    coeffs = np.polyfit(eigs, ranks, poly_deg)
    unfolded = np.polyval(coeffs, eigs)
    return unfolded

def analyze_operator(M, label, remove_trivial=True,
                     do_unfold=True, verbose=True):
    """
    完整谱分析，带展开步骤。
    返回 None 仅当本征值数 < 10。
    """
    eigs_all = np.sort(np.linalg.eigvalsh(M))
    n_neg    = np.sum(eigs_all < -1e-8)
    sym_err  = np.max(np.abs(M - M.T))
    density  = np.mean(np.abs(M) > 1e-10)

    if verbose:
        print(f"\n{'='*60}")
        print(f"实验: {label}")
        print(f"{'='*60}")
        print(f"本征值范围: [{eigs_all[0]:.4f}, {eigs_all[-1]:.4f}]")
        print(f"负本征值数: {n_neg}  |  对称误差: {sym_err:.2e}  |  稠密度: {density:.3f}")

    # 去掉最大本征值（平稳分布的平凡模式）
    eigs = eigs_all[:-1] if remove_trivial else eigs_all

    if len(eigs) < 10:
        if verbose:
            print("本征值数 < 10，跳过统计")
        return None  # 明确返回 None

    # 展开
    if do_unfold and len(eigs) >= 10:
        try:
            eigs_stat = unfold_spectrum(eigs, poly_deg=min(5, len(eigs)//4))
        except Exception:
            eigs_stat = eigs
    else:
        eigs_stat = eigs

    gaps = np.diff(eigs_stat)
    gaps_pos = gaps[gaps > 1e-10]

    if len(gaps_pos) < 5:
        if verbose:
            print("有效间距不足，跳过统计")
        return None

    mean_gap  = np.mean(gaps_pos)
    s         = gaps_pos / mean_gap
    ratios    = gaps_pos[1:] / gaps_pos[:-1]
    mean_r    = np.mean(ratios)
    se_r      = np.std(ratios) / np.sqrt(len(ratios))
    var_s     = np.var(s)
    med_r     = np.median(ratios)
    frac_gt2  = np.mean(ratios > 2)
    frac_lt05 = np.mean(ratios < 0.5)
    sigma_gue = abs(mean_r - 1.7387) / se_r if se_r > 0 else float('inf')

    if verbose:
        print(f"\n谱统计 (展开后, N={len(eigs_stat)}):")
        print(f"  <r>均值:   {mean_r:.4f} ± {se_r:.4f}")
        print(f"  <r>中位数: {med_r:.4f}")
        print(f"  方差:      {var_s:.4f}  (GUE≈0.178, Poisson≈1.000)")
        print(f"  GUE偏差:   {sigma_gue:.2f}σ")
        print(f"  >2比例:    {frac_gt2:.3f}   <0.5比例: {frac_lt05:.3f}")

    return {
        'label': label, 'eigenvalues': eigs_all,
        'eigs_stat': eigs_stat, 'gaps': gaps_pos,
        's': s, 'ratios': ratios,
        'mean_r': mean_r, 'se_r': se_r, 'med_r': med_r,
        'var_s': var_s, 'sigma_gue': sigma_gue,
        'frac_gt2': frac_gt2, 'frac_lt05': frac_lt05,
        'n_neg': n_neg, 'density': density,
    }

# ============================================================
# 主实验循环
# ============================================================

configs = [
    (2, "L=2 (27格点)"),
    (3, "L=3 (64格点)"),
]

all_results = []

for L_max, config_label in configs:
    pts, idx = get_grid(L_max)
    W, _     = build_edge_weights(pts, idx, L_max)
    N        = len(pts)

    print(f"\n{'#'*65}")
    print(f"# 格点配置: {config_label}  N={N}")
    print(f"{'#'*65}")

    # --- 转移矩阵：只做 k=1,2,3 ---
    for k in [1, 2, 3]:
        label = f"Transfer k={k}  [{config_label}]"
        S_k = build_transfer_sym(W, k_steps=k)
        res = analyze_operator(S_k, label, remove_trivial=True, verbose=True)
        if res is not None:          # ← 修复：检查 None
            res['config'] = config_label
            res['method'] = f'Transfer k={k}'
            all_results.append(res)

    # --- 热核：t 从 0.05 到 50，对数均匀 12 个点 ---
    t_values = np.logspace(np.log10(0.05), np.log10(50), 12)
    for t in t_values:
        label = f"HeatKernel t={t:.3f}  [{config_label}]"
        K_t = build_heat_kernel(W, t)
        res = analyze_operator(K_t, label, remove_trivial=True, verbose=True)
        if res is not None:          # ← 修复：检查 None
            res['config'] = config_label
            res['method'] = f'HeatKernel t={t:.3f}'
            res['t_val']  = t
            all_results.append(res)

# ============================================================
# 汇总表
# ============================================================

print("\n" + "="*85)
print("RH-022 v2 汇总对比")
print("="*85)
print(f"{'方法':<42} {'格点':<14} {'<r>均值':<9} {'中位数':<8} {'方差':<8} {'GUE偏差'}")
print("-"*85)
for res in all_results:
    print(f"{res['method']:<42} {res['config']:<14} "
          f"{res['mean_r']:.4f}    {res['med_r']:.4f}   "
          f"{res['var_s']:.4f}   {res['sigma_gue']:.2f}σ")
print(f"{'GUE 理论':<42} {'—':<14} 1.7387    ~1.47    0.178")
print(f"{'Poisson 理论':<42} {'—':<14} 1.3863    ~1.00    1.000")

# ============================================================
# 可视化：<r> / 中位数 / 方差 随 t 的变化曲线
# ============================================================

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

markers = {'L=2 (27格点)': 'o-', 'L=3 (64格点)': 's--'}
mcolors = {'L=2 (27格点)': 'steelblue', 'L=3 (64格点)': 'crimson'}

for config_label in ["L=2 (27格点)", "L=3 (64格点)"]:
    hk = [r for r in all_results
          if r['config'] == config_label and 'HeatKernel' in r['method']]
    if not hk:
        continue
    t_arr    = np.array([r['t_val']  for r in hk])
    mean_arr = np.array([r['mean_r'] for r in hk])
    med_arr  = np.array([r['med_r']  for r in hk])
    var_arr  = np.array([r['var_s']  for r in hk])
    mk = markers[config_label]
    mc = mcolors[config_label]

    axes[0].semilogx(t_arr, mean_arr, mk, color=mc, lw=2,
                     label=config_label, markersize=6)
    axes[1].semilogx(t_arr, med_arr,  mk, color=mc, lw=2,
                     label=config_label, markersize=6)
    axes[2].semilogx(t_arr, var_arr,  mk, color=mc, lw=2,
                     label=config_label, markersize=6)

for ax, (yval_gue, yval_poi, ylabel, title) in zip(axes, [
    (1.7387, 1.3863, '<r>',    '<r> 均值 vs 扩散时间 t'),
    (1.47,   1.00,   '中位数', '<r> 中位数 vs 扩散时间 t'),
    (0.178,  1.000,  '方差',   '归一化间距方差 vs 扩散时间 t'),
]):
    ax.axhline(yval_gue, color='red',   lw=2,   linestyle='--', label=f'GUE {yval_gue}')
    ax.axhline(yval_poi, color='black', lw=1.5, linestyle=':',  label=f'Poisson {yval_poi}')
    ax.set_xlabel('t (扩散时间，对数轴)', fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

plt.suptitle('RH-022 v2: 热核扩散时间扫描 — 谱统计收敛行为',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('RH022v2_heatkernel_scan.png', dpi=150, bbox_inches='tight')
print("\n图像已保存为 RH022v2_heatkernel_scan.png")

# ============================================================
# 附加：找到最接近 GUE 的 t*
# ============================================================

print("\n" + "="*60)
print("最接近 GUE 的参数（按 GUE 偏差排序）")
print("="*60)
sorted_res = sorted(
    [r for r in all_results if 'HeatKernel' in r['method']],
    key=lambda r: r['sigma_gue']
)
print(f"{'方法':<42} {'格点':<14} {'<r>均值':<9} {'中位数':<8} {'GUE偏差'}")
print("-"*70)
for res in sorted_res[:8]:
    print(f"{res['method']:<42} {res['config']:<14} "
          f"{res['mean_r']:.4f}    {res['med_r']:.4f}   "
          f"{res['sigma_gue']:.2f}σ")

print("\n=== RH-022 v2 计算完成 ===")
