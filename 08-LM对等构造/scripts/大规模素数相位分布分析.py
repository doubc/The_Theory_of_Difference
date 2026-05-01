import numpy as np
import matplotlib.pyplot as plt
import os


def visualize_large_scale_mobius_phase(n_max=100000):
    """
    大规模素数相位分布分析，验证"相位空洞"的稳定性
    """
    print(f"正在生成 {n_max} 以内的素数...")
    # 1. 埃拉托斯特尼筛法
    sieve = np.ones(n_max + 1, dtype=bool)
    sieve[0] = sieve[1] = False
    for i in range(2, int(np.sqrt(n_max)) + 1):
        if sieve[i]:
            sieve[i * i::i] = False

    primes = np.where(sieve)[0]
    print(f"✓ 找到 {len(primes)} 个素数")

    # 2. 计算相位与间隙
    # 相位定义为 ln(p) mod 2pi
    log_primes = np.log(primes)
    phases = np.mod(log_primes, 2 * np.pi)
    gaps = np.diff(primes)

    # 3. 可视化配置
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))

    # --- 图 1: 相位分布直方图 ---
    # 使用 200 个 bin 来观察精细结构
    counts, bins, patches = ax1.hist(phases, bins=200, color='steelblue', edgecolor='none', alpha=0.8)

    # 标记出之前的"空洞"区域
    ax1.axvspan(2.4, 4.5, color='red', alpha=0.1, label='Previous Forbidden Zone')

    ax1.set_title(f"Distribution of Prime Phases (N={n_max})", fontsize=15, fontweight='bold')
    ax1.set_xlabel(r"Phase $\phi = \ln(p)\ (\mathrm{mod}\ 2\pi)$", fontsize=12)
    ax1.set_ylabel("Count", fontsize=12)
    ax1.legend()

    # 在柱子上标注峰值，观察是否有周期性
    max_idx = np.argmax(counts)
    ax1.text(bins[max_idx], counts[max_idx], f" Peak: {bins[max_idx]:.2f}",
             color='red', fontweight='bold', ha='left')

    # --- 图 2: 相位 vs 间隙 (带大小映射) ---
    # 颜色映射：素数的大小 (log scale)
    sc = ax2.scatter(phases[:-1], gaps, c=np.log(primes[1:]), cmap='viridis',
                     s=3, alpha=0.5, edgecolors='none')

    ax2.set_title("Prime Gaps vs. Phase Position (Color = log(Prime))", fontsize=15, fontweight='bold')
    ax2.set_xlabel(r"Phase $\phi$", fontsize=12)
    ax2.set_ylabel("Prime Gap ($p_{k+1} - p_k$)", fontsize=12)

    # 添加颜色条
    cbar = plt.colorbar(sc, ax=ax2)
    cbar.set_label("Log(Prime Value)", fontsize=10)

    # 标记"安全区" (低间隙区域)
    ax2.axhline(y=10, color='r', linestyle='--', alpha=0.5, label='Small Gap Threshold (10)')
    ax2.legend()

    plt.tight_layout()
    plt.savefig("mobius_phase_large_scale.png", dpi=300, bbox_inches='tight')
    plt.show()

    # 4. 简单的统计检验：比较空洞区与非空洞区的密度
    mask_hole = (phases > 2.4) & (phases < 4.5)
    mask_safe = ~mask_hole

    density_hole = np.sum(mask_hole) / len(phases)
    density_safe = np.sum(mask_safe) / len(phases)

    print(f"\n📊 统计结果:")
    print(f"  空洞区 (2.4-4.5) 密度: {density_hole:.2%}")
    print(f"  安全区 (其他) 密度: {density_safe:.2%}")
    print(f"  密度比 (Safe/Hole): {density_safe / density_hole:.2f}x")

# 运行实验
visualize_large_scale_mobius_phase(100000)
