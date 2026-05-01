import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import ks_2samp

# ============================================================
# RH-020: 修正拉普拉斯 + 不对称势场 + 大格点推广
# 三个独立实验:
#   Exp A: 修正拉普拉斯（边上度规）+ 原始势场，27格点
#   Exp B: 不对称势场 + 修正拉普拉斯，27格点
#   Exp C: 不对称势场 + 修正拉普拉斯，64格点 (L=3)
# ============================================================

def run_experiment(L_max, phi_func, label, weights=(1,1,1)):
    """
    通用实验函数。
    L_max: 每个坐标方向最大值（格点为 {0,...,L_max}^3）
    phi_func: 势场函数 phi(u) -> float
    label: 实验标签
    weights: 各向异性权重（用于标题显示）
    """
    print(f"\n{'='*60}")
    print(f"实验: {label}")
    print(f"{'='*60}")

    DIM = 3
    grid_points = list(product(range(L_max+1), repeat=DIM))
    N_pts = len(grid_points)
    point_index = {p: i for i, p in enumerate(grid_points)}
    print(f"格点数: {N_pts}")

    # --- Ghost point 边界处理 ---
    def get_neighbor(u, direction, step):
        u = list(u)
        new_val = u[direction] + step
        if new_val < 0:
            new_val = -new_val
        elif new_val > L_max:
            new_val = 2*L_max - new_val
        u[direction] = new_val
        return tuple(u)

    # --- 计算每个格点的度规 ---
    def compute_metric(u):
        g = np.zeros((DIM, DIM))
        phi_u = phi_func(u)
        main_term = 1.0 - 2.0 * phi_u

        for k in range(DIM):
            for l in range(DIM):
                if k == l:
                    u_pk = get_neighbor(u, k, +1)
                    u_mk = get_neighbor(u, k, -1)
                    d2phi = phi_func(u_pk) - 2*phi_func(u) + phi_func(u_mk)
                    g[k, l] = main_term + 2.0 * d2phi
                else:
                    u_pp = get_neighbor(get_neighbor(u, k, +1), l, +1)
                    u_pm = get_neighbor(get_neighbor(u, k, +1), l, -1)
                    u_mp = get_neighbor(get_neighbor(u, k, -1), l, +1)
                    u_mm = get_neighbor(get_neighbor(u, k, -1), l, -1)
                    d2phi = 0.25*(phi_func(u_pp) - phi_func(u_pm)
                                  - phi_func(u_mp) + phi_func(u_mm))
                    g[k, l] = 2.0 * d2phi
        return g

    all_metrics = {u: compute_metric(u) for u in grid_points}

    # 验证正定性
    pd_count = sum(1 for u in grid_points
                   if np.all(np.linalg.eigvalsh(all_metrics[u]) > 0))
    print(f"正定度规格点数: {pd_count}/{N_pts}")

    # --- 修正拉普拉斯：使用边上的度规 (g(u)+g(v))/2 ---
    def build_laplacian_symmetric():
        """
        对称拉普拉斯：边 (u,v) 的权重使用两端点度规的平均值。
        保证 L[i,j] = L[j,i]，无需后处理。
        """
        L_mat = np.zeros((N_pts, N_pts))

        for i, u in enumerate(grid_points):
            g_u = all_metrics[u]

            for k in range(DIM):
                # 对角项：g^{kk} 的贡献
                u_pk = get_neighbor(u, k, +1)
                u_mk = get_neighbor(u, k, -1)
                j_pk = point_index[u_pk]
                j_mk = point_index[u_mk]

                # 边 (u, u+ek) 的度规：平均值
                g_pk = all_metrics[u_pk]
                g_edge_p = (g_u + g_pk) / 2
                try:
                    ginv_p = np.linalg.inv(g_edge_p)
                except np.linalg.LinAlgError:
                    ginv_p = np.linalg.pinv(g_edge_p)

                # 边 (u, u-ek) 的度规：平均值
                g_mk = all_metrics[u_mk]
                g_edge_m = (g_u + g_mk) / 2
                try:
                    ginv_m = np.linalg.inv(g_edge_m)
                except np.linalg.LinAlgError:
                    ginv_m = np.linalg.pinv(g_edge_m)

                coeff_p = ginv_p[k, k]
                coeff_m = ginv_m[k, k]

                L_mat[i, j_pk] += coeff_p
                L_mat[i, j_mk] += coeff_m
                L_mat[i, i]    -= (coeff_p + coeff_m)

            for k in range(DIM):
                for l in range(k+1, DIM):
                    u_pp = get_neighbor(get_neighbor(u, k, +1), l, +1)
                    u_pk_only = get_neighbor(u, k, +1)
                    u_pl_only = get_neighbor(u, l, +1)

                    j_pp = point_index[u_pp]
                    j_pk = point_index[u_pk_only]
                    j_pl = point_index[u_pl_only]

                    # 使用 u 处的度规逆（非对角项的边定义较复杂，用顶点度规）
                    g_inv_u = np.linalg.inv(g_u) if abs(np.linalg.det(g_u)) > 1e-12 \
                              else np.linalg.pinv(g_u)
                    coeff = 2 * g_inv_u[k, l]

                    L_mat[i, j_pp] += coeff
                    L_mat[i, j_pk] -= coeff
                    L_mat[i, j_pl] -= coeff
                    L_mat[i, i]    += coeff

        return L_mat

    L_mat = build_laplacian_symmetric()

    # 检查对称性
    sym_error = np.max(np.abs(L_mat - L_mat.T))
    print(f"矩阵对称性误差（修正后）: {sym_error:.2e}")

    # 对称化消除数值残差
    L_sym = (L_mat + L_mat.T) / 2

    # --- 计算本征值 ---
    eigenvalues = np.sort(np.linalg.eigvalsh(L_sym))

    # --- 简并分析 ---
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
    n_unique = len(unique_eigs)
    print(f"不同本征值数: {n_unique}/{N_pts}")
    print(f"最大重数: {max_mult}  ({max_mult/N_pts:.1%})")
    if max_mult > 1:
        for ev, m in zip(unique_eigs, mults):
            if m > 1:
                print(f"  λ = {ev:+.6f}, 重数 = {m}")

    # --- 谱统计 ---
    gaps = np.diff(eigenvalues)
    # 去掉零间距（简并导致）
    gaps_nonzero = gaps[gaps > 1e-8]
    mean_gap = np.mean(gaps_nonzero)
    s = gaps_nonzero / mean_gap  # 归一化间距

    ratios = gaps_nonzero[1:] / gaps_nonzero[:-1]
    mean_r = np.mean(ratios)
    std_r  = np.std(ratios)
    se_r   = std_r / np.sqrt(len(ratios))

    var_s = np.var(s)

    print(f"\n谱统计:")
    print(f"  有效间距数: {len(gaps_nonzero)}")
    print(f"  <r> = {mean_r:.4f} ± {se_r:.4f}")
    print(f"  GUE: 1.74 | GOE: 1.53 | Poisson: 1.39")
    print(f"  归一化间距方差: {var_s:.4f}")
    print(f"  GUE: ~0.178 | Poisson: ~1.000")

    # 与 GUE 的偏差（sigma 数）
    sigma_from_gue = abs(mean_r - 1.7387) / se_r
    print(f"  与 GUE 偏差: {sigma_from_gue:.2f}σ")

    return eigenvalues, gaps_nonzero, mean_r, se_r, label

# ============================================================
# 定义三个实验的势场
# ============================================================

# 实验 A：原始对称势场（修正拉普拉斯）
def phi_symmetric(u):
    return -1.0 / (sum(u) + 0.5)

# 实验 B：不对称势场（权重 1:2:3）
def phi_asymmetric(u):
    weighted = u[0]*1 + u[1]*2 + u[2]*3
    return -1.0 / (weighted + 0.5)

# 实验 C：不对称势场 + 更大格点 L=3（64格点）
def phi_asymmetric_L3(u):
    weighted = u[0]*1 + u[1]*2 + u[2]*3
    return -1.0 / (weighted + 0.5)

# ============================================================
# 运行实验
# ============================================================

results = []

eigs_A, gaps_A, r_A, se_A, lbl_A = run_experiment(
    L_max=2, phi_func=phi_symmetric,
    label="Exp A: 修正拉普拉斯 + 对称势场 (27格点)")
results.append((eigs_A, gaps_A, r_A, se_A, lbl_A))

eigs_B, gaps_B, r_B, se_B, lbl_B = run_experiment(
    L_max=2, phi_func=phi_asymmetric,
    label="Exp B: 修正拉普拉斯 + 不对称势场 (27格点)")
results.append((eigs_B, gaps_B, r_B, se_B, lbl_B))

eigs_C, gaps_C, r_C, se_C, lbl_C = run_experiment(
    L_max=3, phi_func=phi_asymmetric_L3,
    label="Exp C: 修正拉普拉斯 + 不对称势场 (64格点)")
results.append((eigs_C, gaps_C, r_C, se_C, lbl_C))

# ============================================================
# 汇总对比
# ============================================================

print("\n" + "="*60)
print("汇总对比")
print("="*60)
print(f"{'实验':<45} {'<r>':<8} {'±SE':<8} {'与GUE偏差'}")
print("-"*70)
for _, _, r, se, lbl in results:
    sigma = abs(r - 1.7387) / se
    print(f"{lbl:<45} {r:.4f}   ±{se:.4f}   {sigma:.2f}σ")
print(f"{'GUE 理论值':<45} 1.7387")
print(f"{'GOE 理论值':<45} 1.5307")
print(f"{'Poisson 理论值':<45} 1.3863")

# ============================================================
# 可视化：三个实验的间距分布对比
# ============================================================

fig, axes = plt.subplots(2, 3, figsize=(15, 9))

s_theory = np.linspace(0, 4.5, 300)
p_gue     = (32/np.pi**2) * s_theory**2 * np.exp(-4/np.pi * s_theory**2)
p_goe     = (np.pi/2) * s_theory * np.exp(-np.pi/4 * s_theory**2)
p_poisson = np.exp(-s_theory)

colors = ['steelblue', 'darkorange', 'forestgreen']

for col, (eigs, gaps, mean_r, se_r, lbl) in enumerate(results):
    s_norm = gaps / np.mean(gaps)

    # 上行：归一化间距分布 P(s)
    ax = axes[0, col]
    ax.hist(s_norm, bins=8, density=True, alpha=0.65,
            color=colors[col], edgecolor='white', label='Data')
    ax.plot(s_theory, p_gue,     'r-',  lw=2, label='GUE')
    ax.plot(s_theory, p_goe,     'g--', lw=1.5, label='GOE')
    ax.plot(s_theory, p_poisson, 'k:',  lw=1.5, label='Poisson')
    ax.set_xlabel('Normalized gap s')
    ax.set_ylabel('P(s)')
    short_lbl = lbl.split(':')[0]
    ax.set_title(f'{short_lbl}\n<r>={mean_r:.3f}±{se_r:.3f}')
    ax.legend(fontsize=7)
    ax.set_xlim(0, 4)
    ax.grid(True, alpha=0.3)

    # 下行：本征值谱（阶梯函数 N(λ)）
    ax2 = axes[1, col]
    ax2.step(eigs, np.arange(1, len(eigs)+1),
             where='post', color=colors[col], lw=1.5)
    ax2.set_xlabel('Eigenvalue λ')
    ax2.set_ylabel('Cumulative count N(λ)')
    ax2.set_title(f'{short_lbl}\nSpectrum ({len(eigs)} eigenvalues)')
    ax2.grid(True, alpha=0.3)

plt.suptitle('RH-020: GR Metric Laplacian Spectral Statistics',
             fontsize=13, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig('RH020_spectral_statistics.png', dpi=150, bbox_inches='tight')
print("\n图像已保存为 RH020_spectral_statistics.png")

# ============================================================
# 附加：Exp C（64格点）的详细间距统计
# ============================================================

print("\n" + "="*60)
print("Exp C（64格点）详细统计")
print("="*60)
s_C = gaps_C / np.mean(gaps_C)
print(f"  归一化间距均值: {np.mean(s_C):.4f} (理论=1.000)")
print(f"  归一化间距方差: {np.var(s_C):.4f}")
print(f"  GUE方差预测: ~0.178")
print(f"  Poisson方差预测: ~1.000")

# 间距比的分布
ratios_C = gaps_C[1:] / gaps_C[:-1]
print(f"  间距比 <r>: {np.mean(ratios_C):.4f} ± {np.std(ratios_C)/np.sqrt(len(ratios_C)):.4f}")
print(f"  间距比中位数: {np.median(ratios_C):.4f}")
print(f"  间距比 >2 的比例: {np.mean(ratios_C > 2):.3f}")
print(f"  间距比 <0.5 的比例: {np.mean(ratios_C < 0.5):.3f}")

print("\n=== RH-020 计算完成 ===")
