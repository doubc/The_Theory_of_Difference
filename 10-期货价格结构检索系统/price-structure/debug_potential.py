import json
from statistics import median

with open('output/daily_scan_20260425_1534.json', encoding='utf-8') as f:
    d = json.load(f)

opps = d['opportunities']
print(f"Total: {len(opps)} opportunities")
print()

# Section 1: direction=down opportunities
print("=== direction=down opportunities ===")
down_opps = [o for o in opps if o['direction'] == 'down']
print(f"Count: {len(down_opps)}\n")
for o in down_opps:
    moves = [tm['down_move'] for tm in o['top_matches'] if tm['direction'] == 'down']
    if moves:
        med = median(moves)
        print(f"  {o['symbol']:6s}  stored_median={o['potential_median']:+.4f}  "
              f"calc_median(down_move)={med:+.4f}  samples={moves[:3]}")

print()

# Section 2: direction=up opportunities
print("=== direction=up opportunities ===")
up_opps = [o for o in opps if o['direction'] == 'up']
print(f"Count: {len(up_opps)}\n")
for o in up_opps:
    moves = [tm['up_move'] for tm in o['top_matches'] if tm['direction'] == 'up']
    if moves:
        med = median(moves)
        print(f"  {o['symbol']:6s}  stored_median={o['potential_median']:+.4f}  "
              f"calc_median(up_move)={med:+.4f}  samples={moves[:3]}")

print()

# Section 3: all up_move/down_move distributions
print("=== Value ranges across ALL templates ===")
all_up = []
all_down = []
for o in opps:
    for tm in o['top_matches']:
        if tm['up_move'] != 0:
            all_up.append(tm['up_move'])
        if tm['down_move'] != 0:
            all_down.append(tm['down_move'])

print(f"  up_move:  min={min(all_up):+.4f}  max={max(all_up):+.4f}  avg={sum(all_up)/len(all_up):+.4f}")
print(f"  positive: {sum(1 for x in all_up if x>0)}, negative: {sum(1 for x in all_up if x<0)}")
print(f"  down_move: min={min(all_down):+.4f}  max={max(all_down):+.4f}  avg={sum(all_down)/len(all_down):+.4f}")
print(f"  positive: {sum(1 for x in all_down if x>0)}, negative: {sum(1 for x in all_down if x<0)}")

print()

# Section 4: verify stored vs calculated
print("=== Verify stored vs calculated potential_median ===")
mismatch_count = 0
for o in opps:
    top = o['top_matches']
    d_ = o['direction']
    if d_ == "up":
        moves = [m['up_move'] for m in top if m['direction'] == 'up']
    elif d_ == "down":
        moves = [m['down_move'] for m in top if m['direction'] == 'down']
    else:
        moves = [max(m['up_move'], m['down_move']) for m in top]
    if not moves:
        moves = [0.0]
    calc = median(moves)
    stored = o['potential_median']
    diff = abs(calc - stored)
    if diff > 0.0001:
        mismatch_count += 1
        print(f"  MISMATCH {o['symbol']:6s} dir={d_} stored={stored:+.4f} calc={calc:+.4f}")
if mismatch_count == 0:
    print("  All match OK")

print()

# Section 5: if down_move should be negated (absolute value stored as positive)
print("=== Test: if down_move is stored as absolute value (negate it) ===")
for o in down_opps[:5]:
    top = o['top_matches']
    moves_raw = [m['down_move'] for m in top if m['direction'] == 'down']
    moves_neg = [-m for m in moves_raw]
    stored = o['potential_median']
    calc_neg = median(moves_neg) if moves_neg else 0.0
    match = "MATCH" if abs(calc_neg - stored) < 0.0001 else f"stored={stored:+.4f} NEG_calc={calc_neg:+.4f}"
    print(f"  {o['symbol']:6s}  {match}")