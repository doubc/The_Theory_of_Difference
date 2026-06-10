"""exp_190_phase20_p0_baseline.py — Phase 20 P0: 多世界独立演化基线。

验证: 在 MultiWorld 框架下，各世界独立演化行为 ≈ 单世界基线。

假设 H20-P0: 4/4 世界的涌现深度分布 ≈ 单世界基线 (depth ~4.6, L2 涌现率 ~95%)

运行: python exp_190_phase20_p0_baseline.py
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path

import numpy as np

# 将 diffsim 加入路径
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from diffsim.world import RecursiveWorld, Params


def run_single_world(N0=48, seed=0, max_layers=6, verbose=False):
    """运行单个世界，返回 report。"""
    w = RecursiveWorld(N0=N0, seed=seed, params=Params(), self_encapsulate=True)
    w.run(max_layers=max_layers, verbose=verbose)
    return w.report, w.emergence_depth()


def run_multi_world_baseline(n_worlds=4, N0=48, base_seed=42,
                              max_layers=6, n_seeds=8, verbose=False):
    """多世界基线: 零耦合，各世界独立。"""
    all_results = []

    for seed_offset in range(n_seeds):
        seed = base_seed + seed_offset * n_worlds
        rng = np.random.default_rng(seed)
        seeds = rng.integers(0, 999999, size=n_worlds).tolist()

        world_results = []
        for i, s in enumerate(seeds):
            report, depth = run_single_world(N0=N0, seed=int(s),
                                              max_layers=max_layers, verbose=False)
            rec = {
                "seed_group": seed_offset,
                "world_id": i,
                "seed": int(s),
                "depth": depth,
                "report": report,
                "L2_emerged": any(r["layer"] >= 2 and r["sealed"] for r in report),
                "mean_flux": np.mean([r.get("autonomous_flux", 0.0) for r in report]) if report else 0.0,
            }
            world_results.append(rec)

        all_results.extend(world_results)

        if verbose:
            depths = [wr["depth"] for wr in world_results]
            l2_rate = sum(wr["L2_emerged"] for wr in world_results) / n_worlds
            print(f"  seed_group {seed_offset}: depths={depths}, L2_rate={l2_rate:.2f}")

    return all_results


def analyze_results(results, n_worlds=4):
    """分析多世界基线结果，对比单世界基线。"""
    depths = [r["depth"] for r in results]
    l2_emerged = [r["L2_emerged"] for r in results]
    fluxes = [r["mean_flux"] for r in results]

    # 单世界基线 (来自 Phase 17 验证实验)
    BASELINE = {"mean_depth": 4.65, "L2_rate": 0.95, "mean_flux": 0.2123}

    # H20-P0 评估
    mean_depth = float(np.mean(depths))
    std_depth = float(np.std(depths))
    l2_rate = sum(l2_emerged) / len(l2_emerged)
    mean_flux = float(np.mean([f for f in fluxes if f > 0]))

    # 偏差 < 20% → PASS
    depth_ok = abs(mean_depth - BASELINE["mean_depth"]) / BASELINE["mean_depth"] < 0.20
    l2_ok = l2_rate >= BASELINE["L2_rate"] * 0.80  # 允许 80% 以上
    flux_ok = mean_flux > 0.0  # 只要 > 0 即说明非死秩序

    h20_p0_pass = depth_ok and l2_ok and flux_ok

    analysis = {
        "n_worlds_total": len(results),
        "baseline": BASELINE,
        "multi_world": {
            "mean_depth": round(mean_depth, 2),
            "std_depth": round(std_depth, 2),
            "L2_emergence_rate": round(l2_rate, 4),
            "mean_flux_nonzero": round(mean_flux, 4) if mean_flux > 0 else 0.0,
        },
        "deviation": {
            "depth_rel_error": round(abs(mean_depth - BASELINE["mean_depth"]) / BASELINE["mean_depth"], 4),
            "L2_rate_diff": round(l2_rate - BASELINE["L2_rate"], 4),
        },
        "H20-P0": "PASS ✅" if h20_p0_pass else "FAIL ❌",
        "pass_criteria": {
            "depth_within_20pct": depth_ok,
            "L2_rate_above_80pct": l2_ok,
            "nonzero_flux": flux_ok,
        },
    }
    return analysis


def main():
    print("=" * 60)
    print("Phase 20 P0: Multi-World Baseline (exp_190)")
    print("=" * 60)

    t0 = time.time()
    n_worlds = 4
    n_seeds = 8
    N0 = 48

    print(f"\nConfig: n_worlds={n_worlds}, N0={N0}, n_seeds={n_seeds}")
    print(f"Total worlds: {n_worlds * n_seeds}")
    print("-" * 40)

    results = run_multi_world_baseline(
        n_worlds=n_worlds, N0=N0, base_seed=42,
        max_layers=6, n_seeds=n_seeds, verbose=True
    )

    elapsed = time.time() - t0
    print(f"\nCompleted in {elapsed:.1f}s")
    print("-" * 40)

    analysis = analyze_results(results, n_worlds=n_worlds)
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    for k, v in analysis.items():
        if isinstance(v, dict):
            print(f"\n  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")

    # 保存结果
    out = {
        "config": {"n_worlds": n_worlds, "N0": N0, "n_seeds": n_seeds},
        "results": results,
        "analysis": analysis,
        "elapsed_seconds": round(elapsed, 1),
    }
    out_path = ROOT / "results" / f"exp_190_p0_baseline_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved: {out_path}")

    return analysis


if __name__ == "__main__":
    main()
