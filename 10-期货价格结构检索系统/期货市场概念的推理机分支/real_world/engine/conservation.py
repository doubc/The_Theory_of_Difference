""""守恒检查：差异不能被无代价清零（Phase 2 修正版）。

守恒不是物理守恒，而是模型约束：
- 差异必须有去处（转移、积累、变形、延期、回流）
- 无记录消失 = 模型错误

Phase 2 修正：使用步级压力守恒——每步开始和结束的压力差
只能由已知机制解释（recurrent生成、破缺释放、通道成本）。
"""

from typing import Dict, List, Tuple

from ..core.difference import DifferenceSource
from ..core.trace import Trace


class ConservationError(Exception):
    """守恒违反错误。"""
    pass


def check_conservation(
    initial_total: float,
    differences: Dict[str, DifferenceSource],
    trace: Trace,
    time: int,
    tolerance: float = 5.0,
) -> Tuple[bool, str]:
    """守恒检查（步级压力守恒）。

    核心逻辑：本步结束时的总压力 = 本步开始时的总压力 + recurrent生成 - 破缺释放 - 通道成本损耗

    通道成本损耗 = 转移量 * (1 - 变形效率)
    变形效率 = max(0.3, 1 - congestion)

    Args:
        initial_total: 初始差异压力总量
        differences: 当前所有差异源
        trace: 轨迹记录
        time: 当前时间步
        tolerance: 容差

    Returns:
        (passed, message)
    """
    # 当前残余压力（所有差异）
    remaining = sum(d.pressure for d in differences.values())

    # 本步的 recurrent 生成量
    recurrent_generated = sum(
        e.amount for e in trace.events
        if e.event_type == "recurrent_generate" and e.time == time
    )

    # 本步的破缺释放量
    break_released = sum(
        e.amount for e in trace.events
        if e.event_type == "break_release" and e.time == time
    )

    # 本步的转移量（用于计算通道损耗）
    transferred = sum(
        e.amount for e in trace.events
        if e.event_type == "transfer" and e.time == time
    )

    # 本步的变形量
    transformed = sum(
        e.amount for e in trace.events
        if e.event_type == "transform" and e.time == time
    )

    # 通道成本损耗：转移量中没有变成变形差异的部分
    # 变形效率约 0.7（平均），所以损耗约 0.3
    channel_loss = transferred - transformed if transferred > transformed else 0

    # 守恒检查：用初始总量做全局校验
    # 初始 + 所有recurrent = 当前残余 + 所有转移 + 所有破缺释放 + 通道损耗
    total_recurrent = sum(
        e.amount for e in trace.events
        if e.event_type == "recurrent_generate" and e.time <= time
    )
    total_break = sum(
        e.amount for e in trace.events
        if e.event_type == "break_release" and e.time <= time
    )
    total_transferred = sum(
        e.amount for e in trace.events
        if e.event_type == "transfer" and e.time <= time
    )
    total_transformed = sum(
        e.amount for e in trace.events
        if e.event_type == "transform" and e.time <= time
    )

    # 全局守恒：初始 + recurrent = 残余 + (转移 - 变形损耗) + 破缺释放
    # 转移 - 变形 = 通道吸收的纯损耗
    pure_channel_loss = total_transferred - total_transformed
    total_in = initial_total + total_recurrent
    total_out = remaining + pure_channel_loss + total_break
    gap = abs(total_in - total_out)

    if gap > tolerance:
        msg = (
            f"守恒检查失败: 初始={initial_total:.2f}, "
            f"残余={remaining:.2f}, 转移={total_transferred:.2f}, "
            f"变形={total_transformed:.2f}, 破缺释放={total_break:.2f}, "
            f"recurrent={total_recurrent:.2f}, 差距={gap:.2f}"
        )
        return False, msg

    return True, f"守恒通过: 残余={remaining:.2f}, 转移={total_transferred:.2f}, 破缺释放={total_break:.2f}"
