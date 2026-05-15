# P1 任务计划：similarity/ranker 接口扩展

## 目标

让多维度相似度信息从 similarity.py → engine.py → ranker.py 完整流动，
而不是在 engine.py 中压缩成一个 float 再传给 ranker。

## 当前问题

1. `similarity.py` 的 `SimilarityScore` 有 6 维：total, geometric, relational, motion, family, graph
2. `ranker.py` 的 `combine_scores()` 只接收 `base_score: float`，丢失了 4 维信息
3. `engine.py` 在调用 `combine_scores(base_score=n.score.total, ...)` 时把 6 维压成了 1 个 total

这意味着 ranker 无法区分"几何相似但关系不同"和"关系相似但几何不同"的情况。

## 修改方案

### Step 1: similarity.py — 新增 SimilarityInput 类型

在 similarity.py 中定义一个数据类，用于把完整的相似度信息打包传递：

```python
@dataclass
class SimilarityInput:
    """传递给 ranker 的完整相似度输入"""
    total: float
    geometric: float
    relational: float
    motion: float
    family: float
    graph: float = 0.0
    matched_invariants: dict = field(default_factory=dict)
```

实际上 `SimilarityInput` 和 `SimilarityScore` 字段完全相同。考虑直接复用 `SimilarityScore`，
但为解耦起见（ranker 不应依赖 similarity 模块的具体实现），定义独立类型。

### Step 2: ranker.py — 扩展 combine_scores 接口

```python
# 方案A（推荐）：增加相似度维度的独立权重
@dataclass
class RankScore:
    base_score: float = 0.0
    geometric: float = 0.0
    relational: float = 0.0
    motion: float = 0.0
    family: float = 0.0
    graph_score: float = 0.0
    recency_score: float = 0.0
    quality_score: float = 0.0
    final_score: float = 0.0

def combine_scores(
    base_score: float = 0.0,
    geometric: float = 0.0,
    relational: float = 0.0,
    motion: float = 0.0,
    family: float = 0.0,
    graph_score: float = 0.0,
    recency_score: float = 0.0,
    quality_score: float = 0.0,
    weights: dict[str, float] | None = None,
) -> RankScore:
```

100% 向后兼容：旧的 `combine_scores(base_score=0.8, graph_score=0.5, ...)` 调用不受影响。
新增的 geometric/relational/motion/family 参数默认 0.0，不传就按旧行为。

默认权重扩展：
```python
DEFAULT_WEIGHTS = {
    "base": 0.78,        # 保留：总相似度的兜底权重
    "geometric": 0.0,    # 新增：默认0=不影响旧行为
    "relational": 0.0,
    "motion": 0.0,
    "family": 0.0,
    "graph": 0.12,
    "recency": 0.05,
    "quality": 0.05,
}
```

当细分维度权重全为 0 时，退化为旧行为（只用 base）。
当细分维度有权重时，base 权重自动清零，细分维度接管。

### Step 3: engine.py — 传递完整相似度信息

修改 engine.py 中调用 combine_scores 的部分：

```python
# 旧：
rank_result = combine_scores(
    base_score=n.score.total,
    graph_score=graph_score,
    recency_score=recency,
    quality_score=quality,
    weights=rank_weights,
)

# 新：
rank_result = combine_scores(
    base_score=n.score.total,
    geometric=n.score.geometric,
    relational=n.score.relational,
    motion=n.score.motion,
    family=n.score.family,
    graph_score=graph_score,
    recency_score=recency,
    quality_score=quality,
    weights=rank_weights,
)
```

### Step 4: config.yaml — 新增维度权重（可选）

在 `retrieval.rank_weights` 中添加细分维度权重，默认 0（不影响现有行为）。

### Step 5: 验证

- 确保旧调用方式不受影响（不传细分维度 = 旧行为）
- 确保传了细分维度后 final_score 正确计算
- 跑一个简单的 smoke test

## 文件修改清单

| 文件 | 改动 | 风险 |
|------|------|------|
| `src/retrieval/similarity.py` | 无需改动（SimilarityScore 已有完整字段） | 无 |
| `src/retrieval/ranker.py` | 扩展 RankScore + combine_scores 签名 | 低（向后兼容） |
| `src/retrieval/engine.py` | 传递完整相似度字段给 combine_scores | 低 |
| `config.yaml` | 新增细分维度权重（默认0） | 无 |

## 不做的事

- 不拆分 retrieval/ 目录结构（子代理分析结论：当前不需要大拆）
- 不改 SimilarityScore 的字段定义（已经够用）
- 不改 opportunity.py（它用不同的相似度体系）
- 不改 posterior.py（与本次修改无关）

## 执行顺序

1. 备份当前 ranker.py
2. 修改 ranker.py（扩展 RankScore + combine_scores）
3. 修改 engine.py（传递完整字段）
4. 更新 config.yaml（新增细分权重）
5. Smoke test
6. 记录到 memory
