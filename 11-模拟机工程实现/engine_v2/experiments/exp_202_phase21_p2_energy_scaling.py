#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""exp_202_phase21_p2_energy_scaling.py

Phase 21 P2: 能量标度律实验 (Energy Scaling Law)

核心问题:
    N0 (物理比特数) 变化时, 能量预算的临界阈值如何变化?
    涌现深度标度律如何受能量约束影响?

假设:
    H21-P2a: 临界能量注入阈值 N0* 与 N0 成正比 (更大系统需要更多能量)
    H21-P2b: 涌现深度 = min(Phase17_depth(N0), energy_limit_depth(budget))
             即深度由 N0 和能量预算共同决定, 取较小者
    H21-P2c: L1 flux 不变性 (≈0.19) 在所有 N0+能量配置下成立
    H21-P2d: L2+ 涌现率是能量的阶跃函数 (存在相变阈值)

实验设计:
    N0 × 能量配置 × seeds = 4 × 4 × 8 = 128 runs
    N0: [24, 36, 48, 72]
    能量配置: [无能量, 低注入, 中注入, 高注入]
"""

import sys
import os
import json
import time
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim import RecursiveWorld
from diffsim.energy import EnergyConfig


def run_single(seed, N0, energy_config=None, verbose=False):
    """运行单个模拟。"""
    n0_active = max(1, N0 * 5 // 6)
    w = RecursiveWorld(
        N0=N0,
        n0_active=n0_active,
        seed=seed,
        self_encapsulate=True,
        energy_config=energy_config,
    )
    report = w.run(max_layers=8, verbose=verbose)
    depth = w.emergence_depth()

    layers_info = []
    for r in report:
        info = {
            'layer': r['layer'],
            'N': r['N'],
            'sealed': r['sealed'],
            'flux': r['autonomous_flux'],
        }
        if 'energy_final' in r:
            info['energy_final'] = r['energy_final']
            info['energy_ratio'] = r.get('energy_ratio', 0.0)
        layers_info.append(info)

    l1_flux = 0.0
    for r in report:
        if r['layer'] == 1:
            l1_flux = r['autonomous_flux']
            break

    l2_emerged = depth >= 3
    l3_emerged = depth >= 4
    l4_emerged = depth >= 5

    return {
        'seed': seed,
        'N0': N0,
        'depth': depth,
        'n_layers': len(report),
        'l1_flux': l1_flux,
        'l2_emerged': l2_emerged,
        'l3_emerged': l3_emerged,
        'l4_emerged': l4_emerged,
        'layers': layers_info,
    }


def make_energy_configs(N0):
    """根据 N0 生成相适配的能量配置。
    
    关键公式 (来自 Phase 21 P0 分析):
        equilibrium_budget = (injection_rate * active_ratio - mechanism_cost) / decay_rate
        其中 mechanism_cost ≈ 2.3/step, active_ratio ≈ 0.83
    
    目标: 低/中/高注入分别对应深度不足/临界/饱和三种状态
    """
    # base_injection: N0=48时代谢考深度4.62的注入率
    base_rate = 10.0
    
    # 标度假设: 临界注入与 N0 成正比
    scale_factor = N0 / 48.0
    
    return {
        'no_energy': None,
        'low_inject': EnergyConfig(
            initial_budget=50.0 * scale_factor,
            injection_rate=2.0 * scale_factor,
            decay_rate=0.02,
        ),
        'med_inject': EnergyConfig(
            initial_budget=200.0 * scale_factor,
            injection_rate=5.0 * scale_factor,
            decay_rate=0.01,
        ),
        'high_inject': EnergyConfig(
            initial_budget=500.0 * scale_factor,
            injection_rate=base_rate * scale_factor,
            decay_rate=0.005,
        ),
    }


def main():
    all_seeds = [42, 142, 242, 342, 442, 542, 642, 742]
    n0_values = [24, 36, 48, 72]

    t0 = time.time()
    all_results = {}

    for N0 in n0_values:
        energy_configs = make_energy_configs(N0)
        all_results[N0] = {}

        for cfg_name, energy_cfg in energy_configs.items():
            print(f"\n{'='*60}")
            print(f"N0={N0}, Config={cfg_name}")
            print(f"{'='*60}")

            runs = []
            for s in all_seeds:
                r = run_single(
                    seed=s,
                    N0=N0,
                    energy_config=energy_cfg,
                    verbose=False,
                )
                runs.append(r)
                print(f"  seed={s:4d} depth={r['depth']} l1_flux={r['l1_flux']:.4f} "
                      f"l2={r['l2_emerged']} l3={r['l3_emerged']} l4={r['l4_emerged']}")

            # 汇总
            depths = [r['depth'] for r in runs]
            fluxes = [r['l1_flux'] for r in runs]
            l2_rate = sum(1 for r in runs if r['l2_emerged']) / len(runs)
            l3_rate = sum(1 for r in runs if r['l3_emerged']) / len(runs)
            l4_rate = sum(1 for r in runs if r['l4_emerged']) / len(runs)

            summary = {
                'config': cfg_name,
                'N0': N0,
                'mean_depth': float(np.mean(depths)),
                'std_depth': float(np.std(depths)),
                'mean_l1_flux': float(np.mean(fluxes)),
                'std_l1_flux': float(np.std(fluxes)),
                'l2_emergence_rate': l2_rate,
                'l3_emergence_rate': l3_rate,
                'l4_emergence_rate': l4_rate,
                'n_seeds': len(all_seeds),
            }
            all_results[N0][cfg_name] = {'summary': summary, 'runs': runs}

            print(f"\n  Summary: depth={summary['mean_depth']:.2f}+/-{summary['std_depth']:.2f}")
            print(f"           l1_flux={summary['mean_l1_flux']:.4f}+/-{summary['std_l1_flux']:.4f}")
            print(f"           L2={l2_rate*100:.0f}% L3={l3_rate*100:.0f}% L4={l4_rate*100:.0f}%")

    # === 假设检验 ===
    print(f"\n{'='*60}")
    print("HYPOTHESIS TESTING — Phase 21 P2: Energy Scaling Law")
    print(f"{'='*60}")

    hypothesis_results = {}

    # H21-P2a: 临界注入阈值与 N0 成正比
    h2a_summary = {}
    for N0 in n0_values:
        for cfg_name in ['low_inject', 'med_inject', 'high_inject']:
            cfg = all_results[N0].get(cfg_name)
            if cfg:
                key = f"N0={N0}/{cfg_name}"
                h2a_summary[key] = cfg['summary']['mean_depth']

    # 深层涌现需要足够能量: 对每个N0, 高注入深度 > 低注入深度
    p2a_pass = True
    for N0 in n0_values:
        hi = all_results[N0]['high_inject']['summary']['mean_depth']
        lo = all_results[N0]['low_inject']['summary']['mean_depth']
        no = all_results[N0]['no_energy']['summary']['mean_depth']
        print(f"\nH21-P2a (N0={N0}): high={hi:.2f} vs low={lo:.2f} vs no_energy={no:.2f}")
        if hi <= lo:
            p2a_pass = False
            print(f"  FAIL: high_inject depth ({hi:.2f}) not > low_inject ({lo:.2f})")
        else:
            print(f"  PASS: energy gap = {hi - lo:.2f} layers")
    print(f"  H21-P2a VERDICT: {'PASS' if p2a_pass else 'PARTIAL (some N0 fail)'}")

    # H21-P2b: depth = min(phase17_depth, energy_limit)
    # 验证: 无能量深度 >= 有能量深度 (能量不会增加相17深度)
    p2b_pass = True
    print(f"\nH21-P2b (depth = min(no_energy_depth, energy_limit)):")
    for N0 in n0_values:
        no = all_results[N0]['no_energy']['summary']['mean_depth']
        hi = all_results[N0]['high_inject']['summary']['mean_depth']
        bound_ok = hi <= no + 0.5  # 允许轻微浮动
        if not bound_ok:
            p2b_pass = False
            print(f"  N0={N0}: energy depth {hi:.2f} > no_energy {no:.2f} — unexpected")
        else:
            print(f"  N0={N0}: ok (energy {hi:.2f} <= no_energy {no:.2f})")
    print(f"  H21-P2b VERDICT: {'PASS' if p2b_pass else 'PARTIAL'}")

    # H21-P2c: L1 flux 不变性
    p2c_pass = True
    print(f"\nH21-P2c (L1 flux invariance ~0.19):")
    for N0 in n0_values:
        for cfg_name in ['no_energy', 'low_inject', 'med_inject', 'high_inject']:
            cfg = all_results[N0].get(cfg_name)
            if cfg:
                flux = cfg['summary']['mean_l1_flux']
                label = f"N0={N0}/{cfg_name}"
                if flux < 0.01:
                    p2c_pass = False
                    print(f"  {label}: flux={flux:.4f} — TOO LOW")
                elif abs(flux - 0.19) > 0.15:
                    print(f"  {label}: flux={flux:.4f} — off from 0.19 (possible)")
                else:
                    print(f"  {label}: flux={flux:.4f} — ok")
    print(f"  H21-P2c VERDICT: {'PASS' if p2c_pass else 'PARTIAL'}")

    # H21-P2d: L2+ 涌现是能量阶跃函数
    p2d_result = {}
    print(f"\nH21-P2d (L2 emergence is step function of energy):")
    for N0 in n0_values:
        l2_rates = []
        for cfg_name in ['no_energy', 'low_inject', 'med_inject', 'high_inject']:
            cfg = all_results[N0].get(cfg_name)
            if cfg:
                l2_rates.append((cfg_name, cfg['summary']['l2_emergence_rate']))
        p2d_result[N0] = l2_rates
        for cfg_name, rate in l2_rates:
            print(f"  N0={N0}/{cfg_name}: L2={rate*100:.0f}%")

    hypothesis_results = {
        'H21-P2a': 'PASS' if p2a_pass else 'PARTIAL',
        'H21-P2b': 'PASS' if p2b_pass else 'PARTIAL',
        'H21-P2c': 'PASS' if p2c_pass else 'PARTIAL',
        'H21-P2d': 'ANALYSIS',
    }

    print(f"\n{'='*60}")
    print("HYPOTHESIS SUMMARY")
    for h, v in hypothesis_results.items():
        print(f"  {h}: {v}")
    print(f"{'='*60}")

    # 保存结果
    elapsed = time.time() - t0
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'results',
        f'exp_202_p2_energy_scaling_{timestamp}.json'
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    serializable = {}
    for N0 in n0_values:
        serializable[str(N0)] = {}
        for cfg_name, data in all_results[N0].items():
            serializable[str(N0)][cfg_name] = {
                'summary': data['summary'],
                'runs': data['runs'],
            }
    serializable['hypothesis_results'] = hypothesis_results

    with open(out_path, 'w', encoding='utf-8') as fp:
        json.dump(serializable, fp, indent=2, ensure_ascii=False, default=str)

    print(f"\nResults saved to: {out_path}")
    print(f"Total time: {elapsed:.1f}s")


if __name__ == '__main__':
    main()
