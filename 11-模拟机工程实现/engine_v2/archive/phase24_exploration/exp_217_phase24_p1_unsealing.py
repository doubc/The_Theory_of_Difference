#!/usr/bin/env python3
"""exp_217_phase24_p1_unsealing.py — Phase 24 P1: 解封机制实验

理论假设:
H24-1a: 解封机制增加涌现深度 (unsealing > no-unsealing)
H24-1b: 解封机制增加 L1 flux (unsealing > no-unsealing)
H24-1c: 解封机制增加系统探索的状态空间

实验设计:
- G1: 基线 (无解封, self_encapsulate=True)
- G2: 解封机制 (threshold=0.3, probability=0.5)
- G3: 解封机制 (threshold=0.2, probability=0.3) - 更保守
- G4: 解封机制 (threshold=0.4, probability=0.7) - 更激进

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
from diffsim.unsealing import UnsealingConfig


def run_single(seed: int, unsealing_cfg: Optional[UnsealingConfig] = None) -> dict:
    """运行单个模拟。"""
    world = RecursiveWorld(
        N0=48,
        n_colors=6,
        params=Params(max_steps=400),
        energy_cfg=EnergyConfig(injection_rate=10.0),
        seed=seed,
        self_encapsulate=True,
        unsealing_cfg=unsealing_cfg
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
    
    # 获取解封信息
    unseal_summary = world.unsealing.get_summary() if world.unsealing else None
    total_unseals = sum(l['unseal_count'] for l in unseal_summary['layers'].values()) if unseal_summary else 0
    
    return {
        'seed': seed,
        'depth': depth,
        'n_layers': len(layers),
        'l1_flux': l1_flux,
        'avg_seal_steps': avg_seal_steps,
        'total_unseals': total_unseals,
        'layers': layers,
        'unseal_summary': unseal_summary
    }


def main():
    """运行实验。"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', type=int, default=10, help='Number of random seeds')
    args = parser.parse_args()
    
    seeds = list(range(42, 42 + args.seeds))
    
    print(f"Phase 24 P1: Unsealing Mechanism Experiment")
    print(f"Seeds: {seeds}")
    print(f"=" * 60)
    
    results = {
        'experiment': 'exp_217_phase24_p1_unsealing',
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
    
    # G1: 基线 (无解封)
    print(f"\n[G1] Baseline (no unsealing)...")
    g1_results = []
    for seed in seeds:
        result = run_single(seed, unsealing_cfg=None)
        g1_results.append(result)
        print(f"  Seed {seed}: depth={result['depth']}, l1_flux={result['l1_flux']:.4f}, unseals={result['total_unseals']}")
    
    results['groups']['G1_baseline'] = {
        'desc': '基线 (无解封)',
        'n_seeds': len(seeds),
        'avg_depth': np.mean([r['depth'] for r in g1_results]),
        'std_depth': np.std([r['depth'] for r in g1_results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in g1_results]),
        'avg_seal_steps': np.mean([r['avg_seal_steps'] for r in g1_results]),
        'avg_unseals': np.mean([r['total_unseals'] for r in g1_results]),
        'results': g1_results
    }
    
    # G2: 解封机制 (threshold=0.3, probability=0.5)
    print(f"\n[G2] Unsealing (threshold=0.3, probability=0.5)...")
    g2_results = []
    unsealing_cfg = UnsealingConfig(
        change_rate_threshold=0.3,
        unseal_probability_factor=0.5,
        min_seal_duration=50,
        unfreeze_fraction=0.3
    )
    for seed in seeds:
        result = run_single(seed, unsealing_cfg=unsealing_cfg)
        g2_results.append(result)
        print(f"  Seed {seed}: depth={result['depth']}, l1_flux={result['l1_flux']:.4f}, unseals={result['total_unseals']}")
    
    results['groups']['G2_unseal_0.3'] = {
        'desc': '解封机制 (threshold=0.3, probability=0.5)',
        'n_seeds': len(seeds),
        'avg_depth': np.mean([r['depth'] for r in g2_results]),
        'std_depth': np.std([r['depth'] for r in g2_results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in g2_results]),
        'avg_seal_steps': np.mean([r['avg_seal_steps'] for r in g2_results]),
        'avg_unseals': np.mean([r['total_unseals'] for r in g2_results]),
        'results': g2_results
    }
    
    # G3: 解封机制 (threshold=0.2, probability=0.3) - 更保守
    print(f"\n[G3] Unsealing (threshold=0.2, probability=0.3)...")
    g3_results = []
    unsealing_cfg = UnsealingConfig(
        change_rate_threshold=0.2,
        unseal_probability_factor=0.3,
        min_seal_duration=50,
        unfreeze_fraction=0.2
    )
    for seed in seeds:
        result = run_single(seed, unsealing_cfg=unsealing_cfg)
        g3_results.append(result)
        print(f"  Seed {seed}: depth={result['depth']}, l1_flux={result['l1_flux']:.4f}, unseals={result['total_unseals']}")
    
    results['groups']['G3_unseal_0.2'] = {
        'desc': '解封机制 (threshold=0.2, probability=0.3) - 保守',
        'n_seeds': len(seeds),
        'avg_depth': np.mean([r['depth'] for r in g3_results]),
        'std_depth': np.std([r['depth'] for r in g3_results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in g3_results]),
        'avg_seal_steps': np.mean([r['avg_seal_steps'] for r in g3_results]),
        'avg_unseals': np.mean([r['total_unseals'] for r in g3_results]),
        'results': g3_results
    }
    
    # G4: 解封机制 (threshold=0.4, probability=0.7) - 更激进
    print(f"\n[G4] Unsealing (threshold=0.4, probability=0.7)...")
    g4_results = []
    unsealing_cfg = UnsealingConfig(
        change_rate_threshold=0.4,
        unseal_probability_factor=0.7,
        min_seal_duration=30,
        unfreeze_fraction=0.4
    )
    for seed in seeds:
        result = run_single(seed, unsealing_cfg=unsealing_cfg)
        g4_results.append(result)
        print(f"  Seed {seed}: depth={result['depth']}, l1_flux={result['l1_flux']:.4f}, unseals={result['total_unseals']}")
    
    results['groups']['G4_unseal_0.4'] = {
        'desc': '解封机制 (threshold=0.4, probability=0.7) - 激进',
        'n_seeds': len(seeds),
        'avg_depth': np.mean([r['depth'] for r in g4_results]),
        'std_depth': np.std([r['depth'] for r in g4_results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in g4_results]),
        'avg_seal_steps': np.mean([r['avg_seal_steps'] for r in g4_results]),
        'avg_unseals': np.mean([r['total_unseals'] for r in g4_results]),
        'results': g4_results
    }
    
    # 假设检验
    g1_depth = results['groups']['G1_baseline']['avg_depth']
    g1_flux = results['groups']['G1_baseline']['avg_l1_flux']
    g2_depth = results['groups']['G2_unseal_0.3']['avg_depth']
    g2_flux = results['groups']['G2_unseal_0.3']['avg_l1_flux']
    
    results['hypotheses'] = {
        'H24-1a': {
            'pass': g2_depth > g1_depth,
            'g1_depth': g1_depth,
            'g2_depth': g2_depth,
            'ratio': g2_depth / g1_depth if g1_depth > 0 else 0
        },
        'H24-1b': {
            'pass': g2_flux > g1_flux,
            'g1_flux': g1_flux,
            'g2_flux': g2_flux,
            'ratio': g2_flux / g1_flux if g1_flux > 0 else 0
        }
    }
    
    # 总结
    print(f"\n{'=' * 60}")
    print(f"Results Summary:")
    for group_name, group_data in results['groups'].items():
        print(f"  {group_name}: depth={group_data['avg_depth']:.2f}, flux={group_data['avg_l1_flux']:.4f}, unseals={group_data['avg_unseals']:.1f}")
    
    print(f"\nHypotheses:")
    for h, r in results['hypotheses'].items():
        status = "PASS" if r['pass'] else "FAIL"
        print(f"  {h}: {status}")
    
    # 保存结果
    output_file = f"results/exp_217_phase24_p1_unsealing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs('results', exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_file}")


if __name__ == '__main__':
    main()
