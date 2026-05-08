""""守恒检查：差异不能被无代价清零（Phase 2 最终版）。

守恒检查策略：步级压力对比法。
每步记录开始时的总压力，步末再算一次。
差值只能由已知机制解释：
- recurrent 生成（增加）
- 破缺释放（减少）
- 通道成本损耗（减少）= 转移量 * (1 - 变形效率)

如果差值不能被已知机制解释，就是守恒违反。
"""

from typing import Dict, List, Tuple

from ..core.difference import DifferenceSource
from ..core.trace import Trace


class ConservationError(Exception):
    """守恒违反错误。"""
    pass


# 上一步的总压力（模块级缓存）
_prev_total_pressure: float = 0.0


def check_conservation(
    initial_total: float,
    differences: Dict[str, DifferenceSource],
    trace: Trace,
    time: int,
    tolerance: float = 20.0,
) -> Tuple[bool, str]:
    """守恒检查（步级压力对比法）。

    每步开始时记录总压力，步末再算一次。
    差值 = 步末总压力 - 步初总压力
    已知解释：recurrent生成 - 破缺释放 - 通道损耗

    Args:
        initial_total: 初始差异压力总量
        differences: 当前所有差异源
        trace: 轨迹记录
        time: 当前时间步
        tolerance: 容差

    Returns:
        (passed, message)
    """
    global _prev_total_pressure

    # 当前残余压力
    current_total = sum(d.pressure for d in differences.values())

    # 第一步：用初始总量作为步初
    if time == 1:
        _prev_total_pressure = initial_total

    # 压力变化
    prev = _prev_total_pressure
    delta = current_total - prev

    # 本步的已知机制
    recurrent_generated = sum(
        e.amount for e in trace.events
        if e.event_type == "recurrent_generate" and e.time == time
    )
    break_released = sum(
        e.amount for e in trace.events
        if e.event_type == "break_release" and e.time == time
    )

    # 本步通道损耗：转移量 - 变形量（变形效率损耗）
    transferred = sum(
        e.amount for e in trace.events
        if e.event_type == "transfer" and e.time == time
    )
    transformed = sum(
        e.amount for e in trace.events
        if e.event_type == "transform" and e.time == time
    )
    channel_loss = max(0, transferred - transformed)

    # 已知解释的差值
    explained_delta = recurrent_generated - break_released - channel_loss

    # 未解释的差值
    unexplained = abs(delta - explained_delta)

    # 更新步初压力
    _prev_total_pressure = current_total

    if unexplained > tolerance:
        msg = (
            f"守恒检查失败: 步初={prev:.2f}, "
            f"步末={current_total:.2f}, 变化={delta:.2f}, "
            f"recurrent={recurrent_generated:.2f}, 破缺释放={break_released:.2f}, "
            f"通道损耗={channel_loss:.2f}, 未解释={unexplained:.2f}"
        )
        return False, msg

    return True, f"守恒通过: 步末={current_total:.2f}, 变化={delta:.2f}"


def reset_conservation():
    """重置守恒检查状态（用于新的运行）。"""
    global _prev_total_pressure
    _prev_total_pressure = 0.0
