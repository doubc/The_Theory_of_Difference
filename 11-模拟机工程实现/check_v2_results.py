import json, glob, os, numpy as np

os.chdir(r"C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现")
files = sorted(glob.glob("experiments/results/exp_123_v2_b9_*.json"))
with open(files[-1]) as f:
    data = json.load(f)

print("=== H50 Details ===")
for d in data["hypotheses"]["H50"]["detail"]:
    print(f"  seed {d['seed']}: mean_bias={d['mean_bias']:.4f} {'PASS' if d['pass'] else 'FAIL'}")
print(f"  H50 threshold: > {data['config'].get('H50_BIAS_EFFECT_MIN', 'unknown')}")
print(f"  H50 pass rate: {data['hypotheses']['H50']['pass']}/{data['hypotheses']['H50']['total']}")

print("\n=== H51 Details ===")
for d in data["hypotheses"]["H51"]["detail"]:
    print(f"  seed {d['seed']}: corr={d['corr']:.4f} {'PASS' if d['pass'] else 'FAIL'}")
print(f"  H51 threshold: 0 < corr < {data['config'].get('H51_L1_L2_CORR_MAX', 'unknown')}")
print(f"  H51 pass rate: {data['hypotheses']['H51']['pass']}/{data['hypotheses']['H51']['total']}")

print("\n=== H53 Details ===")
for d in data["hypotheses"]["H53"]["detail"]:
    print(f"  seed {d['seed']}: L0-L2={d['l0_l2_corr']:.4f} L1-L2={d['l1_l2_corr']:.4f} {'PASS' if d['pass'] else 'FAIL'}")
print(f"  H53 pass rate: {data['hypotheses']['H53']['pass']}/{data['hypotheses']['H53']['total']}")

print("\n=== H51 Details ===")
for d in data["hypotheses"]["H51"]["detail"]:
    print(f"  seed {d['seed']}: corr={d['corr']:.4f} {'PASS' if d['pass'] else 'FAIL'}")

print("\n=== H53 Details ===")
for d in data["hypotheses"]["H53"]["detail"]:
    print(f"  seed {d['seed']}: L0-L2={d['l0_l2_corr']:.4f} L1-L2={d['l1_l2_corr']:.4f} {'PASS' if d['pass'] else 'FAIL'}")

print("\n=== Per-seed analysis ===")
for r in data["results"]:
    be = r["l1_bias_effect_history"]
    active_be = [b for b in be if abs(b) > 1e-6]
    l0 = r["l0_stability_history"]
    l1 = r["l1_stability_history"]
    l2 = r["l2_stability_history"]
    print(f"  seed {r['seed']}: L0_mean={np.mean(l0):.3f} L1_mean={np.mean(l1):.3f} L2_mean={np.mean(l2):.3f}")
    print(f"    frozen_bits={r['l1_frozen_bits_count_history'][-1]}, seal_step={r['l1_seal_steps']}")
    if active_be:
        print(f"    active_bias_effects: mean={np.mean(np.abs(active_be)):.4f}, max={np.max(np.abs(active_be)):.4f}")
    else:
        print(f"    NO ACTIVE BIAS EFFECTS")
    print(f"    bias_strength_final={r['l1_bias_strength_history'][-1]:.4f}")
    # Check L2 auto base vs L0 (reverse-engineer from l2_stability = auto + bias + l0_direct)
    l0_dir = [s * 0.3 for s in r['l0_stability_history']]
    bias = r.get('l1_bias_effect_history', [0]*len(r['l2_stability_history']))
    l2_auto = [l - b - d for l, b, d in zip(r['l2_stability_history'], bias, l0_dir)]
    print(f"    L2_auto_base_mean={np.mean(l2_auto):.4f}, L0_mean={np.mean(r['l0_stability_history']):.4f}")
    print(f"    L2_auto-L0 diff={np.mean(l2_auto)-np.mean(r['l0_stability_history']):.4f}")
    print(f"    L2_auto std={np.std(l2_auto):.4f} (noise σ should be ~0.10)")
