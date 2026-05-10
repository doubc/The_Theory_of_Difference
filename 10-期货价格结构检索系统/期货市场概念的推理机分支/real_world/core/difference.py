""""差异源：差异论的起点。

差异是世界的生成元。差异不是「缺少什么」，而是「区分」本身。
差异不能凭空消失，只能转移、变形、积累或破缺。

属性说明：
- magnitude: 差异的绝对规模（0-100+）
- visibility: 差异是否已被市场参与者观察到（0-1）
- persistence: 差异持续存在的倾向（0-1），高=结构性差异
- transformability: 差异可被转移/变形的程度（0-1）
- pressure: 差异当前产生的压力，驱动转移（= magnitude * visibility * persistence）
- status: active | dormant | resolved | accumulated | broken
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DifferenceStatus(str, Enum):
    ACTIVE = "active"
    DORMANT = "dormant"
    RESOLVED = "resolved"
    ACCUMULATED = "accumulated"
    BROKEN = "broken"


@dataclass
class DifferenceSource:
    """差异源对象。"""

    id: str
    type: str  # inventory / time / space / quality / expectation / liquidity / margin / basis / term_structure / delivery / rule
    source_node: str
    target_node: str
    magnitude: float = 50.0
    visibility: float = 0.8
    persistence: float = 0.7
    transformability: float = 0.9
    pressure: float = 0.0  # 初始化时自动计算
    status: DifferenceStatus = DifferenceStatus.ACTIVE
    description: str = ""
    # ---- 差异持续生成机制 ----
    recurrent: bool = False  # 是否每步持续生成压力
    recurrent_rate: float = 0.0  # 每步生成的压力量（magnitude 的百分比）
    recurrent_decay: float = 1.0  # 生成速率衰减（每步 × decay），1.0=不衰减

    def __post_init__(self):
        if self.pressure == 0.0:
            self.pressure = self._compute_pressure()

    def _compute_pressure(self) -> float:
        """压力 = 规模 * 可见性 * 持续性"""
        return self.magnitude * self.visibility * self.persistence

    def update_pressure(self):
        """重新计算压力。"""
        self.pressure = self._compute_pressure()

    def reduce_pressure(self, amount: float):
        """转移后减少压力，不低于 0。"""
        self.pressure = max(0.0, self.pressure - amount)
        if self.pressure <= 0.01:
            self.status = DifferenceStatus.RESOLVED

    def accumulate(self, amount: float):
        """积累压力。

        注意：积累只增加 pressure，不增长 magnitude。
        magnitude 代表差异的结构性规模，不应随无处可去的积累而膨胀。
        只有 recurrent 机制才应该增长 magnitude。
        """
        if amount > 0:
            self.pressure += amount
        if self.status == DifferenceStatus.DORMANT:
            self.status = DifferenceStatus.ACTIVE

    def tick_recurrence(self):
        """每步持续生成压力（如果 recurrent=True）。

        模拟现实：差异不是一次性输入，而是持续产生。
        衰减：recurrent_rate *= recurrent_decay
        """
        if not self.recurrent or self.status != DifferenceStatus.ACTIVE:
            return
        generated = self.magnitude * self.recurrent_rate
        if generated > 0.01:
            self.pressure += generated
            self.recurrent_rate *= self.recurrent_decay  # 衰减
        else:
            # 生成速率过低，停止
            self.recurrent = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "magnitude": round(self.magnitude, 2),
            "visibility": round(self.visibility, 2),
            "persistence": round(self.persistence, 2),
            "transformability": round(self.transformability, 2),
            "pressure": round(self.pressure, 2),
            "status": self.status.value,
            "recurrent": self.recurrent,
            "recurrent_rate": round(self.recurrent_rate, 4),
            "recurrent_decay": round(self.recurrent_decay, 3),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DifferenceSource":
        data = dict(data)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = DifferenceStatus(data["status"])
        return cls(**data)