import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============================================================
# RH-029: 修复 Szegedy 关系 + 正确 CUE 谱统计
#
# 修复负本征值：懒惰游走 T_lazy = (1-alpha)*T + alpha*I
# 使所有本征值 >= 0，Szegedy 关系精确成立
#
# 同时检验：
#   1. Szegedy 关系精度（目标：偏差 < 1e-10）
#   2. W 角度间距统计 vs CUE（目标：方差 -> 0.178）
#   3. Selberg ζ 函数方程的精确形式
#   4. N 增大时角度方差的收敛趋势
# ============================================================

def build_transfer_matrix(N, alpha_arr, J, gamma):
    states = list(product([0,1], repeat=N))
    M = len(states)
    T = np.zeros((M, M))
    for i, x in enumerate(states):
        fx = sum(x)
        row = np.zeros(M)
        for j, y in enumerate(states):
            if i == j: continue
            flipped = [k for k in range(N) if x[k] != y[k]]
            if not flipped: continue
            cost = sum(
                abs(alpha_arr[k] + sum(J[k,l]*x[l]
                    for l in range(N) if l != k))
                for k in flipped)
            w = np.exp(-cost) * np.exp(gamma*(sum(y)-fx))
            row[j] = w
        Z = row.sum()
        if Z > 0: T[i,:] = row / Z
    return T, states


def make_lazy(T, alpha=None):
    """
    懒惰游走：T_lazy = (1-alpha)*T + alpha*I
    alpha 自动选择使所有本征值 >= 0：
      alpha >= |lambda_min| / (1 + |lambda_min|)
    """
    eigs = np.linalg.eigvals(T).real
    lam_min = eigs.min()
    if lam_min >= 0:
        return T, 0.0  # 已经非负，不需要懒惰化
    if alpha is None:
        # 最小 alpha 使 (1-alpha)*lam_min + alpha >= 0
        # => alpha >= -lam_min / (1 - lam_min)
        alpha = (-lam_min) / (1.0 - lam_min) + 1e-10
    M = T.shape[0]
    return (1.0 - alpha) * T + alpha * np.eye(M), alpha


def build_szegedy_walk(T):
    """Szegedy 量子游走算子 W（M^2 × M^2）"""
    M = T.shape[0]
    M2 = M * M

    Pi = np.zeros((M2, M2), dtype=complex)
    for x in range(M):
        psi = np.zeros(M2, dtype=complex)
        for y in range(M):
            psi[x*M + y] = np.sqrt(max(T[x, y], 0.0))
        Pi += np.outer(psi, psi.conj())

    R = 2.0 * Pi - np.eye(M2, dtype=complex)
    S = np.zeros((M2, M2), dtype=complex)
    for x in range(M):
        for y in range(M):
            S[y*M + x, x*M + y] = 1.0

    return R @ S


def szegedy_check(eigs_T, eigs_W, tol=1e-6):
    """
    验证 Szegedy 关系：lambda_T -> e^{±i arccos(sqrt(lambda_T))}
    只对 0 <= lambda_T <= 1 的本征值检验。
    返回最大偏差。
    """
    max_err = 0.0
    valid   = 0
    for lam in eigs_T:
        if not (np.isreal(lam) and -tol <= lam.real <= 1+tol):
            continue
        lam_r = np.clip(lam.real, 0.0, 1.0)
        theta = np.arccos(np.sqrt(lam_r))
        for sign in [+1, -1]:
            expected = np.exp(1j * sign * theta)
            dist = np.min(np.abs(eigs_W - expected))
            max_err = max(max_err, dist)
        valid += 1
    return max_err, valid


def angle_gap_stats(eigs_W):
    """W 本征值的角度间距统计"""
    angles = np.sort(np.angle(eigs_W))
    M2 = len(angles)
    gaps = np.diff(angles)
    gaps = np.append(gaps, angles[0] + 2*np.pi - angles[-1])
    mean_g = np.mean(gaps)
    s = gaps / mean_g
    return np.mean(s), np.var(s), np.median(s)


def selberg_zeta_log(eigs_W, u_vals):
    """log Z(u) = -sum_i log(1 - u*lambda_i)，仅在 |u| < 1 收敛"""
    log_Z = np.zeros(len(u_vals), dtype=complex)
    for k, u in enumerate(u_vals):
        for lam in eigs_W:
            val = u * lam
            if abs(val) < 1.0 - 1e-9:
                log_Z[k] -= np.log(1.0 - val)
    return log_Z


# ============================================================
# 主实验
# ============================================================

np.random.seed(2025)

print("#" * 60)
print("# RH-029: 懒惰游走修复 Szegedy 关系")
print("#" * 60)

all_res = []

# N=3,4,5（N=5 的 W 是 1024×1024，约 8MB，可以运行）
for N in [3, 4, 5]:
    M  = 2**N
    M2 = M * M
    print(f"{'='*55}")
    print(f"N={N}  M={M}  W={M2}×{M2}")
    print(f"{'='*55}")

    alpha_arr = np.random.uniform(0.5, 2.0, N)
    J_raw = np.random.uniform(-0.3, 0.3, (N, N))
    np.fill_diagonal(J_raw, 0)
    J = (J_raw + J_raw.T) / 2.0

    T_orig, states = build_transfer_matrix(N, alpha_arr, J, gamma=0.5)
    eigs_T_orig = np.linalg.eigvals(T_orig)

    lam_min_orig = eigs_T_orig.real.min()
    print(f"T 原始最小本征值: {lam_min_orig:.4f}")
    print(f"T 负本征值数: {np.sum(eigs_T_orig.real < 0)}/{M}")

    # 懒惰化
    T_lazy, alpha_lazy = make_lazy(T_orig)
    eigs_T = np.linalg.eigvals(T_lazy)
    print(f"懒惰化参数 α = {alpha_lazy:.4f}")
    print(f"T_lazy 本征值范围: [{eigs_T.real.min():.4f}, "
          f"{eigs_T.real.max():.4f}]")
    print(f"T_lazy 负本征值数: {np.sum(eigs_T.real < -1e-8)}")

    # Szegedy 游走
    W = build_szegedy_walk(T_lazy)

    # 幺正性
    err_u = np.max(np.abs(W @ W.conj().T - np.eye(M2)))
    print(f"幺正性误差: {err_u:.2e}")

    eigs_W = np.linalg.eigvals(W)
    mod_std = np.std(np.abs(eigs_W))
    print(f"|λ_W| std: {mod_std:.2e}  (应≈0)")

    # Szegedy 关系精度
    szeg_err, n_valid = szegedy_check(eigs_T, eigs_W)
    print(f"Szegedy 关系最大偏差: {szeg_err:.2e}  "
          f"(检验了 {n_valid} 个本征值)")

    # 迹公式
    print(f"Tr(W^k) 验证:")
    print(f"  {'k':<4} {'矩阵幂':<14} {'本征值和':<14} {'误差'}")
    for k in range(1, 7):
        tr_mp  = np.trace(np.linalg.matrix_power(W, k)).real
        tr_eig = np.sum(eigs_W**k).real
        print(f"  {k:<4} {tr_mp:<14.4f} {tr_eig:<14.4f} {abs(tr_mp-tr_eig):.2e}")

    # 角度间距统计
    mean_s, var_s, med_s = angle_gap_stats(eigs_W)
    print(f"角度间距统计:")
    print(f"  均值={mean_s:.4f}  方差={var_s:.4f}  中位数={med_s:.4f}")
    print(f"  CUE目标: 均值=1.000  方差=0.178  中位数≈0.940")

    # Selberg ζ 函数方程精确检验
    # 对幺正矩阵 W，精确函数方程为：
    #   Z(u) * Z(1/u*) = exp(i*phase) * u^{-M2} * det(W)
    # 简化版检验：|Z(u)| * |Z(1/u)| vs |u|^{-M2} * |det(W)|
    print(f"Selberg ζ 函数方程精确检验:")
    det_W = np.linalg.det(W)
    print(f"  |det(W)| = {abs(det_W):.6f}  (幺正矩阵应=1)")
    u_tests = [0.3, 0.5, 0.7]
    for u in u_tests:
        log_Zu  = selberg_zeta_log(eigs_W, [u])[0]
        log_Ziv = selberg_zeta_log(eigs_W, [1.0/u])[0]
        Zu  = np.exp(log_Zu)
        Ziv = np.exp(log_Ziv)
        # 理论：|Z(u)| * |Z(1/u)| = u^{-M2} * |det(W)|^{-1}
        lhs = abs(Zu) * abs(Ziv)
        rhs = (1.0/u)**M2 * (1.0/abs(det_W))
        print(f"  u={u}: |Z(u)|={abs(Zu):.3e}  |Z(1/u)|={abs(Ziv):.3e}  "
              f"乘积={lhs:.3e}  理论={rhs:.3e}  "
              f"比值={lhs/rhs if rhs>0 else 'inf':.4f}")

    all_res.append({
        'N': N, 'M': M, 'M2': M2,
        'alpha_lazy': alpha_lazy,
        'eigs_T': eigs_T, 'eigs_W': eigs_W,
        'szeg_err': szeg_err,
        'var_s': var_s, 'med_s': med_s,
    })

# ============================================================
# 汇总
# ============================================================

print("" + "="*65)
print("RH-029 汇总")
print("="*65)
print(f"{'N':<5} {'M':<6} {'α_lazy':<9} {'Szegedy误差':<14} "
      f"{'角度方差':<12} {'CUE目标'}")
print("-"*65)
for r in all_res:
    print(f"{r['N']:<5} {r['M']:<6} {r['alpha_lazy']:<9.4f} "
          f"{r['szeg_err']:<14.2e} {r['var_s']:<12.4f} 0.178")

# ============================================================
# 可视化
# ============================================================

n_exp = len(all_res)
fig, axes = plt.subplots(2, n_exp, figsize=(5*n_exp, 9))

theta_c = np.linspace(0, 2*np.pi, 300)
s_th    = np.linspace(0, 4, 200)
p_cue   = (np.pi/2) * s_th * np.exp(-np.pi/4 * s_th**2)
p_poi   = np.exp(-s_th)

colors = ['steelblue', 'darkorange', 'forestgreen']

for col, res in enumerate(all_res):
    N   = res['N']
    ev  = res['eigs_W']
    color = colors[col]

    # 行0：W 本征值（单位圆）
    ax = axes[0, col]
    ax.scatter(ev.real, ev.imag, s=6, alpha=0.7, color=color)
    ax.plot(np.cos(theta_c), np.sin(theta_c),
            'k--', lw=1, alpha=0.4)
    ax.set_aspect('equal')
    ax.set_title(f'N={N}: W 本征值\n'
                 f'Szegedy误差={res["szeg_err"]:.1e}', fontsize=9)
    ax.set_xlabel('Re'); ax.set_ylabel('Im')
    ax.grid(True, alpha=0.3)

    # 行1：角度间距分布
    ax2 = axes[1, col]
    angles = np.sort(np.angle(ev))
    gaps   = np.diff(angles)
    gaps   = np.append(gaps, angles[0]+2*np.pi-angles[-1])
    s_vals = gaps / np.mean(gaps)
    ax2.hist(s_vals, bins=15, density=True,
             alpha=0.65, color=color, edgecolor='white')
    ax2.plot(s_th, p_cue, 'r-',  lw=2,   label='CUE')
    ax2.plot(s_th, p_poi, 'k--', lw=1.5, label='Poisson')
    ax2.set_title(f'N={N}: 角度间距\n'
                  f'方差={res["var_s"]:.3f}  中位数={res["med_s"]:.3f}',
                  fontsize=9)
    ax2.set_xlabel('s'); ax2.set_ylabel('P(s)')
    ax2.legend(fontsize=7)
    ax2.grid(True, alpha=0.3)

plt.suptitle('RH-029: 懒惰游走 Szegedy 量子游走 — CUE 谱统计',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('RH029_lazy_szegedy.png', dpi=150, bbox_inches='tight')
print("图像已保存为 RH029_lazy_szegedy.png")
print("=== RH-029 完成 ===")
