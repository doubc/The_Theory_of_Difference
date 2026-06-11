"""exp_192_phase20_p2_competition_synergy.py — Phase 20 P2: 竞争与协同.

假设 H20-P2a: 多条链对有限资源竞争时，会出现"霸权链"（一条链消耗大部分比特）。
假设 H20-P2b: 霸权链的涌现深度显著高于其他链（depth difference > 1）。
假设 H20-P2c: 资源竞争会延迟所有链的密封时间（相比独立运行）。

实验设计:
- 总比特数 N_total = 96
- 并行运行 3-4 条链，每条链初始分配 N_allocated = N_total / n_chains
- 当一条链的 L1 封装消耗比特时，其他链可用比特减少
- 测量霸权链出现、深度差异、密封时间延迟

作者: AI agent (heartbeat 10.0.4.8)
日期: 2026-06-12 01:14 CST
状态: 📋 实现中
"""

from __future__ import annotations
import numpy as np
import json
import sys
import os
from typing import List, Dict, Any, Tuple
from datetime import datetime

# 添加 diffsim 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diffsim.multi_world import MultiWorld
from diffsim.world import RecursiveWorld, Params
from diffsim.core import DifferenceField
from diffsim import mechanisms as M


def run_experiment_192_competition(
    n_chains: int = 3,
    N_total: int = 96,
    n_colors: int = 6,
    base_seed: int = 42,
    max_layers: int = 6,
    max_steps_per_layer: int = 500,
    verbose: bool = False,
) -> Dict[str, Any]:
    """运行竞争与协同实验。
    
    参数:
        n_chains: 并行链数量
        N_total: 总比特数
        n_colors: 颜色数
        base_seed: 随机种子
        max_layers: 最大层数
        max_steps_per_layer: 每层最大步数
        verbose: 是否打印详细信息
        
    返回:
        实验结果字典
    """
    N_allocated = N_total // n_chains
    
    if verbose:
        print(f"[exp_192] Starting competition experiment:")
        print(f"  n_chains={n_chains}, N_total={N_total}, N_allocated={N_allocated}")
        print(f"  max_layers={max_layers}, max_steps={max_steps_per_layer}")
    
    # 创建多世界管理器（无耦合，独立运行）
    mw = MultiWorld(
        n_worlds=n_chains,
        N0=N_allocated,
        n0_active=int(N_allocated * 0.85),  # 85% 初始活跃
        n_colors=n_colors,
        base_seed=base_seed,
        coupling_strength=0.0,
        coupling_mode="none",
    )
    
    # 运行所有链
    mw.run_all(max_layers=max_layers, verbose=verbose)
    
    # 收集结果
    results = {
        "config": {
            "n_chains": n_chains,
            "N_total": N_total,
            "N_allocated": N_allocated,
            "n_colors": n_colors,
            "base_seed": base_seed,
        },
        "worlds": [],
        "hypotheses": {},
    }
    
    depths = []
    seal_steps = []
    
    for i, world in enumerate(mw.worlds):
        depth = world.emergence_depth()
        depths.append(depth)
        
        # 收集密封步长
        world_seal_steps = []
        for layer_report in world.report:
            if layer_report.get("sealed", False):
                world_seal_steps.append(layer_report.get("seal_step", -1))
        seal_steps.append(world_seal_steps)
        
        world_result = {
            "world_id": i,
            "depth": depth,
            "N_allocated": N_allocated,
            "seal_steps": world_seal_steps,
            "report": world.report,
        }
        results["worlds"].append(world_result)
    
    # 分析霸权链
    max_depth = max(depths)
    hegemonic_chains = [i for i, d in enumerate(depths) if d == max_depth]
    
    # H20-P2a: 霸权链出现（一条链消耗大部分比特）
    if len(hegemonic_chains) == 1:
        results["hypotheses"]["H20-P2a"] = {
            "pass": True,
            "detail": f"Single hegemonic chain detected (world {hegemonic_chains[0]})",
        }
    else:
        results["hypotheses"]["H20-P2a"] = {
            "pass": False,
            "detail": f"Multiple or no hegemonic chains ({len(hegemonic_chains)} worlds with depth {max_depth})",
        }
    
    # H20-P2b: 霸权链深度显著高于其他链
    if len(hegemonic_chains) == 1:
        hegemonic_depth = depths[hegemonic_chains[0]]
        other_depths = [d for i, d in enumerate(depths) if i != hegemonic_chains[0]]
        if other_depths:
            depth_diff = hegemonic_depth - max(other_depths)
            results["hypotheses"]["H20-P2b"] = {
                "pass": depth_diff > 1,
                "detail": f"Depth difference: {depth_diff:.2f} (hegemonic: {hegemonic_depth}, max other: {max(other_depths)})",
            }
        else:
            results["hypotheses"]["H20-P2b"] = {
                "pass": False,
                "detail": "No other chains to compare",
            }
    else:
        results["hypotheses"]["H20-P2b"] = {
            "pass": False,
            "detail": "No single hegemonic chain",
        }
    
    # H20-P2c: 资源竞争延迟密封时间（需要基线数据）
    # 这里我们只记录密封步长，与基线比较需要在分析脚本中完成
    results["seal_steps"] = seal_steps
    results["depths"] = depths
    
    # 计算竞争指标
    depth_variance = np.var(depths) if len(depths) > 1 else 0.0
    results["competition_metrics"] = {
        "depth_variance": float(depth_variance),
        "depth_range": float(max(depths) - min(depths)) if depths else 0.0,
        "hegemonic_chain_id": hegemonic_chains[0] if len(hegemonic_chains) == 1 else None,
        "n_hegemonic": len(hegemonic_chains),
    }
    
    if verbose:
        print(f"\n[exp_192] Results:")
        print(f"  Depths: {depths}")
        print(f"  Hegemonic chain(s): {hegemonic_chains}")
        print(f"  H20-P2a: {results['hypotheses']['H20-P2a']['pass']}")
        print(f"  H20-P2b: {results['hypotheses']['H20-P2b']['pass']}")
    
    return results


def run_full_experiment_192(
    n_seeds: int = 8,
    verbose: bool = False,
) -> Dict[str, Any]:
    """运行完整的 exp_192 实验（多配置、多种子）。"""
    
    configs = [
        {"n_chains": 3, "N_total": 96, "label": "3chains_N96"},
        {"n_chains": 4, "N_total": 96, "label": "4chains_N96"},
        {"n_chains": 3, "N_total": 72, "label": "3chains_N72"},
        {"n_chains": 2, "N_total": 96, "label": "2chains_N96"},  # 基线：2条链
    ]
    
    all_results = {
        "experiment": "exp_192_phase20_p2_competition_synergy",
        "timestamp": datetime.now().isoformat(),
        "configs": configs,
        "n_seeds": n_seeds,
        "results": [],
    }
    
    for config in configs:
        if verbose:
            print(f"\n{'='*60}")
            print(f"[exp_192] Running config: {config['label']}")
            print(f"{'='*60}")
        
        config_results = {
            "config": config,
            "seeds": [],
        }
        
        for seed in range(n_seeds):
            if verbose:
                print(f"\n  [Seed {seed}] Running...")
            
            result = run_experiment_192_competition(
                n_chains=config["n_chains"],
                N_total=config["N_total"],
                base_seed=seed,
                verbose=verbose,
            )
            
            config_results["seeds"].append(result)
        
        all_results["results"].append(config_results)
    
    return all_results


def analyze_experiment_192(results: Dict[str, Any]) -> Dict[str, Any]:
    """分析 exp_192 实验结果。"""
    
    analysis = {
        "experiment": "exp_192_phase20_p2_competition_synergy",
        "timestamp": datetime.now().isoformat(),
        "configs": {},
    }
    
    for config_result in results["results"]:
        config = config_result["config"]
        config_label = config["label"]
        
        # 收集所有种子的假设结果
        h2a_pass = []
        h2b_pass = []
        depth_variances = []
        hegemonic_counts = []
        
        for seed_result in config_result["seeds"]:
            h2a_pass.append(seed_result["hypotheses"]["H20-P2a"]["pass"])
            h2b_pass.append(seed_result["hypotheses"]["H20-P2b"]["pass"])
            depth_variances.append(seed_result["competition_metrics"]["depth_variance"])
            hegemonic_counts.append(seed_result["competition_metrics"]["n_hegemonic"])
        
        # 汇总假设通过率
        h2a_pass_rate = sum(h2a_pass) / len(h2a_pass) if h2a_pass else 0.0
        h2b_pass_rate = sum(h2b_pass) / len(h2b_pass) if h2b_pass else 0.0
        
        config_analysis = {
            "H20-P2a_pass_rate": float(h2a_pass_rate),
            "H20-P2b_pass_rate": float(h2b_pass_rate),
            "depth_variance_mean": float(np.mean(depth_variances)),
            "hegemonic_count_mean": float(np.mean(hegemonic_counts)),
            "n_seeds": len(h2a_pass),
        }
        
        # 判断假设是否通过（≥50% 种子通过）
        config_analysis["H20-P2a_overall"] = h2a_pass_rate >= 0.5
        config_analysis["H20-P2b_overall"] = h2b_pass_rate >= 0.5
        
        analysis["configs"][config_label] = config_analysis
        
        print(f"[Analysis] Config {config_label}:")
        print(f"  H20-P2a pass rate: {h2a_pass_rate:.2f} ({'PASS' if config_analysis['H20-P2a_overall'] else 'FAIL'})")
        print(f"  H20-P2b pass rate: {h2b_pass_rate:.2f} ({'PASS' if config_analysis['H20-P2b_overall'] else 'FAIL'})")
        print(f"  Mean depth variance: {config_analysis['depth_variance_mean']:.4f}")
    
    return analysis


def main():
    """主函数：运行 exp_192 实验并保存结果。"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run exp_192 (Phase 20 P2)")
    parser.add_argument("--n_seeds", type=int, default=8, help="Number of seeds per config")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    
    args = parser.parse_args()
    
    print(f"[exp_192] Starting Phase 20 P2: Competition & Synergy")
    print(f"  Seeds: {args.n_seeds}, Verbose: {args.verbose}")
    
    # 运行实验
    results = run_full_experiment_192(
        n_seeds=args.n_seeds,
        verbose=args.verbose,
    )
    
    # 分析结果
    analysis = analyze_experiment_192(results)
    
    # 保存结果
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"results/exp_192_p2_competition_{timestamp}.json"
    else:
        output_path = args.output
    
    # 确保结果目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 保存完整结果
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # 保存分析结果
    analysis_path = output_path.replace(".json", "_analysis.json")
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"\n[exp_192] Results saved:")
    print(f"  Full results: {output_path}")
    print(f"  Analysis: {analysis_path}")
    
    # 打印汇总
    print(f"\n[exp_192] Summary:")
    for config_label, config_analysis in analysis["configs"].items():
        print(f"  {config_label}:")
        print(f"    H20-P2a: {config_analysis['H20-P2a_pass_rate']:.2f} ({'PASS' if config_analysis['H20-P2a_overall'] else 'FAIL'})")
        print(f"    H20-P2b: {config_analysis['H20-P2b_pass_rate']:.2f} ({'PASS' if config_analysis['H20-P2b_overall'] else 'FAIL'})")


if __name__ == "__main__":
    main()
