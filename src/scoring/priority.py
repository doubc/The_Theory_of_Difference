"""
优先级打分 v2 — 针对 forming 阶段增加形成深度维度
打分构成（0~100）：
  离稳态活跃度  (0~25)
  质量分        (0~20)
  运动阶段      (0~20)
  价格位置      (0~15)
  形成深度      (0~20)  ← 新增，解决 forming 同质化
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class PriorityScore:
    total: int
    activity: int
    quality: int
    phase: int
    position: int
    formation_depth: int  # 新增
    breakdown: str


def _formation_depth_score(
        test_count: int,
        duration_days: int,
        amplitude_convergence: float,  # 振幅收敛斜率，负值表示收窄
        time_since_last_test: int,
) -> int:
    """
    形成深度：衡量 forming 结构距离"破缺"有多近
    - 试探次数越多 → 越接近临界
    - 持续时间越长 → 动能积累越多
    - 振幅收敛越快 → 压缩越接近爆发
    - 最近一次试探越近 → 活跃度越高
    """
    # 1. 试探密度：2 次=基线，每多一次加分，上限 8 次
    test_score = min(max(test_count - 1, 0), 7) * 1.0  # 0~7

    # 2. 时间深度：0~90 天线性，90+ 天饱和
    duration_score = min(duration_days / 90.0, 1.0) * 5.0  # 0~5

    # 3. 振幅收敛：negative 值越大（收窄越快）得分越高
    if amplitude_convergence < -0.02:
        conv_score = 5.0
    elif amplitude_convergence < -0.005:
        conv_score = 3.0
    elif amplitude_convergence < 0.005:
        conv_score = 1.5
    else:
        conv_score = 0.0

    # 4. 新鲜度：最近一次试探在 5 日内满分
    if time_since_last_test <= 3:
        fresh_score = 3.0
    elif time_since_last_test <= 7:
        fresh_score = 2.0
    elif time_since_last_test <= 15:
        fresh_score = 1.0
    else:
        fresh_score = 0.0

    return int(round(test_score + duration_score + conv_score + fresh_score))


def compute_priority(
        phase: str,
        activity: int,
        quality: int,
        position_tag: str,
        test_count: int = 0,
        duration_days: int = 0,
        amplitude_convergence: float = 0.0,
        time_since_last_test: int = 999,
) -> PriorityScore:
    # 1. 离稳态活跃度（0~25）
    activity_score = min(int(activity * 0.25), 25)

    # 2. 质量分（0~20，原来是 0~15，按 80 分制换算）
    quality_score = min(int(quality * 0.25), 20)

    # 3. 运动阶段（0~20）
    phase_map = {
        "breakout": 20,
        "confirmation": 16,
        "forming": 10,
        "stable": 6,
        "inversion": 4,
    }
    phase_score = phase_map.get(phase.lower().lstrip("→"), 8)

    # 4. 价格位置（0~15）
    position_map = {
        "H": 15,  # 高于稳态
        "L": 12,  # 低于稳态
        "M": 9,  # 稳态内
        "S": 3,  # 远离稳态（过期偏离大）
    }
    position_score = position_map.get(position_tag, 9)

    # 5. 形成深度（0~20）—— 关键新增
    formation_score = _formation_depth_score(
        test_count, duration_days, amplitude_convergence, time_since_last_test
    )

    total = activity_score + quality_score + phase_score + position_score + formation_score
    breakdown = (
        f"离稳态{activity_score} + 质量{quality_score} + 阶段{phase_score} + "
        f"位置{position_score} + 深度{formation_score}"
    )
    return PriorityScore(
        total=total,
        activity=activity_score,
        quality=quality_score,
        phase=phase_score,
        position=position_score,
        formation_depth=formation_score,
        breakdown=breakdown,
    )


def compute_amplitude_convergence(test_amplitudes: List[float]) -> float:
    """
    对最近几次试探的振幅做线性回归，斜率 < 0 表示收敛
    """
    if len(test_amplitudes) < 3:
        return 0.0
    x = np.arange(len(test_amplitudes), dtype=float)
    y = np.asarray(test_amplitudes, dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    # 归一化到均值
    mean_amp = y.mean() if y.mean() > 1e-9 else 1.0
    return slope / mean_amp
