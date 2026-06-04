# exp_130 — Phase 6 P3: Booster-Free NRC Validation (5000 steps)

**Date**: 2026-06-04
**Config**: N0=48, 8 seeds (42,142,242,342,442,542,642,742), 5000 steps
**Stack**: CSC + NSE + NRC (NO Booster)
**Hypotheses**: H62a (R2 natural activation), H63a (extended convergence), H64a (extended completeness), H65a (natural CIV)

---

## Verdict: 0/4 PASS (all failed)

| Hypothesis | Result | Detail |
|---|---|---|
| **H62a** (R2 natural activation) | **FAIL** | 0/8 seeds with R2 (total = 0) |
| **H63a** (extended convergence) | **FAIL** | 4/8 seeds converge (need >=6) |
| **H64a** (extended completeness) | **FAIL** | 0/8 seeds >=3 cycles/1k (mean = 0.70) |
| **H65a** (natural CIV) | **FAIL** | 0/8 seeds CIV_max >=5 |

**Baseline H1-H8 + H60/H61**: ALL PASS — NRC stable, no degradation.

---

## Per-Seed Detail

| Seed | NSI_max | NSI_mean | Cycles | R2 | R0_sig | CIV_max | CIV_mean | TopDown |
|------|---------|----------|--------|----|--------|---------|----------|---------|
| 42 | 0.844 | 0.657 | 3 | 0 | 3/3 | 3 | 2.99 | 1 |
| 142 | 0.875 | 0.732 | 5 | 0 | 3/3 | 1 | 1.00 | 1 |
| 242 | 0.880 | 0.740 | 4 | 0 | 3/3 | 2 | 1.99 | 1 |
| 342 | 0.873 | 0.708 | 4 | 0 | 3/3 | 4 | 3.98 | 1 |
| 442 | 0.875 | 0.706 | 5 | 0 | 3/3 | 3 | 2.99 | 1 |
| 542 | 0.880 | 0.725 | 1 | 0 | 0/3 | 2 | 1.99 | 1 |
| 642 | 0.870 | 0.672 | 5 | 0 | 3/3 | 2 | 1.99 | 1 |
| 742 | 0.772 | 0.625 | 1 | 0 | 0/3 | 4 | 3.98 | 1 |

**Aggregate**: 28 total cycles, 0 R2 events, all 8 seeds sealed.

---

## Root Cause Analysis: Why R2 Still Fails

### Condition Analysis

R2 triggering requires ALL of:
1. `current_nsi >= r2_threshold_nsi` (0.85)
2. `cooldown_ok`: `current_step - r2_last_step >= r2_cooldown` (200)
3. `cycle_count > 5`

Checking condition 1 — which seeds hit NSI >= 0.85?

| Seed | NSI_max | Hits 0.85? |
|------|---------|------------|
| 42 | 0.844 | NO |
| 142 | 0.875 | YES |
| 242 | 0.880 | YES |
| 342 | 0.873 | YES |
| 442 | 0.875 | YES |
| 542 | 0.880 | YES |
| 642 | 0.870 | YES |
| 742 | 0.772 | NO |

6/8 seeds hit NSI >= 0.85. Yet R2 = 0. So conditions 2 or 3 must be blocking.

### Cycle Timing Analysis

Looking at seed 142 (NSI_max=0.875, 5 cycles):
- Cycle 0: step 10, 2 events, reinforce
- Cycle 1: step 30, 3 events, restructure
- Cycle 2: step 40, 4 events, reinforce
- Cycle 3: step 50, 2 events, reinforce
- Cycle 4: step 420, 1 event, restructure

All 5 cycles complete by step 420. Cycle_count > 5 is never reached (only 5 cycles total). And the cooldown (200 steps) means even if cycle 6 happened at step 420+, r2_last_step would need to be >= 620 for the next R2 — but no more cycles occur.

For seeds 242, 442, 642 (also 4-5 cycles): same pattern. Cycles cluster in the first 200 steps, then go silent. The system "exhausts" its early narrative tension and enters a stable drift.

For seed 542 and 742 (only 1 cycle): these have 0 significant R0 changes, meaning the settled state from the first cycle locked in permanently. No further narrative tension accumulates.

### The Core Problem

**R2 requires narrative tension to accumulate AFTER the initial burst of cycles.** But the system stabilizes after ~5 cycles in the first ~200 steps. No new events = no new cycles = R2 conditions never met.

This is a **structural timescale mismatch**: R2 is designed as an "epochal" event requiring civilizational-scale crisis, but at N0=48, the system reaches equilibrium too quickly for such a crisis to develop.

---

## Detailed Hypothesis Analysis

### H62a FAIL: R2 Natural Activation — Confirmed Absent

**Finding**: Even with 5000 steps (2.5x exp_129 duration) and no booster, R2 remains dormant.

**Interpretation**: This confirms exp_129's finding that R2 is not a matter of time or booster interference. The issue is **structural**: at N0=48, the difference field is too small to generate civilizational-scale narrative tension. R2 may require:
- **N0 >= 72 or larger**: More bits = more structural complexity = more potential for civilizational crisis
- **Explicit crisis injection**: External perturbation (like Track A1's severe perturbation) may be needed to trigger R2
- **R2 threshold adjustment**: The NSI >= 0.85 threshold may be too high for natural dynamics

### H63a FAIL: Extended Convergence — Partial (4/8)

Seeds 142, 242, 442, 642 show convergence (negative slope of cycle-to-cycle weight changes). Seeds 42, 342, 542, 742 do not.

**Interpretation**: Convergence happens when R0 level changes are significant (3/3 levels tracked). Seeds 542 and 742 have 0 R0 changes — they settled into a fixed state after the first cycle and never moved. Convergence requires **continued NRC cycling**.

The 4 converging seeds all have mean_slope around -0.05 to -0.14 — slow convergence, not dramatic. At this rate, true fixed-point convergence would require ~10,000+ steps.

### H64a FAIL: Extended Completeness — Mean 0.70 Cycles/1k

This is WORSE than exp_129 (which had mean 2.00 cycles/1k). Removing the booster reduced cycle frequency.

**Interpretation**: The booster was actually helping NRC by maintaining higher CIV levels, which generated more narrative events. Without it, the system stabilizes faster and NRC cycles become rarer.

**Key tradeoff**: Booster increases CIV (good for H1-H8, bad for natural R2). No booster reduces CIV (good for natural dynamics, bad for NRC frequency).

### H65a FAIL: Natural CIV — Max 4, Mean ~2.5

Without the booster, CIV_max ranges 1-4, mean ~2.5. This is lower than exp_129's CIV_max=3-4 range but similar.

**Interpretation**: Natural CIV dynamics at N0=48 produce modest civilizational activity. No seed reaches CIV >= 5, which confirms that civilizational-scale events are genuinely rare at this scale.

---

## Comparison: exp_129 (P2, 2000 steps, with Booster) vs exp_130 (P3, 5000 steps, no Booster)

| Metric | exp_129 (P2, w/ Booster) | exp_130 (P3, no Booster) | Delta |
|--------|--------------------------|--------------------------|-------|
| Steps | 2000 | 5000 | +3000 |
| Total cycles | 32 | 28 | -4 |
| Cycles/1k | 2.00 | 0.70 | -1.30 |
| R2 events | 0 | 0 | 0 |
| R2 seeds | 0/8 | 0/8 | 0 |
| R0 sig_ratio | 1.000 | 0.875 (7/8) | -0.125 |
| R1 corr | 1.000 | 0.875 (7/8) | -0.125 |
| CIV_max range | 3-4 | 1-4 | wider |
| CIV_mean | ~2.7 | ~2.5 | -0.2 |
| NSI_max range | 0.60-0.75 | 0.77-0.88 | +0.13 |
| NSI_mean | ~0.53 | ~0.70 | +0.17 |
| Convergence | 1/8 | 4/8 | +3 |
| H1-H8 pass | 8/8 | 8/8 | 0 |

**Key insight**: Removing the booster paradoxically *improved* NSI (0.53 -> 0.70) and convergence (1/8 -> 4/8) while *reducing* cycle frequency (2.00 -> 0.70/1k). The booster was creating artificial CIV events that disrupted natural narrative flow.

---

## Key Findings

### What Worked
1. **NRC is stable at 5000 steps** — no degradation, H1-H8 all pass
2. **NSI improved without booster** — natural narrative dynamics produce higher quality NSI
3. **Convergence doubled** — 4/8 seeds converge without booster vs 1/8 with
4. **All seeds sealed** — 100% sealing rate maintained

### What Didn't Work
1. **R2 still dormant** — 0 events across 40,000 seed-steps (8 seeds x 5000 steps)
2. **Cycle frequency dropped** — booster was providing narrative activation energy
3. **No seed reached CIV >= 5** — N0=48 too small for civilizational crisis

### Structural Insights
1. **R2 is a scale problem, not a time problem** — 5000 steps didn't help. Need larger N0.
2. **Booster is a double-edged sword** — increases CIV (good for baseline) but disrupts natural narrative flow (bad for NRC)
3. **NSI and convergence are anti-correlated with cycle frequency** — fewer cycles = deeper reflection = better NSI
4. **N0=48 may be below the R2 critical threshold** — civilizational rewriting may require N0 >= 72+

---

## Recommendations for Phase 6 P4

### Option 1: R2 Threshold Tuning (Quick Test)
Lower `r2_threshold_nsi` from 0.85 to 0.80 or 0.75. Seeds 142, 242, 342, 442, 542, 642 all hit NSI >= 0.87 — they would have triggered R2 at a lower threshold. Test: 8 seeds x 2000 steps, threshold = 0.80.

### Option 2: N0=72 Scaling Test
Run at N0=72 (optimal from Phase 4 P2 Track B). Larger difference field should produce more structural tension and potentially trigger R2 naturally.

### Option 3: Explicit Crisis Injection (Perturbation → R2)
Based on Phase 5 Track A1 (perturbation recovery), inject a severe perturbation at step 1000 in a 3000-step run. The recovery from crisis may trigger R2 as the system reconstructs its narrative space.

### Option 4: Redefine R2's Role
Accept that R2 is genuinely epochal and not observable at N0=48 within 5000 steps. Redefine the hypothesis from "R2 activates within 5000 steps" to "R2 activates only at civilizational crisis thresholds that require N0 >= 72 or external perturbation." This is consistent with 差异论's view that civilizational rewriting is rare and epochal.

### Recommended Path
Run **Option 1** (threshold 0.80, quick 2000-step test) + **Option 2** (N0=72, 2000 steps) in parallel. If both fail, proceed with **Option 4** (redefine R2 as epochal).

---

## Raw Data

Results JSON: `experiments/exp_130_p3_booster_free_5000_results_20260604_1150.json`
