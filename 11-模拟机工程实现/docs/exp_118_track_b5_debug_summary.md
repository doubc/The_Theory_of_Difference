# exp_118 Track B5: Debug Summary & Next Steps

**Date:** 2026-06-02  
**Status:** Blocked — requires architectural change

---

## Problem

exp_118 (B5, independent L2 coupling) with seed 42 produces:
- **H1-H8: 1/8 PASS** (vs exp_117 B4: 8/8 PASS with same seed)
- **NSI = 0.0** — narrative self never emerges
- **signals_processed mean=10.1, 32% non-zero** — signals ARE being generated
- **ODI = None** in step results — ODI not being captured correctly

## Root Cause Analysis

### 1. B5 design uses `max_layers=1` — fundamentally insufficient

The B5 design specifies `max_layers=1` with L1/L2 computed as post-hoc calculations via `IndependentL2Coupling`. But:
- With `max_layers=1`, only the MINI layer is evolved
- The MINI layer state (N0=72 bits) with ILP freezing ~48 bits leaves only ~24 active bits
- This produces a state that's too uniform for meaningful narrative emergence
- The NSE requires multi-layer dynamics to compute NSI (tracks narrative level transitions)

### 2. exp117 (B4) works with `max_layers=1` — why?

exp117 uses the **same** `max_layers=1`, N0=72, ILP config — but produces H1-H8 8/8 PASS.

The difference:
- exp117 uses `MomentumNarrativeOperatorV4P1F` with **averaged bias correction** (sum of all actions / total strength)
- exp118 originally used `MomentumNarrativeOperatorV4P1F` with **strongest-action bias** (single max action)
- Even after fixing the bias correction to match exp117, exp118 still fails

### 3. The real difference: CSC mode

- exp117: `coupling_mode='constraint'`
- exp118: `coupling_mode='independent'`

But testing exp118 with `coupling_mode='constraint'` also fails. So CSC mode is NOT the root cause.

### 4. Standard NarrativeRecursionOperator generates more signals but NSI still 0

Switching to the standard `NarrativeRecursionOperator` (like exp_107) increased signals from 3% to 32%, but NSI remained 0.

This confirms: **the problem is not signal generation — it's the NSE not being able to compute NSI with max_layers=1**.

The NSE's NSI computation tracks narrative level transitions (MINI → INSTITUTIONAL → CIVILIZATION). With only the MINI layer existing, there are no level transitions to track, so NSI stays at 0.

## Conclusion

The B5 design of `max_layers=1` with post-hoc L2 coupling is **architecturally incompatible** with narrative emergence. The NSE requires actual multi-layer dynamics to compute NSI.

## Recommended Fix

**Change `max_layers=1` → `max_layers=3`** so that:
1. All three layers (MINI, INSTITUTIONAL, CIVILIZATION) are actually evolved
2. The NSE can track narrative level transitions and compute NSI
3. L2 has real independent clustering (not just post-hoc calculation)
4. The `IndependentL2Coupling` provides soft constraints between real layers

The `max_layers=3` attempt failed with `IndexError: Layer 1 not exist (total 1)`. This is a HierarchyManager initialization issue — the manager starts with only layer 0 and creates higher layers through encapsulation during evolution. The evolver needs to handle the case where higher layers don't exist yet.

## Files Modified

- `experiments/exp_118_phase5_b5_independent_l2.py` — multiple iterations of config changes
- Key remaining issues:
  - `max_layers=1` should be `max_layers=3`
  - Need to fix HierarchyManager layer initialization for multi-layer mode
  - ODI extraction from step results needs to handle nested dict format

## Hypothesis for Next Attempt

1. Set `max_layers=3` in `build_evolver_b5`
2. Fix the HierarchyManager to properly initialize all layers (or handle missing layers gracefully)
3. Use standard `NarrativeRecursionOperator` (proven to work in exp_107)
4. Use default NSE config (proven to work in exp_110)
5. Keep `IndependentL2Coupling` with soft bias + stability floor
6. Fix ODI extraction to handle nested dict format
