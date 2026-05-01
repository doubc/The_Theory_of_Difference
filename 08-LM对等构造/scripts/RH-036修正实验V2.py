"""
RH-036 修正实验 v2：用 ζ(s) 部分和（加速收敛版）
在临界线上寻找 |Z̃(s,N)| 的极小值，与黎曼零点对齐

核心修正：从 Σμ(n)n^{-s}（1/ζ 的截断，零点处是极大）
          改为 Σn^{-s}（ζ 的截断，零点处应是极小）
          加 Euler-Maclaurin 修正项加速收敛
"""

import numpy as np
import json
import os
import matplotlib.pyplot as plt
from scipy.signal import argrelmin

DATA_DIR   = "./rh036_data"
OUTPUT_DIR = "./rh036_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

KNOWN_ZEROS = [
    14.1347, 21.0220, 25.0109, 30.4249, 32.9351,
    37.5862, 40.9187, 43.3271, 48.0052, 49.7738,
    52.9703, 56.4462, 59.3470, 60.8318, 65.1125,
    67.0798, 69.5464, 72.0672, 75.7047, 77.1448,
]

# ─────────────────────────────────────────
# ζ(s) 部分和（三种版本对比）
# ─────────────────────────────────────────
def zeta_partial_sum(s, N, mode='euler_maclaurin'):
    """
    计算 ζ(s) 的近似值，三种模式：
    'raw'             : Σ_{n=1}^{N} n^{-s}（原始截断）
    'tail_corrected'  : 减去尾部积分 N^{1-s}/(1-s)
    'euler_maclaurin' : 加 EM 修正项（最精确）
    """
    ns = np.arange(1, N + 1, dtype=np.float64)
    log_ns = np.log(ns)
    n_neg_s = np.exp(-s.real * log_ns) * np.exp(-1j * s.imag * log_ns)

    Z_raw = np.sum(n_neg_s)

    if mode == 'raw':
        return Z_raw

    # 尾部积分修正：∫_N^∞ x^{-s} dx = N^{1-s}/(s-1)
    tail = N**(1 - s) / (s - 1)
    Z_tail = Z_raw + tail

    if mode == 'tail_corrected':
        return Z_tail

    # Euler-Maclaurin 修正（前两项）
    # +1/2 · N^{-s}  （边界项）
    # -s/12 · N^{-s-1}（一阶导数项）
    em1 = 0.5 * N**(-s)
    em2 = -s / 12.0 * N**(-s - 1)
    Z_em = Z_tail + em1 + em2

    return Z_em

def scan_critical_line_zeta(N=50000, t_min=10, t_max=80,
                             t_steps=4000, mode='euler_maclaurin'):
    """
    在临界线 σ=0.5 上扫描 |ζ̃(s,N)|
    """
    sigma = 0.5
    ts = np.linspace(t_min, t_max, t_steps)
    vals = np.zeros(t_steps)

    print(f"扫描 ζ 部分和（{mode}），N={N}, t_steps={t_steps}...")

    # 预计算 n^{-σ} 和 log(n)
    ns = np.arange(1, N + 1, dtype=np.float64)
    log_ns = np.log(ns)
    n_sigma = ns ** (-sigma)

    for j, t in enumerate(ts):
        s = complex(sigma, t)
        phases = np.exp(-1j * t * log_ns)
        Z_raw = np.sum(n_sigma * phases)

        if mode == 'raw':
            vals[j] = abs(Z_raw)
        else:
            tail = N**(1 - s) / (s - 1)
            em1 = 0.5 * N**(-s)
            em2 = -s / 12.0 * N**(-s - 1)
            Z_em = Z_raw + tail + em1 + em2
            vals[j] = abs(Z_em)

        if j % 500 == 0:
            print(f"  {j}/{t_steps} ({j/t_steps*100:.0f}%)")

    return ts, vals

def analyze_and_plot(ts, vals_dict, title_suffix=""):
    """
    对多个版本的结果做对比分析和可视化
    vals_dict: {'label': vals_array}
    """
    fig, axes = plt.subplots(len(vals_dict) + 1, 1,
                              figsize=(16, 4 * (len(vals_dict) + 1)))
    fig.suptitle(f"ζ(s) 部分和临界线扫描{title_suffix}", fontsize=13)

    all_stats = {}

    for idx, (label, vals) in enumerate(vals_dict.items()):
        # 找极小值
        min_idx = argrelmin(vals, order=8)[0]
        min_ts = ts[min_idx]
        min_vals = vals[min_idx]

        # 与已知零点对比
        matched = []
        for t_min_val in min_ts:
            dists = [abs(t_min_val - g) for g in KNOWN_ZEROS]
            matched.append(min(dists))
        matched = np.array(matched)

        stats = {
            "num_minima": len(min_ts),
            "mean_deviation": float(np.mean(matched)),
            "median_deviation": float(np.median(matched)),
            "within_0.5": float(np.mean(matched < 0.5) * 100),
            "within_1.0": float(np.mean(matched < 1.0) * 100),
        }
        all_stats[label] = stats

        print(f"[{label}]")
        print(f"  极小值数量: {stats['num_minima']}")
        print(f"  平均偏差:   {stats['mean_deviation']:.4f}")
        print(f"  中位数偏差: {stats['median_deviation']:.4f}")
        print(f"  偏差<0.5:   {stats['within_0.5']:.1f}%")
        print(f"  偏差<1.0:   {stats['within_1.0']:.1f}%")

        ax = axes[idx]
        ax.plot(ts, vals, 'b-', lw=0.7, alpha=0.8)
        ax.scatter(min_ts, min_vals, color='green', s=30, zorder=5)
        for g in KNOWN_ZEROS:
            ax.axvline(g, color='red', lw=0.8, alpha=0.5, ls='--')
        ax.set_title(f'{label} | 平均偏差={stats["mean_deviation"]:.3f} | '
                     f'<0.5:{stats["within_0.5"]:.0f}% <1.0:{stats["within_1.0"]:.0f}%')
        ax.set_ylabel('|Z(s,N)|')
        ax.grid(alpha=0.3)

    # 最后一个子图：三版本叠加对比（归一化）
    ax = axes[-1]
    for label, vals in vals_dict.items():
        v_norm = vals / vals.max()
        ax.plot(ts, v_norm, lw=0.7, alpha=0.8, label=label)
    for g in KNOWN_ZEROS:
        ax.axvline(g, color='red', lw=0.8, alpha=0.4, ls='--')
    ax.set_xlabel('t = Im(s)')
    ax.set_ylabel('归一化 |Z|')
    ax.set_title('三版本叠加对比（归一化）')
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rh036_zeta_scan.png")
    plt.savefig(path, dpi=150)
    print(f"✓ 图已保存: {path}")
    plt.close()

    return all_stats

def main():
    print("=" * 60)
    print("RH-036 v2：ζ(s) 部分和临界线扫描")
    print("=" * 60)

    N = 50000
    t_min, t_max, t_steps = 10, 80, 4000

    # 预计算公共部分
    sigma = 0.5
    ns = np.arange(1, N + 1, dtype=np.float64)
    log_ns = np.log(ns)
    n_sigma = ns ** (-sigma)
    ts = np.linspace(t_min, t_max, t_steps)

    vals_raw = np.zeros(t_steps)
    vals_tail = np.zeros(t_steps)
    vals_em = np.zeros(t_steps)

    print(f"计算三种版本（N={N}，t_steps={t_steps}）...")
    for j, t in enumerate(ts):
        s = complex(sigma, t)
        phases = np.exp(-1j * t * log_ns)
        Z_raw = np.sum(n_sigma * phases)

        tail = N**(1 - s) / (s - 1)
        em1  = 0.5 * N**(-s)
        em2  = -s / 12.0 * N**(-s - 1)

        vals_raw[j]  = abs(Z_raw)
        vals_tail[j] = abs(Z_raw + tail)
        vals_em[j]   = abs(Z_raw + tail + em1 + em2)

        if j % 500 == 0:
            print(f"  {j}/{t_steps} ({j/t_steps*100:.0f}%)")

    vals_dict = {
        "raw（原始截断）":           vals_raw,
        "tail_corrected（尾部修正）": vals_tail,
        "euler_maclaurin（EM修正）":  vals_em,
    }

    stats = analyze_and_plot(ts, vals_dict, title_suffix=f"（N={N}）")

    # 保存统计
    import datetime
    ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {"timestamp": ts_str, "N": N, "stats": stats}
    out_path = os.path.join(OUTPUT_DIR, f"rh036_zeta_summary_{ts_str}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✓ 统计已保存: {out_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
