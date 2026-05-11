#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Futures domain-specific rules.

Difference transform rules, channel-difference type matching,
near-month/far-month rules, exchange second-order absorption.
"""

from typing import Dict, List, Optional, Tuple

# Difference type -> channel type mapping
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

# Difference transform rules: from_type -> (channel_from_type -> to_type)
DIFF_TRANSFORM_RULES: Dict[str, Dict[str, str]] = {
    "inventory": {
        "inventory": "basis",
        "delivery": "delivery",
    },
    "time": {
        "time": "term_structure",
    },
    "space": {
        "space": "inventory",
    },
    "expectation": {
        "expectation": "price",
    },
    "margin": {
        "margin": "liquidity",
    },
    "liquidity": {
        "liquidity": "liquidity",
    },
    "delivery": {
        "delivery": "basis",
        "inventory": "delivery",
    },
    "rule": {
        "rule": "rule",
    },
    "basis": {
        "basis": "price",
    },
    "price": {
        "price": "margin",
    },
}


def get_transform_type(diff_type: str, channel_from_type: str) -> Optional[str]:
    """Get the transformed difference type after passing through a channel."""
    rules = DIFF_TRANSFORM_RULES.get(diff_type, {})
    return rules.get(channel_from_type)


def get_compatible_channels(diff_type: str) -> List[str]:
    """Get list of channel types compatible with a difference type."""
    return DIFF_CHANNEL_MAP.get(diff_type, [])


def near_month_delivery_multiplier(is_near_month: bool, months_to_expiry: int = 1) -> float:
    """Near-month delivery pressure multiplier."""
    if not is_near_month:
        return 1.0
    if months_to_expiry <= 1:
        return 1.5
    elif months_to_expiry <= 3:
        return 1.2
    return 1.0


def apply_futures_transform_rules(difference, channel, transferred_amount, efficiency):
    """Apply futures-specific transform rules to a difference."""
    target_type = get_transform_type(difference.type, channel.from_type)
    if target_type is None:
        return None
    return {
        "source_type": difference.type,
        "target_type": target_type,
        "magnitude": transferred_amount * efficiency,
        "channel_id": channel.id,
    }


class ExchangeIntervention:
    """Exchange as second-order absorber (triple intervention + side-effect differences).

    P2: Added side-effect decay mechanism to prevent linear difference explosion
    under sustained high pressure.
    """

    # P2: class-level defaults for side-effect decay
    DEFAULT_SIDE_EFFECT_DECAY = 0.85  # each intervention reduces side-effect magnitude by 15%
    DEFAULT_SIDE_EFFECT_FLOOR = 5.0   # minimum side-effect magnitude
    DEFAULT_MAX_SIDE_EFFECT_ACCUM = 200.0  # cap on total accumulated side-effect pressure

    def __init__(self, threshold_pressure: float = 80.0,
                 threshold_entity_stress: float = 0.6,
                 side_effect_decay: float = None,
                 side_effect_floor: float = None,
                 max_side_effect_accum: float = None):
        self.threshold_pressure = threshold_pressure
        self.threshold_entity_stress = threshold_entity_stress
        self.intervention_count = 0
        self.cumulative_side_effect_magnitude = 0.0
        # P2: configurable decay params
        self.side_effect_decay = side_effect_decay or self.DEFAULT_SIDE_EFFECT_DECAY
        self.side_effect_floor = side_effect_floor or self.DEFAULT_SIDE_EFFECT_FLOOR
        self.max_side_effect_accum = max_side_effect_accum or self.DEFAULT_MAX_SIDE_EFFECT_ACCUM

    def _calc_side_effect_magnitude(self, base_magnitude: float) -> float:
        """P2: Calculate side-effect magnitude with decay and caps.

        - Decays by side_effect_decay^intervention_count
        - Never below side_effect_floor
        - Cumulative side effects capped at max_side_effect_accum
        """
        decayed = base_magnitude * (self.side_effect_decay ** self.intervention_count)
        magnitude = max(self.side_effect_floor, decayed)
        # Check cumulative cap
        remaining_budget = self.max_side_effect_accum - self.cumulative_side_effect_magnitude
        if remaining_budget <= 0:
            return self.side_effect_floor  # at floor when cap reached
        magnitude = min(magnitude, remaining_budget)
        self.cumulative_side_effect_magnitude += magnitude
        return round(magnitude, 2)

    def should_intervene(self, total_pressure: float, entity_stress_ratio: float) -> bool:
        return total_pressure > self.threshold_pressure and entity_stress_ratio > self.threshold_entity_stress

    def choose_interventions(self, world) -> List[str]:
        actions = []
        high_recurrent = [d for d in world.differences.values() if d.recurrent and d.pressure > 40]
        if high_recurrent:
            actions.append("reduce_recurrent")

        from ...core.channel import ChannelStatus
        congested = [c for c in world.channels.values() if c.status == ChannelStatus.CONGESTED]
        if congested:
            actions.append("expand_channel")

        from ...core.entity import EntityStatus
        stressed = [e for e in world.entities.values()
                    if e.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED)]
        if stressed:
            actions.append("release_entity")

        if not actions:
            actions.append("release_entity")
        return actions

    def intervene_reduce_recurrent(self, world, time: int, reduction: float = 0.3):
        """Action 1: Reduce difference generation rate (position limits).

        Effect: recurrent_rate *= (1 - reduction)
        Side-effect: creates expectation differences (market anticipates further intervention).
        P2: side-effect magnitude decays with repeated interventions.
        """
        affected = []
        for diff in world.differences.values():
            if diff.recurrent and diff.type in ("expectation", "liquidity", "margin"):
                diff.recurrent_rate *= (1 - reduction)
                affected.append(diff.id)

        if affected:
            self.intervention_count += 1
            world.trace.add_event(
                time=time, event_type="exchange_intervene",
                difference_id="", amount=reduction,
                reason=f"交易所降低差异生成率 {reduction:.0%}，影响: {', '.join(affected)}",
            )

            # P2: side-effect with decay
            base_mag = reduction * 35
            mag = self._calc_side_effect_magnitude(base_mag)
            side_effect = {
                "id": f"intervention_expectation_{time}",
                "type": "expectation",
                "source_node": "exchange",
                "target_node": "market",
                "magnitude": mag,
                "visibility": 0.9,
                "persistence": 0.5,
                "transformability": 0.7,
                "description": f"副作用: 限仓干预产生预期差异（第{self.intervention_count}次干预）",
            }
            world.trace.add_event(
                time=time, event_type="intervention_side_effect",
                difference_id=side_effect["id"], amount=mag,
                reason=f"干预副作用: 限仓 → 预期差异 {mag:.1f} (第{self.intervention_count}次)",
            )
            return side_effect
        return None

    def intervene_expand_channel(self, world, time: int, expansion: float = 0.5):
        """Action 2: Expand channel capacity (relax delivery standards).

        Effect: channel.capacity *= (1 + expansion)
        Side-effect: creates rule differences (quality disputes from relaxed standards).
        P2: side-effect magnitude decays with repeated interventions.
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
                time=time, event_type="exchange_intervene",
                difference_id="", amount=expansion,
                reason=f"交易所扩大通道容量 {expansion:.0%}，影响: {', '.join(expanded)}",
            )

            # P2: side-effect with decay
            base_mag = expansion * 25
            mag = self._calc_side_effect_magnitude(base_mag)
            side_effect = {
                "id": f"intervention_rule_{time}",
                "type": "rule",
                "source_node": "exchange",
                "target_node": "delivery",
                "magnitude": mag,
                "visibility": 0.8,
                "persistence": 0.4,
                "transformability": 0.6,
                "description": f"副作用: 扩通道产生规则差异（第{self.intervention_count}次干预）",
            }
            world.trace.add_event(
                time=time, event_type="intervention_side_effect",
                difference_id=side_effect["id"], amount=mag,
                reason=f"干预副作用: 扩通道 → 规则差异 {mag:.1f} (第{self.intervention_count}次)",
            )
            return side_effect
        return None

    def intervene_release_entity(self, world, time: int,
                                  entity_type: str = "speculator", release: float = 0.3):
        """Action 3: Release absorption capacity (lower margin, release frozen funds).

        Effect: entity.release(entity.used_capacity * release)
        Side-effect: creates liquidity differences (funds re-enter market).
        P2: side-effect magnitude decays with repeated interventions.
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
                time=time, event_type="exchange_intervene",
                difference_id="", amount=release,
                reason=f"交易所释放承接力 {release:.0%}，影响: {', '.join(released)}",
            )

            # P2: side-effect with decay
            base_mag = release * 40
            mag = self._calc_side_effect_magnitude(base_mag)
            side_effect = {
                "id": f"intervention_liquidity_{time}",
                "type": "liquidity",
                "source_node": "exchange",
                "target_node": "market",
                "magnitude": mag,
                "visibility": 0.85,
                "persistence": 0.5,
                "transformability": 0.7,
                "description": f"副作用: 释放承接力产生流动性差异（第{self.intervention_count}次干预）",
            }
            world.trace.add_event(
                time=time, event_type="intervention_side_effect",
                difference_id=side_effect["id"], amount=mag,
                reason=f"干预副作用: 释放承接力 → 流动性差异 {mag:.1f} (第{self.intervention_count}次)",
            )
            return side_effect
        return None

    # ---- Legacy interface ----

    def intervene_margin_increase(self, world, time: int, increase: float = 0.2):
        """Increase margin (affects high-leverage entities). Legacy interface."""
        for entity in world.entities.values():
            if entity.type in ("speculator",) and entity.leverage > 2.0:
                entity.apply_margin_pressure(increase * entity.leverage * 10)
        self.intervention_count += 1
        world.trace.add_event(
            time=time, event_type="exchange_intervene",
            difference_id="", amount=increase,
            reason=f"交易所提高保证金 {increase:.0%}，高杠杆主体承压",
        )

    def intervene_position_limit(self, world, time: int, reduction: float = 0.3):
        """Force position reduction (release some absorption capacity). Legacy interface."""
        for entity in world.entities.values():
            if entity.type in ("speculator",) and entity.capacity_ratio > 0.5:
                release_amount = entity.used_capacity * reduction
                entity.release(release_amount)
        self.intervention_count += 1
        world.trace.add_event(
            time=time, event_type="exchange_intervene",
            difference_id="", amount=reduction,
            reason=f"交易所强制减仓 {reduction:.0%}，释放投机承接力",
        )


def apply_exchange_intervention(world, total_pressure: int, time: int) -> Dict:
    """Apply exchange intervention if needed. Returns result dict."""
    from ...core.entity import EntityStatus
    from ...core.channel import ChannelStatus

    intervention = ExchangeIntervention()

    # Calculate entity stress ratio
    stressed_count = sum(1 for e in world.entities.values()
                         if e.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED))
    total_entities = len(world.entities) or 1
    stress_ratio = stressed_count / total_entities

    result = {"triggered": False, "actions": [], "side_effects": [], "description": ""}

    if not intervention.should_intervene(total_pressure, stress_ratio):
        return result

    actions = intervention.choose_interventions(world)
    side_effects = []

    for action in actions:
        if action == "reduce_recurrent":
            se = intervention.intervene_reduce_recurrent(world, time)
            if se:
                side_effects.append(se)
        elif action == "expand_channel":
            se = intervention.intervene_expand_channel(world, time)
            if se:
                side_effects.append(se)
        elif action == "release_entity":
            se = intervention.intervene_release_entity(world, time)
            if se:
                side_effects.append(se)

    result["triggered"] = True
    result["actions"] = actions
    result["side_effects"] = side_effects
    result["description"] = f"交易所干预: {', '.join(actions)} ({len(side_effects)}个副作用差异)"

    return result
