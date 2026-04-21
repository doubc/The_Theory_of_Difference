"""
极值点提取 — 局部极值 + 幅度过滤
"""

from __future__ import annotations

from src.models import Point
from src.data.loader import Bar


def extract_pivots(
    bars: list[Bar],
    min_amplitude: float = 0.02,
    min_duration: int = 2,
    noise_filter: float = 0.005,
) -> list[Point]:
    """
    极值提取算法：

    1. 用 min_duration 窗口找局部高低点（swing high / swing low）
    2. 相同类型取极值（连续高点保留最高的）
    3. 幅度过滤：相邻异类极值差 < min_amplitude 则视为噪声
    """
    if len(bars) < min_duration * 2 + 1:
        return []

    n = min_duration
    candidates: list[tuple[int, str, float, datetime]] = []

    for i in range(n, len(bars) - n):
        h = bars[i].high
        l = bars[i].low

        is_swing_high = all(h >= bars[j].high for j in range(i - n, i + n + 1) if j != i)
        is_swing_low = all(l <= bars[j].low for j in range(i - n, i + n + 1) if j != i)

        if is_swing_high:
            candidates.append((i, "high", h, bars[i].timestamp))
        if is_swing_low:
            candidates.append((i, "low", l, bars[i].timestamp))

    if not candidates:
        return []

    candidates.sort(key=lambda c: c[0])

    # 幅度过滤 + 相同类型取极值
    filtered: list[tuple[int, str, float, datetime]] = [candidates[0]]

    for c in candidates[1:]:
        idx, ctype, price, t = c
        last_idx, last_type, last_price, last_t = filtered[-1]

        amplitude = abs(price - last_price) / last_price

        if ctype == last_type:
            if ctype == "high" and price > last_price:
                filtered[-1] = c
            elif ctype == "low" and price < last_price:
                filtered[-1] = c
            continue

        if amplitude >= min_amplitude:
            filtered.append(c)
        elif amplitude >= noise_filter:
            filtered[-1] = c

    return [Point(t=t, x=price, idx=idx) for idx, ctype, price, t in filtered]
