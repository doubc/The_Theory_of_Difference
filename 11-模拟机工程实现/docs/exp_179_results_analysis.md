# exp_179 Results Analysis — Parallel Multi-layer Evolution (Path D1)

**Date**: 2026-06-09 05:50 CST  
**Experiment**: exp_179 (Phase 16 Path D1)  
**Configs tested**: 7 (1 baseline + 6 experimental) × 2 trials = 14 runs  
**Hypothesis**: H16-D1 — Parallel evolution enables L2 emergence

---

## Experimental Design

The core idea: let L0, L1, L2 **evolve concurrently** instead of serially. By starting L1/L2 BEFORE L0 seals, cross-layer structural coupling during active evolution may produce L2 emergence.

| Config | L1 start | L2 start | Update Interval | Feedback α |
|--------|----------|----------|-----------------|------------|
| baseline_serial | ∞ (never) | ∞ | N/A | 0.0 |
| d1_early | step 3 | step 7 | 5 | 0.05 |
| d1_medium | step 5 | step 12 | 5 | 0.03 |
| d1_late | step 20 | step 40 | 10 | 0.03 |
| d1_continuous | step 2 | step 5 | 2 | 0.10 |
| d1_feedback_only | step 2 | step 5 | 0 | 0.10 |
| d1_burst | step 3 | step 7 | 50 | 0.15 |

All configs: N=48, total_steps=300 (early exit on seal), sealing_threshold=36 (=75% N)

---

## Results

### L2 Seal Rate

| Config | L2 Seal | Avg Step | Avg HW |
|--------|---------|----------|--------|
| baseline_serial | **0/2** (0%) | — | — |
| d1_early | **2/2** (100%) | 21 | 21.0 |
| d1_medium | **2/2** (100%) | 20 | 25.0 |
| d1_late | **0/2** (0%) | — | — |
| d1_continuous | **2/2** (100%) | 16 | 28.5 |
| d1_feedback_only | **2/2** (100%) | 18 | 23.0 |
| d1_burst | **2/2** (100%) | 24 | 20.0 |

**Finding**: 5/6 experimental configs produce 100% L2 sealing. The exception (d1_late) starts L2 at step 40, after L0/L1 are already sealed — functionally equivalent to the serial baseline.

### L2 Structure Quality

| Config | L2 Entropy (mean) | L1-L2 Reflection (mean) |
|--------|-------------------|-------------------------|
| d1_early | **0.9874** | **0.5209** |
| d1_medium | **0.9671** | **0.4584** |
| d1_continuous | **0.9742** | **0.5417** |
| d1_feedback_only | **0.9987** | **0.5521** |
| d1_burst | **0.9799** | **0.5729** |

**Finding**: All L2-sealing configs produce L2 with:
- **High entropy** (0.97-1.0) → near-random binary distribution
- **Low reflection** (0.46-0.57) → uncorrelated with L1 structure (~0.5 = random)

### Timing Analysis

| Config | L0 Seal Step | L1 Seal Step | L2 Seal Step | Parallel Window |
|--------|-------------|-------------|-------------|----------------|
| d1_early | 14 | 14 | 21 | 7 steps (L1 at 3→14) |
| d1_medium | 14 | 13 | 20 | 8 steps |
| d1_continuous | 20 | 14 | 16 | 12 steps |
| d1_feedback_only | 19 | 20 | 18 | 14 steps |
| d1_burst | 18 | 18 | 24 | 15 steps |

**Finding**: The parallel window (L1 active → L0 seals) is 7-15 steps. This is short but sufficient for L2 to initiate and seal.

---

## Success Criteria Evaluation

H16-D1 success requires ALL three for ≥3/6 configs:

| Criterion | Result | Details |
|-----------|--------|---------|
| C1: L2 seal rate > 0% | ✅ PASS | 5/6 configs, 100% sealing |
| C2: L2 structure entropy < 0.5 | ❌ FAIL | All configs ~0.97-1.0 |
| C3: L2 reflection < 0.9 | ✅ PASS | Trivially passed (no structure to reflect) |

**H16-D1: REJECTED** ❌  
Parallel evolution enables L2 **sealing** but not L2 **emergence**. The L2 layer seals with essentially random structure (entropy ≈ 1.0), confirming that concurrent execution alone cannot break the "dead order" topological invariant.

---

## Theoretical Significance

1. **Hierarchical sealing ≠ hierarchical structure**: The system can produce multiple sealing layers without meaningful cross-layer structure. Each layer finds its own attractor independently.

2. **Parallel window is real but insufficient**: The 7-15 step parallel window provides enough coupling for L2 to start, but not enough to imprint L0/L1 structure onto L2's dynamics.

3. **"Dead order" is robust against concurrency**: The topological invariant that locks each layer's structure persists even when layers evolve simultaneously. This suggests the invariant is at the dynamics level, not the timing level.

4. **Path D2/D3 may be necessary**: Enhanced cross-layer feedback (D2) or competitive/synergistic dynamics (D3) may be required to produce structured L2 emergence.

---

## Implications for D2/D3

Given that D1 failed the entropy criterion:
- **D2 (Enhanced Feedback)**: The simple feedback (bit perturbation) used in D1 may be too weak. D2's constraint modulation, transition matrix modulation, and topology reorganization are more invasive and might imprint structure.
- **D3 (Competition & Synergy)**: Resource allocation may force L2 to develop meaningful structure as a survival strategy.

**Decision**: ✅ Proceed to D2 (exp_180) — Enhanced Cross-layer Feedback with stronger coupling mechanisms.

---

## Files

- Experiment script: `experiments/exp_179_phase16_parallel_cross_layer.py`
- Raw results: `experiments/results/exp_179_results_20260609_055053.json`