"""Print Phase 7 comparison section from saved results."""
import json, os, numpy as np

PROJECT_ROOT = r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现'
results_file = os.path.join(PROJECT_ROOT, 'experiments', 'exp_136_phase7_full_spiral_20260604_1838.json')

with open(results_file, 'r') as f:
    data = json.load(f)

h = data['hypotheses']
results = data['per_seed']
nrc_agg = h.get('nrc_aggregate', {})

# Extract H83 values
h83_data = h.get('H83_nsi_improvement', {})
baseline_nsi_72 = h83_data.get('baseline_nsi', 0.50)
h83_overall_mean = float(h83_data.get('value', 'mean_nsi=0.0000').split('mean_nsi=')[1].split(' ')[0])
nsi_max_vals = [r.get('nse_nsi_max', 0) for r in results]
nrc_r2_total = nrc_agg.get('nrc_r2_total', 0)

print()
print('=' * 70)
print("COMPARISON: Phase 5 D1 (N0=72, no NRC) vs Phase 7 (N0=72, full spiral)")
print('=' * 70)
print(f"  Phase 5 D1 baseline NSI: ~{baseline_nsi_72:.2f} (estimated)")
print(f"  Phase 7 NSI (mid-phase): {h83_overall_mean:.4f}")
print(f"  Phase 7 NSI (max): {float(np.max(nsi_max_vals)):.4f}")
print(f"  Delta: {h83_overall_mean - baseline_nsi_72:+.4f} "
      f"{'[GOAL: >=+0.02]' if h83_overall_mean >= baseline_nsi_72 + 0.02 else '[BELOW]'}")

print(f"\n  Phase 6 exp_135 (N0=48): 12 R2 events (from Phase 6 final report)")
print(f"  Phase 7 (N0=72): {nrc_r2_total} R2 events")
print()

# Also print key comparison metrics
print("--- Key Metrics Summary ---")
print(f"  H1-H8: {h['summary']['n_pass']}/8 pass")
print(f"  H81 (spiral completeness): {'PASS' if h.get('H81_spiral_completeness',{}).get('pass') else 'FAIL'}")
print(f"  H82 (R->P rewriting):     {'PASS' if h.get('H82_r2_rewriting',{}).get('pass') else 'FAIL'}")
print(f"  H83 (NSI improvement):    {'PASS' if h.get('H83_nsi_improvement',{}).get('pass') else 'FAIL'}")
print(f"  H84 (cross-scale):        {'FAIL' if not h.get('H84_cross_scale_jaccard',{}).get('pass') else 'PASS'}")
print(f"  H85 (no degradation):     {'PASS' if h.get('H85_no_degradation',{}).get('pass') else 'FAIL'}")
print(f"  Jaccards: {h['H84_cross_scale_jaccard']['value'].split('(jaccards: ')[1].rstrip(')') if 'jaccards:' in h['H84_cross_scale_jaccard']['value'] else 'N/A'}")