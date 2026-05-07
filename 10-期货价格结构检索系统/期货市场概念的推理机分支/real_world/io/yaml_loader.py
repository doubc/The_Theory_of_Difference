""""YAML 配置加载器。

实验配置格式：
`yaml
experiment:
  id: exp_001
  name: 库存差异经基差通道显影

world:
  name: RW-Copper-World
  max_steps: 20

differences:
  - id: inventory_gap_A_B
    type: inventory
    source_node: region_A
    target_node: region_B
    magnitude: 80
    visibility: 0.9
    persistence: 0.8

entities:
  - id: industrial_long_001
    type: industrial_long
    capacity: 100
    available_capacity: 80

channels:
  - id: basis_channel
    from_type: inventory
    to_type: basis
    base_cost: 15
    capacity: 100
`

Usage:
    world = load_world_from_yaml("experiments/futures/exp_001.yaml")
"""

import yaml
from pathlib import Path

from ..core.world import World
from ..core.difference import DifferenceSource, DifferenceStatus
from ..core.entity import Entity, EntityStatus
from ..core.channel import Channel, ChannelStatus


def load_world_from_yaml(yaml_path: str) -> World:
    """从 YAML 文件加载世界对象。"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    exp = data.get("experiment", {})
    world_cfg = data.get("world", {})

    world = World(
        name=world_cfg.get("name", "World"),
        max_steps=world_cfg.get("max_steps", 20),
    )

    # 加载破缺阈值
    if "break_thresholds" in data:
        world.break_thresholds.update(data["break_thresholds"])

    # 加载差异源
    for d_data in data.get("differences", []):
        diff = DifferenceSource(
            id=d_data["id"],
            type=d_data["type"],
            source_node=d_data.get("source_node", ""),
            target_node=d_data.get("target_node", ""),
            magnitude=d_data.get("magnitude", 50.0),
            visibility=d_data.get("visibility", 0.8),
            persistence=d_data.get("persistence", 0.7),
            transformability=d_data.get("transformability", 0.9),
            description=d_data.get("description", ""),
            recurrent=d_data.get("recurrent", False),
            recurrent_rate=d_data.get("recurrent_rate", 0.0),
            recurrent_decay=d_data.get("recurrent_decay", 1.0),
        )
        if "status" in d_data:
            diff.status = DifferenceStatus(d_data["status"])
        world.add_difference(diff)

    # 加载承接体
    for e_data in data.get("entities", []):
        entity = Entity(
            id=e_data["id"],
            type=e_data["type"],
            capacity=e_data.get("capacity", 100.0),
            available_capacity=e_data.get("available_capacity", 80.0),
            risk_tolerance=e_data.get("risk_tolerance", 50.0),
            liquidity=e_data.get("liquidity", 70.0),
            leverage=e_data.get("leverage", 1.0),
            preference=e_data.get("preference", "neutral"),
            description=e_data.get("description", ""),
        )
        if "status" in e_data:
            entity.status = EntityStatus(e_data["status"])
        world.add_entity(entity)

    # 加载通道
    for c_data in data.get("channels", []):
        channel = Channel(
            id=c_data["id"],
            from_type=c_data["from_type"],
            to_type=c_data.get("to_type", c_data["from_type"]),
            base_cost=c_data.get("base_cost", 20.0),
            capacity=c_data.get("capacity", 100.0),
            openness=c_data.get("openness", 0.9),
            congestion=c_data.get("congestion", 0.1),
            rule_penalty=c_data.get("rule_penalty", 0.0),
            description=c_data.get("description", ""),
        )
        if "status" in c_data:
            channel.status = ChannelStatus(c_data["status"])
        world.add_channel(channel)

        # 注册通道-主体承接关系
        for entity_id in c_data.get("entities", []):
            world.add_channel_entity(channel.id, entity_id)

    return world


def world_to_dict(world: World) -> dict:
    """将世界对象序列化为字典（不含状态和轨迹）。"""
    return world.to_dict()