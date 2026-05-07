""""转移引擎：差异如何选择通道并转移。

核心逻辑：
1. 筛选候选通道（开放 + 类型匹配 + 有容量）
2. 按有效成本排序（最小变易原则）
3. 执行转移（容量足则全转，不足则部分转）
4. 剩余压力积累
"""

from typing import List, Optional, Tuple

from ..core.difference import DifferenceSource
from ..core.channel import Channel
from ..core.trace import Trace


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