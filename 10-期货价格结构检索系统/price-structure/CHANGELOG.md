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
