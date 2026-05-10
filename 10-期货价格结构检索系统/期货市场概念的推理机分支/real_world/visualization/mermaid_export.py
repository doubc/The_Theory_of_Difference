""""Mermaid 流程图导出。

每实验输出 .mmd 文件，展示差异转移路径。
"""

from typing import List

from ..core.world import World


def export_mermaid(world: World) -> str:
    """将差异转移路径导出为 Mermaid 流程图。"""
    lines = ["graph TD"]

    # 差异源节点
    for diff in world.differences.values():
        lines.append(f"    {diff.id}[{diff.type}: {diff.pressure:.0f}]")

    # 通道边
    for ch in world.channels.values():
        label = f"{ch.from_type}→{ch.to_type} (cost={ch.effective_cost():.0f})"
        lines.append(f"    {ch.id} -->|{label}| output_{ch.id}")

    # 转移轨迹
    transfer_events = [e for e in world.trace.events if e.event_type == "transfer"]
    if transfer_events:
        lines.append("    subgraph transfers[转移路径]")
        for e in transfer_events[:10]:
            lines.append(f"        {e.difference_id} -->|{e.amount:.0f}| {e.channel_id}")
        lines.append("    end")

    return "\n".join(lines)