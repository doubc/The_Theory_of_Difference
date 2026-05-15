"""
回测指标 — 命中率、平均收益、最大回撤、校准度

每个指标是独立纯函数，输入为预测值和实际值序列。
"""

from __future__ import annotations

import math


def hit_rate(
    predictions: list[str],
    actuals: list[str],
) -> float:
    """
    方向命中率 — 预测方向与实际方向一致的比例

    Args:
        predictions: 预测方向列表 ["up", "down", "up", ...]
        actuals: 实际方向列表 ["up", "up", "down", ...]

    Returns:
        命中率 [0, 1]
    """
    if not predictions or not actuals or len(predictions) != len(actuals):
        return 0.0
    hits = sum(1 for p, a in zip(predictions, actuals) if p == a)
    return hits / len(predictions)


def mean_return(
    returns: list[float],
    weights: list[float] | None = None,
) -> float:
    """
    平均收益 — 等权或加权平均

    Args:
        returns: 收益率列表
        weights: 可选权重列表

    Returns:
        平均收益率
    """
    if not returns:
        return 0.0
    if weights is None:
        return sum(returns) / len(returns)
    if len(weights) != len(returns):
        return sum(returns) / len(returns)
    w_sum = sum(weights)
    if w_sum == 0:
        return 0.0
    return sum(w * r for w, r in zip(weights, returns)) / w_sum


def max_drawdown(
    equity_curve: list[float],
) -> float:
    """
    最大回撤 — 权益曲线从峰值到谷底的最大跌幅

    Args:
        equity_curve: 权益曲线 [100, 105, 98, 102, 95, ...]

    Returns:
        最大回撤 (负数，如 -0.15 = 15% 回撤)
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0

    for v in equity_curve[1:]:
        if v > peak:
            peak = v
        dd = (v - peak) / peak if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd

    return max_dd


def calibration(
    predicted_probs: list[float],
    actual_outcomes: list[bool],
    n_bins: int = 10,
) -> dict:
    """
    校准度 — 预测概率与实际频率的一致性

    完美校准：预测概率 0.7 的事件，实际发生概率也是 0.7。

    Args:
        predicted_probs: 预测概率列表 [0.7, 0.3, 0.9, ...]
        actual_outcomes: 实际结果列表 [True, False, True, ...]
        n_bins: 分桶数

    Returns:
        {
            "bins": [{"pred_mean": float, "actual_freq": float, "count": int}, ...],
            "ece": float,  # Expected Calibration Error
            "mce": float,  # Maximum Calibration Error
        }
    """
    if not predicted_probs or not actual_outcomes or len(predicted_probs) != len(actual_outcomes):
        return {"bins": [], "ece": 0.0, "mce": 0.0}

    # 分桶
    bins = [[] for _ in range(n_bins)]
    for prob, outcome in zip(predicted_probs, actual_outcomes):
        bin_idx = min(int(prob * n_bins), n_bins - 1)
        bins[bin_idx].append((prob, outcome))

    # 计算每个桶的统计
    bin_stats = []
    total_ece = 0.0
    max_ce = 0.0
    total_count = len(predicted_probs)

    for i, bin_items in enumerate(bins):
        if not bin_items:
            continue
        count = len(bin_items)
        pred_mean = sum(p for p, _ in bin_items) / count
        actual_freq = sum(1 for _, o in bin_items if o) / count
        ce = abs(pred_mean - actual_freq)

        bin_stats.append({
            "pred_mean": pred_mean,
            "actual_freq": actual_freq,
            "count": count,
            "calibration_error": ce,
        })

        total_ece += ce * count
        max_ce = max(max_ce, ce)

    ece = total_ece / total_count if total_count > 0 else 0.0

    return {
        "bins": bin_stats,
        "ece": ece,
        "mce": max_ce,
    }
