# exp_175 Results Analysis — Small-world Network (Phase 16 Path B3)

**Date**: 2026-06-09 01:23 CST
**Experiment ID**: exp_175
**Files**: `experiments/results/exp_175_results_20260609_*.json` (6 files)

---

## Hypothesis

**H16-B3**: Small-world network (Watts-Strogatz rewiring) enables L1 structure to reflect L0's global features.

### Mechanism
Replace the regular 1D ring lattice topology with a Watts-Strogatz small-world network. Each edge is rewired with probability `p`, creating a spectrum from regular lattice (p=0) → small-world (p~0.1-0.3) → random network (p=1.0).

### Configs
- p = 0.0 (baseline/regular lattice), 0.1, 0.3, 0.5, 0.7, 0.9 (near-random)
- N=48, L0_steps=3000, L1_steps=2000, sample_interval=25
- N=5 trials per config = 30 total

---

## Results Summary

| Config | p | L0 Seal | L0 HW Final | L0 Clusters | L1 Seal | L1 HW Final | Reflection (mean±std) | Struct Entropy |
|--------|---|---------|-------------|-------------|---------|-------------|----------------------|----------------|
| p00_baseline | 0.0 | 100% | 21.8±1.9 | 4.4±0.9 | 100% | 21.2±1.9 | 0.537±0.252 | 0.000±0.000 |
| p01_weak | 0.1 | 100% | 24.6±3.4 | 4.6±0.5 | 100% | 26.6±2.2 | 0.724±0.188 | 0.000±0.000 |
| p03_medium | 0.3 | 100% | 21.2±3.3 | 4.8±0.8 | 100% | 22.2±2.8 | 0.734±0.228 | 0.000±0.000 |
| p05_strong | 0.5 | 100% | 26.4±6.7 | 5.0±1.0 | 100% | 26.8±5.0 | 0.696±0.286 | 0.000±0.000 |
| p07_stronger | 0.7 | 100% | 23.2±4.7 | 4.8±0.8 | 100% | 23.0±5.8 | 0.514±0.309 | 0.000±0.000 |
| p09_random | 0.9 | 100% | 18.0±5.1 | 4.6±0.5 | 100% | 20.2±4.1 | 0.689±0.302 | 0.000±0.000 |

---

## Analysis

### 1. No Monotonic Trend

The reflection score does NOT follow a monotonic trend with increasing p:
- p=0.0 → 0.537 (baseline)
- p=0.1 → 0.724 (↑)
- p=0.3 → 0.734 (↑, peak)
- p=0.5 → 0.696 (↓)
- p=0.7 → 0.514 (↓, below baseline)
- p=0.9 → 0.689 (↑)

This flat/noisy pattern contrasts sharply with exp_174 (global field), where reflection increased monotonically from 0.738 to **1.000** with alpha.

### 2. High Trial-to-trial Variance

Reflection standard deviations range 0.188-0.309 — very high relative to the mean (0.514-0.734). This indicates:
- Small-world rewiring creates unpredictable structural outcomes
- No config reliably improves reflection
- Any apparent improvement at p=0.1-0.3 is within noise

### 3. Structure Entropy: All Zero

Structure entropy = 0.000 for ALL configs. This is identical to baseline (p=0.0). In stark contrast, exp_174 showed structure entropy reducing monotonically from 0.733 to **0.011** with global field strength.

### 4. Sealing: 100% Unaffected

All configs maintain 100% L0 and L1 seal rates. Small-world topology does not disrupt sealing — consistent with all Phase 16 experiments.

### 5. No Dose-response Relationship

| Metric | Trend with p |
|--------|-------------|
| L0 HW final | Flat (18.0-26.4), no trend |
| L1 HW final | Flat (20.2-26.8), no trend |
| L0 clusters | Flat (4.4-5.0), no trend |
| L0 seal step | Flat (11.8-24.6), no trend |
| L1 seal step | Flat (8.4-25.8), no trend |

---

## Comparison with exp_173 (Long-range Connections)

Both exp_173 and exp_175 involve topological modification:

| Aspect | exp_173 (Long-range) | exp_175 (Small-world) |
|--------|---------------------|----------------------|
| Mechanism | Add K random edges | Rewire edges with prob p |
| Reflection range | — | 0.514-0.734 (no trend) |
| Trend | None | None |
| Conclusion | H16-B1 REJECTED | H16-B3 REJECTED |

**Combined insight**: Modifying the network topology — whether by adding random edges or rewiring existing ones — does NOT systematically improve L1 structure reflection. This contrasts with exp_174 (global field), where a system-wide collective bias modifies the "dead order".

---

## Comparison with exp_174 (Global Field)

| Aspect | exp_174 (Global Field) | exp_175 (Small-world) |
|--------|----------------------|----------------------|
| Mechanism | System-wide collective bias | Topology modification |
| Max reflection | **1.000±0.000** (alpha=0.9) | 0.734±0.228 (p=0.3) |
| Monotonic trend | ✅ Yes | ❌ No |
| Structure entropy reduction | ✅ 0.733 → 0.011 | ❌ All 0.000 |
| Conclusion | ✅ CONFIRMED | ❌ REJECTED |

---

## Conclusions

❌ **H16-B3 REJECTED**: Small-world network does NOT systematically improve L1 structure reflection of L0's global features.

### Evidence
1. **No monotonic trend**: Reflection fluctuates 0.514-0.734 with no clear relationship to p
2. **High variance**: Standard deviations (0.188-0.309) swamp any apparent mean differences
3. **No structure entropy reduction**: All configs = 0.000, identical to baseline
4. **No dose-response**: None of the 5 metrics show a trend with p

### Theoretical Implications

1. **Topology modification ≠ structure propagation** — Changing the graph structure does not automatically make L1 "see" L0's structure. Information still flows through discrete edges, just in a slightly different configuration.

2. **Global field remains the only effective method** — Among all Phase 16 approaches (open system, energy flow, long-range connections, global field, small-world), ONLY the global field (Path B2) has produced a systematic improvement in L1 structure reflection.

3. **The mechanism matters**: Global field is system-wide and uniform — it creates a shared context that all bits sense simultaneously. This contrasts with topology changes which are still pair-wise and discrete, even when non-local.

---

## Phase 16 Path B Overall Status

| Path | Experiment | H# | Status | Result |
|------|-----------|-----|--------|--------|
| B1 | exp_173 (Long-range) | H16-B1 | ✅ COMPLETE | ❌ REJECTED |
| B2 | exp_174 (Global Field) | H16-B2 | ✅ COMPLETE | ✅ CONFIRMED |
| B3 | exp_175 (Small-world) | H16-B3 | ✅ COMPLETE | ❌ REJECTED |

**Path B Summary**: 1/3 hypotheses confirmed (B2-global field). Global field is the only Phase 16 approach that systematically improves reflection.
