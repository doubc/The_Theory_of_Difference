""""轨迹：差异运动的事件流。

轨迹是差异论推理的核心输出——不只给结论，必须给路径。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TraceEvent:
    """单个轨迹事件。"""

    time: int
    event_type: str  # transfer / accumulate / break / lock_in / stable / channel_congest / entity_stress
    difference_id: str
    from_node: str = ""
    to_node: str = ""
    channel_id: str = ""
    amount: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "event_type": self.event_type,
            "difference_id": self.difference_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "channel_id": self.channel_id,
            "amount": round(self.amount, 2),
            "reason": self.reason,
        }


@dataclass
class Trace:
    """轨迹：事件流容器。"""

    events: List[TraceEvent] = field(default_factory=list)

    def add(self, event: TraceEvent):
        self.events.append(event)

    def add_event(self, time: int, event_type: str, difference_id: str,
                  from_node: str = "", to_node: str = "",
                  channel_id: str = "", amount: float = 0.0, reason: str = ""):
        self.add(TraceEvent(
            time=time, event_type=event_type, difference_id=difference_id,
            from_node=from_node, to_node=to_node, channel_id=channel_id,
            amount=amount, reason=reason,
        ))

    def filter_by_type(self, event_type: str) -> List[TraceEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def filter_by_difference(self, diff_id: str) -> List[TraceEvent]:
        return [e for e in self.events if e.difference_id == diff_id]

    def to_list(self) -> List[dict]:
        return [e.to_dict() for e in self.events]

    @property
    def summary(self) -> str:
        """轨迹摘要。"""
        types = {}
        for e in self.events:
            types[e.event_type] = types.get(e.event_type, 0) + 1
        parts = [f"{k}:{v}" for k, v in sorted(types.items())]
        return f"Trace({len(self.events)} events: {', '.join(parts)})"