# exp_157 Result — Phase 13 P3: Multi-subspace Template Growth

## Experiment
Single SpatialLongRangeEvolver (N=72) with post_seal_callback implementing template growth: new bits are injected preferentially near sealed structures (distance-weighted). Template strength 0.0 (baseline) vs 1.0.

## Results

| Metric | Template 0.0 | Template 1.0 | Verdict |
|--------|-------------|--------------|---------|
| Final HW | 36.7 ± 2.9 | 40.7 ± 2.9 | **Different** (+4.0, coupling works) |
| Edge distance (unsealed→sealed) | 0.0748 ± 0.0137 | 0.0757 ± 0.0149 | **Same** (p=0.90, t-test) |
| Correlation length ξ | 1.233 ± 0.128 | 1.278 ± 0.135 | **Same** |
| HW variance (memory) | 8.2 (ratio=0.46) | 8.2 (ratio=0.46) | **Same** |

## Hypotheses
- **H157-1 (Template growth → edge clustering):** ❌ REJECTED
- **H157-2 (Structural inheritance → longer correlation):** ❌ REJECTED
- **H157-3 (Memory → higher HW variance):** ❌ REJECTED

## Conclusion
Template growth coupling IS effective (HW increases by 4.0/72 = 5.6%), but the injected activity is spatially random. No edge clustering, no correlation length increase, no memory. The system remains in a maximum-entropy frozen state despite directed injection.

**L2 emergence requires more than spatial template**: even actively seeding bits near sealed structures fails to produce organized post-seal dynamics.

## Technical Note
Discovered that Phase 11's SubspaceAwareEvolver coupling mechanism (modifying `constraints.binding_strength`) is **broken** — `binding_strength` is never read by the dynamics computation. All Phase 11 P3 results requiring re-evaluation.

## Next Directions
- Time-structured injection (pulsing fields)
- Competing sealed "nuclei" 
- Active constraint shaping (sealed structure actively gates dynamics, not just statically biases)
