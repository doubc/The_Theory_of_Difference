""""Markdown 报告生成器。

输出结构：
1. 实验概况
2. 输入差异
3. 主要转移路径
4. 通道状态
5. 最近稳态
6. 结构判断（无交易建议）
"""

from typing import List

from ..core.world import World
from ..core.state import State


def generate_report(world: World, exp_id: str = "exp") -> str:
    """生成 Markdown 格式的实验报告。

    Args:
        world: 运行完成后的世界对象
        exp_id: 实验ID

    Returns:
        Markdown 文本
    """
    lines: List[str] = []

    # 标题
    lines.append(f"# Real_World 实验报告：{world.name}")
    lines.append("")
    lines.append(f"**实验ID**: {exp_id}")
    lines.append(f"**运行步数**: {world.time}")
    lines.append(f"**总破缺事件**: {len(world.events)}")
    lines.append("")

    # 一、输入差异
    lines.append("## 一、输入差异")
    lines.append("")
    lines.append("| ID | 类型 | 源节点 | 目标节点 | 初始压力 | 最终压力 | 状态 |")
    lines.append("|---|---|---|---|---|---|---|")
    for diff in world.differences.values():
        lines.append(
            f"| {diff.id} | {diff.type} | {diff.source_node} | {diff.target_node} "
            f"| {diff.magnitude * diff.visibility * diff.persistence:.1f} | {diff.pressure:.1f} | {diff.status.value} |"
        )
    lines.append("")

    # 二、主要转移路径
    lines.append("## 二、主要转移路径")
    lines.append("")
    transfer_events = [e for e in world.trace.events if e.event_type == "transfer"]
    if transfer_events:
        lines.append("| 时间 | 差异ID | 通道ID | 转移量 | 说明 |")
        lines.append("|---|---|---|---|---|")
        for e in transfer_events[:20]:  # 最多显示 20 条
            lines.append(f"| {e.time} | {e.difference_id} | {e.channel_id} | {e.amount:.1f} | {e.reason} |")
    else:
        lines.append("*无转移事件*")
    lines.append("")

    # 三、通道状态
    lines.append("## 三、通道状态")
    lines.append("")
    lines.append("| ID | 类型转换 | 有效成本 | 使用率 | 拥堵度 | 锁定度 | 状态 |")
    lines.append("|---|---|---|---|---|---|---|")
    for ch in world.channels.values():
        usage = ch.used_capacity / max(1, ch.capacity) * 100
        lines.append(
            f"| {ch.id} | {ch.from_type}→{ch.to_type} | {ch.effective_cost():.1f} "
            f"| {usage:.0%} | {ch.congestion:.2f} | {ch.lock_in:.3f} | {ch.status.value} |"
        )
    lines.append("")

    # 四、破缺事件
    lines.append("## 四、破缺事件")
    lines.append("")
    if world.events:
        lines.append("| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |")
        lines.append("|---|---|---|---|---|")
        for ev in world.events:
            lines.append(f"| {ev.time} | {ev.event_type.value} | {ev.difference_id} | {ev.severity:.2f} | {ev.description} |")
    else:
        lines.append("*无破缺事件*")
    lines.append("")

    # 五、最近稳态
    lines.append("## 五、最近稳态")
    lines.append("")
    if world.states:
        final_state = world.states[-1]
        lines.append(f"**最终稳态判定**: {final_state.nearest_stable_label}")
        lines.append("")
        reason = final_state.detail.get("stable_reason", "")
        if reason:
            lines.append(f"**判定理由**: {reason}")
    else:
        lines.append("*尚无状态快照*")
    lines.append("")

    # 六、状态演变
    lines.append("## 六、状态演变")
    lines.append("")
    lines.append("| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |")
    lines.append("|---|---|---|---|---|---|")
    for s in world.states:
        lines.append(
            f"| {s.time} | {s.total_pressure:.1f} | {s.active_differences} | {s.active_channels} "
            f"| {s.pressure_level} | {s.nearest_stable_label} |"
        )
    lines.append("")

    # 七、结构判断
    lines.append("## 七、结构判断")
    lines.append("")
    lines.append("> **注意**: 本报告为差异结构分析，不构成任何交易建议。")
    lines.append("")

    # 主导差异
    dom_diff = world.dominant_difference()
    if dom_diff:
        lines.append(f"- **主导差异**: {dom_diff.id}（{dom_diff.type}），压力 {dom_diff.pressure:.1f}")
    else:
        lines.append("- **主导差异**: 无活跃差异")

    # 通道瓶颈
    congested = [c for c in world.channels.values() if c.status.value == "congested"]
    if congested:
        lines.append(f"- **通道瓶颈**: {', '.join(c.id for c in congested)}")

    # 稳态判断
    if world.states:
        final_stable = world.states[-1].nearest_stable_label
        lines.append(f"- **最近稳态**: {final_stable}")
    lines.append("")

    return "\n".join(lines)