import json, sys

with open('experiments/exp159_phase14_p2_dual_nuclei_20260608_060350.json') as f:
    d = json.load(f)

print("=== PARAMS ===")
for k, v in d['params'].items():
    print(f"  {k}: {v}")

print("\n=== ANALYSIS (summary) ===")
a = d['analysis']
if isinstance(a, dict):
    for k, v in a.items():
        if isinstance(v, (str, int, float, bool)):
            print(f"  {k}: {v}")
        elif isinstance(v, list) and len(v) < 20:
            print(f"  {k}: {v}")
        elif isinstance(v, dict):
            print(f"  {k}: dict with {len(v)} keys: {list(v.keys())[:10]}")
        else:
            print(f"  {k}: ({type(v).__name__}, len={len(v) if hasattr(v,'__len__') else '?'})")
elif isinstance(a, list):
    print(f"  list of {len(a)} items")
    if a:
        print(f"  first item type: {type(a[0]).__name__}")

print("\n=== METRICS (summary) ===")
m = d['metrics']
if isinstance(m, dict):
    for k, v in m.items():
        if isinstance(v, (str, int, float, bool)):
            print(f"  {k}: {v}")
        elif isinstance(v, list) and len(v) < 30:
            print(f"  {k}: {v}")
        elif isinstance(v, dict):
            print(f"  {k}: dict with {len(v)} keys: {list(v.keys())[:10]}")
        else:
            print(f"  {k}: ({type(v).__name__}, len={len(v) if hasattr(v,'__len__') else '?'})")