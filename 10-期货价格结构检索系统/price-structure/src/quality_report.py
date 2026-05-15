"""
结构库质量报告 — 定期生成全库质量分布报告

P1 待办事项-6: 监控 A 层占比是否在下降（库退化）。
~100 行，纯函数 + JSONL 持久化。

用法:
    from src.quality_report import generate_quality_report, QualityReport
    report = generate_quality_report(structures, system_states)
    report.save("output/quality_report_2026-04-26.jsonl")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TierDistribution:
    """质量层级分布"""
    total: int = 0
    a_count: int = 0
    b_count: int = 0
    c_count: int = 0
    d_count: int = 0
    a_ratio: float = 0.0
    b_ratio: float = 0.0
    c_ratio: float = 0.0
    d_ratio: float = 0.0


@dataclass
class SymbolQuality:
    """单品种质量摘要"""
    symbol: str = ""
    structure_count: int = 0
    a_count: int = 0
    b_count: int = 0
    mean_score: float = 0.0
    worst_score: float = 0.0
    best_score: float = 0.0


@dataclass
class QualityDegradation:
    """退化检测结果"""
    is_degraded: bool = False
    a_ratio_delta: float = 0.0       # 与上次报告的 A层占比差
    worst_symbols: list[str] = field(default_factory=list)  # A层占比最低的品种
    new_d_tier: list[str] = field(default_factory=list)     # 新降到D层的品种


@dataclass
class QualityReport:
    """结构库质量报告"""
    date: str = ""
    tier_distribution: TierDistribution = field(default_factory=TierDistribution)
    by_symbol: list[SymbolQuality] = field(default_factory=list)
    degradation: QualityDegradation = field(default_factory=QualityDegradation)
    mean_score_overall: float = 0.0
    median_score_overall: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")

    @classmethod
    def load_latest(cls, path: str | Path) -> "QualityReport | None":
        """从 JSONL 文件加载最近一条报告"""
        p = Path(path)
        if not p.exists():
            return None
        last_line = None
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line is None:
            return None
        d = json.loads(last_line)
        return _from_flat_dict(d)


def _from_flat_dict(d: dict) -> QualityReport:
    """从扁平 dict 重建 QualityReport"""
    td = d.get("tier_distribution", {})
    tier_dist = TierDistribution(
        total=td.get("total", 0),
        a_count=td.get("a_count", 0),
        b_count=td.get("b_count", 0),
        c_count=td.get("c_count", 0),
        d_count=td.get("d_count", 0),
        a_ratio=td.get("a_ratio", 0.0),
        b_ratio=td.get("b_ratio", 0.0),
        c_ratio=td.get("c_ratio", 0.0),
        d_ratio=td.get("d_ratio", 0.0),
    )
    by_sym = []
    for s in d.get("by_symbol", []):
        by_sym.append(SymbolQuality(
            symbol=s.get("symbol", ""),
            structure_count=s.get("structure_count", 0),
            a_count=s.get("a_count", 0),
            b_count=s.get("b_count", 0),
            mean_score=s.get("mean_score", 0.0),
            worst_score=s.get("worst_score", 0.0),
            best_score=s.get("best_score", 0.0),
        ))
    deg = d.get("degradation", {})
    degradation = QualityDegradation(
        is_degraded=deg.get("is_degraded", False),
        a_ratio_delta=deg.get("a_ratio_delta", 0.0),
        worst_symbols=deg.get("worst_symbols", []),
        new_d_tier=deg.get("new_d_tier", []),
    )
    return QualityReport(
        date=d.get("date", ""),
        tier_distribution=tier_dist,
        by_symbol=by_sym,
        degradation=degradation,
        mean_score_overall=d.get("mean_score_overall", 0.0),
        median_score_overall=d.get("median_score_overall", 0.0),
    )


def generate_quality_report(
    structures: list,
    system_states: list | None = None,
    prev_report: QualityReport | None = None,
    degradation_threshold: float = -0.10,
) -> QualityReport:
    """
    生成结构库质量报告

    Args:
        structures: 编译出的 Structure 列表
        system_states: SystemState 列表（可选）
        prev_report: 上次报告（用于退化检测）
        degradation_threshold: A层占比下降多少视为退化

    Returns:
        QualityReport
    """
    from src.quality import assess_quality

    today = datetime.now().strftime("%Y-%m-%d")

    # 逐结构评估
    scores = []
    by_tier = {"A": [], "B": [], "C": [], "D": []}
    by_symbol_map: dict[str, list[float]] = {}

    for s in structures:
        try:
            qa = assess_quality(s)
            scores.append(qa.score)
            by_tier[qa.tier.value].append(qa.score)
            sym = s.symbol or "unknown"
            by_symbol_map.setdefault(sym, []).append(qa.score)
        except Exception:
            scores.append(0.0)
            by_tier["D"].append(0.0)

    total = len(scores)
    tier_dist = TierDistribution(
        total=total,
        a_count=len(by_tier["A"]),
        b_count=len(by_tier["B"]),
        c_count=len(by_tier["C"]),
        d_count=len(by_tier["D"]),
    )
    if total > 0:
        tier_dist.a_ratio = tier_dist.a_count / total
        tier_dist.b_ratio = tier_dist.b_count / total
        tier_dist.c_ratio = tier_dist.c_count / total
        tier_dist.d_ratio = tier_dist.d_count / total

    # 按品种统计
    by_symbol = []
    for sym, sym_scores in sorted(by_symbol_map.items()):
        a_count = sum(1 for sc in sym_scores if sc >= 0.75)
        b_count = sum(1 for sc in sym_scores if 0.50 <= sc < 0.75)
        by_symbol.append(SymbolQuality(
            symbol=sym,
            structure_count=len(sym_scores),
            a_count=a_count,
            b_count=b_count,
            mean_score=sum(sym_scores) / len(sym_scores),
            worst_score=min(sym_scores),
            best_score=max(sym_scores),
        ))

    # 退化检测
    degradation = QualityDegradation()
    if prev_report and prev_report.tier_distribution.total > 0:
        prev_a = prev_report.tier_distribution.a_ratio
        curr_a = tier_dist.a_ratio
        degradation.a_ratio_delta = curr_a - prev_a
        degradation.is_degraded = degradation.a_ratio_delta < degradation_threshold
        # A层占比最低的品种
        degradation.worst_symbols = [
            sq.symbol for sq in sorted(by_symbol, key=lambda x: x.a_count / max(x.structure_count, 1))
            if sq.structure_count > 0
        ][:5]

    # 总体统计
    mean_score = sum(scores) / len(scores) if scores else 0.0
    median_score = sorted(scores)[len(scores) // 2] if scores else 0.0

    return QualityReport(
        date=today,
        tier_distribution=tier_dist,
        by_symbol=by_symbol,
        degradation=degradation,
        mean_score_overall=mean_score,
        median_score_overall=median_score,
    )
