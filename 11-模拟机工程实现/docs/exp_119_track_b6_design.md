# exp_119 Track B6: True Multi-Layer + Independent L2 Coupling

**Date:** 2026-06-03  
**Status:** Design Phase  
**Parent:** exp_118 Track B5 (commit 4362b1c)

---

## Problem Statement

Track B5 validated that **soft additive bias + stability floor produces genuine decoupling without silencing L2**:
- H30: 8/8 PASS — L1↔L2 stability r=0.0 with L2 active (mean=0.33)
- H32/H35/H36: 8/8 PASS — L2 autonomy and stability floor working

**But:** Layer 0 never seals at N0=72 within 3000 steps → no true multi-layer evolution → H31/H33/H37/H1-H8 all fail.

The core architectural limitation: B5's `IndependentL2Coupling` is **post-hoc** — it computes L2 stability independently but L2 narrative signals still share the same MINI layer source as L1.

## B6 Design Philosophy

**Combine B5's independent coupling with parameters that enable actual layer sealing.**

Three levers to trigger sealing at N0=72:

### Lever 1: More Steps (Primary)
- B5: 3000 steps → 0/8 seeds seal
- B6: **5000 steps** — give the evolver more time to activate all 72 bits and reach A9 sealing
- Rationale: exp_117 (B4, N0=72, 2000 steps) achieved H1-H8 8/8 with rich MINI dynamics, suggesting the system CAN produce rich dynamics at N0=72 but sealing takes longer

### Lever 2: Lower Binding Threshold
- B5: `binding_threshold=0.1` (default)
- B6: **`binding_threshold=0.05`** — easier to form binding groups → faster encapsulation
- Rationale: At N0=72, binding strengths are more diffuse. Lowering the threshold allows more bits to be grouped and frozen earlier

### Lever 3: ILP Aggressive Freezing
- B5: `institutional_floor=20`, `consumption_rate_limit=0.05`
- B6: **`institutional_floor=15`**, **`consumption_rate_limit=0.10`** — allow more bits to freeze
- Rationale: The ILP's `should_consume` gate was blocking encapsulation. Relaxing it allows the natural sealing process to proceed

### B5 Parameters Carried Forward
- `coupling_mode='independent'`
- `l2_stability_floor=0.15`
- `l2_constraint_strength=0.1` (additive bias)
- `l2_perturbation_rate=0.03`
- `l2_autonomous_decay=0.97`
- `l2_odi_independence_weight=0.5`

## Hypotheses

| ID | Hypothesis | B5 Result | B6 Target |
|----|-----------|-----------|-----------|
| H30 | L1↔L2 stability r < 0.7 | 8/8 PASS (r=0.0) | ≥6/8 (maintain decoupling) |
| H31 | L0→L1 delay detected | 0/8 | ≥4/8 (true multi-layer!) |
| H32 | L2 narrative autonomy > 0.1 | 8/8 PASS | ≥6/8 |
| H33 | L1-L2 ODI correlation < 0.8 | 0/8 (not measurable) | ≥4/8 (add L1-L2 ODI tracking) |
| H35 | L2 min stability ≥ 0.10 | 8/8 PASS | 8/8 |
| H36 | L2 autonomy index > 0.1 | 8/8 PASS | ≥6/8 |
| H37 | L2 intrinsic dynamics detectable | 2/8 | ≥4/8 |
| H1 | CIV NSI > 0.5 | 2/8 | ≥4/8 |
| H3 | CIV range [3, 20] | 0/8 | ≥4/8 (actual CIV layer!) |
| H5 | CIV relaxed [2, 25] | 0/8 | ≥4/8 |
| H6 | CIV min ≥ 2 | 0/8 | ≥4/8 |
| H8 | TopDown active | 0/8 | ≥4/8 |

## Key Metric: Sealing Rate

**Primary success criterion:** ≥4/8 seeds achieve L0 sealing within 5000 steps.

If sealing rate < 50%, B6 fails at the architectural level and we need a different approach (e.g., smaller N0 for Layer 0, or explicit freezing mechanism).

## Files to Modify

1. `engine/cross_scale_coupling.py` — Add L1-L2 ODI correlation tracking to `IndependentL2Coupling`
2. `engine/institutional_layer_protector.py` — Add configurable `consumption_rate_limit` parameter (if not already there)
3. `experiments/exp_119_phase5_b6_true_multilayer.py` — New experiment script
4. `docs/exp_119_track_b6_results.md` — Results analysis (post-run)

## Risk Assessment

- **Risk:** Even with 5000 steps + lower threshold, L0 may still not seal at N0=72
- **Mitigation:** Fallback to N0=48 for Layer 0 (proven to seal in earlier phases) while keeping L2 independent at N0=72
- **Risk:** Sealing happens too early → insufficient MINI dynamics for rich L1 narrative
- **Mitigation:** Monitor NSI and CIV metrics; if too low, increase steps further
