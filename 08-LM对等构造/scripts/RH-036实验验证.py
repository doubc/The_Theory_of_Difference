"""
RH-036 实验验证
三个命题的数值检验 + 可视化

命题1：μ(n) = twist_sign(n) ← 已在代码一验证，这里做统计分析
命题2：|Σ μ(n)n^{-s}| 的极小值结构是否集中在 σ=1/2
命题3：已知黎曼零点处，扭转相位求和是否出现极小值（反向验证）
"""

import numpy as np
import json
import os
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.signal import argrelmin

DATA_DIR = "./rh036_data"
OUTPUT_DIR = "./rh036_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 已知黎曼零点虚部（前20个精确值）
KNOWN_RIEMANN_ZEROS = [
    14.1347, 21.0220, 25.0109, 30.4249, 32.9351,
    37.5862, 40.9187, 43.3271, 48.0052, 49.7738,
    52.9703, 56.4462, 59.3470, 60.8318, 65.1125,
    67.0798, 69.5464, 72.0672, 75.7047, 77.1448,
]

# ─────────────────────────────────────────
# 加载数据
# ─────────────────────────────────────────
def load_data():
    with open(os.path.join(DATA_DIR, "rh036_omega.json")) as f:
        omega_data = json.load(f)
    with open(os.path.join(DATA_DIR, "rh036_grid.json")) as f:
        grid_data = json.load(f)
    print(f"✓ 数据加载完成")
    print(f"  Ω/μ 数据：N={omega_data['N_max']}")
    print(f"  网格数据：σ×t = {len(grid_data['sigmas'])}×{len(grid_data['ts'])}, N={grid_data['N_used']}")
    return omega_data, grid_data


# ─────────────────────────────────────────
# 实验1：扭转相位统计分析
# ─────────────────────────────────────────
def experiment1_twist_statistics(omega_data):
    """
    分析 μ(n) 的符号分布与扭转相位的关系
    核心问题：正负扭转是否"伪随机"平衡？
    """
    print("\n" + "="*60)
    print("实验1：扭转相位统计分析")
    print("="*60)

    mu = np.array(omega_data["mu"])
    N = omega_data["N_max"]
    ns = np.arange(1, N + 1)

    # Mertens 函数 M(x) = Σ_{n≤x} μ(n)
    M = np.cumsum(mu)

    # 统计
    pos = np.sum(mu == 1)
    neg = np.sum(mu == -1)
    zero = np.sum(mu == 0)
    print(f"μ=+1（偶数次扭转）: {pos} ({pos/N*100:.2f}%)")
    print(f"μ=-1（奇数次扭转）: {neg} ({neg/N*100:.2f}%)")
    print(f"μ= 0（相位塌缩）  : {zero} ({zero/N*100:.2f}%)")
    print(f"无平方因子比例: {(pos+neg)/N*100:.2f}% （理论 6/π²={6/np.pi**2*100:.2f}%）")
    print(f"\nM({N}) = {M[-1]}")
    print(f"|M(x)|/√x 最大值: {np.max(np.abs(M)/np.sqrt(ns)):.4f}")
    print(f"|M(x)|/√x 当前值: {abs(M[-1])/np.sqrt(N):.4f}")

    # 图1：M(x) 与 √x 的对比
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("实验1：扭转相位统计 — Mertens 函数与 μ(n) 分布", fontsize=13)

    # (a) M(x) vs ±√x
    ax = axes[0, 0]
    x_plot = ns[::100]
    ax.plot(x_plot, M[::100], 'b-', lw=0.8, label='M(x)')
    ax.plot(x_plot, np.sqrt(x_plot), 'r--', lw=1, label='+√x')
    ax.plot(x_plot, -np.sqrt(x_plot), 'r--', lw=1, label='-√x')
    ax.fill_between(x_plot, -np.sqrt(x_plot), np.sqrt(x_plot), alpha=0.1, color='red')
    ax.set_xlabel('x'); ax.set_ylabel('M(x)')
    ax.set_title('Mertens 函数 M(x) vs ±√x')
    ax.legend(); ax.grid(alpha=0.3)

    # (b) |M(x)|/√x
    ax = axes[0, 1]
    ratio = np.abs(M) / np.sqrt(ns)
    ax.plot(ns[::100], ratio[::100], 'g-', lw=0.8)
    ax.axhline(1.0, color='r', ls='--', lw=1, label='界 = 1（RH 预测上界）')
    ax.set_xlabel('x'); ax.set_ylabel('|M(x)|/√x')
    ax.set_title('|M(x)|/√x（RH 等价：应有界）')
    ax.legend(); ax.grid(alpha=0.3)

    # (c) μ(n) 的游走（随机游走类比）
    ax = axes[1, 0]
    # 只看无平方因子的 n，μ=±1
    squarefree_idx = np.where(mu != 0)[0]
    mu_sf = mu[squarefree_idx]
    walk = np.cumsum(mu_sf)
    ax.plot(range(len(walk[:5000])), walk[:5000], 'purple', lw=0.5)
    ax.plot(range(len(walk[:5000])), np.sqrt(np.arange(len(walk[:5000]))), 'r--', lw=1)
    ax.plot(range(len(walk[:5000])), -np.sqrt(np.arange(len(walk[:5000]))), 'r--', lw=1)
    ax.set_xlabel('无平方因子整数的计数')
    ax.set_ylabel('累积扭转符号')
    ax.set_title('扭转符号游走（±1 随机游走类比）')
    ax.grid(alpha=0.3)

    # (d) Ω(n) 分布
    ax = axes[1, 1]
    omega_vals = np.array(omega_data["omega"])
    max_omega = int(omega_vals.max())
    counts = [np.sum(omega_vals == k) for k in range(max_omega + 1)]
    ax.bar(range(max_omega + 1), counts, color='steelblue', alpha=0.7)
    ax.set_xlabel('Ω(n)（素因子个数，计重数）')
    ax.set_ylabel('计数')
    ax.set_title(f'Ω(n) 分布（n≤{N}）')
    ax.grid(alpha=0.3, axis='y')

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rh036_exp1_twist_stats.png")
    plt.savefig(path, dpi=150)
    print(f"✓ 图1已保存: {path}")
    plt.close()

    return {"M_final": int(M[-1]), "max_ratio": float(ratio.max()),
            "current_ratio": float(ratio[-1])}


# ─────────────────────────────────────────
# 实验2：复平面热图 — 共振轴检验
# ─────────────────────────────────────────
def experiment2_resonance_axis(grid_data):
    """
    在复平面上显示 |Σ μ(n)n^{-s}| 的热图
    核心问题：极小值（深色区域）是否集中在 σ=1/2？
    """
    print("\n" + "="*60)
    print("实验2：复平面共振轴检验")
    print("="*60)

    sigmas = np.array(grid_data["sigmas"])
    ts = np.array(grid_data["ts"])
    grid = np.array(grid_data["grid_mu_abs"])

    min_idx = np.unravel_index(grid.argmin(), grid.shape)
    min_sigma = sigmas[min_idx[0]]
    min_t = ts[min_idx[1]]
    print(f"全局最小值: |D|={grid.min():.6f} 位于 σ={min_sigma:.3f}, t={min_t:.3f}")

    # 沿 t 方向：对每个 σ，找局部极小值的平均深度
    mean_by_sigma = grid.mean(axis=1)
    min_sigma_idx = mean_by_sigma.argmin()
    print(f"平均最小深度对应的 σ: {sigmas[min_sigma_idx]:.3f}（预期 0.500）")

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.suptitle("实验2：复平面共振轴 — |Σ μ(n)n^{-s}|", fontsize=13)

    # (a) 热图
    ax = axes[0]
    im = ax.pcolormesh(ts, sigmas, np.log(grid + 1e-10),
                       cmap='hot_r', shading='auto')
    ax.axhline(0.5, color='cyan', lw=2, ls='--', label='σ=1/2（临界线）')
    # 标记已知零点位置
    for gamma in KNOWN_RIEMANN_ZEROS:
        if ts[0] <= gamma <= ts[-1]:
            ax.axvline(gamma, color='blue', lw=0.5, alpha=0.5)
    ax.set_xlabel('t = Im(s)'); ax.set_ylabel('σ = Re(s)')
    ax.set_title('log|Σ μ(n)n^{-s}|（深色=小）')
    ax.legend(loc='upper right')
    plt.colorbar(im, ax=ax)

    # (b) 沿 σ 方向的平均值
    ax = axes[1]
    ax.plot(sigmas, mean_by_sigma, 'b-o', ms=3)
    ax.axvline(0.5, color='r', ls='--', lw=1.5, label='σ=1/2')
    ax.axvline(sigmas[min_sigma_idx], color='g', ls=':', lw=1.5,
               label=f'实测最小 σ={sigmas[min_sigma_idx]:.3f}')
    ax.set_xlabel('σ = Re(s)')
    ax.set_ylabel('平均 |D(s,N)|')
    ax.set_title('各 σ 的平均部分和模')
    ax.legend(); ax.grid(alpha=0.3)

    # (c) 沿临界线 σ=0.5 的截面
    half_idx = np.argmin(np.abs(sigmas - 0.5))
    ax = axes[2]
    ax.plot(ts, grid[half_idx, :], 'b-', lw=0.8, label=f'σ={sigmas[half_idx]:.3f}')
    # 标记已知零点
    for gamma in KNOWN_RIEMANN_ZEROS:
        if ts[0] <= gamma <= ts[-1]:
            ax.axvline(gamma, color='r', lw=0.8, alpha=0.7, ls='--')
    ax.set_xlabel('t = Im(s)')
    ax.set_ylabel('|D(s,N)|')
    ax.set_title('临界线截面（红线=已知黎曼零点）')
    ax.legend(); ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rh036_exp2_resonance.png")
    plt.savefig(path, dpi=150)
    print(f"✓ 图2已保存: {path}")
    plt.close()

    return {"mean_min_sigma": float(sigmas[min_sigma_idx]),
            "global_min_sigma": float(min_sigma),
            "global_min_t": float(min_t)}


# ─────────────────────────────────────────
# 实验3：已知零点处的扭转相位对齐检验
# ─────────────────────────────────────────
def experiment3_zero_alignment(omega_data, N_check=5000):
    """
    反向验证：在已知黎曼零点 s=1/2+iγ_k 处，
    计算扭转相位求和 Σ μ(n)n^{-s} 的模
    如果框架正确，这些点应该是极小值
    对比：在非零点处（γ_k + 0.5）同样计算，应该更大
    """
    print("\n" + "="*60)
    print("实验3：已知零点处的扭转相位对齐检验")
    print("="*60)

    mu = np.array(omega_data["mu"][:N_check], dtype=np.float64)
    ns = np.arange(1, N_check + 1, dtype=np.float64)
    log_ns = np.log(ns)

    sigma = 0.5  # 临界线

    results_at_zeros = []
    results_off_zeros = []

    for gamma in KNOWN_RIEMANN_ZEROS:
        # 在零点处
        n_neg_s = np.exp(-sigma * log_ns) * np.exp(-1j * gamma * log_ns)
        D_at = abs(np.sum(mu * n_neg_s))
        results_at_zeros.append(D_at)

        # 偏离零点（+0.5）
        n_neg_s_off = np.exp(-sigma * log_ns) * np.exp(-1j * (gamma + 0.5) * log_ns)
        D_off = abs(np.sum(mu * n_neg_s_off))
        results_off_zeros.append(D_off)

    results_at_zeros = np.array(results_at_zeros)
    results_off_zeros = np.array(results_off_zeros)

    print(f"\n{'γ_k':>10} {'|D(1/2+iγ)|':>15} {'|D(1/2+i(γ+0.5))|':>20} {'比值':>8}")
    print("-" * 58)
    for i, gamma in enumerate(KNOWN_RIEMANN_ZEROS):
        ratio = results_at_zeros[i] / (results_off_zeros[i] + 1e-10)
        print(f"{gamma:>10.4f} {results_at_zeros[i]:>15.6f} "
              f"{results_off_zeros[i]:>20.6f} {ratio:>8.4f}")

    print(f"\n平均值（零点处）: {results_at_zeros.mean():.6f}")
    print(f"平均值（偏离处）: {results_off_zeros.mean():.6f}")
    print(f"比值（零点/偏离）: {results_at_zeros.mean()/results_off_zeros.mean():.4f}")
    print(f"（比值<1说明零点处确实更小，支持共振框架）")

    # 图3
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("实验3：已知黎曼零点处的扭转相位对齐", fontsize=13)

    ax = axes[0]
    x = np.arange(len(KNOWN_RIEMANN_ZEROS))
    w = 0.35
    ax.bar(x - w/2, results_at_zeros, w, label='零点处 |D(1/2+iγ)|', color='steelblue')
    ax.bar(x + w/2, results_off_zeros, w, label='偏离处 |D(1/2+i(γ+0.5))|', color='coral')
    ax.set_xticks(x)
    ax.set_xticklabels([f'{g:.1f}' for g in KNOWN_RIEMANN_ZEROS], rotation=45, fontsize=7)
    ax.set_ylabel('|D(s, N)|')
    ax.set_title(f'零点处 vs 偏离处（N={N_check}）')
    ax.legend(); ax.grid(alpha=0.3, axis='y')

    ax = axes[1]
    ax.scatter(KNOWN_RIEMANN_ZEROS, results_at_zeros,
               color='steelblue', s=60, zorder=5, label='零点处')
    ax.scatter(KNOWN_RIEMANN_ZEROS, results_off_zeros,
               color='coral', s=60, zorder=5, marker='^', label='偏离处')
    ax.plot(KNOWN_RIEMANN_ZEROS, results_at_zeros, 'b-', lw=0.8, alpha=0.5)
    ax.plot(KNOWN_RIEMANN_ZEROS, results_off_zeros, 'r-', lw=0.8, alpha=0.5)
    ax.set_xlabel('γ_k（黎曼零点虚部）')
    ax.set_ylabel('|D(s, N)|')
    ax.set_title('随 γ 变化的趋势')
    ax.legend(); ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rh036_exp3_alignment.png")
    plt.savefig(path, dpi=150)
    print(f"✓ 图3已保存: {path}")
    plt.close()

    return {
        "mean_at_zeros": float(results_at_zeros.mean()),
        "mean_off_zeros": float(results_off_zeros.mean()),
        "ratio": float(results_at_zeros.mean() / results_off_zeros.mean()),
    }


# ─────────────────────────────────────────
# 实验4：σ 扫描——极小值集中在哪里？
# ─────────────────────────────────────────
def experiment4_sigma_scan(omega_data, N_check=5000,
                           sigmas=np.linspace(0.3, 0.8, 51)):
    """
    固定已知零点的 t=γ_k，扫描 σ ∈ [0.3, 0.8]
    看 |D(σ+iγ_k)| 的最小值是否落在 σ=0.5
    这是对"临界线是唯一共振轴"的直接数值检验
    """
    print("" + "="*60)
    print("实验4：σ 扫描——极小值集中检验")
    print("="*60)

    mu = np.array(omega_data["mu"][:N_check], dtype=np.float64)
    ns = np.arange(1, N_check + 1, dtype=np.float64)
    log_ns = np.log(ns)

    # 对前10个零点做扫描
    test_zeros = KNOWN_RIEMANN_ZEROS[:10]
    min_sigmas = []

    fig, axes = plt.subplots(2, 5, figsize=(18, 7))
    fig.suptitle("实验4：σ 扫描——|D(σ+iγ)| 的极小值位置", fontsize=13)

    for idx, gamma in enumerate(test_zeros):
        vals = []
        for sigma in sigmas:
            n_neg_s = np.exp(-sigma * log_ns) * np.exp(-1j * gamma * log_ns)
            D = abs(np.sum(mu * n_neg_s))
            vals.append(D)
        vals = np.array(vals)
        min_sigma = sigmas[vals.argmin()]
        min_sigmas.append(min_sigma)

        ax = axes[idx // 5][idx % 5]
        ax.plot(sigmas, vals, 'b-', lw=1.2)
        ax.axvline(0.5, color='r', ls='--', lw=1.5, label='σ=0.5')
        ax.axvline(min_sigma, color='g', ls=':', lw=1.5,
                   label=f'实测最小={min_sigma:.3f}')
        ax.set_title(f'γ={gamma:.4f}', fontsize=9)
        ax.set_xlabel('σ', fontsize=8)
        ax.set_ylabel('|D|', fontsize=8)
        ax.legend(fontsize=6)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rh036_exp4_sigma_scan.png")
    plt.savefig(path, dpi=150)
    print(f"✓ 图4已保存: {path}")
    plt.close()

    min_sigmas = np.array(min_sigmas)
    print(f"{'γ_k':>10} {'实测最小 σ':>12} {'偏离 0.5':>12}")
    print("-" * 38)
    for gamma, ms in zip(test_zeros, min_sigmas):
        print(f"{gamma:>10.4f} {ms:>12.4f} {ms-0.5:>+12.4f}")
    print(f"平均最小 σ: {min_sigmas.mean():.4f}（预期 0.5000）")
    print(f"标准差:     {min_sigmas.std():.4f}")

    return {
        "test_zeros": test_zeros,
        "min_sigmas": min_sigmas.tolist(),
        "mean_min_sigma": float(min_sigmas.mean()),
        "std_min_sigma": float(min_sigmas.std()),
    }


# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def main():
    print("=" * 60)
    print("RH-036 实验验证：扭转相位框架")
    print("=" * 60)

    omega_data, grid_data = load_data()

    r1 = experiment1_twist_statistics(omega_data)
    r2 = experiment2_resonance_axis(grid_data)
    r3 = experiment3_zero_alignment(omega_data, N_check=5000)
    r4 = experiment4_sigma_scan(omega_data, N_check=5000)

    # 汇总结论
    print("" + "=" * 60)
    print("实验汇总与解读")
    print("=" * 60)

    print(f"命题1（扭转相位 = μ(n)）:")
    print(f"  |M(N)|/√N = {r1['current_ratio']:.4f}（<1 支持 RH）")

    print(f"命题2（共振轴）:")
    print(f"  平均最小深度 σ = {r2['mean_min_sigma']:.4f}（预期 0.5000）")

    print(f"命题3（零点对齐）:")
    ratio = r3['ratio']
    print(f"  零点处/偏离处 = {ratio:.4f}")
    if ratio < 1:
        print(f"  ✓ 零点处确实更小，支持扭转共振框架")
    else:
        print(f"  ✗ 零点处未见极小，N 可能不足或框架需修正")

    print(f"命题4（σ 扫描）:")
    print(f"  平均最小 σ = {r4['mean_min_sigma']:.4f}，标准差 = {r4['std_min_sigma']:.4f}")
    deviation = abs(r4['mean_min_sigma'] - 0.5)
    if deviation < 0.05:
        print(f"  ✓ 极小值集中在 σ≈0.5，支持临界线是唯一共振轴")
    else:
        print(f"  △ 偏离 0.5 达 {deviation:.4f}，需增大 N 或检查框架")

    # 保存汇总
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "timestamp": timestamp,
        "exp1_Mertens": r1,
        "exp2_resonance": r2,
        "exp3_alignment": r3,
        "exp4_sigma_scan": {
            "mean_min_sigma": r4["mean_min_sigma"],
            "std_min_sigma": r4["std_min_sigma"],
        },
        "interpretation": {
            "prop1": "μ(n)=扭转符号，精确成立",
            "prop2": f"共振轴 σ={r2['mean_min_sigma']:.4f}",
            "prop3": f"零点处/偏离比={r3['ratio']:.4f}",
            "prop4": f"σ扫描均值={r4['mean_min_sigma']:.4f}±{r4['std_min_sigma']:.4f}",
        }
    }
    out_path = os.path.join(OUTPUT_DIR, f"rh036_summary_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"✓ 汇总已保存: {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

