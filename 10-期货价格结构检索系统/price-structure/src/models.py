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


class ContrastType(Enum):
    """
    共同反差类型 — V1.6 定义 2.2
    驱动多个极值点聚拢的外部差异类型。
    不同反差即使价格相近，也不应归为同一结构。
    """
    PANIC = "panic"              # 恐慌性抛售/抢购（金融危机、黑天鹅）
    OVERSUPPLY = "oversupply"    # 产能过剩/供需失衡
    POLICY = "policy"            # 政策驱动（限产、关税、补贴）
    LIQUIDITY = "liquidity"      # 流动性驱动（宽松/紧缩周期）
    SPECULATION = "speculation"  # 投机驱动（资金推动）
    UNKNOWN = "unknown"          # 未分类


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
    # ── V1.6 P0 新增 ──
    context_contrast: ContrastType = ContrastType.UNKNOWN  # 共同反差类型（V1.6 定义 2.2）
    contrast_label: str = ""     # 反差的人可读描述

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
            "context_contrast": self.context_contrast.value,
            "contrast_label": self.contrast_label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Zone:
        return cls(
            price_center=d["price_center"],
            bandwidth=d["bandwidth"],
            source=ZoneSource(d["source"]),
            strength=d.get("strength", 0.0),
            touches=[Point.from_dict(p) for p in d.get("touches", [])],
            context_contrast=ContrastType(d.get("context_contrast", "unknown")),
            contrast_label=d.get("contrast_label", ""),
        )

    def __repr__(self):
        return f"Zone(center={self.price_center:.2f}, bw=±{self.bandwidth:.2f}, strength={self.strength:.1f})"


@dataclass
class NearestStableState:
    """
    最近稳态 — V1.6 命题 3.4/3.5, 4.4/4.5, 7.6
    差异转移后，系统最先停驻的可稳住安排。
    不是最优解，而是最先可用的解。
    """
    zone: Zone | None = None           # 稳态所在的价位区
    arrival_point: Point | None = None # 到达稳态的极值点
    duration_to_arrive: float = 0.0    # 从 exit 到达稳态的天数
    resistance_level: float = 0.0      # 阻力评分（越低越容易到达）

    def to_dict(self) -> dict:
        return {
            "zone": self.zone.to_dict() if self.zone else None,
            "arrival_point": self.arrival_point.to_dict() if self.arrival_point else None,
            "duration_to_arrive": self.duration_to_arrive,
            "resistance_level": self.resistance_level,
        }

    @classmethod
    def from_dict(cls, d: dict) -> NearestStableState:
        return cls(
            zone=Zone.from_dict(d["zone"]) if d.get("zone") else None,
            arrival_point=Point.from_dict(d["arrival_point"]) if d.get("arrival_point") else None,
            duration_to_arrive=d.get("duration_to_arrive", 0.0),
            resistance_level=d.get("resistance_level", 0.0),
        )

    def __repr__(self):
        if self.zone:
            return f"NearestStable(zone={self.zone.price_center:.2f}, days={self.duration_to_arrive:.0f})"
        return "NearestStable(None)"


@dataclass
class Cycle:
    """循环 — 进入关键区到离开关键区的过程"""
    entry: Segment               # 进入段
    exit: Segment                # 离开段
    zone: Zone
    # ── V1.6 P0 新增 ──
    next_stable: NearestStableState | None = None  # 最近稳态（V1.6 命题 3.4）

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

    @property
    def has_stable_state(self) -> bool:
        """是否已识别最近稳态"""
        return self.next_stable is not None and self.next_stable.zone is not None

    def to_dict(self) -> dict:
        return {
            "entry": self.entry.to_dict(),
            "exit": self.exit.to_dict(),
            "speed_ratio": self.speed_ratio,
            "time_ratio": self.time_ratio,
            "amplitude_ratio": self.amplitude_ratio,
            "next_stable": self.next_stable.to_dict() if self.next_stable else None,
        }

    def __repr__(self):
        stable_str = f", stable={self.next_stable}" if self.has_stable_state else ""
        return (f"Cycle(entry={self.entry}, exit={self.exit}, "
                f"speed_r={self.speed_ratio:.2f}, time_r={self.time_ratio:.2f}{stable_str})")


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
    # ── V1.6 P0 新增 ──
    narrative_context: str = ""  # 结构形成时的市场叙事背景（V1.6 命题 2.3 可叙事性）
    motion: MotionState | None = None  # 运动态（V1.6「系统 = 结构 × 运动」）
    projection: ProjectionAwareness | None = None  # 投影觉知（D0：价格=影子）
    # ── V1.6 P1 新增：差异分层（Ch6 三种差异）──
    liquidity_stress: float = 0.0   # 流动性差异：Zone内外成交量变异系数比 (D6.3)
    fear_index: float = 0.0         # 边界恐惧：跳空+波动率突变+试探密集度 (D6.4)
    time_compression: float = 0.0   # 时间差异：avg_entry_dur / avg_exit_dur (D6.2)
    # ── V1.6 P1 新增：稳定性判定（D7.2 错觉检测）──
    stability_verdict: StabilityVerdict | None = None

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

    @property
    def stable_state_ratio(self) -> float:
        """已识别最近稳态的 Cycle 占比 — V1.6 命题 3.4"""
        if not self.cycles:
            return 0.0
        return sum(1 for c in self.cycles if c.has_stable_state) / len(self.cycles)

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
            "narrative_context": self.narrative_context,
            "motion": self.motion.to_dict() if self.motion else None,
            "projection": self.projection.to_dict() if self.projection else None,
            "stable_state_ratio": self.stable_state_ratio,
            "signature": self.signature(),
            "liquidity_stress": self.liquidity_stress,
            "fear_index": self.fear_index,
            "time_compression": self.time_compression,
            "stability_verdict": self.stability_verdict.to_dict() if self.stability_verdict else None,
        }

    def __repr__(self):
        return (f"Structure(zone={self.zone}, cycles={self.cycle_count}, "
                f"typicality={self.typicality:.2f})")


@dataclass
class ProjectionAwareness:
    """
    投影觉知 — D0 章 + v2.5 D0.3 深化
    价格 = Π(现实差异)，代码分析的是影子，不是实体。
    此对象记录系统对自身认知边界的觉知。

    v2.5: 增加 recommended_actions（系统建议研究者做什么）
          和 blind_evidence（每个盲区通道的具体证据）
    """
    compression_level: float = 0.0   # 投影压缩度 [0,1]，越高=价格越平但底层差异可能越大
    blind_channels: list[str] = field(default_factory=list)  # 可能携带被压缩差异的通道
    projection_confidence: float = 1.0  # 当前投影的可信度（制度变化时下降）
    observation: str = ""  # 人可读：系统看到了什么、没看到什么
    # ── v2.5 D0.3 新增 ──
    recommended_actions: list[str] = field(default_factory=list)  # 系统建议研究者做什么
    blind_evidence: dict = field(default_factory=dict)  # 每个盲区通道的具体证据

    @property
    def is_blind(self) -> bool:
        """高压缩度 = 系统可能在看假象"""
        return self.compression_level > 0.7

    def to_dict(self) -> dict:
        return {
            "compression_level": self.compression_level,
            "blind_channels": self.blind_channels,
            "projection_confidence": self.projection_confidence,
            "observation": self.observation,
            "recommended_actions": self.recommended_actions,
            "blind_evidence": self.blind_evidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProjectionAwareness:
        return cls(
            compression_level=d.get("compression_level", 0.0),
            blind_channels=d.get("blind_channels", []),
            projection_confidence=d.get("projection_confidence", 1.0),
            observation=d.get("observation", ""),
            recommended_actions=d.get("recommended_actions", []),
            blind_evidence=d.get("blind_evidence", {}),
        )

    def __repr__(self):
        if self.is_blind:
            return f"⚠️ Projection(blind, 压缩={self.compression_level:.0%}, 可能→{self.blind_channels})"
        return f"Projection(压缩={self.compression_level:.0%}, 可信={self.projection_confidence:.0%})"


@dataclass
class MotionState:
    """
    运动态 — V1.6「系统 = 结构 × 运动」
    描述差异正在如何运动，不只是结构是什么。
    """
    # 阶段转换趋势
    phase_tendency: str = ""        # "→confirmation", "→breakdown", "stable" 等
    phase_confidence: float = 0.0   # 阶段判断的置信度 [0,1]

    # 差异转移流
    transfer_source: str = ""       # 差异从哪流出（"zone_bandwidth", "speed_ratio" 等）
    transfer_target: str = ""       # 差异流向哪（"shorter_timeframe", "volume" 等）
    transfer_strength: float = 0.0  # 转移强度 [0,1]

    # 稳态趋近
    stable_distance: float = 0.0    # 距最近稳态的归一化距离
    stable_velocity: float = 0.0    # 趋近稳态的速度（正=靠近，负=远离）

    # 守恒通量
    conservation_flux: float = 0.0  # 守恒通量（正值=差异在释放，负值=在压缩）
    flux_detail: str = ""           # 人可读的通量说明

    # 系统时间
    structural_age: int = 0         # 结构已有的 cycle 数
    phase_duration: int = 0         # 当前阶段已持续的 cycle 数

    def to_dict(self) -> dict:
        return {
            "phase_tendency": self.phase_tendency,
            "phase_confidence": self.phase_confidence,
            "transfer_source": self.transfer_source,
            "transfer_target": self.transfer_target,
            "transfer_strength": self.transfer_strength,
            "stable_distance": self.stable_distance,
            "stable_velocity": self.stable_velocity,
            "conservation_flux": self.conservation_flux,
            "flux_detail": self.flux_detail,
            "structural_age": self.structural_age,
            "phase_duration": self.phase_duration,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MotionState:
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})

    def __repr__(self):
        return (f"Motion(→{self.phase_tendency} "
                f"flux={self.conservation_flux:+.2f} "
                f"stable_d={self.stable_distance:.2f})")


@dataclass
class StabilityVerdict:
    """
    错觉检测 — V1.6 D7.2 命题 7.4
    系统不应在波动率下降时立即报告"结构稳定"。
    价格表面变平，差异可能转移到了系统看不到的维度。
    """
    surface: str = "unstable"              # "stable" | "unstable"
    verified: bool = False                 # 是否经过多维度验证
    verification_window: int = 0           # 需要等待多少天才能确认
    pending_channels: list[str] = field(default_factory=list)  # 待检查的转移通道
    verdict_label: str = ""                # 人可读："黄灯" / "绿灯" / "红灯"

    @property
    def traffic_light(self) -> str:
        """红绿灯状态"""
        if self.verified and self.surface == "stable":
            return "🟢 绿灯：结构稳定（已验证）"
        if self.surface == "stable" and not self.verified:
            pending = ", ".join(self.pending_channels) if self.pending_channels else "待确认"
            return f"🟡 黄灯：表面稳定，待验证（{pending}，{self.verification_window}天观察期）"
        return "🔴 红灯：结构不稳定"

    def to_dict(self) -> dict:
        return {
            "surface": self.surface,
            "verified": self.verified,
            "verification_window": self.verification_window,
            "pending_channels": self.pending_channels,
            "verdict_label": self.traffic_light,
        }

    @classmethod
    def from_dict(cls, d: dict) -> StabilityVerdict:
        return cls(
            surface=d.get("surface", "unstable"),
            verified=d.get("verified", False),
            verification_window=d.get("verification_window", 0),
            pending_channels=d.get("pending_channels", []),
        )

    def __repr__(self):
        return self.traffic_light


@dataclass
class SystemState:
    """
    系统态 — V1.6 D9.1「系统 = 结构 × 运动」
    顶层对象，封装一个结构的完整系统状态。
    不是静态快照，而是结构在运动中的瞬时呈现。
    """
    structure: Structure                           # 静态骨架
    motion: MotionState = field(default_factory=MotionState)        # 运动态
    projection: ProjectionAwareness = field(default_factory=ProjectionAwareness)  # 投影觉知
    stability: StabilityVerdict = field(default_factory=StabilityVerdict)         # 稳定性判定
    # ── 差异分层（V1.6 Ch6 三种差异）──
    liquidity_stress: float = 0.0      # 流动性差异：Zone内外成交量CV比 (D6.3)
    fear_index: float = 0.0            # 边界恐惧：跳空+波动率突变+试探密集度 (D6.4)
    time_compression: float = 0.0      # 时间差异：entry_duration / exit_duration (D6.2)

    @property
    def system_time(self) -> dict:
        """系统时间：结构变化的节奏，不是日历时间"""
        return {
            "structural_age": self.motion.structural_age,
            "phase_progress": self.motion.phase_duration,
            "stable_countdown": max(0, self.motion.stable_distance * 20),  # 归一化→天数近似
            "phase_tendency": self.motion.phase_tendency,
        }

    @property
    def is_reliable(self) -> bool:
        """系统态是否可信：非高压缩 + 非黄灯"""
        return not self.projection.is_blind and self.stability.verified

    def narrative_report(self) -> str:
        """自然语言状态报告"""
        parts = []
        st = self.structure

        # 结构是什么
        if st.narrative_context:
            parts.append(f"结构：{st.narrative_context}")
        else:
            parts.append(f"结构：Zone {st.zone.price_center:.0f}，{st.cycle_count}次试探")

        # 在怎么动
        if self.motion.phase_tendency:
            parts.append(f"运动：{self.motion.phase_tendency}，通量{self.motion.conservation_flux:+.2f}")
            if self.motion.flux_detail:
                parts.append(f"  → {self.motion.flux_detail}")

        # 可信度
        parts.append(f"稳定性：{self.stability.traffic_light}")
        if self.projection.is_blind:
            parts.append(f"⚠️ 投影压缩{self.projection.compression_level:.0%}，差异可能藏在：{', '.join(self.projection.blind_channels)}")

        # 差异分层
        layer_parts = []
        if self.liquidity_stress > 1.5:
            layer_parts.append(f"流动性差异释放(应力={self.liquidity_stress:.1f})")
        elif self.liquidity_stress < 0.5 and self.liquidity_stress > 0:
            layer_parts.append(f"流动性枯竭(应力={self.liquidity_stress:.1f})")
        if self.fear_index > 0.6:
            layer_parts.append(f"边界恐惧升高(恐惧={self.fear_index:.2f})")
        if self.time_compression > 1.5:
            layer_parts.append(f"时间差异剧烈(入场慢出场快)")
        elif self.time_compression < 0.67 and self.time_compression > 0:
            layer_parts.append(f"时间差异平缓(入场快出场慢)")
        if layer_parts:
            parts.append("差异分层：" + "，".join(layer_parts))

        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "structure": self.structure.to_dict(),
            "motion": self.motion.to_dict(),
            "projection": self.projection.to_dict(),
            "stability": self.stability.to_dict(),
            "liquidity_stress": self.liquidity_stress,
            "fear_index": self.fear_index,
            "time_compression": self.time_compression,
            "system_time": self.system_time,
            "is_reliable": self.is_reliable,
        }

    def __repr__(self):
        return (f"SystemState(zone={self.structure.zone.price_center:.0f} "
                f"motion={self.motion.phase_tendency} "
                f"stable={self.stability.surface} "
                f"reliable={self.is_reliable})")


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
    """
    极值点序列相似度 — v2.5 实现

    用 DTW (Dynamic Time Warping) 比较两组极值点的价格序列形状。
    允许时间轴非线性拉伸，捕捉"形状相似但时间错位"的结构。

    返回 [0, 1]，1 = 完全相同，0 = 完全不同。
    """
    if not points1 or not points2:
        return 0.0

    # 提取归一化价格序列
    def _normalize(pts: list[Point]) -> list[float]:
        prices = [p.x for p in pts]
        lo, hi = min(prices), max(prices)
        if hi - lo < 1e-12:
            return [0.5] * len(prices)
        return [(p - lo) / (hi - lo) for p in prices]

    seq1 = _normalize(points1)
    seq2 = _normalize(points2)
    n, m = len(seq1), len(seq2)

    # DTW with Sakoe-Chiba band
    window = max(n, m) // 2
    INF = float("inf")
    dtw = [[INF] * (m + 1) for _ in range(n + 1)]
    dtw[0][0] = 0.0

    for i in range(1, n + 1):
        j_lo = max(1, i - window)
        j_hi = min(m, i + window)
        for j in range(j_lo, j_hi + 1):
            cost = (seq1[i - 1] - seq2[j - 1]) ** 2
            dtw[i][j] = cost + min(dtw[i - 1][j], dtw[i][j - 1], dtw[i - 1][j - 1])

    dist = math.sqrt(dtw[n][m])
    max_len = max(n, m)
    normalized_dist = dist / math.sqrt(max_len)
    return 1.0 / (1.0 + normalized_dist)
