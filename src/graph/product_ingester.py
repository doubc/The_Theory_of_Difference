"""
多品种知识图谱导入器 — ProductKnowledgeIngester

从 config/products/ 读取品种配置，注入 GraphStore。
支持：增量更新、全量刷新、品种命名空间隔离。

用法：
    from src.graph.store import GraphStore
    from src.graph.product_ingester import ProductKnowledgeIngester

    store = GraphStore("data/graph")
    ingester = ProductKnowledgeIngester(store)
    stats = ingester.ingest_all_active_products()
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.graph.store import GraphStore


@dataclass
class IngestStats:
    """单品种导入统计"""
    product: str = ""
    entities: int = 0
    relations: int = 0
    chains: int = 0
    polarity_rules: int = 0
    pricing_models: int = 0
    edges: int = 0
    skipped: bool = False
    reason: str = ""


class ProductKnowledgeIngester:
    """
    多品种知识图谱导入器。

    - 读取 config/products/registry.yaml 获取品种清单
    - 按品种加载 JSON 配置
    - 写入 GraphStore（节点 + 边）
    - 支持品种命名空间前缀（cu:GEO_066）
    - 支持增量更新（通过文件 hash 判断是否需要刷新）
    """

    def __init__(
        self,
        graph_store: GraphStore,
        registry_path: str = "config/products/registry.yaml",
        products_dir: str = "config/products",
    ):
        self.store = graph_store
        self.registry_path = Path(registry_path)
        self.products_dir = Path(products_dir)
        self.registry: dict[str, Any] = {}
        self._hash_file: Path | None = None
        self._load_registry()

    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Registry not found: {self.registry_path}")
        with open(self.registry_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.registry = data.get("products", {})
        self._hash_file = self.store.base / "index" / "product_hashes.json"

    # ─── 公开接口 ──────────────────────────────────────────

    def ingest_all_active_products(self, force: bool = False) -> dict[str, IngestStats]:
        """批量导入所有 active 状态品种"""
        results = {}
        for key, prod in self.registry.items():
            if prod.get("status") == "deprecated":
                results[key] = IngestStats(product=key, skipped=True, reason="deprecated")
                continue
            results[key] = self.ingest_product(key, force=force)
        return results

    def ingest_product(self, product_key: str, force: bool = False) -> IngestStats:
        """导入单个品种的全部知识"""
        if product_key not in self.registry:
            return IngestStats(product=product_key, skipped=True, reason="not_in_registry")

        prod = self.registry[product_key]
        if prod.get("status") == "deprecated":
            return IngestStats(product=product_key, skipped=True, reason="deprecated")

        if not force and not self._needs_update(product_key):
            return IngestStats(product=product_key, skipped=True, reason="no_change")

        stats = IngestStats(product=product_key)

        # 依次导入各模块
        files = prod.get("files", {})

        if "entities" in files:
            stats.entities = self._ingest_entities(product_key, files["entities"])

        if "relations" in files:
            stats.relations = self._ingest_relations(product_key, files["relations"])

        if "chains" in files:
            chain_count, edge_count = self._ingest_chains(product_key, files["chains"])
            stats.chains = chain_count
            stats.edges += edge_count

        if "polarity" in files:
            stats.polarity_rules = self._ingest_polarity(product_key, files["polarity"])

        if "pricing_models" in files:
            stats.pricing_models = self._ingest_pricing_models(product_key, files["pricing_models"])

        # 更新 hash
        self._save_hashes(product_key, files)

        return stats

    def reload_product(self, product_key: str) -> IngestStats:
        """强制重新导入（先清理旧数据再全量写入）"""
        self._clear_product(product_key)
        return self.ingest_product(product_key, force=True)

    # ─── 内部：导入各模块 ──────────────────────────────────

    def _ingest_entities(self, prod_key: str, rel_path: str) -> int:
        """导入实体 → Zone/Structure/Narrative 节点"""
        data = self._load_product_file(rel_path)
        entities = data.get("entities", [])
        count = 0

        for ent in entities:
            eid = ent.get("id", "")
            prefixed_id = f"{prod_key}:{eid}"
            ent_type = ent.get("type", "")

            if eid.startswith("GEO_"):
                # 地理节点 → Zone
                self.store.append_zone({
                    "zone_key": prefixed_id,
                    "name": ent.get("name", ""),
                    "node_type": "geo_node",
                    "product": prod_key,
                    "entity_type": ent_type,
                    "importance": ent.get("importance", 5),
                    "description": ent.get("description", ""),
                    "controlled_by": ent.get("controlledBy", []),
                    "vulnerabilities": ent.get("vulnerabilities", []),
                    "tracking_variables": ent.get("trackingVariables", []),
                })
            elif eid.startswith(("POW_", "RUL_")):
                # 权力机构/规则 → Structure
                self.store.append_structure({
                    "struct_id": prefixed_id,
                    "node_type": "authority" if eid.startswith("POW_") else "rule",
                    "product": prod_key,
                    "name": ent.get("name", ""),
                    "entity_type": ent_type,
                    "importance": ent.get("importance", 5),
                    "description": ent.get("description", ""),
                    "jurisdiction": ent.get("jurisdiction", ""),
                    "tracking_variables": ent.get("trackingVariables", []),
                })
            elif eid.startswith("CUL_"):
                # 共识叙事 → Narrative
                self.store.append_narrative({
                    "narrative_id": prefixed_id,
                    "text": ent.get("name", ""),
                    "type": "consensus_narrative",
                    "product": prod_key,
                    "entity_type": ent_type,
                    "importance": ent.get("importance", 5),
                    "description": ent.get("description", ""),
                })
            elif eid.startswith("VAR_"):
                # 变量 → Structure (variable type)
                self.store.append_structure({
                    "struct_id": prefixed_id,
                    "node_type": "variable",
                    "product": prod_key,
                    "name": ent.get("name", ""),
                    "entity_type": ent_type,
                    "importance": ent.get("importance", 5),
                    "current_value": ent.get("currentValue", ""),
                    "historical_range": ent.get("historicalRange", {}),
                    "recent_range": ent.get("recentRange", {}),
                    "tracking_variables": ent.get("trackingVariables", []),
                })
            else:
                # 其他 → Structure
                self.store.append_structure({
                    "struct_id": prefixed_id,
                    "node_type": "entity",
                    "product": prod_key,
                    "name": ent.get("name", ""),
                    "entity_type": ent_type,
                    "importance": ent.get("importance", 5),
                    "description": ent.get("description", ""),
                })

            count += 1

        return count

    def _ingest_relations(self, prod_key: str, rel_path: str) -> int:
        """导入关系 → Edge"""
        data = self._load_product_file(rel_path)
        relations = data.get("relations", [])
        count = 0

        for rel in relations:
            rid = rel.get("id", "")
            from_node = rel.get("from", "")
            to_node = rel.get("to", "")

            # 跨品种关系：如果 from/to 已包含品种前缀则保留，否则加当前品种前缀
            if ":" not in from_node:
                from_node = f"{prod_key}:{from_node}"
            if ":" not in to_node:
                to_node = f"{prod_key}:{to_node}"

            self.store.append_edge({
                "source": from_node,
                "target": to_node,
                "edge_type": rel.get("type", "relation"),
                "relation_id": f"{prod_key}:{rid}",
                "product": prod_key,
                "strength": rel.get("strength", 0.5),
                "direction": rel.get("direction", ""),
                "ground_base": rel.get("groundBase", ""),
                "stability": rel.get("stability", ""),
                "description": rel.get("description", ""),
                "constraint": rel.get("constraint", ""),
                "lag": rel.get("lag", ""),
            })
            count += 1

        return count

    def _ingest_chains(self, prod_key: str, rel_path: str) -> tuple[int, int]:
        """导入传导链 → Narrative 节点 + 多条边"""
        data = self._load_product_file(rel_path)
        chains = data.get("chains", [])
        chain_count = 0
        edge_count = 0

        for chain in chains:
            cid = chain.get("id", "")
            prefixed_cid = f"{prod_key}:{cid}"

            # 传导链本身作为 Narrative 节点
            self.store.append_narrative({
                "narrative_id": prefixed_cid,
                "text": chain.get("name", ""),
                "type": "conduction_chain",
                "product": prod_key,
                "domain": chain.get("domain", ""),
                "trigger_event": chain.get("triggerEvent", ""),
                "reversal_node": chain.get("reversalNode", ""),
                "reversal_condition": chain.get("reversalCondition", ""),
                "polarity_threshold": chain.get("polarityTensionThreshold", 0),
                "reversibility": chain.get("reversibility", 0),
                "tail_probability": chain.get("tailProbability", 0),
            })

            # 传导链的每一步作为边
            for step in chain.get("steps", []):
                from_node = step.get("from", "")
                to_node = step.get("to", "")
                if ":" not in from_node:
                    from_node = f"{prod_key}:{from_node}"
                if ":" not in to_node:
                    to_node = f"{prod_key}:{to_node}"

                self.store.append_edge({
                    "source": from_node,
                    "target": to_node,
                    "edge_type": "conduction_step",
                    "chain_id": prefixed_cid,
                    "product": prod_key,
                    "seq": step.get("seq", 0),
                    "confidence": step.get("confidence", "中"),
                    "lag": step.get("lag", ""),
                    "mechanism": step.get("mechanism", ""),
                })
                edge_count += 1

            chain_count += 1

        return chain_count, edge_count

    def _ingest_polarity(self, prod_key: str, rel_path: str) -> int:
        """导入极值档案 → Structure (polarity_rule 类型)"""
        data = self._load_product_file(rel_path)
        entries = data.get("entries", {})
        count = 0

        for var_name, var_info in entries.items():
            rule_id = f"{prod_key}:polarity:{var_name}"
            self.store.append_structure({
                "struct_id": rule_id,
                "node_type": "polarity_rule",
                "product": prod_key,
                "variable": var_name,
                "historical_min": var_info.get("historicalMin"),
                "historical_max": var_info.get("historicalMax"),
                "recent_min": var_info.get("recentMin"),
                "recent_max": var_info.get("recentMax"),
                "reversal_signals": var_info.get("reversalSignalPatterns", []),
            })
            count += 1

        return count

    def _ingest_pricing_models(self, prod_key: str, rel_path: str) -> int:
        """导入定价模型 → Narrative 节点"""
        data = self._load_product_file(rel_path)
        models = data.get("models", [])
        count = 0

        for model in models:
            mid = model.get("id", "")
            prefixed_mid = f"{prod_key}:{mid}"
            self.store.append_narrative({
                "narrative_id": prefixed_mid,
                "text": model.get("name", ""),
                "type": "pricing_model",
                "product": prod_key,
                "domain": model.get("domain", ""),
                "formula": model.get("formula", ""),
                "dominant_phase": model.get("dominantPhase", ""),
                "variables": model.get("variables", []),
                "linked_entities": model.get("linkToEntities", []),
                "linked_relations": model.get("linkToRelations", []),
                "linked_chains": model.get("linkToConductionChains", []),
            })
            count += 1

        return count

    # ─── 内部：文件操作 ──────────────────────────────────────

    def _load_product_file(self, rel_path: str) -> dict:
        """加载品种配置文件"""
        full_path = self.products_dir / rel_path
        if not full_path.exists():
            return {}
        with open(full_path, encoding="utf-8") as f:
            return json.load(f)

    def _file_hash(self, filepath: Path) -> str:
        if not filepath.exists():
            return ""
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def _load_stored_hashes(self) -> dict[str, str]:
        if not self._hash_file or not self._hash_file.exists():
            return {}
        with open(self._hash_file, encoding="utf-8") as f:
            return json.load(f)

    def _save_hashes(self, prod_key: str, files: dict[str, str]) -> None:
        """保存该品种各文件的 hash"""
        stored = self._load_stored_hashes()
        for file_type, rel_path in files.items():
            full_path = self.products_dir / rel_path
            key = f"{prod_key}:{file_type}"
            stored[key] = self._file_hash(full_path)
        if self._hash_file:
            self._hash_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._hash_file, "w", encoding="utf-8") as f:
                json.dump(stored, f, ensure_ascii=False, indent=2)

    def _needs_update(self, prod_key: str) -> bool:
        """检查该品种配置文件是否有更新"""
        prod = self.registry[prod_key]
        stored = self._load_stored_hashes()
        files = prod.get("files", {})

        for file_type, rel_path in files.items():
            full_path = self.products_dir / rel_path
            key = f"{prod_key}:{file_type}"
            current_hash = self._file_hash(full_path)
            if key not in stored or stored[key] != current_hash:
                return True

        return False

    def _clear_product(self, prod_key: str) -> None:
        """清理该品种的所有旧数据（全量刷新前调用）"""
        # 重写所有 JSONL 文件，过滤掉该品种的数据
        for file_attr in ["structures_file", "zones_file", "narratives_file", "edges_file"]:
            fpath: Path = getattr(self.store, file_attr)
            if not fpath.exists():
                continue
            lines = fpath.read_text(encoding="utf-8").splitlines()
            filtered = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("product") != prod_key:
                        filtered.append(line)
                except json.JSONDecodeError:
                    filtered.append(line)
            fpath.write_text("\n".join(filtered) + "\n" if filtered else "", encoding="utf-8")

        # 清理 hash 记录
        stored = self._load_stored_hashes()
        keys_to_remove = [k for k in stored if k.startswith(f"{prod_key}:")]
        for k in keys_to_remove:
            del stored[k]
        if self._hash_file:
            with open(self._hash_file, "w", encoding="utf-8") as f:
                json.dump(stored, f, ensure_ascii=False, indent=2)
