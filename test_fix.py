#!/usr/bin/env python3
"""
测试修复：稳定性检测和盲区检测
v3.2 修复验证
"""

import sys
sys.path.insert(0, "src")

from src.models import ProjectionAwareness, StabilityVerdict, SystemState
from src.relations import compute_projection, detect_stability_illusion

print("=" * 60)
print("测试 1: is_blind 阈值修复")
print("=" * 60)

# 测试新阈值 (0.5)
test_cases = [
    (0.6, True, "压缩度0.6 > 0.5，应为盲区"),
    (0.5, False, "压缩度0.5 = 阈值，应为非盲区"),
    (0.4, False, "压缩度0.4 < 0.5，应为非盲区"),
    (0.9, True, "压缩度0.9 >> 0.5，应为盲区"),
]

for compression, expected, desc in test_cases:
    p = ProjectionAwareness(compression_level=compression)
    result = "✅" if p.is_blind == expected else "❌"
    print(f"{result} {desc}: is_blind={p.is_blind} (期望={expected})")

print()
print("=" * 60)
print("测试 2: compute_projection 阈值修复")
print("=" * 60)

# 模拟 Structure 对象
class MockZone:
    def __init__(self, bw):
        self.relative_bandwidth = bw

class MockStructure:
    def __init__(self, bw, cycles=None):
        self.zone = MockZone(bw)
        self.cycles = cycles or [1, 2, 3]
        self.invariants = {}

# 测试新阈值
test_bandwidths = [
    (0.005, 0.9, "带宽0.5% → 高压缩(0.9)"),
    (0.008, 0.9, "带宽0.8% → 高压缩(0.9)"),
    (0.01, 0.7, "带宽1.0% → 中等压缩(0.7)"),
    (0.015, 0.7, "带宽1.5% → 中等压缩(0.7)"),
    (0.02, 0.4, "带宽2.0% → 轻度压缩(0.4)"),
    (0.03, 0.4, "带宽3.0% → 轻度压缩(0.4)"),
    (0.05, 0.1, "带宽5.0% → 低压缩(0.1)"),
]

for bw, expected_min, desc in test_bandwidths:
    s = MockStructure(bw)
    proj = compute_projection(s)
    # 检查压缩度是否达到预期范围
    if bw < 0.008:
        expected = 0.9
    elif bw < 0.015:
        expected = 0.7
    elif bw < 0.03:
        expected = 0.4
    else:
        expected = 0.1
    
    result = "✅" if proj.compression_level == expected else "❌"
    is_blind_str = "(盲区)" if proj.is_blind else "(非盲区)"
    print(f"{result} {desc}: compression_level={proj.compression_level} {is_blind_str}")

print()
print("=" * 60)
print("测试 3: CompileResult.get_system_state_for")
print("=" * 60)

from src.compiler.pipeline import CompileResult, CompilerConfig
from src.models import Structure, Zone, Cycle, Segment, Point
from datetime import datetime

# 创建测试数据
zone = Zone(price_center=100, bandwidth=5)

# 创建两个结构，cycle_count 不同用于排序
s1 = Structure(zone=zone, cycles=[1, 2, 3, 4])  # 4 cycles
s2 = Structure(zone=zone, cycles=[1, 2])        # 2 cycles

# 创建对应的 system_states
ss1 = SystemState(structure=s1)
ss2 = SystemState(structure=s2)

# 创建 CompileResult
cr = CompileResult(
    bars_count=100,
    pivots=[],
    segments=[],
    zones=[zone],
    cycles=[],
    structures=[s1, s2],  # 原始顺序: s1, s2
    bundles=[],
    config=CompilerConfig(),
    system_states=[ss1, ss2],
)

# 测试 ranked_structures 排序
ranked = cr.ranked_structures
print(f"原始顺序: {[s.cycle_count for s in cr.structures]}")
print(f"排序后: {[s.cycle_count for s in ranked]}")

# 测试 get_system_state_for
for i, s in enumerate(ranked):
    ss = cr.get_system_state_for(s)
    correct_ss = ss1 if s.cycle_count == 4 else ss2
    result = "✅" if ss is correct_ss else "❌"
    print(f"{result} 结构 {s.cycle_count} cycles → 找到正确的 SystemState")

print()
print("=" * 60)
print("修复验证完成!")
print("=" * 60)
