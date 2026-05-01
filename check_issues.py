"""导入检查脚本 — 检查未使用导入和交叉依赖"""
import ast
import os
import re
import sys

def check_unused_imports(filepath):
    """检查文件中未使用的导入"""
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    
    issues = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                # 跳过 __future__ 导入和 type hint only
                if module == "__future__":
                    continue
                # 简单检查：导入名是否在文件其他地方出现
                # 排除 import 行本身
                pattern = r'\b' + re.escape(name) + r'\b'
                # 找到所有匹配
                matches = re.findall(pattern, source)
                if len(matches) <= 1:
                    issues.append(f"  UNUSED: from {module} import {name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                # 标准库跳过
                if name in ("os", "sys", "math", "json", "ast", "re", "pathlib", "dataclasses", "enum", "typing", "datetime", "statistics", "collections", "functools", "itertools", "copy", "abc", "logging", "time", "hashlib", "base64", "io", "csv", "random"):
                    continue
                pattern = r'\b' + re.escape(name) + r'\b'
                matches = re.findall(pattern, source)
                if len(matches) <= 1:
                    issues.append(f"  UNUSED: import {name}")
    
    return issues

def check_file_size(filepath, limit=500):
    """检查文件是否过大"""
    with open(filepath, encoding="utf-8") as f:
        lines = len(f.readlines())
    return lines, lines > limit

# 扫描所有 Python 文件
all_issues = {}
large_files = {}

for dp, dn, fn in os.walk("src"):
    # 跳过 __pycache__
    if "__pycache__" in dp:
        continue
    for f in fn:
        if f.endswith(".py"):
            path = os.path.join(dp, f)
            
            # 未使用导入
            issues = check_unused_imports(path)
            if issues:
                all_issues[path] = issues
            
            # 文件大小
            lines, is_large = check_file_size(path)
            if is_large:
                large_files[path] = lines

print("=" * 60)
print("未使用导入检查")
print("=" * 60)
if all_issues:
    for path, issues in sorted(all_issues.items()):
        print(f"\n{path}:")
        for issue in issues:
            print(issue)
else:
    print("无问题")

print()
print("=" * 60)
print("大文件检查 (>500行)")
print("=" * 60)
for path, lines in sorted(large_files.items(), key=lambda x: -x[1]):
    print(f"  {path}: {lines} 行")

print()
print("=" * 60)
print("signals.py 稳定性判断一致性检查")
print("=" * 60)

# 检查 signals.py 中的 stability_ok 判断逻辑
with open("src/signals.py", encoding="utf-8") as f:
    content = f.read()

# 检查 stability_ok 的判断条件
if 'stability_ok = stability.surface not in ["ILLUSION", "UNSTABLE"]' in content:
    print("  ⚠️ 问题: stability_ok 检查使用了 'ILLUSION'/'UNSTABLE'，")
    print("     但 StabilityVerdict.surface 的实际值只有 'stable'/'unstable'")
    print("     → 应改为: stability_ok = stability.surface == 'stable' and stability.verified")
elif 'stability_ok = stability.surface == "stable"' in content:
    print("  ✅ stability_ok 检查与 StabilityVerdict 定义一致")
else:
    print("  ❓ 无法判断 stability_ok 逻辑")

print()
print("=" * 60)
print("SystemState 索引一致性检查")
print("=" * 60)

# 检查 ranked_structures vs system_states 索引
with open("src/workbench/tab_scan.py", encoding="utf-8") as f:
    scan_content = f.read()

if "cr.system_states[idx_s]" in scan_content:
    print("  ⚠️ 问题: tab_scan.py 使用 idx_s 索引 system_states")
    print("     ranked_structures 是排序后的，索引会错位")
    print("     → 已添加 get_system_state_for() 修复")
elif "get_system_state_for" in scan_content:
    print("  ✅ tab_scan.py 使用 get_system_state_for()，索引一致")

print()
print("=" * 60)
print("is_blind 阈值一致性检查")
print("=" * 60)

with open("src/models.py", encoding="utf-8") as f:
    models_content = f.read()

if "compression_level > 0.7" in models_content:
    print("  ⚠️ 问题: is_blind 阈值仍为 0.7 (过高)")
elif "compression_level > 0.5" in models_content:
    print("  ✅ is_blind 阈值已调整为 0.5")

# 检查 compute_projection 阈值一致性
with open("src/relations.py", encoding="utf-8") as f:
    rel_content = f.read()

if "bw < 0.005" in rel_content:
    print("  ⚠️ 问题: compute_projection 带宽阈值仍为旧值 (0.5%/1%/2%)")
elif "bw < 0.008" in rel_content:
    print("  ✅ compute_projection 带宽阈值已调整为 0.8%/1.5%/3%")
