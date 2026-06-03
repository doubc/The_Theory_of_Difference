"""Quick test for CIVFloor module."""
import sys
sys.path.insert(0, '.')
from engine.civ_floor import CIVFloor

f = CIVFloor(floor=3)
print(f"CIVFloor: {f}")
print(f"  civ=2, active dist -> {f.step(2.0, {'INSTITUTIONAL': 5, 'MINI': 2})}  (expect 3)")
print(f"  civ=5, active dist -> {f.step(5.0, {'INSTITUTIONAL': 5, 'MINI': 2})}  (expect 5)")
print(f"  civ=2, silent dist -> {f.step(2.0, {'MINI': 10})}                 (expect 2)")
print(f"  civ=2, nsi=0.8    -> {f.step(2.0, nsi=0.8)}                (expect 3)")
print(f"  civ=2, nsi=0.1    -> {f.step(2.0, nsi=0.1)}                (expect 2)")
print(f"  civ=0, empty dist -> {f.step(0.0, {})}                      (expect 0)")
print("ALL OK")
