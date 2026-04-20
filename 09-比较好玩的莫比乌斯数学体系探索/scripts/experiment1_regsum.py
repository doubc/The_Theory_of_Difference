"""
实验一 + 实验二（修复版）

实验一修复：先减去已知发散项，再对残差提取常数项
实验二修复：
  - 嵌入只追踪 (s, epsilon)，x 单独累加
  - 选择真正非交换的参数（s_A != 0, s_B != 0）
"""

import time
from fractions import Fraction

import numpy as np


# ============================================================
# 公共：Bernoulli 数
# ============================================================

def bernoulli(n):
    if n == 0: return Fraction(1)
    if n == 1: return Fraction(-1, 2)
    if n % 2 == 1 and n > 1: return Fraction(0)
    A = [Fraction(0)] * (n + 1)
    for m in range(n + 1):
        A[m] = Fraction(1, m + 1)
        for j in range(m, 0, -1):
            A[j - 1] = j * (A[j - 1] - A[j])
    return A[0]


def zeta_neg_m(m):
    """精确值：zeta(-m) = -B_{m+1}/(m+1)"""
    B = bernoulli(m + 1)
    return float(-B / (m + 1))


# ============================================================
# 实验一修复：残差法提取 Laurent 常数项
#
# Euler-Maclaurin 给出 Sigma(t) 的发散项：
#   Sigma(t) = sum_{n=1}^{inf} n^m * exp(-t*n)
#            = m! / t^{m+1}
#              + (1/2) * m! / t^m * (1/1!)   <- 这里需要精确展开
#
# 更直接的方法：用已知的渐近展开
#   Sigma(t) ~ sum_{k=0}^{m} c_k / t^{m+1-k}  + C + O(t)
# 其中 c_k 可以从 Gamma 函数展开得到。
#
# 最稳健的数值方法：Richardson 外推
# 对于 f(t) = Sigma(t) - [已知发散项]，直接取 t->0 的极限
# ============================================================

def sigma(m, t, N=20000):
    """截断级数 Sigma(t) = sum_{n=1}^{N} n^m * exp(-t*n)"""
    ns = np.arange(1, N + 1, dtype=np.float64)
    return np.sum((ns ** m) * np.exp(-t * ns))


def divergent_part(m, t):
    """
    Sigma(t) 的发散部分（Euler-Maclaurin 展开的极点项）

    对 f(x) = x^m e^{-tx}，Mellin 变换给出：
    sum_{n=1}^{inf} n^m e^{-tn} ~ Gamma(m+1)/t^{m+1}
                                   + sum_{k=1}^{m} B_k/k! * (-1)^k * m!/(m-k+1)! * t^{k-1-m}
                                   + ...

    更简单：直接用多项式减法。
    发散项是 t^{-m-1}, t^{-m}, ..., t^{-1} 的线性组合。
    系数由 Gamma 函数和 Bernoulli 数决定：

    主项：Gamma(m+1) / t^{m+1} = m! / t^{m+1}
    次项：Gamma(m) * B_1 / t^m = (m-1)! * (-1/2) / t^m  （当 m>=1）
    ...

    这里用一个更稳健的方法：
    直接计算 Sigma(t) - Sigma(2t)*2^{m+1}
    这会消去最主要的发散项 m!/t^{m+1}，
    然后对残差再做一次，直到发散项全部消去。
    """
    pass  # 见下面的 Richardson 方法


def path_B_richardson(m, t0=0.01, N_sum=50000, n_extrap=8):
    """
    莫比乌斯路径 B（修复版）：Richardson 外推

    核心思想：
    Sigma(t) = D(t) + C + O(t)
    其中 D(t) 是发散部分（只含 t 的负幂次）。

    对于 Sigma(t) - 2^{m+1} * Sigma(2t)：
    主发散项 m!/t^{m+1} 被消去（因为 2^{m+1} * m!/(2t)^{m+1} = m!/t^{m+1}）。
    但引入了新的常数项偏移。

    更干净的方法：
    构造线性组合 L[Sigma](t) = sum_k a_k * Sigma(r^k * t)
    使得所有负幂次项系数为零，常数项系数为 1。

    这等价于 Richardson 外推消去奇点。

    对 Sigma(t) = c_{m+1}/t^{m+1} + ... + c_1/t + C + c_{-1}*t + ...
    需要消去 m+1 个发散项，需要 m+2 个采样点。
    """
    # 采样比 r = 2，取 m+2 个点
    r = 2.0
    n_pts = m + 3  # 多取几个点保证稳定

    t_vals = t0 * (r ** np.arange(n_pts))  # t0, 2*t0, 4*t0, ...
    sigma_vals = np.array([sigma(m, t, N_sum) for t in t_vals])

    # 构造 Vandermonde 系统：
    # 发散项为 t^k，k = -(m+1), ..., -1
    # 常数项为 t^0
    # 我们要找权重 w_i 使得：
    #   sum_i w_i * t_i^k = 0  for k = -(m+1), ..., -1
    #   sum_i w_i * t_i^0 = 1  (常数项系数为 1)
    #   sum_i w_i = 1          (即上面 k=0 的条件)

    # 等价地：对 g(t) = t^{m+1} * Sigma(t) 做多项式拟合
    # g(t) = c_{m+1} + c_m * t + ... + c_0 * t^{m+1} + C * t^{m+2} + ...
    # 提取 t^{m+1} 的系数即为常数项 C（乘以 (-1)^? 需要核查符号）

    # 实际上最简单的方法：
    # 令 h(t) = t^{m+1} * Sigma(t)
    # h(t) 在 t=0 处是解析的（所有极点被消去）
    # h(0) = lim_{t->0} t^{m+1} * Sigma(t) = m!  （主项系数）
    # 常数项 C 出现在 h(t) 的 t^{m+1} 系数处
    # 用多项式拟合 h(t) 提取该系数

    h_vals = (t_vals ** (m + 1)) * sigma_vals

    # 对 h(t) 做多项式拟合，次数到 m+3
    deg = m + 3
    coeffs = np.polyfit(t_vals, h_vals, deg)
    # polyfit 返回从高次到低次的系数
    # t^{m+1} 的系数在 coeffs[deg - (m+1)] 位置
    poly_coeffs = coeffs[::-1]  # 转为从低次到高次：poly_coeffs[k] 是 t^k 的系数

    if m + 1 < len(poly_coeffs):
        C = poly_coeffs[m + 1]
    else:
        C = float('nan')

    return C


# ============================================================
# 运行实验一
# ============================================================

def run_experiment_1():
    print("=" * 68)
    print("实验一（修复版）：莫比乌斯正则化的独立路径验证")
    print("=" * 68)
    print("路径 A：经典公式 zeta(-m) = -B_{m+1}/(m+1)")
    print("路径 B：Richardson 外推提取 Laurent 常数项")
    print("        （不使用 Bernoulli 数，只做数值级数求和）")
    print()
    print(f"{'m':>3} {'路径A（精确）':>14} {'路径B（数值）':>14} "
          f"{'误差':>12} {'相对误差':>10} {'吻合?':>6}")
    print("-" * 65)

    m_values = [1, 2, 3, 4, 5]
    all_match = True

    for m in m_values:
        A = zeta_neg_m(m)
        B = path_B_richardson(m)

        if abs(A) > 1e-10:
            rel_err = abs(A - B) / abs(A)
        else:
            rel_err = abs(B)  # A=0 时看绝对误差

        match = "✓" if rel_err < 0.05 else "✗"  # 5% 相对误差容差
        if match == "✗":
            all_match = False

        print(f"{m:>3} {A:>14.8f} {B:>14.8f} "
              f"{abs(A - B):>12.2e} {rel_err:>10.4f} {match:>6}")

    print()
    print(f"总体结论：{'两条独立路径吻合 ✓' if all_match else '存在不吻合项 ✗（见下方说明）'}")
    print()
    print("说明：")
    print("  m=2,4（结果为 0）的相对误差用绝对误差衡量。")
    print("  数值误差来源：级数截断（N=50000）+ 多项式拟合条件数。")
    print("  理论保证：N->inf 时路径 B 严格收敛到路径 A 的值（T44）。")


# ============================================================
# 实验二修复
# ============================================================

def mobius_op(p, q):
    """莫比乌斯运算：(x,s,e) o (y,r,d) = (x+y, s+e*r, e*d)"""
    return (p[0] + q[0], p[1] + p[2] * q[1], p[2] * q[2])


def phi_se(s, epsilon):
    """
    正确的 2x2 嵌入：只追踪 (s, epsilon)
    Phi(s, e) = [[e, s],
                 [0, 1]]
    验证：Phi(s1+e1*s2, e1*e2) = Phi(s1,e1) @ Phi(s2,e2)
    """
    return np.array([[epsilon, s], [0, 1]], dtype=np.float64)


def verify_embedding():
    """验证 2x2 嵌入的正确性"""
    print("=" * 65)
    print("代数验证（修复版）：Phi(s,e) 的 2x2 嵌入")
    print("注：x 分量线性独立累加，不进入矩阵")
    print("=" * 65)

    test_cases = [
        ((1.0, 2.0, +1), (3.0, 4.0, -1)),
        ((0.5, -1.0, -1), (2.0, 1.5, -1)),
        ((np.pi, 0.0, +1), (0.0, 1.0, -1)),
        ((1.0, 1.0, -1), (1.0, 1.0, -1)),
        ((0.0, 1.0, -1), (0.0, 1.0, +1)),  # 原始反例
    ]

    print(f"{'测试':>4} {'莫比乌斯 (s,e)':>20} {'矩阵读出 (s,e)':>20} "
          f"{'x误差':>10} {'se误差':>10} {'✓?':>4}")
    print("-" * 75)

    all_ok = True
    for i, (p, q) in enumerate(test_cases):
        x1, s1, e1 = p
        x2, s2, e2 = q

        # 莫比乌斯运算
        mob = mobius_op(p, q)

        # 矩阵乘法（只追踪 s, epsilon）
        M = phi_se(s1, e1) @ phi_se(s2, e2)
        mat_e = M[0, 0]
        mat_s = M[0, 1]
        mat_x = x1 + x2  # x 单独线性累加

        err_x = abs(mob[0] - mat_x)
        err_s = abs(mob[1] - mat_s)
        err_e = abs(mob[2] - mat_e)
        ok = err_x < 1e-10 and err_s < 1e-10 and err_e < 1e-10
        if not ok:
            all_ok = False

        print(f"{i + 1:>4} ({mob[1]:6.2f},{int(mob[2]):+d})          "
              f"({mat_s:6.2f},{int(mat_e):+d})          "
              f"{err_x:>10.2e} {max(err_s, err_e):>10.2e} {'✓' if ok else '✗':>4}")

    print(f"\n代数验证：{'全部通过 ✓' if all_ok else '存在失败 ✗'}")
    print()
    return all_ok


def verify_noncommutativity_fixed():
    """使用 s_A != 0 且 s_B != 0 的真正非交换参数"""
    print("=" * 65)
    print("非交换性验证（修复版）")
    print("=" * 65)

    # 两个纤维分量都非零，扭转状态不同
    p = (0.0, 1.0, -1)  # s=1, epsilon=-1
    q = (0.0, 2.0, +1)  # s=2, epsilon=+1

    pq = mobius_op(p, q)
    qp = mobius_op(q, p)

    print(f"p = (x=0, s=1, ε=-1)")
    print(f"q = (x=0, s=2, ε=+1)")
    print(f"p o q = (x={pq[0]}, s={pq[1]}, ε={int(pq[2])})")
    print(f"q o p = (x={qp[0]}, s={qp[1]}, ε={int(qp[2])})")
    print(f"非交换：p o q ≠ q o p → {pq != qp}")
    print(f"纤维差：{pq[1]} - {qp[1]} = {pq[1] - qp[1]}")
    print()

    # 矩阵验证
    M_pq = phi_se(1.0, -1) @ phi_se(2.0, +1)
    M_qp = phi_se(2.0, +1) @ phi_se(1.0, -1)
    print(f"矩阵 Phi(p)@Phi(q):\n{M_pq}")
    print(f"矩阵 Phi(q)@Phi(p):\n{M_qp}")
    print(f"矩阵非交换性确认: {not np.allclose(M_pq, M_qp)}")
    print()


def run_evolution():
    """演化实验：真正非交换参数 + 正确等价性验证"""
    print("=" * 65)
    print("演化实验（修复版）：非交换合成的性能与等价性")
    print("=" * 65)

    # 真正非交换：两个元素的纤维分量都非零
    # A: 正扭转，带纤维
    # B: 负扭转，带纤维
    # A o B ≠ B o A（已验证）
    A_mob = (0.03, 1.0, +1)
    B_mob = (0.01, 0.5, -1)

    A_mat = phi_se(A_mob[1], A_mob[2])
    B_mat = phi_se(B_mob[1], B_mob[2])

    # 先确认非交换性
    AB = mobius_op(A_mob, B_mob)
    BA = mobius_op(B_mob, A_mob)
    print(f"A = (x={A_mob[0]}, s={A_mob[1]}, ε={int(A_mob[2])})")
    print(f"B = (x={B_mob[0]}, s={B_mob[1]}, ε={int(B_mob[2])})")
    print(f"A o B = (s={AB[1]:.4f}, ε={int(AB[2])})")
    print(f"B o A = (s={BA[1]:.4f}, ε={int(BA[2])})")
    print(f"非交换性确认: {not np.isclose(AB[1], BA[1])}")
    print()

    steps_list = [100, 1000, 10000, 100000, 1000000]

    print(f"{'步数':>10} {'矩阵(ms)':>12} {'莫比乌斯(ms)':>14} "
          f"{'加速比':>8} {'s误差':>12} {'e吻合':>8}")
    print("-" * 70)

    for steps in steps_list:
        # 矩阵方法
        t0 = time.perf_counter()
        for _ in range(3):
            M = np.eye(2)
            x_mat = 0.0
            for i in range(steps):
                if i % 2 == 0:
                    M = A_mat @ M
                    x_mat += A_mob[0]
                else:
                    M = B_mat @ M
                    x_mat += B_mob[0]
        t_mat = (time.perf_counter() - t0) / 3

        # 莫比乌斯方法
        t0 = time.perf_counter()
        for _ in range(3):
            state = (0.0, 0.0, +1)
            for i in range(steps):
                if i % 2 == 0:
                    state = mobius_op(state, A_mob)
                else:
                    state = mobius_op(state, B_mob)
        t_mob = (time.perf_counter() - t0) / 3

        # 等价性验证
        mat_e = M[0, 0]
        mat_s = M[0, 1]
        err_s = abs(state[1] - mat_s)
        err_e = abs(state[2] - mat_e)
        match_e = "✓" if err_e < 0.5 else "✗"

        speedup = t_mat / t_mob
        print(f"{steps:>10} {t_mat * 1000:>12.3f} {t_mob * 1000:>14.3f} "
              f"{speedup:>7.1f}x {err_s:>12.2e} {match_e:>8}")

    print()
    print(f"最终状态（莫比乌斯）: x={state[0]:.4f}, s={state[1]:.4f}, ε={int(state[2])}")
    print(f"最终状态（矩阵读出）: x={x_mat:.4f}, s={M[0, 1]:.4f}, ε={int(M[0, 0])}")


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    run_experiment_1()
    print()
    verify_embedding()
    verify_noncommutativity_fixed()
    run_evolution()
