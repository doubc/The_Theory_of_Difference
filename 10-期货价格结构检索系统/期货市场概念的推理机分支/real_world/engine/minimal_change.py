""""最小变易：优先选阻力小、成本低、可执行的路径。

最小变易不是最优选择，而是「最先能走的路」：
- 先调价，再调现货
- 先减仓，再改经营
- 先近月，再远月

体现在通道选择上：有效成本最低的通道优先。
"""

from typing import List, Optional

from ..core.difference import DifferenceSource
from ..core.channel import Channel
from ..core.entity import Entity


def apply_minimal_change(
    difference: DifferenceSource,
    channels: List[Channel],
    entities: List[Entity],
) -> Optional[str]:
    """应用最小变易原则，返回推荐的通道 ID。

    排序依据：
    1. 有效成本（越低越优先）
    2. 通道开放度（越高越优先）
    3. 锁定度（已有路径依赖时优先）
    """
    candidates = [
        c for c in channels
        if c.can_transfer(difference.type, difference.pressure)
    ]

    if not candidates:
        return None

    # 按有效成本排序（锁定度高的通道有成本折扣，体现路径依赖）
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (c.effective_cost(), -c.openness, -c.lock_in),
    )

    return sorted_candidates[0].id


def rank_channels(
    difference: DifferenceSource,
    channels: List[Channel],
) -> List[dict]:
    """为差异排列所有候选通道，返回排序结果。"""
    candidates = [
        c for c in channels
        if c.from_type == difference.type and c.status.value in ("open", "congested")
    ]

    ranked = sorted(
        candidates,
        key=lambda c: c.effective_cost(),
    )

    return [
        {
            "channel_id": c.id,
            "effective_cost": round(c.effective_cost(), 2),
            "remaining_capacity": round(c.remaining_capacity, 2),
            "lock_in": round(c.lock_in, 3),
            "status": c.status.value,
        }
        for c in ranked
    ]