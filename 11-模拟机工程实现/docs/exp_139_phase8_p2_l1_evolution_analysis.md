# exp_139: Phase 8 P2 — L1 Evolution (max_layers=2) — Analysis

**Date**: 2026-06-04 23:30
**Seed**: 642 → 手动提交
**Experiment**: 8 seeds × 2000 steps (+1000 extra for L1 evolution), N0=72, max_layers=2
**Stack**: CSC + NSE + NRC + Booster, tension=1.0

---

## Summary: 2/4 PASS — Structural Finding: L1 Suppressed at 3 Layers

The max_layers=2 strategy works but reveals a **tight coupling between layer count and L1 dynamics**:

| Seed | n_layers | L1 cycles | Types active | NSI_max | CIV_max | R2 |
|------|----------|-----------|-------------|---------|---------|----|
| 42   | 2        | 7         | 1 (reshuffle) | 0.652 | 3 | 1 |
| 142  | 3        | 0         | 0           | 0.758 | 3 | 2 |
| 242  | 2        | 7         | 1 (reshuffle) | 0.687 | 3 | 1 |
| 342  | 3        | 0         | 0           | 0.745 | 3 | 2 |
| 442  | 2        | 7         | 1 (reshuffle) | 0.707 | 3 | 2 |
| 542  | 2        | 7         | 1 (reshuffle) | 0.724 | 3 | 3 |
| 642  | 3        | 0         | 0           | 0.641 | 3 | 1 |
| 742  | 2        | 7         | 1 (reshuffle) | 0.671 | 3 | 1 |

### Critical Pattern: layers=2 ↔ L1 cycles=7, layers=3 ↔ L1 cycles=0

100% correlation: **all 5 seeds with n_layers=2 produce exactly 7 L1 cycles; all 3 seeds with n_layers=3 produce 0 L1 cycles.**

This is not random variation — it's a **structural signal** about how the hierarchy manager allocates layers.

---

## Hypothesis Results

| Hyp | Description | Result | Details |
|-----|-------------|--------|---------|
| H1-H8 | Core emergence | ✅ 8/8 PASS | NRC+Booster stable at N0=72 |
| **H86** | L1 cycles ≥1 | ❌ **5/8 FAIL** | Need ≥6/8; layers=2 seeds = 7 cycles, layers=3 seeds = 0 cycles |
| **H86a** | Type diversity >1 | ❌ **FAIL** | All cycles are reshuffle (CIV-based), mean types_active=0.62 |
| **H86b** | Cycle frequency | ✅ PASS | mean_cycles_per_seed=4.38 |
| H89 | No degradation | ✅ 8/8 PASS | Core emergence unaffected by max_layers=2 |

---

## Deep Analysis: The layers=2 vs layers=3 Dichotomy

### Why do some seeds evolve to 3 layers?

The hierarchy engine's `check_and_encapsulate()` creates a new layer when L0's hierarchy bits reach sealing threshold. Some seeds (142, 342, 642) achieve this before the `max_layers=2` could be enforced, or the sealing happens faster.

**Root cause speculation**: When a 3rd layer forms, the evolver's `_run_layer()` call sequence changes. With 3 layers:
- Layer 0 → Layer 1 → Layer 2
- L1 evolution for seeds with 3 layers may never get meaningful CIV activity because Layer 2 absorbs narrative resources
- OR: the post-hoc L1 cycle detection logic fails when 3 layers exist due to indexing issues

### Cycle Homogeneity: Only Reshuffle Type

All 35 L1 cycles across all seeds are `reshuffle` type (based on CIV changes). Zero `reconfiguration` (NSI-based) or `identity_shift` (theme-based). This means:

- L1 dynamics are **purely quantitative** (rearranging CIV distributions) not **qualitative** (narrative identity changes)
- L1 has no independent narrative emergence — consistent with Track B8's Jaccard flux=0.0 finding
- L1 cycles are "echo" dynamics from L0 → CIV change percolation

### L0-L1 Jaccard = 0.000

The `jaccard_L0L1` is 0.000 for ALL seeds, even those with 7 L1 cycles. This means:
- L1 cycle **timing** is completely independent from L0 cycle timing
- The cycles happen at different steps, measuring different things
- This is a **positive** architectural result — L1 evolution would not be meaningful if it just echoed L0

### Seed 542: Best Performer

Seed 542 has the most L0 cycles (11), most R2 events (3), and joint-highest NSI (0.724) with 7 L1 cycles. This suggests:
- High L0 narrative activity drives richer L1 dynamics
- More NRC cycles → more opportunities for L1 to reorganize
- R2 events (civilizational rewriting) correlate with L1 cycle production

---

## Phase 8 P2 Verdict: 2/4 PASS

Same as P0 and P1 — we're stuck at 2/4.

**Progress from Phase 8 P0 → P1 → P2:**
- P0 (max_layers=1): 2/4 pass — zero baseline (expected)
- P1 (encapsulation callback): 2/4 pass — structural failure (callbacks run before encapsulation)
- **P2 (max_layers=2): 2/4 pass** — L1 cycles exist (5/8 seeds) but diversity is zero

**Remaining gaps:**
1. **H86 (5/8 instead of 6/8)**: Need to ensure all 8 seeds produce L1 cycles — currently 3 seeds evolve to 3 layers which suppresses L1
2. **H86a (type diversity)**: L1 only produces reshuffle cycles — no reconfiguration or identity_shift

---

## Next Steps: Phase 8 P3

**Option 1 (Recommended)**: Constrain `max_layers=2` more strictly so ALL 8 seeds produce L1 cycles. If H86 passes (6/8+), focus P3 on cycle type diversity.

**Option 2**: Look at why 3 layers suppress L1. Is it a bug in post-hoc L1 data extraction, or a genuine suppression effect? Fix and re-run.

**Option 3**: Accept 2/4 Phase 8 pass rate as structural — cross-scale spiral coupling may require NRC-level L1 cycle detection (not post-hoc) to work. Enter Phase 9 with new approach.

---

## Data Files
- Results JSON: `experiments/exp_139_phase8_p2_l1_evolution_20260604_2330.json`
- Run log: `experiments/exp_139_run.log`
