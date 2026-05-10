""""承接体：差异的承接位置。

主体不应仅按动机分类，而应按其在差异承接中的结构位置分类。
位置是动态的——随市场条件变化而改变。

类型：spot_merchant / industrial_long / industrial_short / speculator / arbitrager / exchange / clearing / warehouse
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

# 反馈衰减因子（每次反馈衰减50%）
FEEDBACK_DECAY = 0.5


class EntityStatus(str, Enum):
    ACTIVE = "active"
    STRESSED = "stressed"
    MARGIN_CALLED = "margin_called"
    FORCED_OUT = "forced_out"
    EXITED = "exited"


@dataclass
class Entity:
    """承接体对象。"""

    id: str
    type: str  # spot_merchant / industrial_long / industrial_short / speculator / arbitrager / exchange / clearing / warehouse
    capacity: float = 100.0  # 总承接能力
    available_capacity: float = 80.0  # 可用承接能力
    risk_tolerance: float = 50.0  # 风险承受度
    liquidity: float = 70.0  # 流动性
    leverage: float = 1.0  # 杠杆
    preference: str = "neutral"  # 偏好方向
    status: EntityStatus = EntityStatus.ACTIVE
    description: str = ""
    
    # Phase 3: 反馈冷却机制
    _feedback_cooldown: Dict[str, int] = field(default_factory=dict)  # type -> last_time

    @property
    def used_capacity(self) -> float:
        return self.capacity - self.available_capacity

    @property
    def capacity_ratio(self) -> float:
        """已用容量比例（0-1）。"""
        if self.capacity <= 0:
            return 1.0
        return self.used_capacity / self.capacity

    def can_absorb(self, amount: float) -> bool:
        """是否能承接指定数量的差异压力。"""
        return self.available_capacity >= amount and self.status in (
            EntityStatus.ACTIVE,
            EntityStatus.STRESSED,
        )

    def absorb(self, amount: float):
        """承接差异压力。

        反馈循环：承压→保证金追加→流动性枯竭→承接力下降
        - 承接量占可用能力比例越高，触发正反馈越强
        - 高杠杆主体对承压更敏感（杠杆放大保证金需求）
        - 流动性低于阈值时，承接能力额外下降
        """
        self.available_capacity = max(0.0, self.available_capacity - amount)
        if self.capacity_ratio > 0.8:
            self.status = EntityStatus.STRESSED
        if self.available_capacity <= 0:
            self.status = EntityStatus.FORCED_OUT

        # ---- 反馈循环：承压触发保证金和流动性变化 ----
        self._apply_absorption_feedback(amount)

    def _apply_absorption_feedback(self, absorb_amount: float):
        """承压反馈循环：承接压力反作用于保证金/流动性/承接力。

        链式逻辑：
        1. 承压 → 占用保证金 → 流动性下降
        2. 流动性低 → 承接力额外下降（无法开新仓）
        3. 高杠杆 → 以上效应放大
        """
        if absorb_amount <= 0:
            return

        # 1. 保证金占用：承接量越大，占用保证金越多
        margin_cost = absorb_amount * 0.1 * self.leverage  # 杠杆放大保证金需求
        self.liquidity = max(0.0, self.liquidity - margin_cost)

        # 2. 流动性枯竭反馈：流动性低于阈值时，承接能力额外下降
        if self.liquidity < self.risk_tolerance * 0.3:
            # 流动性严重不足，额外削减承接力
            extra_cut = absorb_amount * 0.15 * self.leverage
            self.available_capacity = max(0.0, self.available_capacity - extra_cut)
            if self.available_capacity <= 0 and self.status != EntityStatus.FORCED_OUT:
                self.status = EntityStatus.MARGIN_CALLED

        # 3. 高杠杆主体：承压过半时状态升级
        if self.leverage > 2.0 and self.capacity_ratio > 0.6:
            if self.status == EntityStatus.ACTIVE:
                self.status = EntityStatus.STRESSED

    def release(self, amount: float):
        """释放承接能力（如减仓、交易所降保证金）。"""
        self.available_capacity = min(self.capacity, self.available_capacity + amount)
        # 释放时部分恢复流动性
        self.liquidity = min(self.capacity, self.liquidity + amount * 0.2)
        if self.capacity_ratio < 0.5:
            if self.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED):
                self.status = EntityStatus.ACTIVE

    def apply_margin_pressure(self, margin_increase: float):
        """保证金压力降低承接能力。"""
        # 杠杆越高，保证金压力越大
        self.available_capacity = max(0.0, self.available_capacity - margin_increase * self.leverage)
        # 保证金压力也消耗流动性
        self.liquidity = max(0.0, self.liquidity - margin_increase * self.leverage * 0.3)
        if self.available_capacity <= 0:
            self.status = EntityStatus.MARGIN_CALLED

    def _can_generate_feedback(self, fb_type: str, time: int) -> bool:
        """检查是否可以生成该类型的反馈（类型冷却机制）。
        
        同一主体在同一步内，同一类型反馈只能生成一次。
        """
        return self._feedback_cooldown.get(fb_type, -1) < time

    def _mark_feedback_generated(self, fb_type: str, time: int):
        """标记该类型反馈已生成。"""
        self._feedback_cooldown[fb_type] = time

    def generate_feedback_differences(self, absorb_amount: float, time: int) -> list:
        """承压后生成反馈差异（Phase 3 - 带约束）。

        差异论核心判断：差异不能凭空消失，只能换位置、形式或承接体。
        承接体在承接差异时，自身成为新的差异源——差异生成差异。

        Phase 3 改进：
        1. 衰减约束：反馈差异的 magnitude 应用衰减因子
        2. 类型冷却：同一主体在同一步内，同一类型反馈只能生成一次

        反馈的三个层次：
        1. 保证金反馈：承压超过阈值 → margin 差异
        2. 流动性反馈：流动性不足 → liquidity 差异
        3. 强平反馈：承接力耗尽 → position + liquidity 差异

        Returns:
            差异定义字典列表，由 runner 注入世界。
        """
        if absorb_amount <= 0:
            return []

        feedback = []

        # 1. 保证金反馈：承压超过 60% → 产生 margin 差异
        if self.capacity_ratio > 0.6 and self._can_generate_feedback("margin", time):
            # Phase 3: 应用衰减因子
            margin_magnitude = absorb_amount * 0.3 * self.leverage * FEEDBACK_DECAY
            if margin_magnitude > 0.01:
                feedback.append({
                    "id": f"feedback_margin_{self.id}_{time}",
                    "type": "margin",
                    "source_node": self.id,
                    "target_node": "clearing",
                    "magnitude": margin_magnitude,
                    "visibility": 0.9,
                    "persistence": 0.7,
                    "transformability": 0.8,
                    "description": f"反馈: {self.id} 承压 {absorb_amount:.1f}，杠杆 {self.leverage}x，衰减后产生保证金差异 {margin_magnitude:.1f}",
                })
                self._mark_feedback_generated("margin", time)

        # 2. 流动性反馈：流动性低于阈值 → 产生 liquidity 差异
        if self.liquidity < self.risk_tolerance * 0.3 and self._can_generate_feedback("liquidity", time):
            # Phase 3: 应用衰减因子
            liq_magnitude = absorb_amount * 0.2 * FEEDBACK_DECAY
            if liq_magnitude > 0.01:
                feedback.append({
                    "id": f"feedback_liquidity_{self.id}_{time}",
                    "type": "liquidity",
                    "source_node": self.id,
                    "target_node": "market",
                    "magnitude": liq_magnitude,
                    "visibility": 0.85,
                    "persistence": 0.6,
                    "transformability": 0.7,
                    "description": f"反馈: {self.id} 流动性 {self.liquidity:.1f} 低于阈值，衰减后产生流动性差异 {liq_magnitude:.1f}",
                })
                self._mark_feedback_generated("liquidity", time)

        # 3. 强平反馈：承接力耗尽 → 产生 position 差异
        # 注意：强平反馈使用特殊的 "forced_liquidation" 类型，避免与 liquidity 冷却冲突
        if self.available_capacity <= 0 and self._can_generate_feedback("forced_liquidation", time):
            # Phase 3: 应用衰减因子
            pos_magnitude = absorb_amount * 0.5 * FEEDBACK_DECAY
            if pos_magnitude > 0.01:
                feedback.append({
                    "id": f"feedback_position_{self.id}_{time}",
                    "type": "liquidity",  # 强平最终表现为流动性差异
                    "source_node": self.id,
                    "target_node": "market",
                    "magnitude": pos_magnitude,
                    "visibility": 0.95,
                    "persistence": 0.8,
                    "transformability": 0.6,
                    "description": f"反馈: {self.id} 承接力耗尽，衰减后强平产生流动性差异 {pos_magnitude:.1f}",
                })
                self._mark_feedback_generated("forced_liquidation", time)

        return feedback

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "capacity": round(self.capacity, 2),
            "available_capacity": round(self.available_capacity, 2),
            "used_capacity": round(self.used_capacity, 2),
            "capacity_ratio": round(self.capacity_ratio, 3),
            "risk_tolerance": round(self.risk_tolerance, 2),
            "liquidity": round(self.liquidity, 2),
            "leverage": round(self.leverage, 2),
            "preference": self.preference,
            "status": self.status.value,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        data = dict(data)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = EntityStatus(data["status"])
        return cls(**data)