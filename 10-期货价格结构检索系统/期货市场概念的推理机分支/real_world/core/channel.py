""""通道：差异转移的路径。

通道不是中性的——通道有成本、有容量、有拥堵、有锁定。
差异通过通道转移时，形式可能发生变化（如库存差异→基差差异→价格差异）。

有效成本公式：
    effective_cost = base_cost + congestion * 10 + rule_penalty - lock_in * 10

类型：spot_transport / storage / futures_contract / basis / term_structure /
      margin_clearing / warehouse_receipt / delivery / exchange_rule / position_reduction
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChannelStatus(str, Enum):
    OPEN = "open"
    CONGESTED = "congested"
    BLOCKED = "blocked"
    CLOSED = "closed"


@dataclass
class Channel:
    """转移通道对象。"""

    id: str
    from_type: str  # 差异输入类型
    to_type: str    # 差异输出类型（转移后变形）
    base_cost: float = 20.0
    capacity: float = 100.0
    used_capacity: float = 0.0
    openness: float = 0.9  # 开放度（0-1），交易所规则等可降低
    congestion: float = 0.1  # 拥堵度（0-1）
    lock_in: float = 0.0  # 锁定度（0-1），反复使用会增加
    rule_penalty: float = 0.0  # 规则惩罚成本
    status: ChannelStatus = ChannelStatus.OPEN
    description: str = ""
    _cumulative_throughput: float = field(default=0.0, repr=False)  # 累计通过量

    @property
    def remaining_capacity(self) -> float:
        return max(0.0, self.capacity - self.used_capacity)

    def effective_cost(self) -> float:
        """有效成本 = 基础成本 + 拥堵惩罚 + 规则惩罚 - 锁定折扣"""
        return self.base_cost + self.congestion * 10 + self.rule_penalty - self.lock_in * 10

    def can_transfer(self, diff_type: str, amount: float) -> bool:
        """是否可以转移指定类型和数量的差异。"""
        return (
            self.status in (ChannelStatus.OPEN, ChannelStatus.CONGESTED)
            and self.from_type == diff_type
            and self.remaining_capacity >= amount * 0.01  # 至少有少量容量
        )

    def transfer(self, amount: float) -> float:
        """通过通道转移差异。返回实际转移量。"""
        actual = min(amount, self.remaining_capacity)
        self.used_capacity += actual
        self._cumulative_throughput += actual  # 累计
        # 更新拥堵度
        self._update_congestion()
        # 更新锁定度
        self._update_lock_in(actual)
        return actual

    def _update_congestion(self):
        """根据容量使用率更新拥堵度。"""
        if self.capacity <= 0:
            self.congestion = 1.0
        else:
            self.congestion = min(1.0, self.used_capacity / self.capacity)
        # 拥堵度超过阈值，状态变为拥堵
        if self.congestion > 0.8 and self.status == ChannelStatus.OPEN:
            self.status = ChannelStatus.CONGESTED
        elif self.congestion <= 0.5 and self.status == ChannelStatus.CONGESTED:
            self.status = ChannelStatus.OPEN

    def _update_lock_in(self, amount: float):
        """通道使用越多，锁定度越高（路径依赖）。"""
        self.lock_in = min(1.0, self.lock_in + amount * 0.001)

    @property
    def capacity_usage(self) -> float:
        """瞬时容量使用率（0-1），硬限制不超过 1.0。
        
        基于 reset_step 后的 used_capacity，反映当前步的占用状态。
        """
        if self.capacity <= 0:
            return 1.0
        return min(1.0, self.used_capacity / self.capacity)

    @property
    def cumulative_throughput(self) -> float:
        """累计通过量（只增不减），用于报告。"""
        return self._cumulative_throughput

    def reset_step(self):
        """每个时间步重置部分使用量（非永久占用）。

        释放量受锁定度影响：锁定度越高，释放越少（路径依赖占用容量）。
        释放后 used_capacity 不低于 capacity * lock_in（锁定部分不释放）。
        """
        # 锁定部分不释放
        locked_portion = self.capacity * self.lock_in
        released = self.used_capacity * 0.7
        self.used_capacity = max(locked_portion, self.used_capacity - released)
        # 硬保护：确保 used <= capacity
        self.used_capacity = min(self.used_capacity, self.capacity)
        self._update_congestion()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_type": self.from_type,
            "to_type": self.to_type,
            "base_cost": round(self.base_cost, 2),
            "capacity": round(self.capacity, 2),
            "used_capacity": round(self.used_capacity, 2),
            "remaining_capacity": round(self.remaining_capacity, 2),
            "capacity_usage": f"{self.capacity_usage:.0%}",
            "cumulative_throughput": round(self._cumulative_throughput, 2),
            "openness": round(self.openness, 2),
            "congestion": round(self.congestion, 3),
            "lock_in": round(self.lock_in, 3),
            "effective_cost": round(self.effective_cost(), 2),
            "rule_penalty": round(self.rule_penalty, 2),
            "status": self.status.value,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Channel":
        data = dict(data)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ChannelStatus(data["status"])
        return cls(**data)