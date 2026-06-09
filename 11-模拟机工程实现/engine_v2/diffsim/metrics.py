"""metrics.py — 衡量闭环咬合与活/死秩序的指标。"""
from __future__ import annotations


def jaccard_flux(set_a, set_b):
    """两个活跃集合之间的 Jaccard 距离 (= 1 - 交/并)。
    0 => 活跃集完全不变(死秩序); >0 => 有自主演化(活秩序)。"""
    a, b = set(set_a), set(set_b)
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return 1.0 - inter / union if union else 0.0


def summarize(report):
    lines = []
    lines.append(f"{'层':<4}{'N':>5}{'组织数':>7}{'密封':>6}{'自主 flux':>11}  模式")
    for r in report:
        lines.append(
            f"L{r['layer']:<3}{r['N']:>5}{r['n_orgs']:>7}"
            f"{('是' if r['sealed'] else '否'):>6}{r['autonomous_flux']:>11.4f}  {r['mode']}"
        )
    return "\n".join(lines)
