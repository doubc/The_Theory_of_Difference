# exp_117 Track B4: 层间约束传导 (Constraint Conduction)

**Date:** 2026-06-02  
**Parent:** exp_116 (Track B3: L1→L2 Channel Redesign)  
**Status:** Design

---

## B3 失败的根本原因

B3 尝试了三种增强方案（噪声增强 → L2 独立叙事 → L2 稳定性噪声），但 H30/H31/H32 全部失败。根因分析指向一个结构性问题：

> **当前串行耦合是"层间派生"而非"层间耦合"。**

具体表现：
1. L2 的状态（稳定性、叙事活动）完全由 L1 派生，只是加了噪声和衰减
2. L2 没有独立的差异场——它的差异全部来自 L1 的差异
3. L1 和 L2 响应同一个 L0 聚簇动力学，只是幅度和相位不同
4. 噪声只能增加高频方差，不能打破低频结构性相关

**差异论 §2.2 的核心要求：** 每个层级应有独立的"差异场"和独立的动力学。层级间是"耦合"而非"派生"。

---

## B4 设计哲学：从"状态派生"到"约束传导"

### 核心转变

| | 状态派生 (B1-B3) | 约束传导 (B4) |
|---|---|---|
| L2 状态来源 | L2 = f(L1, noise) | L2 = f(L0, L1_constraints, L2_autonomous) |
| L1→L2 关系 | L2 镜像 L1 | L1 约束 L2 的演化边界 |
| L2 自主性 | 噪声注入的伪自主 | 真正的独立差异场 |
| 耦合本质 | 信息传递 | 约束调节 |

### 类比

- **状态派生**：如同影子——影子完全由物体决定，只是模糊了一点
- **约束传导**：如同河流与河床——河床（L1 制度）约束河流（L2 文明）的流向，但河流有自己的水量、流速、泥沙

---

## B4 架构设计

### 1. L2 独立聚簇机制 (Independent L2 Clustering)

**当前问题：** L2 没有自己的聚簇，完全依赖 L1 传递的聚簇信息。

**B4 方案：** L2 直接从 L0 聚簇接收输入，形成自己的独立聚簇结构。

```
L0 聚簇 → L1 制度聚簇 (原有路径)
L0 聚簇 → L2 文明聚簇 (新增路径)
```

**实现细节：**
- L2 有自己的聚簇中心计算：`l2_cluster_centers = f(l0_structural_vectors, l2_N0)`
- `l2_N0` 可以不同于 `l1_N0`，模拟不同层级的聚簇尺度
- L2 聚簇的 ODI 计算独立于 L1

### 2. 约束传导机制 (Constraint Conduction)

**核心思想：** L1 不直接决定 L2 的状态，而是提供**约束信号**，L2 在约束范围内自主演化。

**约束类型：**

| 约束类型 | L1 信号 | L2 响应 | 参数 |
|---|---|---|---|
| 稳定性约束 | L1 制度稳定性 | L2 稳定性上下界 | `constraint_stability_weight` |
| 活动约束 | L1 叙事活动 count | L2 叙事活动阈值 | `constraint_activity_weight` |
| 结构约束 | L1 聚簇结构 | L2 聚簇对齐度 | `constraint_structure_weight` |

**数学形式：**

```python
# L2 的稳定性 = 自主演化 + L0 直接输入 + L1 约束调节
l2_stability_autonomous = evolve(l2_stability_prev, l2_cluster_odi)
l2_stability_from_l0 = f(l0_cluster_stability, l2_N0)
l2_stability_constraint = l1_stability * constraint_weight

# 约束调节：软边界，不是硬派生
l2_stability = (
    l2_stability_autonomous * (1 - constraint_weight) +
    l2_stability_from_l0 * l0_direct_weight +
    l2_stability_constraint * constraint_weight
)

# 约束作为边界而非目标
l2_stability = clamp(
    l2_stability_autonomous,
    l1_stability * (1 - constraint_tolerance),
    l1_stability * (1 + constraint_tolerance)
)
```

### 3. L0→L1 传导增强

**当前问题：** L1 的制度自稳压制了 L0 信号，导致 L0→L1 延迟无法检测。

**B4 方案：**
- 降低 L1 的制度自稳权重（从 ~0.8 降至 ~0.5）
- 增强 L0→L1 的信号权重（从 ~0.2 升至 ~0.5）
- 添加 L1 对 L0 变化的**响应延迟**参数 `l0_to_l1_response_delay`

### 4. L2 叙事活动独立生成

**当前问题：** L2 叙事 count 太低（2-4），无法产生 CIVILIZATION 级叙事。

**B4 方案：**
- L2 叙事活动由 L2 独立聚簇的 ODI 驱动，不依赖 L1
- 提高 L2 叙事递归算子的灵敏度（降低 CIVILIZATION 叙事阈值）
- L2 有自己的叙事活动计数器，独立于 L1

---

## 配置参数

| 参数 | B3 值 | B4 值 | 说明 |
|---|---|---|---|
| `coupling_mode` | serial | **constraint** | 新增模式 |
| `l2_N0` | 继承 L1 | **72 (独立)** | L2 独立聚簇规模 |
| `constraint_stability_weight` | — | **0.2** | L1 稳定性约束权重 |
| `constraint_activity_weight` | — | **0.15** | L1 活动约束权重 |
| `constraint_structure_weight` | — | **0.1** | L1 结构约束权重 |
| `constraint_tolerance` | — | **0.3** | 约束容差（软边界） |
| `l0_direct_to_l2_weight` | — | **0.4** | L0 直接输入 L2 权重 |
| `l0_to_l1_signal_weight` | 0.4 | **0.5** | 增强 L0→L1 |
| `l1_autonomous_stability_weight` | ~0.8 | **0.5** | 降低制度自稳 |
| `l0_to_l1_response_delay` | — | **10** | L0→L1 响应延迟 |
| `l2_narrative_threshold` | 继承 L1 | **0.01** | 降低 L2 叙事阈值 |

---

## 假设更新

### H30 (层间解耦): L1↔L2 NSI 相关性 r < 0.7
- **B3 结果:** 0/8, mean r = 0.937
- **B4 预期:** ≥ 5/8 (62.5%)
- **理论依据:** L2 有独立聚簇 + 约束传导而非状态派生 → L1-L2 相关性应显著降低

### H31 (层级延迟): L0→L1 延迟检测
- **B3 结果:** 0/8 检测到
- **B4 预期:** ≥ 4/8 检测到 L0→L1 延迟
- **理论依据:** L0→L1 信号权重提升 + L1 自稳压制降低 → L0 信号可穿透

### H32 (L2 自主性): L2 叙事与 L1 叙事不一致性 > 0.3
- **B3 结果:** 0/8 (L1/L2 均为 silent)
- **B4 预期:** ≥ 5/8
- **理论依据:** L2 独立聚簇 + 独立叙事生成 → L2 应有非 silent 叙事

### H33 (新增): L2 独立聚簇有效性
- **定义:** L2 聚簇结构与 L1 聚簇结构的差异度（ODI 差异）
- **目标:** L2 ODI 与 L1 ODI 的相关性 < 0.8
- **预期:** ≥ 5/8 通过

### H34 (新增): 约束响应延迟
- **定义:** L2 对 L1 约束变化的响应步数
- **目标:** 平均响应延迟 > 5 步
- **预期:** ≥ 4/8 检测到

---

## 实验配置

- **脚本:** `experiments/exp_117_phase5_b4_constraint_conduction.py`
- **种子:** 8 seeds (与 B1/B2/B3 一致)
- **步数:** 2000 steps
- **N0:** 72 (L1), L2 独立 N0=72
- **架构:** CSC(constraint)+NSE+LNT

---

## 对比基线

| 实验 | 耦合模式 | L1↔L2 r | L0→L1 延迟 | TopDown | L2 叙事 |
|---|---|---|---|---|---|
| B1 (Parallel) | parallel | 0.976 | N/A | 0/8 | silent |
| B2 (Serial) | serial | 0.861 | 0/8 | 0/8 | silent |
| B3 (Redesign) | serial+noise | 0.937 | 0/8 | ~7/8 | silent |
| **B4 (Constraint)** | **constraint** | **目标 < 0.7** | **目标 ≥ 4/8** | **目标 ≥ 4/8** | **目标 ≥ 5/8 非 silent** |

---

## 代码修改清单

### engine/cross_scale_coupling.py
1. 新增 `ConstraintConduction` 类（替代 `SerialCoupling`）
2. 实现 L2 独立聚簇计算
3. 实现约束传导机制（软边界 clamp）
4. 新增 B4 配置参数

### engine/hierarchical_evolver.py
1. 修改 CSC 调用：支持 `constraint` 模式
2. 修改 LNT：L2 叙事独立生成
3. 调整 L1 制度自稳权重

### experiments/exp_117_phase5_b4_constraint_conduction.py
1. 新实验脚本，8 seeds × 2000 steps
2. 新增 H33/H34 假设检测
3. 与 B1/B2/B3 对比分析

---

## 理论依据

### 差异论 §2.2 — 层级的本质

> "层级不是信息的逐级传递，而是差异在不同尺度上的重新组织。"

B4 的核心设计完全遵循这一原则：
- L2 有独立的差异场（独立聚簇）
- L2 有独立的动力学（自主演化）
- L1→L2 是约束调节，不是信息传递

### 差异论 §2.3 — 约束与自由

> "制度是文明的约束，但不是文明的决定者。"

B4 的约束传导机制正是这一思想的工程实现：
- 约束是软边界（tolerance），不是硬派生
- L2 在约束范围内有充分的自主演化空间
- 约束的作用是"塑造"而非"决定"

---

## 风险与应对

| 风险 | 可能性 | 应对 |
|---|---|---|
| L2 独立聚簇不稳定 | 中 | 从 B2 的 serial 配置逐步过渡，先保留部分派生 |
| 约束权重难以调优 | 高 | 设计参数扫描实验，找到最优权重组合 |
| L2 叙事仍为 silent | 中 | 降低叙事阈值，增加 L2 叙事递归灵敏度 |
| H1-H8 基线失败 | 低 | B4 架构与 B3 类似，基线应保持 |

---

## 下一步

1. ✅ 完成 B4 设计文档（本文档）
2. ⬜ 实现 `ConstraintConduction` 类
3. ⬜ 修改 `hierarchical_evolver.py` 支持 constraint 模式
4. ⬜ 编写 `exp_117` 实验脚本
5. ⬜ 运行实验并分析结果
6. ⬜ 与 B1/B2/B3 对比，总结层级耦合规律
