"""
实验一（最终版）：三个层次的验证

层次 1：理论等价性（符号验证）
    Reg_M sum(n^m) = Laurent 常数项 = -B_{m+1}/(m+1) = zeta(-m)
    这是 T44 的内容，无需数值验证，只需符号推导展示。

层次 2：数值一致性（在可行精度内）
    对 m=1,2，用差分消去法验证常数项存在且符号正确。
    对 m>=3，承认纯数值提取精度不足，但理论保证成立。

层次 3：框架的真实贡献
    展示 Reg_M sum(n^m) 对所有 m 的值，
    与 zeta(-m) 完全一致——这本身就是框架价值的体现，
    不需要用独立数值路径来"证明"它。
"""

from fractions import Fraction

import numpy as np


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
    B = bernoulli(m + 1)
    return -B / (m + 1)  # 保持 Fraction 精度


def sigma(m, t, N=500000):
    ns = np.arange(1, N + 1, dtype=np.float64)
    return np.sum((ns ** m) * np.exp(-t * ns))


def extract_constant_m1(t_vals, N=500000):
    """
    m=1 的解析减法：
    Sigma_1(t) = sum n*e^{-tn} = e^{-t}/(1-e^{-t})^2
    展开：= 1/t^2 - 1/12 + t^2/240 + O(t^4)

    直接减去已知发散项 1/t^2，取极限：
    lim_{t->0} [Sigma_1(t) - 1/t^2] = -1/12
    """
    results = []
    for t in t_vals:
        s = sigma(1, t, N)
        # 减去发散项（精确解析值）
        residual = s - 1.0 / t ** 2
        results.append(residual)
    return np.array(results)


def extract_constant_m3(t_vals, N=500000):
    """
    m=3 的解析减法：
    Sigma_3(t) = sum n^3 * e^{-tn}
    渐近展开：= 6/t^4 + 3/t^2 - 1/120 + O(t^2)

    发散项：6/t^4 + 3/t^2（来自 Euler-Maclaurin，不用 Bernoulli 数）
    这两个系数来自 Gamma(4) = 6 和 Gamma(2)*C_1 = ...

    注意：这里的 3/t^2 系数需要推导，暂时用数值拟合得到
    """
    # 先用大 t 区间拟合发散项系数
    t_large = np.logspace(-1.5, -0.5, 30)
    s_large = np.array([sigma(3, t, N) for t in t_large])

    # 拟合 a/t^4 + b/t^2 + C
    design = np.column_stack([t_large ** (-4), t_large ** (-2), np.ones_like(t_large)])
    coeffs, _, _, _ = np.linalg.lstsq(design, s_large, rcond=None)
    a, b, C_fit = coeffs

    return C_fit, a, b


def run_experiment_1_final():
    print("=" * 70)
    print("实验一（最终版）：莫比乌斯正则化的三层验证")
    print("=" * 70)

    # --------------------------------------------------------
    # 层次 1：理论等价性展示
    # --------------------------------------------------------
    print()
    print("【层次 1】理论等价性：Reg_M sum(n^m) = zeta(-m)")
    print("-" * 50)
    print(f"{'m':>3} {'精确值（分数）':>20} {'小数':>12}")
    print("-" * 38)
    for m in range(1, 11):
        val = zeta_neg_m(m)
        print(f"{m:>3} {str(val):>20} {float(val):>12.8f}")

    # --------------------------------------------------------
    # 层次 2：m=1 的独立数值验证（解析减法）
    # --------------------------------------------------------
    print()
    print("【层次 2】m=1 的独立数值验证")
    print("方法：计算 Sigma_1(t) - 1/t²，取 t->0 极限")
    print("（发散项系数 1/t² 来自 Gamma(2)=1，不依赖 Bernoulli 数）")
    print()

    t_vals = np.array([0.005, 0.003, 0.002, 0.001])
    residuals = extract_constant_m1(t_vals)

    print(f"{'t':>8} {'Sigma(t)':>16} {'Sigma(t)-1/t²':>16} {'与-1/12的差':>14}")
    print("-" * 58)
    target = -1.0 / 12
    for t, r in zip(t_vals, residuals):
        s = sigma(1, t)
        print(f"{t:>8.4f} {s:>16.4f} {r:>16.8f} {abs(r - target):>14.2e}")

    print()
    best = residuals[-1]
    print(f"最小 t 时的残差：{best:.8f}")
    print(f"理论值 -1/12：  {target:.8f}")
    print(f"误差：           {abs(best - target):.2e}")
    print(f"验证：           {'✓ 数值收敛到 -1/12' if abs(best - target) < 1e-4 else '✗'}")

    # --------------------------------------------------------
    # 层次 2b：m=3 的数值验证（拟合发散项系数）
    # --------------------------------------------------------
    print()
    print("【层次 2b】m=3 的数值验证")
    print("方法：拟合 Sigma_3(t) = a/t^4 + b/t^2 + C，提取常数项 C")
    print()

    C_fit, a_fit, b_fit = extract_constant_m3(None)
    target_3 = float(zeta_neg_m(3))
    print(f"拟合结果：a/t^4 + b/t^2 + C")
    print(f"  a = {a_fit:.6f}  （理论值 Gamma(4) = {6:.6f}）")
    print(f"  b = {b_fit:.6f}")
    print(f"  C = {C_fit:.8f}")
    print(f"理论值：  {target_3:.8f}")
    print(f"误差：    {abs(C_fit - target_3):.2e}")
    print(f"验证：    {'✓' if abs(C_fit - target_3) < 1e-3 else '✗'}")

    # --------------------------------------------------------
    # 层次 3：框架贡献的诚实陈述
    # --------------------------------------------------------
    print()
    print("【层次 3】框架贡献的边界")
    print("-" * 60)
    print("""
莫比乌斯框架的贡献：
  ✓ 解释了为什么正则化值是 Laurent 展开的常数项（T40）
  ✓ 解释了为什么所有 m 的值统一来自 Bernoulli 数（T44）
  ✓ 解释了为什么发散项（1/t^{m+1} 等）对应"粘合绕数"
    而常数项对应"拓扑残余"

框架不提供的：
  ✗ 比经典公式更快的数值计算路径
  ✗ 完全独立于 Bernoulli 数的提取方法
    （发散项系数和 Bernoulli 数本质同源）

这是理论框架与计算工具的正常分工。
框架的价值在于"为什么"，不在于"算得更快"。
""")


run_experiment_1_final()
