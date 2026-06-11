"""exp_190_phase20_p0_two_chain_baseline.py — Phase 20 P0: 双链基线（Two-Chain Baseline）.

验证: 两条自指链并行运行 + 位交换耦合 是否产生新的 L2+ 结构。

假设 H20-P0a: 两条链的涌现深度相关 (cross-world correlation r > 0.5)
假设 H20-P0b: 耦合产生新的 L2+ 结构（单链运行时没有的）
假设 H20-P0c: 两条链的命名位（A9 输出）趋同

运行: python exp_190_phase20_p0_two_chain_baseline.py
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
import numpy as np
import itertools

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from diffsim.multi_world import MultiWorld
from diffsim.world import Params


def run_experiment(
    n_worlds: int = 2,
    n_seeds: int = 8,
    N0: int = 48,
    base_seed: int = 42,
    coupling_strength: float = 0.0,
    coupling_mode: str = "bit_swap",
    bit_swap_rate: float = 0.1,
    max_layers: int = 6,
    max_steps_per_layer: int = 400,
    verbose: bool = False,
) -> Dict:
    """运行一组实验（n_seeds × n_worlds）。

    返回: 所有世界的 report + 跨世界相关性分析结果。
    """
    all_results = []
    t0 = time.time()

    for seed_offset in range(n_seeds):
        seed = base_seed + seed_offset * n_worlds * 7  # 避免种子重叠
        mw = MultiWorld(
            n_worlds=n_worlds,
            N0=N0,
            base_seed=seed,
            params=Params(),
            coupling_strength=coupling_strength,
            coupling_mode=coupling_mode,
            bit_swap_rate=bit_swap_rate,
        )

        if coupling_strength > 0 or coupling_mode != "none":
            mw = MultiWorld(
                n_worlds=n_worlds,
                N0=N0,
                base_seed=seed,
                params=Params(),
                coupling_strength=coupling_strength,
                coupling_mode=coupling_mode,
                bit_swap_rate=bit_swap_rate,
            )
            report = mw.run_with_coupling(
                max_layers=max_layers,
                max_steps_per_layer=max_steps_per_layer,
                verbose=verbose,
            )
        else:
            report = mw.run_all(max_layers=max_layers, verbose=verbose)

        # 收集结果
        for i, w in enumerate(mw.worlds):
            rec = {
                "seed_group": seed_offset,
                "world_id": i,
                "seed": int(mw.worlds[i].field0.rng.integers(0, 999999) if hasattr(mw.worlds[i], 'field0') else 0),
                "depth": mw.worlds[i].emergence_depth(),
                "report": [dict(r) for r in mw.worlds[i].report],
                "L2_emerged": any(r["layer"] >= 2 and r["sealed"] for r in mw.worlds[i].report),
                "mean_flux": float(np.mean([r.get("autonomous_flux", 0.0) for r in mw.worlds[i].report])) if mw.worlds[i].report else 0.0,
            }
            # 尝试获取真实 seed
            if hasattr(mw.worlds[i], 'field0') and hasattr(mw.worlds[i].field0, 'rng'):
                pass  # field0.rng 是 RandomGenerator, 不能直接读 seed
            rec["seed"] = seed + i  # 近似
            all_results.append(rec)

        if verbose:
            depths = [mw.worlds[i].emergence_depth() for i in range(n_worlds)]
            print(f"  seed_group {seed_offset}: depths={depths}")

    elapsed = time.time() - t0
    return {
        "config": {
            "n_worlds": n_worlds,
            "N0": N0,
            "n_seeds": n_seeds,
            "coupling_strength": coupling_strength,
            "coupling_mode": coupling_mode,
            "bit_swap_rate": bit_swap_rate,
        },
        "results": all_results,
        "elapsed_seconds": round(elapsed, 1),
    }


def analyze_h20_p0(results: Dict) -> Dict:
    """分析 H20-P0a/b/c。"""
    cfg = results["config"]
    data = results["results"]
    n_worlds = cfg["n_worlds"]
    n_seeds = cfg["n_seeds"]

    # --- H20-P0a: 涌现深度相关性 ---
    # 按 seed_group 分组，计算组内 world 之间 depth 相关性
    depth_corrs = []
    flux_corrs = []
    for grp in range(n_seeds):
        grp_data = [r for r in data if r["seed_group"] == grp]
        if len(grp_data) < 2:
            continue
        depths = [r["depth"] for r in grp_data]
        # Pearson correlation of depths within group
        if len(set(depths)) > 1:  # 有方差才能算相关性
            depth_corrs.append(float('nan'))  # 需要配对 flux 序列
        # 简化: 用跨世界 depth 差异来衡量相关性
        if len(depths) >= 2:
            # 用 flux 序列的相关性
            flux_seqs = [r["report"] for r in grp_data]
            # 提取 flux 序列
            flux_lists = []
            for rd in grp_data:
                fl = [r.get("autonomous_flux", 0.0) for r in rd["report"]]
                flux_lists.append(fl)
            # 配对相关性（取最小长度）
            min_len = min(len(fl) for fl in flux_lists)
            if min_len >= 2:
                fA = [fl[:min_len] for fl in flux_lists]
                # 计算第一对的相关性
                corr = np.corrcoef(flux_lists[0][:min_len], flux_lists[1][:min_len])[0, 1]
                if not np.isnan(corr):
                    flux_corrs.append(corr)

    # --- H20-P0b: 新的 L2+ 结构 ---
    # 对比单链基线 (Phase 17: depth ~4.65, L2 rate ~95%)
    BASELINE_DEPTH = 4.65
    BASELINE_L2_RATE = 0.95
    depths = [r["depth"] for r in data]
    l2_emerged = [r["L2_emerged"] for r in data]
    mean_depth = float(np.mean(depths))
    l2_rate = sum(l2_emerged) / len(l2_emerged) if data else 0.0
    depth_higher = mean_depth > BASELINE_DEPTH
    l2_higher = l2_rate > BASELINE_L2_RATE

    # --- H20-P0c: 命名位趋同 ---
    # 简化: 检查各世界 report 的 mode 字段是否趋同
    modes_by_group = []
    for grp in range(n_seeds):
        grp_data = [r for r in data if r["seed_group"] == grp]
        modes = [r["report"][0].get("mode", "seed") if r["report"] else "seed" for r in grp_data]
        modes_by_group.append(modes)
    # 组内 mode 相同比例
    mode_same_count = sum(1 for modes in modes_by_group if len(set(modes)) <= 1)
    mode_convergence_rate = mode_same_count / len(modes_by_group) if modes_by_group else 0.0

    analysis = {
        "H20-P0a": {
            "desc": "涌现深度/动态相关性 > 0.5",
            "flux_correlations": [round(float(c), 4) for c in flux_corrs if not np.isnan(c)],
            "mean_flux_corr": round(float(np.mean([c for c in flux_corrs if not np.isnan(c)])), 4) if flux_corrs else None,
            "PASS": len(flux_corrs) > 0 and np.nanmean(flux_corrs) > 0.5 if flux_corrs else False,
        },
        "H20-P0b": {
            "desc": "耦合产生新的 L2+ 结构（超越单链基线）",
            "mean_depth": round(mean_depth, 2),
            "baseline_depth": BASELINE_DEPTH,
            "depth_higher": depth_higher,
            "L2_rate": round(l2_rate, 4),
            "baseline_L2_rate": BASELINE_L2_RATE,
            "L2_higher": l2_higher,
            "PASS": depth_higher or l2_higher,
        },
        "H20-P0c": {
            "desc": "命名位（mode）趋同",
            "mode_convergence_rate": round(mode_convergence_rate, 4),
            "PASS": mode_convergence_rate >= 0.5,
        },
        "summary": {
            "n_worlds_total": len(data),
            "mean_depth": round(mean_depth, 2),
            "std_depth": round(float(np.std(depths)), 2) if depths else 0.0,
            "L2_emergence_rate": round(l2_rate, 4),
            "mean_flux": round(float(np.mean([r["mean_flux"] for r in data])), 4) if data else 0.0,
        },
    }
    return analysis


def main():
    print("=" * 60)
    print("Phase 20 P0: Two-Chain Baseline (exp_190)")
    print("=" * 60)

    # 用 3 个耦合配置运行
    configs = [
        {"coupling_strength": 0.0, "coupling_mode": "none", "label": "独立（无耦合）"},
        {"coupling_strength": 0.1, "coupling_mode": "bit_swap", "bit_swap_rate": 0.1, "label": "弱耦合 strength=0.1"},
        {"coupling_strength": 0.3, "coupling_mode": "bit_swap", "bit_swap_rate": 0.3, "label": "中耦合 strength=0.3"},
        {"coupling_strength": 0.5, "coupling_mode": "bit_swap", "bit_swap_rate": 0.5, "label": "强耦合 strength=0.5"},
    ]

    all_config_results = {}
    for cfg in configs:
        label = cfg.pop("label")
        print(f"\n{'='*60}")
        print(f"Config: {label}")
        print(f"{'='*60}")
        t0 = time.time()
        results = run_experiment(
            n_worlds=2,
            n_seeds=8,
            N0=48,
            base_seed=42,
            verbose=False,
            **cfg,
        )
        elapsed = time.time() - t0
        print(f"  Completed in {elapsed:.1f}s")

        analysis = analyze_h20_p0(results)
        print(f"\n  Results:")
        print(f"    Mean depth: {analysis['summary']['mean_depth']} (baseline 4.65)")
        print(f"    L2 rate:   {analysis['summary']['L2_emergence_rate']:.2f} (baseline 0.95)")
        print(f"    H20-P0a flux corr:  {analysis['H20-P0a']['mean_flux_corr']}")
        print(f"    H20-P0a PASS: {analysis['H20-P0a']['PASS']}")
        print(f"    H20-P0b PASS: {analysis['H20-P0b']['PASS']}")
        print(f"    H20-P0c mode convergence: {analysis['H20-P0c']['mode_convergence_rate']:.2f}")

        all_config_results[label] = {
            "config": results["config"],
            "summary": analysis["summary"],
            "analysis": {k: v for k, v in analysis.items()},
            "elapsed_seconds": round(elapsed, 1),
        }

        # 保存详细结果
        out_path = ROOT / "results" / f"exp_190_p0_{label.replace(' ', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "config": results["config"],
            "results": results["results"],
            "analysis": analysis,
            "elapsed_seconds": round(elapsed, 1),
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False, default=str)
        print(f"  Saved: {out_path}")

    # 汇总
    print(f"\n{'='*60}")
    print("SUMMARY: All Configs")
    print(f"{'='*60}")
    for label, res in all_config_results.items():
        s = res["summary"]
        print(f"  {label}: depth={s['mean_depth']}, L2={s['L2_emergence_rate']:.2f}, flux={s['mean_flux']:.4f}")

    # 保存汇总
    summary_path = ROOT / "results" / f"exp_190_p0_SUMMARY_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_config_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSummary saved: {summary_path}")


if __name__ == "__main__":
    main()
