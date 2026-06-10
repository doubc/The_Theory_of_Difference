# engine/ → engine_v2/ 组件迁移评估

**日期**: 2026-06-10 12:44 CST  
**作者**: Heartbeat agent  
**状态**: 评估完成 — 不建议迁移，建议新建

---

## 深度评估：engine/ 有 40+ 个模块，哪些值得迁移？

### 评估标准

| 权重 | 标准 |
|------|------|
| ★★★ | 该组件是否提供 engine_v2 尚未覆盖的**全新能力** |
| ★★☆ | 该组件是否是 engine_v2 已有概念的**更优实现** |
| ★☆☆ | 该组件是否承载已被 engine_v2 **推翻或废弃**的假设 |

---

## 逐组件评估

### 🔴 低价值 — 不迁移（概念已内建或被废弃）

| 组件 | 旧用途 | 为什么不迁移 |
|------|--------|-------------|
| `multi_membership_seal.py` | A9 多隶属封口（缓解全无/全有问题） | engine_v2 的 m9_self_reference 用命名位+身体位+余差位更干净地解决了此问题。旧实现是二进制封口的变通，非优雅方案。 |
| `encapsulation_engine.py` | 分层封装引擎 | 已被 engine_v2 的 m9_self_reference 取代 — 自指封装是递归的、内生的，比旧架构的"冻结后手动封装"更理论一致。 |
| `hierarchical_evolver.py` | 跨层级演化器（orchestrator） | 被 RecursiveWorld 取代。旧版本是线性脚本（seal→create L1→continue），engine_v2 的九机制闭环是递归的、原则性的。 |
| `hierarchy_manager.py` | 层级状态管理 | 多余。engine_v2 的 DifferenceField.layer + RecursiveWorld 自然管理层级。 |
| `cross_scale_coupling.py` + `cross_layer_gravity.py` | 跨层信息传导 | 旧架构为打破"死秩序"而设计的数十种耦合模式（并行/串行/约束传导/噪声）全是**治标**方案。engine_v2 的自指是**治本**方案。 |
| `adaptive_momentum_controller.py` | 自适应动量控制 | Phase 4 P2 Track A 消融实验确认冗余（AMC 移除后 8/8 假设通过） |
| `institutional_layer_protector.py` | 制度层保护 | Phase 4 P2 Track A 消融实验确认冗余（ILP 移除后 8/8 假设通过） |
| `narrative_self_emergence.py` + `narrative_recursive_closure.py` | 叙事自涌现/递归封闭 | engine_v2 的 jaccard_flux 是更好的"活性"度量。旧 NSI 度量的精确性已被新 flux 度量覆盖。 |
| `layer_narrative_tracker.py` + `per_layer_metrics.py` | 分层叙事追踪 | engine_v2 原生记录每层 flux 和 active_history。旧 NSI 计算（当时为 H46-H49 设计）在 engine_v2 框架下不适用（ODI 概念不同）。 |
| `l1_cycle_detector.py` | L1 周期检测 | m7_cycle 已内建在 engine_v2 的九机制循环中。 |
| `long_range_evolver_v2.py` + `spatial_evolver_v2.py` | 主引擎（演化和空间） | 概念被 engine_v2 的九机制+位场完全取代。旧演进器的公理约束是硬编码的，engine_v2 的公理是齿轮化的、可组合的。 |
| `global_bias_constraint.py` | 全局偏置约束 | 试图人为创造"前主体态统一视角"。engine_v2 的自指（m9）自然产生跨层结构，不需要外部偏置。 |
| `counterfactual_engine.py` + `anticipatory_bias_engine.py` + `minimal_self_detector.py` | Phase 3 前主体组件 | 旧架构试图构建"前主体态"的行为。engine_v2 从差异本体出发，不再需要这些辅助探测器。 |
| Phase 2 探测器群（`xiang_detector.py`, `six_threshold_detector.py`, `seventh_threshold_detector.py`, `pre_subjectivity_convergence.py`, `cooperative_emergence_detector.py`, `organizational_density_index.py`） | 各种检测/度量器 | 全部被九机制齿轮化吸收（聚簇、层级、破缺、锁定等直接测量绑定和位状态，而非通过代理探测器）。 |
| `functional_differentiation.py` + `functional_signal_coupling.py` + `lateral_coupling.py` + `replicate_pattern.py` + `self_sustaining_circulation.py` + `return_flow_channel.py` + `persistent_bias_memory.py` + `cumulative_selector.py` | Phase 2 各种机制 | 九机制齿轮化从更基本原理出发（聚簇→层级→守恒→完备→变易→破缺→循环→锁定→自指），不再需要这些"功能模块"式组件。 |
| `civ_floor.py` | CIV 最低值 | Phase 4 的 bug 修复产物。engine_v2 的 flux 度量不涉及 CIV 概念。 |
| `unsealing_mechanism.py` | 密封后解封 | Phase 16 Path C 实验表明解封后系统不再重新密封—engine_v2 的自指密封不需要解封（下一层自动生成）。 |
| `subspace_evolver.py` + `subspace_field.py` | 子空间分解 | **⚠️ 见下方单独讨论** |

### 🟡 中等价值 — 可考虑在 engine_v2 中重建

| 组件 | 建议 |
|------|------|
| `difference_density_tracker.py` | 差异密度追踪在 engine_v2 中没有直接对应物。不过 jaccard_flux 已覆盖"活跃度"度量。如需要"差异密度"作为额外度量，可在 `metrics.py` 中添加一个函数，**不迁移旧实现**。 |

### 🟢 高价值 — 可作为 engine_v2 后续阶段的新功能

| 组件 | 建议 |
|------|------|
| `open_system_extension.py` | **推荐重建**。engine_v2 目前是封闭系统（所有差异来自内部自指）。环境交互（能量/信息流入）是通向非平衡态热力学的路。 |
| `subspace_field.py` + `subspace_evolver.py` | **推荐重建**。并行子空间 + 控制耦合可扩展 engine_v2 到"多世界"模拟。旧代码依赖 old evolver，需要从零重写。 |

---

## 关于 `subspace_field.py` 的特别说明

`subspace_field.py` (Phase 11) 的概念有理论价值：将一个统一差异空间分解为多个并行的子空间，每个子空间受相同九公理但不同参数约束。这在 engine_v2 框架中可以有更干净的实现：

```python
# engine_v2 风格的子空间实现思路：
class SubspaceWorld:
    """并行子空间世界，每个子空间运行独立的 RecursiveWorld"""
    def __init__(self, Ns, coupling_matrix, ...):
        self.subspaces = [RecursiveWorld(N0=n, ...) for n in Ns]
        self.coupling = coupling_matrix
    
    def step(self):
        for s in self.subspaces:
            s.step()  # 每个子空间运行一步
        # 子空间间耦合（新设计，旧代码不可重复使用）
```

**不建议迁移旧代码**，但**概念值得保留**以备 Phase 18+。

---

## 总结：迁移推荐

```
engine/ 组件              价值  迁移方式
──────────────────────────────────────────────
open_system_extension     🟢    新实现（不迁移旧代码）
subspace_field/evolver    🟢    新实现（不迁移旧代码）  
difference_density_tracker🟡    新度量函数（10 行）
其余 35+ 个组件            🔴    不迁移
```

### 核心结论：**不迁移，新建**

engine_v2 是一个根本性更好的架构：

1. **旧组件建在错误的基础上** — 它们试图修补一个缺少 m9 自指的密封引擎。迁移意味着搬运错误假设。
2. **engine_v2 的九机制是原子化的** — 旧组件的功能被分散到九个函数中，无需"整合"。
3. **唯一值得新建的功能**是 engine_v2 尚未覆盖的领域：**环境交互**和**并行子空间**，且需要用 engine_v2 框架全新实现。

### 建议的后续阶段

| 阶段 | 方向 | 涉及 |
|------|------|------|
| Phase 17 | ✅ 完成 — engine_v2 深度验证 + 参数鲁棒性 |
| Phase 18 | 📋 涌现深度极限分析 | 自指的"命名位耗尽"何时终止 |
| Phase 19 | 📋 开放系统（环境交互） | 重写 open_system_extension |
| Phase 20 | 📋 多世界（并行子空间） | 重写 subspace_field |

---

## 附：Live engine_v2 输出快照 (2026-06-10 12:44)

```
层      N   组织数   密封   自主 flux  模式
L0     48      6     是     0.0100  seed
L1     18      1     是     0.2242  self_reference
L2      8      1     是     0.7043  self_reference
L3      6      1     是     0.6572  self_reference
L4      4      1     是     0.7750  self_reference

涌现深度: 5
```

关键观察：每层仅 1 个组织 — 自指链生成嵌套的"自我"，但始终保持单一中心。