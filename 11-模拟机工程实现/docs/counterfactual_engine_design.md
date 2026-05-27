# CounterfactualEngine 设计文档

> **版本**: v0.1
> **日期**: 2026-05-28
> **状态**: 设计草稿 — 待实现
> **前置**: Phase 3 P0 (MinimalSelfDetector) ✅, P1 (AnticipatoryBiasEngine) ✅
> **理论依据**: 《差异论》高语义层 + 《象界》第五、六章 + ABA §4.4

---

## 一、核心定位

### 1.1 理论来源

反事实推理（Counterfactual Reasoning）在差异论中的根基：

- **《象界》第五章（再现→复制）**：结构能够再现已有的差异模式
- **《象界》第六章（并存→筛选）**：多种样式在延续中命运分岔
- **《差异论》高语义层**：当结构能够维持多个并行的差异轨迹，并比较它们的后果时，"反事实"就涌现了

### 1.2 与 Phase 2 的区别

| Phase 2 | Phase 3 |
|---------|---------|
| `CumulativeSelector`：追踪**实际发生**的延续概率 | `CounterfactualEngine`：维持**未发生但可能发生**的差异轨迹 |
| 事实性：记录已实现的路径 | 反事实性：探索未实现的路径 |
| 单一轨迹 | 并行轨迹（受计算资源约束） |

### 1.3 工程定义

反事实推理 = 结构对自身可能路径的系统性探索。

**关键约束**：
- 反事实不是"想象"，而是结构对自身可能路径的系统性探索
- 并行轨迹的数量必须有限（受计算资源约束）
- 反事实筛选不能引入"价值判断"——它只是结构对延续概率差异的敏感性
- 语义防火墙：禁止"假设"、"想象"、"可能世界"、"替代现实"等高语义词汇

---

## 二、组件架构

```
CounterfactualEngine（反事实引擎）
├── ParallelTrajectoryMaintainer：并行轨迹维持器
│   ├── TrajectoryNode：轨迹节点
│   ├── TrajectoryBranch：轨迹分支
│   └── TrajectoryState：轨迹状态枚举
├── DivergencePointTracker：分岔点追踪器
│   ├── DivergencePoint：分岔点
│   └── DivergenceType：分岔类型
├── ConsequenceProjector：后果投影器
│   ├── ConsequenceEstimate：后果估计
│   └── ProjectionMethod：投影方法
├── CounterfactualSelector：反事实筛选器
│   ├── ContrastResult：对比结果
│   └── SelectionPressure：选择压力
└── CounterfactualResult：综合结果
```

---

## 三、详细设计

### 3.1 ParallelTrajectoryMaintainer（并行轨迹维持器）

**职责**：维持 K 条并行的差异轨迹，每条轨迹代表一种可能的差异演化路径。

**核心概念**：
- `TrajectoryNode`：单个时间步的状态快照（差异向量 + 时间戳 + 父节点引用）
- `TrajectoryBranch`：从根到叶的完整路径（节点列表 + 累积概率 + 状态）
- `TrajectoryState`：轨迹状态（ACTIVE / PRUNED / MERGED / COMPLETED）

**关键参数**：
- `max_branches` (K=5)：最大并行轨迹数
- `max_depth` (D=10)：最大轨迹深度
- `prune_threshold` (0.1)：低于此概率的轨迹被剪枝
- `merge_similarity` (0.95)：余弦相似度高于此值的轨迹合并

**生命周期**：
1. **创建**：在分岔点创建新轨迹分支
2. **延伸**：每步根据差异更新延伸所有活跃轨迹
3. **剪枝**：概率过低的轨迹被剪枝
4. **合并**：过于相似的轨迹被合并
5. **完成**：达到最大深度或结构收敛时完成

### 3.2 DivergencePointTracker（分岔点追踪器）

**职责**：追踪差异演化中的分岔点——即结构面临多个可能下一步的位置。

**分岔类型**：
- `STOCHASTIC`：随机分岔（噪声驱动）
- `STRUCTURAL`：结构分岔（内部状态驱动）
- `EXTERNAL`：外部分岔（环境变化驱动）
- `COUNTERFACTUAL`：反事实分岔（引擎主动创建）

**检测逻辑**：
- 当差异向量的下一步方向有多个局部最优时，检测到分岔点
- 分岔强度 = 各方向概率的熵
- 分岔显著性 = 最优方向与次优方向的概率比

### 3.3 ConsequenceProjector（后果投影器）

**职责**：将每条轨迹投影到未来，估计其后果（对结构延续的影响）。

**投影方法**：
1. `LINEAR`：线性投影（假设差异匀速变化）
2. `MOMENTUM`：动量投影（假设差异有惯性）
3. `STRUCTURAL`：结构投影（基于结构约束的投影）

**后果估计**：
- `continuation_probability`：轨迹的延续概率
- `structural_impact`：对整体结构的影响
- `density_impact`：对 ODI 的影响
- `coupling_impact`：对层间耦合的影响

### 3.4 CounterfactualSelector（反事实筛选器）

**职责**：比较事实轨迹与反事实轨迹，计算选择压力。

**核心算法**：
1. 计算每条反事实轨迹与事实轨迹的差异度
2. 计算每条反事实轨迹的延续概率
3. 选择压力 = 反事实轨迹与事实轨迹的延续概率差
4. 反事实偏置 = 选择压力加权的方向向量

**输出**：
- `ContrastResult`：事实 vs 反事实的对比结果
- `SelectionPressure`：选择压力（标量 + 方向）
- `CounterfactualBias`：反事实偏置向量

### 3.5 CounterfactualEngine（主体引擎）

**职责**：协调四个子组件，提供统一的 predict/update 接口。

**工作流程**：
1. `explore()`：在当前位置探索可能的分岔
2. `maintain()`：维持所有活跃轨迹
3. `project()`：投影所有轨迹的后果
4. `select()`：比较事实与反事实，生成偏置
5. `update()`：用实际差异更新轨迹状态

**ODI 门控**：
- ODI < 0.4：反事实探索被完全抑制
- 0.4 <= ODI < 0.6：部分抑制（减少并行轨迹数）
- ODI >= 0.6：正常运行

---

## 四、语义防火墙

| 禁止引入 | 原因 | 允许替代 |
|---------|------|---------|
| "假设" | 预设认知主体 | "并行轨迹探索" |
| "想象" | 预设心理活动 | "差异路径维持" |
| "可能世界" | 预设模态逻辑 | "并行差异轨迹" |
| "替代现实" | 预设形而上学 | "未实现的差异路径" |
| "如果...会怎样" | 预设反事实条件句 | "分岔点轨迹投影" |
| "选择" | 预设意志 | "延续概率差异的敏感性" |

---

## 五、与现有组件的集成

| 现有组件 | 集成方式 |
|---------|---------|
| `CumulativeSelector` | 反事实筛选器继承其延续概率计算逻辑 |
| `PersistentBiasMemory` | 反事实偏置写入偏置记忆 |
| `AnticipatoryBiasEngine` | 反事实偏置与预期偏置叠加 |
| `OrganizationalDensityIndex` | 后果投影考虑密度影响 |
| `HierarchicalEvolver` | Phase 3 callback 集成 |

---

## 六、测试计划

### 6.1 单元测试（~30 个）
- TrajectoryNode / TrajectoryBranch 基本操作
- ParallelTrajectoryMaintainer：创建/延伸/剪枝/合并
- DivergencePointTracker：分岔检测/分类
- ConsequenceProjector：三种投影方法
- CounterfactualSelector：对比/选择压力计算

### 6.2 集成测试（~10 个）
- 完整 explore→maintain→project→select 流程
- 与 CumulativeSelector 的协同
- ODI 门控行为
- 并行轨迹数量限制
- 轨迹剪枝和合并

### 6.3 端到端测试（~5 个）
- 在 HierarchicalEvolver Phase 3 callback 中的集成
- 反事实偏置对结构演化的影响
- 与 AnticipatoryBiasEngine 的协同

---

## 七、实现优先级

1. **P0**：ParallelTrajectoryMaintainer + 基础数据结构
2. **P1**：DivergencePointTracker + ConsequenceProjector
3. **P2**：CounterfactualSelector + CounterfactualEngine 主体
4. **P3**：集成到 HierarchicalEvolver + 端到端测试
