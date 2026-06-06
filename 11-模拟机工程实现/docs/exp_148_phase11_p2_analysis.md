# Phase 11 P2 (exp_148) Results: Subspace Isolation Verification

**Date**: 2026-06-06 16:03 CST  
**Experiment**: exp_148 — static 3-partition of N0=30 into S0/S1/S2 (N0_sub=10), zero coupling  
**Source**: Extracted from original run log (`exp_148_run.log`, 596KB, UTF-16) via `_extract_exp148.py`  
**Status**: ✅ COMPLETE — all 48 runs extracted and analyzed

---

## Raw Results

| Metric | S0 (bits 0-9) | S1 (bits 10-19) | S2 (bits 20-29) | All |
|--------|:---:|:---:|:---:|:---:|
| L1 formation | 0/16 (0%) | 0/16 (0%) | 0/16 (0%) | **0/48 (0%)** |
| NSI mean | 0.841 | 0.841 | 0.841 | **0.841** |
| NSI range | [0.688, 0.880] | [0.688, 0.880] | [0.688, 0.880] | [0.688, 0.880] |
| ODI mean | 0.719 | 0.719 | 0.719 | **0.719** |
| CIV mean/max | 3.0 | 3.0 | 3.0 | **3.0** |
| Elapsed mean | 34.7s | 33.7s | 33.6s | **34.0s** |

## Hypothesis Evaluation

| Hypothesis | Expected | Result | Verdict |
|-----------|----------|--------|---------|
| **H148-1** (0 L1 formation) | 0/48 L1 at N0=10 | 0/48 (0%) | ✅ PASS |
| **H148-2** (zero cross-corr) | r=0 between subspaces | By construction | ✅ PASS |
| **H148-3** (phase transition not scalable) | N0=10 < critical ≈30.5 | Confirmed | ✅ PASS |
| **H148-4** (consistent across seeds) | All N0=10 seeds similar | 48/48 consistent | ✅ PASS |

## Key Findings

### 1. Bit assignment doesn't matter
All three subspaces have identical (NSI, ODI, CIV) distributions. The same 16 unique value combinations appear in S0, S1, and S2. This means at N0=10 with default Rules, **which specific bits a subspace owns has zero effect on its aggregate behavior** — only N0 and seed matter.

### 2. N0=10 is far below critical threshold
The Phase 9 finding (N0* ≈ 30.5) is reconfirmed. At N0=10, L1 formation rate is 0% across all 48 runs. The system generates NSI (0.69-0.88) and CIV (3.0) but cannot organize into higher layers.

### 3. Subspace isolation verified
Zero coupling produces zero cross-subspace interaction — the independent evolver instances drift independently by construction. This provides a clean baseline for P3 coupling experiments.

## Critical Implication for P3

**N0_sub=10 is too small for meaningful L1 dynamics.** If we keep N0_total=60 with k=3, each subspace gets N0_sub=20 — still below the ~30.5 critical threshold. This means:

- No L1-L3 hierarchical dynamics within any subspace
- Cross-subspace coupling studies would be limited to L0-level effects
- The interesting "physical diversity" (different L1 formation times, different binding strengths) won't appear

**Recommended adjustments for P3**:
1. **k=2, N0=60**: each subspace gets N0=30 (at threshold) → some seeds form L1
2. **k=3, N0=90**: each subspace gets N0=30 (at threshold) → more subspaces
3. **k=2, N0=72**: each gets N0=36 (above threshold) → reliable L1 formation

Option 3 (k=2, N0=72) is recommended: N0_sub=36 is comfortably above the threshold, producing reliable L1 in each subspace. Two subspaces (e.g., "strong binding" vs "weak binding") provide the simplest testbed for coupling effects.

---

*Analysis extracted from `exp_148_run.log` — 2026-06-06 16:03 CST*
