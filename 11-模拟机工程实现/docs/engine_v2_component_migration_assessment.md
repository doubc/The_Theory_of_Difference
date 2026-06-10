# engine → engine_v2 组件迁移评估

> 日期: 2026-06-10 11:44
> 目标: 评估 Phase 1-16 engine/ 的 ~40 个模块中哪些值得迁移到 engine_v2 框架

---

## 评估标准

1. **与 engine_v2 架构兼容**: 纯 numpy（engine_v2 无 torch/其他重型依赖）
2. **功能独立**: 不依赖 engine/的 HierarchicalEvolver 或 cross_scale_coupling
3. **提供 engine_v2 缺失的能力**: engine_v2 当前是 ~400 行 4 文件的最小闭环
4. **理论成熟度**: 已在原项目中经过实验验证

---

## A. 高优先级 — 建议立即迁移

### A1. per_layer_metrics.py (numpy + 无 torch)

**原位置**: `engine/per_layer_metrics.py` (~730 行)
**依赖**: 纯 numpy + Python stdlib
**状态**: Phase 5 Track B8 开发, 经过 B8-B10 验证

**组件清单**:
| 类/函数 | 迁移难度 | engine_v2 集成方式 |
|----------|---------|-------------------|
| `PerLayerNSITracker` | 低(纯numpy) | 加入 `diffsim/metrics.py` 或新文件 |
| `PerLayerCIVTracker` | 低(纯numpy) | 同上 |
| `PerLayerThemeTracker` | 低(Python set) | 同上 |
| `LayerAutonomyAnalyzer` | 低(numpy corr) | 同上 |

**为什么迁移**:
- engine_v2 当前 metrics.py 只有 `jaccard_flux()` 和 `summarize()`
- per_layer_metrics 提供 NSI、CIV、主题、层间自主性分析
- 是 H46-H49 风格假设检验的基础设施
- 完全无 torch, 直接可在 engine_v2 的 `Layer.flux_trace` 等数据上运行

**迁移建议**:
- 将四个 tracker 类精简为 ~300 行, 放入 `diffsim/metrics.py` 扩展版
- 移除 engine/ 中特有的 LayerNarrativeTracker 耦合
- 增加 `PerLayerAnalyzer` 作为顶级入口, 接受 `Layer` 对象列表

---

### A2. difference_density_tracker.py 概念移植 (torch → numpy)

**原位置**: `engine/difference_density_tracker.py` (~710 行)
**依赖**: **torch** — 需要重写为 numpy
**状态**: Phase 11 P0 开发, 经过验证

**核心概念**:
- K_t (差异密度) = f(hamming_weight_variance, cluster_density, seal_proximity)
- 相变检测: 临界减速(critical slowing down) + 突变(sudden jump) 信号
- 与 engine_v2 非常相关: engine_v2 的密封本身是一阶相变

**为什么迁移**:
- engine_v2 的 RecursiveWorld 逐层密封, 本质上是相变级联
- K_t 追踪可量化"密封前"和"密封后"的差异密度变化
- 相变检测可提供自动密封检测, 替代硬编码 seal_fraction 阈值
- 是 engine_v2 迈向"无参演化"的关键组件

**迁移建议**:
- 重写核心 K_t 计算为纯 numpy (原代码 torcia 化严重)
- 保留滑动窗口 + 相变检测逻辑
- 适配 engine_v2 的 `DifferenceField` 作为输入(替代 torch.Tensor)
- 估计迁移后 ~200 行

---

### A3. civ_floor.py (numpy + 无 torch)

**原位置**: `engine/civ_floor.py` (~120 行)
**依赖**: 纯 numpy
**状态**: Phase 5 小工具, 轻量已验证

**功能**: CIV 下限保证（确保系统在密封后仍有最小 churn）

**为什么迁移**:
- engine_v2 中没有独立的 CIV 下限机制
- churn 参数目前硬编码为 2, 在密封后可能降为 0
- civ_floor 可作为 `Params` 的可选字段

**迁移建议**:
- 直接合并到 `diffsim/world.py` 的 `Params` 数据类
- 在 `m5_minimal_variation` 中使用

---

## B. 中优先级 — 理论价值高但需适配

### B1. MultiMembershipSeal 概念移植 (torch → numpy)

**原位置**: `engine/multi_membership_seal.py` (~470 行)
**依赖**: torch
**状态**: Phase 9 开发, 经过少量验证

**核心概念**:
- 比特可同时隶属多个组织（多隶属）
- 渐进式封口（组织逐步形成, 非一次性）
- 残余自由度追踪

**与 engine_v2 的关系**:
- engine_v2 的 A9 目前是"一次性封装": 密封后立即生成下一层
- 多隶属允许更复杂的层级结构（一个组织可同时属于多个上层）
- 但 engine_v2 的设计哲学是"最小行动验证", 不应过早增加复杂度

**迁移建议**:
- 作为 engine_v2 的 A9 扩展方案而非核心
- 放在 `diffsim/mechanisms_extensions.py` 中可选启用
- 使用 `Params.multi_membership` 标志控制
- 不需要立即迁移

### B2. OrganizationalDensityIndex (第4/5期组件)

**原位置**: `engine/organizational_density_index.py` (~340 行)
**依赖**: 纯 numpy
**状态**: Phase 2-4 多次验证

**功能**: 组织密度度量（与 K_t 互补）

**为什么迁移**:
- engine_v2 的 metrics.py 需要更多指标
- ODI 与 per_layer_metrics 结合可提供完整的"涌现程度"评估

---

## C. 低优先级 / 不建议迁移

### C1. 被 engine_v2 取代的组件

| 组件 | 原因 |
|------|------|
| `cross_scale_coupling.py` | engine_v2 的自指闭环取代了外部 CSC |
| `hierarchical_evolver.py` (164k行!) | engine_v2 的 Layer+RecursiveWorld 是更简洁的替代 |
| `hierarchy_manager.py` | engine_v2 在 core.DifferenceField 中内置了层级 |
| `encapsulation_engine.py` | A9 自指封装已在 mechanisms.m9_self_reference 中实现 |
| `narrative_self_emergence.py` | engine_v2 的 Jaccard flux 直接衡量"活秩序" |
| `narrative_recursive_closure.py` | engine_v2 的自指闭环本身就是叙事递归 |
| `layer_narrative_tracker.py` | 被 per_layer_metrics 覆盖 |
| `l1_cycle_detector.py` | engine_v2 的 m7_cycle 已内置循环检测 |

### C2. torch 依赖过重, 移植成本 > 收益

| 组件 | 依赖 | 行数 | 建议 |
|------|------|------|------|
| `cooperative_emergence_detector.py` | torch | ~30k | 不迁移 |
| `counterfactual_engine.py` | torch | ~50k | 不迁移 |
| `anticipatory_bias_engine.py` | torch | ~29k | 不迁移 |
| `minimal_self_detector.py` | torch | ~29k | 不迁移 |
| `global_bias_constraint.py` | torch | ~14k | 不迁移 |
| `pre_subjectivity_convergence.py` | torch | ~26k | 不迁移 |
| `persistent_bias_memory.py` | torch | ~27k | 不迁移 |

这些组件是 Phase 2-3 的"复杂理论中间体", engine_v2 以更简洁的"九个齿轮"实现了相同的功能。

### C3. 实验性 / 未稳定验证的组件

| 组件 | 状态 | 建议 |
|------|------|------|
| `subspace_evolver.py` | Phase 11 P3 | 作为独立研究线保留在 engine/ |
| `subspace_field.py` | Phase 11 P1 | 同上 |
| `spatial_evolver_v2.py` | Phase 12 | 同上 |
| `long_range_evolver_v2.py` | Phase 1 遗留 | 不迁移 |
| `functional_differentiation.py` | Phase 2 P2 | 被 A9 替代 |
| `functional_signal_coupling.py` | 边缘 | 不迁移 |

---

## D. 基础设施迁移

### D1. 探测器和统计工具

| 组件 | 依赖 | 建议 |
|------|------|------|
| `detectors/statistics.py` | torch | 概念移植: Hamming分布/返回时间/聚类检测 → numpy |
| `detectors/dimension_locking_v2.py` | torch + numpy | 部分移植: 关联维度计算可用 numpy |

### D2. 测试框架

engine_v2 仅有 `tests/test_closure.py` (3 个测试)。旧项目积累了丰富的测试模式:
- **对比测试**: baseline vs fix 模式 (run_experiment.py)
- **参数扫描**: robustness_sweep.py 已实现但可扩展
- **假设检验**: 从 exp_101-exp_175 积累的 H1-H57 框架

建议:
- 将 `robustness_sweep.py` 升级为通用测试框架
- 添加"回归测试": 确保 A9 自指闭环不被后续修改破坏
- 添加"理论约束测试": 验证 flux > 0, depth ≥ 3, L2 ≥ 95%

---

## E. 迁移路线图

### Phase 17 (当前) — 完成核心验证后
```
□ P0: core validation (已迁移)
□ P1: parameter robustness (已验证)
→ P2: per_layer_metrics 迁移 [本评估推荐下一个]
□ P3: civ_floor 合并
```

### Phase 18 — 丰富 metrics 层
```
□ P0: PerLayerAnalyzer 集成 (metrics 扩展)
□ P1: K_t 差异密度追踪 (numpy 版)
□ P2: ODI 集成
```

### Phase 19 — 可选扩展
```
□ P0: MultiMembershipSeal (numpy 版, 可选)
□ P1: 相变自动检测 (替代硬编码 seal_fraction)
□ P2: 探测器迁移 (统计量)
```

---

## F. 结论

### 建议立即迁移 (Phase 17 P2)
1. **per_layer_metrics.py** → 直接 numpy 移植 ≈ 1 个 session
2. **civ_floor.py** → 合并到 world.py Params ≈ 30 分钟

### 建议近期迁移 (Phase 18)
3. **difference_density_tracker.py** (numpy 重写) ≈ 2 个 session

### 不建议迁移
- 其余 ~30 个模块保持原样在 engine/ 中归档
- 新工作在 engine_v2 上开展

### 核心原则
engine_v2 的设计哲学是"最小行动验证"——每个齿轮都要可独立检视、每个假设都要有对应指标。迁移时优先考虑:
1. 是否提供了 engine_v2 当前缺失的**可测量指标**
2. 是否有助于**理论验证**而非扩展功能
3. 是否**无外部依赖** (禁止 torch)

---

*本评估于 2026-06-10 11:44 CST 基于 engine/ (40 模块) 和 engine_v2/ (4 模块 + 扫描脚本) 源码分析完成。*