"""test_energy_constraint.py — 测试能量约束对涌现深度的影响。"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from world_v2 import RecursiveWorld, Params
from energy_v2 import EnergyConfig

def test_energy_constraint():
    """测试能量预算对涌现深度的限制。"""
    print("=" * 70)
    print("Test: Energy Constraint on Emergence Depth")
    print("=" * 70)
    print()
    
    params = Params(max_steps=500)
    
    # 测试不同能量预算
    budgets = [10, 20, 50, 100, 200]
    results = []
    
    for budget in budgets:
        energy_cfg = EnergyConfig(initial_budget=budget, decay_rate=0.01)
        world = RecursiveWorld(
            N0=48, n_colors=6,
            params=params,
            energy_cfg=energy_cfg,
            seed=42
        )
        result = world.run(max_layers=10, verbose=False)
        depth = result['depth']
        results.append((budget, depth))
        
        print("Budget=%d: depth=%d" % (budget, depth))
    
    print()
    print("=" * 70)
    print("Analysis:")
    print("=" * 70)
    
    # 检查能量预算是否影响涌现深度
    depths = [r[1] for r in results]
    if max(depths) > min(depths):
        print("[OK] Energy budget affects emergence depth (H21-P0a supported)")
        print("  Depth range: %d - %d" % (min(depths), max(depths)))
    else:
        print("[WARN] Energy budget does NOT affect depth (H21-P0a not supported)")
        print("  All depths = %d" % depths[0])
    
    print()
    print("Detailed results:")
    for budget, depth in results:
        print("  Budget %3d -> Depth %d" % (budget, depth))
    
    print()
    return results

if __name__ == "__main__":
    try:
        results = test_energy_constraint()
        print("[OK] Test completed successfully!")
    except Exception as e:
        print("[ERROR] Test failed: %s" % str(e))
        import traceback
        traceback.print_exc()
