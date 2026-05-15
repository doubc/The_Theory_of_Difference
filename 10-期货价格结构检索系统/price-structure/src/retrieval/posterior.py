"""
后验统计模块 — 从 engine.py 提取

P1 整改：将 engine.py 中的 _aggregate_posterior 私有函数提取为公开接口。
独立模块便于：
1. 回测框架调用
2. 多窗口后验统计扩展
3. 与 engine.py 解耦

原始逻辑完全保留，只是从私有变公开。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PosteriorStats:
    """后验统计 — 近邻样本的前向演化聚合"""
    sample_size: int
    mean_ret_5d: float
    mean_ret_10d: float
    mean_ret_20d: float
    median_ret_20d: float
    prob_positive_10d: float
    mean_max_dd_20d: float
    mean_max_rise_20d: float


def aggregate_posterior(samples: list) -> PosteriorStats:
    """
    聚合前向演化结果为后验统计

    Args:
        samples: Sample 对象列表，每个 Sample 有 forward_outcome dict

    Returns:
        PosteriorStats

    注意：空列表返回全零统计（sample_size=0）
    """
    n = len(samples)
    if n == 0:
        return PosteriorStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def field_vals(name: str) -> list[float]:
        vals = []
        for s in samples:
            if s.forward_outcome and s.forward_outcome.get(name) is not None:
                vals.append(s.forward_outcome[name])
        return vals

    def mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    def median(xs: list[float]) -> float:
        if not xs:
            return 0.0
        xs = sorted(xs)
        m = len(xs) // 2
        return xs[m] if len(xs) % 2 == 1 else (xs[m - 1] + xs[m]) / 2

    r5 = field_vals("ret_5d")
    r10 = field_vals("ret_10d")
    r20 = field_vals("ret_20d")
    dd = field_vals("max_dd_20d")
    rise = field_vals("max_rise_20d")
    prob_pos = sum(1 for x in r10 if x > 0) / len(r10) if r10 else 0.0

    return PosteriorStats(
        sample_size=n,
        mean_ret_5d=mean(r5),
        mean_ret_10d=mean(r10),
        mean_ret_20d=mean(r20),
        median_ret_20d=median(r20),
        prob_positive_10d=prob_pos,
        mean_max_dd_20d=mean(dd),
        mean_max_rise_20d=mean(rise),
    )


def aggregate_posterior_by_window(
    samples: list,
    query_t_end=None,
    windows: list[int] | None = None,
) -> dict[str, PosteriorStats]:
    """
    分窗口后验统计 — 近期/中期/远期分开计算

    V1.6 P2 升级：后验统计分窗口，避免远近样本混合。

    Args:
        samples: Sample 对象列表
        query_t_end: 查询结构的结束时间（datetime）
        windows: 窗口定义（天数），默认 [30, 90, 365]

    Returns:
        {"recent": PosteriorStats, "mid": PosteriorStats, "far": PosteriorStats}
    """
    if windows is None:
        windows = [30, 90, 365]

    if query_t_end is None or not samples:
        return {
            "recent": aggregate_posterior(samples),
            "mid": PosteriorStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            "far": PosteriorStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        }

    from datetime import timedelta

    recent = []
    mid = []
    far = []

    for sp in samples:
        sp_end = sp.t_end
        if sp_end is None:
            far.append(sp)
            continue

        try:
            delta = (query_t_end - sp_end).days
        except (TypeError, AttributeError):
            far.append(sp)
            continue

        if delta <= windows[0]:
            recent.append(sp)
        elif delta <= windows[1]:
            mid.append(sp)
        else:
            far.append(sp)

    return {
        "recent": aggregate_posterior(recent),
        "mid": aggregate_posterior(mid),
        "far": aggregate_posterior(far),
    }
