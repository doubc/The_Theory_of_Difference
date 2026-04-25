"""
知识图谱模块 — V1.6 P2

将结构、Zone、叙事、规则之间的关系显式化为可遍历的图网络。
不改变现有数据模型，而是在其上层构建关系图。

核心能力：
1. 结构演化链：Structure A → Structure B（同一 Zone 的跨时间演化）
2. 叙事递归链：Narrative → Narrative（叙事如何随时间变化）
3. 差异转移路径：Structure → Structure（差异从一个结构转移到另一个）
4. 反身性闭环：Rule → Structure → (市场变化) → Structure' → Rule 失效
5. Zone 共享网络：多个结构围绕同一 Zone 组织

存储：NetworkX DiGraph + JSONL 持久化
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import json

import networkx as nx
from src.graph.store import GraphStore


# ─── 节点类型 ──────────────────────────────────────────────

class NodeType(Enum):
    STRUCTURE = "structure"
    ZONE = "zone"
    NARRATIVE = "narrative"
    RULE = "rule"
    SYMBOL = "symbol"


# ─── 边类型 ────────────────────────────────────────────────

class EdgeType(Enum):
    # 结构演化
    EVOLVES_TO = "evolves_to"               # S_t → S_{t+1}
    BELONGS_TO = "belongs_to"               # Structure → Zone
    OF_SYMBOL = "of_symbol"                 # Structure → Symbol

    # 叙事递归
    HAS_NARRATIVE = "has_narrative"          # Structure → Narrative
    NARRATIVE_EVOLVES = "narrative_evolves"  # Narrative → Narrative

    # 差异转移
    TRANSFER_TO = "transfer_to"              # Structure → Structure（差异沿低阻通道转移）

    # 反身性闭环
    IDENTIFIED_BY = "identified_by"          # Structure → Rule
    APPLIED_ON = "applied_on"               # Rule → Structure（反向）
    INVALIDATES = "invalidates"             # Structure → Rule（结构变化导致规则失效）

    # Zone 关系
    ADJACENT_ZONE = "adjacent_zone"          # Zone → Zone
    SHARES_ZONE = "shares_zone"             # Structure → Structure（共享同一 Zone）


# ─── 图谱 ─────────────────────────────────────────────────

@dataclass
class StructureGraph:
    """
    价格结构知识图谱

    以 NetworkX DiGraph 为底层，将结构间的关系显式化。
    支持路径查询、演化追踪、叙事链分析。
    """
    G: nx.DiGraph = field(default_factory=nx.DiGraph)
    _node_counter: int = field(default_factory=lambda: 0, init=False)

    def _next_id(self) -> int:
        self._node_counter += 1
        return self._node_counter

    # ─── 添加节点 ──────────────────────────────────────────

    def add_structure_node(self, structure_id: str, **attrs) -> str:
        """添加结构节点"""
        node_id = f"struct:{structure_id}"
        self.G.add_node(node_id, node_type=NodeType.STRUCTURE.value, **attrs)
        return node_id

    def add_zone_node(self, zone_id: str, **attrs) -> str:
        """添加 Zone 节点"""
        node_id = f"zone:{zone_id}"
        self.G.add_node(node_id, node_type=NodeType.ZONE.value, **attrs)
        return node_id

    def add_narrative_node(self, narrative_text: str, timestamp: str = "", **attrs) -> str:
        """添加叙事节点"""
        nid = f"narrative:{self._next_id()}"
        self.G.add_node(nid, node_type=NodeType.NARRATIVE.value,
                        text=narrative_text, timestamp=timestamp, **attrs)
        return nid

    def add_rule_node(self, rule_name: str, **attrs) -> str:
        """添加规则节点"""
        node_id = f"rule:{rule_name}"
        self.G.add_node(node_id, node_type=NodeType.RULE.value, **attrs)
        return node_id

    def add_symbol_node(self, symbol: str, **attrs) -> str:
        """添加品种节点"""
        node_id = f"symbol:{symbol}"
        self.G.add_node(node_id, node_type=NodeType.SYMBOL.value, **attrs)
        return node_id

    # ─── 添加边 ────────────────────────────────────────────

    def add_edge(self, source: str, target: str, edge_type: EdgeType, **attrs) -> None:
        """添加关系边"""
        self.G.add_edge(source, target, edge_type=edge_type.value, **attrs)

    def link_structure_zone(self, struct_node: str, zone_node: str) -> None:
        """结构 → Zone 归属"""
        self.add_edge(struct_node, zone_node, EdgeType.BELONGS_TO)

    def link_structure_symbol(self, struct_node: str, symbol_node: str) -> None:
        """结构 → 品种"""
        self.add_edge(struct_node, symbol_node, EdgeType.OF_SYMBOL)

    def link_evolution(self, old_struct: str, new_struct: str, **attrs) -> None:
        """结构演化链：旧 → 新"""
        self.add_edge(old_struct, new_struct, EdgeType.EVOLVES_TO, **attrs)

    def link_transfer(self, source_struct: str, target_struct: str,
                      channel: str = "", strength: float = 0.0) -> None:
        """差异转移路径"""
        self.add_edge(source_struct, target_struct, EdgeType.TRANSFER_TO,
                      channel=channel, strength=strength)

    def link_narrative_chain(self, struct_node: str, narrative_node: str,
                             prev_narrative: str | None = None) -> None:
        """结构 → 叙事；叙事 → 叙事链"""
        self.add_edge(struct_node, narrative_node, EdgeType.HAS_NARRATIVE)
        if prev_narrative:
            self.add_edge(prev_narrative, narrative_node, EdgeType.NARRATIVE_EVOLVES)

    def link_rule_identification(self, struct_node: str, rule_node: str) -> None:
        """结构被规则识别"""
        self.add_edge(struct_node, rule_node, EdgeType.IDENTIFIED_BY)
        self.add_edge(rule_node, struct_node, EdgeType.APPLIED_ON)

    def link_rule_invalidation(self, struct_node: str, rule_node: str, **attrs) -> None:
        """结构变化导致规则失效（反身性核心边）"""
        self.add_edge(struct_node, rule_node, EdgeType.INVALIDATES, **attrs)

    def link_shared_zone(self, struct1: str, struct2: str) -> None:
        """两个结构共享同一 Zone"""
        self.add_edge(struct1, struct2, EdgeType.SHARES_ZONE)

    def link_adjacent_zones(self, zone1: str, zone2: str, distance: float = 0.0) -> None:
        """两个 Zone 空间相邻"""
        self.add_edge(zone1, zone2, EdgeType.ADJACENT_ZONE, distance=distance)
        self.add_edge(zone2, zone1, EdgeType.ADJACENT_ZONE, distance=distance)

    # ─── 查询 ──────────────────────────────────────────────

    def get_structure_evolution_chain(self, struct_node: str) -> list[str]:
        """获取一个结构的完整演化链"""
        chain = [struct_node]
        current = struct_node
        while True:
            successors = [
                n for n in self.G.successors(current)
                if self.G[current][n].get("edge_type") == EdgeType.EVOLVES_TO.value
            ]
            if not successors:
                break
            current = successors[0]
            chain.append(current)
        return chain

    def get_transfer_paths(self, struct_node: str) -> list[list[str]]:
        """获取差异转移的所有路径"""
        paths = []
        visited = set()

        def _dfs(node, path):
            if node in visited:
                return
            visited.add(node)
            successors = [
                n for n in self.G.successors(node)
                if self.G[node][n].get("edge_type") == EdgeType.TRANSFER_TO.value
            ]
            if not successors:
                if len(path) > 1:
                    paths.append(list(path))
                return
            for s in successors:
                path.append(s)
                _dfs(s, path)
                path.pop()

        _dfs(struct_node, [struct_node])
        return paths

    def get_narrative_chain(self, struct_node: str) -> list[dict]:
        """获取一个结构的叙事递归链"""
        # 找到该结构关联的所有叙事节点
        narrative_nodes = [
            n for n in self.G.successors(struct_node)
            if self.G[struct_node][n].get("edge_type") == EdgeType.HAS_NARRATIVE.value
        ]
        if not narrative_nodes:
            return []

        # 从最早的叙事开始，沿 narrative_evolves 边追踪
        result = []
        for start in narrative_nodes:
            chain = [start]
            current = start
            while True:
                successors = [
                    n for n in self.G.successors(current)
                    if self.G[current][n].get("edge_type") == EdgeType.NARRATIVE_EVOLVES.value
                ]
                if not successors:
                    break
                current = successors[0]
                chain.append(current)
            for n in chain:
                result.append({
                    "node": n,
                    "text": self.G.nodes[n].get("text", ""),
                    "timestamp": self.G.nodes[n].get("timestamp", ""),
                })

        return result

    def get_reflexivity_loops(self) -> list[dict]:
        """
        检测反身性闭环：
        Rule → identifies → Structure → (evolves_to) → Structure' → invalidates → Rule
        """
        loops = []
        for node in self.G.nodes:
            if self.G.nodes[node].get("node_type") != NodeType.RULE.value:
                continue
            # 找规则匹配的结构
            matched_structs = [
                n for n in self.G.successors(node)
                if self.G[node][n].get("edge_type") == EdgeType.APPLIED_ON.value
            ]
            for ms in matched_structs:
                # 沿演化链追踪
                chain = self.get_structure_evolution_chain(ms)
                # 检查链上是否有节点使规则失效
                for s in chain[1:]:  # 跳过自身
                    invalidations = [
                        n for n in self.G.successors(s)
                        if self.G[s][n].get("edge_type") == EdgeType.INVALIDATES.value
                        and n == node
                    ]
                    if invalidations:
                        loops.append({
                            "rule": node,
                            "matched_structure": ms,
                            "invalidating_structure": s,
                            "evolution_length": chain.index(s) - chain.index(ms),
                        })
        return loops

    def get_zone_network(self) -> dict:
        """获取 Zone 之间的空间关系网络"""
        zones = [n for n in self.G.nodes
                 if self.G.nodes[n].get("node_type") == NodeType.ZONE.value]
        network = {}
        for z in zones:
            neighbors = [
                n for n in self.G.neighbors(z)
                if self.G.nodes[n].get("node_type") == NodeType.ZONE.value
            ]
            structures = [
                n for n in self.G.predecessors(z)
                if self.G.nodes[n].get("node_type") == NodeType.STRUCTURE.value
            ]
            network[z] = {
                "adjacent_zones": neighbors,
                "structures": structures,
                "center": self.G.nodes[z].get("price_center", 0),
            }
        return network

    def query_structures_by_narrative(self, keyword: str) -> list[str]:
        """通过叙事关键词检索相关结构"""
        matching = []
        for node in self.G.nodes:
            if self.G.nodes[node].get("node_type") == NodeType.NARRATIVE.value:
                text = self.G.nodes[node].get("text", "")
                if keyword in text:
                    # 沿 HAS_NARRATIVE 反向找结构
                    for pred in self.G.predecessors(node):
                        if self.G[pred][node].get("edge_type") == EdgeType.HAS_NARRATIVE.value:
                            matching.append(pred)
        return list(set(matching))

    # ─── 从编译结果构建 ────────────────────────────────────

    @classmethod
    def from_structures(
        cls,
        structures: list,
        prev_graph: StructureGraph | None = None,
    ) -> StructureGraph:
        """
        从编译结果构建知识图谱。

        Args:
            structures: compile_full() 输出的 Structure 列表
            prev_graph: 前一次编译的图谱（用于构建演化链和叙事递归）
        """
        graph = cls()
        prev_struct_nodes: dict[str, str] = {}  # zone_key → 前次图谱中的 node_id

        # 如果有前次图谱，提取前次结构节点
        if prev_graph:
            for node in prev_graph.G.nodes:
                if prev_graph.G.nodes[node].get("node_type") == NodeType.STRUCTURE.value:
                    zk = prev_graph.G.nodes[node].get("zone_key", "")
                    if zk:
                        prev_struct_nodes[zk] = node

        current_struct_nodes: dict[str, str] = {}

        for i, st in enumerate(structures):
            # 生成结构 ID
            symbol = st.symbol or "unknown"
            zone_key = f"{symbol}:{st.zone.price_center:.0f}"
            struct_id = f"{symbol}_S{i}_{st.t_start.strftime('%Y%m%d') if st.t_start else 'nodate'}"

            # 添加结构节点
            s_attrs = {
                "zone_key": zone_key,
                "zone_center": st.zone.price_center,
                "cycle_count": st.cycle_count,
                "avg_speed_ratio": st.avg_speed_ratio,
                "avg_time_ratio": st.avg_time_ratio,
                "narrative": st.narrative_context,
                "contrast_type": st.zone.context_contrast.value,
                "typicality": st.typicality,
                "label": st.label or "",
            }
            if st.motion:
                s_attrs["phase_tendency"] = st.motion.phase_tendency
                s_attrs["movement_type"] = st.motion.movement_type.value if hasattr(st.motion, 'movement_type') else ""
                s_attrs["conservation_flux"] = st.motion.conservation_flux
                s_attrs["stable_distance"] = st.motion.stable_distance
            if st.projection:
                s_attrs["compression_level"] = st.projection.compression_level

            s_node = graph.add_structure_node(struct_id, **s_attrs)
            current_struct_nodes[zone_key] = s_node

            # 添加 Zone 节点
            zone_id = f"{symbol}_{st.zone.price_center:.0f}"
            z_node = graph.add_zone_node(zone_id,
                                          price_center=st.zone.price_center,
                                          bandwidth=st.zone.bandwidth,
                                          strength=st.zone.strength,
                                          contrast_type=st.zone.context_contrast.value)
            graph.link_structure_zone(s_node, z_node)

            # 添加品种节点
            sym_node = graph.add_symbol_node(symbol)
            graph.link_structure_symbol(s_node, sym_node)

            # 添加叙事节点
            if st.narrative_context:
                ts = st.t_start.strftime("%Y-%m-%d") if st.t_start else ""
                n_node = graph.add_narrative_node(st.narrative_context, timestamp=ts)
                graph.link_narrative_chain(s_node, n_node)

                # 如果前次图谱中同一 Zone 有旧叙事，建立叙事递归链
                if prev_graph and zone_key in prev_struct_nodes:
                    old_s_node = prev_struct_nodes[zone_key]
                    old_narratives = [
                        n for n in prev_graph.G.successors(old_s_node)
                        if prev_graph.G[old_s_node][n].get("edge_type") == EdgeType.HAS_NARRATIVE.value
                    ]
                    if old_narratives:
                        # 复制旧叙事节点到新图谱
                        for old_n in old_narratives:
                            old_text = prev_graph.G.nodes[old_n].get("text", "")
                            old_ts = prev_graph.G.nodes[old_n].get("timestamp", "")
                            new_old_n = graph.add_narrative_node(old_text, timestamp=old_ts)
                            graph.link_narrative_chain(s_node, new_old_n)
                            # 建立叙事演化边
                            if old_text != st.narrative_context:
                                graph.add_edge(new_old_n, n_node, EdgeType.NARRATIVE_EVOLVES)

        # 构建演化链和共享 Zone 关系
        for zone_key, s_node in current_struct_nodes.items():
            if zone_key in prev_struct_nodes and prev_graph:
                old_s = prev_struct_nodes[zone_key]
                # 复制旧节点属性到新图谱（用于演化链）
                old_attrs = dict(prev_graph.G.nodes[old_s])
                old_reconstructed = graph.add_structure_node(
                    f"prev_{old_s}", **old_attrs
                )
                graph.link_evolution(old_reconstructed, s_node)

        # 同一 Zone 的结构互相链接
        zone_to_structs: dict[str, list[str]] = {}
        for node in graph.G.nodes:
            if graph.G.nodes[node].get("node_type") == NodeType.STRUCTURE.value:
                zk = graph.G.nodes[node].get("zone_key", "")
                if zk:
                    zone_to_structs.setdefault(zk, []).append(node)

        for zk, nodes in zone_to_structs.items():
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    graph.link_shared_zone(nodes[i], nodes[j])

        return graph

    # ─── 持久化（GraphStore JSONL）──────────────────────────

    def save_to_store(self, store: GraphStore) -> dict:
        """
        将内存图谱增量写入 JSONL 存储。
        自动处理去重（Zone 不重复、边不重复）。
        """
        records_s = []
        records_z = []
        records_n = []
        records_e = []

        for node in self.G.nodes:
            attrs = dict(self.G.nodes[node])
            nt = attrs.get("node_type", "")

            if nt == NodeType.STRUCTURE.value:
                rec = {k: v for k, v in attrs.items() if k != "node_type"}
                rec["struct_id"] = node.replace("struct:", "")
                records_s.append(rec)
            elif nt == NodeType.ZONE.value:
                rec = {k: v for k, v in attrs.items() if k != "node_type"}
                rec["zone_id"] = node
                rec["zone_key"] = f"{attrs.get('symbol', '')}:{attrs.get('price_center', 0):.0f}" if "price_center" in attrs else node
                records_z.append(rec)
            elif nt == NodeType.NARRATIVE.value:
                rec = {k: v for k, v in attrs.items() if k != "node_type"}
                rec["narrative_id"] = node
                records_n.append(rec)

        for u, v in self.G.edges:
            edge_attrs = dict(self.G[u][v])
            records_e.append({
                "source": u,
                "target": v,
                **edge_attrs,
            })

        for zr in records_z:
            store.append_zone(zr)
        store.save_structures(records_s)
        for nr in records_n:
            store.append_narrative(nr)
        store.save_edges(records_e)

        idx_stats = store.rebuild_indexes()

        return {
            "structures": len(records_s),
            "zones": len(records_z),
            "narratives": len(records_n),
            "edges": len(records_e),
            **idx_stats,
        }

    @classmethod
    def load_from_store(cls, store: GraphStore, symbol: str | None = None) -> StructureGraph:
        """
        从 JSONL 存储加载为内存图谱。
        可按品种过滤。
        """
        graph = cls()

        structures = store.load_all_structures()
        if symbol:
            structures = [s for s in structures if s.get("symbol") == symbol]

        zones = store.load_all_zones()
        narratives = store.load_all_narratives()
        edges = store.load_all_edges()

        # 加载结构节点
        struct_ids = set()
        for s in structures:
            sid = s.get("struct_id", "")
            if not sid:
                continue
            node_id = f"struct:{sid}"
            struct_ids.add(node_id)
            attrs = {k: v for k, v in s.items() if k not in ("struct_id", "_ts")}
            attrs["node_type"] = NodeType.STRUCTURE.value
            graph.G.add_node(node_id, **attrs)

        # 加载 Zone 节点
        for z in zones:
            zid = z.get("zone_id", "")
            if not zid:
                continue
            attrs = {k: v for k, v in z.items() if k not in ("zone_id", "_ts")}
            attrs["node_type"] = NodeType.ZONE.value
            graph.G.add_node(zid, **attrs)

        # 加载叙事节点
        for n in narratives:
            nid = n.get("narrative_id", "")
            if not nid:
                continue
            attrs = {k: v for k, v in n.items() if k not in ("narrative_id", "_ts")}
            attrs["node_type"] = NodeType.NARRATIVE.value
            graph.G.add_node(nid, **attrs)

        # 加载边（只保留连接已加载节点的边）
        node_ids = set(graph.G.nodes)
        for e in edges:
            src = e.get("source", "")
            tgt = e.get("target", "")
            if src in node_ids and tgt in node_ids:
                edge_attrs = {k: v for k, v in e.items()
                              if k not in ("source", "target", "_edge_key", "_ts")}
                graph.G.add_edge(src, tgt, **edge_attrs)

        return graph

    # ─── 持久化（单文件 JSON，兼容旧接口）────────────────

    def to_json(self) -> dict:
        """序列化为 JSON 可兼容的 dict"""
        return {
            "nodes": [
                {"id": n, **dict(self.G.nodes[n])}
                for n in self.G.nodes
            ],
            "edges": [
                {"source": u, "target": v, **dict(self.G[u][v])}
                for u, v in self.G.edges
            ],
        }

    def save(self, path: str) -> None:
        """保存到 JSON 文件"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(self.to_json(), f, ensure_ascii=False, indent=2, default=str)

    @classmethod
    def load(cls, path: str) -> StructureGraph:
        """从 JSON 文件加载"""
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p) as f:
            data = json.load(f)
        graph = cls()
        for node in data.get("nodes", []):
            nid = node.pop("id")
            graph.G.add_node(nid, **node)
        for edge in data.get("edges", []):
            src = edge.pop("source")
            tgt = edge.pop("target")
            graph.G.add_edge(src, tgt, **edge)
        return graph

    def summary(self) -> dict:
        """图谱概览"""
        node_types = {}
        for n in self.G.nodes:
            nt = self.G.nodes[n].get("node_type", "unknown")
            node_types[nt] = node_types.get(nt, 0) + 1

        edge_types = {}
        for u, v in self.G.edges:
            et = self.G[u][v].get("edge_type", "unknown")
            edge_types[et] = edge_types.get(et, 0) + 1

        return {
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
        }

    def __repr__(self):
        s = self.summary()
        return (f"StructureGraph(nodes={s['total_nodes']}, edges={s['total_edges']}, "
                f"types={s['node_types']})")
