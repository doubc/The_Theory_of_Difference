"""exp_185_phase19_p0_strength_sweep.py — Phase 19 P0: 耦合强度扫描。

假设 H19-P0: iso_score > 0.65 时环境不能重新激活自指。
假设 H19-P1: iso_score < 0.50 时环境可以重启自指。

5 strengths × 16 seeds = 80 runs.
"""
import sys, os, json, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim.world import RecursiveWorld, Params

STRENGTHS = [0.0, 0.05, 0.10, 0.20, 0.50]
SEEDS = 16
MAX_LAYERS = 6

ENV_CONFIG = {"N": 16, "structural_entropy": 1, "cycle_length": 5, "threshold": 0.0}

BASELINE_PARAMS = Params(
    bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
    cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
    lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
    target_active=0, max_flip=6, churn=2,
    n_meta_colors=4, max_residual=6, max_steps=400,
)


def run_config(strength, seed):
    """单次实验：给定强度和种子，运行 RecursiveWorld。"""
    world = RecursiveWorld(
        N0=48, n0_active=40, n_colors=6, seed=seed,
        params=BASELINE_PARAMS, self_encapsulate=True,
        env_config=ENV_CONFIG, env_coupling_strength=strength,
    )
    report = world.run(max_layers=MAX_LAYERS, verbose=False)
    return {
        "strength": strength,
        "seed": seed,
        "emergence_depth": world.emergence_depth(),
        "n_layers": len(report),
        "layers": report,
        "env_flux": world.env.mean_flux() if world.env else None,
        "coupling_events": world.env_coupling.summary() if world.env_coupling else None,
    }


def main():
    results = []
    t0 = time.time()
    total = len(STRENGTHS) * SEEDS
    done = 0

    print(f"exp_185 P0: {total} runs ({len(STRENGTHS)} strengths × {SEEDS} seeds)")
    print("-" * 60)
    print(f"{'strength':>8} {'seed':>4} {'depth':>5} {'L0_flux':>8} {'L1_flux':>8} "
          f"{'L2_flux':>8} {'L0_orgs':>7} {'L1_orgs':>7} {'L2_orgs':>7} {'env_flux':>8}")
    print("-" * 80)

    for strength in STRENGTHS:
        for seed in range(SEEDS):
            res = run_config(strength, seed)
            results.append(res)
            done += 1

            depth = res["emergence_depth"]
            layers = res["layers"]
            l0 = layers[0] if len(layers) > 0 else {}
            l1 = layers[1] if len(layers) > 1 else {}
            l2 = layers[2] if len(layers) > 2 else {}
            env_f = res["env_flux"] if res["env_flux"] is not None else 0.0

            print(f"{strength:>8.2f} {seed:>4d} {depth:>5d} "
                  f"{l0.get('autonomous_flux', 0):>8.4f} "
                  f"{l1.get('autonomous_flux', 0):>8.4f} "
                  f"{l2.get('autonomous_flux', 0):>8.4f} "
                  f"{l0.get('n_orgs', 0):>7d} "
                  f"{l1.get('n_orgs', 0):>7d} "
                  f"{l2.get('n_orgs', 0):>7d} "
                  f"{env_f:>8.4f}")

    elapsed = time.time() - t0
    print(f"\nTotal: {done}/{total} runs in {elapsed:.1f}s")

    # 汇总统计
    print("\n=== SUMMARY ===")
    print(f"{'strength':>8} {'mean_depth':>10} {'pct_depth>=3':>12} "
          f"{'mean_L1_flux':>12} {'mean_L2_flux':>12} {'mean_env_flux':>12} "
          f"{'pct_L2_emerged':>14} {'pct_L3_emerged':>14}")
    print("-" * 96)
    for strength in STRENGTHS:
        strs = [r for r in results if r["strength"] == strength]
        depths = [r["emergence_depth"] for r in strs]
        l1_fluxes = [r["layers"][1]["autonomous_flux"] for r in strs if len(r["layers"]) > 1]
        l2_fluxes = [r["layers"][2]["autonomous_flux"] for r in strs if len(r["layers"]) > 2]
        env_fluxes = [r["env_flux"] for r in strs if r["env_flux"] is not None]
        l2_emerged = sum(1 for r in strs if r["emergence_depth"] >= 2)
        l3_emerged = sum(1 for r in strs if r["emergence_depth"] >= 3)
        print(f"{strength:>8.2f} {np.mean(depths):>10.2f} "
              f"{sum(1 for d in depths if d >= 3) / len(depths) * 100:>11.1f}% "
              f"{np.mean(l1_fluxes) if l1_fluxes else 0:>12.4f} "
              f"{np.mean(l2_fluxes) if l2_fluxes else 0:>12.4f} "
              f"{np.mean(env_fluxes) if env_fluxes else 0:>12.4f} "
              f"{l2_emerged / len(strs) * 100:>13.1f}% "
              f"{l3_emerged / len(strs) * 100:>13.1f}%")

    # H19-P0 判定: iso_score > 0.65 (depth >= 3) 时 env 不能重启
    for strength in STRENGTHS:
        strs = [r for r in results if r["strength"] == strength]
        depths = [r["emergence_depth"] for r in strs]
        pct_l3 = sum(1 for d in depths if d >= 3) / len(depths) * 100
        baseline = [r for r in results if r["strength"] == 0.0]
        baseline_l3 = sum(1 for r in baseline if r["emergence_depth"] >= 3) / len(baseline) * 100
        delta = pct_l3 - baseline_l3
        print(f"\nH19-P0 at strength={strength}: L3+={pct_l3:.1f}% (baseline={baseline_l3:.1f}%, delta={delta:+.1f}%)")
        if delta > 10:
            print(f"  -> H19-P0 REJECTED at this strength (env changed self-reference)")
        else:
            print(f"  -> H19-P0 consistent at this strength (no significant change)")

    # 保存结果
    out_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"exp_185_p0_strength_sweep_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "exp_185_phase19_p0_strength_sweep",
            "config": {"strengths": STRENGTHS, "seeds": SEEDS,
                       "env_config": ENV_CONFIG,
                       "params": BASELINE_PARAMS.__dict__},
            "results": results,
            "summary": {f"s{strength:.2f}": {
                "mean_depth": float(np.mean([r["emergence_depth"] for r in [r2 for r2 in results if r2["strength"] == strength]])),
                "pct_l3": float(sum(1 for r in [r2 for r2 in results if r2["strength"] == strength] if r["emergence_depth"] >= 3) / SEEDS * 100),
            } for strength in STRENGTHS},
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()