# Phase 9 P3 Design: Phase Transition Map

**Date**: 2026-06-05 11:03 CST
**Status**: Pre-design (awaiting P2 exp_144 results)
**Prerequisites**: P0 ✅ (2/4 PASS), P1 ✅ (3/3 PASS), P2 🚀 (running, ~2h estimate)

---

## 1. Motivation

P0 and P1 established two key facts about Phase 9 robustness:

1. **The system is extremely stable** in both N0 (6/7 N0 values produce 8/8 formation) and time (8/8 at ALL step counts 500-10000). Most hypotheses passed or failed gracefully.

2. **Sharp transitions DO exist** — the N0=24→36 boundary is the clearest: 0/8 seeds form L1 at N0=24 vs 8/8 at N0=36. This is a genuine **phase transition**, not a gradient.

P3 targets these boundaries with higher resolution to precisely map the system's stability regimes.

---

## 2. Known Boundaries (from P0/P1)

### 2.1 N0 Collapse Boundary (Confirmed Sharp)

| N0 | L1 Formation | Interpretation |
|----|-------------|----------------|
| 24 | 0/8 | Below critical mass |
| 36 | 8/8 | Above critical mass |

**Gap**: What happens at N0=26, 28, 30, 32, 34? Is the transition sharp (percolation-like) or graded?

### 2.2 No Other Sharp Boundaries Found

| Dimension | Range Tested | Result |
|-----------|-------------|--------|
| Time (steps) | 500-10000 | No transition — perfect stability |
| N0 (upper) | 48-288 | No transition — all 8/8 |
| NSI vs N0 | 36-288 | Gradient (anti-correlation), not transition |
| L1 passive | All | Invariant (divergence=0 at ALL tested points) |

### 2.3 The Seal Anomaly

Sealing never fires in P9 config (first_seal_step=-1 at ALL 56+40 runs). This is:
- Partly a **metric extraction bug** (key path mismatch)
- Partly a **configuration issue** (P9_CSC_CONFIG weakened topdown constraint to 0.10)

If P2 recalibrates and re-enables sealing, then **seal hysteresis** becomes a P3 target.

---

## 3. P3 Experimental Design

### 3.1 P3-A: N0 Collapse Boundary (Highest Priority)

**Target**: Precisely map the N0 threshold where L1 formation transitions from impossible to reliable.

**Config**:
```
N0 = [24, 26, 28, 30, 32, 34, 36]   # 7 points
seeds = 16                             # higher precision per point
max_steps = 2000
max_layers = 2
```

**Hypotheses**:

| Hyp | Description | Threshold |
|-----|-------------|-----------|
| H110 | N0 transition is sharp (≥12/16 within 2 adjacent N0 values) | Formation rate goes from ≤3/16 to ≥13/16 across ≤ 2 N0 steps |
| H111 | If graded: formation probability fits logistic with midpoint at N0≈30 | P(formation) = 1 / (1 + exp(-k(N0 - N0₀))), R² ≥ 0.85 |
| H112 | NSI at N0=24 is artifact of missing L1 constraint, not genuine narrative richness | NSI(24) > NSI(36) but structural metrics (Continuity, CIV) are lower |

**Expected**: H110 likely PASS (sharp transition at N0≈28-30)

### 3.2 P3-B: Noise-Induced Collapse (Conditional on P2)

**Target**: Only if P2 noise_scale sweep shows a critical boundary.

**Config** (if noise boundary found at e.g. ~0.10):
```
noise_scale = [0.08, 0.09, 0.10, 0.11, 0.12]  # 5 points around boundary
seeds = 16
N0 = 72
max_steps = 2000
```

**Hypotheses**:
| Hyp | Description | Threshold |
|-----|-------------|-----------|
| H113 | Noise-induced collapse is sharp (≥2× change in H1-H8 within 0.02 noise range) | H1-H8 drops from ≥12/16 to ≤4/16 across ≤ 0.02 noise step |
| H114 | CIV collapse precedes layer collapse (CIV drops before H1-H8) | mean CIV at boundary - 0.01 < mean CIV at boundary |

### 3.3 P3-C: Seal Hysteresis (Conditional on P2 + seal fix)

**Target**: Only if P2 re-enables sealing AND the metric extraction bug is fixed.

**Config** (bidirectional sweep):
```
Forward: seal_threshold = [0.005, 0.006, 0.007, 0.008, 0.009, 0.010]
Reverse: seal_threshold = [0.010, 0.009, 0.008, 0.007, 0.006, 0.005]
seeds = 16, N0 = 72, max_steps = 2000
```

**Hypotheses**:
| Hyp | Description | Threshold |
|-----|-------------|-----------|
| H115 | Seal threshold exhibits hysteresis (forward ≠ reverse) | Forward sealing threshold differs from unsealing threshold by ≥ 2× step size |
| H116 | Once sealed, system stays sealed even when threshold lowered below formation point | Seeds sealed at higher threshold remain sealed at lower threshold |

---

## 4. Implementation

### 4.1 New File

`experiments/exp_145_phase9_p3_phase_transition.py`

### 4.2 Execution Order

```
Step 1: P3-A (N0 collapse boundary)     → ~1h (7×16=112 runs, 2000 steps)
Step 2: P3-B (Noise collapse, if needed) → ~0.5h (5×16=80 runs)
Step 3: P3-C (Seal hysteresis, if needed) → ~0.5h (12×16=192 runs, but short per run)
```

### 4.3 Flow Control

The script should auto-evaluate P2 results to decide whether P3-B and P3-C run:
- Read exp_144 final JSON
- If noise boundary exists (H101 failed or marginal) → queue P3-B
- If seals detected (any first_seal_step > 0) → queue P3-C
- Otherwise, only run P3-A

---

## 5. Expected Output

A **Phase Stability Diagram** with:

```
                     N0 →
       ┌─────────────────────────────────┐
       │  NO LAYER  │ OPERATING REGIME    │
       │  (collapse) │  (stable layers)    │
       │   N0<28    │  N0≥30              │
       │   0/16 L1  │  16/16 L1           │
       │            │                     │
  N0   │  ──── sharp transition ────      │
  24   │  26  28  30  32  34  36  48...   │
       └─────────────────────────────────┘
                        │
              P3 maps this boundary precisely

          ┌─────────────────────────┐
          │ Additional transitions  │
          │ (if P2 finds them):     │
          │ Noise → chaos          │
          │ Seal hysteresis        │
          └─────────────────────────┘
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| N0 transition already fully resolved by P0 (between 24-36, no fine structure) | Medium | Low | Fine mapping at N0=[25,27,29,31,33,35] as fallback |
| P3-B/C never needed (P2 finds no boundaries) | Low | Medium | P3 becomes single-experiment (P3-A only) — acceptable |
| 16 seeds insufficient for P3-A precision | Low | Medium | Increase to 24 seeds (21-min extension per point) |
| Seal metric still broken in P3 | Medium | Low | Document as known limitation; proceed without P3-C |

---

## 7. Preparation Checklist

- [ ] P0 complete (2/4 PASS) ✅
- [ ] P1 complete (3/3 PASS) ✅
- [ ] P2 running (exp_144) 🚀
- [ ] P3-A design complete (this document) ✅
- [ ] P3-B design conditional (waiting P2 noise results)
- [ ] P3-C design conditional (waiting P2 seal + metric fix)
- [ ] Script implementation (exp_145_phase9_p3_phase_transition.py) ⬜
- [ ] Run after P2 completes

---

*Design written: 2026-06-05 11:03 CST*
*Author: Agent (Heartbeat)*