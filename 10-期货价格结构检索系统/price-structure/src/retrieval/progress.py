"""
结构进度检索 — 基于四层相似度的历史对照与预测

系统 = 结构 × 运动

核心问题：
  当前结构可能只是某个大结构的前半程。
  历史上走到类似位置的前半程，后来都走成了什么样？

实现思路：
  1. 编译出当前结构（Structure + MotionState + ProjectionAwareness）
  2. 编译历史全量数据，得到历史结构列表
  3. 用四层相似度（几何 + 关系 + 运动 + 族）找最相似的历史结构
  4. 对每个匹配的历史结构，计算其后续走势（前向演化）
  5. 聚合后续走势 → 候选剧本

四层相似度：
  - 几何层：不变量向量的归一化欧氏距离
  - 关系层：Zone 来源 / Cycle 数 / 速度比方向一致性
  - 运动层：阶段趋势 / 守恒通量 / 稳态距离 / DTW 速度比序列
  - 族层：标签一致 / 镜像变体

顺时序约束：
  - 历史结构必须在当前结构之前形成（t_end < query.t_start）
  - 后续走势是已发生的真实数据
  - 不做权重调整，不做时间衰减

依赖：
  - src/retrieval/similarity.py: 四层相似度
  - src/compiler/pipeline.py: 结构编译
  - src/models.py: 对象模型
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Sequence

from src.data.loader import Bar
from src.compiler.pipeline import compile_full, CompilerConfig
from src.retrieval.similarity import similarity, SimilarityScore
from src.models import Structure, SystemState


# ─── 数据结构 ──────────────────────────────────────────────

@dataclass
class HistoricalCase:
    """
    一个历史结构的完整信息 + 后续走势

    structure: 历史编译出的结构
    similarity: 与当前结构的四层相似度
    match_reason: 匹配原因
    after_direction: 后续走势方向
    after_move: 后续价格变化比例
    after_days: 兑现天数
    after_max_rise: 后续最大涨幅
    after_max_dd: 后续最大回撤
    """
    structure: Structure
    similarity: SimilarityScore
    match_reason: str
    after_direction: str  # "up" / "down" / "range"
    after_move: float
    after_days: int
    after_max_rise: float
    after_max_dd: float

    @property
    def zone_center(self) -> float:
        return self.structure.zone.price_center

    @property
    def cycle_count(self) -> int:
        return self.structure.cycle_count

    @property
    def period(self) -> str:
        s = self.structure.t_start.strftime("%Y-%m-%d") if self.structure.t_start else "?"
        e = self.structure.t_end.strftime("%Y-%m-%d") if self.structure.t_end else "?"
        return f"{s} ~ {e}"


@dataclass
class Playbook:
    """
    候选剧本 — 从多个历史后续走势中聚合

    基于四层相似度匹配的历史案例，给出：
    - 方向概率
    - 中位收益和分位数
    - 典型兑现天数
    - 胜率
    """
    n_matches: int
    prob_up: float
    prob_down: float
    prob_range: float
    median_move: float
    q25_move: float
    q75_move: float
    median_days: int
    direction: str  # "bullish" / "bearish" / "unclear"
    confidence: str  # "high" (>=65%) / "medium" (50-65%) / "low" (<50%)
    win_rate: float
    summary: str
    cases: list[HistoricalCase] = field(default_factory=list)

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


# ─── 前向演化计算 ──────────────────────────────────────────

def _compute_after_outcome(
    bars: list[Bar],
    structure: Structure,
    window_days: int = 20,
) -> dict:
    """
    计算一个历史结构结束后的前向走势。

    取结构 t_end 之后 window_days 天的 bars，
    计算方向、幅度、兑现天数、最大涨幅和最大回撤。

    严格顺时序：只用 t_end 之后的数据。
    """
    if not structure.t_end or not bars:
        return {"direction": "range", "move": 0.0, "days": 0,
                "max_rise": 0.0, "max_dd": 0.0}

    # 找到结构结束后的 bars
    after_start = structure.t_end + timedelta(days=1)
    after_end = after_start + timedelta(days=window_days)
    after_bars = [b for b in bars if after_start <= b.timestamp <= after_end]

    if not after_bars:
        return {"direction": "range", "move": 0.0, "days": 0,
                "max_rise": 0.0, "max_dd": 0.0}

    # 起始价 = 结构最后一根 bar 的收盘价
    # 这里用 after_bars[0] 的 open 作为近似
    start_price = after_bars[0].open
    if start_price <= 0:
        return {"direction": "range", "move": 0.0, "days": 0,
                "max_rise": 0.0, "max_dd": 0.0}

    closes = [b.close for b in after_bars]
    highs = [b.high for b in after_bars]
    lows = [b.low for b in after_bars]

    # 最终收益
    end_price = closes[-1]
    final_move = (end_price - start_price) / start_price

    # 最大涨幅和最大回撤
    peak = start_price
    max_rise = 0.0
    max_dd = 0.0
    trough = start_price

    for b in after_bars:
        if b.high > peak:
            peak = b.high
            max_rise = (peak - start_price) / start_price
        if b.low < trough:
            trough = b.low
            max_dd = (start_price - trough) / start_price

    # 方向判定
    up = (max(highs) - start_price) / start_price
    down = (start_price - min(lows)) / start_price

    if up > down * 1.5 and final_move > 0.005:
        direction = "up"
        move = up
    elif down > up * 1.5 and final_move < -0.005:
        direction = "down"
        move = -down
    else:
        direction = "range"
        move = final_move

    # 兑现天数
    if direction == "up":
        peak_price = max(highs)
        days = next((i for i, b in enumerate(after_bars) if b.high >= peak_price), window_days)
    elif direction == "down":
        trough_price = min(lows)
        days = next((i for i, b in enumerate(after_bars) if b.low <= trough_price), window_days)
    else:
        days = len(after_bars)

    return {
        "direction": direction,
        "move": round(move, 4),
        "days": days,
        "max_rise": round(max_rise, 4),
        "max_dd": round(max_dd, 4),
    }


# ─── 匹配原因生成 ──────────────────────────────────────────

def _generate_match_reason(
    query: Structure,
    matched: Structure,
    score: SimilarityScore,
) -> str:
    """基于四层相似度生成匹配归因"""
    parts = []

    # 反差类型
    qc = query.zone.context_contrast.value if query.zone else "unknown"
    mc = matched.zone.context_contrast.value if matched.zone else "unknown"
    if qc != "unknown" and mc != "unknown" and qc == mc:
        contrast_labels = {
            "panic": "恐慌型", "oversupply": "供需失衡型",
            "policy": "政策驱动型", "liquidity": "流动性驱动型",
            "speculation": "投机驱动型",
        }
        parts.append(f"同为{contrast_labels.get(qc, qc)}反差")

    # 几何
    if score.geometric > 0.7:
        parts.append("几何形态高度一致")
    elif score.geometric > 0.5:
        parts.append("几何形态大致相似")

    # 运动
    if score.motion > 0.7:
        parts.append("运动态一致")

    # 速度比
    qsr = query.avg_speed_ratio
    msr = matched.avg_speed_ratio
    if abs(qsr - msr) < 0.3:
        parts.append(f"速度比接近({qsr:.2f} vs {msr:.2f})")

    # 时间跨度
    if matched.t_start and matched.t_end:
        days = (matched.t_end - matched.t_start).days
        parts.append(f"历史跨度{days}天")

    return "，".join(parts) if parts else f"综合相似度 {score.total:.2f}"


# ─── 核心检索 ──────────────────────────────────────────────

def progress_retrieve(
    query: Structure,
    history_structures: list[Structure],
    history_bars: list[Bar],
    after_window: int = 20,
    min_similarity: float = 0.3,
    top_k: int = 15,
) -> tuple[Playbook, list[HistoricalCase]]:
    """
    结构进度检索。

    用四层相似度在历史结构中找最相似的案例，
    看那些案例的前向走势，聚合成候选剧本。

    Args:
        query: 当前编译出的结构（必须有 t_end）
        history_structures: 历史编译出的结构列表
        history_bars: 该品种的全量历史 bars（用于计算前向走势）
        after_window: 匹配后观察天数（默认 20）
        min_similarity: 最低相似度阈值
        top_k: 返回前 K 个匹配

    Returns:
        (Playbook, list[HistoricalCase])
    """
    if not query.t_end:
        empty = _empty_playbook("当前结构无时间信息")
        return empty, []

    # 过滤：只看在当前结构之前形成的历史结构
    candidates = [
        hs for hs in history_structures
        if hs.t_end and hs.t_end < query.t_start
        and hs.cycle_count >= 2
    ]

    if not candidates:
        empty = _empty_playbook("历史中无足够早的结构")
        return empty, []

    # 四层相似度匹配
    cases = []
    for hs in candidates:
        sc = similarity(query, hs)
        if sc.total < min_similarity:
            continue

        # 前向走势
        outcome = _compute_after_outcome(history_bars, hs, after_window)

        # 匹配原因
        reason = _generate_match_reason(query, hs, sc)

        cases.append(HistoricalCase(
            structure=hs,
            similarity=sc,
            match_reason=reason,
            after_direction=outcome["direction"],
            after_move=outcome["move"],
            after_days=outcome["days"],
            after_max_rise=outcome["max_rise"],
            after_max_dd=outcome["max_dd"],
        ))

    # 按综合相似度排序
    cases.sort(key=lambda c: c.similarity.total, reverse=True)
    cases = cases[:top_k]

    # 聚合
    playbook = _aggregate_playbook(cases)

    return playbook, cases


def _aggregate_playbook(cases: list[HistoricalCase]) -> Playbook:
    """从历史案例中聚合候选剧本"""
    n = len(cases)
    if n == 0:
        return _empty_playbook("无足够相似的历史案例")

    # 方向统计
    ups = sum(1 for c in cases if c.after_direction == "up")
    downs = sum(1 for c in cases if c.after_direction == "down")
    ranges = n - ups - downs

    prob_up = ups / n
    prob_down = downs / n
    prob_range = ranges / n

    # 收益统计
    moves = [c.after_move for c in cases]
    days = [c.after_days for c in cases if c.after_days > 0]

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

    # 胜率
    win_count = sum(1 for c in cases
                    if (c.after_direction == "up" and c.after_move > 0)
                    or (c.after_direction == "down" and c.after_move < 0))
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

    parts = [f"基于 {n} 个历史相似结构"]
    parts.append(f"方向：{dir_label.get(direction, '?')}（{conf_label.get(confidence, '?')}）")
    parts.append(f"上涨 {prob_up:.0%}，下跌 {prob_down:.0%}，横盘 {prob_range:.0%}")
    parts.append(f"后半程中位收益 {median_move:+.1%}")
    if median_days > 0:
        parts.append(f"典型兑现 {median_days} 天")
    if confidence == "high" and max_prob >= 0.65:
        parts.append(f"⚠️ 胜率 {max_prob:.0%} 超过 65%，历史参考价值较高")

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
        cases=cases,
    )


def _empty_playbook(reason: str) -> Playbook:
    return Playbook(
        n_matches=0, prob_up=0, prob_down=0, prob_range=1.0,
        median_move=0, q25_move=0, q75_move=0, median_days=0,
        direction="unclear", confidence="low", win_rate=0,
        summary=reason,
    )
