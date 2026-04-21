"""
关键区识别 — 对极值点做 1D 价格聚类

修复：
1. 高低点用交替序列判定（不排除首尾）
2. 聚类用固定容差（避免动态中心漂移）
"""

from __future__ import annotations
from src.models import Point, Zone, ZoneSource


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
            zones.append(Zone(
                price_center=center,
                bandwidth=bw,
                source=source,
                strength=strength,
                touches=list(cl),
            ))
        return zones

    zones: list[Zone] = []
    zones.extend(_build(highs, ZoneSource.HIGH_CLUSTER))
    zones.extend(_build(lows, ZoneSource.LOW_CLUSTER))
    zones.sort(key=lambda z: z.strength, reverse=True)
    return zones
