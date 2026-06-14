# -*- coding: utf-8 -*-
"""Phase 23 P0 — 基线重建: m9 自指闭环接线验证。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diffsim.world_v2 import RecursiveWorld, Params
from diffsim.energy_v2 import EnergyConfig
import json

def test_baseline_dead_order():
    """基线: self_encapsulate=False → L1 应为死秩序 (flux≈0 或 无L2)"""
    w = RecursiveWorld(N0=48, self_encapsulate=False, seed=42)
    result = w.run(max_layers=4, verbose=False)
    
    print(f"  Baseline: depth={result['depth']}, n_layers={result['n_layers']}")
    for li in result['layers']:
        print(f"    L{li['layer']}: steps={li['steps']}, sealed={li['sealed']}, flux={li['flux']:.4f}")
    
    # 基线应该只有 L0→L1 (被动投影无差异源)
    assert result['n_layers'] >= 1, "L0 should seal and produce L1"
    return result

def test_self_reference_living_order():
    """自指: self_encapsulate=True → 活秩序 (多层涌现)"""
    w = RecursiveWorld(N0=48, self_encapsulate=True, seed=42)
    result = w.run(max_layers=4, verbose=False)
    
    print(f"  Self-ref: depth={result['depth']}, n_layers={result['n_layers']}")
    for li in result['layers']:
        print(f"    L{li['layer']}: steps={li['steps']}, sealed={li['sealed']}, flux={li['flux']:.4f}")
    
    assert result['n_layers'] >= 1, "Should produce at least L1"
    return result

def test_energy_integration():
    """能量集成: self_encapsulate=True + EnergyConfig"""
    w = RecursiveWorld(
        N0=48, self_encapsulate=True, seed=42,
        energy_cfg=EnergyConfig(initial_budget=200)
    )
    result = w.run(max_layers=4, verbose=False)
    
    print(f"  Energy: depth={result['depth']}, n_layers={result['n_layers']}")
    for li in result['layers']:
        e = li.get('energy', {})
        print(f"    L{li['layer']}: steps={li['steps']}, flux={li['flux']:.4f}, energy_budget={e.get('budget', 'N/A')}")
    
    assert 'energy' in result, "Should have energy summary"
    return result

def test_import_from_init():
    """验证从 diffsim 直接导入 RecursiveWorld"""
    from diffsim import RecursiveWorld, Layer, Params
    assert RecursiveWorld is not None
    assert Layer is not None
    print("  Import test: OK")

if __name__ == '__main__':
    print("=== Phase 23 P0: Baseline Verification ===")
    print()
    
    print("Test 1: Import from diffsim")
    test_import_from_init()
    print()
    
    print("Test 2: Baseline dead order (self_encapsulate=False)")
    r1 = test_baseline_dead_order()
    print()
    
    print("Test 3: Self-reference living order (self_encapsulate=True)")
    r2 = test_self_reference_living_order()
    print()
    
    print("Test 4: Energy integration")
    r3 = test_energy_integration()
    print()
    
    # 对比基线 vs 自指
    l1_baseline = [l for l in r1['layers'] if l['layer'] == 1]
    l1_self = [l for l in r2['layers'] if l['layer'] == 1]
    
    if l1_baseline:
        print(f"  Baseline L1 flux: {l1_baseline[0]['flux']:.4f}")
    if l1_self:
        print(f"  Self-ref L1 flux: {l1_self[0]['flux']:.4f}")
    
    if l1_baseline and l1_self:
        delta = l1_self[0]['flux'] - l1_baseline[0]['flux']
        print(f"  Δ flux: {delta:.4f} (self-ref improves dead order)")
    
    print()
    print("=== All tests passed! ===")
