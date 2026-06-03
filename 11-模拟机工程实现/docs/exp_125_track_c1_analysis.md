# exp_125: Phase 5 Track C1 — N0 Shrinking Test (Resource Constraints)

**Date**: 2026-06-03 19:31  
**Experimenter**: Script (run, results saved)  
**Analysis**: 2026-06-03 20:03  
**Git**: Not yet committed

---

## Setup

- **Architecture**: CSC+NSE (simplified, no AMC/ILP)
- **Configs**: N0 ∈ {48 (baseline), 30, 24, 18}
- **Seeds**: [42, 142, 242, 342] × 4 = 16 runs
- **Steps**: 1600
- **Hypotheses**: H1-H8 (standard Phase 4/5 battery) + H32-H35 (Track C1)

---

## Results Summary

| Config | N0 | Pass | Failed | CIV Mean | CIV Min | NSI Max | Cont. Mean | CSCI Std | TopDown |
|--------|:--:|:----:|:------:|:--------:|:-------:|:-------:|:----------:|:--------:|:-------:|
| N0_48_baseline | 48 | **6/8** | H5, H6 | 2.25 | 1 | 0.716 | 0.660 | 0.014 | 4/4 |
| N0_30 | 30 | **6/8** | H5, H6 | 1.25 | 1 | 0.724 | 0.706 | 0.024 | 4/4 |
| N0_24 | 24 | **6/8** | H5, H6 | 0.25 | 0 | 0.784 | 0.762 | 0.031 | 4/4 |
| N0_18 | 18 | **6/8** | H5, H6 | 0.00 | 0 | 0.748 | 0.787 | 0.008 | 4/4 |

### Track C1 Hypotheses

| Hypothesis | Description | Result |
|-----------|-------------|:------:|
| **H32** | N0* ∈ [16,32] where H1-H8 fail; N0* = 30 | ✅ PASS |
| **H33** | Continuity monotonic increase as N0 shrinks | ✅ PASS |
| **H34** | CIV mean ≥ 3 at N0=24 (actual: 0.25) | ❌ FAIL |
| **H35** | CIV min ≥ 2 at N0=18 (actual: 0) | ❌ FAIL |

---

## Key Findings

### 1. CIV Collapse at All N0 Levels (Critical Finding)

**The simplified CSC+NSE architecture produces systematically low CIV**, even at N0=48 (baseline). CIV mean is 2.25 at N0=48, already below the H5 threshold of 3. As N0 shrinks, CIV collapses linearly: 2.25 → 1.25 → 0.25 → 0.0.

At N0=18, CIV is **zero across all 4 seeds** — the system generates no civilizational events at all.

**Architectural implication**: In Phase 4, N0=48 passed 8/8 with the full architecture (AMC/ILP intact). The Phase 4 P2 Track A ablation study claimed AMC/ILP are "redundant" for H1-H8. But **exp_125 directly contradicts this**: the Phase 5 simplified architecture at N0=48 fails H5/H6. The AMC or ILP removal, or some codebase change between phases, has weakened CIV generation.

### 2. NSE Is Surprisingly Robust

Despite CIV collapse, narrative self-emergence (NSI) is **strong and increases slightly** as N0 shrinks:
- NSI max: 0.716 → 0.724 → 0.784 → 0.748 (non-monotonic, peaks at N0=24)
- History depth: 0.192 → 0.192 → 0.281 → 0.230 (also peaks at N0=24)
- Turning points: 9.5 → 9.0 → 15.0 → 11.0

**Interpretation**: Narrative coherence (NSI) and CIV are **decoupled** in this architecture. The system can generate excellent narrative self-structure even when CIV events are absent. This suggests CIV is not necessary for narrative self — a significant finding that may require revisiting the theoretical framework.

### 3. Continuity-Resource Tradeoff (H33 Confirmed)

Continuity increases monotonically as N0 shrinks:
0.660 → 0.706 → 0.762 → 0.787

Smaller difference spaces produce more stable, less varied narrative trajectories. The system converges to a smoother, more predictable narrative at the cost of CIV diversity.

### 4. TopDown Invariant at All N0 Levels

**All 4 configs maintain 4/4 TopDown activation** — even at N0=18 where CIV=0. This contradicts the design document's prediction that TopDown would fail at small N0. The Top-Down constraint mechanism operates independently of CIV events in this regime.

### 5. CSCI Exhibits Peak at N0=24, Then Collapse

CSCI std: 0.014 → 0.024 → **0.031** → 0.008

Cross-scale coherence peaks at N0=24 (the "sweet spot" for small-scale coupling), then collapses at N0=18. The N0=18 collapse is accompanied by one seed (242) with CSCI std = 0.0009 — effectively zero cross-scale coupling.

---

## Per-Seed Details

### N0=48 (baseline)
| Seed | NSI | CIV | Cont. | Depth | TP | CSCI | Sealed |
|:----:|:---:|:---:|:-----:|:-----:|:--:|:----:|:------:|
| 42 | 0.652 | 2 | 0.668 | 0.131 | 6 | 0.012 | ✅ |
| 142 | 0.693 | 1 | 0.654 | 0.211 | 10 | 0.014 | ✅ |
| 242 | 0.715 | 2 | 0.663 | 0.201 | 10 | 0.009 | ✅ |
| 342 | 0.716 | 4 | 0.655 | 0.227 | 12 | 0.020 | ✅ |

All sealed at N0=48. CIV range 1-4.

### N0=30
| Seed | NSI | CIV | Cont. | Depth | TP | CSCI | Sealed |
|:----:|:---:|:---:|:-----:|:-----:|:--:|:----:|:------:|
| 42 | 0.724 | 2 | 0.764 | 0.321 | 12 | 0.022 | ❌ |
| 142 | 0.650 | 1 | 0.652 | 0.101 | 6 | 0.020 | ✅ |
| 242 | 0.700 | 1 | 0.767 | 0.151 | 10 | 0.024 | ❌ |
| 342 | 0.675 | 1 | 0.642 | 0.196 | 8 | 0.031 | ✅ |

Two seeds (42, 242) unsealed. CIV range 1-2.

### N0=24
| Seed | NSI | CIV | Cont. | Depth | TP | CSCI | Sealed |
|:----:|:---:|:---:|:-----:|:-----:|:--:|:----:|:------:|
| 42 | 0.746 | **0** | 0.761 | 0.281 | 14 | 0.024 | ❌ |
| 142 | 0.784 | **0** | 0.757 | 0.315 | 18 | 0.036 | ❌ |
| 242 | 0.745 | **1** | 0.761 | 0.298 | 15 | 0.034 | ❌ |
| 342 | 0.726 | **0** | 0.770 | 0.231 | 13 | 0.029 | ❌ |

**All 4 seeds unsealed** at N0=24. CIV near zero. NSI peaks here (seed 142: 0.784).

### N0=18
| Seed | NSI | CIV | Cont. | Depth | TP | CSCI | Sealed |
|:----:|:---:|:---:|:-----:|:-----:|:--:|:----:|:------:|
| 42 | 0.748 | **0** | 0.790 | 0.305 | 14 | 0.009 | ❌ |
| 142 | 0.676 | **0** | 0.781 | 0.167 | 8 | 0.017 | ❌ |
| 242 | 0.676 | **0** | 0.790 | 0.141 | 8 | **0.001** | ❌ |
| 342 | 0.748 | **0** | 0.790 | 0.308 | 14 | 0.007 | ❌ |

All unsealed. Zero CIV. Seed 242 has near-zero CSCI (0.0009).

---

## Architectural Implications

### CIV Generation Depends on Something Removed

The most important finding: **the Phase 5 simplified architecture cannot generate sufficient CIV even at the proven N0=48**. In Phase 4, N0=48 passed all 8/8. The removal of AMC/ILP (or some other codebase change) has a systemic effect on CIV generation.

Two hypotheses:
1. **AMC contributed to CIV through fragmentation pulses** — AdaptiveMomentumController generated the temporal variation needed for CIV events
2. **ILP contributed to CIV through institutional stability** — InstitutionalLayerProtector maintained lower-bound constraints that allowed CIV to build up

Both were removed in Phase 5 as "redundant" based on the Phase 4 P2 Track A ablation. But that ablation may have masked their contribution through interaction effects with the Phase 4 codebase.

### NSE Can Thrive Without CIV

Narrative self-emergence (NSI 0.65-0.78) is essentially independent of CIV in this architecture. This decoupling suggests:
- NSE measures **narrative structure** (continuity, depth, turning points)
- CIV measures **novelty/variation** (rare events)
- These are different dimensions of system behavior

A complete simulation needs both — narrative coherence AND rare significant events.

---

## Recommendations for Next Steps

1. **Investigate CIV gap**: Compare Phase 4 vs Phase 5 CIV generation at N0=48. If AMC/ILP removal is the cause, consider re-integrating ILP (the minimum floor mechanism) as it was lightweight.

2. **Track C1 has clear answer**: N0=18 is the hard floor; below N0=24, CIV is effectively zero. The minimum viable N0 for CIV generation is ~30 (but with weakened CIV).

3. **Proceed to Track C2**: Time constraint (steps limit) test. The question shifts from "can it work with less space" to "can it work with less time."

4. **Or, pivot to Track D (long-term evolution)**: If CIV issue is fundamental and needs architectural fix, long-term evolution experiments are the next direction.

---

## Files

- Script: `experiments/exp_125_phase5_c1_n0_shrinking.py`
- Post-process: `experiments/post_process_exp125.py`
- Results JSON: `experiments/exp_125_c1_results_20260603_1931.json`
- Design doc: `docs/phase5_track_c1_design.md`
- This analysis: `docs/exp_125_track_c1_analysis.md`
