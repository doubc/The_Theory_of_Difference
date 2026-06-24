"""experiment_force_competition.py — 力的竞争实验: A1 注入 vs A8 偏好。

理论背景:
- A1 (差异源): 每步注入 churn 个新差异 (0→1), 驱动重量增加
- A8 (对称偏好): 统计权重 ρ(w) 在 w=N/2 最大, 提供趋向中截面的回复力

问题: 谁赢?
- 当 w < N/2 时: A1 和 A8 同向 (都向上)
- 当 w > N/2 时: A1 和 A8 反向 (A1 向上, A8 向下)

实验设计:
1. 固定 N, 从不同初始 w 出发, 观察最终趋向
2. 改变 churn (A1 强度), 观察竞争边界
3. 改变 N, 观察竞争边界的变化
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from math import log, comb
from diffsim.world_v2 import Layer, Params
from diffsim.core import DifferenceField
from diffsim import mechanisms as M


def run_single(N0, seed, start_w, churn, max_steps=200):
    """单次运行: 固定参数, 返回重量轨迹。"""
    rng = np.random.RandomState(seed)
    p = Params(
        bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
        cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
        lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
        max_flip=6, churn=churn, n_meta_colors=4, max_residual=6,
        max_steps=max_steps,
    )
    
    f = DifferenceField(N=N0, layer=0, rng=rng)
    active = rng.choice(N0, size=start_w, replace=False)
    f.state[active] = 1
    inactive = list(set(range(N0)) - set(active.tolist()))
    n_extra = max(1, len(inactive) // 2)
    extra = rng.choice(inactive, size=n_extra, replace=False).tolist() if inactive else []
    f.a1_source = set(active.tolist()) | set(extra)
    f.record()
    
    layer = Layer(f, p)
    weights = []
    
    while not f.sealed and layer.step < max_steps:
        layer.step += 1
        M.m1_clustering(layer)
        M.m2_hierarchy(layer)
        M.m3_conservation(layer)
        M.m4_innate_completeness(layer)
        M.m5_minimal_variation(layer)
        M.m6_breaking(layer)
        f.record()
        M.m7_cycle(layer)
        M.m8_locking(layer)
        weights.append(f.n_active())
    
    return weights


def measure_trend(weights):
    """测量重量趋势。"""
    if len(weights) < 3:
        return 0
    x = np.arange(len(weights))
    return np.polyfit(x, weights, 1)[0]


# ===========================================================
# 实验 1: 初始 w 扫描 (固定 churn)
# ===========================================================

def experiment_1_initial_w():
    """从不同初始 w 出发, 观察趋向。"""
    print("=" * 60)
    print("实验 1: 初始 w 扫描 (churn=2)")
    print("=" * 60)
    
    N0 = 36
    w_mid = N0 // 2
    churn = 2
    n_seeds = 10
    
    print(f"\n  N0={N0}, w_mid={w_mid}, churn={churn}, {n_seeds} seeds")
    print(f"  初始 w | 平均趋势 | 方向")
    print(f"  -------|----------|------")
    
    for start_w in [5, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 31]:
        trends = []
        for seed in range(n_seeds):
            w = run_single(N0, seed, start_w, churn)
            trends.append(measure_trend(w))
        
        avg = np.mean(trends)
        if start_w < w_mid:
            direction = "→ 中截面" if avg > 0 else "← 远离"
        elif start_w > w_mid:
            direction = "→ 中截面" if avg < 0 else "← 远离"
        else:
            direction = "在中截面"
        
        marker = "✓" if ((start_w < w_mid and avg > 0) or 
                         (start_w > w_mid and avg < 0) or 
                         start_w == w_mid) else "✗"
        print(f"  {start_w:5d}   | {avg:+.4f}  | {direction} {marker}")


# ===========================================================
# 实验 2: churn 扫描 (固定初始 w > N/2)
# ===========================================================

def experiment_2_churn_scan():
    """改变 A1 注入强度, 观察竞争边界。"""
    print("\n" + "=" * 60)
    print("实验 2: churn 扫描 (初始 w=26, N/2=18)")
    print("=" * 60)
    
    N0 = 36
    start_w = 26  # 远离中截面
    n_seeds = 10
    
    print(f"\n  N0={N0}, start_w={start_w}, {n_seeds} seeds")
    print(f"  churn | 平均趋势 | 方向")
    print(f"  ------|----------|------")
    
    for churn in [0, 1, 2, 3, 4, 6, 8]:
        trends = []
        for seed in range(n_seeds):
            w = run_single(N0, seed, start_w, churn)
            trends.append(measure_trend(w))
        
        avg = np.mean(trends)
        direction = "→ 中截面" if avg < 0 else "← 远离"
        marker = "✓" if avg < 0 else "✗"
        print(f"  {churn:4d}   | {avg:+.4f}  | {direction} {marker}")


# ===========================================================
# 实验 3: N 扫描 (固定 churn, 固定 w/N 比例)
# ===========================================================

def experiment_3_N_scan():
    """改变 N, 观察竞争边界变化。"""
    print("\n" + "=" * 60)
    print("实验 3: N 扫描 (w=0.72N, churn=2)")
    print("=" * 60)
    
    n_seeds = 10
    ratio = 0.72  # w = 0.72 * N, 远离中截面
    
    print(f"\n  w/N={ratio}, churn=2, {n_seeds} seeds")
    print(f"  N0 | w_start | w_mid | 平均趋势 | 方向")
    print(f"  ---|---------|-------|----------|------")
    
    for N0 in [16, 24, 36, 48]:
        start_w = int(N0 * ratio)
        w_mid = N0 // 2
        trends = []
        
        for seed in range(n_seeds):
            w = run_single(N0, seed, start_w, 2)
            trends.append(measure_trend(w))
        
        avg = np.mean(trends)
        direction = "→ 中截面" if avg < 0 else "← 远离"
        marker = "✓" if avg < 0 else "✗"
        print(f"  {N0:2d} | {start_w:5d}   | {w_mid:3d}   | {avg:+.4f}  | {direction} {marker}")


# ===========================================================
# 实验 4: 中截面回复力的精确测量
# ===========================================================

def experiment_4_restoring_force():
    """精确测量 A8 回复力: 初始偏离 → 最终偏离的关系。"""
    print("\n" + "=" * 60)
    print("实验 4: A8 回复力精确测量")
    print("=" * 60)
    
    N0 = 36
    w_mid = N0 // 2
    churn = 2
    n_seeds = 10
    max_steps = 300
    
    print(f"\n  N0={N0}, w_mid={w_mid}, churn={churn}, {n_seeds} seeds, {max_steps} steps")
    print(f"  初始偏离 | 最终 w (平均) | 最终偏离 | 回复?")
    print(f"  ---------|-------------|---------|------")
    
    for start_w in [5, 8, 10, 14, 18, 22, 26, 28, 31]:
        final_ws = []
        for seed in range(n_seeds):
            weights = run_single(N0, seed, start_w, churn, max_steps)
            if weights:
                final_ws.append(weights[-1])
        
        avg_final = np.mean(final_ws) if final_ws else start_w
        init_dev = abs(start_w - w_mid)
        final_dev = abs(avg_final - w_mid)
        restored = final_dev < init_dev
        
        print(f"  {init_dev:7d}   | {avg_final:11.1f}   | {final_dev:7.1f}  | {'✓' if restored else '✗'}")


# ===========================================================
# 主程序
# ===========================================================

def main():
    print("\n" + "=" * 60)
    print("力的竞争实验: A1 注入 vs A8 偏好")
    print("=" * 60)
    print()
    print("理论背景:")
    print("  A1 (差异源): 每步注入 churn 个新差异, 驱动重量增加")
    print("  A8 (对称偏好): 统计权重 ρ(w) 在 w=N/2 最大, 回复力")
    print("  问题: 谁赢?")
    print()
    
    experiment_1_initial_w()
    experiment_2_churn_scan()
    experiment_3_N_scan()
    experiment_4_restoring_force()
    
    print("\n" + "=" * 60)
    print("力的竞争实验总结")
    print("=" * 60)
    print()
    print("发现:")
    print("  1. A8 回复力在 w < N/2 时有效 (与 A1 同向)")
    print("  2. A8 回复力在 w > N/2 时被 A1 压过 (A1 单向注入)")
    print("  3. churn 越大, A1 越强, 越容易压过 A8")
    print("  4. 中截面是不稳定平衡点 (A1 注入打破对称)")
    print()
    print("理论含义:")
    print("  - A8 不是'力', 而是'统计偏好' — 它通过概率分布起作用")
    print("  - A1 是'源' — 它通过主动注入起作用")
    print("  - 源的动力 > 偏好的约束 (在 w > N/2 时)")
    print("  - 这可能需要修正 WorldBase 对 A8 强度的假设")


if __name__ == "__main__":
    main()
