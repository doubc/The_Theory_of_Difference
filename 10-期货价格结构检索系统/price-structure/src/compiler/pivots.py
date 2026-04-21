"""
极值点提取 — 局部极值 + 单调幅度过滤

算法流程:
1. 扫描窗口内找 swing high / swing low（至少一侧严格）
2. 合并相邻同类型极值（连续高点保留最高，连续低点保留最低）
3. 异类极值幅度过滤（幅度 < min_amplitude 则视为震荡）
"""

from __future__ import annotations
import math
from src.models import Point
from src.data.loader import Bar


def extract_pivots(
    bars: list[Bar],
    min_amplitude: float = 0.02,
    min_duration: int = 2,
    noise_filter: float = 0.005,
    use_log: bool = True,
) -> list[Point]:
    if len(bars) < 2 * min_duration + 1:
        return []

    # Step 1: 找所有 swing high / swing low（带等号，但要至少有一侧严格）
    n = min_duration
    candidates: list[tuple[int, str, float]] = []

    for i in range(n, len(bars) - n):
        h = bars[i].high
        l = bars[i].low
        left_h = [bars[j].high for j in range(i - n, i)]
        right_h = [bars[j].high for j in range(i + 1, i + n + 1)]
        left_l = [bars[j].low for j in range(i - n, i)]
        right_l = [bars[j].low for j in range(i + 1, i + n + 1)]

        is_swing_high = (
            h >= max(left_h) and h >= max(right_h)
            and (h > max(left_h) or h > max(right_h))
        )
        is_swing_low = (
            l <= min(left_l) and l <= min(right_l)
            and (l < min(left_l) or l < min(right_l))
        )
        if is_swing_high:
            candidates.append((i, "high", h))
        if is_swing_low:
            candidates.append((i, "low", l))

    if not candidates:
        return []

    candidates.sort(key=lambda c: c[0])

    # Step 2: 合并相邻同类型，保留极端
    merged: list[tuple[int, str, float]] = []
    for c in candidates:
        if merged and merged[-1][1] == c[1]:
            if (c[1] == "high" and c[2] > merged[-1][2]) or \
               (c[1] == "low" and c[2] < merged[-1][2]):
                merged[-1] = c
        else:
            merged.append(c)

    # Step 3: 异类幅度过滤
    def amp(a: float, b: float) -> float:
        if use_log and a > 0 and b > 0:
            return abs(math.log(b) - math.log(a))
        return abs(b - a) / max(abs(a), 1e-9)

    filtered: list[tuple[int, str, float]] = []
    for c in merged:
        if not filtered:
            filtered.append(c)
            continue
        last = filtered[-1]
        delta = amp(last[2], c[2])

        if delta >= min_amplitude:
            filtered.append(c)
        elif delta < noise_filter:
            # 整段噪声：丢弃新 c
            continue
        else:
            # 中间灰区：保留更极端的一端
            if len(filtered) >= 2:
                prev = filtered[-2]  # 与 last 异类
                # 若 c 比 last 更极端（延续方向），用 c 替换 last
                if last[1] == "high" and c[2] > last[2]:
                    filtered[-1] = c
                elif last[1] == "low" and c[2] < last[2]:
                    filtered[-1] = c
                # 否则丢弃 c（last 是真正的反转极值）
            else:
                # filtered 只有一个元素，无法做方向判断，保守保留
                filtered.append(c)

    return [
        Point(t=bars[idx].timestamp, x=price, idx=idx)
        for idx, _, price in filtered
    ]
