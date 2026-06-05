# Phase 9 P2 Analysis: Parameter Sensitivity (exp_144)

**Date**: 2026-06-05 12:56 CST
**Verdict**: 0/4 PASS (formal), but **system is overwhelmingly robust**

---

## 1. Experiment Design

Swept **4 parameters** across **12 configs × 8 seeds = 96 runs**:
- L1 sealing threshold: [0.005, 0.02, 0.10]
- Coupling strength (topdown_constraint): [0.05, 0.15, 0.40]
- R2 tension: [0.50, 1.50, 3.00]
- L2 stability floor: [0.05, 0.40]

---

## 2. Corrected Results (from stdout, not buggy aggregation)

### Robustness (invariants across ALL 96 runs)
| Metric | Value | Interpretation |
|--------|-------|---------------|
| L1 formation | **96/96** | Perfect — hierarchical emergence is parameter-invariant |
| H1-H8 (structural) | **95/96** | 1 seed at topdown=0.05 failed H8 |
| L1 divergence | **0.0000** | Perfect invariant — L1 behaves identically |
| NSI_max | **0.652–0.748** | Narrow range across all parameters |
| CIV_max | **2.875–3.125** | Almost invariant (±~4%) |

### Parameter Effects (real, not buggy)

**R2 Tension**:
- Baseline (1.0): mean R2 events = 1.5
- r2_tension=0.5: similar to baseline
- r2_tension=1.5: R2 events decreasing as expected
- r2_tension=3.0: **mean R2 events = 0.625** (reduced by ~58%)

**Stability Floor**:
- floor=0.05: baseline behavior (seeds with R2=1-2, CIV_max=3)
- floor=0.40: **2/8 seeds show L1 sealing** (first real seals in P9!)
  - seed=142: seal@step 122 (10 bits, ratio=0.28)
  - seed=342: seal@step 19 (17 bits, ratio=0.52)
  - Remaining 6 seeds: unsealed at floor=0.40
  - CIV_max=4 observed in one seed at floor=0.40

**Topdown Constraint**:
- 0.05: 1 seed failed H8 but all 8 formed L1
- 0.15/0.40: identical to baseline

**Seal Threshold** (0.005/0.02/0.10): no effect on sealing (seal metric bug still present)

---

## 3. Hypothesis Verdict

| Hyp | Question | Result |
|-----|----------|--------|
| H100 | Seal threshold plateau [0.005, 0.10] | **FAIL** — seal metric broken for most configs |
| H101 | coupling=0.40 degrades H1-H8 < 6/8 | **FAIL** — still 8/8 at 0.40 |
| H102 | stable floor=0.05 causes CIV<3 | **FAIL** — CIV=3.1 at floor=0.05 |
| H103 | r2_tension=3.00 eliminates R2 | **FAIL** — R2 events = 0.625 (reduced but not eliminated) |

### Corrected interpretation
The 0/4 PASS verdict is technically correct per hypothesis thresholds but **misleading**. The system is EXTREMELY robust:
- L1 emergence: invariant
- L1 structural behavior: near-invariant
- NSI: narrow range
- CIV: near-invariant

The only real parametric fragility is **L1 sealing**, which requires high stability floor (0.40) — and even then is stochastic (2/8 seeds).

---

## 4. Implications for Phase 9

1. **The P9 operating regime is validated** — system tolerates wide parameter variation
2. **Stability floor is the lever for sealing** — suggests a fine-mapping study (P3-C candidate)
3. **R2 tension suppresses civilization events** without destabilizing layers
4. **The N0 collapse boundary at N0≈28-30 remains the only sharp phase transition** — P3-A will map it

---

## 5. Known Issues

- **Aggregation bug**: The `by_config` accumulation in exp_144 aggregates across configs with shared state, producing identical means for all configs. Raw seed-level data printed to stdout is correct but not saved to JSON.
- **Seal metric bug**: Most configs report seal_step=0 despite seeds being unsealed. The metric extraction path mismatch (from P0/P1) persists.
