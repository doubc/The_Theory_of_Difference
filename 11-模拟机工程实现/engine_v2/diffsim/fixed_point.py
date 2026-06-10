#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fixed_point.py — 整体固定点检测器 (Whole Fixed-Point Detector)

核心概念 (差异论 §10.3):
  真正的"整体"不是自指链无法继续的状态（min_org_size 技术终止），
  而是在某个层上 m9(整体) ≅ 整体 —— 自指的结果与自身结构同构。

  同构意味着: 再自指一次也不会产生新的结构信息。
  此时差异域的封闭已完满 → 整体(whole)被精确定义。

四条同构判据 (加权为 [0,1] iso_score):
  1. 组织数一致: k_n ≈ k_{n+1}    (权重 0.35)
  2. 组织大小分布: Jaccard 距离    (权重 0.25)
  3. 自主 flux 一致: 归一化差异     (权重 0.20)
  4. 规模保持: N_{n+1}/N_n ≥ 0.8   (权重 0.20)

用法:
  from diffsim.fixed_point import FixedPointDetector

  detector = FixedPointDetector()
  report = detector.compare(sealed_layer)
  if report.is_fixed_point():
      print(f"L{report.layer}: 整体固定点达成 (iso_score={report.iso_score:.3f})")

依赖: core.DifferenceField, world.Layer, mechanisms.m9_self_reference
"""
from __future__ import annotations
import numpy as np

from .core import DifferenceField
from .world import Layer
from .mechanisms import m9_self_reference


# ---------------------------------------------------------------------------
# FixedPointReport — 单次比较的结果容器
# ---------------------------------------------------------------------------
class FixedPointReport:
    """相邻两层间的固定点比较结果。"""

    def __init__(self, layer: int,
                 n_parent: int, n_child: int,
                 k_parent: int, k_child: int,
                 parent_org_sizes: list, child_org_sizes: list,
                 parent_flux: float, child_flux: float,
                 iso_score: float, reasons: list):
        self.layer = layer
        self.n_parent = n_parent
        self.n_child = n_child
        self.k_parent = k_parent
        self.k_child = k_child
        self.parent_org_sizes = sorted(parent_org_sizes)
        self.child_org_sizes = sorted(child_org_sizes)
        self.parent_flux = parent_flux
        self.child_flux = child_flux
        self.iso_score = iso_score
        self.reasons = reasons
        self._is_fp = iso_score >= 0.8

    def is_fixed_point(self, threshold: float = 0.8) -> bool:
        return self.iso_score >= threshold

    def summary(self) -> str:
        tag = "✅ 固定点" if self._is_fp else "❌ 非固定点"
        return (f"L{self.layer}: {tag}  iso_score={self.iso_score:.4f}  "
                f"k={self.k_parent}→{self.k_child}  N={self.n_parent}→{self.n_child}  "
                f"flux={self.parent_flux:.3f}→{self.child_flux:.3f}  "
                f"reasons={self.reasons}")

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "n_parent": self.n_parent, "n_child": self.n_child,
            "k_parent": self.k_parent, "k_child": self.k_child,
            "parent_org_sizes": self.parent_org_sizes,
            "child_org_sizes": self.child_org_sizes,
            "parent_flux": round(self.parent_flux, 4),
            "child_flux": round(self.child_flux, 4),
            "iso_score": round(self.iso_score, 4),
            "is_fixed_point": self._is_fp,
            "reasons": self.reasons,
        }


# ---------------------------------------------------------------------------
# FixedPointDetector — 核心检测引擎
# ---------------------------------------------------------------------------
class FixedPointDetector:
    """检测两个相邻层是否结构同构（整体固定点）。

    同构评分使用四条加权判据:
      1. 组织数差  (w=0.35)
      2. 组织大小分布 Jaccard  (w=0.25)
      3. 自主 flux 差异  (w=0.20)
      4. 规模收缩比  (w=0.20)
    """

    def __init__(self, weights: dict = None):
        self.weights = weights or {
            "org_count": 0.35,
            "size_dist": 0.25,
            "flux_similarity": 0.20,
            "scale_preservation": 0.20,
        }

    # ── 四个子评分 ────────────────────────────────────────────

    def _score_org_count(self, k_parent: int, k_child: int) -> float:
        """组织数一致评分: 完全一致→1, 差越大→越小"""
        m = max(k_parent, k_child, 1)
        return 1.0 - abs(k_parent - k_child) / m

    def _score_size_distribution(self, parent_sizes: list, child_sizes: list) -> float:
        """组织大小分布 Jaccard 评分"""
        all_sz = set(parent_sizes + child_sizes)
        if not all_sz:
            return 1.0 if not parent_sizes and not child_sizes else 0.0
        ph = np.array([parent_sizes.count(s) for s in all_sz], dtype=float)
        ch = np.array([child_sizes.count(s) for s in all_sz], dtype=float)
        ph /= max(ph.sum(), 1.0)
        ch /= max(ch.sum(), 1.0)
        intersection = np.minimum(ph, ch).sum()
        union = np.maximum(ph, ch).sum()
        return intersection / max(union, 1e-10)

    def _score_flux(self, parent_flux: float, child_flux: float) -> float:
        """自主 flux 一致性"""
        m = max(parent_flux, child_flux, 1e-6)
        return 1.0 - abs(parent_flux - child_flux) / m

    def _score_scale(self, n_parent: int, n_child: int) -> float:
        """规模保持: N_child/N_parent >= 0.8 → 满分; 严重收缩→低分"""
        if n_child >= n_parent:
            return 1.0
        ratio = n_child / max(n_parent, 1)
        return min(1.0, ratio / 0.8)

    # ── 核心 API ──────────────────────────────────────────────

    def compare(self, parent_layer: Layer) -> FixedPointReport | None:
        """密封父层 → m9 生成子层 → 密封子层 → 结构比较。

        如果 m9 返回 None (隐式终止), 判定为 iso_score=1.0 固定点。
        """
        f = parent_layer.field
        if not f.sealed:
            return None

        # 组织数 (已密封, 从 field.organizations 获取)
        parent_orgs = [o for o in f.organizations.values()
                       if len(o) >= parent_layer.p.min_org_size]
        k_p = len(parent_orgs)
        parent_sizes = [len(o) for o in parent_orgs]
        parent_flux = parent_layer.autonomous_flux()

        # 生成子层
        nxt = m9_self_reference(parent_layer, self_encapsulate=True)
        if nxt is None:
            # m9 无法生成下一层 → 隐式整体固定点
            return FixedPointReport(
                layer=f.layer,
                n_parent=f.N, n_child=0,
                k_parent=k_p, k_child=0,
                parent_org_sizes=parent_sizes, child_org_sizes=[],
                parent_flux=parent_flux, child_flux=0.0,
                iso_score=1.0,
                reasons=["m9 返回 None: 隐式终止固定点"],
            )

        # 运行子层密封
        child_layer = Layer(nxt, parent_layer.p)
        child_layer.run_until_seal()

        child_orgs = [o for o in nxt.organizations.values()
                      if len(o) >= parent_layer.p.min_org_size]
        k_c = len(child_orgs)
        child_sizes = [len(o) for o in child_orgs]
        child_flux = child_layer.autonomous_flux()

        # 四维评分
        s_k = self._score_org_count(k_p, k_c)
        s_sz = self._score_size_distribution(parent_sizes, child_sizes)
        s_f = self._score_flux(parent_flux, child_flux)
        s_sc = self._score_scale(f.N, nxt.N)

        w = self.weights
        iso = (w["org_count"] * s_k + w["size_dist"] * s_sz
               + w["flux_similarity"] * s_f + w["scale_preservation"] * s_sc)

        # 收集偏离原因
        reasons = []
        if s_k < 0.8:
            reasons.append(f"组织数差: {k_p}→{k_c}")
        if s_sz < 0.5:
            reasons.append(f"大小分布不匹配")
        if s_f < 0.8:
            reasons.append(f"flux 差: {parent_flux:.3f}→{child_flux:.3f}")
        if s_sc < 0.5:
            reasons.append(f"规模坍缩: {f.N}→{nxt.N}")
        if not reasons:
            reasons.append("✅ 四项均接近, 结构同构")

        return FixedPointReport(
            layer=f.layer,
            n_parent=f.N, n_child=nxt.N,
            k_parent=k_p, k_child=k_c,
            parent_org_sizes=parent_sizes,
            child_org_sizes=child_sizes,
            parent_flux=parent_flux,
            child_flux=child_flux,
            iso_score=round(iso, 4),
            reasons=reasons,
        )

    def analyze_world_reports(self, reports: list[dict]) -> list[FixedPointReport]:
        """对 RecursiveWorld.run() 返回的报告列表做逐层固定点检测。

        reports: RecursiveWorld 的 report 列表 [{layer, N, n_orgs, seal_step, ...}, ...]
        返回: 每层对应的 FixedPointReport 列表 (最后层因无 m9 产物而列为固定点)
        """
        fp_reports = []
        for i in range(len(reports) - 1):
            # 重建一个轻量 Layer 包装 (实际 field 信息已丢失, 需完整链)
            pass
        # 这个方法的完整版需要 RecursiveWorld 保留中间 layer 引用
        return fp_reports


# ---------------------------------------------------------------------------
# 辅助: 批量检测一个 RecursiveWorld 的完整链
# ---------------------------------------------------------------------------
def detect_fixed_points_in_world(world: 'RecursiveWorld',
                                  detector: FixedPointDetector = None) -> list[FixedPointReport]:
    """对一个已运行的 RecursiveWorld, 逐层检测固定点。

    需要 world.self_encapsulate=True 且 layers 列表完整。
    返回 FixedPointReport 列表, 按层号排序。
    """
    if detector is None:
        detector = FixedPointDetector()

    results = []
    for layer in world.layers:
        fp = detector.compare(layer)
        if fp is not None:
            results.append(fp)
    return results


def find_first_fixed_point(reports: list[FixedPointReport],
                           threshold: float = 0.8) -> FixedPointReport | None:
    """返回链中第一个固定点 (iso_score >= threshold)。"""
    for r in reports:
        if r.is_fixed_point(threshold):
            return r
    return None


def summarize_chain(reports: list[FixedPointReport]) -> str:
    """生成一条可读的链摘要。"""
    if not reports:
        return "(空链)"
    lines = ["整体固定点链分析:", "─" * 50]
    for r in reports:
        lines.append(r.summary())
    lines.append("─" * 50)
    first_fp = find_first_fixed_point(reports)
    if first_fp:
        lines.append(f"→ 首个固定点: L{first_fp.layer} (iso_score={first_fp.iso_score:.4f})")
    else:
        max_iso = max(r.iso_score for r in reports)
        max_layer = max((r for r in reports), key=lambda x: x.iso_score).layer
        lines.append(f"→ 未达固定点阈值, 最高 iso_score=L{max_layer}: {max_iso:.4f}")
    lines.append(f"→ 链深度: {len(reports)} 层")
    return "\n".join(lines)