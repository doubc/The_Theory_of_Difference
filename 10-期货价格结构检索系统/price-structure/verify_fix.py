import json, os
from collections import defaultdict
from statistics import median

out_dir = 'output'
files = sorted([f for f in os.listdir(out_dir) if f.startswith('daily_scan_') and f.endswith('.json')])
latest = os.path.join(out_dir, files[-1])
print(f"Reading: {files[-1]}\n")

with open(latest, encoding='utf-8') as f:
    d = json.load(f)

opps = d['opportunities']
up_opps = [o for o in opps if o['direction'] == 'up']
down_opps = [o for o in opps if o['direction'] == 'down']

print(f"Total: {len(opps)} | up={len(up_opps)} down={len(down_opps)}")
print()

# Show all down opportunities - should now have negative potential_median
print("=== direction=down ===")
for o in sorted(down_opps, key=lambda x: x['potential_median']):
    sym = o['symbol']
    mt = o.get('movement_type', '')
    score = o['attention_score']
    pot = o['potential_median']
    p25 = o['potential_p25']
    p75 = o['potential_p75']
    print(f"  {sym:6s}  pot={pot:+.2%}  [p25={p25:+.2%}, p75={p75:+.2%}]  score={score:.2f}  mt={mt}")

print()

# Show all up opportunities - should still have positive potential_median
print("=== direction=up ===")
for o in sorted(up_opps, key=lambda x: -x['potential_median']):
    sym = o['symbol']
    pot = o['potential_median']
    score = o['attention_score']
    print(f"  {sym:6s}  pot={pot:+.2%}  score={score:.2f}")

print()

# Summary stats
pos_pot = [o['potential_median'] for o in opps if o['potential_median'] > 0]
neg_pot = [o['potential_median'] for o in opps if o['potential_median'] < 0]
print("=== Summary ===")
print(f"  Positive potential: {len(pos_pot)} opportunities, avg={sum(pos_pot)/len(pos_pot):+.2%}")
print(f"  Negative potential: {len(neg_pot)} opportunities, avg={sum(neg_pot)/len(neg_pot):+.2%}")
print(f"  Zero potential: {len(opps)-len(pos_pot)-len(neg_pot)} opportunities")
print()
print(f"  UP opportunities   avg potential: {sum(o['potential_median'] for o in up_opps)/len(up_opps):+.2%}")
print(f"  DOWN opportunities  avg potential: {sum(o['potential_median'] for o in down_opps)/len(down_opps):+.2%}")