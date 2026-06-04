# Phase 7 Theory-Engineering Mapping: V1.7 → Simulation Architecture

**Date**: 2026-06-04 18:20  
**Audience**: Post-exp_136 analysis team  
**Purpose**: Map V1.7 §1-§2, §7 formalization directly to exp_136 code/module structure

---

## 1. The Spiral Formula: P_{t+1} = R(S(M(E(P_t))))

### V1.7 §1.2 Formulation

$$P_{t+1} = R(S(M(E(P_t, D_t))))$$

### Engineering Mapping

| Formula Component | Module/Class | File | Method |
|---|---|---|---|
| $P_t$ (possibility space) | `cross_scale_coupling.py` → `CSC.step()` | `engine/cross_scale_coupling.py` | The bit space + level state that feeds NRO |
| $D_t$ (difference accumulation) | `hierarchical_evolver.py` → `run()` step 4 (ODI) | `engine/hierarchical_evolver.py` | ODI computation from bit correlations |
| $E(P_t, D_t)$ (event compression) | `EventCompressor` | `engine/narrative_recursive_closure.py` | Maps narrative_tension → structural/base-map/narrative-shift events |
| $M(\cdot)$ (minimal variation) | `MinimumVariationSelector` | `engine/narrative_recursive_closure.py` | Selects minimal-resistance response paths |
| $S(\cdot)$ (nearest stable) | `NearestStableSettler` | `engine/narrative_recursive_closure.py` | Falls to temporary equilibrium |
| $R(\cdot)$ (narrative recursion) | `NarrativeRecursor` (R0/R1/R2) | `engine/narrative_recursive_closure.py` | 3-layer recursion producing rewritten_space |
| $P_{t+1}$ (new P-space) | `SpaceRewriter` → CSC feedback | `engine/narrative_recursive_closure.py` + `hierarchical_evolver.py` | `rewritten_space` → `level_states` stability/basin override |

### Linear Flow (per NRC cycle)

```
NRO.get_summary() → narrative_level_distribution
  → EventCompressor.compress() → events[]
    → MinimumVariationSelector.select() → response_paths
      → NearestStableSettler.settle() → settled_states
        → NarrativeRecursor.recurse() → rewritten_space
          → SpaceRewriter.rewrite() → modified level_states
            → CSC.step() reads modified level_states → next step
```

---

## 2. Three-Layer Narrative Recursion (V1.7 §2.2)

### V1.7 Description

> 小叙事递归：组织一次行情、一次危机中的共同行动
> 制度正当化叙事：稳定某个最近稳态
> 文明级生成叙事：改写理解世界的基本坐标

### Engineering Mapping

| V1.7 Layer | NRC Layer | Activation Condition | Effect |
|---|---|---|---|
| 小叙事递归 | **R₀ (micro)** | Every NRC cycle | Adjusts level_affinity weights (which narrative levels are more/less likely) |
| 制度正当化叙事 | **R₁ (institutional)** | Every NRC cycle | Adjusts stability_basin widths (makes some basins wider/more attractive) |
| 文明级生成叙事 | **R₂ (civilizational)** | cumulative_tension ≥ r2_tension_threshold (1.0) | **Rewrites bit space**: modifies level_transition_weights, inter_level_stability_coupling |

### Phase 6 History

| Layer | exp_129 | exp_130 | exp_131 | exp_132 | exp_133 | exp_134 | exp_135 |
|---|---|---|---|---|---|---|---|
| R₀ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| R₁ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| R₂ | ❌ | ❌ | ❌ | ❌ | **✅** | **✅** | **✅** |

**Key insight**: R2 required cumulative tension trigger (not NSI threshold). This is now enabled for Phase 7.

---

## 3. Narrative as Mediating Mechanism (V1.7 §2.3)

### V1.7 Description

> 叙事是差异从分散状态进入共同行动状态的中介机制，它完成五个动作

### Engineering Mapping

| Narrative Action | NRC Component | Evidence in Simulation |
|---|---|---|
| 筛选差异 (filter) | `EventCompressor.compress()` | `tension > threshold` determines which differences become events |
| 命名差异 (name) | NRC `_format_level_state()` | Level names: MINI_NARRATIVE, TRUST, INSTITUTION, CIVILIZATION |
| 连接差异 (connect) | `NarrativeRecursor._update_affinity()` | Builds level → level transition weights (causal links) |
| 行动化差异 (act) | `SpaceRewriter.rewrite()` → CSC feedback | Changes stability_basin → alters next CSC.step() output |
| 递归验证差异 (verify) | Next NRC cycle compares old/new level distribution | Cycle_count increments; convergence slope measures change |

**Gap**: The simulation lacks explicit "递归验证差异" tracking — there's no mechanism that compares pre-cycle and post-cycle level distributions to validate whether the narrative recursion produced expected changes. The convergence slope (H63) is a proxy but not the full mechanism.

---

## 4. Bit Space Rewriting as R→P (V1.7 §7.1)

### V1.7 Formalization

$$P_{t+1} = R(S(M(E(P_t, D_t))))$$

### Engineering Implementation

The `SpaceRewriter.rewrite()` returns a dict that gets applied to `level_states`:

```python
# From narrative_recursive_closure.py (SpaceRewriter)
def rewrite(self, settled_states, rewritten_space):
    """Apply R output back to P-space (CSC input)."""
    # rewritten_space contains:
    # - level_transition_weights: modified by R2
    # - stability_basins: modified by R1
    # - level_affinity: modified by R0
    return {
        'level_transition_weights': modified_weights,
        'stability_basins': modified_basins_with_fallbacks,
        'level_affinity': modified_affinity
    }
```

In `hierarchical_evolver.py`, this dict is applied:

```python
# run() step (after NRC.process()):
if active_rewriting:
    for key in rewritten_space:
        level_states[key] = rewritten_space[key]
```

### H82 Measurement

H82 tests whether this rewriting is **detectable** at the system level:

```python
def h82_rewriting_detectability(nrc_metrics):
    """Measure mean level_transition_weights delta after R2."""
    deltas = nrc_metrics.get('r2_rewriting_deltas', [])
    if not deltas:
        return 0.0
    return np.mean(deltas)  # threshold: > 0.05
```

**Key question**: Is the rewrite `level_states[key] = rewritten_space[key]` strong enough to be picked up by next-step metrics? If the stability_basin change is small, the next CSC.step() may produce nearly identical output, making R→P invisible to measurement.

---

## 5. Structural vs Base-Map Events (V1.7 §3.1)

### V1.7 Description

> 结构事件：旧结构还在，但路径变窄
> 底图事件：旧结构赖以运转的可能性空间被改写

### Engineering Mapping

| Event Type | EventCompressor Category | Effect on P-space |
|---|---|---|
| Structural Event | `structural` | Alters level_transition_weights temporarily |
| Base-Map Event | `base_map` | Changes stability_basin boundaries (which basins are stable vs unstable) |
| Narrative Shift | `narrative_shift` | Changes level_affinity (which narratives are "in play") |

### Phase 7 Expectation

At N0=72 (optimal scale), we expect more structural differentiation → more structural events → more NRC cycles → higher chance of base-map events.

---

## 6. H81-H85 Mapped to V1.7 Concepts

| Hypothesis | V1.7 Section | Core Question | Engineering Measure |
|---|---|---|---|
| **H81** (spiral completeness) | §1.2 | Does the spiral produce cycles? | ≥2 E→M→S→R cycles in first 500 steps |
| **H82** (R→P rewriting) | §2.2, §7.1 | Does R² measurably change P-space? | level_transition_weights delta > 0.05 |
| **H83** (NSI improvement) | §2.3 | Does recursion enrich narrative? | Mean NSI ≥ Phase 5 D1 baseline + 0.02 |
| **H84** (cross-scale consistency) | §6 (象界咬合) | Do L0 and L1 spirals align? | Jaccard event timing > 0.3 |
| **H85** (no degradation) | §5.4 (限缩公约) | Does the spiral destabilize? | H1-H8 pass at step 5000 |

### Theoretical Weight

| Hyp | If PASS | If FAIL |
|---|---|---|
| H81 | Spiral formula is computationally realizable at N0=72 | N0=72 may not increase event frequency (contrary to §1.2 expectation) |
| H82 | **R→P is real** — narrative reshapes P-space (confirms §2.2 civilization-level claim) | R→P is cosmetic — rewritten_space doesn't measurably change system behavior |
| H83 | Recursion enriches narrative (confirms §2.3's "action化差异" claim) | Recursion is neutral on narrative quality |
| H84 | Multi-scale spiral is consistent (confirms §6 咬合 claim) | L0/L1 spirals are independent (interesting theoretical result) |
| H85 | §5.4 self-limitation is robust; spiral doesn't break the system | Architecture unstable at N0=72 |

---

## 7. Phase 7 vs V1.7: What's Missing

While Phase 7 closes the R→P feedback path, V1.7 describes a richer framework that the simulation doesn't yet implement:

| V1.7 Concept | Current Status | Future Phase |
|---|---|---|
| Five mediating actions (筛选→命名→连接→行动化→递归验证) | 4/5 implemented; **递归验证** missing | Phase 8? |
| Structural vs Base-Map events | Both classified but **base-map event → true bit space rewriting** has no feedback path (R2 rewrites level weights, not the bit space itself) | Phase 8.5 |
| Difference density K_t and phase transition Γ_t | Not tracked | Phase 9 |
| State space X_t = (P, V, OI, I, B, σ, C, D, K, A, N, Γ) | Only P, N, A partially tracked | Phase 9-10 |
| Limitation conventions (5.4) | Applied implicitly; not formalized | Phase 10 |

---

## 8. Prediction: Phase 7 Expected Outcome

Based on V1.7 §1.2 and engineering constraints:

| Hyp | Prediction | Rationale |
|---|---|---|
| H81 | **PASS** (≥6/8) | N0=72 → more structural differentiation → more events → ≥2 cycles |
| H82 | **PARTIAL** (3-4/8) | R→P rewriting exists but may be submerged by CSC's own dynamics |
| H83 | **BORDERLINE** | NSI at N0=72 was 0.50-0.70 in Phase 5 D1; NRC may add 0.02-0.05 |
| H84 | **PASS** (≥4/8) | N0=72 produces L1 clusters naturally; events diffuse across scales |
| H85 | **PASS** (8/8) | H1-H8 held through Phase 6 at N0=48 with NRC; N0=72 should hold |

**Overall**: 3-4/5 PASS — partial success, proceeding to Phase 8 with documented findings.

---

*Written while exp_136 runs in background (PID 1432, started 18:19 CST). Ready for analysis upon completion.*
