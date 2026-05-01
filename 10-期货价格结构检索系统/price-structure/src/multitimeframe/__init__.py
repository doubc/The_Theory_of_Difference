"""
src/multitimeframe/__init__.py — 多时间维度分析包

提供跨时间维度的结构对比和一致性分析。

用法：
    from src.multitimeframe import MultiTimeframeComparator, compare_timeframes
"""

from src.multitimeframe.comparator import (
    MultiTimeframeComparator,
    MultiTimeframeCompiler,
    MultiTimeframeReport,
    CrossTimeframeMatch,
    compare_timeframes,
    resample_bars,
)

__all__ = [
    "MultiTimeframeComparator",
    "MultiTimeframeCompiler",
    "MultiTimeframeReport",
    "CrossTimeframeMatch",
    "compare_timeframes",
    "resample_bars",
]
