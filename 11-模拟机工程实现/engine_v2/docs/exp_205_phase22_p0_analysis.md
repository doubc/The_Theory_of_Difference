# exp_205: Phase 22 P0 — Open System Energy Flow Analysis

**Date**: 2026-06-13
**Total Runs**: 34 (5 configurations × multiple seeds)

## Summary

Phase 22 P0 validates the open system energy-entropy flow integration. The EnvironmentEnergyField injects energy proportional to constraint strength, while the EntropyExhaust removes excess entropy — together enabling sustained non-equilibrium dynamics.

## Hypothesis Results (5/5 PASS)

### H22-P0a: Higher Energy in Open System ✅
Open system maintains **52% higher final energy** (94.29 vs 62.11).
- Open system injects ~5.25 energy/step on top of Phase 21's 2.0/step baseline
- Total injection: 31-58 per run depending on sealing timing
- Result: Energy stays near 90-96 instead of decaying to 57-67

### H22-P0b: Lower Entropy in Open System ✅
Open system has **9.4% lower entropy** (0.8894 vs 0.9818).
- Entropy exhaust removes 0.5-0.9 units per run
- Effect is modest at exhaust_rate=0.1 because the entropy level is near Shannon max (~1.0 bit)
- Higher exhaust rates amplify the effect (see H22-P0e)

### H22-P0c: Higher Energy Floor ✅
Open system minimum energy = final energy (94.29), closed = 62.11.
- The system doesn't dip below its steady-state energy
- Important: energy floor is determined by steady-state balance, not transient dips

### H22-P0d: Constraint → Injection Proportional ✅
| Constraint Strength | Mean Injection | Ratio |
|---|---|---|
| 0.1 (low) | 38.0 | 1.0x |
| 0.5 (medium) | 57.8 | 1.52x |
| 0.9 (high) | 77.5 | 2.04x |

- Injection formula: `base_rate * (1 + constraint * factor)` = 3.0 * (1 + cs * 1.5)
- cs=0.1: 3.0 * 1.15 = 3.45/step
- cs=0.9: 3.0 * 2.35 = 7.05/step (2.04x higher)
- Result confirms the constraint-energy focusing principle

### H22-P0e: Exhaust → Entropy Reduction ✅
| Exhaust Rate | Mean Entropy | Reduction |
|---|---|---|
| 0.01 | 0.9706 | 0% (baseline) |
| 0.1 | 0.8874 | -8.6% |
| 0.3 | 0.7025 | -27.6% |

- Higher exhaust rate produces proportionally lower entropy
- At er=0.3, exhaustive removal prevents entropy from reaching Shannon maximum
- Key insight: exhaust rate acts as an **inverse temperature** parameter

## Key Findings

1. **Energy maintenance is linear**: Each step, injection ≈ 3.5-7.0, decay ≈ 4.5-5.0, net ≈ -1.0 to +2.5
2. **Entropy removal is multiplicative**: exhaust = rate × entropy; at er=0.3, 30% of entropy removed per step
3. **Open system creates steady-state**: The system settles into a balance between energy decay and injection — a dynamic equilibrium
4. **Constraint focuses energy**: Higher constraint doesn't drain energy, it focuses it (matches Phase 22 design principle)

## Theoretical Significance

Phase 22 demonstrates that **open system energy flow can sustain non-equilibrium dynamics** in the difference simulator. This is the first implementation of environment→system energy coupling in the engine, and matches predictions from the differential theory:
- Constraints focus energy rather than draining it
- Entropy exhaust prevents "heat death" of closed systems
- The system maintains a dynamic equilibrium far from equilibrium

## Next Steps
- Phase 22 P3: Energy scaling law (N0 sweep for open system)
- Phase 22 P4: Constraint gradient (non-uniform spatial constraint)
- Phase 22 P5: Multiple environment fields (competing constraints)
