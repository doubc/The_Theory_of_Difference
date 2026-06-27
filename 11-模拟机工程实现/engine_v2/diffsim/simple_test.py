"""simple_test.py — 简单测试 world_v2_fixed 是否能正常导入和运行。"""

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
from world_v2 import RecursiveWorld, Params, Layer

print("✅ All imports successful!")
print()

# 测试 1: 基本创建
print("=" * 60)
print("Test 1: Basic Creation")
print("=" * 60)
params = Params(N0=24, max_steps=200)
world = RecursiveWorld(N0=24, n_colors=4, params=params, seed=42)
print(f"✅ World created: N0={world.N0}, n_layers={len(world.layers)}")
print()

# 测试 2: 运行模拟
print("=" * 60)
print("Test 2: Run Simulation")
print("=" * 60)
result = world.run(max_layers=5, verbose=True)
print(f"✅ Simulation complete: depth={result['depth']}")
print()

# 测试 3: 检查层信息
print("=" * 60)
print("Test 3: Layer Information")
print("=" * 60)
for layer_info in result['layers']:
    print(f"  L{layer_info['layer']}: steps={layer_info['steps']}, "
          f"sealed={layer_info['sealed']}, flux={layer_info['flux']:.4f}")
print()

print("=" * 60)
print("All basic tests PASSED!")
print("=" * 60)
