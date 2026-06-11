"""test_exp_192_v2.py — 测试 exp_192 v2 的动态资源池实现."""

import sys
import os

# 添加 diffsim 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from diffsim.world import RecursiveWorld, Params
from diffsim.core import DifferenceField
import numpy as np

def test_basic_chain():
    """测试单条链的基本功能。"""
    print("="*60)
    print("Test: Basic Chain Functionality")
    print("="*60)
    
    # 创建世界 (使用正确的 API)
    world = RecursiveWorld(
        N0=48,
        n0_active=40,
        n_colors=6,
        seed=42,
    )
    
    # 检查 API
    print(f"\nWorld created: {world}")
    print(f"World attributes (first 10): {dir(world)[:10]}...")
    
    # 运行世界
    try:
        print(f"\nRunning world.run(max_layers=6)...")
        report = world.run(max_layers=6, verbose=False)
        depth = world.emergence_depth()
        print(f"  Depth after run: {depth}")
        print(f"  Report: {report[:2]}...")  # 打印前 2 层
    except Exception as e:
        print(f"\nError running world: {e}")
        import traceback
        traceback.print_exc()

def test_resource_pool():
    """测试资源池功能。"""
    print("\n" + "="*60)
    print("Test: Resource Pool")
    print("="*60)
    
    from experiments.exp_192_phase20_p2_competition_synergy_v2 import ResourcePool
    
    pool = ResourcePool(N_total=96, base_seed=42)
    
    print(f"\nInitial pool: available={pool.available}, allocated={pool.allocated}")
    
    # 链 0 请求 32 比特
    allocated = pool.request(0, 32)
    print(f"\nChain 0 requests 32: allocated={allocated}")
    print(f"  Pool: available={pool.available}, allocated={pool.allocated}")
    
    # 链 1 请求 32 比特
    allocated = pool.request(1, 32)
    print(f"\nChain 1 requests 32: allocated={allocated}")
    print(f"  Pool: available={pool.available}, allocated={pool.allocated}")
    
    # 链 2 请求 32 比特
    allocated = pool.request(2, 32)
    print(f"\nChain 2 requests 32: allocated={allocated}")
    print(f"  Pool: available={pool.available}, allocated={pool.allocated}")
    
    # 链 3 请求 32 比特 (应该只得到 0)
    allocated = pool.request(3, 32)
    print(f"\nChain 3 requests 32: allocated={allocated}")
    print(f"  Pool: available={pool.available}, allocated={pool.allocated}")
    
    # 释放链 0
    pool.release(0)
    print(f"\nChain 0 released")
    print(f"  Pool: available={pool.available}, allocated={pool.allocated}")
    
    # 链 3 再次请求
    allocated = pool.request(3, 32)
    print(f"\nChain 3 requests 32 again: allocated={allocated}")
    print(f"  Pool: available={pool.available}, allocated={pool.allocated}")

def main():
    """运行所有测试。"""
    print("\nTesting exp_192 v2 Implementation")
    print("="*60)
    
    # 测试资源池
    test_resource_pool()
    
    # 测试基本链功能
    test_basic_chain()
    
    print("\n" + "="*60)
    print("All tests completed")
    print("="*60)

if __name__ == "__main__":
    main()
