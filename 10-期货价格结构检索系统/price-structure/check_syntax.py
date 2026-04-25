"""语法检查脚本"""
import ast
import os
import sys

errors = []
passed = 0
total = 0

for dp, dn, fn in os.walk("src"):
    for f in fn:
        if f.endswith(".py"):
            total += 1
            path = os.path.join(dp, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    ast.parse(fh.read())
                passed += 1
            except SyntaxError as e:
                errors.append(f"SYNTAX ERROR: {path}: {e}")
            except Exception as e:
                errors.append(f"ERROR: {path}: {e}")

print(f"Syntax check: {passed}/{total} passed")
if errors:
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("ALL PASS")
