# Experiment Report: Phase 3 Experiment 2 - Full Integration

## Info

- **Time**: 20260528_032431
- **Elapsed**: 4.05s
- **Config**: N0=48, steps=500
- **Sample interval**: 10, P1 interval: 10

## Layer Info

| Layer | Status | N | Weight | Steps | Clusters |
|---|---|---|---|---|---|
| 0 | Sealed | 48 | 16 | 500 | 5 |
| 1 | Open | 12 | 6 | 0 | 0 |

## Phase 3 Metrics

| Metric | Value |
|---|---|
| MSI (latest) | 0.0000 |
| MSI detected | No |
| Anticipation accuracy | 0.0000 |
| Counterfactual active | No |
| Counterfactual branches | 1 |

## Analysis

| Metric | Value |
|---|---|
| ODI max | 0.6808 |
| ODI mean | 0.0661 |
| ODI final | 0.6802 |
| ODI > 0.5 ratio | 10.00% |
| ODI zone distribution | {'pre_subjective_deep': 5} |
| MSI max | 0.0000 |
| 6T max | 6 |
| 6T mean | 0.60 |
| 6T all-met ratio | 10.00% |
| Convergence ratio | 0.00% |
| Ant-ODI correlation | -0.5674 |
| CF active ratio | 0.00% |

## Acceptance Criteria

- **A_ODI_reaches_05**: PASS
- **B_MSI_grows_after_05**: FAIL
- **C_anticipation_positive_corr**: FAIL
- **D_counterfactual_active**: FAIL

**Overall**: FAIL

## Key Finding

## Timeseries (ODI > 0 entries)

| Step | Layer | ODI | Zone | 6T met | Conv | MSI | Ant.Conf | CF | 7th conf |
|---|---|---|---|---|---|---|---|---|---|
| 90 | 0 | 0.6308 | pre_subjective_deep | 6 | N | 0.0000 | 0.5764 | N | 0.0000 |
| 190 | 0 | 0.6308 | pre_subjective_deep | 6 | N | 0.0000 | 0.2757 | N | 0.0000 |
| 290 | 0 | 0.6808 | pre_subjective_deep | 6 | N | 0.0000 | 0.2910 | N | 0.0000 |
| 390 | 0 | 0.6803 | pre_subjective_deep | 6 | N | 0.0000 | 0.2871 | N | 0.0000 |
| 490 | 0 | 0.6802 | pre_subjective_deep | 6 | N | 0.0000 | 0.2986 | N | 0.0000 |

## Theoretical Mapping

1. **ODI plateau** <- The system self-organizes to a structuring equilibrium below pre-subjective
2. **5/6 threshold bottleneck** <- One threshold (3.5) consistently fails, preventing full pre-subjective convergence
3. **Phase 3 inactive** <- Without crossing ODI=0.5, the structural conditions for minimal self are not met
4. **Implication** <- Either more steps, different initial conditions, or parameter tuning is needed

## Next Steps

- Investigate why threshold 3.5 consistently fails (which threshold is this?)
- Try larger N0 or different initial conditions to push ODI higher
- Run with only Phase 2 components (no Phase 3 overhead) to isolate the bottleneck
- Phase 3 Experiment 3: MSI growth curve (once ODI > 0.5 is achieved)


---
*Auto-generated at 20260528_032431*
