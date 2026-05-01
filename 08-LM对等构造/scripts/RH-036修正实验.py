"""
RH-036 修正实验：临界线上的极小值对齐
沿 σ=0.5 密集采样 |D(1/2+it, N)|，
找局部极小值位置，与已知黎曼零点比较
"""

import numpy as np
import json
import os
import matplotlib.pyplot as plt
from scipy.signal import argrelmin

DATA_DIR   = "./rh036_data"
OUTPUT_DIR = "./rh036_results"

KNOWN_ZEROS = [
    14.1347, 21.0220, 25.0109, 30.4249, 32.9351,
    37.5862, 40.9187, 43.3271, 48.0052, 49.7738,
    52.9703, 56.4462, 59.3470, 60.8318, 65.1125,
    67.0798, 69.5464, 72.0672, 75.7047, 77.1448,
]

def load_mu(N=20000):
    with open(os.path.join(DATA_DIR, "rh036_omega.json")) as f:
        d = json.load(f)
    return np.array(d["mu"][:N], dtype=np.float64)

def scan_critical_line(mu, t_min=10, t_max=80, t_steps=2000, sigma=0.5):
    """
    在临界线 σ=0.5 上密集采样 |D(s,N)|
    t_steps 要足够密，才能分辨相邻零点（最近间距约 2）
    """
    N = len(mu)
    ns = np.arange(1, N+1, dtype=np.float64)
    log_ns = np.log(ns)
    n_sigma = ns ** (-sigma)   # n^{-σ}，与 t 无关，预计算

    ts = np.linspace(t_min, t_max, t_steps)
    vals = np.zeros(t_steps)

    print(f"扫描临界线 σ={sigma}，t∈[{t_min},{t_max}]，步数={t_steps}，N={N}...")
    for j, t in enumerate(ts):
        phases = np.exp(-1j * t * log_ns)
        D = np.sum(mu * n_sigma * phases)
        vals[j] = abs(D)
        if j % 200 == 0:
            print(f"  进度 {j}/{t_steps}")

    return ts, vals

def find_local_minima(ts, vals, order=5):
    """找局部极小值"""
    idx = argrelmin(vals, order=order)[0]
    return ts[idx], vals[idx]

def main():
    mu = load_mu(N=20000)

    # 扫描临界线
    ts, vals = scan_critical_line(mu, t_min=10, t_max=80, t_steps=3000)

    # 找极小值
    min_ts, min_vals = find_local_minima(ts, vals, order=8)
    print(f"\n找到 {len(min_ts)} 个局部极小值")

    # 与已知零点对比：每个极小值找最近的已知零点
    print(f"\n{'极小值 t':>12} {'最近零点 γ':>14} {'偏差':>10} {'极小值':>12}")
    print("-" * 52)
    matched = []
    for t_min_val, v in zip(min_ts, min_vals):
        dists = [abs(t_min_val - g) for g in KNOWN_ZEROS]
        nearest_gamma = KNOWN_ZEROS[np.argmin(dists)]
        deviation = t_min_val - nearest_gamma
        matched.append(abs(deviation))
        print(f"{t_min_val:>12.4f} {nearest_gamma:>14.4f} {deviation:>+10.4f} {v:>12.6f}")

    print(f"\n平均偏差: {np.mean(matched):.4f}")
    print(f"中位数偏差: {np.median(matched):.4f}")
    print(f"偏差<0.5 的比例: {np.mean(np.array(matched)<0.5)*100:.1f}%")
    print(f"偏差<1.0 的比例: {np.mean(np.array(matched)<1.0)*100:.1f}%")

    # 可视化
    fig, axes = plt.subplots(2, 1, figsize=(16, 9))
    fig.suptitle(f"临界线 σ=0.5 上的 |D(s,N)| 极小值 vs 黎曼零点（N={len(mu)}）", fontsize=13)

    # 上图：完整扫描
    ax = axes[0]
    ax.plot(ts, vals, 'b-', lw=0.7, label='|D(1/2+it, N)|')
    ax.scatter(min_ts, min_vals, color='green', s=40, zorder=5, label='局部极小值')
    for g in KNOWN_ZEROS:
        ax.axvline(g, color='red', lw=0.8, alpha=0.6, ls='--')
    ax.axvline(KNOWN_ZEROS[0], color='red', lw=0.8, alpha=0.6, ls='--', label='已知黎曼零点')
    ax.set_xlabel('t = Im(s)')
    ax.set_ylabel('|D(s,N)|')
    ax.set_title('全局视图')
    ax.legend(loc='upper right')
    ax.grid(alpha=0.3)

    # 下图：局部放大（前5个零点）
    ax = axes[1]
    t_zoom = (10, 55)
    mask = (ts >= t_zoom[0]) & (ts <= t_zoom[1])
    ax.plot(ts[mask], vals[mask], 'b-', lw=1.2, label='|D(1/2+it, N)|')
    min_mask = (min_ts >= t_zoom[0]) & (min_ts <= t_zoom[1])
    ax.scatter(min_ts[min_mask], min_vals[min_mask],
               color='green', s=60, zorder=5, label='局部极小值')
    for g in KNOWN_ZEROS:
        if t_zoom[0] <= g <= t_zoom[1]:
            ax.axvline(g, color='red', lw=1.2, alpha=0.7, ls='--')
    ax.set_xlabel('t = Im(s)')
    ax.set_ylabel('|D(s,N)|')
    ax.set_title('局部放大（t=10~55）')
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "rh036_critical_line_scan.png")
    plt.savefig(path, dpi=150)
    print(f"\n✓ 图已保存: {path}")
    plt.close()

if __name__ == "__main__":
    main()
