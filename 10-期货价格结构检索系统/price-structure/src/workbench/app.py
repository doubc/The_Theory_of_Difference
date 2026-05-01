#!/usr/bin/env python3
"""
价格结构研究工作台 v3.0

主入口 — 侧栏 + 8 个 Tab 路由
各 Tab 逻辑拆分到 tab_*.py 独立模块。

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


# ============================================================================
# 研究闭环辅助函数
# 给 pages/research_loop.py 提供稳定、完整、带默认值的数据
# ============================================================================


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
        if dist >= 3:
            return "far_above"
        return "above"

    if current_price < lower:
        if dist >= 3:
            return "far_below"
        return "below"

    return "unknown"


def _extract_duration_days(structure):
    zone = getattr(structure, "zone", None)
    if zone is None:
        return 0

    start = None
    end = None

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
            delta = end - start
            return max(int(delta.days), 0)
    except Exception:
        pass

    return 0


def _extract_time_since_last_test(structure, bars):
    cycles = _extract_cycles(structure)
    if not cycles or not bars:
        return 0

    last_ts = None

    # 优先从 cycle 取末次时间
    for c in reversed(cycles):
        for attr in ("end_time", "timestamp", "t_end", "end_date"):
            if hasattr(c, attr):
                last_ts = getattr(c, attr, None)
                if last_ts is not None:
                    break
        if last_ts is not None:
            break

    # fallback 到 zone
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
            delta = bars[-1].timestamp - last_ts
            return max(int(delta.days), 0)
    except Exception:
        pass

    return 0


def _pick_current_structure(result):
    structures = getattr(result, "structures", None) or getattr(result, "ranked_structures", None) or []
    if not structures:
        return None

    # 优先按结束时间排序，取最近结构
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
    """
    给 research_loop.render() 构造完整上下文字典。
    所有字段都保证存在，避免 KeyError。
    """
    empty = {
        "symbol": "",
        "has_data": False,

        "phase": "unknown",
        "activity": 0,
        "quality": 0,
        "quality_tier": "D",
        "position_tag": "unknown",

        "test_count": 0,
        "duration_days": 0,
        "time_since_last_test": 0,

        "flux": 0.0,
        "current_price": 0.0,
        "zone_center": 0.0,
        "zone_half_width": 0.0,

        "movement_type": "unknown",
        "test_amplitudes": [],

        # 兼容旧代码可能访问的字段
        "deviation_activity": 0,
        "quality_score": 0,
        "center": 0.0,
        "half_width": 0.0,
        "tests": 0,
        "tier": "D",
        "score": 0,
    }

    if result is None:
        return empty

    cur = _pick_current_structure(result)
    if cur is None:
        return {
            **empty,
            "symbol": _safe_str(getattr(result, "symbol", ""), ""),
        }

    symbol = _safe_str(
        getattr(result, "symbol", None) or getattr(cur, "symbol", None),
        ""
    )

    zone, zone_center, zone_half_width = _extract_zone(cur)
    motion, phase, flux, movement_type = _extract_motion(cur)
    cycles = _extract_cycles(cur)
    test_amplitudes = _extract_test_amplitudes(cycles)

    quality_score = _safe_int(
        getattr(cur, "quality_score", getattr(cur, "score", 0)),
        0
    )
    quality_tier = _safe_str(
        getattr(cur, "quality_tier", getattr(cur, "tier", "D")),
        "D"
    )
    deviation_activity = _safe_int(
        getattr(cur, "deviation_activity",
                getattr(cur, "off_zone_activity",
                        getattr(cur, "activity", 0))),
        0
    )
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
        "symbol": symbol,
        "has_data": True,

        "phase": phase,
        "activity": deviation_activity,
        "quality": quality_score,
        "quality_tier": quality_tier,
        "position_tag": position_tag,

        "test_count": test_count,
        "duration_days": duration_days,
        "time_since_last_test": time_since_last_test,

        "flux": flux,
        "current_price": current_price,
        "zone_center": zone_center,
        "zone_half_width": zone_half_width,

        "movement_type": movement_type,
        "test_amplitudes": test_amplitudes,

        # 兼容字段
        "deviation_activity": deviation_activity,
        "quality_score": quality_score,
        "center": zone_center,
        "half_width": zone_half_width,
        "tests": test_count,
        "tier": quality_tier,
        "score": quality_score,
    }


def _load_mtf_snapshots(symbol: str) -> dict:
    """
    先返回空，避免研究闭环页直接崩。
    research_loop.py 已经对空字典做了 graceful fallback。
    """
    return {}


def _load_history_transitions(symbol: str) -> list:
    """
    先返回空列表。
    如果后续你已经有 transitions 数据落盘，再在这里接真实数据。
    """
    return []


# ─── 页面配置 ──────────────────────────────────────────────

st.set_page_config(
    page_title="价格结构研究工作台 v3",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CSS_STYLE, unsafe_allow_html=True)

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

    exchange_groups = {}
    for sym in ALL_SYMBOLS:
        info = META.get(sym, META.get(sym.upper(), {}))
        ex = info.get("exchange", "其他") if isinstance(info, dict) else "其他"
        exchange_groups.setdefault(ex, []).append(sym)

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

    st.divider()
    if st.button("🔄 刷新全部"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

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
# 主页面
# ═══════════════════════════════════════════════════════════

# ========================================================================
# 辅助：把 compile_full 的 result 转成 UI 层需要的扁平字典
# ========================================================================

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
    "🎯 研究闭环",
    "🗺️ 知识图谱",
]
tabs = st.tabs(tab_names)

# ── 上下文字典，传给各 Tab ──
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

from src.workbench import tab_scan, tab_history, tab_compare
from src.workbench import tab_stability, tab_journal, tab_contract
from src.workbench import tab_multitime, tab_quality
from src.workbench import tab_knowledge_graph

with tabs[0]:
    tab_scan.render(ctx)

with tabs[1]:
    tab_history.render(ctx)

with tabs[2]:
    tab_compare.render(ctx)

with tabs[3]:
    tab_stability.render(ctx)

with tabs[4]:
    tab_journal.render(ctx)

with tabs[5]:
    tab_contract.render(ctx)

with tabs[6]:
    tab_multitime.render(ctx)

with tabs[7]:
    tab_quality.render(ctx)

with tabs[8]:
    from src.workbench.pages.research_loop import render as render_loop

    st.session_state["research_loop_ctx"] = {
        "symbol": selected_symbol,
        "current_structure": _build_current_structure_dict(result, bars),
        "mtf_snapshots": _load_mtf_snapshots(selected_symbol),
        "history_transitions": _load_history_transitions(selected_symbol),
    }

    # TODO: 提供 mtf_snapshots 和 history_transitions 数据
    render_loop(
        symbol=selected_symbol,
        current_structure=_build_current_structure_dict(result, bars),
        mtf_snapshots=_load_mtf_snapshots(selected_symbol),
        history_transitions=_load_history_transitions(selected_symbol),
    )

with tabs[9]:
    tab_knowledge_graph.render(ctx)
