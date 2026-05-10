""""事件：破缺、规则调整等异常事件的记录。

事件不是外生冲击，而是差异积累到阈值后的内生结果。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    PRICE_JUMP = "price_jump"               # 价格跳变
    BASIS_ANOMALY = "basis_anomaly"         # 基差异常
    NEAR_MONTH_SQUEEZE = "near_month_squeeze"  # 近月逼仓
    LIQUIDITY_DRY = "liquidity_dry"         # 流动性枯竭
    MARGIN_CALL = "margin_call"             # 保证金追缴
    FORCED_LIQUIDATION = "forced_liquidation"  # 强制平仓
    RULE_CHANGE = "rule_change"             # 规则调整
    DELIVERY_FAILURE = "delivery_failure"   # 交割失败
    ENTITY_EXIT = "entity_exit"             # 主体退出
    ACCUMULATION_OVERFLOW = "accumulation_overflow"  # 积累溢出


@dataclass
class Event:
    """破缺事件。"""

    time: int
    event_type: EventType
    difference_id: str = ""
    channel_id: str = ""
    entity_id: str = ""
    severity: float = 1.0  # 0-1 严重程度
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "event_type": self.event_type.value,
            "difference_id": self.difference_id,
            "channel_id": self.channel_id,
            "entity_id": self.entity_id,
            "severity": round(self.severity, 2),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        data = dict(data)
        if "event_type" in data and isinstance(data["event_type"], str):
            data["event_type"] = EventType(data["event_type"])
        return cls(**data)