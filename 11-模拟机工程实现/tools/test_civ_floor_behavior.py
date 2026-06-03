"""Test: Does CIVFloor actually trigger with current parameters?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.civ_floor import CIVFloor

# Default CIVFloor
cf_default = CIVFloor(floor=3)
# Low-threshold CIVFloor
cf_sensitive = CIVFloor(floor=3, narrative_threshold=0.05)

test_cases = [
    # (label, civ_count, nld, nsi)
    ("Default: MINI+INST (2/12)", 0.0, {"MINI": 10, "INSTITUTIONAL": 2}, None),
    ("Default: MINI only", 0.0, {"MINI": 10}, None),
    ("Default: CIVILIZATION present", 0.0, {"MINI": 10, "CIVILIZATION": 1}, None),
    ("Default: NSI=0.5", 0.0, None, 0.5),
    ("Sensitive: MINI+INST (2/12)", 0.0, {"MINI": 10, "INSTITUTIONAL": 2}, None),
    ("Sensitive: MINI only", 0.0, {"MINI": 10}, None),
    ("Sensitive: CIVILIZATION present", 0.0, {"MINI": 10, "CIVILIZATION": 1}, None),
    ("Sensitive: NSI=0.3", 0.0, None, 0.3),
    ("Sensitive: NSI=0.8", 0.0, None, 0.8),
]

print(f"{'Test Case':<40} | {'Default':>8} | {'Sensitive':>8}")
print(f"{'-'*40}-+-{'-'*8}-+-{'-'*8}")
for label, civ, nld, nsi in test_cases:
    d = cf_default.step(civ_count=civ, narrative_level_dist=nld or {}, nsi=nsi)
    s = cf_sensitive.step(civ_count=civ, narrative_level_dist=nld or {}, nsi=nsi)
    print(f"{label:<40} | {d:>8.1f} | {s:>8.1f}")

print()
# Root cause: what ratio does is_narrative_active compute?
print("Default is_narrative_active:")
print(f"  MINI+INST (2/12): {cf_default.is_narrative_active({'MINI': 10, 'INSTITUTIONAL': 2})}")
print(f"  MINI+CIV (1/11):  {cf_default.is_narrative_active({'MINI': 10, 'CIVILIZATION': 1})}")
print(f"  MINI+INST (8/12): {cf_default.is_narrative_active({'MINI': 4, 'INSTITUTIONAL': 8})}")
