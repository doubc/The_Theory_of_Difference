"""
图谱匹配解释 — 为检索结果提供图谱层面的解释

P1 整改：从 engine.py 的 _generate_match_reason 和图谱归因逻辑中提取。
独立模块，可被 engine.py 和其他模块调用。
"""

from __future__ import annotations

from src.models import Structure
from src.retrieval.similarity import SimilarityScore


# 反差类型中文标签
CONTRAST_LABELS = {
    "panic": "恐慌型",
    "oversupply": "供需失衡型",
    "policy": "政策驱动型",
    "liquidity": "流动性驱动型",
    "speculation": "投机驱动型",
}


def explain_graph_match(
    query: Structure,
    matched: Structure,
    score: SimilarityScore,
    graph_score: float = 0.0,
) -> str:
    """
    生成图谱匹配解释 — 包含反差类型、几何特征、图谱关联

    Args:
        query: 查询结构
        matched: 匹配结构
        score: 相似度评分
        graph_score: 图谱上下文得分

    Returns:
        人可读的匹配原因解释
    """
    parts = []

    # 反差类型匹配
    qc = query.zone.context_contrast.value if query.zone else "unknown"
    mc = matched.zone.context_contrast.value if matched.zone else "unknown"
    if qc != "unknown" and mc != "unknown" and qc == mc:
        parts.append(f"共同面临{CONTRAST_LABELS.get(qc, qc)}反差")

    # 几何特征匹配
    if score.geometric > 0.7:
        parts.append("几何形态高度一致")
    elif score.geometric > 0.5:
        parts.append("几何形态大致相似")

    # 关系特征匹配
    qi = query.invariants
    mi = matched.invariants
    qsr = qi.get("avg_speed_ratio", 0)
    msr = mi.get("avg_speed_ratio", 0)
    if qsr and msr and abs(qsr - msr) < 0.3:
        parts.append("速度比高度一致")

    qtr = qi.get("avg_time_ratio", 0)
    mtr = mi.get("avg_time_ratio", 0)
    if qtr and mtr and abs(qtr - mtr) < 0.3:
        parts.append("试探频率高度一致")

    # 图谱关联
    if graph_score > 0.5:
        parts.append("图谱上下文强关联")
    elif graph_score > 0.3:
        parts.append("图谱上下文弱关联")

    if not parts:
        parts.append(f"综合相似度 {score.total:.2f}")

    return "，".join(parts)
