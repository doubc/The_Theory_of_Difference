import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# RH-019: GR 度规拉普拉斯的谱统计
# 宏观格点 {0,1,2}^3，27 个格点
# ============================================================

# --- 1. 基本设置 ---

L = 2  # 每个坐标方向的最大值
DIM = 3  # 空间维度

# 生成所有 27 个格点，按字典序排列
grid_points = list(product(range(L+1), repeat=DIM))  # 27 个 (u1, u2, u3)
N_pts = len(grid_points)  # 27
point_index = {p: i for i, p in enumerate(grid_points)}

print(f"格点数: {N_pts}")
print(f"格点示例: {grid_points[:5]}")

# --- 2. 势场 ---

def Phi(u):
    """正规化势场 Phi(u) = -1 / (|u|_1 + 0.5)"""
    norm1 = sum(u)
    return -1.0 / (norm1 + 0.5)

# 验证势场值
print("\n势场值:")
for r in range(7):
    print(f"  |u|_1 = {r}: Phi = {-2/(2*r+1):.6f}")

# --- 3. 在每个格点处计算度规 g_kl(u) ---
# 使用弱场近似度规:
# g_kl(u) = (1 - 2*Phi(u)) * delta_kl + 2 * d^2Phi/du^k du^l
# 其中 d^2Phi 用有限差分计算，边界用 ghost point (Neumann 条件)

def get_neighbor(u, direction, step):
    """
    获取 u 在 direction 方向移动 step 步后的格点。
    若超出边界，用 ghost point (镜像) 处理。
    """
    u = list(u)
    new_val = u[direction] + step
    if new_val < 0:
        new_val = -new_val  # 镜像
    elif new_val > L:
        new_val = 2*L - new_val  # 镜像
    u[direction] = new_val
    return tuple(u)

def compute_metric(u):
    """
    在格点 u 处计算 3x3 度规矩阵 g_kl。
    返回 numpy 3x3 数组。
    """
    g = np.zeros((DIM, DIM))
    phi_u = Phi(u)

    # 主项: (1 - 2*Phi) * delta_kl
    main_term = 1.0 - 2.0 * phi_u

    for k in range(DIM):
        for l in range(DIM):
            if k == l:
                # 对角分量: 主项 + 二阶差分修正
                u_pk = get_neighbor(u, k, +1)
                u_mk = get_neighbor(u, k, -1)
                d2phi_kk = Phi(u_pk) - 2*Phi(u) + Phi(u_mk)
                g[k, l] = main_term + 2.0 * d2phi_kk
            else:
                # 非对角分量: 混合偏导数
                # 用四点差分: (1/4)[Phi(u+ek+el) - Phi(u+ek-el) - Phi(u-ek+el) + Phi(u-ek-el)]
                u_pp = get_neighbor(get_neighbor(u, k, +1), l, +1)
                u_pm = get_neighbor(get_neighbor(u, k, +1), l, -1)
                u_mp = get_neighbor(get_neighbor(u, k, -1), l, +1)
                u_mm = get_neighbor(get_neighbor(u, k, -1), l, -1)
                d2phi_kl = 0.25 * (Phi(u_pp) - Phi(u_pm) - Phi(u_mp) + Phi(u_mm))
                g[k, l] = 2.0 * d2phi_kl

    return g

# 计算所有格点的度规并验证正定性
print("\n验证度规正定性 (前几个格点):")
all_metrics = {}
positive_definite_count = 0
for u in grid_points:
    g = compute_metric(u)
    all_metrics[u] = g
    eigenvalues = np.linalg.eigvalsh(g)
    if np.all(eigenvalues > 0):
        positive_definite_count += 1

print(f"  正定度规格点数: {positive_definite_count} / {N_pts}")

# 打印几个典型格点的度规
for u in [(0,0,0), (1,0,0), (1,1,0), (1,1,1), (2,2,2)]:
    g = all_metrics[u]
    eigs = np.linalg.eigvalsh(g)
    print(f"  u={u}, |u|_1={sum(u)}, 度规本征值: {eigs}")

# --- 4. 构造 27x27 拉普拉斯矩阵 ---
# Laplacian: Delta f(u) = sum_{k,l} g^{kl}(u) * [二阶差分]
# 离散形式:
# Delta f(u) = sum_k g^{kk}(u) * [f(u+ek) - 2f(u) + f(u-ek)]
#            + sum_{k<l} 2*g^{kl}(u) * [f(u+ek+el) - f(u+ek) - f(u+el) + f(u)]

def build_laplacian():
    """构造 27x27 拉普拉斯矩阵"""
    L_mat = np.zeros((N_pts, N_pts))

    for i, u in enumerate(grid_points):
        g = all_metrics[u]
        # 检查度规是否可逆
        det_g = np.linalg.det(g)
        if abs(det_g) < 1e-12:
            # 度规奇异，用正规化处理
            g_inv = np.linalg.pinv(g)
        else:
            g_inv = np.linalg.inv(g)

        # 对角项: sum_k g^{kk} * [f(u+ek) - 2f(u) + f(u-ek)]
        for k in range(DIM):
            u_pk = get_neighbor(u, k, +1)
            u_mk = get_neighbor(u, k, -1)
            j_pk = point_index[u_pk]
            j_mk = point_index[u_mk]

            coeff = g_inv[k, k]
            L_mat[i, j_pk] += coeff
            L_mat[i, j_mk] += coeff
            L_mat[i, i]    -= 2 * coeff

        # 非对角项: sum_{k<l} 2*g^{kl} * [f(u+ek+el) - f(u+ek) - f(u+el) + f(u)]
        for k in range(DIM):
            for l in range(k+1, DIM):
                u_pk_pl = get_neighbor(get_neighbor(u, k, +1), l, +1)
                u_pk    = get_neighbor(u, k, +1)
                u_pl    = get_neighbor(u, l, +1)

                j_pp = point_index[u_pk_pl]
                j_pk = point_index[u_pk]
                j_pl = point_index[u_pl]

                coeff = 2 * g_inv[k, l]
                L_mat[i, j_pp] += coeff
                L_mat[i, j_pk] -= coeff
                L_mat[i, j_pl] -= coeff
                L_mat[i, i]    += coeff

    return L_mat

print("\n构造拉普拉斯矩阵...")
L_mat = build_laplacian()

# 检查矩阵性质
print(f"  矩阵尺寸: {L_mat.shape}")
print(f"  矩阵对称性误差: {np.max(np.abs(L_mat - L_mat.T)):.2e}")
print(f"  行和 (应接近0): max={np.max(np.abs(L_mat.sum(axis=1))):.2e}")

# 对称化（消除数值误差）
L_sym = (L_mat + L_mat.T) / 2
print(f"  对称化后对称性误差: {np.max(np.abs(L_sym - L_sym.T)):.2e}")

# --- 5. 计算本征值 ---
print("\n计算本征值...")
eigenvalues = np.linalg.eigvalsh(L_sym)
eigenvalues_sorted = np.sort(eigenvalues)

print(f"\n全部 {N_pts} 个本征值:")
for i, ev in enumerate(eigenvalues_sorted):
    print(f"  λ_{i+1:2d} = {ev:+.6f}")

# --- 6. 简并分析 ---
print("\n简并分析:")
tolerance = 1e-6
unique_eigs = []
multiplicities = []
current_eig = eigenvalues_sorted[0]
current_mult = 1

for ev in eigenvalues_sorted[1:]:
    if abs(ev - current_eig) < tolerance:
        current_mult += 1
    else:
        unique_eigs.append(current_eig)
        multiplicities.append(current_mult)
        current_eig = ev
        current_mult = 1
unique_eigs.append(current_eig)
multiplicities.append(current_mult)

print(f"  不同本征值数: {len(unique_eigs)}")
print(f"  最大重数: {max(multiplicities)}")
for ev, mult in zip(unique_eigs, multiplicities):
    if mult > 1:
        print(f"  λ = {ev:.6f}, 重数 = {mult}")

# 与 L_A8 比较
print(f"\n  L_A8 中 λ=1 的重数: 11/16 = {11/16:.1%}")
print(f"  GR 度规拉普拉斯中最大重数: {max(multiplicities)}/{N_pts} = {max(multiplicities)/N_pts:.1%}")

# --- 7. 谱统计分析 ---
print("\n谱统计分析:")
gaps = np.diff(eigenvalues_sorted)
mean_gap = np.mean(gaps)
normalized_gaps = gaps / mean_gap

print(f"  本征值范围: [{eigenvalues_sorted[0]:.4f}, {eigenvalues_sorted[-1]:.4f}]")
print(f"  平均间距: {mean_gap:.6f}")
print(f"  间距数: {len(gaps)}")

# 相邻间距比 r_i = s_{i+1} / s_i (排除零间距)
nonzero_gaps = gaps[gaps > 1e-10]  # 过滤掉过小的间距
if len(nonzero_gaps) > 1:
    ratios = nonzero_gaps[1:] / nonzero_gaps[:-1]
    mean_ratio = np.mean(ratios)
    print(f"\n  有效间距数: {len(nonzero_gaps)}")
    print(f"  相邻间距比 <r>: {mean_ratio:.4f}")
    print(f"  GUE 预测: ~1.74")
    print(f"  Poisson 预测: ~1.39")
    print(f"  GOE 预测: ~1.53")
else:
    ratios = np.array([])
    mean_ratio = 0.0
    print(f"\n  警告: 有效间距太少，无法计算间距比")

# 间距方差
var_normalized = np.var(normalized_gaps)
print(f"\n  归一化间距方差: {var_normalized:.4f}")
print(f"  GUE 预测: ~0.178")
print(f"  Poisson 预测: ~1.000")

# --- 8. 可视化 ---
fig, axes = plt.subplots(1, 3, figsize=(15, 4))

# 图1: 本征值谱
ax1 = axes[0]
ax1.scatter(range(1, N_pts+1), eigenvalues_sorted, s=30, color='blue', alpha=0.7)
ax1.set_xlabel('Index')
ax1.set_ylabel('Eigenvalue')
ax1.set_title('GR Metric Laplacian Spectrum\n(N=27 grid points)')
ax1.grid(True, alpha=0.3)

# 图2: 归一化间距分布
ax2 = axes[1]
s_values = np.linspace(0, 4, 200)
# Wigner surmise for GUE
p_gue = (32/np.pi**2) * s_values**2 * np.exp(-4/np.pi * s_values**2)
# Wigner surmise for GOE
p_goe = (np.pi/2) * s_values * np.exp(-np.pi/4 * s_values**2)
# Poisson
p_poisson = np.exp(-s_values)

ax2.hist(normalized_gaps, bins=10, density=True, alpha=0.6, color='steelblue',
         label='Data', edgecolor='white')
ax2.plot(s_values, p_gue, 'r-', linewidth=2, label='GUE (Wigner)')
ax2.plot(s_values, p_goe, 'g--', linewidth=2, label='GOE (Wigner)')
ax2.plot(s_values, p_poisson, 'k:', linewidth=2, label='Poisson')
ax2.set_xlabel('Normalized Gap s')
ax2.set_ylabel('P(s)')
ax2.set_title('Gap Distribution')
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3)

# 图3: 间距比分布
ax3 = axes[2]
if len(ratios) > 0:
    ax3.hist(ratios, bins=10, density=True, alpha=0.6, color='coral',
             label='Data', edgecolor='white')
    ax3.axvline(x=1.74, color='red', linewidth=2, linestyle='-', label=f'GUE: 1.74')
    ax3.axvline(x=1.39, color='black', linewidth=2, linestyle=':', label=f'Poisson: 1.39')
    ax3.axvline(x=mean_ratio, color='blue', linewidth=2, linestyle='--',
                label=f'Data: {mean_ratio:.2f}')
    ax3.set_xlim(0, 5)  # 限制x轴范围
else:
    ax3.text(0.5, 0.5, 'Insufficient data\nfor gap ratio analysis',
             ha='center', va='center', transform=ax3.transAxes)
ax3.set_xlabel('Gap Ratio r')
ax3.set_ylabel('Density')
ax3.set_title('Adjacent Gap Ratio Distribution')
ax3.legend(fontsize=8)
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('RH019_spectrum.png', dpi=150, bbox_inches='tight')
print("\n图像已保存为 RH019_spectrum.png")

# --- 9. 附加：度规各向异性分析 ---
print("\n度规各向异性分析（打破层内简并的关键）:")
print("格点类型 | |u|_1 | g_11  | g_22  | g_33  | 各向异性")
print("-" * 65)
representative_points = [
    (0,0,0), (1,0,0), (1,1,0), (1,1,1),
    (2,0,0), (2,1,0), (2,1,1), (2,2,0), (2,2,1), (2,2,2)
]
for u in representative_points:
    g = all_metrics[u]
    g11, g22, g33 = g[0,0], g[1,1], g[2,2]
    anisotropy = max(g11, g22, g33) / (min(abs(g11), abs(g22), abs(g33)) + 1e-10)
    print(f"  {str(u):12s} | {sum(u):5d} | {g11:+.4f} | {g22:+.4f} | {g33:+.4f} | {anisotropy:.3f}")

print("\n=== RH-019 计算完成 ===")
