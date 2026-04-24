"""
相似结构检索 + 后验统计 + 最近稳态分析

给定一个当前结构，从样本库中找到最相似的历史案例，
并聚合它们的前向演化结果，输出后验分布 + 稳态分析。

V1.6 P1 升级：
- context_contrast 作为首要过滤条件（同反差类型才能匹配）
- 检索结果附带"最近稳态"分析
- 匹配原因归因解释

V1.6 P2 升级（2026-04-24）：
- 顺时序约束：只检索最近 max_lookback_days 天内的样本
- 时间衰减：越近的样本在排序中权重越高
- 后验统计分窗口：近期/中期/远期后验分开计算
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.models import Structure, Zone, ZoneSource
from src.sample.store import Sample, SampleStore
from src.retrieval.similarity import similarity, SimilarityScore


@dataclass
class Neighbor:
    """一个近邻样本 + 相似度 + 匹配归因"""
    sample: Sample
    score: SimilarityScore
    match_reason: str = ""  # 匹配原因归因解释（V1.6 P1）


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


@dataclass
class RetrievalResult:
    """检索结果"""
    query: Structure
    neighbors: list[Neighbor]
    posterior: PosteriorStats


class RetrievalEngine:
    """相似结构检索引擎（V1.6 P1 升级）"""

    def __init__(self, store: SampleStore):
        self.store = store

    def retrieve(
        self,
        query: Structure,
        top_k: int = 10,
        filter_label: str | None = None,
        min_score: float = 0.3,
        filter_contrast: bool = True,
        max_lookback_days: int = 0,
    ) -> RetrievalResult:
        """
        检索最相似的历史结构

        v3.1 优化：批量预提取不变量向量，向量化几何相似度计算。
        V1.6 P1: 反差类型过滤 + 匹配归因。

        历史样本本身都是真实的，不做权重调整。
        max_lookback_days 可选启用，默认不限制（0 = 全量历史）。

        Args:
            query: 当前编译出的结构
            top_k: 返回前 K 个近邻
            filter_label: 只检索特定类型
            min_score: 最低相似度阈值
            filter_contrast: 是否按共同反差类型过滤（V1.6 P1，D2.2）
            max_lookback_days: 最大回溯天数（默认 0 = 不限制）。
                仅在需要主动限制检索范围时启用。

        Returns:
            RetrievalResult 含近邻列表 + 后验统计
        """
        candidates = self.store.filter(label_type=filter_label) if filter_label else self.store.load_all()

        # 可选：限制检索范围
        if max_lookback_days > 0 and query.t_end:
            cutoff = query.t_end - timedelta(days=max_lookback_days)
            candidates = [sp for sp in candidates if sp.t_end >= cutoff]

        # ── V1.6 P1: 反差类型过滤 ──
        query_contrast = query.zone.context_contrast.value if query.zone else "unknown"
        if filter_contrast and query_contrast != "unknown":
            same_contrast = [sp for sp in candidates
                             if sp.structure.get("invariants", {}).get("contrast_type") == query_contrast]
            if same_contrast:
                candidates = same_contrast

        # ── v3.1: 批量预提取不变量，向量化几何相似度 ──
        try:
            import numpy as np
            from src.fast import batch_geometric_similarity_fast
            from src.retrieval.similarity import (
                _normalized_vector, INVARIANT_KEYS, INVARIANT_SCALES,
                relational_similarity, motion_similarity, family_similarity,
                SimilarityScore,
            )

            # 提取查询向量
            q_vec = np.array(_normalized_vector(query.invariants), dtype=np.float64)
            dim = len(q_vec)

            # 预构建候选矩阵
            valid_samples = []
            c_matrix_rows = []
            for sp in candidates:
                s2 = _rebuild_structure_shim(sp)
                if s2 is None:
                    continue
                valid_samples.append((sp, s2))
                c_matrix_rows.append(_normalized_vector(s2.invariants))

            if not c_matrix_rows:
                return RetrievalResult(query=query, neighbors=[], posterior=_aggregate_posterior([]))

            c_matrix = np.array(c_matrix_rows, dtype=np.float64)
            n = len(c_matrix_rows)

            # 批量几何相似度（C 加速）
            geo_scores = np.array(batch_geometric_similarity_fast(q_vec, c_matrix), dtype=np.float64)

            # 快速预筛：只对几何相似度 > 阈值的做完整计算
            geo_threshold = min_score * 0.5  # 几何分太低的直接跳过
            scored: list[Neighbor] = []

            for i, (sp, s2) in enumerate(valid_samples):
                if geo_scores[i] < geo_threshold:
                    continue

                sc = similarity(query, s2)
                if sc.total >= min_score:
                    reason = _generate_match_reason(query, s2, sc)
                    scored.append(Neighbor(sample=sp, score=sc, match_reason=reason))

        except (ImportError, Exception):
            # Fallback: 逐个计算
            scored: list[Neighbor] = []
            for sp in candidates:
                s2 = _rebuild_structure_shim(sp)
                if s2 is None:
                    continue
                sc = similarity(query, s2)
                if sc.total >= min_score:
                    reason = _generate_match_reason(query, s2, sc)
                    scored.append(Neighbor(sample=sp, score=sc, match_reason=reason))

        scored.sort(key=lambda n: n.score.total, reverse=True)
        top = scored[:top_k]
        posterior = _aggregate_posterior([n.sample for n in top])
        return RetrievalResult(query=query, neighbors=top, posterior=posterior)


def _rebuild_structure_shim(sp: Sample) -> Structure | None:
    """
    从 Sample.structure (dict) 重建一个最小 Structure 用于相似度计算
    只保留 invariants 与 zone / label / contrast_type，不重建 Point / Segment 细节
    """
    try:
        from src.models import ContrastType
        zd = sp.structure["zone"]
        ct_val = zd.get("context_contrast", sp.structure.get("invariants", {}).get("contrast_type", "unknown"))
        try:
            ct = ContrastType(ct_val)
        except (ValueError, KeyError):
            ct = ContrastType.UNKNOWN
        zone = Zone(
            price_center=zd["price_center"],
            bandwidth=zd["bandwidth"],
            source=ZoneSource(zd["source"]),
            strength=zd.get("strength", 0.0),
            context_contrast=ct,
        )
        s = Structure(
            zone=zone,
            invariants=sp.structure.get("invariants", {}),
            label=sp.label_type,
            symbol=sp.symbol,
            typicality=sp.typicality,
        )
        return s
    except Exception:
        return None


def _generate_match_reason(query: Structure, matched: Structure, score: SimilarityScore) -> str:
    """生成匹配归因解释（V1.6 P1：可叙事性）"""
    parts = []

    # 反差类型匹配
    qc = query.zone.context_contrast.value if query.zone else "unknown"
    mc = matched.zone.context_contrast.value if matched.zone else "unknown"
    if qc != "unknown" and mc != "unknown" and qc == mc:
        contrast_labels = {
            "panic": "恐慌型",
            "oversupply": "供需失衡型",
            "policy": "政策驱动型",
            "liquidity": "流动性驱动型",
            "speculation": "投机驱动型",
        }
        parts.append(f"共同面临{contrast_labels.get(qc, qc)}反差")

    # 几何特征匹配
    if score.geometric > 0.7:
        parts.append("几何形态高度一致")
    elif score.geometric > 0.5:
        parts.append("几何形态大致相似")

    # 关系特征匹配
    qi = query.invariants
    mi = matched.invariants
    qsr = qi.get("avg_speed_ratio", 0)
    msr = mi.get("avg_speed_ratio", 0)
    if qsr and msr and abs(qsr - msr) < 0.3:
        parts.append("速度比高度一致")

    qtr = qi.get("avg_time_ratio", 0)
    mtr = mi.get("avg_time_ratio", 0)
    if qtr and mtr and abs(qtr - mtr) < 0.3:
        parts.append("试探频率高度一致")

    if not parts:
        parts.append(f"综合相似度 {score.total:.2f}")

    return "，".join(parts)


def _aggregate_posterior(samples: list[Sample]) -> PosteriorStats:
    """聚合前向演化结果为后验统计"""
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
