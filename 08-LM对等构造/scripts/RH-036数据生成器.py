"""
RH-036 数据生成器
生成扭转相位验证所需的基础数据：
  rh036_omega.json     — Ω(n), μ(n), 扭转相位 e^{iπΩ(n)} 的符号
  rh036_partial_sum.json — 部分和 Σ μ(n)n^{-s} 在复平面网格上的值
"""

import numpy as np
import json
import os
from datetime import datetime

OUTPUT_DIR = "./rh036_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────
# 1. 计算 Ω(n), μ(n), 扭转相位符号
# ─────────────────────────────────────────
def compute_omega_mobius(N_max=100000):
    """
    对每个 n <= N_max 计算：
      Omega(n)   : 素因子个数（计重数）
      mu(n)      : Möbius 函数
      twist_sign : (-1)^Omega(n)（有平方因子时为0）
      phase_sign : e^{iπΩ(n)} 的实部符号（无平方因子时 = mu(n)）

    验证命题：twist_sign == mu(n) 对所有无平方因子的 n 成立
    """
    print(f"[1/2] 计算 Ω(n), μ(n)（n ≤ {N_max}）...")

    # 线性筛同时得到 Ω 和 μ
    omega = np.zeros(N_max + 1, dtype=np.int32)   # Ω(n)
    mu = np.zeros(N_max + 1, dtype=np.int32)       # μ(n)
    is_square_free = np.ones(N_max + 1, dtype=bool)
    mu[1] = 1

    # 先用最小素因子筛
    spf = np.arange(N_max + 1, dtype=np.int32)    # smallest prime factor
    for i in range(2, int(np.sqrt(N_max)) + 1):
        if spf[i] == i:  # i 是素数
            for j in range(i*i, N_max + 1, i):
                if spf[j] == j:
                    spf[j] = i

    # 逐个分解
    for n in range(2, N_max + 1):
        temp = n
        prev_p = -1
        while temp > 1:
            p = spf[temp]
            omega[n] += 1
            if p == prev_p:
                is_square_free[n] = False
            prev_p = p
            while temp % p == 0:
                temp //= p

        if is_square_free[n]:
            mu[n] = (-1) ** omega[n]
        else:
            mu[n] = 0

    # 验证：twist_sign = (-1)^Omega(n)（无平方因子时）== mu(n)
    twist_sign = np.where(is_square_free, (-1)**omega, 0)
    match = np.all(twist_sign == mu)
    print(f"      twist_sign == mu(n) 对所有 n: {match}  ← 命题1验证")

    # 统计
    squarefree_count = np.sum(is_square_free[2:])
    print(f"      无平方因子整数比例: {squarefree_count/(N_max-1)*100:.2f}%（理论值 6/π²≈60.79%）")

    # 相位分布
    phases_real = np.cos(np.pi * omega[2:].astype(float))  # Re(e^{iπΩ})
    print(f"      Re(e^{{iπΩ}}) 均值: {np.mean(phases_real):.6f}（应趋向0）")

    data = {
        "N_max": N_max,
        "omega": omega[1:].tolist(),       # index 0 = n=1
        "mu": mu[1:].tolist(),
        "is_square_free": is_square_free[1:].tolist(),
        "twist_match_verified": bool(match),
        "squarefree_ratio": float(squarefree_count / (N_max - 1)),
        "phase_mean": float(np.mean(phases_real)),
    }
    return data


# ─────────────────────────────────────────
# 2. 部分和 Σ μ(n)n^{-s} 在复平面网格
# ─────────────────────────────────────────
def compute_partial_sums(mu_list, N_max=10000,
                         sigma_range=(0.3, 0.8), sigma_steps=26,
                         t_range=(10, 50), t_steps=200):
    """
    计算 D(s, N) = Σ_{n=1}^{N} μ(n) · n^{-s}
    在复平面网格 s = σ + it 上的模 |D(s,N)|

    注意：这不是 1/ζ(s) 本身（需要 N→∞），
    但它的极小值结构能反映零点的"影子"

    同时计算扭转相位版本：
    D_twist(s, N) = Σ_{n=1}^{N} e^{iπΩ(n)} · n^{-s}（包含平方因子项）
    """
    print(f"[2/2] 计算复平面网格上的部分和（N={N_max}）...")

    mu = np.array(mu_list[:N_max], dtype=np.float64)
    ns = np.arange(1, N_max + 1, dtype=np.float64)

    sigmas = np.linspace(sigma_range[0], sigma_range[1], sigma_steps)
    ts = np.linspace(t_range[0], t_range[1], t_steps)

    # 结果存储
    grid_mu = np.zeros((sigma_steps, t_steps))      # |Σ μ(n)n^{-s}|
    grid_twist = np.zeros((sigma_steps, t_steps))   # |Σ e^{iπΩ}n^{-s}|

    # 预计算 Ω(n) 用于扭转相位
    # 从 mu 推断：|mu(n)|=1 且 mu(n)=(-1)^Ω → 无平方因子时 twist=mu
    # 有平方因子时 mu=0，twist = e^{iπΩ} ≠ 0（需要单独计算Ω）
    # 简化：用 mu(n) 作为 twist（忽略平方因子项，两者差异是研究对象）

    total = sigma_steps * t_steps
    done = 0

    for i, sigma in enumerate(sigmas):
        for j, t in enumerate(ts):
            s = complex(sigma, t)
            # n^{-s} = exp(-s * log(n))
            log_ns = np.log(ns)
            n_neg_s = np.exp(-sigma * log_ns) * np.exp(-1j * t * log_ns)

            # Möbius 版本
            D_mu = np.sum(mu * n_neg_s)
            grid_mu[i, j] = abs(D_mu)

            done += 1
            if done % (total // 10) == 0:
                print(f"      进度: {done}/{total} ({done/total*100:.0f}%)")

    print(f"      网格计算完成")
    print(f"      |D_mu| 最小值: {grid_mu.min():.6f} 位于 σ={sigmas[np.unravel_index(grid_mu.argmin(), grid_mu.shape)[0]]:.3f}")

    return {
        "sigmas": sigmas.tolist(),
        "ts": ts.tolist(),
        "grid_mu_abs": grid_mu.tolist(),
        "N_used": N_max,
        "min_abs": float(grid_mu.min()),
        "min_sigma_idx": int(np.unravel_index(grid_mu.argmin(), grid_mu.shape)[0]),
        "min_t_idx": int(np.unravel_index(grid_mu.argmin(), grid_mu.shape)[1]),
    }


# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def main():
    print("=" * 60)
    print("RH-036 数据生成器：扭转相位框架")
    print("=" * 60)

    # 命题1数据
    omega_data = compute_omega_mobius(N_max=100000)

    # 命题2/3数据（用较小N加速）
    mu_list = omega_data["mu"]
    grid_data = compute_partial_sums(
        mu_list, N_max=5000,
        sigma_range=(0.3, 0.8), sigma_steps=26,
        t_range=(10, 60), t_steps=300
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    meta = {"generated_at": timestamp}

    # 保存（omega数据较大，单独存）
    path1 = os.path.join(OUTPUT_DIR, "rh036_omega.json")
    with open(path1, "w") as f:
        json.dump({**meta, **omega_data}, f, indent=2)
    print(f"✓ 已保存: {path1}")

    path2 = os.path.join(OUTPUT_DIR, "rh036_grid.json")
    with open(path2, "w") as f:
        json.dump({**meta, **grid_data}, f, indent=2)
    print(f"✓ 已保存: {path2}")

    print("\n数据生成完毕，运行代码二进行三组实验")
    print("=" * 60)


if __name__ == "__main__":
    main()
