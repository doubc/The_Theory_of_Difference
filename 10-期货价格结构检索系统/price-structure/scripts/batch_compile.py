"""
全市场批量编译脚本 — 一键编译所有本地品种

功能：
- 从 LocalStore 读取所有本地 Parquet 数据
- 并行编译所有品种
- 结果缓存到本地
- 增量编译（只编译新数据）
- 输出全市场结构报告

用法：
    python scripts/batch_compile.py                    # 全市场日线编译
    python scripts/batch_compile.py --freq 5m          # 5分钟线编译
    python scripts/batch_compile.py --symbols cu0,al0  # 指定品种
    python scripts/batch_compile.py --parallel 4       # 4进程并行
"""

from __future__ import annotations

import sys
import time
import json
import pickle
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from src.data.local_store import LocalStore, LocalStoreConfig
from src.compiler.pipeline import compile_full, CompilerConfig, CompileResult


# ─── 单品种编译（进程安全）─────────────────────────────────

def compile_one(args: tuple) -> tuple[str, dict | None, str | None]:
    """
    单品种编译（可在子进程中运行）

    Args:
        args: (symbol, bars_data, config_dict, freq)

    Returns:
        (symbol, result_summary, error)
    """
    symbol, bars_data, config_dict, freq = args

    try:
        # 重建对象
        from src.data.loader import Bar
        bars = [
            Bar(
                symbol=symbol,
                timestamp=datetime.fromisoformat(b["timestamp"]),
                open=b["open"], high=b["high"],
                low=b["low"], close=b["close"],
                volume=b["volume"],
            )
            for b in bars_data
        ]

        config = CompilerConfig(**config_dict)
        result = compile_full(bars, config, symbol=symbol)

        # 序列化摘要（不传整个 CompileResult 跨进程）
        summary = {
            "bars": result.bars_count,
            "pivots": len(result.pivots),
            "segments": len(result.segments),
            "zones": len(result.zones),
            "cycles": len(result.cycles),
            "structures": len(result.structures),
            "bundles": len(result.bundles),
        }

        if result.system_states:
            summary["system_states"] = len(result.system_states)
            summary["reliable_count"] = sum(1 for ss in result.system_states if ss.is_reliable)
            summary["blind_count"] = sum(1 for ss in result.system_states if ss.projection.is_blind)

        # 结构详情
        structures_info = []
        for st in result.structures[:5]:  # 只保留前5个最强结构
            structures_info.append({
                "zone_center": st.zone.price_center,
                "zone_bw": st.zone.bandwidth,
                "cycle_count": st.cycle_count,
                "avg_speed_ratio": st.avg_speed_ratio,
                "avg_time_ratio": st.avg_time_ratio,
                "label": st.label or "",
                "phase_tendency": st.motion.phase_tendency if st.motion else "",
                "conservation_flux": st.motion.conservation_flux if st.motion else 0,
                "is_blind": st.projection.is_blind if st.projection else False,
            })
        summary["top_structures"] = structures_info

        return symbol, summary, None

    except Exception as e:
        return symbol, None, str(e)


# ─── 批量编译 ────────────────────────────────────────────

def batch_compile(
    store: LocalStore,
    symbols: list[str] | None = None,
    freq: str = "1d",
    config: CompilerConfig | None = None,
    parallel: int = 4,
    cache_results: bool = True,
) -> dict:
    """
    全市场批量编译

    Args:
        store: 本地数据仓库
        symbols: 指定品种（None = 全部）
        freq: 数据频率
        config: 编译配置
        parallel: 并行进程数
        cache_results: 是否缓存编译结果

    Returns:
        {
            "total": int,
            "success": int,
            "failed": int,
            "elapsed": float,
            "results": {symbol: summary_dict},
            "errors": {symbol: error_str},
        }
    """
    if config is None:
        config = CompilerConfig()

    if symbols is None:
        symbols = store.list_symbols(freq=freq)

    if not symbols:
        return {"total": 0, "success": 0, "failed": 0, "elapsed": 0,
                "results": {}, "errors": {}}

    print(f"批量编译: {len(symbols)} 个品种, freq={freq}, parallel={parallel}")

    # 预加载所有数据
    all_bars = {}
    for sym in symbols:
        bars = store.load_bars(sym, freq=freq)
        if bars:
            all_bars[sym] = bars

    # 准备任务参数
    config_dict = {
        "min_amplitude": config.min_amplitude,
        "min_duration": config.min_duration,
        "noise_filter": config.noise_filter,
        "use_log_price": config.use_log_price,
        "min_segment_delta_pct": config.min_segment_delta_pct,
        "zone_bandwidth": config.zone_bandwidth,
        "cluster_eps": config.cluster_eps,
        "cluster_min_points": config.cluster_min_points,
        "min_cycles": config.min_cycles,
        "tolerance": config.tolerance,
        "adaptive_pivots": config.adaptive_pivots,
        "fractal_threshold": config.fractal_threshold,
    }

    tasks = []
    for sym in symbols:
        if sym not in all_bars:
            continue
        bars_data = [
            {
                "timestamp": b.timestamp.isoformat(),
                "open": b.open, "high": b.high,
                "low": b.low, "close": b.close,
                "volume": b.volume,
            }
            for b in all_bars[sym]
        ]
        tasks.append((sym, bars_data, config_dict, freq))

    # 并行编译
    results = {}
    errors = {}
    start_time = time.time()

    if parallel <= 1:
        # 单进程
        for task in tasks:
            sym, summary, error = compile_one(task)
            if error:
                errors[sym] = error
            else:
                results[sym] = summary
                print(f"  ✓ {sym}: {summary['structures']} structures")
    else:
        # 多进程
        with ProcessPoolExecutor(max_workers=parallel) as executor:
            futures = {executor.submit(compile_one, t): t[0] for t in tasks}
            done = 0
            for future in as_completed(futures):
                sym = futures[future]
                done += 1
                try:
                    sym, summary, error = future.result()
                    if error:
                        errors[sym] = error
                        print(f"  ✗ {sym}: {error[:80]}")
                    else:
                        results[sym] = summary
                        print(f"  ✓ {sym}: {summary['structures']} structures [{done}/{len(tasks)}]")
                except Exception as e:
                    errors[sym] = str(e)

    elapsed = time.time() - start_time

    # 缓存结果
    if cache_results:
        cache_path = Path(store.config.cache_dir) / f"batch_compile_{freq}_{datetime.now():%Y%m%d_%H%M%S}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "freq": freq,
                "config": config_dict,
                "results": results,
                "errors": errors,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n缓存已保存: {cache_path}")

    # 输出报告
    total_structures = sum(r.get("structures", 0) for r in results.values())
    total_reliable = sum(r.get("reliable_count", 0) for r in results.values())

    print(f"\n{'='*60}")
    print(f"批量编译完成!")
    print(f"  品种: {len(results)}/{len(tasks)} 成功, {len(errors)} 失败")
    print(f"  结构: {total_structures} 个 (其中可靠: {total_reliable})")
    print(f"  耗时: {elapsed:.1f}s ({elapsed/len(tasks):.2f}s/品种)" if tasks else "")

    # Top 10 结构
    if results:
        print(f"\n结构最多的品种 Top 10:")
        top = sorted(results.items(), key=lambda x: x[1].get("structures", 0), reverse=True)[:10]
        for sym, info in top:
            print(f"  {sym}: {info['structures']} structures, "
                  f"{info.get('cycles', 0)} cycles, "
                  f"{info.get('reliable_count', 0)} reliable")

    return {
        "total": len(tasks),
        "success": len(results),
        "failed": len(errors),
        "elapsed": elapsed,
        "results": results,
        "errors": errors,
    }


# ─── CLI 入口 ─────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="全市场批量编译")
    parser.add_argument("--freq", default="1d", choices=["1d", "5m"])
    parser.add_argument("--symbols", default="", help="指定品种（逗号分隔）")
    parser.add_argument("--parallel", type=int, default=4, help="并行进程数")
    parser.add_argument("--no-cache", action="store_true", help="不缓存结果")
    parser.add_argument("--store-dir", default="data/local")
    args = parser.parse_args()

    store = LocalStore(LocalStoreConfig(base_dir=args.store_dir))

    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    batch_compile(
        store,
        symbols=symbols,
        freq=args.freq,
        parallel=args.parallel,
        cache_results=not args.no_cache,
    )


if __name__ == "__main__":
    main()
