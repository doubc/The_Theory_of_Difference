"""
关系算子层 — 不存储，纯计算
所有"点间/段间/结构间"的关系在这里定义
"""

from __future__ import annotations
import math
from typing import Sequence
from src.models import Point, Segment, Zone, Structure


# ─── 点间 ──────────────────────────────────────────────────

def first_diff(p1: Point, p2: Point) -> float:
    return p2.x - p1.x


def log_diff(p1: Point, p2: Point) -> float:
    return p2.log_x - p1.log_x


def second_diff(p1: Point, p2: Point, p3: Point) -> float:
    return p3.x - 2 * p2.x + p1.x


def time_gap_days(p1: Point, p2: Point) -> float:
    return (p2.t - p1.t).days


# ─── 段间 ──────────────────────────────────────────────────

def segment_speed_ratio(s1: Segment, s2: Segment) -> float:
    if s1.abs_rate == 0:
        return float("inf") if s2.abs_rate > 0 else 0.0
    return s2.abs_rate / s1.abs_rate


def segment_log_speed_ratio(s1: Segment, s2: Segment) -> float:
    a, b = abs(s1.log_rate), abs(s2.log_rate)
    if a == 0:
        return float("inf") if b > 0 else 0.0
    return b / a


def segment_time_ratio(s1: Segment, s2: Segment) -> float:
    if s2.duration == 0:
        return 0.0
    return s1.duration / s2.duration


def direction_change(s1: Segment, s2: Segment) -> int:
    prod = s1.direction.value * s2.direction.value
    if prod < 0:
        return 1
    if prod > 0:
        return 0
    return -1


# ─── 点与 Zone ─────────────────────────────────────────────

def distance_to_zone(p: Point, z: Zone) -> float:
    return z.distance_to(p.x)


def relative_distance_to_zone(p: Point, z: Zone) -> float:
    if z.bandwidth == 0:
        return 0.0
    return z.distance_to(p.x) / z.bandwidth


# ─── 极值点聚集度 ──────────────────────────────────────────

def extrema_dispersion(points: Sequence[Point]) -> float:
    if len(points) < 2:
        return 0.0
    prices = [p.x for p in points]
    mean = sum(prices) / len(prices)
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in prices) / len(prices)
    return math.sqrt(var) / mean


def extrema_trend(points: Sequence[Point]) -> float:
    if len(points) < 2:
        return 0.0
    n = len(points)
    xs = list(range(n))
    ys = [p.x for p in points]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    if den == 0 or my == 0:
        return 0.0
    return (num / den) / my


# ─── 结构级不变量 ──────────────────────────────────────────

def structure_invariants(s: Structure) -> dict:
    """把结构的所有不变量打包成 dict（全部归一化为无量纲比率）"""
    highs_above: list[Point] = []
    lows_below: list[Point] = []
    for c in s.cycles:
        for p in (c.entry.start, c.entry.end, c.exit.start, c.exit.end):
            if p.x >= s.zone.price_center:
                highs_above.append(p)
            else:
                lows_below.append(p)

    # 对数速度比均值（消除绝对价格影响）
    log_srs = [c.log_speed_ratio for c in s.cycles if c.log_speed_ratio > 0]
    avg_log_sr = sum(log_srs) / len(log_srs) if log_srs else 0.0

    return {
        "cycle_count": s.cycle_count,
        "avg_speed_ratio": s.avg_speed_ratio,       # 速度比：|v_exit| / |v_entry|
        "avg_log_speed_ratio": avg_log_sr,          # 对数速度比：更稳健的比例度量
        "avg_time_ratio": s.avg_time_ratio,         # 时间比：Δt_entry / Δt_exit
        "high_dispersion": extrema_dispersion(highs_above),  # 高点聚集度 (CV)
        "low_dispersion": extrema_dispersion(lows_below),    # 低点聚集度 (CV)
        "high_trend": extrema_trend(highs_above),   # 高点趋势斜率 (归一化)
        "low_trend": extrema_trend(lows_below),     # 低点趋势斜率 (归一化)
        "zone_rel_bw": s.zone.relative_bandwidth,   # 相对带宽：bw / center
        "zone_strength": s.zone.strength,           # 强度：试探次数加权
    }
