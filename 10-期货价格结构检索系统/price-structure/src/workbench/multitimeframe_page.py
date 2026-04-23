"""
Tab 7: 多时间维度对比 — 5分钟/1小时/日线 跨尺度结构验证

插入到 app.py 的 tab_names 列表末尾，作为第 7 个 Tab。

集成方式：
1. 在 app.py 的 tab_names 列表中添加 "⏱️ 多时间维度对比"
2. 在 tabs = st.tabs(tab_names) 后添加 with tabs[6]: 包裹此文件内容
3. 或者直接将此文件内容粘贴到 app.py 末尾

本文件也可独立运行：streamlit run src/workbench/multitimeframe_page.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time as _time

from src.data.loader import Bar, MySQLLoader
from src.data.local_store import LocalStore, LocalStoreConfig
from src.data.sina_fetcher import fetch_bars as sina_fetch_bars, detect_source
from src.compiler.pipeline import compile_full, CompilerConfig
from src.multitimeframe.comparator import (
    MultiTimeframeComparator, resample_bars,
    cross_timeframe_consistency, compute_zone_overlap,
)


# ─── 页面标题 ──────────────────────────────────────────────

st.markdown("#### ⏱️ 多时间维度对比")
st.caption("同一品种在不同时间尺度上的结构交叉验证 — 5分钟 / 1小时 / 日线")

st.markdown("""
> **核心思想**：如果一个品种在多个时间维度上都编译出相似的结构，
> 那这个信号的可靠性远高于单时间维度的判断。
> 反之，如果不同尺度的结构方向矛盾，可能是噪声或尺度错配。
""")


# ─── 数据源选择 ────────────────────────────────────────────

col_sym, col_range, col_mode = st.columns([2, 2, 1])

with col_sym:
    # 品种选择
    preset_codes = [
        "cu0", "al0", "zn0", "rb0", "i0", "j0", "m0", "y0",
        "ma0", "sr0", "cf0", "ta0", "au0", "ag0", "sc0",
    ]
    mode = st.radio("输入方式", ["📋 预置", "✏️ 自由输入"], horizontal=True, key="mtf_mode")
    if mode == "📋 预置":
        mtf_symbol = st.selectbox("品种", preset_codes, index=0, key="mtf_preset").lower()
    else:
        mtf_symbol = st.text_input("品种代码", value="cu0", key="mtf_free").strip().lower()

with col_range:
    col_s, col_e = st.columns(2)
    with col_s:
        mtf_start = st.date_input("开始日期", value=datetime.now() - timedelta(days=180), key="mtf_start")
    with col_e:
        mtf_end = st.date_input("结束日期", value=datetime.now(), key="mtf_end")

with col_mode:
    st.markdown("<br>", unsafe_allow_html=True)
    mtf_run = st.button("🚀 开始分析", type="primary", use_container_width=True, key="mtf_run")


# ─── 灵敏度设置 ────────────────────────────────────────────

with st.expander("⚙️ 编译参数", expanded=False):
    col_1d, col_1h, col_5m = st.columns(3)

    with col_1d:
        st.markdown("**日线参数**")
        d1_min_amp = st.slider("最小幅度(1d)", 0.01, 0.10, 0.03, 0.005, key="d1_amp")
        d1_min_dur = st.slider("最小窗口(1d)", 1, 10, 3, key="d1_dur")

    with col_1h:
        st.markdown("**1小时参数**")
        h1_min_amp = st.slider("最小幅度(1h)", 0.005, 0.05, 0.01, 0.005, key="h1_amp")
        h1_min_dur = st.slider("最小窗口(1h)", 1, 10, 2, key="h1_dur")

    with col_5m:
        st.markdown("**5分钟参数**")
        m5_min_amp = st.slider("最小幅度(5m)", 0.001, 0.02, 0.005, 0.001, key="m5_amp")
        m5_min_dur = st.slider("最小窗口(5m)", 1, 10, 2, key="m5_dur")


# ═══════════════════════════════════════════════════════════
# 核心分析逻辑
# ═══════════════════════════════════════════════════════════

def _load_and_compile(symbol: str, freq: str, start: str, end: str, config: CompilerConfig):
    """加载数据并编译"""
    bars = []

    # 优先尝试 MySQL
    try:
        loader = MySQLLoader()
        bars = loader.get(symbol=symbol.upper(), start=start, end=end, freq=freq)
    except Exception:
        pass

    # 降级到新浪
    if not bars:
        try:
            bars = sina_fetch_bars(symbol, freq=freq, timeout=15)
            if bars and start:
                from datetime import datetime as dt
                s = dt.strptime(start, "%Y-%m-%d")
                e = dt.strptime(end, "%Y-%m-%d") if end else dt.now()
                bars = [b for b in bars if s <= b.timestamp <= e]
        except Exception:
            pass

    if not bars:
        return None, []

    result = compile_full(bars, config, symbol=symbol.upper())
    return result, bars


def _make_candlestick(bars: list[Bar], title: str = "") -> go.Figure:
    """生成 K 线图"""
    df = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "vol": b.volume,
    } for b in bars])

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.8, 0.2])
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
        name=title,
    ), row=1, col=1)
    fig.add_trace(go.Bar(x=df["date"], y=df["vol"], marker_color="#90a4ae", name="Volume"),
                  row=2, col=1)
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=30, b=0),
        xaxis_rangeslider_visible=False,
        showlegend=False,
        template="plotly_white",
    )
    return fig


def _render_structure_card(s, freq_label: str, last_price: float):
    """渲染结构卡片"""
    motion = s.motion
    flux = f"{motion.conservation_flux:+.2f}" if motion else "—"
    tendency = motion.phase_tendency if motion else "unknown"
    proj_warn = " · ⚠️ 高压缩" if (s.projection and s.projection.is_blind) else ""

    # 运动态颜色
    if "breakdown" in tendency:
        badge_cls = "badge-breakdown"
    elif "confirmation" in tendency:
        badge_cls = "badge-confirmation"
    elif tendency in ("stable", "forming"):
        badge_cls = "badge-stable"
    else:
        badge_cls = "badge-forming"

    # 价格 vs Zone 位置
    zone = s.zone
    if last_price > zone.upper:
        pos = f"📈 价格在 Zone 上方 (+{(last_price - zone.price_center) / zone.bandwidth:.1f} bw)"
    elif last_price < zone.lower:
        pos = f"📉 价格在 Zone 下方 (-{(zone.price_center - last_price) / zone.bandwidth:.1f} bw)"
    else:
        pos = "📊 价格在 Zone 内部"

    card_cls = "danger" if "breakdown" in tendency else "ok" if "confirmation" in tendency else ""

    st.markdown(f"""
    <div class="structure-card {card_cls}">
        <span class="zone-label">Zone {zone.price_center:.0f}</span>
        <span class="meta-text">(±{zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
        · <span class="motion-badge {badge_cls}">{freq_label} · {tendency}</span>
        · <span class="meta-text">通量 {flux}</span>{proj_warn}
        <div class="meta-text">{pos}</div>
        <div class="narrative-text">{s.narrative_context or ''}</div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 执行分析
# ═══════════════════════════════════════════════════════════

if mtf_run and mtf_symbol:
    start_str = mtf_start.strftime("%Y-%m-%d")
    end_str = mtf_end.strftime("%Y-%m-%d")

    # ── 配置 ──
    config_1d = CompilerConfig(
        min_amplitude=d1_min_amp, min_duration=d1_min_dur,
        adaptive_pivots=True, fractal_threshold=0.34,
    )
    config_1h = CompilerConfig(
        min_amplitude=h1_min_amp, min_duration=h1_min_dur,
        adaptive_pivots=True, fractal_threshold=0.34,
    )
    config_5m = CompilerConfig(
        min_amplitude=m5_min_amp, min_duration=m5_min_dur,
        adaptive_pivots=True, fractal_threshold=0.34,
    )

    # ── 日线编译 ──
    with st.spinner(f"📡 编译 {mtf_symbol} 日线结构..."):
        result_1d, bars_1d = _load_and_compile(mtf_symbol, "1d", start_str, end_str, config_1d)

    # ── 5分钟线编译 ──
    with st.spinner(f"📡 编译 {mtf_symbol} 5分钟线结构..."):
        result_5m, bars_5m = _load_and_compile(mtf_symbol, "5m", start_str, end_str, config_5m)

    # ── 1小时线（从5分钟重采样）──
    result_1h, bars_1h = None, []
    if bars_5m:
        with st.spinner(f"🔄 重采样为1小时线并编译..."):
            bars_1h = resample_bars(bars_5m, "1h")
            if bars_1h:
                result_1h = compile_full(bars_1h, config_1h, symbol=mtf_symbol.upper())

    # ═══════════════════════════════════════════════════════
    # 结果展示
    # ═══════════════════════════════════════════════════════

    st.markdown("---")

    # ── 概要指标 ──
    metric_cols = st.columns(7)
    metric_cols[0].metric("品种", mtf_symbol.upper())
    metric_cols[1].metric("日线结构", len(result_1d.structures) if result_1d else 0)
    metric_cols[2].metric("1H 结构", len(result_1h.structures) if result_1h else 0)
    metric_cols[3].metric("5M 结构", len(result_5m.structures) if result_5m else 0)
    metric_cols[4].metric("日线 bars", len(bars_1d))
    metric_cols[5].metric("5M bars", len(bars_5m))
    metric_cols[6].metric("1H bars", len(bars_1h))

    # ── 数据可用性 ──
    has_1d = result_1d is not None and len(result_1d.structures) > 0
    has_1h = result_1h is not None and len(result_1h.structures) > 0
    has_5m = result_5m is not None and len(result_5m.structures) > 0

    if not has_1d and not has_5m:
        st.error("❌ 日线和5分钟线都未编译出结构，尝试降低灵敏度")
        st.stop()

    # ═══════════════════════════════════════════════════════
    # Section 1: 各维度结构概览
    # ═══════════════════════════════════════════════════════

    st.markdown("##### 📊 各时间维度结构概览")

    last_price_1d = bars_1d[-1].close if bars_1d else 0
    last_price_5m = bars_5m[-1].close if bars_5m else last_price_1d

    tab_1d, tab_1h, tab_5m = st.tabs(["📅 日线", "🕐 1小时", "⏱️ 5分钟"])

    with tab_1d:
        if has_1d:
            for s in result_1d.ranked_structures[:5]:
                _render_structure_card(s, "日线", last_price_1d)
        else:
            st.info("日线无结构")

    with tab_1h:
        if has_1h:
            for s in result_1h.ranked_structures[:5]:
                _render_structure_card(s, "1H", last_price_5m)
        else:
            st.info("1小时线无结构（需要5分钟数据）")

    with tab_5m:
        if has_5m:
            for s in result_5m.ranked_structures[:5]:
                _render_structure_card(s, "5M", last_price_5m)
        else:
            st.info("5分钟线无结构")

    # ═══════════════════════════════════════════════════════
    # Section 2: 跨维度一致性分析
    # ═══════════════════════════════════════════════════════

    st.markdown("---")
    st.markdown("##### 🔗 跨维度一致性分析")

    # 计算所有跨维度匹配
    all_matches = []
    freq_pairs = []
    if has_1d and has_5m:
        freq_pairs.append(("1d", "5m", result_1d, result_5m))
    if has_1d and has_1h:
        freq_pairs.append(("1d", "1h", result_1d, result_1h))
    if has_1h and has_5m:
        freq_pairs.append(("1h", "5m", result_1h, result_5m))

    for freq_a, freq_b, res_a, res_b in freq_pairs:
        for sa in res_a.structures:
            best_score = -1
            best_match = None
            for sb in res_b.structures:
                match = cross_timeframe_consistency(sa, sb, freq_a, freq_b)
                if match.consistency_score > best_score:
                    best_score = match.consistency_score
                    best_match = match
            if best_match and best_match.consistency_score > 0.2:
                all_matches.append(best_match)

    all_matches.sort(key=lambda m: m.consistency_score, reverse=True)

    if all_matches:
        # 总体一致性
        avg_consistency = sum(m.consistency_score for m in all_matches) / len(all_matches)

        col_score, col_verdict = st.columns([1, 3])
        with col_score:
            st.metric("总体一致性", f"{avg_consistency:.0%}")
        with col_verdict:
            if avg_consistency > 0.7:
                st.success("🟢 **多尺度高度一致** — 信号可靠性高，各时间维度结构方向一致")
            elif avg_consistency > 0.4:
                st.warning("🟡 **多尺度部分一致** — 存在尺度差异，需关注矛盾点")
            else:
                st.error("🔴 **多尺度不一致** — 可能存在噪声信号，结构方向在不同尺度矛盾")

        # 匹配详情表
        match_rows = []
        for m in all_matches[:15]:
            match_rows.append({
                "维度对": f"{m.freq_a} ↔ {m.freq_b}",
                "Zone A": f"{m.structure_a.zone.price_center:.0f}",
                "Zone B": f"{m.structure_b.zone.price_center:.0f}",
                "Zone重叠": f"{m.zone_overlap:.0%}",
                "方向": "✓ 一致" if m.direction_match else "✗ 不一致",
                "速度比差": f"{m.speed_ratio_diff:.2f}",
                "一致性": f"{m.consistency_score:.2f}",
                "判断": "🟢" if m.consistency_score > 0.7 else "🟡" if m.consistency_score > 0.4 else "🔴",
            })

        st.dataframe(pd.DataFrame(match_rows), hide_index=True, use_container_width=True)

        # ── 最佳匹配的结构对比 ──
        if all_matches:
            best = all_matches[0]
            st.markdown(f"**最佳匹配对比** — {best.freq_a} ↔ {best.freq_b} (一致性: {best.consistency_score:.0%})")

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**{best.freq_a} 结构**")
                s_a = best.structure_a
                st.markdown(f"""
                - Zone: {s_a.zone.price_center:.0f} (±{s_a.zone.bandwidth:.0f})
                - Cycle 数: {s_a.cycle_count}
                - 速度比: {s_a.avg_speed_ratio:.2f}
                - 时间比: {s_a.avg_time_ratio:.2f}
                - 运动态: {s_a.motion.phase_tendency if s_a.motion else '—'}
                - 通量: {s_a.motion.conservation_flux:+.2f if s_a.motion else '—'}
                """)
            with col_b:
                st.markdown(f"**{best.freq_b} 结构**")
                s_b = best.structure_b
                st.markdown(f"""
                - Zone: {s_b.zone.price_center:.0f} (±{s_b.zone.bandwidth:.0f})
                - Cycle 数: {s_b.cycle_count}
                - 速度比: {s_b.avg_speed_ratio:.2f}
                - 时间比: {s_b.avg_time_ratio:.2f}
                - 运动态: {s_b.motion.phase_tendency if s_b.motion else '—'}
                - 通量: {s_b.motion.conservation_flux:+.2f if s_b.motion else '—'}
                """)

        # ── 不一致分析 ──
        inconsistent = [m for m in all_matches if not m.is_consistent]
        if inconsistent:
            with st.expander(f"⚠️ 不一致匹配 ({len(inconsistent)} 对)", expanded=False):
                for m in inconsistent[:5]:
                    st.markdown(
                        f"- **{m.freq_a}↔{m.freq_b}**: "
                        f"Zone {m.structure_a.zone.price_center:.0f} vs {m.structure_b.zone.price_center:.0f}, "
                        f"方向{'一致' if m.direction_match else '矛盾'}, "
                        f"一致性 {m.consistency_score:.0%}"
                    )
                    if not m.direction_match:
                        st.caption("  → 方向矛盾：大时间维度看涨但小时间维度看跌（或反之），可能为尺度错配")

    else:
        st.info("未找到跨维度匹配 — 可能原因：① 某维度无结构 ② 结构 Zone 距离过远 ③ 方向完全矛盾")

    # ═══════════════════════════════════════════════════════
    # Section 3: K 线并排对比
    # ═══════════════════════════════════════════════════════

    st.markdown("---")
    st.markdown("##### 📈 K 线并排对比")

    kline_tabs = []
    if has_1d:
        kline_tabs.append("📅 日线 K 线")
    if has_5m:
        kline_tabs.append("⏱️ 5分钟 K 线 (近期)")
    if has_1h:
        kline_tabs.append("🕐 1小时 K 线 (近期)")

    if kline_tabs:
        kt = st.tabs(kline_tabs)
        idx = 0
        if has_1d:
            with kt[idx]:
                fig = _make_candlestick(bars_1d[-120:], f"{mtf_symbol.upper()} 日线")
                for s in result_1d.ranked_structures[:3]:
                    fig.add_hline(y=s.zone.price_center, line_dash="dot",
                                 line_color="#4a90d9", opacity=0.6,
                                 annotation_text=f"Zone {s.zone.price_center:.0f}")
                    fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                                 fillcolor="#4a90d9", opacity=0.08, line_width=0)
                st.plotly_chart(fig, use_container_width=True)
            idx += 1

        if has_5m:
            with kt[idx]:
                fig = _make_candlestick(bars_5m[-500:], f"{mtf_symbol.upper()} 5分钟")
                for s in result_5m.ranked_structures[:3]:
                    fig.add_hline(y=s.zone.price_center, line_dash="dot",
                                 line_color="#ff9800", opacity=0.6,
                                 annotation_text=f"Zone {s.zone.price_center:.0f}")
                    fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                                 fillcolor="#ff9800", opacity=0.08, line_width=0)
                st.plotly_chart(fig, use_container_width=True)
            idx += 1

        if has_1h:
            with kt[idx]:
                fig = _make_candlestick(bars_1h[-200:], f"{mtf_symbol.upper()} 1小时")
                for s in result_1h.ranked_structures[:3]:
                    fig.add_hline(y=s.zone.price_center, line_dash="dot",
                                 line_color="#4caf50", opacity=0.6,
                                 annotation_text=f"Zone {s.zone.price_center:.0f}")
                    fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                                 fillcolor="#4caf50", opacity=0.08, line_width=0)
                st.plotly_chart(fig, use_container_width=True)

    # ═══════════════════════════════════════════════════════
    # Section 4: 不变量雷达图
    # ═══════════════════════════════════════════════════════

    if has_1d and (has_5m or has_1h):
        st.markdown("---")
        st.markdown("##### 🕸️ 不变量雷达图对比")

        # 取各维度最强结构
        s_1d = result_1d.ranked_structures[0]
        s_other = (result_5m or result_1h).ranked_structures[0]
        other_label = "5分钟" if has_5m else "1小时"

        categories = ["Cycle数", "速度比", "时间比", "带宽", "强度"]
        vals_1d = [
            s_1d.cycle_count / 10,
            min(s_1d.avg_speed_ratio / 2, 1),
            min(s_1d.avg_time_ratio / 2, 1),
            s_1d.zone.relative_bandwidth * 10,
            min(s_1d.zone.strength / 10, 1),
        ]
        vals_other = [
            s_other.cycle_count / 10,
            min(s_other.avg_speed_ratio / 2, 1),
            min(s_other.avg_time_ratio / 2, 1),
            s_other.zone.relative_bandwidth * 10,
            min(s_other.zone.strength / 10, 1),
        ]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=vals_1d + [vals_1d[0]], theta=categories + [categories[0]],
            fill="toself", name="日线", line_color="#4a90d9", opacity=0.6,
        ))
        fig.add_trace(go.Scatterpolar(
            r=vals_other + [vals_other[0]], theta=categories + [categories[0]],
            fill="toself", name=other_label, line_color="#ff9800", opacity=0.6,
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            showlegend=True, height=350,
            margin=dict(l=60, r=60, t=30, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ═══════════════════════════════════════════════════════
    # Section 5: 研究建议
    # ═══════════════════════════════════════════════════════

    st.markdown("---")
    st.markdown("##### 💡 研究建议")

    suggestions = []

    if all_matches:
        avg_c = sum(m.consistency_score for m in all_matches) / len(all_matches)

        if avg_c > 0.7:
            suggestions.append("✅ **多尺度高度一致** — 结构信号可靠性高，可重点关注")
            suggestions.append("📋 **下一步**：查看历史对照，寻找类似多尺度一致的历史案例")
        elif avg_c > 0.4:
            suggestions.append("⚠️ **尺度间存在差异** — 检查差异来源")
            suggestions.append("📋 **下一步**：对比不同尺度的 Zone 位置，看是否存在尺度错配")
        else:
            suggestions.append("🔴 **尺度严重不一致** — 可能是噪声行情")
            suggestions.append("📋 **下一步**：等待更多数据，或降低灵敏度重新分析")

        # 方向矛盾
        dir_mismatch = [m for m in all_matches if not m.direction_match]
        if dir_mismatch:
            suggestions.append(f"⚠️ **{len(dir_mismatch)} 对方向矛盾** — 大尺度看涨但小尺度看跌（或反之），通常是回调/反弹信号")

        # Zone 偏移
        zone_far = [m for m in all_matches if m.zone_overlap < 0.1]
        if zone_far:
            suggestions.append(f"📐 **{len(zone_far)} 对 Zone 无重叠** — 不同尺度的支撑/阻力位不同，可能存在多层结构")

    else:
        suggestions.append("ℹ️ **无跨维度匹配** — 数据不足或结构不显著")
        suggestions.append("📋 **下一步**：尝试降低灵敏度，或扩展时间范围")

    for s in suggestions:
        st.markdown(s)

elif mtf_run:
    st.warning("请输入品种代码")


# ─── 独立运行入口 ──────────────────────────────────────────

if __name__ == "__main__":
    pass  # Streamlit 直接运行此文件即可
