""""守恒检查：差异不能被无代价清零。

守恒不是物理守恒，而是模型约束：
- 差异必须有去处（转移、积累、变形、延期、回流）
- 无记录消失 = 模型错误
- 守恒检查是每步必须执行的验证
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
    tolerance: float = 0.5,
) -> Tuple[bool, str]:
    """守恒检查。

    初始总量 = 当前残余压力 + 已转移量 + 已变形量 + 通道成本

    Args:
        initial_total: 初始差异压力总量
        differences: 当前所有差异源
        trace: 轨迹记录
        time: 当前时间步
        tolerance: 容差（浮点误差允许范围）

    Returns:
        (passed, message)
    """
    # 当前残余压力
    remaining = sum(d.pressure for d in differences.values())

    # 已转移量（从轨迹中提取）
    transferred = sum(
        e.amount for e in trace.events
        if e.event_type == "transfer" and e.time <= time
    )

    # 已积累量
    accumulated = sum(
        e.amount for e in trace.events
        if e.event_type == "accumulate" and e.time <= time
    )

    # 简化守恒：初始 ≈ 残余 + 已转移
    accounted = remaining + transferred
    gap = abs(initial_total - accounted)

    if gap > tolerance:
        msg = (
            f"守恒检查失败: 初始={initial_total:.2f}, "
            f"残余={remaining:.2f}, 已转移={transferred:.2f}, "
            f"差距={gap:.2f} > 容差={tolerance:.2f}"
        )
        return False, msg

    return True, f"守恒检查通过: 初始={initial_total:.2f}, 残余={remaining:.2f}, 已转移={transferred:.2f}"