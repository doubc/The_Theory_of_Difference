# Phase 8: Cross-Scale Spiral Coupling Design

## 1. Motivation

Phase 7 (exp_136) proved the R→P feedback path is real (H82: 8/8 seeds, mean rewriting delta 0.09–0.15),
but exposed a structural gap: **L1 has no cycle tracking infrastructure** (H84: 0/8 seeds, all L1 arrays empty).

The NRC operates only at the system level (CSC `level_states` representing L0). The `per_layer_metrics.py`
module tracks L1 NSI/CIV/Theme time series but has no concept of "cycle detection" or "cycle events."
Meanwhile, L1 is the institutional memory layer — its narrative dynamics, if coupled with L0's generative
cycles, would realize the full V1.7 spiral across scales.

**Phase 8 closes this gap by making L1 a first-class participant in the recursive cycle architecture.**

---

## 2. Theory Foundation

### 2.1 V1.7 §6 — 象界咬合 (Phenomenal Interlocking)

> "不同层次的差异应有时序上的相关性。制度层的结构变化应与文明层的叙事转折相关联。"

Phase 7 H84 failed because there was no mechanism to *measure* or *create* this interlocking.
L0 and L1 were operating on independent clocks — L0 driven by generative narrative events (NRC),
L1 driven only by bit-space evolution through CSC level_states.

The solution is not to make L1 a copy of L0, but to **design explicit coupling mechanisms** that
align their cycle timing while preserving L1's institutional character.

### 2.2 The Dual-Track Spiral

```
        ┌──────────────────────────────────────────┐
        │          R0/R1/R2 (System-Level)         │
        │  L0: Generative Narrative Cycles         │
        │        ↓  ↓  ↓  ↓  ↓                    │
        │  E→M→S→R→Rewrite (NRC Pipeline)          │
        └──────────────────────────────────────────┘
                          │
                L0 Rewrite Energy │ L1 Cycle Bias
                          ▼
        ┌──────────────────────────────────────────┐
        │          L1 Cycle Detector               │
        │  L1: Institutional Memory Cycles         │
        │        ↓  ↓  ↓  ↓  ↓                    │
        │  NSI/Stability/Theme → Cycle Events      │
        │        ↓  ↓  ↓  ↓  ↓                    │
        │  L1 Events → Modulate L0 Compression     │
        └──────────────────────────────────────────┘
```

**Principle**: L0 and L1 run independent cycle detectors, but their outputs are bidirectionally
coupled — L0 rewrite energy biases L1 stability; L1 cycle events modulate L0 event compression.

---

## 3. Architecture: Two New Components

### 3.1 Component A: LCylDet — Lightweight L1 Cycle Detector

**File**: `engine/l1_cycle_detector.py` (new module ~250 lines)

**Purpose**: Detect cycle events in L1 time series without a full NRC instance.

**Inputs** (from `PerLayerMetricsCollector` at each step):
- L1 NSI time series (from PerLayerNSITracker)
- L1 CIV time series (from PerLayerCIVTracker)
- L1 Theme Jaccard series (from PerLayerThemeTracker)
- L1 stability (from LayerNarrativeTracker if available)

**Cycle Detection Algorithm** (three signals → three cycle types):

| Signal | Cycle Type | Detection Rule |
|---|---|---|
| L1 NSI | **Institutional Reconfiguration** | NSI drops > 30% from running max, then recovers > 50% within N=50 steps |
| L1 CIV | **Resource Reshuffle** | CIV changes by ≥ 3 bits in ≤ 20 steps (indicating cluster shift) |
| L1 Theme Jaccard | **Identity Shift** | Jaccard(A(t), A(t-50)) < 0.6 (theme composition changed significantly) |

Each detected cycle produces a `CycleEvent` with:
- `step`: the step at which the cycle is detected (at recovery confirmation)
- `type`: `'reconfiguration'|'reshuffle'|'identity_shift'`
- `magnitude`: 0.0–1.0 based on the severity (drop depth, bit delta, or Jaccard distance)
- `state_before`: snapshot of L1 state before the drop
- `state_after`: snapshot of L1 state after recovery

**Window management**: Rolling window of 200 steps; events older than 200 steps discarded.

**Tuning parameters**:
- `nsi_drop_threshold`: 0.30 (30% drop from running max)
- `nsi_recovery_threshold`: 0.50 (50% of pre-drop level)
- `nsi_recovery_window`: 50 (steps to look for recovery)
- `civ_delta_threshold`: 3 (bits)
- `civ_delta_window`: 20 (steps)
- `theme_jaccard_threshold`: 0.6 (minimum similarity across 50-step gap)

### 3.2 Component B: BiCouple — Bidirectional Coupling Mediator

**File**: `engine/bi_directional_couple.py` (new module ~300 lines)

**Purpose**: Bridge L0 NRC output ↔ L1 cycle events.

**Two coupling directions**:

#### Direction A: L0→L1 (Top-Down Biasing)
When NRC produces a RewrittenSpace (after R1/R2 events), the rewritten `level_transition_weights`
and `stability_basin_width` modulate L1 stability. Specifically:

```
L1_stability_modulation = α * rewrite_energy + β * r2_trigger_bonus
```

where:
- `rewrite_energy` = mean absolute change in level_transition_weights (0.0–0.2 typical)
- `r2_trigger_bonus` = 0.15 if R2 triggered, else 0.0
- `α = 0.3`, `β = 0.2` (tunable)

This modulation is injected into CSC level_states at the next CSC.step() call, affecting L1 clustering
dynamics. It creates a **tendency** for L1 to reorganize following L0 cycles — not a deterministic
copy, but a biased likelihood.

#### Direction B: L1→L0 (Bottom-Up Modulation)
When LCylDet detects an L1 cycle event, it modulates the NRC's EventCompressor:

```
NRC_event_threshold_modulation = γ * l1_event_magnitude
```

where:
- `l1_event_magnitude` = magnitude of the most recent L1 cycle event (0.0–1.0)
- `γ = 0.2` (tunable)
- The modulation is applied as a temporary reduction to `EventCompressor.event_threshold`
  (making it easier to generate NRC events when L1 is active)

This creates a **sensitivity window**: when the institutional layer is going through change,
the generative narrative layer becomes more responsive to tension accumulation.

#### Gradual Coupling Schedule

| Phase 8 Sub-phase | L0→L1 coupling | L1→L0 coupling | Purpose |
|---|---|---|---|
| P0 | Off | Off | Baseline: does L1 alone produce cycles? |
| P1 | On | Off | Does L0 rewriting bias L1 timing? |
| P2 | On | On | Full bidirectional coupling |
| P3 | Sweep α,β,γ | Sweep α,β,γ | Optimal coupling strength |

---

## 4. Hypotheses

| Hyp | Description | Success Criterion |
|---|---|---|
| **H86** | LCylDet detects L1 cycles | ≥6/8 seeds with ≥2 L1 cycle events in 5000 steps |
| **H87** | L0↔L1 cycle timing correlation | ≥4/8 seeds with Jaccard(L0_cycle_times, L1_cycle_times, ε=50) > 0.3 |
| **H88** | NSI improvement > Phase 7 | Mean NSI ≥ 0.56 (+0.03 over Phase 7's 0.53) |
| **H89** | Coupling preserves H1-H8 | ≥6/8 seeds pass all baseline hypotheses |
| **H90** | Bidirectional > Unidirectional | P2 (bidirectional) Jaccard > P1 (L0→L1 only) by ≥0.1 |

---

## 5. Experiment Plan

### Sub-phase P0: L1 Cycle Baseline (exp_137)

**Purpose**: Before adding coupling, does L1 produce detectable cycle patterns at all?

**Config**: Phase 7 baseline (N0=72, CSC+NSE+NRC+Booster, tension=1.0) + LCylDet (monitor only,
no feedback to NRC).

**Runs**: 8 seeds × 5000 steps

**Minimal new code**: Only need `engine/l1_cycle_detector.py`. No coupling mediator yet.

**Expected outcome**: If H86 passes without coupling, L1 has intrinsic cycle dynamics
(institutional restructuring independent of L0 narrative). If H86 fails, L1 is purely
passive even at the cycle level — coupling is essential.

### Sub-phase P1: L0→L1 Biasing (exp_138)

**Add**: BiCouple Direction A (L0 rewrite → L1 stability modulation).

**Requires**: `engine/bi_directional_couple.py` + integration in `engine/hierarchical_evolver.py`

**Runs**: 8 seeds × 5000 steps

**Expected outcome**: H87 ≥4/8, or H87 < H86 pass count (coupling disrupts L1's natural
patterns). Either is informative.

### Sub-phase P2: Full Bidirectional Coupling (exp_139)

**Add**: BiCouple Direction B (L1 cycle → NRC event threshold modulation).

**Runs**: 8 seeds × 5000 steps

**Expected outcome**: H87 should improve vs P1; H88 should improve as L1 events amplify
NRC sensitivity at the right moments.

### Sub-phase P3: Parameter Sweep (exp_140)

**Config**: 3 coupling strengths × 8 seeds × 3000 steps = 24 runs

Coupling strengths to sweep:
- `α=0.15, β=0.10, γ=0.10` (weak coupling)
- `α=0.30, β=0.20, γ=0.20` (moderate — P2 baseline)
- `α=0.50, β=0.35, γ=0.35` (strong coupling)

**Goal**: Find optimal coupling that maximizes H87 (cross-scale Jaccard) without degrading
H89 (baseline H1-H8).

---

## 6. Success Criteria

| Level | Criteria | Action |
|---|---|---|
| ✅ Full PASS | 5/5 H86-H90 pass | → Phase 9 |
| ⚠️ Partial | 3-4/5 pass | → Phase 9 with H86-H90 refinements |
| ❌ Fail | 0-2/5 pass | → Architectural redesign for Phase 8 |

---

## 7. Theory-to-Simulation Mapping

| V1.7 § | Concept | Phase 8 Component |
|---|---|---|
| §6.1 象界咬合 | 各层时序相关性 | BiCouple bidirectional coupling |
| §6.2 耦合功能化 | 约束在层间双向传导 | Direction A: L0 rewrite → L1 stability |
| §6.3 层间递归 | 高层扰动影响低层压缩阈值 | Direction B: L1 event → L0 threshold modulation |
| §1.2 P = R(S(M(E(P)))) | 螺旋完整性 | L0 NRC pipeline (existing) + L1 cycle detector (new) |
| §2.3 叙事中介 | 差异从分散→共同行动 | L1 events create NRC sensitivity windows |
| §5.4 限缩公约 | 系统稳定性 | H89 guard (H1-H8 preservation) |
| §7 生成式世界模型 | 完整生成机制 | Cross-scale spiral = fully integrated world model |

---

## 8. Implementation Order

```
1. engine/l1_cycle_detector.py        ← NEW (250 lines)
2. engine/bi_directional_couple.py     ← NEW (300 lines)
3. engine/hierarchical_evolver.py      ← MODIFY: add BiCouple calls
4. experiments/exp_137_phase8_p0.py    ← NEW (P0: L1 baseline)
5. experiments/exp_138_phase8_p1.py    ← NEW (P1: L0→L1 only)
6. experiments/exp_139_phase8_p2.py    ← NEW (P2: bidirectional)
7. experiments/exp_140_phase8_p3.py    ← NEW (P3: parameter sweep)
```

---

*Design document v1.0 — 2026-06-04 19:16*
*Author: Heartbeat action — Phase 8 design after Phase 7 completion*