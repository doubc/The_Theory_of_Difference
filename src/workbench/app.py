"""
价格结构研究工作台 v4.0

升级亮点：
  - 全新仪表盘首页（品种热力图、今日精选、快速入口）
  - 改进的侧栏导航（分组、搜索、收藏）
  - 更清晰的 Tab 布局和命名
  - 移动端友好
  - 暗色主题优化

运行: streamlit run src/workbench/app.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
import pandas as pd

from src.data.loader import Bar, CSVLoader, MySQLLoader
from src.data.symbol_meta import symbol_name, load_symbol_meta
from src.compiler.pipeline import compile_full, CompilerConfig

from src.workbench.shared import CSS_STYLE, SENS_MAP
from src.workbench.data_layer import (
    get_mysql_engine, discover_mysql_symbols, discover_csv_symbols,
    get_all_available_symbols, load_bars, compile_structures,
)

# ─── 页面配置 ──────────────────────────────────────────────

st.set_page_config(
    page_title="价格结构研究工作台 v4",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 增强 CSS ──────────────────────────────────────────────

ENHANCED_CSS = """
<style>
    /* 全局字体和间距优化 */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* 侧栏样式优化 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a192f 0%, #112240 100%);
    }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #ccd6f6 !important;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown li {
        color: #8892b0 !important;
    }

    /* Tab 样式优化 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background: #0a192f;
        border-radius: 10px 10px 0 0;
        padding: 4px 4px 0 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 16px;
        font-weight: 600;
        font-size: 0.9em;
    }
    .stTabs [aria-selected="true"] {
        background: #1d3557 !important;
        color: #64ffda !important;
    }

    /* 指标卡片 */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 16px;
        border-left: 4px solid #4a90d9;
    }
    [data-testid="stMetric"] label {
        color: #8892b0 !important;
        font-size: 0.85em !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #ccd6f6 !important;
        font-size: 1.6em !important;
    }

    /* 按钮优化 */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
        border: 1px solid #233554;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(100, 255, 218, 0.15);
        border-color: #64ffda;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1d3557 0%, #457b9d 100%);
        border-color: #64ffda;
        color: #64ffda;
    }

    /* 信息框优化 */
    .stAlert {
        border-radius: 10px;
    }

    /* 分割线 */
    hr {
        border-color: #233554 !important;
    }

    /* 数据框优化 */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    /* 选框优化 */
    .stSelectbox > div > div {
        border-radius: 8px;
        border-color: #233554;
    }

    /* 多选框优化 */
    .stMultiSelect > div > div {
        border-radius: 8px;
        border-color: #233554;
    }

    /* 滑块优化 */
    .stSlider > div > div > div {
        color: #64ffda;
    }

    /* 侧栏导航分组 */
    .nav-group {
        margin: 12px 0 8px 0;
        padding-bottom: 4px;
        border-bottom: 1px solid #233554;
    }
    .nav-group-title {
        font-size: 0.75em;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64ffda;
        font-weight: 700;
    }

    /* 品种选择器优化 */
    .symbol-chip {
        display: inline-block;
        padding: 4px 12px;
        margin: 2px 4px;
        border-radius: 16px;
        font-size: 0.82em;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s;
        border: 1px solid #233554;
        background: #112240;
        color: #8892b0;
    }
    .symbol-chip:hover {
        border-color: #64ffda;
        color: #64ffda;
    }
    .symbol-chip.active {
        background: #1d3557;
        border-color: #64ffda;
        color: #64ffda;
    }

    /* 运动标签 */
    .motion-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .badge-breakout { background: rgba(239,83,80,0.15); color: #ff6b6b; }
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

    /* 页脚 */
    .footer {
        text-align: center;
        padding: 20px 0;
        color: #495057;
        font-size: 0.82em;
        border-top: 1px solid #e9ecef;
        margin-top: 40px;
    }

    /* 响应式调整 */
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] {
            padding: 6px 10px;
            font-size: 0.8em;
        }
        [data-testid="stMetric"] {
            padding: 10px;
        }
    }
</style>
"""

st.markdown(ENHANCED_CSS, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 辅助函数（从原 app.py 保留）
# ═══════════════════════════════════════════════════════════

def _safe_float(v, default=0.0):
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _safe_int(v, default=0):
    try:
        if v is None:
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def _safe_str(v, default=""):
    try:
        if v is None:
            return default
        return str(v)
    except Exception:
        return default


def _extract_zone(structure):
    zone = getattr(structure, "zone", None)
    if zone is None:
        return None, 0.0, 0.0
    center = _safe_float(getattr(zone, "price_center", 0.0), 0.0)
    half_width = _safe_float(getattr(zone, "half_width", 0.0), 0.0)
    return zone, center, half_width


def _extract_motion(structure):
    motion = getattr(structure, "motion", None)
    if motion is None:
        return None, "unknown", 0.0, "unknown"
    phase = _safe_str(getattr(motion, "phase_tendency", "unknown"), "unknown")
    flux = _safe_float(getattr(motion, "conservation_flux", 0.0), 0.0)
    movement_type = _safe_str(getattr(motion, "movement_type", "unknown"), "unknown")
    return motion, phase, flux, movement_type


def _extract_cycles(structure):
    cycles = getattr(structure, "cycles", None) or []
    return cycles


def _extract_test_amplitudes(cycles):
    amplitudes = []
    for c in cycles:
        amp = None
        for attr in ("amplitude", "price_amplitude", "abs_amplitude", "delta"):
            if hasattr(c, attr):
                amp = getattr(c, attr, None)
                if amp is not None:
                    break
        if amp is not None:
            try:
                amplitudes.append(abs(float(amp)))
            except Exception:
                pass
    return amplitudes


def _extract_position_tag(current_price, zone_center, zone_half_width):
    if zone_half_width <= 0:
        return "unknown"
    lower = zone_center - zone_half_width
    upper = zone_center + zone_half_width
    if lower <= current_price <= upper:
        return "inside"
    dist = abs(current_price - zone_center) / max(zone_half_width, 1e-9)
    if current_price > upper:
        return "far_above" if dist >= 3 else "above"
    if current_price < lower:
        return "far_below" if dist >= 3 else "below"
    return "unknown"


def _extract_duration_days(structure):
    zone = getattr(structure, "zone", None)
    if zone is None:
        return 0
    start = end = None
    for attr in ("start_date", "first_touch_date", "t_start"):
        if hasattr(zone, attr):
            start = getattr(zone, attr, None)
            if start is not None:
                break
    for attr in ("end_date", "last_touch_date", "t_end"):
        if hasattr(zone, attr):
            end = getattr(zone, attr, None)
            if end is not None:
                break
    try:
        if start is not None and end is not None:
            return max(int((end - start).days), 0)
    except Exception:
        pass
    return 0


def _extract_time_since_last_test(structure, bars):
    cycles = _extract_cycles(structure)
    if not cycles or not bars:
        return 0
    last_ts = None
    for c in reversed(cycles):
        for attr in ("end_time", "timestamp", "t_end", "end_date"):
            if hasattr(c, attr):
                last_ts = getattr(c, attr, None)
                if last_ts is not None:
                    break
        if last_ts is not None:
            break
    if last_ts is None:
        zone = getattr(structure, "zone", None)
        if zone is not None:
            for attr in ("last_touch_date", "end_date", "t_end"):
                if hasattr(zone, attr):
                    last_ts = getattr(zone, attr, None)
                    if last_ts is not None:
                        break
    try:
        if last_ts is not None:
            return max(int((bars[-1].timestamp - last_ts).days), 0)
    except Exception:
        pass
    return 0


def _pick_current_structure(result):
    structures = getattr(result, "structures", None) or getattr(result, "ranked_structures", None) or []
    if not structures:
        return None
    def _sort_key(s):
        for attr in ("t_end", "end_date"):
            v = getattr(s, attr, None)
            if v is not None:
                return v
        z = getattr(s, "zone", None)
        if z is not None:
            for attr in ("t_end", "end_date", "last_touch_date", "start_date", "first_touch_date"):
                v = getattr(z, attr, None)
                if v is not None:
                    return v
        return 0
    try:
        return sorted(structures, key=_sort_key)[-1]
    except Exception:
        return structures[-1]


def _build_current_structure_dict(result, bars=None) -> dict:
    empty = {
        "symbol": "", "has_data": False,
        "phase": "unknown", "activity": 0, "quality": 0, "quality_tier": "D",
        "position_tag": "unknown", "test_count": 0, "duration_days": 0,
        "time_since_last_test": 0, "flux": 0.0, "current_price": 0.0,
        "zone_center": 0.0, "zone_half_width": 0.0, "movement_type": "unknown",
        "test_amplitudes": [], "deviation_activity": 0, "quality_score": 0,
        "center": 0.0, "half_width": 0.0, "tests": 0, "tier": "D", "score": 0,
    }
    if result is None:
        return empty
    cur = _pick_current_structure(result)
    if cur is None:
        return {**empty, "symbol": _safe_str(getattr(result, "symbol", ""), "")}

    symbol = _safe_str(getattr(result, "symbol", None) or getattr(cur, "symbol", None), "")
    zone, zone_center, zone_half_width = _extract_zone(cur)
    motion, phase, flux, movement_type = _extract_motion(cur)
    cycles = _extract_cycles(cur)
    test_amplitudes = _extract_test_amplitudes(cycles)
    quality_score = _safe_int(getattr(cur, "quality_score", getattr(cur, "score", 0)), 0)
    quality_tier = _safe_str(getattr(cur, "quality_tier", getattr(cur, "tier", "D")), "D")
    deviation_activity = _safe_int(
        getattr(cur, "deviation_activity",
                getattr(cur, "off_zone_activity", getattr(cur, "activity", 0))), 0)
    test_count = _safe_int(len(cycles), 0)
    duration_days = _extract_duration_days(cur)
    time_since_last_test = _extract_time_since_last_test(cur, bars or [])
    current_price = 0.0
    try:
        if bars and len(bars) > 0:
            last_bar = bars[-1]
            current_price = _safe_float(getattr(last_bar, "close", None), 0.0)
            if current_price == 0.0:
                current_price = _safe_float(getattr(last_bar, "price", None), 0.0)
    except Exception:
        current_price = 0.0
    position_tag = _extract_position_tag(current_price, zone_center, zone_half_width)

    return {
        "symbol": symbol, "has_data": True,
        "phase": phase, "activity": deviation_activity, "quality": quality_score,
        "quality_tier": quality_tier, "position_tag": position_tag,
        "test_count": test_count, "duration_days": duration_days,
        "time_since_last_test": time_since_last_test, "flux": flux,
        "current_price": current_price, "zone_center": zone_center,
        "zone_half_width": zone_half_width, "movement_type": movement_type,
        "test_amplitudes": test_amplitudes, "deviation_activity": deviation_activity,
        "quality_score": quality_score, "center": zone_center,
        "half_width": zone_half_width, "tests": test_count,
        "tier": quality_tier, "score": quality_score,
    }


def _load_mtf_snapshots(symbol: str) -> dict:
    return {}


def _load_history_transitions(symbol: str) -> list:
    return []


# ═══════════════════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════════════════

ALL_SYMBOLS = get_all_available_symbols()
MYSQL_SYMBOLS = discover_mysql_symbols()
CSV_SYMBOLS = discover_csv_symbols()
META = load_symbol_meta()


# ═══════════════════════════════════════════════════════════
# 侧栏 — 改进版
# ═══════════════════════════════════════════════════════════

with st.sidebar:
    # Logo 和版本
    st.markdown("""
    <div style="text-align:center;padding:10px 0">
        <div style="font-size:2em">🔬</div>
        <div style="font-size:1.1em;font-weight:700;color:#ccd6f6;margin-top:4px">
            价格结构工作台
        </div>
        <div style="font-size:0.8em;color:#64ffda">v4.0 · 结构 × 运动</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── 数据源状态 ──
    st.markdown('<div class="nav-group"><span class="nav-group-title">📡 数据源</span></div>',
                unsafe_allow_html=True)
    mysql_ok = len(MYSQL_SYMBOLS) > 0
    if mysql_ok:
        st.success(f"MySQL · {len(MYSQL_SYMBOLS)} 个品种")
    else:
        st.warning("MySQL 未连接")
    st.caption(f"CSV · {len(CSV_SYMBOLS)} 个品种可用")

    st.divider()

    # ── 品种选择（支持搜索）──
    st.markdown('<div class="nav-group"><span class="nav-group-title">📈 品种选择</span></div>',
                unsafe_allow_html=True)

    # 按交易所分组
    exchange_groups = {}
    for sym in ALL_SYMBOLS:
        info = META.get(sym, META.get(sym.upper(), {}))
        ex = info.get("exchange", "其他") if isinstance(info, dict) else "其他"
        exchange_groups.setdefault(ex, []).append(sym)

    # 构建选项列表
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

    # 搜索框
    search = st.text_input("🔍 搜索品种", placeholder="输入代码或名称...",
                          label_visibility="collapsed")

    if search:
        filtered = [(s, l) for s, l in symbol_options
                   if search.upper() in s.upper() or search.upper() in l.upper()]
        if filtered:
            symbol_options = filtered
            sym_labels = [l for _, l in symbol_options]
            sym_codes = [s for s, _ in symbol_options]

    default_idx = sym_codes.index("CU0") if "CU0" in sym_codes else 0
    selected_label = st.selectbox("主品种", sym_labels, index=default_idx,
                                 label_visibility="collapsed")
    selected_symbol = sym_codes[sym_labels.index(selected_label)]

    # 收藏品种
    if "favorites" not in st.session_state:
        st.session_state.favorites = set()

    fav_col1, fav_col2 = st.columns([3, 1])
    with fav_col2:
        if selected_symbol in st.session_state.favorites:
            if st.button("⭐", key="unfav", help="取消收藏"):
                st.session_state.favorites.discard(selected_symbol)
                st.rerun()
        else:
            if st.button("☆", key="fav", help="收藏品种"):
                st.session_state.favorites.add(selected_symbol)
                st.rerun()

    # 收藏列表
    if st.session_state.favorites:
        st.markdown("**⭐ 收藏品种**")
        for fav in list(st.session_state.favorites)[:5]:
            info = META.get(fav, {})
            name = info.get("name", fav) if isinstance(info, dict) else fav
            if st.button(f"  {fav} · {name}", key=f"sidebar_fav_{fav}",
                       use_container_width=True):
                st.session_state["selected_symbol"] = fav
                st.rerun()

    # 对比品种
    compare_symbols = st.multiselect(
        "对比品种",
        [l for s, l in symbol_options if s != selected_symbol],
        max_selections=4,
        label_visibility="collapsed",
        placeholder="选择对比品种...",
    )
    compare_codes = [sym_codes[sym_labels.index(l)] for l in compare_symbols]

    st.divider()

    # ── 分析参数 ──
    st.markdown('<div class="nav-group"><span class="nav-group-title">🎛️ 分析参数</span></div>',
                unsafe_allow_html=True)

    data_range = st.selectbox(
        "时间范围",
        ["最近60天", "最近120天", "最近半年", "最近一年", "全部数据"],
        index=1,
    )
    range_map = {
        "最近60天": 60, "最近120天": 120,
        "最近半年": 180, "最近一年": 365, "全部数据": 99999,
    }

    sensitivity = st.select_slider(
        "结构灵敏度",
        options=["粗糙", "标准", "精细"],
        value="标准",
    )

    st.divider()

    # ── 快捷操作 ──
    st.markdown('<div class="nav-group"><span class="nav-group-title">⚡ 快捷操作</span></div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 刷新", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
    with col2:
        if st.button("📊 全市场", use_container_width=True):
            st.session_state["active_tab"] = "scan"
            st.rerun()

    # ── 快捷操作 ──
    st.markdown('<div class="nav-group"><span class="nav-group-title">❓ 帮助</span></div>',
                unsafe_allow_html=True)

    if st.button("📖 使用指南", use_container_width=True):
        st.session_state["show_help"] = True
        st.rerun()

    if st.button("📊 系统状态", use_container_width=True):
        st.session_state["show_status"] = True
        st.rerun()

    # ── 页脚 ──
    st.divider()
    st.markdown("""
    <div style="text-align:center;padding:8px 0">
        <div style="font-size:0.75em;color:#495057">
            价格结构形式系统 v4.0<br>
            系统 = 结构 × 运动
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 数据加载 + 编译
# ═══════════════════════════════════════════════════════════

sens = SENS_MAP[sensitivity]
result, bars = compile_structures(
    selected_symbol, sens["min_amp"], sens["min_dur"], sens["min_cycles"]
)

if result is None or not bars:
    st.error(f"❌ 无法加载 {selected_symbol} ({symbol_name(selected_symbol)}) 的数据")
    st.info("请确认：MySQL 中有该品种的日线表，或 data/ 目录下有对应的 CSV 文件")
    st.stop()

compare_results = {}
for csym in compare_codes:
    cr, cbars = compile_structures(
        csym, sens["min_amp"], sens["min_dur"], sens["min_cycles"]
    )
    if cr is not None and cbars:
        compare_results[csym] = (cr, cbars)

days = range_map[data_range]
cutoff = bars[-1].timestamp - pd.Timedelta(days=days)
recent_structures = [s for s in result.ranked_structures
                     if s.t_end and s.t_end >= cutoff]


# ═══════════════════════════════════════════════════════════
# 主页面 — Tab 布局
# ═══════════════════════════════════════════════════════════

# 品种信息条
ds = META.get(selected_symbol, {})
ds_name = ds.get("name", selected_symbol) if isinstance(ds, dict) else selected_symbol
ds_exchange = ds.get("exchange", "") if isinstance(ds, dict) else ""
ds_sector = ds.get("sector", "") if isinstance(ds, dict) else ""

st.markdown(f"""
<div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
            border-radius:12px;padding:16px 24px;margin-bottom:16px;
            border-left:4px solid #64ffda">
    <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
            <span style="font-size:1.3em;font-weight:700;color:#ccd6f6">{selected_symbol}</span>
            <span style="font-size:1.1em;color:#8892b0;margin-left:8px">{ds_name}</span>
            <span style="font-size:0.85em;color:#64ffda;margin-left:12px">{ds_exchange} {ds_sector}</span>
        </div>
        <div style="text-align:right">
            <div style="font-size:0.85em;color:#8892b0">
                {bars[0].timestamp:%Y-%m-%d} → {bars[-1].timestamp:%Y-%m-%d}
            </div>
            <div style="font-size:0.8em;color:#64ffda">
                {len(recent_structures)} 个结构 · {'🗄️ MySQL' if selected_symbol.upper() in MYSQL_SYMBOLS else '📄 CSV'}
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if compare_codes:
    compare_names = [f"{c}({symbol_name(c)})" for c in compare_codes]
    st.caption(f"📊 对比品种: {', '.join(compare_names)}")


# ── Tab 定义 ──
tab_config = [
    ("🏠", "仪表盘"),
    ("📡", "今日扫描"),
    ("📋", "每日简报"),
    ("🔍", "历史对照"),
    ("📊", "跨品种对比"),
    ("🗺️", "稳态地图"),
    ("📝", "复盘日志"),
    ("🔎", "合约检索"),
    ("⏱️", "多时间维度"),
    ("🔬", "质量与共振"),
    ("🎯", "研究闭环"),
]

# 检查是否从仪表盘跳转
active_tab = st.session_state.get("active_tab", None)
default_idx = 0
if active_tab:
    tab_map = {"scan": 1, "briefing": 2, "history": 3, "compare": 4, "journal": 6}
    default_idx = tab_map.get(active_tab, 0)
    st.session_state.pop("active_tab", None)

tab_labels = [f"{icon} {name}" for icon, name in tab_config]
tabs = st.tabs(tab_labels)

# ── 上下文字典 ──
ctx = {
    "selected_symbol": selected_symbol,
    "bars": bars,
    "result": result,
    "recent_structures": recent_structures,
    "compare_codes": compare_codes,
    "compare_results": compare_results,
    "sens": sens,
    "ALL_SYMBOLS": ALL_SYMBOLS,
    "MYSQL_SYMBOLS": MYSQL_SYMBOLS,
    "CSV_SYMBOLS": CSV_SYMBOLS,
    "META": META,
    "ds_name": ds_name,
}


# ═══════════════════════════════════════════════════════════
# Tab 路由
# ═══════════════════════════════════════════════════════════

# Tab 0: 仪表盘
with tabs[0]:
    from src.workbench.dashboard import render_dashboard
    render_dashboard(ctx)

# Tab 1: 今日扫描
with tabs[1]:
    from src.workbench import tab_scan
    tab_scan.render(ctx)

# Tab 2: 每日简报
with tabs[2]:
    from src.workbench.daily_briefing import render_daily_briefing
    render_daily_briefing(ctx)

# Tab 3: 历史对照
with tabs[3]:
    from src.workbench import tab_history
    tab_history.render(ctx)

# Tab 4: 跨品种对比
with tabs[4]:
    from src.workbench import tab_compare
    tab_compare.render(ctx)

# Tab 5: 稳态地图
with tabs[5]:
    from src.workbench import tab_stability
    tab_stability.render(ctx)

# Tab 6: 复盘日志
with tabs[6]:
    from src.workbench import tab_journal
    tab_journal.render(ctx)

# Tab 7: 合约检索
with tabs[7]:
    from src.workbench import tab_contract
    tab_contract.render(ctx)

# Tab 8: 多时间维度
with tabs[8]:
    from src.workbench import tab_multitime
    tab_multitime.render(ctx)

# Tab 9: 质量与共振
with tabs[9]:
    from src.workbench import tab_quality
    tab_quality.render(ctx)

# Tab 10: 研究闭环
with tabs[10]:
    from src.workbench.pages.research_loop import render as render_loop
    st.session_state["research_loop_ctx"] = {
        "symbol": selected_symbol,
        "current_structure": _build_current_structure_dict(result, bars),
        "mtf_snapshots": _load_mtf_snapshots(selected_symbol),
        "history_transitions": _load_history_transitions(selected_symbol),
    }
    render_loop(
        symbol=selected_symbol,
        current_structure=_build_current_structure_dict(result, bars),
        mtf_snapshots=_load_mtf_snapshots(selected_symbol),
        history_transitions=_load_history_transitions(selected_symbol),
    )


# ── 帮助模态框 ──
if st.session_state.get("show_help", False):
    from src.workbench.help_system import QUICK_START
    with st.expander("📖 使用指南", expanded=True):
        st.markdown(QUICK_START)
        if st.button("关闭帮助"):
            st.session_state["show_help"] = False
            st.rerun()

# ── 系统状态模态框 ──
if st.session_state.get("show_status", False):
    with st.expander("📊 系统状态", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("品种总数", len(ALL_SYMBOLS))
            st.metric("MySQL 品种", len(MYSQL_SYMBOLS))
        with col2:
            st.metric("CSV 品种", len(CSV_SYMBOLS))
            st.metric("当前品种", selected_symbol)
        with col3:
            st.metric("数据范围", data_range)
            st.metric("灵敏度", sensitivity)

        st.markdown("---")
        st.markdown("**数据源状态**")
        if MYSQL_SYMBOLS:
            st.success(f"✅ MySQL 已连接 · {len(MYSQL_SYMBOLS)} 个品种")
        else:
            st.warning("⚠️ MySQL 未连接")
        if CSV_SYMBOLS:
            st.info(f"📄 CSV 可用 · {len(CSV_SYMBOLS)} 个品种")

        if st.button("关闭状态"):
            st.session_state["show_status"] = False
            st.rerun()

# ── 浮动帮助按钮 ──
from src.workbench.help_system import render_help_button, render_help_modal
render_help_button()
render_help_modal()

# ── 页脚 ──
st.markdown("""
<div class="footer">
    🔬 价格结构形式系统 v4.0 · 系统 = 结构 × 运动<br>
    <span style="font-size:0.85em">
        数据来源: MySQL + CSV · 编译器: C扩展加速 · 相似度: 四层检索
    </span>
</div>
""", unsafe_allow_html=True)
