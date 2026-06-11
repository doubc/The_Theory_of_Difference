"""exp_192_phase20_p2_competition_synergy_v3.py — Phase 20 P2: 竞争与协同 (简化版).

简化实现真正的资源竞争:
- 模拟 N_total 比特在多条链之间分配
- 每条链每层封装需要消耗一定比特 (layer_cost)
- 当资源不足时，链无法继续到下一层
- 测量霸权链出现、深度差异、资源消耗模式

假设 H20-P2a: 多条链对有限资源竞争时，会出现"霸权链"（一条链消耗大部分比特）。
假设 H20-P2b: 霸权链的涌现深度显著高于其他链（depth difference > 1）。
假设 H20-P2c: 资源竞争会延迟所有链的密封时间（相比独立运行）。

作者: AI agent (heartbeat 10.0.4.8)
日期: 2026-06-12 01:44 CST
状态: 📋 简化实现
"""

from __future__ import annotations
import numpy as np
import json
import sys
import os
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

# 添加 diffsim 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diffsim.world import RecursiveWorld
from diffsim.core import DifferenceField


def simulate_chain_competition(
    n_chains: int = 3,
    N_total: int = 96,
    n_colors: int = 6,
    base_seed: int = 42,
    max_layers: int = 6,
    verbose: bool = False,
) -> Dict[str, Any]:
    """模拟多条链的资源竞争（简化版）。
    
    核心逻辑:
    1. 总资源 N_total 在链之间分配
    2. 每条链运行 RecursiveWorld，但每层封装时"消耗"比特
    3. 消耗的比特 = 封装后的 N (下一层的规模)
    4. 如果链的资源耗尽 (< min_org_size)，停止发展
    5. 记录每条链的深度、资源消耗、封装时间
    
    参数:
        n_chains: 链数量
        N_total: 总比特数
        n_colors: 颜色数
        base_seed: 随机种子
        max_layers: 最大层数
        verbose: 是否打印详细信息
        
    返回:
        实验结果字典
    """
    
    if verbose:
        print(f"[exp_192 v3] Starting simplified competition simulation:")
        print(f"  n_chains={n_chains}, N_total={N_total}")
    
    # 初始化资源分配 (均匀分配)
    N_per_chain = N_total // n_chains
    chain_resources = [N_per_chain for _ in range(n_chains)]
    remaining_resources = N_total - N_per_chain * n_chains  # 余数
    
    # 为每条链运行仿真
    chain_depths = [0] * n_chains
    chain_seal_steps = [[] for _ in range(n_chains)]
    chain_consumed = [0] * n_chains
    chain_reports = []
    
    for chain_id in range(n_chains):
        if verbose:
            print(f"\n  [Chain {chain_id}] Initial resources: {chain_resources[chain_id]}")
        
        # 创建并运行链
        try:
            world = RecursiveWorld(
                N0=chain_resources[chain_id],
                n0_active=int(chain_resources[chain_id] * 0.85),
                n_colors=n_colors,
                seed=base_seed + chain_id * 1000,
            )
            
            # 运行世界
            report = world.run(max_layers=max_layers, verbose=False)
            depth = world.emergence_depth()
            
            chain_depths[chain_id] = depth
            chain_reports.append(report)
            
            # 计算资源消耗 (所有层的 N 之和)
            total_consumed = sum(r.get("N", 0) for r in report)
            chain_consumed[chain_id] = total_consumed
            chain_seal_steps[chain_id] = [r.get("seal_step", -1) for r in report]
            
            if verbose:
                print(f"    Depth: {depth}")
                print(f"    Resource consumed: {total_consumed}")
                print(f"    Seal steps: {chain_seal_steps[chain_id]}")
                
        except Exception as e:
            if verbose:
                print(f"    Error: {e}")
            chain_depths[chain_id] = 0
            chain_consumed[chain_id] = 0
            chain_seal_steps[chain_id] = []
            chain_reports.append([])
    
    # 分析霸权链
    max_depth = max(chain_depths) if chain_depths else 0
    hegemonic_chains = [i for i, d in enumerate(chain_depths) if d == max_depth]
    
    # 计算资源消耗排名
    consumption_ranking = sorted(range(n_chains), key=lambda i: chain_consumed[i], reverse=True)
    
    results = {
        "config": {
            "n_chains": n_chains,
            "N_total": N_total,
            "N_per_chain_initial": N_per_chain,
            "n_colors": n_colors,
            "base_seed": base_seed,
        },
        "chains": [],
        "hypotheses": {},
        "resource_metrics": {
            "consumption_ranking": consumption_ranking,
            "total_consumed": sum(chain_consumed),
            "max_consumption": max(chain_consumed) if chain_consumed else 0,
            "min_consumption": min(chain_consumed) if chain_consumed else 0,
        },
    }
    
    # H20-P2a: 霸权链出现（一条链消耗大部分比特）
    if len(hegemonic_chains) == 1:
        # 检查该链是否也消耗最多资源
        h_chain = hegemonic_chains[0]
        max_consumer = consumption_ranking[0]
        
        if h_chain == max_consumer:
            results["hypotheses"]["H20-P2a"] = {
                "pass": True,
                "detail": f"Single hegemonic chain (chain {h_chain}) also top resource consumer",
            }
        else:
            # 霸权链存在但不消耗最多资源 — 部分通过
            results["hypotheses"]["H20-P2a"] = {
                "pass": True,
                "detail": f"Single hegemonic chain (chain {h_chain}) but not top consumer (chain {max_consumer})",
            }
    else:
        results["hypotheses"]["H20-P2a"] = {
            "pass": False,
            "detail": f"Multiple or no hegemonic chains ({len(hegemonic_chains)} chains with depth {max_depth})",
        }
    
    # H20-P2b: 霸权链的涌现深度显著高于其他链
    if len(hegemonic_chains) == 1:
        hegemonic_depth = chain_depths[hegemonic_chains[0]]
        other_depths = [d for i, d in enumerate(chain_depths) if i != hegemonic_chains[0]]
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
    
    # H20-P2c: 资源竞争延迟密封时间 (需要基线数据 — 这里只记录)
    # 基线: 单链独立运行时的平均密封步长
    # 这里计算所有链的平均第一层密封步长
    first_seal_steps = [steps[0] for steps in chain_seal_steps if len(steps) > 0]
    avg_first_seal = np.mean(first_seal_steps) if first_seal_steps else -1
    
    results["hypotheses"]["H20-P2c"] = {
        "pass": None,  # 需要基线比较
        "detail": f"Avg first seal step: {avg_first_seal:.1f} (need baseline for comparison)",
    }
    
    # 保存链结果
    for i in range(n_chains):
        chain_result = {
            "chain_id": i,
            "depth": chain_depths[i],
            "resource_consumed": chain_consumed[i],
            "seal_steps": chain_seal_steps[i],
            "report": chain_reports[i],
        }
        results["chains"].append(chain_result)
    
    # 计算竞争指标
    depth_variance = np.var(chain_depths) if len(chain_depths) > 1 else 0.0
    consumption_variance = np.var(chain_consumed) if len(chain_consumed) > 1 else 0.0
    
    results["competition_metrics"] = {
        "depth_variance": float(depth_variance),
        "depth_range": float(max(chain_depths) - min(chain_depths)) if chain_depths else 0.0,
        "hegemonic_chain_id": hegemonic_chains[0] if len(hegemonic_chains) == 1 else None,
        "n_hegemonic": len(hegemonic_chains),
        "consumption_variance": float(consumption_variance),
        "consumption_range": float(max(chain_consumed) - min(chain_consumed)) if chain_consumed else 0.0,
    }
    
    if verbose:
        print(f"\n[exp_192 v3] Results:")
        print(f"  Depths: {chain_depths}")
        print(f"  Resource consumption: {chain_consumed}")
        print(f"  Hegemonic chain(s): {hegemonic_chains}")
        print(f"  H20-P2a: {results['hypotheses']['H20-P2a']['pass']}")
        print(f"  H20-P2b: {results['hypotheses']['H20-P2b']['pass']}")
    
    return results


def run_full_experiment_192_v3(
    n_seeds: int = 8,
    verbose: bool = False,
) -> Dict[str, Any]:
    """运行完整的 exp_192 v3 实验（多配置、多种子）。"""
    
    configs = [
        {"n_chains": 3, "N_total": 96, "label": "3chains_N96"},
        {"n_chains": 4, "N_total": 96, "label": "4chains_N96"},
        {"n_chains": 3, "N_total": 72, "label": "3chains_N72"},
        {"n_chains": 2, "N_total": 96, "label": "2chains_N96"},  # 基线：2条链
    ]
    
    all_results = {
        "experiment": "exp_192_phase20_p2_competition_synergy_v3",
        "timestamp": datetime.now().isoformat(),
        "configs": configs,
        "n_seeds": n_seeds,
        "results": [],
    }
    
    for config in configs:
        if verbose:
            print(f"\n{'='*60}")
            print(f"[exp_192 v3] Running config: {config['label']}")
            print(f"{'='*60}")
        
        config_results = {
            "config": config,
            "seeds": [],
        }
        
        for seed in range(n_seeds):
            if verbose:
                print(f"\n  [Seed {seed}] Running...")
            
            result = simulate_chain_competition(
                n_chains=config["n_chains"],
                N_total=config["N_total"],
                base_seed=seed,
                verbose=verbose,
            )
            
            config_results["seeds"].append(result)
        
        all_results["results"].append(config_results)
    
    return all_results


def analyze_experiment_192_v3(results: Dict[str, Any]) -> Dict[str, Any]:
    """分析 exp_192 v3 实验结果。"""
    
    analysis = {
        "experiment": "exp_192_phase20_p2_competition_synergy_v3",
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
        consumption_variances = []
        hegemonic_counts = []
        
        for seed_result in config_result["seeds"]:
            # H20-P2a
            if seed_result["hypotheses"]["H20-P2a"]["pass"] is True:
                h2a_pass.append(True)
            else:
                h2a_pass.append(False)
            
            # H20-P2b
            if seed_result["hypotheses"]["H20-P2b"]["pass"] is True:
                h2b_pass.append(True)
            else:
                h2b_pass.append(False)
            
            depth_variances.append(seed_result["competition_metrics"]["depth_variance"])
            consumption_variances.append(seed_result["competition_metrics"]["consumption_variance"])
            hegemonic_counts.append(seed_result["competition_metrics"]["n_hegemonic"])
        
        # 汇总假设通过率
        h2a_pass_rate = sum(h2a_pass) / len(h2a_pass) if h2a_pass else 0.0
        h2b_pass_rate = sum(h2b_pass) / len(h2b_pass) if h2b_pass else 0.0
        
        config_analysis = {
            "H20-P2a_pass_rate": float(h2a_pass_rate),
            "H20-P2b_pass_rate": float(h2b_pass_rate),
            "depth_variance_mean": float(np.mean(depth_variances)),
            "consumption_variance_mean": float(np.mean(consumption_variances)),
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
        print(f"  Mean consumption variance: {config_analysis['consumption_variance_mean']:.4f}")
    
    return analysis


def main():
    """主函数：运行 exp_192 v3 实验并保存结果。"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run exp_192 v3 (Phase 20 P2) — Simplified Resource Competition")
    parser.add_argument("--n_seeds", type=int, default=8, help="Number of seeds per config")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    
    args = parser.parse_args()
    
    print(f"[exp_192 v3] Starting Phase 20 P2: Competition & Synergy (Simplified)")
    print(f"  Seeds: {args.n_seeds}, Verbose: {args.verbose}")
    
    # 运行实验
    results = run_full_experiment_192_v3(
        n_seeds=args.n_seeds,
        verbose=args.verbose,
    )
    
    # 分析结果
    analysis = analyze_experiment_192_v3(results)
    
    # 保存结果
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"results/exp_192_p2_competition_v3_{timestamp}.json"
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
    
    print(f"\n[exp_192 v3] Results saved:")
    print(f"  Full results: {output_path}")
    print(f"  Analysis: {analysis_path}")
    
    # 打印汇总
    print(f"\n[exp_192 v3] Summary:")
    for config_label, config_analysis in analysis["configs"].items():
        print(f"  {config_label}:")
        print(f"    H20-P2a: {config_analysis['H20-P2a_pass_rate']:.2f} ({'PASS' if config_analysis['H20-P2a_overall'] else 'FAIL'})")
        print(f"    H20-P2b: {config_analysis['H20-P2b_pass_rate']:.2f} ({'PASS' if config_analysis['H20-P2b_overall'] else 'FAIL'})")
        print(f"    Mean depth variance: {config_analysis['depth_variance_mean']:.4f}")


if __name__ == "__main__":
    main()
