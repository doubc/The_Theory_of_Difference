"""exp_200_v5_fixed_imports.py

Phase 21 P0: 能量流基线实验 (修复版)
===========================

修复内容:
1. 使用正确的导入 (diffsim.world_v2 而非 diffsim.world)
2. 使用正确的参数名 (energy_cfg 而非 energy_config)
3. 移除不支持的参数 (self_encapsulate, n0_active)

假设:
- H21-P0a: 能量预算耗尽时系统进入死秩序 (autonomous_flux -> 0)
- H21-P0b: 有能量注入时活秩序维持更长时间 (flux 衰减更慢)
- H21-P0c: 涌现深度与初始能量预算正相关
- H21-P0d: 熵产生持续 > 0 表示不可逆的叙事演化

配置:
- baseline: 无能量流 (energy_cfg=None, 对照组)
- with_energy: 有能量流 + 注入
- low_budget: 低初始预算 (30.0)
- high_decay: 高衰减率 (0.05)

每配置 8 seeds, 2000 steps.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np

# 确保 diffsim 可导入
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 修复 1: 使用正确的导入 (world_v2.py 版本)
from diffsim.world_v2 import RecursiveWorld, Params  # Params 在 world_v2.py 中定义
from diffsim.energy_v2 import EnergyConfig  # 使用 energy_v2
from diffsim.entropy import EntropyConfig


def run_single(cfg_name: str, seed: int, N0: int = 48) -> dict:
    """运行单个配置+种子，返回结果字典。"""
    p = Params()
    
    # 修复 2: 使用 Params 设置初始活跃数 (而非 n0_active 参数)
    p.target_active = 40  # 相当于原来的 n0_active=40

    if cfg_name == "baseline":
        energy_cfg = None
        entropy_cfg = None
    elif cfg_name == "with_energy":
        energy_cfg = EnergyConfig(initial_budget=100.0, decay_rate=0.01, injection_rate=0.5)
        entropy_cfg = EntropyConfig()
    elif cfg_name == "low_budget":
        energy_cfg = EnergyConfig(initial_budget=30.0, decay_rate=0.01, injection_rate=0.3)
        entropy_cfg = EntropyConfig()
    elif cfg_name == "high_decay":
        energy_cfg = EnergyConfig(initial_budget=100.0, decay_rate=0.05, injection_rate=0.5)
        entropy_cfg = EntropyConfig()
    else:
        raise ValueError(f"Unknown config: {cfg_name}")

    # 修复 3: 使用正确的参数名
    world = RecursiveWorld(
        N0=N0, n_colors=6, seed=seed,
        params=p,
        energy_cfg=energy_cfg,  # 不是 energy_config
        entropy_cfg=entropy_cfg,  # 不是 entropy_config
        # 移除 self_encapsulate (v2 版本不支持或默认启用)
    )
    report = world.run(max_layers=6, verbose=False)

    # 收集各层能量/熵信息
    layer_energy = []
    layer_entropy = []
    for layer in world.layers:
        if hasattr(layer, 'energy') and layer.energy:
            layer_energy.append(layer.energy.get_summary())
        if hasattr(layer, 'entropy') and layer.entropy:
            layer_entropy.append(layer.entropy.get_summary())

    result = {
        "config": cfg_name,
        "seed": seed,
        "N0": N0,
        "emergence_depth": world.get_emergence_depth(),  # 修复 4: 使用正确的方法名
        "report": report,
        "layer_energy": layer_energy,
        "layer_entropy": layer_entropy,
    }

    # H21-P0a: 检测低能量样本
    if layer_energy:
        final_ratios = [e["budget_ratio"] for e in layer_energy if "budget_ratio" in e]
        if final_ratios:
            result["mean_energy_ratio"] = float(np.mean(final_ratios))
        else:
            result["mean_energy_ratio"] = None
        result["dead_order_layers"] = sum(1 for e in layer_energy if e.get("is_depleted", False))
    else:
        result["mean_energy_ratio"] = None
        result["dead_order_layers"] = 0

    # H21-P0d: 不可逆性
    if layer_entropy:
        irr = [e.get("is_irreversible", False) for e in layer_entropy]
        result["any_irreversible"] = any(irr)
    else:
        result["any_irreversible"] = None

    return result


def evaluate_hypotheses(results: list) -> dict:
    """评估四个假设。"""
    configs = sorted(set(r["config"] for r in results))
    by_cfg = {c: [r for r in results if r["config"] == c] for c in configs}

    eval_out = {}

    # H21-P0a: 能量预算耗尽时进入死秩序
    print("\n  H21-P0a (能量预算耗尽 → 死秩序):")
    for c in ["low_budget", "with_energy", "high_decay"]:
        if c in by_cfg:
            n_dead = sum(r.get("dead_order_layers", 0) for r in by_cfg[c])
            n_total = sum(max(len(r.get("layer_energy", [])), 1) for r in by_cfg[c])
            print(f"    [{c}]: {n_dead}/{n_total} layers in dead order")

    # H21-P0b: 有能量注入时 flux 维持更久
    print("\n  H21-P0b (能量注入 → flux 维持):")
    for c in configs:
        if c in by_cfg:
            # 获取 L0 的 flux
            fluxes = []
            for r in by_cfg[c]:
                if r.get("report") and len(r["report"]) > 0:
                    flux = r["report"][0].get("flux", 0.0)
                    fluxes.append(flux)
            if fluxes:
                print(f"    [{c}]: mean L0 flux = {np.mean(fluxes):.4f} (expect ~0.2123)")

    # H21-P0c: 涌现深度与初始能量预算正相关
    print("\n  H21-P0c (能量预算 ∝ 涌现深度):")
    for c in configs:
        if c in by_cfg:
            depths = [r.get("emergence_depth", 0) for r in by_cfg[c]]
            print(f"    [{c}]: mean depth = {np.mean(depths):.2f}")

    # H21-P0d: 熵产生 > 0 (不可逆)
    print("\n  H21-P0d (熵产生 > 0 → 不可逆):")
    for c in configs:
        if c in by_cfg:
            irr = [r.get("any_irreversible") for r in by_cfg[c]]
            n_irr = sum(1 for x in irr if x is True)
            print(f"    [{c}]: irreversible = {n_irr}/{len(irr)}")

    return eval_out


def main():
    configs = ["baseline", "with_energy", "low_budget", "high_decay"]
    seeds = range(4)  # 先用 4 seeds 测试
    N0 = 48

    all_results = []
    for cfg_name in configs:
        for seed in seeds:
            print(f"  Running {cfg_name} seed={seed}...")
            try:
                result = run_single(cfg_name, seed, N0)
                all_results.append(result)
                depth = result.get("emergence_depth", 0)
                print(f"    depth={depth}")
            except Exception as e:
                print(f"    ERROR: {e}")
                import traceback
                traceback.print_exc()
                all_results.append({"config": cfg_name, "seed": seed, "error": str(e)})

    # 保存结果
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "exp_200_v5_fixed_20260613.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    # 评估假设
    print("\n=== Hypothesis Evaluation ===")
    evaluate_hypotheses(all_results)


if __name__ == "__main__":
    main()
