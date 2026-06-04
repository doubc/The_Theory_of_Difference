# Phase 6 P3 Design — NRC R2 Activation Investigation

> 2026-06-04 | 承接 exp_129 (Phase 6 P2)

## 问题陈述

exp_129 (8 seeds × 2000 steps, N0=48, CSC+NSE+NRC+Booster) 结果：

| Hypothesis | Result | Detail |
|---|---|---|
| H60 (R0 micro) | ✅ 8/8 PASS | sig_ratio=1.000 |
| H61 (R1 institutional) | ✅ 8/8 PASS | corr=1.000 |
| H62 (R2 civilizational) | ❌ 0/8 | total R2=0 |
| H63 (spiral convergence) | ❌ 1/8 | 仅种子142收敛 |
| H64 (spiral completeness) | ❌ 1/8 | mean=2.00 cycles/1k |

**核心问题**: R0 和 R1 完全正常，但 R2（文明级递归重写）完全 dormant。螺旋收敛极其罕见。

## 根因分析

### 1. R2 触发条件过于严格
R2 需要 civilizational-scale crisis — 即大量 CIVILIZATION-level 叙事事件积累到阈值。但在当前配置下：
- N0=48 的差异场规模有限
- 2000 步不足以积累足够的 CIV 事件
- NarrativeLevelBooster 人为抬高了 CIV 基线，可能掩盖了自然的 CIV 演化轨迹

### 2. 系统处于 slow drift 而非 convergence
exp_129 发现系统不是朝向固定点收敛，而是在缓慢漂移。这意味着：
- 螺旋收敛不是自然吸引子
- 需要更强的约束或更长的时间尺度

### 3. NRC 与 Booster 的交互
Booster 强制提升 CIV 计数，但这可能：
- 让系统"跳过"自然的 CIV 积累过程
- 导致 R2 的触发条件（基于真实 CIV 事件）无法被满足

## P3 方案

### 方案 A: Booster-free Baseline @ 5000 steps（推荐，首选）

**设计**:
- 移除 NarrativeLevelBooster
- 运行 5000 步（2.5× exp_129 时长）
- N0=48 保持不变
- 观察 R2 是否自然激活

**假设**:
- H62a: 移除 Booster 后，CIV 自然演化轨迹更真实，R2 可能仍不激活（确认需要更大规模/更长时间）
- H63a: 5000 步可能观察到初步收敛迹象
- H64a: 螺旋周期频率可能提升

**实验配置**:
```
seeds: 8
steps: 5000
N0: 48
stack: CSC + NSE + NRC (no Booster)
```

### 方案 B: N0=72 扩展测试

**设计**:
- 保持 Booster，N0=72
- 更大的差异场 → 更多 CIVILIZATION 级事件
- 2000 步

**假设**:
- H62b: N0=72 产生更多 CIV 事件，R2 激活率提升

### 方案 C: R2 阈值调优

**设计**:
- 降低 `min_civilizational_events` 触发门槛
- 从当前值（需查证）降至更低的阈值
- 观察 R2 激活后的质量

**风险**: 可能产生"虚假" R2 事件（质量不足）

## 执行顺序

```
P3-A (booster-free 5000 steps) → 确认 R2 是否需要更大规模
  ↓ 若 R2 仍不激活
P3-B (N0=72) → 测试规模效应
  ↓ 若 R2 激活但质量低
P3-C (阈值调优) → 精细调优 R2 触发条件
```

## 预期产出

1. exp_130 实验脚本: `experiments/exp_130_phase6_p3_booster_free_5000.py`
2. 实验结果 JSON
3. 分析报告: `docs/exp_130_phase6_p3_analysis.md`
4. Phase 6 阶段性结论（R2 的激活条件）

## 理论映射

差异论 §1.2 螺旋公式 `P_{t+1} = R(S(M(E(P_t))))` 中，R2 对应"框架重组层"。如果 R2 无法激活，意味着：
- 当前系统只能产生微观和制度级递归
- 文明级框架重组需要更长的时间尺度或更大的差异场
- 这与差异论中"框架重组是稀有事件"的论断一致

---

*设计完成待执行 | 2026-06-04*
