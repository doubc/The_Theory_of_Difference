"""
共享工具函数 — 消除模块间重复代码

本模块提供跨多个子系统复用的统计和数学工具。
所有函数无副作用、无状态，可安全并行调用。
"""

from __future__ import annotations
import math


def safe_cv(vals: list[float]) -> float:
    """
    安全计算变异系数 (Coefficient of Variation)

    CV = std / |mean|
    处理空列表、单元素、零均值等边界情况。

    Args:
        vals: 数值列表

    Returns:
        变异系数 [0, +inf)，空列表或零均值返回 0.0
    """
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    if m == 0:
        return 0.0
    var = sum((v - m) ** 2 for v in vals) / len(vals)
    return math.sqrt(var) / abs(m)


def safe_mean(vals: list[float]) -> float:
    """安全均值，空列表返回 0.0"""
    return sum(vals) / len(vals) if vals else 0.0


def safe_median(vals: list[float]) -> float:
    """安全中位数，空列表返回 0.0"""
    if not vals:
        return 0.0
    xs = sorted(vals)
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 == 1 else (xs[m - 1] + xs[m]) / 2


def safe_stddev(vals: list[float]) -> float:
    """安全标准差，少于 2 个元素返回 0.0"""
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / len(vals)
    return math.sqrt(var)


def normalize_minmax(vals: list[float]) -> list[float]:
    """Min-max 归一化到 [0, 1]，常量序列返回 [0.5, ...]"""
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """将值限制在 [lo, hi] 范围内"""
    return max(lo, min(hi, value))
