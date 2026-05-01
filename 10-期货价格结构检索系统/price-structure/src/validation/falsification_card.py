"""
可证伪实验卡片 — 每条信号发出前必须生成一张卡片，
包含：假设、预期、失效条件、评估时点、先验概率。
到期后自动对照实际走势，生成 hit/miss 记录，形成长期命中率数据库。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List


@dataclass
class FalsificationCard:
    card_id: str
    created_at: str
    symbol: str
    structure_zone: float
    phase: str
    quality_tier: str

    # 可证伪三要素
    hypothesis: str  # 预测描述
    expected_direction: str  # 'up' / 'down' / 'range'
    expected_target_price: float
    expected_stop_price: float
    evaluation_deadline: str  # ISO 时间

    # 事前登记
    prior_probability: float  # 来自转移矩阵
    prior_ci_lower: float
    prior_ci_upper: float
    historical_support: int  # 样本量

    # 事后填写
    closed: bool = False
    actual_direction: Optional[str] = None
    actual_max_favorable: Optional[float] = None
    actual_max_adverse: Optional[float] = None
    hit: Optional[bool] = None
    notes: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def create_card(
        symbol: str,
        zone_center: float,
        current_price: float,
        phase: str,
        quality_tier: str,
        transition_dist,  # TransitionDistribution 对象
        holding_days: int = 10,
) -> FalsificationCard:
    """根据当前结构状态和转移分布自动生成卡片"""
    top = transition_dist.top_k(1)[0] if transition_dist.candidates else None
    if top is None:
        raise ValueError("转移分布为空，无法生成可证伪卡片")

    target_price = zone_center * (1 + top.target_zone_offset)
    direction = "up" if target_price > current_price else ("down" if target_price < current_price else "range")
    stop_price = current_price * (1 - 0.015) if direction == "up" else current_price * (1 + 0.015)

    return FalsificationCard(
        card_id=str(uuid.uuid4())[:8],
        created_at=datetime.now().isoformat(timespec="seconds"),
        symbol=symbol,
        structure_zone=zone_center,
        phase=phase,
        quality_tier=quality_tier,
        hypothesis=(
            f"{symbol} 当前处于 {phase} 阶段（{quality_tier}层质量），"
            f"预计在 {holding_days} 个交易日内滑向 {target_price:.0f} "
            f"（偏移 {top.target_zone_offset:+.1%}）。"
        ),
        expected_direction=direction,
        expected_target_price=round(target_price, 2),
        expected_stop_price=round(stop_price, 2),
        evaluation_deadline=(datetime.now() + timedelta(days=holding_days)).isoformat(timespec="seconds"),
        prior_probability=round(top.prob, 3),
        prior_ci_lower=round(top.prob_lower, 3),
        prior_ci_upper=round(top.prob_upper, 3),
        historical_support=top.n_support,
    )


def close_card(card: FalsificationCard, price_series_after: List[float]) -> FalsificationCard:
    """到期回填实际走势，判定 hit/miss"""
    if not price_series_after:
        return card
    start = price_series_after[0]
    highs = max(price_series_after)
    lows = min(price_series_after)
    end = price_series_after[-1]

    card.actual_max_favorable = round(
        (highs - start) / start if card.expected_direction == "up" else (start - lows) / start, 4
    )
    card.actual_max_adverse = round(
        (start - lows) / start if card.expected_direction == "up" else (highs - start) / start, 4
    )
    card.actual_direction = "up" if end > start else ("down" if end < start else "range")

    if card.expected_direction == "range":
        card.hit = abs(end - start) / start < 0.01
    elif card.expected_direction == "up":
        card.hit = highs >= card.expected_target_price and lows > card.expected_stop_price
    else:
        card.hit = lows <= card.expected_target_price and highs < card.expected_stop_price

    card.closed = True
    return card


def append_to_ledger(card: FalsificationCard, ledger_path: str = "data/logs/falsification_ledger.jsonl"):
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(card.to_json() + "\n")


def compute_hit_rate(ledger_path: str = "data/logs/falsification_ledger.jsonl") -> Dict[str, Any]:
    """长期命中率统计，按质量层、阶段、置信区间分组"""
    p = Path(ledger_path)
    if not p.exists():
        return {"total": 0}
    records = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    closed = [r for r in records if r.get("closed")]
    if not closed:
        return {"total": len(records), "closed": 0}

    hits = sum(1 for r in closed if r.get("hit"))
    by_tier: Dict[str, List[bool]] = {}
    by_phase: Dict[str, List[bool]] = {}
    for r in closed:
        by_tier.setdefault(r["quality_tier"], []).append(bool(r["hit"]))
        by_phase.setdefault(r["phase"], []).append(bool(r["hit"]))

    return {
        "total": len(records),
        "closed": len(closed),
        "overall_hit_rate": round(hits / len(closed), 3),
        "by_quality_tier": {k: round(sum(v) / len(v), 3) for k, v in by_tier.items()},
        "by_phase": {k: round(sum(v) / len(v), 3) for k, v in by_phase.items()},
    }
