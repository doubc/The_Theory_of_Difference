#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_182 — Phase 18 P0: 单层压缩率测量 (Single-Layer Compression Ratio)

目的: 测量 N → k → N' 的精确映射关系, 建立 k(N) 查找表。

方法:
  对每个 N ∈ [12, 18, 24, 30, 36, 48, 60, 72, 96]:
    运行 16 seeds 的孤立 Layer(N)
    记录: k(N) = 密封后组织数
          residual(N) = 活跃未冻结位
          N_next(N) = 2*k(N) + min(residual(N), max_residual)
          seal_step = 密封步数

假设 H18-P0: k(N) 在 N 较小时相对于 N 增长更快(超线性),
            即 r(N) = k(N)/N 不是常数。

Phase 18 设计: docs/phase18_design_emergence_depth_limit.md
"""
import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')  # Windows GBK fix
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from diffsim import RecursiveWorld
from diffsim.core import DifferenceField
from diffsim.world import Layer, Params
from diffsim import mechanisms as M
from diffsim.metrics import jaccard_flux


def measure_k_single(N, seed=0, params=None, verbose=False):
    """运行 N 位场的孤立密封, 返回 k, residual, seal_step, flux."""
    rng = np.random.default_rng(seed)
    p = params or Params()
    n_active = min(N, max(6, N // 2))
    active0 = rng.choice(N, size=n_active, replace=False).tolist()
    color0 = rng.integers(0, 6, size=N)
    field = DifferenceField(
        N=N, active=active0, a1_source=set(active0),
        direction=np.zeros(N, dtype=np.int8), color=color0,
        layer=0, rng=rng,
    )
    layer = Layer(field, p)
    sealed = layer.run_until_seal(verbose=verbose)

    k = len([o for o in field.organizations.values()
             if len(o) >= p.min_org_size])
    residual = sorted(field.active_set() - field.sealed_bits)
    n_res = min(len(residual), p.max_residual)
    n_next = 2 * k + n_res
    flux = layer.autonomous_flux()

    return {
        "N": N, "seed": seed, "sealed": sealed,
        "seal_step": field.seal_step if sealed else None,
        "k": k, "residual": n_res, "n_next": n_next,
        "flux": round(flux, 4),
        "r_ratio": round(k / N, 4) if N > 0 else 0,
    }


def sweep_N(N_values=None, seeds_per_N=16, params=None, verbose=False):
    """扫描多个 N 值, 每点 seeds_per_N 次运行."""
    if N_values is None:
        N_values = [12, 18, 24, 30, 36, 48, 60, 72, 96]
    results = []
    total = len(N_values) * seeds_per_N
    done = 0
    t0 = time.time()
    for N in N_values:
        for s in range(seeds_per_N):
            rec = measure_k_single(N, seed=s, params=params, verbose=verbose)
            results.append(rec)
            done += 1
            if done % 16 == 0 or done == total:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                print(f"  [{done}/{total}] N={N} seed={s} "
                      f"k={rec['k']} seal={rec['seal_step']} "
                      f"flux={rec['flux']} ({rate:.1f} runs/s)")
    return results


def analyze(results, N_values):
    """分析 k(N) 映射并计算预测深度."""
    print("\n" + "=" * 70)
    print("exp_182 — P0 单层压缩率测量: 结果汇总")
    print("=" * 70)
    print(f"  {'N':>5} | {'seal%':>6} | {'mean k':>7} | {'max k':>6} | "
          f"{'mean r':>7} | {'mean N_next':>10} | {'pred depth':>10}")
    print("-" * 65)

    for N in N_values:
        recs = [r for r in results if r["N"] == N]
        seal_rate = 100 * np.mean([r["sealed"] for r in recs])
        k_vals = [r["k"] for r in recs]
        n_next_vals = [r["n_next"] for r in recs]
        r_vals = [r["r_ratio"] for r in recs]
        mean_k = np.mean(k_vals)
        max_k = np.max(k_vals)
        mean_r = np.mean(r_vals)
        mean_nn = np.mean(n_next_vals)

        # 预测涌现深度: 从 N 开始迭代 n_next
        depth = 0
        n_curr = N
        while n_curr >= 6:
            # 用当前 N 的 mean_n_next 作为下一层大小
            # 如果 n_curr 不在 N_values 中, 插值
            if n_curr in N_values:
                nn = np.mean([r["n_next"] for r in results if r["N"] == n_curr])
            else:
                # 近似: 用最接近的 N 的压缩率
                nearest = min(N_values, key=lambda x: abs(x - n_curr))
                ratio = np.mean([r["r_ratio"] for r in results if r["N"] == nearest])
                nn = 2 * max(1, int(ratio * n_curr)) + 3
            if nn < 6 or nn >= n_curr:
                break
            n_curr = nn
            depth += 1

        print(f"  {N:>5} | {seal_rate:>5.0f}% | {mean_k:>7.2f} | {max_k:>6} | "
              f"{mean_r:>7.4f} | {mean_nn:>10.1f} | {depth:>10}")

    # 检查 H18-P0: r(N) 是否随 N 减小而增加
    print("\n--- H18-P0 检验: r(N) 是否随 N 增大而递减(超线性)? ---")
    r_by_N = []
    for N in N_values:
        recs = [r for r in results if r["N"] == N and r["sealed"]]
        r = np.mean([r["r_ratio"] for r in recs])
        r_by_N.append((N, r))
    decreasing = all(r_by_N[i][1] > r_by_N[i+1][1] * 0.95
                     for i in range(len(r_by_N) - 1)) if len(r_by_N) > 1 else False
    print(f"  超线性趋势(小N r更大): {'CONFIRMED' if decreasing else 'PARTIAL'}")
    for N, r in r_by_N:
        print(f"    N={N:>3}: r={r:.4f}")
    print(f"  结论: r(N) 的变化趋势决定了深度极限的数学结构。")


def main():
    print("=" * 70)
    print("exp_182 — Phase 18 P0: 单层压缩率测量")
    print("=" * 70)
    t0 = time.time()

    N_values = [12, 18, 24, 30, 36, 48, 60, 72, 96]
    seeds_per_N = 16

    print(f"\n运行: {len(N_values)} N 值 × {seeds_per_N} seeds = "
          f"{len(N_values) * seeds_per_N} runs\n")

    p = Params()
    results = sweep_N(N_values, seeds_per_N, params=p)
    analyze(results, N_values)

    # 保存结果
    os.makedirs("results", exist_ok=True)
    out_path = f"results/exp_182_p0_compression_{time.strftime('%Y%m%d_%H%M')}.json"
    with open(out_path, "w") as f:
        json.dump({
            "experiment": "exp_182_phase18_p0_compression_ratio",
            "params": {k: v for k, v in p.__dict__.items() if not k.startswith("_")},
            "N_values": N_values,
            "seeds_per_N": seeds_per_N,
            "results": results,
            "elapsed_seconds": round(time.time() - t0, 1),
        }, f, indent=2)
    print(f"\n结果已保存: {out_path}")
    print(f"总耗时: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()