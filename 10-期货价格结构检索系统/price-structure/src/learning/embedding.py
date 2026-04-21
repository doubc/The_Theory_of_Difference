"""
结构 Embedding — 把结构映射到向量空间

T1 任务：Structure → vector ∈ R^d
同类近、异类远

Stage A: 基于特征向量的简单 embedding
Stage B: 对比学习 embedding（需要训练数据量足够时启用）
"""

from __future__ import annotations

import math
from typing import Sequence

from src.models import Structure
from src.learning.features import extract_features, FEATURE_NAMES


# ─── 特征归一化参数 ────────────────────────────────────────
# 基于铜连续合约的经验量级，用于归一化

FEATURE_SCALES = [
    10.0,    # cycle_count
    500.0,   # total_duration_days
    2.0,     # avg_speed_ratio
    2.0,     # avg_time_ratio
    1.0,     # std_speed_ratio
    1.0,     # std_time_ratio
    1.0,     # avg_log_speed_ratio
    0.05,    # high_cluster_cv
    0.05,    # zone_relative_bandwidth
    10.0,    # zone_strength
    1.0,     # avg_amplitude_ratio
    50000.0, # total_abs_delta
    1.0,     # up_segment_ratio
]


def embed(s: Structure) -> list[float]:
    """
    结构 → 归一化特征向量

    用作 embedding 的 Stage A 实现。
    向量各维度归一化到 [0, ~1] 量级。
    """
    raw = extract_features(s)
    return [
        raw[i] / FEATURE_SCALES[i] if FEATURE_SCALES[i] > 0 else raw[i]
        for i in range(len(raw))
    ]


def embed_batch(structures: Sequence[Structure]) -> list[list[float]]:
    """批量 embedding"""
    return [embed(s) for s in structures]


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """余弦相似度"""
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def euclidean_distance(v1: list[float], v2: list[float]) -> float:
    """欧氏距离"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def find_nearest(
    query_vec: list[float],
    candidate_vecs: list[list[float]],
    top_k: int = 5,
) -> list[tuple[int, float]]:
    """
    找最近邻

    返回 [(index, similarity), ...] 按相似度降序
    """
    scores = [(i, cosine_similarity(query_vec, v)) for i, v in enumerate(candidate_vecs)]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]
