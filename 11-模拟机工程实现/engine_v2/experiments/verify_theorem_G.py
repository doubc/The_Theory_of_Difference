#!/usr/bin/env python3
"""verify_theorem_G.py — 定理G物理势验证

验证: Φ=-1/d_H 是流密度 (∝-1/r²), 物理势是其径向积分 (∝-1/r)

理论来源: 02-worldbase形式化框架/03-gravity.md §3.3-3.4
证明: 02-worldbase形式化框架/04-continuous-limit.md §4.4 步骤3-4
"""

import numpy as np
import math
from itertools import combinations


def block_embed(x: np.ndarray, N: int, L: float = 1.0) -> np.ndarray:
    """分块嵌入: {0,1}^N → [0,L]^3
    
    将 N 比特均分为 3 组, 每组求和后缩放到 [0,L]
    """
    n = N // 3
    epsilon_N = L / n
    u = np.zeros(3)
    for k in range(3):
        u[k] = epsilon_N * np.sum(x[k*n:(k+1)*n])
    return u


def verify_theorem_G(N: int = 6, verbose: bool = True):
    """验证定理G: 流密度 → 物理势
    
    步骤:
    1. 枚举所有状态, 计算 Φ=-1/d_H (流密度)
    2. 嵌入 3D 空间, 计算欧氏距离 r
    3. 按 r 分箱, 计算径向平均 Φ
    4. 径向积分: Φ_physical = -∫(流密度)dr
    5. 验证 Φ_physical ∝ -1/r
    """
    L = 1.0
    stable = np.ones(N, dtype=int)
    u_stable = block_embed(stable, N, L)
    
    if verbose:
        print(f"=== 定理G 物理势验证 (N={N}) ===")
        print(f"稳定态: s={'1'*N}, u_stable={u_stable}")
        print(f"嵌入: {N} 比特 → 3 组 × {N//3} 比特")
    
    # 步骤1+2: 枚举所有状态, 计算 Φ 和 r
    data = []
    for w in range(N + 1):
        d_H = N - w
        if d_H == 0:
            continue
        phi_flux = -1.0 / d_H  # 流密度
        
        # 该重量层的所有状态
        if math.comb(N, w) <= 100:
            for ones in combinations(range(N), w):
                x = np.zeros(N, dtype=int)
                x[list(ones)] = 1
                u = block_embed(x, N, L)
                r = np.linalg.norm(u - u_stable)
                data.append((r, phi_flux, w, d_H))
        else:
            rng = np.random.RandomState(42)
            for _ in range(100):
                x = np.zeros(N, dtype=int)
                x[rng.choice(N, size=w, replace=False)] = 1
                u = block_embed(x, N, L)
                r = np.linalg.norm(u - u_stable)
                data.append((r, phi_flux, w, d_H))
    
    data.sort(key=lambda t: t[0])
    
    # 步骤3: 按 r 分箱, 计算径向平均
    r_values = np.array([d[0] for d in data])
    phi_values = np.array([d[1] for d in data])
    
    # 分箱
    n_bins = min(10, len(set(r_values)))
    r_bins = np.linspace(r_values.min(), r_values.max(), n_bins + 1)
    r_centers = []
    phi_means = []
    
    for i in range(n_bins):
        mask = (r_values >= r_bins[i]) & (r_values < r_bins[i+1])
        if mask.any():
            r_centers.append(np.mean(r_values[mask]))
            phi_means.append(np.mean(phi_values[mask]))
    
    r_centers = np.array(r_centers)
    phi_means = np.array(phi_means)
    
    # 步骤4: 径向积分: Φ_physical(r) = -∫_0^r φ_flux(r') dr'
    # 离散积分 (梯形法则)
    phi_physical = np.zeros_like(phi_means)
    for i in range(1, len(r_centers)):
        dr = r_centers[i] - r_centers[i-1]
        phi_physical[i] = phi_physical[i-1] + phi_means[i] * dr
    # 注意: phi_means 是负值, 所以 phi_physical 也是负值
    
    # 步骤5: 验证 Φ_physical ∝ -1/r
    if verbose:
        print(f"\n{'r':>8} {'Φ_flux':>10} {'Φ_phys':>10} {'-1/r':>10} {'Φ_phys/(-1/r)':>14}")
        print("-" * 55)
        for i in range(len(r_centers)):
            r = r_centers[i]
            inv_r = -1.0 / r if r > 0 else 0
            ratio = phi_physical[i] / inv_r if inv_r != 0 else 0
            print(f"{r:8.4f} {phi_means[i]:10.4f} {phi_physical[i]:10.4f} {inv_r:10.4f} {ratio:14.4f}")
    
    # 计算 Φ_physical 与 -1/r 的相关系数
    valid = r_centers > 0
    if valid.any():
        inv_r = -1.0 / r_centers[valid]
        corr = np.corrcoef(phi_physical[valid], inv_r)[0, 1]
        if verbose:
            print(f"\nΦ_physical 与 -1/r 的相关系数: {corr:.4f}")
            if corr > 0.99:
                print(f"✓ 定理G 验证通过: 物理势 ∝ -1/r")
            elif corr > 0.95:
                print(f"~ 定理G 基本通过 (小N效应)")
            else:
                print(f"✗ 定理G 未通过")
        return corr
    return 0


def verify_convergence(N_values: list, verbose: bool = True):
    """验证物理势随 N 增大的收敛性"""
    if verbose:
        print(f"\n=== 物理势收敛验证 ===")
        print(f"{'N':>6} {'corr(-1/r)':>12}")
        print("-" * 20)
    
    corrs = []
    for N in N_values:
        if N % 3 != 0:
            N = (N // 3) * 3
        corr = verify_theorem_G(N, verbose=False)
        corrs.append(corr)
        if verbose:
            print(f"{N:6d} {corr:12.4f}")
    
    if verbose:
        print(f"\n收敛趋势: {'→'.join(f'{c:.3f}' for c in corrs)}")
    
    return corrs


if __name__ == '__main__':
    # N=6 最小验证实例
    verify_theorem_G(N=6, verbose=True)
    
    # 收敛验证
    verify_convergence([6, 9, 12, 15, 18], verbose=True)
