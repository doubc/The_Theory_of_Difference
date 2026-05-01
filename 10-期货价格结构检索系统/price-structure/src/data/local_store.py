"""
本地数据仓库 — Parquet 存储 + DuckDB 查询

全市场数据本地化：批量从 Sina 采集，存储为 Parquet，
后续编译/检索直接读本地，速度提升 10-100x。

目录结构：
    data/local/
    ├── daily/          # 日线 Parquet
    │   ├── CU0.parquet
    │   ├── AL0.parquet
    │   └── ...
    ├── 5min/           # 5分钟线 Parquet
    │   ├── CU0.parquet
    │   └── ...
    ├── meta.json       # 元数据：最后更新时间、合约列表
    └── scan_cache/     # 编译缓存
        ├── CU0_daily.pkl
        └── ...
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.data.loader import Bar


# ─── 配置 ─────────────────────────────────────────────────

@dataclass
class LocalStoreConfig:
    base_dir: str = "data/local"
    daily_dir: str = "data/local/daily"
    min5_dir: str = "data/local/5min"
    cache_dir: str = "data/local/scan_cache"
    meta_file: str = "data/local/meta.json"
    compression: str = "snappy"  # snappy / gzip / zstd / lz4
    row_group_size: int = 100_000


# ─── 元数据管理 ───────────────────────────────────────────

@dataclass
class ContractMeta:
    symbol: str
    source: str  # inner / global / fx
    daily_rows: int = 0
    min5_rows: int = 0
    daily_last_date: str = ""
    min5_last_date: str = ""
    last_fetch_ts: str = ""
    error_count: int = 0


@dataclass
class StoreMeta:
    contracts: dict[str, ContractMeta] = field(default_factory=dict)
    last_full_scan: str = ""

    def save(self, path: str):
        data = {
            "last_full_scan": self.last_full_scan,
            "contracts": {
                k: {
                    "symbol": v.symbol,
                    "source": v.source,
                    "daily_rows": v.daily_rows,
                    "min5_rows": v.min5_rows,
                    "daily_last_date": v.daily_last_date,
                    "min5_last_date": v.min5_last_date,
                    "last_fetch_ts": v.last_fetch_ts,
                    "error_count": v.error_count,
                }
                for k, v in self.contracts.items()
            },
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> StoreMeta:
        if not Path(path).exists():
            return cls()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        meta = cls(last_full_scan=data.get("last_full_scan", ""))
        for k, v in data.get("contracts", {}).items():
            meta.contracts[k] = ContractMeta(**v)
        return meta


# ─── Bar ↔ DataFrame 转换 ─────────────────────────────────

def bars_to_dataframe(bars: list[Bar]) -> pd.DataFrame:
    """Bar 列表 → pandas DataFrame（Parquet 友好格式）"""
    if not bars:
        return pd.DataFrame(columns=[
            "timestamp", "open", "high", "low", "close", "volume"
        ])
    records = []
    for b in bars:
        records.append({
            "timestamp": b.timestamp,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        })
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)


def dataframe_to_bars(df: pd.DataFrame, symbol: str = "") -> list[Bar]:
    """pandas DataFrame → Bar 列表"""
    bars = []
    for _, row in df.iterrows():
        bars.append(Bar(
            symbol=symbol,
            timestamp=row["timestamp"].to_pydatetime() if hasattr(row["timestamp"], "to_pydatetime") else row["timestamp"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0)),
        ))
    return bars


# ─── 本地存储引擎 ─────────────────────────────────────────

class LocalStore:
    """
    本地 Parquet 数据仓库

    核心功能：
    - save_bars(symbol, bars, freq): 保存 Bar 列表到 Parquet
    - load_bars(symbol, freq, start, end): 从 Parquet 加载 Bar 列表
    - load_all_symbols(freq): 加载所有品种到 dict[symbol, list[Bar]]
    - get_dataframe(symbol, freq): 返回 pandas DataFrame
    - incremental_update(symbol, new_bars, freq): 增量追加新数据
    """

    def __init__(self, config: LocalStoreConfig | None = None):
        self.config = config or LocalStoreConfig()
        self._ensure_dirs()
        self.meta = StoreMeta.load(self.config.meta_file)

    def _ensure_dirs(self):
        for d in [self.config.daily_dir, self.config.min5_dir, self.config.cache_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)

    def _parquet_path(self, symbol: str, freq: str = "1d") -> Path:
        if freq == "5m":
            return Path(self.config.min5_dir) / f"{symbol}.parquet"
        return Path(self.config.daily_dir) / f"{symbol}.parquet"

    def _freq_key(self, freq: str) -> str:
        return "min5" if freq == "5m" else "daily"

    # ── 写入 ──

    def save_bars(self, symbol: str, bars: list[Bar], freq: str = "1d") -> int:
        """保存 Bar 列表到 Parquet，返回写入行数"""
        if not bars:
            return 0

        df = bars_to_dataframe(bars)
        path = self._parquet_path(symbol, freq)
        path.parent.mkdir(parents=True, exist_ok=True)

        table = pa.Table.from_pandas(df)
        pq.write_table(
            table, str(path),
            compression=self.config.compression,
            row_group_size=self.config.row_group_size,
        )

        # 更新元数据
        self._update_meta(symbol, freq, df)
        return len(df)

    def incremental_update(self, symbol: str, new_bars: list[Bar], freq: str = "1d") -> int:
        """增量更新：合并已有数据 + 新数据，去重后写入"""
        existing = self.load_bars(symbol, freq=freq)
        if not existing:
            return self.save_bars(symbol, new_bars, freq=freq)

        # 合并 + 去重
        existing_df = bars_to_dataframe(existing)
        new_df = bars_to_dataframe(new_bars)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
        combined = combined.sort_values("timestamp").reset_index(drop=True)

        # 转回 Bar 写入
        bars = dataframe_to_bars(combined, symbol=symbol)
        return self.save_bars(symbol, bars, freq=freq)

    # ── 读取 ──

    def load_bars(
        self,
        symbol: str,
        freq: str = "1d",
        start: str | datetime | None = None,
        end: str | datetime | None = None,
    ) -> list[Bar]:
        """从 Parquet 加载 Bar 列表"""
        path = self._parquet_path(symbol, freq)
        if not path.exists():
            return []

        df = pq.read_table(str(path)).to_pandas()
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        if start:
            s = pd.Timestamp(start)
            df = df[df["timestamp"] >= s]
        if end:
            e = pd.Timestamp(end)
            df = df[df["timestamp"] <= e]

        return dataframe_to_bars(df, symbol=symbol)

    def get_dataframe(
        self,
        symbol: str,
        freq: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """返回 pandas DataFrame（直接操作，更快）"""
        path = self._parquet_path(symbol, freq)
        if not path.exists():
            return pd.DataFrame()

        df = pq.read_table(str(path)).to_pandas()
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        if start:
            df = df[df["timestamp"] >= pd.Timestamp(start)]
        if end:
            df = df[df["timestamp"] <= pd.Timestamp(end)]

        return df.reset_index(drop=True)

    def load_all_symbols(self, freq: str = "1d") -> dict[str, list[Bar]]:
        """加载所有本地存储的品种数据"""
        dir_path = Path(self.config.min5_dir) if freq == "5m" else Path(self.config.daily_dir)
        result = {}
        for p in dir_path.glob("*.parquet"):
            symbol = p.stem
            result[symbol] = self.load_bars(symbol, freq=freq)
        return result

    def load_all_dataframes(self, freq: str = "1d") -> dict[str, pd.DataFrame]:
        """加载所有品种为 DataFrame（编译器直接用，省去转换开销）"""
        dir_path = Path(self.config.min5_dir) if freq == "5m" else Path(self.config.daily_dir)
        result = {}
        for p in dir_path.glob("*.parquet"):
            symbol = p.stem
            df = pq.read_table(str(p)).to_pandas()
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            result[symbol] = df
        return result

    # ── 查询 ──

    def list_symbols(self, freq: str = "1d") -> list[str]:
        """列出所有本地存储的品种"""
        dir_path = Path(self.config.min5_dir) if freq == "5m" else Path(self.config.daily_dir)
        return sorted([p.stem for p in dir_path.glob("*.parquet")])

    def symbol_info(self, symbol: str) -> dict:
        """查看某品种的本地数据信息"""
        info = {}
        for freq in ["1d", "5m"]:
            path = self._parquet_path(symbol, freq)
            if path.exists():
                meta = pq.read_metadata(str(path))
                info[freq] = {
                    "rows": meta.num_rows,
                    "size_bytes": meta.serialized_size,
                    "row_groups": meta.num_row_groups,
                }
        if symbol in self.meta.contracts:
            cm = self.meta.contracts[symbol]
            info["last_fetch"] = cm.last_fetch_ts
            info["source"] = cm.source
            info["error_count"] = cm.error_count
        return info

    # ── 编译缓存 ──

    def save_compile_cache(self, symbol: str, freq: str, result_bytes: bytes):
        """保存编译结果缓存"""
        import pickle
        path = Path(self.config.cache_dir) / f"{symbol}_{freq}.pkl"
        with open(path, "wb") as f:
            pickle.dump(result_bytes, f)

    def load_compile_cache(self, symbol: str, freq: str) -> bytes | None:
        """加载编译结果缓存"""
        import pickle
        path = Path(self.config.cache_dir) / f"{symbol}_{freq}.pkl"
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return pickle.load(f)

    def clear_cache(self):
        """清除所有编译缓存"""
        import shutil
        cache = Path(self.config.cache_dir)
        if cache.exists():
            shutil.rmtree(cache)
            cache.mkdir(parents=True)

    # ── 内部 ──

    def _update_meta(self, symbol: str, freq: str, df: pd.DataFrame):
        """更新元数据"""
        if symbol not in self.meta.contracts:
            from src.data.sina_fetcher import detect_source
            source = detect_source(symbol.lower())
            self.meta.contracts[symbol] = ContractMeta(symbol=symbol, source=source)

        cm = self.meta.contracts[symbol]
        last_date = df["timestamp"].max().isoformat() if len(df) > 0 else ""
        rows = len(df)

        if freq == "5m":
            cm.min5_rows = rows
            cm.min5_last_date = last_date
        else:
            cm.daily_rows = rows
            cm.daily_last_date = last_date

        cm.last_fetch_ts = datetime.now().isoformat()
        self.meta.save(self.config.meta_file)

    def save_meta(self):
        """手动保存元数据"""
        self.meta.save(self.config.meta_file)

    # ── 统计 ──

    def stats(self) -> dict:
        """返回仓库统计信息"""
        daily_symbols = self.list_symbols("1d")
        min5_symbols = self.list_symbols("5m")

        total_daily_rows = 0
        total_min5_rows = 0
        for s in daily_symbols:
            path = self._parquet_path(s, "1d")
            if path.exists():
                total_daily_rows += pq.read_metadata(str(path)).num_rows
        for s in min5_symbols:
            path = self._parquet_path(s, "5m")
            if path.exists():
                total_min5_rows += pq.read_metadata(str(path)).num_rows

        return {
            "daily_symbols": len(daily_symbols),
            "min5_symbols": len(min5_symbols),
            "total_daily_rows": total_daily_rows,
            "total_min5_rows": total_min5_rows,
            "last_full_scan": self.meta.last_full_scan,
        }


# ─── 便捷函数 ─────────────────────────────────────────────

def open_store(base_dir: str = "data/local") -> LocalStore:
    """打开或创建本地数据仓库"""
    return LocalStore(LocalStoreConfig(base_dir=base_dir))
