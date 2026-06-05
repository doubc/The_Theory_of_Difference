"""
_launch_p3b_rerun.py — Phase 9 P3-B (high-res) + N0=32/34 clean re-run

Launches two batches:
  Part A: N0=32,34 clean re-run (16 seeds each = 32 runs, ~30min)
  Part B: N0=29,30,31 high-res (16 seeds each = 48 runs, ~45min)

Features:
  - Uses run_single_seed from exp_145 (same code path, now with OOB fix)
  - Per-seed error handling (never crashes the whole batch)
  - Incremental checkpoints every 8 seeds
  - Final JSON with full results

Est. total: ~1h15min (P3-B data for publication-quality transition curve)
"""
import sys, os, time, json, traceback
from datetime import datetime

PROJECT_ROOT = r"C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现"
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from experiments.exp_145_phase9_p3_phase_transition import (
    run_single_seed, evaluate_N0_boundary,
    STEPS, SI, GSN, ML,
)

# ── Config ─────────────────────────────────────────────────────────────

PART_A_RERUN = [32, 34]           # N0=32,34 clean re-run (was crashed in P3-A)
PART_B_HIGHRES = [29, 30, 31]     # P3-B: high-res around the transition
SEEDS_ALL = [42, 142, 242, 342, 442, 542, 642, 742,
             842, 942, 1042, 1142, 1242, 1342, 1442, 1542]

N0_P3B = [29, 30, 31]             # P3-B alone (for analysis final output)
N0_RERUN = [32, 34]               # Re-run alone

ALL_N0 = sorted(set(PART_A_RERUN + PART_B_HIGHRES))  # [29,30,31,32,34]

CHECKPOINT_FILE = os.path.join(PROJECT_ROOT, "experiments", "_exp146_checkpoint.json")

# ── Load/save checkpoint ──────────────────────────────────────────────

def load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return None
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_checkpoint(results_by_n0, done_count, total_count):
    data = {
        "timestamp": datetime.now().isoformat(),
        "done": done_count,
        "total": total_count,
        "results": {str(k): v for k, v in results_by_n0.items()},
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def get_completed_seeds(results_by_n0):
    completed = set()
    for n0, seeds_data in results_by_n0.items():
        for r in seeds_data:
            if "seed" in r and "error" not in r:
                completed.add((n0, r["seed"]))
    return completed

# ── Main ──────────────────────────────────────────────────────────────

def main():
    print("=" * 75)
    print("  PHASE 9 P3-B (HIGH-RES) + N0=32/34 CLEAN RE-RUN")
    print("=" * 75)
    print(f"  Part A (re-run):  N0={PART_A_RERUN}, {len(SEEDS_ALL)} seeds each = {len(PART_A_RERUN)*len(SEEDS_ALL)} runs")
    print(f"  Part B (P3-B):    N0={PART_B_HIGHRES}, {len(SEEDS_ALL)} seeds each = {len(PART_B_HIGHRES)*len(SEEDS_ALL)} runs")
    print(f"  Total:            {len(ALL_N0)} N0 points × {len(SEEDS_ALL)} seeds = {len(ALL_N0)*len(SEEDS_ALL)} runs")
    print(f"  Steps: {STEPS}, SI={SI}, GSN={GSN}, ML={ML}")
    print(f"  Checkpoint: {CHECKPOINT_FILE}")
    print()

    # ── Initialize results ──
    results_by_n0 = {n0: [] for n0 in ALL_N0}
    checkpoint = load_checkpoint()
    if checkpoint:
        ckpt_results = checkpoint.get("results", {})
        for n0_str, seeds_data in ckpt_results.items():
            n0 = int(n0_str)
            if n0 in results_by_n0:
                results_by_n0[n0] = seeds_data
        completed = get_completed_seeds(results_by_n0)
        print(f"  Resumed from checkpoint: {len(completed)} seeds already done")
        if completed:
            print(f"  Completed: {sorted(completed)[:10]}{'...' if len(completed) > 10 else ''}")
        print()
    else:
        completed = set()

    # ── Build run queue ──
    total = len(ALL_N0) * len(SEEDS_ALL)
    run_queue = []
    for n0 in ALL_N0:
        for seed in SEEDS_ALL:
            if (n0, seed) not in completed:
                run_queue.append((n0, seed))

    if not run_queue:
        print("  All runs already complete! Skipping to analysis.")
    else:
        print(f"  Queue: {len(run_queue)} pending seeds")
        done = len(completed)

        for idx, (n0, seed) in enumerate(run_queue):
            t0 = time.time()
            try:
                print(f"\n  [{done+1}/{total}] N0={n0} seed={seed} ...", end=" ", flush=True)
                result = run_single_seed(n0, STEPS, seed, SI, GSN, ML)
                elapsed = time.time() - t0
                results_by_n0[n0].append(result)
                done += 1
                l1ok = "OK" if result.get("l1_metrics", {}).get("l1_formed", False) else "NO"
                sealed = "SEAL" if result.get("sealed", False) else "open"
                print(f"L1:{l1ok} {sealed} NSI={result.get('nse_nsi_max', 0.0):.3f} [{elapsed:.0f}s]",
                      flush=True)
            except Exception as e:
                elapsed = time.time() - t0
                print(f"CRASHED at {elapsed:.0f}s: {e}", flush=True)
                traceback.print_exc()
                results_by_n0[n0].append({
                    "N0": n0, "seed": seed, "error": str(e),
                    "elapsed": elapsed, "n_layers_formed": 0,
                    "sealed": False, "l1_sealed": False,
                    "odi_max": 0, "nse_nsi_max": 0, "civ_max": 0,
                    "l1_metrics": {"l1_formed": False},
                })
                done += 1

            # Checkpoint every 8 seeds
            if (done % 8) == 0:
                save_checkpoint(results_by_n0, done, total)
                elapsed_total = time.time() - t0_global
                rate = done / (elapsed_total / 60)
                remain = (total - done) / rate
                print(f"\n  >>> CHECKPOINT: {done}/{total} | "
                      f"{elapsed_total/60:.0f}min elapsed | ~{remain:.0f}min remaining <<<",
                      flush=True)

        # Save final checkpoint
        save_checkpoint(results_by_n0, done, total)
        print(f"\n  Final checkpoint saved: {done}/{total}")

    # ── Run analysis ──
    print(f"\n{'=' * 75}")
    print("  ANALYSIS RESULTS")
    print(f"{'=' * 75}")

    # Separate P3-B and re-run analyses
    for label, n0_list in [("P3-B (high-res N0=29,30,31)", N0_P3B),
                            ("Re-run (clean N0=32,34)", N0_RERUN)]:
        subset = {n0: results_by_n0[n0] for n0 in n0_list}
        evaluation = evaluate_N0_boundary(subset)

        print(f"\n  --- {label} ---")
        for n0 in sorted(n0_list):
            seeds_data = results_by_n0[n0]
            n_formed = sum(
                1 for r in seeds_data
                if r.get("l1_metrics", {}).get("l1_formed", False)
            )
            n_sealed = sum(1 for r in seeds_data if r.get("sealed", False))
            n_total = len(seeds_data)
            print(f"    N0={n0}: {n_formed}/{n_total} L1 formed, "
                  f"{n_sealed}/{n_total} sealed")

    # Full P3-B + re-run combined evaluation
    evaluation = evaluate_N0_boundary(results_by_n0)

    h110 = evaluation["H110"]
    h111 = evaluation["H111"]
    h112 = evaluation["H112"]
    n_pass = evaluation["n_hypotheses_passed"]

    print(f"\n  --- Combined (P3-B + re-run) ---")
    pass_str = "PASS" if h110["pass"] else "FAIL"
    print(f"  H110 (Sharp transition >=12/16 in <=2 N0 steps): {pass_str}")
    print(f"    Max adjacent swing: {h110['max_swing_adjacent']}/16")

    if h111["logistic_fit"]:
        k, x0, r2 = h111["logistic_fit"]
        pass_str = "PASS" if h111["pass"] else "FAIL"
        print(f"  H111 (Logistic fit R2>=0.85): {pass_str}")
        print(f"    k={k:.3f}, N0_0={x0:.1f}, R2={r2:.3f}")

    print(f"\n  Phase 9 P3-B: {n_pass} hypotheses evaluated")

    # ── Save results ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    rf = os.path.join(PROJECT_ROOT, "experiments",
                      f"exp_146_phase9_p3b_highres_{timestamp}.json")

    per_seed = {}
    for n0 in ALL_N0:
        per_seed[str(n0)] = []
        for r in results_by_n0[n0]:
            entry = {k: v for k, v in r.items()
                     if k not in ("nrc_metrics", "l1_metrics")}
            entry["l1_formed"] = r.get("l1_metrics", {}).get(
                "l1_formed", False)
            entry["l1_sealed"] = r.get("l1_metrics", {}).get(
                "l1_sealed", False)
            entry["l0_l1_divergence"] = r.get("l1_metrics", {}).get(
                "l0_l1_theme_divergence", 0.0)
            entry["n_r2_events"] = r.get("nrc_metrics", {}).get(
                "n_r2_events", 0)
            per_seed[str(n0)].append(entry)

    with open(rf, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "exp_146_phase9_p3b",
            "datetime": datetime.now().isoformat(),
            "config": {
                "N0_p3b": N0_P3B,
                "N0_rerun": N0_RERUN,
                "n_seeds": len(SEEDS_ALL),
                "steps": STEPS,
                "max_layers": ML,
                "sample_interval": SI,
                "gbc_soft_nudge": GSN,
            },
            "hypotheses": {
                "H110": {
                    "pass": h110["pass"],
                    "max_swing_adjacent": h110["max_swing_adjacent"],
                    "sharp_window": h110["sharp_window"],
                },
                "H111": {
                    "pass": h111["pass"],
                    "logistic_fit": h111["logistic_fit"],
                },
            },
            "formed_by_N0": {
                str(k): (v[0], v[1]) if isinstance(v, (list, tuple)) else v
                for k, v in evaluation.get("formed_by_n0", {}).items()
            },
            "per_seed": per_seed,
        }, f, indent=2, default=str)

    print(f"\n  Results saved: {rf}")

    # Clean up checkpoint
    try:
        os.remove(CHECKPOINT_FILE)
    except OSError:
        pass

    print(f"\n{'=' * 75}")
    print("  DONE")
    print(f"{'=' * 75}")


if __name__ == "__main__":
    t0_global = time.time()
    main()
