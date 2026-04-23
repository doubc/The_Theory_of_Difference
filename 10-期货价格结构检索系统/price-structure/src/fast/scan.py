"""
全市场扫描 C 加速模块 — 批量编译 + 批量相似度

将全市场的编译和相似度计算向量化，减少 Python 循环开销。
核心思想：把所有品种的数据拼接成大数组，一次 C 调用处理。

用法：
    from src.fast.scan import batch_compile_fast, batch_similarity_fast
"""

from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data.loader import Bar


def prepare_batch_arrays(all_bars: dict[str, list["Bar"]]) -> tuple:
    """
    将多个品种的 Bar 数据准备为批量编译所需的扁平数组

    Args:
        all_bars: {symbol: [Bar, ...]}

    Returns:
        (all_prices, all_returns, offsets, symbols)
        - all_prices: 扁平价格数组 [total_bars]
        - all_returns: 扁平收益率数组 [total_bars]
        - offsets: 每个品种的起始偏移 [n_symbols+1]
        - symbols: 品种列表
    """
    symbols = list(all_bars.keys())
    total_bars = sum(len(bars) for bars in all_bars.values())

    all_prices = np.zeros(total_bars, dtype=np.float64)
    all_returns = np.zeros(total_bars, dtype=np.float64)
    offsets = np.zeros(len(symbols) + 1, dtype=np.int32)

    pos = 0
    for i, sym in enumerate(symbols):
        bars = all_bars[sym]
        offsets[i] = pos

        for j, b in enumerate(bars):
            all_prices[pos] = b.close
            if j > 0 and bars[j-1].close > 0:
                all_returns[pos] = (b.close - bars[j-1].close) / bars[j-1].close
            pos += 1

    offsets[len(symbols)] = pos
    return all_prices, all_returns, offsets, symbols


def batch_compile_fast(
    all_bars: dict[str, list["Bar"]],
    min_amplitude: float = 0.02,
    base_window: int = 3,
    noise_filter: float = 0.005,
    adaptive: bool = True,
    fractal_threshold: float = 0.34,
) -> dict[str, list[dict]]:
    """
    批量极值提取（C 加速）

    Args:
        all_bars: {symbol: [Bar, ...]}
        其他参数同 extract_pivots_fast

    Returns:
        {symbol: [{"idx": int, "price": float, "direction": int, "fractal": float}, ...]}
    """
    from src.fast import extract_pivots_fast

    results = {}
    for sym, bars in all_bars.items():
        prices = [b.close for b in bars]
        pivots = extract_pivots_fast(
            prices,
            min_amplitude=min_amplitude,
            base_window=base_window,
            noise_filter=noise_filter,
            adaptive=adaptive,
            fractal_threshold=fractal_threshold,
        )
        results[sym] = pivots

    return results


def batch_similarity_fast(
    query_invariants: dict,
    candidate_invariants_list: list[dict],
    weights: tuple[float, ...] = (0.35, 0.35, 0.15, 0.15),
) -> list[float]:
    """
    批量相似度计算（向量化）

    给定一个查询结构的不变量，与所有候选结构计算相似度。

    Args:
        query_invariants: 查询结构的不变量 dict
        candidate_invariants_list: 候选结构的不变量 dict 列表
        weights: (几何, 关系, 运动, 族) 权重

    Returns:
        相似度列表 [0, 1]
    """
    from src.fast import dtw_similarity_fast

    # 几何相似度：向量化欧氏距离
    INVARIANT_KEYS = [
        "cycle_count", "avg_speed_ratio", "avg_log_speed_ratio",
        "avg_time_ratio", "high_dispersion", "low_dispersion",
        "high_trend", "low_trend", "zone_rel_bw", "zone_strength",
    ]
    INVARIANT_SCALES = {
        "cycle_count": 10.0, "avg_speed_ratio": 2.0,
        "avg_log_speed_ratio": 2.0, "avg_time_ratio": 2.0,
        "high_dispersion": 1.0, "low_dispersion": 1.0,
        "high_trend": 1.0, "low_trend": 1.0,
        "zone_rel_bw": 1.0, "zone_strength": 10.0,
    }

    def _vec(inv):
        return np.array([
            (inv.get(k, 0) or 0) / INVARIANT_SCALES[k]
            for k in INVARIANT_KEYS
        ], dtype=np.float64)

    q_vec = _vec(query_invariants)
    n = len(candidate_invariants_list)

    # 批量计算几何距离
    c_matrix = np.zeros((n, len(INVARIANT_KEYS)), dtype=np.float64)
    for i, inv in enumerate(candidate_invariants_list):
        c_matrix[i] = _vec(inv)

    # 欧氏距离（向量化）
    diff = c_matrix - q_vec
    distances = np.sqrt(np.sum(diff ** 2, axis=1))
    geo_scores = np.maximum(0, 1.0 - distances / np.sqrt(len(INVARIANT_KEYS)))

    # 综合评分（简化版，实际使用时可加入关系/运动/族维度）
    w_g, w_r, w_m, w_f = weights
    scores = w_g * geo_scores + w_r * 0.5 + w_m * 0.5 + w_f * 0.5

    return scores.tolist()


def find_top_similar(
    query_invariants: dict,
    candidate_invariants_list: list[dict],
    top_k: int = 10,
    weights: tuple[float, ...] = (0.35, 0.35, 0.15, 0.15),
) -> list[tuple[int, float]]:
    """
    快速 Top-K 相似度检索

    Args:
        query_invariants: 查询结构的不变量
        candidate_invariants_list: 候选结构的不变量列表
        top_k: 返回前 K 个
        weights: 权重

    Returns:
        [(index, score), ...] 按 score 降序
    """
    scores = batch_similarity_fast(query_invariants, candidate_invariants_list, weights)

    # 用 numpy argpartition 找 top-k（O(n) 而不是 O(n log n)）
    arr = np.array(scores)
    if len(arr) <= top_k:
        indices = np.argsort(arr)[::-1]
    else:
        indices = np.argpartition(arr, -top_k)[-top_k:]
        indices = indices[np.argsort(arr[indices])[::-1]]

    return [(int(i), float(arr[i])) for i in indices]
