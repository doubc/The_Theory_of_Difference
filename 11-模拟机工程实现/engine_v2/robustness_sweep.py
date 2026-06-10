#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""robustness_sweep.py — engine_v2 参数鲁棒性扫描。

测试自指闭环(修复版)在不同参数下的表现:
1. N0 扫描: 24, 36, 48, 72, 96
2. bind_threshold 扫描: 0.5, 1.0, 2.0
3. seal_fraction 扫描: 0.4, 0.6, 0.8

每个配置运行 8 seeds，测量:
- 涌现深度 (emergence_depth)
- L1 自主 Jaccard flux
- L2 涌现率
- 平均密封步数
"""
import argparse
import numpy as np
import sys
import os
import json

# 添加父目录到路径以便导入 diffsim
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diffsim import RecursiveWorld
from diffsim.world import Params
from diffsim.metrics import jaccard_flux


def run_sweep(N0_list, bind_thresholds, seal_fractions, n_seeds=8, n_colors=6):
    """运行参数扫描，返回结果字典"""
    results = {}
    
    for N0 in N0_list:
        for bt in bind_thresholds:
            for sf in seal_fractions:
                config_key = f"N0={N0}_bind={bt}_seal={sf}"
                depths, fluxes_l1, seal_steps = [], [], []
                l2_emergence = []
                
                for seed in range(n_seeds):
                    try:
                        params = Params(bind_threshold=bt, seal_fraction=sf)
                        w = RecursiveWorld(
                            seed=seed,
                            self_encapsulate=True,
                            N0=N0,
                            n0_active=max(20, N0 - 8),  # 自动调整活跃比特数
                            n_colors=n_colors,
                            params=params
                        )
                        rep = w.run(max_layers=6)
                        
                        # 提取指标
                        depth = w.emergence_depth()
                        depths.append(depth)
                        
                        l1 = [r for r in rep if r["layer"] == 1]
                        flux = l1[0]["autonomous_flux"] if l1 else 0.0
                        fluxes_l1.append(flux)
                        
                        # L2 涌现 = depth >= 3
                        l2_emergence.append(depth >= 3)
                        
                        # 密封步数 (从 report 提取 L0 seal_step)
                        l0_rec = [r for r in rep if r["layer"] == 0]
                        if l0_rec and "seal_step" in l0_rec[0]:
                            seal_steps.append(l0_rec[0]["seal_step"])
                        
                    except Exception as e:
                        print(f"  ⚠️  Seed {seed} 失败: {e}")
                        depths.append(0)
                        fluxes_l1.append(0.0)
                        l2_emergence.append(False)
                
                results[config_key] = {
                    "N0": N0,
                    "bind_threshold": bt,
                    "seal_fraction": sf,
                    "depths": depths,
                    "mean_depth": np.mean(depths),
                    "std_depth": np.std(depths),
                    "fluxes_l1": fluxes_l1,
                    "mean_flux": np.mean(fluxes_l1),
                    "std_flux": np.std(fluxes_l1),
                    "l2_rate": np.mean(l2_emergence),
                    "seal_steps": seal_steps,
                    "mean_seal_step": np.mean(seal_steps) if seal_steps else 0,
                }
    
    return results


def print_results(results):
    """打印扫描结果表格"""
    print("\n" + "=" * 110)
    print("参数鲁棒性扫描结果 — 自指闭环 (self_encapsulate=True)")
    print("=" * 110)
    print(f"{'配置':<35} {'深度(mean±std)':<20} {'L1 flux(mean)':<18} {'L2涌现率':<12} {'密封步数'}")
    print("-" * 110)
    
    for key, res in sorted(results.items()):
        config_str = f"N0={res['N0']} b={res['bind_threshold']} s={res['seal_fraction']}"
        depth_str = f"{res['mean_depth']:.2f}±{res['std_depth']:.2f}"
        flux_str = f"{res['mean_flux']:.4f}"
        l2_str = f"{res['l2_rate']*100:.0f}%"
        seal_str = f"{res['mean_seal_step']:.0f}" if res['mean_seal_step'] > 0 else "N/A"
        
        print(f"{config_str:<35} {depth_str:<20} {flux_str:<18} {l2_str:<12} {seal_str}")
    
    print("=" * 110)


def find_optimal(results):
    """找出最优配置"""
    print("\n【最优配置分析】")
    
    # 按 L2 涌现率排序
    sorted_by_l2 = sorted(results.items(), key=lambda x: x[1]['l2_rate'], reverse=True)
    print(f"\n  L2 涌现率最高:")
    for key, res in sorted_by_l2[:3]:
        print(f"    {key}: {res['l2_rate']*100:.0f}% (深度={res['mean_depth']:.2f}, flux={res['mean_flux']:.4f})")
    
    # 按 L1 flux 排序
    sorted_by_flux = sorted(results.items(), key=lambda x: x[1]['mean_flux'], reverse=True)
    print(f"\n  L1 自主 flux 最高:")
    for key, res in sorted_by_flux[:3]:
        print(f"    {key}: {res['mean_flux']:.4f} (L2={res['l2_rate']*100:.0f}%)")
    
    # 综合评分: L2涌现率 * 深度 * (flux + 0.01) 避免全0
    print(f"\n  综合评分最高 (L2_rate * depth * (flux+0.01)):")
    scored = []
    for key, res in results.items():
        score = res['l2_rate'] * res['mean_depth'] * (res['mean_flux'] + 0.01)
        scored.append((key, res, score))
    
    scored.sort(key=lambda x: x[2], reverse=True)
    for key, res, score in scored[:5]:
        print(f"    {key}: score={score:.4f} (L2={res['l2_rate']*100:.0f}%, depth={res['mean_depth']:.2f}, flux={res['mean_flux']:.4f})")


def main():
    ap = argparse.ArgumentParser(description="engine_v2 参数鲁棒性扫描")
    ap.add_argument("--n-seeds", type=int, default=8, help="每个配置运行的种子数")
    ap.add_argument("--n-colors", type=int, default=6, help="颜色数")
    args = ap.parse_args()
    
    # 参数扫描范围 (使用 Params 中的字段名)
    N0_list = [24, 36, 48, 72, 96]
    bind_thresholds = [0.5, 1.0, 2.0]      # Params.bind_threshold
    seal_fractions = [0.4, 0.6, 0.8]        # Params.seal_fraction
    
    total_configs = len(N0_list) * len(bind_thresholds) * len(seal_fractions)
    total_runs = total_configs * args.n_seeds
    
    print("=" * 70)
    print("差异论模拟机 v2 — 参数鲁棒性扫描")
    print("=" * 70)
    print(f"\n扫描范围:")
    print(f"  N0: {N0_list}")
    print(f"  bind_threshold: {bind_thresholds}")
    print(f"  seal_fraction: {seal_fractions}")
    print(f"\n总计: {total_configs} 配置 × {args.n_seeds} seeds = {total_runs} 次运行")
    print(f"\n开始扫描...\n")
    
    results = run_sweep(
        N0_list,
        bind_thresholds,
        seal_fractions,
        n_seeds=args.n_seeds,
        n_colors=args.n_colors
    )
    
    print_results(results)
    find_optimal(results)
    
    # 保存结果到 JSON
    output_file = "robustness_sweep_results.json"
    
    # 转换 numpy 类型为 Python 原生类型以便 JSON 序列化
    serializable_results = {}
    for key, res in results.items():
        serializable_results[key] = {
            "N0": int(res["N0"]),
            "bind_threshold": float(res["bind_threshold"]),
            "seal_fraction": float(res["seal_fraction"]),
            "depths": [int(d) for d in res["depths"]],
            "mean_depth": float(res["mean_depth"]),
            "std_depth": float(res["std_depth"]),
            "fluxes_l1": [float(f) for f in res["fluxes_l1"]],
            "mean_flux": float(res["mean_flux"]),
            "std_flux": float(res["std_flux"]),
            "l2_rate": float(res["l2_rate"]),
            "seal_steps": [int(s) for s in res["seal_steps"]],
            "mean_seal_step": float(res["mean_seal_step"]),
        }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n结果已保存到: {output_file}")
    print("\n" + "=" * 70)
    print("扫描完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
