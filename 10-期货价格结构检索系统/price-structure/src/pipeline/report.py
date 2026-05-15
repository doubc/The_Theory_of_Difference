"""
Pipeline report — 日更报告渲染

P1 整改：将 daily_pipeline.py 中的报告生成逻辑独立为模块。
只负责从 PipelineContext 渲染 Markdown，不负责 I/O。
"""

from __future__ import annotations

from src.pipeline.context import PipelineContext
from src.pipeline.config import PipelineConfig


def render_daily_report(ctx: PipelineContext, cfg: PipelineConfig) -> str:
    """
    从流水线上下文渲染日更报告

    Args:
        ctx: 已完成所有 step 的流水线上下文
        cfg: 流水线配置

    Returns:
        Markdown 格式的报告字符串
    """
    lines: list[str] = []

    # ── 头部 ──
    lines.append(f"# 日更报告 — {ctx.run_date}\n")
    lines.append(f"**品种**: {ctx.symbol}\n")

    if ctx.bar_count > 0:
        lines.append(f"**数据**: {ctx.bar_count} bars ({ctx.bar_range})\n")
    else:
        lines.append("**数据**: 未加载\n")

    lines.append(f"**编译**: {len(ctx.structures)} 结构, {len(ctx.zones)} 区, {len(ctx.bundles)} 丛\n")
    lines.append(f"**规则匹配**: {len(ctx.matches)} / {len(ctx.structures)}\n")

    if ctx.stratification_summary:
        lines.append(f"**质量分层**: {ctx.stratification_summary}\n")

    if ctx.graph_result:
        n_nodes = ctx.graph_result.get("structures_ingested", 0)
        n_edges = ctx.graph_result.get("edges_ingested", 0)
        lines.append(f"**图谱**: {n_nodes} 节点, {n_edges} 边\n")

    if ctx.lifecycle_records:
        lines.append(f"**生命周期**: 记录 {len(ctx.lifecycle_records)} 个结构快照\n")

    lines.append("---\n")

    # ── 检索结果 ──
    try:
        from src.quality import assess_quality
        has_quality = True
    except ImportError:
        has_quality = False

    for i, (m, ret) in enumerate(ctx.retrieval_results):
        # 质量评估
        qa_str = ""
        if has_quality:
            try:
                qa = assess_quality(m.structure)
                qa_str = f" [{qa.tier.value}层 {qa.score:.0%}]"
            except Exception:
                pass

        lines.append(f"## 候选 {i+1}: {m.rule.name}{qa_str}\n")
        lines.append(f"- Zone: {m.structure.zone.price_center:.0f} (±{m.structure.zone.bandwidth:.0f})")
        lines.append(f"- Cycles: {m.structure.cycle_count}")
        lines.append(f"- speed_r: {m.structure.avg_speed_ratio:.2f}, time_r: {m.structure.avg_time_ratio:.2f}")
        lines.append(f"- typicality: {m.typicality:.2f}")

        if has_quality:
            try:
                qa = assess_quality(m.structure)
                if qa.flags:
                    lines.append(f"- 质量标记: {' · '.join(qa.flags[:3])}")
            except Exception:
                pass

        lines.append("")

        if ret.neighbors:
            p = ret.posterior
            lines.append(f"**后验 (n={p.sample_size})**:")
            lines.append(f"- ret_5d: {p.mean_ret_5d:+.2%}")
            lines.append(f"- ret_10d: {p.mean_ret_10d:+.2%}")
            lines.append(f"- ret_20d: {p.mean_ret_20d:+.2%}")
            lines.append(f"- P(正): {p.prob_positive_10d:.0%}")
            lines.append(f"- max_dd: {p.mean_max_dd_20d:+.2%}")
            lines.append(f"- max_rise: {p.mean_max_rise_20d:+.2%}\n")
        else:
            lines.append("无足够相似样本\n")

    # ── 错误汇总 ──
    if ctx.errors:
        lines.append("---\n")
        lines.append("## 运行错误\n")
        for err in ctx.errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)
