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
    volume_weighted: bool = False,
    volume_boost: float = 0.3,
) -> list[Point]:
    """
    极值点提取。

    Args:
        volume_weighted: 是否启用成交量加权模式（V1.6 P1 D6.3）
                         高成交量极值被赋予更低的过滤阈值，更容易被保留
        volume_boost: 成交量加权系数，越大 = 高量极值越容易保留
    """
    if len(bars) < 2 * min_duration + 1:
        return []

    # 预计算成交量分位数（用于 volume_weighted 模式）
    if volume_weighted and bars:
        vols = sorted([b.volume for b in bars if b.volume > 0])
        if vols:
            vol_median = vols[len(vols) // 2]
            vol_p75 = vols[int(len(vols) * 0.75)]
        else:
            vol_median = 1.0
            vol_p75 = 1.0
    else:
        vol_median = 1.0
        vol_p75 = 1.0

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

    # Step 3: 异类幅度过滤（含 volume_weighted 模式）
    def amp(a: float, b: float) -> float:
        if use_log and a > 0 and b > 0:
            return abs(math.log(b) - math.log(a))
        return abs(b - a) / max(abs(a), 1e-9)

    def _effective_threshold(idx: int) -> float:
        """根据成交量调整阈值：高成交量极值更容易保留"""
        if not volume_weighted:
            return min_amplitude
        vol = bars[idx].volume if idx < len(bars) else 0
        if vol > vol_p75:
            return min_amplitude * (1 - volume_boost)  # 高量极值：降低阈值
        elif vol < vol_median:
            return min_amplitude * (1 + volume_boost * 0.5)  # 低量极值：提高阈值
        return min_amplitude

    filtered: list[tuple[int, str, float]] = []
    for c in merged:
        if not filtered:
            filtered.append(c)
            continue
        last = filtered[-1]
        delta = amp(last[2], c[2])
        effective_threshold = _effective_threshold(c[0])

        if delta >= effective_threshold:
            filtered.append(c)
        elif delta < noise_filter:
            # 整段噪声：丢弃新 c
            continue
        else:
            # 中间灰区：保留更极端的一端
            if len(filtered) >= 2:
                if last[1] == "high" and c[2] > last[2]:
                    filtered[-1] = c
                elif last[1] == "low" and c[2] < last[2]:
                    filtered[-1] = c
            else:
                filtered.append(c)

    # Step 4: 后处理 — 强制交替（修复灰区替换可能破坏的交替性）
    if len(filtered) < 2:
        return [
            Point(t=bars[idx].timestamp, x=price, idx=idx)
            for idx, _, price in filtered
        ]

    strict: list[tuple[int, str, float]] = [filtered[0]]
    for c in filtered[1:]:
        last = strict[-1]
        if c[1] != last[1]:
            # 类型不同 → 交替成立
            strict.append(c)
        else:
            # 类型相同 → 合并：保留更极端的
            if c[1] == "high" and c[2] > last[2]:
                strict[-1] = c
            elif c[1] == "low" and c[2] < last[2]:
                strict[-1] = c
            # 否则丢弃 c

    return [
        Point(t=bars[idx].timestamp, x=price, idx=idx)
        for idx, _, price in strict
    ]
