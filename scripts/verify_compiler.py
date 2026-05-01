#!/usr/bin/env python3
"""
阶段验证脚本 — 用铜连续合约数据测试编译器

运行: python3 scripts/verify_compiler.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.loader import load_cu0
from src.compiler.pipeline import compile_full, CompilerConfig


def main():
    print("=" * 60)
    print("  价格结构编译器 — 铜连续合约验证")
    print("=" * 60)

    # 1. 加载数据（带去重）
    print("\n[1] 加载数据（自动去重）...")
    loader = load_cu0("data", dedup=True)

    print("\n    数据质量报告:")
    print(loader.report)

    summary = loader.summary()
    print(f"\n    清洗后: {summary['count']} bars")
    print(f"    范围:   {summary['start']} ~ {summary['end']}")
    print(f"    价格:   {summary['price_range'][0]:.0f} ~ {summary['price_range'][1]:.0f}")

    # 2. 测试：最近两年
    print("\n[2] 编译最近两年...")
    bars = loader.get(start="2024-01-01", end="2026-04-20")
    print(f"    窗口: {bars[0].timestamp:%Y-%m-%d} ~ {bars[-1].timestamp:%Y-%m-%d} ({len(bars)} bars)")

    config = CompilerConfig(
        min_amplitude=0.03,
        min_duration=3,
        noise_filter=0.008,
        zone_bandwidth=0.015,
        cluster_eps=0.02,
        cluster_min_points=2,
        min_cycles=2,
        tolerance=0.03,
    )

    result = compile_full(bars, config)
    s = result.summary()

    print(f"\n[3] 编译结果:")
    print(f"    极值点: {s['pivots']}  段: {s['segments']}  "
          f"区: {s['zones']}  循环: {s['cycles']}  结构: {s['structures']}")

    # 关键区
    if result.zones:
        print(f"\n[4] 关键区 ({len(result.zones)} 个):")
        for z in result.zones[:10]:
            print(f"    {z}")

    # 结构
    if result.structures:
        print(f"\n[5] 结构 ({len(result.structures)} 个):")
        for i, st in enumerate(result.structures[:5]):
            print(f"\n    [{i+1}] {st}")
            print(f"        不变量: {st.invariants}")
            for j, c in enumerate(st.cycles[:3]):
                print(f"        Cycle {j+1}: {c}")

    # 3. 全量数据
    print("\n" + "=" * 60)
    print("[6] 全量数据（2005-2026）编译...")
    all_bars = loader.get()
    result_all = compile_full(all_bars, config)
    s_all = result_all.summary()
    print(f"    极值点: {s_all['pivots']}  段: {s_all['segments']}  "
          f"区: {s_all['zones']}  循环: {s_all['cycles']}  结构: {s_all['structures']}")

    if result_all.structures:
        print(f"\n    最强结构:")
        st = result_all.structures[0]
        print(f"    {st}")
        print(f"    区: {st.zone}")
        print(f"    不变量: {st.invariants}")

    print("\n" + "=" * 60)
    print("  验证完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
