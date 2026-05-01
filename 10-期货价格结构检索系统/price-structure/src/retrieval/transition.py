"""
稳态转移矩阵 v2 — 条件概率 + Wilson 置信区间 + Jeffreys 先验平滑
回答：在 {当前阶段, 质量层, 通量符号} 条件下，下一个稳态最可能落在哪里？
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class TransitionCandidate:
    target_zone_offset: float  # 相对当前 Zone 中心的价位偏移（归一化）
    prob: float  # 平滑后的条件概率
    prob_lower: float  # Wilson 95% 下界
    prob_upper: float  # Wilson 95% 上界
    n_support: int  # 样本量
    avg_holding_days: float  # 平均到达时间
    avg_max_drawdown: float  # 平均最大不利偏移


@dataclass
class TransitionDistribution:
    context: Dict[str, str]
    candidates: List[TransitionCandidate]
    total_samples: int
    entropy: float  # 分布熵，越低越集中

    def top_k(self, k: int = 3) -> List[TransitionCandidate]:
        return sorted(self.candidates, key=lambda c: -c.prob)[:k]


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score 区间，比正态近似稳健得多，特别适合小样本"""
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _shannon_entropy(probs: List[float]) -> float:
    return -sum(p * math.log(p + 1e-12) for p in probs if p > 0)


def build_transition_distribution(
        history_transitions: List[dict],
        current_context: Dict[str, str],
        zone_bin_width: float = 0.02,  # 相对价位 2% 一档
        min_support: int = 5,
        jeffreys_alpha: float = 0.5,  # Jeffreys 先验平滑
) -> TransitionDistribution:
    """
    history_transitions: 每条记录形如
      {'phase': 'confirmation', 'quality': 'B', 'flux_sign': '-',
       'from_zone': 98895, 'to_zone': 101500,
       'holding_days': 14, 'max_drawdown': 0.023}
    current_context: {'phase': 'confirmation', 'quality': 'B', 'flux_sign': '-'}
    """
    # 1. 按 context 严格过滤
    matched = [
        t for t in history_transitions
        if all(t.get(k) == v for k, v in current_context.items())
    ]

    # 2. 如果严格匹配样本不足，逐步放松（先去掉 flux_sign，再去掉 quality）
    if len(matched) < min_support:
        relax_ctx = {k: v for k, v in current_context.items() if k != "flux_sign"}
        matched = [t for t in history_transitions
                   if all(t.get(k) == v for k, v in relax_ctx.items())]
    if len(matched) < min_support:
        matched = [t for t in history_transitions
                   if t.get("phase") == current_context.get("phase")]

    total = len(matched)
    if total == 0:
        return TransitionDistribution(current_context, [], 0, 0.0)

    # 3. 归一化价位偏移并分箱
    buckets: Dict[int, List[dict]] = defaultdict(list)
    for t in matched:
        offset = (t["to_zone"] - t["from_zone"]) / t["from_zone"]
        bucket_id = int(round(offset / zone_bin_width))
        buckets[bucket_id].append(t)

    # 4. Jeffreys 平滑 + Wilson 置信区间
    n_buckets = len(buckets)
    denom_smooth = total + jeffreys_alpha * n_buckets
    candidates: List[TransitionCandidate] = []
    for bucket_id, recs in buckets.items():
        k = len(recs)
        p_smooth = (k + jeffreys_alpha) / denom_smooth
        lower, upper = wilson_interval(k, total)
        offset_mid = bucket_id * zone_bin_width
        avg_hold = float(np.mean([r["holding_days"] for r in recs]))
        avg_dd = float(np.mean([r.get("max_drawdown", 0.0) for r in recs]))
        candidates.append(TransitionCandidate(
            target_zone_offset=offset_mid,
            prob=p_smooth,
            prob_lower=lower,
            prob_upper=upper,
            n_support=k,
            avg_holding_days=avg_hold,
            avg_max_drawdown=avg_dd,
        ))

    probs = [c.prob for c in candidates]
    entropy = _shannon_entropy(probs)

    return TransitionDistribution(
        context=current_context,
        candidates=candidates,
        total_samples=total,
        entropy=entropy,
    )


def format_transition_report(dist: TransitionDistribution, current_price: float, zone_center: float) -> str:
    """生成可直接贴到 Streamlit 的 Markdown 报告"""
    if dist.total_samples == 0:
        return "⚠️ 历史样本不足，无法给出条件分布"

    lines = [
        f"**条件**：{dist.context}",
        f"**样本量**：{dist.total_samples} · **分布熵**：{dist.entropy:.2f}"
        f"（熵越低越集中，参考阈值 <1.0 为高置信）",
        "",
        "| 排名 | 目标价位 | 概率（95% CI） | 样本 | 平均到达 | 平均最大回撤 |",
        "|------|----------|----------------|------|----------|--------------|",
    ]
    for i, c in enumerate(dist.top_k(5), 1):
        target_price = zone_center * (1 + c.target_zone_offset)
        lines.append(
            f"| {i} | {target_price:.0f}（{c.target_zone_offset:+.1%}） "
            f"| {c.prob:.1%}（{c.prob_lower:.1%}~{c.prob_upper:.1%}） "
            f"| {c.n_support} | {c.avg_holding_days:.1f}天 "
            f"| {c.avg_max_drawdown:.2%} |"
        )
    return "\n".join(lines)
