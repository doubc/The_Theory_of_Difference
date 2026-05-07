""""合约：差异进入市场的制度界面。

合约不是现实的完整复制，而是制度压缩——
通过标准化来压缩差异，但压缩也意味着排斥（某些差异留在合约之外）。
"""

from dataclasses import dataclass


@dataclass
class Contract:
    """期货合约。"""

    id: str  # e.g. "RW-Copper-2507"
    commodity_id: str
    month: str  # 交割月份，e.g. "2507"
    price: float = 0.0  # 当前价格
    open_interest: float = 0.0  # 持仓量
    volume: float = 0.0  # 成交量
    liquidity: float = 50.0  # 流动性（0-100）
    delivery_pressure: float = 0.0  # 交割压力
    is_near_month: bool = False  # 是否近月
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "commodity_id": self.commodity_id,
            "month": self.month,
            "price": round(self.price, 2),
            "open_interest": round(self.open_interest, 2),
            "volume": round(self.volume, 2),
            "liquidity": round(self.liquidity, 2),
            "delivery_pressure": round(self.delivery_pressure, 2),
            "is_near_month": self.is_near_month,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Contract":
        return cls(**data)