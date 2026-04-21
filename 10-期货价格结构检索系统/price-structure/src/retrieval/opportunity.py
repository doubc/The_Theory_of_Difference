"""
机会聚合层 —— 把 top_k 模板匹配聚合成面向研究决策的 Opportunity 对象。
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from statistics import median
from typing import Sequence

FEATURE_SCALES = {
    "avg_speed_ratio": 2.0,
    "avg_time_ratio": 2.0,
    "zone_rel_bw": 0.03,
    "high_dispersion": 0.02,
    "low_dispersion": 0.02,
    "zone_strength": 5.0,
}
FEATURES = list(FEATURE_SCALES.keys())


@dataclass
class TemplateMatch:
    symbol: str
    symbol_name: str
    end_date: str
    outcome_start: str
    direction: str  # up / down / unclear
    up_move: float
    down_move: float
    days_to_peak: int
    days_to_trough: int
    bundle_id: str | None
    diff_detail: dict[str, float]
    distance: float
    similarity: float  # 1/(1+distance)


@dataclass
class Opportunity:
    symbol: str
    symbol_name: str
    current_price: float
    confirmed_at: str
    attention_score: float

    direction: str
    direction_confidence: float
    potential_median: float
    potential_p25: float
    potential_p75: float
    trigger_price: float
    expected_window_days: int

    top_matches: list[TemplateMatch]

    sim_total: float
    sim_geometry: float
    sim_relation: float
    sim_family: float
    diff_detail: dict[str, float]

    evidence: dict
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["top_matches"] = [asdict(m) for m in self.top_matches]
        return d


# ── 聚合逻辑 ───────────────────────────────────────────────────────────
def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _decompose_similarity(diff_detail: dict[str, float]) -> tuple[float, float, float]:
    """把分项差异拆成几何 / 关系 / 家族三类"""
    geo_keys = ["zone_rel_bw", "high_dispersion", "low_dispersion"]
    rel_keys = ["avg_speed_ratio", "avg_time_ratio"]
    fam_keys = ["zone_strength"]

    def _score(keys):
        vals = [diff_detail.get(k, 0) for k in keys if k in diff_detail]
        if not vals:
            return 0.0
        avg = sum(vals) / len(vals)
        return 1 / (1 + avg)

    return _score(geo_keys), _score(rel_keys), _score(fam_keys)


def compute_attention_score(
        similarity: float,
        direction_confidence: float,
        potential_median: float,
        match_count: int,
) -> float:
    """
    关注度评分: 综合相似度、方向一致性、潜力、样本充足度。
    输出 0~100 分。
    """
    sim_w = min(similarity, 1.0) * 40  # 相似度权重 40
    dir_w = direction_confidence * 25  # 方向置信度权重 25
    pot_w = min(potential_median / 0.20, 1.0) * 25  # 潜力权重 25 (20% 封顶)
    cnt_w = min(match_count / 5, 1.0) * 10  # 样本充足度权重 10
    return round(sim_w + dir_w + pot_w + cnt_w, 2)


def generate_next_actions(
        symbol: str,
        direction: str,
        trigger_price: float,
        top_matches: list[TemplateMatch],
) -> list[str]:
    """自动生成研究建议（不是交易信号，是研究动作）"""
    actions = []
    if top_matches:
        best = top_matches[0]
        actions.append(
            f"先对照 {best.symbol_name}({best.symbol}) {best.end_date[:7]} 的结构图，"
            f"确认高低点分布是否一致"
        )
        if len(top_matches) >= 3:
            other = top_matches[1:3]
            names = "、".join(f"{m.symbol_name} {m.end_date[:7]}" for m in other)
            actions.append(f"再对比 {names} 的后续走势差异，判断当前形态更接近哪种")

    if direction == "up":
        actions.append(f"重点观察价格突破 {trigger_price:.1f} 之后的放量情况")
    elif direction == "down":
        actions.append(f"重点观察价格跌破 {trigger_price:.1f} 之后的反抽力度")
    else:
        actions.append("方向尚不明朗，建议等待一根明确方向的 bar 再介入研究")

    actions.append(f"在数据库中调出 {symbol} 近 6 个月日线，人工核对 Zone 标注位置")
    return actions


def aggregate_opportunity(
        symbol: str,
        symbol_name: str,
        current_price: float,
        confirmed_at: str,
        current_inv: dict,
        top_matches: list[TemplateMatch],
        evidence: dict,
) -> Opportunity | None:
    """核心聚合函数"""
    if not top_matches:
        return None

    # 方向置信度
    up_count = sum(1 for m in top_matches if m.direction == "up")
    down_count = sum(1 for m in top_matches if m.direction == "down")
    total = len(top_matches)
    if up_count > down_count:
        direction = "up"
        direction_conf = up_count / total
    elif down_count > up_count:
        direction = "down"
        direction_conf = down_count / total
    else:
        direction = "unclear"
        direction_conf = 0.5

    # 潜力分布（取主方向那一侧的 move）
    if direction == "up":
        moves = [m.up_move for m in top_matches if m.direction == "up"]
        days = [m.days_to_peak for m in top_matches if m.direction == "up" and m.days_to_peak > 0]
    elif direction == "down":
        moves = [m.down_move for m in top_matches if m.direction == "down"]
        days = [m.days_to_trough for m in top_matches if m.direction == "down" and m.days_to_trough > 0]
    else:
        moves = [max(m.up_move, m.down_move) for m in top_matches]
        days = []

    if not moves:
        moves = [0.0]

    pot_median = median(moves)
    pot_p25 = _percentile(moves, 0.25)
    pot_p75 = _percentile(moves, 0.75)
    expected_days = int(median(days)) if days else 20

    # 触发价
    if direction == "up":
        trigger_price = current_price * 1.01
    elif direction == "down":
        trigger_price = current_price * 0.99
    else:
        trigger_price = current_price

    # 相似度
    sim_total = top_matches[0].similarity
    diff_detail = top_matches[0].diff_detail
    sim_geo, sim_rel, sim_fam = _decompose_similarity(diff_detail)

    attention = compute_attention_score(sim_total, direction_conf, pot_median, total)

    actions = generate_next_actions(symbol, direction, trigger_price, top_matches)

    return Opportunity(
        symbol=symbol,
        symbol_name=symbol_name,
        current_price=current_price,
        confirmed_at=confirmed_at,
        attention_score=attention,
        direction=direction,
        direction_confidence=round(direction_conf, 3),
        potential_median=round(pot_median, 4),
        potential_p25=round(pot_p25, 4),
        potential_p75=round(pot_p75, 4),
        trigger_price=round(trigger_price, 2),
        expected_window_days=expected_days,
        top_matches=top_matches[:5],
        sim_total=round(sim_total, 3),
        sim_geometry=round(sim_geo, 3),
        sim_relation=round(sim_rel, 3),
        sim_family=round(sim_fam, 3),
        diff_detail=diff_detail,
        evidence=evidence,
        next_actions=actions,
    )
