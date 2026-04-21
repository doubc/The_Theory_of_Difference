# 主动匹配（Active Match）

## 设计意图

日报扫描是"系统主动推"——每天跑一遍全市场，告诉你有什么机会。
主动匹配是"用户主动拉"——用户带着具体观点和问题来查。

典型场景：
> "AL0 价格到了历史极高水平，单位利润接近 12000 元/吨，实际历史平均成本只有 14000。我想看看历史上类似的结构丛后来怎么走了。检索 2024-2026 或者 2023-2026 的结构特征，列出相似的，指引我去比较前后情况。"

## 与日报扫描的区别

| 维度 | 日报扫描 (daily_scan) | 主动匹配 (active_match) |
|------|----------------------|------------------------|
| 触发方 | 系统定时 | 用户手动 |
| 查询对象 | 全市场所有品种 | 用户指定 1~N 个品种 |
| 时间窗口 | 最新数据 | 用户指定（如 2023-2026） |
| 输出重点 | 关注度排序的机会清单 | 历史相似案例的对比指引 |
| 用户背景 | 无 | 用户自带观点和上下文 |
| 输出格式 | HTML 日报 | HTML 对比报告 + JSON 快照 |

## 信息架构

一条匹配结果 = 当前结构 + 历史相似结构 + 前后对比指引

### 输入

```
ActiveMatchQuery(
    symbols: list[str]          # 品种列表，如 ["AL0"]
    search_start: str           # 检索窗口起始，如 "2023-01-01"
    search_end: str             # 检索窗口结束，如 "2026-04-21"
    context_note: str           # 用户观点描述
    profit_per_unit: float | None   # 当前单位利润
    avg_cost: float | None          # 历史平均成本
    price_context: str | None       # 价格定性描述
    min_cycles: int = 2         # 最小 cycle 数
    top_k: int = 10             # 返回最相似的 N 段历史
)
```

### 输出

```
ActiveMatchResult(
    query: ActiveMatchQuery
    compiled_structures: list[Structure]     # 窗口内编译出的结构
    historical_matches: list[HistoricalMatch] # 历史相似段
    scan_meta: dict                          # 扫描元信息
)
```

每条历史匹配：

```
HistoricalMatch(
    symbol: str
    symbol_name: str
    search_window: str              # 用户检索的窗口
    matched_structure: Structure    # 当前窗口内的结构
    matched_inv: dict               # 不变量
    historical_cases: list[Case]    # 最相似的 K 段历史
    comparison_guide: list[str]     # 对比指引（文字）
)
```

每段历史案例：

```
Case(
    symbol: str
    symbol_name: str
    period: str                     # "2019-03 ~ 2019-06"
    similarity: float
    sim_geometry: float
    sim_relation: float
    sim_family: float
    diff_detail: dict
    direction: str                  # 后续方向
    outcome_move: float             # 后续幅度
    outcome_days: int               # 兑现天数
    description: str                # 自动生成的一句话描述
)
```

## 使用方式

```bash
# CLI
python scripts/active_match.py \
    --symbols AL0 \
    --window 2023-01-01:2026-04-21 \
    --context "铝价历史极高水平，单位利润12000，平均成本14000" \
    --top-k 10

# Python API
from scripts.active_match import active_match, ActiveMatchQuery

query = ActiveMatchQuery(
    symbols=["AL0"],
    search_start="2023-01-01",
    search_end="2026-04-21",
    context_note="铝价历史极高水平，单位利润12000，平均成本14000",
    profit_per_unit=12000,
    avg_cost=14000,
    price_context="历史极高水平",
)
result = active_match(query)
```

## 文件结构

```
src/retrieval/active_match.py    # 核心逻辑：查询 → 编译 → 匹配 → 对比指引
scripts/active_match.py          # CLI 入口
output/active_match_report.html  # HTML 对比报告
```
