"""
段生成 — 相邻极值点连线成段
"""

from __future__ import annotations

from src.models import Point, Segment


def build_segments(pivots: list[Point]) -> list[Segment]:
    """相邻 pivot 两两成段"""
    if len(pivots) < 2:
        return []
    return [Segment(start=pivots[i], end=pivots[i + 1]) for i in range(len(pivots) - 1)]


def merge_micro_segments(
    segments: list[Segment],
    min_abs_delta_pct: float = 0.005,
) -> list[Segment]:
    """
    合并微小段 — 相对幅度 < 阈值的段，与相邻段合并
    防止高频噪声污染结构识别
    """
    if not segments:
        return []
    result = [segments[0]]
    for seg in segments[1:]:
        last = result[-1]
        rel_delta = seg.abs_delta / seg.start.x if seg.start.x > 0 else 0
        if rel_delta < min_abs_delta_pct:
            result[-1] = Segment(start=last.start, end=seg.end)
        else:
            result.append(seg)
    return result
