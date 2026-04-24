"""
结构进度检索 — 用历史完整结构的前半程来对照和预测当前结构

核心问题：
  当前结构可能只是某个大结构的 1/3 或 1/2。
  历史上那些走到同样进度的前半程，后来都走成了什么样？

实现思路（价格进度法）：
  1. 历史全量数据编译出完整结构（比如 360 天的大结构）
  2. 对每个完整结构，记录其价格范围（最低到最高）
  3. 当前价格在历史结构的价格范围中走到哪了 = 价格进度
     - 价格进度 0.33 = 当前价位处于历史结构价格范围的 1/3 处
     - 价格进度 0.50 = 当前价位处于历史结构价格范围的 1/2 处
  4. 找历史上价格进度相似的前半程
  5. 看那些前半程后来走成了什么样

顺时序约束：
  - 当前结构必须是近期形成的
  - 历史结构的"后半程"是已发生的真实走势
  - 不看未来数据

返回：
  候选剧本列表（历史后续走势），含胜率、中位收益、兑现天数
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Sequence

from src.data.loader import Bar
from src.retrieval.similarity import similarity, SimilarityScore
from src.models import Structure


# ─── 数据结构 ──────────────────────────────────────────────

@dataclass
class HistoricalFullStructure:
    """
    一个历史完整结构的价格范围和走势信息

    用于进度检索：记录这个结构从开始到结束的完整价格旅程，
    以便判断当前价格在这个旅程中处于什么位置。
    """
    structure: Structure          # 编译出的结构对象
    symbol: str
    price_low: float              # 结构期间最低价
    price_high: float             # 结构期间最高价
    price_range: float            # 价格范围（high - low）
    t_start: datetime
    t_end: datetime
    duration_days: int
    direction: str                # 整体方向 "up" / "down" / "range"
    final_move: float             # 从起始到结束的价格变化比例

    def price_progress(self, current_price: float) -> float:
        """
        计算当前价格在该结构价格范围中的进度。

        返回 [0, 1]：
          0.0 = 当前价 = 结构最低价（刚开始）
          0.5 = 当前价 = 结构中间价（走到一半）
          1.0 = 当前价 = 结构最高价（走完了）

        如果当前价超出范围，返回 <0 或 >1。
        """
        if self.price_range <= 0:
            return 0.5
        return (current_price - self.price_low) / self.price_range

    def time_progress(self, current_date: datetime) -> float:
        """
        计算当前时间在该结构时间跨度中的进度。

        返回 [0, 1]。
        """
        if self.duration_days <= 0:
            return 0.5
        elapsed = (current_date - self.t_start).days
        return elapsed / self.duration_days


@dataclass
class ProgressMatch:
    """
    当前结构与某个历史前半程的匹配结果

    historical: 匹配到的历史完整结构
    price_progress_at_match: 匹配时的价格进度（当前价在历史结构中的位置）
    time_progress_at_match: 匹配时的时间进度
    similarity_score: 结构相似度
    match_reason: 匹配原因
    outcome: 该历史结构的后半程走势
    """
    historical: HistoricalFullStructure
    price_progress_at_match: float
    time_progress_at_match: float
    similarity_score: float
    match_reason: str
    outcome: dict  # {"direction": "up"/"down", "remaining_move": float, "remaining_days": int}


@dataclass
class Playbook:
    """
    候选剧本 — 从历史匹配中聚合出的预测

    基于多个历史前半程的后验表现，给出：
    - 方向概率（上涨/下跌的比例）
    - 中位收益和分位数
    - 典型兑现天数
    - 胜率
    """
    n_matches: int
    prob_up: float
    prob_down: float
    median_remaining_move: float
    q25_remaining_move: float
    q75_remaining_move: float
    median_remaining_days: int
    win_rate: float  # 同向且收益 > 0 的比例
    direction: str  # "bullish" / "bearish" / "unclear"
    confidence: str  # "high" (>=65%) / "medium" (50-65%) / "low" (<50%)
    matches: list[ProgressMatch] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "n_matches": self.n_matches,
            "prob_up": round(self.prob_up, 3),
            "prob_down": round(self.prob_down, 3),
            "median_remaining_move": round(self.median_remaining_move, 4),
            "q25_remaining_move": round(self.q25_remaining_move, 4),
            "q75_remaining_move": round(self.q75_remaining_move, 4),
            "median_remaining_days": self.median_remaining_days,
            "win_rate": round(self.win_rate, 3),
            "direction": self.direction,
            "confidence": self.confidence,
            "summary": self.summary,
        }


# ─── 核心逻辑 ──────────────────────────────────────────────

PROGRESS_LEVELS = [0.25, 0.33, 0.50, 0.67, 0.75]


def build_historical_full_structures(
    bars: list[Bar],
    compiled_structures: list[Structure],
    symbol: str,
    min_duration_days: int = 60,
) -> list[HistoricalFullStructure]:
    """
    从编译出的结构中构建历史完整结构列表。

    对每个结构，用其时间范围内的 bars 计算价格范围和方向。

    Args:
        bars: 该品种的全量历史 bars（按时间排序）
        compiled_structures: 编译出的结构列表
        symbol: 品种代码
        min_duration_days: 最小持续天数（太短的结构不做进度分析）

    Returns:
        HistoricalFullStructure 列表
    """
    result = []

    for s in compiled_structures:
        if not s.t_start or not s.t_end:
            continue
        days = (s.t_end - s.t_start).days
        if days < min_duration_days:
            continue
        if s.cycle_count < 3:
            continue

        # 取结构时间范围内的 bars
        struct_bars = [b for b in bars if s.t_start <= b.timestamp <= s.t_end]
        if not struct_bars:
            continue

        price_low = min(b.low for b in struct_bars)
        price_high = max(b.high for b in struct_bars)
        price_range = price_high - price_low

        # 整体方向
        start_price = struct_bars[0].close
        end_price = struct_bars[-1].close
        if start_price > 0:
            final_move = (end_price - start_price) / start_price
        else:
            final_move = 0.0

        if final_move > 0.03:
            direction = "up"
        elif final_move < -0.03:
            direction = "down"
        else:
            direction = "range"

        fid = f"{symbol}_{int(s.zone.price_center)}_{s.t_start.strftime('%Y%m%d')}"
        result.append(HistoricalFullStructure(
            structure=s,
            symbol=symbol,
            price_low=price_low,
            price_high=price_high,
            price_range=price_range,
            t_start=s.t_start,
            t_end=s.t_end,
            duration_days=days,
            direction=direction,
            final_move=final_move,
        ))

    return result


def match_by_price_progress(
    current_price: float,
    current_structure: Structure,
    current_date: datetime,
    historical: list[HistoricalFullStructure],
    progress_tolerance: float = 0.15,
    min_structure_similarity: float = 0.2,
    top_k: int = 15,
) -> list[ProgressMatch]:
    """
    用价格进度匹配历史前半程。

    核心逻辑：
      当前价格在历史结构的价格范围中处于什么位置？
      找到价格进度相似的历史结构，看它们的后半程。

    例如：
      历史结构 A：价格从 5000 涨到 10000（范围 5000）
      当前价格 7500 → 价格进度 = (7500-5000)/5000 = 0.50（走到一半）
      找到这个历史结构，看它从 7500 涨到 10000 的后半程

    顺时序：
      历史结构的后半程是已发生的真实走势，不做权重调整。

    Args:
        current_price: 当前价格（如今天收盘价）
        current_structure: 当前编译出的结构
        current_date: 当前日期
        historical: 历史完整结构列表
        progress_tolerance: 价格进度匹配容差（默认 ±15%）
        min_structure_similarity: 结构相似度最低阈值
        top_k: 返回前 K 个

    Returns:
        ProgressMatch 列表，按结构相似度降序
    """
    matches = []

    for h in historical:
        # 计算当前价格在该历史结构中的价格进度
        pprog = h.price_progress(current_price)

        # 只看"走到一半以内"的（后半程才有参考价值）
        # 且价格进度必须在 [0.1, 0.9] 范围内（太靠近两端没意义）
        if pprog < 0.10 or pprog > 0.90:
            continue

        # 价格进度必须在容差范围内
        # 匹配 1/4、1/3、1/2、2/3、3/4 这几个关键进度
        matched_level = None
        for level in PROGRESS_LEVELS:
            if abs(pprog - level) <= progress_tolerance:
                matched_level = level
                break
        if matched_level is None:
            continue

        # 计算时间进度
        tprog = h.time_progress(current_date)

        # 结构相似度（当前结构与历史结构的 Zone 相似度）
        sim = _compute_structure_similarity(current_structure, h.structure)
        if sim < min_structure_similarity:
            continue

        # 后半程表现
        outcome = _compute_remaining_outcome(h, current_price, current_date)

        # 匹配原因
        reason = _generate_match_reason(h, pprog, tprog, sim)

        matches.append(ProgressMatch(
            historical=h,
            price_progress_at_match=round(pprog, 3),
            time_progress_at_match=round(tprog, 3),
            similarity_score=round(sim, 4),
            match_reason=reason,
            outcome=outcome,
        ))

    # 按结构相似度排序
    matches.sort(key=lambda m: m.similarity_score, reverse=True)
    return matches[:top_k]


def _compute_structure_similarity(s1: Structure, s2: Structure) -> float:
    """
    计算两个结构的综合相似度。

    简化版：用 Zone 中心距离 + 速度比距离 + 时间比距离。
    """
    # Zone 中心距离
    z1 = s1.zone.price_center
    z2 = s2.zone.price_center
    max_z = max(z1, z2, 1.0)
    zone_dist = abs(z1 - z2) / max_z

    # 速度比距离
    sr1 = s1.avg_speed_ratio
    sr2 = s2.avg_speed_ratio
    sr_dist = abs(sr1 - sr2) / max(sr1, sr2, 0.01)

    # 时间比距离
    tr1 = s1.avg_time_ratio
    tr2 = s2.avg_time_ratio
    tr_dist = abs(tr1 - tr2) / max(tr1, tr2, 0.01)

    # 综合距离 → 相似度
    dist = (zone_dist + sr_dist + tr_dist) / 3.0
    return max(0.0, 1.0 - dist)


def _compute_remaining_outcome(
    h: HistoricalFullStructure,
    current_price: float,
    current_date: datetime,
) -> dict:
    """
    计算历史结构从当前进度到结束的后半程表现。

    后半程 = 从当前价格/时间到结构结束的价格变化和天数。
    """
    end_price = h.structure.cycles[-1].exit.end.x if h.structure.cycles else h.price_high

    if current_price > 0:
        remaining_move = (end_price - current_price) / current_price
    else:
        remaining_move = 0.0

    remaining_days = (h.t_end - current_date).days

    if remaining_move > 0.01:
        direction = "up"
    elif remaining_move < -0.01:
        direction = "down"
    else:
        direction = "range"

    return {
        "direction": direction,
        "remaining_move": round(remaining_move, 4),
        "remaining_days": max(remaining_days, 0),
        "end_price": round(end_price, 2),
        "final_move": round(h.final_move, 4),
    }


def _generate_match_reason(
    h: HistoricalFullStructure,
    pprog: float,
    tprog: float,
    sim: float,
) -> str:
    """生成匹配原因"""
    parts = []

    pct = int(pprog * 100)
    parts.append(f"价格进度 {pct}%（历史价格范围的 {pct}% 处）")

    if sim > 0.7:
        parts.append("结构高度相似")
    elif sim > 0.5:
        parts.append("结构大致相似")

    parts.append(f"历史整体方向: {h.direction}({h.final_move:+.1%})")
    parts.append(f"历史跨度 {h.duration_days} 天")

    return "，".join(parts)


def aggregate_playbook(matches: list[ProgressMatch]) -> Playbook:
    """
    从多个历史匹配中聚合出候选剧本。

    统计：
    - 方向概率（上涨/下跌的比例）
    - 后半程中位收益和分位数
    - 典型兑现天数
    - 胜率
    """
    n = len(matches)
    if n == 0:
        return Playbook(
            n_matches=0, prob_up=0, prob_down=0,
            median_remaining_move=0, q25_remaining_move=0, q75_remaining_move=0,
            median_remaining_days=0, win_rate=0,
            direction="unclear", confidence="low",
            summary="无足够相似的历史前半程案例",
        )

    # 方向统计
    directions = [m.outcome.get("direction", "range") for m in matches]
    up = sum(1 for d in directions if d == "up")
    down = sum(1 for d in directions if d == "down")

    prob_up = up / n
    prob_down = down / n

    # 后半程收益
    moves = [m.outcome.get("remaining_move", 0) for m in matches]
    days = [m.outcome.get("remaining_days", 0) for m in matches if m.outcome.get("remaining_days", 0) > 0]

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

    # 胜率：同向且后半程收益方向与历史整体方向一致
    win_count = 0
    for m in matches:
        h_dir = m.historical.direction
        r_move = m.outcome.get("remaining_move", 0)
        if (h_dir == "up" and r_move > 0) or (h_dir == "down" and r_move < 0):
            win_count += 1
    win_rate = win_count / n

    # 主方向
    if prob_up > prob_down * 1.3:
        direction = "bullish"
    elif prob_down > prob_up * 1.3:
        direction = "bearish"
    else:
        direction = "unclear"

    # 置信度
    if n >= 5 and max(prob_up, prob_down) >= 0.65:
        confidence = "high"
    elif n >= 3 and max(prob_up, prob_down) >= 0.50:
        confidence = "medium"
    else:
        confidence = "low"

    summary = _generate_playbook_summary(
        n, prob_up, prob_down, median_move, median_days, direction, confidence
    )

    return Playbook(
        n_matches=n,
        prob_up=prob_up,
        prob_down=prob_down,
        median_remaining_move=median_move,
        q25_remaining_move=q25_move,
        q75_remaining_move=q75_move,
        median_remaining_days=median_days,
        win_rate=win_rate,
        direction=direction,
        confidence=confidence,
        matches=matches,
        summary=summary,
    )


def _generate_playbook_summary(
    n: int,
    prob_up: float,
    prob_down: float,
    median_move: float,
    median_days: int,
    direction: str,
    confidence: str,
) -> str:
    """生成候选剧本的人可读摘要"""
    parts = []

    dir_label = {"bullish": "看涨", "bearish": "看跌", "unclear": "方向不明"}
    conf_label = {"high": "高置信", "medium": "中置信", "low": "低置信"}

    parts.append(f"基于 {n} 个历史前半程案例")
    parts.append(f"方向：{dir_label.get(direction, '?')}（{conf_label.get(confidence, '?')}）")
    parts.append(f"上涨概率 {prob_up:.0%}，下跌概率 {prob_down:.0%}")
    parts.append(f"后半程中位收益 {median_move:+.1%}")

    if median_days > 0:
        parts.append(f"典型兑现 {median_days} 天")

    if confidence == "high" and max(prob_up, prob_down) >= 0.65:
        parts.append(f"⚠️ 胜率 {max(prob_up, prob_down):.0%} 超过 65%，历史参考价值较高")
    elif confidence == "low":
        parts.append("案例不足或方向分歧大，建议观望")

    return "，".join(parts)


# ─── 顶层入口 ──────────────────────────────────────────────

def progress_retrieve(
    current_price: float,
    current_structure: Structure,
    current_date: datetime,
    history_bars: list[Bar],
    history_structures: list[Structure],
    symbol: str,
    top_k: int = 15,
    progress_tolerance: float = 0.15,
) -> tuple[Playbook, list[ProgressMatch]]:
    """
    结构进度检索的顶层入口。

    流程：
    1. 构建历史完整结构列表（含价格范围和方向）
    2. 计算当前价格在每个历史结构中的价格进度
    3. 找到价格进度相似的历史前半程
    4. 看那些前半程的后半程走成了什么样
    5. 聚合出候选剧本

    Args:
        current_price: 当前价格（如今天收盘价）
        current_structure: 当前编译出的结构
        current_date: 当前日期
        history_bars: 该品种的全量历史 bars
        history_structures: 该品种的全量历史完整结构
        symbol: 品种代码
        top_k: 返回前 K 个匹配
        progress_tolerance: 价格进度匹配容差

    Returns:
        (Playbook, list[ProgressMatch])
    """
    # 1. 构建历史完整结构
    historical = build_historical_full_structures(history_bars, history_structures, symbol)

    if not historical:
        empty = Playbook(
            n_matches=0, prob_up=0, prob_down=0,
            median_remaining_move=0, q25_remaining_move=0, q75_remaining_move=0,
            median_remaining_days=0, win_rate=0,
            direction="unclear", confidence="low",
            summary="历史中无足够长的完整结构可供进度分析",
        )
        return empty, []

    # 2. 匹配
    matches = match_by_price_progress(
        current_price, current_structure, current_date,
        historical, progress_tolerance, top_k=top_k,
    )

    # 3. 聚合
    playbook = aggregate_playbook(matches)

    return playbook, matches
