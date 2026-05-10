""""转移引擎：差异如何选择通道并转移 + 变形链。

核心逻辑：
1. 筛选候选通道（开放 + 类型匹配 + 有容量）
2. 按有效成本排序（最小变易原则）
3. 执行转移（容量足则全转，不足则部分转）
4. 剩余压力积累
5. 变形：差异经通道转移后，按变形规则生成新类型差异（Phase 2）
"""

from typing import List, Optional, Tuple, Dict, Any

from ..core.difference import DifferenceSource
from ..core.channel import Channel
from ..core.trace import Trace
from ..domains.futures.futures_rules import get_transform_type


def choose_channel(difference: DifferenceSource, channels: List[Channel]) -> Optional[Channel]:
    """为差异选择最优通道（最小变易原则：取有效成本最低的）。"""
    candidates = [
        c for c in channels
        if c.can_transfer(difference.type, difference.pressure)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda c: c.effective_cost())


def transfer_difference(
    difference: DifferenceSource,
    channel: Channel,
    trace: Trace,
    time: int,
) -> Tuple[float, float]:
    """通过通道转移差异压力。

    Returns:
        (transferred_amount, remaining_amount)
    """
    if difference.pressure <= 0:
        return 0.0, 0.0

    # 实际转移量 = min(差异压力, 通道剩余容量)
    amount = min(difference.pressure, channel.remaining_capacity)

    if amount <= 0:
        # 通道容量不足，差异积累
        trace.add_event(
            time=time,
            event_type="accumulate",
            difference_id=difference.id,
            channel_id=channel.id,
            amount=difference.pressure,
            reason="通道容量不足，差异积累",
        )
        return 0.0, difference.pressure

    # 执行转移
    actual = channel.transfer(amount)
    difference.reduce_pressure(actual)

    # 记录轨迹
    trace.add_event(
        time=time,
        event_type="transfer",
        difference_id=difference.id,
        from_node=difference.source_node,
        to_node=difference.target_node,
        channel_id=channel.id,
        amount=actual,
        reason=f"经通道 {channel.id} 转移 {actual:.1f} 压力",
    )

    remaining = difference.pressure
    if remaining > 0.01:
        trace.add_event(
            time=time,
            event_type="accumulate",
            difference_id=difference.id,
            amount=remaining,
            reason=f"转移后剩余 {remaining:.1f} 压力积累",
        )

    return actual, remaining


def transfer_and_transform(
    difference: DifferenceSource,
    channel: Channel,
    trace: Trace,
    time: int,
    chain_depth: int = 0,
) -> Tuple[float, float, Optional[Dict[str, Any]]]:
    """转移差异并检查变形规则。

    变形不是"继续转移同一个差异"，而是"转移后产生的新差异继续寻找通道"。
    每一步变形都是差异生成新差异的过程。

    Returns:
        (transferred_amount, remaining_amount, transform_diff_dict_or_None)
        transform_diff_dict 包含新差异的定义，由 runner 注入世界。
    """
    transferred, remaining = transfer_difference(difference, channel, trace, time)

    transform_info = None
    if transferred > 0:
        # 检查变形规则
        new_type = get_transform_type(difference.type, channel.from_type)
        if new_type and new_type != difference.type:
            # 变形：生成新类型差异
            # 压力 = 转移量 * 变形效率（通道拥堵越高，变形损耗越大）
            transform_efficiency = max(0.3, 1.0 - channel.congestion)
            transform_pressure = transferred * transform_efficiency
            # 精确计算损耗：转移量 - 变形后压力
            loss_amount = transferred - transform_pressure

            if transform_pressure > 0.01:
                transform_info = {
                    "id": f"transform_{difference.type}_to_{new_type}_{chain_depth}_{difference.id}",
                    "type": new_type,
                    "source_node": channel.id,
                    "target_node": difference.target_node,
                    "magnitude": transform_pressure,
                    "pressure": transform_pressure,
                    "visibility": difference.visibility,
                    "persistence": difference.persistence * 0.8,  # 变形后持续性略降
                    "transformability": difference.transformability * 0.9,
                    "description": f"变形: {difference.type} → {new_type}，经通道 {channel.id}，深度 {chain_depth}",
                }

                # 记录变形事件（包含精确损耗）
                trace.add_event(
                    time=time,
                    event_type="transform",
                    difference_id=difference.id,
                    channel_id=channel.id,
                    amount=transform_pressure,
                    reason=f"差异变形: {difference.type} → {new_type}，经通道 {channel.id}，深度 {chain_depth}，损耗={loss_amount:.2f}",
                )

                # 单独记录损耗事件（用于精确守恒检查）
                if loss_amount > 0.01:
                    trace.add_event(
                        time=time,
                        event_type="loss",
                        difference_id=difference.id,
                        channel_id=channel.id,
                        amount=loss_amount,
                        reason=f"通道损耗: 转移 {transferred:.2f}，效率 {transform_efficiency:.2f}，损耗 {loss_amount:.2f}",
                    )

    return transferred, remaining, transform_info
