# exp_117 Track B4: 层间约束传导 (Constraint Conduction) — Results Analysis

**Date:** 2026-06-02  
**Parent:** exp_116 (Track B3)  
**Status:** Complete — Mixed Results

---

## Executive Summary

| Hypothesis | Target | B4 Result | Verdict |
|---|---|---|---|
| H30 (L1↔L2 decoupling) | r < 0.7, ≥5/8 | **r = 0.0000, 8/8** | ✅ PASS (but for wrong reason) |
| H31 (L0→L1 delay) | ≥4/8 detected | 0/8 | ❌ FAIL |
| H32 (L2 autonomy) | ≥5/8, index > 0.3 | 0/8, index = 0 | ❌ FAIL |
| H33 (L2 ODI indep) | ≥5/8, corr < 0.8 | 0/8, N/A | ❌ FAIL |
| H34 (response delay) | ≥4/8, delay > 5 | 0/8 | ❌ FAIL |
| H1-H8 baseline | ≥6/8 | 7-8/8 | ✅ PASS |

---

## Key Finding: H30 "Pass" is a False Positive

**H30 shows r = 0.0000 (perfect decoupling), but this is because both L1 and L2 are silent.**

- L1 narrative: `['silent']` for all 8 seeds
- L2 narrative: `['silent']` for all 8 seeds
- Zero variance → zero correlation → technically "decoupled" but not meaningfully so

This is **not** the intended decoupling. The intended decoupling is:
- L1 and L2 both active but with independent dynamics
- L2 has its own difference field, not derived from L1
- L1 provides soft constraints, not hard derivation

**What actually happened:** The constraint conduction clamp is too aggressive. When L1 stability is low (near 0), the constraint bounds [L1*(1-tol), L1*(1+tol)] collapse to near-zero, and L2's autonomous stability (also low) gets clamped to near-zero. Result: L2 is suppressed, not decoupled.

---

## Detailed Results by Seed

| Seed | H1-H8 | CIV Count | TopDown | L1 Narr | L2 Narr | H30 r |
|---|---|---|---|---|---|---|
| 42 | 8/8 | 3 | 2 | silent | silent | 0.0000 |
| 142 | 8/8 | 3 | 2 | silent | silent | 0.0000 |
| 242 | 7/8 | 24 | 2 | silent | silent | 0.0000 |
| 342 | 8/8 | 15 | 2 | silent | silent | 0.0000 |
| 442 | 8/8 | 4 | 2 | silent | silent | 0.0000 |
| 542 | 8/8 | 5 | 2 | silent | silent | 0.0000 |
| 642 | 8/8 | 8 | 2 | silent | silent | 0.0000 |
| 742 | 8/8 | 3 | 2 | silent | silent | 0.0000 |

**Anomaly:** Seed 242 has CIV count = 24 (way above H5 range of 3-15). This seed likely has a different narrative dynamic.

---

## Root Cause Analysis

### Why is L2 silent?

The `ConstraintConduction.update()` computes:

```python
l2_base_stability = l2_auto_stability * (1 - l0_direct_weight) + l0_stability * l0_direct_weight
lower_bound = l1_stability * (1 - tolerance)
upper_bound = l1_stability * (1 + tolerance)
l2_constrained_stability = clip(l2_base_stability, lower_bound, upper_bound)
```

**Problem:** In the current architecture, L2 doesn't have independent clustering. The `l2_auto_state` passed to `ConstraintConduction` is the externally-provided CIVILIZATION state from the NSE global calculation, which is the same shared ODI used by all layers. When L1 stability is low (which it is during most of the run), the constraint bounds are near-zero, and L2 gets clamped to near-zero.

**The fundamental issue:** B4's design requires L2 to have **independent clustering from L0**, but the current implementation doesn't create a separate L2 clustering. The L2 state is still the global (shared) state.

### Why is L1 silent?

L1 (INSTITUTIONAL) narratives are also silent for all seeds. This is unexpected because seed 242 has CIV count = 24, suggesting active narrative dynamics. The issue is likely in the narrative labeling — the `narrative_level` from `narrative_recursion` is not being properly propagated to the LNT.

### Why H31, H33, H34 all fail?

- **H31 (L0→L1 delay):** Requires narrative activity at both L0 and L1. Since L1 is silent, no delay can be detected.
- **H33 (L2 ODI independence):** L2 ODI data is not being extracted from the constraint conduction output properly.
- **H34 (response delay):** No significant L1 stability changes occur (L1 is stable at near-zero), so no response events are detected.

---

## Historical Comparison

| Experiment | Coupling Mode | H30 (L1↔L2 r) | L1 Narr | L2 Narr |
|---|---|---|---|---|
| B1 (exp_114) | parallel | 0.976 (0/8) | silent | silent |
| B2 (exp_115) | serial | 0.861 (1/8) | silent | silent |
| B3 (exp_116) | serial+noise | 0.937 (0/8) | silent | silent |
| **B4 (exp_117)** | **constraint** | **0.000 (8/8)** | **silent** | **silent** |

B4 achieves the lowest correlation, but at the cost of suppressing L2 entirely.

---

## Lessons Learned

1. **Correlation ≠ Decoupling:** Zero correlation can mean "both silent" not "independently active."
2. **Constraint conduction needs independent L2 clustering:** Without it, L2 is just a clamped version of the global state.
3. **Soft boundaries can become hard suppression:** When L1 stability is near-zero, the tolerance window collapses.
4. **Narrative activity is a prerequisite for measuring layer independence:** Silent layers can't be meaningfully compared.

---

## Recommendations for Track B5

1. **Implement true independent L2 clustering:** L2 should cluster L0 structural vectors with its own N0 and its own ODI calculation.
2. **Add L2 stability floor:** Prevent L2 from being clamped to near-zero even when L1 is unstable.
3. **Improve narrative labeling:** Ensure L1 and L2 narrative levels are properly tracked and reported.
4. **Consider asymmetric constraints:** L1→L2 constraint should be one-way (L1 constrains L2, not vice versa).
5. **Add L2 intrinsic dynamics:** L2 should have its own perturbation and decay mechanisms independent of L1.

---

## Files

- **Experiment script:** `experiments/exp_117_phase5_b4_constraint_conduction.py`
- **Results:** `experiments/exp_117_b4_results.json`
- **Design doc:** `docs/exp_117_track_b4_constraint_conduction_design.md`
- **CSC changes:** `engine/cross_scale_coupling.py` (added `ConstraintConduction` class)

---

## Git

```
commit <pending>
experiments/exp_117_phase5_b4_constraint_conduction.py  (new)
engine/cross_scale_coupling.py                          (modified)
docs/exp_117_track_b4_constraint_conduction_design.md   (pre-existing)
```
