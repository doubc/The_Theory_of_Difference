"""
价格结构形式系统 — 对象模型定义

Point → Segment → Zone → Cycle → Structure → Bundle

设计原则：
1. 对象只保存状态，不做复杂计算（计算放在 relations / invariants）
2. 所有对象支持 to_dict / from_dict（JSON 友好）
3. Point 只保留 (t, x, idx)，其它属性由算子推导
4. 类定义顺序：基础类型 → 辅助状态 → 复合对象（消除前向引用）
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


class MarketMovementType(Enum):
    """
    市场运动类型 — 由稳态（NearestStableState）跃迁关系定义。

    震荡：在同一个稳态内部的价格往复运动
    上涨趋势：时序上后一个稳态比前一个稳态的位置高
    下跌趋势：时序上后一个稳态比前一个稳态的位置低
    反转：趋势方向的转换（上涨→下跌，或下跌→上涨）

    与 Phase 的区别：Phase 描述结构的生命周期，MarketMovementType 描述价格在稳态间的运动方式。
    """
    TREND_UP = "trend_up"         # 上涨趋势：后一稳态 > 前一稳态
    TREND_DOWN = "trend_down"     # 下跌趋势：后一稳态 < 前一稳态
    OSCILLATION = "oscillation"   # 震荡：同一稳态内部往复
    REVERSAL = "reversal"         # 反转：趋势方向切换


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


# ─── 辅助状态对象（在 Structure 之前定义，消除前向引用）─────

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
        """高压缩度 = 系统可能在看假象
        
        v3.2: 阈值从 0.7 降至 0.5，适配期货数据特征
        期货品种波动较大，原阈值 0.7 导致盲区检测失效
        """
        return self.compression_level > 0.5

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

    # 运动类型（由稳态跃迁关系判定）
    movement_type: MarketMovementType = MarketMovementType.OSCILLATION  # 趋势/震荡/反转

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
            "movement_type": self.movement_type.value,
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
        import dataclasses
        kwargs = {}
        for f in dataclasses.fields(cls):
            if f.name in d:
                val = d[f.name]
                # 枚举字段：字符串 → 枚举值
                if f.type == "MarketMovementType" and isinstance(val, str):
                    val = MarketMovementType(val)
                kwargs[f.name] = val
            elif f.default is not dataclasses.MISSING:
                kwargs[f.name] = f.default
            elif f.default_factory is not dataclasses.MISSING:
                kwargs[f.name] = f.default_factory()
        return cls(**kwargs)

    def __repr__(self):
        return (f"Motion({self.movement_type.value} "
                f"→{self.phase_tendency} "
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


# ─── 复合对象 ──────────────────────────────────────────────

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
            "movement_type": self.motion.movement_type.value if hasattr(self.motion, 'movement_type') else "",
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
            mt = self.motion.movement_type.value if hasattr(self.motion, 'movement_type') else ""
            mt_cn = {"trend_up": "上涨趋势", "trend_down": "下跌趋势",
                     "oscillation": "震荡", "reversal": "反转"}.get(mt, "")
            parts.append(f"运动：{mt_cn or self.motion.phase_tendency}，通量{self.motion.conservation_flux:+.2f}")
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


# ─── 交易信号层 ──────────────────────────────────────────

class SignalKind(Enum):
    """信号类型 — 来自多视角交集分析的5种信号"""
    BREAKOUT_CONFIRM = "breakout_confirm"    # Zone突破确认
    FAKE_BREAKOUT = "fake_breakout"          # 假突破反向信号
    PULLBACK_CONFIRM = "pullback_confirm"    # 回踩确认入场（TA专属）
    STRUCTURE_EXPIRED = "structure_expired"   # 结构老化失效
    BLIND_BREAKOUT = "blind_breakout"         # 盲区突破观察


class FakeBreakoutPattern(Enum):
    """假突破7种模式 — 四视角完全一致的判定逻辑"""
    FAKE_PIN = "fake_pin"                      # 探针型：盘中大幅穿透但收盘回到Zone内
    FAKE_DSPIKE = "fake_dspike"                # 单K极端：单根K线极端价格+弱通量
    FAKE_VOLDIV = "fake_voldiv"                # 量能背离：价格突破但量能萎缩
    FAKE_BLIND_WHIP = "fake_blind_whip"        # 盲区抽鞭：盲区快速突破但无后续
    FAKE_GAP = "fake_gap"                      # 跳空回补：跳空突破Zone但缺口当日回补
    FAKE_WICK_CLUSTER = "fake_wick_cluster"    # 连续影线簇：3-5根影线在Zone外，实体在Zone内
    FAKE_TIME_TRAP = "fake_time_trap"          # 时间陷阱：突破后Zone外停留数日无后续，再回归


@dataclass
class Signal:
    """
    交易信号 — 轻量级信号对象

    来自4视角交集分析（Quant/TA/Risk/MM），核心设计原则：
    1. conservation_flux 必须参与所有信号过滤（共识3）
    2. stability_verdict 红灯覆盖方向性判断（共识4）
    3. 假突破判定关键 = flux方向与价格突破方向相反（共识2）
    4. 信号优先级：假突破反向 > 突破确认 > 回踩确认 > 结构老化

    用法：
        from src.signals import generate_signal
        signal = generate_signal(structure, bars=bars, system_state=ss)
        if signal:
            print(f"{signal.kind.value} {signal.direction} conf={signal.confidence:.0%}")
    """
    kind: SignalKind                             # 信号类型
    direction: str                               # 'long' | 'short' | 'neutral'
    confidence: float                            # 置信度 [0,1]，基于质量层+评分
    flux_aligned: bool                           # conservation_flux是否与信号方向一致
    stability_ok: bool                           # stability_verdict != 'red'
    entry_note: str                              # 入场说明（自然语言）
    # ── 扩展字段 ──
    breakout_score: float = 0.0                  # 5维突破评分（仅突破/假突破时有效）
    fake_pattern: FakeBreakoutPattern | None = None  # 假突破模式（仅假突破时有效）
    quality_tier: str = ""                       # 产生信号时的质量层
    is_blind: bool = False                       # 盲区标记
    days_since_formation: int = 0                # 结构形成后天数
    # ── 风控辅助 ──
    entry_price: float = 0.0                     # 入场价（数值）
    entry_limit_upper: float = 0.0               # 入场可接受最高价（Zone边界+容忍度）
    entry_limit_lower: float = 0.0               # 入场可接受最低价（Zone边界-容忍度）
    stop_loss_hint: str = ""                     # 止损位文字提示
    stop_loss_price: float = 0.0                 # 止损价（数值）
    take_profit_price: float = 0.0               # 目标价（数值）
    rr_ratio: float = 0.0                        # 盈亏比 (reward/risk)
    position_size_factor: float = 1.0            # 仓位系数（A=1.0, B=0.6, C=0.3, D=0）
    # ── 时效与框架 ──
    timeframe: str = ""                          # 时间框架（"60min"/"15min"/"daily"等）
    signal_bars_index: int = 0                   # 信号生成时的K线索引（用于计算TTL）
    ttl_bars: int = 0                            # 信号有效期（K线根数）
    atr_value: float = 0.0                       # 信号生成时的ATR值

    @property
    def priority(self) -> int:
        """信号优先级（数字越小优先级越高）"""
        return {
            SignalKind.FAKE_BREAKOUT: 1,
            SignalKind.BREAKOUT_CONFIRM: 2,
            SignalKind.PULLBACK_CONFIRM: 3,
            SignalKind.BLIND_BREAKOUT: 4,
            SignalKind.STRUCTURE_EXPIRED: 5,
        }.get(self.kind, 99)

    @property
    def display_label(self) -> str:
        """人可读的信号标签"""
        labels = {
            SignalKind.BREAKOUT_CONFIRM: "突破确认",
            SignalKind.FAKE_BREAKOUT: "假突破·反向",
            SignalKind.PULLBACK_CONFIRM: "回踩确认",
            SignalKind.STRUCTURE_EXPIRED: "结构老化",
            SignalKind.BLIND_BREAKOUT: "盲区突破·观察",
        }
        return labels.get(self.kind, self.kind.value)

    @property
    def signal_type_label(self) -> str:
        """信号类型详细标签（含假突破子模式）"""
        if self.kind == SignalKind.FAKE_BREAKOUT and self.fake_pattern:
            pattern_labels = {
                "fake_pin": "探针型",
                "fake_dspike": "单K极端",
                "fake_voldiv": "量能背离",
                "fake_blind_whip": "盲区抽鞭",
                "fake_gap": "跳空回补",
                "fake_wick_cluster": "影线簇",
                "fake_time_trap": "时间陷阱",
            }
            sub = pattern_labels.get(self.fake_pattern.value, self.fake_pattern.value)
            return f"假突破·{sub}"
        return self.display_label

    @property
    def display_direction(self) -> str:
        """人可读的方向"""
        return {"long": "📈做多", "short": "📉做空", "neutral": "➡️观望"}.get(self.direction, self.direction)

    @property
    def traffic_light(self) -> str:
        """信号置信度红绿灯"""
        if self.confidence >= 0.8 and self.stability_ok and self.flux_aligned:
            return "🟢"
        elif self.confidence >= 0.55 and self.stability_ok:
            return "🟡"
        return "🔴"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "direction": self.direction,
            "confidence": round(self.confidence, 3),
            "flux_aligned": self.flux_aligned,
            "stability_ok": self.stability_ok,
            "entry_note": self.entry_note,
            "breakout_score": round(self.breakout_score, 3),
            "fake_pattern": self.fake_pattern.value if self.fake_pattern else None,
            "quality_tier": self.quality_tier,
            "is_blind": self.is_blind,
            "days_since_formation": self.days_since_formation,
            "entry_price": round(self.entry_price, 2),
            "entry_limit_upper": round(self.entry_limit_upper, 2),
            "entry_limit_lower": round(self.entry_limit_lower, 2),
            "stop_loss_hint": self.stop_loss_hint,
            "stop_loss_price": round(self.stop_loss_price, 2),
            "take_profit_price": round(self.take_profit_price, 2),
            "rr_ratio": round(self.rr_ratio, 2),
            "position_size_factor": self.position_size_factor,
            "timeframe": self.timeframe,
            "signal_bars_index": self.signal_bars_index,
            "ttl_bars": self.ttl_bars,
            "atr_value": round(self.atr_value, 4),
            "priority": self.priority,
            "display_label": self.display_label,
            "display_direction": self.display_direction,
            "traffic_light": self.traffic_light,
            "signal_type_label": self.signal_type_label,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Signal:
        return cls(
            kind=SignalKind(d["kind"]),
            direction=d["direction"],
            confidence=d["confidence"],
            flux_aligned=d["flux_aligned"],
            stability_ok=d["stability_ok"],
            entry_note=d["entry_note"],
            breakout_score=d.get("breakout_score", 0.0),
            fake_pattern=FakeBreakoutPattern(d["fake_pattern"]) if d.get("fake_pattern") else None,
            quality_tier=d.get("quality_tier", ""),
            is_blind=d.get("is_blind", False),
            days_since_formation=d.get("days_since_formation", 0),
            entry_price=d.get("entry_price", 0.0),
            entry_limit_upper=d.get("entry_limit_upper", 0.0),
            entry_limit_lower=d.get("entry_limit_lower", 0.0),
            stop_loss_hint=d.get("stop_loss_hint", ""),
            stop_loss_price=d.get("stop_loss_price", 0.0),
            take_profit_price=d.get("take_profit_price", 0.0),
            rr_ratio=d.get("rr_ratio", 0.0),
            position_size_factor=d.get("position_size_factor", 1.0),
            timeframe=d.get("timeframe", ""),
            signal_bars_index=d.get("signal_bars_index", 0),
            ttl_bars=d.get("ttl_bars", 0),
            atr_value=d.get("atr_value", 0.0),
        )

    def __repr__(self):
        blind_tag = " · ⚠️盲区" if self.is_blind else ""
        rr_tag = f" · RR={self.rr_ratio:.1f}" if self.rr_ratio > 0 else ""
        return (f"Signal({self.display_label} {self.direction} "
                f"conf={self.confidence:.0%} {self.traffic_light}{rr_tag}{blind_tag})")


# ─── 基础算子（从 utils.py 导入）────────────────────────────
# v4.2: 算子函数已迁移到 utils.py，消除循环依赖
from src.utils import (
    first_diff, log_diff, second_diff,
    time_gap, distance_to_zone, relative_distance_to_zone,
    extrema_dispersion,
)
