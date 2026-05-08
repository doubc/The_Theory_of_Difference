""""Markdown 报告生成器（Phase 2）。

输出结构：
1. 实验概况
2. 输入差异
3. 主要转移路径
4. 变形链
5. 反馈差异
6. 干预记录
7. 通道状态
8. 破缺事件
9. 最近稳态
10. 状态演变
11. 结构判断（无交易建议）
"""

from typing import List

from ..core.world import World
from ..core.state import State


def generate_report(world: World, exp_id: str = "exp") -> str:
    """生成 Markdown 格式的实验报告。"""
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
        # 只显示初始差异（非变形、非反馈、非干预副作用）
        if not diff.id.startswith(("transform_", "feedback_", "intervention_")):
            initial_pressure = diff.magnitude * diff.visibility * diff.persistence
            lines.append(
                f"| {diff.id} | {diff.type} | {diff.source_node} | {diff.target_node} "
                f"| {initial_pressure:.1f} | {diff.pressure:.1f} | {diff.status.value} |"
            )
    lines.append("")

    # 二、主要转移路径
    lines.append("## 二、主要转移路径")
    lines.append("")
    transfer_events = [e for e in world.trace.events if e.event_type == "transfer"]
    if transfer_events:
        lines.append("| 时间 | 差异ID | 通道ID | 转移量 | 说明 |")
        lines.append("|---|---|---|---|---|")
        for e in transfer_events[:30]:
            lines.append(f"| {e.time} | {e.difference_id} | {e.channel_id} | {e.amount:.1f} | {e.reason} |")
    else:
        lines.append("*无转移事件*")
    lines.append("")

    # 三、变形链（Phase 2）
    transform_events = [e for e in world.trace.events if e.event_type == "transform"]
    if transform_events:
        lines.append("## 三、变形链")
        lines.append("")
        lines.append("| 时间 | 源差异 | 通道 | 变形量 | 说明 |")
        lines.append("|---|---|---|---|---|")
        for e in transform_events:
            lines.append(f"| {e.time} | {e.difference_id} | {e.channel_id} | {e.amount:.1f} | {e.reason} |")
        lines.append("")

    # 四、反馈差异（Phase 2）
    feedback_diffs = [d for d in world.differences.values() if d.id.startswith("feedback_")]
    if feedback_diffs:
        lines.append("## 四、反馈差异")
        lines.append("")
        lines.append("| ID | 类型 | 来源 | 最终压力 | 状态 | 说明 |")
        lines.append("|---|---|---|---|---|---|")
        for d in feedback_diffs:
            lines.append(f"| {d.id} | {d.type} | {d.source_node} | {d.pressure:.1f} | {d.status.value} | {d.description} |")
        lines.append("")

    # 五、干预记录（Phase 2）
    intervention_events = [e for e in world.trace.events if e.event_type in ("exchange_intervene", "intervention_side_effect")]
    if intervention_events:
        lines.append("## 五、干预记录")
        lines.append("")
        lines.append("| 时间 | 类型 | 量 | 说明 |")
        lines.append("|---|---|---|---|")
        for e in intervention_events:
            lines.append(f"| {e.time} | {e.event_type} | {e.amount:.2f} | {e.reason} |")
        lines.append("")

    # 六、通道状态
    lines.append("## 六、通道状态")
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

    # 七、破缺事件
    lines.append("## 七、破缺事件")
    lines.append("")
    if world.events:
        lines.append("| 时间 | 事件类型 | 差异ID | 严重度 | 说明 |")
        lines.append("|---|---|---|---|---|")
        for ev in world.events:
            lines.append(f"| {ev.time} | {ev.event_type.value} | {ev.difference_id} | {ev.severity:.2f} | {ev.description} |")
    else:
        lines.append("*无破缺事件*")
    lines.append("")

    # 八、最近稳态
    lines.append("## 八、最近稳态")
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

    # 九、状态演变
    lines.append("## 九、状态演变")
    lines.append("")
    lines.append("| 时间 | 总压力 | 活跃差异 | 活跃通道 | 压力等级 | 稳态标签 |")
    lines.append("|---|---|---|---|---|---|")
    for s in world.states:
        lines.append(
            f"| {s.time} | {s.total_pressure:.1f} | {s.active_differences} | {s.active_channels} "
            f"| {s.pressure_level} | {s.nearest_stable_label} |"
        )
    lines.append("")

    # 十、结构判断
    lines.append("## 十、结构判断")
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
    from ..core.channel import ChannelStatus
    congested = [c for c in world.channels.values() if c.status == ChannelStatus.CONGESTED]
    if congested:
        lines.append(f"- **通道瓶颈**: {', '.join(c.id for c in congested)}")

    # 主体状态
    from ..core.entity import EntityStatus
    stressed_entities = [e for e in world.entities.values() if e.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED, EntityStatus.FORCED_OUT)]
    if stressed_entities:
        lines.append(f"- **承压主体**: {', '.join(e.id + '(' + e.status.value + ')' for e in stressed_entities)}")

    # 稳态判断
    if world.states:
        final_stable = world.states[-1].nearest_stable_label
        lines.append(f"- **最近稳态**: {final_stable}")

    # 变形链统计
    if transform_events:
        lines.append(f"- **变形链事件**: {len(transform_events)} 次变形")

    # 反馈统计
    if feedback_diffs:
        resolved_fb = sum(1 for d in feedback_diffs if d.status.value == "resolved")
        lines.append(f"- **反馈差异**: {len(feedback_diffs)} 个（已解决 {resolved_fb}）")

    lines.append("")

    return "\n".join(lines)
