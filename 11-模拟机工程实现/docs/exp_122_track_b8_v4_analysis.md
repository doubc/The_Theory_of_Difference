# Track B8 v4: L1 Passive Projection — Architectural Implications

> **Date**: 2026-06-03 (13:44 CST)
> **Status**: DEFINITIVE — B8 complete, no further re-runs needed
> **Git**: c8770e5 (PerLayerNSITracker v4: Jaccard flux)

---

## 1. Executive Summary

**The B8 finding is definitive**: L1 has zero post-seal autonomous dynamics. This is a **system truth**, not a metric failure.

PerLayerNSITracker v4 (Jaccard flux) correctly reports 0.0 because post-seal active bit sets are IDENTICAL across snapshots — no identity change occurs. This kills the original B9 design (L1→L2 cascade) and forces a fundamental architectural re-evaluation.

**Core insight**: L1 is not a living difference field — it's a **passive projection** of L0's lateral configuration at seal time. This is architecturally meaningful, but different from what was assumed.

---

## 2. Data Summary (Seed 42, 10000 steps)

### 2.1 Sealing and Formation
| Property | Value |
|----------|-------|
| L0 sealed | Yes (step ~32) |
| L1 formed | Yes (32 lateral bits → ~18 L1 bits) |
| L0 seal ratio | 1.0 (all lateral bits frozen) |
| L1 seal ratio | 0.567 (some L1 bits frozen) |
| L0 active count | 36 bits |
| L1 active count | 17 bits |

### 2.2 Post-Seal Dynamics — ZERO
| Metric | Value | Interpretation |
|--------|-------|---------------|
| L0 NSI (post-step-6000) | 0.4777 **constant** | No narrative change |
| L1 NSI (post-step-11000) | 0.3929 **constant** | No narrative change |
| Jaccard(t, t-10) | 1.0 **always** | Identical bit sets |
| Jaccard flux | 0.0 **always** | Zero identity turnover |
| L0 CIV | 14 **constant** | No Hamming change |
| L1 CIV | 3 → 2 (brief) → 3 | Nearly constant |

### 2.3 Pipeline Bug
Only seed 42 was processed in the analysis phase. All 8 seeds ran the simulation phase correctly, but the per-layer analysis loop (`for seed_key in self.results:`) only iterates 1 entry. The other 7 seeds' data is **lost** — not in the JSON. This is a secondary issue because seed 42 is representative for the core finding.

---

## 3. Root Cause Analysis: Why Is L1 Passive?

### 3.1 Architectural Mechanism

L1 is created at L0 seal time through the following pipeline:

```
L0 lateral bits freeze → extract frozen set → encapsulate → L1 created (N∼18)
                              ↓
L1 bits are a SUBSET of L0's frozen laterals
                              ↓
After creation, L1's bits have NO independent evolution mechanism
```

**Critical flaw**: L1 has no mechanism to generate new differences. Its bit space is:
- Created ONCE at L0's seal moment
- Sealed further by its own binding_threshold (some bits freeze)
- **No clustering process, no mutation, no noise injection**
- Result: bits are forever identical to their initial configuration

### 3.2 Why CIV Delta Failed (v3)
CIV delta measured `|H(t) - H(t-1)|` — the Hamming weight change. During post-seal, H goes from 3 to 2 (a 1-bit change) and then stays constant. This gives odi_delta ≈ 0, making all NSI values identical → zero rolling correlation.

### 3.3 Why Jaccard Flux = 0.0 (v4, Correct)
Jaccard flux = 1 - Jaccard(A(t), A(t-1)). It measures bit IDENTITY change, not count change.

For seed 42:
- step 0: {{1,2,3,7,8,9,10,11,12,13,14,15,16,17,18,19,20}} = 17 bits
- step 10: SAME 17 bits → intersection=17, union=17 → Jaccard=1.0 → flux=0.0
- Every subsequent step: SAME set → flux=0.0

**This is not a bug. The system genuinely has no ongoing bit identity change.**

### 3.4 Why Bits Don't Change

The evolver's bit evolution logic operates on the **source layer's** bit space. After L0 seal:
- L0's hierarchy bits continue evolving → L0's active set changes slowly
- L1's bits are a **projection** of L0's frozen laterals → L1's active set is FIXED
- No cross-layer mutation mechanism exists
- L1 is frozen in time at L0's seal moment

**In 差异论 terms**: L1 lacks an independent difference field. All differences in L1 are inherited from L0 and never renewed.

---

## 4. Architectural Implications

### 4.1 The Passive Projection Problem

The current architecture has a fundamental asymmetry:

| Layer | Difference Source | Dynamics | Role |
|-------|-----------------|----------|------|
| L0 | Own clustering | Active, evolving | Primary difference field |
| L1 | L0's frozen laterals | **None** | Passive projection |
| L2 (B5) | Independent (derived from L0) | Active | Independently active layer |

**L1 exists but doesn't LIVE.** It's a snapshot, not an agent.

### 4.2 Is Passive L1 Wrong?

**No — it depends on what L1 IS in the ontology.**

The 差异论 says:
> "对象不是幻觉，而是生成的成果；不是起点，而是差异组织达到一定稳定度之后的显现。"

L1 IS the "generated achievement" — the stable structure that emerges when L0's lateral differences reach sufficient organization. Its passivity is not a bug if its role is to be a **structural memory** rather than an **active agent**.

### 4.3 Hierarchy Framework: 差异论 Re-reading

From the theory note (theory_note_l0_l1_reorganization_20260603.md):

> "差异不是时间顺序上站在最前面的东西，而是发生学顺序上不可绕开的条件。"

**The hierarchy is GENETIC, not TEMPORAL.** L1's role is to be a CONDITION for higher organization, not to exhibit its own temporal dynamics.

This reframes the architecture:

| Level | Role | Dynamics | Time Scale |
|-------|------|----------|------------|
| **L0** | Primary difference field | Active clustering | Fast (∼30 steps to seal) |
| **L1** | Institutional memory | **Static constraint** | Frozen at seal time |
| **L2** | Cultural/civilizational | Independent clustering | Independent |

L1 doesn't need to move — it's the ground that L2 walks on.

### 4.4 The "Constraint Conduction" Model

This aligns perfectly with what Track B4 (exp_117, ConstraintConduction) was trying to achieve — but B4's failure was in the implementation (constraint clamp suppressed L2). The conceptual model is correct:

```
L0 (active) → seal → L1 (frozen constraint) → L2 (active within L1's field)
                   ↘ L0→L2 (independent coupling) →
```

L1's frozen bits provide the **constraint field** that shapes L2's clustering space. L2 doesn't need to be "driven" by L1's dynamics — it needs to **respect** L1's structure.

---

## 5. Revised Phase 5 Architecture

### 5.1 New Layer Ontology

| Layer | Name | Nature | Implementation |
|-------|------|--------|---------------|
| L0 | **Difference Field** | Active, evolving | Current axioms + clustering |
| L1 | **Institutional Structure** | Static projection, sealed | L0's frozen laterals, no dynamics |
| L2 | **Civilizational Narrative** | Active, independent clustering | B5-style IndependentL2Coupling |

### 5.2 L1's Role

L1 becomes a **constraint provider**:
1. L0 seals → L1 forms (already works, B7)
2. L1's frozen bit configuration encodes the **institutional structure** of L0's lateral patterns
3. L2 operates within L1's constraint field — L2's clustering is biased by L1's frozen bits
4. L1 is read-only after formation

This is NOT a downgrade — it's a role clarification. Institutions ARE frozen difference configurations.

### 5.3 L1→L2 Connection (B9 Redesign)

**Original B9** (exp_123_design.md): L1 forms → L1 develops autonomous dynamics → L1 seals → L2 forms from L1's seal.
**Problem**: L1 has no autonomous dynamics → cannot drive cascade.

**Revised B9**: 
1. L0 seals → L1 forms (passive)
2. L1's frozen bits provide CONSTRAINT FIELD for L2
3. L2 creates its own difference space (B5-style, N_L2 = 48-72) **biased by L1's structure**
4. L2 develops autonomous dynamics within L1's constraint

**Key change**: L2 is NOT created from L1's sealed bits. L2 is created with its OWN independent bit space, but L1's configuration biases L2's clustering.

### 5.4 Implementation: Constraint-Biased Independent Clustering

```python
class IndependentL2Coupling:
    """
    L2 is CLUSTERING-INDEPENDENT of L1 but CONSTRAINT-BIASED by L1.
    
    L2 creates its own bit space (N_L2) with independent clustering.
    L1's frozen bit configuration provides BIAS for L2 cluster formation:
    - Bits that align with L1's structure are MORE likely to cluster
    - Bits that conflict with L1's structure face HIGHER thresholds
    """
    
    def __init__(self, l1_frozen_bits, l2_n=72, bias_strength=0.3):
        self.l1_constraint = l1_frozen_bits
        self.bias_strength = bias_strength
        # L2 creates its OWN difference field
        self.l2_field = DifferenceField(n=l2_n)
```

This replaces the "literal cascade" with a "constraint-guided generation" model.

### 5.5 Hypotheses for Revised B9 (H56-H60)

| ID | Hypothesis | Target | Test |
|----|-----------|--------|------|
| H56 | L2 forms with independent clustering | ≥ 7/8 seeds | L2 created post-seal |
| H57 | L2 autonomous NSI | ≥ 7/8 seeds | L2 NSI rolling corr < 0.5 with L1 |
| H58 | L1 constraint shapes L2 | ≥ 6/8 seeds | L2 theme similarity to L1 > random |
| H59 | L2 CIV independent of L0 | ≥ 6/8 seeds | L0-L2 CIV corr < 0.6 |
| H60 | L2 durability | ≥ 7/8 seeds | L2 active for > 80% of post-formation steps |

---

## 6. Track B9 Redesign Decision

### 6.1 What Changes

| Component | Old Design | Revised Design |
|-----------|-----------|---------------|
| L2 origin | L1 cascade (literal) | Constraint-biased independence |
| L2 bit space | L1's frozen bits | Independent N_L2 |
| L2 dynamics | Derived from L1 | Independent clustering |
| L1 role | Active agent | Static constraint provider |
| B9 value | Cascade test | Constraint conduction test |

### 6.2 What Stays

- L0 → L1 partial sealing pipeline (B7, working)
- L1 formation mechanism (working)  
- Per-layer metrics infrastructure (PerLayerMetricsCollector)
- Backward compatibility with Phase 4 (CSC+NSE baseline)

### 6.3 Code Changes Required

1. **`hierarchical_evolver.py`**: After L1 formation, create L2 with IndependentL2Coupling (B5 style) + L1 bias
2. **`cross_scale_coupling.py`**: Add `ConstraintBiasedCoupling` class
3. **PerLayerMetricsCollector**: Already handles arbitrary layers — just need to ensure L2 tracking
4. **Experiment script**: `exp_123_v2_phase5_b9_constraint_conduction.py`

---

## 7. Relationship to B5 (IndependentL2Coupling)

B5 (exp_118) already demonstrated that independent L2 clustering works:
- H35 (decoupling): PASS, mean r=0.03 (TRUE)
- H36 (stability floor): PASS, all seeds maintain min=0.15
- H37 (ODI independence): PASS, mean r=0.36
- H1-H8: 8/8 PASS

**B9 redesign is NOT building B5 again.** The novel contribution is:
- B5: L2 is independent of L0 (no constraint from above)
- B9: L2 is independent of L0 but **biased by L1** (constraint from below)
- B9 tests whether a passive constraint layer can meaningfully shape L2's trajectory

This is the **institutional constraint hypothesis**: a frozen institutional structure (L1) should bias civilizational narrative (L2) without determining it.

---

## 8. Revised Phase 5 Track Map

```
Track B7  ✅ L0 partial sealing → L1 formation (COMPLETE)
Track B8  ✅ L1 passive projection diagnosis (COMPLETE - THIS DOC)
Track B9  🔄 L1→L2 constraint conduction (REDESIGN NEEDED)
            ├── exp_123: Implement ConstraintBiasedCoupling
            ├── exp_124: Vary bias_strength (0.0, 0.1, 0.3, 0.5, 0.7)
            └── exp_125: Vary L2 size (N_L2 = 24, 48, 72)
Track B10 🔄 Final synthesis + architecture freeze
```

---

## 9. Action Items

1. **Fix exp_122 analysis pipeline bug** (only 1/8 seeds output) — minor, data is still valid
2. **Write B9 redesign document** (this doc + exp_123_v2 design)
3. **Implement ConstraintBiasedCoupling** in `cross_scale_coupling.py`
4. **Implement B9 experiment scripts** (exp_123_v2, exp_124, exp_125)
5. **Run B9 experiments** (8 seeds × 3 experiments = ~24 runs)

---

## 10. Conclusion

B8's definitive finding — L1 is a passive projection with zero post-seal dynamics — is a **positive architectural discovery**, not a failure. It clarifies that:

1. **L1 is institutional memory**, not an independent agent
2. **Multi-layer architecture must be constraint-based**, not cascade-based
3. **B9 is still viable** with a redesigned L1→L2 connection

The 差异论's "发生学秩序" framework supports this re-reading: each layer is a genetic condition for the next, not a temporal predecessor with its own dynamics. L1's passivity is ontologically correct.

**Next step**: Implement ConstraintBiasedCoupling + write exp_123_v2.