# Phase 9 Planning: Robustness Cartography & Parameter Space

**Date**: 2026-06-05 03:46 CST  
**Status**: Planning — Phase 8 COMPLETE ✅ (L1 = passive constraint, exp_141)  
**Git context**: `b97deae` (Phase 8 P4 exp_141 final)

---

## 1. Why Phase 9 Now

### 1.1 What's Been Established

| Phase | Verified | Scale |
|-------|----------|-------|
| Phase 4 | CSC+NSE core architecture (AMC/ILP removed as redundant) | N0=72 |
| Phase 5 B1-B10 | L0→L1→L2→L3 cascade, layer dynamics | N0=48-72, 2000-10000 steps |
| Phase 6 P1-P6 | NRC R→P feedback closed (R0, R1, R2) | N0=72 |
| Phase 7 | Full spiral integration (NRC + layers, exp_136: 4/5 PASS) | N0=72 |
| Phase 8 P0-P4 | L1 = passive constraint provider (honest confirmation, 32+ seeds) | N0=72, max_layers=2 |

### 1.2 The Gap

**Every single experiment** runs at or near N0=72 with similar parameter ranges. We have *no idea* whether:
- The architecture works at N0=36 (half the cells)
- The architecture works at N0=288 (4× the cells)
- The layer dynamics persist at 500 steps vs 10000 steps
- Key parameters (noise, bias, seal thresholds) have wide stability basins or narrow sweet spots
- There exist phase transitions where the system collapses, diverges, or enters a different regime

### 1.3 What Phase 9 Is Not

Phase 9 is **not** a new architectural feature (no new modules, no new coupling mechanisms).
Phase 9 is **not** a theory-validation exercise.
Phase 9 is **cartography** — mapping the terrain we already have.

---

## 2. Phase 9 Structure

### 2.1 Sub-Phases Overview

| Sub-phase | Focus | Experiments | Success Criteria |
|-----------|-------|-------------|------------------|
| **P0** | N0 Scaling | 5-6 N0 values × 8 seeds | Layer formation rate ≥ 75% across N0 range |
| **P1** | Time Scaling | 4-5 step counts × 8 seeds | H1-H8 pass rate stable across ranges |
| **P2** | Parameter Sensitivity | 6-8 params × 3-5 values each | Identify stability boundaries |
| **P3** | Phase Transition Map | Targeted sweeps at boundaries | Document collapse/divergence regimes |

### 2.2 Total Experiment Budget

| Sub-phase | Experiments | Seeds | Total Runs |
|-----------|------------|-------|------------|
| P0 | 6 | 8 | 48 |
| P1 | 5 | 8 | 40 |
| P2 | 8 | 8 | 64 |
| P3 | 4 | 16 | 64 |
| **Total** | **23** | — | **~216** |

Estimated runtime: ~6-12 hours wall clock (depends on max N0 and steps per experiment).

---

## 3. P0: N0 Scaling

### 3.1 Motivation

All Phase 4-8 experiments use N0 ∈ {48, 72}. We need to know:
- Does layer formation require a minimum cell count?
- Do larger systems produce richer dynamics or just noise?
- Is there an optimal N0 where layer diversity peaks?

### 3.2 Candidates

| N0 | Rationale | Layer Formation (Hypothesis) |
|----|-----------|------------------------------|
| 24 | Minimum — less than L0+2L1 | Unlikely to form stable layers |
| 36 | Half-current — resource constraint | Marginal formation (H86-alt: <4/8) |
| 48 | Phase 5 B6-B8 scale | Expected: 6-8/8 formation |
| **72** | **Baseline** — all Phase 4-8 | **8/8 formation** (known) |
| 96 | 33% larger | Expected: 8/8 (more diversity?) |
| 144 | 2× baseline | Expected: 8/8 but longer convergence |
| 288 | 4× baseline | Unknown — may show scaling limitations |

### 3.3 Configuration per Experiment

```
N0 = [24, 36, 48, 72, 96, 144, 288]  # 7 experiments
seeds = 8
max_steps = 2000
max_layers = 2  # Phase 8 validated
architecture = CSC + NSE + NRC + Booster
```

### 3.4 Hypotheses (P0)

| Hyp | Description | Threshold |
|-----|-------------|-----------|
| H90 | Layer formation ≥ 6/8 seeds at N0 ≥ 36 | H86-alt metric |
| H91 | NSI monotonic with N0 (more cells → richer narrative) | Mean NSI(N0) correlation > 0.5 |
| H92 | Convergence time scales sub-linearly with N0 | Steps to first seal ≤ 0.5 × N0 |
| H93 | L0-L1 divergence remains 0 at all N0 | Confirm L1 passive across scales |

---

## 4. P1: Time Scaling

### 4.1 Motivation

Most experiments run for 2000 steps. Phase 5 B8 ran for 10000. We need to know:
- How early do layers form? (Step 100? Step 500?)
- Do long runs (5000+) reveal degradation?
- Is there a "golden window" for narrative development?

### 4.2 Candidates

| Steps | Rationale | Expected |
|-------|-----------|----------|
| 500 | Ultra-short — can layers form? | Likely <4/8 formation |
| 1000 | Short — minimum viable? | 4-6/8 formation |
| **2000** | **Baseline** | **8/8 formation** (known) |
| 5000 | Extended — stability test | 8/8 formation, no degradation |
| 10000 | Long — Phase 5 B8 repeat | 8/8 formation, no degradation |

### 4.3 Configuration per Experiment

```
N0 = 72
seeds = 8
max_steps = [500, 1000, 2000, 5000, 10000]
max_layers = 2
```

### 4.4 Hypotheses (P1)

| Hyp | Description | Threshold |
|-----|-------------|-----------|
| H95 | Layer formation detectable by step 500 | ≥4/8 seeds with partial seal by step 500 |
| H96 | H1-H8 pass rate stable at 2000+ steps | No more than 1 degradation per 2000 step interval |
| H97 | NSI growth saturates before step 5000 | Mean NSI at step 4000 and step 5000 within 5% |

---

## 5. P2: Parameter Sensitivity

### 5.1 Motivation

The architecture has ~20 parameters. We've tuned them heuristically. We need to know:
- Which parameters are critically sensitive?
- Which parameters have wide stability basins?
- Where are the failure boundaries?

### 5.2 Parameters to Sweep

| Parameter | Baseline | Range | Rationale |
|-----------|----------|-------|-----------|
| **seal_threshold** | 0.20 | [0.05, 0.10, 0.20, 0.30, 0.45] | Controls layer creation rate |
| **seal_probability** | 0.10 | [0.03, 0.06, 0.10, 0.15, 0.25] | Controls how aggressive sealing is |
| **noise_scale** | 0.05 | [0.01, 0.03, 0.05, 0.10, 0.20] | Controls background randomness |
| **coupling_strength** | 0.50 | [0.20, 0.35, 0.50, 0.65, 0.80] | Controls L0→L1 coupling |
| **nrc_tension_threshold** | 0.50 | [0.20, 0.35, 0.50, 0.65, 0.80] | Controls NRC activation frequency |
| **r2_tension_threshold** | 1.00 | [0.50, 0.75, 1.00, 1.25, 1.50] | Controls R2 (civilizational) trigger |
| **booster_lookback** | 10 | [5, 10, 20, 40] | Controls narrative memory |
| **stability_floor** | 0.15 | [0.05, 0.10, 0.15, 0.20, 0.30] | Controls minimum stability for layers |

### 5.3 Experimental Strategy

Each parameter is swept independently at N0=72, 8 seeds, 2000 steps. Other parameters held at baseline.

**8 parameters × 5 values each = 40 experiments total.**

But to conserve compute, use a two-pass strategy:
- **Pass 1 (coarse sweep)**: 3 extreme values (min, mid, max) → 8×3 = 24 experiments
- **Pass 2 (fine resolution)**: Only for parameters with narrow stability basins → additional 2-3 values

### 5.4 Hypotheses (P2)

| Hyp | Description | Threshold |
|-----|-------------|-----------|
| H100 | seal_threshold stability basin width ≥ 0.15 (20→25% range) | Layer formation ≥ 6/8 across threshold range |
| H101 | noise_scale critical boundary at ~0.10 (above = system collapse) | H1-H8 pass rate drops below 4/8 above boundary |
| H102 | coupling_strength has U-shaped effect (too low = no coupling, too high = fusion) | L0-L1 divergence peaks at mid coupling values |
| H103 | booster_lookback has diminishing returns beyond 20 | NSI(20) - NSI(40) < 0.05 |

---

## 6. P3: Phase Transition Map

### 6.1 Motivation

P0-P2 may reveal boundaries where the system qualitatively changes behavior. P3 targets those boundaries with higher-resolution sweeps and larger seed counts to precisely map the transitions.

### 6.2 Candidates (to be determined by P0-P2 results)

Likely candidates for P3:
- **N0→0 collapse boundary**: The minimum N0 where any layer forms
- **Noise→chaos transition**: The noise threshold where stable structures dissolve
- **Coupling freeze boundary**: The coupling value where L1 ceases to be distinguishable from L0
- **Seal hysteresis**: Crossing seal threshold from below vs from above (hysteresis effect)

### 6.3 Configuration

```
Targeted at sub-phases P0-P2 results
16 seeds per boundary point (higher precision)
3000 steps max (boundaries may be fragile)
```

### 6.4 Expected Output

A **stability phase diagram** showing:

```
                    noise_scale →
       ┌─────────────────────────────────┐
       │       NO MAN'S LAND             │
       │     (no stable layers)          │
       │                                 │
  N0   │         OPERATING REGIME        │
       │    ┌─────────────────────┐      │
       │    │  Phase 4-8 proven   │      │
       │    │  N0=72, noise=0.05  │      │
       │    └─────────────────────┘      │
       │                                 │
       │       SCALING LIMIT             │
       └─────────────────────────────────┘
```

---

## 7. Implementation Plan

### 7.1 New Files

| File | Purpose |
|------|---------|
| `experiments/exp_142_phase9_p0_n0_scale.py` | N0 scaling experiment (P0) |
| `experiments/exp_143_phase9_p1_time_scale.py` | Time scaling experiment (P1) |
| `experiments/exp_144_phase9_p2_params.py` | Parameter sensitivity (P2) |
| `experiments/exp_145_phase9_p3_phase_transition.py` | Phase transition map (P3) |
| `docs/phase9_robustness_cartography.md` | This plan (current file) |

### 7.2 Reused Infrastructure

All existing modules without modification:
- `engine/hierarchical_evolver.py` (CSC+NSE+NRC)
- `layers/hierarchy_manager.py`
- `layers/axioms_v2.py`
- `engine/narrative_recursive_closure.py`
- Existing metrics and analysis scripts

### 7.3 Execution Order

```
Phase 9:
  P0 (N0 scaling)        → 7 experiments × 8 seeds → ~2 hours
  P1 (time scaling)      → 5 experiments × 8 seeds → ~3 hours (10000-step runs)
  P2 pass 1 (coarse)     → 24 experiments × 8 seeds → ~3 hours
  P2 pass 2 (fine)       → conditional → ~1 hour
  P3 (phase transition)  → 4 experiments × 16 seeds → ~3 hours (if needed)
  Final report
Total estimated wall clock: 8-12 hours (can be parallelized)
```

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| N0=288 runs are too slow | Medium | Medium | Reduce steps to 1000 for large N0 |
| Parameters too correlated for independent sweep | High | Medium | Use Latin hypercube design in P2 pass 2 if needed |
| Phase boundaries are smooth, not sharp | High | Low | Document as "gradient regime" not "phase transition" |
| System always works (no boundaries found) | Low | High | Extend to N0=576 + noise=0.50 until breaking |
| P2 generates 40 experiments instead of 24 | Medium | Low | Accept ~5 hours for P2 instead of ~3 |

---

## 9. Next Steps

1. ✅ Phase 8 complete (03:16, 2026-06-05)
2. ✅ Phase 9 plan written (this document)
3. ⬜ Implement `exp_142_phase9_p0_n0_scale.py`
4. ⬜ Run P0 (N0 scaling) — highest priority
5. ⬜ Based on P0 results, proceed to P1/P2

**First action**: Implement and run `exp_142_phase9_p0_n0_scale.py` with N0=[24, 36, 48, 72, 96, 144, 288], 8 seeds each, 2000 steps.

---

*Plan written: 2026-06-05 03:46 CST*
*Author: Agent (Heartbeat)*