# Phase 9 P3-B: High-Resolution N0 Phase Transition Analysis

**Date**: 2026-06-05  
**Experiment**: exp_146  
**Config**: N0=[29,30,31,32,34], 16 seeds each, 2000 steps, SI=10, GSN=0.2, ML=2

## Results

| N0 | L1 Sealed | L1 Formed (2+ layers) | Fraction | Notes |
|----|-----------|----------------------|----------|-------|
| 29 | 0/16 | 0/16 | 0.00 | Pure L0 dynamics |
| 30 | 7/16 | 7/16 | 0.44 | Threshold zone — all sealed seeds are 2-layer |
| 31 | 13/16 | 13/16 | 0.81 | Strong transition — all sealed are 2-layer |
| 32 | 16/16 | 16/16 | 1.00 | Full formation (OOB fix confirmed clean) |
| 34 | 16/16 | 16/16 | 1.00 | Full formation, all 2-layer |

## Hypothesis Verdicts

### H110: Sharp Transition (≥10/16 swing between adjacent N0)
**FAIL** ❌  
Max adjacent swing = 6 (N0=30→31: 7→13). No adjacent pair exceeds 10/16.  
The P3-A sharp transition (15/16 swing between N0=30 and N0=32) was an artifact of coarse N0 sampling (skipping 31).

### H111: Logistic Transition
**PASS** ✅  
Logistic fit: `f(N0) = 1 / (1 + exp(-2.18*(N0-30.19)))`  
- Midpoint: N0≈30.2
- Steepness: 2.18 (moderate, not sharp)
- The transition spans ~2 units of N0 (29→31)

## Key Findings

1. **L1 is a probabilistic threshold phenomenon**: The transition from 0→1 L1 layers follows a logistic curve, not a sharp step function.

2. **Critical zone**: N0∈[29,31] — below 29, L1 almost never forms; above 31, L1 almost always forms.

3. **Seal implies multi-layer**: Every seed with L1 sealing had exactly 2 layers. No case of 2+ layers without sealing, and no case of sealing with only 1 layer.

4. **NSI is tightly bounded**: All sealed seeds show N0-sealed NSI mean ≈ 0.50-0.57, consistent across N0=30,31,32,34. The constraint engine fixes NSI regardless of N0 once L1 is established.

## Next Steps

- **P3-C (Seal Hysteresis)**: Once sealed, does reducing N0 break the seal? Test N0=29→24→back after seal at N0=31.