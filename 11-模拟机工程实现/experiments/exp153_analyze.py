"""exp_153 analysis: seal order patterns across runs"""
import json, numpy as np
from collections import Counter

with open('experiments/results/exp153_phase12_p1_20260607_132033.json') as f:
    data = json.load(f)

sealed = [m for m in data['metrics'] if m['sealed']]
nseal = len(sealed)
N = data['params']['N']
print(f"=== N={N}, sealed={nseal}/{data['params']['n_runs']} ===\n")

# === Seal step distribution ===
steps = [m['seal_step'] for m in sealed]
print("--- Seal step distribution ---")
print(f"  mean={np.mean(steps):.1f}, std={np.std(steps):.1f}, "
      f"range=[{min(steps)}, {max(steps)}], median={np.median(steps):.0f}")
steps.sort()
if len(steps) > 10:
    print(f"  deciles: {[np.percentile(steps, p) for p in [10, 25, 50, 75, 90]]}")
    # Find the outlier(s)
    q75, q25 = np.percentile(steps, [75 ,25])
    iqr = q75 - q25
    outliers = [s for s in steps if s > q75 + 1.5*iqr]
    if outliers:
        print(f"  IQR outliers (> {q75 + 1.5*iqr:.0f}): {outliers}")
print()

# === Cascade analysis ===
cascade_events = [m['n_cascade_events'] for m in sealed]
cascade_sizes = [m['max_cascade_size'] for m in sealed]
print("--- Cascade analysis ---")
print(f"  Events per run: {Counter(cascade_events)}")
print(f"  Size distribution: {Counter(cascade_sizes)}")
print()

# === Seal order / bit frequency ===
frozen_counter = Counter()
kept_counter = Counter()
for m in sealed:
    frozen = set(m['seal_order'])
    for bit in frozen:
        frozen_counter[bit] += 1
    kept = set(range(N)) - frozen
    for bit in kept:
        kept_counter[bit] += 1

print("--- Frozen bit frequency (how often each bit is frozen/sealed) ---")
sorted_frozen = sorted(frozen_counter.items(), key=lambda x: x[1], reverse=True)
for bit, cnt in sorted_frozen:
    pct = cnt/nseal*100
    bar = '#' * int(pct/4)
    print(f"  bit {bit:2d}: {pct:5.1f}% {bar}")
print()

print("--- Kept bit frequency (how often each bit survives as active) ---")
sorted_kept = sorted(kept_counter.items(), key=lambda x: x[1], reverse=True)
for bit, cnt in sorted_kept:
    pct = cnt/nseal*100
    bar = '#' * int(pct/4)
    print(f"  bit {bit:2d}: {pct:5.1f}% {bar}")
print()

# Bits that are NEVER frozen (always kept)
never_frozen = sorted(set(range(N)) - set(frozen_counter.keys()))
always_frozen = sorted([b for b, c in frozen_counter.items() if c == nseal])
mixed = sorted([b for b, c in frozen_counter.items() if 0 < c < nseal])
print(f"--- Bit role stability ---")
print(f"  Never frozen (always kept): {never_frozen} ({len(never_frozen)} bits)")
print(f"  Always frozen: {always_frozen} ({len(always_frozen)} bits)")
print(f"  Mixed (sometimes kept, sometimes frozen): {mixed} ({len(mixed)} bits)")
print()

# === Correlation: initial state vs seal step ===
init_vs_step = [(m['n_initial_ones'], m['seal_step']) for m in sealed]
init_counts = sorted(set(i for i,_ in init_vs_step))
print("--- Init ones vs seal step ---")
for ic in init_counts:
    group = [s for i,s in init_vs_step if i == ic]
    print(f"  init_ones={ic}: n={len(group)}, mean_step={np.mean(group):.1f}, "
          f"steps={[s for s in sorted(group)[:5]]}{'...' if len(group)>5 else ''}")
print()

# === Weight vs seal step ===
w_vs_step = [(m['final_weight'], m['seal_step']) for m in sealed]
print("--- Weight vs seal step ---")
# Low seal step (<10) vs high seal step (>50)
low = [w for w,s in w_vs_step if s < 10]
mid = [w for w,s in w_vs_step if 10 <= s <= 30]
high = [w for w,s in w_vs_step if s > 30]
if low: print(f"  fast seal (<10 steps): mean_weight={np.mean(low):.1f}, n={len(low)}")
if mid: print(f"  normal (10-30 steps): mean_weight={np.mean(mid):.1f}, n={len(mid)}")
if high: print(f"  slow seal (>30 steps): mean_weight={np.mean(high):.1f}, n={len(high)}")
print()

# The outlier run 23 (step=110, cascade=15)
if sealed[23]['seal_step'] > 100:
    r23 = sealed[23]
    print(f"--- Run 23 outlier ---")
    print(f"  init_ones={r23['n_initial_ones']}, step={r23['seal_step']}, "
          f"max_cascade={r23['max_cascade_size']}, weight={r23['final_weight']}")
print()

# Run 28 (not sealed)
unsealed = [m for m in data['metrics'] if not m['sealed']]
if unsealed:
    ru = unsealed[0]
    print(f"--- Unsealed run (run {ru['run_id']}) ---")
    print(f"  init_ones={ru['n_initial_ones']}, final_weight={ru['final_weight']}")
