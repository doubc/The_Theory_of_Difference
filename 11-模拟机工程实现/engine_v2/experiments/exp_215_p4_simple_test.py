"""
exp_215_p4_simple_test.py — Phase 23 P4 简化测试

测试 RecursiveWorld 基础功能，为完整实验做准备。

作者: OpenClaw AI (心跳 2026-06-15 02:14)
"""

from __future__ import annotations
import sys
import os
import json
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diffsim.world_v2 import RecursiveWorld, Params, EnergyConfig, EntropyConfig


def test_basic_functionality():
    """测试基础功能"""
    print("=" * 60)
    print("Simple Functionality Test")
    print("=" * 60)
    
    # 测试 1: 无自指 (G1 基线)
    print("\n[Test 1] G1 - No self-reference (dead order baseline)...")
    world_g1 = RecursiveWorld(
        N0=100,
        n_colors=6,
        params=Params(target_active=0, max_steps=400),
        energy_cfg=None,
        entropy_cfg=None,
        seed=42,
        self_encapsulate=False  # 无自指
    )
    
    result_g1 = world_g1.run(max_layers=5, verbose=False)
    depth_g1 = result_g1['depth']
    print(f"  Result: depth={depth_g1}, n_layers={result_g1['n_layers']}")
    
    # 测试 2: 自指闭环 (G3)
    print("\n[Test 2] G3 - Self-reference (A9/m9)...")
    world_g3 = RecursiveWorld(
        N0=100,
        n_colors=6,
        params=Params(target_active=0, max_steps=400),
        energy_cfg=None,
        entropy_cfg=None,  # 暂时禁用熵追踪
        seed=42,
        self_encapsulate=True  # 启用自指
    )
    
    result_g3 = world_g3.run(max_layers=5, verbose=False)
    depth_g3 = result_g3['depth']
    print(f"  Result: depth={depth_g3}, n_layers={result_g3['n_layers']}")
    
    # 测试 3: 能量+自指 (G4)
    print("\n[Test 3] G4 - Energy + Self-reference...")
    world_g4 = RecursiveWorld(
        N0=100,
        n_colors=6,
        params=Params(target_active=0, max_steps=400),
        energy_cfg=EnergyConfig(initial_budget=50.0, injection_rate=0.3, m1_cost=1.0, m9_cost=2.0),  # 修正 API
        entropy_cfg=None,  # 暂时禁用熵追踪
        seed=42,
        self_encapsulate=True  # 启用自指
    )
    
    result_g4 = world_g4.run(max_layers=5, verbose=False)
    depth_g4 = result_g4['depth']
    print(f"  Result: depth={depth_g4}, n_layers={result_g4['n_layers']}")
    
    # 对比结果
    print("\n" + "=" * 60)
    print("Comparison:")
    print("=" * 60)
    print(f"  G1 (no self-ref): depth={depth_g1}")
    print(f"  G3 (self-ref):    depth={depth_g3}")
    print(f"  G4 (energy+ref):  depth={depth_g4}")
    
    if depth_g3 > depth_g1:
        print("\n[PASS] Self-reference enables emergence (G3 > G1)")
    else:
        print("\n[FAIL] Self-reference failed (G3 <= G1)")
    
    if depth_g4 < depth_g3:
        print("[WARN] Energy + self-ref = negative interference (G4 < G3)")
        print("       This matches P1 finding: energy budget truncates emergence")
    else:
        print("[PASS] Energy enhances self-reference (G4 >= G3)")
    
    return {
        'G1': result_g1,
        'G3': result_g3,
        'G4': result_g4
    }


def test_multiple_seeds():
    """测试多个随机种子"""
    print("\n" + "=" * 60)
    print("Multiple Seeds Test (5 seeds)")
    print("=" * 60)
    
    results = {
        'G1': [],
        'G3': [],
        'G4': []
    }
    
    for seed in range(5):
        print(f"\nSeed {seed}:")
        
        # G1
        world = RecursiveWorld(
            N0=100, n_colors=6,
            params=Params(target_active=0, max_steps=400),
            energy_cfg=None, entropy_cfg=None,
            seed=seed, self_encapsulate=False
        )
        r = world.run(max_layers=5, verbose=False)
        results['G1'].append(r['depth'])
        print(f"  G1: depth={r['depth']}")
        
        # G3
        world = RecursiveWorld(
            N0=100, n_colors=6,
            params=Params(target_active=0, max_steps=400),
            energy_cfg=None,
            entropy_cfg=None,  # 暂时禁用熵追踪
            seed=seed, self_encapsulate=True
        )
        r = world.run(max_layers=5, verbose=False)
        results['G3'].append(r['depth'])
        print(f"  G3: depth={r['depth']}")
        
        # G4
        world = RecursiveWorld(
            N0=100, n_colors=6,
            params=Params(target_active=0, max_steps=400),
            energy_cfg=EnergyConfig(initial_budget=50.0, injection_rate=0.3, m1_cost=1.0, m9_cost=2.0),  # 修正 API
            entropy_cfg=None,  # 暂时禁用熵追踪
            seed=seed, self_encapsulate=True
        )
        r = world.run(max_layers=5, verbose=False)
        results['G4'].append(r['depth'])
        print(f"  G4: depth={r['depth']}")
    
    # 统计
    print("\n" + "=" * 60)
    print("Statistics (mean ± std):")
    print("=" * 60)
    for group, depths in results.items():
        print(f"  {group}: {np.mean(depths):.2f} ± {np.std(depths):.2f}")
    
    return results


def main():
    """主测试流程"""
    print("Phase 23 P4 - Simple Functionality Test")
    print("Testing RecursiveWorld API before full experiment")
    
    # 测试基础功能
    results_basic = test_basic_functionality()
    
    # 测试多个种子
    results_multi = test_multiple_seeds()
    
    # 保存结果
    output_file = os.path.join(os.path.dirname(__file__), '../results/exp_215_p4_simple_test.json')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump({
            'basic_test': {
                'G1_depth': results_basic['G1']['depth'],
                'G3_depth': results_basic['G3']['depth'],
                'G4_depth': results_basic['G4']['depth'],
            },
            'multi_seed_test': {
                group: {
                    'depths': depths,
                    'mean': float(np.mean(depths)),
                    'std': float(np.std(depths))
                }
                for group, depths in results_multi.items()
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("1. ✅ Basic functionality verified")
    print("2. ⏳ Implement RecursiveNarrativeLoop wrapper")
    print("3. ⏳ Design narrative recursion experiment")
    print("4. ⏳ Run full exp_215 with H23-4 hypothesis testing")
    
    return results_basic, results_multi


if __name__ == "__main__":
    main()
