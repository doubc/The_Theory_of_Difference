# Experiment Report: Phase 3 Experiment 3 — MSI Growth Curve

## Info

- **Time**: 20260528_092113
- **Elapsed**: 56.59s
- **Total runs**: 12 (4 configs × 3 runs)
- **Overall**: ❌ FAIL

## Configurations

- **A_baseline**: Baseline: all mode, threshold=0.30, N72
- **B_majority**: Majority mode, threshold=0.15, N72
- **C_weighted**: Weighted mode, threshold=0.30, N72 — exp_68 best
- **D_weighted_long**: Weighted mode, threshold=0.30, N72, 500 steps

## Cross-Configuration Results

| Config | ODI max | MSI max | MSI growth | Conv% | Ant-ODI r | CF active |
|---|---|---|---|---|---|---|
| A_baseline | 0.8610±0.0119 | 0.0000±0.0000 | +0.0000±0.0000 | 10.0% | -0.1862 | 0.0% |
| B_majority | 0.8490±0.0077 | 0.0000±0.0000 | +0.0000±0.0000 | 6.1% | 0.1849 | 0.0% |
| C_weighted | 0.8757±0.0227 | 0.0000±0.0000 | +0.0000±0.0000 | 12.2% | 0.0134 | 0.0% |
| D_weighted_long | 0.8463±0.0534 | 0.0000±0.0000 | +0.0000±0.0000 | 13.3% | -0.0458 | 0.0% |

## Acceptance Criteria

- **C1_MSI_above_03_in_2plus_configs**: ❌ FAIL
- **C2_MSI_positive_growth_in_2plus_configs**: ❌ FAIL
- **C3_ant_odi_corr_above_03_in_1plus_config**: ❌ FAIL
- **C4_counterfactual_activates_at_least_once**: ❌ FAIL

**Overall**: ❌ FAIL (0/4)

## Per-Run Details

### A_baseline

| Run | ODI max | MSI max | MSI growth | Conv% | Ant-ODI r | CF | Samples |
|---|---|---|---|---|---|---|---|
| 1 | 0.8446 | 0.0000 | +0.0000 | 11.7% | -0.7993 | N | 60 |
| 2 | 0.8724 | 0.0000 | +0.0000 | 13.3% | 0.4461 | N | 60 |
| 3 | 0.8661 | 0.0000 | +0.0000 | 5.0% | -0.2053 | N | 60 |

### B_majority

| Run | ODI max | MSI max | MSI growth | Conv% | Ant-ODI r | CF | Samples |
|---|---|---|---|---|---|---|---|
| 1 | 0.8412 | 0.0000 | +0.0000 | 3.3% | -0.2074 | N | 60 |
| 2 | 0.8595 | 0.0000 | +0.0000 | 8.3% | 0.3617 | N | 60 |
| 3 | 0.8463 | 0.0000 | +0.0000 | 6.7% | 0.4003 | N | 60 |

### C_weighted

| Run | ODI max | MSI max | MSI growth | Conv% | Ant-ODI r | CF | Samples |
|---|---|---|---|---|---|---|---|
| 1 | 0.9038 | 0.0000 | +0.0000 | 18.3% | -0.1366 | N | 60 |
| 2 | 0.8752 | 0.0000 | +0.0000 | 16.7% | -0.3330 | N | 60 |
| 3 | 0.8481 | 0.0000 | +0.0000 | 1.7% | 0.5098 | N | 60 |

### D_weighted_long

| Run | ODI max | MSI max | MSI growth | Conv% | Ant-ODI r | CF | Samples |
|---|---|---|---|---|---|---|---|
| 1 | 0.7813 | 0.0000 | +0.0000 | 1.0% | 0.0245 | N | 100 |
| 2 | 0.9120 | 0.0000 | +0.0000 | 19.0% | -0.4125 | N | 100 |
| 3 | 0.8455 | 0.0000 | +0.0000 | 20.0% | 0.2505 | N | 100 |

## Theoretical Mapping

1. **MSI growth after ODI > 0.5** ↔ 象界前主体态 → 最小自我涌现
2. **Anticipation-ODI correlation** ↔ 结构密度 → 预期能力正反馈
3. **Counterfactual activation** ↔ 复制+筛选联合扩展 → 反事实推理
4. **MSI sub-indices** (asymmetry/history/self-ref) ↔ 三条件检测器

## Next Steps

- If MSI growth is positive: investigate the growth rate and saturation level
- If CF never activates: investigate ODI threshold for CF activation
- If Ant-ODI correlation is low: investigate anticipation gating mechanism
- exp_71: 功能信号耦合原型（P2 from architecture redesign）
- exp_72: 分层耦合（P3 from architecture redesign）


---
*Auto-generated at 20260528_092113*
