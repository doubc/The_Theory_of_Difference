# Binding Threshold Tuning for Small N (L1 at ~18 bits)

## Problem

exp_121 (Track B7) showed that L1 at N=18 doesn't seal with `binding_threshold=0.05`.
L0 at N=48 seals fine (13/32 lateral bits, ~40%) with the same threshold.
The question: what binding_threshold should L1 use?

## Theoretical Analysis

### Binding Threshold Definition

`binding_threshold` in `encapsulation_engine.py` is a per-pair threshold:
```
if binding_strength[i][j].item() > self.binding_threshold:
    uf.union(i_idx, j_idx)
```

`binding_strength[i][j]` measures co-occurrence frequency between bit i and bit j.
The threshold determines what fraction of co-occurrence is "significant."

### Scale Dependence

| Parameter | L0 (N=48) | L1 (N=18) | Ratio |
|-----------|-----------|-----------|-------|
| Total bits | 48 | 18 | 2.67x |
| Lateral bits | 32 | 6 | 5.33x |
| Hierarchy bits | 16 | 6 | 2.67x |
| C(32,2) lateral pairs | 496 | 15 | 33x |
| C(16,2) hierarchy pairs | 120 | 15 | 8x |

The pair count drops by **8-33x**, meaning per-pair binding_strength variance is much higher
at small N. The same threshold 0.05 that produces clean binding at N=48
may be too strict at N=18 because fewer samples ≈ noisier estimates.

### Binding Strength Distribution

Co-occurrence strength for bit pairs follows a distribution that depends on:

1. **Step count** — more steps = more stable estimates
2. **Register count** — more registers = more pairs = better law of large numbers
3. **Bit activity** — active bits co-occur more frequently

For L1 at N=18 with only 6 lateral bits:
- Few lateral pairs (15) mean each pair's co-occurrence is noisier
- Hierarchy pairs similarly limited
- The threshold needs to accommodate this higher noise floor

## Proposed Solution: Adaptive Threshold Scaling

Rather than a fixed global threshold, scale the threshold for smaller layers:

### Formula

```
binding_threshold_for_N = base_threshold * (N_current / N_ref)
```

Where:
- `base_threshold` = target threshold at reference scale (e.g., 0.05 at N_ref=48)
- `N_current` = current layer's bit count
- `N_ref` = reference bit count (usually N0)

For N=18 with base=0.05 at N_ref=48:
```
threshold = 0.05 * (18/48) = 0.01875
```

### Rationale

Linear scaling with N ensures the same expected **absolute number** of bound pairs
is maintained across scales. This is conservative — it keeps the binding mechanism
consistent even as variance increases.

### Alternative: Quadratic Scaling

If binding is pair-count-dominated:
```
threshold = base * (C(N_current,2) / C(N_ref,2))
```

For N=18 lateral bits (only 6), N_ref=48 lateral bits (32):
```
threshold = 0.05 * (C(6,2) / C(32,2)) = 0.05 * (15/496) = 0.0015
```

This is likely too aggressive — would make essentially all pairs "bind."

**Recommendation**: Start with linear scaling (`0.01875`), test, and adjust.

## Implementation Options

### Option A: Per-layer binding_threshold in HierarchicalEvolver

Add `layer_binding_thresholds` parameter to `HierarchicalEvolver.__init__()`:
```python
def __init__(self, ..., binding_threshold=0.05, 
             layer_binding_thresholds: Dict[int, float] = None):
    if layer_binding_thresholds is None:
        # Auto-compute from linear scaling
        layer_binding_thresholds = {}
    self.layer_binding_thresholds = layer_binding_thresholds
```

When creating a new layer, adjust its `self.binding_threshold` if specified.

### Option B: Keep global, tune for L1

Simpler: keep same mechanism, just set `binding_threshold=0.02` globally.
This makes L0 slightly more permissive (acceptable — L0 at 0.05 already seals ~40%)
while allowing L1 to seal.

### Option C: Variable threshold in sealing logic

Add adaptive threshold to EncapsulationEngine:
```python
effective_threshold = self.binding_threshold * (N / N_ref)
```

## Recommendation

**Start with Option B**: global `binding_threshold=0.02`.

- Minimal code change (just the exp_121 parameter)
- L0 sealing at N=48 with 0.02 will be more aggressive (already at 0.05 it seals well)
  — acceptably so for Track B7 goals
- L1 at N=18 with 0.02 should be comparable to L0 at N=48 with 0.05
  (ratio of actual-to-reference N: 18/48 ≈ 0.375, so 0.02 ≈ 0.05 * 0.375)

**Fallback to Option A** if L0 becomes too permissive or L1 still doesn't seal.

## Validation Plan

1. Modify exp_121 script: change `binding_threshold=0.05` → `binding_threshold=0.02`
2. Run quick 2-seed validation (seed 42, 542) at 1000 steps
3. Check L0 lateral seal ratio and L1 seal ratio
4. If L1 still doesn't seal, try `binding_threshold=0.01`
5. Document results and update exp_121 parameters

---

*Written: 2026-06-03 08:44*