"""期货领域专用规则。

差异变形规则：差异经通道转移时，形式可能变化。
通道-差异类型匹配：哪些差异可以走哪些通道。
近月/远月规则：近月交割压力更大。
交易所二阶承接：市场承接不足时，交易所介入。
"""

from typing import Dict, List, Optional, Tuple

# 差异类型→通道类型匹配表
DIFF_CHANNEL_MAP: Dict[str, List[str]] = {
    "inventory": ["basis", "storage", "futures_contract", "warehouse_receipt"],
    "time": ["term_structure", "futures_contract"],
    "space": ["spot_transport", "basis"],
    "quality": ["basis", "warehouse_receipt"],
    "expectation": ["futures_contract", "term_structure"],
    "liquidity": ["position_reduction", "futures_contract"],
    "margin": ["margin_clearing", "position_reduction"],
    "basis": ["futures_contract", "arbitrage"],
    "term_structure": ["futures_contract", "arbitrage"],
    "delivery": ["delivery_channel", "warehouse_receipt"],
    "rule": ["exchange_rule"],
}

# 差异变形规则：from_type → (channel_type, to_type)
DIFF_TRANSFORM_RULES: Dict[str, Dict[str, str]] = {
    "inventory": {
        "basis": "basis",
        "storage": "inventory",
        "futures_contract": "price",
        "warehouse_receipt": "delivery",
    },
    "time": {
        "term_structure": "term_structure",
        "futures_contract": "price",
    },
    "space": {
        "spot_transport": "inventory",
        "basis": "basis",
    },
    "expectation": {
        "futures_contract": "price",
        "term_structure": "term_structure",
    },
    "margin": {
        "margin_clearing": "liquidity",
        "position_reduction": "liquidity",
    },
    "liquidity": {
        "position_reduction": "liquidity",
        "futures_contract": "price",
    },
    "delivery": {
        "delivery_channel": "basis",
        "warehouse_receipt": "delivery",
    },
    "rule": {
        "exchange_rule": "rule",
    },
}


def get_transform_type(diff_type: str, channel_from_type: str) -> Optional[str]:
    """差异经通道转移后的变形类型。"""
    rules = DIFF_TRANSFORM_RULES.get(diff_type, {})
    return rules.get(channel_from_type)


def get_compatible_channels(diff_type: str) -> List[str]:
    """获取与差异类型兼容的通道类型列表。"""
    return DIFF_CHANNEL_MAP.get(diff_type, [])


def near_month_delivery_multiplier(is_near_month: bool, months_to_expiry: int = 1) -> float:
    """近月交割压力乘数。近月压力放大。"""
    if not is_near_month:
        return 1.0
    if months_to_expiry <= 1:
        return 1.5
    elif months_to_expiry <= 3:
        return 1.2
    return 1.0


class ExchangeIntervention:
    """交易所作为二阶承接位置。

    当市场承接不足时，交易所可能介入：
    - 提高保证金 → 降低投机承接
    - 调整涨跌停板 → 限制价格运动
    - 强制减仓 → 释放部分承接力
    - 调整交割规则 → 增加可交割品

    交易所介入不是消除差异，而是重组差异结构。
    """

    def __init__(self, threshold_pressure: float = 80.0, threshold_entity_stress: float = 0.6):
        self.threshold_pressure = threshold_pressure
        self.threshold_entity_stress = threshold_entity_stress
        self.intervention_count = 0

    def should_intervene(self, total_pressure: float, entity_stress_ratio: float) -> bool:
        """判断是否需要交易所介入。"""
        return total_pressure > self.threshold_pressure and entity_stress_ratio > self.threshold_entity_stress

    def intervene_margin_increase(self, world, time: int, increase: float = 0.2):
        """提高保证金（影响高杠杆主体）。"""
        for entity in world.entities.values():
            if entity.type in ("speculator",) and entity.leverage > 2.0:
                entity.apply_margin_pressure(increase * entity.leverage * 10)
        self.intervention_count += 1
        world.trace.add_event(
            time=time,
            event_type="exchange_intervene",
            difference_id="",
            amount=increase,
            reason=f"交易所提高保证金 {increase:.0%}，高杠杆主体承压",
        )

    def intervene_position_limit(self, world, time: int, reduction: float = 0.3):
        """强制减仓（释放部分承接力）。"""
        for entity in world.entities.values():
            if entity.type in ("speculator",) and entity.capacity_ratio > 0.5:
                release_amount = entity.used_capacity * reduction
                entity.release(release_amount)
        self.intervention_count += 1
        world.trace.add_event(
            time=time,
            event_type="exchange_intervene",
            difference_id="",
            amount=reduction,
            reason=f"交易所强制减仓 {reduction:.0%}，释放投机承接力",
        )