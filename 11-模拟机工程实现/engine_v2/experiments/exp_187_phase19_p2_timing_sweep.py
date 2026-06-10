#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_187_phase19_p2_timing_sweep.py — Phase 19 P2: 环境引入时序扫描。

核心问题: 环境是否能在 L0 密封前改变系统演化轨迹？
Phase 19 P0 (exp_185) 确认: iso > 0.65 时环境不能重启自指。
Phase 19 P1 (exp_186) 发现: 环境是"约束场"而非"结构传递者"。

exp_187 测试: 在 L0 密封的不同阶段引入环境 — 是否早期引入能改变轨迹？

假设体系:
  H19-P1a: 密封前引入环境改变 L0 seal_step (偏离 ≥20% 基线)
  H19-P1b: 早期环境 (step 0) 改变涌现深度 (偏离基线 ≥1)
  H19-P1c: 中期环境 (step 25) 最大程度改变 L1/L2 动力学

配置 (4 timing × 16 seeds = 64 runs):
  none: 无环境 (基线)
  early: 环境从 step 0 开始施加
  mid: 环境从 step 25 开始施加
  late: 环境在 L0 密封后施加 (exp_185/186 行为 = 对照)

指标:
  - L0 seal_step, emergence_depth, L1 flux, L2 flux, L0 n_orgs
  - L0 seal_ratio (密封时活跃比特比例)
"""
import sys, os, json, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim.world import RecursiveWorld, Params

# --- 配置 ---
TIMING_CONFIGS = {
    "none":  None,    # 无环境
    "early": 0,       # 从 step 0 开始 (L0 全程耦合)
    "mid":   5,       # 从 step 5 开始 (L0 密封中期介入)
    "late":  None,    # L0 密封后 (对照, 同 exp_185/186)
}
SEEDS = 16
MAX_LAYERS = 6

ENV_CONFIG = {"N": 12, "structural_entropy": 1, "cycle_length": 5, "threshold": 0.0}
COUPLING_STRENGTH = 0.20

BASELINE_PARAMS = Params(
    bind_inc=0.18, bind_cap=5.0, bind_threshold=1.0,
    cascade_density=0.9, min_org_size=3, seal_fraction=0.6,
    lock_inc=0.12, lock_threshold=0.6, cycle_persistence=3,
    target_active=0, max_flip=6, churn=2,
    n_meta_colors=4, max_residual=6, max_steps=400,
)


def run_config(timing_name, seed):
    """单次实验。"""
    env_start = TIMING_CONFIGS[timing_name]
    env_config = ENV_CONFIG if timing_name != "none" else None

    world = RecursiveWorld(
        N0=48, n0_active=40, n_colors=6, seed=seed,
        params=BASELINE_PARAMS, self_encapsulate=True,
        env_config=env_config, env_coupling_strength=COUPLING_STRENGTH,
        env_start_step=env_start,
    )
    report = world.run(max_layers=MAX_LAYERS, verbose=False)

    # 收集 L0 密封时指标
    l0_r = report[0] if len(report) > 0 else {}
    l1_r = report[1] if len(report) > 1 else {}
    l2_r = report[2] if len(report) > 2 else {}

    result = {
        "timing": timing_name,
        "seed": seed,
        "emergence_depth": world.emergence_depth(),
        "n_layers": len(report),
        "l0_seal_step": l0_r.get("seal_step", -1),
        "l0_n_orgs": l0_r.get("n_orgs", 0),
        "l0_flux": l0_r.get("autonomous_flux", 0),
        "l1_flux": l1_r.get("autonomous_flux", 0),
        "l1_n_orgs": l1_r.get("n_orgs", 0),
        "l2_flux": l2_r.get("autonomous_flux", 0),
        "l2_n_orgs": l2_r.get("n_orgs", 0),
        "env_flux": world.env.mean_flux() if world.env else None,
    }

    # 环境耦合事件统计
    if world.env_coupling:
        cs = world.env_coupling.summary()
        result["coupling_events_total"] = cs["events"]
        result["coupling_direct"] = cs["direct"]
        result["coupling_indirect"] = cs["indirect"]

    return result


def main():
    results = []
    t0 = time.time()
    timings = list(TIMING_CONFIGS.keys())
    total = len(timings) * SEEDS
    done = 0

    print(f"exp_187 Phase 19 P2: {total} runs ({len(timings)} timings × {SEEDS} seeds)")
    print("-" * 90)
    header = f"{'timing':>6} {'seed':>4} {'depth':>5} {'L0ss':>5} {'L0_k':>4} {'L0_flux':>8} {'L1_flux':>8} {'L2_flux':>8} {'env_flux':>8}"
    print(header)
    print("-" * 90)

    for timing in timings:
        for seed in range(SEEDS):
            res = run_config(timing, seed)
            results.append(res)
            done += 1
            print(f"{timing:>6} {seed:>4d} {res['emergence_depth']:>5d} "
                  f"{res['l0_seal_step']:>5d} {res['l0_n_orgs']:>4d} "
                  f"{res['l0_flux']:>8.4f} {res['l1_flux']:>8.4f} "
                  f"{res['l2_flux']:>8.4f} "
                  f"{res['env_flux'] if res['env_flux'] is not None else 0:>8.4f}")

    elapsed = time.time() - t0
    print(f"\nTotal: {done}/{total} runs in {elapsed:.1f}s")

    # 汇总统计
    print("\n" + "=" * 90)
    print("=== PHASE 19 P2 SUMMARY ===")
    print("=" * 90)
    summary_header = (f"{'timing':>6} {'mean_depth':>10} {'L3+%':>7} {'mean_L0ss':>9} "
                      f"{'mean_L0_k':>8} {'mean_L1flux':>10} {'mean_L2flux':>10} "
                      f"{'mean_envflux':>10}")
    print(summary_header)
    print("-" * 80)
    for timing in timings:
        strs = [r for r in results if r["timing"] == timing]
        depths = [r["emergence_depth"] for r in strs]
        l0ss = [r["l0_seal_step"] for r in strs]
        l0k = [r["l0_n_orgs"] for r in strs]
        l1f = [r["l1_flux"] for r in strs if r["l1_flux"] is not None and r["emergence_depth"] >= 2]
        l2f = [r["l2_flux"] for r in strs if r["l2_flux"] is not None and r["emergence_depth"] >= 3]
        ef = [r["env_flux"] for r in strs if r["env_flux"] is not None]
        l3pct = sum(1 for d in depths if d >= 3) / len(depths) * 100
        print(f"{timing:>6} {np.mean(depths):>10.2f} {l3pct:>6.1f}% "
              f"{np.mean(l0ss):>9.1f} {np.mean(l0k):>8.2f} "
              f"{np.mean(l1f) if l1f else 0:>10.4f} "
              f"{np.mean(l2f) if l2f else 0:>10.4f} "
              f"{np.mean(ef) if ef else 0:>10.4f}")

    # H19-P1a: 密封前引入环境改变 seal_step
    print("\n--- H19-P1a: L0 seal_step change vs baseline (none) ---")
    none_seeds = [r for r in results if r["timing"] == "none"]
    baseline_ss = np.mean([r["l0_seal_step"] for r in none_seeds])
    for timing in ["early", "mid", "late"]:
        strs = [r for r in results if r["timing"] == timing]
        mean_ss = np.mean([r["l0_seal_step"] for r in strs])
        delta = (mean_ss - baseline_ss) / baseline_ss * 100
        pass_str = "PASS" if abs(delta) >= 20 else "FAIL"
        print(f"  {timing:>6}: mean_ss={mean_ss:.1f} vs baseline={baseline_ss:.1f} "
              f"delta={delta:+.1f}% [{pass_str}] (target >=20%)")

    # H19-P1b: 早期环境改变涌现深度
    print("\n--- H19-P1b: emergence depth change vs baseline (none) ---")
    baseline_depth = np.mean([r["emergence_depth"] for r in none_seeds])
    for timing in ["early", "mid", "late"]:
        strs = [r for r in results if r["timing"] == timing]
        mean_d = np.mean([r["emergence_depth"] for r in strs])
        delta = mean_d - baseline_depth
        pass_str = "PASS" if abs(delta) >= 1 else "FAIL"
        print(f"  {timing:>6}: mean_depth={mean_d:.2f} vs baseline={baseline_depth:.2f} "
              f"delta={delta:+.2f} [{pass_str}] (target >=1.0)")

    # H19-P1c: 中期环境最大程度改变 L1/L2 动力学
    print("\n--- H19-P1c: L1/L2 flux change — mid vs early vs late ---")
    for timing in ["early", "mid", "late"]:
        strs = [r for r in results if r["timing"] == timing]
        l1f = [r["l1_flux"] for r in strs if r["emergence_depth"] >= 2]
        l2f = [r["l2_flux"] for r in strs if r["emergence_depth"] >= 3]
        print(f"  {timing:>6}: L1_flux={np.mean(l1f):.4f} (n={len(l1f)}) "
              f"L2_flux={np.mean(l2f):.4f} (n={len(l2f)})")
    print("  (预期: mid 的 flux 偏离最大 — 对 early 和 late 的比较)")

    # 保存结果
    out_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"exp_187_p2_timing_sweep_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "exp_187_phase19_p2_timing_sweep",
            "config": {"timings": timings, "seeds": SEEDS,
                       "env_config": ENV_CONFIG,
                       "coupling_strength": COUPLING_STRENGTH,
                       "params": BASELINE_PARAMS.__dict__},
            "results": results,
            "summary": {t: {
                "mean_depth": float(np.mean([r["emergence_depth"]
                    for r in results if r["timing"] == t])),
                "mean_l0_ss": float(np.mean([r["l0_seal_step"]
                    for r in results if r["timing"] == t])),
                "mean_l1_flux": float(np.mean([r["l1_flux"]
                    for r in results if r["timing"] == t
                    if r["emergence_depth"] >= 2]) or 0),
                "mean_l2_flux": float(np.mean([r["l2_flux"]
                    for r in results if r["timing"] == t
                    if r["emergence_depth"] >= 3]) or 0),
            } for t in timings},
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()