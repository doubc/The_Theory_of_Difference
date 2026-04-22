# 理论-代码偏差分析与修改路线图

> 基于《差异论 V1.6》逐章对照 price-structure 项目代码
> 初版: 2026-04-21 | P0 完成: 2026-04-22

---

## 一、对齐的部分

| 理论章节 | 命题 | 代码对应 | 状态 |
|----------|------|---------|------|
| Ch1 差异是成立条件 | 无差异则无世界 | `Point` — 一阶差分/对数差分定义最小可区分单位 | ✅ |
| 核心隐喻 | 系统 = 结构 × 运动 | `Structure` + `MotionState` | ✅ 本轮新增 |
| Ch2 聚簇与结构形成 | 共同反差驱动聚簇 | `Zone.context_contrast` + `_infer_contrast()` | ✅ P0 |
| Ch2 聚簇与结构形成 | 可叙事性 | `Structure.narrative_context` + `infer_narrative_context()` | ✅ P0 |
| Ch3 离散事件 | 变化是离散的，非连续流 | `Cycle` — entry/exit 离散定义 | ✅ |
| Ch3 最近稳态 | 阻力最小方向，最先可用 | `Cycle.next_stable` + `_find_nearest_stable()` | ✅ P0 |
| Ch4 守恒与转移 | 差异不能无代价清零 | `check_conservation()` 骨架 | ✅ P0(骨架) |
| Ch5 结构反过来约束差异 | 结构不只是结果，还重塑差异 | `Structure.invariants` 反向用于检索 | ✅ |
| Ch8 迁移的离散事件结构 | 阈值、锁定 | `pivots.py` — 摆动极值 = 阈值触发 | ✅ |
| Ch18 可能性空间分析 | 找有承接条件的分支 | `active_match.py` — 检索历史相似结构 | ✅ |

---

## 二、偏差清单（按严重度排序）

### ~~🔴 偏差 1：聚簇驱动力丢失——"共同反差"没有建模~~ ✅ 已修复 (P0)

**理论（Ch2 定义 2.2）**：

> 共同反差，是多个差异单元共同面对的外部差异，它为聚簇提供方向、压力和边界。

命题 2.3：能够形成结构的差异，通常同时具备可识别性、可利用性和**可叙事性**。

**代码现状**：`zones.py` 用纯价格聚类——"这些极值点价格相近，所以归为一个 zone"。完全不问"驱动它们聚拢的共同外部差异是什么"。

**后果**：2008 年金融危机低点和 2015 年产能过剩低点可能因为价格相近被聚为同一 zone，但驱动它们的共同反差完全不同（恐慌 vs 过剩）。理论上这两个不应该被归为同一个结构。

**修改方向**：→ ✅ 已实现
- `Zone` 增加 `context_contrast: ContrastType` + `contrast_label` 字段
- `_infer_contrast()` 函数：基于极值点时序密集度推断反差类型（恐慌/过剩/政策/流动性/投机）
- `detect_zones()` 集成反差推断
- `Structure` 增加 `narrative_context` 字段
- `infer_narrative_context()` 函数：生成人可读的结构叙事背景
- `structure_invariants()` 增加 `contrast_type` 字段

---

### ~~🔴 偏差 2：最近稳态完全缺失~~ ✅ 已修复 (P0)

**理论（Ch3 命题 3.4）**：

> 社会变化通常先沿阻力最小的方向发生，并首先停驻在一个最近的、能够暂时稳住局面的平衡点上。

命题 3.5：最近稳态的意义不在于它最优，而在于它最先可用。

Ch4 命题 4.4、Ch7 命题 7.6、Ch12 命题 12.6 反复回响。

**代码现状**：`Cycle` 只记录"进入 zone → 离开 zone"，不回答"离开之后去了哪里"。没有建模"下一个可承接的稳态"。

**后果**：active_match 只能说"历史上类似结构后续涨/跌了多少"，不能说"如果这个结构崩塌，最可能先滑向哪个最近稳态"。这恰恰是理论最强调的判断工具。

**修改方向**：→ ✅ 已实现
- `NearestStableState` dataclass：zone + arrival_point + duration + resistance_level
- `Cycle.next_stable: NearestStableState | None` 字段
- `_find_nearest_stable()` 函数：exit 后扫描后续段，两种判定：
  1. 终点触及已知 zone → 最近稳态
  2. 连续两段幅度递减 → 减速点 = 稳态候选
- `build_cycles()` 集成稳态检测
- `Structure.stable_state_ratio` 属性
- `structure_invariants()` 增加 `stable_state_ratio` + `avg_resistance_level`

---

### ~~🟡 偏差 3：差异守恒没有验证~~ ✅ 已修复 (P0骨架)

**理论（Ch4 定义 4.1）**：

> 社会守恒，不是差异数值的严格等量，而是差异不可能被无代价清零的结构性约束。

命题 4.2：差异被压缩时，最常见的命运不是消失，而是转移。

**代码现状**：只计算差异，不验证守恒。当一个 zone 的波动率被压平，不会检查差异是否转移到了其他维度。

**后果**：代码会误判"结构稳定了"——实际上差异可能只是被转移到了代码没观察的维度（比如成交量异动、更短周期的张力积累）。

**修改方向**：→ ✅ 已实现（骨架）
- `check_conservation()` 函数：三项检查
  1. 速度比变化显著 → 差异在转移
  2. Zone 带宽极窄 → 差异可能转移到短周期/成交量
  3. 稳态阻力异常低 → 假稳态，差异在隐性积累
- `compile_full()` 集成守恒检查到每个 Structure
- 完整实现需引入 volume/OI 低频数据（P1）

---

### 🟡 偏差 4：价格内三种差异没有分层

**理论（Ch13 命题 13.3）**：

> 价格之所以经常过头，不只是因为信息更新，而是因为时间差异、流动性差异和边界恐惧一起被压进了价格。

**代码现状**：`Bar` 只有 `open/high/low/close/volume`，编译器只看价格差异。不区分：
- **时间差异**：谁能等、谁不能等（无持仓时间/换手率/期限结构）
- **流动性差异**：能不能变成钱（volume 有但未被编译器使用）
- **边界恐惧**：怕被踢出局（完全没建模）

**后果**：代码把"差异密度极高的社会结构结果"简化成了"价格形态的几何分析"。理论说价格是差异显影，代码只显影了一层。

**修改方向**：→ ✅ 已实现 (P1)
- `Structure` 新增 `liquidity_stress`、`fear_index`、`time_compression` 字段
- `compute_liquidity_stress()`：Zone 内外成交量变异系数比 (D6.3)
- `compute_fear_index()`：跳空频率 + 波动率突变 + 试探密集度加权 (D6.4)
- `compute_time_compression()`：entry/exit duration 比值 (D6.2)
- `extract_pivots()` 新增 `volume_weighted` 模式：高成交量极值降低过滤阈值
- `SystemState` 封装三层差异分层

---

### 🟡 偏差 5：反身性缺失——管线是单向的

**理论（Ch14 命题 14.4）**：

> 方法失效的根本原因，不是市场突然无规律，而是方法在被广泛采用后，会逐步压缩支撑它有效的差异。

**代码现状**：整条管线是单向的——编译 → 规则匹配 → 检索 → 输出。没有"输出如何反过来改变被检索对象"的回路。

**修改方向**：→ 🔲 骨架完成 (P2)
- 新增 `src/reflexivity.py`：`ReflexivityTracker` + `RulePerformanceRecord`
- 支持规则匹配记录 → 实际结果回填 → 准确率衰减检测 → 权重建议
- 持久化到 `data/reflexivity/records.jsonl`
- 完整效果需长期运行积累数据

---

### 🟢 偏差 6：叙事递归没有追踪

**理论（Ch9 命题 9.4）**：叙事与现实是递归关系。

**代码现状**：`comparison_guide` 生成静态建议，规则是写死的，不会根据后续表现自我修正。

**修改方向**：
- `dsl/rule.py` 增加 `rule_performance_history`：每条规则匹配后，追踪被匹配结构的后续表现，统计规则的"准确率衰减"
- 当准确率衰减超过阈值时，自动降低该规则的权重或标记为"可能已失效"
- `comparison_guide` 增加："历史上给出类似指引后，市场实际走向与指引的偏差有多大"

---

### 🟢 偏差 7：跨周期交叉验证缺失

**理论（Ch12 命题 12.3）**：被压抑差异在更窄通道中积累更高密度。

**代码现状**：只在单一频率（日线）上编译，不交叉验证。

**修改方向**：
- `compile_full()` 增加 `multi_freq` 模式：同时编译日线和 5 分钟线的结构
- `detect_compressed_difference()` 函数：当日线 zone 的波动率低于阈值时，检查 5 分钟线是否出现了异常的张力积累
- `Structure` 增加 `cross_freq_signal: str` 字段

---

## 三、修改优先级与进度

按"理论核心性 × 实现可行性"排序：

| 优先级 | 偏差 | 状态 | 理由 |
|--------|------|------|------|
| **P0** | 偏差 2：最近稳态 | ✅ 完成 | 理论方法论核心，Ch3/4/7/12 反复回响 |
| **P0** | 偏差 1：共同反差 | ✅ 完成 | 聚簇驱动力，决定 zone 质量 |
| **P0** | 偏差 3：守恒验证 | ✅ 骨架完成 | 防止误判"结构稳定" |
| **P1** | 偏差 4：三种差异分层 | ✅ 完成 | liquidity_stress + fear_index + time_compression + volume_weighted pivots |
| **P1** | 错觉检测 (D7.2) | ✅ 完成 | StabilityVerdict 红绿灯机制 |
| **P1** | SystemState (D9.1) | ✅ 完成 | Structure × Motion 顶层封装 |
| **P1** | 叙事化输出 | ✅ 完成 | narrative.py 生成自然语言报告 |
| **P1** | 检索反差过滤 | ✅ 完成 | context_contrast 作为首要过滤条件 + 匹配归因 |
| **P1** | 守恒完整版 | 🔲 待做 | 需多频率数据交叉 |
| **P2** | 偏差 5：反身性 | 🔲 骨架完成 | ReflexivityTracker + 衰减检测 |
| **P3** | 偏差 6：叙事递归 | 🔲 待做 | 需大量样本积累 |
| **P3** | 偏差 7：跨周期 | 🔲 待做 | 数据工程量大 |

---

## 四、P0 修改清单（2026-04-22）

### 修改的文件

| 文件 | 修改内容 |
|------|---------|
| `src/models.py` | 新增 `ContrastType` 枚举、`NearestStableState` 数据类；`Zone` 增加 `context_contrast`/`contrast_label`；`Cycle` 增加 `next_stable`；`Structure` 增加 `narrative_context`/`stable_state_ratio` |
| `src/compiler/zones.py` | 新增 `_infer_contrast()` 函数；`detect_zones()` 集成反差推断 |
| `src/compiler/cycles.py` | 新增 `_find_nearest_stable()` 函数；`build_cycles()` 集成最近稳态检测 |
| `src/compiler/pipeline.py` | `compile_full()` 增加叙事上下文推断 + 守恒检查 |
| `src/relations.py` | 新增 `infer_narrative_context()`、`check_conservation()` 函数；`structure_invariants()` 增加稳定态/反差字段 |

### 新增的理论对应

| V1.6 理论 | 命题 | 代码实现 |
|-----------|------|---------|
| Ch2 定义 2.2 共同反差 | 多个差异单元共同面对的外部差异 | `Zone.context_contrast` + `_infer_contrast()` |
| Ch2 命题 2.3 可叙事性 | 差异能被讲出来才持久 | `Structure.narrative_context` + `infer_narrative_context()` |
| Ch3 命题 3.4 最小变易 | 变化沿阻力最小方向 | `_find_nearest_stable()` — 从 exit 段扫描最近停驻点 |
| Ch3 命题 3.5 最近稳态 | 不是最优而是最先可用 | `NearestStableState.resistance_level` |
| Ch4 命题 4.1 守恒 | 差异不能无代价清零 | `check_conservation()` — 波动率转移检测 |
| Ch4 命题 4.2 转移 | 压缩后沿低阻通道走 | `check_conservation().transfer_channels` |

---

## 五、下一步（P1）

1. **偏差 4 分层**：引入 volume 数据 → `extract_pivots()` 增加 `volume_weighted` 模式
2. **守恒完整版**：接入 MySQL 5 分钟线数据 → 跨频率守恒验证
3. **active_match.py** 更新：comparison_guide 增加最近稳态分析

---

## 六、工作记录

### 2026-04-21
1. 同步 GitHub 仓库到本地
2. 落地阶段三整改意见（similarity.py 对齐 invariant keys、pivots.py 容错、config.yaml 字段对齐）
3. 重写 daily_scan.py（委托 opportunity + daily_report 模块）
4. 新增主动匹配功能（active_match）
5. CU0 2025-04~2026-04 测试通过
6. 推送到 GitHub（commit 13004d1）
7. 深入阅读差异论 V1.6，完成理论-代码偏差分析

### 2026-04-22
1. P0 修改完成：
   - 最近稳态检测（`NearestStableState` + `_find_nearest_stable()`）
   - 共同反差推断（`ContrastType` + `_infer_contrast()`）
   - 叙事上下文推断（`infer_narrative_context()`）
   - 守恒检查骨架（`check_conservation()`）
   - 文档更新
2. P1 修改完成（外部审校意见驱动升级）：
   - **模型层**：新增 `StabilityVerdict`（错觉检测红绿灯）、`SystemState`（系统态=结构×运动）、`Structure` 增加 `liquidity_stress`/`fear_index`/`time_compression`
   - **算子层**：新增 `compute_liquidity_stress()` (D6.3)、`compute_fear_index()` (D6.4)、`compute_time_compression()` (D6.2)、`detect_stability_illusion()` (D7.2)、`build_system_state()` (D9.1)
   - **编译器层**：`extract_pivots()` 新增 `volume_weighted` 模式；`compile_full()` 集成 SystemState 构建
   - **检索层**：`RetrievalEngine` 以 `context_contrast` 为首要过滤器；匹配结果附带归因解释
   - **叙事层**：新增 `src/narrative.py`——自然语言诊断报告、每日摘要、匹配归因解释
   - **反身性**：新增 `src/reflexivity.py`——`ReflexivityTracker` 骨架，规则准确率衰减检测
   - 全部 73 个测试通过
