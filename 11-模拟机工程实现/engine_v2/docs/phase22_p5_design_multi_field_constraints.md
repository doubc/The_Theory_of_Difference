# Phase 22 P5: Multi-Field Competitive Constraints — Design

**Date**: 2026-06-14  
**Status**: Design Complete — Pending Implementation  
**Prerequisite**: Phase 22 P4 (Proportional Injection Rate) ✅

---

## 1. Theoretical Motivation

### 1.1 The Single-Field Limit

Phase 22 P0-P4 have all operated with a **single constraint field**: the environment energy field with a single `constraint_strength` parameter. This means the entire system experiences one homogeneous injection field.

In real open systems, however, constraints are **multiple, heterogeneous, and often competing**:
- Biological systems face simultaneous thermodynamic, metabolic, and informational constraints
- Social systems face economic, cultural, and political constraints operating at different scales
- Physical systems face multiple boundary conditions (temperature, pressure, chemical potential)

### 1.2 Key Question

**What happens when multiple constraint fields compete or cooperate?**

Single-field dynamics show:
- Stronger constraint → more energy injection (P0)
- Constraint focuses energy, doesn't drain it (P0)
- Proportional injection achieves scale invariance (P4)

Multi-field dynamics introduce:
- **Interference**: Two fields with opposite phase → cancellation or standing waves
- **Synergy**: Cooperative fields → super-linear effect exceeding sum of parts
- **Dominance**: Stronger field overrides weaker one → phase transition at critical ratio
- **Emergent basins**: Multiple attractors from field configuration space

### 1.3 Physical Analogy

Single field = one tuning parameter on a radio (just volume)  
Multi-field = full equalizer (bass, treble, balance, fade)

A single scalar constraint strength is like adjusting only the global energy level. Multi-field competition enables **spectral shaping** of emergence — different constraints acting on different bit subspaces or scales.

---

## 2. Design

### 2.1 Multi-Field Infrastructure

**Concept**: Replace single `constraint_strength` with an array of `ConstraintField` objects, each with:
- `strength`: Field intensity (0.0-1.0)
- `frequency`: Temporal modulation frequency (0 = static)
- `phase`: Phase offset for interference patterns
- `domain`: Subspace the field acts on (all, even, odd, specific bit range)
- `coupling_type`: "additive" (sum), "multiplicative" (product), "competitive" (max)

```python
@dataclass
class ConstraintField:
    """A single constraint field for multi-field competition."""
    name: str                    # Field identifier
    strength: float = 0.5        # 0.0-1.0, field intensity
    frequency: float = 0.0       # Temporal modulation (0 = static)
    phase: float = 0.0           # Phase offset (radians)
    domain: str = "all"          # "all", "even", "odd", "range:low:high"
    coupling_type: str = "additive"  # "additive", "multiplicative", "competitive"
```

### 2.2 Effective Constraint Computation

The effective constraint at each step is computed from all active fields:

**Additive coupling** (default):
```
effective_c = Σ(wi × ci × modulation_t)
```
where:
- wi = field weight (normalized so sum of weights = 1)
- ci = field strength
- modulation_t = 0.5 × (1 + sin(2π × frequency × t + phase))

**Multiplicative coupling**:
```
effective_c = Π(1 + wi × ci × modulation_t) - 1
```
(Capped to [0, 1])

**Competitive coupling**:
```
effective_c = max(wi × ci × modulation_t)
```
(Strongest field dominates — winner-take-all)

### 2.3 Unified Injection Formula

The effective constraint feeds into the same injection formula verified in P0-P4:

```
injection = base_rate × (1 + effective_c × constraint_energy_factor)
```

This keeps backward compatibility: with one field at strength = constraint_strength, the formula reduces to the P0-P4 behavior.

### 2.4 Bit-Subspace Domains

Each field can act on a different bit subspace:
- `"all"`: All bits feel the field (original behavior)
- `"even"`: Only even-indexed bits
- `"odd"`: Only odd-indexed bits
- `"range:low:high"`: Bits in index range [low, high)

This allows **spatially heterogeneous constraints** — different parts of the bit string experience different field intensities.

For domain-limited fields, the injection is partitioned:
```
injection_per_bit = injection × (n_domain / n_total)
total_injection = Σ(injection_per_bit for active fields on that bit)
```

---

## 3. Hypotheses (H22-P5a through H22-P5e)

### H22-P5a: Field Interference ✅/❌

> Two out-of-phase fields (same strength, π phase offset) produce **lower effective energy** than one field of the same total strength.

- **Prediction**: Phase cancellation reduces net injection
- **Config**: 2 fields, strength=0.5 each, phase=0 vs phase=π
- **Metric**: Mean energy at step 1000
- **Expected**: Phase-cancelled pair yields E ≈ 70-80 vs in-phase pair E ≈ 90-100

### H22-P5b: Cooperative Synergy ✅/❌

> Two weak fields (strength=0.3 each) produce **super-linear energy** compared to one medium field (strength=0.6).

- **Prediction**: Additive coupling of two coherent fields amplifies beyond single-field equivalent
- **Config**: 2 fields × 0.3 in-phase vs 1 field × 0.6
- **Metric**: Mean energy comparison
- **Expected**: 2×0.3 > 1×0.6 (synergy from coherent modulation)

### H22-P5c: Critical Dominance Ratio ✅/❌

> There exists a critical strength ratio R_c where one field transitions from cooperative to dominant, producing a phase change in emergence dynamics.

- **Prediction**: At R ≈ 0.7 (e.g., field1=0.7, field2=0.3), the stronger field dominates and the weaker field's contribution becomes negligible
- **Config**: Sweep ratio from 0.5:0.5 to 0.9:0.1
- **Metric**: Step change in NSI, exit time, or sealing behavior at critical ratio
- **Expected**: Phase transition at R_c ≈ 0.65-0.75

### H22-P5d: Spatial Field Separation ✅/❌

> Two fields acting on different bit subspaces (even/odd) produce **higher total entropy** than two fields acting on the same subspace.

- **Prediction**: Spatial separation prevents interference → each field drives its subspace independently → more total structure but less coherence
- **Config**: 2 fields × strength=0.5, domain=even vs odd
- **Metric**: Total entropy, cross-subspace correlation, NSI
- **Expected**: Higher S_total but lower NSI (less system-wide coherence)

### H22-P5e: Competitive Coupling Regime ✅/❌

> Under competitive (winner-take-all) coupling, system dynamics become **bistable** — switching between field-dominant regimes.

- **Prediction**: Strong field dominates for a period, then weak field overtakes → intermittent dynamics
- **Config**: 2 fields with competitive coupling + temporal modulation (frequency=0.001)
- **Metric**: Field dominance time series, switching rate
- **Expected**: Bimodal distribution of bit-states, switching frequency ∝ modulation frequency

---

## 4. Experimental Design

### 4.1 Experiment Script Structure

```python
# exp_208_phase22_p5_multi_field.py

N0 = 48
seeds = 8
steps = 2000

# Field configurations (14 configs × 8 seeds = 112 runs)
configs = [
    # Baseline: single field
    {"fields": [ConstraintField("single", strength=0.5)], "coupling": "additive"},
    
    # Field interference (in-phase vs out-of-phase)
    {"fields": [
        ConstraintField("A", strength=0.5, frequency=0.0, phase=0.0),
        ConstraintField("B", strength=0.5, frequency=0.0, phase=0.0)
    ], "coupling": "additive"},
    {"fields": [
        ConstraintField("A", strength=0.5, frequency=0.0, phase=0.0),
        ConstraintField("B", strength=0.5, frequency=0.0, phase=math.pi)
    ], "coupling": "additive"},
    
    # Cooperative synergy
    {"fields": [
        ConstraintField("A", strength=0.3, frequency=0.0, phase=0.0),
        ConstraintField("B", strength=0.3, frequency=0.0, phase=0.0)
    ], "coupling": "additive"},
    {"fields": [ConstraintField("single", strength=0.6)], "coupling": "additive"},
    
    # Critical dominance ratio sweep (R: 0.5/0.5 → 0.9/0.1)
    {"fields": [
        ConstraintField("A", strength=0.6, frequency=0.0, phase=0.0),
        ConstraintField("B", strength=0.4, frequency=0.0, phase=0.0)
    ], "coupling": "additive"},
    {"fields": [
        ConstraintField("A", strength=0.7, frequency=0.0, phase=0.0),
        ConstraintField("B", strength=0.3, frequency=0.0, phase=0.0)
    ], "coupling": "additive"},
    {"fields": [
        ConstraintField("A", strength=0.8, frequency=0.0, phase=0.0),
        ConstraintField("B", strength=0.2, frequency=0.0, phase=0.0)
    ], "coupling": "additive"},
    {"fields": [
        ConstraintField("A", strength=0.9, frequency=0.0, phase=0.0),
        ConstraintField("B", strength=0.1, frequency=0.0, phase=0.0)
    ], "coupling": "additive"},
    
    # Spatial field separation
    {"fields": [
        ConstraintField("even_field", strength=0.5, domain="even"),
        ConstraintField("odd_field", strength=0.5, domain="odd")
    ], "coupling": "additive"},
    
    # Competitive coupling (bistability)
    {"fields": [
        ConstraintField("A", strength=0.7, frequency=0.001, phase=0.0),
        ConstraintField("B", strength=0.7, frequency=0.001, phase=math.pi)
    ], "coupling": "competitive"},
    
    # Mixed coupling types for exploration
    {"fields": [
        ConstraintField("A", strength=0.5, frequency=0.0, phase=0.0),
        ConstraintField("B", strength=0.5, frequency=0.0, phase=0.0)
    ], "coupling": "multiplicative"},
]
```

### 4.2 Metrics

For each run, collect:
- **Energy time series** (mean, std, min, max per step)
- **Entropy time series** (total, per-subspace)
- **Field dominance** (injection fraction from each field per step)
- **NSI** (narrative self-emergence index)
- **CIV** (collective innovation volume)
- **Field switching rate** (for H22-P5e: frequency of dominant-field changes)
- **Cross-field correlation** (bit-level correlation between field-affected subspaces)
- **Sealing time** (steps until bit freezing threshold reached)

### 4.3 Expected Total Runs

14 configs × 8 seeds = **112 runs**  
Estimated time: ~45-60 minutes on engine_v2

---

## 5. Infrastructure Changes

### 5.1 New/Modified Files

| File | Change |
|------|--------|
| `diffsim/environment_energy.py` | Add `ConstraintField` dataclass + `MultiFieldEnvironment` class |
| `diffsim/world.py` | Support multiple `ConstraintField` objects in WorldConfig |
| `experiments/exp_208_phase22_p5_multi_field.py` | New experiment script |
| `docs/phase22_p5_design_multi_field_constraints.md` | This document ✅ |

### 5.2 New Class: MultiFieldEnvironment

```python
class MultiFieldEnvironment:
    """
    Multi-field competitive constraints environment.
    
    Manages N constraint fields with configurable coupling types.
    Replaces single EnvironmentEnergyField when N > 1.
    """
    
    def __init__(self, config: MultiFieldConfig):
        self.fields = config.fields
        self.coupling = config.coupling_type  # additive/multiplicative/competitive
        self.base_rate = config.base_rate
        ...
    
    def compute_effective_constraint(self, step: int, 
                                      layer_bits: np.ndarray) -> float:
        """Compute net constraint from all fields at this step."""
        ...
    
    def compute_per_bit_injection(self, step: int,
                                   layer_bits: np.ndarray) -> np.ndarray:
        """Compute per-bit injection accounting for subspace domains."""
        ...
```

### 5.3 Backward Compatibility

`EnvironmentEnergyField` is kept as a convenience wrapper equivalent to `MultiFieldEnvironment` with a single field at `coupling_type="additive"`. All P0-P4 experiments run without changes.

---

## 6. Theoretical Predictions

### 6.1 Phase Diagram

```
Field Ratio (A:B)
    1:0              [single field phase] — baseline behavior
    0.75:0.25        [dominant phase] — A dominates, B negligible
    0.5:0.5 ↑ phase  [interference phase] — cancellation/modulation
    0.5:0.5 in-phase [synergy phase] — super-linear cooperation
    0.5:0.5 spatial  [independent phase] — subspace independence
```

Predicted phase boundaries:
- **Dominance transition**: at A:B ≈ 0.65:0.35 (H22-P5c)
- **Interference depth**: max cancellation at Δφ = π (H22-P5a)
- **Synergy gain**: 2×0.3 fields > 1×0.6 field by ~10-15% (H22-P5b)

### 6.2 Emergence Implications

If multi-field dynamics confirm these predictions, the **constraint field phase diagram** becomes a tunable parameter space for emergence engineering:
- **Constructive interference** → deeper emergence
- **Destructive interference** → shallower emergence (system control)
- **Spatial separation** → specialized sub-structures
- **Competitive coupling** → switching/intermittent dynamics

This would be a significant step toward "emergence engineering" — designing constraint landscapes to produce desired emergent properties.

---

## 7. File

- **Design document**: `engine_v2/docs/phase22_p5_design_multi_field_constraints.md` (this file)

## 8. Git

- **Commit**: Pending implementation of exp_208
- **Bug fix**: `environment_energy.py` — `step()` method fixed double-counting of exhausted entropy
