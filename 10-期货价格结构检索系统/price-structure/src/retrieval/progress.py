"""
结构进度检索 — DTW 滑动形状匹配

核心思路：
  拿当前结构的价格曲线形状，在历史曲线上滑动比对，
  找到前面重合的位置，看后面走出了什么。

流程：
  1. 取当前结构对应的最近 N 天收盘价序列 → 归一化 → query shape
  2. 在历史 bars 上用固定窗口滑动，每个位置取 N 天 → 归一化 → candidate
  3. DTW(query, candidate) → 距离
  4. 取距离最小的 top_k 个位置
  5. 看这些位置后面 M 天的走势 → 聚合出方向/收益/天数
  6. 最多的走势类型 = 候选剧本

顺时序：
  - query 是当前的形状（近期）
  - 匹配发生在历史更早的时间段（query 的时间 > candidate 的时间）
  - 后半程是 candidate 之后已发生的真实走势
  - 不看未来数据
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Sequence

from src.data.loader import Bar


# ─── 数据结构 ──────────────────────────────────────────────

@dataclass
class ShapeMatch:
    """
    一个历史形状匹配结果

    match_start: 匹配段起始日期
    match_end: 匹配段结束日期
    dtw_distance: DTW 距离（越小越相似）
    similarity: 相似度 [0, 1]（由距离转换）
    after_direction: 匹配段之后的走势方向
    after_move: 匹配段之后的价格变化比例
    after_days: 匹配段之后走势兑现的天数
    after_bars: 匹配段之后的价格序列（用于可视化）
    """
    match_start: datetime
    match_end: datetime
    dtw_distance: float
    similarity: float
    after_direction: str  # "up" / "down" / "range"
    after_move: float
    after_days: int
    after_bars: list[float] = field(default_factory=list)


@dataclass
class Playbook:
    """
    候选剧本 — 从多个历史匹配中聚合

    n_matches: 匹配数量
    prob_up: 后续上涨的概率
    prob_down: 后续下跌的概率
    prob_range: 后续横盘的概率
    median_move: 后续中位收益
    q25_move: 后续 25 分位收益
    q75_move: 后续 75 分位收益
    median_days: 后续中位兑现天数
    direction: 主方向
    confidence: 置信度
    win_rate: 胜率
    summary: 人可读摘要
    matches: 匹配列表
    """
    n_matches: int
    prob_up: float
    prob_down: float
    prob_range: float
    median_move: float
    q25_move: float
    q75_move: float
    median_days: int
    direction: str
    confidence: str
    win_rate: float
    summary: str
    matches: list[ShapeMatch] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "n_matches": self.n_matches,
            "prob_up": round(self.prob_up, 3),
            "prob_down": round(self.prob_down, 3),
            "prob_range": round(self.prob_range, 3),
            "median_move": round(self.median_move, 4),
            "q25_move": round(self.q25_move, 4),
            "q75_move": round(self.q75_move, 4),
            "median_days": self.median_days,
            "direction": self.direction,
            "confidence": self.confidence,
            "win_rate": round(self.win_rate, 3),
            "summary": self.summary,
        }


# ─── DTW 核心 ─────────────────────────────────────────────

def _dtw_distance(seq1: list[float], seq2: list[float], window: int | None = None) -> float:
    """
    DTW 距离，带 Sakoe-Chiba 带宽约束。
    空间优化：只保留两行，O(m) 空间。
    """
    n, m = len(seq1), len(seq2)
    if n == 0 or m == 0:
        return float("inf")

    if window is None:
        window = max(n, m)
    window = max(window, abs(n - m))

    INF = float("inf")
    prev = [INF] * (m + 1)
    prev[0] = 0.0

    for i in range(1, n + 1):
        curr = [INF] * (m + 1)
        j_lo = max(1, i - window)
        j_hi = min(m, i + window)
        for j in range(j_lo, j_hi + 1):
            cost = (seq1[i - 1] - seq2[j - 1]) ** 2
            curr[j] = cost + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr

    return math.sqrt(prev[m])


def _normalize(values: list[float]) -> list[float]:
    """Min-max 归一化到 [0, 1]"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


# ─── 滑动匹配 ─────────────────────────────────────────────

def slide_match(
    query_bars: list[Bar],
    history_bars: list[Bar],
    after_window: int = 20,
    top_k: int = 20,
    step: int = 1,
    min_gap_days: int = 30,
) -> list[ShapeMatch]:
    """
    在历史曲线上滑动匹配 query 的形状。

    Args:
        query_bars: 当前结构对应的 bars（最近 N 天），用于提取形状
        history_bars: 历史全量 bars（按时间排序）
        after_window: 匹配后观察的天数（默认 20 天）
        top_k: 返回前 K 个最相似的匹配
        step: 滑动步长（默认每天滑 1 根 bar）
        min_gap_days: query 与匹配段之间的最小间隔天数（避免重叠）

    Returns:
        ShapeMatch 列表，按相似度降序
    """
    if len(query_bars) < 10 or len(history_bars) < 10:
        return []

    # 提取 query 的收盘价序列并归一化
    query_closes = [b.close for b in query_bars]
    query_norm = _normalize(query_closes)
    query_len = len(query_norm)

    if query_len < 5:
        return []

    # query 的时间范围
    query_start = query_bars[0].timestamp
    query_end = query_bars[-1].timestamp

    # 滑动窗口
    window = query_len // 2  # DTW 带宽约束
    results = []

    for i in range(0, len(history_bars) - query_len - after_window, step):
        candidate_bars = history_bars[i:i + query_len]
        candidate_start = candidate_bars[0].timestamp
        candidate_end = candidate_bars[-1].timestamp

        # 顺时序：匹配段必须在 query 之前
        if candidate_end >= query_start - timedelta(days=min_gap_days):
            continue

        # 提取 candidate 的收盘价序列并归一化
        candidate_closes = [b.close for b in candidate_bars]
        candidate_norm = _normalize(candidate_closes)

        # DTW 距离
        dist = _dtw_distance(query_norm, candidate_norm, window=window)

        # 转换为相似度
        normalized_dist = dist / math.sqrt(query_len)
        sim = 1.0 / (1.0 + normalized_dist)

        # 后半程：匹配段之后 after_window 天的走势
        after_start = i + query_len
        after_end = min(after_start + after_window, len(history_bars))
        after_bars_data = history_bars[after_start:after_end]

        if not after_bars_data:
            continue

        start_price = candidate_closes[-1]  # 匹配段最后一根 bar 的收盘价
        if start_price <= 0:
            continue

        # 后半程走势
        after_closes = [b.close for b in after_bars_data]
        peak = max(after_closes)
        trough = min(after_closes)
        end_price = after_closes[-1]

        up = (peak - start_price) / start_price
        down = (start_price - trough) / start_price
        final = (end_price - start_price) / start_price

        if up > down * 1.5 and final > 0.005:
            direction = "up"
            move = up
        elif down > up * 1.5 and final < -0.005:
            direction = "down"
            move = -down
        else:
            direction = "range"
            move = final

        # 兑现天数
        if direction == "up":
            days = next((j for j, c in enumerate(after_closes) if c >= peak), after_window)
        elif direction == "down":
            days = next((j for j, c in enumerate(after_closes) if c <= trough), after_window)
        else:
            days = after_window

        results.append(ShapeMatch(
            match_start=candidate_start,
            match_end=candidate_end,
            dtw_distance=round(dist, 4),
            similarity=round(sim, 4),
            after_direction=direction,
            after_move=round(move, 4),
            after_days=days,
            after_bars=after_closes,
        ))

    # 按相似度排序
    results.sort(key=lambda m: m.similarity, reverse=True)
    return results[:top_k]


def aggregate_playbook(matches: list[ShapeMatch]) -> Playbook:
    """
    从多个历史匹配中聚合出候选剧本。
    """
    n = len(matches)
    if n == 0:
        return Playbook(
            n_matches=0, prob_up=0, prob_down=0, prob_range=1.0,
            median_move=0, q25_move=0, q75_move=0, median_days=0,
            direction="unclear", confidence="low", win_rate=0,
            summary="无足够相似的历史形状匹配",
        )

    # 方向统计
    ups = sum(1 for m in matches if m.after_direction == "up")
    downs = sum(1 for m in matches if m.after_direction == "down")
    ranges = n - ups - downs

    prob_up = ups / n
    prob_down = downs / n
    prob_range = ranges / n

    # 收益统计
    moves = [m.after_move for m in matches]
    days = [m.after_days for m in matches if m.after_days > 0]

    def _median(xs):
        if not xs:
            return 0.0
        xs = sorted(xs)
        m = len(xs) // 2
        return xs[m] if len(xs) % 2 == 1 else (xs[m - 1] + xs[m]) / 2

    def _percentile(xs, p):
        if not xs:
            return 0.0
        xs = sorted(xs)
        idx = int(len(xs) * p)
        return xs[min(idx, len(xs) - 1)]

    median_move = _median(moves)
    q25_move = _percentile(moves, 0.25)
    q75_move = _percentile(moves, 0.75)
    median_days = int(_median(days))

    # 胜率：方向明确且收益 > 0
    win_count = sum(1 for m in matches
                    if (m.after_direction == "up" and m.after_move > 0)
                    or (m.after_direction == "down" and m.after_move < 0))
    win_rate = win_count / n

    # 主方向
    if prob_up > prob_down * 1.3:
        direction = "bullish"
    elif prob_down > prob_up * 1.3:
        direction = "bearish"
    else:
        direction = "unclear"

    # 置信度
    max_prob = max(prob_up, prob_down)
    if n >= 10 and max_prob >= 0.65:
        confidence = "high"
    elif n >= 5 and max_prob >= 0.50:
        confidence = "medium"
    else:
        confidence = "low"

    # 摘要
    dir_label = {"bullish": "看涨", "bearish": "看跌", "unclear": "方向不明"}
    conf_label = {"high": "高置信", "medium": "中置信", "low": "低置信"}

    parts = [f"基于 {n} 个历史形状匹配"]
    parts.append(f"方向：{dir_label.get(direction, '?')}（{conf_label.get(confidence, '?')}）")
    parts.append(f"上涨 {prob_up:.0%}，下跌 {prob_down:.0%}，横盘 {prob_range:.0%}")
    parts.append(f"后半程中位收益 {median_move:+.1%}")
    if median_days > 0:
        parts.append(f"典型兑现 {median_days} 天")
    if confidence == "high" and max_prob >= 0.65:
        parts.append(f"胜率 {max_prob:.0%} 超过 65%，参考价值较高")

    return Playbook(
        n_matches=n,
        prob_up=prob_up,
        prob_down=prob_down,
        prob_range=prob_range,
        median_move=median_move,
        q25_move=q25_move,
        q75_move=q75_move,
        median_days=median_days,
        direction=direction,
        confidence=confidence,
        win_rate=win_rate,
        summary="，".join(parts),
        matches=matches,
    )


# ─── 顶层入口 ──────────────────────────────────────────────

def progress_retrieve(
    current_bars: list[Bar],
    history_bars: list[Bar],
    after_window: int = 20,
    top_k: int = 20,
    step: int = 1,
) -> tuple[Playbook, list[ShapeMatch]]:
    """
    结构进度检索。

    Args:
        current_bars: 当前结构对应的 bars（最近 N 天的收盘价）
        history_bars: 历史全量 bars
        after_window: 匹配后观察天数
        top_k: 返回前 K 个匹配
        step: 滑动步长

    Returns:
        (Playbook, list[ShapeMatch])
    """
    matches = slide_match(current_bars, history_bars, after_window, top_k, step)
    playbook = aggregate_playbook(matches)
    return playbook, matches
