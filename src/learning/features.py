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
    """批量提取特征（v3.1: 尝试 C 加速，fallback 到逐个调用）"""
    try:
        from src.fast import batch_extract_features_fast
        import numpy as np

        # 准备扁平化数据
        all_sr, all_tr, all_lsr, all_ar = [], [], [], []
        all_ade, all_adx, all_due, all_dux, all_dir = [], [], [], [], []
        offsets = [0]
        bw_rel, strength, cv = [], [], []

        for s in structures:
            cycles = s.cycles
            for c in cycles:
                all_sr.append(c.speed_ratio)
                all_tr.append(c.time_ratio)
                lsr = c.log_speed_ratio
                all_lsr.append(lsr if lsr > 0 and lsr != float('inf') else 0.0)
                all_ar.append(c.amplitude_ratio)
                all_ade.append(c.entry.abs_delta)
                all_adx.append(c.exit.abs_delta)
                all_due.append(c.entry.duration)
                all_dux.append(c.exit.duration)
                all_dir.append(1 if c.entry.direction.value > 0 else -1)
            offsets.append(len(all_sr))
            bw_rel.append(s.zone.relative_bandwidth)
            strength.append(s.zone.strength)
            cv.append(s.high_cluster_cv)

        data = {
            'speed_ratios': np.array(all_sr, dtype=np.float64),
            'time_ratios': np.array(all_tr, dtype=np.float64),
            'log_speed_ratios': np.array(all_lsr, dtype=np.float64),
            'amplitude_ratios': np.array(all_ar, dtype=np.float64),
            'abs_deltas_entry': np.array(all_ade, dtype=np.float64),
            'abs_deltas_exit': np.array(all_adx, dtype=np.float64),
            'durations_entry': np.array(all_due, dtype=np.float64),
            'durations_exit': np.array(all_dux, dtype=np.float64),
            'directions_entry': np.array(all_dir, dtype=np.int32),
            'cycle_offsets': np.array(offsets, dtype=np.int32),
            'zone_bw_rel': np.array(bw_rel, dtype=np.float64),
            'zone_strength': np.array(strength, dtype=np.float64),
            'high_cluster_cv': np.array(cv, dtype=np.float64),
        }
        features = batch_extract_features_fast(data)
        return features.tolist()
    except (ImportError, Exception):
        return [extract_features(s) for s in structures]
