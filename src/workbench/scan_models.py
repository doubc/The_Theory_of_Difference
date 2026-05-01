"""
扫描数据模型 — ScanRecord dataclass

将散落在 tab_scan.py 各处的 dict 结构统一为强类型模型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SignalInfo:
    """交易信号详情"""
    kind: str = ""
    direction: str = "neutral"
    confidence: float = 0.0
    flux_aligned: bool = False
    stability_ok: bool = False
    entry_note: str = ""
    breakout_score: float = 0.0
    fake_pattern: Optional[str] = None
    quality_tier: str = ""
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    rr_ratio: float = 0.0
    position_size_factor: float = 1.0
    signal_type_label: str = ""
    display_label: str = ""


@dataclass
class ZoneInfo:
    """稳态 Zone 信息"""
    center: float
    bw: float
    upper: float
    lower: float
    date_range: str
    cycles: int
    t_start: Optional[datetime] = None
    t_end: Optional[datetime] = None


@dataclass
class ScanRecord:
    """一次扫描中单个合约的完整记录"""
    # 基础信息
    symbol: str
    symbol_name: str = ""
    volume: int = 0
    last_price: float = 0.0
    last_date: str = ""

    # 稳态序列
    zones: list[ZoneInfo] = field(default_factory=list)
    latest_zone_center: float = 0.0
    latest_zone_bw: float = 0.0
    zone_trend: str = "—"
    zone_relation: str = "—"
    zone_count: int = 0

    # 价格位置
    price_position: str = ""
    price_position_code: str = "M"  # H / M / L

    # 运动阶段
    motion: str = "—"
    motion_label: str = "—"
    phase_code: str = "stable"
    flux: float = 0.0
    direction: str = "unclear"

    # 确认日
    breakout_date: str = ""

    # 质量
    tier: str = "?"
    score: float = 0.0
    cycles: int = 0
    is_blind: bool = False

    # 离稳态
    departure_score: float = 0.0

    # 板块
    sector: str = "未知"

    # 优先级
    priority_score: float = 0.0

    # 信号详情
    signal_info: Optional[SignalInfo] = None

    def to_dict(self) -> dict:
        """转为 dict（兼容旧代码）"""
        d = {
            "symbol": self.symbol,
            "symbol_name": self.symbol_name,
            "volume": self.volume,
            "last_price": self.last_price,
            "last_date": self.last_date,
            "zones": [
                {
                    "center": z.center, "bw": z.bw, "upper": z.upper, "lower": z.lower,
                    "date_range": z.date_range, "cycles": z.cycles,
                    "t_start": z.t_start, "t_end": z.t_end,
                }
                for z in self.zones
            ],
            "latest_zone_center": self.latest_zone_center,
            "latest_zone_bw": self.latest_zone_bw,
            "zone_trend": self.zone_trend,
            "zone_relation": self.zone_relation,
            "zone_count": self.zone_count,
            "price_position": self.price_position,
            "price_position_code": self.price_position_code,
            "motion": self.motion,
            "motion_label": self.motion_label,
            "phase_code": self.phase_code,
            "flux": self.flux,
            "direction": self.direction,
            "breakout_date": self.breakout_date,
            "tier": self.tier,
            "score": self.score,
            "cycles": self.cycles,
            "is_blind": self.is_blind,
            "departure_score": self.departure_score,
            "sector": self.sector,
            "priority_score": self.priority_score,
            "signal_info": None,
        }
        if self.signal_info:
            d["signal_info"] = {
                "kind": self.signal_info.kind,
                "direction": self.signal_info.direction,
                "confidence": self.signal_info.confidence,
                "flux_aligned": self.signal_info.flux_aligned,
                "stability_ok": self.signal_info.stability_ok,
                "entry_note": self.signal_info.entry_note,
                "breakout_score": self.signal_info.breakout_score,
                "fake_pattern": self.signal_info.fake_pattern,
                "quality_tier": self.signal_info.quality_tier,
                "entry_price": self.signal_info.entry_price,
                "stop_loss_price": self.signal_info.stop_loss_price,
                "take_profit_price": self.signal_info.take_profit_price,
                "rr_ratio": self.signal_info.rr_ratio,
                "position_size_factor": self.signal_info.position_size_factor,
                "signal_type_label": self.signal_info.signal_type_label,
                "display_label": self.signal_info.display_label,
            }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ScanRecord:
        """从 dict 构建（兼容旧数据）"""
        zones = [ZoneInfo(**z) for z in d.get("zones", [])]
        sig = None
        if d.get("signal_info"):
            sig = SignalInfo(**d["signal_info"])
        return cls(
            symbol=d["symbol"],
            symbol_name=d.get("symbol_name", ""),
            volume=d.get("volume", 0),
            last_price=d.get("last_price", 0.0),
            last_date=d.get("last_date", ""),
            zones=zones,
            latest_zone_center=d.get("latest_zone_center", 0.0),
            latest_zone_bw=d.get("latest_zone_bw", 0.0),
            zone_trend=d.get("zone_trend", "—"),
            zone_relation=d.get("zone_relation", "—"),
            zone_count=d.get("zone_count", 0),
            price_position=d.get("price_position", ""),
            price_position_code=d.get("price_position_code", "M"),
            motion=d.get("motion", "—"),
            motion_label=d.get("motion_label", "—"),
            phase_code=d.get("phase_code", "stable"),
            flux=d.get("flux", 0.0),
            direction=d.get("direction", "unclear"),
            breakout_date=d.get("breakout_date", ""),
            tier=d.get("tier", "?"),
            score=d.get("score", 0.0),
            cycles=d.get("cycles", 0),
            is_blind=d.get("is_blind", False),
            departure_score=d.get("departure_score", 0.0),
            sector=d.get("sector", "未知"),
            priority_score=d.get("priority_score", 0.0),
            signal_info=sig,
        )
