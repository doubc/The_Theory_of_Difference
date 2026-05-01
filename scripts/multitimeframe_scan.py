"""
多时间维度扫描脚本 — 5分钟 + 1小时 + 日线 三维度扫描

功能：
- 全市场多时间维度编译
- 5分钟 vs 日线结构一致性检查
- 1小时 vs 日线结构一致性检查
- 输出多尺度一致性报告
- 筛选高一致性品种

用法：
    python scripts/multitimeframe_scan.py              # 全市场扫描
    python scripts/multitimeframe_scan.py --top 20     # 只显示 Top 20
    python scripts/multitimeframe_scan.py --min-consistency 0.5  # 一致性阈值
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from src.data.local_store import LocalStore, LocalStoreConfig
from src.multitimeframe.comparator import (
    MultiTimeframeComparator, MultiTimeframeReport,
    resample_bars,
)
from src.compiler.pipeline import compile_full, CompilerConfig


# ─── 全市场扫描 ──────────────────────────────────────────

def scan_all(
    store: LocalStore,
    top_n: int = 30,
    min_consistency: float = 0.3,
    start: str | None = None,
    end: str | None = None,
) -> list[MultiTimeframeReport]:
    """
    全市场多时间维度扫描

    Args:
        store: 本地数据仓库
        top_n: 返回前 N 个最一致的品种
        min_consistency: 最低一致性阈值
        start, end: 时间范围

    Returns:
        按一致性排序的报告列表
    """
    comparator = MultiTimeframeComparator(store)
    symbols = store.list_symbols("1d")

    # 检查5分钟数据
    symbols_5m = set(store.list_symbols("5m"))

    # 只扫描有5分钟数据的品种（否则没有跨维度对比意义）
    candidates = [s for s in symbols if s in symbols_5m]
    if not candidates:
        # 没有5分钟数据，只做日线扫描
        candidates = symbols

    print(f"多时间维度扫描: {len(candidates)} 个品种")
    print(f"有5分钟数据: {len(symbols_5m)} 个")

    reports = []
    start_time = time.time()

    for i, sym in enumerate(candidates):
        try:
            report = comparator.compare(sym, start=start, end=end)
            if report.consistency_score >= min_consistency:
                reports.append(report)
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                print(f"  [{i+1}/{len(candidates)}] {elapsed:.0f}s, "
                      f"{len(reports)} above threshold")
        except Exception as e:
            print(f"  ✗ {sym}: {str(e)[:80]}")

    # 按一致性排序
    reports.sort(key=lambda r: r.consistency_score, reverse=True)

    elapsed = time.time() - start_time
    print(f"\n扫描完成: {elapsed:.1f}s, {len(reports)}/{len(candidates)} 品种达标")

    return reports[:top_n]


# ─── 5分钟对比专项 ────────────────────────────────────────

def compare_5min_vs_daily(
    store: LocalStore,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """
    5分钟结构 vs 日线结构 对比

    返回详细的对比结果
    """
    # 加载数据
    bars_5m = store.load_bars(symbol, freq="5m", start=start, end=end)
    bars_1d = store.load_bars(symbol, freq="1d", start=start, end=end)

    if not bars_5m:
        return {"error": "无5分钟数据"}
    if not bars_1d:
        return {"error": "无日线数据"}

    # 编译
    config_5m = CompilerConfig(
        min_amplitude=0.005,
        min_duration=2,
        zone_bandwidth=0.005,
    )
    config_1d = CompilerConfig()

    result_5m = compile_full(bars_5m, config_5m, symbol=symbol)
    result_1d = compile_full(bars_1d, config_1d, symbol=symbol)

    # 对比
    from src.multitimeframe.comparator import cross_timeframe_consistency

    matches = []
    for s1d in result_1d.structures:
        for s5m in result_5m.structures:
            match = cross_timeframe_consistency(s1d, s5m, "1d", "5m")
            if match.consistency_score > 0.3:
                matches.append(match)

    matches.sort(key=lambda m: m.consistency_score, reverse=True)

    return {
        "symbol": symbol,
        "bars_5m": len(bars_5m),
        "bars_1d": len(bars_1d),
        "structures_5m": len(result_5m.structures),
        "structures_1d": len(result_1d.structures),
        "matches": len(matches),
        "top_matches": [
            {
                "consistency": m.consistency_score,
                "zone_overlap": m.zone_overlap,
                "direction_match": m.direction_match,
                "zone_1d": m.structure_a.zone.price_center,
                "zone_5m": m.structure_b.zone.price_center,
                "cycles_1d": m.structure_a.cycle_count,
                "cycles_5m": m.structure_b.cycle_count,
            }
            for m in matches[:5]
        ],
    }


# ─── 1小时对比专项 ────────────────────────────────────────

def compare_1h_vs_daily(
    store: LocalStore,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """
    1小时结构 vs 日线结构 对比

    从5分钟数据重采样为1小时，再与日线对比。
    """
    bars_5m = store.load_bars(symbol, freq="5m", start=start, end=end)
    bars_1d = store.load_bars(symbol, freq="1d", start=start, end=end)

    if not bars_5m:
        return {"error": "无5分钟数据（无法生成1小时线）"}
    if not bars_1d:
        return {"error": "无日线数据"}

    # 5分钟 → 1小时
    bars_1h = resample_bars(bars_5m, "1h")

    # 编译
    config_1h = CompilerConfig(
        min_amplitude=0.01,
        min_duration=2,
        zone_bandwidth=0.008,
    )
    config_1d = CompilerConfig()

    result_1h = compile_full(bars_1h, config_1h, symbol=symbol)
    result_1d = compile_full(bars_1d, config_1d, symbol=symbol)

    # 对比
    from src.multitimeframe.comparator import cross_timeframe_consistency

    matches = []
    for s1d in result_1d.structures:
        for s1h in result_1h.structures:
            match = cross_timeframe_consistency(s1d, s1h, "1d", "1h")
            if match.consistency_score > 0.3:
                matches.append(match)

    matches.sort(key=lambda m: m.consistency_score, reverse=True)

    return {
        "symbol": symbol,
        "bars_1h": len(bars_1h),
        "bars_1d": len(bars_1d),
        "structures_1h": len(result_1h.structures),
        "structures_1d": len(result_1d.structures),
        "matches": len(matches),
        "top_matches": [
            {
                "consistency": m.consistency_score,
                "zone_overlap": m.zone_overlap,
                "direction_match": m.direction_match,
                "zone_1d": m.structure_a.zone.price_center,
                "zone_1h": m.structure_b.zone.price_center,
            }
            for m in matches[:5]
        ],
    }


# ─── 报告生成 ────────────────────────────────────────────

def print_scan_report(reports: list[MultiTimeframeReport]):
    """打印扫描报告"""
    print(f"\n{'='*70}")
    print(f"多时间维度扫描报告 — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*70}")

    if not reports:
        print("无达标品种")
        return

    # 一致性分布
    high = sum(1 for r in reports if r.consistency_score > 0.7)
    mid = sum(1 for r in reports if 0.4 < r.consistency_score <= 0.7)
    low = sum(1 for r in reports if r.consistency_score <= 0.4)

    print(f"\n一致性分布: 🟢高({high}) 🟡中({mid}) 🔴低({low})")

    # Top 品种
    print(f"\n{'─'*70}")
    print(f"{'品种':<10} {'一致性':>8} {'1D结构':>8} {'5M结构':>8} {'匹配':>8} {'判断':>10}")
    print(f"{'─'*70}")

    for r in reports:
        # 获取各维度结构数
        s_1d = r.timeframe_results.get("1d")
        s_5m = r.timeframe_results.get("5m")
        n_1d = len(s_1d.structures) if s_1d and s_1d.has_structures else 0
        n_5m = len(s_5m.structures) if s_5m and s_5m.has_structures else 0

        verdict = "🟢高" if r.consistency_score > 0.7 else "🟡中" if r.consistency_score > 0.4 else "🔴低"
        print(
            f"{r.symbol:<10} {r.consistency_score:>8.2f} {n_1d:>8} {n_5m:>8} "
            f"{len(r.cross_matches):>8} {verdict:>10}"
        )

    # 详细分析 Top 5
    print(f"\n{'='*70}")
    print("Top 5 详细分析:")
    print(f"{'='*70}")

    for i, r in enumerate(reports[:5]):
        print(f"\n--- #{i+1} {r.symbol} (一致性: {r.consistency_score:.2f}) ---")
        print(r.summary())


# ─── CLI 入口 ─────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="多时间维度扫描")
    parser.add_argument("--symbols", default="", help="指定品种")
    parser.add_argument("--top", type=int, default=30, help="显示前N个")
    parser.add_argument("--min-consistency", type=float, default=0.3, help="最低一致性")
    parser.add_argument("--start", default="", help="开始日期")
    parser.add_argument("--end", default="", help="结束日期")
    parser.add_argument("--store-dir", default="data/local")
    parser.add_argument("--detail", default="", help="单品种详细对比")
    args = parser.parse_args()

    store = LocalStore(LocalStoreConfig(base_dir=args.store_dir))

    if args.detail:
        # 单品种详细对比
        sym = args.detail.upper()
        print(f"\n=== {sym} 5分钟 vs 日线 ===")
        r5 = compare_5min_vs_daily(store, sym, start=args.start or None, end=args.end or None)
        if "error" in r5:
            print(f"  {r5['error']}")
        else:
            print(f"  5分钟: {r5['structures_5m']} 结构")
            print(f"  日线:  {r5['structures_1d']} 结构")
            print(f"  匹配:  {r5['matches']} 对")
            for m in r5.get("top_matches", []):
                print(f"    一致性={m['consistency']:.2f}, Zone重叠={m['zone_overlap']:.2f}")

        print(f"\n=== {sym} 1小时 vs 日线 ===")
        r1 = compare_1h_vs_daily(store, sym, start=args.start or None, end=args.end or None)
        if "error" in r1:
            print(f"  {r1['error']}")
        else:
            print(f"  1小时: {r1['structures_1h']} 结构")
            print(f"  日线:  {r1['structures_1d']} 结构")
            print(f"  匹配:  {r1['matches']} 对")
    else:
        # 全市场扫描
        reports = scan_all(
            store,
            top_n=args.top,
            min_consistency=args.min_consistency,
            start=args.start or None,
            end=args.end or None,
        )
        print_scan_report(reports)


if __name__ == "__main__":
    main()
