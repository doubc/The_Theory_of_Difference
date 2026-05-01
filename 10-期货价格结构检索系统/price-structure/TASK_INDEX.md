# 价格结构检索系统 — 任务索引

**目标**：构建5层"结构雷达"全景展示+筛选系统

**分工**：🤖 我（助理）负责打勾和更新状态，💻 mi-mo 负责写代码

---

## 当前进度总览

| 阶段 | 完成度 | 状态 |
|------|--------|------|
| Phase 0 — Bug修复 | ✅ 4/4 | **已完成** |
| Phase 1 — 字段链路打通 | ✅ 5/5 | **已完成** |
| Phase 2 — 展示增强 | ✅ 5/5 | **已完成** |
| Phase 3 — 全景展示 | ✅ 5/5 | **已完成** |
| Phase 4 — 交互升级 | ✅ 4/4 | **已完成** |
| Phase 5 — 数据层优化 | ✅ 4/4 | **已完成** |
| Phase 6 — 可视化升级 | ✅ 3/3 | **已完成** |
| Phase 7 — 知识图谱 | ✅ 6/6 | **已完成** |
| Phase 8 — 知识层(L1/L2/L3) | ✅ 5/5 | **已完成** |

---

## Phase 0 — Bug修复（阻断性问题）✅ 已完成

| # | 任务 | 状态 | 验证结果 |
|---|------|------|----------|
| 0-1 | compile_structures 返回值顺序 | ✅ | 当前代码 `sym_result, sym_bars = ...` 正确 |
| 0-2 | 历史日志字段名不一致 (similarity) | ✅ | 当前代码 `c["score"].total` 正确 |
| 0-3 | signal_score placeholder | ✅ | 当前代码 `qa.score` 正确 |
| 0-4 | 运动阶段枚举统一 (breakdown) | ✅ | 当前代码 `motion_map` 映射正确 |

---

## Phase 1 — 字段链路打通（Data → UI）✅ 已完成

**目标**：5个字段全部打通，为后续筛选和排序做准备

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 1-1 | session_state 持久化完整结果 | ✅ | `scan_results_full` 存储完整 `dashboard_data` |
| 1-2 | price_position_code 字段 | ✅ | H/M/L/S 四级 |
| 1-3 | phase_code 字段 | ✅ | breakout/confirmation/forming/stable/breakdown |
| 1-4 | sector 字段加载 | ✅ | `get_sector()` 函数，symbol_meta.yaml 驱动 |
| 1-5 | priority_score 字段 | ✅ | 综合排序分数（0-100）|

---

## Phase 2 — 展示增强（筛选器 + 排序 + 分页）✅ 已完成

**目标**：增加5个筛选器，重构分页逻辑，让筛选器从 session_state 读取数据。

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 2-1 | priority_score 综合排序 | ✅ | 默认排序改为 priority_score 降序 |
| 2-2 | 价格位置筛选器 | ✅ | 全部/高位/中位/低位/过期 |
| 2-3 | 运动阶段筛选器 | ✅ | phase_code 字段筛选 |
| 2-4 | sector 板块筛选器 | ✅ | 5大板块筛选 |
| 2-5 | 分页增强 | ✅ | 筛选面板外移，从 session_state 读取 |

---

## Phase 3 — 全景展示 ✅ 已完成

**目标**：5层结构雷达——板块热度图 → 机会队列 → 合约详情 → 观察池 → 自选提醒

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 3-1 | 板块热度图 | ✅ | 按 sector 分组，情绪卡片（偏多/偏空/分歧） |
| 3-2 | 机会队列 | ✅ | 按板块分组 top3 优先级合约 |
| 3-3 | 合约详情面板增强 | ✅ | 3列布局 + priority_score 构成分解 |
| 3-4 | 观察池 | ✅ | session_state + 文件持久化，添加/删除/清空 |
| 3-5 | 自选提醒 | ✅ | 阶段变化提醒 + 价格远离稳态提醒 |

---

## Phase 4 — 交互升级 ✅ 已完成

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 4-1 | 信号详情展示 | ✅ | 突破确认/假突破/回踩确认/结构失效/盲区突破 5种信号 |
| 4-2 | 假突破模式判定 | ✅ | 6种假突破模式：探针/单K极端/量能背离/盲区抽鞭/跳空回补/影线簇 |
| 4-3 | 风险管理指标 | ✅ | 入场价/止损/目标/盈亏比/仓位系数 |
| 4-4 | 精细检索条件 | ✅ | 日期范围/价位/方向/反差/运动态/相似度/排序方式 |

---

## Phase 5 — 数据层优化 ✅ 已完成

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 5-1 | 数据本地化 (Parquet) | ✅ | `local_store.py`：列式压缩，读取快 10x+ |
| 5-2 | 批量抓取 | ✅ | `batch_fetcher.py`：65+ 合约并发抓取，增量更新 |
| 5-3 | 活动日志 | ✅ | `ActivityLog` 类（JSONL 格式） |
| 5-4 | 新浪数据源 | ✅ | `sina_fetcher.py`：国内期货/外盘/外汇三种数据源 |

---

## Phase 6 — 可视化升级 ✅ 已完成

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 6-1 | C 扩展加速 | ✅ | `_pivots.c` 24x / `_dtw.c` 132x / `_compiler.c` 132x |
| 6-2 | 多时间维度对比 | ✅ | `multitimeframe/comparator.py`：5min vs 日线跨尺度一致性 |
| 6-3 | 全市场扫描优化 | ✅ | 成交量筛选 + 30min TTL 缓存 + 排序优化 |

---

## Phase 7 — 知识图谱 ✅ 已完成

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 7-1 | GraphStore 持久化 | ✅ | JSONL append-only + 派生索引 + 每日快照 |
| 7-2 | 结构演化链 | ✅ | `StructureGraph`：结构/Zone/叙事/规则节点 + 11种边类型 |
| 7-3 | 叙事递归追踪 | ✅ | `NarrativeRecursionTracker`：漂移率 + 锁定检测 |
| 7-4 | 反身性闭环检测 | ✅ | `ReflexivityDetector`：模板衰减 + 闭环检测 |
| 7-5 | 跨品种传导网络 | ✅ | `TransferNetwork`：差异转移 + 热力矩阵 |
| 7-6 | 多品种知识配置 | ✅ | `config/products/`：7品种 + ProductKnowledgeIngester |

---

## Phase 8 — 知识层（L1/L2/L3）✅ 已完成

**目标**：三层知识注入系统——判定知识/失效知识/市场智慧

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 8-1 | L1 判定知识 YAML | ✅ | `knowledge/L1_conditions.yaml`：8条规则 |
| 8-2 | L2 失效知识 YAML | ✅ | `knowledge/L2_invalidation.yaml`：7条规则 |
| 8-3 | L3 市场知识 YAML | ✅ | `knowledge/L3_wisdom.yaml`：12条规则 |
| 8-4 | KnowledgeEngine 引擎 | ✅ | `src/knowledge/engine.py`：YAML 加载 + 条件匹配 |
| 8-5 | 知识增强质量评估 | ✅ | `src/quality.py`：第6维度「知识置信度」|

---

## 设计参考

### sector 映射（symbol_meta.yaml）
```yaml
黑色金属: rb, hc, j, i, jm
有色金属: cu, al, zn, ni, sn
能源化工: sc, bu, ta, ma, pf
农产品: m, y, p, cs, a
贵金属: au, ag
```

### priority_score 公式
```
priority_score = departure_score×0.30 + quality_score×0.20 + phase_score×0.20 + position_score×0.15 + volume_score×0.15
```

---

## 执行记录

**2026-04-29 22:15** 
- ✅ Phase 1 完成：5/5 字段链路任务全部实现

**2026-04-29 22:37**
- ✅ Phase 2 + Phase 3 一次性完成：10/10 任务全部实现

**2026-04-30 ~ 2026-05-01**
- ✅ Phase 4 完成：信号详情 + 假突破模式 + 风险管理 + 精细检索
- ✅ Phase 5 完成：Parquet 本地化 + 批量抓取 + 活动日志 + 新浪数据源
- ✅ Phase 6 完成：C 扩展加速 + 多时间维度 + 全市场扫描优化
- ✅ Phase 7 完成：知识图谱全套（GraphStore + 演化链 + 叙事追踪 + 反身性 + 传导网络 + 品种配置）
- ✅ Phase 8 完成：L1/L2/L3 三层知识体系 + KnowledgeEngine + 知识增强质量评估

**2026-05-01**
- 📝 更新 TASK_INDEX.md：同步实际进度，Phase 0-8 全部标记完成
