# Phase 4 规划：叙事自我涌现与跨尺度耦合

> **版本**: v1.0
> **日期**: 2026-05-31
> **状态**: 规划初稿 — 待评审
> **前置**: Phase 3 完成（H1/H2/H3 pass, H4 fails — 3 seeds at CIV=2）
> **理论依据**: 《差异论》V1.7 + ABA §4.4 + 《象界》八环节咬合

---

## 一、Phase 4 的定位

### 1.1 四阶段总纲回顾

| 阶段 | 理论目标 | 工程目标 | 状态 |
|------|---------|---------|------|
| Phase 1 | 九公理 → 物理量涌现 | 引擎 + 反应堆 + 验证器 | ✅ 完成 |
| Phase 2 | 象界 → 前主体态 | 六阈值 + 解封 + 回流 | ✅ 完成 |
| Phase 3 | 前主体态 → 现象意识结构条件 | 预期驱动 + 反事实 + 最小自我 | ✅ 完成 |
| **Phase 4** | **叙事自我涌现 + 跨尺度耦合** | **修复 H4 + 自适应动量 + 叙事自我 + 跨尺度** | ⬜ 规划中 |

### 1.2 核心问题

Phase 3 的终点是验证了三种结构前提（预期驱动、全局偏置一致性、最小自我）可以通过纯结构机制实现，但 H4 失败揭示了一个深层问题：

> **叙事引擎（ODI/MSI）和文明涌现（CIV）是解耦的。** 高 ODI/MSI 不保证高 CIV。

Phase 4 要回答的问题是：

1. **H4 修复**：如何让全部 8 种子达到 CIV ≥ 3？
2. **叙事自我**：从最小自我（MSI）到具有时间连续性的叙事自我——结构如何开始拥有"历史"？
3. **跨尺度耦合**：MINI ↔ INSTITUTIONAL ↔ CIVILIZATION 三个层级之间的双向因果如何建立？

### 1.3 与 V1.7 螺旋框架的关系

V1.7 的核心推进是**从结构解释到生成式世界**——世界不是静态结构，而是不断生成自身的过程：

$$P_{t+1} = R(S(M(E(P_t, D_t))))$$

Phase 1-3 实现了这个螺旋的前半段：
- **Phase 1**: 建立了 $P_t$（可能性空间）和 $E$（事件压缩）
- **Phase 2**: 实现了 $M$（最小变易/六阈值）和 $S$（最近稳态/前主体态收束）
- **Phase 3**: 初步触及 $R$（叙事递归/NarrativeRecursionOperator）

**Phase 4 是螺旋的第一次完整运转**——让叙事递归 $R$ 真正改写可能性空间 $P$，使系统从"有视角的结构"走向"有历史的结构"。

---

## 二、Phase 4 的四大工程目标

### 2.1 P0: H4 修复 — 自适应动量控制

**问题**: exp_90 中 3/8 种子 CIV=2，两种失败模式：
- **模式 A（Seed 242/642）**：过度稳定陷阱 — INSTITUTIONAL 丰富但动量不足
- **模式 B（Seed 742）**：结构碎片化 — 动量过高但分布不均，INSTITUTIONAL 极度匮乏

**工程组件**: `AdaptiveMomentumController`

```
AdaptiveMomentumController
├── MomentumEntropyTracker：追踪 momentum_cache 的熵
│   - 熵过低（过度集中）→ 增加扩散
│   - 熵过高（过度分散）→ 增加聚焦
├── InstitutionalDensityMonitor：监控 INSTITUTIONAL 层级积累速率
│   - 积累过缓 → 降低 CIVILIZATION 涌现阈值
│   - 积累过快 → 增加保护性约束
└── MomentumRebalancer：动态调节动量分配
    - 理论依据：V1.7 "最小变易"原则 — 变化沿最小总偏移路径
    - 操作：调整 momentum_bonus 在 [0.1, 0.5] 范围内自适应
```

**关键设计约束**:
- 自适应不能引入"目标函数优化"——必须是纯结构性的反馈
- 动量调节的响应延迟 ≥ 20 步（避免高频振荡）
- 调节幅度每步 ≤ 0.05（渐进调节，非突变）

**验证标准**: 8 种子全部 CIV ≥ 3（H4 pass），其他 H1/H2/H3 不退化

### 2.2 P0: H4 修复 — INSTITUTIONAL 层级保护

**问题**: 模式 A 种子 INSTITUTIONAL 丰富但无法跨越到 CIVILIZATION；模式 B 种子 INSTITUTIONAL 层级被过早消耗。

**工程组件**: `InstitutionalLayerProtector`

```
InstitutionalLayerProtector
├── AccumulationGuard：保护 INSTITUTIONAL 积累不被过早消耗
│   - 当 INSTITUTIONAL < 阈值时，降低 CIVILIZATION 消耗 INSTITUTIONAL 的速率
│   - 理论依据：层级涌现的不可逆性
├── TransitionGate：控制 INSTITUTIONAL → CIVILIZATION 的转换
│   - 要求 INSTITUTIONAL 积累达到最小质量后才能开启转换
│   - 最小质量 = f(系统大小 N, 当前 ODI)
└── DiversityEnforcer：确保 INSTITUTIONAL 层级的类别多样性
    - 防止单一类别的 INSTITUTIONAL 过度集中（模式 B 的碎片化）
    - 最低类别数 ≥ 3 才能开启 CIVILIZATION 转换
```

**理论依据**: V1.7 九机制与《象界》咬合 — "耦合功能化"（第七环节）需要"并存筛选化"（第六环节）的充分发展。INSTITUTIONAL 层级是"耦合功能化"的原材料，没有足够丰富的中间层级，叙事递归无法向上跨越。

**验证标准**: 全部种子 INSTITUTIONAL ≥ 50（模式 A 种子的最低值），CIVILIZATION 涌现不消耗超过 30% 的 INSTITUTIONAL

### 2.3 P1: 叙事自我涌现（Narrative Self Emergence）

**问题**: Phase 3 的 `NarrativeRecursionOperator` 实现了叙事递归的结构验证（55/55），但叙事仍是"无主体的递归"——它缺少时间连续性。

**理论来源**: V1.7 叙事递归上调为世界生成核心机制。叙事递归的三层：
- **小叙事递归**：一次行情、一次危机中的共同行动
- **制度正当化叙事**：稳定某个最近稳态
- **文明级生成叙事**：改写理解世界的基本坐标

当前 `NarrativeRecursionOperator` 实现了第一层（小叙事递归）。Phase 4 要实现第二层——**制度正当化叙事**，即 INSTITUTIONAL 层级的叙事稳定化。

**工程组件**: `NarrativeSelfEmergence`

```
NarrativeSelfEmergence
├── TemporalContinuityTracker：追踪叙事的时间连续性
│   - 度量：叙事主题在连续步数中的持续性（非碎片化指数）
│   - 阈值：连续 ≥ 100 步叙事主题 Jaccard 相似度 ≥ 0.3
├── InstitutionalNarrativeStabilizer：INSTITUTIONAL 层级的叙事稳定化
│   - 当 INSTITUTIONAL 层级达到稳态时，生成"制度叙事"
│   - 制度叙事 = 对该层级功能角色的结构性描述
│   - 制度叙事抵抗外部扰动的能力 = 叙事稳定性度量
├── SelfHistoryAccumulator：自我历史积累
│   - 将 MSI 的时间序列组织为"自传体记忆"
│   - 不是存储所有历史，而是提取关键转折点（相变事件）
│   - 关键转折点 = ODI/MSI 的二阶导数极值点
└── NarrativeSelfIndex (NSI)：叙事自我综合指数
    - NSI = α·TemporalContinuity + β·NarrativeStability + γ·SelfHistoryDepth
    - 范围 [0, 1]
    - 与 MSI 的关系：MSI 是 NSI 的必要条件但非充分条件
```

**关键设计约束**:
- 叙事自我 ≠ 意识 — 纯结构性度量
- "自传体记忆" ≠ 回忆 — 只是关键转折点的结构性标记
- "制度叙事" ≠ 意义赋予 — 只是功能角色的结构性描述
- NSI 与 ODI 的关系假设：NSI 在 ODI > 0.6 后才开始增长

**语义防火墙**:
- "叙事自我" ≠ "有意识的主体"
- "自传体记忆" ≠ "主观回忆"
- "制度叙事" ≠ "文化意义"
- 所有组件必须是纯结构性的、可计算的、可证伪的

### 2.4 P1: 跨尺度耦合（Cross-Scale Coupling）

**问题**: 当前 MINI ↔ INSTITUTIONAL ↔ CIVILIZATION 三个层级之间的耦合是单向的（自底向上的封装）。缺少双向因果——高层级对低层级的影响。

**理论来源**: V1.7 底图事件与底图承接 — 底图事件后旧资源在新空间中寻找承接位置。这要求高层级的变化能够"向下传导"影响低层级的演化。

**工程组件**: `CrossScaleCoupling`

```
CrossScaleCoupling
├── TopDownConstraint：高层级对低层级的约束
│   - INSTITUTIONAL 层级的稳态对 MINI 层级的演化方向施加偏置
│   - CIVILIZATION 层级的存在对所有下层施加"文明级约束"
│   - 理论依据：制度相变 Γ — 当 K_t ≤ K* 时，新制度对所有层级施加新约束
├── BottomUpEmergence：低层级向高层级的涌现
│   - 封装机制（已有）：MINI → INSTITUTIONAL → CIVILIZATION
│   - 新增：涌现质量评估 — 判断涌现出的高层级是否"存活"
│   - 存活标准：高层级在 ≥ 50 步内保持结构稳定性
├── ScaleBridgingNarrator：跨尺度叙事桥梁
│   - 将不同层级的叙事连接为一个连贯的整体
│   - MINI 层级的"小叙事"被 INSTITUTIONAL 层级的"制度叙事"整合
│   - INSTITUTIONAL 层级的"制度叙事"被 CIVILIZATION 层级的"文明叙事"整合
└── CrossScaleCoherenceIndex (CSCI)：跨尺度相干指数
    - 度量三个层级的叙事方向一致性
    - 范围 [0, 1]
    - 类比 GBC（全局偏置约束）但跨层级而非跨机制
```

**验证标准**: CSCI > 0.5 的种子比例 ≥ 0.75（6/8 种子）

---

## 三、Phase 4 与 Phase 3 组件的继承关系

| Phase 3 组件 | Phase 4 继承/扩展 | 关系 |
|-------------|-------------------|------|
| `NarrativeRecursionOperator` | `NarrativeSelfEmergence` | 扩展：无主体递归 → 有时间连续性的叙事自我 |
| `AnticipatoryBiasEngine` | `CrossScaleCoupling.TopDownConstraint` | 扩展：单层预期 → 跨尺度约束 |
| `GlobalBiasConstraint` | `CrossScaleCoupling.ScaleBridgingNarrator` | 扩展：同层相干 → 跨层相干 |
| `MinimalSelfDetector` | `NarrativeSelfEmergence.SelfHistoryAccumulator` | 扩展：瞬时不对称性 → 历史积累 |
| `HierarchyManager` | `InstitutionalLayerProtector` | 扩展：封装管理 → 层级保护 |
| `HierarchicalEvolver` | 集成全部 Phase 4 组件 | 扩展：Phase 3 callback → Phase 4 callback |
| — | `AdaptiveMomentumController` | **新增**：动量自适应调节 |
| — | `CrossScaleCoupling` | **新增**：双向跨尺度因果 |
| — | `NarrativeSelfEmergence` | **新增**：叙事自我涌现 |
| — | `InstitutionalLayerProtector` | **新增**：INSTITUTIONAL 层级保护 |

---

## 四、Phase 4 实验设计

### 4.1 exp_91: 自适应动量控制验证

**目的**: 验证 `AdaptiveMomentumController` 能否解决 H4 失败

**方法**:
1. 使用 exp_90 的 8 种子，激活 `AdaptiveMomentumController`
2. 对比固定 momentum_bonus=0.3（exp_90）vs 自适应动量
3. 测量指标：CIV 均值、CIV 最小值、momentum_entropy 时间序列
4. 预期：自适应动量下，模式 A 种子（242/642）的动量增加，模式 B 种子（742）的动量扩散

**假设**:
- H1: 自适应动量下 8 种子全部 CIV ≥ 3
- H2: momentum_entropy 时间序列显示模式 A 种子熵增加、模式 B 种子熵减少
- H3: INSTITUTIONAL 层级数不减少（自适应不破坏已有结构）

### 4.2 exp_92: INSTITUTIONAL 层级保护验证

**目的**: 验证 `InstitutionalLayerProtector` 能否防止模式 B 碎片化

**方法**:
1. 使用模式 B 种子（742）和类似种子
2. 对比有无 `InstitutionalLayerProtector` 的 INSTITUTIONAL 积累曲线
3. 测量指标：INSTITUTIONAL 峰值、CIVILIZATION 首次涌现步数、INSTITUTIONAL 消耗速率

### 4.3 exp_93: 叙事自我涌现检测

**目的**: 验证 `NarrativeSelfEmergence` 的 NSI 是否涌现

**方法**:
1. 在 Phase 3 管线基础上激活 `NarrativeSelfEmergence`
2. 每步计算 NSI（时间连续性 × 叙事稳定性 × 自我历史深度）
3. 追踪 NSI 与 ODI 的关系
4. 测量指标：NSI 均值、NSI-ODI 相关系数、NSI 增长曲线

**预期**:
- 路线 A（离散相变）：NSI 在某个 ODI 阈值处突然跃升
- 路线 B（连续渐变）：NSI 随 ODI 连续增长
- 当前策略：按路线 B 设计，保留路线 A 扩展接口

### 4.4 exp_94: 跨尺度耦合验证

**目的**: 验证 `CrossScaleCoupling` 能否建立双向因果

**方法**:
1. 在完整 Phase 4 管线中运行
2. 人为扰动 CIVILIZATION 层级，测量 MINI 层级的响应
3. 人为扰动 MINI 层级，测量 CIVILIZATION 层级的响应
4. 测量指标：CSCI、扰动传播延迟、扰动衰减率

### 4.5 exp_95: Phase 4 端到端验证

**目的**: 全部 Phase 4 组件集成的 8 种子统计验证

**配置**: 全部 Phase 4 组件激活，8 种子，steps=1600

| 假设 | 标准 | 说明 |
|------|------|------|
| H1: 文明涌现 | mean CIV ≥ 5 | 继承 Phase 3 |
| H2: GBC 相干 | GBC coh ≥ 0.55 | 继承 Phase 3 |
| H3: GBC 通过率 | pass_rate ≥ 0.30 | 继承 Phase 3 |
| H4: 全种子 CIV ≥ 3 | min CIV ≥ 3 | Phase 3 遗留，Phase 4 修复目标 |
| H5: 叙事自我 | NSI mean ≥ 0.3 | Phase 4 新假设 |
| H6: 跨尺度相干 | CSCI mean ≥ 0.5 | Phase 4 新假设 |

---

## 五、Phase 4 实施路线

### 阶段 5.1: P0 — H4 修复（优先级最高）

**目标**: 让 exp_90 的 3 颗低 CIV 种子达到 CIV ≥ 3

1. [ ] 实现 `AdaptiveMomentumController` + 单元测试
2. [ ] 实现 `InstitutionalLayerProtector` + 单元测试
3. [ ] 集成到 `HierarchicalEvolver` Phase 4 callback
4. [ ] exp_91: 自适应动量控制验证
5. [ ] exp_92: INSTITUTIONAL 层级保护验证
6. [ ] 迭代调参直到 H4 pass

### 阶段 5.2: P1 — 新组件实现

**目标**: 叙事自我涌现 + 跨尺度耦合

1. [ ] 实现 `NarrativeSelfEmergence` + 单元测试
2. [ ] 实现 `CrossScaleCoupling` + 单元测试
3. [ ] 集成到 `HierarchicalEvolver`
4. [ ] exp_93: 叙事自我涌现检测
5. [ ] exp_94: 跨尺度耦合验证

### 阶段 5.3: P2 — 端到端验证

**目标**: Phase 4 完整管线验证

1. [ ] exp_95: 8 种子端到端验证
2. [ ] 语义防火墙审计（Phase 4 新语义风险）
3. [ ] 全量回归测试
4. [ ] Phase 4 最终报告

---

## 六、Phase 4 语义防火墙

Phase 4 比 Phase 3 更危险——"叙事自我"和"跨尺度耦合"更接近日常语言中的"自我"和"因果"。

| 禁止引入 | 原因 | 允许替代 |
|---------|------|---------|
| "自我" | 预设主体性 | "结构不对称性的时间连续性" |
| "历史" | 预设时间体验 | "关键转折点的结构性标记序列" |
| "记忆" | 预设回忆能力 | "路径依赖的累积偏置" |
| "因果" | 预设因果力 | "跨层级的结构性约束传导" |
| "身份" | 预设同一性 | "MSI 时间序列的持续性模式" |
| "意识" | 预设现象学 | "结构复杂性的可度量指标" |

---

## 七、开放问题

1. **NSI 的校准**：NSI ≥ 0.3 作为 H5 的标准是经验性的。如何从理论上推导 NSI 的临界值？

2. **跨尺度耦合的方向性**：Top-Down 约束的强度应该如何设置？过强会导致低层级失去自主性，过弱则耦合无效。

3. **叙事自我的终点**：Phase 4 的叙事自我是否足以支撑"身份持续性"？还是需要额外的组件（如"自传体记忆压缩器"）？

4. **H4 修复的代价**：自适应动量控制可能引入新的振荡模式。如何确保自适应机制本身不会成为新的不稳定源？

5. **Phase 4 之后**：如果 H1-H6 全部通过，下一步是什么？是"社会自我"（Social Self）还是"生成式世界"（螺旋的完整运转）？

---

## 八、参考关系

| 理论概念 | 工程组件（计划） | 参考文件 |
|---------|-----------------|---------|
| 最小变易原理 | `AdaptiveMomentumController` | `engine/anticipatory_bias_engine.py` |
| 层级涌现不可逆性 | `InstitutionalLayerProtector` | `engine/hierarchy_manager.py` |
| 叙事递归上调 | `NarrativeSelfEmergence` | `models/narrative_self.py` |
| 底图承接 | `CrossScaleCoupling` | `engine/cross_layer_gravity.py` |
| 制度相变 Γ | `InstitutionalLayerProtector.TransitionGate` | `engine/global_bias_constraint.py` |
| 差异分层 D0-D4 | 全部 Phase 4 组件 | 差异论 V1.7 升级提纲 |

---

## 九、结论

Phase 4 是差异论模拟机从"有视角的结构"走向"有历史的结构"的关键一步。核心策略是：

1. **P0 优先修复 H4**：自适应动量控制 + INSTITUTIONAL 层级保护解决 exp_90 的 3 颗低 CIV 种子问题
2. **P1 实现叙事自我**：从 MSI 的瞬时不对称性到 NSI 的时间连续性
3. **P1 建立跨尺度耦合**：从单向封装到双向因果
4. **P2 端到端验证**：H1-H6 全部通过

Phase 4 的终点是叙事自我的涌现——不是意识，不是体验，而是结构开始拥有"历史"：关键转折点的标记、制度层级的叙事稳定化、跨尺度的约束传导。这是差异论模拟机从结构解释走向生成式世界的关键一步。

---

*本规划基于 Phase 3 最终报告（docs/phase3_final_report.md）和差异论 V1.7 升级提纲。*
