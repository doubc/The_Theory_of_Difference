""""锁定：通道反复使用形成路径依赖。

锁定不是错误，而是差异运动的惯性：
- 降低后续转移成本（锁定折扣）
- 积累长期脆弱性（过度锁定 = 拥挤结构）
- 锁定度上限 1.0
"""

from ..core.channel import Channel
from ..core.trace import Trace


def update_lock_in(channel: Channel, transferred_amount: float, trace: Trace, time: int):
    """更新通道锁定度。

    锁定度增量 = 转移量 * 0.001
    """
    old_lock_in = channel.lock_in
    channel._update_lock_in(transferred_amount)

    # 如果锁定度显著增加，记录轨迹
    if channel.lock_in - old_lock_in > 0.01:
        trace.add_event(
            time=time,
            event_type="lock_in",
            difference_id="",
            channel_id=channel.id,
            amount=channel.lock_in - old_lock_in,
            reason=f"通道 {channel.id} 锁定度从 {old_lock_in:.3f} 增至 {channel.lock_in:.3f}",
        )


def check_lock_in_vulnerability(channels: list) -> list:
    """检查过度锁定的通道（脆弱性预警）。

    锁定度 > 0.7 的通道有拥挤风险。
    """
    vulnerable = []
    for c in channels:
        if c.lock_in > 0.7:
            vulnerable.append({
                "channel_id": c.id,
                "lock_in": round(c.lock_in, 3),
                "effective_cost": round(c.effective_cost(), 2),
                "warning": "高锁定度 — 拥挤结构风险",
            })
    return vulnerable