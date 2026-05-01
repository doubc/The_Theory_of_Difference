"""
新浪期货数据采集器 — 从 Sina Finance API 抓取日线 + 5 分钟线

支持三种数据源（自动判断）：
  - 国内期货（cu0, rb2510, al0 ...）
  - 外盘期货（cad, gc, cl ...）
  - 外汇（usdcny, eurusd ...）

核心函数：
  fetch_bars(code, freq='1d') → list[Bar]
  detect_source(code) → 'inner' | 'global' | 'fx'
  available_contracts() → list[str]   返回预置的可检索合约列表
"""

from __future__ import annotations

import json
import requests
import pandas as pd
from datetime import datetime
from typing import Literal

from src.data.loader import Bar


# ─── 新浪 API URL 构造 ────────────────────────────────────

def _inner_url_day(code: str) -> str:
    return (f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php"
            f"/=/InnerFuturesNewService.getDailyKLine?symbol={code}")


def _inner_url_m5(code: str) -> str:
    return (f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php"
            f"/=/InnerFuturesNewService.getFewMinLine?symbol={code.upper()}&type=5")


def _global_url_day(code: str) -> str:
    return (f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php"
            f"/=/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol={code}")


def _global_url_m5(code: str) -> str:
    return (f"https://gu.sina.cn/ft/api/jsonp.php"
            f"/=/GlobalService.getMink?symbol={code}&type=5")


def _fx_url_day(code: str) -> str:
    return (f"https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php"
            f"/=/NewForexService.getDayKLine?symbol=fx_s{code}")


def _fx_url_m5(code: str) -> str:
    return (f"https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php"
            f"/=/NewForexService.getOldMinKline?symbol={code}&scale=5&datalen=1840")


# ─── 数据源判断 ────────────────────────────────────────────

GLOBAL_CODES = frozenset([
    "cad", "nid", "snd", "pbd", "zsd", "ahd", "cl", "s", "sm", "bo",
    "trb", "ng", "si", "gc", "oil", "ct", "hg",
])

FX_CODES = frozenset([
    "usdcny", "audusd", "diniw", "eurusd", "gbpusd", "nzdusd",
    "usdcad", "usdchf", "usdjpy", "usdmyr", "usdsgd", "usdtwd",
])


def detect_source(code: str) -> Literal["inner", "global", "fx"]:
    """判断合约代码属于哪个数据源"""
    c = code.lower()
    if c in FX_CODES:
        return "fx"
    if c in GLOBAL_CODES:
        return "global"
    return "inner"


# ─── 数据清洗 ──────────────────────────────────────────────

def _parse_jsonp(text: str) -> list[dict]:
    """解析新浪 JSONP 响应为 JSON 列表"""
    try:
        data = text.split("=")[2][1:-2]
        return json.loads(data)
    except (IndexError, json.JSONDecodeError):
        # 尝试另一种分割方式（FX 格式略有不同）
        try:
            data = text.split("=")[2][2:-3]
            return json.loads(data)
        except Exception:
            return []


def _clean_day_inner(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records).rename(columns={
        'd': 'date', 'o': 'open', 'h': 'high',
        'l': 'low', 'c': 'close', 'v': 'vol',
    })
    df['date'] = pd.to_datetime(df['date'])
    return df[['date', 'open', 'high', 'low', 'close', 'vol']]


def _clean_day_global(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records).rename(columns={
        'date': 'date', 'open': 'open', 'high': 'high',
        'low': 'low', 'close': 'close', 'volume': 'vol',
    })
    df['date'] = pd.to_datetime(df['date'])
    return df[['date', 'open', 'high', 'low', 'close', 'vol']]


def _clean_day_fx(text: str) -> pd.DataFrame:
    """FX 日线格式特殊，需要手动解析"""
    try:
        raw = text.split("=")[2][2:-3]
        rows = [r.split(",") for r in raw.split(",|")]
        df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close'])
        df['date'] = pd.to_datetime(df['date'])
        df['vol'] = 0
        return df[['date', 'open', 'high', 'low', 'close', 'vol']]
    except Exception:
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'vol'])


def _clean_m5(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records).rename(columns={
        'd': 'date', 'o': 'open', 'h': 'high',
        'l': 'low', 'c': 'close', 'v': 'vol',
    })
    df['date'] = pd.to_datetime(df['date'])
    return df[['date', 'open', 'high', 'low', 'close']]


# ─── 核心抓取函数 ──────────────────────────────────────────

def _fetch_url(url: str, timeout: int = 10) -> str:
    """带超时的 HTTP GET"""
    resp = requests.get(url, timeout=timeout)
    resp.encoding = 'utf-8'
    return resp.text


def fetch_bars(
    code: str,
    freq: Literal["1d", "5m"] = "1d",
    timeout: int = 10,
) -> list[Bar]:
    """
    从新浪 API 抓取指定合约的 K 线数据。

    Args:
        code: 合约代码，如 'cu0', 'rb2510', 'cad', 'usdcny'
        freq: '1d' 日线 / '5m' 五分钟线
        timeout: 请求超时秒数

    Returns:
        list[Bar] — 按时间升序排列的 K 线列表
    """
    source = detect_source(code)
    c = code.lower()

    try:
        if freq == "5m":
            if source == "inner":
                text = _fetch_url(_inner_url_m5(c), timeout)
            elif source == "global":
                text = _fetch_url(_global_url_m5(c), timeout)
            else:
                text = _fetch_url(_fx_url_m5(c), timeout)
            records = _parse_jsonp(text)
            if not records:
                return []
            df = _clean_m5(records)
        else:
            if source == "inner":
                text = _fetch_url(_inner_url_day(c), timeout)
                records = _parse_jsonp(text)
                df = _clean_day_inner(records) if records else pd.DataFrame()
            elif source == "global":
                text = _fetch_url(_global_url_day(c), timeout)
                records = _parse_jsonp(text)
                df = _clean_day_global(records) if records else pd.DataFrame()
            else:
                text = _fetch_url(_fx_url_day(c), timeout)
                df = _clean_day_fx(text)

        if df.empty:
            return []

        # 转为 Bar 列表
        bars = []
        for _, row in df.iterrows():
            bars.append(Bar(
                symbol=code.upper(),
                timestamp=row['date'],
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row.get('vol', 0)),
            ))
        return bars

    except Exception as e:
        print(f"[SinaFetcher] {code} 抓取失败: {e}")
        return []


# ─── 预置合约列表 ──────────────────────────────────────────

# 国内期货主力合约
INNER_MAIN = [
    # 上期所 SHFE
    "cu0", "al0", "zn0", "pb0", "ni0", "sn0",
    "au0", "ag0",
    "rb0", "hc0", "ss0", "bu0", "ru0", "fu0", "sp0",
    # 大商所 DCE
    "i0", "j0", "jm0", "rb0", "m0", "y0", "p0", "a0", "b0",
    "c0", "cs0", "l0", "v0", "pp0", "eg0", "eb0", "pg0",
    # 郑商所 CZCE
    "ma0", "sr0", "cf0", "oi0", "ta0", "rm0", "fg0",
    "zc0", "sf0", "sm0", "ur0", "sa0",
    # 广期所 GFEX
    "lc0", "si0",
]

# 外盘主力
GLOBAL_MAIN = [
    "cad", "nid", "snd", "pbd", "zsd", "ahd",
    "cl", "s", "sm", "bo", "si", "gc", "oil", "ct", "hg",
]

# 外汇
FX_MAIN = ["usdcny", "eurusd", "gbpusd", "usdjpy"]


def available_contracts() -> dict[str, list[str]]:
    """返回按数据源分组的可检索合约列表"""
    return {
        "国内期货(主力)": INNER_MAIN,
        "外盘期货": GLOBAL_MAIN,
        "外汇": FX_MAIN,
    }
