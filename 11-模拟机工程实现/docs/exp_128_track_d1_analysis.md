# exp_128 — Phase 5 Track D1: Long-Term Evolution (5000 steps)

**Date**: 2026-06-04  
**Config**: N0=48, 8 seeds (42,142,242,342,442,542,642,742), 5000 steps  
**Stack**: CSC+NSE+NarrativeLevelBooster (min_civ=3)  

---

## Baseline H1-H8: ALL PASS (8/8) ✅

All 8 core emergence hypotheses pass at 5000 steps. The system is robust at long time scales.

| Hypothesis | Result | Key Metrics |
|---|---|---|
| H1 (NSI max) | PASS | mean max=0.88 |
| H2 (NSI active rate) | PASS | 0.982 (all seeds) |
| H3 (continuity) | PASS | 0.887 mean |
| H4 (history depth/turning pts) | PASS | depth=0.43, tp=22.2 |
| H5 (CIV max>=3) | PASS | max=4.0 (seed 342,542) |
| H6 (CIV max>=2) | PASS | max=4.0 |
| H7 (CSCI std>0.005) | PASS | 0.0109 mean |
| H8 (TopDown>=2 seeds) | PASS | 8/8 seeds |

## Track D1 Hypotheses

| Hyp | Description | Result | Detail |
|---|---|---|---|
| **H36** | Long-term stability (H1-H8 pass at 5000) | **PASS** ✅ | All 8/8 core hypotheses pass |
| **H37** | Secondary transition | **PASS** ✅ | 6/8 seeds show >10% NSI increase in phase 3 (threshold >=4) |
| **H38** | Narrative maturity | **FAIL** ❌ | 0/8 seeds have >=70% CIV in first 2500 steps |
| **H39** | NSI stability | **FAIL** ❌ | 1/8 seeds (seed 442) within +/-15% drift |
| **H_D1_1** | Multi-layer persistence | **FAIL** ❌ | 0/8 seeds -- no hierarchical layer activation |

**Track D1 Total: 2/5 PASS**

---

## Detailed Analysis

### Secondary Transitions (H37 PASS)

6/8 seeds exceed >10% NSI increase in phase 3:
- seed 42: +11.3%
- seed 142: +12.6%
- seed 242: +14.2%
- seed 342: **+21.4%** (strongest)
- seed 542: +11.5%
- seed 642: **+21.6%** (strongest)
- Failed at threshold: seed 442 (+7.8%), seed 742 (+9.9%)

**Phase progression** (all-seed means):
- Phase 1 (0-1666): NSI=0.493
- Phase 2 (1667-3333): NSI=0.706 (+43%)
- Phase 3 (3334-5000): NSI=0.802 (+14% from phase 2)

NSI continues to grow monotonically across all three phases -- no plateau detected.

### Narrative Maturity (H38 FAIL)

CIV is **perfectly evenly distributed** across all seeds:
- First half CIV sum: 49.8% (mean 49.80-49.89% across all seeds)
- Second half CIV sum: 50.2%

This is a direct consequence of the NarrativeLevelBooster: it ensures steady CIV events at every step (499/500 steps have boost events). The booster maintains a constant CIV supply, eliminating the natural front-loading that would create "maturity."

**Root cause**: The booster's `min_civ=3` forces CIV events every step in a sustained pattern. Without it, natural CIV fades after the initial exploration phase.

### NSI Stability (H39 FAIL -- Upward Drift)

- Only seed 442 passes: drift 9.9% (from NSI=0.724 at step 2000 -> 0.796 at final)
- All 7 failing seeds show **upward drift** (NSI continues rising):
  - seed 42: 0.700 -> 0.856 (+22.3%)
  - seed 342: 0.597 -> 0.873 (+46.2%)
  - seed 642: 0.671 -> 0.878 (+30.9%)

This is not "instability" in the degradation sense -- NSI never drops. The system continues to develop deeper narratives, which is arguably a feature, not a bug. But it means NSI doesn't converge to a plateau within 5000 steps.

### Multi-Layer Persistence (H_D1_1 FAIL)

0/8 seeds trigger PerLayerMetrics. This is expected -- the N0=48 configuration doesn't use hierarchical evolution. PerLayerMetrics is only active when MultiLayerManager's `tracking_callback` is passed to the evolver (requires B7/B8 hierarchical infrastructure).

---

## Conclusions

### What Worked ✅
1. **Core system is robust at 5000 steps** -- H1-H8 all pass, no degradation
2. **Secondary transitions occur** -- 75% of seeds show continued narrative growth in phase 3
3. **Growth is monotonic** -- NSI never drops (upward drift, not oscillation)
4. **Booster maintains steady CIV** -- all seeds achieve CIV max=3-4

### What Failed ❌
1. **No narrative maturity** -- CIV is evenly distributed because the booster sustains it
2. **No NSI plateau** -- system keeps improving, never stabilizes within 5000 steps
3. **Multi-layer not tested** -- requires hierarchical evolution infrastructure

### Recommendations
1. **Relax H39** -- The "instability" is upward-only growth, not oscillation. Either extend the threshold or redefine as "monotonic non-decreasing NSI"
2. **H38 definition issue** -- With the booster, CIV maturity can never happen by design. Consider removing this hypothesis or running without booster
3. **Multi-layer requires B7/B8** -- H_D1_1 depends on hierarchical seal+encapsulation being active; can't pass at N0=48 single-layer
4. **Run a non-booster baseline at 5000 steps** -- To compare natural CIV distribution vs boosted

---

## Raw Data

Results JSON: `experiments/exp_128_d1_results_20260604_0604.json`