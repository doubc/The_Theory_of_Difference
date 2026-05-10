""""商品：期货市场的实物基础。

商品不是抽象资产，而是带着时间、空间、质量、库存差异的现实存在。
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Commodity:
    """商品对象（虚构或真实品种）。"""

    id: str  # e.g. "RW-Copper", "ToyMetal"
    name: str
    unit: str = "ton"  # 交易单位
    quality_standard: str = "standard"  # 质量标准
    regions: Dict[str, "Region"] = field(default_factory=dict)
    contracts: Dict[str, "Contract"] = field(default_factory=dict)
    description: str = ""

    def add_region(self, region: "Region"):
        self.regions[region.id] = region

    def add_contract(self, contract: "Contract"):
        self.contracts[contract.id] = contract

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "unit": self.unit,
            "quality_standard": self.quality_standard,
            "regions": {k: v.to_dict() for k, v in self.regions.items()},
            "contracts": {k: v.to_dict() for k, v in self.contracts.items()},
            "description": self.description,
        }


# 避免循环引用，在文件底部导入
from .region import Region
from .contract import Contract