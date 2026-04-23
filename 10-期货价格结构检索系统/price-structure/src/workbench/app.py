#!/usr/bin/env python3
"""
价格结构研究工作台 v3.0

全面升级：
  1. 数据源自动探测：MySQL 优先，CSV 降级
  2. 全品种选择器：从 MySQL + CSV + symbol_meta 自动发现
  3. 历史对照引擎：主动从 MySQL 拉取全量历史，编译+匹配
  4. 跨品种丛结构对比
  5. 结构片段对比视图（选两段历史 K 线并排）

运行: streamlit run src/workbench/app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime, timedelta
import json
import math

from src.data.loader import Bar, CSVLoader, MySQLLoader
from src.data.symbol_meta import symbol_name, load_symbol_meta
from src.compiler.pipeline import compile_full, CompilerConfig, CompileResult
from src.retrieval.similarity import similarity, INVARIANT_KEYS, INVARIANT_SCALES
from src.retrieval.active_match import (
    active_match, ActiveMatchQuery, ActiveMatchResult,
    HistoricalCase, MatchedStructure,
)
from src.narrative import generate_daily_summary

# ─── 页面配置 ──────────────────────────────────────────────

st.set_page_config(
    page_title="价格结构研究工作台 v3",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 样式 ──────────────────────────────────────────────────

st.markdown("""
<style>
    /* 运动标签 */
    .motion-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .badge-breakdown { background: rgba(239,83,80,0.15); color: #ff6b6b; }
    .badge-confirmation { background: rgba(38,166,154,0.15); color: #4ecdc4; }
    .badge-stable { background: rgba(255,167,38,0.15); color: #ffb74d; }
    .badge-forming { background: rgba(66,165,245,0.15); color: #64b5f6; }

    /* 结构卡片 — 浅色背景 + 深色文字，确保可读性 */
    .structure-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 10px;
        padding: 14px 18px;
        margin: 8px 0;
        border-left: 5px solid #4a90d9;
        color: #212529;
        font-size: 0.92em;
        line-height: 1.6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .structure-card b { color: #1a1a2e; }
    .structure-card .zone-label { font-size: 1.05em; font-weight: 700; color: #0d1b2a; }
    .structure-card .meta-text { color: #495057; font-size: 0.88em; }
    .structure-card .narrative-text { color: #6c757d; font-size: 0.85em; margin-top: 4px; }
    .structure-card.warning { border-left-color: #ff9800; }
    .structure-card.danger  { border-left-color: #ef5350; background: linear-gradient(135deg, #fff5f5 0%, #ffe0e0 100%); }
    .structure-card.ok      { border-left-color: #26a69a; background: linear-gradient(135deg, #f0faf8 0%, #d4efea 100%); }

    /* 案例卡片 */
    .case-card {
        background: #f0f4f8;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
        border-left: 3px solid #4a90d9;
        color: #212529;
    }
    .case-up { border-left-color: #26a69a; }
    .case-down { border-left-color: #ef5350; }

    /* 复盘日志条目 */
    .journal-entry {
        background: #ffffff;
        border-radius: 8px;
        padding: 14px 18px;
        margin: 8px 0;
        border: 1px solid #dee2e6;
        color: #212529;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .journal-entry .entry-header {
        font-weight: 700;
        color: #0d1b2a;
        font-size: 0.95em;
        margin-bottom: 6px;
        border-bottom: 1px solid #e9ecef;
        padding-bottom: 6px;
    }
    .journal-entry .entry-body {
        color: #343a40;
        font-size: 0.9em;
        line-height: 1.7;
        white-space: pre-wrap;
    }
    .journal-tag {
        display: inline-block;
        padding: 1px 8px;
        border-radius: 3px;
        font-size: 0.8em;
        margin-right: 4px;
    }
    .tag-bullish { background: #d4edda; color: #155724; }
    .tag-bearish { background: #f8d7da; color: #721c24; }
    .tag-neutral { background: #fff3cd; color: #856404; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 数据层：MySQL 优先 + CSV 降级 + 全品种发现
# ═══════════════════════════════════════════════════════════

@st.cache_resource
def get_mysql_engine():
    """尝试连接 MySQL，返回 engine 或 None"""
    try:
        from sqlalchemy import create_engine, inspect
        engine = create_engine("mysql+pymysql://root:root@localhost/sina?charset=utf8")
        # 快速验证连接
        insp = inspect(engine)
        _ = insp.get_table_names()
        return engine
    except Exception:
        return None


@st.cache_data(ttl=300)
def discover_mysql_symbols() -> list[str]:
    """从 MySQL 发现所有可用品种（排除 5 分钟线表）"""
    engine = get_mysql_engine()
    if engine is None:
        return []
    try:
        from sqlalchemy import inspect
        insp = inspect(engine)
        tables = insp.get_table_names()
        # 排除 m5 后缀的5分钟线表、test 表
        symbols = [t.upper() for t in tables
                   if not t.endswith("m5") and not t.startswith("test")
                   and not t.startswith("_")]
        return sorted(set(symbols))
    except Exception:
        return []


@st.cache_data
def discover_csv_symbols() -> list[str]:
    """从 data/ 目录发现 CSV 品种"""
    data_dir = Path("data")
    if not data_dir.exists():
        return []
    symbols = []
    for f in sorted(data_dir.glob("*.csv")):
        sym = f.stem.upper()
        if len(sym) >= 2:
            symbols.append(sym)
    return symbols


def get_all_available_symbols() -> list[str]:
    """合并 MySQL + CSV + symbol_meta 中的品种，去重排序"""
    mysql_syms = discover_mysql_symbols()
    csv_syms = discover_csv_symbols()
    meta_syms = list(load_symbol_meta().keys())
    all_syms = sorted(set(mysql_syms + csv_syms + meta_syms))
    return all_syms


@st.cache_data
def load_bars(symbol: str, source: str = "auto") -> list[Bar]:
    """
    加载品种数据：MySQL 优先，CSV 降级。
    source: "auto" | "mysql" | "csv"
    """
    bars = []

    # 尝试 MySQL
    if source in ("auto", "mysql"):
        try:
            loader = MySQLLoader(host="localhost", user="root", password="root", db="sina")
            bars = loader.get(symbol=symbol, freq="1d")
            if bars:
                return bars
        except Exception:
            pass

    # 降级 CSV
    if source in ("auto", "csv"):
        csv_dir = Path("data")
        for pattern in [f"{symbol.lower()}.csv", f"{symbol}.csv", f"{symbol.upper()}.csv"]:
            path = csv_dir / pattern
            if path.exists():
                loader = CSVLoader(str(path), symbol=symbol)
                return loader.get()

    return []


@st.cache_data
def compile_structures(symbol: str, min_amp, min_dur, min_cycles, source: str = "auto"):
    bars = load_bars(symbol, source)
    if not bars or len(bars) < 30:
        return None, bars
    config = CompilerConfig(
        min_amplitude=min_amp, min_duration=min_dur,
        min_cycles=min_cycles,
        adaptive_pivots=True, fractal_threshold=0.34,
    )
    result = compile_full(bars, config, symbol=symbol)
    return result, bars


# ═══════════════════════════════════════════════════════════
# 侧栏
# ═══════════════════════════════════════════════════════════

ALL_SYMBOLS = get_all_available_symbols()
MYSQL_SYMBOLS = discover_mysql_symbols()
CSV_SYMBOLS = discover_csv_symbols()
META = load_symbol_meta()

with st.sidebar:
    st.markdown("## 🔬 价格结构工作台")
    st.caption("v3.0 · 系统 = 结构 × 运动")
    st.divider()

    # ── 数据源状态 ──
    st.markdown("### 📡 数据源")
    mysql_ok = len(MYSQL_SYMBOLS) > 0
    if mysql_ok:
        st.success(f"MySQL 已连接 · {len(MYSQL_SYMBOLS)} 个品种")
    else:
        st.warning("MySQL 未连接 · 仅 CSV")
    st.caption(f"CSV 可用: {len(CSV_SYMBOLS)} 个品种")

    st.divider()

    # ── 品种选择（支持多选对比）──
    st.markdown("### 📈 品种选择")

    # 按交易所分组展示
    exchange_groups = {}
    for sym in ALL_SYMBOLS:
        info = META.get(sym, META.get(sym.upper(), {}))
        ex = info.get("exchange", "其他") if isinstance(info, dict) else "其他"
        exchange_groups.setdefault(ex, []).append(sym)

    # 主品种（单选）
    symbol_options = []
    for ex in ["SHFE", "DCE", "CZCE", "GFEX", "CFETS", "其他"]:
        syms = exchange_groups.get(ex, [])
        for s in syms:
            name = META.get(s, {}).get("name", s) if isinstance(META.get(s), dict) else s
            label = f"{s} · {name}" if name != s else s
            if s in MYSQL_SYMBOLS:
                label += " 🗄️"
            elif s in CSV_SYMBOLS:
                label += " 📄"
            symbol_options.append((s, label))

    sym_labels = [l for _, l in symbol_options]
    sym_codes = [s for s, _ in symbol_options]

    default_idx = sym_codes.index("CU0") if "CU0" in sym_codes else 0
    selected_label = st.selectbox("主品种", sym_labels, index=default_idx)
    selected_symbol = sym_codes[sym_labels.index(selected_label)]

    # 对比品种（多选）
    compare_symbols = st.multiselect(
        "对比品种（可选多个）",
        [l for s, l in symbol_options if s != selected_symbol],
        max_selections=4,
        help="选择其他品种做跨品种结构对比",
    )
    compare_codes = [sym_codes[sym_labels.index(l)] for l in compare_symbols]

    st.divider()

    # ── 数据范围 ──
    st.markdown("### 📊 数据范围")
    data_range = st.selectbox(
        "时间范围",
        ["最近60天", "最近120天", "最近半年", "最近一年", "全部数据"],
        index=1,
    )
    range_map = {
        "最近60天": 60, "最近120天": 120,
        "最近半年": 180, "最近一年": 365, "全部数据": 99999,
    }

    st.divider()

    # ── 灵敏度 ──
    st.markdown("### 🎛️ 灵敏度")
    sensitivity = st.select_slider(
        "结构识别灵敏度",
        options=["粗糙", "标准", "精细"],
        value="标准",
        help="粗糙=只看大结构，精细=捕捉小波动",
    )
    sens_map = {
        "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3},
        "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2},
        "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2},
    }

    st.divider()
    if st.button("🔄 刷新全部"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()


# ═══════════════════════════════════════════════════════════
# 数据加载 + 编译
# ═══════════════════════════════════════════════════════════

sens = sens_map[sensitivity]
result, bars = compile_structures(
    selected_symbol, sens["min_amp"], sens["min_dur"], sens["min_cycles"]
)

if result is None or not bars:
    st.error(f"❌ 无法加载 {selected_symbol} ({symbol_name(selected_symbol)}) 的数据")
    st.info("请确认：MySQL 中有该品种的日线表，或 data/ 目录下有对应的 CSV 文件")
    st.stop()

# 对比品种编译
compare_results = {}
for csym in compare_codes:
    cr, cbars = compile_structures(
        csym, sens["min_amp"], sens["min_dur"], sens["min_cycles"]
    )
    if cr is not None and cbars:
        compare_results[csym] = (cr, cbars)

# 按时间范围过滤
days = range_map[data_range]
cutoff = bars[-1].timestamp - pd.Timedelta(days=days)
recent_structures = [s for s in result.ranked_structures
                     if s.t_end and s.t_end >= cutoff]


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def motion_badge(tendency: str) -> str:
    cls = "badge-forming"
    if "breakdown" in tendency:
        cls = "badge-breakdown"
    elif "confirmation" in tendency:
        cls = "badge-confirmation"
    elif tendency == "stable":
        cls = "badge-stable"
    return f'<span class="motion-badge {cls}">{tendency}</span>'


def make_candlestick(bars_list, title="", height=350):
    df = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume,
    } for b in bars_list])
    fig = go.Figure(data=[go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    )])
    fig.update_layout(
        height=height, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=30, b=0),
        title=title,
    )
    return fig


def make_comparison_chart(bars_a, bars_b, name_a, name_b, zones_a=None, zones_b=None):
    """并排 K 线对比图"""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=False,
        subplot_titles=[f"{name_a}", f"{name_b}"],
        vertical_spacing=0.08,
    )

    # 上方：品种 A
    df_a = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close,
    } for b in bars_a])
    fig.add_trace(go.Candlestick(
        x=df_a["date"], open=df_a["open"], high=df_a["high"],
        low=df_a["low"], close=df_a["close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        name=name_a,
    ), row=1, col=1)

    # 下方：品种 B
    df_b = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close,
    } for b in bars_b])
    fig.add_trace(go.Candlestick(
        x=df_b["date"], open=df_b["open"], high=df_b["high"],
        low=df_b["low"], close=df_b["close"],
        increasing_line_color="#42a5f5", decreasing_line_color="#ff9800",
        name=name_b,
    ), row=2, col=1)

    # Zone 标注
    if zones_a:
        for z in zones_a:
            fig.add_hline(y=z, line_dash="dot", line_color="#4a90d9",
                         opacity=0.5, row=1, col=1)
    if zones_b:
        for z in zones_b:
            fig.add_hline(y=z, line_dash="dot", line_color="#ff9800",
                         opacity=0.5, row=2, col=1)

    fig.update_layout(
        height=600, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False,
    )
    return fig


def _describe_outcome(fo: dict) -> str:
    if not fo:
        return "无后续数据"
    parts = []
    ret5 = fo.get("ret_5d", 0) or 0
    ret10 = fo.get("ret_10d", 0) or 0
    ret20 = fo.get("ret_20d", 0) or 0
    max_rise = fo.get("max_rise_20d", 0) or 0
    max_dd = fo.get("max_dd_20d", 0) or 0
    if ret20 > 0.03:
        parts.append("之后整体上涨")
    elif ret20 < -0.03:
        parts.append("之后整体下跌")
    elif ret10 > 0.01:
        parts.append("之后先涨后回落")
    elif ret10 < -0.01:
        parts.append("之后先跌后反弹")
    else:
        parts.append("之后横盘整理")
    if abs(ret5) > 0.01:
        d = "涨" if ret5 > 0 else "跌"
        parts.append(f"5日{d}了约{abs(ret5):.0%}")
    if abs(ret10) > 0.01:
        d = "涨" if ret10 > 0 else "跌"
        parts.append(f"10日{d}了约{abs(ret10):.0%}")
    if max_rise > 0.05:
        parts.append(f"期间最高涨{max_rise:.0%}")
    if max_dd < -0.05:
        parts.append(f"期间最大回撤{abs(max_dd):.0%}")
    return "，".join(parts) if parts else "变化不大"


def _format_invariants(inv: dict) -> str:
    """格式化不变量为可读字符串"""
    parts = []
    if inv.get("cycle_count"):
        parts.append(f"Cycle={inv['cycle_count']}")
    if inv.get("avg_speed_ratio"):
        parts.append(f"SR={inv['avg_speed_ratio']:.2f}")
    if inv.get("avg_time_ratio"):
        parts.append(f"TR={inv['avg_time_ratio']:.2f}")
    if inv.get("zone_rel_bw"):
        parts.append(f"BW={inv['zone_rel_bw']:.3f}")
    return " · ".join(parts)


def _invariant_diff_table(inv1: dict, inv2: dict, name1: str, name2: str) -> pd.DataFrame:
    """生成两段结构的不变量对比表"""
    rows = []
    for k in INVARIANT_KEYS:
        v1 = inv1.get(k, 0) or 0
        v2 = inv2.get(k, 0) or 0
        scale = INVARIANT_SCALES.get(k, 1.0)
        diff = abs(v1 - v2) / scale if scale > 0 else 0
        rows.append({
            "指标": k,
            name1: round(v1, 4),
            name2: round(v2, 4),
            "归一化差异": round(diff, 3),
            "匹配度": "✅" if diff < 0.3 else "⚠️" if diff < 0.6 else "❌",
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
# 主页面
# ═══════════════════════════════════════════════════════════

st.markdown("### 🔬 价格结构研究工作台")
ds = META.get(selected_symbol, {})
ds_name = ds.get("name", selected_symbol) if isinstance(ds, dict) else selected_symbol
ds_exchange = ds.get("exchange", "") if isinstance(ds, dict) else ""
st.caption(f"**{selected_symbol}** ({ds_name}) {ds_exchange} · "
           f"{bars[0].timestamp:%Y-%m-%d} → {bars[-1].timestamp:%Y-%m-%d} · "
           f"{len(recent_structures)} 个结构 · "
           f"数据源: {'🗄️ MySQL' if selected_symbol.upper() in MYSQL_SYMBOLS else '📄 CSV'}")

if compare_codes:
    compare_names = [f"{c}({symbol_name(c)})" for c in compare_codes]
    st.caption(f"对比品种: {', '.join(compare_names)}")

tab_names = [
    "📡 今天值得关注什么",
    "🔍 历史对照（主动拉取）",
    "📊 跨品种对比",
    "🗺️ 稳态地图",
    "📝 复盘日志",
]
tabs = st.tabs(tab_names)


# ═══════════════════════════════════════════════════════════
# Tab 1: 今天值得关注什么
# ═══════════════════════════════════════════════════════════

with tabs[0]:
    st.markdown("#### 📡 今天值得关注什么")
    st.caption("有什么结构在形成、在确认、或正在破缺")

    if not recent_structures:
        st.info("当前时间范围内没有显著结构")
    else:
        breaking = [s for s in recent_structures
                    if s.motion and "breakdown" in s.motion.phase_tendency]
        confirming = [s for s in recent_structures
                      if s.motion and "confirmation" in s.motion.phase_tendency]
        forming = [s for s in recent_structures
                   if s.motion and s.motion.phase_tendency in ("forming", "stable", "")]

        if breaking:
            st.markdown("**🔴 正在破缺**")
            for s in breaking[:3]:
                flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                st.markdown(f"""
                <div class="structure-card danger">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(s.motion.phase_tendency)}
                    · <span class="meta-text">通量 {flux}</span>
                    <div class="narrative-text">{s.narrative_context or ''}</div>
                </div>
                """, unsafe_allow_html=True)

        if confirming:
            st.markdown("**🟢 趋向确认**")
            for s in confirming[:3]:
                flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                st.markdown(f"""
                <div class="structure-card ok">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(s.motion.phase_tendency)}
                    · <span class="meta-text">通量 {flux}</span>
                    <div class="narrative-text">{s.narrative_context or ''}</div>
                </div>
                """, unsafe_allow_html=True)

        if forming:
            st.markdown("**🔵 形成中**")
            for s in forming[:5]:
                proj_warn = " · ⚠️ 高压缩" if (s.projection and s.projection.is_blind) else ""
                tendency = s.motion.phase_tendency if s.motion else 'unknown'
                st.markdown(f"""
                <div class="structure-card">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(tendency)}{proj_warn}
                    <div class="narrative-text">{s.narrative_context or ''}</div>
                </div>
                """, unsafe_allow_html=True)

        # K 线图 + Zone 标注
        st.markdown("---")
        col_chart, col_info = st.columns([2, 1])
        with col_chart:
            st.markdown("**K 线 + 关键区**")
            fig = make_candlestick(bars[-120:])
            for s in recent_structures[:5]:
                fig.add_hline(y=s.zone.price_center, line_dash="dot",
                             line_color="#4a90d9", opacity=0.5,
                             annotation_text=f"Zone {s.zone.price_center:.0f}")
                fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                             fillcolor="#4a90d9", opacity=0.08, line_width=0)
            st.plotly_chart(fig, use_container_width=True)
        with col_info:
            st.markdown("**结构汇总**")
            st.metric("结构总数", len(result.structures))
            st.metric("Zone 数", len(result.zones))
            st.metric("Bundle 数", len(result.bundles))
            ss_count = sum(1 for ss in result.system_states if ss.is_reliable)
            st.metric("可信结构", ss_count)
            blind_count = sum(1 for ss in result.system_states if ss.projection.is_blind)
            if blind_count:
                st.metric("⚠️ 高压缩", blind_count)


# ═══════════════════════════════════════════════════════════
# Tab 2: 历史对照（主动从 MySQL 拉取比较）
# ═══════════════════════════════════════════════════════════

with tabs[1]:
    st.markdown("#### 🔍 历史对照 — 主动拉取比较")
    st.caption("从 MySQL/CSV 加载全量历史 → 编译 → 找最相似的历史段 → 对比详情")

    if not recent_structures:
        st.info("没有可比较的结构")
    else:
        # ── 选择要查询的结构 ──
        col_sel, col_params = st.columns([1, 1])
        with col_sel:
            options = [f"Zone {s.zone.price_center:.0f} ({s.cycle_count}次, "
                       f"{s.narrative_context or '?'})"
                       for s in recent_structures]
            sel = st.selectbox("选择当前结构", options, index=0)
            idx = options.index(sel)
            query_st = recent_structures[idx]

        with col_params:
            search_years = st.slider("历史检索范围（年）", 1, 10, 3)
            top_k = st.slider("返回案例数", 3, 20, 8)
            run_search = st.button("🚀 开始检索", type="primary")

        # 当前结构概要
        m = query_st.motion
        p = query_st.projection
        flux_str = f"{m.conservation_flux:+.2f}" if m else "—"
        tendency_str = m.phase_tendency if m else "—"
        st.markdown(f"""
        **当前结构** · Zone {query_st.zone.price_center:.0f} (±{query_st.zone.bandwidth:.0f})
        · {query_st.cycle_count}次试探 · {query_st.narrative_context or '?'}
        · 运动: {tendency_str} · 通量: {flux_str}
        """)

        # ── 执行检索 ──
        if run_search:
            with st.spinner(f"正在从 {'MySQL' if mysql_ok else 'CSV'} 加载 {selected_symbol} 全量历史数据..."):
                all_bars = load_bars(selected_symbol)
                if not all_bars:
                    st.error("无法加载历史数据")
                    st.stop()

                # 编译全量历史
                all_config = CompilerConfig(
                    min_amplitude=sens["min_amp"],
                    min_duration=sens["min_dur"],
                    min_cycles=sens["min_cycles"],
                    adaptive_pivots=True, fractal_threshold=0.34,
                )
                all_result = compile_full(all_bars, all_config, symbol=selected_symbol)

            st.success(f"历史数据: {len(all_bars)} 根 bar，{len(all_result.structures)} 个历史结构")

            # 在历史结构中找最相似的
            candidates = []
            for hs in all_result.structures:
                if hs is query_st:
                    continue
                # 跳过时间重叠的
                if hs.t_end and query_st.t_start and hs.t_end >= query_st.t_start:
                    continue

                sc = similarity(query_st, hs)

                # 计算前向表现
                if hs.t_end:
                    outcome_start = hs.t_end + timedelta(days=3)
                    outcome_end = outcome_start + timedelta(days=30)
                    future = [b for b in all_bars if outcome_start <= b.timestamp <= outcome_end]
                    if future:
                        start_p = future[0].open
                        peak = max(b.high for b in future)
                        trough = min(b.low for b in future)
                        up = (peak - start_p) / start_p if start_p > 0 else 0
                        down = (start_p - trough) / start_p if start_p > 0 else 0
                        direction = "up" if up >= down else "down"
                        move = max(up, down)
                    else:
                        direction = "unclear"
                        move = 0
                else:
                    direction = "unclear"
                    move = 0

                candidates.append({
                    "structure": hs,
                    "score": sc,
                    "direction": direction,
                    "move": move,
                })

            candidates.sort(key=lambda c: c["score"].total, reverse=True)
            top_cases = candidates[:top_k]

            if top_cases:
                st.markdown("---")
                st.markdown(f"**找到 {len(top_cases)} 个历史相似案例（按相似度排序）：**")

                # ── 统计面板 ──
                up_cases = [c for c in top_cases if c["direction"] == "up"]
                down_cases = [c for c in top_cases if c["direction"] == "down"]
                n = len(top_cases)

                stat_cols = st.columns(5)
                stat_cols[0].metric("总案例", n)
                stat_cols[1].metric("上涨", f"{len(up_cases)} ({len(up_cases)/n:.0%})")
                stat_cols[2].metric("下跌", f"{len(down_cases)} ({len(down_cases)/n:.0%})")
                if up_cases:
                    avg_up = sum(c["move"] for c in up_cases) / len(up_cases)
                    stat_cols[3].metric("平均涨幅", f"{avg_up:.1%}")
                if down_cases:
                    avg_down = sum(c["move"] for c in down_cases) / len(down_cases)
                    stat_cols[4].metric("平均跌幅", f"{avg_down:.1%}")

                st.markdown("---")

                # ── 逐案例展示 ──
                for i, case in enumerate(top_cases):
                    hs = case["structure"]
                    sc = case["score"]
                    direction = case["direction"]
                    move = case["move"]

                    direction_icon = "📈" if direction == "up" else "📉" if direction == "down" else "➡️"
                    case_cls = "case-up" if direction == "up" else "case-down"

                    with st.expander(
                        f"{direction_icon} #{i+1}  "
                        f"{hs.t_start:%Y-%m-%d} ~ {hs.t_end:%Y-%m-%d}  "
                        f"相似度 {sc.total:.0%}  "
                        f"后续{'涨' if direction=='up' else '跌' if direction=='down' else '横'}{move:.1%}",
                        expanded=(i == 0),
                    ):
                        col_left, col_right = st.columns([1, 1])

                        with col_left:
                            st.markdown("**不变量对比**")
                            diff_df = _invariant_diff_table(
                                query_st.invariants or {},
                                hs.invariants or {},
                                "当前", "历史",
                            )
                            st.dataframe(diff_df, hide_index=True, use_container_width=True)

                        with col_right:
                            st.markdown("**相似度分层**")
                            sim_cols = st.columns(2)
                            sim_cols[0].metric("几何", f"{sc.geometric:.0%}")
                            sim_cols[1].metric("关系", f"{sc.relational:.0%}")

                            st.markdown("**结构特征**")
                            st.caption(f"Cycle: {hs.cycle_count} · "
                                      f"SR: {hs.avg_speed_ratio:.2f} · "
                                      f"TR: {hs.avg_time_ratio:.2f} · "
                                      f"BW: {hs.zone.relative_bandwidth:.3f}")

                            if direction != "unclear":
                                st.markdown(f"**后续走势**: {direction} {move:.1%}")

                        # 历史段 K 线
                        if hs.t_start and hs.t_end:
                            margin = timedelta(days=15)
                            hist_bars = [b for b in all_bars
                                        if hs.t_start - margin <= b.timestamp <= hs.t_end + margin]
                            if hist_bars:
                                fig = make_candlestick(hist_bars,
                                    title=f"历史段 {hs.t_start:%Y-%m-%d} ~ {hs.t_end:%Y-%m-%d}")
                                fig.add_hline(y=hs.zone.price_center, line_dash="dot",
                                             line_color="#4a90d9",
                                             annotation_text=f"Zone {hs.zone.price_center:.0f}")
                                fig.add_hrect(y0=hs.zone.lower, y1=hs.zone.upper,
                                             fillcolor="#4a90d9", opacity=0.08, line_width=0)
                                st.plotly_chart(fig, use_container_width=True)

                # ── 综合研判 ──
                st.markdown("---")
                st.markdown("#### 📋 综合研判")

                if len(up_cases) > len(down_cases):
                    st.success(f"**偏多**：{len(up_cases)}/{n} 个历史案例后续上涨，"
                              f"平均涨幅 {sum(c['move'] for c in up_cases)/len(up_cases):.1%}")
                elif len(down_cases) > len(up_cases):
                    st.error(f"**偏空**：{len(down_cases)}/{n} 个历史案例后续下跌，"
                            f"平均跌幅 {sum(c['move'] for c in down_cases)/len(down_cases):.1%}")
                else:
                    st.warning(f"**分歧**：上涨 {len(up_cases)} / 下跌 {len(down_cases)}，方向不明")

            else:
                st.info("未找到足够的历史相似案例，建议降低灵敏度或扩大检索范围")


# ═══════════════════════════════════════════════════════════
# Tab 3: 跨品种对比
# ═══════════════════════════════════════════════════════════

with tabs[2]:
    st.markdown("#### 📊 跨品种结构对比")
    st.caption("选择侧栏的对比品种，自动并排展示同类型结构")

    if not compare_codes:
        st.info("请在侧栏选择 1~4 个对比品种")
    else:
        # 对比表格
        compare_rows = []

        # 主品种
        for s in recent_structures[:3]:
            compare_rows.append({
                "品种": f"{selected_symbol} ({ds_name})",
                "Zone": f"{s.zone.price_center:.0f}",
                "Cycle数": s.cycle_count,
                "速度比": f"{s.avg_speed_ratio:.2f}",
                "时间比": f"{s.avg_time_ratio:.2f}",
                "带宽": f"{s.zone.relative_bandwidth:.3f}",
                "运动": s.motion.phase_tendency if s.motion else "—",
                "通量": f"{s.motion.conservation_flux:+.2f}" if s.motion else "—",
                "反差": s.zone.context_contrast.value,
            })

        # 对比品种
        for csym in compare_codes:
            if csym not in compare_results:
                continue
            cr, cbars = compare_results[csym]
            cs_name = symbol_name(csym)
            cs_recent = [s for s in cr.ranked_structures
                        if s.t_end and s.t_end >= cutoff]
            for s in cs_recent[:3]:
                compare_rows.append({
                    "品种": f"{csym} ({cs_name})",
                    "Zone": f"{s.zone.price_center:.0f}",
                    "Cycle数": s.cycle_count,
                    "速度比": f"{s.avg_speed_ratio:.2f}",
                    "时间比": f"{s.avg_time_ratio:.2f}",
                    "带宽": f"{s.zone.relative_bandwidth:.3f}",
                    "运动": s.motion.phase_tendency if s.motion else "—",
                    "通量": f"{s.motion.conservation_flux:+.2f}" if s.motion else "—",
                    "反差": s.zone.context_contrast.value,
                })

        if compare_rows:
            df_compare = pd.DataFrame(compare_rows)
            st.dataframe(df_compare, use_container_width=True, hide_index=True)

        # ── 不变量雷达图对比 ──
        if recent_structures and any(c in compare_results for c in compare_codes):
            st.markdown("---")
            st.markdown("**不变量雷达图**")

            # 取主品种最近结构
            main_s = recent_structures[0]
            main_inv = main_s.invariants or {}

            radar_keys = ["cycle_count", "avg_speed_ratio", "avg_time_ratio",
                         "zone_rel_bw", "zone_strength"]
            radar_labels = ["Cycle数", "速度比", "时间比", "相对带宽", "强度"]

            fig = go.Figure()

            # 主品种
            main_vals = [(main_inv.get(k, 0) or 0) / INVARIANT_SCALES.get(k, 1)
                        for k in radar_keys]
            fig.add_trace(go.Scatterpolar(
                r=main_vals + [main_vals[0]],
                theta=radar_labels + [radar_labels[0]],
                fill='toself',
                name=f"{selected_symbol} ({ds_name})",
                line_color="#4a90d9",
            ))

            # 对比品种
            colors = ["#26a69a", "#ef5350", "#ff9800", "#ab47bc"]
            for ci, csym in enumerate(compare_codes):
                if csym not in compare_results:
                    continue
                cr, _ = compare_results[csym]
                if not cr.ranked_structures:
                    continue
                cs_inv = cr.ranked_structures[0].invariants or {}
                cs_vals = [(cs_inv.get(k, 0) or 0) / INVARIANT_SCALES.get(k, 1)
                          for k in radar_keys]
                cs_name = symbol_name(csym)
                fig.add_trace(go.Scatterpolar(
                    r=cs_vals + [cs_vals[0]],
                    theta=radar_labels + [radar_labels[0]],
                    fill='toself',
                    name=f"{csym} ({cs_name})",
                    line_color=colors[ci % len(colors)],
                    opacity=0.6,
                ))

            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                height=400, template="plotly_dark",
                margin=dict(l=60, r=60, t=30, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── 跨品种 K 线并排 ──
        if compare_codes and len(compare_codes) == 1:
            csym = compare_codes[0]
            if csym in compare_results:
                st.markdown("---")
                st.markdown(f"**K 线对比: {selected_symbol} vs {csym}**")
                _, cbars = compare_results[csym]
                fig = make_comparison_chart(
                    bars[-120:], cbars[-120:],
                    f"{selected_symbol} ({ds_name})",
                    f"{csym} ({symbol_name(csym)})",
                )
                st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# Tab 4: 稳态地图
# ═══════════════════════════════════════════════════════════

with tabs[3]:
    st.markdown("#### 🗺️ 稳态地图")
    st.caption("如果结构崩塌，市场最可能先滑向哪里")

    stable_data = []
    for si, st_obj in enumerate(recent_structures):
        for ci, c in enumerate(st_obj.cycles):
            if c.has_stable_state:
                ns = c.next_stable
                stable_data.append({
                    "结构": f"Zone {st_obj.zone.price_center:.0f}",
                    "Cycle": ci + 1,
                    "Exit方向": "↑" if c.exit.delta > 0 else "↓",
                    "稳态价位": ns.zone.price_center if ns.zone else 0,
                    "到达天数": ns.duration_to_arrive,
                    "阻力": ns.resistance_level,
                })

    if stable_data:
        sdf = pd.DataFrame(stable_data)
        st.dataframe(sdf, use_container_width=True, hide_index=True)

        col_hist, col_stats = st.columns([2, 1])
        with col_hist:
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=sdf["稳态价位"], nbinsx=20,
                marker_color="#ff9800", name="最近稳态",
            ))
            fig.update_layout(
                height=300, template="plotly_dark",
                xaxis_title="价位", yaxis_title="频次",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_stats:
            st.metric("平均阻力", f"{sdf['阻力'].mean():.3f}")
            st.metric("低阻力占比(<0.3)", f"{(sdf['阻力'] < 0.3).mean():.0%}")
            st.metric("稳态覆盖率",
                     f"{len(sdf) / max(sum(s.cycle_count for s in recent_structures), 1):.0%}")

            low_res = sdf[sdf["阻力"] < 0.2]
            if not low_res.empty:
                st.warning(f"⚠️ {len(low_res)} 个稳态阻力 < 0.2 — 可能是假稳态")
    else:
        st.info("当前没有识别到最近稳态")


# ═══════════════════════════════════════════════════════════
# Tab 5: 复盘日志
# ═══════════════════════════════════════════════════════════

with tabs[4]:
    st.markdown("#### 📝 复盘日志")
    st.caption("结构化记录 · 自动保存到本地 · 可回溯查看")

    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    journal_file = log_dir / "journal.jsonl"
    today = datetime.now().strftime("%Y-%m-%d")
    md_file = log_dir / f"{today}.md"

    # ── 子 Tab：写日志 / 历史回顾 ──
    sub_tab_write, sub_tab_history = st.tabs(["✏️ 写日志", "📚 历史回顾"])

    # ════════════════════════════════════════════════════════
    # 写日志
    # ════════════════════════════════════════════════════════
    with sub_tab_write:
        st.markdown("**新建一条复盘记录**")

        # 自动填充当前结构上下文
        auto_context = ""
        if recent_structures:
            auto_context = f"[{selected_symbol}] {len(recent_structures)}个结构活跃: "
            auto_context += ", ".join(
                f"Zone {s.zone.price_center:.0f}({s.motion.phase_tendency if s.motion else '?'})"
                for s in recent_structures[:3]
            )

        col_a, col_b = st.columns([1, 1])
        with col_a:
            entry_type = st.selectbox(
                "记录类型",
                ["结构观察", "交易想法", "复盘总结", "疑问待解", "其他"],
                index=0,
            )
        with col_b:
            sentiment = st.selectbox(
                "倾向判断",
                ["偏多 📈", "偏空 📉", "中性 ➡️", "不确定 ❓"],
                index=2,
            )

        # 关联结构（可选）
        if recent_structures:
            zone_options = ["不关联"] + [
                f"Zone {s.zone.price_center:.0f} ({s.cycle_count}次试探)"
                for s in recent_structures
            ]
            linked_zone = st.selectbox("关联结构", zone_options, index=0)
        else:
            linked_zone = "不关联"

        # 正文
        content = st.text_area(
            "日志内容",
            value="",
            height=180,
            placeholder=f"记录你的观察、判断、理由...\n\n自动上下文：{auto_context}",
        )

        # 标签
        tags_input = st.text_input("标签（逗号分隔）", placeholder="例如: 铜,关键区突破,需要验证")

        col_save, col_info = st.columns([1, 2])
        with col_save:
            if st.button("💾 保存日志", type="primary", use_container_width=True):
                if content.strip():
                    import json as _json
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "date": today,
                        "symbol": selected_symbol,
                        "symbol_name": ds_name,
                        "type": entry_type,
                        "sentiment": sentiment,
                        "linked_zone": linked_zone if linked_zone != "不关联" else "",
                        "content": content.strip(),
                        "tags": [t.strip() for t in tags_input.split(",") if t.strip()],
                        "structures_snapshot": [
                            {
                                "zone": s.zone.price_center,
                                "cycles": s.cycle_count,
                                "tendency": s.motion.phase_tendency if s.motion else "",
                                "flux": round(s.motion.conservation_flux, 2) if s.motion else 0,
                            }
                            for s in recent_structures[:5]
                        ],
                    }
                    with open(journal_file, "a", encoding="utf-8") as f:
                        f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
                    st.success(f"✅ 已保存 · {entry_type} · {selected_symbol} · {today}")
                else:
                    st.warning("请输入日志内容")

        with col_info:
            st.caption(f"保存位置: `{journal_file}`")
            st.caption("JSONL 格式，每行一条记录，可用 Python/pandas 直接读取分析")

        # 今日自动上下文预览
        if recent_structures:
            with st.expander("📋 当前编译上下文（自动记录）"):
                ctx = f"品种: {selected_symbol} ({ds_name})\n"
                ctx += f"数据: {bars[0].timestamp:%Y-%m-%d} → {bars[-1].timestamp:%Y-%m-%d}\n"
                ctx += f"结构: {len(recent_structures)} 个\n"
                for s in recent_structures[:5]:
                    m = s.motion
                    ctx += f"  Zone {s.zone.price_center:.0f}: {s.narrative_context or '?'}"
                    if m:
                        ctx += f" [{m.phase_tendency}, 通量{m.conservation_flux:+.2f}]"
                    ctx += "\n"
                st.code(ctx, language="text")

    # ════════════════════════════════════════════════════════
    # 历史回顾
    # ════════════════════════════════════════════════════════
    with sub_tab_history:
        st.markdown("**浏览历史复盘记录**")

        if not journal_file.exists():
            st.info("暂无复盘记录，在「写日志」标签页开始记录")
        else:
            import json as _json
            entries = []
            with open(journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(_json.loads(line))
                        except _json.JSONDecodeError:
                            continue

            if not entries:
                st.info("暂无复盘记录")
            else:
                # 过滤器
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    filter_symbols = list(set(e.get("symbol", "") for e in entries))
                    filter_sym = st.selectbox("品种筛选", ["全部"] + sorted(filter_symbols))
                with col_f2:
                    filter_types = list(set(e.get("type", "") for e in entries))
                    filter_type = st.selectbox("类型筛选", ["全部"] + sorted(filter_types))
                with col_f3:
                    filter_dates = sorted(set(e.get("date", "") for e in entries), reverse=True)
                    filter_date = st.selectbox("日期筛选", ["全部"] + filter_dates)

                # 应用过滤
                filtered = entries
                if filter_sym != "全部":
                    filtered = [e for e in filtered if e.get("symbol") == filter_sym]
                if filter_type != "全部":
                    filtered = [e for e in filtered if e.get("type") == filter_type]
                if filter_date != "全部":
                    filtered = [e for e in filtered if e.get("date") == filter_date]

                # 倒序展示（最新在前）
                filtered = list(reversed(filtered))

                st.caption(f"共 {len(filtered)} 条记录")

                for entry in filtered[:20]:
                    ts = entry.get("timestamp", "")
                    try:
                        dt = datetime.fromisoformat(ts)
                        time_str = dt.strftime("%m-%d %H:%M")
                    except Exception:
                        time_str = ts[:16]

                    sym = entry.get("symbol", "")
                    sym_name = entry.get("symbol_name", "")
                    etype = entry.get("type", "")
                    sentiment = entry.get("sentiment", "")
                    zone = entry.get("linked_zone", "")
                    content = entry.get("content", "")
                    tags = entry.get("tags", [])

                    # 情绪标签颜色
                    if "偏多" in sentiment:
                        tag_cls = "tag-bullish"
                    elif "偏空" in sentiment:
                        tag_cls = "tag-bearish"
                    else:
                        tag_cls = "tag-neutral"

                    header_parts = [f"🕐 {time_str}", f"**{sym}** ({sym_name})", etype]
                    if zone:
                        header_parts.append(f"🔗 {zone}")
                    header = " · ".join(header_parts)

                    with st.expander(f"{time_str} | {sym} | {etype} | {sentiment}", expanded=False):
                        st.markdown(f"""
                        <div class="journal-entry">
                            <div class="entry-header">{header}</div>
                            <div class="entry-body">{content}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        if tags:
                            tags_html = " ".join(
                                f'<span class="journal-tag {tag_cls}">{t}</span>' for t in tags
                            )
                            st.markdown(tags_html, unsafe_allow_html=True)
                        # 关联的结构快照
                        snapshot = entry.get("structures_snapshot", [])
                        if snapshot:
                            snap_text = "当时结构: " + ", ".join(
                                f"Zone {s['zone']:.0f}({s['tendency']}, 通量{s['flux']:+.2f})"
                                for s in snapshot
                            )
                            st.caption(snap_text)

                # 导出
                st.markdown("---")
                col_export1, col_export2 = st.columns(2)
                with col_export1:
                    if st.button("📥 导出为 Markdown"):
                        md_lines = [f"# 复盘日志导出 {today}\n"]
                        for e in filtered:
                            md_lines.append(f"## {e.get('date', '')} {e.get('symbol', '')} {e.get('type', '')}")
                            md_lines.append(f"倾向: {e.get('sentiment', '')}")
                            if e.get("linked_zone"):
                                md_lines.append(f"关联: {e['linked_zone']}")
                            md_lines.append(f"\n{e.get('content', '')}\n")
                            if e.get("tags"):
                                md_lines.append(f"标签: {', '.join(e['tags'])}")
                            md_lines.append("---\n")
                        export_path = log_dir / f"export_{today}.md"
                        export_path.write_text("\n".join(md_lines), encoding="utf-8")
                        st.success(f"已导出到 {export_path}")
                with col_export2:
                    st.caption(f"数据文件: `{journal_file}`")
