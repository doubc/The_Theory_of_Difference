# exp_118 Track B5: Independent L2 — 失败分析与重构方案

> **⚠️ 重要发现**: 本分析基于种子42的完整运行结果。其余7个种子全部崩溃。调试会话 (commit a0fbb08) 发现了更根本的架构问题。

## 实验结果汇总

| 指标 | 结果 | 目标 | 状态 |
|------|------|------|------|
| H1-H8 | 1-2/8 (NSI=0.0) | 8/8 | ❌ 灾难性失败 |
| H30 (L1↔L2 r<0.7) | 8/8 (r=0.0) | ≥5/8 | ⚠️ 假阳性 |
| H31 (L0→L1 延迟) | 0/8 | ≥4/8 | ❌ |
| H32 (L2 自主性) | 0/8 | ≥5/8 | ❌ |
| H33 (L2 ODI 独立) | 0/8 | ≥5/8 | ❌ |
| H34 (响应延迟) | 0/8 | ≥4/8 | ❌ |

**8个种子中，只有种子42完整运行（exp_118_b5_results.json），其余7个种子全部崩溃或报错。**

## 崩溃原因

1. **SIGKILL (rapid-cr)**: `numpy corrcoef` 中 `invalid value encountered in divide` — 当 L1 和 L2 稳定性序列方差为0时，相关系数计算产生 NaN
2. **hierarchical_evolver.py line 1839**: `narrative_recursion` 回调中，L2 的 structure_vector 为 None 或全零，导致后续计算崩溃
3. **hierarchical_evolver.py line 2257**: `hierarchy.get_layer(layer_id)` 中 layer_id 无效 — 可能因 L2 状态异常导致层级注册失败
4. **exp_118 line 489**: `AnticipatoryBiasEngine` 初始化参数错误

## 根本原因分析

### 🔴 根本原因：max_layers=1 架构不兼容（调试会话发现，commit a0fbb08）

**这是比独立 L2 耦合更根本的问题。**

B5 设计使用 `max_layers=1`，L1/L2 仅作为后验计算（post-hoc calculation）通过 `IndependentL2Coupling` 生成。但：

- **NSE 需要实际的多层动力学来计算 NSI**：NSE 的 NSI 计算追踪叙事层级转换（MINI → INSTITUTIONAL → CIVILIZATION）
- **max_layers=1 时只有 MINI 层**：没有层级转换可追踪，NSI 永远为 0
- **信号确实存在**：signals_processed mean=10.1, 32% non-zero — 信号在生成，但 NSE 无法计算 NSI
- **ODI = None**：ODI 未被正确提取（嵌套 dict 格式问题）

**关键对比**：
- exp_117 (B4): `max_layers=1`, `coupling_mode='constraint'` → H1-H8 8/8 PASS
- exp_118 (B5): `max_layers=1`, `coupling_mode='independent'` → H1-H8 1/8 PASS

两者都用 `max_layers=1`，但 B4 成功而 B5 失败。差异在于：
- B4 使用 `MomentumNarrativeOperatorV4P1F` 的**平均偏差校正**
- B5 最初使用**最强动作偏差**，即使改为平均偏差校正后仍然失败
- 即使将 B5 的 CSC mode 改回 `'constraint'`，仍然失败

**结论**: `max_layers=1` + 后验 L2 耦合与叙事涌现**架构不兼容**。NSE 需要实际的多层动态。

### 次要原因：H30 是假阳性，同 B4

B5 的 H30 "通过"（r=0.0）与 B4 完全相同，都是**假阳性**：

```
B4: L1 silent, L2 silent → 零方差 → 零相关 → H30 "pass"
B5: L1 dead (NSI=0), L2 zombie (stability=0.15, ODI≈0) → 极低方差 → 零相关 → H30 "pass"
```

### 机制分析

`IndependentL2Coupling.update()` 的计算流程：

```
Step 1: l2_auto_base = l0_stability * 0.6          # L0 死亡 → 0
Step 2: l2_vector = l0_vector + noise              # L0 无结构 → 纯噪声
Step 3: l2_odi = l0_odi * 0.5 + noise_component    # L0 ODI=0 → ≈0
Step 4: l2_stability = l2_auto_base + L1_bias      # ≈0 + 小量
Step 5: l2_stability = clip(l2_stability, 0.15, 1) # 被地板强行抬到 0.15
```

**关键缺陷**：

1. **稳定性地板制造了"僵尸 L2"**：即使 L0 完全死亡（NSI=0），L2 仍被强制维持 0.15 的稳定性。这创造了一个有活动但无内容的 L2。

2. **L2 结构向量是纯噪声**：`l2_vector = l0_vector + noise`，当 `l0_vector` 为零或接近零时，L2 的结构完全来自随机噪声，与 L0 的差异场无关。

3. **L2 ODI 几乎为零**：`l2_odi = l0_odi * 0.5 + ...`，当 L0 ODI=0 时，L2 ODI 也接近 0。

4. **叙事递归无法工作**：`NarrativeRecursionOperator` 需要三层都有有意义的结构向量才能构建跨层叙事。当 L2 是噪声、L0 是死亡状态时，叙事递归返回空结果 → NSI=0。

### 理论诊断

**独立 L2 聚簇的根本问题**：

差异论的核心是"差异产生结构"。L1 和 L2 都是对 L0 差异场的不同尺度编码。如果 L2 完全独立聚簇（即从 L0 的原始向量重新聚类），那么：

- L2 的差异场与 L1 的差异场**没有共享的结构基础**
- 两层之间的"差异"不是层级差异，而是**随机差异**
- 这违背了差异论的层级性原则：高层级应该是低层级差异场的**再编码**，而非**重新聚类**

《差异论 V1.7》第二章："层级不是独立的差异场，而是同一差异场在不同尺度上的投影。"

## 重构方案

### 🔴 首要修复：max_layers=1 → max_layers=3

这是调试会话 (commit a0fbb08) 发现的**根本性架构问题**。必须首先修复：

1. **将 `max_layers=1` 改为 `max_layers=3`**：让 MINI、INSTITUTIONAL、CIVILIZATION 三层都被实际演化
2. **修复 HierarchyManager 的层级初始化**：当前 manager 从 layer 0 开始，通过封装在演化过程中创建高层级。需要处理高层级尚未存在的情况
3. **使用标准 `NarrativeRecursionOperator`**（已在 exp_107 验证有效）
4. **使用默认 NSE 配置**（已在 exp_110 验证有效）
5. **修复 ODI 提取**：处理嵌套 dict 格式

### 次要修复：IndependentL2Coupling 改进

在 max_layers=3 的基础上，改进 `IndependentL2Coupling`：

1. **移除稳定性地板**：让 L2 的稳定性完全由 L0 的活跃程度决定，避免"僵尸 L2"
2. **L2 结构向量 = L0 结构向量的低通滤波版本**：`l2_vector = smooth(l0_vector, window=T2)`，其中 T2 > T1
3. **L2 ODI = L0 ODI 的累积版本**：`l2_odi = cumulative_odi(l0_odi, window=T2)`
4. **L1 提供软约束**：作为 additive bias，但不强制地板

### 方案对比

| 方案 | 描述 | 可行性 | 风险 |
|------|------|--------|------|
| A | max_layers=3 + 改进的 IndependentL2Coupling | ✅ 推荐 | 需要修复 HierarchyManager |
| B | L2 独立差异场 + 共享种子空间 | ⚠️ 可能 | 仍然可能导致结构不相关 |
| C | L2 = L1 时间延迟版本 | ⚠️ 备选 | 更接近差异论，但需要重新设计 |

## 建议

**第一步（必须）**：修复 `max_layers=1 → max_layers=3` 和 HierarchyManager 初始化。

**第二步**：在多层架构基础上，重新设计 `IndependentL2Coupling`：
- L2 从 L0 的结构向量派生（共享差异场基础）
- 通过低通滤波实现时间尺度分离
- 移除稳定性地板，避免僵尸 L2
- L1 提供软约束作为 additive bias

**第三步**：重新运行实验（exp_119），验证：
- H1-H8 基线恢复 8/8
- H30 真实通过（非假阳性）
- H31-H34 层级动力学指标

**下一步**：
1. 修复 `engine/hierarchy_manager.py` 的多层初始化
2. 修改 `exp_118` 或创建 `exp_119`，设置 `max_layers=3`
3. 改进 `IndependentL2Coupling`，移除稳定性地板
4. 使用标准 `NarrativeRecursionOperator` + 默认 NSE
5. 运行完整 8 seeds 实验

---

## 历史对比

| Track | 方法 | max_layers | H30 | H1-H8 | 结论 |
|-------|------|-----------|-----|-------|------|
| B1 | 并行耦合 | 1 | 0/8 (r=0.976) | 8/8 | L1-L2 完全耦合 |
| B2 | 串行耦合 | 1 | 1/8 (r=0.861) | 8/8 | 轻微改善 |
| B3 | 噪声注入 | 1 | 0/8 (r=0.937) | 8/8 | 噪声不足 |
| B4 | 约束 clamp | 1 | 8/8 (r=0.0) | 0/8 | 假阳性（双沉默） |
| B5 | 独立 L2 | 1 | 8/8 (r=0.0) | 1-2/8 | 假阳性（僵尸 L2）+ 架构不兼容 |

**结论**：
1. 通过"破坏耦合"来实现 H30 的所有尝试都失败了。B1-B3 无法解耦，B4-B5 通过破坏系统实现了假阳性解耦。
2. **B5 的额外问题**：`max_layers=1` 与 NSE 架构不兼容 — NSE 需要实际的多层动力学来计算 NSI。
3. **真正的解耦必须在不破坏层级动力学的前提下实现**——这需要通过**时间尺度分离**，而非空间独立。
4. **首要修复**：`max_layers=1 → max_layers=3`，然后重新设计 L2 耦合机制。
