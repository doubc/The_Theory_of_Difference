# 第二阶段设计文档：从象界底象到前主体态

> **版本**: draft v0.1  
> **日期**: 2026-05-25  
> **状态**: 设计草稿，待评审  
> **依据**: 《象界》八章生成链 + 《Appearing Before Appearing》六阈值框架

---

## 一、阶段定位

### 1.1 在四书体系中的位置

```
WorldBase (差异之基) → 差异即世界 (总链条) → 象界 (中层显现) → 差异论 (历史世界)
                                              ↑
                                         第二阶段覆盖范围
```

- **起点**: 象界底象 — 差异跨过组织门槛，从被动分布转为可追踪状态
- **终点**: 前主体态 — 六机制耦合收束为可承受高语义加载的组织整体
- **核心任务**: 完成从"差异发生"到"差异组织"的完整生成链

### 1.2 与M4（第一阶段）的关系

| 维度 | M4（已完成） | 第二阶段（待实现） |
|------|-------------|-----------------|
| 检测维度 | 引力势 + 汉明距离（2维） | 六阈值同步检测（6维） |
| 偏置机制 | BiasField（同步、当下） | PersistentBiasMemory（历史累积） |
| 复制逻辑 | 模式重建（追求相似度） | 关键关系保真（允许细节偏差） |
| 筛选机制 | 单次跃迁判断 | 累积窗口 + 多次保留趋势 |
| 功能分化 | 静态分配 | 动态调整 + 贡献不对称追踪 |
| 回流通道 | 单向（高层→低层） | 双向闭环 + 解封机制 |

---

## 二、八章生成链 → 工程组件映射

### 2.1 完整映射表

| 章 | 转化方向 | 核心门槛 | 工程组件 | 状态 |
|---|---------|---------|---------|------|
| 1 | 存在 → 底象 | 差异跨过组织门槛 | `XiàngDetector`（底象检测器） | 🔴 未实现 |
| 2 | 分隔 → 界面 | 边界转为选择性交换接口 | `EncapsulationEngine`（已有）→ 增强 | 🟡 需增强 |
| 3 | 闭合 → 自维持 | 循环在开放中重建自身 | `SelfSustainingCirculation` | 🔴 未实现 |
| 4 | 痕迹 → 记忆 | 痕迹转为可调用概率偏置 | `PersistentBiasMemory` | 🔴 未实现 |
| 5 | 再现 → 复制 | 模式转为内部支撑延续 | `ReplicatePattern`（已有）→ 增强 | 🟡 需增强 |
| 6 | 并存 → 筛选 | 多样式转为延续概率分流 | `CumulativeSelector` | 🔴 未实现 |
| 7 | 耦合 → 功能 | 内部关系形成不对称地位 | `FunctionalDifferentiation` | 🔴 未实现 |
| 8 | 前主体态 | 六机制耦合收束 | `PreSubjectivityConvergence` | 🔴 未实现 |

### 2.2 组件优先级排序

**P0（必须先实现，构成最小闭环）**:
1. `XiàngDetector` — 底象检测是起点，没有它后续无从谈起
2. `PersistentBiasMemory` — 记忆是"历史进入结构"的关键，是前主体态的必要条件
3. `CumulativeSelector` — 筛选的累积逻辑是区分"偶然"与"趋势"的核心

**P1（增强已有组件）**:
4. `EncapsulationEngine` 增强 — 增加界面调节度指标
5. `ReplicatePattern` 增强 — 从"完全复制"改为"关键关系保真"

**P2（完整闭环）**:
6. `SelfSustainingCirculation` — 自维持能力
7. `FunctionalDifferentiation` — 动态功能分化
8. `PreSubjectivityConvergence` — 六机制收束判定

---

## 三、核心组件设计

### 3.1 XiàngDetector — 底象检测器

**职责**: 检测差异是否跨过组织门槛，从被动分布转为可追踪状态。

**输入**:
- 当前层的差异分布矩阵 `D ∈ ℝ^{n×n}`
- 组织密度阈值 `ρ_threshold`
- 状态可追踪性指标 `T`（基于差异轨迹的连续性）

**输出**:
- `xiàng_formed: bool` — 是否形成底象
- `organization_density: float` — 当前组织密度
- `traceability_score: float` — 可追踪性评分

**算法逻辑**:
```
1. 计算局部差异梯度 ∇D
2. 统计梯度超过阈值的区域占比 → organization_density
3. 追踪差异轨迹的连续性（连续N步保持组织结构的概率）→ traceability_score
4. 当 organization_density > ρ_threshold 且 traceability_score > τ 时，判定底象形成
```

**与M4的区别**: M4的层级跃迁检测基于引力势和汉明距离，是"结果导向"的；底象检测是"过程导向"的，关注差异本身是否开始"留下自身"。

---

### 3.2 PersistentBiasMemory — 历史累积偏置记忆

**职责**: 记录路径偏置的历史累积，使过去通过结构对未来施加持续限制。

**设计原则**:
- 不是单次偏置，而是"跨多次重构连续偏置"
- 偏置携带时间衰减因子，但核心结构偏置可长期保留
- 支持偏置的"冻结"与"解冻"（对应解封机制）

**数据结构**:
```python
class PersistentBiasMemory:
    # 偏置条目
    entries: List[BiasEntry]  # 按时间排序
    
    # 累积偏置场（当前生效的）
    current_accumulated: BiasField
    
    # 偏置历史（用于回溯和解封）
    history: Deque[BiasFieldSnapshot]
    
    # 配置
    max_history_depth: int      # 历史保留深度
    decay_rate: float           # 时间衰减率
    freeze_threshold: float     # 偏置强度超过此值则冻结
```

**核心方法**:
- `record(path: Path, bias: BiasField, timestamp: int)`: 记录一次偏置
- `get_accumulated() -> BiasField`: 获取当前累积偏置
- `freeze(entry_id: str)`: 冻结某条偏置（使其不受衰减影响）
- `unseal(entry_id: str) -> BiasField`: 解封被冻结的偏置，返回其偏置场
- `get_historical(depth: int) -> List[BiasField]`: 获取历史偏置序列

**与现有 BiasField 的关系**:
- `BiasField` 是同步的、当下的偏置传播
- `PersistentBiasMemory` 是异步的、历史的偏置累积
- 两者通过 `apply_bias()` 接口统一：当前偏置 = 同步偏置 + 历史累积偏置

---

### 3.3 CumulativeSelector — 累积筛选器

**职责**: 追踪多次展开中的延续概率差异，区分"偶然保留"与"趋势形成"。

**核心洞见**: "一次保留未必构成趋势，多次保留才会形成偏向。"

**设计**:
```python
class CumulativeSelector:
    # 候选变体的延续记录
    continuation_history: Dict[VariantID, List[bool]]  # 每次展开是否被保留
    
    # 累积窗口大小
    window_size: int
    
    # 趋势判定阈值
    trend_threshold: float  # 保留频率超过此值判定为趋势
    
    # 命运分岔记录
    fate_branches: Dict[VariantID, float]  # 累积延续概率
```

**核心方法**:
- `record_continuation(variant_id: VariantID, retained: bool)`: 记录一次延续结果
- `get_trend(variant_id: VariantID) -> Optional[float]`: 获取某变体的趋势评分（最近window_size次的保留频率）
- `is_trend_forming(variant_id: VariantID) -> bool`: 是否已形成趋势
- `get_fate_divergence() -> Dict[VariantID, float]`: 获取所有变体的命运分岔（累积延续概率差异）

---

### 3.4 SixThresholdDetector — 六阈值检测器

**职责**: 同步检测六个结构阈值，判定是否跨越"象界"进入前主体态。

**六个阈值**（来自《Appearing Before Appearing》）:

| 阈值 | 指标 | 计算方式 | 阈值判定 |
|------|------|---------|---------|
| 3.1 界面调节度 | 封装边界的活跃交换比例 | `active_exchanges / total_boundary_edges` | > τ₁ |
| 3.2 自维持稳健性 | 扰动后重建成功率 | `rebuild_success_count / perturbation_count` | > τ₂ |
| 3.3 保持深度 | 偏置场的递归调用层数 | `max(recursion_depth for bias in memory)` | > τ₃ |
| 3.4 复制保真度 | 跨实例模式重建的相似度 | `structural_similarity(current, replicated)` | > τ₄ |
| 3.5 选择压力 | 组织变体的延续概率差异 | `max_prob - min_prob`（归一化） | > τ₅ |
| 3.6 功能分化指数 | 内部组件贡献不对称度 | `GiniCoefficient(component_contributions)` | > τ₆ |

**判定逻辑**:
```
六阈值必须同时收敛（AND关系，不是OR）
→ 任一阈值未达标，则未跨越象界
→ 全部达标，进入前主体态判定
```

---

### 3.5 PreSubjectivityConvergence — 前主体态收束判定

**职责**: 判定六机制是否已耦合收束为可承受高语义加载的组织整体。

**收束条件**:
1. 六阈值全部达标（SixThresholdDetector通过）
2. 各机制之间的耦合强度超过阈值（相互依赖度）
3. 组织整体的稳定性（在扰动下保持结构的能力）
4. 语义加载测试：注入高语义扰动后，结构不发生崩塌

**语义防火墙**（严格克制）:
> 前主体态不是主体，却是差异结构在低语义层中所能达到的最充分完成形态。

工程上必须确保：
- 不引入"身份"概念（只有边界，没有身份）
- 不引入"意志"概念（只有自维持，没有意志）
- 不引入"回忆"概念（只有保持，没有回忆）
- 不引入"自我表征"概念（只有复制，没有自我表征）
- 不引入"评价"概念（只有选择，没有评价）
- 不引入"意义赋予"概念（只有功能，没有意义）

---

## 四、解封机制与回流通道

### 4.1 解封机制

**背景**: M4已完成单向回流（高层→低层），但缺乏"解封"能力 — 即被冻结的历史偏置如何重新激活。

**设计**:
```
解封触发条件:
1. 当前层遇到无法解释的差异模式（"异常"检测）
2. 高层语义注入导致低层结构失稳
3. 显式请求（外部干预）

解封流程:
1. 从 PersistentBiasMemory 中检索相关历史偏置
2. 评估偏置与当前差异模式的匹配度
3. 匹配度超过阈值 → 解冻并注入当前偏置场
4. 记录解封事件（用于后续分析）
```

### 4.2 双向偏置回路

```
高层 ←── propagate_bias_up ──→ 低层
  ↑                              ↓
  └── unseal + propagate_bias_down ──┘
```

- `propagate_bias_up`: 低层结构特征向高层聚合（已有）
- `propagate_bias_down`: 高层偏置向低层传播（已有）
- `unseal`: 解封历史偏置并注入回路（新增）

---

## 五、实施路线

### 阶段 5.1: 最小闭环（P0组件）
- [ ] `XiàngDetector` 实现 + 单元测试
- [ ] `PersistentBiasMemory` 实现 + 与现有 `BiasField` 的集成
- [ ] `CumulativeSelector` 实现 + 单元测试
- [ ] 集成测试：底象 → 记忆 → 筛选 的完整链路

### 阶段 5.2: 增强已有组件（P1组件）
- [ ] `EncapsulationEngine` 增加界面调节度指标
- [ ] `ReplicatePattern` 改为"关键关系保真"模式
- [ ] 回归测试：确保M4已有功能不受影响

### 阶段 5.3: 完整闭环（P2组件）
- [ ] `SelfSustainingCirculation` 实现
- [ ] `FunctionalDifferentiation` 实现
- [ ] `SixThresholdDetector` 实现
- [ ] `PreSubjectivityConvergence` 判定逻辑
- [ ] 解封机制 + 双向回流完整链路

### 阶段 5.4: 端到端验证
- [ ] 端到端实验：从底象到前主体态的完整生成链
- [ ] 语义防火墙验证：确保无高语义词汇提前污染
- [ ] 性能测试：六阈值同步检测的计算开销

---

## 六、开放问题

1. **第七阈值是否存在?** — 《Appearing Before Appearing》5.4节提出：从"前主体态"到"最小自我"是否需要第七个结构阈值？这决定第三阶段（主体性涌现）的架构开放程度。

2. **"关键关系"的形式化定义** — 第五章要求复制时保留"关键关系"而非所有细节。工程上如何定义"关键关系"？是基于结构同构？功能等价？还是其他标准？

3. **时间尺度问题** — 历史累积偏置的时间尺度如何设定？不同的时间尺度会导致不同的前主体态形态。

4. **六阈值的阈值参数** — τ₁~τ₆ 的具体数值如何确定？是通过实验调参？理论推导？还是自适应学习？

---

## 七、参考文献

1. 《象界》— 八章生成链完整展开
2. 《Appearing Before Appearing: A Structural Account of Pre-Phenomenal Manifestation》— 六阈值框架
3. 《传统理论与差异论对照研究》— 多维度底图重排检测逻辑
4. M4 批次11 工程实现 — `hierarchy_manager.py`, `encapsulation_engine.py`, `bias_field` 相关代码
