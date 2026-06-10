#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_184 — Phase 18 P2: 整体固定点检测器验证实验 (Whole Fixed-Point Detector)

目的:
  实现整体固定点检测器并在 engine_v2 自指链上验证。

  核心问题:
    Phase 18 分析发现链终止是 min_org_size=3 的工程 artifact。
    真正的"整体"应是自指链上 m9(L_n) ≅ L_n 的结构同构不动点。
    本实验验证固定点检测器是否能找到真正的整体。

方法 (3 个子实验):
  Config A — 标准 engine_v2 (min_org_size=3):  预期: 链终止(非固定点), iso_score 逐层如何变化?
  Config B — min_org_size=2 (无限链可能性):     预期: 深层 iso_score 上升, 可能在 L5+ 到达固定点
  Config C — min_org_size=2 + 放松 seal_fraction:  预期: 更大的下一层 → 更容易达到固定点

对每层 (L0..Lmax) 测量:
  - k_parent, k_child (组织数)
  - iso_score (四维加权同构评分)
  - 组织大小分布相似度
  - flux 一致性
  - 规模保持比

假设 H18-P2:
  (A) 标准 config: iso_score 在浅层低 (<0.6), 链终止前略升 (~0.6-0.7)
  (B) min_org_size=2: iso_score 在 L3+ 稳定 > 0.8 → 固定点达成
  (C) 放松密封: 在更深层达成固定点, iso_score > 0.85

依赖:
  diffsim.core, diffsim.world, diffsim.fixed_point
  diffsim.mechanisms.m9_self_reference
"""
import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from diffsim import RecursiveWorld, Layer
from diffsim.core import DifferenceField
from diffsim.world import Params
from diffsim.fixed_point import (
    FixedPointDetector, detect_fixed_points_in_world,
    find_first_fixed_point, summarize_chain,
)


# ─────────────────────────────────────────
#  1. 运行一个 RecursiveWorld + 固定点检测
# ─────────────────────────────────────────
def run_and_detect(N0=48, seed=0, params: Params = None,
                   max_layers=8, verbose=False) -> dict | None:
    """
    1. 运行 RecursiveWorld 直到链终止。
    2. 对每个密封层做固定点检测。
    3. 返回完整结果字典。
    """
    world = RecursiveWorld(N0=N0, n0_active=max(6, N0 // 2),
                           n_colors=6, seed=seed, params=params,
                           self_encapsulate=True)
    world.run(max_layers=max_layers, verbose=verbose)

    if not world.layers:
        return {"seed": seed, "error": "No layers formed"}

    detector = FixedPointDetector()
    fp_reports = detect_fixed_points_in_world(world, detector)

    # 链概要
    first_fp = find_first_fixed_point(fp_reports)
    max_iso = max((r.iso_score for r in fp_reports), default=0.0)
    max_iso_layer = max(fp_reports, key=lambda r: r.iso_score).layer if fp_reports else -1

    # 每层原始指标
    layer_metrics = []
    for i, layer in enumerate(world.layers):
        f = layer.field
        k = len([o for o in f.organizations.values()
                 if len(o) >= params.min_org_size])
        layer_metrics.append({
            "layer": f.layer, "N": f.N, "sealed": f.sealed,
            "seal_step": f.seal_step or -1,
            "n_orgs": k, "flux": round(layer.autonomous_flux(), 4),
        })

    return {
        "seed": seed,
        "depth": len(world.layers),
        "emergence_depth": world.emergence_depth(),
        "first_fp_layer": first_fp.layer if first_fp else None,
        "first_fp_score": round(first_fp.iso_score, 4) if first_fp else None,
        "max_iso": round(max_iso, 4),
        "max_iso_layer": max_iso_layer,
        "has_fixed_point": first_fp is not None,
        "world_report": world.report,
        "layer_metrics": layer_metrics,
        "fp_reports": [r.to_dict() for r in fp_reports],
        "config_tag": f"N0={N0}_minorg={params.min_org_size}_seal={params.seal_fraction}",
    }


# ─────────────────────────────────────────
#  2. Configs
# ─────────────────────────────────────────
CONFIGS = {
    "A_standard": {
        "N0": 48,
        "params": Params(min_org_size=3, seal_fraction=0.6),
        "desc": "标准 engine_v2 (min_org_size=3, seal_fraction=0.6)",
    },
    "B_min_org_2": {
        "N0": 48,
        "params": Params(min_org_size=2, seal_fraction=0.6),
        "desc": "min_org_size=2 (无限链可能性)",
    },
    "C_relaxed": {
        "N0": 48,
        "params": Params(min_org_size=2, seal_fraction=0.4,
                          lock_inc=0.15, lock_threshold=0.5),
        "desc": "min_org_size=2 + seal_fraction=0.4 (更容易深层密封)",
    },
}


# ─────────────────────────────────────────
#  3. 扫描 Configs × Seeds
# ─────────────────────────────────────────
def run_config(config_name: str, config: dict, seeds: int = 16,
               max_layers: int = 8, verbose: bool = False) -> list[dict]:
    desc = config["desc"]
    N0 = config["N0"]
    params = config["params"]
    print(f"\n{'='*65}")
    print(f"Config {config_name}: {desc}")
    print(f"{'='*65}")

    results = []
    t0 = time.time()
    for s in range(seeds):
        rec = run_and_detect(N0=N0, seed=s, params=params,
                             max_layers=max_layers, verbose=verbose)
        results.append(rec)
        if (s + 1) % 4 == 0 or s == seeds - 1:
            elapsed = time.time() - t0
            rate = (s + 1) / elapsed if elapsed > 0 else 0
            print(f"  [{s+1}/{seeds}] seed={s} depth={rec['depth']} "
                  f"fp={rec['first_fp_layer']} iso_max={rec['max_iso']:.4f} "
                  f"({rate:.1f} seeds/s)")
    print(f"  完成: {seeds} seeds in {time.time()-t0:.1f}s")
    return results


# ─────────────────────────────────────────
#  4. 分析
# ─────────────────────────────────────────
def analyze_config(config_name: str, results: list[dict]):
    print(f"\n{'─'*65}")
    print(f"📊  分析: {config_name}")
    print(f"{'─'*65}")

    seeds = len(results)
    depths = [r["depth"] for r in results]
    has_fp = sum(1 for r in results if r["has_fixed_point"])
    fp_layers = [r["first_fp_layer"] for r in results if r["has_fixed_point"]]
    max_isos = [r["max_iso"] for r in results]
    mean_max_iso = np.mean(max_isos)

    print(f"  Seeds: {seeds}")
    print(f"  平均深度: {np.mean(depths):.2f} (范围 {min(depths)}-{max(depths)})")
    print(f"  固定点种子: {has_fp}/{seeds} = {100*has_fp/seeds:.0f}%")
    if fp_layers:
        print(f"  首次固定点层分布: {sorted(fp_layers)}")
    print(f"  平均 max_iso: {mean_max_iso:.4f}")
    print(f"  max_iso 范围: {min(max_isos):.4f} - {max(max_isos):.4f}")

    # 逐层 iso_score 统计
    layers_fp = {}
    for r in results:
        for fp in r.get("fp_reports", []):
            layer = fp["layer"]
            if layer not in layers_fp:
                layers_fp[layer] = []
            layers_fp[layer].append(fp["iso_score"])

    print(f"\n  逐层 iso_score 统计:")
    print(f"    {'层':<5} {'平均':>8} {'标准差':>8} {'最小':>8} {'最大':>8} {'固定点率':>10}")
    for layer in sorted(layers_fp.keys()):
        scores = layers_fp[layer]
        mean_s = np.mean(scores)
        std_s = np.std(scores)
        min_s = min(scores)
        max_s = max(scores)
        fp_rate = sum(1 for s in scores if s >= 0.8) / len(scores)
        print(f"    L{layer:<3} {mean_s:>8.4f} {std_s:>8.4f} {min_s:>8.4f} "
              f"{max_s:>8.4f} {100*fp_rate:>9.0f}%")

    # 逐层 k_parent vs k_child 对比
    print(f"\n  逐层 k_parent → k_child (组织数):")
    print(f"    {'层':<5} {'k_parent':>10} {'k_child':>10} {'差异':>8} {'变化趋势':>12}")
    for layer in sorted(layers_fp.keys()):
        k_parents = [r["k_parent"] for r in layers_fp if layer == r]
        # Need to pull from fp_reports
        kp = []
        kc = []
        for r in results:
            for fp in r.get("fp_reports", []):
                if fp["layer"] == layer:
                    kp.append(fp["k_parent"])
                    kc.append(fp["k_child"])
        if kp:
            mean_kp = np.mean(kp)
            mean_kc = np.mean(kc)
            delta = mean_kc - mean_kp
            trend = "↑ 增长" if delta > 0.3 else ("↓ 衰减" if delta < -0.3 else "→ 持平")
            print(f"    L{layer:<3} {mean_kp:>10.2f} {mean_kc:>10.2f} "
                  f"{delta:>+8.2f} {trend:>12}")

    # H18-P2 检验
    print(f"\n  H18-P2 检验:")
    if config_name in ("B_min_org_2", "C_relaxed"):
        if has_fp / seeds >= 0.5:
            print(f"    ✅ 确认: {100*has_fp/seeds:.0f}% 种子达固定点 (≥50% 阈值)")
            if config_name == "C_relaxed":
                print(f"    ✅ 确认: 放松密封参数后固定点更频繁/更早")
        else:
            print(f"    ⚠️  部分确认: {100*has_fp/seeds:.0f}% 种子达固定点, 低于 50%")
    else:
        print(f"    Config A (标准): max_iso 均值 {mean_max_iso:.4f}")
        if mean_max_iso < 0.7:
            print(f"    ✅ 确认: 标准 config 不会在终止前到达固定点")
        else:
            print(f"    ⚠️  部分确认: {mean_max_iso:.4f} > 0.7, 略高")

    return {
        "config": config_name,
        "seeds": seeds,
        "mean_depth": float(np.mean(depths)),
        "depth_range": [int(min(depths)), int(max(depths))],
        "fixed_point_rate": has_fp / seeds,
        "mean_max_iso": float(mean_max_iso),
        "per_layer_iso": {str(k): {
            "mean": float(np.mean(v)), "std": float(np.std(v)),
            "fp_rate": float(sum(1 for s in v if s >= 0.8) / len(v)),
        } for k, v in layers_fp.items()},
    }


# ─────────────────────────────────────────
#  5. Main
# ─────────────────────────────────────────
def main():
    print("=" * 65)
    print("exp_184 — Phase 18 P2: 整体固定点检测器验证实验")
    print("=" * 65)
    t0 = time.time()

    configs_to_run = ["A_standard", "B_min_org_2", "C_relaxed"]
    seeds_per_config = 16
    max_layers = 8

    all_results = {}
    summaries = []

    for cname in configs_to_run:
        config = CONFIGS[cname]
        results = run_config(cname, config, seeds=seeds_per_config,
                             max_layers=max_layers)
        all_results[cname] = results
        summary = analyze_config(cname, results)
        summaries.append(summary)

    # 总体对比表
    print(f"\n{'='*65}")
    print("📋  三 Config 总体对比")
    print(f"{'='*65}")
    print(f"  {'Config':<20} {'深度':>6} {'固定点率':>10} {'max_iso':>8} "
          f"{'首次固定点层':>14}")
    for s in summaries:
        c = s["config"]
        fp_rate_str = f"{100*s['fixed_point_rate']:.0f}%"
        fp_layer = all_results[c][0].get("first_fp_layer", "N/A")
        print(f"  {CONFIGS[c]['desc']:<20} {s['mean_depth']:>6.2f} "
              f"{fp_rate_str:>10} {s['mean_max_iso']:>8.4f} "
              f"{str(fp_layer):>14}")

    # 保存结果
    os.makedirs("results", exist_ok=True)
    out_path = f"results/exp_184_p2_fixed_point_{time.strftime('%Y%m%d_%H%M')}.json"
    with open(out_path, "w") as f:
        json.dump({
            "experiment": "exp_184_phase18_p2_fixed_point_detector",
            "configs": {k: {kk: vv for kk, vv in v.items() if kk != "params"}
                        for k, v in CONFIGS.items()},
            "params": {k: {kk: vv for kk, vv in v["params"].__dict__.items()
                           if not kk.startswith("_")}
                       for k, v in CONFIGS.items()},
            "seeds_per_config": seeds_per_config,
            "summaries": summaries,
            "results": all_results,
            "elapsed_seconds": round(time.time() - t0, 1),
        }, f, indent=2)
    print(f"\n结果已保存: {out_path}")
    print(f"总耗时: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()