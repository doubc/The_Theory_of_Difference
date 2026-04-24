#!/usr/bin/env python3
"""
价格结构研究工作台 v3.0

主入口 — 侧栏 + 8 个 Tab 路由
各 Tab 逻辑拆分到 tab_*.py 独立模块。

运行: streamlit run src/workbench/app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

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
