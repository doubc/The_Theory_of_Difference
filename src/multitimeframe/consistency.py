"""
多时间维度一致性指数 (MTF Consistency Index, MCI)
综合三个尺度的：
  1. 方向一致性（趋势 × 通量符号）
  2. Zone 嵌套性（小尺度 Zone 是否落在大尺度 Zone 内）
  3. 阶段对齐度（是否处于协同节奏）
输出 0~1，>0.7 视为强共振，<0.3 视为尺度矛盾
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class TFSnapshot:
    timeframe: str  # '5m' / '1h' / 'D'
    trend: str  # 'up' / 'down' / 'flat'
    flux_sign: int  # +1 / -1 / 0
    phase: str
    zone_center: float
    zone_half_width: float
    quality_score: int


@dataclass
class ConsistencyReport:
    mci: float
    direction_agreement: float
    nesting_score: float
    phase_alignment: float
    verdict: str
    details: str


_PHASE_COMPAT = {
    ("forming", "forming"): 1.0,
    ("forming", "confirmation"): 0.7,
    ("confirmation", "confirmation"): 1.0,
    ("confirmation", "breakout"): 0.8,
    ("breakout", "breakout"): 1.0,
    ("breakout", "confirmation"): 0.8,
    ("stable", "stable"): 1.0,
    ("inversion", "inversion"): 1.0,
}


def _phase_compat(a: str, b: str) -> float:
    key = tuple(sorted([a.lower().lstrip("→"), b.lower().lstrip("→")]))
    return _PHASE_COMPAT.get(key, _PHASE_COMPAT.get((key[1], key[0]), 0.3))


def _pairwise_direction(a: TFSnapshot, b: TFSnapshot) -> float:
    trend_score = 1.0 if a.trend == b.trend else (0.5 if "flat" in (a.trend, b.trend) else 0.0)
    flux_score = 1.0 if a.flux_sign * b.flux_sign > 0 else (0.5 if 0 in (a.flux_sign, b.flux_sign) else 0.0)
    return 0.6 * trend_score + 0.4 * flux_score


def _pairwise_nesting(small: TFSnapshot, large: TFSnapshot) -> float:
    """小尺度 Zone 是否落在大尺度 Zone 内"""
    small_low = small.zone_center - small.zone_half_width
    small_high = small.zone_center + small.zone_half_width
    large_low = large.zone_center - large.zone_half_width
    large_high = large.zone_center + large.zone_half_width
    if small_low >= large_low and small_high <= large_high:
        return 1.0
    overlap = max(0.0, min(small_high, large_high) - max(small_low, large_low))
    small_width = max(small_high - small_low, 1e-9)
    return overlap / small_width


def compute_mci(snapshots: Dict[str, TFSnapshot]) -> ConsistencyReport:
    """
    snapshots: {'5m': ..., '1h': ..., 'D': ...}
    """
    assert set(snapshots.keys()) >= {"5m", "1h", "D"}, "需要三个尺度的快照"
    m5, h1, d1 = snapshots["5m"], snapshots["1h"], snapshots["D"]

    # 1. 方向一致性（两两比较后加权）
    dir_5m_1h = _pairwiseDirection = _pairwise_direction(m5, h1)
    dir_1h_d = _pairwise_direction(h1, d1)
    dir_5m_d = _pairwise_direction(m5, d1)
    direction_agreement = 0.25 * dir_5m_1h + 0.45 * dir_1h_d + 0.30 * dir_5m_d

    # 2. 嵌套性
    nest_5m_1h = _pairwise_nesting(m5, h1)
    nest_1h_d = _pairwise_nesting(h1, d1)
    nesting_score = 0.5 * nest_5m_1h + 0.5 * nest_1h_d

    # 3. 阶段对齐
    pa_5m_1h = _phase_compat(m5.phase, h1.phase)
    pa_1h_d = _phase_compat(h1.phase, d1.phase)
    phase_alignment = 0.4 * pa_5m_1h + 0.6 * pa_1h_d

    # 加权合成：日线主导 → 方向占 50%, 嵌套 30%, 阶段 20%
    mci = 0.50 * direction_agreement + 0.30 * nesting_score + 0.20 * phase_alignment

    # 结论
    if mci >= 0.70:
        verdict = "🟢 强共振 — 三尺度一致，信号可信度高"
    elif mci >= 0.45:
        verdict = "🟡 部分共振 — 主尺度方向一致，次尺度待确认"
    else:
        verdict = "🔴 尺度矛盾 — 可能是噪声或尺度错配，谨慎采信"

    details = (
        f"方向一致性 {direction_agreement:.2f} · "
        f"Zone 嵌套 {nesting_score:.2f} · "
        f"阶段对齐 {phase_alignment:.2f}"
    )

    return ConsistencyReport(
        mci=round(mci, 3),
        direction_agreement=round(direction_agreement, 3),
        nesting_score=round(nesting_score, 3),
        phase_alignment=round(phase_alignment, 3),
        verdict=verdict,
        details=details,
    )
