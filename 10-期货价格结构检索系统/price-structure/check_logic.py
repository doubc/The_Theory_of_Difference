# -*- coding: utf-8 -*-
"""逻辑一致性检查脚本"""
import sys
import os

sys.path.insert(0, "src")

print("=" * 60)
print("1. signals.py stability_ok 逻辑检查")
print("=" * 60)

with open("src/signals.py", encoding="utf-8") as f:
    content = f.read()

# 检查 stability_ok 判断
if 'stability_ok = stability.surface not in ["ILLUSION", "UNSTABLE"]' in content:
    print("  BUG: stability_ok uses 'ILLUSION'/'UNSTABLE' but StabilityVerdict.surface only has 'stable'/'unstable'")
    print("  FIX: should be stability_ok = stability.surface == 'stable' and stability.verified")
else:
    # 查找 stability_ok 定义
    for line in content.split('\n'):
        if 'stability_ok' in line and '=' in line and 'stability.surface' in line:
            print(f"  Current: {line.strip()}")

print()
print("=" * 60)
print("2. StabilityVerdict.surface 值域检查")
print("=" * 60)

with open("src/models.py", encoding="utf-8") as f:
    content = f.read()

# 找到 StabilityVerdict 定义
in_class = False
for line in content.split('\n'):
    if 'class StabilityVerdict' in line:
        in_class = True
    if in_class:
        if 'surface' in line:
            print(f"  {line.strip()}")
        if line.strip().startswith('class ') and 'StabilityVerdict' not in line:
            break

print()
print("=" * 60)
print("3. SystemState 索引一致性检查")
print("=" * 60)

with open("src/workbench/tab_scan.py", encoding="utf-8") as f:
    content = f.read()

if "cr.system_states[idx_s]" in content:
    print("  BUG: tab_scan.py uses idx_s (ranked index) to access system_states (original order)")
    print("  This causes index mismatch - stability data will be wrong")
elif "get_system_state_for" in content:
    print("  OK: tab_scan.py uses get_system_state_for()")

with open("src/compiler/pipeline.py", encoding="utf-8") as f:
    content = f.read()

if "get_system_state_for" in content:
    print("  OK: CompileResult has get_system_state_for() method")
else:
    print("  MISSING: CompileResult.get_system_state_for() not found")

print()
print("=" * 60)
print("4. is_blind threshold check")
print("=" * 60)

with open("src/models.py", encoding="utf-8") as f:
    content = f.read()

for line in content.split('\n'):
    if 'compression_level >' in line and 'is_blind' not in line:
        continue
    if 'is_blind' in line and 'compression_level' in line:
        print(f"  models.py: {line.strip()}")

with open("src/relations.py", encoding="utf-8") as f:
    content = f.read()

for i, line in enumerate(content.split('\n'), 1):
    if 'bw <' in line and ('0.005' in line or '0.008' in line or '0.01' in line or '0.015' in line or '0.02' in line or '0.03' in line):
        print(f"  relations.py line {i}: {line.strip()}")

print()
print("=" * 60)
print("5. signals.py assess_quality 调用一致性")
print("=" * 60)

# signals.py 中 generate_signal 调用了 assess_quality(structure)
# 但 tab_scan.py 中已经调用过 assess_quality(structure, ss)
# signals.py 内部又调用了一次不带 ss 的版本，导致质量评分不一致

with open("src/signals.py", encoding="utf-8") as f:
    content = f.read()

if "assess_quality(structure)" in content:
    print("  BUG: signals.py calls assess_quality(structure) without system_state")
    print("  This means quality tier inside signal may differ from tab_scan.py's tier")
    print("  FIX: pass quality_tier as parameter, or pass ss to assess_quality")
elif "assess_quality(structure, ss)" in content:
    print("  OK: signals.py passes system_state to assess_quality")

print()
print("=" * 60)
print("6. lifecycle.py stability 'unknown' fallback check")
print("=" * 60)

with open("src/lifecycle.py", encoding="utf-8") as f:
    content = f.read()

for i, line in enumerate(content.split('\n'), 1):
    if 'stability' in line.lower() and 'unknown' in line.lower():
        print(f"  lifecycle.py line {i}: {line.strip()}")

print()
print("=" * 60)
print("7. Check for hardcoded passwords")
print("=" * 60)

import re
for dp, dn, fn in os.walk("src"):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if f.endswith(".py"):
            path = os.path.join(dp, f)
            with open(path, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if re.search(r'password\s*=\s*["\']', line, re.IGNORECASE) and 'MYSQL_PASSWORD' not in line and 'environ' not in line and 'os.getenv' not in line and 'example' not in line.lower():
                        print(f"  HARDCODED PASSWORD: {path} line {i}: {line.strip()}")

print()
print("=" * 60)
print("8. Cross-module type consistency")
print("=" * 60)

# Check if Structure fields like motion/projection are consistently set
# build_system_state modifies Structure in-place - check if this is documented
with open("src/relations.py", encoding="utf-8") as f:
    content = f.read()

if "s.motion =" in content or "s.projection =" in content or "s.stability_verdict =" in content or "s.liquidity_stress =" in content:
    print("  NOTE: build_system_state() modifies Structure fields in-place:")
    for i, line in enumerate(content.split('\n'), 1):
        if ('s.motion =' in line or 's.projection =' in line or 's.stability_verdict =' in line or 
            's.liquidity_stress =' in line or 's.fear_index =' in line or 's.time_compression =' in line or
            's.invariants[' in line):
            print(f"    relations.py line {i}: {line.strip()}")

print()
print("Done.")
