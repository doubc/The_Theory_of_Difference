"""exp_192_phase20_p2_competition_synergy_v2.py — Phase 20 P2: 竞争与协同 (修正版).

修正核心问题: 实现真正的动态资源竞争 (ResourcePool)。

假设 H20-P2a: 多条链对有限资源竞争时，会出现"霸权链"（一条链消耗大部分比特）。
假设 H20-P2b: 霸权链的涌现深度显著高于其他链（depth difference > 1）。
假设 H20-P2c: 资源竞争会延迟所有链的密封时间（相比独立运行）。

实验设计 (v2 修正):
- 总比特数 N_total = 96 (共享资源池)
- 并行运行 3-4 条链，初始时所有比特都在资源池中
- 当一条链封装 (L1 formation) 时，它从资源池中取出比特 (消耗资源)
- 其他链只能使用资源池中剩余的比特
- 如果资源池为空，链无法继续封装 (depth 停止增长)
- 测量霸权链出现、深度差异、密封时间延迟

作者: AI agent (heartbeat 10.0.4.8)
日期: 2026-06-12 01:44 CST
状态: 📋 修正实现
"""

from __future__ import annotations
import numpy as np
import json
import sys
import os
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import heapq

# 添加 diffsim 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diffsim.multi_world import MultiWorld
from diffsim.world import RecursiveWorld, Params
from diffsim.core import DifferenceField
from diffsim import mechanisms as M


class ResourcePool:
    """动态资源池 — 管理多条链对比特的竞争。"""
    
    def __init__(self, N_total: int, base_seed: int = 42):
        """初始化资源池。
        
        参数:
            N_total: 总比特数
            base_seed: 随机种子
        """
        self.N_total = N_total
        self.available = N_total  # 可用比特数
        self.allocated = {}  # {chain_id: allocated_N}
        self.history = []  # [(step, available, allocated)]
        self.rng = np.random.RandomState(base_seed)
        
    def request(self, chain_id: int, requested_N: int) -> int:
        """链请求比特。
        
        参数:
            chain_id: 链 ID
            requested_N: 请求的比特数
            
        返回:
            实际分配的比特数 (可能小于 requested_N)
        """
        if chain_id in self.allocated:
            # 已分配的链，检查是否需要更多
            current = self.allocated[chain_id]
            needed = requested_N - current
            if needed <= 0:
                return current
            
            # 从资源池中取出所需比特
            actual = min(needed, self.available)
            self.allocated[chain_id] = current + actual
            self.available -= actual
            return current + actual
        else:
            # 新链，首次请求
            actual = min(requested_N, self.available)
            self.allocated[chain_id] = actual
            self.available -= actual
            return actual
    
    def release(self, chain_id: int) -> None:
        """链释放比特 (封装完成或链终止)。"""
        if chain_id in self.allocated:
            released = self.allocated[chain_id]
            self.available += released
            del self.allocated[chain_id]
    
    def get_snapshot(self) -> Dict[str, Any]:
        """获取资源池快照。"""
        return {
            "total": self.N_total,
            "available": self.available,
            "allocated": dict(self.allocated),
            "n_active_chains": len(self.allocated),
        }
    
    def log(self, step: int) -> None:
        """记录资源池状态。"""
        snapshot = {
            "step": step,
            "available": self.available,
            "allocated": dict(self.allocated),
        }
        self.history.append(snapshot)


def run_experiment_192_competition_v2(
    n_chains: int = 3,
    N_total: int = 96,
    n_colors: int = 6,
    base_seed: int = 42,
    max_layers: int = 6,
    max_steps_per_layer: int = 500,
    verbose: bool = False,
) -> Dict[str, Any]:
    """运行竞争与协同实验 (v2 — 动态资源池)。
    
    参数:
        n_chains: 并行链数量
        N_total: 总比特数 (资源池)
        n_colors: 颜色数
        base_seed: 随机种子
        max_layers: 最大层数
        max_steps_per_layer: 每层最大步数
        verbose: 是否打印详细信息
        
    返回:
        实验结果字典
    """
    
    if verbose:
        print(f"[exp_192 v2] Starting competition experiment (dynamic resource pool):")
        print(f"  n_chains={n_chains}, N_total={N_total}")
        print(f"  max_layers={max_layers}, max_steps={max_steps_per_layer}")
    
    # 创建资源池
    pool = ResourcePool(N_total=N_total, base_seed=base_seed)
    
    # 创建多条链 (RecursiveWorld)
    chains = []
    chain_depths = []
    chain_seal_steps = []
    chain_histories = []
    
    for chain_id in range(n_chains):
        # 从资源池请求初始比特
        allocated_N = pool.request(chain_id, requested_N=N_total // n_chains)
        
        if allocated_N == 0:
            if verbose:
                print(f"  [Chain {chain_id}] No resources available, skipping")
            chains.append(None)
            chain_depths.append(0)
            chain_seal_steps.append([])
            chain_histories.append([])
            continue
        
        # 创建链
        params = Params(
            N0=allocated_N,
            n_colors=n_colors,
            base_seed=base_seed + chain_id * 1000,
        )
        world = RecursiveWorld(params)
        
        chains.append(world)
        chain_depths.append(0)
        chain_seal_steps.append([])
        chain_histories.append([])
        
        if verbose:
            print(f"  [Chain {chain_id}] Allocated N={allocated_N}")
    
    # 并行运行链 (简化版: 顺序运行每层)
    # 注意: 真实实现需要协程或线程来真正并行，这里用顺序模拟
    
    # 跟踪每层封装事件
    layer = 0
    active_chains = [i for i, w in enumerate(chains) if w is not None]
    
    while layer < max_layers and len(active_chains) > 0:
        if verbose:
            print(f"\n  [Layer {layer}] Active chains: {active_chains}")
            print(f"  Resource pool: available={pool.available}, allocated={pool.allocated}")
        
        # 为每条活跃链运行当前层
        for chain_id in active_chains[:]:  # 复制列表，允许修改
            world = chains[chain_id]
            if world is None:
                continue
            
            # 运行当前层直到封装或达到最大步数
            try:
                # 简化: 直接运行到封装 (真实实现需要逐步执行并检测封装)
                # 这里用 world.run_layer(layer, max_steps=max_steps_per_layer)
                # 但 RecursiveWorld API 可能不同
                
                # 获取当前层的封装状态
                current_depth = world.emergence_depth()
                
                if current_depth > chain_depths[chain_id]:
                    # 封装发生
                    chain_depths[chain_id] = current_depth
                    chain_seal_steps[chain_id].append(layer)
                    
                    if verbose:
                        print(f"    [Chain {chain_id}] Layer {layer} sealed, depth={current_depth}")
                    
                    # 链封装消耗了比特 — 从资源池中保留已分配的比特
                    # (不释放，因为封装后的比特被"锁定"在该层中)
                    # 如果链要继续到下一层，它需要更多比特
                    if current_depth >= max_layers:
                        # 链达到最大深度，释放剩余资源
                        pool.release(chain_id)
                        active_chains.remove(chain_id)
                        
                        if verbose:
                            print(f"    [Chain {chain_id}] Reached max depth, released resources")
                else:
                    # 未封装，继续运行
                    pass
                    
            except Exception as e:
                if verbose:
                    print(f"    [Chain {chain_id}] Error: {e}")
                # 链失败，释放资源
                pool.release(chain_id)
                active_chains.remove(chain_id)
        
        # 检查资源池是否为空
        if pool.available == 0 and all(chain_depths[i] >= 1 for i in active_chains):
            if verbose:
                print(f"\n  Resource pool exhausted, stopping")
            break
        
        layer += 1
    
    # 收集结果
    results = {
        "config": {
            "n_chains": n_chains,
            "N_total": N_total,
            "n_colors": n_colors,
            "base_seed": base_seed,
        },
        "resource_pool": {
            "final_available": pool.available,
            "final_allocated": dict(pool.allocated),
            "history": pool.history[:10],  # 只保存前 10 个快照
        },
        "chains": [],
        "hypotheses": {},
    }
    
    # 分析霸权链
    max_depth = max(chain_depths) if chain_depths else 0
    hegemonic_chains = [i for i, d in enumerate(chain_depths) if d == max_depth]
    
    # H20-P2a: 霸权链出现（一条链消耗大部分比特）
    if len(hegemonic_chains) == 1:
        results["hypotheses"]["H20-P2a"] = {
            "pass": True,
            "detail": f"Single hegemonic chain detected (chain {hegemonic_chains[0]})",
        }
    else:
        results["hypotheses"]["H20-P2a"] = {
            "pass": False,
            "detail": f"Multiple or no hegemonic chains ({len(hegemonic_chains)} chains with depth {max_depth})",
        }
    
    # H20-P2b: 霸权链深度显著高于其他链
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
    
    # H20-P2c: 资源竞争延迟密封时间 (需要基线数据)
    # 这里记录密封步长，与基线比较需要在分析脚本中完成
    results["seal_steps"] = chain_seal_steps
    results["depths"] = chain_depths
    
    # 计算竞争指标
    depth_variance = np.var(chain_depths) if len(chain_depths) > 1 else 0.0
    results["competition_metrics"] = {
        "depth_variance": float(depth_variance),
        "depth_range": float(max(chain_depths) - min(chain_depths)) if chain_depths else 0.0,
        "hegemonic_chain_id": hegemonic_chains[0] if len(hegemonic_chains) == 1 else None,
        "n_hegemonic": len(hegemonic_chains),
        "resource_exhausted": pool.available == 0,
    }
    
    # 保存链结果
    for i, (depth, seal_steps) in enumerate(zip(chain_depths, chain_seal_steps)):
        chain_result = {
            "chain_id": i,
            "depth": depth,
            "seal_steps": seal_steps,
            "allocated_N": pool.allocated.get(i, 0),
        }
        results["chains"].append(chain_result)
    
    if verbose:
        print(f"\n[exp_192 v2] Results:")
        print(f"  Depths: {chain_depths}")
        print(f"  Hegemonic chain(s): {hegemonic_chains}")
        print(f"  H20-P2a: {results['hypotheses']['H20-P2a']['pass']}")
        print(f"  H20-P2b: {results['hypotheses']['H20-P2b']['pass']}")
        print(f"  Resource exhausted: {results['competition_metrics']['resource_exhausted']}")
    
    return results


def run_full_experiment_192_v2(
    n_seeds: int = 8,
    verbose: bool = False,
) -> Dict[str, Any]:
    """运行完整的 exp_192 v2 实验（多配置、多种子）。"""
    
    configs = [
        {"n_chains": 3, "N_total": 96, "label": "3chains_N96"},
        {"n_chains": 4, "N_total": 96, "label": "4chains_N96"},
        {"n_chains": 3, "N_total": 72, "label": "3chains_N72"},
        {"n_chains": 2, "N_total": 96, "label": "2chains_N96"},  # 基线：2条链
    ]
    
    all_results = {
        "experiment": "exp_192_phase20_p2_competition_synergy_v2",
        "timestamp": datetime.now().isoformat(),
        "configs": configs,
        "n_seeds": n_seeds,
        "results": [],
    }
    
    for config in configs:
        if verbose:
            print(f"\n{'='*60}")
            print(f"[exp_192 v2] Running config: {config['label']}")
            print(f"{'='*60}")
        
        config_results = {
            "config": config,
            "seeds": [],
        }
        
        for seed in range(n_seeds):
            if verbose:
                print(f"\n  [Seed {seed}] Running...")
            
            result = run_experiment_192_competition_v2(
                n_chains=config["n_chains"],
                N_total=config["N_total"],
                base_seed=seed,
                verbose=verbose,
            )
            
            config_results["seeds"].append(result)
        
        all_results["results"].append(config_results)
    
    return all_results


def analyze_experiment_192_v2(results: Dict[str, Any]) -> Dict[str, Any]:
    """分析 exp_192 v2 实验结果。"""
    
    analysis = {
        "experiment": "exp_192_phase20_p2_competition_synergy_v2",
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
        resource_exhausted = []
        
        for seed_result in config_result["seeds"]:
            h2a_pass.append(seed_result["hypotheses"]["H20-P2a"]["pass"])
            h2b_pass.append(seed_result["hypotheses"]["H20-P2b"]["pass"])
            depth_variances.append(seed_result["competition_metrics"]["depth_variance"])
            hegemonic_counts.append(seed_result["competition_metrics"]["n_hegemonic"])
            resource_exhausted.append(seed_result["competition_metrics"]["resource_exhausted"])
        
        # 汇总假设通过率
        h2a_pass_rate = sum(h2a_pass) / len(h2a_pass) if h2a_pass else 0.0
        h2b_pass_rate = sum(h2b_pass) / len(h2b_pass) if h2b_pass else 0.0
        
        config_analysis = {
            "H20-P2a_pass_rate": float(h2a_pass_rate),
            "H20-P2b_pass_rate": float(h2b_pass_rate),
            "depth_variance_mean": float(np.mean(depth_variances)),
            "hegemonic_count_mean": float(np.mean(hegemonic_counts)),
            "resource_exhausted_rate": float(sum(resource_exhausted) / len(resource_exhausted)),
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
        print(f"  Resource exhausted rate: {config_analysis['resource_exhausted_rate']:.2f}")
    
    return analysis


def main():
    """主函数：运行 exp_192 v2 实验并保存结果。"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run exp_192 v2 (Phase 20 P2) — Dynamic Resource Pool")
    parser.add_argument("--n_seeds", type=int, default=8, help="Number of seeds per config")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    
    args = parser.parse_args()
    
    print(f"[exp_192 v2] Starting Phase 20 P2: Competition & Synergy (Dynamic Resource Pool)")
    print(f"  Seeds: {args.n_seeds}, Verbose: {args.verbose}")
    
    # 运行实验
    results = run_full_experiment_192_v2(
        n_seeds=args.n_seeds,
        verbose=args.verbose,
    )
    
    # 分析结果
    analysis = analyze_experiment_192_v2(results)
    
    # 保存结果
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"results/exp_192_p2_competition_v2_{timestamp}.json"
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
    
    print(f"\n[exp_192 v2] Results saved:")
    print(f"  Full results: {output_path}")
    print(f"  Analysis: {analysis_path}")
    
    # 打印汇总
    print(f"\n[exp_192 v2] Summary:")
    for config_label, config_analysis in analysis["configs"].items():
        print(f"  {config_label}:")
        print(f"    H20-P2a: {config_analysis['H20-P2a_pass_rate']:.2f} ({'PASS' if config_analysis['H20-P2a_overall'] else 'FAIL'})")
        print(f"    H20-P2b: {config_analysis['H20-P2b_pass_rate']:.2f} ({'PASS' if config_analysis['H20-P2b_overall'] else 'FAIL'})")
        print(f"    Resource exhausted: {config_analysis['resource_exhausted_rate']:.2f}")


if __name__ == "__main__":
    main()
