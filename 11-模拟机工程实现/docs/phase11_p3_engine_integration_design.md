# Phase 11 P3: SubspaceField → HierarchicalEvolver Engine Integration Design

**Date**: 2026-06-06 16:03 CST  
**Audience**: Engineering design for Phase 11 P3 coupling experiments  
**Status**: 📋 DESIGN — to be implemented after P2 results  

---

## 1. Motivation

Phase 11 P1 (subspace_field.py) created a **pure data-structure layer**:
- SubspaceSpec (bit assignment + per-subspace Rules)
- SubspaceField (container + coupling topology)
- 3 allocation strategies (static, interleaved, random)
- 34 unit tests

Phase 11 P2 (exp_148) verifies **isolated subspace behavior** by running independent N0_sub-sized HierarchicalEvolver instances. This tells us if N0_sub=10 worlds behave like independent scaled-down systems.

**For P3 (coupling experiments), SubspaceField must be integrated into the HierarchicalEvolver runtime** — meaning the evolver must:
1. Partition N0 bits per subspace assignment
2. Apply per-subspace Rules when computing A1-A9 axiom effects
3. Implement coupling ports for cross-subspace communication at runtime

This document designs that integration.

---

## 2. Core Design Decision: Single Evolver vs. Multiple Evolvers

### Option A: Multi-Evolver Architecture
Run k independent SpatialLongRangeEvolver instances (one per subspace) at each layer, with coupling ports between them.

| Pro | Con |
|-----|-----|
| Natural isolation: each subspace has its own state, constraints, axioms | Cross-subspace binding requires new inter-evolver communication |
| Parallel execution possible | Binding matrix is global — splitting it is non-trivial |
| Reuses existing evolver API directly | Sealing decisions must be coordinated across subspaces |

### Option B: Single Evolver with Per-Bit Rules
Modify SpatialLongRangeEvolver to apply per-bit rules and per-bit constraint scaling from SubspaceSpec.

| Pro | Con |
|-----|-----|
| Single binding matrix, single state space | Rules system originally designed for layer-level, not bit-level |
| Sealing is already global | Major refactor of axioms_v2.py required |
| Coupling is "automatic" (same space) | Hard to control coupling strength independently from spatial adjacency |

### Decision: Option A (Multi-Evolver)

**Rationale**:
1. Phase 11's core question is *"do different parameterizations produce different physics?"* — this requires independent evolvers with different Rules
2. Cross-subspace coupling should be a *controlled channel*, not an emergent property of adjacency in a unified space
3. The evolver already has a `SpatialLongRangeEvolver` per-layer pattern — adding per-subspace evolvers extends this naturally
4. P2's isolated-instance approach (exp_148) validates this architecture at zero coupling

---

## 3. Architecture: SubspaceAwareEvolver

### 3.1 Class Design

```python
class SubspaceAwareEvolver:
    """
    Wraps k independent SpatialLongRangeEvolver instances (one per subspace)
    with cross-subspace coupling ports.

    At each layer L, each subspace creates its own SpatialLongRangeEvolver
    with N = subspace_size[L]. The evolvers step synchronously, and
    coupling is applied between steps.

    Layer progression (sealing → new layer) is per-subspace:
    - Each subspace seals independently at its own time
    - An "all sealed" barrier triggers the next layer
    - Or a "majority sealed" trigger with lagging subspaces continuing
    """
```

### 3.2 Key Components

```
SubspaceAwareEvolver
├── SubspaceField           # from subspace_field.py (data structure)
├── SubspaceSolver[]        # k per-layer SpatialLongRangeEvolver wrappers
├── CouplingEngine          # cross-subspace coupling at each step
├── LayerCoordinator        # seal/next-layer coordination
└── MetricsCollector        # per-subspace + cross-subspace metrics
```

### 3.3 SubspaceSolver (per-subspace evolver wrapper)

```python
@dataclass
class SubspaceSolver:
    """Wraps one SpatialLongRangeEvolver for one subspace at one layer."""
    name: str                        # e.g., "S0", "S1", "S2"
    subspace: SubspaceSpec           # bit indices + rules
    evolver: SpatialLongRangeEvolver # actual evolver instance
    state: torch.Tensor              # current state (N_sub bits)
    binding_matrix: torch.Tensor     # binding matrix for this subspace
    constraints: LayerConstraints    # scaled by subspace Rules
    current_layer: int               # which hierarchical layer
    is_sealed: bool                  # whether this subspace has sealed
    frozen_bits: Set[int]            # locally frozen bits
```

**Rules → Constraints Mapping**:
```
binding_strength *= rules.binding_multiplier
source_weight *= (0.5 + rules.direction_bias)   # direction bias
sink_weight *= (0.5 + (1 - rules.direction_bias))
conservation_tightness controls A5 residual threshold
seal_threshold *= rules.seal_threshold_multiplier
```

### 3.4 CouplingEngine

```python
class CouplingEngine:
    """
    Applies cross-subspace coupling at each step.
    
    Coupling mechanism: bias injection
    
    For each connection (src → tgt) with strength s:
        bias[tgt] += s * binding_strength[src] * direction[src]
    
    For FULLY_CONNECTED:
        all subspaces exchange biases
    
    For UNIDIRECTIONAL:
        only source → target direction
    
    Coupling strength s ∈ [0.0, 1.0]:
        0.0 = no coupling (P2 mode)
        0.3 = weak coupling (subtle influence)
        0.7 = strong coupling (near-unified)
        1.0 = full coupling (effectively N0_total space)
    """
```

**Design choice**: Bias injection is the simplest physically meaningful coupling mechanism. It modulates how one subspace's binding/direction field influences another's axiom computations. This avoids the complexity of merging independent binding matrices while still creating cross-subspace influence.

### 3.5 LayerCoordinator

Handles per-subspace progression through hierarchical layers:

```python
class LayerCoordinator:
    """
    Coordinates per-subspace sealing and layer progression.
    
    Strategies:
    1. ALL_SEALED: advance all subspaces together (conservative)
    2. MAJORITY_SEALED: advance when >50% subspaces sealed (progressive)
    3. INDEPENDENT: each subspace progresses independently (maximum freedom)
    
    For P3 coupling exploration, MAJORITY_SEALED is the default.
    
    When a subspace seals at layer L:
    - Its frozen bits become a bias constraint for the next layer
    - Other subspaces at layer L continue evolving
    - Once across the barrier, all subspaces initialize layer L+1
    """
```

---

## 4. Integration Points into HierarchicalEvolver

### 4.1 Constructor Extension

Add to `HierarchicalEvolver.__init__()`:

```python
class HierarchicalEvolver:
    def __init__(self, ..., 
                 subspace_field: Optional[SubspaceField] = None):
        """
        subspace_field: If provided, enables subspace decomposition mode.
                        If None, behaves as original unified evolver (backward compat).
        """
        self.subspace_field = subspace_field
        self.subspace_mode = subspace_field is not None
```

### 4.2 Layer Initialization Change

Current (unified): One SpatialLongRangeEvolver per layer
New (subspace): N_per_layer * k SubspaceSolver instances

```python
def _init_layer(self, layer_id: int):
    if self.subspace_mode:
        for sub_name in self.subspace_field.space_names:
            spec = self.subspace_field.get_spec(sub_name)
            N_sub = self._get_subspace_N(layer_id, spec)
            evolver = SpatialLongRangeEvolver(
                N=N_sub,
                total_steps=self.steps_per_layer,
                ...
            )
            evolver.constraints = self._build_subspace_constraints(
                spec, N_sub, layer_id
            )
            self._subspace_solvers[layer_id][sub_name] = SubspaceSolver(
                name=sub_name, subspace=spec, evolver=evolver, ...
            )
    else:
        # original: single evolver per layer
        evolver = SpatialLongRangeEvolver(N=N, ...)
```

### 4.3 Step Loop Modification

Current: `evolver.step()` → step_callback
New: 
```python
for step in range(steps):
    for solver in subspace_solvers.values():
        solver.evolver.step()
    if coupling_strength > 0:
        self._apply_coupling(solvers)
    # coordination check
    if self._should_advance_layer(solvers):
        break
```

### 4.4 Metric Changes

New metrics needed:
- **Per-subspace**: H1-H8 pass rates, NSI, CIV, sealing time, L1 formation
- **Cross-subspace**: Pearson r(Sᵢ, Sⱼ), mutual information, binding matrix block strength
- **Emergent**: Cross-subspace theme coherence, inter-subspace binding at boundaries

---

## 5. Implementation Plan

### Phase 1: Core Wrapper (P3 pre-work)
1. Create `engine/subspace_evolver.py` with `SubspaceSolver` and `SubspaceAwareEvolver`
2. Implement `CouplingEngine.bias_injection()` — simplest coupling mechanism
3. Implement `LayerCoordinator` with MAJORITY_SEALED strategy
4. Wire into `HierarchicalEvolver.__init__()` as optional `subspace_field` parameter

### Phase 2: Per-Subspace Rules Application
1. Implement `_build_subspace_constraints()` — maps Rules → constraint scaling
2. Test: verify binding_multiplier=2.0 produces stronger binding (faster L1)
3. Test: verify direction_bias=0.9 produces stronger source-sink asymmetry
4. Test: verify no-Rules subspace (default) = original behavior

### Phase 3: Coupling Exploration (P3 experiments)
1. Implement exp_150: symmetric coupling scan (6 levels × 8 seeds)
2. Implement exp_151: asymmetric coupling (master-slave, 16 seeds)
3. Analysis: identify three coupling phase regions (weak/medium/strong)

### Phase 4: Parameter Specialization (P4 experiments)
1. Implement exp_152: binding strength differentiation (0.5×, 1.0×, 3.0×)
2. Implement exp_153: direction bias differentiation (0.9, 0.6, 0.5)

---

## 6. Backward Compatibility

The design ensures backward compatibility via the `subspace_field is None` check:

| Mode | subspace_field | Behavior | Tests |
|------|---------------|----------|-------|
| Unified | None | Original HierarchicalEvolver | 1029 tests pass |
| Isolated | SubspaceField(c=0.0) | k independent evolvers | New P2 tests |
| Coupled | SubspaceField(c>0.0) | k evolvers with bias injection | New P3 tests |

No existing functionality is affected.

---

## 7. Open Questions

1. **Sealing coordination**: If subspaces seal at different times, how long do we wait? A "stuck" subspace with no sealing events could block the entire cascade indefinitely. Solution: add a step limit timeout per-layer, advance with partial sealing.

2. **Coupling mechanism beyond bias injection**: Should we also support binding strength transfer (subspace A's tight binding makes subspace B's binding tighter)? For P3, bias injection is sufficient. Binding transfer would be P4+.

3. **Subspace at different layers**: Can S0 be at layer 2 while S1 is still at layer 1? The LayerCoordinator design allows this (INDEPENDENT mode), but for P3 we'll use MAJORITY_SEALED to keep things simple.

4. **Per-subspace memory/IO**: Each subspace evolver should ideally write separate snapshots and results. For P3, we'll aggregate into a single results dict with subspace-prefixed keys.

---

## 8. Timeline

| Step | Task | Est. |
|------|------|------|
| 1 | Create engine/subspace_evolver.py (SubspaceSolver + CouplingEngine) | 1 heartbeat |
| 2 | Wire into HierarchicalEvolver (constructor + layer init + step loop) | 1 heartbeat |
| 3 | Implement _build_subspace_constraints() | 0.5 heartbeat |
| 4 | Unit tests (subspace evolution, coupling, coordination) | 1 heartbeat |
| 5 | exp_150: symmetric coupling scan | 2 heartbeats |
| 6 | exp_151: asymmetric coupling | 1 heartbeat |
| **Total P3** | | **6.5 heartbeats** |

---

*Design v0.1 — 2026-06-06 16:03 CST*
*Next step: Wait for P2 results, then implement Phase 1 (subspace_evolver.py)*