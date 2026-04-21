"""
价格结构形式系统 — 对象模型定义

Point → Segment → Zone → Cycle → Structure → Bundle
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


# ─── 枚举类型 ───────────────────────────────────────────────

class Direction(Enum):
    UP = 1
    DOWN = -1
    FLAT = 0


class ZoneSource(Enum):
    HIGH_CLUSTER = "high_cluster"
    LOW_CLUSTER = "low_cluster"
    PIVOT = "pivot"
    VOLUME = "volume"


class Phase(Enum):
    """结构生命周期阶段"""
    FORMATION = "formation"       # 生成
    CONFIRMATION = "confirmation" # 确认
    BREAKDOWN = "breakdown"       # 破坏
    INVERSION = "inversion"       # 反演


# ─── 基础对象 ──────────────────────────────────────────────

@dataclass
class Point:
    """极值点"""
    t: datetime                  # 时间
    x: float                     # 价格位置
    idx: int = 0                 # 在原始序列中的索引

    def __repr__(self):
        return f"Point(t={self.t:%Y-%m-%d}, x={self.x:.2f})"


@dataclass
class Segment:
    """段 — 两个相邻极值点之间的连线"""
    start: Point
    end: Point
    duration: float = 0.0        # 持续时间（天数）
    delta: float = 0.0           # 价格变化量
    avg_rate: float = 0.0        # 平均速率
    direction: Direction = Direction.FLAT
    noise_level: float = 0.0     # 噪声水平

    def __post_init__(self):
        if self.duration == 0 and self.start.t != self.end.t:
            self.duration = (self.end.t - self.start.t).days
        if self.delta == 0:
            self.delta = self.end.x - self.start.x
        if self.avg_rate == 0 and self.duration > 0:
            self.avg_rate = self.delta / self.duration
        if self.direction == Direction.FLAT:
            if self.delta > 0:
                self.direction = Direction.UP
            elif self.delta < 0:
                self.direction = Direction.DOWN

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)

    @property
    def abs_rate(self) -> float:
        return abs(self.avg_rate)

    def __repr__(self):
        arrow = "↑" if self.direction == Direction.UP else "↓" if self.direction == Direction.DOWN else "→"
        return f"Segment({arrow} {self.delta:+.2f} in {self.duration:.0f}d)"


@dataclass
class Zone:
    """关键区 — 价格聚集或反复试探的区间"""
    price_center: float
    bandwidth: float             # 带宽（半宽度）
    source: ZoneSource = ZoneSource.PIVOT
    strength: float = 0.0        # 强度
    touches: list[Point] = field(default_factory=list)  # 触及该区的极值点

    @property
    def upper(self) -> float:
        return self.price_center + self.bandwidth

    @property
    def lower(self) -> float:
        return self.price_center - self.bandwidth

    def contains(self, price: float) -> bool:
        return self.lower <= price <= self.upper

    def distance_to(self, price: float) -> float:
        """价格到区边界的距离"""
        if self.contains(price):
            return 0.0
        if price > self.upper:
            return price - self.upper
        return self.lower - price

    def __repr__(self):
        return f"Zone(center={self.price_center:.2f}, bw=±{self.bandwidth:.2f}, strength={self.strength:.1f})"


@dataclass
class Cycle:
    """循环 — 进入关键区到离开关键区的过程"""
    entry: Segment               # 进入段
    exit: Segment                # 离开段
    zone: Zone

    @property
    def speed_ratio(self) -> float:
        """速度比 |v_exit| / |v_entry|"""
        if self.entry.abs_rate == 0:
            return 0.0
        if self.exit.abs_rate == 0:
            return 0.0
        return self.exit.abs_rate / self.entry.abs_rate

    @property
    def time_ratio(self) -> float:
        """时间比 Δt_entry / Δt_exit"""
        if self.exit.duration == 0 or self.entry.duration == 0:
            return 0.0
        return self.entry.duration / self.exit.duration

    def __repr__(self):
        return (f"Cycle(entry={self.entry}, exit={self.exit}, "
                f"speed_r={self.speed_ratio:.2f}, time_r={self.time_ratio:.2f})")


@dataclass
class Structure:
    """结构 — 围绕一个区组织的多个 Cycle 的集合"""
    zone: Zone
    cycles: list[Cycle] = field(default_factory=list)
    phases: list[Phase] = field(default_factory=list)
    invariants: dict = field(default_factory=dict)
    typicality: float = 0.0      # 典型度 [0, 1]

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)

    @property
    def avg_speed_ratio(self) -> float:
        if not self.cycles:
            return 0.0
        return sum(c.speed_ratio for c in self.cycles) / len(self.cycles)

    @property
    def avg_time_ratio(self) -> float:
        if not self.cycles:
            return 0.0
        return sum(c.time_ratio for c in self.cycles) / len(self.cycles)

    @property
    def high_cluster_stddev(self) -> float:
        """高点聚集度"""
        highs = [p.x for c in self.cycles
                 for p in [c.entry.end, c.exit.start]
                 if p.x > self.zone.price_center]
        if len(highs) < 2:
            return 0.0
        mean = sum(highs) / len(highs)
        return (sum((x - mean) ** 2 for x in highs) / len(highs)) ** 0.5

    def __repr__(self):
        return (f"Structure(zone={self.zone}, cycles={self.cycle_count}, "
                f"typicality={self.typicality:.2f})")


@dataclass
class Bundle:
    """丛 — 共享生成约束的多个 Structure 的集合"""
    structures: list[Structure] = field(default_factory=list)
    generator_constraint: str = ""  # 共同生成约束描述

    def __repr__(self):
        return f"Bundle({len(self.structures)} structures)"


# ─── 关系算子（不存储，计算时使用）────────────────────────────

def first_diff(p1: Point, p2: Point) -> float:
    """一阶差分：两点间价格差"""
    return p2.x - p1.x


def second_diff(p1: Point, p2: Point, p3: Point) -> float:
    """二阶差分：三点间曲率"""
    return (p3.x - 2 * p2.x + p1.x)


def distance_to_zone(p: Point, z: Zone) -> float:
    """点到区的距离"""
    return z.distance_to(p.x)


def extrema_similarity(points1: list[Point], points2: list[Point]) -> float:
    """极值点相似度（简化版，后续在 M7 完善）"""
    # TODO: 实现 DTW 或其他相似度度量
    return 0.0
