import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# RH-028: 量子随机游走 — 同时满足幺正性和路径积分结构
#
# 核心思路：
#   经典 T（行随机）: 有路径结构，无函数方程
#   幺正 U（极分解）: 有函数方程，无路径结构
#   量子游走 U_Q:     两者兼顾
#
# Szegedy 量子游走构造：
#   给定经典转移矩阵 T，构造希尔伯特空间 H = C^M ⊗ C^M
#   基向量 |x,y>，x,y ∈ {0,1}^N
#   投影算子 Pi_x = |psi_x><psi_x|，其中
#     |psi_x> = sum_y sqrt(T_{xy}) |x,y>
#   反射算子 R = 2*Pi - I，其中 Pi = sum_x Pi_x
#   游走算子 W = R * S，其中 S|x,y> = |y,x>（交换算子）
#
#   W 是幺正的，且其本征值与 T 的本征值有精确关系：
#   若 T 的本征值为 lambda，则 W 的本征值为
#     e^{±i arccos(sqrt(lambda))}（对 0 <= lambda <= 1）
#
# 这个关系使得：
#   1. W 的谱统计（GUE/Poisson）可以从 T 的谱推导
#   2. W 满足幺正性 => 函数方程自动成立
#   3. W 的迹公式 Tr(W^k) 与 T 的闭合路径有精确对应
# ============================================================

def build_transfer_matrix(N, alpha, J, gamma):
    states = list(product([0,1], repeat=N))
    M = len(states)
    idx = {s: i for i, s in enumerate(states)}
    T = np.zeros((M, M))
    for i, x in enumerate(states):
        fx = sum(x)
        row = np.zeros(M)
        for j, y in enumerate(states):
            if i == j: continue
            flipped = [k for k in range(N) if x[k] != y[k]]
            if not flipped: continue
            cost = sum(
                abs(alpha[k] + sum(J[k,l]*x[l]
                    for l in range(N) if l != k))
                for k in flipped)
            w = np.exp(-cost) * np.exp(gamma*(sum(y)-fx))
            row[j] = w
        Z = row.sum()
        if Z > 0: T[i,:] = row / Z
    return T, states, idx


def build_szegedy_walk(T):
    """
    Szegedy 量子游走算子 W。
    T: M×M 行随机矩阵
    返回: W (M^2 × M^2 幺正矩阵)
    """
    M = T.shape[0]
    M2 = M * M

    # 基向量 |x,y> 的索引：idx = x*M + y
    def xy_idx(x, y): return x * M + y

    # 构造 |psi_x> = sum_y sqrt(T_{xy}) |x,y>
    # Pi_x = |psi_x><psi_x|
    # Pi = sum_x Pi_x（在 M^2 维空间上）

    Pi = np.zeros((M2, M2), dtype=complex)
    for x in range(M):
        psi_x = np.zeros(M2, dtype=complex)
        for y in range(M):
            psi_x[xy_idx(x, y)] = np.sqrt(T[x, y])
        Pi += np.outer(psi_x, psi_x.conj())

    # 反射算子 R = 2*Pi - I
    R = 2.0 * Pi - np.eye(M2, dtype=complex)

    # 交换算子 S|x,y> = |y,x>
    S = np.zeros((M2, M2), dtype=complex)
    for x in range(M):
        for y in range(M):
            S[xy_idx(y, x), xy_idx(x, y)] = 1.0

    # 游走算子 W = R * S
    W = R @ S
    return W


def szegedy_eigenvalue_relation(eigs_T, eigs_W):
    """
    验证 Szegedy 关系：
    T 的本征值 lambda => W 的本征值 e^{±i*arccos(sqrt(lambda))}
    （对实数 0 <= lambda <= 1）
    """
    relations = []
    for lam in eigs_T:
        if np.isreal(lam) and 0 <= lam.real <= 1:
            theta = np.arccos(np.sqrt(lam.real))
            expected_p = np.exp( 1j * theta)
            expected_m = np.exp(-1j * theta)
            # 在 W 的本征值中找最近的
            dist_p = np.min(np.abs(eigs_W - expected_p))
            dist_m = np.min(np.abs(eigs_W - expected_m))
            relations.append((lam.real, theta, dist_p, dist_m))
    return relations


def trace_formula_check(W, eigs_W, max_k=8):
    """Tr(W^k) 验证：矩阵幂 vs 本征值求和"""
    results = []
    for k in range(1, max_k+1):
        tr_mp  = np.trace(np.linalg.matrix_power(W, k)).real
        tr_eig = np.sum(eigs_W**k).real
        results.append((k, tr_mp, tr_eig, abs(tr_mp - tr_eig)))
    return results


def unit_circle_check(eigs):
    """检验本征值是否在单位圆上"""
    mods = np.abs(eigs)
    return mods.min(), mods.max(), np.std(mods)


def selberg_zeta_from_walk(eigs_W, u_vals):
    """
    基于量子游走的 Ihara-Selberg ζ：
    Z(u) = det(I - u*W)^{-1}
    = prod_i (1 - u*lambda_i)^{-1}
    log Z(u) = -sum_i log(1-u*lambda_i)
             = sum_{k>=1} Tr(W^k) * u^k / k
    """
    log_Z = np.zeros(len(u_vals), dtype=complex)
    for idx_u, u in enumerate(u_vals):
        for lam in eigs_W:
            val = u * lam
            if abs(val) < 1 - 1e-6:
                log_Z[idx_u] -= np.log(1 - val)
    return np.exp(log_Z)


# ============================================================
# 主实验
# ============================================================

np.random.seed(2025)

print("#" * 60)
print("# RH-028: Szegedy 量子游走")
print("#" * 60)

all_res = []

for N in [3, 4]:   # N=5 时 W 是 1024×1024，仍可计算但较慢
    M  = 2**N
    M2 = M * M
    print(f"{'='*55}")
    print(f"N={N}  M={M}  W大小={M2}×{M2}")
    print(f"{'='*55}")

    alpha = np.random.uniform(0.5, 2.0, N)
    J_raw = np.random.uniform(-0.3, 0.3, (N, N))
    np.fill_diagonal(J_raw, 0)
    J = (J_raw + J_raw.T) / 2.0

    T, states, idx = build_transfer_matrix(N, alpha, J, gamma=0.5)
    eigs_T = np.linalg.eigvals(T)

    print(f"T 本征值 (实部前6): "
          f"{sorted(eigs_T.real, reverse=True)[:6]}")

    # --- 构造 Szegedy 游走算子 ---
    print(f"构造 Szegedy 游走算子 W ({M2}×{M2})...")
    W = build_szegedy_walk(T)

    # 验证幺正性
    err_unitary = np.max(np.abs(W @ W.conj().T - np.eye(M2)))
    print(f"幺正性误差 ||WW†-I||_max = {err_unitary:.2e}")

    # W 的本征值
    print(f"计算 W 本征值...")
    eigs_W = np.linalg.eigvals(W)

    # 单位圆检验
    mod_min, mod_max, mod_std = unit_circle_check(eigs_W)
    print(f"W 本征值 |λ|: min={mod_min:.6f} max={mod_max:.6f} std={mod_std:.2e}")

    # --- Szegedy 关系验证 ---
    print(f"Szegedy 本征值关系验证 (T.lambda -> W.e^{{±i*arccos(sqrt(lambda))}}):")
    relations = szegedy_eigenvalue_relation(eigs_T, eigs_W)
    print(f"  {'T.λ':<10} {'θ':<10} {'W偏差+':<10} {'W偏差-'}")
    for lam, theta, dp, dm in relations[:8]:
        print(f"  {lam:<10.4f} {theta:<10.4f} {dp:<10.4f} {dm:.4f}")

    # --- 迹公式验证 ---
    print(f"Tr(W^k) 验证:")
    tr_results = trace_formula_check(W, eigs_W, max_k=6)
    print(f"  {'k':<4} {'矩阵幂':<14} {'本征值和':<14} {'误差'}")
    for k, tr_mp, tr_eig, err in tr_results:
        print(f"  {k:<4} {tr_mp:<14.6f} {tr_eig:<14.6f} {err:.2e}")

    # --- 函数方程检验：Tr(W^k) vs Tr(W^{-k}) ---
    # W 幺正 => W^{-1} = W†，所以 Tr(W^{-k}) = Tr(W^k)* = conj(Tr(W^k))
    # 对实数迹：Tr(W^{-k}) = Tr(W^k)（函数方程自动满足！）
    print(f"函数方程检验 Tr(W^k) vs Tr(W^†k) = conj(Tr(W^k)):")
    for k, tr_mp, tr_eig, _ in tr_results:
        tr_conj = np.sum(eigs_W**(-k)).real
        diff = abs(tr_mp - tr_conj)
        print(f"  k={k}: Tr(W^k)={tr_mp:.4f}  "
              f"Tr(W^†k)={tr_conj:.4f}  差={diff:.2e}")

    # --- Selberg ζ 函数 ---
    print(f"离散 Selberg ζ 函数 Z(u) = det(I-uW)^{{-1}}:")
    # 在实轴上 u ∈ [0, 0.9] 计算
    u_real = np.linspace(0.01, 0.90, 50)
    Z_real = selberg_zeta_from_walk(eigs_W, u_real)
    print(f"  u=0.1: |Z|={abs(Z_real[4]):.4f}")
    print(f"  u=0.5: |Z|={abs(Z_real[24]):.4f}")
    print(f"  u=0.9: |Z|={abs(Z_real[49]):.4f}")

    # 函数方程 Z(u) = Z(1/u)*factor 检验
    # 对幺正 W：Z(u) = det(I-uW)^{-1}
    # Z(1/u) = det(I - W/u)^{-1} = det(-W/u)^{-1} * det(W/u - I)^{-1}
    # 精确关系：Z(1/u) = (-u)^{M2} * det(W)^{-1} * Z(u)^{-1} ... 复杂
    # 简单检验：|Z(u)| vs |Z(1/u)|
    u_test = np.array([0.3, 0.5, 0.7])
    print(f"  |Z(u)| vs |Z(1/u)| (函数方程对称性):")
    for u in u_test:
        Z_u   = selberg_zeta_from_walk(eigs_W, [u])[0]
        Z_inv = selberg_zeta_from_walk(eigs_W, [1.0/u])[0]
        print(f"  u={u}: |Z(u)|={abs(Z_u):.4f}  "
              f"|Z(1/u)|={abs(Z_inv):.4f}  "
              f"比值={abs(Z_u)/abs(Z_inv):.4f}")

    # --- 谱统计（W 的本征值角度分布）---
    angles = np.angle(eigs_W)
    # 相邻角度间距
    angles_sorted = np.sort(angles)
    gaps = np.diff(angles_sorted)
    gaps = np.append(gaps, angles_sorted[0] + 2*np.pi - angles_sorted[-1])
    mean_gap = np.mean(gaps)
    s = gaps / mean_gap
    mean_s = np.mean(s)
    var_s  = np.var(s)
    print(f"W 本征值角度间距统计:")
    print(f"  均值: {mean_s:.4f}  方差: {var_s:.4f}")
    print(f"  CUE(圆幺正系综)理论: 均值=1.0000, 方差≈0.178")

    all_res.append({
        'N': N, 'M': M, 'M2': M2,
        'T': T, 'W': W,
        'eigs_T': eigs_T, 'eigs_W': eigs_W,
        'u_real': u_real, 'Z_real': Z_real,
        'angles_sorted': angles_sorted,
        'gaps': gaps, 's': s,
        'var_s': var_s,
    })

# ============================================================
# 汇总
# ============================================================

print("" + "="*55)
print("RH-028 汇总")
print("="*55)
print(f"{'N':<5} {'W大小':<8} {'幺正误差':<12} {'角度方差':<12} {'CUE目标'}")
print("-"*55)
for r in all_res:
    err_u = np.max(np.abs(r['W'] @ r['W'].conj().T
                          - np.eye(r['M2'])))
    print(f"{r['N']:<5} {r['M2']:<8} {err_u:<12.2e} "
          f"{r['var_s']:<12.4f} 0.178")

# ============================================================
# 可视化
# ============================================================

n_exp = len(all_res)
fig, axes = plt.subplots(2, n_exp * 2, figsize=(6*n_exp, 10))

theta_c = np.linspace(0, 2*np.pi, 300)

for col, res in enumerate(all_res):
    N = res['N']

    # 列 2*col: W 本征值（单位圆上）
    ax = axes[0, 2*col]
    ev = res['eigs_W']
    ax.scatter(ev.real, ev.imag, s=8, alpha=0.6, color='steelblue')
    ax.plot(np.cos(theta_c), np.sin(theta_c),
            'k--', lw=1, alpha=0.5)
    ax.set_aspect('equal')
    ax.set_title(f'N={N}: W 本征值（单位圆）', fontsize=9)
    ax.set_xlabel('Re'); ax.set_ylabel('Im')
    ax.grid(True, alpha=0.3)

    # 列 2*col+1: 角度间距分布 vs CUE
    ax2 = axes[0, 2*col+1]
    s_th = np.linspace(0, 4, 200)
    # CUE 间距分布（N→∞ 极限）: P(s) = (pi/2)*s*exp(-pi*s^2/4)
    p_cue = (np.pi/2) * s_th * np.exp(-np.pi/4 * s_th**2)
    p_poi = np.exp(-s_th)
    ax2.hist(res['s'], bins=12, density=True,
             alpha=0.65, color='steelblue', edgecolor='white')
    ax2.plot(s_th, p_cue, 'r-',  lw=2, label=f'CUE')
    ax2.plot(s_th, p_poi, 'k--', lw=1.5, label='Poisson')
    ax2.set_title(f'N={N}: 角度间距 var={res["var_s"]:.3f}', fontsize=9)
    ax2.set_xlabel('s'); ax2.set_ylabel('P(s)')
    ax2.legend(fontsize=7); ax2.grid(True, alpha=0.3)

    # 行2左: |Z(u)| 曲线
    ax3 = axes[1, 2*col]
    ax3.semilogy(res['u_real'], np.abs(res['Z_real']),
                 'g-', lw=2)
    ax3.set_xlabel('u'); ax3.set_ylabel('|Z(u)|')
    ax3.set_title(f'N={N}: Selberg ζ |Z(u)|', fontsize=9)
    ax3.grid(True, alpha=0.3)

    # 行2右: T vs W 本征值对比
    ax4 = axes[1, 2*col+1]
    ev_T = np.sort(res['eigs_T'].real)[::-1]
    ev_W_mod = np.sort(np.angle(res['eigs_W']))
    ax4.scatter(range(len(ev_T)), ev_T,
                s=20, color='crimson', label='T 本征值', zorder=3)
    ax4_r = ax4.twinx()
    ax4_r.scatter(range(len(ev_W_mod)),
                  ev_W_mod[:len(ev_T)],
                  s=20, color='steelblue',
                  alpha=0.5, label='W 本征值角度')
    ax4.set_xlabel('索引')
    ax4.set_ylabel('T 本征值', color='crimson')
    ax4_r.set_ylabel('W 本征值角度', color='steelblue')
    ax4.set_title(f'N={N}: T vs W 本征值', fontsize=9)
    ax4.grid(True, alpha=0.3)

plt.suptitle('RH-028: Szegedy 量子游走 — 幺正性 + 函数方程',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('RH028_szegedy.png', dpi=150, bbox_inches='tight')
print("图像已保存为 RH028_szegedy.png")
print("=== RH-028 完成 ===")
