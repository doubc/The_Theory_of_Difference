import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os


def visualize_mobius_prime_topology(n_max=5000, save_dir="output_data"):
    """
    1. 构建三维莫比乌斯带
    2. 将素数映射到带上
    3. 观察素数的空间分布与扭转关系
    """
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # 1. 生成素数
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(np.sqrt(n_max)) + 1):
        if sieve[i]:
            sieve[i * i::i] = False
    primes = np.where(sieve)[0]

    # 2. 定义莫比乌斯带参数
    # u: 角度 (0 to 2pi), v: 带宽 (-1 to 1)
    u = np.linspace(0, 2 * np.pi, 200)
    v = np.linspace(-1, 1, 50)
    U, V = np.meshgrid(u, v)

    R = 3.0
    X = (R + V * np.cos(U / 2)) * np.cos(U)
    Y = (R + V * np.cos(U / 2)) * np.sin(U)
    Z = V * np.sin(U / 2)

    # 3. 计算素数在带上的坐标
    # 我们将素数 p 映射到角度 theta_p
    # 关键：如何让素数“落”在带上？
    # 尝试方案：theta_p = 2 * pi * (p / n_max)
    prime_u = 2 * np.pi * primes / n_max
    prime_v = np.zeros_like(prime_u)  # 先放在中心线上

    px = (R + prime_v * np.cos(prime_u / 2)) * np.cos(prime_u)
    py = (R + prime_v * np.cos(prime_u / 2)) * np.sin(prime_u)
    pz = prime_v * np.sin(prime_u / 2)

    # --- 图1: 三维莫比乌斯带上的素数分布 ---
    fig1 = plt.figure(figsize=(12, 8))
    ax1 = fig1.add_subplot(111, projection='3d')

    # 绘制半透明的莫比乌斯带网格
    ax1.plot_surface(X, Y, Z, alpha=0.1, color='cyan', rstride=5, cstride=5)

    # 绘制素数点（红色）
    ax1.scatter(px, py, pz, c='red', s=20, depthshade=True, label='Primes on Centerline')

    ax1.set_title(f"Primes on 3D Möbius Strip (N={n_max})")
    ax1.legend()
    plt.savefig(os.path.join(save_dir, "mobius_3d_primes.png"), dpi=300, bbox_inches='tight')

    # --- 图2: 展开后的相位-间隙图 (The Unrolled View) ---
    # 这能看出“不均匀的圆”背后的规律
    fig2, (ax2, ax3) = plt.subplots(2, 1, figsize=(12, 10))

    log_p = np.log(primes)
    phase = np.mod(log_p, 2 * np.pi)
    gaps = np.diff(primes)

    # 子图 A: 相位分布直方图
    ax2.hist(phase, bins=100, color='steelblue', edgecolor='black', alpha=0.7)
    ax2.set_title("Distribution of Prime Phases (log(p) mod 2π)")
    ax2.set_xlabel("Phase [0, 2π)")
    ax2.grid(True, alpha=0.3)

    # 子图 B: 相位 vs 间隙
    ax3.scatter(phase[:-1], gaps, c=primes[1:], cmap='plasma', s=10, alpha=0.6)
    ax3.set_title("Prime Gaps vs. Phase Position")
    ax3.set_xlabel("Phase")
    ax3.set_ylabel("Numerical Gap")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, "mobius_phase_analysis.png"), dpi=300, bbox_inches='tight')
    plt.show()
    print(f"Images saved to {save_dir}")

# 执行可视化
visualize_mobius_prime_topology()
