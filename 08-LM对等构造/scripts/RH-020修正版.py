import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def run_experiment_v2(L_max, phi_func, label):
    """
    完全对称的图拉普拉斯：
    边权重 w(u,v) = (g^{kk}(u) + g^{kk}(v)) / 2
    只使用对角度规分量，天然对称，无需后处理。
    """
    print(f"\n{'='*60}")
    print(f"实验: {label}")
    print(f"{'='*60}")

    DIM = 3
    grid_points = list(product(range(L_max+1), repeat=DIM))
    N_pts = len(grid_points)
    point_index = {p: i for i, p in enumerate(grid_points)}
    print(f"格点数: {N_pts}")

    def get_neighbor(u, direction, step):
        u = list(u)
        new_val = u[direction] + step
        if new_val < 0:
            new_val = -new_val
        elif new_val > L_max:
            new_val = 2*L_max - new_val
        u[direction] = new_val
        return tuple(u)

    def compute_metric_diagonal(u):
        """只计算度规的对角分量 g_{kk}(u)，用于图拉普拉斯权重。"""
        g_diag = np.zeros(DIM)
        phi_u = phi_func(u)
        main_term = 1.0 - 2.0 * phi_u
        for k in range(DIM):
            u_pk = get_neighbor(u, k, +1)
            u_mk = get_neighbor(u, k, -1)
            d2phi = phi_func(u_pk) - 2*phi_func(u) + phi_func(u_mk)
            g_diag[k] = main_term + 2.0 * d2phi
        return g_diag

    # 计算所有格点的对角度规分量
    all_g_diag = {u: compute_metric_diagonal(u) for u in grid_points}

    # 验证正定性（对角分量全正）
    pd_count = sum(1 for u in grid_points if np.all(all_g_diag[u] > 0))
    print(f"对角度规正定格点数: {pd_count}/{N_pts}")

    # 构造完全对称的图拉普拉斯
    L_mat = np.zeros((N_pts, N_pts))
    for i, u in enumerate(grid_points):
        g_u = all_g_diag[u]
        for k in range(DIM):
            v = get_neighbor(u, k, +1)
            j = point_index[v]
            if i == j:
                continue  # ghost point 映射到自身，跳过
            g_v = all_g_diag[v]
            # 对角度规分量的倒数（度规逆的对角元素，近似）
            # 对对角度规：g^{kk} = 1/g_{kk}
            g_kk_u = g_u[k]
            g_kk_v = g_v[k]
            if g_kk_u <= 0 or g_kk_v <= 0:
                continue  # 跳过非正定的边
            ginv_kk_u = 1.0 / g_kk_u
            ginv_kk_v = 1.0 / g_kk_v
            w = 0.5 * (ginv_kk_u + ginv_kk_v)  # 边权重：两端点度规逆的平均
            L_mat[i, j] -= w
            L_mat[j, i] -= w  # 直接保证对称
            L_mat[i, i] += w
            L_mat[j, j] += w

    # 验证对称性
    sym_error = np.max(np.abs(L_mat - L_mat.T))
    print(f"矩阵对称性误差: {sym_error:.2e}  (应为机器精度)")

    # 验证半正定性（图拉普拉斯应半正定）
    eigenvalues = np.sort(np.linalg.eigvalsh(L_mat))
    n_negative = np.sum(eigenvalues < -1e-8)
    print(f"负本征值数: {n_negative}  (图拉普拉斯应为0)")

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
    print(f"不同本征值数: {len(unique_eigs)}/{N_pts}")
    print(f"最大重数: {max_mult}  ({max_mult/N_pts:.1%})")
    if max_mult > 1:
        for ev, m in zip(unique_eigs, mults):
            if m > 1:
                print(f"  λ = {ev:+.6f}, 重数 = {m}")

    # 谱统计（去掉零本征值——图拉普拉斯的常数模式）
    eigs_nonzero = eigenvalues[eigenvalues > 1e-8]
    gaps = np.diff(eigs_nonzero)
    gaps_nonzero = gaps[gaps > 1e-8]

    if len(gaps_nonzero) < 3:
        print("有效间距不足，跳过统计")
        return eigenvalues, gaps_nonzero, None, None, label

    mean_gap = np.mean(gaps_nonzero)
    s = gaps_nonzero / mean_gap

    ratios = gaps_nonzero[1:] / gaps_nonzero[:-1]
    mean_r = np.mean(ratios)
    std_r  = np.std(ratios)
    se_r   = std_r / np.sqrt(len(ratios))
    var_s  = np.var(s)

    print(f"\n谱统计:")
    print(f"  有效间距数: {len(gaps_nonzero)}")
    print(f"  <r> = {mean_r:.4f} ± {se_r:.4f}")
    print(f"  GUE: 1.7387 | GOE: 1.5307 | Poisson: 1.3863")
    print(f"  归一化间距方差: {var_s:.4f}")
    print(f"  GUE: ~0.178 | Poisson: ~1.000")
    sigma_from_gue = abs(mean_r - 1.7387) / se_r if se_r > 0 else float('inf')
    print(f"  与 GUE 偏差: {sigma_from_gue:.2f}σ")
    print(f"  间距比中位数: {np.median(ratios):.4f}")
    print(f"  间距比 >2 的比例: {np.mean(ratios > 2):.3f}")
    print(f"  间距比 <0.5 的比例: {np.mean(ratios < 0.5):.3f}")

    return eigenvalues, gaps_nonzero, mean_r, se_r, label


# 势场定义
def phi_symmetric(u):
    return -1.0 / (sum(u) + 0.5)

def phi_asymmetric(u):
    return -1.0 / (u[0]*1 + u[1]*2 + u[2]*3 + 0.5)

# 运行三个实验
results = []
for L_max, phi, lbl in [
    (2, phi_symmetric,  "Exp A v2: 图拉普拉斯 + 对称势场  (27格点)"),
    (2, phi_asymmetric, "Exp B v2: 图拉普拉斯 + 不对称势场 (27格点)"),
    (3, phi_asymmetric, "Exp C v2: 图拉普拉斯 + 不对称势场 (64格点)"),
]:
    res = run_experiment_v2(L_max, phi, lbl)
    results.append(res)

# 可视化
s_th = np.linspace(0, 4.5, 300)
p_gue     = (32/np.pi**2)*s_th**2*np.exp(-4/np.pi*s_th**2)
p_goe     = (np.pi/2)*s_th*np.exp(-np.pi/4*s_th**2)
p_poisson = np.exp(-s_th)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
colors = ['steelblue', 'darkorange', 'forestgreen']

for col, (eigs, gaps, mean_r, se_r, lbl) in enumerate(results):
    if gaps is None or len(gaps) < 3:
        continue
    s_norm = gaps / np.mean(gaps)
    ax = axes[col]
    ax.hist(s_norm, bins=10, density=True, alpha=0.65,
            color=colors[col], edgecolor='white', label='Data')
    ax.plot(s_th, p_gue,     'r-',  lw=2,   label='GUE')
    ax.plot(s_th, p_goe,     'g--', lw=1.5, label='GOE')
    ax.plot(s_th, p_poisson, 'k:',  lw=1.5, label='Poisson')
    title_r = f"<r>={mean_r:.3f}±{se_r:.3f}" if mean_r else ""
    ax.set_title(f"{lbl.split(':')[0]}\n{title_r}", fontsize=9)
    ax.set_xlabel('Normalized gap s')
    ax.set_ylabel('P(s)')
    ax.legend(fontsize=7)
    ax.set_xlim(0, 4.5)
    ax.grid(True, alpha=0.3)

plt.suptitle('RH-020 v2: Fully Symmetric Graph Laplacian', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('RH020v2_spectral_statistics.png', dpi=150, bbox_inches='tight')
print("\n图像已保存为 RH020v2_spectral_statistics.png")
print("\n=== RH-020 修正版计算完成 ===")
