#!/usr/bin/env python3
"""
可视化工具 — 生成编译结果的 SVG 图表

输出:
  1. 价格路径 + 极值点 + 关键区
  2. 结构详情图
  3. 丛分类总览
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from src.data.loader import load_cu0
from src.compiler.pipeline import compile_full, CompilerConfig
from src.models import ZoneSource


def price_chart_svg(bars, result, width=1200, height=500):
    """生成价格路径 + 极值点 + Zone 的 SVG"""
    if not bars:
        return ""

    # 数据范围
    t_min = bars[0].timestamp
    t_max = bars[-1].timestamp
    p_min = min(b.low for b in bars)
    p_max = max(b.high for b in bars)
    p_range = p_max - p_min or 1
    t_span = (t_max - t_min).days or 1

    margin = {"l": 70, "r": 30, "t": 30, "b": 50}
    pw = width - margin["l"] - margin["r"]
    ph = height - margin["t"] - margin["b"]

    def tx(t):
        return margin["l"] + ((t - t_min).days / t_span) * pw

    def ty(p):
        return margin["t"] + (1 - (p - p_min) / p_range) * ph

    lines = []
    # BG
    lines.append(f'<rect width="{width}" height="{height}" fill="#1a1a2e"/>')

    # Grid
    for i in range(6):
        p = p_min + (p_range * i / 5)
        y = ty(p)
        lines.append(f'<line x1="{margin["l"]}" y1="{y}" x2="{width-margin["r"]}" y2="{y}" stroke="#333" stroke-width="0.5"/>')
        lines.append(f'<text x="{margin["l"]-5}" y="{y+4}" fill="#888" font-size="10" text-anchor="end">{p:.0f}</text>')

    # Year labels
    for year in range(t_min.year, t_max.year + 1):
        dt = datetime(year, 1, 1)
        if t_min <= dt <= t_max:
            x = tx(dt)
            lines.append(f'<line x1="{x}" y1="{margin["t"]}" x2="{x}" y2="{height-margin["b"]}" stroke="#333" stroke-width="0.5"/>')
            lines.append(f'<text x="{x}" y="{height-margin["b"]+15}" fill="#888" font-size="10" text-anchor="middle">{year}</text>')

    # Candlesticks (simplified as close line)
    step = max(1, len(bars) // 600)
    for i in range(0, len(bars), step):
        b = bars[i]
        x = tx(b.timestamp)
        # high-low wick
        lines.append(f'<line x1="{x}" y1="{ty(b.high)}" x2="{x}" y2="{ty(b.low)}" stroke="#555" stroke-width="1"/>')
        # open-close body
        color = "#26a69a" if b.close >= b.open else "#ef5350"
        y1, y2 = sorted([ty(b.open), ty(b.close)])
        lines.append(f'<rect x="{x-1}" y="{y1}" width="2" height="{max(y2-y1,1)}" fill="{color}"/>')

    # Zones
    for z in result.zones:
        y1 = ty(z.upper)
        y2 = ty(z.lower)
        color = "#ff980055" if z.source.value == "high_cluster" else "#2196f355"
        border = "#ff9800" if z.source.value == "high_cluster" else "#2196f3"
        label_type = "高点区" if z.source.value == "high_cluster" else "低点区"
        lines.append(
            f'<rect x="{margin["l"]}" y="{y1}" '
            f'width="{pw}" height="{max(y2 - y1, 2)}" '
            f'fill="{color}" stroke="{border}" stroke-width="0.5"/>'
        )
        # 标注：类型 + 价格 + strength + touches
        lines.append(
            f'<text x="{margin["l"] + 4}" y="{(y1 + y2) / 2 + 4}" '
            f'font-size="10" fill="{border}">'
            f'{label_type} {z.price_center:.0f} '
            f'(强度{z.strength:.1f} / {len(z.touches)}次触及)</text>'
        )

    # Pivots
    for p in result.pivots:
        x = tx(p.t)
        y = ty(p.x)
        lines.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#ffeb3b" stroke="#fff" stroke-width="0.5"/>')

    # Title
    lines.append(f'<text x="{width/2}" y="18" fill="#fff" font-size="14" text-anchor="middle" font-weight="bold">铜连续合约 — 价格结构编译</text>')

    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">\n' + '\n'.join(lines) + '\n</svg>'


def bundle_chart_svg(result, width=1200, height=400):
    """丛分类总览图"""
    bundles = result.bundles
    if not bundles:
        return ""

    lines = []
    lines.append(f'<rect width="{width}" height="{height}" fill="#1a1a2e"/>')
    lines.append(f'<text x="{width/2}" y="22" fill="#fff" font-size="14" text-anchor="middle" font-weight="bold">丛 (Bundle) 分类总览</text>')

    # 颜色映射
    type_colors = {
        "slow_up_fast_down": "#ef5350",
        "fast_up_slow_down": "#26a69a",
        "balanced": "#ff9800",
        "mixed": "#9e9e9e",
    }

    y = 50
    for i, bundle in enumerate(bundles):
        btype = bundle.generator_constraint.split(",")[0].replace("type=", "")
        color = type_colors.get(btype, "#9e9e9e")
        n = len(bundle.structures)

        # Bar
        bar_w = min(n * 40, width - 400)
        lines.append(f'<rect x="200" y="{y-12}" width="{bar_w}" height="20" fill="{color}" rx="3" opacity="0.7"/>')

        # Label
        lines.append(f'<text x="10" y="{y+4}" fill="#fff" font-size="11">{btype}</text>')
        lines.append(f'<text x="195" y="{y+4}" fill="#ccc" font-size="10" text-anchor="end">{n}个结构</text>')

        # Avg ratios
        if bundle.structures:
            avg_sr = sum(s.avg_speed_ratio for s in bundle.structures) / n
            avg_tr = sum(s.avg_time_ratio for s in bundle.structures) / n
            lines.append(f'<text x="{205 + bar_w}" y="{y+4}" fill="#888" font-size="10">speed={avg_sr:.2f} time={avg_tr:.2f}</text>')

        y += 35

    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">\n' + '\n'.join(lines) + '\n</svg>'


def _cycle_bar_height(segment, max_log_rate: float, max_h: float = 60, min_h: float = 8) -> float:
    """用对数幅度（log_rate）归一化 Cycle 柱高，避免硬编码除数"""
    if max_log_rate <= 0:
        return min_h
    ratio = abs(getattr(segment, 'log_rate', 0) or 0) / max_log_rate
    return min_h + ratio * (max_h - min_h)


def structure_detail_svg(structure, idx, width=800, height=320):
    """单个结构的 Cycle 详情图（修订版）"""
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                 f'style="background:#1a1a2e;font-family:monospace">')
    lines.append(
        f'<text x="10" y="22" font-size="13" fill="#90caf9">'
        f'Structure #{idx + 1} — Zone {structure.zone.price_center:.0f} '
        f'(±{structure.zone.bandwidth:.0f}) | '
        f'强度{structure.zone.strength:.1f} | {len(structure.zone.touches)}次触及</text>'
    )

    info = (
        f"cycles={structure.cycle_count}  "
        f"speed_r={structure.avg_speed_ratio:.2f}  "
        f"time_r={structure.avg_time_ratio:.2f}  "
        f"label={getattr(structure, 'primary_label', None) or '未标注'}"
    )
    lines.append(f'<text x="10" y="42" font-size="11" fill="#888">{info}</text>')

    y_base = 180
    x_start = 50
    usable_w = width - 100
    cycles = structure.cycles[:12]
    n = max(len(cycles), 1)
    step = usable_w / n

    # 先算最大 log_rate，用于归一化
    all_log_rates = []
    for c in cycles:
        all_log_rates.append(abs(getattr(c.entry, 'log_rate', 0) or 0))
        all_log_rates.append(abs(getattr(c.exit, 'log_rate', 0) or 0))
    max_log_rate = max(all_log_rates) if all_log_rates else 1.0

    for i, cycle in enumerate(cycles):
        cx = x_start + step * i
        bar_w = max(step * 0.35, 4)

        entry_h = _cycle_bar_height(cycle.entry, max_log_rate)
        exit_h = _cycle_bar_height(cycle.exit, max_log_rate)

        entry_color = "#26a69a" if cycle.entry.delta > 0 else "#ef5350"
        exit_color = "#26a69a" if cycle.exit.delta > 0 else "#ef5350"

        # Entry bar（左）
        ey = y_base - entry_h if cycle.entry.delta > 0 else y_base
        lines.append(
            f'<rect x="{cx}" y="{ey}" width="{bar_w}" height="{entry_h}" '
            f'fill="{entry_color}" opacity="0.85"/>'
        )
        # Exit bar（右）
        exy = y_base - exit_h if cycle.exit.delta > 0 else y_base
        lines.append(
            f'<rect x="{cx + bar_w + 2}" y="{exy}" width="{bar_w}" height="{exit_h}" '
            f'fill="{exit_color}" opacity="0.85"/>'
        )
        # 速度比标注
        lines.append(
            f'<text x="{cx + bar_w}" y="{y_base + 16}" '
            f'font-size="9" fill="#ccc" text-anchor="middle">'
            f'{cycle.speed_ratio:.1f}x</text>'
        )
        # 时间比标注
        lines.append(
            f'<text x="{cx + bar_w}" y="{y_base + 27}" '
            f'font-size="9" fill="#888" text-anchor="middle">'
            f't={cycle.time_ratio:.1f}</text>'
        )

    # 基准线（Zone 价格中心）
    lines.append(
        f'<line x1="{x_start}" y1="{y_base}" '
        f'x2="{x_start + usable_w}" y2="{y_base}" '
        f'stroke="#555" stroke-dasharray="4,3"/>'
    )
    lines.append(
        f'<text x="{x_start - 5}" y="{y_base + 4}" '
        f'font-size="9" fill="#666" text-anchor="end">Zone</text>'
    )

    # 图例
    legend_x = width - 200
    for color, label in [("#26a69a", "上涨段"), ("#ef5350", "下跌段")]:
        lines.append(
            f'<rect x="{legend_x}" y="55" width="10" height="10" fill="{color}"/>'
        )
        lines.append(
            f'<text x="{legend_x + 14}" y="64" font-size="10" fill="#aaa">{label}</text>'
        )
        legend_x += 70

    lines.append(
        f'<text x="{width - 200}" y="82" font-size="9" fill="#555">'
        f'左=entry 右=exit | 高度=log幅度归一化</text>'
    )

    lines.append('</svg>')
    return '\n'.join(lines)


def main():
    print("=" * 60)
    print("  生成可视化图表...")
    print("=" * 60)

    loader = load_cu0("data", dedup=True)
    all_bars = loader.get()

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

    result = compile_full(all_bars, config)

    # 打印结构摘要
    s = result.summary()
    print(f"\n  编译结果: {s['pivots']} 极值点, {s['zones']} 区, {s['structures']} 结构, {s['bundles']} 丛")

    print(f"\n  丛分类:")
    for i, bundle in enumerate(result.bundles):
        print(f"    [{i+1}] {bundle.generator_constraint}")
        for j, st in enumerate(bundle.structures[:3]):
            print(f"        - {st}")
        if len(bundle.structures) > 3:
            print(f"        ... 及 {len(bundle.structures)-3} 个")

    # 生成 SVG
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)

    # 1. 主价格图
    svg1 = price_chart_svg(all_bars, result)
    with open(f"{out_dir}/price_chart.svg", "w") as f:
        f.write(svg1)
    print(f"\n  生成: {out_dir}/price_chart.svg")

    # 2. 丛总览
    svg2 = bundle_chart_svg(result)
    with open(f"{out_dir}/bundle_overview.svg", "w") as f:
        f.write(svg2)
    print(f"  生成: {out_dir}/bundle_overview.svg")

    # 3. 前3个结构详情
    for i, st in enumerate(result.structures[:3]):
        svg3 = structure_detail_svg(st, i)
        with open(f"{out_dir}/structure_{i+1}.svg", "w") as f:
            f.write(svg3)
        print(f"  生成: {out_dir}/structure_{i+1}.svg")

    # 4. 输出 Markdown 报告
    report = generate_report(result, all_bars)
    with open(f"{out_dir}/compile_report.md", "w") as f:
        f.write(report)
    print(f"  生成: {out_dir}/compile_report.md")

    print("\n" + "=" * 60)
    print("  完成")
    print("=" * 60)


def generate_report(result, bars):
    lines = [
        "# 铜连续合约 — 结构编译报告\n",
        f"**数据范围**: {bars[0].timestamp:%Y-%m-%d} ~ {bars[-1].timestamp:%Y-%m-%d} ({len(bars)} bars)\n",
        f"**价格范围**: {min(b.low for b in bars):.0f} ~ {max(b.high for b in bars):.0f}\n",
        "---\n",
        "## 编译统计\n",
        f"- 极值点: {len(result.pivots)}",
        f"- 段: {len(result.segments)}",
        f"- 关键区: {len(result.zones)}",
        f"- 循环: {len(result.cycles)}",
        f"- 结构: {len(result.structures)}",
        f"- 丛: {len(result.bundles)}\n",
        "---\n",
        "## 丛分类\n",
    ]

    for i, bundle in enumerate(result.bundles):
        lines.append(f"### 丛 {i+1}: {bundle.generator_constraint}\n")
        lines.append(f"包含 {len(bundle.structures)} 个结构:\n")
        for j, st in enumerate(bundle.structures):
            lines.append(f"  {j+1}. Zone={st.zone.price_center:.0f} "
                         f"(±{st.zone.bandwidth:.0f}), "
                         f"cycles={st.cycle_count}, "
                         f"speed_r={st.avg_speed_ratio:.2f}, "
                         f"time_r={st.avg_time_ratio:.2f}")
        lines.append("")

    lines.append("---\n")
    lines.append("## 关键区详情\n")
    for i, z in enumerate(result.zones):
        lines.append(f"- **Zone {i+1}**: center={z.price_center:.0f}, "
                     f"bandwidth=±{z.bandwidth:.0f}, "
                     f"source={z.source.value}, "
                     f"strength={z.strength:.1f}, "
                     f"touches={len(z.touches)}")

    lines.append("\n---\n")
    lines.append("## 最强结构详情\n")
    for i, st in enumerate(result.structures[:5]):
        lines.append(f"### 结构 {i+1}\n")
        lines.append(f"- Zone: {st.zone.price_center:.0f} (±{st.zone.bandwidth:.0f})")
        lines.append(f"- Cycles: {st.cycle_count}")
        lines.append(f"- 不变量: {st.invariants}\n")
        for j, c in enumerate(st.cycles[:5]):
            lines.append(f"  Cycle {j+1}: entry={c.entry}, exit={c.exit}, "
                         f"speed_r={c.speed_ratio:.2f}, time_r={c.time_ratio:.2f}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
