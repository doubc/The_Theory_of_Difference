"""
关键区识别 — 对极值点做价格聚类
"""

from __future__ import annotations

from src.models import Point, Zone, ZoneSource


def detect_zones(
    pivots: list[Point],
    zone_bandwidth: float = 0.01,
    cluster_eps: float = 0.015,
    cluster_min_points: int = 2,
) -> list[Zone]:
    """
    Zone 识别流程：

    1. 分离高点和低点（通过与邻居比较）
    2. 对高点/低点分别做 1D 聚类（按相对价格距离）
    3. 每个聚类生成一个 Zone
    """
    if not pivots:
        return []

    high_points: list[Point] = []
    low_points: list[Point] = []

    for i, p in enumerate(pivots):
        if i == 0 or i == len(pivots) - 1:
            continue
        if p.x > pivots[i - 1].x and p.x > pivots[i + 1].x:
            high_points.append(p)
        elif p.x < pivots[i - 1].x and p.x < pivots[i + 1].x:
            low_points.append(p)

    def cluster_points(points: list[Point], source: ZoneSource) -> list[Zone]:
        if not points:
            return []
        sorted_pts = sorted(points, key=lambda p: p.x)
        clusters: list[list[Point]] = [[sorted_pts[0]]]

        for p in sorted_pts[1:]:
            center = sum(pt.x for pt in clusters[-1]) / len(clusters[-1])
            if abs(p.x - center) / center <= cluster_eps:
                clusters[-1].append(p)
            else:
                clusters.append([p])

        result = []
        for cluster in clusters:
            if len(cluster) < cluster_min_points:
                continue
            center = sum(p.x for p in cluster) / len(cluster)
            bw = center * zone_bandwidth

            n_touches = len(cluster)
            price_range = max(p.x for p in cluster) - min(p.x for p in cluster)
            compactness = 1.0 / (1.0 + price_range / center)
            strength = n_touches * compactness

            result.append(Zone(
                price_center=center,
                bandwidth=bw,
                source=source,
                strength=strength,
                touches=cluster,
            ))
        return result

    zones = []
    zones.extend(cluster_points(high_points, ZoneSource.HIGH_CLUSTER))
    zones.extend(cluster_points(low_points, ZoneSource.LOW_CLUSTER))
    zones.sort(key=lambda z: z.strength, reverse=True)
    return zones
