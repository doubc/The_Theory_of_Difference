"""
价格上下文模块 — 顺时序价格分位数与价格体制判定

核心原则：所有计算严格顺时序，只用 t 时刻之前的数据，绝不看未来。

用途：
1. 给定一个 Zone 在时间 T 的位置，计算它在历史价格中的分位数
2. 判定当前价格所处的体制（历史高位/中位/低位）
3. 为反差推断提供价格位置信号

V1.6 理论依据：
- Ch2 定义 2.2: 共同反差是"多个差异单元共同面对的外部差异"
  同样的价格聚集，出现在历史高位和历史低位，驱动它的外部反差可能完全不同
- A0: 价格是影子 — 价格位置本身就是差异的低维压缩
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from src.data.loader import Bar


@dataclass
class PriceRegime:
    """
    价格体制判定结果

    percentile: 价格在历史中的分位数 [0, 1]
        0.0 = 历史最低, 1.0 = 历史最高
    regime: 体制标签
        "historical_high"  — percentile > 0.80
        "elevated"         — 0.60 < percentile <= 0.80
        "mid_range"        — 0.40 < percentile <= 0.60
        "depressed"        — 0.20 < percentile <= 0.40
        "historical_low"   — percentile <= 0.20
    lookback_days: 回溯天数
    sample_size: 用于计算的 bar 数量
    """
    percentile: float
    regime: str
    lookback_days: int
    sample_size: int

    @property
    def is_extreme(self) -> bool:
        """是否处于极端位置（历史高位或低位）"""
        return self.percentile > 0.80 or self.percentile < 0.20

    @property
    def regime_label(self) -> str:
        labels = {
            "historical_high": "历史高位",
            "elevated": "偏高",
            "mid_range": "中位",
            "depressed": "偏低",
            "historical_low": "历史低位",
        }
        return labels.get(self.regime, "未知")


@dataclass
class VolatilityContext:
    """
    波动率上下文 — 当前波动率相对于历史的位置

    current_vol: 最近 N 日的日收益率标准差
    percentile: 当前波动率在历史中的分位数 [0, 1]
    regime: 波动率体制 ("high_vol" / "normal_vol" / "low_vol")
    """
    current_vol: float
    percentile: float
    regime: str
    lookback_days: int


def compute_price_percentile(
    bars: Sequence[Bar],
    target_price: float,
    lookback_days: int = 252,
    as_of: datetime | None = None,
) -> PriceRegime:
    """
    计算 target_price 在历史价格中的分位数。

    严格顺时序：只使用 as_of 时刻之前的数据。
    如果 as_of 为 None，使用 bars 的最后一个时间戳。

    Args:
        bars: 按时间排序的 Bar 序列
        target_price: 要评估的价格（如 Zone 的 price_center）
        lookback_days: 回溯天数（默认 252 ≈ 1 年交易日）
        as_of: 截止时间（只看此时间之前的数据）

    Returns:
        PriceRegime 对象
    """
    if not bars:
        return PriceRegime(percentile=0.5, regime="mid_range",
                           lookback_days=0, sample_size=0)

    # 顺时序截断：只用 as_of 之前的数据
    if as_of is not None:
        usable = [b for b in bars if b.timestamp <= as_of]
    else:
        usable = list(bars)

    if not usable:
        return PriceRegime(percentile=0.5, regime="mid_range",
                           lookback_days=0, sample_size=0)

    # 取最近 lookback_days 根 bar
    if len(usable) > lookback_days:
        usable = usable[-lookback_days:]

    # 用 close 价格计算分位数
    closes = [b.close for b in usable]
    n = len(closes)
    below = sum(1 for c in closes if c < target_price)
    percentile = below / n if n > 0 else 0.5

    # 体制判定
    if percentile > 0.80:
        regime = "historical_high"
    elif percentile > 0.60:
        regime = "elevated"
    elif percentile > 0.40:
        regime = "mid_range"
    elif percentile > 0.20:
        regime = "depressed"
    else:
        regime = "historical_low"

    span_days = (usable[-1].timestamp - usable[0].timestamp).days if len(usable) > 1 else 0

    return PriceRegime(
        percentile=round(percentile, 4),
        regime=regime,
        lookback_days=span_days,
        sample_size=n,
    )


def compute_volatility_context(
    bars: Sequence[Bar],
    lookback_days: int = 252,
    short_window: int = 20,
    as_of: datetime | None = None,
) -> VolatilityContext:
    """
    计算当前波动率在历史中的位置。

    严格顺时序：只使用 as_of 时刻之前的数据。

    Args:
        bars: 按时间排序的 Bar 序列
        lookback_days: 历史回溯天数
        short_window: 最近波动率的计算窗口（日）
        as_of: 截止时间

    Returns:
        VolatilityContext 对象
    """
    if not bars or len(bars) < short_window + 1:
        return VolatilityContext(current_vol=0.0, percentile=0.5, regime="normal_vol",
                                 lookback_days=0)

    # 顺时序截断
    if as_of is not None:
        usable = [b for b in bars if b.timestamp <= as_of]
    else:
        usable = list(bars)

    if len(usable) < short_window + 1:
        return VolatilityContext(current_vol=0.0, percentile=0.5, regime="normal_vol",
                                 lookback_days=0)

    # 计算日收益率
    def _daily_returns(sub: Sequence[Bar]) -> list[float]:
        rets = []
        for i in range(1, len(sub)):
            if sub[i - 1].close > 0:
                rets.append((sub[i].close - sub[i - 1].close) / sub[i - 1].close)
        return rets

    # 当前波动率（最近 short_window 日）
    recent_bars = usable[-(short_window + 1):]
    recent_rets = _daily_returns(recent_bars)
    if not recent_rets:
        return VolatilityContext(current_vol=0.0, percentile=0.5, regime="normal_vol",
                                 lookback_days=0)

    mean_r = sum(recent_rets) / len(recent_rets)
    current_vol = math.sqrt(sum((r - mean_r) ** 2 for r in recent_rets) / len(recent_rets))

    # 历史波动率分布（滚动窗口）
    if len(usable) > lookback_days:
        hist_bars = usable[-lookback_days:]
    else:
        hist_bars = usable

    hist_rets = _daily_returns(hist_bars)
    if len(hist_rets) < short_window:
        return VolatilityContext(
            current_vol=round(current_vol, 6),
            percentile=0.5, regime="normal_vol",
            lookback_days=len(usable),
        )

    # 滚动计算历史每日波动率
    hist_vols = []
    for i in range(short_window, len(hist_rets) + 1):
        window = hist_rets[i - short_window:i]
        m = sum(window) / len(window)
        v = math.sqrt(sum((r - m) ** 2 for r in window) / len(window))
        hist_vols.append(v)

    if not hist_vols:
        return VolatilityContext(
            current_vol=round(current_vol, 6),
            percentile=0.5, regime="normal_vol",
            lookback_days=len(usable),
        )

    below = sum(1 for v in hist_vols if v < current_vol)
    percentile = below / len(hist_vols)

    if percentile > 0.75:
        regime = "high_vol"
    elif percentile < 0.25:
        regime = "low_vol"
    else:
        regime = "normal_vol"

    return VolatilityContext(
        current_vol=round(current_vol, 6),
        percentile=round(percentile, 4),
        regime=regime,
        lookback_days=(hist_bars[-1].timestamp - hist_bars[0].timestamp).days if len(hist_bars) > 1 else 0,
    )


def compute_zone_price_context(
    bars: Sequence[Bar],
    zone_center: float,
    lookback_days: int = 252,
    as_of: datetime | None = None,
) -> dict:
    """
    给定 Zone 中心价格，计算其在历史中的完整上下文。

    严格顺时序。返回 dict 包含：
    - price_percentile: 价格分位数
    - price_regime: 价格体制
    - vol_context: 波动率上下文
    - distance_from_peak: 距历史最高价的相对距离
    - distance_from_trough: 距历史最低价的相对距离

    这些信号用于增强反差推断（_infer_contrast）：
    - 历史高位 + 密集试探 → 更可能是恐慌/过剩
    - 历史低位 + 密集试探 → 更可能是供需失衡/底部筑底
    - 中位 + 均匀试探 → 更可能是政策驱动
    """
    price_ctx = compute_price_percentile(bars, zone_center, lookback_days, as_of)
    vol_ctx = compute_volatility_context(bars, lookback_days, as_of=as_of)

    # 顺时序截断
    if as_of is not None:
        usable = [b for b in bars if b.timestamp <= as_of]
    else:
        usable = list(bars)

    if lookback_days and len(usable) > lookback_days:
        usable = usable[-lookback_days:]

    # 距极值的相对距离
    if usable:
        hist_high = max(b.high for b in usable)
        hist_low = min(b.low for b in usable)
        price_range = hist_high - hist_low
        dist_from_peak = (hist_high - zone_center) / price_range if price_range > 0 else 0.5
        dist_from_trough = (zone_center - hist_low) / price_range if price_range > 0 else 0.5
    else:
        dist_from_peak = 0.5
        dist_from_trough = 0.5

    return {
        "price_percentile": price_ctx.percentile,
        "price_regime": price_ctx.regime,
        "price_regime_label": price_ctx.regime_label,
        "vol_percentile": vol_ctx.percentile,
        "vol_regime": vol_ctx.regime,
        "distance_from_peak": round(dist_from_peak, 4),
        "distance_from_trough": round(dist_from_trough, 4),
        "lookback_days": price_ctx.lookback_days,
        "sample_size": price_ctx.sample_size,
    }
