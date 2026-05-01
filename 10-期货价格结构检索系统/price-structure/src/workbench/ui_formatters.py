"""
UI 格式化函数 — 统一各处散落的格式化逻辑

提供: fmt_direction, fmt_phase, fmt_position, fmt_volume, fmt_flux_color,
      fmt_tier_color, fmt_departure_color, fmt_priority_color, fmt_price_position
"""
from __future__ import annotations


def fmt_direction(direction: str) -> str:
    """方向 → 图标"""
    return {"up": "📈", "down": "📉"}.get(direction, "➡️")


def fmt_phase(phase_code: str) -> str:
    """阶段代码 → 中文标签"""
    return {
        "breakout": "🔴 破缺",
        "confirmation": "🟢 确认",
        "forming": "🔵 形成",
        "stable": "⚪ 稳态",
        "breakdown": "🟠 回落",
    }.get(phase_code, "—")


def fmt_position(price_position_code: str) -> str:
    """位置代码 → 中文"""
    return {"H": "高位", "M": "中位", "L": "低位"}.get(price_position_code, "—")


def fmt_volume(vol: int) -> str:
    """成交量 → 带千分位"""
    return f"{vol:,}"


def fmt_flux_color(flux: float) -> str:
    """通量 → CSS 颜色"""
    if flux > 0.2:
        return "#4caf50"
    if flux < -0.2:
        return "#ef5350"
    return "#999"


def fmt_tier_color(tier: str) -> str:
    """质量层 → CSS 颜色"""
    return {"A": "#4caf50", "B": "#2196f3", "C": "#ff9800"}.get(tier, "#999")


def fmt_departure_color(dep: float) -> str:
    """离稳态分数 → CSS 颜色"""
    if dep > 50:
        return "#4caf50"
    if dep > 25:
        return "#ff9800"
    return "#999"


def fmt_priority_color(ps: float) -> str:
    """优先级分数 → CSS 颜色"""
    if ps >= 60:
        return "#4caf50"
    if ps >= 40:
        return "#ff9800"
    return "#999"


def fmt_price_position(price_position_code: str) -> str:
    """价格位置代码 → 中文（用于筛选器映射）"""
    return {"H": "高位", "M": "中位", "L": "低位"}.get(price_position_code, "—")


def classify_price_position(last_price: float, zone_upper: float,
                            zone_lower: float, zone_center: float,
                            zone_bw: float) -> tuple[str, str]:
    """
    分类价格相对于 Zone 的位置。

    Returns:
        (描述文本, 位置代码 H/M/L)
    """
    if zone_bw <= 0:
        return ("· 稳态内", "M")

    if last_price > zone_upper:
        pct = (last_price - zone_center) / zone_center * 100 if zone_center > 0 else 0
        return (f"↑ 破缺上行 +{pct:.1f}%", "H")
    elif last_price < zone_lower:
        pct = (zone_center - last_price) / zone_center * 100 if zone_center > 0 else 0
        return (f"↓ 破缺下行 -{pct:.1f}%", "L")
    else:
        dist_to_upper = (zone_upper - last_price) / zone_bw
        dist_to_lower = (last_price - zone_lower) / zone_bw
        if dist_to_upper < 0.15 or dist_to_lower < 0.15:
            return (" ! 试探边界", "M")
        return (" · 稳态内", "M")


def build_risk_tags(r: dict) -> list[str]:
    """
    为扫描记录生成风险标签列表。

    Args:
        r: 扫描结果 dict（需包含 motion, is_blind, flux, departure_score 等）

    Returns:
        标签列表，如 ["⚠️高压缩", "🔴破缺"]
    """
    tags = []
    if r.get("is_blind"):
        tags.append("⚠️高压缩")

    phase = r.get("phase_code", "")
    if phase == "breakout":
        tags.append("🔴破缺")
    elif phase == "confirmation":
        tags.append("🟢确认")
    elif phase == "breakdown":
        tags.append("🟠回落")

    if abs(r.get("flux", 0)) > 0.5:
        tags.append("⚡高通量")

    dep = r.get("departure_score", 0)
    if dep > 60:
        tags.append("🔥高活跃")

    return tags
