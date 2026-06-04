# Phase 8 P0: L1 Formation Gap Analysis

## Problem

Phase 8 P0 (exp_137) aims to establish an L1 cycle baseline using the L1CycleDetector (LCylDet).
However, with `max_layers=1` (the standard Phase 4-7 evolver configuration), the tracking callback
never receives per-layer data for L1. The encapsulated L1 layer exists within L0's internal
structure (from the hierarchy's sealing/encapsulation mechanism), but it is NOT iterated as a
separate layer in the `_run_layer` callback loop.

### Evidence

- The evolver logs show encapsulation: `[HIERARCHY] L0 -> L1: 72 -> 33 bits (30 active + 1 enc)`
- L1 exists with 33 bits after sealing
- But the tracking callback is only invoked for the explicit `max_layers` count (=1)
- The callback always receives `layer_id=0`, never `layer_id=1`

### Root Cause

The tracking callback is called from `HierarchicalEvolver._run_layer()`, which iterates over
`self.hierarchy` layers. With `max_layers=1`, the hierarchy has exactly 1 layer (L0). The
encapsulated sub-layers (L1+) exist within the hierarchy's internal bit structure, not as
separate iteration targets.

## Why `max_layers=2` Doesn't Work

Setting `max_layers=2` causes the evolver to create 2 explicit layers at initialization.
This triggers a tensor size mismatch in the narrative pipeline:

```
RuntimeError: The size of tensor a (36) must match the size of tensor b (72) at non-singleton dimension 0
```

The narrative operators (MomentumNarrativeOperatorV4P1F, NarrativeFilter, etc.) are sized for
the full N0-bit space (72 bits). With `max_layers=2`, L0 has fewer bits (e.g., 36) and L1 has
the rest (36). When the narrative operator processes L1's signal tensor (36 dimensions), it
mismatches with the operator's internal history tensors (72 dimensions).

Affected components:
- `narrative_self.py: NarrativeFilter._compute_novelty()` — tensor dot product mismatch
- Likely also: ODI, MSI, GBC, and other N0-sized components

## Phase 8 P1 Design Implications

Three approaches for enabling L1 cycle detection:

### Approach A: Encapsulation-Aware Callback (Recommended for P1)

Modify the tracking callback to detect the encapsulated L1 layer from the evolver's hierarchy
state, rather than relying on the `_run_layer` loop. The callback can access:
- `evolver.hierarchy.layer(0).n_bits` — original N0
- `evolver.hierarchy.layer(0).encapsulated_bits` — bits moved to L1
- The number of active L1 bits = `encapsulated_bits ∩ active_bits`
- Per-layer CIV and ODI can be computed from active bit masks

**Implementation sketch:**
```python
class L1AwareCallback(LCylDetTrackingCallback):
    def step(self, step, layer_id, ...):
        super().step(step, layer_id, ...)
        if layer_id == 0 and hasattr(self, '_evolver'):
            # Extract L1 data from hierarchy encapsulation
            hier = self._evolver.hierarchy
            l0 = hier.layer(0)
            n_total = l0.n_bits
            encapsulated = l0.encapsulated_bits
            if encapsulated:
                l1_active = encapsulated & active_bits
                l1_civ = len(l1_active)
                l1_n_active = len(l1_active)
                l1_nsi = l1_n_active / max(len(encapsulated), 1)
                # Feed to LCylDet
```

### Approach B: Dual-Tracker (For Validation)

Run two PerLayerMetricsCollectors: one fed from the standard callback (L0 data),
and one fed from a custom thread that extracts L1 encapsulation data from each snapshot's
bit-level state. This keeps the separation clean for validation.

### Approach C: Linear L0-Only Proxy (Quick Baseline)

Skip L1 entirely and feed L0 metrics into the LCylDet under the assumption that,
at high sealing ratios, L0's internal dynamics approximate L1 behavior. Not recommended
for rigorous validation.

## Recommended Path Forward

1. **P0 (this experiment)**: Accept the zero baseline with `max_layers=1`
2. **P1**: Implement Approach A — encapsulation-aware callback that detects L1 bits
   from the hierarchy's sealed/encapsulated state
3. **P2**: Validate with both max_layers=1 (encapsulated L1) and max_layers=2 (if
   narrative tensor sizing is refactored)
4. **P3**: Cross-scale coupling — bidirectional L0↔L1 cycle coupling with NRC feedback

## Appendix: PerLayerMetricsCollector State with max_layers=1

With only `layer_id=0` calls, the collector stores:
- `_nsi_tracker._layer_nsi = {0: [(step0, nsi0), (step1, nsi1), ...]}` — only L0
- `_civ_tracker._layer_civ = {0: [(step0, civ0), ...]}` — only L0
- `_theme_tracker._layer_themes = {0: [(step0, themes0), ...]}` — only L0

`extract_l1_metrics()` checks `len(tracker._layer_nsi) > 1`, which is False.
All L1 metrics return 0. The LCylDet receives no data.

