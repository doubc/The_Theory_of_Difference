import json, os

# find the latest scan json
out_dir = 'output'
files = [f for f in os.listdir(out_dir) if f.startswith('daily_scan_') and f.endswith('.json')]
files.sort()
latest = files[-1]
print(f"Reading: {latest}")

with open(os.path.join(out_dir, latest), encoding='utf-8') as f:
    d = json.load(f)

opps = d['opportunities']
print(f"Total: {len(opps)} opportunities")
print()

mt_map = {"trend_up": "上涨趋势", "trend_down": "下跌趋势",
          "oscillation": "震荡", "reversal": "反转", "": "(空)"}
for o in opps:
    sym = o.get('symbol', '?')
    mt = o.get('movement_type', '')
    mt_cn = mt_map.get(mt, mt or '(空)')
    tend = o.get('motion_tendency', '')
    flux = o.get('motion_flux', 0)
    score = o.get('attention_score', 0)
    print(f"{sym:6s}  [{mt_cn:8s}]  flux={flux:+.2f}  tendency={tend or 'N/A':15s}  score={score:.2f}")

# Count movement types
from collections import Counter
mt_counts = Counter(o.get('movement_type', '') or '' for o in opps)
print()
print("Movement type distribution:")
for mt, cnt in mt_counts.most_common():
    print(f"  {mt_map.get(mt, mt):10s}: {cnt} 个")