"""
价格结构研究工作台 v4.0 — 仪表盘首页

一屏展示：
  1. 顶部指标条（市场温度、活跃结构数、今日信号）
  2. 品种热力图（按质量/活跃度着色）
  3. 今日精选（Top 3 值得关注的结构）
  4. 快速入口卡片
"""

from __future__ import annotations
import streamlit as st
from datetime import datetime
from src.workbench.shared import motion_badge, movement_badge, struct_status, struct_scenario


def _metric_card(label: str, value: str, delta: str = "", color: str = "#4a90d9"):
    """指标卡片"""
    delta_html = f'<span style="font-size:0.8em;color:#6c757d">{delta}</span>' if delta else ""
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
                border-radius:12px;padding:16px 20px;border-left:4px solid {color};
                margin:4px 0">
        <div style="font-size:0.85em;color:#8892b0;margin-bottom:4px">{label}</div>
        <div style="font-size:1.8em;font-weight:700;color:#ccd6f6">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def _quick_action(label: str, icon: str, desc: str, key: str):
    """快速入口卡片"""
    st.markdown(f"""
    <div style="background:#f8f9fa;border-radius:10px;padding:16px;
                border:1px solid #e9ecef;cursor:pointer;transition:all 0.2s;
                height:140px;display:flex;flex-direction:column;justify-content:center">
        <div style="font-size:1.8em;margin-bottom:8px">{icon}</div>
        <div style="font-weight:700;color:#0d1b2a;font-size:1em;margin-bottom:4px">{label}</div>
        <div style="font-size:0.82em;color:#6c757d;line-height:1.4">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


def _structure_card_mini(sym: str, name: str, s, bars, rank: int):
    """精选结构迷你卡片"""
    m = s.motion
    zone = s.zone
    phase = m.phase_tendency if m else "unknown"
    flux = m.conservation_flux if m else 0
    mt = m.movement_type.value if m else "unknown" if hasattr(m, 'movement_type') else "unknown"

    mt_cn = {"trend_up": "📈 上涨", "trend_down": "📉 下跌",
             "oscillation": "🔄 震荡", "reversal": "🔀 反转"}.get(mt, mt)

    flux_arrow = "↑" if flux > 0 else "↓" if flux < 0 else "→"
    flux_color = "#ef5350" if flux > 0 else "#26a69a" if flux < 0 else "#ffc107"

    last_price = bars[-1].close if bars else 0
    zc = zone.price_center
    dist_pct = ((last_price - zc) / zc * 100) if zc else 0

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#f8f9fa 0%,#e9ecef 100%);
                border-radius:12px;padding:16px 20px;margin:8px 0;
                border-left:5px solid {'#ef5350' if 'up' in mt else '#26a69a' if 'down' in mt else '#ffc107'};
                box-shadow:0 2px 8px rgba(0,0,0,0.06)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div>
                <span style="font-size:1.1em;font-weight:700;color:#0d1b2a">#{rank}</span>
                <span style="font-size:1.05em;font-weight:600;color:#212529;margin-left:8px">
                    {sym} · {name}
                </span>
            </div>
            <span style="font-size:0.9em;font-weight:600;color:{flux_color}">
                {mt_cn} {flux_arrow}
            </span>
        </div>
        <div style="display:flex;gap:20px;font-size:0.88em;color:#495057">
            <div>Zone: <b>{zc:.0f}</b> ± {zone.half_width:.0f}</div>
            <div>价格偏离: <b style="color:{'#ef5350' if dist_pct > 0 else '#26a69a'}">{dist_pct:+.1f}%</b></div>
            <div>试探: <b>{s.cycle_count}</b> 次</div>
            <div>阶段: <b>{phase}</b></div>
        </div>
        <div style="font-size:0.82em;color:#6c757d;margin-top:6px">
            {struct_scenario(s)}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _heatmap_cell(sym: str, name: str, score: float, phase: str):
    """热力图单元格"""
    if score >= 80:
        bg, fg = "#1b5e20", "#fff"
    elif score >= 60:
        bg, fg = "#0d47a1", "#fff"
    elif score >= 40:
        bg, fg = "#e65100", "#fff"
    else:
        bg, fg = "#455a64", "#fff"

    phase_short = phase.replace("→", "").replace("confirmation", "确认").replace("breakout", "突破")[:4]

    st.markdown(f"""
    <div style="background:{bg};border-radius:8px;padding:10px 8px;text-align:center;
                cursor:pointer;transition:transform 0.15s;min-height:70px"
         onmouseover="this.style.transform='scale(1.05)'"
         onmouseout="this.style.transform='scale(1)'">
        <div style="font-weight:700;color:{fg};font-size:0.9em">{sym}</div>
        <div style="font-size:0.75em;color:{fg};opacity:0.8">{name[:4]}</div>
        <div style="font-size:1.1em;font-weight:700;color:{fg}">{score:.0f}</div>
        <div style="font-size:0.7em;color:{fg};opacity:0.7">{phase_short}</div>
    </div>
    """, unsafe_allow_html=True)


def render_dashboard(ctx: dict):
    """渲染仪表盘首页"""
    ALL_SYMBOLS = ctx["ALL_SYMBOLS"]
    META = ctx["META"]
    MYSQL_SYMBOLS = ctx["MYSQL_SYMBOLS"]

    # ── 顶部欢迎 ──
    st.markdown("""
    <div style="text-align:center;padding:20px 0 10px 0">
        <h1 style="font-size:2em;margin-bottom:4px;color:#ccd6f6">
            🔬 价格结构研究工作台
        </h1>
        <p style="color:#8892b0;font-size:1.05em">
            从期货价格序列中提取结构不变量，辅助交易决策
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── 快速分析入口 ──
    st.markdown("#### ⚡ 快速分析")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("📡 全市场扫描", use_container_width=True, type="primary"):
            st.session_state["active_tab"] = "scan"
            st.rerun()
    with col2:
        if st.button("📋 每日简报", use_container_width=True):
            st.session_state["active_tab"] = "briefing"
            st.rerun()
    with col3:
        if st.button("🔍 历史对照", use_container_width=True):
            st.session_state["active_tab"] = "history"
            st.rerun()
    with col4:
        if st.button("📊 跨品种对比", use_container_width=True):
            st.session_state["active_tab"] = "compare"
            st.rerun()
    with col5:
        if st.button("📝 复盘日志", use_container_width=True):
            st.session_state["active_tab"] = "journal"
            st.rerun()

    st.markdown("---")

    # ── 指标条 ──
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _metric_card("品种总数", str(len(ALL_SYMBOLS)),
                     f"MySQL: {len(MYSQL_SYMBOLS)}", "#4a90d9")
    with col2:
        _metric_card("数据源", "🗄️ MySQL" if MYSQL_SYMBOLS else "📄 CSV",
                     f"{len(ALL_SYMBOLS)} 个品种可用", "#26a69a")
    with col3:
        _metric_card("系统版本", "v4.0",
                     "结构 × 运动", "#ff9800")
    with col4:
        _metric_card("更新时间", datetime.now().strftime("%H:%M"),
                     datetime.now().strftime("%Y-%m-%d"), "#9c27b0")

    st.markdown("---")

    # ── 品种速览 ──
    st.markdown("#### 📈 品种速览")

    exchange_groups = {}
    for sym in ALL_SYMBOLS:
        info = META.get(sym, META.get(sym.upper(), {}))
        ex = info.get("exchange", "其他") if isinstance(info, dict) else "其他"
        exchange_groups.setdefault(ex, []).append(sym)

    for ex in ["SHFE", "DCE", "CZCE", "GFEX", "CFETS", "其他"]:
        syms = exchange_groups.get(ex, [])
        if not syms:
            continue

        ex_names = {"SHFE": "上海期货", "DCE": "大连商品", "CZCE": "郑州商品",
                    "GFEX": "广州期货", "CFETS": "外汇交易中心", "其他": "其他"}

        st.markdown(f"**{ex_names.get(ex, ex)}** ({len(syms)} 个)")
        cols = st.columns(min(len(syms), 8))
        for i, sym in enumerate(syms[:8]):
            info = META.get(sym, {})
            name = info.get("name", sym) if isinstance(info, dict) else sym
            with cols[i % len(cols)]:
                if st.button(f"{sym}\n{name}", key=f"dash_{sym}",
                           use_container_width=True):
                    st.session_state["selected_symbol"] = sym
                    st.session_state["active_tab"] = "scan"
                    st.rerun()

    st.markdown("---")

    # ── 使用指南 ──
    st.markdown("#### 📖 使用指南")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **📡 今天值得关注什么**
        - 全市场自动扫描
        - 今日精选 Top 3
        - 结构质量评分
        """)
    with col2:
        st.markdown("""
        **🔍 历史对照**
        - 拉取历史相似案例
        - 四层相似度匹配
        - 不变量对比分析
        """)
    with col3:
        st.markdown("""
        **📊 跨品种对比**
        - 多品种结构对比
        - 板块联动分析
        - 跨品种共振检测
        """)
