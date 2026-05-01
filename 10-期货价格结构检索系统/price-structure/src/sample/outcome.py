"""
前向演化标签计算器

给样本打 forward_outcome 标签 — 基于结构结束后的 N 日价格表现
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from src.data.loader import Bar
from src.sample.store import ForwardOutcome


def compute_forward_outcome(
    bars: Sequence[Bar],
    t_end: datetime,
    windows: tuple[int, ...] = (5, 10, 20),
) -> ForwardOutcome:
    """
    计算结构结束后的后续表现

    Args:
        bars: 完整价格序列
        t_end: 结构结束时间
        windows: 计算窗口（天数）

    Returns:
        ForwardOutcome 包含各窗口收益 + 最大涨幅/回撤
    """
    # 找到 t_end 对应的索引
    idx = None
    for i, b in enumerate(bars):
        if b.timestamp >= t_end:
            idx = i
            break

    if idx is None or idx >= len(bars) - 1:
        return ForwardOutcome()

    base = bars[idx].close
    outcome = ForwardOutcome()

    for w in windows:
        end_idx = min(idx + w, len(bars) - 1)
        if end_idx > idx:
            ret = (bars[end_idx].close - base) / base
            setattr(outcome, f"ret_{w}d", ret)

    # 20日内最大涨幅 / 最大回撤
    end_idx = min(idx + 20, len(bars) - 1)
    window_bars = bars[idx + 1: end_idx + 1]
    if window_bars:
        max_p = max(b.high for b in window_bars)
        min_p = min(b.low for b in window_bars)
        outcome.max_rise_20d = (max_p - base) / base
        outcome.max_dd_20d = (min_p - base) / base

    return outcome
