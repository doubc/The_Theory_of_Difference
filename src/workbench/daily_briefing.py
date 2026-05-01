"""
每日研究简报 — 一键生成今日市场结构摘要

功能：
  1. 自动扫描全市场
  2. 生成结构化简报（Markdown 格式）
  3. 高亮今日 Top 3 机会
  4. 板块热度总结
  5. 可导出为 Markdown 文件
"""

from __future__ import annotations
import streamlit as st
from datetime import datetime
from pathlib import Path
import json


def _generate_briefing(scan_data: list, symbol_meta: dict) -> str:
    """从扫描数据生成 Markdown 简报"""
    today = datetime.now().strftime("%Y-%m-%d")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()]

    lines = []
    lines.append(f"# 📋 价格结构每日简报")
    lines.append(f"**日期**: {today} {weekday}")
    lines.append(f"**扫描品种**: {len(scan_data)} 个活跃合约")
    lines.append("")

    if not scan_data:
        lines.append("⚠️ 今日无活跃结构数据，请先执行全市场扫描。")
        return "\n".join(lines)

    # ── 市场概览 ──
    n_up = sum(1 for r in scan_data if r.get("direction") == "up")
    n_down = sum(1 for r in scan_data if r.get("direction") == "down")
    n_breakout = sum(1 for r in scan_data if "breakout" in (r.get("motion") or ""))
    n_confirm = sum(1 for r in scan_data if "confirmation" in (r.get("motion") or ""))
    n_blind = sum(1 for r in scan_data if r.get("is_blind"))

    lines.append("## 📊 市场概览")
    lines.append(f"- 📈 偏多: **{n_up}** 个")
    lines.append(f"- 📉 偏空: **{n_down}** 个")
    lines.append(f"- 🔴 破缺中: **{n_breakout}** 个")
    lines.append(f"- 🟢 确认中: **{n_confirm}** 个")
    if n_blind:
        lines.append(f"- ⚠️ 高压缩(盲区): **{n_blind}** 个")
    lines.append("")

    # ── Top 3 精选 ──
    lines.append("## 🎯 今日精选 Top 3")
    top3 = sorted(scan_data, key=lambda x: x.get("priority_score", 0), reverse=True)[:3]
    for i, r in enumerate(top3):
        sym = r.get("symbol", "?")
        name = r.get("symbol_name", "")
        ps = r.get("priority_score", 0)
        phase = r.get("motion_label", "—")
        direction = "📈 偏多" if r.get("direction") == "up" else "📉 偏空" if r.get("direction") == "down" else "➡️ 不明"
        flux = r.get("flux", 0)
        zone_center = r.get("latest_zone_center", 0)
        zone_bw = r.get("latest_zone_bw", 0)
        price = r.get("last_price", 0)
        score = r.get("score", 0)
        tier = r.get("tier", "?")
        sector = r.get("sector", "未知")

        lines.append(f"### #{i+1} {sym} · {name}")
        lines.append(f"- **板块**: {sector}")
        lines.append(f"- **方向**: {direction} · **阶段**: {phase}")
        lines.append(f"- **Zone**: {zone_center:.0f} (±{zone_bw:.0f})")
        lines.append(f"- **现价**: {price:.0f} · **优先级**: P{ps:.0f}")
        lines.append(f"- **质量**: {tier}层 ({score:.0f}分) · **通量**: {flux:+.3f}")

        # 信号信息
        sig = r.get("signal_info")
        if sig:
            kind_labels = {
                "breakout_confirm": "✅ 突破确认",
                "fake_breakout": "⚠️ 假突破",
                "pullback_confirm": "🔄 回踩确认",
                "structure_expired": "💀 结构失效",
                "blind_breakout": "👁 盲区突破",
            }
            sig_label = kind_labels.get(sig.get("kind", ""), sig.get("kind", ""))
            dir_label = {"long": "📈 多", "short": "📉 空", "neutral": "➡️ 中性"}.get(
                sig.get("direction", ""), sig.get("direction", ""))
            conf = sig.get("confidence", 0) * 100
            lines.append(f"- **信号**: {sig_label} · {dir_label} · 置信度 {conf:.0f}%")
            if sig.get("entry_price", 0) > 0:
                lines.append(f"- **入场**: {sig['entry_price']:.1f} · **止损**: {sig.get('stop_loss_price', 0):.1f} · **目标**: {sig.get('take_profit_price', 0):.1f}")

        lines.append("")

    # ── 板块热度 ──
    lines.append("## 🗺️ 板块热度")
    sector_groups = {}
    for r in scan_data:
        sec = r.get("sector", "未知")
        sector_groups.setdefault(sec, []).append(r)

    for sec, items in sorted(sector_groups.items(), key=lambda x: -len(x[1])):
        s_up = sum(1 for r in items if r.get("direction") == "up")
        s_down = sum(1 for r in items if r.get("direction") == "down")
        total = len(items)
        top = max(items, key=lambda x: x.get("priority_score", 0))

        if s_up > s_down and s_up >= total * 0.5:
            sentiment = "📈 偏多"
        elif s_down > s_up and s_down >= total * 0.5:
            sentiment = "📉 偏空"
        else:
            sentiment = "⚖️ 分歧"

        lines.append(f"- **{sec}**: {sentiment} · {total}个 · 🏆 {top['symbol']} P{top.get('priority_score', 0):.0f}")

    lines.append("")

    # ── 阶段分布 ──
    lines.append("## 📈 运动阶段分布")
    stage_groups = {}
    for r in scan_data:
        stage = r.get("motion_label", "未分类")
        stage_groups.setdefault(stage, []).append(r)
    for stage, items in sorted(stage_groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"- {stage}: **{len(items)}** 个")

    lines.append("")
    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%H:%M:%S')} · 价格结构形式系统 v4.0*")

    return "\n".join(lines)


def render_daily_briefing(ctx: dict):
    """渲染每日简报页面"""
    st.markdown("#### 📋 每日研究简报")
    st.caption("一键生成今日市场结构摘要，可导出为 Markdown 文件")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        generate = st.button("📋 生成今日简报", type="primary", use_container_width=True)
    with col2:
        auto_scan = st.checkbox("同时执行扫描", value=True)
    with col3:
        st.caption("需要先有扫描数据")

    if generate:
        # 检查是否有扫描数据
        scan_data = st.session_state.get("scan_results_full", [])

        if not scan_data and auto_scan:
            # 自动执行扫描
            from src.workbench.tab_scan import _build_dashboard_data
            from src.compiler.pipeline import compile_full
            from src.workbench.data_layer import load_bars

            ALL_SYMBOLS = ctx["ALL_SYMBOLS"]
            with st.spinner("🔍 正在扫描全市场..."):
                prog = st.progress(0, text="准备扫描...")
                scan_data = _build_dashboard_data(ALL_SYMBOLS, load_bars, compile_full, "标准")
                prog.progress(1.0, text=f"✅ 扫描完成")
                st.session_state["scan_results_full"] = scan_data

        if scan_data:
            briefing = _generate_briefing(scan_data, ctx["META"])
            st.session_state["daily_briefing"] = briefing

            # 显示简报
            st.markdown("---")
            st.markdown(briefing)

            # 导出按钮
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📥 下载 Markdown 简报",
                    data=briefing,
                    file_name=f"briefing_{datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col2:
                # 保存到本地
                briefing_dir = Path(__file__).parent.parent / "data" / "briefings"
                briefing_dir.mkdir(parents=True, exist_ok=True)
                briefing_file = briefing_dir / f"briefing_{datetime.now().strftime('%Y%m%d')}.md"
                briefing_file.write_text(briefing, encoding="utf-8")
                st.success(f"✅ 已保存到 {briefing_file.name}")
        else:
            st.warning("⚠️ 无扫描数据。请先执行「📡 今日扫描」Tab 中的全市场扫描。")

    # 显示历史简报
    st.markdown("---")
    st.markdown("#### 📂 历史简报")
    briefing_dir = Path(__file__).parent.parent / "data" / "briefings"
    if briefing_dir.exists():
        briefing_files = sorted(briefing_dir.glob("briefing_*.md"), reverse=True)
        if briefing_files:
            for f in briefing_files[:10]:
                date_str = f.stem.replace("briefing_", "")
                with st.expander(f"📄 {date_str}"):
                    content = f.read_text(encoding="utf-8")
                    st.markdown(content)
        else:
            st.caption("暂无历史简报")
    else:
        st.caption("暂无历史简报")
