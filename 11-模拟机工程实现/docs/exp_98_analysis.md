# exp_98 Analysis: Full Integration (AMC + ILP + CSC + GBC + NSE)

**Date**: 2026-06-01 18:25
**Experiment**: exp_98_full_integration
**Commit**: 00b6552 (AMC+ILP integration) + bugfix (layer→constraints)
**Result**: 5/6 pass — H5 fails (CIV explosion persists)

## Purpose

Validate whether AMC (AdaptiveMomentumController) and ILP (InstitutionalLayerProtector)
can stabilize the CIV positive feedback loop observed in exp_97. exp_97 Run 2 showed
CIV=186 in seed 342; the hypothesis is that AMC dampens CIV acceleration and ILP
protects INSTITUTIONAL layer from premature consumption.

## Configuration

- Same base as exp_97: N0=72, steps=1600, 8 seeds
- CSC: ON (exp_95 stable config)
- GBC: ON (random direction init, soft nudge=0.2)
- NSE: ON (multi-signal turning point detection)
- **AMC: ON** (adaptive momentum control)
- **ILP: ON** (institutional layer protection)

## Per-Seed Results

| Seed | NSI_max | Continuity | Hist_depth | Turn_pts | CIV | Sealed | AMC_bonus | ILP_level |
|------|---------|------------|------------|----------|-----|--------|-----------|-----------|
| 42   | 0.8088  | 0.7546     | 0.40       | 20       | 15  | Yes    | 0.4853    | strong    |
| 142  | 0.7458  | 0.7711     | 0.16       | 8        | 9   | Yes    | 0.4851    | strong    |
| 242  | 0.7086  | 0.6489     | 0.04       | 2        | 5   | Yes    | 0.4862    | strong    |
| 342  | 0.7184  | 0.6515     | 0.08       | 4        | 8   | Yes    | 0.4854    | strong    |
| 442  | 0.7206  | 0.7702     | 0.08       | 4        | 10  | **No** | 0.4855    | strong    |
| 542  | 0.8230  | 0.7546     | 0.44       | 22       | **184** | **No** | 0.4852 | strong    |
| 642  | 0.7510  | 0.7543     | 0.20       | 10       | **182** | **No** | 0.4858 | strong    |
| 742  | 0.7390  | 0.7610     | 0.16       | 8        | 9   | **No** | 0.4856 | strong    |

## Hypothesis Evaluation

| Hypothesis | Criterion | Result | Verdict |
|------------|-----------|--------|---------|
| H1: NSI max > 0.1 | max = 0.823 | All seeds strong | ✅ PASS |
| H2: NSI active rate > 0.3 | mean = 0.869 | Nearly always active | ✅ PASS |
| H3: Continuity mean > 0.1 | mean = 0.733 | Strong continuity | ✅ PASS |
| H4: History depth > 0.05 OR tp > 0 | depth=0.074, tp=9.8 | Both pass | ✅ PASS |
| H5: CIV mean ∈ [3, 15] | mean = 52.75 | **Explosion** | ❌ FAIL |
| H6: min CIV ≥ 3 | min = 5 | No collapse | ✅ PASS |

**Overall: 5/6 pass — H5 fails due to CIV explosion in seeds 542 and 642.**

## Critical Finding: AMC Is Not Activating

The most striking observation is that **AMC momentum bonus is ~0.485 across ALL 8 seeds**,
regardless of whether CIV is exploding (CIV=184) or stable (CIV=5). This indicates the
AMC is not responding to CIV acceleration at all.

### AMC Behavior Analysis

| Metric | Value | Interpretation |
|--------|-------|----------------|
| AMC_bonus range | 0.4851 – 0.4862 | Nearly constant |
| AMC_bonus std | 0.0004 | Essentially zero variance |
| ILP level | all "strong" | ILP always in strong protection |
| ILP transition | varies | But doesn't prevent CIV explosion |

The AMC momentum bonus should vary in response to CIV acceleration. The fact that it
stays at ~0.485 (near the default 0.5 maximum) means the AMC's adaptive logic is
**not triggering any dampening action** despite CIV counts reaching 184.

### Root Cause: AMC Signal Path Is Disconnected

The AMC receives `category_heats`, `institutional_count`, and `civilization_count` as inputs.
However, the AMC's internal logic may not be correctly detecting CIV acceleration because:

1. **CIV count is sampled at `sample_interval=10`**: The AMC sees CIV counts at steps 0, 10, 20, ...
   but the CIV explosion may happen between samples or the rate of change may be below
   the AMC's acceleration threshold.

2. **AMC acceleration threshold may be too high**: If the AMC requires a certain rate of
   CIV increase per step to trigger dampening, but the CIV increase is gradual (e.g., +1
   per sample interval), it may never exceed the threshold.

3. **AMC only adjusts momentum_bonus**: Even if AMC detects the problem, adjusting
   momentum_bonus from 0.5 to 0.48 is a 4% change — far too small to disrupt a positive
   feedback loop that produces CIV=184.

4. **The CIV positive feedback loop is in the narrative turning point detection, not in
   the momentum**: AMC controls momentum_bonus, but the CIV explosion is driven by the
   multi-signal turning point detector (NSE) creating more history → more CIV → more
   turning points. AMC doesn't directly control NSE.

## The CIV Explosion Pattern: Sealed vs Non-Sealed

| Seed | Sealed | CIV | TP  | Interpretation |
|------|--------|-----|-----|----------------|
| 42   | Yes    | 15  | 20  | High but bounded (sealed) |
| 142  | Yes    | 9   | 8   | Stable (sealed) |
| 242  | Yes    | 5   | 2   | Low activity (sealed) |
| 342  | Yes    | 8   | 4   | Stable (sealed) |
| 442  | **No** | 10  | 4   | Moderate (not sealed) |
| 542  | **No** | 184 | 22  | **EXPLOSION** (not sealed) |
| 642  | **No** | 182 | 10  | **EXPLOSION** (not sealed) |
| 742  | **No** | 9   | 8   | Stable (not sealed) |

**Key insight**: Sealed seeds (42, 142, 242, 342) all have CIV ≤ 15. Non-sealed seeds
show bimodal behavior: either stable (CIV=9-10) or exploding (CIV=182-184). The sealing
mechanism acts as a natural bound on CIV — when the system seals, the structure freezes
and CIV can't grow unbounded.

This means the CIV explosion is a **non-sealed system phenomenon**. In non-sealed systems,
the持续的流动 allows the NSE-CIV feedback loop to run unchecked.

## Comparison Across Experiments

| Experiment | CSC | GBC | NSE | AMC | ILP | H5 Result | CIV mean |
|------------|-----|-----|-----|-----|-----|-----------|----------|
| exp_95     | ON  | ON  | OFF | OFF | OFF | ✅ PASS   | 6.50     |
| exp_96     | ON  | ON  | ON  | OFF | OFF | ✅ PASS   | 5.88     |
| exp_97 R1  | ON  | ON  | ON* | OFF | OFF | ✅ PASS   | 7.13     |
| exp_97 R2  | ON  | ON  | ON* | OFF | OFF | ❌ FAIL   | 34.5     |
| **exp_98** | ON  | ON  | ON* | **ON** | **ON** | ❌ FAIL | **52.75** |

\* NSE with multi-signal turning point detection

**Trend**: Each successive experiment shows worsening CIV:
- exp_95 (no NSE): 6.50 — baseline
- exp_96 (NSE, single-signal): 5.88 — slightly better (no turning points)
- exp_97 R1 (NSE, multi-signal): 7.13 — slightly worse (some turning points)
- exp_97 R2 (NSE, multi-signal): 34.5 — explosion in one seed
- exp_98 (NSE multi + AMC + ILP): 52.75 — explosion in TWO seeds

**AMC+ILP made things worse, not better.** The CIV explosion is now affecting 2/8 seeds
instead of 1/8.

## Why AMC+ILP Failed

### 1. Wrong Control Point

AMC controls `momentum_bonus` in the narrative recursion operator. But the CIV explosion
is driven by the **NSE turning point detection**, not by narrative momentum. The feedback
loop is:

```
More turning points → more self-history → more narrative activity
→ more CIV events → stronger CIV signal in multi-signal detector
→ more turning points
```

AMC doesn't touch the turning point detection mechanism. It only adjusts how much
"bonus" momentum narratives get — a parameter that has little effect on whether
turning points are detected.

### 2. ILP Doesn't Constrain CIV Directly

ILP protects the INSTITUTIONAL layer from premature consumption. But the CIV explosion
is about CIVILIZATION-level events being counted, not about INSTITUTIONAL layer depletion.
ILP's `consumption_rate_limit` affects how fast INSTITUTIONAL converts to CIVILIZATION,
but once the system is in a positive feedback loop, this limit is either too high or
not applied to the right mechanism.

### 3. The Real Problem: NSE-CIV Coupling

The fundamental issue is that the multi-signal turning point detector includes CIV as
one of its signals (weight 0.2). This creates a direct positive feedback channel:

```python
# In SelfHistoryAccumulator._detect_turning_point():
signals = {
    'msi': msi_second_deriv * 0.4,
    'odi': odi_second_deriv * 0.3,
    'civ': civ_change * 0.2,        # ← THIS is the problem
    'gbc': gbc_change * 0.1,
}
```

When CIV increases, it directly contributes to turning point detection, which creates
more history, which creates more narrative activity, which creates more CIV.

## Recommendations

### Immediate: Remove CIV from Multi-Signal Detection

The CIV weight (0.2) in the turning point detector should be set to 0. This breaks
the direct positive feedback loop at its source:

```python
signals = {
    'msi': msi_second_deriv * 0.4,
    'odi': odi_second_deriv * 0.3,
    'civ': 0.0,  # DISABLED — prevents feedback loop
    'gbc': gbc_change * 0.1,
}
```

This is a one-line change that should immediately stabilize H5.

### Short-Term: AMC Needs to Control NSE Directly

If AMC is meant to prevent CIV explosion, it needs to act on the NSE turning point
detection, not just on narrative momentum. Possible approaches:

1. **AMC modulates the CIV weight** in multi-signal detection: When CIV accelerates,
   AMC reduces the CIV weight toward 0.
2. **AMC adds a turning point cooldown**: After a turning point is detected, enforce
   a minimum interval before the next one.
3. **AMC caps CIV contribution**: Limit the maximum CIV signal that can contribute
   to turning point detection.

### Medium-Term: Redesign the NSE-CIV Boundary

The current design conflates two separate concerns:
- **NSE**: Narrative self-emergence (should be about narrative continuity and history)
- **CIV**: Civilization-level events (should be about structural complexity)

CIV should not be an input to NSE turning point detection. Instead, CIV should be a
**downstream** measure that reflects the structural consequences of narrative activity,
not a **driver** of it.

## Bugfix Note

During this experiment, a bug was found and fixed in `hierarchical_evolver.py` line 1929:
- **Before**: `if hasattr(layer.constraints, 'institutional_categories'):`
- **After**: `if hasattr(constraints, 'institutional_categories'):`

The variable `layer` was not in scope; the correct variable is `constraints` (the 4th
parameter of the callback function).

## Conclusion

exp_98 shows that AMC and ILP, as currently designed, do not solve the CIV explosion
problem. The AMC momentum bonus remains constant (~0.485) across all seeds regardless
of CIV behavior, and ILP's INSTITUTIONAL protection doesn't affect the NSE-CIV feedback
loop.

The root cause is architectural: the multi-signal turning point detector includes CIV
as an input signal, creating a positive feedback loop that AMC and ILP don't touch.
The fix should be at the NSE level — either removing CIV from the turning point
detection signal vector, or having AMC directly modulate the CIV weight.

**Status**: 5/6 pass. H5 requires NSE-level fix, not AMC/ILP-level fix.
