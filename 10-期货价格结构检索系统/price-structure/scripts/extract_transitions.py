"""
从全历史 K 线中抽取“从一个稳态破缺到下一个稳态”的转移样本
输出: data/transitions/{symbol}.parquet
运行: python scripts/extract_transitions.py --symbols CU0,RB0,HC0,...
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 确保项目根在 Python 路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from src.compiler.pipeline import compile_full, CompilerConfig


# -------- 工具：兼容多种 Zone 字段命名 --------

def _zone_first_date(zone, bars: pd.DataFrame):
    """尝试多种字段名拿 Zone 的首次试探日期"""
    for attr in ("first_touch_date", "first_date", "start_date", "t_start"):
        if hasattr(zone, attr):
            v = getattr(zone, attr)
            if v is not None:
                return pd.Timestamp(v).normalize()
    # 退而求其次：按 bar index
    for attr in ("first_bar_index", "start_index", "i_start"):
        if hasattr(zone, attr):
            idx = int(getattr(zone, attr))
            if 0 <= idx < len(bars):
                return pd.Timestamp(bars.iloc[idx]["date"]).normalize()
    raise AttributeError(f"Zone 对象缺少首次日期字段，实际字段: {list(vars(zone).keys())}")


def _zone_last_date(zone, bars: pd.DataFrame):
    for attr in ("last_touch_date", "last_date", "end_date", "t_end"):
        if hasattr(zone, attr):
            v = getattr(zone, attr)
            if v is not None:
                return pd.Timestamp(v).normalize()
    for attr in ("last_bar_index", "end_index", "i_end"):
        if hasattr(zone, attr):
            idx = int(getattr(zone, attr))
            if 0 <= idx < len(bars):
                return pd.Timestamp(bars.iloc[idx]["date"]).normalize()
    raise AttributeError(f"Zone 对象缺少末次日期字段，实际字段: {list(vars(zone).keys())}")


def _load_bars(symbol: str) -> pd.DataFrame:
    """
    统一的 bar 加载入口：优先尝试 load_symbol / MySQLLoader / CSV 三种方式。
    找到哪个用哪个，与 src/data/loader.py 的实际 API 无关。
    """
    try:
        from src.data import loader as data_loader
    except ImportError as e:
        raise RuntimeError(f"无法导入 src.data.loader: {e}")

    # 1. 优先尝试通用函数
    if hasattr(data_loader, "load_symbol"):
        return data_loader.load_symbol(symbol).get()
    if hasattr(data_loader, f"load_{symbol.lower()}"):
        return getattr(data_loader, f"load_{symbol.lower()}")().get()

    # 2. 尝试 MySQLLoader
    if hasattr(data_loader, "MySQLLoader"):
        password = os.getenv("MYSQL_PASSWORD", "")
        mysql_loader = data_loader.MySQLLoader(
            host="localhost", user="root", password=password, db="sina"
        )
        # MySQLLoader 可能用 symbol= 或 table= 或 get(symbol)，依次尝试
        for try_kwargs in (
                {"symbol": symbol, "freq": "1d"},
                {"symbol": symbol},
                {"table": symbol.lower()},
                {},
        ):
            try:
                bars = mysql_loader.get(**try_kwargs) if try_kwargs else mysql_loader.get(symbol)
                if bars is not None and len(bars) > 0:
                    return bars
            except TypeError:
                continue
            except Exception:
                continue

    raise RuntimeError(f"无法为 {symbol} 加载数据，请检查 src/data/loader.py 的 API")


def _ensure_date_column(bars: pd.DataFrame) -> pd.DataFrame:
    """保证 bars 有一个 date 列，且类型为 pd.Timestamp"""
    if "date" not in bars.columns:
        # 常见别名
        for alt in ("time", "datetime", "trade_date"):
            if alt in bars.columns:
                bars = bars.rename(columns={alt: "date"})
                break
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    return bars


def extract_for_symbol(symbol: str) -> pd.DataFrame:
    bars = _ensure_date_column(_load_bars(symbol))
    if len(bars) < 50:
        return pd.DataFrame()

    result = compile_full(bars, CompilerConfig(min_amplitude=0.03), symbol=symbol)
    if not result.structures:
        return pd.DataFrame()

    # 结构按首次触碰日期排序
    structures = sorted(result.structures, key=lambda s: _zone_first_date(s.zone, bars))

    rows = []
    for i in range(len(structures) - 1):
        cur, nxt = structures[i], structures[i + 1]
        try:
            cur_end = _zone_last_date(cur.zone, bars)
            nxt_start = _zone_first_date(nxt.zone, bars)
        except AttributeError as e:
            print(f"  [警告] 跳过一对结构，原因: {e}")
            continue

        from_price = float(cur.zone.price_center)
        to_price = float(nxt.zone.price_center)
        hold_days = max((nxt_start - cur_end).days, 1)

        seg = bars[(bars["date"] >= cur_end) & (bars["date"] <= nxt_start)]
        if len(seg) == 0:
            continue

        if to_price >= from_price:
            max_dd = float((from_price - seg["low"].min()) / from_price)
        else:
            max_dd = float((seg["high"].max() - from_price) / from_price)

        rows.append({
            "phase": str(getattr(cur.motion, "phase_tendency", "unknown")),
            "quality": str(getattr(cur, "quality_tier", "B")),
            "flux_sign": "+" if getattr(cur.motion, "conservation_flux", 0.0) >= 0 else "-",
            "from_zone": from_price,
            "to_zone": to_price,
            "holding_days": hold_days,
            "max_drawdown": round(max_dd, 4),
            "from_date": cur_end.strftime("%Y-%m-%d"),
            "to_date": nxt_start.strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True, help="逗号分隔，例如 CU0,RB0,HC0")
    ap.add_argument("--out_dir", default="data/transitions")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for sym in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        print(f"[{sym}] 抽取中 ...")
        try:
            df = extract_for_symbol(sym)
        except Exception as e:
            print(f"  ✗ 失败: {type(e).__name__}: {e}")
            summary.append((sym, 0, f"error: {e}"))
            continue

        if len(df) > 0:
            df.to_parquet(out_dir / f"{sym}.parquet", index=False)
            print(f"  ✓ {len(df)} 条转移样本")
            summary.append((sym, len(df), "ok"))
        else:
            print("  · 无有效数据")
            summary.append((sym, 0, "empty"))

    print("\n=== 汇总 ===")
    for sym, n, status in summary:
        print(f"  {sym:6s}  {n:>5d}  {status}")


if __name__ == "__main__":
    main()
