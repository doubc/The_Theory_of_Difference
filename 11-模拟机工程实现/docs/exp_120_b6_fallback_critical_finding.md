# Phase 5 Track B6 Fallback — Critical Finding: Sealing Mechanism Bug

**Date:** 2026-06-03 03:04 (Asia/Shanghai)
**Experiment:** exp_120 (B6 Fallback: N0=48 L0 + N0=72 L2)
**Status:** FAILED — Root cause identified

## Summary

The B6 fallback experiment (N0=48 for L0, independent L2 at N0=72) also **failed to seal** — L0 remained unsealed after 7500 steps (5000 + 2500 extra). This confirms the sealing failure is **not a scale problem** (N0=72 vs N0=48) but a **fundamental bug in the sealing mechanism**.

## Root Cause: Monotonically Growing `active_bits`

In `acl.axioms_v2.AxiomConstraints`:

```python
self.active_bits: Set[int] = set()  # Line 59 — only grows, never shrinks

def record_active(self, flip_idx: int):  # Only adds, never removes
    self.active_bits.add(flip_idx)

def _seal(self):  # Line 340
    if len(self.active_bits) <= self.min_active_bits:  # Never true after early steps
        self.sealed = True
        return
```

**The sealing condition** `len(active_bits) <= min_active_bits` can only be true in the very early steps when few bits have been activated. Once the system has injected/flipped enough bits (which happens quickly — within hundreds of steps), `active_bits` exceeds `min_active_bits` and **sealing becomes mathematically impossible**.

### Evidence from exp_120 (seed 42, N0=48):
```
Step   2500: w= 12, inj=0, abs=0, lat=2, active=44, cycles=333
Layer 0 done: w=12, sealed=False, inj=2584, abs=2584, cycles=596
Extra 2500 steps: sealed=False
```
- `active=44` at step 2500, but `min_active_bits = max(48//3, 12) = 16`
- 44 > 16, so sealing condition can never be met
- Total inject=2584, absorb=2584 — bits cycle but `active_bits` set keeps growing

### Evidence from exp_119 (seed 42, N0=72):
```
Step   2500: w= 12, inj=0, abs=0, lat=2, active=41, cycles=322
```
- `active=41` at step 2500, but `min_active_bits = max(72//3, 12) = 24`
- 41 > 24, same problem

## Impact

**All multi-layer experiments (B1-B6) are affected:**
- B1 (exp_114): N0=72 → L0 never sealed → no L1 formed
- B2 (exp_115): N0=72, serial → L0 never sealed
- B3 (exp_116): N0=72, redesigned → L0 never sealed
- B4 (exp_117): N0=72, constraint conduction → L0 never sealed
- B5 (exp_118): N0=72, independent L2 → L0 never sealed (L2 worked because it's independent)
- B6 (exp_119): N0=72, more steps → L0 never sealed (only 1/8 seed sealed by chance)
- B6 fallback (exp_120): N0=48 → L0 never sealed

**The only "successful" sealing in B6 (seed 542, 1/8 = 12.5%)** was likely a statistical anomaly where the active_bits set happened to stay small enough — not a reliable mechanism.

## Proposed Fixes

### Option A: Sliding Window for `active_bits` (Recommended)
Track only **recently active** bits (e.g., last W steps) instead of all ever-active bits:
```python
# Instead of: self.active_bits: Set[int] = set()
# Use: self.active_bits: Deque[int] = deque(maxlen=window_size)
# Or: self.active_bits: Dict[int, int] = {}  # {bit_idx: last_active_step}
#     Then filter out old entries each step
```

### Option B: Change Sealing Condition
Use a different metric for sealing, e.g.:
- **Current activity rate**: fraction of bits flipping in recent window
- **Binding strength concentration**: max binding strength among active bits
- **Spatial clustering**: fraction of active bits in contiguous regions

### Option C: Decay Mechanism
Add a decay step that removes bits from `active_bits` if they haven't been active recently:
```python
def step_decay(self, step: int, inactive_threshold: int = 100):
    """Remove bits that haven't been active in recent steps."""
    # Requires tracking last_active_step per bit
    pass
```

## Recommendation

**Option A (sliding window)** is the cleanest fix that preserves the original intent of A9 (seal when the system has explored enough and stabilized). The current implementation confuses "bits that have ever been active" with "currently active bits."

## Next Steps

1. **Fix the sealing bug** in `acl/axioms_v2.py` (or wrap it with a corrected version)
2. **Re-run B1-B6** with the fix to validate multi-layer dynamics
3. **Proceed with B6 fallback** (exp_120) after fix — N0=48 should seal reliably
4. **Update all hypothesis results** for B1-B6 with corrected sealing data

## Files Modified

- `experiments/exp_120_phase5_b6_fallback_n048_l0.py` — B6 fallback experiment script
- `experiments/exp_120_b6_fallback_results.json` — Results (2/17 PASS, sealing failed)

## Git Status

- exp_120 script committed but not pushed (need to add this analysis doc first)


---

## FIX IMPLEMENTED (2026-06-03 04:04)

### Root Cause Confirmed
The sealing bug is **not a scale problem** -- it is a fundamental design flaw in AxiomConstraints.

### Fix Applied
Replaced monotonically-growing Set[int] with a sliding window Dict[int, int] (bit_idx to last_active_step):

Files modified:
1. acl/axioms_v2.py -- Core fix:
   - active_bits: Set[int] to Dict[int, int]
   - Added active_window = max(N//2, 100) sliding window parameter
   - Added _count_active_in_window(), _get_active_in_window(), _step_counter()
   - _seal() now uses window-restricted active bits
   - Added set_current_step() for outer evolver to update step counter

2. engine/spatial_evolver_v2.py -- Added self.constraints.set_current_step(step) in run() loop
3. engine/long_range_evolver_v2.py -- Same fix
4. engine/hierarchy_manager.py -- Same fix + compatibility fixes for active_bits usage:
   - encapsulate_current_layer(): uses _get_active_in_window() instead of raw active_bits
   - step_layer(): added set_current_step(step) in loop
   - _apply_cross_layer_gravity_modulation(): uses _get_active_in_window() for active pattern
   - step_layer() return dict: uses _count_active_in_window() for active_bits count

### Verification
Smoke test (test_sealing_fix.py) confirms:
- Old mechanism: sealing impossible after ~3 steps (active_bits=48 > min_active=16)
- New mechanism: seals at step 29, keeps 16 bits, freezes 32 bits [PASS]

### Next Steps
1. Re-run exp_120 (B6 fallback) with the fix to validate multi-layer sealing
2. Re-run B1-B5 experiments with the fix
3. Proceed with Track B7 (L2 autonomous dynamics parameter sweep)
