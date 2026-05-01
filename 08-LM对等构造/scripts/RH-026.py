import numpy as np
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import defaultdict

# ============================================================
# RH-026: {0,1}^N 上的离散 Selberg 迹公式验证
#
# Selberg 迹公式（离散版）：
#   Tr(T^k) = sum_{gamma: 闭合路径, |gamma|=k} w(gamma)
#
# 左边：转移矩阵 T 的 k 次幂的迹（谱方法）
# 右边：长度恰好为 k 的所有闭合路径的权重之和（几何方法）
#
# 如果两边相等（在数值精度内），说明：
#   1. 转移矩阵的谱与闭合路径的几何有精确对应
#   2. 这是 Selberg 迹公式在 WorldBase 框架中的实现
#   3. 为 Selberg ζ 函数的函数方程提供基础
#
# 额外计算：
#   - 原始闭合路径 vs 可约路径的分解（Möbius 反演）
#   - Selberg ζ 函数的离散版本：Z(s) = prod_{gamma prime} (1-w(gamma)^s)^{-1}
#   - 检验 Z(s) 是否满足函数方程
# ============================================================

def build_transfer_matrix(N, alpha, J, gamma):
    """Ising 型 A5 转移矩阵（RH-025 的构造）"""
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
            cost = sum(abs(alpha[k] + sum(J[k,l]*x[l] for l in range(N) if l!=k))
                       for k in flipped)
            w = np.exp(-cost) * np.exp(gamma*(sum(y)-fx))
            row[j] = w
        Z = row.sum()
        if Z > 0: T[i,:] = row / Z
    return T, states, idx

def enumerate_closed_paths(states, idx, T, k, weight_func=None):
    """
    枚举所有长度恰好为 k 的闭合路径（x_0 -> x_1 -> ... -> x_k = x_0）。
    返回：路径列表和对应权重。
    weight_func: 若为 None，用 T 矩阵元乘积作为权重。
    """
    M = len(states)
    closed_paths = []
    total_weight = 0.0

    # DFS 枚举
    def dfs(path, current_weight):
        nonlocal total_weight
        depth = len(path) - 1
        start = path[0]
        cur   = path[-1]

        if depth == k:
            if cur == start:
                closed_paths.append(list(path))
                total_weight += current_weight
            return

        i_cur = idx[cur]
        for j, nxt in enumerate(states):
            if T[i_cur, j] < 1e-12: continue
            if depth < k - 1 and nxt == start: continue  # 不提前回到起点
            path.append(nxt)
            dfs(path, current_weight * T[i_cur, j])
            path.pop()

    for start in states:
        dfs([start], 1.0)

    return closed_paths, total_weight

def trace_power(T, k):
    """Tr(T^k)：谱方法"""
    Tk = np.linalg.matrix_power(T, k)
    return np.trace(Tk)

def selberg_zeta_discrete(prime_paths, s_values):
    """
    离散 Selberg ζ 函数：
    Z(s) = prod_{gamma prime} (1 - w(gamma)^s)^{-1}
    用对数求和代替乘积：log Z(s) = -sum log(1 - w^s)
    """
    Z_vals = np.zeros(len(s_values), dtype=complex)
    for s in s_values:
        log_Z = 0.0
        for w, l in prime_paths:  # w=权重, l=长度
            term = w**s
            if abs(term) < 1 - 1e-10:
                log_Z -= np.log(1 - term)
        Z_vals[np.searchsorted(s_values, s)] = np.exp(log_Z)
    return Z_vals

def find_prime_paths(closed_paths_by_len, max_len):
    """
    从所有闭合路径中提取原始路径（不可约路径）。
    原始路径：不能写成更短路径的重复。
    """
    prime_paths = []
    for l in range(1, max_len+1):
        if l not in closed_paths_by_len: continue
        for path in closed_paths_by_len[l]:
            # 检查是否是更短路径的重复
            is_primitive = True
            for d in range(1, l):
                if l % d == 0:
                    # 检查 path 是否是长度 d 的路径重复 l//d 次
                    sub = path[:d]
                    repeated = sub * (l // d)
                    if path[:-1] == repeated[:-1]:  # 忽略最后的回到起点
                        is_primitive = False
                        break
            if is_primitive:
                # 计算路径权重（T 矩阵元乘积）
                prime_paths.append((path, l))
    return prime_paths


# ============================================================
# 主实验
# ============================================================

np.random.seed(2025)

print("" + "#"*65)
print("# RH-026: 离散 Selberg 迹公式验证")
print("#"*65)

for N in [3, 4, 5]:
    M = 2**N
    print(f"{'='*60}")
    print(f"N={N} ({M}态)")
    print(f"{'='*60}")

    # 使用 RH-025 实验组 B 的参数（随机 alpha+J，有部分复数本征值）
    alpha = np.random.uniform(0.5, 2.0, N)
    J_raw = np.random.uniform(-0.3, 0.3, (N, N))
    np.fill_diagonal(J_raw, 0)
    J = (J_raw + J_raw.T) / 2  # 对称耦合

    T, states, idx = build_transfer_matrix(N, alpha, J, gamma=0.5)

    print(f"转移矩阵构造完成，大小: {M}×{M}")
    print(f"矩阵稠密度: {np.mean(T > 1e-10):.3f}")

    # --- 谱方法：Tr(T^k) ---
    max_k = min(8, M)
    trace_spectral = {}
    for k in range(1, max_k+1):
        trace_spectral[k] = trace_power(T, k)

    print(f"Tr(T^k) [谱方法]:")
    for k in range(1, max_k+1):
        print(f"  k={k}: {trace_spectral[k]:.6f}")

    # --- 几何方法：枚举闭合路径 ---
    # 只对小 N 做完整枚举（N=3,4）
    if N <= 4:
        print(f"闭合路径枚举 [几何方法]:")
        trace_geometric = {}
        closed_by_len = defaultdict(list)

        for k in range(1, min(6, max_k+1)):
            paths, total_w = enumerate_closed_paths(states, idx, T, k)
            trace_geometric[k] = total_w
            for p in paths:
                closed_by_len[k].append(p[:-1])  # 去掉重复的起点

            match = abs(trace_spectral[k] - total_w) < 1e-6
            print(f"  k={k}: 谱={trace_spectral[k]:.6f}  几何={total_w:.6f}  "
                  f"误差={abs(trace_spectral[k]-total_w):.2e}  "
                  f"{'✓匹配' if match else '✗不匹配'}")
    else:
        print(f"  (N={N} 路径枚举计算量过大，跳过几何方法)")

    # --- 本征值谱 ---
    eigs = np.linalg.eigvals(T)
    eigs_sorted = sorted(eigs, key=lambda z: -abs(z))

    print(f"本征值谱 (前10个，按模排序):")
    for i, ev in enumerate(eigs_sorted[:10]):
        print(f"  λ_{i+1} = {ev.real:+.6f} {ev.imag:+.6f}i  "
              f"|λ|={abs(ev):.6f}")

    # 用本征值验证迹公式：Tr(T^k) = sum_i lambda_i^k
    print(f"本征值验证 Tr(T^k) = sum lambda^k:")
    for k in range(1, min(6, max_k+1)):
        trace_from_eigs = sum(ev**k for ev in eigs).real
        err = abs(trace_spectral[k] - trace_from_eigs)
        print(f"  k={k}: 矩阵幂={trace_spectral[k]:.6f}  "
              f"本征值和={trace_from_eigs:.6f}  误差={err:.2e}")

    # --- 离散 Selberg ζ 函数（仅 N=3,4）---
    if N <= 4:
        print(f"离散 Selberg ζ 函数分析:")
        # 用迹公式的对数导数形式：
        # -Z'/Z(s) = sum_{k>=1} sum_{gamma, |gamma|=k} w(gamma)^s * log(w(gamma))
        # 等价于：sum_{k>=1} k * Tr(T_w^k) 其中 T_w 是加权矩阵
        # 这里用简化版：Z(s) ~ exp(sum_k Tr(T^k) * s^k / k)

        # 构造 Selberg ζ 的系数（用迹公式）
        # log Z(s) = sum_{k=1}^{inf} Tr(T^k) * s^k / k
        # 这是形式幂级数，s 在谱半径倒数内收敛
        rho = max(abs(ev) for ev in eigs)  # 谱半径
        print(f"  谱半径 rho = {rho:.6f}")
        print(f"  收敛半径 |s| < 1/rho = {1/rho:.6f}")

        # 计算 log Z(s) 的系数
        print(f"  log Z(s) = sum_k c_k * s^k 的系数 c_k = Tr(T^k)/k:")
        for k in range(1, min(7, max_k+1)):
            ck = trace_spectral[k] / k
            print(f"    c_{k} = {ck:.6f}")

        # 函数方程检验：Z(s) = Z(1-s) 等价于 c_k(s) = c_k(1-s)
        # 对于幂级数，这要求 Tr(T^k) 满足特定对称性
        print(f"  函数方程检验 [Tr(T^k) vs Tr((T^{{-1}})^k)]:")
        try:
            T_inv = np.linalg.inv(T)
            for k in range(1, min(5, max_k+1)):
                tr_T   = trace_spectral[k]
                tr_inv = np.trace(np.linalg.matrix_power(T_inv, k)).real
                ratio  = tr_T / tr_inv if abs(tr_inv) > 1e-10 else float('inf')
                print(f"    k={k}: Tr(T^k)={tr_T:.4f}  "
                      f"Tr(T^{{-k}})={tr_inv:.4f}  比值={ratio:.4f}")
        except np.linalg.LinAlgError:
            print("    T 不可逆，跳过")


# ============================================================
# 可视化：N=4 的迹公式验证
# ============================================================

N_vis = 4
alpha_v = np.random.uniform(0.5, 2.0, N_vis)
J_v = np.random.uniform(-0.3, 0.3, (N_vis, N_vis))
np.fill_diagonal(J_v, 0)
J_v = (J_v + J_v.T) / 2
T_v, states_v, idx_v = build_transfer_matrix(N_vis, alpha_v, J_v, gamma=0.5)
eigs_v = np.linalg.eigvals(T_v)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# 图1：复平面本征值
ax = axes[0]
ax.scatter(eigs_v.real, eigs_v.imag, s=40, color='steelblue', zorder=3)
theta = np.linspace(0, 2*np.pi, 200)
r = np.median(np.abs(eigs_v))
ax.plot(r*np.cos(theta), r*np.sin(theta), 'k--', lw=1, alpha=0.4)
ax.axhline(0, color='gray', lw=0.5)
ax.axvline(0, color='gray', lw=0.5)
ax.set_aspect('equal')
ax.set_title(f'N={N_vis}: 本征值分布（复平面）', fontsize=10)
ax.set_xlabel('Re(λ)'); ax.set_ylabel('Im(λ)')
ax.grid(True, alpha=0.3)

# 图2：|Tr(T^k)| vs k
ks = range(1, 9)
tr_vals = [abs(trace_power(T_v, k)) for k in ks]
tr_eigs = [abs(sum(ev**k for ev in eigs_v)) for k in ks]
ax2 = axes[1]
ax2.semilogy(list(ks), tr_vals,  'bo-', lw=2, markersize=6, label='矩阵幂 Tr(T^k)')
ax2.semilogy(list(ks), tr_eigs,  'r^--', lw=2, markersize=6, label='本征值和 Σλ^k')
ax2.set_xlabel('k'); ax2.set_ylabel('|Tr(T^k)|')
ax2.set_title(f'N={N_vis}: 迹公式验证', fontsize=10)
ax2.legend(fontsize=9); ax2.grid(True, alpha=0.3)

# 图3：log Z(s) 的收敛性（实轴上）
s_vals = np.linspace(0.01, 0.8/max(abs(ev) for ev in eigs_v), 100)
log_Z = np.zeros(len(s_vals))
for k in range(1, 15):
    tr_k = trace_power(T_v, k)
    log_Z += (tr_k * s_vals**k / k).real
ax3 = axes[2]
ax3.plot(s_vals, log_Z, 'g-', lw=2)
ax3.set_xlabel('s (实轴)'); ax3.set_ylabel('log Z(s)')
ax3.set_title(f'N={N_vis}: 离散 Selberg ζ（log Z）', fontsize=10)
ax3.grid(True, alpha=0.3)

plt.suptitle('RH-026: 离散 Selberg 迹公式验证', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('RH026_selberg.png', dpi=150, bbox_inches='tight')
print("图像已保存为 RH026_selberg.png")
print("=== RH-026 计算完成 ===")
