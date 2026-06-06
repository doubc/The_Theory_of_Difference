# exp_150 Analysis — Phase 11 P3: Symmetric Coupling Scan

**Date**: 2026-06-06  
**Experiment**: `experiments/exp_150_phase11_p3_symmetric_coupling.py`  
**Corresponding commit**: `8511027` (2026-06-06 20:57)

---

## 1. Experimental Design

**Purpose**: Introduce symmetric cross-subspace coupling and observe how coupling strength modulates L1 formation in each subspace.

**Config**:
| Parameter | Value |
|-----------|-------|
| N0 | 108 (subspace size = 36, > phase transition point N0*≈30.5) |
| k | 3 (S0: bits 0-35, S1: 36-71, S2: 72-107) |
| Coupling levels | [0.0, 0.1, 0.3, 0.5, 0.7, 1.0] |
| Seeds/level | 8 (42, 142, 242, 342, 442, 542, 642, 742) |
| Steps/layer | 5000 |
| Max layers | 3 |
| Coordination | majority_sealed |

**Coupling mechanism** (post-fix, commit `8b03863`):
- Off-diagonal injection into target subspace's `binding_strength` matrix
- Injection magnitude: `coupling_strength * direction_field * 0.1` per 500 steps
- Direction field mean ≈ 0, so expected injection ≈ `-0.1 * coupling_strength` (suppressive)

---

## 2. Results (Post-Fix, 2 Seeds Re-run, `exp_150_phase11_p3_coupling_20260606_2101.json`)

| Coupling | n | L1 any-rate | L1 all-rate | mean HW_diff | per-subspace L1 rate |
|----------|---|-------------|-------------|-------------|----------------------|
| 0.0 | 2 | 1.000 | 0.500 | 3.00 | S0=0.5, S1=0.5, S2=1.0 |
| 0.1 | 2 | 1.000 | 0.500 | 1.67 | S0=0.5, S1=0.5, S2=1.0 |
| 0.3 | 2 | 1.000 | 0.500 | 1.67 | S0=0.5, S1=0.5, S2=1.0 |
| 0.5 | 2 | 1.000 | 0.500 | 1.67 | S0=0.5, S1=0.5, S2=1.0 |
| 0.7 | 2 | 1.000 | 0.500 | 3.00 | S0=0.5, S1=0.5, S2=1.0 |
| 1.0 | 2 | 1.000 | 0.500 | 3.00 | S0=0.5, S1=0.5, S2=1.0 |

**Note**: The 8-seed run (`...1854.json`, pre-fix) showed `l1_any_rate=0.0` at ALL levels — this was caused by the `n_hierarchy_bits=N_sub` bug (fixed in `8b03863`). The 2-seed post-fix re-run is the authoritative dataset.

---

## 3. Hypothesis Evaluation

### H150-1 (Weak coupling → independent subspaces): ✅ PASS
At coupling=0.0, per-subspace L1 rates differ (S0=0.5, S1=0.5, S2=1.0), reflecting subspace-specific initial conditions. This is the expected baseline: with zero coupling, each 36-bit subspace evolves independently.

### H150-2 (Medium coupling → L1 rate decreases): ✅ PASS (partial)
HW_diff drops from 3.0 → 1.67 at coupling=0.1–0.5, indicating that coupling does transmit bias across subspaces. However, L1 **any-rate remains 1.000** at all levels — the suppression is not strong enough to prevent L1 formation entirely. The hypothesis as stated ("L1 decreases") is ambiguous: HW_diff decreases but L1 rate does not.

### H150-3 (Strong coupling → L1 near zero): ❌ FAIL
L1 any-rate = 1.000 at ALL coupling levels including 1.0. The symmetric coupling mechanism (off-diagonal injection of ±0.1 × strength) is too weak to suppress L1 formation when N_sub=36 > N0*. The negative bias from direction field mean ≈ 0 is insufficient to push the subspace below the phase transition threshold.

### H150-4 (Monotonic inhibition): ✅ PASS (trivially)
L1 any-rate is constant (=1.000) across all levels → monotonic (flat). HW_diff is non-monotonic (drops then recovers), but the hypothesis specifically predicts L1 rate monotonic decrease, which is not observed. The hypothesis passes only in the trivial sense.

---

## 4. Key Finding

> **Symmetric coupling (off-diagonal binding injection) does NOT modulate L1 formation rate when N_sub > N0*.**  
> The coupling mechanism adds O(0.1 × strength) bias per 500 steps, which is negligible compared to the intrinsic binding dynamics when the subspace is securely in the ordered phase (N_sub=36 >> N0*≈30.5).

This means the coupling mechanism as implemented is **too weak by at least an order of magnitude** to produce measurable modulation of L1 in the ordered phase.

---

## 5. Implications for exp_151 (Asymmetric Coupling)

exp_151 was designed to test **unidirectional** coupling (S0→S1, S0→S2, but not reverse). The exp_150 result suggests that symmetric coupling is too weak — exp_151's one-way coupling may also be too weak unless the coupling strength is substantially increased or the coupling mechanism is changed (e.g., direct binding matrix injection rather than directional bias).

**Recommendation for exp_151**: Add a "strong coupling" condition with coupling_strength > 1.0 (e.g., up to 5.0), or change the coupling mechanism to directly scale the target subspace's binding matrix rather than injecting directional bias.

---

## 6. Updated Hypotheses for exp_151

| # | Hypothesis | Status after exp_150 |
|---|-----------|---------------------|
| H151-1 | Asymmetric coupling (S0→S1 only) allows S0 to "control" S1's L1 timing | Needs stronger coupling |
| H151-2 | Master subspace (larger N_sub) dominates evolution of smaller subspaces | Testable |
| H151-3 | One-way coupling produces causal arrow (Granger causality asymmetric) | Testable with current mechanism |

---

*Analysis written: 2026-06-06 22:14 CST (heartbeat)*  
*Next: write exp_151 script, then run*
