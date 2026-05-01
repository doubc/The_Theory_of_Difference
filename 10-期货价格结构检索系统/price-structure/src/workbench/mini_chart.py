"""
紧凑缩略图 SVG 渲染 —— 200×80 级别，嵌入 HTML 日报。
"""
from __future__ import annotations


def mini_price_svg(bars, zones=None, width: int = 200, height: int = 80) -> str:
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

    # 价格折线
    pts = " ".join(f"{tx(i):.1f},{ty(b.close):.1f}" for i, b in enumerate(bars))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:#f5f7fa">'
    ]
    # Zone 横带
    for z in zones:
        y1, y2 = ty(z.upper), ty(z.lower)
        color = "#ff980066" if z.source.value == "high_cluster" else "#2196f366"
        parts.append(
            f'<rect x="0" y="{y1:.1f}" width="{width}" '
            f'height="{max(y2 - y1, 1):.1f}" fill="{color}"/>'
        )
    # 走势折线
    parts.append(
        f'<polyline points="{pts}" fill="none" stroke="#1565c0" stroke-width="1.2"/>'
    )
    # 起止点
    parts.append(
        f'<circle cx="{tx(0):.1f}" cy="{ty(bars[0].close):.1f}" r="2" fill="#78909c"/>'
    )
    parts.append(
        f'<circle cx="{tx(len(bars) - 1):.1f}" cy="{ty(bars[-1].close):.1f}" '
        f'r="2.5" fill="#c62828"/>'
    )
    parts.append("</svg>")
    return "".join(parts)
