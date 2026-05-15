"""
知识图谱上下文嵌入层

目标：
1. 不替代原有 geometric / relational / motion / family 相似度；
2. 只提供 graph_context_bonus，用于检索结果重排；
3. 使用已有 GraphStore 的 JSONL 数据，不引入新数据库；
4. 让"同 Zone 演化链、同品种结构网络、叙事递归、差异转移"参与检索。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.models import Structure
from src.graph.store import GraphStore


@dataclass
class GraphContext:
    """
    一个结构在知识图谱里的上下文摘要。
    这些字段不是市场预测信号，而是结构关系语义。
    """
    symbol: str
    zone_key: str
    same_zone_count: int = 0
    same_symbol_count: int = 0
    evolution_in_count: int = 0
    evolution_out_count: int = 0
    narrative_count: int = 0
    transfer_out_count: int = 0
    label_count: int = 0

    def to_vector(self) -> list[float]:
        """
        转成一个稳定的小向量。
        用 log 压缩，避免历史越多的品种天然占优。
        """
        import math

        return [
            math.log1p(self.same_zone_count),
            math.log1p(self.same_symbol_count),
            math.log1p(self.evolution_in_count),
            math.log1p(self.evolution_out_count),
            math.log1p(self.narrative_count),
            math.log1p(self.transfer_out_count),
            math.log1p(self.label_count),
        ]


def _safe_symbol(s: Structure) -> str:
    return s.symbol or "unknown"


def _zone_key(s: Structure) -> str:
    symbol = _safe_symbol(s)
    if not s.zone:
        return f"{symbol}:unknown"
    return f"{symbol}:{s.zone.price_center:.0f}"


def _label(s: Structure) -> str:
    return s.label or ""


class GraphEmbedder:
    """
    从 GraphStore 读取知识图谱上下文，并计算结构之间的图谱相似度。
    """

    def __init__(self, store: GraphStore):
        self.store = store
        self._structures: list[dict[str, Any]] | None = None
        self._edges: list[dict[str, Any]] | None = None
        self._narratives: list[dict[str, Any]] | None = None

    @property
    def structures(self) -> list[dict[str, Any]]:
        if self._structures is None:
            self._structures = self.store.load_all_structures()
        return self._structures

    @property
    def edges(self) -> list[dict[str, Any]]:
        if self._edges is None:
            self._edges = self.store.load_all_edges()
        return self._edges

    @property
    def narratives(self) -> list[dict[str, Any]]:
        if self._narratives is None:
            self._narratives = self.store.load_all_narratives()
        return self._narratives

    def context_from_structure(self, s: Structure) -> GraphContext:
        """
        给当前 Structure 构造图谱上下文。
        当前结构可能还没入库，所以用 symbol / zone_key / label 去图谱里找邻域。
        """
        symbol = _safe_symbol(s)
        zone_key = _zone_key(s)
        label = _label(s)

        same_zone = [
            r for r in self.structures
            if r.get("zone_key") == zone_key
        ]

        same_symbol = [
            r for r in self.structures
            if r.get("symbol") == symbol
        ]

        same_label = [
            r for r in self.structures
            if label and r.get("label") == label
        ]

        related_struct_ids = {
            f"struct:{r.get('struct_id')}"
            for r in same_zone
            if r.get("struct_id")
        }

        evolution_in = 0
        evolution_out = 0
        transfer_out = 0

        for e in self.edges:
            et = e.get("edge_type")
            src = e.get("source")
            tgt = e.get("target")

            if et == "evolves_to":
                if tgt in related_struct_ids:
                    evolution_in += 1
                if src in related_struct_ids:
                    evolution_out += 1

            if et == "transfer_to" and src in related_struct_ids:
                transfer_out += 1

        narrative_count = sum(
            1 for n in self.narratives
            if n.get("zone_key") == zone_key
        )

        return GraphContext(
            symbol=symbol,
            zone_key=zone_key,
            same_zone_count=len(same_zone),
            same_symbol_count=len(same_symbol),
            evolution_in_count=evolution_in,
            evolution_out_count=evolution_out,
            narrative_count=narrative_count,
            transfer_out_count=transfer_out,
            label_count=len(same_label),
        )

    def context_from_sample_dict(self, sample_structure: dict, symbol: str = "", label: str = "") -> GraphContext:
        """
        给历史样本构造图谱上下文。
        Sample.structure 是 dict，不一定能完整 rebuild 成 Structure，所以单独处理。
        """
        zd = sample_structure.get("zone", {}) or {}
        sym = symbol or sample_structure.get("symbol") or "unknown"
        center = zd.get("price_center")

        if center is None:
            zone_key = f"{sym}:unknown"
        else:
            zone_key = f"{sym}:{center:.0f}"

        same_zone = [
            r for r in self.structures
            if r.get("zone_key") == zone_key
        ]

        same_symbol = [
            r for r in self.structures
            if r.get("symbol") == sym
        ]

        same_label = [
            r for r in self.structures
            if label and r.get("label") == label
        ]

        related_struct_ids = {
            f"struct:{r.get('struct_id')}"
            for r in same_zone
            if r.get("struct_id")
        }

        evolution_in = 0
        evolution_out = 0
        transfer_out = 0

        for e in self.edges:
            et = e.get("edge_type")
            src = e.get("source")
            tgt = e.get("target")

            if et == "evolves_to":
                if tgt in related_struct_ids:
                    evolution_in += 1
                if src in related_struct_ids:
                    evolution_out += 1

            if et == "transfer_to" and src in related_struct_ids:
                transfer_out += 1

        narrative_count = sum(
            1 for n in self.narratives
            if n.get("zone_key") == zone_key
        )

        return GraphContext(
            symbol=sym,
            zone_key=zone_key,
            same_zone_count=len(same_zone),
            same_symbol_count=len(same_symbol),
            evolution_in_count=evolution_in,
            evolution_out_count=evolution_out,
            narrative_count=narrative_count,
            transfer_out_count=transfer_out,
            label_count=len(same_label),
        )

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        import math

        if not a or not b or len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))

        if na == 0 or nb == 0:
            return 0.0

        return dot / (na * nb)

    def graph_similarity(self, query: Structure, sample_structure: dict, symbol: str = "", label: str = "") -> float:
        """
        图谱上下文相似度。
        返回 [0, 1]。
        """
        q_ctx = self.context_from_structure(query)
        s_ctx = self.context_from_sample_dict(sample_structure, symbol=symbol, label=label)

        base = self.cosine(q_ctx.to_vector(), s_ctx.to_vector())

        # 强规则：同 Zone 是强关系，但不能直接给满分，避免过拟合。
        same_zone_bonus = 0.15 if q_ctx.zone_key == s_ctx.zone_key else 0.0

        # 同品种是弱关系，因为跨品种结构同态仍然重要。
        same_symbol_bonus = 0.05 if q_ctx.symbol == s_ctx.symbol else 0.0

        return min(1.0, base + same_zone_bonus + same_symbol_bonus)
