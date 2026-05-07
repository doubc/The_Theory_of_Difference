""""世界：差异运动的总容器。

世界不是被动的容器，而是差异运动的场地。
世界维护时间步、实体、差异、通道、规则、状态和轨迹。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .difference import DifferenceSource
from .entity import Entity
from .channel import Channel
from .state import State
from .trace import Trace
from .event import Event


@dataclass
class World:
    """差异结构推理机的世界对象。"""

    name: str
    time: int = 0
    max_steps: int = 30
    entities: Dict[str, Entity] = field(default_factory=dict)
    differences: Dict[str, DifferenceSource] = field(default_factory=dict)
    channels: Dict[str, Channel] = field(default_factory=dict)
    rules: Dict = field(default_factory=dict)
    states: List[State] = field(default_factory=list)
    trace: Trace = field(default_factory=Trace)
    events: List[Event] = field(default_factory=list)
    # 通道→承接体列表映射：定义哪些主体负责承接哪些通道上的差异
    channel_entity_map: Dict[str, List[str]] = field(default_factory=dict)
    break_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "inventory": 100,
        "liquidity": 80,
        "expectation": 90,
        "margin": 70,
    })

    def add_difference(self, diff: DifferenceSource):
        self.differences[diff.id] = diff

    def add_entity(self, entity: Entity):
        self.entities[entity.id] = entity

    def add_channel(self, channel: Channel):
        self.channels[channel.id] = channel

    def add_channel_entity(self, channel_id: str, entity_id: str):
        """注册主体为通道的承接者。"""
        if channel_id not in self.channel_entity_map:
            self.channel_entity_map[channel_id] = []
        if entity_id not in self.channel_entity_map[channel_id]:
            self.channel_entity_map[channel_id].append(entity_id)

    def get_channel_entities(self, channel_id: str) -> List[Entity]:
        """获取通道的承接主体列表（按承接能力降序）。"""
        entity_ids = self.channel_entity_map.get(channel_id, [])
        entities = [self.entities[eid] for eid in entity_ids if eid in self.entities]
        # 按可用承接能力降序排列
        entities.sort(key=lambda e: e.available_capacity, reverse=True)
        return entities

    def get_active_differences(self) -> List[DifferenceSource]:
        return [d for d in self.differences.values() if d.status.value == "active"]

    def get_open_channels(self) -> List[Channel]:
        return [c for c in self.channels.values() if c.status.value in ("open", "congested")]

    def total_pressure(self) -> float:
        return sum(d.pressure for d in self.get_active_differences())

    def dominant_difference(self) -> Optional[DifferenceSource]:
        active = self.get_active_differences()
        if not active:
            return None
        return max(active, key=lambda d: d.pressure)

    def dominant_entity(self) -> Optional[Entity]:
        active = [e for e in self.entities.values() if e.status.value in ("active", "stressed")]
        if not active:
            return None
        return max(active, key=lambda e: e.used_capacity)

    def snapshot_state(self) -> State:
        """拍摄当前状态快照。"""
        dom_diff = self.dominant_difference()
        dom_entity = self.dominant_entity()
        state = State(
            time=self.time,
            total_pressure=self.total_pressure(),
            active_differences=len(self.get_active_differences()),
            active_channels=len(self.get_open_channels()),
            blocked_channels=len([c for c in self.channels.values() if c.status.value in ("blocked", "closed")]),
            dominant_difference_id=dom_diff.id if dom_diff else "",
            dominant_difference_type=dom_diff.type if dom_diff else "",
            dominant_entity_id=dom_entity.id if dom_entity else "",
            pressure_level="low",
            break_events_count=len(self.events),
        )
        state.pressure_level = state.classify_pressure()
        self.states.append(state)
        return state

    def step(self):
        """推进一步时间。"""
        self.time += 1

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "time": self.time,
            "max_steps": self.max_steps,
            "differences": {k: v.to_dict() for k, v in self.differences.items()},
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "channels": {k: v.to_dict() for k, v in self.channels.items()},
            "rules": self.rules,
            "total_pressure": round(self.total_pressure(), 2),
        }