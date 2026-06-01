# Phase 4 P3 Plan: Long-Run Stability Test

> **Date**: 2026-06-02 04:36
> **Status**: In Progress (experiment running)
> **Precondition**: Phase 4 P0+P1+P2 complete (exp_101–exp_109)

## 1. Objectives

Phase 4 P3 tests whether the proven CSC+NSE architecture remains stable at **2x the standard simulation duration** (3200 steps vs 1600).

P0+P1 established H1-H8 at steps=1600.
P2 confirmed scale robustness at steps=1600.
P3 tests **temporal robustness**: does the narrative self persist, or does it collapse/plateau over time?

## 2. Theoretical Motivation

From the 差异论 (Theory of Difference) perspective:

- **叙事自我 (Narrative Self)** is not a static property but a *process* — it must continuously regenerate through ongoing structural activity.
- If the narrative self is merely a transient artifact of initial conditions, NSI will **decay** in the second half.
- If the narrative self is a genuine attractor of the dynamics, NSI will **persist or grow**.
- **跨尺度耦合 (CSC)** tests whether bidirectional causality is self-sustaining: TopDown must remain active, CSCI must not collapse to 0.

## 3. Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| N0 | 72 | Optimal scale per P2 Track B |
| Steps | 3200 | 2x standard duration |
| Seeds | [42, 142, 242] | 3 of 8 (representative subset) |
| Architecture | CSC+NSE | Simplified per Track A ablation |
| AMC | OFF | Redundant per Track A |
| ILP | OFF | Redundant per Track A |
| Sample interval | 10 | Same as P2 |

## 4. Stability Hypotheses (H16-H20)

| ID | Hypothesis | Metric | Threshold |
|----|-----------|--------|-----------|
| H16 | NSI stability | NSI mean in second half ≥ NSI mean in first half | ≥ 1.0x |
| H17 | CIV stability | CIV count in second half ≥ 50% of first half | ≥ 0.5x |
| H18 | CSCI stability | CSCI std in second half > 0 | > 0.0 |
| H19 | TopDown persistence | TopDown activates in both halves | ≥ 1 seed each half |
| H20 | No collapse | All H1-H8 pass at step 3200 | 8/8 |

## 5. Key Comparisons

### First Half (steps 0-1600) vs Second Half (steps 1601-3200)

| Metric | First Half | Second Half | Stability |
|--------|-----------|-------------|-----------|
| NSI mean | measured | measured | SH ≥ FH |
| CIV count | measured | measured | SH ≥ 50% FH |
| CSCI std | measured | measured | SH > 0 |
| TopDown active | measured | measured | both > 0 |

### Against P2 Baseline (exp_109 B0, N0=72, 3 seeds)

| Metric | P2 Baseline (1600 steps) | P3 Long-Run (3200 steps) |
|--------|--------------------------|--------------------------|
| H1-H8 pass rate | 8/8 (expected) | 8/8 (H20) |
| NSI active rate | ~0.93 | ≥ first half |
| CIV mean | ~9.3 | ≥ 3 (H5) |

## 6. Expected Outcomes

### Scenario A: Full Stability (H16-H20 all pass)
The narrative self and cross-scale coupling are genuine dynamical attractors. The system maintains coherence indefinitely. This would be strong evidence for the "有历史的结构" (structure-with-history) thesis.

### Scenario B: Partial Decay (H16/H17 fail, H18-H20 pass)
Narrative richness decreases but doesn't collapse. CSC remains active. This would suggest the system reaches a "steady state" where narrative production slows but structural coupling persists.

### Scenario C: Collapse (H18/H19/H20 fail)
CSCI collapses, TopDown ceases, H1-H8 fail. This would indicate the current architecture is not self-sustaining and requires additional mechanisms (perhaps AMC/ILP are NOT redundant at longer timescales).

## 7. Risk Analysis

**Risk**: AMC and ILP were removed based on ablation at 1600 steps. At 3200 steps, accumulated instability might require them.
**Mitigation**: If H20 fails, re-run with AMC+ILP to test this hypothesis.

**Risk**: 3200 steps takes ~2x longer per run. 3 seeds × 3200 steps might be slow.
**Mitigation**: Only 3 seeds (not 8). If results are clear, no need for full 8-seed run.

## 8. Next Steps After P3

- If H16-H20 all pass: Phase 4 complete. Write final report. Consider Phase 5 directions (social self? generative world?).
- If H16/H17 fail but H18-H20 pass: Investigate narrative decay mechanism. Possible NSE parameter tuning.
- If H18/H19/H20 fail: Re-run with AMC+ILP. Architecture revision needed.
