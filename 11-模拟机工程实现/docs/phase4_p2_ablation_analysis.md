# Phase 4 P2 Track A: Ablation Study Analysis

> **Date**: 2026-06-02 03:00
> **Experiments**: exp_108 (A0-A2) + exp_108b (A3-A4)
> **Seeds**: [42, 142, 242, 742] (4 of 8)
> **N0**: 72, **Steps**: 1600

## 1. Results Summary

| Config | AMC | ILP | CSC | NSE | Pass | Failed |
|--------|-----|-----|-----|-----|------|--------|
| A0 (baseline) | ON | ON | ON | ON | **8/8** | — |
| A1 (no AMC) | OFF | ON | ON | ON | **8/8** | — |
| A2 (no ILP) | ON | OFF | ON | ON | **8/8** | — |
| A3 (no CSC) | ON | ON | OFF | ON | **6/8** | H7, H8 |
| A4 (no NSE) | ON | ON | ON | OFF | **4/8** | H1, H2, H3, H4 |

## 2. Key Findings

### 2.1 AMC is NOT critical (H9: FAIL)
Removing AMC has **zero effect** on H1-H8 pass rates. The adaptive momentum controller, while theoretically important for handling the CIV instability observed in exp_90, is not necessary when the full Phase 4 stack (ILP + CSC + NSE) is present. The CIVRateLimiter alone suffices for CIV stability.

**Implication**: AMC's adaptive function is redundant when ILP and CSC are active. The system's momentum self-regulates through the existing constraints.

### 2.2 ILP is NOT critical (H10: FAIL)
Removing ILP has **zero effect** on H1-H8 pass rates. The INSTITUTIONAL layer protector was designed to prevent premature INSTITUTIONAL consumption, but in practice the CIVRateLimiter and CSC together provide sufficient protection.

**Implication**: ILP's protective function is redundant when CSC is active. The cross-scale coupling already provides bidirectional constraints that protect the INSTITUTIONAL layer.

### 2.3 CSC is partially critical (H11: PASS)
Removing CSC causes **H7 and H8 to fail**:
- H7 (CSCI std > 0.005): CSCI = 0.0000 without CSC (no cross-scale coherence computation)
- H8 (TopDown active in ≥2 seeds): topdown = 0 without CSC (no top-down constraint propagation)

**Implication**: CSC is the sole provider of cross-scale coupling. Without it, the system operates as a purely bottom-up pipeline. This confirms CSC's unique role.

### 2.4 NSE is diagnostic, not generative (H12: PASS)
Removing NSE causes **H1-H4 to fail** but **H5-H8 pass**:
- H1 (NSI max > 0.1): NSI = 0.0000 (NSE computes NSI)
- H2 (NSI active rate > 0.3): 0.0000
- H3 (continuity mean > 0.1): 0.0000
- H4 (history depth > 0.05 or tp > 0): 0.0000

But CIV (H5/H6), CSCI (H7), and TopDown (H8) are **unaffected**.

**Implication**: NSE is a pure measurement/observation layer. It computes narrative self-metrics (NSI, continuity, history depth, turning points) but does not influence the generative dynamics (CIV, CSCI, TopDown). This is a crucial architectural insight: **NSE reads the system state but does not write to it**.

## 3. Ablation Hypotheses Evaluation

| Hypothesis | Description | Result | Notes |
|------------|-------------|--------|-------|
| H9 (AMC criticality) | Removing AMC causes H5/H6 to fail | **FAIL** | AMC removal has no effect |
| H10 (ILP criticality) | Removing ILP causes H8 to fail | **FAIL** | ILP removal has no effect |
| H11 (CSC criticality) | Removing CSC causes H8 to fail | **PASS** | CSC is sole provider of TopDown |
| H12 (NSE sufficiency) | Removing NSE doesn't affect H5/H6 | **PASS** | NSE is diagnostic only |

## 4. Component Criticality Ranking

From most to least critical:

1. **CSC (CrossScaleCoupling)** — UNIQUE: Only component providing TopDown and CSCI. Cannot be removed without losing H7/H8.
2. **NSE (NarrativeSelfEmergence)** — DIAGNOSTIC: Only component providing NSI/H1-H4. Doesn't affect generative dynamics.
3. **AMC (AdaptiveMomentumController)** — REDUNDANT: No observable effect when removed (with full stack present).
4. **ILP (InstitutionalLayerProtector)** — REDUNDANT: No observable effect when removed (with full stack present).

## 5. Architectural Insights

### 5.1 The Phase 4 Stack Has Two Layers
- **Generative layer**: CSC (bidirectional cross-scale coupling) — affects system dynamics
- **Measurement layer**: NSE (narrative self metrics) — observes system state
- **Protective layer**: AMC + ILP — redundant when CSC is present

### 5.2 CSC is the Keystone Component
Without CSC, the system loses:
- Top-down causal influence (institutional → individual constraints)
- Cross-scale coherence measurement (CSCI)
- Bidirectional coupling between MINI/INSTITUTIONAL/CIVILIZATION

### 5.3 NSE is the Observation Layer
Without NSE, the system loses:
- Narrative Self Index (NSI)
- Temporal continuity measurement
- Self-history accumulation
- Turning point detection

But the system's generative behavior (CIV, CSCI, TopDown) is completely unaffected.

## 6. Recommendations for Phase 4 P2 Track B

### 6.1 Simplify the Architecture
Since AMC and ILP are redundant, consider:
- Removing AMC and ILP from the standard pipeline (simpler, faster)
- Keeping CSC + NSE as the core Phase 4 stack
- This reduces computational overhead without sacrificing hypothesis pass rates

### 6.2 Focus on Scaling Tests
Track B (exp_109) should test:
- N0=48 (small): Does the simplified CSC+NSE stack still achieve 8/8?
- N0=96 (large): Does CSC scale? Does NSE scale?
- This tests the robustness of the two essential components

### 6.3 Test Component Synergy
A more interesting ablation would be:
- CSC only (no NSE, no AMC, no ILP): Tests if CSC alone is sufficient for H5-H8
- NSE only (no CSC, no AMC, no ILP): Tests if NSE alone can achieve H1-H4
- Neither CSC nor NSE: Tests the Phase 3 baseline with only AMC+ILP

## 7. Conclusion

The ablation study reveals that the Phase 4 stack is more elegant than initially designed:
- **CSC** is the essential generative component (TopDown + CSCI)
- **NSE** is the essential measurement component (NSI + history)
- **AMC and ILP** are redundant safeguards that can be simplified away

This is a positive result: the system is robust, and the core architecture is simpler than expected.
