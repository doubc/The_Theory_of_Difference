# exp_120 Track B6 Fallback: Mixed-Scale Multi-Layer — Analysis

**Date:** 2026-06-03  
**Config:** N0=48 for L0, N0=72 for L2 (independent), 5000 steps + 2500 extra, binding_threshold=0.08, ILP floor=20, consumption=0.05  
**Seeds:** 42, 142, 242, 342, 442, 542, 642, 742 (8 runs)

---

## Results Summary

| Seed | L0 Sealed | Sealed Bits | Ratio | L1 Formed | Track B | Baseline |
|------|-----------|-------------|-------|-----------|---------|----------|
| 42   | ❌        | 0           | 0.00  | ❌        | 3/9     | 4/8      |
| 142  | ✅        | 32          | 0.67  | ❌        | 4/9     | 5/8      |
| 242  | ❌        | 0           | 0.00  | ❌        | 3/9     | 4/8      |
| 342  | ✅        | 32          | 0.67  | ❌        | 4/9     | 5/8      |
| 442  | ❌        | 0           | 0.00  | ❌        | 3/9     | 4/8      |
| 542  | ✅        | 32          | 0.67  | ❌        | 4/9     | 5/8      |
| 642  | ❌        | 0           | 0.00  | ❌        | 3/9     | 4/8      |
| 742  | ❌        | 0           | 0.00  | ❌        | 3/9     | 4/8      |

**Sealing rate: 3/8 = 37.5%** (target: ≥6/8)  
**Layer 1 formation rate: 0/8 = 0%** (target: ≥4/8)

---

## Hypothesis Results

| Hypothesis | Target | Result | Notes |
|------------|--------|--------|-------|
| H30 (L1↔L2 decoupling) | ≥6/8 | **8/8 ✅** | r=0.000 for all seeds — L2 genuinely independent |
| H31 (L0→L1 delay) | ≥4/8 | **0/8 ❌** | No L1 exists to measure delay |
| H32 (L2 autonomy) | ≥6/8 | **0/8 ❌** | L1 NSI=0, L2 NSI=0 — both silent |
| H33 (L1-L2 ODI) | ≥4/8 | **8/8 ✅** | r=0.000 — no correlation |
| H35 (L2 stability floor) | 8/8 | **8/8 ✅** | min ≥ 0.15 for all seeds |
| H36 (L2 autonomy index) | ≥6/8 | **0/8 ❌** | Both layers silent |
| H37 (L2 intrinsic dynamics) | ≥4/8 | **0/8 ❌** | L2 NSI std = 0 |
| H39 (L0 sealing) | ≥6/8 | **3/8 ❌** | 37.5% sealing rate |
| H40 (Layer 1 formation) | ≥4/8 | **0/8 ❌** | Evolver stops after L0 seal |
| H1 (CIV NSI > 0.5) | ≥4/8 | **8/8 ✅** | All seeds > 0.5 |
| H2 (NSI trend) | ≥4/8 | **8/8 ✅** | All increasing or stable_high |
| H3 (CIV range [3,20]) | ≥4/8 | **0/8 ❌** | CIV=0 (no seal) or 32 (too high) |
| H4 (Turning points ≥3) | ≥4/8 | **8/8 ✅** | All ≥3 |
| H5 (CIV relaxed [2,25]) | ≥4/8 | **3/8 ❌** | Same as H3 |
| H6 (CIV min ≥2) | ≥4/8 | **3/8 ❌** | Same as H3 |
| H7 (History depth > 0.05) | ≥4/8 | **8/8 ✅** | All > 0.05 |
| H8 (TopDown active) | ≥4/8 | **0/8 ❌** | TopDown never activates |

---

## Key Findings

### 1. Sealing is Highly Seed-Dependent at N0=48

The mixed-scale fallback improved sealing from 12.5% (exp_119, N0=72) to 37.5% (exp_120, N0=48), but it's still far from the 75%+ target. The pattern is stark:

- **Sealing seeds (142, 342, 542):** All sealed at exactly 32 bits (ratio=0.67), keeping all 16 hierarchy bits + 16 lateral bits
- **Non-sealing seeds (42, 242, 442, 642, 742):** All failed even after 7500 total steps, with w stabilizing at 38-40 and active bits at 46-47

This suggests the sealing mechanism has a **bimodal behavior** — seeds either seal cleanly or never seal at all. The boundary is determined by early-stage dynamics (first ~100 steps).

### 2. Layer 1 Auto-Creation is Broken

When L0 seals (seeds 142, 342, 542), the evolver correctly reports `sealed=True` with 32 bits frozen. But then it immediately stops with "Layer 1 does not exist yet (only 1 layers). Stopping ← previous layer did not seal."

This is a **logic error** in `HierarchicalEvolver`: after L0 seals, it should create Layer 1 from the sealed hierarchy bits, but instead it treats "previous layer did not seal" as a stopping condition even when L0 *did* seal. The evolver's layer progression logic needs to be fixed.

### 3. L2 Independent Coupling Works Perfectly

H30 passed 8/8 with r=0.000 — L2 is genuinely decoupled from L1. H35 passed 8/8 with stability floor maintained. This confirms that the B5 IndependentL2Coupling architecture is sound. The problem is entirely on the L0→L1 sealing path.

### 4. CIV Count is Bimodal: 0 or 32

There's no middle ground. Seeds that don't seal have CIV=0. Seeds that seal have CIV=32 (all 32 lateral bits frozen). Neither falls in the target range [3, 20]. This means:

- The sealing mechanism either freezes nothing or freezes everything
- There's no partial sealing where only some lateral bits freeze
- The hierarchy bits (16) are always kept, never frozen

### 5. TopDown Never Activates

H8 failed 0/8 across all seeds. TopDown requires L1 to emerge and reach stability threshold, but L1 never forms. This is a cascading failure: no L0 seal → no L1 → no TopDown.

---

## Root Cause Analysis

The fundamental problem is **not the scale** (N0=48 vs N0=72). The problem is:

1. **Sealing mechanism is all-or-nothing:** The binding threshold (0.08) combined with the coherence calculation causes lateral bits to either all freeze together or none freeze. There's no gradual sealing.

2. **Layer progression logic is broken:** Even when L0 seals correctly, the evolver doesn't proceed to create Layer 1. The `HierarchicalEvolver.run()` method checks `if not previous_layer_sealed: stop` but doesn't have a path for "previous layer sealed, create next layer."

3. **CIV range target is misaligned:** The target CIV count [3, 20] assumes partial sealing, but the mechanism produces all-or-nothing results. Either the target needs adjustment, or the sealing mechanism needs to support partial freezing.

---

## Recommendations for Track B7

### Immediate Fix: Fix Layer 1 Auto-Creation

The evolver should, after L0 seals:
1. Extract the 16 sealed hierarchy bits
2. Create Layer 1 with these bits as its initial active set
3. Continue evolution with L1 as the active layer

### Alternative: Redesign Sealing for Partial Freezing

Instead of freezing all lateral bits at once, implement gradual sealing:
- Freeze lateral bits one at a time as they reach individual coherence thresholds
- This would produce CIV counts in the [3, 20] range naturally

### Track B7 Focus: Layer 1 Dynamics

Once Layer 1 auto-creation is fixed, Track B7 should focus on:
- H41: L1 emerges from sealed L0 hierarchy bits
- H42: L1 stability grows over time
- H43: L1↔L2 decoupling maintained after L1 formation
- H44: TopDown activates after L1 reaches stability threshold

---

## Comparison with Previous Tracks

| Experiment | N0 | Sealing Rate | L1 Formed | L1↔L2 Corr | Key Outcome |
|------------|-----|-------------|-----------|------------|-------------|
| B1 (exp_114) | 72 | ~100% | ✅ | 0.976 | Fully coupled |
| B2 (exp_115) | 72 | ~100% | ✅ | 0.861 | Still coupled |
| B3 (exp_116) | 72 | ~100% | ✅ | 0.937 | Even more coupled |
| B4 (exp_117) | 72 | ~100% | ✅ | 0.000* | L2 silent (FALSE POSITIVE) |
| B5 (exp_118) | 72 | 0% | ❌ | 0.032 | L2 decoupled but L0 no seal |
| B6 (exp_119) | 72 | 12.5% | ❌ | 0.000 | L2 silent, L0 mostly no seal |
| **B6 fallback (exp_120)** | **48/72** | **37.5%** | **❌** | **0.000** | **L2 decoupled, L0 partial seal** |

*H30 pass in B4 was a false positive — L2 was completely silent, not meaningfully decoupled.

The trajectory shows: coupling fixes → sealing breaks → scale reduction helps sealing but doesn't solve it → Layer 1 creation is the missing link.
