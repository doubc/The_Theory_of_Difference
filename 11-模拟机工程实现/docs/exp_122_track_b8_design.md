# Phase 5 Track B8: L1 Autonomous Dynamics — Design Document

## Overview

**Track**: Phase 5 Track B8 — L1 Autonomous Dynamics  
**Predecessor**: Track B7 (exp_121) — A9 sealing fix, 8/8 sealing rate, L1 formation 100%  
**Core Question**: After L0 seals and L1 forms, does L1 develop its own autonomous narrative dynamics, or is it merely a coarser echo of L0?

## Theoretical Motivation

From《差异论》:
- **差异先行本体论**: 每个层级应有独立的差异场和叙事轨迹
- **对象是差异关系的凝聚态**: L1 的凝聚态（从 L0 封装而来）不应完全继承 L0 的差异结构，而应在自身尺度上重新组织差异
- **持留是路径依赖的递归**: L1 一旦形成，其自身的演化路径应产生与 L0 不同的历史依赖

**关键假设**: L1 不是 L0 的"缩小版"，而是一个新的差异场。它应该：
1. 发展出自己的叙事连续性（NSI）轨迹
2. 有自己的稳定性波动模式
3. 可能最终也会封口并生成 L2

## Hypotheses

### H46: L1 NSI Autonomy
**Target**: After L0 sealing, L1 NSI trajectory diverges from L0 NSI trajectory
**Metric**: After seal step, compute rolling correlation (window=200) between L0 NSI and L1 NSI
**Pass**: Mean rolling correlation < 0.5 for ≥ 6/8 seeds
**Rationale**: If L1 is autonomous, its narrative self should not track L0's narrative self

### H47: L1 CIV-like Dynamics
**Target**: L1 develops its own "CIV" (active bit count) dynamics independent of L0
**Metric**: After seal, compute correlation between L0 hamming_weight and L1 hamming_weight
**Pass**: Mean correlation < 0.6 for ≥ 5/8 seeds
**Rationale**: L1's activity pattern should not mirror L0's

### H48: L1 Sealing Potential
**Target**: At least some seeds show L1 approaching its own sealing threshold
**Metric**: Track L1's `total_unique_active` / `sealing_threshold` ratio over time
**Pass**: ≥ 3/8 seeds reach ratio > 0.8 (approaching seal) within 5000 post-seal steps
**Rationale**: If L1 is a genuine layer, it should be capable of its own sealing

### H49: L1 Narrative Theme Divergence
**Target**: L1 narrative themes diverge from L0 narrative themes after sealing
**Metric**: Jaccard similarity between L0 and L1 active theme sets, computed in sliding windows
**Pass**: Mean post-seal Jaccard < 0.4 for ≥ 5/8 seeds
**Rationale**: Different layers should organize different functional themes

## Experimental Design

### Configuration
- **N0**: 48 (proven sealing scale from B7)
- **Steps**: 10000 (5000 pre-seal + ~5000 post-seal, since seal happens at ~30 steps)
- **Seeds**: 8 (42, 142, 242, 342, 442, 542, 642, 742)
- **Binding threshold**: 0.05
- **ILP floor**: 15
- **CSC**: Enabled (L0→L1 coupling for initial formation, then monitor decoupling)
- **NSE**: Enabled on both L0 and L1
- **LNT**: Enhanced to track L0 and L1 independently with post-seal divergence metrics

### Key Modifications from B7

1. **Extended run length**: 10000 steps (vs 5000 in B7) to capture post-seal L1 dynamics
2. **Dual-layer NSE**: Run NarrativeSelfEmergence on both L0 and L1 independently
3. **Enhanced LNT**: Add post-seal divergence tracking (H46, H49 metrics)
4. **L1 sealing monitor**: Track L1's sealing progress (H48 metric)
5. **Hamming weight tracking**: Log both L0 and L1 hamming weights at each step (H47 metric)

### Metrics to Log Per Step
- L0: state, hamming_weight, active_bits, NSI, narrative_themes
- L1: state, hamming_weight, active_bits, NSI, narrative_themes (after L1 formation)
- L0→L1: rolling NSI correlation, rolling hamming correlation, theme Jaccard
- L1 sealing progress: unique_active / threshold ratio

## Expected Outcomes

| Scenario | H46 | H47 | H48 | H49 | Interpretation |
|----------|-----|-----|-----|-----|----------------|
| L1 fully autonomous | PASS | PASS | Maybe | PASS | L1 is a genuine new layer |
| L1 partially autonomous | PASS | FAIL | Maybe | PASS | L1 has narrative independence but activity coupling |
| L1 is L0 echo | FAIL | FAIL | No | FAIL | L1 is just a coarser L0 |
| L1 silent/stagnant | N/A | N/A | No | N/A | L1 forms but doesn't evolve |

## Files to Create/Modify

1. `experiments/exp_122_phase5_b8_l1_autonomous_dynamics.py` — new experiment script
2. `engine/layer_narrative_tracker.py` — add post-seal divergence tracking
3. `docs/exp_122_track_b8_design.md` — this design document (moved to docs after creation)

## Relation to Future Tracks

- **Track B9**: If H48 passes (L1 sealing), test L1→L2 sealing
- **Track B9**: If H48 fails, investigate why L1 can't seal (scale? dynamics?)
- **Track C1**: Multi-layer cascade (L0→L1→L2→L3) if sealing propagates
