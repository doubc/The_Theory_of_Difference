# CHANGELOG

## [v3.1] 2026-04-24 — C 扩展优化 + 扫描修复

### C 扩展优化 — `src/fast/`

**新增 `_compiler.c`**（530 行）：
- `binary_filter_bars` — 二分查找 bar 时间过滤，O(log n) 替代 O(n) 线性扫描
- `batch_geometric_similarity` — 向量化欧氏距离，矩阵化计算
- `batch_relational_similarity` — 关系一致性批量检查
- `batch_motion_similarity` — 运动态批量对比
- `batch_total_similarity` — 四层综合相似度（几何+关系+运动+族）
- `batch_extract_features` — 批量特征提取，13 维向量
- `batch_structure_invariants` — 批量不变量计算
- `cluster_by_price` — Zone 聚类

**修复 `_pivots.c`**：
- 修复 `PyArg_ParseTuple` 格式字符串多了一个 `i` 的 bug（导致 13 vs 12 参数错误）

**优化 `_dtw.c`**：
- 小序列栈分配（<1024 免 malloc）
- `DTWWorkspace` 预分配工作区，批量场景零 malloc
- 内层循环 min 展开，减少分支预测失败
- `edit_distance_c` 同步栈分配优化

**修复 `setup.py`**：
- MSVC `/O2` → GCC `-O3 -march=native -ffast-math -funroll-loops -flto`
- 跨平台编译参数自动检测

**新增 `setup_fast.py`**（根目录）：
- 解决 `build_ext --inplace` 路径问题

**扩展 `__init__.py`**：
- 新增 `binary_filter_bars` / `batch_geometric_similarity_fast` / `batch_total_similarity_fast` / `batch_extract_features_fast` Python 包装
- 检测 `_compiler` 模块可用性

### Python 端优化

**`pipeline.py`**：
- bar 预过滤改用二分查找，预提取时间戳为 int64 数组
- 每个结构的窗口过滤从 O(n) 降到 O(log n)

**`retrieval/engine.py`**：
- 批量预提取候选不变量向量
- 几何相似度矩阵化预筛，跳过低分候选

**`retrieval/active_match.py`**：
- `_compute_outcome` 改用二分查找过滤时间窗口
- `_compile_structures` 改用二分查找

**`learning/features.py`**：
- `extract_features_batch` 尝试 C 批量提取，fallback 到逐个调用

**`learning/embedding.py`**：
- `find_nearest` / `cosine_similarity` / `euclidean_distance` 改用 numpy 向量化
- `find_nearest` 用 argpartition 避免全排序

### 扫描修复 — `src/workbench/tab_scan.py`

**问题**：全量历史数据编译，旧结构（>30天）混入扫描结果

**修复**：
- 只加载最近 120-240 天数据（按灵敏度）
- 30 天 recency 过滤，`t_end` 超过 30 天的跳过
- 排序改为质量 70% + recency 30% 混合
- 卡片加新鲜度标记（🟢 3天内 / 🟡 7天内 / 灰色更早）

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

### 测试
- 85 passed，全部通过
- 空数组/单元素/极端值边界测试通过
- C 扩展加载 + fallback 测试通过

---

## [未发布] 2026-04-23

### 设计
- 新增 `docs/12_检索功能升级设计.md` — 检索功能升级设计文档
  - 定义当日机会扫描（Daily Opportunity Scan）流程与数据流
  - 定义历史检索精细筛选条件（8 个新增控件）
  - 定义检索结果二次过滤机制
  - UI 布局变更方案
  - 实现步骤与风险约束

### 实现 — `src/workbench/app.py`

#### Tab 1 "今天值得关注什么" — 全市场机会扫描
- 新增 `_scan_all_symbols()` 缓存函数（`@st.cache_data(ttl=300)`）
- 扫描所有可用品种（MySQL + CSV），编译结构，按关注度评分排序
- 评分逻辑：基础分 30 + cycle_count × 3 + 通量绝对值 + 运动态加权（breakdown +15, confirmation +12, forming +5）+ 高压缩 +10
- 展示 Top 10 机会卡片：品种名、Zone、运动态、通量、方向判断、关注度评分
- `st.spinner` + `st.progress` 进度提示
- 保留原有"当前品种结构"展示

#### Tab 2 "历史对照" — 精细检索条件
- `st.expander("🎛️ 精细检索条件")` 内新增 6 类筛选器：
  - 日期范围筛选（起止 `st.date_input`）
  - Zone 价位范围（`st.slider`）
  - 方向筛选（`st.multiselect` up/down/unclear）
  - 反差类型筛选（`st.multiselect` panic/oversupply/policy/liquidity/speculation/unknown）
  - 运动状态筛选（`st.multiselect` →breakdown/→confirmation/stable/forming）
  - 最小相似度阈值（`st.slider`）
  - 结果排序方式（`st.radio` 相似度/涨幅/日期）

#### Tab 2 检索结果增强
- 统计面板增加"中位数收益"展示
- 新增实时过滤控件：按方向筛选 + 按相似度升降序
- 案例 expander 标题增加反差类型和运动状态标签
- 案例详情内增加反差/运动状态文字展示
- 检索进度增加已用时间 + 预估剩余时间

#### Tab 1 扫描增强 — 研究建议 + 风控 + 一致性 + 变化追踪
- 每张扫描卡片可展开查看**研究建议**（基于结构特征自动生成下一步研究动作）
- **风控评级**：关注度 ≥75→高(5-8%) / 55-74→中(3-5%) / <55→低(1-3%)
- **跨品种信号一致性**：按交易所分组，判断板块方向是否一致（≥60% 偏多/偏空则提示）
- **每日变化报告**：session_state 存储上次扫描结果，同一天内自动对比新增/变化/退出
- 扫描卡片增加**价格 vs Zone 位置**显示（Zone 内/上方/下方 + 偏移百分比）

#### Tab 6 "合约检索"（新增）
- 新增 `src/data/sina_fetcher.py` — 新浪期货数据采集器
  - 支持三种数据源：国内期货（InnerUrl）、外盘期货（GlobalUrl）、外汇（FxUrl）
  - `fetch_bars(code, freq)` — 统一入口，自动判断数据源
  - `detect_source(code)` — 数据源识别
  - `available_contracts()` — 预置 65 个可检索合约
  - 不依赖 pymysql/threading，纯 HTTP 请求 + pandas 清洗
- Tab 6 UI：预置合约下拉 + 自由输入 + 频率选择 + 灵敏度调节
- 拉取→编译→结构卡片（含价格位置）+ K 线图 + 不变量详情

### 全局优化
- **红涨绿跌**（A 股惯例）：K 线图 increasing→红(#ef5350)、decreasing→绿(#26a69a)
- 扫描卡片方向色：上涨→红(danger)、下跌→绿(ok)
- CSS 标签：`.tag-bullish`→红底、`.tag-bearish`→绿底
- 筛选器中文化：`up/down/unclear` → `📈 上涨(up)` 等，内部 `_extract_key()` 提取英文 key
- 清理死代码：`_describe_outcome()`、`_format_invariants()` + 5 个无用 import + 4 个无用 CSS 类
- `_extract_key()` / `_price_vs_zone()` 提到模块级工具函数
- `import time as _time` 统一顶部，消除内联重复
- 空状态提示增加具体操作引导
- 评分说明 popover
- README 同步更新（六页布局、Tab 6、项目结构）
