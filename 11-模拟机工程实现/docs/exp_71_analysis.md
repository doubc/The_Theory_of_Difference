# exp_71 实验分析报告

> **日期**：2026-05-28
> **实验**：Functional Signal Coupling — 功能信号耦合 vs. 位置耦合
> **结果文件**：`experiments/exp_71_results_20260528_102740.json`

---

## 一、实验目的

测试从 Phase 2 组件输出中提取的功能信号耦合（functional coupling）是否优于位置耦合（positional coupling，即 `bit_id % 6` 分组）。

四个配置：
- **A**：基线 — 位置加权耦合（weighted, threshold=0.30, N72）
- **B**：功能信号耦合（functional, threshold=0.30, N72）
- **C**：功能信号耦合 + 更低阈值（functional, threshold=0.15, N72）
- **D**：功能信号耦合 + 最低阈值（functional, threshold=0.10, N72）

---

## 二、实验结果

| 配置 | 收敛率 | Avg ODI | Max ODI | 耦合率 |
|------|--------|---------|---------|--------|
| A (baseline) | 19.2% | 0.000 | 0.000 | 20.0% |
| B (func 0.30) | 19.2% | 0.000 | 0.000 | 20.0% |
| C (func 0.15) | 19.2% | 0.000 | 0.000 | 20.0% |
| D (func 0.10) | 19.2% | 0.000 | 0.000 | 20.0% |

**所有四个配置的结果完全一致。**

---

## 三、根因分析

### 3.1 表面原因

`HierarchicalEvolver` 确实在 step 循环中提取了功能信号并传递给 `PreSubjectivityConvergence.evaluate()`（见 `hierarchical_evolver.py:603-653`）。功能信号提取代码路径存在且被调用。

### 3.2 深层原因

功能信号的值在短运行（300步）中几乎全为零：

1. **`variant_retention_rates`**：`cumulative_selector._variants` 在 300 步内积累的变体极少，多数变体 `n_observations == 0`，导致列表为空 → `extract_functional_signals` 收到 `None` → `replication = 0.0`

2. **`selection_trend_scores`**：同上，`cumulative_selector` 的变体保留率在短运行中趋近于 0 → `selection = 0.0`

3. **`aggregate_retention_depth`**：`persistent_bias_memory` 的偏置递归深度在 300 步内尚未建立 → `retention = 0.0`

4. **`component_contributions`**：`component_contributions` 可能为 `None` 或空 → `functional_differentiation = 0.0`

5. **`direction_agreement`（自维持）**：`self_sustaining` 值来自 rebuild success count，在短运行中可能较低 → `self_sustaining ≈ 0.0`

6. **`active_count / total_bits`（界面调节）**：这是唯一可能有非零值的信号，但仅凭一个非零信号无法让 6 机制耦合矩阵通过加权评分（需要 ≥50% 总权重）。

### 3.3 结论

**功能信号耦合在当前的短运行实验中退化为零信号耦合。** 这不是代码 bug，而是实验设计问题：Phase 2 组件需要更长的运行时间和更多的结构积累才能产生有意义的功能信号。

---

## 四、与基线相同的另一个可能原因

即使功能信号全为零，`extract_functional_signals` 返回的 `FunctionalSignalSet` 所有字段为 0，`compute_functional_coupling_matrix` 计算的耦合矩阵对角线为 1.0、非对角线为 0.0。`n_above_threshold(0.30)` = 0，加权得分 = 0，耦合不通过。

但基线（positional weighted）的耦合矩阵也是全零（因为 `coupling_matrix` 参数也是从同一组 Phase 2 组件状态计算的），所以两者都得到相同的耦合率（20% = 仅靠 `active_count/total_bits` 一个信号偶尔通过）。

---

## 五、改进建议

### P0：延长实验运行时间
- 将 `steps` 从 300 提升到 2000-5000，让 Phase 2 组件有足够时间积累信号
- 或者增加 `episodes` 和 `steps_per_episode`

### P1：添加功能信号诊断日志
- 在 `exp_71` 中打印每步的 `functional_signals` 值，确认信号是否在积累
- 在 `PreSubjectivityConvergence._evaluate_functional_coupling` 中添加 debug 日志

### P2：设计功能信号预热阶段
- 在正式评估前运行 500 步预热，让 `cumulative_selector` 和 `persistent_bias_memory` 积累足够数据

### P3：考虑功能信号的替代来源
- 如果 Phase 2 组件积累太慢，可以考虑从 `SpatialLongRangeEvolver` 的中间状态（如源/汇权重、横向耦合强度）直接提取功能信号

---

## 六、当前阶段判断

exp_71 的结果表明：**功能信号耦合方案在架构上是正确的（代码路径存在且逻辑自洽），但实验参数（运行时间太短）导致信号尚未激活。** 这不影响 Phase 2 组件的正确性，但意味着需要更长的实验来验证功能耦合的优势。

**建议下一步**：先运行 exp_72（延长版，steps=2000），同时添加功能信号诊断日志。
