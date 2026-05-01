"""
共享算子函数 — Point、Zone 相关的基础计算

这些函数不依赖任何业务模型，只处理纯数学计算。
被 models.py、relations.py 等模块共用。

迁移历史：
  - v4.2: 算子函数从 relations.py 迁移到此，消除循环依赖
  - 旧代码中的延迟导入（models.py 函数内导入）已改为直接导入
"""

from __future__ import annotations
from datetime import datetime
import math
from typing import Sequence


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


# ═══════════════════════════════════════════════════════════
# Point/Zone 基础算子（从 relations.py 迁移）
# ═══════════════════════════════════════════════════════════


def first_diff(p1: 'Point', p2: 'Point') -> float:
    """一阶差分（价格变化量）"""
    return p2.x - p1.x


def log_diff(p1: 'Point', p2: 'Point') -> float:
    """对数差分（品种无关的收益率）"""
    if p1.x <= 0 or p2.x <= 0:
        return 0.0
    return math.log(p2.x / p1.x)


def second_diff(p1: 'Point', p2: 'Point', p3: 'Point') -> float:
    """二阶差分（曲率/加速度），单位与价格一致"""
    return (p3.x - p2.x) - (p2.x - p1.x)


def time_gap(p1: 'Point', p2: 'Point') -> float:
    """时间间隔（天数），支持 datetime 或 numeric index"""
    if isinstance(p1.t, datetime) and isinstance(p2.t, datetime):
        return (p2.t - p1.t).total_seconds() / 86400.0
    # 假设 p.t 是 numeric index（天数）
    return float(p2.t - p1.t)


def distance_to_zone(p: 'Point', z: 'Zone') -> float:
    """点到 Zone 的距离（相对带宽）"""
    return (p.x - z.price_center) / z.bandwidth if z.bandwidth > 0 else 0.0


def relative_distance_to_zone(p: 'Point', z: 'Zone') -> float:
    """点到 Zone 的相对位置（-1 到 1，0 为中心）"""
    return 2 * distance_to_zone(p, z)


def extrema_dispersion(points: list['Point']) -> float:
    """
    极值点变异系数 (CV) = std / |mean|

    衡量极值点在价格维度上的聚集程度：
    - CV ≈ 0：极值点高度聚集（同价位反复试探）
    - CV ≈ 1：极值点均匀分散
    - CV > 1：极值点高度分散（异常）

    用于判定 Zone 强度和结构稳定性。
    """
    if len(points) < 2:
        return 0.0
    xs = [p.x for p in points]
    m = sum(xs) / len(xs)
    if m == 0:
        return 0.0
    var = sum((x - m) ** 2 for x in xs) / len(xs)
    return math.sqrt(var) / abs(m)


def display_term(text: str) -> str:
    """
    显示文本包装函数。用于 UI 展示时的文本格式化。
    Args:
        text: 原始文本
    Returns:
        格式化后的文本
    """
    return text
