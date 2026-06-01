#!/usr/bin/env python3
"""Write Phase 4 P2 plan document."""
import os

content = r"""# Phase 4 P2 Plan: Extended Validation

> **Date**: 2026-06-02
> **Status**: Draft
> **Precondition**: Phase 4 P0+P1 complete (exp_107, 8/8 ALL PASS)

## 1. Objectives

Phase 4 P2 extends validation beyond the baseline H1-H8 hypotheses with two tracks:

- **Track A: Ablation Study** — Systematically remove each Phase 4 component to measure individual contribution
- **Track B: Scaling Test** — Vary N0 to test if hypotheses hold across system sizes

## 2. Phase 4 Components Under Test

| Component | Role | Phase | If Removed |
|----------|------|-------|------------|
| AMC (AdaptiveMomentumController) | Dynamic momentum adjustment | P0 | CIV instability (over/under) |
| ILP (InstitutionalLayerProtector) | Protect INSTITUTIONAL accumulation | P0 | INSTITUTIONAL over-consumption |
| CSC (CrossScaleCoupling) | Bidirectional cross-layer causality | P1 | No TopDown, no CSCI |
| NSE (NarrativeSelfEmergence) | Narrative self-index computation | P1 | No NSI, no history depth |

## 3. Track A: Ablation Study (exp_108)

### 3.1 Configurations

Each config removes exactly ONE Phase 4 component from the full exp_107 baseline:

| Config | AMC | ILP | CSC | NSE | Expected Impact |
|--------|-----|-----|-----|-----|----------------|
| A0 (baseline) | ON | ON | ON | ON | All pass (replicate exp_107) |
| A1 (no AMC) | OFF | ON | ON | ON | CIV instability, H5/H6 fail |
| A2 (no ILP) | ON | OFF | ON | ON | INSTITUTIONAL depletion, H8 fail |
| A3 (no CSC) | ON | ON | OFF | ON | No TopDown, H8 fail |
| A4 (no NSE) | ON | ON | ON | OFF | No NSI, H1-H4 fail |

### 3.2 Method

- 4 seeds (subset of 8 for speed): [42, 142, 242, 742]
- N0=72, steps=1600
- Evaluate H1-H8 for each config
- Identify which component is most critical for each hypothesis

### 3.3 New Hypotheses

- **H9 (AMC criticality)**: Removing AMC causes H5 or H6 to fail (CIV instability)
- **H10 (ILP criticality)**: Removing ILP causes H8 to fail (TopDown loss)
- **H11 (CSC criticality)**: Removing CSC causes H8 to fail (TopDown loss)
- **H12 (NSE sufficiency)**: Removing NSE does NOT cause H5/H6 to fail (NSE is diagnostic, not generative)

## 4. Track B: Scaling Test (exp_109)

### 4.1 Configurations

| Config | N0 | Steps | Seeds | Purpose |
|--------|----|-------|-------|---------|
| B1 (small) | 48 | 1600 | [42, 142, 742] | Test lower bound |
| B0 (baseline) | 72 | 1600 | [42, 142, 742] | Replicate exp_107 subset |
| B2 (large) | 96 | 1600 | [42, 142, 742] | Test upper bound |

### 4.2 New Hypotheses

- **H13 (scale robustness)**: H1-H8 all pass at N0=48 and N0=96
- **H14 (NSI scales with N0)**: NSI mean increases with N0 (larger systems = richer narrative self)
- **H15 (CIV scales with N0)**: CIV count scales sub-linearly with N0 (diminishing returns)

## 5. Execution Order

1. exp_108 A0 (baseline replication, 4 seeds) — verify exp_107 results
2. exp_108 A1-A4 (ablation configs) — measure component contributions
3. exp_109 B0-B2 (scaling configs) — test cross-scale robustness
4. Analysis + P2 report

## 6. Expected Outcomes

### Most Likely
- A1 (no AMC): H5/H6 fail — AMC is critical for CIV stability
- A4 (no NSE): H1-H4 fail — NSE generates NSI signals
- A2/A3 (no ILP/CSC): H8 partially degraded — TopDown weakened
- B1/B2: All pass at small scale, possible degradation at large scale

### Implications
- If A1 causes H5/H6 fail → AMC is the keystone component for Phase 4
- If A4 causes H1-H4 fail but H5-H8 pass → NSE is diagnostic (not generative)
- If B2 degrades → system has optimal scale range (not infinitely scalable)
"""

output_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'docs', 'phase4_p2_plan.md'
)
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"Written to {output_path}")
