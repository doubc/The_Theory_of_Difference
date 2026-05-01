"""
数据层：MySQL 优先 + CSV 降级 + 全品种发现

提取自 app.py，供各 Tab 页面复用。
"""

import os
from pathlib import Path

import streamlit as st
from src.compiler.pipeline import compile_full, CompilerConfig
from src.data.loader import Bar, CSVLoader, MySQLLoader
from src.data.symbol_meta import load_symbol_meta


# ═══════════════════════════════════════════════════════════
# MySQL / CSV 连接 & 品种发现
# ═══════════════════════════════════════════════════════════

@st.cache_resource
def get_mysql_engine():
    """尝试连接 MySQL，返回 engine 或 None"""
    try:
        from sqlalchemy import create_engine, inspect
        password = os.getenv('MYSQL_PASSWORD', '')
        user = os.getenv('MYSQL_USER', 'root')
        host = os.getenv('MYSQL_HOST', 'localhost')
        db = os.getenv('MYSQL_DB', 'sina')
        if not password:
            print("[data_layer] MySQL password not set, skipping MySQL")
            return None
        engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8")
        insp = inspect(engine)
        _ = insp.get_table_names()
        print(f"[data_layer] Connected to MySQL ({host}/{db})")
        return engine
    except Exception as e:
        print(f"[data_layer] MySQL connection failed: {e}")
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


# ═══════════════════════════════════════════════════════════
# 数据加载 & 编译
# ═══════════════════════════════════════════════════════════

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
            password = os.getenv('MYSQL_PASSWORD', '')
            loader = MySQLLoader(password=password, db="sina")
            bars = loader.get(symbol=symbol, freq="1d")
            if bars:
                print(f"[data_layer] Loaded {len(bars)} bars for {symbol} from MySQL")
                return bars
        except Exception as e:
            print(f"[data_layer] MySQL load failed for {symbol}: {e}")
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
