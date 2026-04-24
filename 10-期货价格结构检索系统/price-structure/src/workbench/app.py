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
import time as _time

from src.data.loader import Bar, CSVLoader, MySQLLoader
from src.data.symbol_meta import symbol_name, load_symbol_meta
from src.data.sina_fetcher import fetch_bars as sina_fetch_bars, detect_source, available_contracts
from src.compiler.pipeline import compile_full, CompilerConfig
from src.retrieval.similarity import similarity, INVARIANT_KEYS, INVARIANT_SCALES
from src.quality import assess_quality, QualityTier

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
    /* A股惯例：红涨绿跌 — danger=看多(红), ok=看空(绿) */
    .structure-card.danger  { border-left-color: #ef5350; background: linear-gradient(135deg, #fff5f5 0%, #ffe0e0 100%); }
    .structure-card.ok      { border-left-color: #26a69a; background: linear-gradient(135deg, #f0faf8 0%, #d4efea 100%); }

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
    /* A股惯例：红涨绿跌 */
    .tag-bullish { background: #f8d7da; color: #721c24; }
    .tag-bearish { background: #d4edda; color: #155724; }
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
        import os
        from sqlalchemy import create_engine, inspect
        password = os.getenv('MYSQL_PASSWORD', '')
        engine = create_engine(f"mysql+pymysql://root:{password}@localhost/sina?charset=utf8")
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
            import os
            password = os.getenv('MYSQL_PASSWORD', '')
            loader = MySQLLoader(host="localhost", user="root", password=password, db="sina")
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


TIER_COLORS = {"A": ("#1b5e20", "#c8e6c9"), "B": ("#0d47a1", "#bbdefb"),
               "C": ("#e65100", "#ffe0b2"), "D": ("#b71c1c", "#ffcdd2")}


def _extract_key(label: str) -> str:
    """从中文标签中提取英文 key，如 '📈 上涨(up)' → 'up'"""
    if "(" in label and ")" in label:
        return label[label.index("(") + 1 : label.index(")")]
    return label


def _price_vs_zone(last_price: float, zone_center: float, zone_bw: float) -> str:
    """当前价格相对于 Zone 的位置描述"""
    if zone_bw <= 0:
        return ""
    upper = zone_center + zone_bw
    lower = zone_center - zone_bw
    if lower <= last_price <= upper:
        dist_pct = (last_price - zone_center) / zone_bw * 100
        return f"📍 价格在 Zone 内（偏{'上' if dist_pct > 0 else '下'}{abs(dist_pct):.0f}%）"
    elif last_price > upper:
        pct = (last_price - zone_center) / zone_center * 100
        return f"📍 价格在 Zone 上方 +{pct:.1f}%"
    else:
        pct = (zone_center - last_price) / zone_center * 100
        return f"📍 价格在 Zone 下方 -{pct:.1f}%"


def make_candlestick(bars_list, title="", height=350):
    df = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume,
    } for b in bars_list])
    fig = go.Figure(data=[go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
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
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
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
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
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
    "🔎 合约检索",
    "⏱️ 多时间维度对比",
    "🔬 v3.0 质量与共振",
]
tabs = st.tabs(tab_names)


# ═══════════════════════════════════════════════════════════
# Tab 1: 今天值得关注什么
# ═══════════════════════════════════════════════════════════

with tabs[0]:
    st.markdown("#### 📡 今天值得关注什么")
    st.caption("有什么结构在形成、在确认、或正在破缺")

    # ── 全市场机会扫描 ──
    @st.cache_data(ttl=300)
    def _scan_all_symbols(sens_key: str) -> list[dict]:
        """扫描所有品种，返回按关注度排序的 Top 机会列表"""
        _sens = {
            "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3},
            "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2},
            "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2},
        }
        _s = _sens.get(sens_key, _sens["标准"])
        results = []
        for sym in ALL_SYMBOLS:
            bars_data = load_bars(sym)
            if not bars_data or len(bars_data) < 30:
                continue
            cfg = CompilerConfig(
                min_amplitude=_s["min_amp"], min_duration=_s["min_dur"],
                min_cycles=_s["min_cycles"],
                adaptive_pivots=True, fractal_threshold=0.34,
            )
            cr = compile_full(bars_data, cfg, symbol=sym)
            if not cr.ranked_structures:
                continue
            last_price = bars_data[-1].close
            for idx_s, s in enumerate(cr.ranked_structures[:3]):
                m = s.motion
                p = s.projection
                # 关注度评分：使用 quality.py 五维度评估
                ss = cr.system_states[idx_s] if idx_s < len(cr.system_states) else None
                qa = assess_quality(s, ss)
                score_100 = round(qa.score * 100, 1)  # quality 分是 [0,1]，转为百分制

                # 方向判断
                direction = "unclear"
                if m and "breakdown" in m.phase_tendency:
                    direction = "down" if m.conservation_flux < 0 else "up"
                elif m and "confirmation" in m.phase_tendency:
                    direction = "up" if m.conservation_flux > 0 else "down"

                # 研究建议（基于质量评估 flags + 结构特征）
                suggestions = []
                if direction == "up":
                    suggestions.append(f"观察价格突破 Zone 上沿 {s.zone.price_center + s.zone.bandwidth:.0f} 后的放量情况")
                elif direction == "down":
                    suggestions.append(f"观察价格跌破 Zone 下沿 {s.zone.price_center - s.zone.bandwidth:.0f} 后的反抽力度")
                else:
                    suggestions.append("方向不明，等待明确信号再介入研究")
                if m and "breakdown" in m.phase_tendency:
                    suggestions.append("处于破缺阶段，关注是否能稳住在新价位")
                if p and p.is_blind:
                    suggestions.append("高压缩结构，突破后波动可能放大，注意节奏")
                # 基于质量评估的补充建议
                for rec in qa.recommendations[:2]:
                    suggestions.append(f"📋 {rec}")

                # 风控评级（基于质量分层）
                if qa.tier == QualityTier.A:
                    risk_level = "高"
                    risk_pct = "5-8%"
                elif qa.tier == QualityTier.B:
                    risk_level = "中"
                    risk_pct = "3-5%"
                else:
                    risk_level = "低"
                    risk_pct = "1-3%"

                results.append({
                    "symbol": sym,
                    "symbol_name": symbol_name(sym),
                    "zone_center": s.zone.price_center,
                    "zone_bw": s.zone.bandwidth,
                    "cycles": s.cycle_count,
                    "motion": m.phase_tendency if m else "—",
                    "flux": round(m.conservation_flux, 2) if m else 0,
                    "score": score_100,
                    "tier": qa.tier.value,
                    "direction": direction,
                    "is_blind": p.is_blind if p else False,
                    "contrast": s.zone.context_contrast.value if s.zone else "",
                    "narrative": s.narrative_context or "",
                    "last_price": last_price,
                    "suggestions": suggestions,
                    "risk_level": risk_level,
                    "risk_pct": risk_pct,
                    "quality_flags": qa.flags[:3],
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    scan_col1, scan_col2, scan_col3 = st.columns([1, 2, 1])
    with scan_col1:
        run_scan = st.button("🔍 全市场扫描", type="primary", use_container_width=True, key="btn_market_scan")
    with scan_col2:
        st.caption("扫描所有品种的活跃结构，按关注度评分排序，展示 Top 10 机会")
    with scan_col3:
        with st.popover("ℹ️ 评分说明"):
            st.markdown("""
            **质量评分**（满分 100）基于 `quality.py` 五维度评估：

            | 维度 | 权重 | 说明 |
            |---|---|---|
            | 结构完整性 | 25% | cycle 数、zone 强度、不变量完整度 |
            | 运动可信度 | 25% | 稳定性验证、投影非盲、运动态置信度 |
            | 守恒一致性 | 20% | 通量合理性、速度比/时间比范围 |
            | 时间成熟度 | 15% | cycle 数适中（3-8 为佳）|
            | 后验可追溯 | 15% | 标签、典型度、叙事背景 |

            **分层标准**：A 层 ≥75 · B 层 50-74 · C 层 25-49 · D 层 <25
            """)

    if run_scan:
        from src.lifecycle import LifecycleTracker, LifecycleRecord
        total_syms = len(ALL_SYMBOLS)
        with st.spinner(f"🔍 正在扫描 {total_syms} 个品种的结构..."):
            prog = st.progress(0, text=f"准备扫描 {total_syms} 个品种...")
            scan_results = _scan_all_symbols(sensitivity)
            prog.progress(1.0, text=f"✅ 扫描完成，发现 {len(scan_results)} 个活跃结构")

        # 生命周期记录：从扫描 dict 直接构建 LifecycleRecord（无需重新编译）
        if scan_results:
            _tracker = LifecycleTracker()
            _today_str = datetime.now().strftime("%Y-%m-%d")
            _recorded = 0
            for r in scan_results[:20]:
                try:
                    zc = r["zone_center"]
                    lifecycle_id = _tracker._match_existing_zone(r["symbol"], zc, _today_str)
                    rec = LifecycleRecord(
                        date=_today_str,
                        symbol=r["symbol"],
                        zone_center=zc,
                        zone_bw=r["zone_bw"],
                        cycle_count=r["cycles"],
                        quality_tier=r.get("tier", "?"),
                        quality_score=r["score"] / 100.0,
                        phase_tendency=r["motion"],
                        conservation_flux=r["flux"],
                        speed_ratio=0,  # 扫描 dict 中无此字段
                        direction=r["direction"],
                        is_blind=r["is_blind"],
                        stability="unknown",
                        lifecycle_id=lifecycle_id,
                    )
                    _tracker._append_records(r["symbol"], [rec])
                    _recorded += 1
                except Exception:
                    pass
            if _recorded:
                st.caption(f"📝 已记录 {_recorded} 个品种的生命周期")

        if scan_results:
            top10 = scan_results[:10]
            st.markdown("---")
            st.markdown(f"**🏆 Top 10 关注机会**（共扫描 {len(scan_results)} 个活跃结构）")

            # 统计面板
            dir_up = sum(1 for r in top10 if r["direction"] == "up")
            dir_down = sum(1 for r in top10 if r["direction"] == "down")
            dir_unclear = sum(1 for r in top10 if r["direction"] == "unclear")
            stat_c = st.columns(4)
            stat_c[0].metric("总机会", len(top10))
            stat_c[1].metric("📈 偏多", dir_up)
            stat_c[2].metric("📉 偏空", dir_down)
            stat_c[3].metric("➡️ 不明", dir_unclear)

            # 逐卡片展示
            for i, r in enumerate(top10):
                dir_icon = "📈" if r["direction"] == "up" else "📉" if r["direction"] == "down" else "➡️"
                # A股惯例：红涨绿跌
                card_cls = "danger" if r["direction"] == "up" else "ok" if r["direction"] == "down" else ""
                motion_html = motion_badge(r["motion"])
                blind_tag = " · ⚠️高压缩" if r["is_blind"] else ""
                contrast_tag = f" · {r['contrast']}" if r["contrast"] else ""
                price_pos = _price_vs_zone(r["last_price"], r["zone_center"], r["zone_bw"])

                # 质量层级颜色
                tier = r.get("tier", "?")
                tier_fg, tier_bg = TIER_COLORS.get(tier, ("#666", "#eee"))
                tier_badge = f'<span style="background:{tier_bg};color:{tier_fg};padding:1px 6px;border-radius:3px;font-size:0.8em;font-weight:700">{tier}层</span>'

                # 风控评级颜色
                risk_color = {"高": "#ef5350", "中": "#ff9800", "低": "#26a69a"}.get(r["risk_level"], "#999")

                st.markdown(f"""
                <div class="structure-card {card_cls}">
                    <b>#{i+1}</b> {dir_icon}
                    <span class="zone-label">{r['symbol']} · {r['symbol_name']}</span>
                    {tier_badge}
                    <span class="meta-text"> Zone {r['zone_center']:.0f} (±{r['zone_bw']:.0f}) · {r['cycles']}次试探</span>
                    · {motion_html} · 通量 {r['flux']:+.2f}{blind_tag}{contrast_tag}
                    · <b>质量 {r['score']:.0f}分</b>
                    · <span style="color:{risk_color};font-weight:700">⚖️ {r['risk_level']}关注度</span>
                    <div class="meta-text">{price_pos} · 现价 {r['last_price']:.1f}</div>
                    <div class="narrative-text">{r['narrative']}</div>
                </div>
                """, unsafe_allow_html=True)

                # 研究建议（折叠显示）
                with st.expander(f"💡 #{i+1} {r['symbol']} 研究建议 · {tier}层", expanded=False):
                    st.markdown(f"**风控建议**：{tier}层质量（{r['score']:.0f}分），建议单笔关注不超过总资金的 **{r['risk_pct']}**")
                    # 质量标记
                    flags = r.get("quality_flags", [])
                    if flags:
                        st.markdown("**质量标记**：" + " · ".join(flags))
                    st.markdown("**下一步研究动作**：")
                    for j, sug in enumerate(r["suggestions"], 1):
                        st.markdown(f"  {j}. {sug}")

            # ── 今日三选 ──
            st.markdown("---")
            st.markdown("#### 🎯 今日三选")
            st.caption("从 Top 10 中精选三种策略类型 — 激进 / 稳健 / 潜伏")

            # 激进型：breakdown + 最高通量
            aggressive = [r for r in scan_results[:20]
                          if r["motion"] and "breakdown" in r["motion"]]
            aggressive.sort(key=lambda r: abs(r["flux"]), reverse=True)

            # 稳健型：confirmation + 非零通量
            stable = [r for r in scan_results[:20]
                      if r["motion"] and "confirmation" in r["motion"]]
            stable.sort(key=lambda r: r["score"], reverse=True)

            # 潜伏型：forming/stable + 高压缩或高关注度
            latent = [r for r in scan_results[:20]
                      if r["motion"] in ("forming", "stable", "") and (r["is_blind"] or r["score"] >= 50)]
            latent.sort(key=lambda r: r["score"], reverse=True)

            trio = [
                ("🔴 激进型", "breakdown + 高通量，波动大", aggressive),
                ("🟢 稳健型", "confirmation，方向明确", stable),
                ("🔵 潜伏型", "forming + 高压缩，等待突破", latent),
            ]

            trio_cols = st.columns(3)
            for col, (label, desc, candidates) in zip(trio_cols, trio):
                with col:
                    st.markdown(f"**{label}**")
                    st.caption(desc)
                    if candidates:
                        r = candidates[0]
                        pos = _price_vs_zone(r["last_price"], r["zone_center"], r["zone_bw"])
                        risk_color = {"高": "#ef5350", "中": "#ff9800", "低": "#26a69a"}.get(r["risk_level"], "#999")
                        t = r.get("tier", "?")
                        st.markdown(f"""
                        <div class="structure-card">
                            <span class="zone-label">{r['symbol']} · {r['symbol_name']}</span>
                            <span style="background:{TIER_COLORS.get(t, ('#666','#eee'))[1]};color:{TIER_COLORS.get(t, ('#666','#eee'))[0]};padding:1px 6px;border-radius:3px;font-size:0.8em;font-weight:700">{t}层</span><br>
                            <span class="meta-text">Zone {r['zone_center']:.0f} (±{r['zone_bw']:.0f}) · {motion_badge(r['motion'])} · 通量 {r['flux']:+.2f}</span><br>
                            <span class="meta-text">{pos}</span><br>
                            <span style="color:{risk_color};font-weight:700">质量 {r['score']:.0f}分 · {r['risk_level']}关注度</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption(f"💡 {r['suggestions'][0]}" if r['suggestions'] else "")
                    else:
                        st.info("暂无符合条件的结构")

            # ── 跨品种信号一致性分析 ──
            st.markdown("---")
            st.markdown("#### 🔗 跨品种信号一致性")

            # 按交易所分组
            exchange_groups = {}
            for r in scan_results[:20]:
                info = META.get(r["symbol"], META.get(r["symbol"].upper(), {}))
                ex = info.get("exchange", "其他") if isinstance(info, dict) else "其他"
                exchange_groups.setdefault(ex, []).append(r)

            for ex, items in sorted(exchange_groups.items()):
                if len(items) < 2:
                    continue
                up_n = sum(1 for r in items if r["direction"] == "up")
                down_n = sum(1 for r in items if r["direction"] == "down")
                total = len(items)
                names = ", ".join(f"{r['symbol']}" for r in items[:5])

                if up_n > down_n and up_n >= total * 0.6:
                    st.success(f"**{ex}** 板块偏多：{up_n}/{total} 偏多 · {names}")
                elif down_n > up_n and down_n >= total * 0.6:
                    st.error(f"**{ex}** 板块偏空：{down_n}/{total} 偏空 · {names}")
                else:
                    st.warning(f"**{ex}** 板块信号分歧：📈{up_n} / 📉{down_n} / ➡️{total - up_n - down_n} · {names}")

            # ── 每日变化报告 ──
            st.markdown("---")
            st.markdown("#### 📋 每日变化报告")

            _today_key = datetime.now().strftime("%Y-%m-%d")
            _prev_results = st.session_state.get("prev_scan_results", {})
            _prev_date = st.session_state.get("prev_scan_date", "")

            if _prev_date == _today_key and _prev_results:
                # 对比上次扫描
                prev_map = {(r["symbol"], r["zone_center"]): r for r in _prev_results}
                curr_map = {(r["symbol"], r["zone_center"]): r for r in scan_results[:20]}

                new_items = [(k, v) for k, v in curr_map.items() if k not in prev_map]
                gone_items = [(k, v) for k, v in prev_map.items() if k not in curr_map]
                changed_items = []
                for k, v in curr_map.items():
                    if k in prev_map:
                        pv = prev_map[k]
                        if pv["motion"] != v["motion"] or abs(pv["flux"] - v["flux"]) > 0.3:
                            changed_items.append((k, v, pv))

                if new_items:
                    st.markdown("**🆕 新增结构**")
                    for (sym, zone), r in new_items:
                        st.markdown(f"  - {sym} Zone {zone:.0f} · {r['motion']} · 关注度 {r['score']:.0f}分")

                if changed_items:
                    st.markdown("**🔄 状态变化**")
                    for (sym, zone), r, pv in changed_items:
                        motion_change = f"{pv['motion']} → {r['motion']}" if pv['motion'] != r['motion'] else ""
                        flux_change = f"通量 {pv['flux']:+.2f} → {r['flux']:+.2f}" if abs(pv['flux'] - r['flux']) > 0.3 else ""
                        parts = [p for p in [motion_change, flux_change] if p]
                        st.markdown(f"  - {sym} Zone {zone:.0f} · {' · '.join(parts)}")

                if gone_items:
                    st.markdown("**❌ 退出 Top 20**")
                    for (sym, zone), r in gone_items:
                        st.markdown(f"  - {sym} Zone {zone:.0f} · 原关注度 {r['score']:.0f}分")

                if not new_items and not changed_items and not gone_items:
                    st.caption("与上次扫描相比无变化")
            else:
                st.caption(f"首次扫描（{_today_key}），下次扫描将自动对比变化")

            # 保存本次结果供下次对比
            st.session_state["prev_scan_results"] = scan_results[:20]
            st.session_state["prev_scan_date"] = _today_key
        else:
            st.warning("🔍 未扫描到活跃结构")
            st.caption("可能原因：① 数据源无数据（检查 MySQL 连接或 data/ 目录）② 当前灵敏度下无满足条件的结构 — 试试侧栏调为「精细」")

        st.markdown("---")

    # ── 当前品种结构展示（保留原有内容）──
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
        st.info("📡 当前时间范围内没有显著结构 — 试试侧栏扩大时间范围或降低灵敏度")
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

        # ── 检索颗粒度（独立于侧栏灵敏度）──
        col_gran, col_scope, col_btn = st.columns([1, 2, 1])
        with col_gran:
            search_granularity = st.select_slider(
                "检索颗粒度",
                options=["粗粒度", "中等", "细粒度"],
                value="细粒度",
                help="粗粒度=只匹配大结构(高振幅/长周期)，细粒度=捕捉小波动结构",
            )
            search_sens_map = {
                "粗粒度": {"min_amp": 0.06, "min_dur": 6, "min_cycles": 3},
                "中等":   {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2},
                "细粒度": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2},
            }
            search_sens = search_sens_map[search_granularity]

        with col_scope:
            search_scope = st.radio(
                "检索范围",
                ["仅当前品种", "全品种（MySQL + CSV）"],
                horizontal=True,
                help="全品种模式会加载所有可用品种的历史数据进行对比",
            )
            is_cross_symbol = "全品种" in search_scope

        # ── 精细检索条件 ──
        with st.expander("🎛️ 精细检索条件（可选）", expanded=False):
            fin_col1, fin_col2, fin_col3 = st.columns(3)

            with fin_col1:
                date_col1, date_col2 = st.columns(2)
                with date_col1:
                    search_date_start = st.date_input(
                        "起始日期",
                        value=datetime.now().date() - timedelta(days=search_years * 365),
                        key="search_date_start",
                    )
                with date_col2:
                    search_date_end = st.date_input(
                        "结束日期",
                        value=datetime.now().date(),
                        key="search_date_end",
                    )
                search_zone_range = st.slider(
                    "Zone 价位范围",
                    min_value=0.0, max_value=100000.0,
                    value=(0.0, 100000.0),
                    step=100.0,
                    key="search_zone_range",
                    help="筛选 Zone price_center 在此范围内的案例",
                )

            with fin_col2:
                search_dir_filter = st.multiselect(
                    "方向筛选",
                    ["📈 上涨(up)", "📉 下跌(down)", "➡️ 不明(unclear)"],
                    default=[],
                    key="search_dir_filter",
                    help="只看指定方向的案例，留空=全部",
                )
                search_contrast_filter = st.multiselect(
                    "反差类型",
                    ["恐慌(panic)", "过剩(oversupply)", "政策(policy)",
                     "流动性(liquidity)", "投机(speculation)", "未知(unknown)"],
                    default=[],
                    key="search_contrast_filter",
                    help="筛选 zone.context_contrast 类型",
                )
                search_motion_filter = st.multiselect(
                    "运动状态",
                    ["🔻 破缺(→breakdown)", "✅ 确认(→confirmation)",
                     "⚖️ 稳定(stable)", "🔄 形成中(forming)"],
                    default=[],
                    key="search_motion_filter",
                    help="筛选结构的 phase_tendency",
                )

            with fin_col3:
                search_min_sim = st.slider(
                    "最小相似度",
                    min_value=0.0, max_value=1.0,
                    value=0.0, step=0.05,
                    key="search_min_sim",
                    help="过滤掉相似度低于此值的案例",
                )
                search_sort_by = st.radio(
                    "结果排序",
                    ["按相似度", "按后续涨幅", "按日期"],
                    key="search_sort_by",
                    help="选择检索结果的排序方式",
                )

        with col_btn:
            run_search = st.button("🚀 开始检索", type="primary", use_container_width=True)

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
            search_symbols = ALL_SYMBOLS if is_cross_symbol else [selected_symbol]
            all_candidates = []
            total_syms = len(search_symbols)
            _t0 = _time.time()

            progress = st.progress(0, text=f"准备检索 {total_syms} 个品种...")

            for si, sym in enumerate(search_symbols):
                elapsed = _time.time() - _t0
                if si > 0:
                    eta = elapsed / si * (total_syms - si)
                    time_text = f"⏱️ 已用 {elapsed:.0f}s · 预估剩余 {eta:.0f}s"
                else:
                    time_text = "⏱️ 启动中..."
                progress.progress(
                    si / max(total_syms, 1),
                    text=f"[{si+1}/{total_syms}] {sym} ({symbol_name(sym)}) · {time_text}"
                )

                sym_bars = load_bars(sym)
                if not sym_bars or len(sym_bars) < 30:
                    continue

                sym_config = CompilerConfig(
                    min_amplitude=search_sens["min_amp"],
                    min_duration=search_sens["min_dur"],
                    min_cycles=search_sens["min_cycles"],
                    adaptive_pivots=True, fractal_threshold=0.34,
                )
                sym_result = compile_full(sym_bars, sym_config, symbol=sym)
                if not sym_result.structures:
                    continue

                for hs in sym_result.structures:
                    # 跳过自身（同品种同时间）
                    if sym == selected_symbol and hs is query_st:
                        continue
                    # 同品种跳过时间重叠
                    if sym == selected_symbol:
                        if hs.t_end and query_st.t_start and hs.t_end >= query_st.t_start:
                            continue

                    sc = similarity(query_st, hs)

                    # 计算前向表现
                    direction, move = "unclear", 0.0
                    if hs.t_end:
                        outcome_start = hs.t_end + timedelta(days=3)
                        outcome_end = outcome_start + timedelta(days=30)
                        future = [b for b in sym_bars if outcome_start <= b.timestamp <= outcome_end]
                        if future:
                            start_p = future[0].open
                            if start_p > 0:
                                peak = max(b.high for b in future)
                                trough = min(b.low for b in future)
                                up = (peak - start_p) / start_p
                                down = (start_p - trough) / start_p
                                direction = "up" if up >= down else "down"
                                move = max(up, down)

                    all_candidates.append({
                        "structure": hs,
                        "score": sc,
                        "direction": direction,
                        "move": move,
                        "symbol": sym,
                        "symbol_name": symbol_name(sym),
                    })

            progress.progress(0.95, text="应用精细筛选...")

            # ── 应用精细筛选 ──
            filtered_candidates = []
            _min_sim = st.session_state.get("search_min_sim", 0.0)
            _d_start = st.session_state.get("search_date_start")
            _d_end = st.session_state.get("search_date_end")
            _zr = st.session_state.get("search_zone_range", (0.0, 100000.0))
            _dir_f_raw = st.session_state.get("search_dir_filter", [])
            _contrast_f_raw = st.session_state.get("search_contrast_filter", [])
            _motion_f_raw = st.session_state.get("search_motion_filter", [])

            # 从中文标签中提取英文 key（使用模块级 _extract_key）
            _dir_f = [_extract_key(v) for v in _dir_f_raw]
            _contrast_f = [_extract_key(v) for v in _contrast_f_raw]
            _motion_f = [_extract_key(v) for v in _motion_f_raw]

            for c in all_candidates:
                hs = c["structure"]
                if c["score"].total < _min_sim:
                    continue
                if hs.t_start:
                    d = hs.t_start.date()
                    if _d_start and d < _d_start:
                        continue
                    if _d_end and d > _d_end:
                        continue
                if not (_zr[0] <= hs.zone.price_center <= _zr[1]):
                    continue
                if _dir_f and c["direction"] not in _dir_f:
                    continue
                if _contrast_f:
                    hs_contrast = hs.zone.context_contrast.value if hs.zone else ""
                    if hs_contrast not in _contrast_f:
                        continue
                if _motion_f:
                    hs_motion = hs.motion.phase_tendency if hs.motion else ""
                    if hs_motion not in _motion_f:
                        continue
                filtered_candidates.append(c)

            all_candidates = filtered_candidates

            # 排序
            _sort_by = st.session_state.get("search_sort_by", "按相似度")
            if _sort_by == "按相似度":
                all_candidates.sort(key=lambda c: c["score"].total, reverse=True)
            elif _sort_by == "按后续涨幅":
                all_candidates.sort(key=lambda c: c["move"], reverse=True)
            elif _sort_by == "按日期":
                all_candidates.sort(key=lambda c: c["structure"].t_start or datetime.min, reverse=True)

            progress.progress(1.0, text=f"✅ 检索完成 · {_time.time() - _t0:.1f}s · {len(all_candidates)} 个匹配")
            top_cases = all_candidates[:top_k]

            if top_cases:
                # 品种来源统计
                sym_distribution = {}
                for c in top_cases:
                    s = c["symbol"]
                    sym_distribution[s] = sym_distribution.get(s, 0) + 1

                st.markdown("---")
                scope_label = f"全品种 {len(search_symbols)} 个" if is_cross_symbol else selected_symbol
                st.markdown(f"**找到 {len(top_cases)} 个历史相似案例**（检索范围: {scope_label} · 颗粒度: {search_granularity}）")

                # ── 品种来源分布 ──
                if is_cross_symbol and len(sym_distribution) > 1:
                    dist_text = " · ".join(
                        f"**{s}**({symbol_name(s)}) ×{n}"
                        for s, n in sorted(sym_distribution.items(), key=lambda x: -x[1])
                    )
                    st.caption(f"来源分布: {dist_text}")

                # ── 统计面板（增加中位数收益）──
                up_cases = [c for c in top_cases if c["direction"] == "up"]
                down_cases = [c for c in top_cases if c["direction"] == "down"]
                all_moves = [c["move"] for c in top_cases if c["move"] > 0]
                n = len(top_cases)

                stat_cols = st.columns(6)
                stat_cols[0].metric("总案例", n)
                stat_cols[1].metric("上涨", f"{len(up_cases)} ({len(up_cases)/n:.0%})")
                stat_cols[2].metric("下跌", f"{len(down_cases)} ({len(down_cases)/n:.0%})")
                if up_cases:
                    avg_up = sum(c["move"] for c in up_cases) / len(up_cases)
                    stat_cols[3].metric("平均涨幅", f"{avg_up:.1%}")
                if down_cases:
                    avg_down = sum(c["move"] for c in down_cases) / len(down_cases)
                    stat_cols[4].metric("平均跌幅", f"{avg_down:.1%}")
                if all_moves:
                    median_move = sorted(all_moves)[len(all_moves) // 2]
                    stat_cols[5].metric("中位数收益", f"{median_move:.1%}")

                # ── 实时过滤控件 ──
                st.markdown("---")
                rt_col1, rt_col2 = st.columns(2)
                with rt_col1:
                    rt_dir_filter = st.multiselect(
                        "🔎 按方向筛选显示",
                        ["📈 上涨(up)", "📉 下跌(down)", "➡️ 不明(unclear)"],
                        default=[],
                        key="rt_dir_filter",
                    )
                with rt_col2:
                    rt_sort = st.selectbox(
                        "🔃 按相似度排序",
                        ["相似度降序", "相似度升序"],
                        key="rt_sort",
                    )

                display_cases = top_cases
                if rt_dir_filter:
                    rt_dir_keys = [_extract_key(v) for v in rt_dir_filter]
                    display_cases = [c for c in display_cases if c["direction"] in rt_dir_keys]
                if rt_sort == "相似度升序":
                    display_cases = sorted(display_cases, key=lambda c: c["score"].total)

                st.markdown("---")

                # ── 逐案例展示（增加反差类型 + 运动状态标签）──
                for i, case in enumerate(display_cases):
                    hs = case["structure"]
                    sc = case["score"]
                    direction = case["direction"]
                    move = case["move"]
                    case_sym = case["symbol"]
                    case_sym_name = case["symbol_name"]

                    direction_icon = "📈" if direction == "up" else "📉" if direction == "down" else "➡️"

                    # 反差类型 + 运动状态标签
                    contrast_val = hs.zone.context_contrast.value if hs.zone else ""
                    motion_val = hs.motion.phase_tendency if hs.motion else ""
                    tag_parts = []
                    if contrast_val:
                        tag_parts.append(f"[{contrast_val}]")
                    if motion_val:
                        tag_parts.append(f"[{motion_val}]")
                    tag_str = " ".join(tag_parts) + " " if tag_parts else ""

                    # 标题包含品种信息（全品种模式下）
                    sym_tag = f"[{case_sym}] " if is_cross_symbol else ""
                    with st.expander(
                        f"{direction_icon} #{i+1}  {sym_tag}{tag_str}"
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
                                "当前", f"历史({case_sym})",
                            )
                            st.dataframe(diff_df, hide_index=True, use_container_width=True)

                        with col_right:
                            st.markdown("**相似度分层**")
                            sim_cols = st.columns(2)
                            sim_cols[0].metric("几何", f"{sc.geometric:.0%}")
                            sim_cols[1].metric("关系", f"{sc.relational:.0%}")

                            st.markdown("**结构特征**")
                            st.caption(f"品种: {case_sym} ({case_sym_name})\n\n"
                                      f"Cycle: {hs.cycle_count} · "
                                      f"SR: {hs.avg_speed_ratio:.2f} · "
                                      f"TR: {hs.avg_time_ratio:.2f} · "
                                      f"BW: {hs.zone.relative_bandwidth:.3f}")

                            # 标签展示
                            if contrast_val or motion_val:
                                st.markdown(f"**反差类型**: {contrast_val or '—'} · "
                                           f"**运动状态**: {motion_val or '—'}")

                            if direction != "unclear":
                                st.markdown(f"**后续走势**: {direction} {move:.1%}")

                        # 历史段 K 线
                        if hs.t_start and hs.t_end:
                            case_bars = load_bars(case_sym)
                            margin = timedelta(days=15)
                            hist_bars = [b for b in case_bars
                                        if hs.t_start - margin <= b.timestamp <= hs.t_end + margin]
                            if hist_bars:
                                fig = make_candlestick(hist_bars,
                                    title=f"{case_sym} {hs.t_start:%Y-%m-%d} ~ {hs.t_end:%Y-%m-%d}")
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

                # 跨品种洞察
                if is_cross_symbol and len(sym_distribution) > 1:
                    st.markdown("---")
                    st.markdown("#### 🔗 跨品种洞察")
                    for sym, count in sym_distribution.items():
                        sym_cases = [c for c in top_cases if c["symbol"] == sym]
                        sym_up = sum(1 for c in sym_cases if c["direction"] == "up")
                        sym_down = sum(1 for c in sym_cases if c["direction"] == "down")
                        avg_sim = sum(c["score"].total for c in sym_cases) / len(sym_cases)
                        st.markdown(
                            f"**{sym} ({symbol_name(sym)})** × {count} 例 · "
                            f"平均相似度 {avg_sim:.0%} · "
                            f"📈{sym_up} / 📉{sym_down}"
                        )

            else:
                st.warning("🔍 匹配不足 — 试试：① 降低「最小相似度」阈值 ② 切换到「粗粒度」③ 扩大检索范围到「全品种」④ 增加历史检索年数")


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
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
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
            entries = []
            with open(journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
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


# ═══════════════════════════════════════════════════════════
# Tab 6: 合约检索 — 输入任意合约代码，实时拉取 + 编译
# ═══════════════════════════════════════════════════════════

with tabs[5]:
    st.markdown("#### 🔎 合约检索")
    st.caption("输入任意合约代码（如 cu2507、rb2510、cad），从新浪实时拉取数据 → 编译结构 → 展示分析")

    # ── 合约选择 ──
    contracts = available_contracts()

    col_input, col_freq = st.columns([3, 1])
    with col_input:
        # 预置合约下拉 + 自由输入
        all_presets = []
        for group, codes in contracts.items():
            for c in codes:
                all_presets.append(f"{c} ({group})")

        contract_mode = st.radio(
            "选择方式",
            ["📋 预置合约", "✏️ 自由输入"],
            horizontal=True,
            key="contract_mode",
        )

        if contract_mode == "📋 预置合约":
            preset_sel = st.selectbox(
                "选择合约",
                all_presets,
                key="preset_contract",
            )
            # 提取代码
            contract_code = preset_sel.split(" ")[0].strip()
        else:
            contract_code = st.text_input(
                "合约代码",
                value="cu0",
                placeholder="输入合约代码，如 cu2507、rb2510、cad、usdcny",
                key="free_contract",
            ).strip().lower()

    with col_freq:
        freq = st.selectbox("数据频率", ["日线", "5分钟线"], key="contract_freq")
        freq_code = "5m" if freq == "5分钟线" else "1d"

        # 数据源识别
        if contract_code:
            src = detect_source(contract_code)
            src_labels = {"inner": "🇨🇳 国内期货", "global": "🌍 外盘期货", "fx": "💱 外汇"}
            st.caption(f"数据源: {src_labels.get(src, src)}")

    # ── 编译参数 ──
    col_sens, col_btn = st.columns([3, 1])
    with col_sens:
        contract_sensitivity = st.select_slider(
            "结构灵敏度",
            options=["粗糙", "标准", "精细"],
            value="标准",
            key="contract_sensitivity",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        run_fetch = st.button("🚀 拉取并编译", type="primary", use_container_width=True, key="btn_contract_fetch")

    # ── 执行 ──
    if run_fetch and contract_code:

        with st.spinner(f"📡 正在从新浪拉取 {contract_code} 的{freq}数据..."):
            _t0 = _time.time()
            bars_data = sina_fetch_bars(contract_code, freq=freq_code, timeout=15)
            fetch_time = _time.time() - _t0

        if not bars_data:
            st.error(f"❌ 未能获取 {contract_code} 的数据")
            st.caption("可能原因：① 合约代码不存在 ② 新浪 API 暂时不可用 ③ 该合约已退市")
        else:
            st.success(f"✅ 获取 {len(bars_data)} 条 {freq}数据 · 用时 {fetch_time:.1f}s · "
                       f"{bars_data[0].timestamp:%Y-%m-%d} → {bars_data[-1].timestamp:%Y-%m-%d}")

            # 编译结构
            _sens_map = {
                "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3},
                "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2},
                "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2},
            }
            _s = _sens_map[contract_sensitivity]

            with st.spinner("🔧 正在编译价格结构..."):
                cfg = CompilerConfig(
                    min_amplitude=_s["min_amp"], min_duration=_s["min_dur"],
                    min_cycles=_s["min_cycles"],
                    adaptive_pivots=True, fractal_threshold=0.34,
                )
                comp_result = compile_full(bars_data, cfg, symbol=contract_code.upper())

            if not comp_result.structures:
                st.warning("🔍 未识别到显著结构 — 试试降低灵敏度到「精细」")
            else:
                n_structs = len(comp_result.structures)
                n_zones = len(comp_result.zones)
                last_price = bars_data[-1].close

                # ── 概要指标 ──
                st.markdown("---")
                metric_cols = st.columns(6)
                metric_cols[0].metric("最新价", f"{last_price:.2f}")
                metric_cols[1].metric("结构数", n_structs)
                metric_cols[2].metric("Zone 数", n_zones)
                metric_cols[3].metric("数据条数", len(bars_data))
                ss_reliable = sum(1 for ss in comp_result.system_states if ss.is_reliable)
                metric_cols[4].metric("可信结构", ss_reliable)
                blind_count = sum(1 for ss in comp_result.system_states if ss.projection.is_blind)
                metric_cols[5].metric("⚠️ 高压缩", blind_count)

                # ── 结构卡片 ──
                ranked = comp_result.ranked_structures
                breaking = [s for s in ranked if s.motion and "breakdown" in s.motion.phase_tendency]
                confirming = [s for s in ranked if s.motion and "confirmation" in s.motion.phase_tendency]
                forming = [s for s in ranked if s.motion and s.motion.phase_tendency in ("forming", "stable", "")]

                if breaking:
                    st.markdown("**🔴 正在破缺**")
                    for s in breaking[:3]:
                        flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                        pos = _price_vs_zone(last_price, s.zone.price_center, s.zone.bandwidth)
                        st.markdown(f"""
                        <div class="structure-card danger">
                            <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                            <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                            · {motion_badge(s.motion.phase_tendency)}
                            · <span class="meta-text">通量 {flux}</span>
                            <div class="meta-text">{pos}</div>
                            <div class="narrative-text">{s.narrative_context or ''}</div>
                        </div>
                        """, unsafe_allow_html=True)

                if confirming:
                    st.markdown("**🟢 趋向确认**")
                    for s in confirming[:3]:
                        flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                        pos = _price_vs_zone(last_price, s.zone.price_center, s.zone.bandwidth)
                        st.markdown(f"""
                        <div class="structure-card ok">
                            <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                            <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                            · {motion_badge(s.motion.phase_tendency)}
                            · <span class="meta-text">通量 {flux}</span>
                            <div class="meta-text">{pos}</div>
                            <div class="narrative-text">{s.narrative_context or ''}</div>
                        </div>
                        """, unsafe_allow_html=True)

                if forming:
                    st.markdown("**🔵 形成中**")
                    for s in forming[:5]:
                        proj_warn = " · ⚠️ 高压缩" if (s.projection and s.projection.is_blind) else ""
                        tendency = s.motion.phase_tendency if s.motion else 'unknown'
                        pos = _price_vs_zone(last_price, s.zone.price_center, s.zone.bandwidth)
                        st.markdown(f"""
                        <div class="structure-card">
                            <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                            <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                            · {motion_badge(tendency)}{proj_warn}
                            <div class="meta-text">{pos}</div>
                            <div class="narrative-text">{s.narrative_context or ''}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # ── K 线图 + Zone 标注 ──
                st.markdown("---")
                st.markdown(f"**K 线图 · {contract_code.upper()}**")
                fig = make_candlestick(bars_data[-120:])
                for s in ranked[:5]:
                    fig.add_hline(y=s.zone.price_center, line_dash="dot",
                                 line_color="#4a90d9", opacity=0.5,
                                 annotation_text=f"Zone {s.zone.price_center:.0f}")
                    fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                                 fillcolor="#4a90d9", opacity=0.08, line_width=0)
                st.plotly_chart(fig, use_container_width=True)

                # ── 不变量汇总 ──
                if ranked:
                    with st.expander("📊 结构不变量详情"):
                        inv_rows = []
                        for s in ranked[:10]:
                            inv = s.invariants or {}
                            m = s.motion
                            inv_rows.append({
                                "Zone": f"{s.zone.price_center:.0f}",
                                "Cycle数": s.cycle_count,
                                "速度比": f"{s.avg_speed_ratio:.2f}",
                                "时间比": f"{s.avg_time_ratio:.2f}",
                                "带宽": f"{s.zone.relative_bandwidth:.3f}",
                                "运动": m.phase_tendency if m else "—",
                                "通量": f"{m.conservation_flux:+.2f}" if m else "—",
                                "反差": s.zone.context_contrast.value,
                            })
                        st.dataframe(pd.DataFrame(inv_rows), hide_index=True, use_container_width=True)

    elif run_fetch:
        st.warning("请输入合约代码")


# ═══════════════════════════════════════════════════════════
# Tab 7: 多时间维度对比
# ═══════════════════════════════════════════════════════════

with tabs[6]:
    from src.multitimeframe.comparator import (
        resample_bars,
        cross_timeframe_consistency,
    )

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

    def _load_and_compile_mtf(symbol: str, freq: str, start: str, end: str, config: CompilerConfig):
        """加载数据并编译"""
        bars = []

        # 优先尝试 MySQL
        try:
            password = os.getenv('MYSQL_PASSWORD', 'root')
            loader = MySQLLoader(host="localhost", user="root", password=password, db="sina")
            bars = loader.get(symbol=symbol.upper(), start=start, end=end, freq=freq)
        except Exception:
            pass

        # 降级到新浪
        if not bars:
            try:
                bars = sina_fetch_bars(symbol, freq=freq, timeout=15)
                if bars and start:
                    s = datetime.strptime(start, "%Y-%m-%d")
                    e = datetime.strptime(end, "%Y-%m-%d") if end else datetime.now()
                    bars = [b for b in bars if s <= b.timestamp <= e]
            except Exception:
                pass

        if not bars:
            return None, []

        result = compile_full(bars, config, symbol=symbol.upper())
        return result, bars

    def _make_candlestick_mtf(bars: list[Bar], title: str = "") -> go.Figure:
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

    def _render_structure_card_mtf(s, freq_label: str, last_price: float):
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
            result_1d, bars_1d = _load_and_compile_mtf(mtf_symbol, "1d", start_str, end_str, config_1d)

        # ── 5分钟线编译 ──
        with st.spinner(f"📡 编译 {mtf_symbol} 5分钟线结构..."):
            result_5m, bars_5m = _load_and_compile_mtf(mtf_symbol, "5m", start_str, end_str, config_5m)

        # ── 1小时线（从5分钟重采样）──
        result_1h, bars_1h = None, []
        if bars_5m:
            with st.spinner(f"🔄 重采样为1小时线并编译..."):
                bars_1h = resample_bars(bars_5m, "1h")
                if bars_1h:
                    result_1h = compile_full(bars_1h, config_1h, symbol=mtf_symbol.upper())

        # ═══════════════════════════════════════════════════════════
        # 结果展示
        # ═══════════════════════════════════════════════════════════

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

        # Section 1: 各维度结构概览
        st.markdown("##### 📊 各时间维度结构概览")

        last_price_1d = bars_1d[-1].close if bars_1d else 0
        last_price_5m = bars_5m[-1].close if bars_5m else last_price_1d

        tab_1d, tab_1h, tab_5m = st.tabs(["📅 日线", "🕐 1小时", "⏱️ 5分钟"])

        with tab_1d:
            if has_1d:
                for s in result_1d.ranked_structures[:5]:
                    _render_structure_card_mtf(s, "日线", last_price_1d)
            else:
                st.info("日线无结构")

        with tab_1h:
            if has_1h:
                for s in result_1h.ranked_structures[:5]:
                    _render_structure_card_mtf(s, "1H", last_price_5m)
            else:
                st.info("1小时线无结构（需要5分钟数据）")

        with tab_5m:
            if has_5m:
                for s in result_5m.ranked_structures[:5]:
                    _render_structure_card_mtf(s, "5M", last_price_5m)
            else:
                st.info("5分钟线无结构")

        # Section 2: 跨维度一致性分析
        st.markdown("---")
        st.markdown("##### 🔗 跨维度一致性分析")

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
                    - 通量: {f'{s_a.motion.conservation_flux:+.2f}' if s_a.motion else '—'}
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
                    - 通量: {f'{s_b.motion.conservation_flux:+.2f}' if s_b.motion else '—'}
                    """)

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

        # Section 3: K 线并排对比
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
                    fig = _make_candlestick_mtf(bars_1d[-120:], f"{mtf_symbol.upper()} 日线")
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
                    fig = _make_candlestick_mtf(bars_5m[-500:], f"{mtf_symbol.upper()} 5分钟")
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
                    fig = _make_candlestick_mtf(bars_1h[-200:], f"{mtf_symbol.upper()} 1小时")
                    for s in result_1h.ranked_structures[:3]:
                        fig.add_hline(y=s.zone.price_center, line_dash="dot",
                                     line_color="#4caf50", opacity=0.6,
                                     annotation_text=f"Zone {s.zone.price_center:.0f}")
                        fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                                     fillcolor="#4caf50", opacity=0.08, line_width=0)
                    st.plotly_chart(fig, use_container_width=True)

        # Section 4: 不变量雷达图对比
        if has_1d and (has_5m or has_1h):
            st.markdown("---")
            st.markdown("##### 🕸️ 不变量雷达图对比")

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

        # Section 5: 研究建议
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

            dir_mismatch = [m for m in all_matches if not m.direction_match]
            if dir_mismatch:
                suggestions.append(f"⚠️ **{len(dir_mismatch)} 对方向矛盾** — 大尺度看涨但小尺度看跌（或反之），通常是回调/反弹信号")

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


# ═══════════════════════════════════════════════════════════
# Tab 8: v3.0 质量与共振
# ═══════════════════════════════════════════════════════════

with tabs[7]:
    from src.quality import stratify_structures, QualityTier
    from src.resonance import ResonanceDetector
    from src.lifecycle import LifecycleTracker
    from src.intraday_rhythm import IntradayRhythmAnalyzer, SESSION_LABELS

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

                        # 概要指标
                        col_a, col_b, col_c, col_d, col_total = st.columns(5)
                        col_a.metric("A层·高质量", strat.stats.get("A", 0))
                        col_b.metric("B层·中等", strat.stats.get("B", 0))
                        col_c.metric("C层·低质量", strat.stats.get("C", 0))
                        col_d.metric("D层·噪声", strat.stats.get("D", 0))
                        col_total.metric("总计", strat.total)

                        # 分层饼图
                        fig_pie = go.Figure(data=[go.Pie(
                            labels=["A层", "B层", "C层", "D层"],
                            values=[strat.stats.get(t, 0) for t in ["A", "B", "C", "D"]],
                            marker_colors=["#1b5e20", "#0d47a1", "#e65100", "#b71c1c"],
                            hole=0.4,
                        )])
                        fig_pie.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0))
                        st.plotly_chart(fig_pie, use_container_width=True)

                        # 各层详情
                        for tier_val in ["A", "B", "C", "D"]:
                            items = strat.tiers.get(tier_val, [])
                            if not items:
                                continue

                            tier = QualityTier(tier_val)
                            with st.expander(f"{tier.label} ({len(items)} 个)", expanded=(tier_val == "A")):
                                for s, qa in items[:8]:
                                    breakdown = qa.breakdown
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
        st.caption("追踪结构从 formation → confirmation → breakdown 的完整轨迹")

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
