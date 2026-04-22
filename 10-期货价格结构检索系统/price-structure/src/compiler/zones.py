"""
关键区识别 — 对极值点做 1D 价格聚类

修复：
1. 高低点用交替序列判定（不排除首尾）
2. 聚类用固定容差（避免动态中心漂移）

V1.6 P0 新增：
3. 共同反差推断 — V1.6 定义 2.2, 命题 2.3
   基于极值点的时序特征推断驱动聚簇的外部反差类型
"""

from __future__ import annotations
from src.models import Point, Zone, ZoneSource, ContrastType


def _classify_highs_lows(pivots: list[Point]) -> tuple[list[Point], list[Point]]:
    """
    把 pivot 分成高点与低点：
    - 交替序列中相邻点类型不同
    - 首点用与第二点的比较来定性
    """
    if len(pivots) < 2:
        return [], []

    highs, lows = [], []

    if pivots[0].x > pivots[1].x:
        highs.append(pivots[0])
        start_is_high = True
    else:
        lows.append(pivots[0])
        start_is_high = False

    is_high = not start_is_high
    for p in pivots[1:]:
        if is_high:
            highs.append(p)
        else:
            lows.append(p)
        is_high = not is_high

    return highs, lows


def _cluster_by_fixed_pct(
    points: list[Point],
    eps: float,
) -> list[list[Point]]:
    """
    基于"范围容差"的聚类，避免动态中心漂移。
    按价格排序后贪心合并：若新点与当前簇的价格范围差 <= eps*center，则合并。
    """
    if not points:
        return []
    sorted_pts = sorted(points, key=lambda p: p.x)
    clusters: list[list[Point]] = [[sorted_pts[0]]]

    for p in sorted_pts[1:]:
        last_cluster = clusters[-1]
        cmin = min(pt.x for pt in last_cluster)
        cmax = max(pt.x for pt in last_cluster)
        center = (cmin + cmax) / 2
        tol = center * eps
        if p.x - cmax <= tol:
            last_cluster.append(p)
        else:
            clusters.append([p])
    return clusters


def _infer_contrast(cluster: list[Point]) -> tuple[ContrastType, str]:
    """
    V1.6 定义 2.2: 共同反差推断
    基于极值点的时序密集度推断驱动聚簇的外部反差类型。

    逻辑：
    - 极值点在极短时间内密集出现（<30天内 ≥3次） → 恐慌 PANIC
    - 极值点在长时间内缓慢聚集（跨度 >180天）    → 过剩 OVERSUPPLY
    - 中等时间跨度、规则间隔                       → 政策 POLICY
    - 其他                                        → 未知 UNKNOWN
    """
    if len(cluster) < 2:
        return ContrastType.UNKNOWN, ""

    times = sorted([p.t for p in cluster])
    total_span = (times[-1] - times[0]).days if len(times) >= 2 else 0

    # 计算相邻极值点的平均间隔
    if len(times) >= 2:
        gaps = [(times[i + 1] - times[i]).days for i in range(len(times) - 1)]
        avg_gap = sum(gaps) / len(gaps)
    else:
        avg_gap = 0

    n = len(cluster)

    # 恐慌：密集爆发（短时间多次试探同一价位）
    if total_span < 30 and n >= 3:
        return ContrastType.PANIC, f"{n}次试探密集在{total_span}天内"

    # 过剩：长时间缓慢堆积
    if total_span > 180:
        return ContrastType.OVERSUPPLY, f"{n}次试探跨越{total_span}天"

    # 政策驱动：中等时间、间隔较均匀
    if 30 <= total_span <= 180 and len(cluster) >= 3:
        if avg_gap > 0:
            gaps = [(times[i + 1] - times[i]).days for i in range(len(times) - 1)]
            gap_cv = (sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)) ** 0.5 / avg_gap
            if gap_cv < 0.5:
                return ContrastType.POLICY, f"试探间隔均匀(平均{avg_gap:.0f}天)"

    return ContrastType.UNKNOWN, ""


def detect_zones(
    pivots: list[Point],
    zone_bandwidth: float = 0.01,
    cluster_eps: float = 0.015,
    cluster_min_points: int = 2,
) -> list[Zone]:
    if len(pivots) < 2:
        return []

    highs, lows = _classify_highs_lows(pivots)

    def _build(points: list[Point], source: ZoneSource) -> list[Zone]:
        if not points:
            return []
        clusters = _cluster_by_fixed_pct(points, cluster_eps)
        zones: list[Zone] = []
        for cl in clusters:
            if len(cl) < cluster_min_points:
                continue
            center = sum(p.x for p in cl) / len(cl)
            bw = center * zone_bandwidth
            price_range = max(p.x for p in cl) - min(p.x for p in cl)
            compactness = 1.0 / (1.0 + price_range / center)
            strength = len(cl) * compactness

            # ── V1.6 P0: 共同反差推断 ──
            contrast_type, contrast_label = _infer_contrast(cl)

            zones.append(Zone(
                price_center=center,
                bandwidth=bw,
                source=source,
                strength=strength,
                touches=list(cl),
                context_contrast=contrast_type,
                contrast_label=contrast_label,
            ))
        return zones

    zones: list[Zone] = []
    zones.extend(_build(highs, ZoneSource.HIGH_CLUSTER))
    zones.extend(_build(lows, ZoneSource.LOW_CLUSTER))
    zones.sort(key=lambda z: z.strength, reverse=True)
    return zones
