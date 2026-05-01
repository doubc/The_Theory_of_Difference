"""
全市场批量采集器 — 从 Sina Finance 批量抓取所有期货合约数据

功能：
- 65+ 合约并发抓取（日线 + 5分钟线）
- 进度追踪 + 断点续传
- 错误重试 + 速率控制
- 自动存入 LocalStore (Parquet)
- 增量更新（只追加新数据）

用法：
    python -m src.data.batch_fetcher              # 全量抓取日线
    python -m src.data.batch_fetcher --freq 5m    # 全量抓取5分钟线
    python -m src.data.batch_fetcher --symbols cu0,al0,rb0  # 指定品种
    python -m src.data.batch_fetcher --incremental  # 增量更新
"""

from __future__ import annotations

import sys
import time
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.data.sina_fetcher import (
    fetch_bars, detect_source, available_contracts,
    INNER_MAIN, GLOBAL_MAIN, FX_MAIN,
)
from src.data.local_store import LocalStore, LocalStoreConfig, StoreMeta


# ─── 配置 ─────────────────────────────────────────────────

@dataclass
class FetcherConfig:
    max_workers: int = 8          # 并发数
    timeout: int = 15             # 单次请求超时
    retry_count: int = 3          # 重试次数
    retry_delay: float = 2.0      # 重试间隔（秒）
    rate_limit: float = 0.3       # 请求间隔（秒），避免被封
    batch_size: int = 10          # 每批处理数量
    store_dir: str = "data/local"


# ─── 进度追踪 ─────────────────────────────────────────────

@dataclass
class FetchProgress:
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    start_time: float = 0.0

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time if self.start_time else 0

    @property
    def eta(self) -> float:
        if self.completed == 0:
            return 0
        rate = self.completed / self.elapsed
        remaining = self.total - self.completed - self.failed - self.skipped
        return remaining / rate if rate > 0 else 0

    def report(self) -> str:
        pct = (self.completed + self.failed + self.skipped) / self.total * 100 if self.total else 0
        return (
            f"[{pct:.0f}%] {self.completed}✓ {self.failed}✗ {self.skipped}⏭ "
            f"| {self.elapsed:.0f}s elapsed, ~{self.eta:.0f}s remaining"
        )


# ─── 核心采集 ─────────────────────────────────────────────

def fetch_single(
    symbol: str,
    freq: str = "1d",
    timeout: int = 15,
    retry_count: int = 3,
    retry_delay: float = 2.0,
) -> tuple[str, list, str | None]:
    """
    抓取单个品种，返回 (symbol, bars, error)

    带重试的包装函数，用于多线程调用。
    """
    for attempt in range(retry_count):
        try:
            bars = fetch_bars(symbol, freq=freq, timeout=timeout)
            if bars:
                return symbol, bars, None
            else:
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    continue
                return symbol, [], f"空数据（{retry_count}次尝试）"
        except Exception as e:
            if attempt < retry_count - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return symbol, [], str(e)
    return symbol, [], "未知错误"


def batch_fetch(
    symbols: list[str],
    freq: str = "1d",
    config: FetcherConfig | None = None,
    incremental: bool = True,
    progress_callback=None,
) -> FetchProgress:
    """
    批量抓取多个品种的数据

    Args:
        symbols: 品种代码列表，如 ["cu0", "al0", "rb0"]
        freq: "1d" 日线 / "5m" 5分钟线
        config: 采集配置
        incremental: 是否增量更新（只追加新数据）
        progress_callback: 进度回调函数 fn(progress: FetchProgress)

    Returns:
        FetchProgress 进度对象
    """
    if config is None:
        config = FetcherConfig()

    store = LocalStore(LocalStoreConfig(base_dir=config.store_dir))
    progress = FetchProgress(total=len(symbols), start_time=time.time())

    # 按 batch_size 分批
    for batch_start in range(0, len(symbols), config.batch_size):
        batch = symbols[batch_start:batch_start + config.batch_size]

        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            futures = {
                executor.submit(
                    fetch_single, sym, freq,
                    config.timeout, config.retry_count, config.retry_delay
                ): sym
                for sym in batch
            }

            for future in as_completed(futures):
                sym = futures[future]
                try:
                    symbol, bars, error = future.result()

                    if error:
                        progress.failed += 1
                        progress.errors[symbol] = error
                    elif not bars:
                        progress.skipped += 1
                    else:
                        # 存入本地仓库
                        if incremental:
                            count = store.incremental_update(symbol, bars, freq=freq)
                        else:
                            count = store.save_bars(symbol, bars, freq=freq)
                        progress.completed += 1

                except Exception as e:
                    progress.failed += 1
                    progress.errors[sym] = str(e)

                if progress_callback:
                    progress_callback(progress)

        # 批次间延迟
        if batch_start + config.batch_size < len(symbols):
            time.sleep(config.rate_limit * 2)

    # 保存元数据
    store.meta.last_full_scan = datetime.now().isoformat()
    store.save_meta()

    return progress


def fetch_all_market(
    freq: str = "1d",
    config: FetcherConfig | None = None,
    incremental: bool = True,
    progress_callback=None,
) -> FetchProgress:
    """
    全市场采集：抓取所有预置合约

    Args:
        freq: "1d" / "5m"
        config: 配置
        incremental: 增量更新
        progress_callback: 进度回调

    Returns:
        FetchProgress
    """
    all_symbols = []
    for group_name, symbols in available_contracts().items():
        all_symbols.extend(symbols)

    # 去重
    all_symbols = list(dict.fromkeys(all_symbols))

    print(f"开始全市场采集: {len(all_symbols)} 个合约, freq={freq}")
    print(f"并发={config.max_workers if config else 8}, 增量={incremental}")

    return batch_fetch(all_symbols, freq=freq, config=config,
                       incremental=incremental, progress_callback=progress_callback)


# ─── 增量更新检测 ─────────────────────────────────────────

def detect_stale_contracts(store: LocalStore, freq: str = "1d", max_age_days: int = 2) -> list[str]:
    """检测需要更新的合约（超过 max_age_days 天未更新）"""
    stale = []
    now = datetime.now()
    threshold = now - __import__("datetime").timedelta(days=max_age_days)

    for symbol in store.list_symbols(freq=freq):
        info = store.symbol_info(symbol)
        last_date_str = info.get(freq, {}).get("daily_last_date", "") if freq == "1d" else info.get(freq, {}).get("min5_last_date", "")
        if not last_date_str:
            stale.append(symbol)
            continue
        try:
            last_date = datetime.fromisoformat(last_date_str.replace("Z", "+00:00").split("+")[0])
            if last_date < threshold:
                stale.append(symbol)
        except (ValueError, TypeError):
            stale.append(symbol)

    return stale


def smart_update(
    freq: str = "1d",
    max_age_days: int = 2,
    config: FetcherConfig | None = None,
) -> FetchProgress:
    """
    智能更新：只抓取过期合约

    检查本地数据最后日期，只更新超过 max_age_days 天未更新的合约。
    """
    store = LocalStore(LocalStoreConfig(base_dir=(config or FetcherConfig()).store_dir))
    stale = detect_stale_contracts(store, freq=freq, max_age_days=max_age_days)

    if not stale:
        print("所有合约数据都是最新的，无需更新。")
        return FetchProgress(total=0, completed=0)

    print(f"检测到 {len(stale)} 个过期合约，开始更新...")
    return batch_fetch(stale, freq=freq, config=config, incremental=True)


# ─── CLI 入口 ─────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="全市场数据批量采集器")
    parser.add_argument("--freq", default="1d", choices=["1d", "5m"], help="数据频率")
    parser.add_argument("--symbols", default="", help="指定品种（逗号分隔），留空则全市场")
    parser.add_argument("--incremental", action="store_true", default=True, help="增量更新")
    parser.add_argument("--full", action="store_true", help="全量覆盖（非增量）")
    parser.add_argument("--smart", action="store_true", help="智能更新（只更新过期合约）")
    parser.add_argument("--max-age", type=int, default=2, help="智能更新：过期天数阈值")
    parser.add_argument("--workers", type=int, default=8, help="并发数")
    parser.add_argument("--store-dir", default="data/local", help="本地仓库目录")
    args = parser.parse_args()

    config = FetcherConfig(
        max_workers=args.workers,
        store_dir=args.store_dir,
    )

    def on_progress(p):
        sys.stdout.write(f"\r{p.report()}")
        sys.stdout.flush()

    if args.smart:
        progress = smart_update(freq=args.freq, max_age_days=args.max_age, config=config)
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        progress = batch_fetch(
            symbols, freq=args.freq, config=config,
            incremental=not args.full, progress_callback=on_progress,
        )
    else:
        progress = fetch_all_market(
            freq=args.freq, config=config,
            incremental=not args.full, progress_callback=on_progress,
        )

    print(f"\n\n{'='*50}")
    print(f"采集完成!")
    print(f"  成功: {progress.completed}")
    print(f"  失败: {progress.failed}")
    print(f"  跳过: {progress.skipped}")
    print(f"  耗时: {progress.elapsed:.1f}s")

    if progress.errors:
        print(f"\n失败详情:")
        for sym, err in progress.errors.items():
            print(f"  {sym}: {err}")


if __name__ == "__main__":
    main()
