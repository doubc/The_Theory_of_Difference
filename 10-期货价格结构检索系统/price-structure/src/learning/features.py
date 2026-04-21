"""
结构特征工程 — 把 Structure 对象转为数值特征向量

用于分类、embedding、条件分布建模。
所有特征无量纲或归一化，跨品种可比。
"""

from __future__ import annotations

import math
from typing import Sequence

from src.models import Structure, Segment, Cycle


# ─── 特征名 ────────────────────────────────────────────────

FEATURE_NAMES = [
    # 结构规模
    "cycle_count",
    "total_duration_days",

    # 速度/时间比
    "avg_speed_ratio",
    "avg_time_ratio",
    "std_speed_ratio",
    "std_time_ratio",

    # 对数度量（品种无关）
    "avg_log_speed_ratio",

    # 聚集度
    "high_cluster_cv",
    "zone_relative_bandwidth",
    "zone_strength",

    # 幅度特征
    "avg_amplitude_ratio",
    "total_abs_delta",

    # 方向特征
    "up_segment_ratio",
]


def extract_features(s: Structure) -> list[float]:
    """从 Structure 提取特征向量"""
    cycles = s.cycles
    n = len(cycles) if cycles else 1

    # 速度比
    speed_ratios = [c.speed_ratio for c in cycles] if cycles else [0]
    avg_sr = sum(speed_ratios) / n
    std_sr = math.sqrt(sum((x - avg_sr) ** 2 for x in speed_ratios) / n) if n > 1 else 0

    # 时间比
    time_ratios = [c.time_ratio for c in cycles] if cycles else [0]
    avg_tr = sum(time_ratios) / n
    std_tr = math.sqrt(sum((x - avg_tr) ** 2 for x in time_ratios) / n) if n > 1 else 0

    # 幅度比
    amp_ratios = [c.amplitude_ratio for c in cycles] if cycles else [0]
    avg_ar = sum(amp_ratios) / n

    # 总持续时间
    total_dur = sum(c.entry.duration + c.exit.duration for c in cycles) if cycles else 0

    # 总绝对变化量
    total_abs = sum(c.entry.abs_delta + c.exit.abs_delta for c in cycles) if cycles else 0

    # 上涨段比例
    all_segs = []
    for c in cycles:
        all_segs.extend([c.entry, c.exit])
    up_ratio = sum(1 for seg in all_segs if seg.delta > 0) / len(all_segs) if all_segs else 0.5

    # 对数速度比
    log_srs = [c.log_speed_ratio for c in cycles] if cycles else [0]
    avg_log_sr = sum(log_srs) / n

    return [
        float(len(cycles)),
        total_dur,
        avg_sr,
        avg_tr,
        std_sr,
        std_tr,
        avg_log_sr,
        s.high_cluster_cv,
        s.zone.relative_bandwidth,
        s.zone.strength,
        avg_ar,
        total_abs,
        up_ratio,
    ]


def extract_features_batch(structures: Sequence[Structure]) -> list[list[float]]:
    """批量提取特征"""
    return [extract_features(s) for s in structures]
