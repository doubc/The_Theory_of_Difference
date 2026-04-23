# CHANGELOG

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
