# Track B9: L1→L2 Cascade Design

> **Date**: 2026-06-03 (11:36 CST)
> **Status**: Design draft (pending exp_122 v3 results)
> **Depends on**: B8 results (H46-H49), exp_121 L1 sealing params

---

## 1. Core Question

After L0 partial sealing triggers Layer 1 formation, and L1 develops autonomous dynamics (B8), does L1's own partial sealing trigger Layer 2 formation through the same cascade mechanism?

This tests the **ontological hierarchy** claim from the Theory of Difference: each layer emerges from the difference field created by the layer below it, not from direct parallel derivation.

---

## 2. Theoretical Foundation

### 2.1 Difference Reorganization (from §1.1-§1.3)

```
Layer 0: Raw difference field → partial seal → frozen bits = constraint field
                  ↓
Layer 1: Emerges from L0's constraint field → autonomous dynamics → partial seal → frozen bits = new constraint field
                  ↓
Layer 2: Emerges from L1's constraint field → autonomous dynamics → ...
```

Each layer is:
- **Constituted by**: the frozen (sealed) bits of the layer below
- **Active within**: the remaining unsealed space of the layer below
- **Driver of next layer**: when it partially seals, its frozen bits provide the constraint field for the next layer

### 2.2 Key Insight from B7 Partial Sealing

B7 showed that **partial sealing is essential** for multi-layer formation:
- Lateral bits seal → provide boundary (object-hood)
- Hierarchy bits remain active → provide internal difference organization
- L1 forms from the **difference between sealed and unsealed** in L0

For B9, L1 must undergo the same partial sealing process:
- Some L1 bits freeze → provide L2's constraint field
- Other L1 bits remain active → L1 continues dynamics
- L2 emerges from L1's sealed/unsealed boundary

### 2.3 Binding Threshold Scaling

From theory note analysis: As layer level increases, constraint space narrows.

**BindingThreshold Formula**:
```
threshold_L(i) = threshold_base / N_L(i) * K_scale
```

Where:
- `threshold_base` = 0.05 (proven for L0 N=48)
- `N_L(i)` = active bits in layer i
- `K_scale` = normalization factor

For L0 N=48, threshold=0.05 → scales to L1 N≈22, threshold≈0.02-0.03

---

## 3. Hypothesis Set (H50-H55)

### H50: L1 Partial Sealing
- L1 achieves partial sealing (ratio > 0.4) for >= 5/8 seeds
- Test: PerLayerMetricsCollector seal ratio after L1 formation
- **Prediction**: PASS if binding_threshold is scaled down to ~0.02

### H51: L2 Formation
- Layer 2 forms within 500 steps after L1 partial seal for >= 5/8 seeds
- Test: evolver.n_layers >= 3 after L1 seal
- **Prediction**: PASS if B9 mechanism is correctly implemented

### H52: L1 NSI Autonomy from L0 (corroborate B8)
- Post-L0-seal, L1 NSI rolling correlation with L0 < 0.5 for >= 6/8 seeds
- Test: Same as H46
- **Prediction**: PASS (replicate B8)

### H53: L2 NSI Autonomy from L1
- Post-L1-seal, L2 NSI rolling correlation with L1 < 0.5 for >= 6/8 seeds
- Test: PerLayerNSITracker between L1 and L2
- **Prediction**: PASS (theory predicts genuine independence)

### H54: CIV Independence (L1 vs L2)
- Post-L1-seal, L1-L2 Hamming correlation < 0.6 for >= 5/8 seeds
- Test: PerLayerCIVTracker
- **Prediction**: PASS (different bit spaces)

### H55: Theme Divergence (L1 vs L2)
- Post-L1-seal, Jaccard similarity between L1 and L2 active themes < 0.4 for >= 5/8 seeds
- Test: PerLayerThemeTracker
- **Prediction**: PASS (different constraint fields)

---

## 4. Implementation Plan

### 4.1 Changes to `hierarchical_evolver.py`

The current L1→L2 cascade logic (from B7) only handles L0→L1. Extend to:

```python
# In _check_layer_formation():
if layer == 1 and l1_partial_seal_detected:
    # 1. Extract L1's frozen bits as L2 constraint field
    l1_frozen = get_frozen_bits(layer=1)
    
    # 2. Create L2 from L1's active space under L1 constraints
    l2_bits = create_layer_from_constraints(
        base_layer=1,
        constraint_bits=l1_frozen,
        binding_threshold=scaled_threshold(1, l1_active_count)
    )
    
    # 3. Register L2
    add_layer(l2_bits, parent=1)
```

### 4.2 New Method: `encapsulate_next_layer(parent_layer)`

The existing `encapsulate_with_bits()` in `hierarchy_manager.py` handles single-layer parent→child. For B9:

```python
def encapsulate_next_layer(parent_layer: int) -> Layer:
    """
    Create next layer from parent's frozen bits as constraint field.
    
    Steps:
    1. Get parent's frozen lateral bits (the sealed portion)
    2. Get parent's active hierarchy bits (the unsealed portion)  
    3. Apply constraint field: only bits NOT in frozen set are eligible
    4. Apply binding_threshold to eligible bits
    5. Create new layer with constrained bit set
    """
```

### 4.3 Binding Threshold Scaling

```python
def scaled_threshold(layer_index: int, n_active: int) -> float:
    """Scale binding threshold for higher layers."""
    base = 0.05        # proven for L0 (N0=48)
    base_n = 48.0
    k_scale = 2.0      # empirically determined
    
    if layer_index == 0:
        return base
    
    # Scale: smaller spaces need lower thresholds to achieve same coherence
    ratio = n_active / base_n
    return base * ratio * k_scale
```

---

## 5. Experiment Config (exp_123)

### 5.1 Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| N0 | 48 | Proven to seal (B8) |
| total_steps | 15000 | Extra steps for L1→L2 cascade |
| sample_interval | 10 | Dense sampling |
| binding_threshold | 0.05 (L0) | Standard |
| ilp_floor | 15 | Standard |
| l1_threshold_scaling | True | Enable automated scaling |
| max_layers | 3 | Allow L2 formation |

### 5.2 Seeds

Same 8 seeds: [42, 142, 242, 342, 442, 542, 642, 742]

### 5.3 Output

- Per-layer NSI/CIV/Jaccard (from PerLayerMetricsCollector)
- Layer formation timestamps (L0 seal, L1 formation, L1 seal, L2 formation)
- H50-H55 pass/fail per seed
- Layer cascade diagram

---

## 6. Risk Analysis

### 6.1 L1 Never Seals
- **Risk**: Medium. B8 showed L1 seal ratio ~0.55 which is > 0.4 but not > 0.8 (old threshold)
- **Mitigation**: Scale binding_threshold to 0.02
- **Contingency**: If L1 never seals, B9 is blocked; need more aggressive threshold tuning or different partial seal strategy

### 6.2 L2 Forms But Is Silent
- **Risk**: Low. B5 showed L2 with independent coupling was genuinely active
- **Mitigation**: Monitor L2 active bits / Hamming weight during experiment

### 6.3 L2 Merely Echoes L1 (false autonomy)
- **Risk**: Medium. B1-B3 showed persistent L1↔L2 coupling
- **Mitigation**: This is precisely what H53-H55 test; if they fail, architecture needs fundamental redesign

### 6.4 Computation Time
- **Risk**: High. 8 seeds × 15000 steps may take 3-6 hours
- **Mitigation**: Run overnight; consider 4 seeds for initial validation

---

## 7. Theory-Driven Predictions

Based on the Theory of Difference mapping:

| Hypothesis | Theory-based Prediction | Confidence |
|-----------|------------------------|------------|
| H50 (L1 seals) | PASS if threshold scaled | High |
| H51 (L2 forms) | PASS | High |
| H52 (L1 auto) | PASS (replicate B8) | High |
| H53 (L2 auto) | PASS | Medium-High |
| H54 (CIV indep) | PASS | Medium |
| H55 (theme div) | PASS | Medium |

**Key theoretical claim**: If L2 is truly generated from L1's constraint field (not from L0 directly), then L2's dynamics should be **autonomous but constrained** — not a derivate of L1, but operating within L1's frozen structure.

---

## 8. Next Steps

1. **Wait for exp_122 v3 results** to confirm H46-H49 values
2. **If H48 fails** (L1 seal ratio < 0.4): tune binding_threshold to 0.02 in exp_121 first
3. **If H48 passes**: proceed directly to exp_123 with current params
4. **Implement B9 code changes** in `hierarchical_evolver.py`
5. **Write exp_123 script**
6. **Run exp_123** (8 seeds × 15000 steps)
