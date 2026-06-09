"""Analyze exp_152 results: extract seal steps from A9 log output."""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

result_file = os.path.join(os.path.dirname(__file__),
                           'results', 'phase11_p4', 'exp_152_20260607_090047.npy')
results = np.load(result_file, allow_pickle=True).item()

print("=" * 60)
print("exp_152 Analysis: effect of coupling on seal speed")
print("=" * 60)
print()
print(f"{'Strength':>8} | {'avg_w0':>6} | {'avg_w1':>6} | {'w1_effect':>9}")
print("-" * 50)

# We don't have step data in the npy (only final_w). 
# But from the console log we saw:
# strength=0.0: S1 seals at steps [16, 18, 21, 13, 12] -> avg ~16
# strength=0.3: S1 seals at steps [17, 7, 5, 12, 20] -> avg ~12
# strength=5.0: S1 seals at steps [43, 12, 18, 24, 9] -> avg ~21 (slow in run 0!)

# The npy doesn't store seal_step. Need to re-run with instrumentation.
# For now, just report what we have:
for level in results:
    s = level['strength']
    runs = level['runs']
    avg_w0 = sum(r['S0_final_w'] for r in runs) / len(runs)
    avg_w1 = sum(r['S1_final_w'] for r in runs) / len(runs)
    print(f"{s:>8.1f} | {avg_w0:>6.1f} | {avg_w1:>6.1f} | ? (need step data)")

print()
print("NOTE: npy result doesn't include seal_step.")
print("Need to re-run with step-level instrumentation to quantify speedup.")
