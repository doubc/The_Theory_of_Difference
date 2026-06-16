#!/usr/bin/env python3
"""exp_216_phase24_p0_gravity_baseline.py — Phase 24 P0: 跨层级引力调制基线实验

理论假设:
H24-0a: 引力调制提升涌现深度 (gravity > no-gravity)
H24-0b: 引力调制提升 L1 flux (gravity > no-gravity)
H24-0c: 引力调制加速密封 (gravity 密封步数 < no-gravity)
H24-0d: 引力调制增加组织质量 (gravity 组织质量 > no-gravity)

实验设计:
- G1: 基线 (无引力, self_encapsulate=True)
- G2: 引力调制 (strength=0.3, source_weight)
- G3: 引力调制 (strength=0.5, all)
- G4: 引力调制 (strength=0.8, all)

每个配置: 10 seeds, N0=48, max_layers=8, max_steps=400
"""

import sys
import os
import json
import numpy as np
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim.world_v2 import RecursiveWorld, Params
from diffsim.energy_v2 import EnergyConfig
from diffsim.cross_layer_gravity import GravityConfig


def run_single(seed: int, gravity_cfg: Optional[GravityConfig] = None, 
               gravity_strength: float = 0.0) -> dict:
    """运行单个模拟。"""
    world = RecursiveWorld(
        N0=48,
        n_colors=6,
        params=Params(max_steps=400),
        energy_cfg=EnergyConfig(injection_rate=10.0),
        seed=seed,
        self_encapsulate=True,
        gravity_cfg=gravity_cfg
    )
    
    result = world.run(max_layers=8, verbose=False)
    
    # 提取关键指标
    layers = result['layers']
    depth = result['depth']
    
    # 计算 L1 flux
    l1_flux = layers[1]['flux'] if len(layers) > 1 else 0.0
    
    # 计算平均密封步数
    seal_steps = [l['steps'] for l in layers if l['sealed']]
    avg_seal_steps = np.mean(seal_steps) if seal_steps else 0.0
    
    # 计算组织质量 (如果有引力场)
    org_mass = 0.0
    if world.gravity:
        summary = world.gravity.get_summary()
        for layer_data in summary['layers'].values():
            org_mass += layer_data['total_mass']
    
    return {
        'seed': seed,
        'depth': depth,
        'n_layers': len(layers),
        'l1_flux': l1_flux,
        'avg_seal_steps': avg_seal_steps,
        'org_mass': org_mass,
        'layers': layers,
        'gravity_summary': world.gravity.get_summary() if world.gravity else None
    }


def main():
    """运行实验。"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', type=int, default=10, help='Number of random seeds')
    args = parser.parse_args()
    
    seeds = list(range(42, 42 + args.seeds))
    
    print(f"Phase 24 P0: Cross-Layer Gravity Baseline Experiment")
    print(f"Seeds: {seeds}")
    print(f"=" * 60)
    
    results = {
        'experiment': 'exp_216_phase24_p0_gravity_baseline',
        'timestamp': datetime.now().isoformat(),
        'parameters': {
            'n_seeds': len(seeds),
            'N0': 48,
            'max_layers': 8,
            'max_steps': 400,
            'energy_injection': 10.0
        },
        'groups': {}
    }
    
    # G1: 基线 (无引力)
    print(f"\\n[G1] Baseline (no gravity)...")
    g1_results = []
    for seed in seeds:
        result = run_single(seed, gravity_cfg=None)
        g1_results.append(result)
        print(f"  Seed {seed}: depth={result['depth']}, l1_flux={result['l1_flux']:.4f}")
    
    results['groups']['G1_baseline'] = {
        'desc': '基线 (无引力)',
        'gravity_strength': 0.0,
        'n_seeds': len(seeds),
        'avg_depth': np.mean([r['depth'] for r in g1_results]),
        'std_depth': np.std([r['depth'] for r in g1_results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in g1_results]),
        'avg_seal_steps': np.mean([r['avg_seal_steps'] for r in g1_results]),
        'avg_org_mass': np.mean([r['org_mass'] for r in g1_results]),
        'results': g1_results
    }
    
    # G2: 引力调制 (strength=0.3, source_weight)
    print(f"\\n[G2] Gravity (strength=0.3, source_weight)...")
    g2_results = []
    gravity_cfg = GravityConfig(gravity_strength=0.3, modulation_mode='source_weight')
    for seed in seeds:
        result = run_single(seed, gravity_cfg=gravity_cfg, gravity_strength=0.3)
        g2_results.append(result)
        print(f"  Seed {seed}: depth={result['depth']}, l1_flux={result['l1_flux']:.4f}")
    
    results['groups']['G2_gravity_0.3'] = {
        'desc': '引力调制 (strength=0.3, source_weight)',
        'gravity_strength': 0.3,
        'n_seeds': len(seeds),
        'avg_depth': np.mean([r['depth'] for r in g2_results]),
        'std_depth': np.std([r['depth'] for r in g2_results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in g2_results]),
        'avg_seal_steps': np.mean([r['avg_seal_steps'] for r in g2_results]),
        'avg_org_mass': np.mean([r['org_mass'] for r in g2_results]),
        'results': g2_results
    }
    
    # G3: 引力调制 (strength=0.5, all)
    print(f"\\n[G3] Gravity (strength=0.5, all)...")
    g3_results = []
    gravity_cfg = GravityConfig(gravity_strength=0.5, modulation_mode='all')
    for seed in seeds:
        result = run_single(seed, gravity_cfg=gravity_cfg, gravity_strength=0.5)
        g3_results.append(result)
        print(f"  Seed {seed}: depth={result['depth']}, l1_flux={result['l1_flux']:.4f}")
    
    results['groups']['G3_gravity_0.5'] = {
        'desc': '引力调制 (strength=0.5, all)',
        'gravity_strength': 0.5,
        'n_seeds': len(seeds),
        'avg_depth': np.mean([r['depth'] for r in g3_results]),
        'std_depth': np.std([r['depth'] for r in g3_results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in g3_results]),
        'avg_seal_steps': np.mean([r['avg_seal_steps'] for r in g3_results]),
        'avg_org_mass': np.mean([r['org_mass'] for r in g3_results]),
        'results': g3_results
    }
    
    # G4: 引力调制 (strength=0.8, all)
    print(f"\\n[G4] Gravity (strength=0.8, all)...")
    g4_results = []
    gravity_cfg = GravityConfig(gravity_strength=0.8, modulation_mode='all')
    for seed in seeds:
        result = run_single(seed, gravity_cfg=gravity_cfg, gravity_strength=0.8)
        g4_results.append(result)
        print(f"  Seed {seed}: depth={result['depth']}, l1_flux={result['l1_flux']:.4f}")
    
    results['groups']['G4_gravity_0.8'] = {
        'desc': '引力调制 (strength=0.8, all)',
        'gravity_strength': 0.8,
        'n_seeds': len(seeds),
        'avg_depth': np.mean([r['depth'] for r in g4_results]),
        'std_depth': np.std([r['depth'] for r in g4_results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in g4_results]),
        'avg_seal_steps': np.mean([r['avg_seal_steps'] for r in g4_results]),
        'avg_org_mass': np.mean([r['org_mass'] for r in g4_results]),
        'results': g4_results
    }
    
    # 假设检验
    g1_depth = results['groups']['G1_baseline']['avg_depth']
    g1_flux = results['groups']['G1_baseline']['avg_l1_flux']
    g3_depth = results['groups']['G3_gravity_0.5']['avg_depth']
    g3_flux = results['groups']['G3_gravity_0.5']['avg_l1_flux']
    
    results['hypotheses'] = {
        'H24-0a': {
            'pass': g3_depth > g1_depth,
            'g1_depth': g1_depth,
            'g3_depth': g3_depth,
            'ratio': g3_depth / g1_depth if g1_depth > 0 else 0
        },
        'H24-0b': {
            'pass': g3_flux > g1_flux,
            'g1_flux': g1_flux,
            'g3_flux': g3_flux,
            'ratio': g3_flux / g1_flux if g1_flux > 0 else 0
        }
    }
    
    # 总结
    print(f"\\n{'=' * 60}")
    print(f"Results Summary:")
    for group_name, group_data in results['groups'].items():
        print(f"  {group_name}: depth={group_data['avg_depth']:.2f}, flux={group_data['avg_l1_flux']:.4f}")
    
    print(f"\\nHypotheses:")
    for h, r in results['hypotheses'].items():
        status = "PASS" if r['pass'] else "FAIL"
        print(f"  {h}: {status}")
    
    # 保存结果
    output_file = f"results/exp_216_phase24_p0_gravity_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs('results', exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\\nResults saved to: {output_file}")


if __name__ == '__main__':
    main()
