"""
结构 Embedding — 把结构映射到向量空间

T1 任务：Structure → vector ∈ R^d
同类近、异类远

Stage A: 基于特征向量的简单 embedding
Stage B: 对比学习 embedding（需要训练数据量足够时启用）
"""

from __future__ import annotations

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


def find_nearest(
    query_vec: list[float],
    candidate_vecs: list[list[float]],
    top_k: int = 5,
) -> list[tuple[int, float]]:
    """
    找最近邻（v3.1: numpy 向量化）

    返回 [(index, similarity), ...] 按相似度降序
    """
    import numpy as np
    q = np.asarray(query_vec, dtype=np.float64)
    c = np.asarray(candidate_vecs, dtype=np.float64)

    # 向量化余弦相似度
    dot = c @ q
    n2 = np.sqrt(np.sum(c * c, axis=1))
    nq = np.sqrt(np.dot(q, q))
    denom = n2 * nq
    denom[denom == 0] = 1e-12
    scores = dot / denom

    # Top-K（用 argpartition 避免全排序）
    n = len(scores)
    if n <= top_k:
        indices = np.argsort(scores)[::-1]
    else:
        indices = np.argpartition(scores, -top_k)[-top_k:]
        indices = indices[np.argsort(scores[indices])[::-1]]

    return [(int(i), float(scores[i])) for i in indices]


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """余弦相似度（v3.1: numpy 向量化）"""
    import numpy as np
    a = np.asarray(v1, dtype=np.float64)
    b = np.asarray(v2, dtype=np.float64)
    dot = np.dot(a, b)
    n1 = np.sqrt(np.dot(a, a))
    n2 = np.sqrt(np.dot(b, b))
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(dot / (n1 * n2))


def euclidean_distance(v1: list[float], v2: list[float]) -> float:
    """欧氏距离（v3.1: numpy 向量化）"""
    import numpy as np
    a = np.asarray(v1, dtype=np.float64)
    b = np.asarray(v2, dtype=np.float64)
    d = a - b
    return float(np.sqrt(np.dot(d, d)))
