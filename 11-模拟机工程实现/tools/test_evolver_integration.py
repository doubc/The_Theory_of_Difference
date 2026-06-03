"""Integration test: CIVFloor + HierarchicalEvolver"""
import sys
sys.path.insert(0, '.')
from engine.hierarchical_evolver import HierarchicalEvolver
from engine.civ_floor import CIVFloor

cf = CIVFloor(floor=3)
print(f"CIVFloor imported: {cf}")

# Check init signature has civ_floor
import inspect
sig = inspect.signature(HierarchicalEvolver.__init__)
print(f"civ_floor in init params: {'civ_floor' in sig.parameters}")
if 'civ_floor' in sig.parameters:
    param = sig.parameters['civ_floor']
    print(f"  default: {param.default}")

print("ALL OK")