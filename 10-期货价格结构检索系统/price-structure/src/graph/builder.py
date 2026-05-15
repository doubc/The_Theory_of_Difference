"""
图谱构建模块 — 从 Structure 构建节点和边

P1 整改：从 graph/__init__.py 中提取构建逻辑。
StructureGraph.from_structures() 的核心代码迁移到这里，
__init__.py 保留类定义和查询方法，builder 负责构建。
"""

from __future__ import annotations

from src.graph import StructureGraph, NodeType, EdgeType


def build_structure_nodes(
    graph: StructureGraph,
    structure,
    index: int,
    prev_graph: StructureGraph | None = None,
    prev_struct_nodes: dict[str, str] | None = None,
) -> tuple[str, str]:
    """
    从单个 Structure 构建节点和边

    Args:
        graph: 目标 StructureGraph
        structure: Structure 对象
        index: 结构索引
        prev_graph: 前一次编译的图谱（用于演化链）
        prev_struct_nodes: 前次图谱的 zone_key → node_id 映射

    Returns:
        (struct_node_id, zone_key)
    """
    symbol = structure.symbol or "unknown"
    zone_key = f"{symbol}:{structure.zone.price_center:.0f}"
    struct_id = f"{symbol}_S{index}_{structure.t_start.strftime('%Y%m%d') if structure.t_start else 'nodate'}"

    # 结构节点属性
    s_attrs = {
        "zone_key": zone_key,
        "zone_center": structure.zone.price_center,
        "cycle_count": structure.cycle_count,
        "avg_speed_ratio": structure.avg_speed_ratio,
        "avg_time_ratio": structure.avg_time_ratio,
        "narrative": structure.narrative_context,
        "contrast_type": structure.zone.context_contrast.value,
        "typicality": structure.typicality,
        "label": structure.label or "",
    }
    if structure.motion:
        s_attrs["phase_tendency"] = structure.motion.phase_tendency
        s_attrs["movement_type"] = structure.motion.movement_type.value if hasattr(structure.motion, 'movement_type') else ""
        s_attrs["conservation_flux"] = structure.motion.conservation_flux
        s_attrs["stable_distance"] = structure.motion.stable_distance
    if structure.projection:
        s_attrs["compression_level"] = structure.projection.compression_level

    s_node = graph.add_structure_node(struct_id, **s_attrs)

    # Zone 节点
    zone_id = f"{symbol}_{structure.zone.price_center:.0f}"
    z_node = graph.add_zone_node(zone_id,
                                  price_center=structure.zone.price_center,
                                  bandwidth=structure.zone.bandwidth,
                                  strength=structure.zone.strength,
                                  contrast_type=structure.zone.context_contrast.value)
    graph.link_structure_zone(s_node, z_node)

    # 品种节点
    sym_node = graph.add_symbol_node(symbol)
    graph.link_structure_symbol(s_node, sym_node)

    # 叙事节点
    if structure.narrative_context:
        ts = structure.t_start.strftime("%Y-%m-%d") if structure.t_start else ""
        n_node = graph.add_narrative_node(structure.narrative_context, timestamp=ts)
        graph.link_narrative_chain(s_node, n_node)

        # 叙事递归链
        if prev_graph and prev_struct_nodes and zone_key in prev_struct_nodes:
            old_s_node = prev_struct_nodes[zone_key]
            old_narratives = [
                n for n in prev_graph.G.successors(old_s_node)
                if prev_graph.G[old_s_node][n].get("edge_type") == EdgeType.HAS_NARRATIVE.value
            ]
            if old_narratives:
                for old_n in old_narratives:
                    old_text = prev_graph.G.nodes[old_n].get("text", "")
                    old_ts = prev_graph.G.nodes[old_n].get("timestamp", "")
                    new_old_n = graph.add_narrative_node(old_text, timestamp=old_ts)
                    graph.link_narrative_chain(s_node, new_old_n)
                    if old_text != structure.narrative_context:
                        graph.add_edge(new_old_n, n_node, EdgeType.NARRATIVE_EVOLVES)

    return s_node, zone_key


def build_evolution_edges(
    graph: StructureGraph,
    current_struct_nodes: dict[str, str],
    prev_struct_nodes: dict[str, str],
    prev_graph: StructureGraph | None = None,
) -> None:
    """
    构建演化链和共享 Zone 关系

    Args:
        graph: 目标 StructureGraph
        current_struct_nodes: 本次编译的 zone_key → node_id
        prev_struct_nodes: 前次编译的 zone_key → node_id
        prev_graph: 前次图谱
    """
    # 演化链
    for zone_key, s_node in current_struct_nodes.items():
        if zone_key in prev_struct_nodes and prev_graph:
            old_s = prev_struct_nodes[zone_key]
            old_attrs = dict(prev_graph.G.nodes[old_s])
            old_reconstructed = graph.add_structure_node(f"prev_{old_s}", **old_attrs)
            graph.link_evolution(old_reconstructed, s_node)

    # 同 Zone 结构互链
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


def build_graph_from_structures(
    structures: list,
    prev_graph: StructureGraph | None = None,
) -> StructureGraph:
    """
    从编译结果构建完整知识图谱

    这是 StructureGraph.from_structures() 的重构版本，
    将构建逻辑拆分为节点构建和边构建两步。

    Args:
        structures: compile_full() 输出的 Structure 列表
        prev_graph: 前一次编译的图谱

    Returns:
        新的 StructureGraph
    """
    graph = StructureGraph()

    # 提取前次图谱的结构节点
    prev_struct_nodes: dict[str, str] = {}
    if prev_graph:
        for node in prev_graph.G.nodes:
            if prev_graph.G.nodes[node].get("node_type") == NodeType.STRUCTURE.value:
                zk = prev_graph.G.nodes[node].get("zone_key", "")
                if zk:
                    prev_struct_nodes[zk] = node

    current_struct_nodes: dict[str, str] = {}

    for i, st in enumerate(structures):
        s_node, zone_key = build_structure_nodes(
            graph, st, i,
            prev_graph=prev_graph,
            prev_struct_nodes=prev_struct_nodes,
        )
        current_struct_nodes[zone_key] = s_node

    build_evolution_edges(
        graph, current_struct_nodes, prev_struct_nodes,
        prev_graph=prev_graph,
    )

    return graph
