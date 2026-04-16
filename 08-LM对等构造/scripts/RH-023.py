import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# RH-023: 完整 GR 度规拉普拉斯（含非对角项）
#
# 核心：打破乘积结构需要非对角度规分量 g_{kl}, k≠l
# 有限差分：(g^{kl} ∂_k ∂_l f)(u) 用对称差分格式
#   ∂_k ∂_l f ≈ [f(u+e_k+e_l) - f(u+e_k-e_l)
#               - f(u-e_k+e_l) + f(u-e_k-e_l)] / 4
# 天然对称：对角差分算子对称，交叉差分算子对称
# ============================================================

DIM = 3

def get_grid(L_max):
    pts = list(product(range(L_max+1), repeat=DIM))
    idx = {p: i for i, p in enumerate(pts)}
    return pts, idx

def reflect(coord, L_max):
    """反射边界条件"""
    if coord < 0:       return -coord
    if coord > L_max:   return 2*L_max - coord
    return coord

def nbr(u, shifts, L_max):
    """u 沿 shifts（字典 {dim: delta}）移动后的格点"""
    ul = list(u)
    for k, d in shifts.items():
        ul[k] = reflect(ul[k] + d, L_max)
    return tuple(ul)

# ============================================================
# 完整度规（含非对角项）
# ============================================================

def phi(u):
    """不对称势场"""
    return -1.0 / (u[0]*1 + u[1]*2 + u[2]*3 + 0.5)

def dphi(u, k, L_max):
    """一阶偏导数（中心差分）"""
    up = nbr(u, {k: +1}, L_max)
    um = nbr(u, {k: -1}, L_max)
    return (phi(up) - phi(um)) / 2.0

def d2phi_diag(u, k, L_max):
    """二阶对角偏导数"""
    up = nbr(u, {k: +1}, L_max)
    um = nbr(u, {k: -1}, L_max)
    return phi(up) - 2*phi(u) + phi(um)

def d2phi_cross(u, k, l, L_max):
    """二阶交叉偏导数"""
    upp = nbr(u, {k: +1, l: +1}, L_max)
    upm = nbr(u, {k: +1, l: -1}, L_max)
    ump = nbr(u, {k: -1, l: +1}, L_max)
    umm = nbr(u, {k: -1, l: -1}, L_max)
    return (phi(upp) - phi(upm) - phi(ump) + phi(umm)) / 4.0

def get_full_metric(u, L_max):
    """
    完整 3x3 度规张量 g_{kl}(u)。
    线性化 GR：g_{kl} = (1-2Phi)delta_{kl} + 2 partial_k partial_l Phi
    """
    phi_u = phi(u)
    main  = 1.0 - 2.0 * phi_u
    g = np.zeros((DIM, DIM))
    for k in range(DIM):
        g[k, k] = main + 2.0 * d2phi_diag(u, k, L_max)
        for l in range(k+1, DIM):
            cross = 2.0 * d2phi_cross(u, k, l, L_max)
            g[k, l] = cross
            g[l, k] = cross
    return g

def get_metric_inv(g):
    """
    度规逆 g^{kl}。若不正定，返回 None。
    """
    try:
        eigvals = np.linalg.eigvalsh(g)
        if np.min(eigvals) <= 0:
            return None
        return np.linalg.inv(g)
    except np.linalg.LinAlgError:
        return None

# ============================================================
# 完整 GR 拉普拉斯算子（对称有限差分）
#
# Laplacian f = (1/sqrt(g)) partial_k (sqrt(g) g^{kl} partial_l f)
# 离散化（在格点 u 处）：
#
# 对角项 k=l：
#   contrib = g^{kk}(u) * [f(u+e_k) - 2f(u) + f(u-e_k)]
#           + (1/2)(g^{kk}(u+e_k) - g^{kk}(u-e_k)) * [f(u+e_k) - f(u-e_k)] / 2
#   (用格点 u 处的 g^{kk} 作为主项，梯度修正项保对称性)
#
# 交叉项 k≠l（对称化）：
#   contrib = g^{kl}(u) * [f(u+e_k+e_l) - f(u+e_k-e_l)
#                         - f(u-e_k+e_l) + f(u-e_k-e_l)] / 4
#   乘以 2（k<l 只算一次，需补偿）
# ============================================================

def build_full_gr_laplacian(L_max, strength=1.0):
    """
    构造完整 GR 拉普拉斯（含非对角度规项）。
    strength: 非对角项的耦合强度（0=纯对角，1=完整GR）
    返回对称矩阵。
    """
    pts, idx = get_grid(L_max)
    N = len(pts)

    # 预计算所有格点的度规逆
    ginv_cache = {}
    n_skip = 0
    for u in pts:
        g = get_full_metric(u, L_max)
        ginv = get_metric_inv(g)
        if ginv is None:
            n_skip += 1
            ginv_cache[u] = None
        else:
            ginv_cache[u] = ginv

    L_mat = np.zeros((N, N))

    for i, u in enumerate(pts):
        ginv_u = ginv_cache[u]
        if ginv_u is None:
            continue

        # --- 对角项 k=k ---
        for k in range(DIM):
            gkk = ginv_u[k, k]
            u_p = nbr(u, {k: +1}, L_max)
            u_m = nbr(u, {k: -1}, L_max)
            jp  = idx[u_p]
            jm  = idx[u_m]

            # 主项：g^{kk}(u) * (f_p - 2f_u + f_m)
            L_mat[i, jp] += gkk
            L_mat[i, jm] += gkk
            L_mat[i, i ] -= 2.0 * gkk

            # 梯度修正（保持对称性：用两端平均）
            ginv_p = ginv_cache[u_p]
            ginv_m = ginv_cache[u_m]
            if ginv_p is not None and ginv_m is not None:
                grad_gkk = (ginv_p[k,k] - ginv_m[k,k]) / 4.0
                L_mat[i, jp] += grad_gkk
                L_mat[i, jm] -= grad_gkk

        # --- 交叉项 k≠l ---
        for k in range(DIM):
            for l in range(k+1, DIM):
                gkl = ginv_u[k, l] * strength
                if abs(gkl) < 1e-12:
                    continue

                u_pp = nbr(u, {k: +1, l: +1}, L_max)
                u_pm = nbr(u, {k: +1, l: -1}, L_max)
                u_mp = nbr(u, {k: -1, l: +1}, L_max)
                u_mm = nbr(u, {k: -1, l: -1}, L_max)

                j_pp = idx[u_pp]
                j_pm = idx[u_pm]
                j_mp = idx[u_mp]
                j_mm = idx[u_mm]

                # 交叉差分：g^{kl} * (f_{++} - f_{+-} - f_{-+} + f_{--}) / 4
                # 系数 2 因为 k<l 只算一次
                coeff = gkl / 2.0  # 1/4 * 2 = 1/2
                L_mat[i, j_pp] += coeff
                L_mat[i, j_pm] -= coeff
                L_mat[i, j_mp] -= coeff
                L_mat[i, j_mm] += coeff

    # 对称化（消除数值误差）
    L_sym = (L_mat + L_mat.T) / 2.0
    return L_sym, pts, idx, n_skip


def analyze_spectrum(eigenvalues, label, do_unfold=True, verbose=True):
    """谱统计分析（展开版）"""
    n_neg   = np.sum(eigenvalues < -1e-8)
    N       = len(eigenvalues)

    if verbose:
        print(f"{'='*60}")
        print(f"实验: {label}")
        print(f"{'='*60}")
        print(f"N={N}, 负本征值: {n_neg}")
        print(f"本征值范围: [{eigenvalues[0]:.4f}, {eigenvalues[-1]:.4f}]")

    # 去掉最小本征值（零模）
    eigs = eigenvalues[1:]

    if len(eigs) < 10:
        if verbose: print("本征值数不足")
        return None

    if do_unfold:
        try:
            ranks  = np.arange(1, len(eigs)+1, dtype=float)
            coeffs = np.polyfit(eigs, ranks, min(5, len(eigs)//4))
            eigs_u = np.polyval(coeffs, eigs)
        except Exception:
            eigs_u = eigs
    else:
        eigs_u = eigs

    gaps     = np.diff(eigs_u)
    gaps_pos = gaps[gaps > 1e-10]
    if len(gaps_pos) < 5:
        if verbose: print("有效间距不足")
        return None

    s        = gaps_pos / np.mean(gaps_pos)
    ratios   = gaps_pos[1:] / gaps_pos[:-1]
    mean_r   = np.mean(ratios)
    se_r     = np.std(ratios) / np.sqrt(len(ratios))
    med_r    = np.median(ratios)
    var_s    = np.var(s)
    fgt2     = np.mean(ratios > 2)
    flt05    = np.mean(ratios < 0.5)
    sig_gue  = abs(mean_r - 1.7387) / se_r if se_r > 0 else np.inf
    sig_med  = abs(med_r  - 1.47)   / (0.5/np.sqrt(len(ratios)))

    if verbose:
        print(f"谱统计 (展开后):")
        print(f"  <r>均值:   {mean_r:.4f} ± {se_r:.4f}  (GUE偏差: {sig_gue:.2f}σ)")
        print(f"  <r>中位数: {med_r:.4f}  (GUE≈1.47, Poisson≈1.00)")
        print(f"  方差:      {var_s:.4f}  (GUE≈0.178, Poisson≈1.000)")
        print(f"  >2比例:    {fgt2:.3f}   <0.5比例: {flt05:.3f}")
        print(f"  中位数偏离 GUE: {sig_med:.2f}σ")

    return {
        'label': label, 'eigenvalues': eigenvalues,
        'eigs_u': eigs_u, 's': s, 'ratios': ratios,
        'mean_r': mean_r, 'se_r': se_r, 'med_r': med_r,
        'var_s': var_s, 'sig_gue': sig_gue, 'sig_med': sig_med,
        'fgt2': fgt2, 'flt05': flt05, 'n_neg': n_neg,
    }


# ============================================================
# 实验：扫描非对角项强度 strength
# ============================================================

print("" + "#"*65)
print("# RH-023: 完整 GR 拉普拉斯 — 非对角项强度扫描")
print("#"*65)

results = []

for L_max in [2, 3]:
    N_pts = (L_max+1)**3
    print(f"{'='*65}")
    print(f"格点配置: L={L_max} ({N_pts}格点)")
    print(f"{'='*65}")

    strengths = [0.0, 0.25, 0.5, 0.75, 1.0]
    for s_val in strengths:
        label = f"GR-Lap s={s_val:.2f}  [L={L_max}, {N_pts}pts]"
        L_mat, pts, idx, n_skip = build_full_gr_laplacian(L_max, strength=s_val)

        sym_err = np.max(np.abs(L_mat - L_mat.T))
        eigs    = np.sort(np.linalg.eigvalsh(L_mat))
        density = np.mean(np.abs(L_mat) > 1e-10)

        print(f"[构造] strength={s_val:.2f}: sym_err={sym_err:.2e}, "              f"density={density:.3f}, skip={n_skip}")

        res = analyze_spectrum(eigs, label, do_unfold=True, verbose=True)
        if res is not None:
            res['L_max']    = L_max
            res['strength'] = s_val
            res['density']  = density
            results.append(res)


# ============================================================
# 汇总
# ============================================================

print("" + "="*80)
print("RH-023 汇总：非对角项强度 vs 谱统计")
print("="*80)
print(f"{'实验':<42} {'中位数':<9} {'方差':<8} {'均值':<8} {'GUE偏差(中位)'}")
print("-"*80)
for res in results:
    print(f"{res['label']:<42} {res['med_r']:.4f}    "
          f"{res['var_s']:.4f}   {res['mean_r']:.4f}   {res['sig_med']:.2f}σ")
print(f"{'GUE 理论':<42} ~1.47      0.178    1.739")
print(f"{'Poisson 理论':<42} ~1.00      1.000    1.386")


# ============================================================
# 可视化
# ============================================================

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for L_max, color, marker in [(2, 'steelblue', 'o-'), (3, 'crimson', 's--')]:
    sub = [r for r in results if r['L_max'] == L_max]
    if not sub: continue
    sv   = [r['strength'] for r in sub]
    medv = [r['med_r']    for r in sub]
    varv = [r['var_s']    for r in sub]
    mnv  = [r['mean_r']   for r in sub]
    lbl  = f"L={L_max}"

    axes[0].plot(sv, medv,  marker, color=color, lw=2, label=lbl, markersize=7)
    axes[1].plot(sv, varv,  marker, color=color, lw=2, label=lbl, markersize=7)
    axes[2].plot(sv, mnv,   marker, color=color, lw=2, label=lbl, markersize=7)

for ax, (gue_v, poi_v, ylabel, title) in zip(axes, [
    (1.47,  1.00,  '<r> 中位数',       '中位数 vs 非对角项强度'),
    (0.178, 1.000, '归一化间距方差',   '方差 vs 非对角项强度'),
    (1.739, 1.386, '<r> 均值',         '均值 vs 非对角项强度'),
]):
    ax.axhline(gue_v, color='red',   lw=2,   linestyle='--', label=f'GUE {gue_v}')
    ax.axhline(poi_v, color='black', lw=1.5, linestyle=':',  label=f'Poisson {poi_v}')
    ax.set_xlabel('非对角项强度 strength', fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

plt.suptitle('RH-023: 完整 GR 拉普拉斯 — 非对角耦合对谱统计的影响',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('RH023_offdiag_scan.png', dpi=150, bbox_inches='tight')
print("图像已保存为 RH023_offdiag_scan.png")
print("=== RH-023 计算完成 ===")
