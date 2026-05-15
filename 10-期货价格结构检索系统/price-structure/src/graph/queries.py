"""
图谱查询模块 — 演化链、叙事链、反身性查询

P1 整改：从 graph/__init__.py 中提取查询方法为独立函数。
将 StructureGraph 的查询方法封装为纯函数，便于外部直接调用。
"""

from __future__ import annotations

from typing import Any

from src.graph import StructureGraph, NodeType, EdgeType


def query_evolution_chain(graph: StructureGraph, struct_node: str) -> list[str]:
    """获取一个结构的完整演化链"""
    chain = [struct_node]
    current = struct_node
    while True:
        successors = [
            n for n in graph.G.successors(current)
            if graph.G[current][n].get("edge_type") == EdgeType.EVOLVES_TO.value
        ]
        if not successors:
            break
        current = successors[0]
        chain.append(current)
    return chain


def query_transfer_paths(graph: StructureGraph, struct_node: str) -> list[list[str]]:
    """获取差异转移的所有路径"""
    paths = []
    visited = set()

    def _dfs(node, path):
        if node in visited:
            return
        visited.add(node)
        successors = [
            n for n in graph.G.successors(node)
            if graph.G[node][n].get("edge_type") == EdgeType.TRANSFER_TO.value
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


def query_narrative_chain(graph: StructureGraph, struct_node: str) -> list[dict]:
    """获取一个结构的叙事递归链"""
    narrative_nodes = [
        n for n in graph.G.successors(struct_node)
        if graph.G[struct_node][n].get("edge_type") == EdgeType.HAS_NARRATIVE.value
    ]
    if not narrative_nodes:
        return []

    result = []
    for start in narrative_nodes:
        chain = [start]
        current = start
        while True:
            successors = [
                n for n in graph.G.successors(current)
                if graph.G[current][n].get("edge_type") == EdgeType.NARRATIVE_EVOLVES.value
            ]
            if not successors:
                break
            current = successors[0]
            chain.append(current)
        for n in chain:
            result.append({
                "node": n,
                "text": graph.G.nodes[n].get("text", ""),
                "timestamp": graph.G.nodes[n].get("timestamp", ""),
            })
    return result


def query_reflexivity_loops(graph: StructureGraph) -> list[dict]:
    """
    检测反身性闭环：
    Rule → identifies → Structure → (evolves_to) → Structure' → invalidates → Rule
    """
    loops = []
    for node in graph.G.nodes:
        if graph.G.nodes[node].get("node_type") != NodeType.RULE.value:
            continue
        matched_structs = [
            n for n in graph.G.successors(node)
            if graph.G[node][n].get("edge_type") == EdgeType.APPLIED_ON.value
        ]
        for ms in matched_structs:
            chain = query_evolution_chain(graph, ms)
            for s in chain[1:]:
                invalidations = [
                    n for n in graph.G.successors(s)
                    if graph.G[s][n].get("edge_type") == EdgeType.INVALIDATES.value
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


def query_zone_network(graph: StructureGraph) -> dict:
    """获取 Zone 之间的空间关系网络"""
    zones = [n for n in graph.G.nodes
             if graph.G.nodes[n].get("node_type") == NodeType.ZONE.value]
    network = {}
    for z in zones:
        neighbors = [
            n for n in graph.G.neighbors(z)
            if graph.G.nodes[n].get("node_type") == NodeType.ZONE.value
        ]
        structures = [
            n for n in graph.G.predecessors(z)
            if graph.G.nodes[n].get("node_type") == NodeType.STRUCTURE.value
        ]
        network[z] = {
            "adjacent_zones": neighbors,
            "structures": structures,
            "center": graph.G.nodes[z].get("price_center", 0),
        }
    return network


def query_structures_by_narrative(graph: StructureGraph, keyword: str) -> list[str]:
    """通过叙事关键词检索相关结构"""
    matching = []
    for node in graph.G.nodes:
        if graph.G.nodes[node].get("node_type") == NodeType.NARRATIVE.value:
            text = graph.G.nodes[node].get("text", "")
            if keyword in text:
                for pred in graph.G.predecessors(node):
                    if graph.G[pred][node].get("edge_type") == EdgeType.HAS_NARRATIVE.value:
                        matching.append(pred)
    return list(set(matching))
