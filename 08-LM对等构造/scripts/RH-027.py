import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

np.random.seed(2025)

# ============================================================
# RH-027 优化版
# 关键优化：
#   1. 路径枚举 -> 矩阵幂迹（O(M^3) per k，替代 O(M^k) DFS）
#   2. Sinkhorn 迭代次数从 1000 降到 50
#   3. N 只跑 3,4（N=5 的几何验证跳过，只做谱分析）
#   4. 所有循环加进度提示
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
            if i == j:
                continue
            flipped = [k for k in range(N) if x[k] != y[k]]
            if not flipped:
                continue
            cost = sum(
                abs(alpha[k] + sum(J[k, l] * x[l]
                    for l in range(N) if l != k))
                for k in flipped
            )
            w = np.exp(-cost) * np.exp(gamma * (sum(y) - fx))
            row[j] = w
        Z = row.sum()
        if Z > 0:
            T[i, :] = row / Z
    return T, states, idx


def trace_via_matrix_power(T, k):
    """Tr(T^k)：用矩阵幂，O(M^3 * k)"""
    return float(np.trace(np.linalg.matrix_power(T, k)).real)


def trace_via_eigenvalues(eigs, k):
    """Tr(T^k) = sum lambda_i^k，O(M * k)"""
    return float(np.sum(eigs ** k).real)


def check_detailed_balance(T, states):
    """细致平衡检验"""
    eigs_l, vecs_l = np.linalg.eig(T.T)
    idx_one = np.argmin(np.abs(eigs_l - 1.0))
    pi = np.abs(vecs_l[:, idx_one])
    pi /= pi.sum()
    M = len(states)
    max_viol = 0.0
    for i in range(M):
        for j in range(i+1, M):
            lhs = pi[i] * T[i, j]
            rhs = pi[j] * T[j, i]
            max_viol = max(max_viol, abs(lhs - rhs))
    return pi, max_viol


def build_symmetric_transfer(T, pi):
    """T_sym = D^{1/2} T D^{-1/2}，实对称矩阵"""
    pi = np.maximum(pi, 1e-12)
    D_sqrt     = np.diag(np.sqrt(pi))
    D_inv_sqrt = np.diag(1.0 / np.sqrt(pi))
    T_sym = D_sqrt @ T @ D_inv_sqrt
    return (T_sym + T_sym.T) / 2.0


def sinkhorn(T, n_iter=50):
    """双随机矩阵（Sinkhorn，50次迭代）"""
    A = T.copy()
    for _ in range(n_iter):
        A /= np.maximum(A.sum(axis=1, keepdims=True), 1e-12)
        A /= np.maximum(A.sum(axis=0, keepdims=True), 1e-12)
    return A


def unit_circle_symmetry(eigs):
    """
    检验谱关于单位圆的对称性：
    对每个 |lambda| < 1 的本征值，找最近的 1/lambda*。
    返回最大偏差。
    """
    violations = []
    for lam in eigs:
        if abs(lam) < 1e-8:
            continue
        inv_conj = 1.0 / np.conj(lam)
        dists = np.abs(eigs - inv_conj)
        violations.append(np.min(dists))
    return np.max(violations) if violations else 0.0


# ============================================================
# 主循环
# ============================================================

print("#" * 60)
print("# RH-027 优化版")
print("#" * 60)

all_results = []

for N in [3, 4, 5]:
    M = 2**N
    print(f"\n{'='*55}")
    print(f"N={N}  M={M}")
    print(f"{'='*55}")

    alpha = np.random.uniform(0.5, 2.0, N)
    J_raw = np.random.uniform(-0.3, 0.3, (N, N))
    np.fill_diagonal(J_raw, 0)
    J = (J_raw + J_raw.T) / 2.0

    T, states, idx = build_transfer_matrix(N, alpha, J, gamma=0.5)
    eigs_c = np.linalg.eigvals(T)
    eigs_r = np.sort(eigs_c.real)[::-1]

    print(f"稠密度: {np.mean(T > 1e-10):.3f}")
    print(f"谱半径: {np.max(np.abs(eigs_c)):.6f}")
    print(f"复数本征值比例: {np.mean(np.abs(eigs_c.imag) > 1e-6):.3f}")

    # ----------------------------------------------------------
    # [1] 迹公式：矩阵幂 vs 本征值求和
    # ----------------------------------------------------------
    print(f"\n[1] 迹公式验证  Tr(T^k):")
    print(f"  {'k':<4} {'矩阵幂':<12} {'本征值和':<12} {'误差':<10}")
    max_k = min(8, M)
    for k in range(1, max_k + 1):
        tr_mp  = trace_via_matrix_power(T, k)
        tr_eig = trace_via_eigenvalues(eigs_c, k)
        err    = abs(tr_mp - tr_eig)
        print(f"  {k:<4} {tr_mp:<12.6f} {tr_eig:<12.6f} {err:<10.2e}")

    # ----------------------------------------------------------
    # [2] 细致平衡
    # ----------------------------------------------------------
    pi, max_viol = check_detailed_balance(T, states)
    print(f"\n[2] 细致平衡违反量: {max_viol:.6f}  "
          f"{'✓ 可逆链' if max_viol < 1e-4 else '✗ 不可逆链'}")

    # ----------------------------------------------------------
    # [3] 对称化矩阵 T_sym
    # ----------------------------------------------------------
    T_sym   = build_symmetric_transfer(T, pi)
    eigs_sym = np.sort(np.linalg.eigvalsh(T_sym))[::-1]
    neg_count = np.sum(eigs_sym < 0)
    # 检验关于 0 的对称性（bipartite 图特征）
    sym_about_zero = max(
        abs(eigs_sym[i] + eigs_sym[M - 1 - i])
        for i in range(M // 2)
    )
    print(f"\n[3] T_sym 本征值:")
    print(f"  范围: [{eigs_sym[-1]:.4f}, {eigs_sym[0]:.4f}]")
    print(f"  负本征值数: {neg_count}/{M}")
    print(f"  关于 0 的对称性 max|λ_i + λ_|: {sym_about_zero:.4f}")
    print(f"  前8个: {[f'{e:.4f}' for e in eigs_sym[:8]]}")

    # ----------------------------------------------------------
    # [4] 双随机矩阵（仅 N<=4）
    # ----------------------------------------------------------
    if N <= 4:
        T_ds    = sinkhorn(T, n_iter=50)
        eigs_ds = np.linalg.eigvals(T_ds)
        row_err = abs(T_ds.sum(axis=1) - 1).max()
        col_err = abs(T_ds.sum(axis=0) - 1).max()
        print(f"\n[4] 双随机矩阵 (Sinkhorn 50步):")
        print(f"  行和误差: {row_err:.2e}  列和误差: {col_err:.2e}")
        eigs_ds_s = sorted(eigs_ds, key=lambda z: -abs(z))
        print(f"  本征值 (前6): "
              f"{[f'{e.real:.4f}+{e.imag:.4f}i' for e in eigs_ds_s[:6]]}")
        uc_sym_ds = unit_circle_symmetry(eigs_ds)
        print(f"  单位圆对称性违反: {uc_sym_ds:.4f}")
    else:
        T_ds = None

    # ----------------------------------------------------------
    # [5] Ihara/Selberg ζ：单位圆对称性检验
    # ----------------------------------------------------------
    uc_sym_T = unit_circle_symmetry(eigs_c)
    print(f"\n[5] T 的谱单位圆对称性违反: {uc_sym_T:.4f}")
    print(f"  （函数方程 Z(u)=Z(1/u) 要求此值≈0）")

    # ----------------------------------------------------------
    # [6] 函数方程检验：Tr(T^k) vs Tr(T^{-k})
    # ----------------------------------------------------------
    try:
        T_inv = np.linalg.inv(T)
        print(f"\n[6] 函数方程检验 Tr(T^k) / Tr(T^{{-k}}):")
        for k in range(1, 5):
            tr_k    = trace_via_matrix_power(T, k)
            tr_invk = trace_via_matrix_power(T_inv, k)
            ratio   = tr_k / tr_invk if abs(tr_invk) > 1e-8 else float('inf')
            print(f"  k={k}: {tr_k:.4f} / {tr_invk:.4f} = {ratio:.6f}")
    except np.linalg.LinAlgError:
        print(f"\n[6] T 不可逆，跳过")

    # ----------------------------------------------------------
    # [7] 构造满足单位圆对称的修正矩阵
    #     方法：T_unitary = T * (T^T T)^{-1/2}（极分解的幺正因子）
    #     幺正矩阵的本征值在单位圆上，自动满足函数方程
    # ----------------------------------------------------------
    print(f"\n[7] 极分解幺正因子 U（本征值在单位圆上）:")
    try:
        # SVD: T = U S V^T => 幺正因子 = U V^T
        U_svd, S_svd, Vt_svd = np.linalg.svd(T)
        T_unitary = U_svd @ Vt_svd
        eigs_u = np.linalg.eigvals(T_unitary)
        uc_sym_u = unit_circle_symmetry(eigs_u)
        mods_u = np.abs(eigs_u)
        print(f"  |λ| 范围: [{mods_u.min():.6f}, {mods_u.max():.6f}]")
        print(f"  单位圆对称性违反: {uc_sym_u:.4f}")
        # 迹公式
        print(f"  Tr(U^k) for k=1..4: "
              f"{[f'{trace_via_eigenvalues(eigs_u,k):.4f}' for k in range(1,5)]}")
    except Exception as e:
        print(f"  失败: {e}")

    all_results.append({
        'N': N, 'M': M,
        'T': T, 'T_sym': T_sym, 'T_ds': T_ds,
        'eigs_c': eigs_c, 'eigs_sym': eigs_sym,
        'pi': pi, 'max_viol': max_viol,
        'uc_sym_T': uc_sym_T,
    })

# ============================================================
# 汇总表
# ============================================================

print("\n" + "="*65)
print("RH-027 汇总")
print("="*65)
print(f"{'N':<5} {'M':<6} {'细致平衡':<12} {'单位圆对称':<14} {'负本征值'}")
print("-"*65)
for r in all_results:
    print(f"{r['N']:<5} {r['M']:<6} {r['max_viol']:<12.4f} "
          f"{r['uc_sym_T']:<14.4f} "
          f"{np.sum(r['eigs_sym']<0)}/{r['M']}")
print("\n函数方程 Z(u)=Z(1/u) 需要：单位圆对称性 ≈ 0")
print("细致平衡 ≈ 0 是函数方程的弱化版本（只保证实数谱）")

# ============================================================
# 可视化（3列：T本征值 | T_sym本征值 | 迹序列）
# ============================================================

fig, axes = plt.subplots(3, 3, figsize=(13, 12))
theta_c = np.linspace(0, 2*np.pi, 300)

for row, res in enumerate(all_results):
    N = res['N']
    M = res['M']

    # 列0：T 本征值（复平面）
    ax = axes[row, 0]
    ev = res['eigs_c']
    ax.scatter(ev.real, ev.imag, s=25, color='steelblue', zorder=3)
    ax.plot(np.cos(theta_c), np.sin(theta_c),
            'k--', lw=1, alpha=0.4, label='单位圆')
    ax.axhline(0, color='gray', lw=0.5)
    ax.axvline(0, color='gray', lw=0.5)
    ax.set_aspect('equal')
    ax.set_title(f'N={N}: T 本征值', fontsize=9)
    ax.set_xlabel('Re'); ax.set_ylabel('Im')
    ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    # 列1：T_sym 本征值（实轴上）
    ax2 = axes[row, 1]
    ev_s = res['eigs_sym']
    ax2.scatter(ev_s, np.zeros_like(ev_s),
                s=25, color='crimson', zorder=3)
    ax2.axvline(0,  color='steelblue', lw=1.5, linestyle='--', alpha=0.7)
    ax2.axvline(1,  color='green',     lw=1.5, linestyle=':',  alpha=0.7)
    ax2.axvline(-1, color='green',     lw=1.5, linestyle=':',  alpha=0.7)
    ax2.set_ylim(-0.1, 0.1)
    ax2.set_title(f'N={N}: T_sym 本征值（实轴）', fontsize=9)
    ax2.set_xlabel('λ'); ax2.grid(True, alpha=0.3)

    # 列2：|Tr(T^k)| 衰减曲线
    ax3 = axes[row, 2]
    ks  = range(1, min(9, M))
    trs = [abs(trace_via_eigenvalues(res['eigs_c'], k)) for k in ks]
    ax3.semilogy(list(ks), trs, 'go-', lw=2, markersize=5)
    ax3.set_xlabel('k'); ax3.set_ylabel('|Tr(T^k)|')
    ax3.set_title(f'N={N}: 迹序列', fontsize=9)
    ax3.grid(True, alpha=0.3)

plt.suptitle('RH-027: 迹公式 + 函数方程代数条件',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('RH027_optimized.png', dpi=150, bbox_inches='tight')
print("\n图像已保存为 RH027_optimized.png")
print("\n=== RH-027 优化版完成 ===")
