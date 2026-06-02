# exp_118 Track B5: 独立 L2 聚簇 + 稳定性地板 (Independent L2 Clustering + Stability Floor)

**Date:** 2026-06-02  
**Parent:** exp_117 (Track B4)  
**Status:** Design — Implementation in progress

---

## 问题回顾：Track B4 的失败

| 指标 | B4 结果 | 问题 |
|---|---|---|
| H30 (L1↔L2 r) | 0.0000, 8/8 PASS | **假阳性** — L1和L2都silent，零方差→零相关 |
| H31 (L0→L1延迟) | 0/8 | L1 silent，无法检测 |
| H32 (L2自主性) | 0/8 | L2被clamp到近零 |
| H33 (L2 ODI独立) | 0/8 | L2无独立ODI |
| H34 (响应延迟) | 0/8 | L1稳定在近零，无变化事件 |

**根因分析：**

1. **L2没有独立聚簇**：当前`ConstraintConduction`接收的`l2_autonomous_state`是全局（共享）ODI，不是L2自己的聚簇结果。L2只是L0聚簇的一个"映射"，没有独立的差异场。

2. **约束clamp过于激进**：当L1稳定性低（~0）时，约束边界`[L1*(1-tol), L1*(1+tol)]`坍缩到近零，L2被强制压到零。

3. **L1也silent**：叙事标签没有正确传播到LNT，导致INSTITUTIONAL层叙事活动无法被检测到。

---

## Track B5 设计

### 核心转变：从"约束传导"到"独立聚簇+软约束"

```
┌─────────────────────────────────────────────────────────────┐
│                     Track B5 Architecture                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   L0 (MINI)                    L0 (MINI)                    │
│   ┌─────────┐                  ┌─────────┐                  │
│   │ Clustering│                │ Clustering│                │
│   │  N0=72   │                │  N0=72   │                  │
│   └────┬────┘                  └────┬────┘                  │
│        │                            │                         │
│   ┌────┴────┐                  ┌────┴────┐                  │
│   │ L1 Inst │                  │ L2 Civ  │ ← 独立聚簇！     │
│   │ N0=72   │                  │ N0=72   │   自己的ODI      │
│   └────┬────┘                  └────┬────┘                  │
│        │                            │                         │
│        │    ┌──────────────┐        │                       │
│        └───►│ Stability    │◄───────┘                       │
│             │ Floor (0.15) │                                │
│             └──────┬───────┘                                │
│                    │                                         │
│             ┌──────┴───────┐                                │
│             │ Soft Constraint│ ← L1提供软边界，非硬clamp    │
│             │ (additive偏置) │   不改变L2的聚簇结果          │
│             └──────┬───────┘                                │
│                    │                                         │
│             ┌──────┴───────┐                                │
│             │  L2 Final    │                                │
│             │  Stability   │                                │
│             └──────────────┘                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 三个关键修改

#### 1. L2 独立聚簇

L2不再依赖全局共享状态，而是：
- 从L0的结构向量中**独立聚簇**（使用相同的N0=72，但独立的随机种子）
- 计算**独立的ODI**（基于L2自己的聚簇中心间差异）
- 产生**独立的稳定性评分**

```python
# L2独立聚簇伪代码
l2_clusters = cluster(l0_structural_vectors, N0=l2_N0, seed=l2_seed)
l2_odi = compute_odi(l2_clusters.centers)
l2_stability = compute_stability(l2_clusters, l2_structural_vectors)
```

#### 2. 稳定性地板 (Stability Floor)

防止L2被clamp到近零。即使L1稳定性很低，L2也有最小活动水平。

```python
STABILITY_FLOOR = 0.15  # L2最小稳定性

# 软约束：additive偏置，而非clamp
constraint_bias = (l1_stability - l2_stability) * constraint_strength
l2_final_stability = clip(l2_stability + constraint_bias, STABILITY_FLOOR, 1.0)
```

**关键区别：** B4使用`clip(l2_base, lower_bound, upper_bound)`（硬clamp），B5使用`l2_base + bias`（软偏置）+ floor。

#### 3. L2 内在动力学

L2有自己的扰动和衰减机制：
- 每步以概率`perturbation_rate`对结构向量施加随机扰动
- 稳定性自动衰减（模拟文明自然耗散）
- 但这些不影响L2的聚簇结果（聚簇是周期性的，不是每步的）

### 假设

| ID | 假设 | 判定标准 |
|---|---|---|
| H30 | L1↔L2 decoupled | Pearson r < 0.7, ≥5/8 seeds |
| H31 | L0→L1有延迟 | ≥4/8 seeds检测到延迟 ≥5步 |
| H32 | L2有自主性 | ≥5/8 seeds, autonomy_index > 0.3 |
| H33 | L2 ODI独立 | ≥5/8 seeds, L2 ODI与L0 ODI corr < 0.8 |
| H34 | L1→L2响应延迟 | ≥4/8 seeds, delay > 5步 |
| H1-H8 | 基线假设 | ≥6/8 seeds全部通过 |

### 与B4的关键差异

| 维度 | B4 (Constraint Conduction) | B5 (Independent Clustering) |
|---|---|---|
| L2来源 | 全局共享ODI + L1 clamp | L2独立聚簇L0向量 |
| 约束方式 | hard clamp `[L1*(1-tol), L1*(1+tol)]` | soft additive bias + floor |
| 稳定性地板 | 无 | 0.15 |
| L2 ODI | 全局ODI | 独立计算 |
| L1 silent? | 是 | 预期改善（L0→L1信号增强） |

---

## 实现计划

1. **`engine/cross_scale_coupling.py`**: 修改`ConstraintConduction`为`IndependentL2Coupling`
   - 添加L2独立聚簇逻辑（简化版：基于L0向量的子空间聚簇）
   - 将hard clamp改为soft bias + floor
   - 添加L2内在动力学

2. **`experiments/exp_118_phase5_b5_independent_l2.py`**: 实验脚本
   - 8 seeds × 2000 steps
   - 记录L0/L1/L2的ODI、稳定性、叙事标签
   - 计算H30-H34指标

3. **`engine/layer_narrative_tracker.py`**: 修复L1叙事标签传播
   - 确保INSTITUTIONAL层叙事标签正确传递到LNT

---

## 理论依据

- 差异论 §2.2: "层级不是信息的逐级传递，而是差异在不同尺度上的重新组织"
- 差异论 §2.3: "制度是文明的约束，但不是文明的决定者"
- 《象界》: 文明层级有自己的"象"，不是制度的放大版

---

## 预期风险

1. **L2聚簇计算开销**：独立聚簇可能增加计算成本
   - 缓解：使用简化聚簇（k-means with fixed N0，不每步运行）

2. **L1仍然silent**：如果L0→L1信号不够强
   - 缓解：增加`l0_to_l1_signal_weight`，降低`l1_autonomous_stability_weight`

3. **H30假阳性再次出现**：如果L2活动仍然太低
   - 缓解：降低stability floor，增加L2内在扰动
