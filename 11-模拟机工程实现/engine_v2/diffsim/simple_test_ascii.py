"""simple_test_ascii.py — 简单测试 world_v2_fixed (ASCII only)."""

import numpy as np
import sys
import os

# 直接导入 (不使用相对导入)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 先导入依赖模块
from core import DifferenceField
from energy_v2 import EnergyConfig, EnergyManager
from entropy import EntropyConfig, EntropyTracker
from metrics import jaccard_flux

# 导入修复后的世界模块
from world_v2_fixed import RecursiveWorld, Params, Layer

print("[OK] All imports successful!")
print()

# 测试 1: 基本创建
print("=" * 60)
print("Test 1: Basic Creation")
print("=" * 60)
params = Params(max_steps=200)
world = RecursiveWorld(N0=24, n_colors=4, params=params, seed=42)
print("World created: N0=%d, n_layers=%d" % (world.N0, len(world.layers)))
print()

# 测试 2: 运行模拟
print("=" * 60)
print("Test 2: Run Simulation")
print("=" * 60)
result = world.run(max_layers=5, verbose=True)
print("Simulation complete: depth=%d" % result['depth'])
print()

# 测试 3: 检查层信息
print("=" * 60)
print("Test 3: Layer Information")
print("=" * 60)
for layer_info in result['layers']:
    print("  L%d: steps=%d, sealed=%s, flux=%.4f" % (
        layer_info['layer'],
        layer_info['steps'],
        str(layer_info['sealed']),
        layer_info['flux']
    ))
print()

print("=" * 60)
print("All basic tests PASSED!")
print("=" * 60)
