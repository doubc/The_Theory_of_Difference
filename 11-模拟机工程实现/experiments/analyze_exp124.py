import json, glob

files = glob.glob("experiments/results/exp_124_b10_l2_l3_cascade_*.json")
if not files:
    print("No results files found")
    exit(1)

fname = sorted(files)[-1]
print(f"Reading: {fname}")
with open(fname, 'r') as f:
    data = json.load(f)

print("\n=== H57: L1-L2 Correlation (preservation check) ===")
for d in data['hypotheses']['H57']['detail']:
    print(f"  Seed {d['seed']}: corr={d.get('l1_l2_corr', 'N/A')} pass={d['pass']}")

print("\n=== L1/L2 Seal Events ===")
for r in data['results']:
    print(f"  Seed {r['seed']}: L1_seals={r['n_l1_freeze_events']} L2_seals={r['n_l2_freeze_events']}")

print("\n=== H55: L2→L3 Bias Effect ===")
for d in data['hypotheses']['H55']['detail']:
    print(f"  Seed {d['seed']}: mean_bias={d['mean_bias']:.4f} active_steps={d['n_active_biases']} pass={d['pass']}")

print("\n=== H56: L3 Autonomous NSI ===")
for d in data['hypotheses']['H56']['detail']:
    print(f"  Seed {d['seed']}: l3_nsi={d['l3_nsi_autocorr']:.4f} l3_odi={d['l3_mean_odi']:.4f} pass={d['pass']}")

print("\n=== L2 Summary (correlations) ===")
for r in data['results']:
    l2s = r.get('l2_l3_summary', {})
    print(f"  Seed {r['seed']}: L2-L3 corr={l2s.get('l2_l3_correlation', 'N/A')} L0-L3 corr={l2s.get('l0_l3_correlation', 'N/A')} L3_odi={l2s.get('l3_mean_odi', 'N/A')} L3_bias={l2s.get('l3_mean_bias_effect', 'N/A')}")
