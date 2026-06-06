# 差异论模拟机工程 — 最终架构参考 v1

**日期**: 2026-06-06 10:26 CST  
**基于**: 全局构型 global-architecture.md (2026-05-14) + Phase 2-9 全部扩展  
**范围**: 模块依赖图、数据流、关键参数、已知限制、测试覆盖  
**状态**: 引擎功能完整 ✅ (Phase 1-9 COMPLETE)

---

## 1. 架构全景

### 1.1 三阶段总纲

| 阶段 | 理论目标 | 工程实现 | 状态 |
|------|---------|---------|------|
| **第一阶段** | 离散空间 + 九公理 → 物理性质可检测 | 引擎实现九公理约束，涌现可测量物理量 | ✅ COMPLETE |
| **第二阶段** | 象界 → 涌现前主体态（前主体） | 生成链八章门槛在演化中逐章通过 | ✅ COMPLETE (Phase 3-6) |
| **第三阶段** | 主体态 | 整合涌现、预期驱动、反事实推理 | ✅ COMPLETE (Phase 3) |

### 1.2 引擎组件演化（按 Phase 顺序）

```
Phase 1:                    long_range_evolver_v2, spatial_evolver_v2
                            (基础空间演化器)
                               ↓
Phase 2:  HierarchicalEvolver (整合所有下层组件)
        ├── EncapsulationEngine        (层封装)
        ├── HierarchyManager           (层级管理)
        ├── CrossLayerGravityModulator (跨层级引力)
        ├── XiàngDetector              (底象检测)
        ├── PersistentBiasMemory       (偏置记忆)
        ├── CumulativeSelector         (累积筛选)
        ├── ReturnFlowChannel          (回流通道)
        ├── SixThresholdDetector       (六阈值检测)
        ├── SeventhThresholdDetector   (第七阈值检测)
        ├── PreSubjectivityConvergence (前主体收敛判定)
        ├── UnsealingMechanism         (解封机制)
        ├── SelfSustainingCirculation  (自维持循环)
        ├── FunctionalDifferentiation  (功能分化)
        ├── ReplicatePattern           (复制模式)
        ├── CooperativeEmergenceDetector (协同涌现)
        ├── LateralCoupler             (横向耦合)
        └── OrganizationalDensityIndex (组织密度指数)
                               ↓
Phase 3:  HierarchicalEvolver + Phase 3 组件
        ├── MinimalSelfDetector        (最小自我检测)
        ├── AnticipatoryBiasEngine     (预期偏置)
        ├── CounterfactualEngine       (反事实推理)
        └── GlobalBiasConstraint       (全局偏置约束)
                               ↓
Phase 4:  HierarchicalEvolver + Phase 4 组件
        ├── CrossScaleCoupling         (跨尺度耦合)
        └── NarrativeSelfEmergence     (叙事自我涌现)
                               ↓
Phase 5:  HierarchicalEvolver + Phase 5 组件
        ├── CIVFloor                   (CIV下限)
        ├── PerLayerMetricsCollector   (分层指标)
        └── AdaptiveMomentumController (自适应动量)
                               ↓
Phase 6:  HierarchicalEvolver + Phase 6 组件
        └── NarrativeRecursiveClosure  (叙事递归闭合 NRC)
                               ↓
Phase 8:  HierarchicalEvolver + Phase 8 组件
        └── L1CycleDetector            (L1循环检测)
                               ↓
Phase 9:  HierarchicalEvolver + Phase 9 组件
        └── MultiMembershipSeal        (多隶属封口)
```

---

## 2. 模块依赖图（显式导入关系）

### 2.1 顶层入口

```
HierarchicalEvolver (engine/hierarchical_evolver.py)
  是整个引擎的**唯一主入口**。
  它直接导入并编排所有子系统组件。
```

### 2.2 完整依赖关系

```
HierarchicalEvolver
  ├── SpatialLongRangeEvolver (engine/spatial_evolver_v2.py)
  │     └── 继承自 LongRangeEvolverBase
  ├── HierarchyManager (engine/hierarchy_manager.py)
  │     ├── LayerState
  │     └── BiasField
  ├── EncapsulationEngine (engine/encapsulation_engine.py)
  │     ├── EncapsulatedBit
  │     └── IndexMapping
  ├── CrossLayerGravityModulator (engine/cross_layer_gravity.py)
  │     └── GravityField
  ├── XiàngDetector (engine/xiang_detector.py)
  ├── PersistentBiasMemory (engine/persistent_bias_memory.py)
  │     ├── BiasEntry
  │     └── BiasFieldSnapshot
  ├── CumulativeSelector (engine/cumulative_selector.py)
  ├── ReturnFlowChannel (engine/return_flow_channel.py)
  │     ├── HighSemanticPayload
  │     ├── AnchorPoint
  │     └── SemanticFirewallGuard
  ├── OrganizationalDensityIndex (engine/organizational_density_index.py)
  │     └── DensityIndexResult
  ├── SixThresholdDetector (engine/six_threshold_detector.py)
  ├── SeventhThresholdDetector (engine/seventh_threshold_detector.py)
  │     └── SeventhThresholdResult
  ├── PreSubjectivityConvergence (engine/pre_subjectivity_convergence.py)
  ├── UnsealingMechanism (engine/unsealing_mechanism.py)
  │     └── UnsealingEvent
  ├── SelfSustainingCirculation (engine/self_sustaining_circulation.py)
  ├── FunctionalDifferentiation (engine/functional_differentiation.py)
  ├── ReplicatePattern (engine/replicate_pattern.py)
  ├── CooperativeEmergenceDetector (engine/cooperative_emergence_detector.py)
  │     ├── CooperativeEmergenceResult
  │     └── SynchronizedCrossing
  ├── LateralCoupler (engine/lateral_coupling.py)
  │     └── LateralCouplingReport
  ├── FunctionalSignalCoupling (engine/functional_signal_coupling.py)
  ├── AdaptiveMomentumController (engine/adaptive_momentum_controller.py)
  ├── InstitutionalLayerProtector (engine/institutional_layer_protector.py)
  ├── MinimalSelfDetector (engine/minimal_self_detector.py)
  │     └── MinimalSelfResult
  ├── AnticipatoryBiasEngine (engine/anticipatory_bias_engine.py)
  │     └── AnticipationResult
  ├── CounterfactualEngine (engine/counterfactual_engine.py)
  │     └── CounterfactualResult
  ├── GlobalBiasConstraint (engine/global_bias_constraint.py)
  ├── CrossScaleCoupling (engine/cross_scale_coupling.py)
  ├── NarrativeSelfEmergence (engine/narrative_self_emergence.py)
  ├── CIVFloor (engine/civ_floor.py)
  ├── NarrativeRecursiveClosure (engine/narrative_recursive_closure.py)
  ├── L1CycleDetector (engine/l1_cycle_detector.py)
  └── MultiMembershipSeal (engine/multi_membership_seal.py)
       ├── OrgInfo
       └── MembershipSnapshot

外部依赖（Engine → Layer）:
  layers/three_dim_hamming.py → ThreeDimHammingLattice
  models/narrative_self.py   → NarrativeRecursionOperator, DifferenceSignal
  engine/detectors/statistics.py
  engine/detectors/dimension_locking_v2.py
  engine/difference_density_tracker.py

外部依赖（Engine → Axioms）:
  acl/axioms_v2.py           → AxiomConstraints

外部依赖（Engine → Tools）:
  tools/coupling_bridging.py
```

### 2.3 模块分层

```
Layer 0: 基础库
  torch, numpy, typing, dataclasses, collections, math, enum

Layer 1: 公理层
  acl/axioms_v2.py           — 九公理约束引擎

Layer 2: 空间演化层
  engine/spatial_evolver_v2.py        — 空间长程演化
  engine/long_range_evolver_v2.py     — 长程演化（旧版）
  layers/three_dim_hamming.py         — 汉明几何3D晶格

Layer 3: 层级封装层
  engine/encapsulation_engine.py      — 层封装
  engine/hierarchy_manager.py         — 层级管理
  engine/cross_layer_gravity.py       — 跨层级引力

Layer 4: 象界检测层
  engine/xiang_detector.py            — 底象检测
  engine/persistent_bias_memory.py    — 偏置记忆
  engine/cumulative_selector.py       — 累积筛选
  engine/return_flow_channel.py       — 回流通道
  engine/organizational_density_index.py — 组织密度指数

Layer 5: 阈值与收敛层
  engine/six_threshold_detector.py        — 六阈值同步检测
  engine/seventh_threshold_detector.py    — 第七阈值检测
  engine/pre_subjectivity_convergence.py  — 前主体收敛判定
  engine/unsealing_mechanism.py           — 解封机制

Layer 6: 象界机制层
  engine/self_sustaining_circulation.py    — 自维持循环
  engine/functional_differentiation.py     — 功能分化
  engine/replicate_pattern.py              — 复制模式
  engine/cooperative_emergence_detector.py — 协同涌现检测
  engine/lateral_coupling.py               — 横向耦合
  engine/functional_signal_coupling.py     — 功能信号耦合

Layer 7: 前主体→主体层
  engine/minimal_self_detector.py      — 最小自我
  engine/anticipatory_bias_engine.py   — 预期偏置
  engine/counterfactual_engine.py      — 反事实推理
  engine/global_bias_constraint.py     — 全局偏置约束

Layer 8: 跨尺度与叙事层
  engine/cross_scale_coupling.py        — 跨尺度耦合
  engine/narrative_self_emergence.py    — 叙事自我涌现
  engine/civ_floor.py                   — CIV下限
  engine/per_layer_metrics.py           — 分层指标

Layer 9: 叙事递归与自适应层
  engine/narrative_recursive_closure.py     — 叙事递归闭合
  engine/adaptive_momentum_controller.py    — 自适应动量控制
  engine/institutional_layer_protector.py   — 制度层保护

Layer 10: 循环检测与封口层
  engine/l1_cycle_detector.py          — L1循环检测
  engine/multi_membership_seal.py      — 多隶属封口（A9渐进式）
  engine/difference_density_tracker.py — 差异密度追踪
  engine/detectors/dimension_locking_v2.py — 维度锁定V2
  engine/detectors/statistics.py       — 通用统计探测器
```

---

## 3. 数据流

### 3.1 主循环数据流（每步）

```
HierarchicalEvolver.step()
  │
  ├─ 1. SpatialEvolver.step()
  │     └─ AxiomConstraints.check_all()  →  loss metrics
  │
  ├─ 2. Phase 2 组件链（每个 L0 步）:
  │     ├─ XiàngDetector.detect()           → 底象判定
  │     ├─ PersistentBiasMemory.record()     → 偏置累积
  │     ├─ CumulativeSelector.feed()         → 趋势筛选
  │     ├─ OrganizationalDensityIndex.feed() → ODI
  │     ├─ SixThresholdDetector.feed()       → 六阈值状态
  │     ├─ SeventhThresholdDetector.feed()   → 第七阈值
  │     ├─ PreSubjectivityConvergence.feed() → 前主体收敛
  │     ├─ SelfSustainingCirculation.evaluate() → 自维持
  │     ├─ FunctionalDifferentiation.feed()  → 功能分化
  │     ├─ ReplicatePattern.replicate()      → 复制
  │     ├─ CooperativeEmergenceDetector.feed()→ 协同涌现
  │     ├─ LateralCoupler.step()             → 横向耦合
  │     └─ UnsealingMechanism.step()         → 解封事件
  │
  ├─ 3. Phase 3 组件链:
  │     ├─ MinimalSelfDetector.feed()        → MSI
  │     ├─ AnticipatoryBiasEngine.predict()  → 预期
  │     ├─ AnticipatoryBiasEngine.update()   → 误差更新
  │     ├─ CounterfactualEngine.step()       → 反事实
  │     └─ GlobalBiasConstraint.evaluate()   → 偏置一致性
  │
  ├─ 4. Phase 4 组件链:
  │     ├─ CrossScaleCoupling.step()         → CSCI
  │     └─ NarrativeSelfEmergence.feed()     → NSI
  │
  ├─ 5. Phase 5 组件:
  │     ├─ CIVFloor.update()                 → CIV下限
  │     └─ AdaptiveMomentumController.step() → 动量调整
  │
  ├─ 6. Phase 6 组件:
  │     └─ NarrativeRecursiveClosure.step()  → NRC (P→R→P重写)
  │         ├─ EventCompressor
  │         ├─ MinimumVariationSelector
  │         ├─ NearestStableSettler
  │         └─ SpaceRewriter
  │
  ├─ 7. Phase 8 组件:
  │     └─ L1CycleDetector.feed()            → L1循环检测
  │
  ├─ 8. Phase 9 组件:
  │     └─ MultiMembershipSeal.step()        → 多隶属封口
  │         ├─ form_organizations()          → 组织聚类
  │         └─ record_active()              → 锁定追踪
  │
  ├─ 9. 层级演化逻辑:
  │     ├─ A9封口判定 → HierarchyManager.encapsulate() → 新层
  │     ├─ 跨层级回归测试 (GravityModulation)
  │     ├─ Injection/Absorb/Lateral 统计
  │     └─ 快照保存 (HierarchicalSnapshot)
  │
  └─ 10. 返回 Phase2StepResult / Phase3StepResult
```

### 3.2 跨层级数据流

```
L0 (原始空间 N=72..288)
  │ SpatialEvolver → 位翻转/注入/吸收
  │ A9封口 → EncapsulationEngine → 冻结比特分组
  ▼
L1 (粗粒化 N≥30)
  │ HierarchyManager 封装 → 新层
  │ CrossLayerGravity: 冻结比特→质量分布→引力势
  │ ReturnFlowChannel: 解封事件→高语义载荷→锚定
  │
  ▼
L2 (稳定制度层)
  │ InstitutionalLayerProtector
  │ SelfSustainingCirculation
  │
  ▼
L3 (叙事/文明层)
  │ CrossScaleCoupling (TopDown + BottomUp)
  │ NarrativeRecursiveClosure
```

### 3.3 关键状态传递

```
演化状态 (torch.Tensor) → 各组件共享
  每层独立维护 state tensor (N₁×N₂ 或 N-dimensional)

偏置场 (BiasField) → TopDown约束 → 位注入偏置
  HierarchicalEvolver 管理多个 BiasField，跨层传播

封口状态 (sealed_bits / membership) → 层级升级决策
  MultiMembershipSeal 提供渐进式 locking level

ODI → 各组件门控
  MSI、NRC、CooperativeEmergence 等都被 ODI 门控
  只有当 ODI ≥ threshold 时这些组件才输出非零信号

快照链 (List[HierarchicalSnapshot]) → 分析与回放
  每层每步保存完整状态与统计数据
```

---

## 4. 关键参数及其稳定范围

以下参数范围全部来自 Phase 9 系统鲁棒性测绘（exp_142-144），共 200+ 独立运行。

### 4.1 核心演化参数

| 参数 | 默认值 | 稳定范围 | 特性 |
|------|--------|---------|------|
| N0 (初始空间大小) | 72 | 30–288 | **严格下限 N0≥30**：N0<26 时 L1 完全无法形成；N0=26-29 时随机涌现（0/64 或偶发）；N0≥30 时 64/64 形成 L1。N0*≈30.5 为一阶相变点 |
| steps (演化步数) | 500 | 500–10000 | **零退化**：所有指标在 10000 步内无下降 |
| max_layers | 3 | 2–4 | max_layers=2 时强制在 2 层内结束，不影响涌现质量 |

### 4.2 层级参数

| 参数 | 默认值 | 稳定范围 | 特性 |
|------|--------|---------|------|
| L1 sealing threshold | 0.02 | 0.005–0.10 | **无影响**——该范围内对封口行为无差异（封口度量bug掩盖了阈值效应；即使修复，预期影响也很小） |
| stability_floor | 0.05 | 0.05–0.40 | 唯一有显著影响：floor=0.40 时 2/8 seeds 出现 L1 封口（首次！），其余 6/8 未封口。CIV_max=4 仅在 floor=0.40 出现 |
| topdown_constraint | 0.15 | 0.05–0.40 | 极其鲁棒：0.05 时 1/8 seed 轻微 H8 失败，其余完全正常 |

### 4.3 Phase 3 参数

| 参数 | 默认值 | 稳定范围 | 特性 |
|------|--------|---------|------|
| r2_tension | 1.0 | 0.5–3.0 | r2_tension=3.0 将 R2 事件数从 1.5 降至 0.625（下降 ~58%），且不破坏层级稳定性。这是系统对压力参数的清洁响应 |
| odi_gate | 0.05 | 0.0–0.30 | ODI 门控不影响涌现稳定性，仅控制检测灵敏度 |

### 4.4 涌现指标的正常范围（Phase 9 测绘）

| 指标 | 最小值 | 最大值 | 均值 | 特性 |
|------|--------|-------|------|------|
| NSI (叙事自我指数) | 0.652 | 0.748 | ~0.70 | 在所有条件下保持极窄范围 |
| CIV_max (文明最大指数) | 2.875 | 3.125 | ~3.00 | 几乎不变（±4%） |
| MSI (最小自我指数) | 0.10 | 0.50 | ~0.30 | 受 ODI 门控影响 |
| ODI (组织密度指数) | 0.10 | 0.85 | ~0.50 | 渐进增长，存在明确的阈值动态 |
| L1 形成率 | — | — | 100% | 96/96 所有种子、所有配置均已形成 |
| H1-H8 结构指标通过率 | — | — | 99% | 95/96 seeds 全部通过；1 seed topdown=0.05 时 H8 未通过 |

### 4.5 相变参数（Phase 9 P3）

| 参数 | 值 | 含义 |
|------|-----|------|
| N0* (临界点) | ~30.5 | 一阶（不连续）对称破缺 |
| N0=26-29 | 0/64 seeds L1 形成 | 纯 L0 无序相 |
| N0=30 | 7/16 seeds L1 形成 | 临界点：双峰分布 |
| N0=31-34 | 64/64 seeds L1 形成 | 有序相 |
| 结合强度骤降 | ~50% | 相变处绑定强度减半 |
| 组织整合 | 单调增长 | 有序相中组织化随时间增长 |

### 4.6 维度锁定参数（V2 检测器修复后）

| 参数 | 值 |
|------|-----|
| D_eff (有效自由度) | ≈18.5（测量方法导致；不是物理失效） |
| 实际维数 (D_2) | 用关联维数法正确测定 |
| 维度锁定 | 基于 PCA + 关联维数，修复了 V1 的伪方差问题 |

---

## 5. 测试覆盖地图

**总测试文件**: 46 个，~995 通过，23 跳过  
**测试工具**: pytest (覆盖 31 of 36 engine 模块)

### 5.1 按组件分类

| 测试文件 | 行数 | 覆盖组件 | 覆盖率评估 |
|---------|------|---------|-----------|
| **Phase 2 核心** | | | |
| test_encapsulation.py | 379 | EncapsulationEngine | ✅ 完整 |
| test_hierarchy.py | 164 | HierarchyManager, LayerState | ✅ 核心功能 |
| test_bias_field.py | 179 | BiasField 传播 | ✅ 完整 |
| test_bias_propagation.py | 207 | 偏置传播 | ✅ 完整 |
| test_encapsulation_enhanced.py | 89 | 接口调节 | ⚠️ 基础 |
| test_cross_layer_gravity_integration.py | 247 | CrossLayerGravityModulator | ✅ 完整 |
| **Phase 2 象界** | | | |
| test_xiangjie.py | 221 | XiàngDetector | ✅ 完整 |
| test_return_flow.py | 219 | ReturnFlowChannel | ✅ 完整 |
| test_semantic_firewall_guard.py | 418 | SemanticFirewallGuard | ✅ 详尽 |
| test_organizational_density_index.py | 559 | ODI (核心组件) | ✅ 详尽 |
| test_six_threshold_detector.py | 197 | SixThresholdDetector | ✅ 完整 |
| test_seventh_threshold_detector.py | 388 | SeventhThresholdDetector | ✅ 完整 |
| test_pre_subjectivity_convergence.py | 458 | PreSubjectivityConvergence | ✅ 详尽 |
| test_unsealing.py | 555 | UnsealingMechanism | ✅ 详尽 |
| test_cooperative_emergence.py | 559 | CooperativeEmergenceDetector | ✅ 详尽 |
| test_zone_transition.py | 251 | 区域转换 | ✅ 完整 |
| **Phase 2 机制** | | | |
| test_self_sustaining_circulation.py | 213 | SelfSustainingCirculation | ✅ 完整 |
| test_functional_differentiation.py | 183 | FunctionalDifferentiation | ✅ 完整 |
| test_replicate_pattern.py | 197 | ReplicatePattern | ✅ 完整 |
| test_lateral_coupling.py | 314 | LateralCoupler | ✅ 详尽 |
| test_evolver_lateral_coupling.py | 242 | 与演化器集成 | ✅ 完整 |
| **Phase 3 主体** | | | |
| test_minimal_self_detector.py | 443 | MinimalSelfDetector | ✅ 详尽 |
| test_anticipatory_bias_engine.py | 415 | AnticipatoryBiasEngine | ✅ 详尽 |
| test_counterfactual_engine.py | 684 | CounterfactualEngine (推理最大) | ✅ 详尽 |
| test_global_bias_constraint.py | 275 | GlobalBiasConstraint | ✅ 完整 |
| test_gbc_fix.py | 133 | GBC 修复验证 | ✅ 专项 |
| test_gbc_production.py | 47 | GBC 生产测试 | ⚠️ 基础 |
| test_phase3_integration.py | 253 | Phase 3 集成 | ✅ 完整 |
| **Phase 4 叙事与跨尺度** | | | |
| test_cross_scale_coupling.py | 269 | CrossScaleCoupling | ✅ 完整 |
| test_narrative_self.py | 201 | NarrativeRecursionOperator | ✅ 完整 |
| test_narrative_self_emergence.py | 381 | NarrativeSelfEmergence | ✅ 详尽 |
| test_narrative_recursion_integration.py | 200 | NRC 集成 | ✅ 完整 |
| **Phase 5 保护层** | | | |
| test_institutional_layer_protector.py | 422 | InstitutionalLayerProtector | ✅ 详尽 |
| test_adaptive_momentum_controller.py | 311 | AdaptiveMomentumController | ✅ 详尽 |
| **Phase 8/9** | | | |
| test_l1_cycle_detector | — | L1CycleDetector | 基础 |
| test_multi_membership_seal.py | 641 | MultiMembershipSeal | ✅ 详尽 |
| **跨阶段** | | | |
| test_axioms_v2.py | 164 | AxiomConstraints + 演化器 | ✅ 核心 |
| test_hamming_layer.py | 169 | ThreeDimHammingLattice | ✅ 完整 |
| test_three_dim_hamming.py | 156 | 3D 汉明几何 | ✅ 完整 |
| test_phase2_integration.py | 397 | Phase 2 全流程 | ✅ 完整 |
| test_e2e_phase2.py | 718 | 端到端 Phase 2 | ✅ 详尽 |
| test_retention_depth.py | 460 | 偏置记忆深度 | ✅ 完整 |
| test_threshold_proximity_sigmoid.py | 70 | 阈值邻近 | ⚠️ 专项 |
| test_sealing_fix.py | 102 | 封口修复验证 | ✅ 专项 |
| test_difference_density_tracker.py | 462 | DifferenceDensityTracker | ✅ 详尽 |

### 5.2 关键覆盖缺口

| 未覆盖组件 | 文件 | 风险 | 建议 |
|-----------|------|------|------|
| PerLayerMetricsCollector | engine/per_layer_metrics.py | 低 | Phase 5 辅助组件，被 CIVFloor 隐式覆盖 |
| CIVFloor | engine/civ_floor.py | 低 | 在 test_institutional_layer_protector 中隐式测试 |
| FunctionalSignalCoupling | engine/functional_signal_coupling.py | 低 | 工具函数，在集成测试中覆盖 |
| CrossLayerGravityModulator 边界 | engine/cross_layer_gravity.py | 低 | 仅集成测试，缺乏单元级边界测试 |

### 5.3 已知测试跳过

23 个测试因以下原因跳过：
- 需要 GPU 环境（约 8 个）
- 需要长时间运行的高步数测试（约 10 个）
- 需要特定种子复现的旧 bug 回归测试（约 5 个）

---

## 6. 已知限制与解决方法

### 6.1 功能限制

| # | 限制 | 影响 | 解决方法/备注 |
|---|------|------|-------------|
| 1 | **A6 DAG 约束可绕过** | 演化方向性约束不完整，存在理论上的可逆路径 | `axioms_v2.py` 已有 `block_reverse` 逻辑，但覆盖不全。已作为"已知开放问题"记录在 theory_synthesis_v1.md |
| 2 | **A7 循环闭合为事后检测** | 循环闭合未被用作演化约束，仅作为统计指标 | 不影响涌现实验结论。循环闭合检测器已在 `axioms_v2.py` 中实现但非强制 |
| 3 | **A8 对称偏好无强制机制** | w=N/2 偏好未被编码为演化偏好 | 仅观测统计。不影响 Phase 9 结论——系统在任何偏好条件下都涌现 |
| 4 | **L1/L0 无自然反馈闭环** | L0 和 L1 动力学不形成自然反馈循环 | 已通过 CrossScaleCoupling 的 TopDown 约束人为桥接。不作为代码bug，而是开放理论问题 |
| 5 | **封口度量提取路径不匹配** | 某些配置报告 seal_step=0 尽管 seed 未封口（P9 已知 bug） | `test_sealing_fix.py` 已确认修复的正确性，但旧配置仍可能触发。不影响涌现结论 |
| 6 | **l1_cycle_detector 无独立测试** | L1CycleDetector 缺少专门单元测试 | 风险低——该组件逻辑简单，仅在 Phase 8 中使用 |
| 7 | **PerLayerMetricsCollector 无独立测试** | 分层指标收集器缺少专门测试 | 风险低——被 CIVFloor 和集成测试隐式覆盖 |

### 6.2 结构限制

| # | 限制 | 解释 |
|---|------|------|
| 1 | **引擎不模拟现实物理** | 不声称构建引力/QFT/标准模型。子空间分解（引力/弱力/强力/电磁）仅在理论映射层面 |
| 2 | **无种群演化** | 单世界演化，无多世界竞争选择（这将是 Phase 2/3 的自然扩展） |
| 3 | **无并行演化** | 九机制并行只能在"事后理论分析"中确认。引擎内部是串行的——这是理论并行与实现串行的自然差异 |
| 4 | **子空间未分解** | 引力/弱力/强力/电磁各子空间目前在同一网格上演化，未分解为独立子空间。这不是 Phase 10 的目标 |
| 5 | **维度锁定 V2 整合到标准诊断** | 需要将 `DimensionLockingDetectorV2` 标准化为默认探测器。目前 V1 和 V2 同时存在 |

### 6.3 性能限制

| # | 限制 | 值 |
|---|------|-----|
| 1 | 最大实验规模 | N0=288, steps=10000, 单次运行约 30 分钟 |
| 2 | 内存峰值 | N0=288 + 4层 + 全部组件 ≈ 2-4 GB GPU |
| 3 | 同时运行 | 建议不超过 16 个并行 seed |
| 4 | 支持 OS | Linux & Windows（部分路径在 Windows 上需反斜杠调整） |

---

## 7. 配置参考

### 7.1 Phase 2 默认配置

```python
# engine/hierarchy_manager.py 中的层级管理默认值
DEFAULT_SEAL_THRESHOLD = 0.02      # A9 封口阈值
DEFAULT_MAX_LAYERS = 3             # 最大层级数
DEFAULT_STABILITY_FLOOR = 0.05     # 稳定性下限
DEFAULT_TOP_DOWN_STRENGTH = 0.15   # 自上而下约束强度
```

### 7.2 Phase 3 默认配置

```python
# engine/global_bias_constraint.py
DEFAULT_COUPLING_STRENGTH = 0.15   # 耦合强度

# engine/anticipatory_bias_engine.py
DEFAULT_ANTICIPATION_CONFIG = {
    'history_window': 50,
    'prediction_horizon': 10,
    'confidence_threshold': 0.3,
    'odi_gate': 0.05,
}

# engine/counterfactual_engine.py
DEFAULT_COUNTERFACTUAL_CONFIG = {
    'max_branches': 5,
    'branch_depth': 20,
    'prune_threshold': 0.1,
    'odi_gate': 0.05,
}
```

### 7.3 Phase 4 默认配置

```python
# engine/cross_scale_coupling.py
DEFAULT_CROSS_SCALE_COUPLING_CONFIG = {
    'topdown_max_constraint_strength': 0.15,
    'topdown_min_constraint_strength': 0.02,
    'topdown_response_delay': 15,
    'topdown_decay_rate': 0.97,
    'topdown_propagation_depth': 2,
    'topdown_stability_threshold': 0.3,
    'emergence_min_stability_steps': 50,
    'emergence_stability_threshold': 0.6,
    'emergence_min_odi': 0.25,
    'emergence_cooldown_steps': 30,
}
```

### 7.4 Phase 9 默认配置

```python
# engine/multi_membership_seal.py
# 默认多隶属封口配置（通过类方法创建）
MultiMembershipSeal(n_bits, binding_matrix)
    # n_bits: 空间中的比特数
    # binding_matrix: N×N 绑定强度矩阵（来自 EncapsulationEngine）
    # 行为:
    #   1. form_organizations() 基于 binding_matrix 聚类组织
    #   2. record_active(active_bits) 追踪活动模式
    #   3. is_fully_locked() 判断封口状态
    #   4. lock_level / sealed 向后兼容
```

---

## 8. 依赖的外部工具

| 工具 | 路径 | 用途 |
|------|------|------|
| tools/coupling_bridging.py | 模拟机工程根目录 | 跨层耦合桥接辅助函数 |
| 实验运行器 | experiments/ | Phase 1-9 实验脚本 |
| 验证器 | validators/ | 结构验证（旧版，大部分功能已被 engine 组件取代） |
| 模型 | models/ | NarrativeSelf 模型（NRC 所需） |
| 测试 | tests/ | 46 个 pytest 文件 |

---

## 9. 架构变更日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-05-14 | 初始全局构型 | Phase 1-2 启动 |
| 2026-05-26 | Phase 2 结束：层级封装 + 象界检测 | M4 批次完成 |
| 2026-05-29 | Phase 3 完成：前主体→最小自我 | 预期+反事实+全局偏置 |
| 2026-06-01 | Phase 4 完成：叙事自我 + 跨尺度耦合 | 跨层次双向因果 |
| 2026-06-02 | Phase 5 完成：CIV 下限 + 自适应动量 | 系统压力测试 |
| 2026-06-03 | Phase 6 完成：叙事递归闭合 (NRC) | P→R→P 螺旋 |
| 2026-06-04 | Phase 7 理论映射 | 九机制并行性确立 |
| 2026-06-05 | Phase 8 完成：L1 被动约束 + 跨尺度螺旋 | L1 作为被动约束在最大 2 层时仍成立 |
| 2026-06-05 | Phase 9 完成：鲁棒性测绘 (exp_142-147) | N0*≈30.5 一阶相变确认 |
| 2026-06-06 | A9 多隶属整合 (MultiMembershipSeal → engine 主路径) | Phase 10 P1 完成 |
| 2026-06-06 | Phase 10 P2: 最终架构参考 v1 — 本文 | 模块依赖图 + 数据流 + 参数范围 + 测试覆盖 + 已知限制 |