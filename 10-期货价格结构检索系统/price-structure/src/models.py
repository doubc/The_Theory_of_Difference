"""
价格结构形式系统 — 对象模型定义

Point → Segment → Zone → Cycle → Structure → Bundle

设计原则：
1. 对象只保存状态，不做复杂计算（计算放在 relations / invariants）
2. 所有对象支持 to_dict / from_dict（JSON 友好）
3. Point 只保留 (t, x, idx)，其它属性由算子推导
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


# ─── 枚举类型 ───────────────────────────────────────────────

class Direction(Enum):
    UP = 1
    DOWN = -1
    FLAT = 0

    @classmethod
    def from_delta(cls, delta: float, eps: float = 1e-9) -> Direction:
        """从价格差推断方向"""
        if delta > eps:
            return cls.UP
        if delta < -eps:
            return cls.DOWN
        return cls.FLAT


class ZoneSource(Enum):
    HIGH_CLUSTER = "high_cluster"
    LOW_CLUSTER = "low_cluster"
    PIVOT = "pivot"
    VOLUME = "volume"


class Phase(Enum):
    """结构生命周期阶段"""
    FORMATION = "formation"       # 生成
    CONFIRMATION = "confirmation"  # 确认
    BREAKDOWN = "breakdown"       # 破坏
    INVERSION = "inversion"       # 反演


# ─── 基础对象 ──────────────────────────────────────────────

@dataclass
class Point:
    """极值点"""
    t: datetime                  # 时间
    x: float                     # 价格位置
    idx: int = 0                 # 在原始序列中的索引

    @property
    def log_x(self) -> float:
        """对数价格 — 消除宏观量纲漂移，关注比例关系"""
        return math.log(self.x) if self.x > 0 else float("-inf")

    def to_dict(self) -> dict:
        return {"t": self.t.isoformat(), "x": self.x, "idx": self.idx}

    @classmethod
    def from_dict(cls, d: dict) -> Point:
        return cls(
            t=datetime.fromisoformat(d["t"]),
            x=d["x"],
            idx=d.get("idx", 0),
        )

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
        if self.start.t != self.end.t:
            days = (self.end.t - self.start.t).days
            if days == 0:
                days = (self.end.t - self.start.t).total_seconds() / 86400
            self.duration = days
        self.delta = self.end.x - self.start.x
        if self.duration > 0:
            self.avg_rate = self.delta / self.duration
        self.direction = Direction.from_delta(self.delta)

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)

    @property
    def abs_rate(self) -> float:
        return abs(self.avg_rate)

    @property
    def log_delta(self) -> float:
        """对数差分 — 跨品种可比"""
        return self.end.log_x - self.start.log_x

    @property
    def log_rate(self) -> float:
        """对数速率 — 跨品种可比"""
        return self.log_delta / self.duration if self.duration > 0 else 0.0

    @property
    def abs_log_rate(self) -> float:
        return abs(self.log_rate)

    def to_dict(self) -> dict:
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "duration": self.duration,
            "delta": self.delta,
            "avg_rate": self.avg_rate,
            "direction": self.direction.value,
            "noise_level": self.noise_level,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Segment:
        seg = cls(
            start=Point.from_dict(d["start"]),
            end=Point.from_dict(d["end"]),
        )
        # __post_init__ 已经推断了，但如果 dict 有显式值就用显式值
        if "noise_level" in d:
            seg.noise_level = d["noise_level"]
        return seg

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

    @property
    def relative_bandwidth(self) -> float:
        """相对带宽 (消除价格量纲，关注结构紧凑度)"""
        return self.bandwidth / self.price_center if self.price_center > 0 else 0.0

    def contains(self, price: float) -> bool:
        return self.lower <= price <= self.upper

    def distance_to(self, price: float) -> float:
        """价格到区边界的距离"""
        if self.contains(price):
            return 0.0
        if price > self.upper:
            return price - self.upper
        return self.lower - price

    def compute_strength(self, decay: float = 0.9) -> float:
        """strength = Σ decay^i（试探次数 × 距离衰减）"""
        self.strength = sum(decay ** i for i in range(len(self.touches)))
        return self.strength

    def to_dict(self) -> dict:
        return {
            "price_center": self.price_center,
            "bandwidth": self.bandwidth,
            "source": self.source.value,
            "strength": self.strength,
            "touches": [p.to_dict() for p in self.touches],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Zone:
        return cls(
            price_center=d["price_center"],
            bandwidth=d["bandwidth"],
            source=ZoneSource(d["source"]),
            strength=d.get("strength", 0.0),
            touches=[Point.from_dict(p) for p in d.get("touches", [])],
        )

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
        if self.entry.abs_rate == 0 or self.exit.abs_rate == 0:
            return 0.0
        return self.exit.abs_rate / self.entry.abs_rate

    @property
    def log_speed_ratio(self) -> float:
        """对数速度比 — 品种无关"""
        le, lx = abs(self.entry.log_rate), abs(self.exit.log_rate)
        if le == 0 or lx == 0:
            return 0.0
        return lx / le

    @property
    def time_ratio(self) -> float:
        """时间比 Δt_entry / Δt_exit"""
        if self.exit.duration == 0 or self.entry.duration == 0:
            return 0.0
        return self.entry.duration / self.exit.duration

    @property
    def amplitude_ratio(self) -> float:
        """幅度比 |Δ_exit| / |Δ_entry|"""
        if self.entry.abs_delta == 0:
            return 0.0
        return self.exit.abs_delta / self.entry.abs_delta

    def to_dict(self) -> dict:
        return {
            "entry": self.entry.to_dict(),
            "exit": self.exit.to_dict(),
            "speed_ratio": self.speed_ratio,
            "time_ratio": self.time_ratio,
            "amplitude_ratio": self.amplitude_ratio,
        }

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
    label: Optional[str] = None   # 规则引擎打的标签
    symbol: Optional[str] = None  # 品种
    t_start: Optional[datetime] = None
    t_end: Optional[datetime] = None

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
    def avg_log_speed_ratio(self) -> float:
        """对数速度比均值 — 品种无关"""
        if not self.cycles:
            return 0.0
        return sum(c.log_speed_ratio for c in self.cycles) / len(self.cycles)

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

    @property
    def high_cluster_cv(self) -> float:
        """高点聚集度（变异系数，无量纲）"""
        highs = [p.x for c in self.cycles
                 for p in [c.entry.end, c.exit.start]
                 if p.x > self.zone.price_center]
        if len(highs) < 2:
            return 0.0
        mean = sum(highs) / len(highs)
        if mean == 0:
            return 0.0
        stddev = (sum((x - mean) ** 2 for x in highs) / len(highs)) ** 0.5
        return stddev / mean

    def signature(self) -> str:
        """结构签名 — 用于检索与去重"""
        parts = [
            f"n={self.cycle_count}",
            f"sr={self.avg_speed_ratio:.2f}",
            f"tr={self.avg_time_ratio:.2f}",
            f"zbw={self.zone.relative_bandwidth:.3f}",
        ]
        return "|".join(parts)

    def to_dict(self) -> dict:
        return {
            "zone": self.zone.to_dict(),
            "cycles": [c.to_dict() for c in self.cycles],
            "phases": [p.value for p in self.phases],
            "invariants": self.invariants,
            "typicality": self.typicality,
            "label": self.label,
            "symbol": self.symbol,
            "t_start": self.t_start.isoformat() if self.t_start else None,
            "t_end": self.t_end.isoformat() if self.t_end else None,
            "signature": self.signature(),
        }

    def __repr__(self):
        return (f"Structure(zone={self.zone}, cycles={self.cycle_count}, "
                f"typicality={self.typicality:.2f})")


@dataclass
class Bundle:
    """丛 — 共享生成约束的多个 Structure 的集合"""
    structures: list[Structure] = field(default_factory=list)
    generator_constraint: str = ""  # 共同生成约束描述

    def to_dict(self) -> dict:
        return {
            "generator_constraint": self.generator_constraint,
            "structures": [s.to_dict() for s in self.structures],
        }

    def __repr__(self):
        return f"Bundle({len(self.structures)} structures)"


# ─── 关系算子（不存储，计算时使用）────────────────────────────

def first_diff(p1: Point, p2: Point) -> float:
    """一阶差分：两点间价格差"""
    return p2.x - p1.x


def log_diff(p1: Point, p2: Point) -> float:
    """对数差分 — 品种无关"""
    return p2.log_x - p1.log_x


def second_diff(p1: Point, p2: Point, p3: Point) -> float:
    """二阶差分：三点间曲率"""
    return (p3.x - 2 * p2.x + p1.x)


def time_gap(p1: Point, p2: Point) -> float:
    """两点间时间差（天数）"""
    return (p2.t - p1.t).days


def distance_to_zone(p: Point, z: Zone) -> float:
    """点到区的距离"""
    return z.distance_to(p.x)


def relative_distance_to_zone(p: Point, z: Zone) -> float:
    """相对距离 — 以 Zone 带宽为单位"""
    if z.bandwidth == 0:
        return 0.0
    return z.distance_to(p.x) / z.bandwidth


def extrema_dispersion(points: list[Point]) -> float:
    """极值点价格的相对标准差 (CV)"""
    if len(points) < 2:
        return 0.0
    prices = [p.x for p in points]
    mean = sum(prices) / len(prices)
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in prices) / len(prices)
    return math.sqrt(var) / mean


def extrema_similarity(points1: list[Point], points2: list[Point]) -> float:
    """极值点相似度（简化版，后续在 M7 完善）"""
    # TODO: 实现 DTW 或其他相似度度量
    return 0.0
