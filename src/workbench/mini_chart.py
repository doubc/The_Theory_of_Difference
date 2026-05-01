"""
紧凑缩略图 SVG 渲染 —— 支持多种图表类型

升级内容：
  - 支持 K 线图、折线图、柱状图
  - 改进的配色方案
  - 支持 Zone 标注和信号标记
  - 支持成交量柱
"""
from __future__ import annotations
from typing import List, Optional, Tuple


def mini_price_svg(bars, zones=None, width: int = 200, height: int = 80,
                   show_volume: bool = False, highlight_last: bool = True) -> str:
    """基础折线图 SVG"""
    if not bars:
        return ""
    zones = zones or []
    p_min = min(b.low for b in bars)
    p_max = max(b.high for b in bars)
    p_range = p_max - p_min or 1

    # 成交量区域
    vol_height = height * 0.2 if show_volume else 0
    price_height = height - vol_height

    def tx(i: int) -> float:
        return (i / max(len(bars) - 1, 1)) * width

    def ty(p: float) -> float:
        return price_height - ((p - p_min) / p_range) * price_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:#0a192f;border-radius:6px">'
    ]

    # Zone 横带
    for z in zones:
        y1, y2 = ty(z.upper), ty(z.lower)
        color = "#ff980033" if hasattr(z, 'source') and z.source.value == "high_cluster" else "#2196f333"
        parts.append(
            f'<rect x="0" y="{y1:.1f}" width="{width}" '
            f'height="{max(y2 - y1, 1):.1f}" fill="{color}"/>'
        )
        # Zone 中线
        y_center = ty(z.price_center)
        parts.append(
            f'<line x1="0" y1="{y_center:.1f}" x2="{width}" y2="{y_center:.1f}" '
            f'stroke="{color.replace("33", "66")}" stroke-width="0.5" stroke-dasharray="4,2"/>'
        )

    # 走势折线（渐变）
    pts = " ".join(f"{tx(i):.1f},{ty(b.close):.1f}" for i, b in enumerate(bars))
    parts.append(
        f'<defs><linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#64ffda" stop-opacity="0.8"/>'
        f'<stop offset="100%" stop-color="#64ffda" stop-opacity="0.2"/>'
        f'</linearGradient></defs>'
    )

    # 填充区域
    fill_pts = f"{tx(0):.1f},{price_height} {pts} {tx(len(bars)-1):.1f},{price_height}"
    parts.append(
        f'<polygon points="{fill_pts}" fill="url(#lineGrad)" opacity="0.3"/>'
    )

    # 折线
    parts.append(
        f'<polyline points="{pts}" fill="none" stroke="#64ffda" stroke-width="1.5"/>'
    )

    # 起止点
    parts.append(
        f'<circle cx="{tx(0):.1f}" cy="{ty(bars[0].close):.1f}" r="2" fill="#8892b0"/>'
    )

    if highlight_last:
        last_x = tx(len(bars) - 1)
        last_y = ty(bars[-1].close)
        # 高亮最后一个点
        parts.append(
            f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="#64ffda" opacity="0.6"/>'
        )
        parts.append(
            f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.5" fill="#64ffda"/>'
        )

    # 成交量柱
    if show_volume and bars:
        vol_max = max(b.volume for b in bars) if bars else 1
        vol_max = max(vol_max, 1)
        bar_width = max(width / len(bars) * 0.6, 1)
        for i, b in enumerate(bars):
            x = tx(i) - bar_width / 2
            vol_h = (b.volume / vol_max) * vol_height
            vol_y = height - vol_h
            color = "#ef535066" if b.close >= b.open else "#26a69a66"
            parts.append(
                f'<rect x="{x:.1f}" y="{vol_y:.1f}" width="{bar_width:.1f}" '
                f'height="{vol_h:.1f}" fill="{color}"/>'
            )

    parts.append("</svg>")
    return "".join(parts)


def mini_candlestick_svg(bars, zones=None, width: int = 200, height: int = 80) -> str:
    """迷你 K 线图 SVG"""
    if not bars:
        return ""
    zones = zones or []
    p_min = min(b.low for b in bars)
    p_max = max(b.high for b in bars)
    p_range = p_max - p_min or 1

    def tx(i: int) -> float:
        return (i / max(len(bars) - 1, 1)) * width

    def ty(p: float) -> float:
        return height - ((p - p_min) / p_range) * height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:#0a192f;border-radius:6px">'
    ]

    # Zone 横带
    for z in zones:
        y1, y2 = ty(z.upper), ty(z.lower)
        parts.append(
            f'<rect x="0" y="{y1:.1f}" width="{width}" '
            f'height="{max(y2 - y1, 1):.1f}" fill="#2196f322"/>'
        )

    # K 线
    candle_width = max(width / len(bars) * 0.6, 2)
    for i, b in enumerate(bars):
        x = tx(i)
        color = "#ef5350" if b.close >= b.open else "#26a69a"
        body_top = ty(max(b.open, b.close))
        body_bottom = ty(min(b.open, b.close))
        body_height = max(body_bottom - body_top, 1)

        # 影线
        parts.append(
            f'<line x1="{x:.1f}" y1="{ty(b.high):.1f}" x2="{x:.1f}" y2="{ty(b.low):.1f}" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        # 实体
        parts.append(
            f'<rect x="{x - candle_width/2:.1f}" y="{body_top:.1f}" '
            f'width="{candle_width:.1f}" height="{body_height:.1f}" '
            f'fill="{color}" rx="0.5"/>'
        )

    parts.append("</svg>")
    return "".join(parts)


def mini_comparison_svg(bars_a, bars_b, name_a: str = "A", name_b: str = "B",
                        width: int = 300, height: int = 120) -> str:
    """双品种对比 SVG（归一化叠加）"""
    if not bars_a or not bars_b:
        return ""

    # 归一化到 0-1
    def normalize(bars):
        p_min = min(b.low for b in bars)
        p_max = max(b.high for b in bars)
        p_range = p_max - p_min or 1
        return [(b.close - p_min) / p_range for b in bars]

    norm_a = normalize(bars_a)
    norm_b = normalize(bars_b)

    def tx_a(i): return (i / max(len(norm_a) - 1, 1)) * width
    def tx_b(i): return (i / max(len(norm_b) - 1, 1)) * width
    def ty(v): return height - v * height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:#0a192f;border-radius:6px">'
    ]

    # 品种 A
    pts_a = " ".join(f"{tx_a(i):.1f},{ty(v):.1f}" for i, v in enumerate(norm_a))
    parts.append(f'<polyline points="{pts_a}" fill="none" stroke="#64ffda" stroke-width="1.5"/>')

    # 品种 B
    pts_b = " ".join(f"{tx_b(i):.1f},{ty(v):.1f}" for i, v in enumerate(norm_b))
    parts.append(f'<polyline points="{pts_b}" fill="none" stroke="#ff9800" stroke-width="1.5"/>')

    # 图例
    parts.append(
        f'<text x="5" y="12" fill="#64ffda" font-size="10" font-family="sans-serif">{name_a}</text>'
    )
    parts.append(
        f'<text x="5" y="24" fill="#ff9800" font-size="10" font-family="sans-serif">{name_b}</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


def zone_sequence_svg(zones: list, current_price: float = 0,
                      width: int = 200, height: int = 60) -> str:
    """稳态序列可视化 SVG"""
    if not zones:
        return ""

    all_prices = []
    for z in zones:
        all_prices.extend([z.get("upper", 0), z.get("lower", 0)])
    if current_price:
        all_prices.append(current_price)

    p_min = min(all_prices) if all_prices else 0
    p_max = max(all_prices) if all_prices else 1
    p_range = p_max - p_min or 1

    def ty(p): return height - ((p - p_min) / p_range) * height * 0.8 - height * 0.1

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:#0a192f;border-radius:6px">'
    ]

    zone_width = width / max(len(zones), 1) * 0.7
    gap = width / max(len(zones), 1) * 0.3

    for i, z in enumerate(zones):
        x = i * (zone_width + gap) + gap / 2
        center = z.get("center", 0)
        bw = z.get("bw", 0)
        upper = center + bw
        lower = center - bw

        y_upper = ty(upper)
        y_lower = ty(lower)
        zone_h = max(y_lower - y_upper, 2)

        # Zone 矩形
        color = "#2196f3" if i < len(zones) - 1 else "#64ffda"
        parts.append(
            f'<rect x="{x:.1f}" y="{y_upper:.1f}" width="{zone_width:.1f}" '
            f'height="{zone_h:.1f}" fill="{color}33" stroke="{color}" stroke-width="1" rx="2"/>'
        )
        # 中线
        y_center = ty(center)
        parts.append(
            f'<line x1="{x:.1f}" y1="{y_center:.1f}" x2="{x+zone_width:.1f}" y2="{y_center:.1f}" '
            f'stroke="{color}" stroke-width="0.5" stroke-dasharray="2,2"/>'
        )

    # 当前价格线
    if current_price:
        y_price = ty(current_price)
        parts.append(
            f'<line x1="0" y1="{y_price:.1f}" x2="{width}" y2="{y_price:.1f}" '
            f'stroke="#ef5350" stroke-width="1" stroke-dasharray="4,2"/>'
        )
        parts.append(
            f'<text x="{width-5}" y="{y_price-3}" fill="#ef5350" font-size="9" '
            f'text-anchor="end" font-family="sans-serif">{current_price:.0f}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
