""""现货地区：库存/需求/运输成本。

现货世界由时间、空间、质量、库存、信用、预期差异构成。
地区是空间差异的具体载体。
"""

from dataclasses import dataclass


@dataclass
class Region:
    """现货地区。"""

    id: str  # e.g. "region_A"
    name: str
    inventory: float = 50.0  # 库存水平
    demand: float = 50.0  # 需求水平
    transport_cost: float = 20.0  # 运输成本
    is_delivery_point: bool = False  # 是否交割地
    warehouse_capacity: float = 100.0  # 仓库容量
    description: str = ""

    @property
    def inventory_demand_gap(self) -> float:
        """库存-需求缺口。"""
        return self.inventory - self.demand

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "inventory": round(self.inventory, 2),
            "demand": round(self.demand, 2),
            "inventory_demand_gap": round(self.inventory_demand_gap, 2),
            "transport_cost": round(self.transport_cost, 2),
            "is_delivery_point": self.is_delivery_point,
            "warehouse_capacity": round(self.warehouse_capacity, 2),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Region":
        return cls(**data)