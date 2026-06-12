"""exp_200_v2 — Phase 21 P0: 能量硬约束验证实验。

验证 H21-P0a: 能量预算不足时涌现深度降低
验证 H21-P0b: 能量衰减率影响密封时间
验证 H21-P0c: 死秩序在能量耗尽时发生
验证 H21-P0d: 能量注入能重启自指链

Configs:
  baseline:   无能量系统 (energy_cfg=None)
  low_budget: 能量预算 30 (N0=24 下预期深度 1-2)
  high_decay: 衰减率 0.05 (能量快速耗尽)
  injection:   周期性注入 (每 500 步注入 20)
"""

import sys
import json
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from diffsim.energy_v2 import EnergyManager, EnergyConfig
from diffsim.world_v2 import RecursiveWorld

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def run_config(config_name, N0, seed, energy_cfg=None, max_layers=10, verbose=False):
    """运行单个配置，返回结果字典。"""
    world = RecursiveWorld(N0=N0, seed=seed, energy_cfg=energy_cfg)
    result = world.run(max_layers=max_layers, verbose=verbose)

    # 提取能量历史
    energy_info = {}
    if energy_cfg and world.layers:
        for i, layer in enumerate(world.layers):
            if layer.energy:
                energy_info[f"L{i}"] = layer.energy.get_summary()

    return {
        "config": config_name,
        "N0": N0,
        "seed": seed,
        "depth": result["depth"],
        "n_layers": result["n_layers"],
        "energy": energy_info,
    }


def main():
    N0 = 24
    seeds = [42, 142, 242, 342, 442, 542, 642, 742]
    configs = {}

    # baseline: 无能量系统
    configs["baseline"] = {"energy_cfg": None}

    # low_budget: 初始能量 30 (远低于 N0=24 密封所需)
    configs["low_budget"] = {
        "energy_cfg": EnergyConfig(initial_budget=30.0, decay_rate=0.01)
    }

    # high_decay: 高衰减率
    configs["high_decay"] = {
        "energy_cfg": EnergyConfig(initial_budget=100.0, decay_rate=0.05)
    }

    # injection: 周期性注入（通过 custom callback 实现）
    # 简化：暂不包含 injection，留待 P1

    all_results = []

    for cfg_name, cfg_opts in configs.items():
        print(f"\n=== Config: {cfg_name} ===")
        for seed in seeds:
            result = run_config(cfg_name, N0, seed, **cfg_opts)
            all_results.append(result)
            print(f"  seed={seed}: depth={result['depth']}, layers={result['n_layers']}")

    # 汇总分析
    print("\n=== Summary ===")
    for cfg_name in configs:
        cfg_results = [r for r in all_results if r["config"] == cfg_name]
        depths = [r["depth"] for r in cfg_results]
        print(f"{cfg_name}: mean_depth={np.mean(depths):.2f}, "
              f"min={np.min(depths)}, max={np.max(depths)}")

    # 保存结果
    import time; ts = int(time.time())
    output_path = RESULTS_DIR / f"exp_200_v2_{ts}.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
