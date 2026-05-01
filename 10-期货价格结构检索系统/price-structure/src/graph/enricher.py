"""
知识图谱增强器 — StructureEnricher

将 config/products/ 的品种知识注入到价格结构分析结果中。
这是知识图谱与价格结构之间的桥梁。

核心能力：
1. 结构关联实体：当前结构涉及哪些矿山、交易所、变量
2. 传导链激活检测：价格走势是否触发了某条传导链
3. 跨品种联动信号：基于关系网络的品种间信号
4. 叙事增强：用知识图谱的叙事丰富结构的 narrative_context

数据流：
  compile_full() → structures
  + config knowledge → enriched structures
  → 更有信息量的检索和展示
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import json
from pathlib import Path


@dataclass
class RelatedEntity:
    """关联实体"""
    entity_id: str
    name: str
    entity_type: str  # 资源节点/权力机构/变量/共识叙事
    importance: int  # 1-10
    relevance_score: float  # 与当前结构的相关度 0-1
    description: str = ""
    tracking_variables: list[str] = field(default_factory=list)


@dataclass
class ActivatedChain:
    """被激活的传导链"""
    chain_id: str
    chain_name: str
    domain: str
    trigger_event: str
    matched_step: int  # 当前匹配到第几步
    total_steps: int
    activation_confidence: str  # 高/中/低
    reversal_node: str = ""
    reversal_condition: str = ""
    historical_cases: list[dict] = field(default_factory=list)


@dataclass
class CrossProductSignal:
    """跨品种联动信号"""
    source_symbol: str
    target_symbol: str
    relation_type: str
    strength: float
    direction: str
    description: str = ""


@dataclass
class EnrichedStructure:
    """增强后的结构"""
    symbol: str
    zone_center: float
    narrative: str
    # 知识图谱增强
    related_entities: list[RelatedEntity] = field(default_factory=list)
    activated_chains: list[ActivatedChain] = field(default_factory=list)
    cross_product_signals: list[CrossProductSignal] = field(default_factory=list)
    enriched_narrative: str = ""  # 增强后的叙事


class StructureEnricher:
    """
    知识图谱增强器

    从 GraphStore 加载品种知识，为价格结构提供上下文增强。
    """

    def __init__(self, graph_store=None, config_dir: str = "config/products"):
        self.graph_store = graph_store
        self.config_dir = Path(config_dir)
        self._entities_cache: dict[str, list[dict]] = {}
        self._relations_cache: dict[str, list[dict]] = {}
        self._chains_cache: dict[str, list[dict]] = {}
        self._loaded = False

    def _load_config(self) -> None:
        """加载所有品种配置"""
        if self._loaded:
            return

        registry_path = self.config_dir / "registry.yaml"
        if not registry_path.exists():
            return

        import yaml
        with open(registry_path, encoding="utf-8") as f:
            registry = yaml.safe_load(f)

        for prod_key, prod in registry.get("products", {}).items():
            files = prod.get("files", {})

            if "entities" in files:
                path = self.config_dir / files["entities"]
                if path.exists():
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    self._entities_cache[prod_key] = data.get("entities", [])

            if "relations" in files:
                path = self.config_dir / files["relations"]
                if path.exists():
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    self._relations_cache[prod_key] = data.get("relations", [])

            if "chains" in files:
                path = self.config_dir / files["chains"]
                if path.exists():
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    self._chains_cache[prod_key] = data.get("chains", [])

        self._loaded = True

    # ─── 核心接口 ──────────────────────────────────────────

    def enrich(self, structure, symbol: str = "") -> EnrichedStructure:
        """
        增强单个结构。

        Args:
            structure: compile_full() 输出的 Structure 对象
            symbol: 品种代码

        Returns:
            EnrichedStructure
        """
        self._load_config()

        sym = symbol or getattr(structure, "symbol", "") or "unknown"
        zone_center = structure.zone.price_center
        narrative = structure.narrative_context or ""

        enriched = EnrichedStructure(
            symbol=sym,
            zone_center=zone_center,
            narrative=narrative,
        )

        # 1. 关联实体
        enriched.related_entities = self._find_related_entities(structure, sym)

        # 2. 传导链激活
        enriched.activated_chains = self._detect_chain_activation(structure, sym)

        # 3. 跨品种联动
        enriched.cross_product_signals = self._detect_cross_product_signals(structure, sym)

        # 4. 增强叙事
        enriched.enriched_narrative = self._build_enriched_narrative(enriched)

        return enriched

    def enrich_batch(self, structures: list, symbol: str = "") -> list[EnrichedStructure]:
        """批量增强"""
        return [self.enrich(s, symbol) for s in structures]

    # ─── 实体关联 ──────────────────────────────────────────

    def _find_related_entities(self, structure, symbol: str) -> list[RelatedEntity]:
        """找到与当前结构相关的实体"""
        self._load_config()
        related = []

        # 从图谱存储中查找
        if self.graph_store:
            zones = self.graph_store.load_all_zones()
            for z in zones:
                if z.get("product") == symbol or z.get("symbol") == symbol:
                    # 检查价格区间是否与当前结构的 Zone 重叠
                    z_center = z.get("price_center", 0)
                    if z_center > 0 and abs(z_center - structure.zone.price_center) / max(structure.zone.price_center, 1) < 0.1:
                        related.append(RelatedEntity(
                            entity_id=z.get("zone_key", ""),
                            name=z.get("name", z.get("zone_key", "")),
                            entity_type=z.get("node_type", "zone"),
                            importance=z.get("importance", 5),
                            relevance_score=0.8,
                            description=z.get("description", ""),
                        ))

        # 从 config 实体中查找
        entities = self._entities_cache.get(symbol, [])
        entities += self._entities_cache.get("_shared", [])

        for ent in entities:
            relevance = self._compute_entity_relevance(ent, structure)
            if relevance > 0.3:
                related.append(RelatedEntity(
                    entity_id=ent.get("id", ""),
                    name=ent.get("name", ""),
                    entity_type=ent.get("type", ""),
                    importance=ent.get("importance", 5),
                    relevance_score=relevance,
                    description=ent.get("description", ""),
                    tracking_variables=ent.get("trackingVariables", []),
                ))

        # 按相关度排序
        related.sort(key=lambda e: e.relevance_score * e.importance, reverse=True)
        return related[:10]

    def _compute_entity_relevance(self, entity: dict, structure) -> float:
        """计算实体与结构的相关度"""
        score = 0.0
        narrative = structure.narrative_context or ""
        entity_name = entity.get("name", "")
        entity_desc = entity.get("description", "")

        # 叙事关键词匹配
        if narrative:
            keywords = narrative.split()
            for kw in keywords:
                if len(kw) >= 2 and (kw in entity_name or kw in entity_desc):
                    score += 0.3

        # 变量实体：检查是否与 Zone 价格相关
        if entity.get("id", "").startswith("VAR_"):
            var_name = entity.get("name", "")
            if any(kw in var_name for kw in ["铜价", "LME", "库存", "TC/RC"]):
                score += 0.2

        # 地理实体：铜矿相关
        if entity.get("id", "").startswith("GEO_"):
            if "铜" in entity_desc or "矿" in entity_desc:
                score += 0.15

        # 共识叙事：直接匹配
        if entity.get("id", "").startswith("CUL_"):
            if narrative and any(kw in entity_desc for kw in narrative[:10].split()):
                score += 0.4

        return min(1.0, score)

    # ─── 传导链激活 ────────────────────────────────────────

    def _detect_chain_activation(self, structure, symbol: str) -> list[ActivatedChain]:
        """检测价格走势是否触发了传导链"""
        self._load_config()
        activated = []

        chains = self._chains_cache.get(symbol, [])
        chains += self._chains_cache.get("_shared", [])

        motion = structure.motion
        if not motion:
            return activated

        for chain in chains:
            steps = chain.get("steps", [])
            if not steps:
                continue

            # 检查触发事件是否与当前运动态匹配
            trigger = chain.get("triggerEvent", "")
            match_score = self._match_trigger_to_motion(trigger, motion, structure)

            if match_score > 0.3:
                # 确定匹配到第几步
                matched_step = self._determine_chain_step(steps, motion, structure)

                activated.append(ActivatedChain(
                    chain_id=chain.get("id", ""),
                    chain_name=chain.get("name", ""),
                    domain=chain.get("domain", ""),
                    trigger_event=trigger,
                    matched_step=matched_step,
                    total_steps=len(steps),
                    activation_confidence="高" if match_score > 0.7 else "中" if match_score > 0.5 else "低",
                    reversal_node=chain.get("reversalNode", ""),
                    reversal_condition=chain.get("reversalCondition", ""),
                    historical_cases=chain.get("historicalCases", []),
                ))

        activated.sort(key=lambda c: c.matched_step / max(c.total_steps, 1), reverse=True)
        return activated[:5]

    def _match_trigger_to_motion(self, trigger: str, motion, structure) -> float:
        """匹配触发事件与当前运动态"""
        score = 0.0

        # 通量方向匹配
        flux = motion.conservation_flux
        if "下跌" in trigger and flux < -0.3:
            score += 0.4
        elif "上涨" in trigger and flux > 0.3:
            score += 0.4
        elif "库存" in trigger and "去" in trigger and flux > 0.2:
            score += 0.3
        elif "供给" in trigger and ("紧" in trigger or "减" in trigger) and flux < -0.2:
            score += 0.3

        # 阶段匹配
        phase = motion.phase_tendency
        if "突破" in trigger and phase in ("release", "trending"):
            score += 0.3
        elif "蓄势" in trigger and phase in ("accumulation", "compression"):
            score += 0.3

        # 叙事匹配
        narrative = structure.narrative_context or ""
        if narrative and trigger:
            trigger_keywords = set(trigger.replace("，", " ").split())
            narrative_keywords = set(narrative.replace("，", " ").split())
            overlap = trigger_keywords & narrative_keywords
            if overlap:
                score += min(0.3, len(overlap) * 0.1)

        return min(1.0, score)

    def _determine_chain_step(self, steps: list, motion, structure) -> int:
        """确定当前匹配到传导链的第几步"""
        # 简化逻辑：根据通量和阶段推断
        flux = motion.conservation_flux
        phase = motion.phase_tendency

        if phase in ("accumulation", "compression"):
            return 1  # 刚触发
        elif phase in ("confirmation",):
            return min(2, len(steps))
        elif phase in ("release", "trending"):
            return min(3, len(steps))
        elif phase in ("breakdown", "inversion"):
            return len(steps)  # 接近反转
        return 1

    # ─── 跨品种联动 ────────────────────────────────────────

    def _detect_cross_product_signals(self, structure, symbol: str) -> list[CrossProductSignal]:
        """检测跨品种联动信号"""
        self._load_config()
        signals = []

        # 从共享关系中找跨品种连接
        shared_relations = self._relations_cache.get("_shared", [])
        for rel in shared_relations:
            rel_type = rel.get("type", "")
            from_node = rel.get("from", "")
            to_node = rel.get("to", "")

            # 检查是否涉及当前品种
            if symbol in from_node or symbol in to_node:
                # 检查关系类型是否与当前结构相关
                if self._relation_matches_structure(rel, structure):
                    target = to_node if symbol in from_node else from_node
                    signals.append(CrossProductSignal(
                        source_symbol=symbol,
                        target_symbol=target.split(":")[-1] if ":" in target else target,
                        relation_type=rel_type,
                        strength=rel.get("strength", 0.5),
                        direction=rel.get("direction", ""),
                        description=rel.get("description", ""),
                    ))

        return signals[:5]

    def _relation_matches_structure(self, relation: dict, structure) -> bool:
        """检查关系是否与当前结构相关"""
        rel_type = relation.get("type", "")
        narrative = structure.narrative_context or ""

        # 关键词匹配
        keywords = ["供给", "需求", "库存", "价格", "成本", "利润"]
        return any(kw in rel_type or kw in narrative for kw in keywords)

    # ─── 叙事增强 ──────────────────────────────────────────

    def _build_enriched_narrative(self, enriched: EnrichedStructure) -> str:
        """构建增强后的叙事"""
        parts = []

        if enriched.narrative:
            parts.append(enriched.narrative)

        # 添加高重要度实体
        top_entities = [e for e in enriched.related_entities if e.importance >= 8]
        if top_entities:
            entity_names = [e.name for e in top_entities[:3]]
            parts.append(f"相关核心标的：{'、'.join(entity_names)}")

        # 添加激活的传导链
        if enriched.activated_chains:
            chain = enriched.activated_chains[0]
            parts.append(f"传导链激活：{chain.chain_name}（第{chain.matched_step}/{chain.total_steps}步）")
            if chain.reversal_node:
                parts.append(f"反转节点：{chain.reversal_node}")

        # 添加跨品种信号
        if enriched.cross_product_signals:
            sig = enriched.cross_product_signals[0]
            parts.append(f"跨品种联动：{sig.source_symbol} ↔ {sig.target_symbol}（{sig.relation_type}，强度{sig.strength:.0%}）")

        return " | ".join(parts) if parts else enriched.narrative

    # ─── 序列化 ──────────────────────────────────────────

    def to_dict(self, enriched: EnrichedStructure) -> dict:
        """将增强结果转为可序列化字典"""
        return {
            "symbol": enriched.symbol,
            "zone_center": enriched.zone_center,
            "narrative": enriched.narrative,
            "enriched_narrative": enriched.enriched_narrative,
            "related_entities": [
                {
                    "id": e.entity_id,
                    "name": e.name,
                    "type": e.entity_type,
                    "importance": e.importance,
                    "relevance": round(e.relevance_score, 3),
                }
                for e in enriched.related_entities
            ],
            "activated_chains": [
                {
                    "id": c.chain_id,
                    "name": c.chain_name,
                    "step": c.matched_step,
                    "total": c.total_steps,
                    "confidence": c.activation_confidence,
                    "reversal": c.reversal_node,
                }
                for c in enriched.activated_chains
            ],
            "cross_product_signals": [
                {
                    "source": s.source_symbol,
                    "target": s.target_symbol,
                    "type": s.relation_type,
                    "strength": s.strength,
                }
                for s in enriched.cross_product_signals
            ],
        }
