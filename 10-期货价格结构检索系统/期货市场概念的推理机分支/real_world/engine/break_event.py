""""破缺：差异积累超阈值触发的内生事件。

破缺不是外生冲击，而是差异积累到阈值后的必然结果：
- 价格跳变
- 基差异常
- 近月逼仓
- 流动性枯竭
- 保证金追缴
- 强制平仓
- 规则调整
- 交割失败
- 主体退出
"""

from typing import Dict, List

from ..core.difference import DifferenceSource, DifferenceStatus
from ..core.event import Event, EventType
from ..core.trace import Trace


# 差异类型到破缺事件类型的映射
BREAK_EVENT_MAP = {
    "inventory": EventType.ACCUMULATION_OVERFLOW,
    "liquidity": EventType.LIQUIDITY_DRY,
    "expectation": EventType.PRICE_JUMP,
    "margin": EventType.MARGIN_CALL,
    "basis": EventType.BASIS_ANOMALY,
    "delivery": EventType.DELIVERY_FAILURE,
    "term_structure": EventType.NEAR_MONTH_SQUEEZE,
}


def check_break_events(
    differences: Dict[str, DifferenceSource],
    thresholds: Dict[str, float],
    trace: Trace,
    time: int,
) -> List[Event]:
    """检查是否有差异积累超过阈值，触发破缺事件。

    Args:
        differences: 所有差异源
        thresholds: 各类型的破缺阈值 { type: threshold }
        trace: 轨迹记录
        time: 当前时间步

    Returns:
        本次触发的破缺事件列表
    """
    events = []

    for diff_id, diff in differences.items():
        if diff.status != DifferenceStatus.ACTIVE:
            continue

        threshold = thresholds.get(diff.type)
        if threshold is None:
            continue

        if diff.pressure >= threshold:
            event_type = BREAK_EVENT_MAP.get(diff.type, EventType.ACCUMULATION_OVERFLOW)
            severity = min(1.0, diff.pressure / threshold)

            event = Event(
                time=time,
                event_type=event_type,
                difference_id=diff_id,
                severity=severity,
                description=(
                    f"差异 {diff_id} 压力 {diff.pressure:.1f} 超过阈值 {threshold:.1f}，"
                    f"触发 {event_type.value}，严重度 {severity:.2f}"
                ),
            )
            events.append(event)

            # 记录轨迹
            trace.add_event(
                time=time,
                event_type="break",
                difference_id=diff_id,
                amount=diff.pressure,
                reason=f"破缺: {event_type.value}，压力 {diff.pressure:.1f} >= 阈值 {threshold:.1f}",
            )

            # 破缺后差异压力部分释放
            diff.reduce_pressure(diff.pressure * 0.5)

    return events