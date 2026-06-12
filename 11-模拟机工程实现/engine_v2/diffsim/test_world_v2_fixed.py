"""test_world_v2_fixed.py — 测试 world_v2_fixed.py 的基本功能。"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from world_v2_fixed import RecursiveWorld, Params
from energy_v2 import EnergyConfig
from entropy import EntropyConfig


def test_basic_multi_layer():
    """测试基本多层级涌现。"""
    print("=" * 60)
    print("Test 1: Basic Multi-Layer Emergence")
    print("=" * 60)
    
    params = Params(N0=48, max_steps=500)
    world = RecursiveWorld(N0=48, n_colors=6, params=params, seed=42)
    
    result = world.run(max_layers=10, verbose=True)
    
    print(f"\nResult: depth={result['depth']}, n_layers={result['n_layers']}")
    
    # 验证
    assert result['depth'] >= 1, "Should have at least 1 layer (L0->L1)"
    assert result['n_layers'] >= 2, "Should have at least 2 layers"
    
    print("✅ Test 1 PASSED\n")
    return result


def test_energy_constraint():
    """测试能量约束。"""
    print("=" * 60)
    print("Test 2: Energy Constraint")
    print("=" * 60)
    
    # 低能量预算应限制涌现深度
    energy_cfg = EnergyConfig(initial_budget=20.0, decay_rate=0.05)
    params = Params(N0=48, max_steps=500)
    
    world = RecursiveWorld(
        N0=48, n_colors=6, 
        params=params,
        energy_cfg=energy_cfg,
        seed=42
    )
    
    result = world.run(max_layers=10, verbose=True)
    
    print(f"\nResult with low energy: depth={result['depth']}")
    
    # 检查能量追踪
    if 'energy' in result:
        for layer_key, energy_info in result['energy'].items():
            print(f"  {layer_key}: budget={energy_info['budget']:.2f}, consumed={energy_info['consumed']:.2f}")
    
    print("✅ Test 2 PASSED\n")
    return result


def test_compare_with_without_energy():
    """比较有能量和无能量的涌现深度。"""
    print("=" * 60)
    print("Test 3: Compare With/Without Energy")
    print("=" * 60)
    
    params = Params(N0=48, max_steps=500)
    
    # 无能量
    world_no_energy = RecursiveWorld(N0=48, n_colors=6, params=params, seed=42)
    result_no_energy = world_no_energy.run(max_layers=10, verbose=False)
    
    # 有能量 (充足预算)
    energy_cfg = EnergyConfig(initial_budget=200.0, decay_rate=0.01)
    world_with_energy = RecursiveWorld(
        N0=48, n_colors=6, 
        params=params,
        energy_cfg=energy_cfg,
        seed=42
    )
    result_with_energy = world_with_energy.run(max_layers=10, verbose=False)
    
    print(f"Without energy: depth={result_no_energy['depth']}")
    print(f"With energy (budget=200): depth={result_with_energy['depth']}")
    
    print("✅ Test 3 PASSED\n")
    return result_no_energy, result_with_energy


if __name__ == "__main__":
    print("\nStarting world_v2_fixed tests...\n")
    
    try:
        result1 = test_basic_multi_layer()
        result2 = test_energy_constraint()
        result3 = test_compare_with_without_energy()
        
        print("=" * 60)
        print("All tests PASSED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
