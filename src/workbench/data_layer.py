"""
数据层：MySQL 优先 + CSV 降级 + 全品种发现

v4.0 改进：
  - 更好的错误处理和日志
  - 支持 Parquet 本地缓存
  - 品种元数据增强
  - 数据质量检查
"""

import os
from pathlib import Path
from typing import Optional, Tuple, List

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
        engine = create_engine(
            f"mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8",
            pool_pre_ping=True,
            pool_recycle=3600,
        )
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
    except Exception as e:
        print(f"[data_layer] MySQL symbol discovery failed: {e}")
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
# 数据质量检查
# ═══════════════════════════════════════════════════════════

def check_data_quality(bars: List[Bar]) -> dict:
    """检查数据质量，返回质量报告"""
    if not bars:
        return {"status": "error", "message": "无数据", "quality": 0}

    issues = []
    warnings = []

    # 检查数据量
    if len(bars) < 30:
        issues.append(f"数据量不足：{len(bars)} 根 K 线（最少需要 30）")
    elif len(bars) < 60:
        warnings.append(f"数据量较少：{len(bars)} 根 K 线（建议 60+）")

    # 检查日期连续性
    dates = [b.timestamp for b in bars]
    date_gaps = []
    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i-1]).days
        if gap > 5:  # 超过5天没有数据
            date_gaps.append((dates[i-1].strftime("%Y-%m-%d"), dates[i].strftime("%Y-%m-%d"), gap))

    if date_gaps:
        warnings.append(f"发现 {len(date_gaps)} 个日期间隔（>5天）")

    # 检查价格异常
    closes = [b.close for b in bars]
    if closes:
        avg_price = sum(closes) / len(closes)
        extreme_moves = []
        for i in range(1, len(closes)):
            change = abs(closes[i] - closes[i-1]) / closes[i-1]
            if change > 0.1:  # 单日涨跌超过10%
                extreme_moves.append((bars[i].timestamp.strftime("%Y-%m-%d"), change * 100))

        if extreme_moves:
            warnings.append(f"发现 {len(extreme_moves)} 个极端波动（>10%）")

    # 检查成交量
    volumes = [b.volume for b in bars if hasattr(b, 'volume') and b.volume]
    if volumes:
        avg_vol = sum(volumes) / len(volumes)
        zero_vol_days = sum(1 for v in volumes if v == 0)
        if zero_vol_days > len(volumes) * 0.1:
            warnings.append(f"成交量为0的天数过多：{zero_vol_days}/{len(volumes)}")

    # 计算质量分数
    quality_score = 100
    quality_score -= len(issues) * 30
    quality_score -= len(warnings) * 10
    quality_score = max(0, min(100, quality_score))

    status = "excellent" if quality_score >= 90 else \
             "good" if quality_score >= 70 else \
             "warning" if quality_score >= 50 else "error"

    return {
        "status": status,
        "quality": quality_score,
        "bars_count": len(bars),
        "date_range": f"{dates[0].strftime('%Y-%m-%d')} → {dates[-1].strftime('%Y-%m-%d')}" if dates else "—",
        "issues": issues,
        "warnings": warnings,
        "date_gaps": date_gaps[:5],  # 最多显示5个
    }


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
                try:
                    loader = CSVLoader(str(path), symbol=symbol)
                    bars = loader.get()
                    if bars:
                        print(f"[data_layer] Loaded {len(bars)} bars for {symbol} from CSV")
                        return bars
                except Exception as e:
                    print(f"[data_layer] CSV load failed for {symbol}: {e}")
                    continue

    return []


@st.cache_data
def compile_structures(symbol: str, min_amp, min_dur, min_cycles,
                       source: str = "auto") -> Tuple[Optional[object], List[Bar]]:
    """
    编译品种结构：加载数据 → 编译 → 返回结果

    Returns:
        (result, bars) 或 (None, bars) 如果编译失败
    """
    bars = load_bars(symbol, source)

    if not bars or len(bars) < 30:
        return None, bars

    try:
        config = CompilerConfig(
            min_amplitude=min_amp, min_duration=min_dur,
            min_cycles=min_cycles,
            adaptive_pivots=True, fractal_threshold=0.34,
        )
        result = compile_full(bars, config, symbol=symbol)
        return result, bars
    except Exception as e:
        print(f"[data_layer] Compilation failed for {symbol}: {e}")
        return None, bars


def get_data_source_info(symbol: str) -> dict:
    """获取品种的数据源信息"""
    mysql_syms = discover_mysql_symbols()
    csv_syms = discover_csv_symbols()

    if symbol.upper() in mysql_syms:
        return {"source": "MySQL", "icon": "🗄️", "status": "available"}
    elif symbol.upper() in csv_syms or symbol.lower() in csv_syms:
        return {"source": "CSV", "icon": "📄", "status": "available"}
    else:
        # 检查 symbol_meta
        meta = load_symbol_meta()
        if symbol in meta or symbol.upper() in meta:
            return {"source": "Meta", "icon": "📋", "status": "meta_only"}
        return {"source": "Unknown", "icon": "❓", "status": "unavailable"}


def get_symbol_info(symbol: str) -> dict:
    """获取品种的详细信息"""
    meta = load_symbol_meta()
    info = meta.get(symbol, meta.get(symbol.upper(), {}))

    if not info:
        return {"name": symbol, "exchange": "未知", "sector": "未知"}

    return {
        "name": info.get("name", symbol),
        "exchange": info.get("exchange", "未知"),
        "sector": info.get("sector", "未知"),
        "unit": info.get("unit", ""),
        "multiplier": info.get("multiplier", 1),
        "tick_size": info.get("tick_size", 1),
        "typical_vol": info.get("typical_vol", 0),
        "vol_regime": info.get("vol_regime", "unknown"),
        "description": info.get("description", ""),
    }
