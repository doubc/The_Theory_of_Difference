"""
兼容层：把 compile_full 的输出适配为 compute_priority 的入参
用这个适配器而不是直接改扫描脚本，可以随时回退到旧打分
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .priority import compute_priority, compute_amplitude_convergence, PriorityScore


def score_structure(structure: Any, current_bar_date: date) -> PriorityScore:
    """
    输入：compile_full 返回的单个 Structure 对象
    输出：PriorityScore
    """
    zone = structure.zone
    motion = structure.motion

    # 1. 提取试探次数与时间跨度
    cycles = getattr(structure, "cycles", []) or []
    test_count = len(cycles)

    if cycles:
        first_day = cycles[0].start_date
        last_day = cycles[-1].end_date
        duration_days = (last_day - first_day).days
        time_since_last_test = (current_bar_date - last_day).days
        test_amplitudes = [abs(c.amplitude) for c in cycles if hasattr(c, "amplitude")]
    else:
        duration_days = 0
        time_since_last_test = 999
        test_amplitudes = []

    convergence = compute_amplitude_convergence(test_amplitudes)

    # 2. 位置标签
    position_tag = _position_tag(structure)

    # 3. 质量分 & 活跃度（原系统已有，这里假定字段名）
    quality = int(getattr(structure, "quality_score", 60))
    activity = int(getattr(structure, "deviation_activity", 30))

    # 4. 阶段
    phase = str(getattr(motion, "phase_tendency", "forming"))

    return compute_priority(
        phase=phase,
        activity=activity,
        quality=quality,
        position_tag=position_tag,
        test_count=test_count,
        duration_days=duration_days,
        amplitude_convergence=convergence,
        time_since_last_test=time_since_last_test,
    )


def _position_tag(structure: Any) -> str:
    """根据当前价相对 Zone 的位置给 H/L/M/S 四档标签"""
    price = float(getattr(structure, "current_price", 0))
    center = float(structure.zone.price_center)
    half = float(structure.zone.half_width)
    if abs(price - center) <= half:
        return "M"
    deviation_ratio = abs(price - center) / max(half, 1e-9)
    if deviation_ratio > 5.0:
        return "S"
    return "H" if price > center else "L"
