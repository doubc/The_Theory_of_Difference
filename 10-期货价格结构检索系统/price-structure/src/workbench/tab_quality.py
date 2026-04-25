"""
Tab 7: 质量与共振 — 质量分层 + 板块共振 + 生命周期 + 日内节奏

从 app.py 提取的独立模块。
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from src.data.sina_fetcher import fetch_bars as sina_fetch_bars, available_contracts
from src.compiler.pipeline import compile_full, CompilerConfig
from src.quality import assess_quality, QualityTier, stratify_structures
from src.resonance import ResonanceDetector
from src.lifecycle import LifecycleTracker
from src.intraday_rhythm import IntradayRhythmAnalyzer, SESSION_LABELS


def render(ctx: dict):
    """渲染 Tab 7: 质量与共振"""
    st.markdown("#### 🔬 v3.0 质量分层与共振检测")
    st.caption("结构质量评估 · 跨品种共振 · 生命周期追踪 · 日内节奏分析")

    # ─── Sub-Tab 布局 ──────────────────────────────────────────────

    sub_tabs = st.tabs([
        "📊 质量分层",
        "🔗 板块共振",
        "📈 生命周期",
        "⏱️ 日内节奏",
    ])

    # ═══════════════════════════════════════════════════════════
    # Sub-Tab 1: 质量分层
    # ═══════════════════════════════════════════════════════════

    with sub_tabs[0]:
        st.markdown("##### 📊 结构质量分层")
        st.caption("5 个维度评分 → A/B/C/D 四层 → 检索和统计按层加权")

        col_sym, col_btn = st.columns([3, 1])
        with col_sym:
            q_symbol = st.text_input("品种代码", value="cu0", key="q_symbol").strip().lower()
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            q_run = st.button("🚀 评估", type="primary", key="q_run")

        if q_run and q_symbol:
            with st.spinner(f"编译 {q_symbol}..."):
                bars = sina_fetch_bars(q_symbol, freq="1d", timeout=15)
                if bars:
                    result = compile_full(bars, CompilerConfig(adaptive_pivots=True), symbol=q_symbol.upper())

                    if result.structures:
                        strat = stratify_structures(result.structures, result.system_states)

                        col_a, col_b, col_c, col_d, col_total = st.columns(5)
                        col_a.metric("A层·高质量", strat.stats.get("A", 0))
                        col_b.metric("B层·中等", strat.stats.get("B", 0))
                        col_c.metric("C层·低质量", strat.stats.get("C", 0))
                        col_d.metric("D层·噪声", strat.stats.get("D", 0))
                        col_total.metric("总计", strat.total)

                        fig_pie = go.Figure(data=[go.Pie(
                            labels=["A层", "B层", "C层", "D层"],
                            values=[strat.stats.get(t, 0) for t in ["A", "B", "C", "D"]],
                            marker_colors=["#1b5e20", "#0d47a1", "#e65100", "#b71c1c"],
                            hole=0.4,
                        )])
                        fig_pie.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0))
                        st.plotly_chart(fig_pie, use_container_width=True)

                        for tier_val in ["A", "B", "C", "D"]:
                            items = strat.tiers.get(tier_val, [])
                            if not items:
                                continue

                            tier = QualityTier(tier_val)
                            with st.expander(f"{tier.label} ({len(items)} 个)", expanded=(tier_val == "A")):
                                for s, qa in items[:8]:
                                    breakdown = qa.dimension_scores
                                    dims = list(breakdown.keys())
                                    vals = list(breakdown.values())

                                    col_card, col_bar = st.columns([1, 2])
                                    with col_card:
                                        flags_str = " · ".join(qa.flags[:2]) if qa.flags else "无标记"
                                        st.markdown(
                                            f"**Zone {s.zone.price_center:.0f}** (±{s.zone.bandwidth:.0f})\n"
                                            f"- {s.cycle_count} cycles · 速度比 {s.avg_speed_ratio:.2f}\n"
                                            f"- 质量分: **{qa.score:.0%}**\n"
                                            f"- {flags_str}"
                                        )
                                    with col_bar:
                                        fig_bar = go.Figure()
                                        fig_bar.add_trace(go.Bar(
                                            y=dims, x=vals,
                                            orientation="h",
                                            marker_color=["#4caf50" if v > 0.6 else "#ff9800" if v > 0.3 else "#f44336" for v in vals],
                                        ))
                                        fig_bar.update_layout(
                                            height=150, margin=dict(l=0, r=0, t=0, b=0),
                                            xaxis=dict(range=[0, 1], showticklabels=False),
                                            yaxis=dict(autorange="reversed"),
                                        )
                                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.warning("未编译出结构")
                else:
                    st.error("数据获取失败")

    # ═══════════════════════════════════════════════════════════
    # Sub-Tab 2: 板块共振
    # ═══════════════════════════════════════════════════════════

    with sub_tabs[1]:
        st.markdown("##### 🔗 跨品种信号共振")
        st.caption("同板块多品种同时出现 A/B 层结构 → 板块级信号")

        st.info(
            "💡 共振检测需要全市场编译数据。点击下方按钮开始全市场扫描。"
        )

        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            r_run = st.button("🚀 全市场共振扫描", type="primary", key="r_run")

        if r_run:
            all_contracts = []
            for group, codes in available_contracts().items():
                all_contracts.extend(codes[:5])

            st.caption(f"扫描 {len(all_contracts)} 个品种...")

            compile_results = {}
            progress = st.progress(0)
            for i, code in enumerate(all_contracts):
                try:
                    bars = sina_fetch_bars(code, freq="1d", timeout=10)
                    if bars and len(bars) > 50:
                        result = compile_full(bars, CompilerConfig(adaptive_pivots=True), symbol=code.upper())
                        compile_results[code.upper()] = (result.structures, result.system_states)
                except Exception:
                    pass
                progress.progress((i + 1) / len(all_contracts))

            if compile_results:
                detector = ResonanceDetector()
                resonance = detector.detect(compile_results)

                st.success(f"扫描完成: {len(compile_results)} 品种, {len(resonance.signals)} 板块有信号")

                for signal in resonance.signals:
                    color = "🔴" if signal.direction == "bullish" else "🟢" if signal.direction == "bearish" else "🟡"
                    with st.expander(
                        f"{color} {signal.sector} · 共振 {signal.resonance_score:.0%} · "
                        f"{len(signal.participating)} 品种",
                        expanded=signal.is_strong,
                    ):
                        col_detail, col_participants = st.columns([1, 2])

                        with col_detail:
                            st.markdown(f"**方向**: {signal.direction_label}")
                            st.metric("共振强度", f"{signal.resonance_score:.0%}")
                            st.metric("质量密度", f"{signal.quality_density:.0%}")
                            st.metric("方向一致性", f"{signal.direction_consistency:.0%}")
                            st.metric("Zone 聚集度", f"{signal.zone_clustering:.0%}")

                        with col_participants:
                            df_part = pd.DataFrame(signal.participating)
                            if not df_part.empty:
                                st.dataframe(
                                    df_part[["symbol", "zone", "tier", "direction", "score"]].rename(columns={
                                        "symbol": "品种", "zone": "Zone", "tier": "层级",
                                        "direction": "方向", "score": "质量分",
                                    }),
                                    hide_index=True, use_container_width=True,
                                )

                if not resonance.signals:
                    st.warning("未检测到板块共振信号")
            else:
                st.error("全市场扫描失败")

    # ═══════════════════════════════════════════════════════════
    # Sub-Tab 3: 生命周期
    # ═══════════════════════════════════════════════════════════

    with sub_tabs[2]:
        st.markdown("##### 📈 结构生命周期追踪")
        st.caption("追踪结构从 formation → confirmation → breakout 的完整轨迹")

        col_sym, col_days = st.columns([2, 1])
        with col_sym:
            l_symbol = st.text_input("品种代码", value="cu0", key="l_symbol").strip().lower()
        with col_days:
            l_days = st.slider("追踪天数", 7, 180, 30, key="l_days")

        tracker = LifecycleTracker()

        if l_symbol:
            lifecycles = tracker.get_active_lifecycles(l_symbol.upper(), max_age_days=l_days)

            if lifecycles:
                st.markdown(f"**活跃生命周期**: {len(lifecycles)} 个")

                for lc in lifecycles[:5]:
                    with st.expander(
                        f"Zone {lc.zone_center:.0f} · 存续 {lc.duration_days} 天 · "
                        f"当前 {lc.current_tier}层 · 趋势 {lc.quality_trend}",
                        expanded=True,
                    ):
                        dates = [r.date for r in lc.records]
                        scores = [r.quality_score for r in lc.records]
                        tiers = [r.quality_tier for r in lc.records]

                        fig_timeline = go.Figure()
                        fig_timeline.add_trace(go.Scatter(
                            x=dates, y=scores, mode="lines+markers",
                            name="质量分", line=dict(color="#4a90d9", width=2),
                            marker=dict(size=8),
                        ))

                        tier_colors = {"A": "#1b5e20", "B": "#0d47a1", "C": "#e65100", "D": "#b71c1c"}
                        for tier_val, color in tier_colors.items():
                            tier_dates = [d for d, t in zip(dates, tiers) if t == tier_val]
                            tier_scores = [s for s, t in zip(scores, tiers) if t == tier_val]
                            if tier_dates:
                                fig_timeline.add_trace(go.Scatter(
                                    x=tier_dates, y=tier_scores, mode="markers",
                                    name=f"{tier_val}层", marker=dict(color=color, size=12, symbol="diamond"),
                                ))

                        fig_timeline.update_layout(
                            height=300, margin=dict(l=0, r=0, t=30, b=0),
                            yaxis=dict(range=[0, 1], title="质量分"),
                            xaxis=dict(title="日期"),
                            title="质量分时间线",
                        )
                        st.plotly_chart(fig_timeline, use_container_width=True)

                        col_info, col_phases = st.columns(2)
                        with col_info:
                            st.markdown(f"**生命周期 ID**: `{lc.lifecycle_id}`")
                            st.markdown(f"**Zone 中心**: {lc.zone_center:.0f}")
                            st.markdown(f"**首次出现**: {lc.first_seen}")
                            st.markdown(f"**最后记录**: {lc.last_seen}")
                            st.markdown(f"**质量趋势**: {lc.quality_trend}")

                        with col_phases:
                            st.markdown("**阶段演进**:")
                            for r in lc.records[-10:]:
                                tier_color = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🔴"}.get(r.quality_tier, "⚪")
                                st.caption(
                                    f"  {r.date}: {tier_color} {r.quality_tier}层 "
                                    f"({r.quality_score:.0%}) · {r.phase_tendency} · "
                                    f"通量 {r.conservation_flux:+.2f}"
                                )

                        transitions = tracker.detect_transitions(l_symbol.upper())
                        if transitions:
                            st.markdown("**阶段转换事件**:")
                            for t in transitions[-5:]:
                                st.caption(
                                    f"  {t.date}: {t.from_phase} → {t.to_phase} · "
                                    f"{t.from_tier}层 → {t.to_tier}层"
                                )
            else:
                st.info(f"无活跃生命周期（最近 {l_days} 天）。需要先进行每日扫描记录。")

                if st.button(f"📝 立即记录 {l_symbol.upper()}", key="l_record"):
                    with st.spinner(f"编译 {l_symbol}..."):
                        bars = sina_fetch_bars(l_symbol, freq="1d", timeout=15)
                        if bars:
                            result = compile_full(bars, CompilerConfig(adaptive_pivots=True), symbol=l_symbol.upper())
                            if result.structures:
                                records = tracker.record(
                                    l_symbol.upper(), result.structures, result.system_states,
                                    date_str=datetime.now().strftime("%Y-%m-%d"),
                                )
                                st.success(f"已记录 {len(records)} 个结构")
                                st.rerun()

    # ═══════════════════════════════════════════════════════════
    # Sub-Tab 4: 日内节奏
    # ═══════════════════════════════════════════════════════════

    with sub_tabs[3]:
        st.markdown("##### ⏱️ 5分钟结构日内节奏")
        st.caption("分析不同时段的结构特征差异：开盘/盘中/收盘")

        col_sym, col_btn = st.columns([3, 1])
        with col_sym:
            i_symbol = st.text_input("品种代码", value="cu0", key="i_symbol").strip().lower()
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            i_run = st.button("🚀 分析", type="primary", key="i_run")

        if i_run and i_symbol:
            with st.spinner(f"拉取 {i_symbol} 5分钟数据..."):
                bars_5m = sina_fetch_bars(i_symbol, freq="5m", timeout=15)

            if bars_5m and len(bars_5m) > 50:
                with st.spinner("编译 5 分钟结构..."):
                    config_5m = CompilerConfig(
                        min_amplitude=0.005, min_duration=2,
                        adaptive_pivots=True, fractal_threshold=0.34,
                    )
                    result_5m = compile_full(bars_5m, config_5m, symbol=i_symbol.upper())

                analyzer = IntradayRhythmAnalyzer()
                report = analyzer.analyze(bars_5m, result_5m.structures, result_5m.system_states)

                st.success(
                    f"分析完成: {len(bars_5m)} bars · {len(result_5m.structures)} 结构"
                )

                comparison = analyzer.compare_sessions(bars_5m, result_5m.structures, result_5m.system_states)

                if comparison["sessions"]:
                    col_chart, col_table = st.columns([2, 1])

                    with col_chart:
                        fig_bar = go.Figure()
                        fig_bar.add_trace(go.Bar(
                            x=comparison["sessions"],
                            y=comparison["structure_counts"],
                            name="结构数",
                            marker_color="#4a90d9",
                        ))
                        fig_bar.update_layout(
                            height=250, margin=dict(l=0, r=0, t=30, b=0),
                            title="各时段结构数量",
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)

                        fig_speed = go.Figure()
                        fig_speed.add_trace(go.Bar(
                            x=comparison["sessions"],
                            y=comparison["speed_ratios"],
                            name="平均速度比",
                            marker_color="#ff9800",
                        ))
                        fig_speed.update_layout(
                            height=250, margin=dict(l=0, r=0, t=30, b=0),
                            title="各时段平均速度比",
                        )
                        st.plotly_chart(fig_speed, use_container_width=True)

                    with col_table:
                        st.markdown("**时段统计**")
                        for ss in report.session_stats:
                            if ss.bar_count == 0:
                                continue
                            st.markdown(f"**{ss.label}**")
                            st.caption(
                                f"- bars: {ss.bar_count}\n"
                                f"- 结构: {ss.structure_count}\n"
                                f"- 速度比: {ss.avg_speed_ratio:.2f}\n"
                                f"- 质量均分: {ss.avg_quality_score:.0%}\n"
                                f"- 方向: {ss.dominant_direction}\n"
                                f"- 振幅: {ss.avg_amplitude:.3f}%"
                            )

                    st.markdown("---")
                    col_best, col_fast, col_quality = st.columns(3)
                    with col_best:
                        if report.best_session:
                            st.metric("📊 结构最多", SESSION_LABELS.get(report.best_session, report.best_session).split("(")[0].strip())
                    with col_fast:
                        if report.fastest_session:
                            st.metric("⚡ 速度最快", SESSION_LABELS.get(report.fastest_session, report.fastest_session).split("(")[0].strip())
                    with col_quality:
                        if report.highest_quality_session:
                            st.metric("🏆 质量最高", SESSION_LABELS.get(report.highest_quality_session, report.highest_quality_session).split("(")[0].strip())

                    with st.expander("完整报告", expanded=False):
                        st.text(report.summary())
                else:
                    st.warning("无有效时段数据")
            else:
                st.error("5分钟数据获取失败或数据不足")
