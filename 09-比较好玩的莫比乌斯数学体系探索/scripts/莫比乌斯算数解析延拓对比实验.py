import time

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


# ============================================================
# Benchmark 2 v2: 正确的莫比乌斯正则化
# ============================================================

def gamma_stirling(z, terms=10):
    if z.real < 0.5:
        return gamma_stirling(z + 1, terms) / z
    result = np.sqrt(2 * np.pi / z) * (z / np.e) ** z
    c = [1 / 12, 1 / 288, -139 / 51840, -571 / 2488320]
    s = 1.0
    for k in range(min(terms, len(c))):
        s += c[k] / (z ** (k + 1))
    return result * s


def traditional_zeta(s, N=2000):
    if s.real > 1:
        ns = np.arange(1, N + 1, dtype=float)
        return np.sum(ns ** (-s))
    else:
        chi = (2.0 ** s) * (np.pi ** (s - 1)) * np.sin(np.pi * s / 2.0) * gamma_stirling(1.0 - s)
        ns = np.arange(1, N + 1, dtype=float)
        zeta_1ms = np.sum(ns ** (s - 1))
        return chi * zeta_1ms


def mobius_zeta_v2(s):
    """
    莫比乌斯正则化 v2：
    用两个不同阻尼值，消去发散项，保留有限部分
    """
    # 两个阻尼参数
    t1 = 0.01
    t2 = 0.02

    N = 2000
    ns = np.arange(1, N + 1, dtype=float)

    # 两个阻尼级数
    S1 = np.sum(ns ** (-s) * np.exp(-2 * np.pi * t1 * ns))
    S2 = np.sum(ns ** (-s) * np.exp(-2 * np.pi * t2 * ns))

    # 发散项形式: A / t^k (对临界线 k=1)
    # 两值相减消去发散项
    # S(t) = A/t + zeta(s) + O(t)
    # S1 = A/t1 + zeta + O(t1)
    # S2 = A/t2 + zeta + O(t2)
    # S1 - S2 = A(1/t1 - 1/t2) + O(t)
    # A = (S1 - S2) / (1/t1 - 1/t2)
    # zeta = S1 - A/t1

    # 更稳健：Richardson 外推
    A = (S1 - S2) / (1.0 / t1 - 1.0 / t2)
    zeta_est = S1 - A / t1

    return zeta_est


# --- 测试 ---
t_values = np.linspace(1, 50, 300)

print("=" * 60)
print("Benchmark 2 v2: 解析延拓 (修正版)")
print("=" * 60)
print(f"测试点数: {len(t_values)}")
print()

t0 = time.perf_counter()
zeta_trad = np.array([traditional_zeta(0.5 + 1j * t) for t in t_values])
t_trad = time.perf_counter() - t0

t0 = time.perf_counter()
zeta_mob = np.array([mobius_zeta_v2(0.5 + 1j * t) for t in t_values])
t_mob = time.perf_counter() - t0

print(f"传统 (函数方程): {t_trad * 1000:.2f} ms")
print(f"莫比乌斯 v2:     {t_mob * 1000:.2f} ms")
print(f"加速比:          {t_trad / t_mob:.1f}x")
print()

diff = np.abs(zeta_trad - zeta_mob)
mag = np.abs(zeta_trad)
rel_diff = diff / (mag + 1e-30)

print(f"最大绝对误差:    {np.max(diff):.6e}")
print(f"平均绝对误差:    {np.mean(diff):.6e}")
print(f"最大相对误差:    {np.max(rel_diff):.6e}")
print(f"平均相对误差:    {np.mean(rel_diff):.6e}")

# --- 画图 ---
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

axes[0, 0].plot(t_values, zeta_trad.real, 'b-', linewidth=0.8, label='传统')
axes[0, 0].plot(t_values, zeta_mob.real, 'r--', linewidth=0.8, label='莫比乌斯 v2')
axes[0, 0].set_xlabel('t')
axes[0, 0].set_ylabel('Re(ζ)')
axes[0, 0].set_title('实部: ζ(1/2 + it)')
axes[0, 0].legend()
axes[0, 0].grid(True, alpha=0.3)

axes[0, 1].plot(t_values, zeta_trad.imag, 'b-', linewidth=0.8, label='传统')
axes[0, 1].plot(t_values, zeta_mob.imag, 'r--', linewidth=0.8, label='莫比乌斯 v2')
axes[0, 1].set_xlabel('t')
axes[0, 1].set_ylabel('Im(ζ)')
axes[0, 1].set_title('虚部: ζ(1/2 + it)')
axes[0, 1].legend()
axes[0, 1].grid(True, alpha=0.3)

axes[1, 0].semilogy(t_values, rel_diff, 'g-', linewidth=0.8)
axes[1, 0].set_xlabel('t')
axes[1, 0].set_ylabel('相对误差')
axes[1, 0].set_title('相对误差')
axes[1, 0].grid(True, alpha=0.3)

axes[1, 1].bar(['传统\n(函数方程)', '莫比乌斯 v2\n(Richardson)'],
               [t_trad * 1000, t_mob * 1000],
               color=['steelblue', 'crimson'], alpha=0.8)
axes[1, 1].set_ylabel('时间 (ms)')
axes[1, 1].set_title(f'计算时间 (加速 {t_trad / t_mob:.1f}x)')
axes[1, 1].grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('benchmark_zeta_v2.png', dpi=150)
plt.show()
print("图已保存: benchmark_zeta_v2.png")
