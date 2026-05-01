import time

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


# ============================================================
# Benchmark 1: 磁滞回线
# ============================================================

# --- 传统方法：Jiles-Atherton ---
def langevin(x):
    if abs(x) < 1e-10:
        return x / 3.0
    return 1.0 / np.tanh(x) - 1.0 / x


def jiles_atherton(H_array, Ms=1e6, a=1000, alpha=1e-3, k=5000, c=0.1):
    """
    Jiles-Atherton 磁滞模型
    5个经验参数，每步需要判断方向、分段计算
    """
    M = np.zeros_like(H_array)
    M[0] = 0.0
    Heff = np.zeros_like(H_array)

    for i in range(1, len(H_array)):
        Heff[i] = H_array[i] + alpha * M[i - 1]
        Man = Ms * langevin(a * Heff[i])

        dH = H_array[i] - H_array[i - 1]
        if abs(dH) < 1e-20:
            M[i] = M[i - 1]
            continue

        delta = 1.0 if dH > 0 else -1.0
        dM_irr = (Man - M[i - 1]) / (k * delta - alpha * (Man - M[i - 1]))

        if abs(k * delta - alpha * (Man - M[i - 1])) < 1e-20:
            dM_irr = 0.0

        dM = dM_irr * (1 - c) + c * dH * Ms / a
        M[i] = M[i - 1] + dM

    return M


# --- 莫比乌斯方法 ---
def mobius_hysteresis(H_array, chi=0.8):
    """
    莫比乌斯算数磁滞模型
    单个运算，方向由 epsilon 自动编码
    不需要分段，不需要 langevin，不需要5个参数
    """
    M = np.zeros_like(H_array)
    # 状态: (H, M, epsilon)
    H_curr, M_curr, eps = 0.0, 0.0, +1

    for i in range(len(H_array)):
        dH = H_array[i] - H_curr

        # 莫比乌斯运算
        eps = +1 if dH >= 0 else -1
        H_curr = H_curr + dH
        M_curr = M_curr + eps * chi * dH

        M[i] = M_curr

    return M


# --- 驱动磁场：三角波 ---
N_points = 10000
H_max = 80000
cycles = 3
t = np.linspace(0, cycles * 2 * np.pi, N_points)
H_drive = H_max * np.sin(t)

# --- 计时 ---
t0 = time.perf_counter()
M_ja = jiles_atherton(H_drive)
t_ja = time.perf_counter() - t0

t0 = time.perf_counter()
M_mob = mobius_hysteresis(H_drive)
t_mob = time.perf_counter() - t0

print("=" * 60)
print("Benchmark 1: 磁滞回线")
print("=" * 60)
print(f"点数:           {N_points}")
print(f"Jiles-Atherton: {t_ja * 1000:.2f} ms")
print(f"莫比乌斯:       {t_mob * 1000:.2f} ms")
print(f"加速比:         {t_ja / t_mob:.1f}x")
print(f"参数数:         JA=5, 莫比乌斯=1")

# --- 画图 ---
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].plot(H_drive, M_ja, 'b-', linewidth=0.8, label='Jiles-Atherton (5参数)')
axes[0].plot(H_drive, M_mob, 'r--', linewidth=0.8, label='莫比乌斯 (1参数)')
axes[0].set_xlabel('H (磁场)')
axes[0].set_ylabel('M (磁化)')
axes[0].set_title('磁滞回线对比')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# 时间对比柱状图
axes[1].bar(['Jiles-Atherton\n(5参数)', '莫比乌斯\n(1参数)'],
            [t_ja * 1000, t_mob * 1000],
            color=['steelblue', 'crimson'], alpha=0.8)
axes[1].set_ylabel('时间 (ms)')
axes[1].set_title(f'计算时间对比 (加速 {t_ja / t_mob:.1f}x)')
axes[1].grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('benchmark_hysteresis.png', dpi=150)
plt.show()
print("图已保存: benchmark_hysteresis.png")
