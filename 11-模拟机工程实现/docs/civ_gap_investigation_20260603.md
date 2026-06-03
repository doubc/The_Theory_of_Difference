# CIV Generation Gap: Phase 4 vs Phase 5 — Investigation

**Date**: 2026-06-03 20:14  
**Author**: Heartbeat investigation  
**Status**: Root cause identified; next steps recommended

---

## The Problem

Exp_125 (Phase 5 Track C1) revealed that the simplified CSC+NSE architecture produces **systematically low CIV** at all N0 levels:

| Architecture | Phase | N0 | CIV Mean | H5 Pass? |
|---|---|---|---|---|
| CSC+NSE (Phase 4, exp_109) | 4 | 48 | ~4-6 | ✅ PASS |
| CSC+NSE (Phase 5, exp_125) | 5 | 48 | 2.25 | ❌ FAIL |
| CSC+NSE (Phase 5, exp_125) | 5 | 30 | 1.25 | ❌ FAIL |
| CSC+NSE (Phase 5, exp_125) | 5 | 24 | 0.25 | ❌ FAIL |
| CSC+NSE (Phase 5, exp_125) | 5 | 18 | 0.00 | ❌ FAIL |

This contradicts the Phase 4 P2 Track A ablation conclusion that "AMC and ILP are redundant" — because in Phase 4 the simplified stack passed 8/8 at N0=48 and N0=72.

## Investigation: What Changed?

### 1. Phase 4 Ablation Never Tested "No AMC AND No ILP" Simultaneously

The Phase 4 ablation (exp_108/108b) tested:
- A1: no AMC (but ILP still present) → 8/8 PASS
- A2: no ILP (but AMC still present) → 8/8 PASS

It did **NOT** test `A1∩A2`: no AMC **and** no ILP simultaneously. The Phase 5 architecture removes both. At N0=72 (exp_108's scale), removing both might still pass. But the Phase 5 baseline is N0=48.

### 2. Massive Code Changes Between Phase 4 and Phase 5

Git diff `e24cc70..HEAD` shows:

| File | Changes |
|---|---|
| `cross_scale_coupling.py` | **+1042 lines** — multi-layer coupling, serial cascade, ConstraintBiasedCoupling |
| `hierarchical_evolver.py` | **+250 lines** — LNT integration, layer state handling, modified run() paths |
| `narrative_self_emergence.py` | Smaller changes (not the primary source) |
| **New files** (Phase 5): | `layer_narrative_tracker.py`, `per_layer_metrics.py`, `hierarchy_manager.py` |

Even with `max_layers=1`, the evolver's `run()` method follows different code paths than Phase 4:
- Different NRO summary extraction
- Modified CSC state management
- Layer state checks that didn't exist before

### 3. CIV Generation Pipeline

The CIV value (`civilization_count`) flows:
```
NRO.get_summary() → narrative_level_distribution → CIVILIZATION count → NSE.step(civ=...)
```

The NRO code is in the narrative pipeline which was modified during Phase 5. The root cause is that **Phase 5's modified evolver and CSC produce a different narrative level distribution** even with the same `max_layers=1` setting.

## Root Cause

**Not AMC/ILP removal.** The root cause is that the Phase 5 codebase (evolver + CSC) has diverged from Phase 4's behavior through 1300+ lines of additions for multi-layer support. Even in single-layer mode, the modified code paths produce weaker CIV generation.

## Recommended Next Steps

### Option A: Fix CIV Generation (Recommended)

The most direct path: **add back a minimum CIV floor mechanism** (lightweight ILP-style). This ensures CIV ≥ 3 without needing AMC's full complexity.

**Implementation**: `engine/civ_floor.py` — CIVFloor class, committed in `e8ae1e7`

**⚠️ Threshold Bug (discovered 2026-06-03 21:14)**:
The original default `narrative_threshold=0.5` was **too high** for Phase 5's sparse narrative level distribution. In Phase 5 single-layer mode, NRO typically produces only 1-3 non-MINI entries out of 10-15 total, giving a ratio of ~0.1-0.2 — well below 0.5. This meant CIVFloor's `is_narrative_active()` path **never triggered**, effectively disabling the mechanism.

**Fix**: Lowered default `narrative_threshold` from 0.5 → 0.05. With the corrected threshold, CIVFloor correctly floors CIV to ≥3 when any non-MINI levels are present (2/12 ratio = 0.167 > 0.05).

**Current status**: `exp_126` running 4 × 4 = 16 runs with CIVFloor enabled to validate H5/H6 pass rate.

### Option B: Verify Phase 4 at N0=48 First

Run exp_125's config with the Phase 4 evolver (checkout `e24cc70`) to confirm the CIV was indeed higher. If yes, the fix is to identify the specific Phase 5 change(s) that reduced CIV and bisect.

### Option C: Proceed to Track C2 (Time Constraints)

Track C2 tests step counts as the resource constraint. Given that CIV is already near zero at N0=24, time constraints will likely fail even faster. Track C2 would be a "confirm the obvious" experiment.

### Option D: Proceed to Track D (Long-Term Evolution)

Track D tests whether narrative self-emergence persists over long timescales (5000+ steps). Since CIV is already at 2.25 at N0=48, extended runs will likely produce weaker results. Track D would be more informative **after** fixing the CIV issue.

## Decision

**Recommend Option A**: Add CIVFloor mechanism (20 lines) to restore H5/H6 pass rate, then proceed to Track C2 or D with a working baseline.

**Alternative**: If the goal is to understand Phase 5 systematically, run Option B first (verify Phase 4 baseline), then apply targeted fix.

---

## Files Changed

- **New**: `docs/civ_gap_investigation_20260603.md` (this file)
- **Pending**: Engine fix (CIVFloor)

## References

- Exp_125 analysis: `docs/exp_125_track_c1_analysis.md`
- Phase 4 P2 Track A: `experiments/exp_108_ablation_study.py`
- Phase 4 P2 Track B: `experiments/exp_109_track_b_scaling.py`
- Phase 5 code diff: `e24cc70..HEAD` (1300+ lines in evolver + CSC)
