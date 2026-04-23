"""
极值点提取 — 自适应窗口 + 局部极值 + 单调幅度过滤

v2.5 升级:
  - 自适应窗口: 根据局部波动率自动调整 swing 检测窗口
  - 分形一致性: 多尺度验证极值点的稳健性
  - 成交量加权: 高成交量极值优先保留 (V1.6 P1 D6.3)

算法流程:
  1. 计算局部波动率 → 自适应窗口大小
  2. 多窗口 swing 检测 + 分形一致性过滤
  3. 合并相邻同类型极值（连续高点保留最高，连续低点保留最低）
  4. 异类极值幅度过滤（幅度 < min_amplitude 则视为震荡）
  5. 强制交替后处理
"""

from __future__ import annotations
import math
from src.models import Point
from src.data.loader import Bar


def _local_volatility(bars: list[Bar], center: int, window: int = 20) -> float:
    """
    计算 center 附近的局部波动率（日收益率标准差）。
    用于自适应调整极值检测窗口。
    """
    lo = max(0, center - window)
    hi = min(len(bars), center + window + 1)
    if hi - lo < 3:
        return 0.01  # 默认中等波动

    returns = []
    for i in range(lo + 1, hi):
        prev_close = bars[i - 1].close
        if prev_close > 0:
            returns.append((bars[i].close - prev_close) / prev_close)

    if len(returns) < 2:
        return 0.01

    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    return math.sqrt(var)


def _adaptive_window(bars: list[Bar], center: int, base_n: int) -> int:
    """
    自适应窗口: 波动率高 → 缩短窗口（捕捉急涨急跌）;
                波动率低 → 延长窗口（过滤缓慢震荡）。

    返回 [base_n // 2, base_n * 3] 范围内的窗口大小。
    """
    vol = _local_volatility(bars, center)
    median_vol = 0.015  # 典型品种的中位波动率

    if vol <= 0:
        ratio = 1.0
    else:
        ratio = median_vol / vol

    # 高波动(vol > median) → ratio < 1 → 缩短窗口
    # 低波动(vol < median) → ratio > 1 → 延长窗口
    adaptive = int(base_n * ratio)
    return max(base_n // 2, min(base_n * 3, adaptive))


def _fractal_consistency(
    bars: list[Bar],
    idx: int,
    ptype: str,
    price: float,
    base_n: int,
) -> float:
    """
    分形一致性: 用 3 个不同窗口验证同一位置是否都是极值。
    返回 [0, 1]，1 = 三个窗口都确认，0 = 只有原始窗口。
    """
    confirmations = 0
    scales = [max(1, base_n // 2), base_n, base_n * 2]

    for n in scales:
        if idx < n or idx >= len(bars) - n:
            continue

        if ptype == "high":
            left = [bars[j].high for j in range(idx - n, idx)]
            right = [bars[j].high for j in range(idx + 1, idx + n + 1)]
            if left and right and price >= max(left) and price >= max(right):
                confirmations += 1
        else:
            left = [bars[j].low for j in range(idx - n, idx)]
            right = [bars[j].low for j in range(idx + 1, idx + n + 1)]
            if left and right and price <= min(left) and price <= min(right):
                confirmations += 1

    return confirmations / len(scales)


def extract_pivots(
    bars: list[Bar],
    min_amplitude: float = 0.02,
    min_duration: int = 2,
    noise_filter: float = 0.005,
    use_log: bool = True,
    volume_weighted: bool = False,
    volume_boost: float = 0.3,
    adaptive: bool = True,
    fractal_threshold: float = 0.34,
) -> list[Point]:
    """
    极值点提取 — v2.5 自适应版本。

    Args:
        volume_weighted: 是否启用成交量加权模式（V1.6 P1 D6.3）
        volume_boost: 成交量加权系数，越大 = 高量极值越容易保留
        adaptive: 是否启用自适应窗口 (v2.5 新增)
        fractal_threshold: 分形一致性阈值，低于此值的极值点被过滤 (v2.5 新增)
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

    # Step 1: 自适应 swing 检测
    candidates: list[tuple[int, str, float, float]] = []  # (idx, type, price, fractal_score)

    for i in range(min_duration, len(bars) - min_duration):
        # 自适应窗口
        n = _adaptive_window(bars, i, min_duration) if adaptive else min_duration
        if i < n or i >= len(bars) - n:
            continue

        h = bars[i].high
        l = bars[i].low
        left_h = [bars[j].high for j in range(i - n, i)]
        right_h = [bars[j].high for j in range(i + 1, i + n + 1)]
        left_l = [bars[j].low for j in range(i - n, i)]
        right_l = [bars[j].low for j in range(i + 1, i + n + 1)]

        if not left_h or not right_h or not left_l or not right_l:
            continue

        is_swing_high = (
            h >= max(left_h) and h >= max(right_h)
            and (h > max(left_h) or h > max(right_h))
        )
        is_swing_low = (
            l <= min(left_l) and l <= min(right_l)
            and (l < min(left_l) or l < min(right_l))
        )

        if is_swing_high:
            frac = _fractal_consistency(bars, i, "high", h, min_duration)
            candidates.append((i, "high", h, frac))
        if is_swing_low:
            frac = _fractal_consistency(bars, i, "low", l, min_duration)
            candidates.append((i, "low", l, frac))

    if not candidates:
        return []

    candidates.sort(key=lambda c: c[0])

    # Step 1.5: 分形一致性过滤 (v2.5)
    candidates = [c for c in candidates if c[3] >= fractal_threshold]

    # Step 2: 合并相邻同类型，保留极端
    merged: list[tuple[int, str, float, float]] = []
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
            return min_amplitude * (1 - volume_boost)
        elif vol < vol_median:
            return min_amplitude * (1 + volume_boost * 0.5)
        return min_amplitude

    filtered: list[tuple[int, str, float, float]] = []
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
            continue
        else:
            if len(filtered) >= 2:
                if last[1] == "high" and c[2] > last[2]:
                    filtered[-1] = c
                elif last[1] == "low" and c[2] < last[2]:
                    filtered[-1] = c
            else:
                filtered.append(c)

    # Step 4: 强制交替
    if len(filtered) < 2:
        return [
            Point(t=bars[idx].timestamp, x=price, idx=idx)
            for idx, _, price, _ in filtered
        ]

    strict: list[tuple[int, str, float, float]] = [filtered[0]]
    for c in filtered[1:]:
        last = strict[-1]
        if c[1] != last[1]:
            strict.append(c)
        else:
            if c[1] == "high" and c[2] > last[2]:
                strict[-1] = c
            elif c[1] == "low" and c[2] < last[2]:
                strict[-1] = c

    return [
        Point(t=bars[idx].timestamp, x=price, idx=idx)
        for idx, _, price, _ in strict
    ]
