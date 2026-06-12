#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""exp_200_v6_phase21_p0_energy_drive.py

Phase 21 P0: 能量驱动涌现深度实验 (v6 — 使用工作版 world.py)

核心假设:
    H21-P0a: 能量预算正比于涌现深度 (budget -> depth)
    H21-P0b: 能量衰减率影响系统持续性 (decay -> depth)
    H21-P0c: 自指(m9)频率正比于 flux (m9_active -> l1_flux)

实验设计:
    4 configs x 8 seeds = 32 runs
    - baseline: 无能量约束
    - high_budget: budget=500, decay=0.005 (充足能量)
    - medium_budget: budget=200, decay=0.01 (中等能量)
    - low_budget: budget=50, decay=0.03 (低能量)

关键区别: 使用 world.py (工作版 RecursiveWorld + self_encapsulate)
而非 world_v2.py (简化版, 无自指封装)
"""

import sys
import os
import json
import time
import numpy as np
from datetime import datetime

# 确保 diffsim 可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim import RecursiveWorld
from diffsim.energy import EnergyConfig, EnergyManager


def run_single(seed, N0, self_encapsulate, energy_config=None, verbose=False):
    """运行单个模拟。"""
    w = RecursiveWorld(
        N0=N0,
        n0_active=max(1, N0 * 5 // 6),
        seed=seed,
        self_encapsulate=self_encapsulate,
        energy_config=energy_config,
    )
    report = w.run(max_layers=8, verbose=verbose)
    depth = w.emergence_depth()

    # 收集每层信息
    layers_info = []
    for r in report:
        info = {
            'layer': r['layer'],
            'N': r['N'],
            'sealed': r['sealed'],
            'flux': r['autonomous_flux'],
            'mode': r.get('mode', 'unknown'),
        }
        if 'energy_final' in r:
            info['energy_final'] = r['energy_final']
            info['energy_ratio'] = r.get('energy_ratio', 0.0)
            info['energy_low'] = r.get('energy_low', False)
        if 'negentropy_final' in r:
            info['negentropy'] = r['negentropy_final']
            info['irreversible'] = r.get('is_irreversible', False)
        layers_info.append(info)

    # L1 flux (关键指标)
    l1_flux = 0.0
    for r in report:
        if r['layer'] == 1:
            l1_flux = r['autonomous_flux']
            break

    # L2+ 涌现率
    l2_emerged = depth >= 3

    return {
        'seed': seed,
        'depth': depth,
        'n_layers': len(report),
        'l1_flux': l1_flux,
        'l2_emerged': l2_emerged,
        'layers': layers_info,
    }


def main():
    seeds = [42, 142, 242, 342, 442, 542, 642, 742]
    N0 = 48

    configs = {
        'baseline': {
            'name': 'no_energy',
            'energy_config': None,
        },
        'high_budget': {
            'name': 'high_budget',
            'energy_config': EnergyConfig(initial_budget=500.0, decay_rate=0.005),
        },
        'medium_budget': {
            'name': 'medium_budget',
            'energy_config': EnergyConfig(initial_budget=200.0, decay_rate=0.01),
        },
        'low_budget': {
            'name': 'low_budget',
            'energy_config': EnergyConfig(initial_budget=50.0, decay_rate=0.03),
        },
    }

    results = {}
    t0 = time.time()

    for cfg_name, cfg in configs.items():
        print(f"\n{'='*60}")
        print(f"Config: {cfg['name']}")
        print(f"{'='*60}")

        runs = []
        for s in seeds:
            r = run_single(
                seed=s,
                N0=N0,
                self_encapsulate=True,
                energy_config=cfg['energy_config'],
                verbose=False,
            )
            runs.append(r)
            print(f"  seed={s:4d} depth={r['depth']} l1_flux={r['l1_flux']:.4f} l2={r['l2_emerged']}")

        # 汇总
        depths = [r['depth'] for r in runs]
        fluxes = [r['l1_flux'] for r in runs]
        l2_rate = sum(1 for r in runs if r['l2_emerged']) / len(runs)

        summary = {
            'config': cfg['name'],
            'mean_depth': float(np.mean(depths)),
            'std_depth': float(np.std(depths)),
            'mean_l1_flux': float(np.mean(fluxes)),
            'std_l1_flux': float(np.std(fluxes)),
            'l2_emergence_rate': l2_rate,
            'n_seeds': len(seeds),
        }
        results[cfg_name] = {'summary': summary, 'runs': runs}

        print(f"\n  Summary: depth={summary['mean_depth']:.2f} +/- {summary['std_depth']:.2f}")
        print(f"           l1_flux={summary['mean_l1_flux']:.4f} +/- {summary['std_l1_flux']:.4f}")
        print(f"           L2 emergence rate = {summary['l2_emergence_rate']*100:.0f}%")

    # 假设检验
    print(f"\n{'='*60}")
    print("HYPOTHESIS TESTING")
    print(f"{'='*60}")

    baseline_d = np.mean([r['depth'] for r in results['baseline']['runs']])
    high_d = np.mean([r['depth'] for r in results['high_budget']['runs']])
    med_d = np.mean([r['depth'] for r in results['medium_budget']['runs']])
    low_d = np.mean([r['depth'] for r in results['low_budget']['runs']])

    baseline_f = np.mean([r['l1_flux'] for r in results['baseline']['runs']])
    high_f = np.mean([r['l1_flux'] for r in results['high_budget']['runs']])
    med_f = np.mean([r['l1_flux'] for r in results['medium_budget']['runs']])
    low_f = np.mean([r['l1_flux'] for r in results['low_budget']['runs']])

    # H21-P0a: 能量预算正比于涌现深度
    depth_order = low_d <= med_d <= high_d
    print(f"\nH21-P0a (budget ~ depth):")
    print(f"  low={low_d:.2f}, med={med_d:.2f}, high={high_d:.2f}, baseline={baseline_d:.2f}")
    if depth_order:
        print(f"  VERDICT: PASS (monotonic relationship confirmed)")
    else:
        print(f"  VERDICT: {'PASS' if high_d > low_d else 'FAIL'} (partial monotonicity)")

    # H21-P0b: 能量衰减率影响持续性
    # 预期: low_budget (high decay) depth < high_budget depth
    print(f"\nH21-P0b (decay -> persistence):")
    print(f"  low_budget(50,0.03)={low_d:.2f} vs high_budget(500,0.005)={high_d:.2f}")
    if low_d < high_d:
        print(f"  VERDICT: PASS (low budget -> lower depth)")
    else:
        print(f"  VERDICT: FAIL (no depth difference)")

    # H21-P0c: 自指存在时 flux > 0
    print(f"\nH21-P0c (self-reference -> flux > 0):")
    print(f"  baseline l1_flux={baseline_f:.4f}")
    if baseline_f > 0.01:
        print(f"  VERDICT: PASS (flux={baseline_f:.4f} > 0.01, self-reference works)")
    else:
        print(f"  VERDICT: FAIL (flux too low)")

    # 保存结果
    elapsed = time.time() - t0
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'results',
        f'exp_200_v6_{timestamp}.json'
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 准备可序列化的结果
    serializable = {}
    for k, v in results.items():
        serializable[k] = {
            'summary': v['summary'],
            'runs': v['runs'],
        }

    with open(out_path, 'w', encoding='utf-8') as fp:
        json.dump(serializable, fp, indent=2, ensure_ascii=False, default=str)

    print(f"\nResults saved to: {out_path}")
    print(f"Total time: {elapsed:.1f}s")


if __name__ == '__main__':
    main()
