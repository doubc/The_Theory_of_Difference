"""
结构相似性度量 — 三层

1. 几何相似 — 不变量向量的归一化欧氏距离
2. 关系相似 — 方向序列 / Zone 来源 / Cycle 数的一致性
3. 结构族相似 — 是否同一标签类或镜像变体

sim_total = w1·sim_geometric + w2·sim_relational + w3·sim_family
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.models import Structure


@dataclass
class SimilarityScore:
    """相似度评分详情"""
    total: float
    geometric: float
    relational: float
    family: float
    matched_invariants: dict


# ─── 不变量向量配置 ─────────────────────────────────────────
# 与 relations.structure_invariants() 输出的 dict key 对齐

INVARIANT_KEYS = [
    "cycle_count",
    "avg_speed_ratio",
    "avg_log_speed_ratio",
    "avg_time_ratio",
    "high_dispersion",
    "low_dispersion",
    "high_trend",
    "low_trend",
    "zone_rel_bw",
    "zone_strength",
]

# 每个不变量的典型量级，用于归一化
INVARIANT_SCALES = {
    "cycle_count": 10.0,
    "avg_speed_ratio": 2.0,
    "avg_log_speed_ratio": 2.0,
    "avg_time_ratio": 2.0,
    "high_dispersion": 1.0,
    "low_dispersion": 1.0,
    "high_trend": 1.0,
    "low_trend": 1.0,
    "zone_rel_bw": 1.0,
    "zone_strength": 10.0,
}


def _normalized_vector(inv: dict) -> list[float]:
    """从 invariants dict 提取归一化向量"""
    return [
        (inv.get(k, 0) or 0) / INVARIANT_SCALES[k]
        for k in INVARIANT_KEYS
    ]


# ─── 几何相似 ──────────────────────────────────────────────

def geometric_similarity(s1: Structure, s2: Structure) -> float:
    """
    归一化不变量向量的 1 - 欧氏距离(clip 到 [0,1])

    核心思想：两个结构的 speed_ratio、time_ratio、cycle_count、
    高点聚集度越接近 → 几何越相似
    """
    v1 = _normalized_vector(s1.invariants)
    v2 = _normalized_vector(s2.invariants)
    d = math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))
    return max(0.0, 1.0 - d / math.sqrt(len(v1)))


# ─── 关系相似 ──────────────────────────────────────────────

def relational_similarity(s1: Structure, s2: Structure) -> float:
    """
    离散关系的一致性：
    - Zone 来源一致（high_cluster vs low_cluster）
    - Cycle 数量相近
    - 速度比方向一致（同为 >1 或同为 <1）
    """
    score = 0.0
    n = 0

    # Zone 来源一致性
    n += 1
    if s1.zone.source == s2.zone.source:
        score += 1.0

    # Cycle 数量相近
    n += 1
    dn = abs(s1.cycle_count - s2.cycle_count)
    score += max(0.0, 1.0 - dn / 5.0)

    # 速度比方向一致
    n += 1
    if (s1.avg_speed_ratio > 1) == (s2.avg_speed_ratio > 1):
        score += 1.0

    # 时间比方向一致
    n += 1
    if (s1.avg_time_ratio > 1) == (s2.avg_time_ratio > 1):
        score += 1.0

    return score / n if n > 0 else 0.0


# ─── 结构族相似 ────────────────────────────────────────────

# 镜像对：顶部和底部是镜像关系
MIRROR_PAIRS = {
    ("SlowUpFastDown_TopReversal", "SlowDownFastUp_BottomReversal"),
    ("FastUpSlowDown_TopDistribution", "TripleTest_BottomBreakout"),
    ("SlowDownFastUp_BottomReversal", "SlowUpFastDown_TopReversal"),
    ("TripleTest_BottomBreakout", "FastUpSlowDown_TopDistribution"),
}


def _is_mirror(a: str, b: str) -> bool:
    return (a, b) in MIRROR_PAIRS or (b, a) in MIRROR_PAIRS


def family_similarity(s1: Structure, s2: Structure) -> float:
    """
    结构族相似：是否属于同一类型或镜像
    """
    if s1.label and s2.label:
        if s1.label == s2.label:
            return 1.0
        if _is_mirror(s1.label, s2.label):
            return 0.6
        return 0.0
    # 无 label，退化为 zone source 一致
    return 0.5 if s1.zone.source == s2.zone.source else 0.2


# ─── 综合相似度 ────────────────────────────────────────────

def similarity(
    s1: Structure,
    s2: Structure,
    weights: tuple[float, float, float] = (0.4, 0.4, 0.2),
) -> SimilarityScore:
    """
    三层加权相似度

    默认权重：几何 0.4, 关系 0.4, 族 0.2
    """
    w_g, w_r, w_f = weights
    g = geometric_similarity(s1, s2)
    r = relational_similarity(s1, s2)
    f = family_similarity(s1, s2)
    total = w_g * g + w_r * r + w_f * f

    # 匹配详情
    matched = {}
    for k in INVARIANT_KEYS:
        v1 = s1.invariants.get(k, 0) or 0
        v2 = s2.invariants.get(k, 0) or 0
        scale = INVARIANT_SCALES[k]
        matched[k] = {
            "s1": v1,
            "s2": v2,
            "diff_ratio": abs(v1 - v2) / scale if scale > 0 else 0.0,
        }

    return SimilarityScore(
        total=total, geometric=g, relational=r, family=f,
        matched_invariants=matched,
    )
