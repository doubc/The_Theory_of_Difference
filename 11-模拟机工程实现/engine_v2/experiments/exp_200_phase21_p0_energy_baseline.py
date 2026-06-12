"""exp_200_phase21_p0_energy_baseline.py

Phase 21 P0: 能量流基线实验
===========================

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

from diffsim.world import RecursiveWorld, Params
from diffsim.energy import EnergyConfig
from diffsim.entropy import EntropyConfig


def run_single(cfg_name: str, seed: int, N0: int = 48) -> dict:
    """运行单个配置+种子，返回结果字典。"""
    p = Params()

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

    world = RecursiveWorld(
        N0=N0, n0_active=40, n_colors=6, seed=seed,
        params=p,
        self_encapsulate=True,
        energy_config=energy_cfg,
        entropy_config=entropy_cfg,
    )
    report = world.run(max_layers=6, verbose=False)

    # 收集各层能量/熵信息
    layer_energy = []
    layer_entropy = []
    for layer in world.layers:
        if layer.energy:
            layer_energy.append(layer.energy.summary())
        if layer.entropy:
            layer_entropy.append(layer.entropy.summary())

    result = {
        "config": cfg_name,
        "seed": seed,
        "N0": N0,
        "emergence_depth": world.emergence_depth(),
        "report": report,
        "layer_energy": layer_energy,
        "layer_entropy": layer_entropy,
    }

    # H21-P0a: 检测低能量样本
    if layer_energy:
        final_ratios = [e["budget_ratio"] for e in layer_energy]
        result["mean_energy_ratio"] = float(np.mean(final_ratios))
        result["dead_order_layers"] = sum(1 for e in layer_energy if e.get("is_dead_order", False))
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
    # 预期: low_budget 的 dead_order_layers > 0
    for c in ["low_budget", "with_energy", "high_decay"]:
        if c in by_cfg:
            n_dead = sum(r["dead_order_layers"] for r in by_cfg[c])
            n_total = len(by_cfg[c]) * max(len(r["layer_energy"]) for r in by_cfg[c])
            print(f"  H21-P0a [{c}]: {n_dead}/{n_total} layers in dead order")
    eval_out["H21-P0a"] = "see printed stats"

    # H21-P0b: 有能量注入时 flux 维持更久
    for c in configs:
        fluxes = [r["report"][0].get("autonomous_flux", 0.0) for r in by_cfg[c] if r["report"]]
        if fluxes:
            print(f"  H21-P0b [{c}]: mean L0 flux = {np.mean(fluxes):.4f}")
    eval_out["H21-P0b"] = "see printed stats"

    # H21-P0c: 涌现深度与初始能量预算正相关
    depths = {c: [r["emergence_depth"] for r in by_cfg[c]] for c in configs}
    for c in configs:
        print(f"  H21-P0c [{c}]: mean depth = {np.mean(depths[c]):.2f}")
    eval_out["H21-P0c"] = "see printed stats"

    # H21-P0d: 熵产生 > 0 (不可逆)
    for c in configs:
        irr = [r["any_irreversible"] for r in by_cfg[c]]
        print(f"  H21-P0d [{c}]: irreversible = {sum(x is True for x in irr)}/{len(irr)}")
    eval_out["H21-P0d"] = "see printed stats"

    return eval_out


def main():
    configs = ["baseline", "with_energy", "low_budget", "high_decay"]
    seeds = range(8)  # 0-7
    N0 = 48

    all_results = []
    for cfg_name in configs:
        for seed in seeds:
            print(f"  Running {cfg_name} seed={seed}...")
            try:
                result = run_single(cfg_name, seed, N0)
                all_results.append(result)
                depth = result["emergence_depth"]
                flux = result["report"][0].get("autonomous_flux", 0.0) if result["report"] else 0.0
                print(f"    depth={depth} flux={flux:.4f}")
            except Exception as e:
                print(f"    ERROR: {e}")
                all_results.append({"config": cfg_name, "seed": seed, "error": str(e)})

    # 保存结果
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "exp_200_p0_energy_baseline.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    # 评估假设
    print("\n=== Hypothesis Evaluation ===")
    evaluate_hypotheses(all_results)


if __name__ == "__main__":
    main()
