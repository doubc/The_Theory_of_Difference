""""状态快照：每步系统的整体状态。

状态不是均衡，而是「当前约束下暂时能维持的最近稳态」。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class State:
    """世界在某个时间步的状态快照。"""

    time: int
    total_pressure: float = 0.0
    active_differences: int = 0
    active_channels: int = 0
    blocked_channels: int = 0
    dominant_difference_id: str = ""
    dominant_difference_type: str = ""
    dominant_entity_id: str = ""
    nearest_stable_label: str = ""
    pressure_level: str = "low"  # low / medium / high / critical
    break_events_count: int = 0
    detail: Dict = field(default_factory=dict)

    def classify_pressure(self) -> str:
        """压力等级分类。"""
        if self.total_pressure < 30:
            return "low"
        elif self.total_pressure < 60:
            return "medium"
        elif self.total_pressure < 90:
            return "high"
        else:
            return "critical"

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "total_pressure": round(self.total_pressure, 2),
            "active_differences": self.active_differences,
            "active_channels": self.active_channels,
            "blocked_channels": self.blocked_channels,
            "dominant_difference_id": self.dominant_difference_id,
            "dominant_difference_type": self.dominant_difference_type,
            "dominant_entity_id": self.dominant_entity_id,
            "nearest_stable_label": self.nearest_stable_label,
            "pressure_level": self.classify_pressure(),
            "break_events_count": self.break_events_count,
            "detail": self.detail,
        }