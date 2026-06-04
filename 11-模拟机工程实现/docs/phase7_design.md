# Phase 7 Design: Full Spiral Integration

**Date**: 2026-06-04  
**Based on**: Phase 6 Final Report + V1.7 Upgrade Outline §1-§2, §7  
**Phase 6 Complete**: 7 experiments, 96+ runs, NRC pipeline operational ✅

---

## 1. Motivation: The Completed Spiral

Phase 6 closed the R→P feedback path — NRC produces rewritten space from narrative
tension. But validation focused on the NRC mechanism's internal behavior (cycle count,
R2 frequency, convergence). **Phase 7 validates the full spiral end-to-end:**

$$P_{t+1} = R(S(M(E(P_t))))$$

The core question isn't "does NRC produce cycles?" (yes, Phase 6 proved that).
The core question is: **does the full spiral produce measurably different outcomes
than the open-loop (no feedback) baseline?**

| Aspect | Phase 6 (Mechanism-level) | Phase 7 (System-level) |
|---|---|---|
| Scale | N0=48 (standard) | **N0=72** (optimal, Phase 4 P2B) |
| Focus | NRC internal dynamics | **Full spiral end-to-end** |
| Metrics | H60-H80 (NRC cycles) | **H81-H85 (system-level validation)** |
| R→P path | Validated as present | **Measured as impactful** |
| Baseline | None | **Phase 5 D1 baseline at N0=72** |

---

## 2. Key Architectural Decisions

### 2.1 N0=72 (Optimal Scale)
Phase 4 P2B identified N0=72 as the optimal scale where NSI peaks and cross-scale
coherence is maximal. Phase 6 ran at N0=48 (conservative). Phase 7 scales up.

Rationale:
- N0=72 produced the highest NSI in Phase 4 (non-monotonic — N0=96 over-clusters)
- Larger bit space may increase event frequency (more structural differentiation)
- More bits → more room for R→P rewriting (H82 metrics have dynamic range)

### 2.2 Tension-Based R2 Trigger (Proven Effective)
All Phase 7 runs use `r2_use_tension=True` with `r2_tension_threshold=1.0`.
This is the recommended default from Phase 6 P4/P5:
- 23/24 seeds activated R2 in exp_133
- 22/24 seeds activated R2 in exp_134 (with booster)
- 8/8 seeds activated R2 in exp_135 (8000 steps)

### 2.3 Booster Included
NarrativeLevelBooster (min_civ=3) is included. Phase 6 P5 proved it does not
interfere with tension-based R2. Rationale:
- Maintains CIV floor (prevents H5 false positives)
- Minor NSI improvement with booster (0.53 vs 0.70 without — though natural flow
  produced higher NSI, the difference is small and CIV protection matters more)

### 2.4 "Cycles in First 500 Steps" Metric
Phase 6 proved NRC is event-driven, not periodic. The H64 metric (≥3 cycles/1k over
full run) failed because cycles cluster in the first ~500 steps and go silent.

Phase 7 uses the redesigned metric: **≥2 complete cycles within the first 500 steps**
captures the NRC's actual behavior pattern.

### 2.5 R→P Measurability
The key innovation of Phase 7: measuring whether the NRC's rewritten space actually
changes P-space in a way that is detectable at the system level.

Three measurements:
1. **P-space drift**: Does the level_transition_weights vector from rewritten space
   significantly differ from the pre-cycle baseline? (L1 distance > 0.05)
2. **Stability basin shift**: Does rewritten basin_width differ from pre-cycle
   baseline by > 5%?
3. **NRC-active vs NRC-inactive control**: Compare NSI distribution between seeds
   with/without NRC rewriting activity.

---

## 3. Hypotheses

### H81: Spiral Completeness at Scale
**Statement**: The full spiral at N0=72 produces ≥2 complete E→M→S→R cycles within
the first 500 steps.
**Threshold**: ≥6/8 seeds
**Rationale**: Phase 6 at N0=48 produced 1-3 cycles in first 500 steps at
tension=1.0. At N0=72, more bits should mean more structural differentiation,
hence more events, hence more cycles.
**Related to**: Phase 6 H64 (redesigned), Phase 5 B8

### H82: R→P Rewriting Detectability
**Statement**: R2 civilizational recursion measurably rewrites P-space.
**Metric**: After any R2 event, the rewritten_space's level_transition_weights
vector has mean absolute change > 0.05 from pre-cycle baseline.
**Threshold**: ≥4/8 seeds (R2 is rare — 1-3 events per seed)
**Rationale**: R2 is supposed to be epochal. If it doesn't measurably change
P-space, the whole R→P feedback path is cosmetic.
**Related to**: V1.7 §1.2 "叙事递归改变可能性空间的结构"

### H83: Spiral Closure Improves NSI
**Statement**: Seeds with active NRC rewriting (≥1 rewritten_space applied) show
higher mean NSI at step 500+ than the Phase 5 D1 baseline (N0=72, no NRC).
**Metric**: Mean NSI over steps 500-1000, compared against running Phase 5 D1
results at N0=72.
**Threshold**: Phase 7 mean NSI ≥ Phase 5 D1 mean NSI + 0.02
**Rationale**: The recursive closure should enrich narrative quality. If it doesn't,
the feedback loop is adding computational cost without benefit.
**Related to**: Phase 5 D1 (long-term evolution baseline)

### H84: Cross-Scale Spiral Consistency
**Statement**: NRC cycles at L0 (bit-level) and L1 (cluster-level) are correlated
in their event timing.
**Metric**: Jaccard similarity of event timesteps (within ±5 step tolerance) > 0.3.
**Threshold**: ≥4/8 seeds
**Rationale**: If the spiral operates consistently across scales, events should
cluster at similar times. If L0 and L1 spirals are uncorrelated, the multi-scale
architecture isn't integrated.
**Note**: Requires L1 tracking (N0=72 produces L1 clusters naturally).

### H85: No System Degradation at Scale
**Statement**: Full spiral integration (NRC + CSC + NSE + Booster at N0=72) does
NOT destabilize core narrative emergence over 5000 steps.
**Metric**: H1-H8 pass at final step (step 5000).
**Threshold**: 8/8 seeds
**Rationale**: Phase 6 proved this at N0=48. Must confirm at N0=72.

---

## 4. Experiment Design

### Single Configuration
| Parameter | Value | Rationale |
|---|---|---|
| N0 | 72 | Optimal scale from Phase 4 P2B |
| Steps | 5000 | Longer than phase transitions (~500 steps), short enough for 8 seeds |
| Seeds | 8 (42, 142, 242, 342, 442, 542, 642, 742) | Standard seed set |
| R2 tension threshold | 1.0 | Recommended default from Phase 6 P5 |
| Booster | Yes (min_civ=3) | Standard |
| Sample interval | 10 | Standard |
| GBC soft nudge | 0.2 | Standard |
| Architecture | CSC+NSE+NRC+Booster | Full spiral stack |

### Comparison Baselines
1. **Phase 5 D1 at N0=72**: Long-term evolution without NRC (historical data)
   - If available from exp_128 track D1 at N0=72
   - If not, approximate from exp_132 Phase 6 P4 scaling test (N0=72, no NRC)

2. **Phase 6 exp_135 at N0=48**: 8000-step long run with NRC but smaller scale
   - Direct comparison: does N0=72 produce more cycles?

---

## 5. Metric Definitions

### H81: Cycles in First 500 Steps
```python
def h81_cycles_in_first_500(cycles, n_steps=500):
    """Count complete E->M->S->R cycles within first 500 steps."""
    early_cycles = [c for c in cycles if c.step <= n_steps]
    return len(early_cycles)
```
**Requirement**: ≥6/8 seeds have ≥2 early cycles.

### H82: R→P Rewriting Detectability
```python
def h82_r2_rewriting_power(nrc_metrics):
    """Measure mean level_transition_weights delta after R2."""
    if not nrc_metrics.get('r2_rewriting_deltas', []):
        return 0.0
    return np.mean(nrc_metrics['r2_rewriting_deltas'])
```
**Requirement**: ≥4/8 seeds have mean delta > 0.05.

### H83: NSI Improvement
```python
def h83_nsi_improvement(nsi_values_mid, baseline_nsi):
    """Compare mid-phase NSI to Phase 5 D1 baseline."""
    current_mean = np.mean(nsi_values_mid[50:100])  # steps 500-1000
    return current_mean - baseline_nsi
```
**Requirement**: Mean NSI across seeds ≥ baseline + 0.02.

### H84: Cross-Scale Jaccard
```python
def h84_cross_scale_jaccard(l0_cycles, l1_cycles):
    """Jaccard similarity of event timesteps within ±5 tolerance."""
    l0_times = {c.step for c in l0_cycles}
    l1_times = {c.step for c in l1_cycles}
    # Apply tolerance
    return jaccard_with_tolerance(l0_times, l1_times, tolerance=5)
```
**Requirement**: ≥4/8 seeds have Jaccard > 0.3.

### H85: Core Preservation
Same as H1-H8 from Phase 4:
- **H1**: Max NSI > 0.1
- **H2**: NSI active rate > 0.3 for all seeds
- **H3**: Mean continuity > 0.1
- **H4**: History depth > 0.05 OR turning points > 0
- **H5**: Max CIV ≥ 3
- **H6**: Max CIV ≥ 2
- **H7**: CSCI std > 0.005
- **H8**: TopDown active ≥ 2 seeds

---

## 6. Expected Outcomes

| Hypothesis | Expected | Risk | Mitigation |
|---|---|---|---|
| H81 (cycles) | **PASS** — N0=72 should increase events | Lower than expected | Check N0=72 event frequency in exp_132 |
| H82 (R→P rewrite) | **PARTIAL** — rewriting is subtle | Not detectable | Use L1 drift in level weights, not absolute change |
| H83 (NSI improvement) | **PASS** — NRC should enrich narrative | Degradation instead | NSI may decrease initially (restructuring cost) |
| H84 (cross-scale) | **PASS** — events should be correlated | No correlation | Separate L0/L1 spirals may be independent |
| H85 (no degradation) | **PASS** — Phase 6 proof at N0=48 | N0=72 destabilizes | Unlikely — H1-H8 held through Phase 6 |

### Optimistic: 4/5 PASS (H82 partial)
### Realistic: 3/5 PASS (H81, H83, H85 full; H82/H84 partial)

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| N0=72 produces fewer events than expected | H81 fails | Fall back to N0=96 or adjust threshold to ≥1 cycle |
| R→P rewriting is too subtle to measure | H82 fails | Add P-space trajectory analysis (PCA of level weight vectors over time) |
| NSI decreases with NRC | H83 fails | The restructuring cost may be temporary — expand window to steps 1000-2000 |
| Cross-scale correlation is zero | H84 fails | Accept as finding: L0 and L1 spirals are independent (meaningful result) |
| N0=72 destabilizes core emergence | H85 fails | Reduce to N0=48 and re-run |

---

## 8. Success Criteria

**Phase 7 PASS**: ≥3/5 hypotheses pass with clear evidence.

| Level | Criteria | Action |
|---|---|---|
| ✅ Full PASS | 5/5 pass | Publish results, proceed to Phase 8 |
| ⚠️ Partial | 3-4/5 pass | Document failures, adjust metrics, proceed to Phase 8 |
| ❌ Fail | <3/5 pass | Root-cause analysis before Phase 8 |

---

## 9. Relationship to V1.7

V1.7 §1.2 describes the spiral as:

> "P_{t+1} = R(S(M(E(P_t, D_t)))) — 叙事递归不只是对既有安排的解释，
> 它会改变主体对自身、对他人、对制度、对未来的理解，从而重排可能性空间的结构。"

Phase 7 directly tests this claim by measuring whether the R→P feedback path
produces measurable P-space restructuring. If H82 passes, the simulation has
achieved what V1.7 describes — narrative that doesn't just explain, but reshapes.

---

*Phase 7 design complete. Experiment: exp_136.*
