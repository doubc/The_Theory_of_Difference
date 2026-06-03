# Phase 6: Narrative Recursive Closure (NRC)

**Design Date**: 2026-06-04  
**Based on**: 差异论 V1.7 Upgrade Outline §1-§2 + §7  
**Phase 5 Complete**: Tracks A-D ✅ (Phase 5 Track Summary: docs/phase5_track_b_summary.md)

---

## 1. Motivation: The Spiral We Haven't Closed

Phase 4 built CSC+NSE — the generative engine (CSC) and the measurement apparatus (NSE). Phase 5 layered multi-scale dynamics on top: L1 passive constraint (B8), L2 independent clustering (B5), L3 framework reorganization (B10), resource constraints (C1-C2), and long-term evolution (D1).

But there's a structural omission: **narrative never feeds back into the possibility space.**

In the current architecture:
- CSC reads NRO state → generates narrative → NSE measures NSI → **stop**
- Narrative is the **output** — it's measured, analyzed, and filed. It never changes what CSC sees as its "possibility space."
- The spiral P_{t+1} = R(S(M(E(P_t)))) is broken at the R→P step.

V1.7 §1.2 formalizes this gap precisely:
> "叙事递归不只是对既有安排的解释，它会改变主体对自身、对他人、对制度、对未来的理解，从而重排可能性空间的结构。"

The simulation has been building the **generative forward pass** of the spiral. Phase 6 builds the **recursive closure** — the feedback path that completes the cycle.

---

## 2. The Core Form: P_{t+1} = R(S(M(E(P_t))))

From V1.7 §7.1:

$$P_{t+1} = R(S(M(E(P_t, D_t))))$$

Where:
- **E** = Event Compression — narrative accumulation condenses into events
- **M** = Minimum Variation — system selects minimal-variation paths
- **S** = Nearest Stable State — system settles into a new temporary equilibrium
- **R** = Narrative Recursion — the settled state is interpreted, named, legitimized, and fed back

In the simulation's existing language:

| Formal Component | Existing Mechanism | Gap |
|---|---|---|
| **P_t** (Possibility Space) | NRO state + bit space | Implicit, not formalized |
| **E** (Event Compression) | Narrative level distribution → CIV events | Partial — event detection exists |
| **M** (Minimum Variation) | CIVRateLimiter → stabilization dynamics | Partial — too coarse |
| **S** (Nearest Stable State) | NSE stability metrics + ILP | Partial — measurement exists |
| **R** (Narrative Recursion) | **NONE** | **MISSING — Phase 6 adds this** |
| **P_{t+1}** (Recursed Space) | **NONE** | **MISSING — Phase 6 adds this** |

---

## 3. Architecture: Narrative Recursive Closure Module

### 3.1 High-Level Design

```
         ┌──────────────────────────────────────────────────────┐
         │                     NRC Module                       │
         │  ┌─────────┐  ┌─────────┐  ┌──────────────────┐    │
P_t ─────┼─▶│  Event  │──▶│Minimum │──▶│  Nearest Stable  │    │
         │  │Compress │  │Variation│  │  State (settle)   │    │
         │  └─────────┘  └─────────┘  └────────┬─────────┘    │
         │                                     │              │
         │                        ┌────────────▼──────────┐   │
         │                        │  Narrative Recursion  │   │
         │                        │  (3-layer recursion)  │   │
         │                        └────────────┬──────────┘   │
         │                                     │              │
         │                        ┌────────────▼──────────┐   │
         │                        │  Space Rewriting      │   │
         │                        │  (P_t → P_{t+1})     │   │
         │                        └────────────┬──────────┘   │
         └─────────────────────────────────────┼──────────────┘
                                               │
                                               ▼
                                         P_{t+1}
                                    (rewritten bit space)
                                               │
                                               ▼
                                     CSC receives P_{t+1}
                                    as its new possibility space
```

### 3.2 Module: EventCompressor (E-function)

**Purpose**: Convert accumulated narrative tension into discrete events.

**Input**: NRO narrative level distribution over a window of steps.  
**Output**: Set of events {e₁, e₂, ..., eₙ} with type and magnitude.

**Design**:

```python
class EventCompressor:
    """
    E(P_t, D_t): Event function — difference accumulation compresses into events.
    """
    def __init__(self, window=20, collapse_threshold=0.15):
        self.window = window
        self.collapse_threshold = collapse_threshold
    
    def compute_events(self, step_results):
        """
        1. Track narrative level transitions over window
        2. Detect 'collapses' — sudden drop in a level's presence
        3. Detect 'emergences' — sudden rise in a level's presence
        4. Return list of Event objects
        """
        events = []
        # Collapse event: level presence drops > threshold
        # Emergence event: level presence rises > threshold
        # Tipping event: a minor level crosses to majority
        return events
```

**Types of events** (from V1.7 §3.1):
- **Structural Event**: Level re-organization within existing bit structure
- **Base-Map Event**: Bit space itself gets rewritten (partial reset, new dimensions added)
- **Narrative Shift Event**: Dominant narrative level changes (e.g., MINI → INSTITUTIONAL)

### 3.3 Module: MinimumVariationSelector (M-function)

**Purpose**: After events compress, select the minimal-variation response path.

**Input**: Event set + current possibility space P_t.  
**Output**: Selected response path (affects CIV selection, bit mutation bias).

**Design**:
```python
class MinimumVariationSelector:
    """
    M(·): Minimum variation function — select minimal resistance path.
    """
    def __init__(self, base_cost=0.1, path_memory=50):
        self.base_cost = base_cost
        self.path_memory = path_memory
    
    def select_path(self, events, possibility_space):
        """
        1. For each possible response, compute variation cost
        2. Select path with minimal variation (Occam's razor in action-space)
        3. Exception: base-map events force high-variation responses
        """
        pass
```

### 3.4 Module: NearestStableSettler (S-function)

**Purpose**: The system falls to the nearest temporary stable state after events + variation.

**Input**: Selected response path + current state.  
**Output**: New settled state (affects NSE stability metrics, ILP).

**Design**:
```python
class NearestStableSettler:
    """
    S(·): Nearest stable state function — fall to temporary equilibrium.
    """
    def __init__(self, settling_rate=0.3):
        self.settling_rate = settling_rate
    
    def settle(self, response_path, current_state):
        """
        1. Apply response path as adjustments to narrative levels
        2. Settle toward local stability minimum
        3. Return new stable distribution
        """
        pass
```

### 3.5 Module: NarrativeRecursor (R-function) — THE KEY COMPONENT

**Purpose**: The settled state is interpreted and named, then fed back to rewrite the possibility space. This is the core addition of Phase 6.

**Three layers** (from V1.7 §2.2):

| Layer | Name | Effect on P_t | Granularity |
|---|---|---|---|
| **R₀** | Micro-recursion | Promotes/demotes individual levels | Per-narrative-level |
| **R₁** | Institutional recursion | Shifts stability basin weights | Per-snapshot |
| **R₂** | Civilizational recursion | Rewrites bit space topology | Global/epochal |

**Design**:
```python
class NarrativeRecursor:
    """
    R(·): Narrative recursion function — three layers of recursive feedback.
    P_{t+1} = R(S(M(E(P_t))))
    """
    def __init__(self):
        self.r0_weight = 0.4  # Micro
        self.r1_weight = 0.35 # Institutional  
        self.r2_weight = 0.25 # Civilizational (rare, powerful)
        
        # Recursion thresholds
        self.r2_threshold_nsi = 0.85  # Need high NSI for civilizational recursion
        self.r2_cooldown = 200        # Min steps between civilizational events
    
    def recurse(self, settled_state, current_possibility_space, nsi_history):
        """
        1. R₀: Micro-recursion — adjust level-affinity weights
           - CIV events → CIV becomes more likely (narrative reinforcement)
           - Failed events → suppressed (narrative suppression)
        
        2. R₁: Institutional recursion — shift stability basins
           - Stable institutional narrative → wider basin
           - Unstable → basin narrows (crisis window)
        
        3. R₂: Civilizational recursion — rewrite bit space (rare)
           - Requires NSI > r2_threshold AND sufficient difference accumulation
           - Adds new bit dimensions or redefines existing ones
           - This is the 'base-map event' mechanism from V1.7 §3.1
        
        Returns: rewritten_possibility_space (P_{t+1})
        """
        p_new = copy.deepcopy(current_possibility_space)
        
        # R₀: Micro level-affinity shifts
        p_new = self._micro_recurse(p_new, settled_state)
        
        # R₁: Institutional basin shifts
        p_new = self._institutional_recurse(p_new, settled_state)
        
        # R₂: Civilizational rewriting (conditional, rare)
        if self._should_civilizational_recurse(nsi_history):
            p_new = self._civilizational_recurse(p_new, settled_state)
            self.r2_last_step = current_step
        
        return p_new
    
    def _micro_recurse(self, p, state):
        """
        Adjust level-transition probabilities based on recent narrative success.
        If CIV level fires, CIV→CIV transition gets slightly boosted.
        If MINI level fails (never reaches CIV), MINI→CIV gets suppressed.
        """
        for level in p.level_transition_weights:
            if state.narrative_levels[level.name] > 0:
                p.level_transition_weights[level.name] *= (1 + self.r0_weight * 0.01)
            else:
                p.level_transition_weights[level.name] *= (1 - self.r0_weight * 0.005)
        return p
    
    def _institutional_recurse(self, p, state):
        """
        Adjust institutional stability parameters based on narrative persistence.
        A stable INSTITUTIONAL layer widens its own stability basin.
        """
        inst_stability = state.institutional_stability
        p.stability_basin_width *= (1 + self.r1_weight * (inst_stability - 0.5) * 0.02)
        p.stability_basin_floor *= (1 + self.r1_weight * (inst_stability - 0.5) * 0.01)
        return p
    
    def _civilizational_recurse(self, p, state):
        """
        RARE event: rewrite the possibility space itself.
        In simulation terms: add new bit dimensions, redefine bit categories,
        or create a new layer structure.
        This is the 'cognitive revolution' moment — the simulation 
        fundamentally changes its own architecture.
        """
        n_new_bits = max(1, int(p.n_bits * 0.1))  # Add 10% new bits
        p.n_bits += n_new_bits
        p.add_dimension(n_new_bits, source='civilizational_recursion')
        return p
```

### 3.6 SpaceRewriter

**Purpose**: Bridge from R(·) output back to P_{t+1} that CSC can consume. This is the actual "rewriting of possibility space."

```python
class SpaceRewriter:
    """
    Converts NarrativeRecursor output into changes the simulation engine
    can consume: modified bit space, adjusted transition probabilities,
    new structural dimensions.
    """
    def rewrite(self, recursed_space, csc_state):
        """
        1. Apply transition weight changes to NRO's narrative level generator
        2. Apply stability basin changes to ILP/booster parameters
        3. Apply civilizational changes (if R₂ triggered) to bit space
        4. Return new CSC input state
        """
        csc_state.narrative_weights = recursed_space.level_transition_weights
        csc_state.stability_floor = recursed_space.stability_basin_floor
        if recursed_space.new_dimensions:
            csc_state.add_dimensions(recursed_space.new_dimensions)
        return csc_state
```

---

## 4. Integration with Existing Architecture

### 4.1 Pipeline

Current pipeline:
```
NRO → CSC → NSE → metrics
```

Phase 6 pipeline:
```
NRO → CSC → NSE → [NRC → SpaceRewriter] → CSC (next step)
                ↑___________________________|
```

### 4.2 Where NRC Sits

NRC runs **after** NSE but **before** the next CSC step. It's a feedback module, not a replacement.

The existing evolver `run()` loop would be modified at the end of each snapshot:
```
1. NRO.get_summary()
2. CSC.couple(summary)
3. NSE.step(civ_count, ...)  
4. [NEW] NRC.process(nse_state, csc_state, possibility_space)
5. [NEW] SpaceRewriter.apply(nrc_output, csc_state)
6. ... continue to next step
```

### 4.3 What Changes vs Phase 5

| Component | Phase 5 | Phase 6 |
|---|---|---|
| CSC | Generative engine (L0→L1→L2 coupling) | Same + receives rewritten P_t |
| NSE | Measurement only (NSI, CIV metrics) | Same + feeds event data to NRC |
| Booster | Forces CIV count up | Same (maintains minimum activity) |
| **NRC** | **Doesn't exist** | **NEW — closes the spiral** |
| **SpaceRewriter** | **Doesn't exist** | **NEW — feeds back to CSC** |
| PerLayerMetrics | L0/L1/L2 tracking, Jaccard flux | Same + feeds layer-specific recursion |

---

## 5. Hypotheses for Phase 6

### 5.1 Core Narrative Recursion Hypotheses

| Hyp | Description | Threshold |
|---|---|---|
| **H60** | Micro-recursion (R₀) produces measurable level-affinity shifts | ≥80% of levels show >5% weight change within 200 steps |
| **H61** | Institutional recursion (R₁) creates wider stability basins for persistent narratives | Correlation between INSTITUTIONAL persistence and basin width >0.5 |
| **H62** | Civilizational recursion (R₂) triggers base-map events | ≥1 R₂ event per 1000 steps when NSI >0.85 |
| **H63** | The spiral converges (not diverges) | P_{t+1} - P_t decreases monotonically over 2000 steps |
| **H64** | Spiral completeness: all four components (E→M→S→R) fire at least once | ≥3 complete cycles per 1000 steps |

### 5.2 Effect on Existing Metrics

| Existing Hyp | Expected Change | Direction |
|---|---|---|
| H1 (NSI max) | Should increase (recursive feedback amplifies narrative) | ↑ |
| H5 (CIV) | CIV may become more structured (not constant booster) | → or ↑ quality |
| H37 (secondary transitions) | Should become more frequent (R₁ produces institutional shifts) | ↑ |
| H39 (NSI stability) | May show genuine cycles now (R→P feedback creates oscillation) | Changed |

### 5.3 V1.7 Form Integration Hypotheses

| Hyp | Description | Threshold |
|---|---|---|
| **H70** | Form fidelity: simulation E→M→S→R sequence matches P_{t+1}=R(S(M(E(P_t)))) | ≥90% cycle completion rate |
| **H71** | P_{t+1} ≠ P_t (non-repetition) | Mean difference >0.1 across consecutive spaces |
| **H72** | Institutional phase transition (Γ_t) triggers at critical difference density K* | Γ_t fires within 50 steps of K_t ≤ K* |
| **H73** | Narrative recursion five actions fire in sequence (screen→name→connect→act→verify) | ≥70% of cycles show complete action sequence |

---

## 6. Implementation Plan

### Phase 6 P0: Core Module (1 session)
1. Create `engine/narrative_recursive_closure.py` with EventCompressor, MinimumVariationSelector, NearestStableSettler, NarrativeRecursor, SpaceRewriter
2. Define data types: Event, RecursionOutput, RewrittenSpace
3. Unit tests for each sub-module

### Phase 6 P1: Integration (1 session)
1. Modify `hierarchical_evolver.py` `run()` to call NRC after NSE
2. Wire SpaceRewriter output into next CSC iteration
3. Integration test with exp_129 (4 seeds × 1000 steps)

### Phase 6 P2: Validation (1-2 sessions)
1. Run exp_129_core (8 seeds × 2000 steps)
2. Test H60-H64 and H70-H73
3. Compare with Phase 5 D1 baseline

### Phase 6 P3: Multi-layer NRC (if time allows)
1. Layer-specific narrative recursion (L0-recursion affects L1, L1-recursion affects L2)
2. Test cascading recursion closure at scale

---

## 7. Key Design Decisions

### Decision 1: NRC as separate module, not NSE extension
- **Rationale**: NSE is measurement (read-only). NRC is feedback (write-capable). Mixing them violates separation of concerns.
- **Consequence**: NSE metrics remain interpretable as "diagnostics" even after Phase 6.

### Decision 2: Three-layer recursion is granularity-mapped to simulation layers
- R₀ (micro) → per-narrative-level adjustments (fast, continuous)
- R₁ (institutional) → stability basin shifts (medium, episodic)
- R₂ (civilizational) → bit space rewriting (rare, epochal)
- This mirrors the L0/L1/L2 hierarchy but is NOT the same — R₀ can fire within a single simulation layer.

### Decision 3: Civilizational recursion is rate-limited
- R₂ cooldown prevents cascading destruction of the simulation space.
- This matches V1.7 §5.4 (self-limitation) — the theory limits itself, the simulation limits itself.

### Decision 4: Event compression uses narrative level transitions, not raw CIV
- Raw CIV is too coarse (booster artifact). Level transitions capture qualitative shifts.
- This aligns with V1.7 §3.1's distinction between structural events and base-map events.

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| NRC destabilizes existing H1-H8 | Medium | High | Run without booster in ablation |
| R₂ base-map events break the simulator | Low | Critical | Hard lock on max 20% new bits per event |
| Recursion creates runaway feedback | Medium | Medium | Apply dampening: recursion_weight ∈ [0.1, 0.5] |
| Event compressor fires nothing (flat narrative) | Low | High | Fallback: force-compress at fixed intervals |
| V1.7 formalization too abstract for simulation | Medium | Low | Keep practical: minimal function set, expand later |

---

## 9. Summary

Phase 6 closes the spiral that V1.7 describes but that no simulation has yet implemented:

> P_{t+1} = R(S(M(E(P_t))))

Phase 5 built L0→L1→L2 emergence and measured it. Phase 6 builds the feedback path — narrative that rewrites its own possibility space. This is the difference between a **generative model** (what exists) and a **self-modifying generative model** (what Phase 6 aims for).

The key architectural insight: the NRC module is small (~300-400 lines), but its integration into the existing loop completes a theoretical cycle that has never been implemented in a running simulation. The NRC doesn't replace anything — it adds the missing R→P arrow.
