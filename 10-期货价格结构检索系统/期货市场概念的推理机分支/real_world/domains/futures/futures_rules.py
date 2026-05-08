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

# 差异变形规则：from_type → (channel_from_type, to_type)
# 差异经通道转移后形式变化：inventory 经 basis_channel 变为 basis
DIFF_TRANSFORM_RULES: Dict[str, Dict[str, str]] = {
    "inventory": {
        "inventory": "basis",       # 库存经基差通道 → 基差差异
        "delivery": "delivery",     # 库存经仓单通道 → 交割差异
    },
    "time": {
        "time": "term_structure",
    },
    "space": {
        "space": "inventory",
    },
    "expectation": {
        "expectation": "price",     # 预期经期货合约通道 → 价格差异
    },
    "margin": {
        "margin": "liquidity",      # 保证金经清算通道 → 流动性差异
    },
    "liquidity": {
        "liquidity": "liquidity",   # 流动性经减仓通道 → 流动性差异（释放）
    },
    "delivery": {
        "delivery": "basis",        # 交割经交割通道 → 基差差异
        "inventory": "delivery",    # 交割经仓单通道 → 交割差异
    },
    "rule": {
        "rule": "rule",
    },
    "basis": {
        "basis": "price",           # 基差经基差通道 → 价格差异
    },
    "price": {
        "price": "margin",          # 价格经保证金通道 → 保证金差异
    },
}


def get_transform_type(diff_type: str, channel_from_type: str) -> Optional[str]:
    """差异经通道转移后的变形类型。

    变形规则查表逻辑：
    1. 先查 diff_type 对应的规则集
    2. 在规则集中找 channel_from_type 匹配的变形目标
    3. 如果没有匹配，返回 None（不发生变形）
    """
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
    """交易所作为二阶承接位置（Phase 2：三重干预 + 副作用差异）。

    当市场承接不足时，交易所可能介入：
    1. 降低差异生成率（限仓、限制新开仓）→ 作用于差异源
    2. 扩大通道容量（放宽交割品等级、增加交割库）→ 作用于通道
    3. 释放承接力（降保证金、释放冻结资金）→ 作用于承接体

    交易所介入不是消除差异，而是重组差异结构。
    每种干预都会产生副作用差异。
    """

    def __init__(self, threshold_pressure: float = 80.0, threshold_entity_stress: float = 0.6):
        self.threshold_pressure = threshold_pressure
        self.threshold_entity_stress = threshold_entity_stress
        self.intervention_count = 0

    def should_intervene(self, total_pressure: float, entity_stress_ratio: float) -> bool:
        """判断是否需要交易所介入。"""
        return total_pressure > self.threshold_pressure and entity_stress_ratio > self.threshold_entity_stress

    def choose_interventions(self, world) -> List[str]:
        """根据当前状态选择干预动作组合。

        策略：
        1. 差异源压力高（有 recurrent 差异）→ 降低差异生成率
        2. 通道拥堵 → 扩大通道容量
        3. 主体承压 → 释放承接力
        4. 持续破缺 → 三者同时执行
        """
        actions = []

        # 检查是否有高压力的 recurrent 差异
        high_recurrent = [
            d for d in world.differences.values()
            if d.recurrent and d.pressure > 40
        ]
        if high_recurrent:
            actions.append("reduce_recurrent")

        # 检查通道拥堵
        from ...core.channel import ChannelStatus
        congested = [
            c for c in world.channels.values()
            if c.status == ChannelStatus.CONGESTED
        ]
        if congested:
            actions.append("expand_channel")

        # 检查主体承压
        from ...core.entity import EntityStatus
        stressed = [
            e for e in world.entities.values()
            if e.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED)
        ]
        if stressed:
            actions.append("release_entity")

        # 如果没有任何匹配，至少尝试释放承接力
        if not actions:
            actions.append("release_entity")

        return actions

    def intervene_reduce_recurrent(self, world, time: int, reduction: float = 0.3):
        """动作一：降低差异生成率（限制新开仓）。

        效果：recurrent_rate *= (1 - reduction)
        限制对象：投机性差异源（expectation, liquidity, margin）
        不限制：结构性差异源（inventory, delivery）——这些是真实供需

        副作用：限仓产生预期差异（市场预期交易所进一步干预）
        """
        affected = []
        for diff in world.differences.values():
            if diff.recurrent and diff.type in ("expectation", "liquidity", "margin"):
                old_rate = diff.recurrent_rate
                diff.recurrent_rate *= (1 - reduction)
                affected.append(diff.id)

        if affected:
            self.intervention_count += 1
            world.trace.add_event(
                time=time,
                event_type="exchange_intervene",
                difference_id="",
                amount=reduction,
                reason=f"交易所降低差异生成率 {reduction:.0%}，影响: {', '.join(affected)}",
            )

            # 副作用：限仓产生预期差异
            side_effect = {
                "id": f"intervention_expectation_{time}",
                "type": "expectation",
                "source_node": "exchange",
                "target_node": "market",
                "magnitude": reduction * 35,
                "visibility": 0.9,
                "persistence": 0.5,
                "transformability": 0.7,
                "description": f"副作用: 限仓干预产生预期差异（市场预期交易所进一步干预）",
            }
            world.trace.add_event(
                time=time,
                event_type="intervention_side_effect",
                difference_id=side_effect["id"],
                amount=side_effect["magnitude"],
                reason=f"干预副作用: 限仓 → 预期差异 {side_effect['magnitude']:.1f}",
            )
            return side_effect

        return None

    def intervene_expand_channel(self, world, time: int, expansion: float = 0.5):
        """动作二：扩大通道容量（放宽交割品等级、增加交割库）。

        效果：channel.capacity *= (1 + expansion)
        副作用：扩通道产生规则差异（交割标准放宽可能引发质量争议）
        """
        from ...core.channel import ChannelStatus
        expanded = []
        for ch in world.channels.values():
            if ch.status == ChannelStatus.CONGESTED:
                old_cap = ch.capacity
                ch.capacity *= (1 + expansion)
                expanded.append(f"{ch.id}({old_cap:.0f}→{ch.capacity:.0f})")

        if expanded:
            self.intervention_count += 1
            world.trace.add_event(
                time=time,
                event_type="exchange_intervene",
                difference_id="",
                amount=expansion,
                reason=f"交易所扩大通道容量 {expansion:.0%}，影响: {', '.join(expanded)}",
            )

            # 副作用：扩通道产生规则差异
            side_effect = {
                "id": f"intervention_rule_{time}",
                "type": "rule",
                "source_node": "exchange",
                "target_node": "delivery",
                "magnitude": expansion * 25,
                "visibility": 0.8,
                "persistence": 0.4,
                "transformability": 0.6,
                "description": f"副作用: 扩通道产生规则差异（交割标准放宽引发质量争议）",
            }
            world.trace.add_event(
                time=time,
                event_type="intervention_side_effect",
                difference_id=side_effect["id"],
                amount=side_effect["magnitude"],
                reason=f"干预副作用: 扩通道 → 规则差异 {side_effect['magnitude']:.1f}",
            )
            return side_effect

        return None

    def intervene_release_entity(self, world, time: int, entity_type: str = "speculator", release: float = 0.3):
        """动作三：释放承接力（降保证金、释放冻结资金）。

        效果：entity.release(entity.used_capacity * release)
        副作用：释放承接力产生流动性差异（资金重新流入市场）
        """
        from ...core.entity import EntityStatus
        released = []
        for entity in world.entities.values():
            if entity.type == entity_type and entity.capacity_ratio > 0.3:
                release_amount = entity.used_capacity * release
                if release_amount > 0.01:
                    entity.release(release_amount)
                    released.append(f"{entity.id}({release_amount:.1f})")

        if released:
            self.intervention_count += 1
            world.trace.add_event(
                time=time,
                event_type="exchange_intervene",
                difference_id="",
                amount=release,
                reason=f"交易所释放承接力 {release:.0%}，影响: {', '.join(released)}",
            )

            # 副作用：释放承接力产生流动性差异
            side_effect = {
                "id": f"intervention_liquidity_{time}",
                "type": "liquidity",
                "source_node": "exchange",
                "target_node": "market",
                "magnitude": release * 40,
                "visibility": 0.85,
                "persistence": 0.5,
                "transformability": 0.7,
                "description": f"副作用: 释放承接力产生流动性差异（资金重新流入市场）",
            }
            world.trace.add_event(
                time=time,
                event_type="intervention_side_effect",
                difference_id=side_effect["id"],
                amount=side_effect["magnitude"],
                reason=f"干预副作用: 释放承接力 → 流动性差异 {side_effect['magnitude']:.1f}",
            )
            return side_effect

        return None

    # ---- 兼容旧接口 ----

    def intervene_margin_increase(self, world, time: int, increase: float = 0.2):
        """提高保证金（影响高杠杆主体）。兼容旧接口。"""
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
        """强制减仓（释放部分承接力）。兼容旧接口。"""
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
