"""
结构相似性度量 — 四层

1. 几何相似 — 不变量向量的归一化欧氏距离
2. 关系相似 — 方向序列 / Zone 来源 / Cycle 数的一致性
3. 运动相似 — 阶段趋势 / 守恒通量 / 稳态距离的一致性 (V1.6)
4. 结构族相似 — 是否同一标签类或镜像变体

sim_total = w1·sim_geometric + w2·sim_relational + w3·sim_motion + w4·sim_family
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.models import Structure, Cycle


@dataclass
class SimilarityScore:
    """相似度评分详情"""
    total: float
    geometric: float
    relational: float
    motion: float
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


# ─── 运动相似 (V1.6) ───────────────────────────────────────

def motion_similarity(s1: Structure, s2: Structure) -> float:
    """
    V1.6 运动相似：阶段趋势、守恒通量、稳态距离的一致性
    
    两个几何相似但运动方向相反的结构，后验行为可能完全不同。
    运动维度确保我们区分"在走向 breakdown"和"在走向 confirmation"。
    """
    m1, m2 = s1.motion, s2.motion

    # 无运动态 → 两者都无 = 完全一致；只有一方无 = 不确定
    if m1 is None and m2 is None:
        return 1.0
    if m1 is None or m2 is None:
        return 0.5

    score = 0.0
    n = 0

    # 1. 阶段趋势一致性
    n += 1
    if m1.phase_tendency == m2.phase_tendency:
        score += 1.0
    elif ("breakdown" in m1.phase_tendency) == ("breakdown" in m2.phase_tendency):
        score += 0.5  # 都含 breakdown 或都不含

    # 2. 守恒通量方向一致性（同为正或同为负）
    n += 1
    if m1.conservation_flux * m2.conservation_flux > 0:
        score += 1.0
    elif abs(m1.conservation_flux) < 0.1 and abs(m2.conservation_flux) < 0.1:
        score += 0.8  # 都接近零

    # 3. 稳态距离相近
    n += 1
    dd = abs(m1.stable_distance - m2.stable_distance)
    score += max(0.0, 1.0 - dd)

    # 4. 反差类型一致性
    n += 1
    c1 = s1.zone.context_contrast.value if s1.zone else ""
    c2 = s2.zone.context_contrast.value if s2.zone else ""
    if c1 and c2 and c1 == c2:
        score += 1.0
    elif c1 == "unknown" or c2 == "unknown":
        score += 0.5
    else:
        score += 0.0

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
    weights: tuple[float, ...] = (0.35, 0.35, 0.15, 0.15),
) -> SimilarityScore:
    """
    四层加权相似度

    默认权重：几何 0.35, 关系 0.35, 运动 0.15, 族 0.15
    """
    if len(weights) == 3:
        # 兼容旧调用（3权重）
        w_g, w_r, w_f = weights
        w_m = 0.0
    else:
        w_g, w_r, w_m, w_f = weights

    g = geometric_similarity(s1, s2)
    r = relational_similarity(s1, s2)
    m = motion_similarity(s1, s2) if w_m > 0 else 0.0
    f = family_similarity(s1, s2)
    total = w_g * g + w_r * r + w_m * m + w_f * f

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
        total=total, geometric=g, relational=r, motion=m, family=f,
        matched_invariants=matched,
    )


# ═══ v2.5 新增: DTW 时间序列相似度 ═══════════════════════════

def _dtw_distance(seq1: list[float], seq2: list[float], window: int | None = None) -> float:
    """
    Dynamic Time Warping 距离 — v2.5 核心新增

    两个价格序列之间的最优对齐距离。
    允许时间轴非线性拉伸/压缩，捕捉"形状相似但时间错位"的结构。

    空间优化：只保留 DP 矩阵的两行，内存从 O(nm) 降到 O(m)。

    Args:
        seq1, seq2: 归一化价格序列（建议先做 min-max 归一化）
        window: Sakoe-Chiba 带宽约束（None = 无约束）

    Returns:
        DTW 距离（越小越相似）
    """
    n, m = len(seq1), len(seq2)
    if n == 0 or m == 0:
        return float("inf")

    # 带宽约束
    if window is None:
        window = max(n, m)
    window = max(window, abs(n - m))

    # 空间优化：只保留两行
    INF = float("inf")
    prev = [INF] * (m + 1)
    prev[0] = 0.0

    for i in range(1, n + 1):
        curr = [INF] * (m + 1)
        j_lo = max(1, i - window)
        j_hi = min(m, i + window)
        for j in range(j_lo, j_hi + 1):
            cost = (seq1[i - 1] - seq2[j - 1]) ** 2
            curr[j] = cost + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr

    return math.sqrt(prev[m])


def _normalize_series(values: list[float]) -> list[float]:
    """Min-max 归一化到 [0, 1]"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _series_from_structure(s: Structure) -> list[float]:
    """
    从结构中提取用于 DTW 的特征序列。

    使用 Cycle 级别的速度比序列作为结构的"指纹"：
    - 有 Cycle → [speed_ratio_1, speed_ratio_2, ...]
    - 无 Cycle → 退化为不变量向量
    """
    if s.cycles:
        return [c.speed_ratio for c in s.cycles]
    # 退化：用不变量向量
    return _normalized_vector(s.invariants)


def dtw_similarity(s1: Structure, s2: Structure) -> float:
    """
    v2.5: 基于 DTW 的时间序列结构相似度。

    核心思想：两个结构的 Cycle 速度比序列越"形状相似"，
    即使时间轴拉伸/压缩，它们的后验行为也越接近。

    返回 [0, 1]，1 = 完全相同，0 = 完全不同。
    """
    seq1 = _series_from_structure(s1)
    seq2 = _series_from_structure(s2)

    if not seq1 or not seq2:
        return 0.0

    # 归一化
    n1 = _normalize_series(seq1)
    n2 = _normalize_series(seq2)

    # DTW 距离
    dist = _dtw_distance(n1, n2, window=max(len(n1), len(n2)) // 2)

    # 转换为相似度 [0, 1]
    # 典型 DTW 距离在 [0, sqrt(n)] 范围，用 sigmoid 压缩
    max_len = max(len(n1), len(n2))
    if max_len == 0:
        return 0.0
    normalized_dist = dist / math.sqrt(max_len)
    return 1.0 / (1.0 + normalized_dist)


def segment_shape_similarity(s1: Structure, s2: Structure) -> float:
    """
    v2.5: 段级形状相似度 — 比较两个结构的段序列形状。

    不只比较不变量，而是直接比较段的 (方向, 相对幅度, 相对时长) 序列。
    用编辑距离 (Levenshtein) 度量序列差异。
    """
    if not s1.cycles or not s2.cycles:
        return 0.0

    def _seg_signature(cycle: Cycle) -> str:
        """将 Cycle 编码为离散符号"""
        # 速度比分桶
        sr = cycle.speed_ratio
        if sr > 1.5:
            sr_bin = "F"  # Fast
        elif sr > 0.8:
            sr_bin = "M"  # Medium
        else:
            sr_bin = "S"  # Slow

        # 时间比分桶
        tr = cycle.time_ratio
        if tr > 1.5:
            tr_bin = "L"  # Long entry
        elif tr > 0.8:
            tr_bin = "E"  # Equal
        else:
            tr_bin = "S"  # Short entry

        # 方向
        d = "U" if cycle.entry.direction.value > 0 else "D"

        return f"{d}{sr_bin}{tr_bin}"

    seq1 = [_seg_signature(c) for c in s1.cycles]
    seq2 = [_seg_signature(c) for c in s2.cycles]

    # 编辑距离
    n, m = len(seq1), len(seq2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )

    max_len = max(n, m)
    if max_len == 0:
        return 1.0
    return 1.0 - dp[n][m] / max_len
