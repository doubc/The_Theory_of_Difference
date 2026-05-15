"""
检索排序器 — 多维度加权排序

P1 整改：从 engine.py 中提取排序逻辑，独立为可配置的 ranker 模块。
支持自定义权重字典，默认权重来自 config.yaml retrieval.rank_weights。

设计原则：
1. 与 engine.py 解耦 — ranker 不知道 RetrievalEngine 的存在
2. 纯函数 — combine_scores() 无副作用
3. 可配置 — 权重从配置文件读取，不硬编码
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RankScore:
    """
    排序得分分解 — 一个候选结构的最终排序依据

    分为四个维度：
    - base_score: 基础相似度（geometric + relational + motion + family）
    - graph_score: 图谱上下文相似度
    - recency_score: 时间新鲜度（越近越高）
    - quality_score: 质量分层权重
    - final_score: 加权后的最终排序分
    """
    base_score: float = 0.0
    graph_score: float = 0.0
    recency_score: float = 0.0
    quality_score: float = 0.0
    final_score: float = 0.0


# 默认权重 — 与 config.yaml retrieval.rank_weights 对齐
DEFAULT_WEIGHTS: dict[str, float] = {
    "base": 0.78,
    "graph": 0.12,
    "recency": 0.05,
    "quality": 0.05,
}


def combine_scores(
    base_score: float,
    graph_score: float = 0.0,
    recency_score: float = 0.0,
    quality_score: float = 0.0,
    weights: dict[str, float] | None = None,
) -> RankScore:
    """
    多维度加权排序

    Args:
        base_score: 基础相似度（similarity.total）
        graph_score: 图谱上下文得分
        recency_score: 时间新鲜度得分 [0, 1]，1 = 最今天
        quality_score: 质量权重 [0, 1]，A层=1.0, B层=0.6, C层=0.25, D层=0.0
        weights: 自定义权重字典，默认 {"base":0.78, "graph":0.12, "recency":0.05, "quality":0.05}

    Returns:
        RankScore 含各维度得分和最终加权分
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS

    w_base = w.get("base", 0.78)
    w_graph = w.get("graph", 0.12)
    w_recency = w.get("recency", 0.05)
    w_quality = w.get("quality", 0.05)

    # 归一化权重（确保总和为 1）
    w_sum = w_base + w_graph + w_recency + w_quality
    if w_sum > 0:
        w_base /= w_sum
        w_graph /= w_sum
        w_recency /= w_sum
        w_quality /= w_sum

    final = (
        w_base * base_score +
        w_graph * graph_score +
        w_recency * recency_score +
        w_quality * quality_score
    )

    return RankScore(
        base_score=base_score,
        graph_score=graph_score,
        recency_score=recency_score,
        quality_score=quality_score,
        final_score=final,
    )


def compute_recency_score(
    sample_t_end,
    query_t_end,
    max_lookback_days: int = 365,
) -> float:
    """
    计算时间新鲜度得分

    样本越新，得分越高。指数衰减。
    当天 = 1.0，一年前 ≈ 0.37 (1/e)。

    Args:
        sample_t_end: 样本结束时间（datetime）
        query_t_end: 查询结束时间（datetime）
        max_lookback_days: 衰减时间尺度（天）

    Returns:
        [0, 1] 新鲜度得分
    """
    if sample_t_end is None or query_t_end is None:
        return 0.5  # 无时间信息，给中间分

    try:
        delta_days = (query_t_end - sample_t_end).days
        if delta_days < 0:
            return 1.0  # 未来样本（不应该出现），给最高分
        import math
        return math.exp(-delta_days / max(max_lookback_days, 1))
    except (TypeError, AttributeError):
        return 0.5


def compute_quality_score(quality_tier: str) -> float:
    """
    从质量层级映射到排序权重

    Args:
        quality_tier: "A" | "B" | "C" | "D"

    Returns:
        排序权重 [0, 1]
    """
    return {"A": 1.0, "B": 0.6, "C": 0.25, "D": 0.0}.get(quality_tier, 0.5)
