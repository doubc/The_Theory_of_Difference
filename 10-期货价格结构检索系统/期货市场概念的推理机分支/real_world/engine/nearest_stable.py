""""最近稳态判定：当前约束下最先能稳住的状态，不是最优。

最近稳态的形成条件：
1. 总压力低于阈值
2. 主要差异有承接
3. 连续若干轮无破缺
4. 通道选择稳定
5. 主体退出放缓

可能滑向的稳态：
- basis_widening: 基差扩大稳态
- low_liquidity: 低流动性稳态
- near_month_squeeze: 近月挤压稳态
- rule_adjusted: 规则调整后新稳态
- liquidity_recovery: 流动性恢复稳态
- margin_relief: 保证金缓解稳态
"""

from typing import Dict, List, Tuple, Optional

from ..core.difference import DifferenceSource, DifferenceStatus
from ..core.channel import Channel, ChannelStatus
from ..core.entity import Entity, EntityStatus
from ..core.state import State
from ..core.trace import Trace


STABLE_LABELS = [
    "basis_widening",
    "low_liquidity",
    "near_month_squeeze",
    "rule_adjusted",
    "liquidity_recovery",
    "margin_relief",
    "unstable",
]


def check_nearest_stable(
    differences: Dict[str, DifferenceSource],
    channels: Dict[str, Channel],
    entities: Dict[str, Entity],
    states: List[State],
    trace: Trace,
    time: int,
    stability_window: int = 3,
    pressure_threshold: float = 30.0,
) -> Tuple[str, str]:
    """判定当前最近稳态。

    Returns:
        (stable_label, reason)
    """
    if not states:
        return "unstable", "尚无状态快照，无法判定稳态"

    # 检查最近 N 步是否有破缺事件
    recent_states = states[-stability_window:]
    recent_breaks = sum(s.break_events_count for s in recent_states)

    # 计算当前总压力
    total_pressure = sum(d.pressure for d in differences.values() if d.status == DifferenceStatus.ACTIVE)

    # 计算通道拥堵比例
    active_channels = [c for c in channels.values() if c.status == ChannelStatus.OPEN]
    congested_channels = [c for c in channels.values() if c.status == ChannelStatus.CONGESTED]
    congestion_ratio = len(congested_channels) / max(1, len(channels))

    # 计算主体压力比例
    stressed_entities = [e for e in entities.values() if e.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED)]
    entity_stress_ratio = len(stressed_entities) / max(1, len(entities))

    # 检查是否有dominant差异类型
    active_diffs = [d for d in differences.values() if d.status == DifferenceStatus.ACTIVE]
    if active_diffs:
        diff_type_count: Dict[str, float] = {}
        for d in active_diffs:
            diff_type_count[d.type] = diff_type_count.get(d.type, 0.0) + d.pressure
        dominant_type = max(diff_type_count, key=diff_type_count.get)
    else:
        dominant_type = "none"

    # --- 判定逻辑 ---
    if recent_breaks > 0 and recent_breaks >= len(recent_states):
        return "unstable", f"近{stability_window}步有{recent_breaks}次破缺，系统不稳定"

    if entity_stress_ratio > 0.5:
        return "margin_relief", f"超过{entity_stress_ratio:.0%}主体处于压力状态，等待保证金缓解"

    if total_pressure < pressure_threshold and len(active_diffs) <= 2:
        # 压力低且差异少，流动性恢复
        return "liquidity_recovery", f"总压力{total_pressure:.1f}<{pressure_threshold}，活跃差异{len(active_diffs)}≤2，流动性恢复稳态"

    if congestion_ratio > 0.6:
        return "low_liquidity", f"通道拥堵比例{congestion_ratio:.0%}>60%，低流动性稳态"

    # 基于dominant差异类型判定
    if dominant_type == "inventory":
        # 库存差异显影为基差 → 基差扩大稳态
        return "basis_widening", f"主导差异类型为 {dominant_type}，库存差异经基差通道显影，基差扩大稳态"

    elif dominant_type == "term_structure":
        return "near_month_squeeze", f"主导差异类型为 {dominant_type}，近月交割压力积累，近月挤压稳态"

    elif dominant_type == "rule":
        return "rule_adjusted", f"主导差异类型为 {dominant_type}，交易所规则变化，等待规则调整后新稳态"

    # 默认：压力中等但无明显破缺 → 仍不稳定
    if total_pressure < 60:
        return "unstable", f"总压力{total_pressure:.1f}，无明显稳定路径，需继续观察"

    return "unstable", f"总压力{total_pressure:.1f}，近期破缺{recent_breaks}次，通道拥堵{congestion_ratio:.0%}，尚未找到最近稳态"