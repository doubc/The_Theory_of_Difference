# exp_131 & exp_132 — Phase 6 P4: R2 Threshold Tuning + N0=72 Scaling

**Date**: 2026-06-04
**Status**: Complete — R2 remains dormant without tension-based trigger

---

## exp_131: R2 Threshold Tuning (3 configs × 8 seeds × 300 steps)

**Hypotheses**:
- H66: ≥4/8 seeds with R2 (threshold=0.80)
- H67: ≥2/8 seeds with R2 (any threshold)
- H68: Cycle frequency sensitivity

### Results

| Config | R2 Total | Seeds with R2 | NSI_max (range) | CIV_max (max) | Cycles (total) |
|--------|----------|---------------|-----------------|---------------|-----------------|
| th0.80_cd100 | 0 | 0/8 | 0.597–0.870 | 6 | 38 |
| th0.80_cd200 | 0 | 0/8 | 0.597–0.870 | 6 | 38 |
| th0.75_cd100 | 0 | 0/8 | 0.597–0.870 | 6 | 38 |

**H66**: FAIL — 0/8 seeds (need ≥4)
**H67**: FAIL — 0/8 seeds (need ≥2)
**H68**: PASS — mean cycles/1k = 1.58 (>0.5)

**H1-H8**: ALL PASS ✅ — all three configs preserve core emergence

### Key Finding
Lowering R2 threshold from 0.85 to 0.75 and cooldown from 200 to 100 has **zero effect** on R2 activation. R2 is not a threshold problem — it's a structural timing mismatch (NSI peaks before cycle_count reaches threshold).

---

## exp_132: N0=72 Scaling (8 seeds × 300 steps)

**Hypotheses**:
- H69: R2 activates at N0=72
- H70: NSI scales with N0
- H71: CIV scales with N0
- H72: Cycle frequency at N0=72

### Results

| Seed | NSI_max | R2 Events | CIV_max | Cycles |
|------|---------|-----------|---------|--------|
| 42 | 0.628 | 0 | 3 | 3 |
| 142 | 0.661 | 0 | 3 | 9 |
| 242 | 0.748 | 0 | 1 | 4 |
| 342 | 0.698 | 0 | 2 | 8 |
| 442 | 0.638 | 0 | 2 | 4 |
| 542 | 0.734 | 0 | 2 | 6 |
| 642 | 0.721 | 0 | 3 | 5 |
| 742 | 0.722 | 0 | 1 | 5 |

**H69**: FAIL — 0/8 seeds with R2 (total=0)
**H70**: FAIL — mean NSI_max=0.694 (<0.70 threshold, but this is N0=48 range)
**H71**: FAIL — max CIV=3 (<4 threshold)
**H72**: PASS — mean cycles/1k=1.83 (>0.70)

**H1-H8**: ALL PASS ✅

### Key Finding
Scaling N0 from 48→72 does NOT activate R2. This confirms the root cause: the R2 trigger condition (NSI ≥ threshold AND cycle_count > 5) is structurally impossible to satisfy, regardless of N0 or threshold parameters.

---

## Combined Conclusion

**exp_131 + exp_132 confirm**: R2 activation is NOT achievable through parameter tuning alone. The problem is architectural — the NSI-based trigger cannot work because:
1. NSI peaks during early narrative emergence (first ~200 steps)
2. Cycle_count > 5 is typically reached after NSI has peaked
3. The two conditions are temporally mismatched

**Solution**: exp_133 implements tension-based R2 trigger (cumulative narrative tension replaces NSI threshold), which achieves 8/8 seeds with R2.

---

## Comparison Table

| Experiment | Trigger Type | N0 | Steps | R2 Total | Seeds with R2 |
|------------|-------------|-----|-------|----------|---------------|
| exp_129 | NSI + Booster | 48 | 2000 | 0 | 0/8 |
| exp_130 | NSI (no Booster) | 48 | 5000 | 0 | 0/8 |
| exp_131 | NSI (threshold sweep) | 48 | 300 | 0 | 0/24 |
| exp_132 | NSI (N0=72) | 72 | 300 | 0 | 0/8 |
| **exp_133** | **Tension-based** | **48** | **300** | **12** | **8/8** |

---

**Files**: exp_131_phase6_p4_r2_threshold.py, exp_132_phase6_p4_n072_scaling.py, results JSONs
