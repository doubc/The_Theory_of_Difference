# CHANGELOG

## 2026-05-01 — 知识层（L1/L2/L3）+ 文档同步

### 新增

- **`knowledge/` 目录**：三层知识体系 YAML 规则库
  - `L1_conditions.yaml`：8 条判定知识（趋势可靠性、震荡充分、反转确认、高质量结构等）
  - `L2_invalidation.yaml`：7 条失效知识（通量背离、结构老化、投影不可信等）
  - `L3_wisdom.yaml`：12 条市场知识（品种特征、反差类型、形态模式、跨品种联动等）
- **`src/knowledge/` 模块**：知识引擎
  - `engine.py`：KnowledgeEngine — YAML 加载 + 条件匹配 + 三层评估
  - `result.py`：KnowledgeResult + MatchedRule — 匹配结果封装
- **`src/quality.py` 增强**：第 6 维度「知识置信度」
  - `assess_quality_with_knowledge()`：知识增强质量评估
  - 知识维度占总分 10%，L1 正向/L2 负向/L3 参考
- **`src/workbench/tab_knowledge_graph.py` 增强**：新增「🧠 知识层」子 Tab
  - 知识库总览（L1/L2/L3 规则数统计）
  - 当前结构知识匹配（实时评估 + 可视化）
  - 知识库详情浏览（按层分类展示规则）

### 文档同步

- **TASK_INDEX.md**：更新进度总览，Phase 0-8 全部标记完成
- **docs/待办事项.md**：移除已完成项，仅保留实际待办
- **docs/SUMMARY.md**：更新核心能力描述 + 技术架构图
- **README.md**：更新品种配置表 + 新增知识层章节

---

## 2026-05-01 — 金融知识图谱多品种配置系统

### 新增

- **`config/products/`**：按品种独立目录的配置系统
  - `registry.yaml`：品种注册表（清单 + 状态 + 文件路径）
  - `_template/`：新品种模板（5 个 JSON 文件）
  - `_shared/`：跨品种共享知识（211 实体 / 192 关系 / 39 传导链 / 30 极值）
  - `copper/`：铜品种（35 实体 / 23 关系 / 7 传导链 / 7 极值 / 5 定价模型）
  - `lithium_carbonate/`：碳酸锂品种（5 实体 / 1 极值）
- **`config/keywords/all.json`**：全局投研关键词库（431 条）
- **`src/graph/product_ingester.py`**：多品种知识导入器
  - 支持增量更新（文件 hash 判断）
  - 支持全量刷新（`reload_product`）
  - 品种命名空间隔离（`cu:GEO_066`）
  - 跨品种联动关系支持
- **`scripts/smoke_test_finance_graph.py`**：金融图谱冒烟测试

### 数据来源

- WorldBase 原始数据（用户定义）
- DeepSeek 扩展（2026-05-01 关键词、关系、传导链、实体、极值）
- 铜产业链专题（DeepSeek 生成）
- 碳酸锂产业链专题（DeepSeek 生成）

### 设计决策

- 采用「配置即知识」方案：品种数据全部以 JSON 文件存储，无需改 Python 代码即可增删品种
- 金融图谱独立于价格结构图谱（`data/graph/`），权重低于结构相似度（0.08 vs 0.85）
- 知识图谱接入点为检索后处理，不干扰编译器和四层相似度计算

---

## 2026-04-24 — C 扩展优化 + 扫描修复 + 安全加固

### C 扩展优化

- 新增 `_compiler.c`：二分查找 bar 过滤、向量化批量相似度计算、批量特征提取
- 修复 `_pivots.c` 参数解析 bug（格式字符串多余 `i`）
- 优化 `_dtw.c`：小序列栈分配、预分配工作区、内层循环 min 展开
- 修复 `setup.py` 跨平台编译参数
- 新增根目录 `setup_fast.py` 解决 `build_ext --inplace` 路径问题

### Python 端优化

- `pipeline.py`：bar 预过滤改用二分查找
- `retrieval/engine.py`：批量预提取候选不变量向量，几何相似度矩阵化预筛
- `retrieval/active_match.py`：二分查找过滤时间窗口
- `learning/features.py`：尝试 C 批量提取，fallback 到逐个调用
- `learning/embedding.py`：numpy 向量化 + argpartition 避免全排序

### 扫描修复

- 只加载最近 120-240 天数据（按灵敏度）
- 30 天 recency 过滤，排序改为质量 70% + recency 30% 混合
- 卡片加新鲜度标记（🟢 3天内 / 🟡 7天内 / 灰色更早）

### 安全加固

- MySQL 密码从硬编码改为环境变量 `MYSQL_PASSWORD`
- 新增 `.env.example` 模板
- 同步 `requirements.txt` 与 `pyproject.toml` 依赖

### 活动日志

- 新增 `ActivityLog` 类（JSONL 格式），自动保存扫描/检索/对比/合约结果
- 复盘日志新增「📊 活动日志」子标签页

### 性能基准（5178 bars / 29 structures）

| 操作 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| DTW 距离 (200×200) | 9.4 ms | 0.1 ms | 132x |
| Bar 过滤 (100k bars) | 14.9 ms | 0.1 ms | 132x |
| 极值提取 (5000 bars) | 35 ms | 1.5 ms | 24x |
| 特征批量提取 | ~5 ms | 0.6 ms | 8x |
| 几何相似度 (5000 cand) | 0.17 ms | 0.08 ms | 2.2x |
| 单品种编译 | 87 ms | 74 ms | 1.2x |
| 全市场扫描 (60品种) | 5.2 s | 4.4 s | 1.2x |

---

## 2026-04-23 — 全市场扫描 + 精细检索 + 合约检索

### 全市场机会扫描

- 新增 `_scan_all_symbols()` 缓存函数，扫描所有品种按关注度评分排序
- 展示 Top 10 机会卡片：品种名、Zone、运动态、通量、方向判断
- 研究建议、风控评级、跨品种信号一致性、每日变化追踪

### 精细检索条件

- 日期范围、Zone 价位范围、方向、反差类型、运动状态、最小相似度、排序方式
- 统计面板增加中位数收益展示
- 实时过滤控件：按方向筛选 + 按相似度升降序

### 合约检索

- 新增 `src/data/sina_fetcher.py`：支持国内期货/外盘/外汇三种数据源
- 预置 65 个可检索合约 + 自由输入任意代码

### UI 优化

- 红涨绿跌（A 股惯例）
- 筛选器中文化
- 清理死代码和无用 import

---

## 2026-04-24 — 数据本地化 + C 加速 + 多时间维度

### 数据层

- 新增 `src/data/local_store.py`：Parquet 本地数据仓库，列式压缩，读取快 10x+
- 新增 `src/data/batch_fetcher.py`：65+ 合约并发抓取，增量更新
- 元数据自动追踪每个品种的最后更新时间

### C 扩展

- 新增 `_pivots.c`：极值提取 C 实现，自适应窗口 + 分形一致性
- 新增 `_dtw.c`：DTW 距离 C 实现，Sakoe-Chiba 带宽约束
- Python 包装器自动检测 C 扩展可用性，无 C 编译器自动 fallback

### 多时间维度对比

- 新增 `src/multitimeframe/comparator.py`：5 分钟 vs 日线、1 小时 vs 日线跨尺度一致性检查
- Zone 重叠度用 IoU，综合一致性 = 0.4×Zone重叠 + 0.3×方向一致 + 0.3×速度比相似
- 新增 `scripts/multitimeframe_scan.py` 全市场扫描

### 工作台模块化

- `app.py` 拆分为 `shared.py`（共享工具函数）+ `data_layer.py`（数据层）

### PythonGO 策略优化

- 提取 `_place_order()` 消除重复下单逻辑
- 拆分 `check_resonance` 为子方法
- 修复 `Params` 类定义缺失 bug

### 性能预期

| 操作 | C 扩展 | Python fallback |
|------|--------|----------------|
| 极值提取 (10K bars) | ~0.02s | ~0.5s |
| DTW (100 vs 100) | ~0.05s | ~1.5s |
| 全市场编译 (65品种) | ~30s | ~2min |
| 全市场检索 | ~20s | ~8min |

### 关键设计决策

- 选 Parquet 而非 SQLite：列式存储读取快，适合批量编译
- 选纯 C 而非 Cython：避免编译依赖
- 多时间维度用重采样而非插值：降采样是信息减少，插值是信息伪造
- 独立模块化，不修改现有文件：降低集成风险

---

## 2026-04-24 — 检索功能升级设计

- 定义当日机会扫描流程与数据流
- 定义历史检索精细筛选条件（8 个新增控件）
- 定义检索结果二次过滤机制
- UI 布局变更方案
