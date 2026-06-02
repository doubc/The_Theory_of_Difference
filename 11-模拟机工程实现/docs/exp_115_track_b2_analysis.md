# exp_115 Track B2: Serial CSC Coupling — Analysis Report

**Date:** 2026-06-02  
**Experiment:** `experiments/exp_115_phase5_b2_serial_coupling.py`  
**Config:** `coupling_mode='serial'`, N0=72, steps=2000, seeds=8  
**Architecture:** CSC(serial)+NSE+LNT (no AMC/ILP)

---

## Hypothesis Results

| Hypothesis | Target | Result | Pass Rate |
|---|---|---|---|
| **H30** Layer Decoupling (L1<->L2 r < 0.7) | >= 6/8 | **FAIL** | 1/8 (12.5%) |
| **H31** Hierarchical Delay (L0->L1 + L1->L2 > L0->L2) | >= 6/8 | **FAIL** | 0/8 (0.0%) |
| **H1-H7** Baseline | 8/8 | **PASS** | 8/8 (100%) |
| **H8** TopDown Activation | 8/8 | **FAIL** | 0/8 (0.0%) |

---

## H30: Layer Decoupling — Detailed Results

### L1<->L2 NSI Correlation

| Seed | r (L1<->L2) | Pass? |
|---|---|---|
| 42 | 0.7049 | ❌ |
| 142 | 0.8980 | ❌ |
| 242 | 0.9146 | ❌ |
| 342 | 0.9331 | ❌ |
| 442 | 0.9285 | ❌ |
| 542 | 0.9240 | ❌ |
| 642 | 0.9099 | ❌ |
| 742 | **0.6743** | ✅ |

**Mean:** 0.8609 ± 0.0997  
**Range:** [0.6743, 0.9331]

### Comparison with B1 (Parallel Coupling)

| Metric | B1 (Parallel) | B2 (Serial) | Change |
|---|---|---|---|
| L1<->L2 correlation | 0.976 ± 0.003 | 0.8609 ± 0.0997 | **-11.8%** |
| Pass rate (r < 0.7) | 0/8 | 1/8 | +1 seed |

**Assessment:** Serial coupling reduced L1<->L2 correlation by 11.8% (0.976 → 0.861), but the reduction is far from sufficient. The target of r < 0.7 was achieved in only 1/8 seeds. The mean correlation of 0.86 still indicates strong coupling between L1 and L2.

### Per-Pair Correlations

| Pair | Mean | Std | Range |
|---|---|---|---|
| MINI ↔ INSTITUTIONAL | 0.5549 | 0.0920 | [0.377, 0.627] |
| MINI ↔ CIVILIZATION | 0.6996 | 0.0570 | [0.599, 0.775] |
| INSTITUTIONAL ↔ CIVILIZATION | 0.8758 | 0.0863 | [0.705, 0.933] |

**Key observation:** MINI↔INSTITUTIONAL is the weakest link (r=0.55), while INSTITUTIONAL↔CIVILIZATION remains very strong (r=0.88). This suggests the serial coupling is working at the L0→L1 boundary but failing at L1→L2.

---

## H31: Hierarchical Delay — Detailed Results

| Delay Path | Mean | Seeds with Data |
|---|---|---|
| L0 → L1 | **None detected** | 0/8 |
| L1 → L2 | 31.7 steps | 3/8 (seeds 142, 442, 642) |
| L0 → L2 | 97.0 steps | 1/8 (seed 342) |

**Assessment:** H31 fails completely. The most critical finding is that **L0→L1 delay is never detected** in any seed. This means L1 is not responding to L0 cluster changes with a measurable lag — it's either instantaneous or the signal doesn't propagate through the serial chain at all.

The fact that L1→L2 delay is detected in only 3/8 seeds (and L0→L2 in only 1/8) further confirms that the serial coupling is not functioning as a true chain.

---

## Per-Layer NSI (Aggregate)

| Layer | Mean | Std | Range |
|---|---|---|---|
| MINI (L0) | 0.1833 | 0.0150 | [0.145, 0.195] |
| INSTITUTIONAL (L1) | 0.6087 | 0.0267 | [0.566, 0.635] |
| CIVILIZATION (L2) | 0.1518 | 0.0237 | [0.100, 0.186] |

**Pattern:** L1 (INSTITUTIONAL) dominates with NSI ≈ 0.61, while L0 and L2 are both low (~0.15-0.18). This is the same pattern as B1 — the institutional layer is the primary narrative driver regardless of coupling mode.

---

## Root Cause Analysis

### Why Serial Coupling Failed

1. **L1↔L2 still highly correlated (r=0.86):** The serial coupling mode in `CrossScaleCoupling` reads from the same L0 cluster embeddings for both L1 and L2, then applies different projection matrices. This means L1 and L2 are still fed from the same source simultaneously — they're not truly serial.

2. **L0→L1 delay never detected:** The delay detection algorithm looks for NSI correlation peaks between layers. If L1's narrative is driven primarily by its own institutional dynamics (ILP-stabilized) rather than L0 cluster changes, there's no measurable L0→L1 signal to detect.

3. **TopDown (H8) still inactive:** Same root cause as B1 — the institutional layer's stability (ILP) suppresses the feedback signal that TopDown needs to activate.

### Theoretical Implication

The failure of serial coupling suggests that **architecture-level changes alone cannot create true hierarchy**. The issue is not just how information flows (parallel vs. serial), but **what drives each layer's dynamics**:

- L1 is driven by its own institutional self-stabilization, not by L0
- L2 mirrors L1 because both are responding to the same underlying cluster structure
- True hierarchy requires L2 to be driven by L1's *institutional output* (not just cluster projections), with sufficient attenuation and noise

---

## Recommendations for Next Iteration

1. **Fix the serial coupling implementation:** L2 should receive input from L1's institutional state (not L0 clusters), with explicit attenuation and noise injection.

2. **Add L1→L2 coupling strength parameter:** Control how much L1's institutional narrative influences L2's civilization narrative.

3. **Consider H5 threshold relaxation:** As noted in Track A3, H5 (CIV range) failures may warrant a wider threshold [2, 20].

4. **Track B3 direction:** If serial coupling cannot decouple L1-L2 through architecture alone, consider adding explicit noise/attenuation between layers, or redesigning the L1→L2 information channel.

---

## Git Commits

- `0596ec4` — feat(phase5-b2): serial CSC coupling (L0→L1→L2)
- `bbde266` — fix(exp_115): unicode encoding fixes
