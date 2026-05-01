import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# RH-021: 势场变体 + 谱形因子 + 125格点扩展
#
# Exp A: 软化势场 alpha=0.5，64格点
# Exp B: 线性势场，64格点
# Exp C: 原始势场，125格点 (L=4)
# Exp D: 软化势场 alpha=0.5，125格点
# 所有实验均计算谱形因子 K(tau)
# ============================================================

def build_graph_laplacian(L_max, phi_func):
    """
    完全对称图拉普拉斯（RH-020 v2 确认的构造）。
    返回：(eigenvalues, L_mat, grid_points)
    """
    DIM = 3
    grid_points = list(product(range(L_max+1), repeat=DIM))
    N_pts = len(grid_points)
    point_index = {p: i for i, p in enumerate(grid_points)}

    def get_neighbor(u, direction, step):
        u = list(u)
        new_val = u[direction] + step
        if new_val < 0:
            new_val = -new_val
        elif new_val > L_max:
            new_val = 2*L_max - new_val
        u[direction] = new_val
        return tuple(u)

    def compute_g_diag(u):
        g_diag = np.zeros(DIM)
        phi_u = phi_func(u)
        main_term = 1.0 - 2.0 * phi_u
        for k in range(DIM):
            u_pk = get_neighbor(u, k, +1)
            u_mk = get_neighbor(u, k, -1)
            d2phi = phi_func(u_pk) - 2*phi_func(u) + phi_func(u_mk)
            g_diag[k] = main_term + 2.0 * d2phi
        return g_diag

    all_g_diag = {u: compute_g_diag(u) for u in grid_points}

    L_mat = np.zeros((N_pts, N_pts))
    n_skip = 0
    for i, u in enumerate(grid_points):
        g_u = all_g_diag[u]
        for k in range(DIM):
            v = get_neighbor(u, k, +1)
            j = point_index[v]
            if i == j:
                continue
            g_v = all_g_diag[v]
            g_kk_u = g_u[k]
            g_kk_v = g_v[k]
            if g_kk_u <= 0 or g_kk_v <= 0:
                n_skip += 1
                continue
            w = 0.5 * (1.0/g_kk_u + 1.0/g_kk_v)
            L_mat[i, j] -= w
            L_mat[j, i] -= w
            L_mat[i, i] += w
            L_mat[j, j] += w

    eigenvalues = np.sort(np.linalg.eigvalsh(L_mat))
    return eigenvalues, L_mat, grid_points, n_skip


def spectral_form_factor(eigenvalues, tau_max=20.0, n_tau=500):
    """
    计算谱形因子 K(tau) = (1/N^2) |sum_n exp(i*lambda_n*tau)|^2
    展开折叠（unfold）后的本征值。
    """
    # 本征值展开（unfold）：使累积态密度均匀
    N = len(eigenvalues)
    # 用多项式拟合累积态密度
    ranks = np.arange(1, N+1, dtype=float)
    # 三次多项式拟合 N(lambda)
    coeffs = np.polyfit(eigenvalues, ranks, 3)
    unfolded = np.polyval(coeffs, eigenvalues)

    tau_vals = np.linspace(0.01, tau_max, n_tau)
    K_vals = np.zeros(n_tau)
    for idx, tau in enumerate(tau_vals):
        phases = np.exp(1j * 2 * np.pi * unfolded * tau)
        K_vals[idx] = np.abs(np.sum(phases))**2 / N**2

    return tau_vals, K_vals


def analyze_spectrum(eigenvalues, label, verbose=True):
    """
    完整谱分析：简并、谱统计、谱形因子。
    """
    N_pts = len(eigenvalues)
    if verbose:
        print(f"\n{'='*60}")
        print(f"实验: {label}")
        print(f"{'='*60}")
        print(f"格点数: {N_pts}")

    # 简并分析
    tol = 1e-6
    unique_eigs, mults = [], []
    cur, cnt = eigenvalues[0], 1
    for ev in eigenvalues[1:]:
        if abs(ev - cur) < tol:
            cnt += 1
        else:
            unique_eigs.append(cur); mults.append(cnt)
            cur, cnt = ev, 1
    unique_eigs.append(cur); mults.append(cnt)
    max_mult = max(mults)
    if verbose:
        print(f"不同本征值数: {len(unique_eigs)}/{N_pts}")
        print(f"最大重数: {max_mult}  ({max_mult/N_pts:.1%})")

    # 谱统计（去掉零本征值）
    eigs_nz = eigenvalues[eigenvalues > 1e-8]
    gaps = np.diff(eigs_nz)
    gaps_nz = gaps[gaps > 1e-8]

    if len(gaps_nz) < 5:
        if verbose:
            print("有效间距不足，跳过统计")
        return None

    mean_gap = np.mean(gaps_nz)
    s = gaps_nz / mean_gap
    ratios = gaps_nz[1:] / gaps_nz[:-1]
    mean_r = np.mean(ratios)
    se_r   = np.std(ratios) / np.sqrt(len(ratios))
    var_s  = np.var(s)
    med_r  = np.median(ratios)
    frac_gt2  = np.mean(ratios > 2)
    frac_lt05 = np.mean(ratios < 0.5)
    sigma_gue = abs(mean_r - 1.7387) / se_r if se_r > 0 else float('inf')

    if verbose:
        print(f"\n谱统计:")
        print(f"  有效间距数: {len(gaps_nz)}")
        print(f"  <r>均值:    {mean_r:.4f} ± {se_r:.4f}")
        print(f"  <r>中位数:  {med_r:.4f}")
        print(f"  GUE: 1.7387 | GOE: 1.5307 | Poisson: 1.3863")
        print(f"  归一化间距方差: {var_s:.4f}")
        print(f"  GUE: ~0.178 | Poisson: ~1.000")
        print(f"  与 GUE 偏差: {sigma_gue:.2f}σ")
        print(f"  间距比 >2 的比例: {frac_gt2:.3f}  (GUE~0.08, Poisson~0.135)")
        print(f"  间距比 <0.5 的比例: {frac_lt05:.3f}  (GUE~0.08, Poisson~0.135)")

    # 谱形因子
    tau_vals, K_vals = spectral_form_factor(eigs_nz)

    return {
        'label': label,
        'eigenvalues': eigenvalues,
        'gaps': gaps_nz,
        's': s,
        'ratios': ratios,
        'mean_r': mean_r,
        'se_r': se_r,
        'med_r': med_r,
        'var_s': var_s,
        'sigma_gue': sigma_gue,
        'frac_gt2': frac_gt2,
        'frac_lt05': frac_lt05,
        'tau_vals': tau_vals,
        'K_vals': K_vals,
        'max_mult': max_mult,
        'n_unique': len(unique_eigs),
    }


# ============================================================
# 势场定义
# ============================================================

def phi_original(u):
    """原始不对称势场（RH-020 v2 Exp B/C）"""
    return -1.0 / (u[0]*1 + u[1]*2 + u[2]*3 + 0.5)

def phi_soft(u, alpha=0.5):
    """软化势场：衰减更慢，动态范围更小"""
    r = u[0]*1 + u[1]*2 + u[2]*3 + 0.5
    return -1.0 / (r ** alpha)

def phi_linear(u):
    """线性势场：完全消除曲率项"""
    return -0.05 * (u[0]*1 + u[1]*2 + u[2]*3)

def phi_log(u):
    """对数势场：更温和的衰减"""
    r = u[0]*1 + u[1]*2 + u[2]*3 + 1.0
    return -0.3 * np.log(r) / r


# ============================================================
# 运行实验
# ============================================================

experiments = [
    (2, lambda u: phi_soft(u, 0.5),  "Exp A: 软化势场 α=0.5  (64格点, L=3)"),
    (2, phi_linear,                   "Exp B: 线性势场        (64格点, L=3)"),
    (3, phi_original,                 "Exp C: 原始势场        (125格点, L=4)"),
    (3, lambda u: phi_soft(u, 0.5),  "Exp D: 软化势场 α=0.5  (125格点, L=4)"),
    (3, phi_log,                      "Exp E: 对数势场        (125格点, L=4)"),
]

results = []
for L_max, phi_func, label in experiments:
    eigs, L_mat, gpts, n_skip = build_graph_laplacian(L_max, phi_func)
    N_pts = (L_max+1)**3
    n_pd = sum(1 for u in gpts
               if all(1.0 - 2*phi_func(u) + 2*(phi_func(list(u).__setitem__(k, u[k]+1) or tuple(u))
                      if False else 0) > 0 for k in range(3)))
    sym_err = np.max(np.abs(L_mat - L_mat.T))
    n_neg   = np.sum(eigs < -1e-8)
    print(f"\n[构造] {label}")
    print(f"  格点数: {N_pts}, 跳过边: {n_skip}, 对称误差: {sym_err:.2e}, 负本征值: {n_neg}")
    res = analyze_spectrum(eigs, label, verbose=True)
    if res:
        results.append(res)


# ============================================================
# 汇总对比表
# ============================================================

print("\n" + "="*75)
print("汇总对比")
print("="*75)
print(f"{'实验':<42} {'<r>均值':<9} {'中位数':<8} {'方差':<8} {'GUE偏差':<9} {'>2比例'}")
print("-"*75)
for res in results:
    print(f"{res['label']:<42} {res['mean_r']:.4f}    {res['med_r']:.4f}   "
          f"{res['var_s']:.4f}   {res['sigma_gue']:.2f}σ     {res['frac_gt2']:.3f}")
print(f"{'GUE 理论':<42} 1.7387    ~1.47    0.178")
print(f"{'Poisson 理论':<42} 1.3863    ~1.00    1.000")


# ============================================================
# 可视化：4行图
# 行1: P(s) 间距分布
# 行2: 间距比分布
# 行3: 谱形因子 K(tau)
# 行4: 本征值阶梯函数 N(lambda)
# ============================================================

n_exp = len(results)
fig, axes = plt.subplots(4, n_exp, figsize=(4*n_exp, 16))

s_th = np.linspace(0, 5, 400)
p_gue     = (32/np.pi**2)*s_th**2*np.exp(-4/np.pi*s_th**2)
p_goe     = (np.pi/2)*s_th*np.exp(-np.pi/4*s_th**2)
p_poisson = np.exp(-s_th)

colors = ['steelblue', 'darkorange', 'forestgreen', 'crimson', 'purple']

for col, res in enumerate(results):
    color = colors[col % len(colors)]
    short = res['label'].split(':')[0]

    # 行1：P(s) 间距分布
    ax = axes[0, col]
    ax.hist(res['s'], bins=10, density=True, alpha=0.65,
            color=color, edgecolor='white')
    ax.plot(s_th, p_gue,     'r-',  lw=2,   label='GUE')
    ax.plot(s_th, p_goe,     'g--', lw=1.5, label='GOE')
    ax.plot(s_th, p_poisson, 'k:',  lw=1.5, label='Poisson')
    ax.set_title(f"{short}\n<r>={res['mean_r']:.3f}±{res['se_r']:.3f}", fontsize=9)
    ax.set_xlabel('s'); ax.set_ylabel('P(s)')
    ax.legend(fontsize=6); ax.set_xlim(0, 5); ax.grid(True, alpha=0.3)

    # 行2：间距比分布
    ax2 = axes[1, col]
    ax2.hist(res['ratios'], bins=15, density=True, alpha=0.65,
             color=color, edgecolor='white')
    ax2.axvline(1.7387, color='r', lw=2, linestyle='-',  label='GUE')
    ax2.axvline(1.3863, color='k', lw=1.5, linestyle=':', label='Poisson')
    ax2.axvline(res['med_r'], color='navy', lw=1.5, linestyle='--',
                label=f'med={res["med_r"]:.2f}')
    ax2.set_xlabel('r = gap ratio'); ax2.set_ylabel('P(r)')
    ax2.set_title(f'Gap ratio dist.\nmed={res["med_r"]:.3f}', fontsize=9)
    ax2.legend(fontsize=6); ax2.set_xlim(0, 6); ax2.grid(True, alpha=0.3)

    # 行3：谱形因子 K(tau)
    ax3 = axes[2, col]
    tau_gue_ramp = res['tau_vals']  # GUE: K(tau) = tau for tau < 1
    ax3.plot(res['tau_vals'], res['K_vals'], color=color, lw=1.5, label='Data')
    ax3.axhline(1.0, color='gray', lw=1, linestyle='--', label='Plateau=1')
    # GUE 预测：线性斜率
    tau_ramp = res['tau_vals'][res['tau_vals'] <= 1]
    ax3.plot(tau_ramp, tau_ramp, 'r-', lw=2, label='GUE ramp')
    ax3.set_xlabel('τ'); ax3.set_ylabel('K(τ)')
    ax3.set_title('Spectral Form Factor', fontsize=9)
    ax3.legend(fontsize=6); ax3.set_ylim(0, 3); ax3.grid(True, alpha=0.3)

    # 行4：本征值阶梯函数
    ax4 = axes[3, col]
    eigs = res['eigenvalues']
    ax4.step(eigs, np.arange(1, len(eigs)+1), where='post',
             color=color, lw=1.5)
    ax4.set_xlabel('λ'); ax4.set_ylabel('N(λ)')
    ax4.set_title(f'Spectrum ({len(eigs)} eigs)', fontsize=9)
    ax4.grid(True, alpha=0.3)

plt.suptitle('RH-021: Potential Variants + Spectral Form Factor',
             fontsize=13, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig('RH021_analysis.png', dpi=150, bbox_inches='tight')
print("\n图像已保存为 RH021_analysis.png")


# ============================================================
# 附加：势场动态范围分析（诊断重尾来源）
# ============================================================

print("\n" + "="*60)
print("势场动态范围分析（L=3，64格点）")
print("="*60)

for phi_func, name in [
    (phi_original,              "原始势场"),
    (lambda u: phi_soft(u,0.5), "软化势场 α=0.5"),
    (phi_linear,                "线性势场"),
    (phi_log,                   "对数势场"),
]:
    grid = list(product(range(4), repeat=3))
    weights = []
    for u in grid:
        phi_u = phi_func(u)
        main = 1.0 - 2*phi_u
        # 近似对角度规（用主项估计）
        g_kk_approx = main  # 忽略曲率修正，仅看主项
        if g_kk_approx > 0:
            weights.append(1.0/g_kk_approx)
    weights = np.array(weights)
    print(f"\n{name}:")
    print(f"  度规逆权重范围: [{weights.min():.4f}, {weights.max():.4f}]")
    print(f"  动态范围比: {weights.max()/weights.min():.2f}x")
    print(f"  均值/中位数: {weights.mean():.4f} / {np.median(weights):.4f}")

print("\n=== RH-021 计算完成 ===")
