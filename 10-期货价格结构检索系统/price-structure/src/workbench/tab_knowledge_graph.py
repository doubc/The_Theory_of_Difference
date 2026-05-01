"""
知识图谱 Tab — 价格结构研究工作台

功能：
1. 🌐 图谱总览：结构演化链 + Zone 网络 + 叙事递归
2. 📊 叙事追踪：叙事漂移率 + 锁定检测
3. 🔄 反身性分析：规则有效性衰减 + 闭环检测
4. 🔀 跨品种传导：差异转移网络 + 热力矩阵
5. 📈 图谱统计：节点/边/路径统计

运行依赖：
  - src/graph/__init__.py (StructureGraph)
  - src/graph/store.py (GraphStore)
  - src/graph/narrative_tracker.py (NarrativeRecursionTracker)
  - src/graph/reflexivity.py (ReflexivityDetector)
  - src/graph/transfer_network.py (TransferNetwork)
"""

from __future__ import annotations
import os
import sys
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.graph.store import GraphStore
from src.graph import StructureGraph, NodeType, EdgeType
from src.graph.narrative_tracker import NarrativeRecursionTracker
from src.graph.reflexivity import ReflexivityDetector
from src.graph.transfer_network import TransferNetwork
from src.graph.product_ingester import ProductKnowledgeIngester


# ─── 样式 ────────────────────────────────────────────────

KG_CSS = """
<style>
.kg-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px;
    margin: 8px 0;
    border: 1px solid #dee2e6;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.kg-card h3 {
    color: #c62828;
    margin-top: 0;
    font-size: 1.1em;
}
.kg-metric {
    display: inline-block;
    padding: 8px 16px;
    margin: 4px;
    background: #ffebee;
    border-radius: 8px;
    border: 1px solid #ef9a9a;
}
.kg-metric .value {
    font-size: 1.5em;
    font-weight: bold;
    color: #c62828;
}
.kg-metric .label {
    font-size: 0.85em;
    color: #546e7a;
}
.kg-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.8em;
    font-weight: bold;
}
.kg-badge-a { background: #2e7d32; color: #fff; }
.kg-badge-b { background: #e65100; color: #fff; }
.kg-badge-c { background: #c62828; color: #fff; }
.kg-badge-d { background: #95a5a6; color: #fff; }
.narrative-box {
    background: rgba(52, 152, 219, 0.1);
    border-left: 3px solid #3498db;
    padding: 10px 15px;
    margin: 5px 0;
    border-radius: 0 8px 8px 0;
}
.locked-narrative {
    background: rgba(231, 76, 60, 0.1);
    border-left: 3px solid #e74c3c;
}
.transfer-hot {
    background: rgba(241, 196, 15, 0.15);
    border: 1px solid #f1c40f;
    border-radius: 8px;
    padding: 10px;
    margin: 5px 0;
}
</style>
"""


# ─── 渲染入口 ──────────────────────────────────────────────

def render(ctx: dict) -> None:
    """渲染知识图谱 Tab"""
    st.markdown(KG_CSS, unsafe_allow_html=True)

    selected_symbol = ctx["selected_symbol"]
    result = ctx["result"]
    bars = ctx["bars"]
    sens = ctx["sens"]

    st.markdown("### 🗺️ 知识图谱")
    st.caption("结构演化链 · 叙事递归 · 反身性闭环 · 跨品种传导")

    # 子 Tab
    sub_tabs = st.tabs([
        "🌐 图谱总览",
        "📖 叙事追踪",
        "🔄 反身性分析",
        "🔀 跨品种传导",
        "📊 图谱统计",
        "💉 知识注入",
        "🧠 知识层",
    ])

    # 初始化图谱存储
    graph_store = GraphStore("data/graph")

    with sub_tabs[0]:
        _render_overview(ctx, graph_store)

    with sub_tabs[1]:
        _render_narrative_tracking(ctx, graph_store)

    with sub_tabs[2]:
        _render_reflexivity(ctx, graph_store)

    with sub_tabs[3]:
        _render_transfer_network(ctx, graph_store)

    with sub_tabs[4]:
        _render_statistics(ctx, graph_store)

    with sub_tabs[5]:
        _render_knowledge_injection(ctx, graph_store)

    with sub_tabs[6]:
        _render_knowledge_layers(ctx)


# ─── Tab 1: 图谱总览 ──────────────────────────────────────

def _render_overview(ctx: dict, store: GraphStore) -> None:
    """图谱总览"""
    selected_symbol = ctx["selected_symbol"]
    result = ctx["result"]

    col1, col2, col3, col4 = st.columns(4)

    # 优先用编译器已构建的 result.graph
    graph = getattr(result, "graph", None) if result else None

    if graph and graph.G.number_of_nodes() > 0:
        node_count = graph.G.number_of_nodes()
        edge_count = graph.G.number_of_edges()
        structure_count = sum(
            1 for n in graph.G.nodes
            if graph.G.nodes[n].get("node_type") == NodeType.STRUCTURE.value
        )
        zone_count = sum(
            1 for n in graph.G.nodes
            if graph.G.nodes[n].get("node_type") == NodeType.ZONE.value
        )
    else:
        # fallback: 从 JSONL 存储加载
        try:
            graph = StructureGraph.load_from_store(store, symbol=selected_symbol)
            node_count = graph.G.number_of_nodes()
            edge_count = graph.G.number_of_edges()
            structure_count = sum(
                1 for n in graph.G.nodes
                if graph.G.nodes[n].get("node_type") == NodeType.STRUCTURE.value
            )
            zone_count = sum(
                1 for n in graph.G.nodes
                if graph.G.nodes[n].get("node_type") == NodeType.ZONE.value
            )
        except Exception:
            node_count, edge_count, structure_count, zone_count = 0, 0, 0, 0
            graph = None

    with col1:
        st.metric("🧩 节点总数", node_count)
    with col2:
        st.metric("🔗 关系边数", edge_count)
    with col3:
        st.metric("📐 结构节点", structure_count)
    with col4:
        st.metric("🎯 Zone 节点", zone_count)

    st.divider()

    # 图谱已在编译时自动构建（pipeline.py 3.6 节）
    if graph and graph.G.number_of_nodes() > 0:
        source = "编译器自动构建" if getattr(result, "graph", None) else "JSONL 存储加载"
        st.success(f"✅ 图谱已就绪（来源: {source}）")
        _render_graph_visualization(graph)
    else:
        st.info("📭 图谱为空。运行编译器后图谱会自动构建（pipeline.py 3.6 节）。")


def _render_graph_visualization(graph: StructureGraph) -> None:
    """用 Plotly 渲染力导向图"""
    G = graph.G

    if G.number_of_nodes() == 0:
        return

    # 使用 spring layout
    try:
        import networkx as nx
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    except Exception:
        pos = {n: (i, 0) for i, n in enumerate(G.nodes)}

    # 节点颜色映射
    color_map = {
        NodeType.STRUCTURE.value: "#e94560",
        NodeType.ZONE.value: "#3498db",
        NodeType.NARRATIVE.value: "#2ecc71",
        NodeType.RULE.value: "#f39c12",
        NodeType.SYMBOL.value: "#9b59b6",
    }

    # 绘制边
    edge_traces = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_type = data.get("edge_type", "")
        color = "#555" if edge_type in ("evolves_to", "transfer_to") else "#333"
        width = 2 if edge_type in ("evolves_to", "transfer_to") else 1

        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode='lines',
            line=dict(width=width, color=color),
            hoverinfo='none',
            showlegend=False,
        ))

    # 绘制节点
    node_x, node_y, node_text, node_color, node_size = [], [], [], [], []
    for node in G.nodes:
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        attrs = G.nodes[node]
        nt = attrs.get("node_type", "unknown")
        node_color.append(color_map.get(nt, "#78909c"))

        # 节点大小：根据连接数
        degree = G.degree(node)
        node_size.append(max(10, min(30, 8 + degree * 3)))

        # 悬浮文本
        label = attrs.get("name", node)
        text = f"<b>{node}</b><br>Type: {nt}"
        if "price_center" in attrs:
            text += f"<br>Price: {attrs['price_center']:.0f}"
        if "narrative" in attrs:
            text += f"<br>Narrative: {attrs['narrative'][:50]}..."
        node_text.append(text)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(size=node_size, color=node_color, line=dict(width=1, color="#37474f")),
        text=[n.split(":")[-1][:8] for n in G.nodes],
        textposition="top center",
        textfont=dict(size=8, color="#37474f"),
        hovertext=node_text,
        hoverinfo='text',
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title="知识图谱 — 力导向布局",
        template="plotly_dark",
        height=500,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Tab 2: 叙事追踪 ──────────────────────────────────────

def _render_narrative_tracking(ctx: dict, store: GraphStore) -> None:
    """叙事递归追踪"""
    selected_symbol = ctx["selected_symbol"]
    result = ctx["result"]

    st.markdown("#### 📖 叙事递归追踪")
    st.caption("追踪市场叙事如何随时间演化，检测叙事锁定与漂移")

    # 优先用编译器已构建的图谱
    graph = getattr(result, "graph", None) if result else None

    tracker = NarrativeRecursionTracker.from_store(store, symbol=selected_symbol)

    # 从编译结果的 structures 更新追踪器
    structures = getattr(result, "structures", []) if result else []
    if structures:
        chains = tracker.track_evolution(structures, symbol=selected_symbol)

        # 显示每个 Zone 的叙事演化
        if chains:
            for zone_key, chain in chains.items():
                with st.expander(
                    f"🎯 {zone_key} — 漂移率 {chain.total_drift:.3f} | "
                    f"{'🔒 已锁定' if chain.is_locked else '🔄 演化中'}",
                    expanded=chain.is_locked,
                ):
                    # 叙事时间线
                    if chain.snapshots:
                        st.markdown("**叙事时间线：**")
                        for i, snap in enumerate(chain.snapshots):
                            icon = "📝" if i < len(chain.snapshots) - 1 else "📍"
                            locked_class = "locked-narrative" if chain.is_locked and i == len(chain.snapshots) - 1 else ""
                            st.markdown(
                                f'<div class="narrative-box {locked_class}">'
                                f'{icon} <b>{snap.timestamp.strftime("%Y-%m-%d")}</b> — '
                                f'{snap.text or "(无叙事)"}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    # 漂移率可视化
                    if chain.steps:
                        drift_data = pd.DataFrame({
                            "步骤": range(1, len(chain.steps) + 1),
                            "相似度": [s.similarity for s in chain.steps],
                            "漂移量": [s.drift_delta for s in chain.steps],
                        })
                        fig = make_subplots(specs=[[{"secondary_y": True}]])
                        fig.add_trace(
                            go.Scatter(
                                x=drift_data["步骤"], y=drift_data["相似度"],
                                name="相似度", line=dict(color="#3498db"),
                            ),
                            secondary_y=False,
                        )
                        fig.add_trace(
                            go.Bar(
                                x=drift_data["步骤"], y=drift_data["漂移量"],
                                name="漂移量", marker_color="rgba(233, 69, 96, 0.5)",
                            ),
                            secondary_y=True,
                        )
                        fig.update_layout(
                            template="plotly_dark", height=250,
                            margin=dict(l=40, r=40, t=20, b=20),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    # 锁定检测
                    lock_report = tracker.detect_lock(chain)
                    if lock_report.is_locked:
                        st.warning(
                            f"🔒 **叙事锁定检测** — 锁定强度: {lock_report.lock_strength:.1%} | "
                            f"持续 {lock_report.lock_duration_days} 天 | "
                            f"{lock_report.recommendation}"
                        )

            # 漂移率总览
            drift_reports = tracker.compute_all_drift_rates()
            if drift_reports:
                st.divider()
                st.markdown("#### 📊 叙事漂移率总览")

                drift_df = pd.DataFrame([
                    {
                        "Zone": zk,
                        "漂移率": r.drift_rate,
                        "趋势": r.drift_trend,
                        "多样性": r.narrative_diversity,
                        "高漂移步骤": len(r.high_drift_steps),
                    }
                    for zk, r in drift_reports.items()
                ])

                if not drift_df.empty:
                    fig = px.bar(
                        drift_df, x="Zone", y="漂移率",
                        color="趋势",
                        color_discrete_map={
                            "accelerating": "#e74c3c",
                            "decelerating": "#2ecc71",
                            "stable": "#3498db",
                        },
                        template="plotly_dark",
                        height=300,
                    )
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("当前编译结果中无叙事数据")
    else:
        st.info("请先在「今天值得关注什么」Tab 中编译数据")


# ─── Tab 3: 反身性分析 ──────────────────────────────────────

def _render_reflexivity(ctx: dict, store: GraphStore) -> None:
    """反身性闭环分析"""
    selected_symbol = ctx["selected_symbol"]

    st.markdown("#### 🔄 反身性分析")
    st.caption("检测规则 → 结构 → 失效 的反身性闭环，追踪模板有效性衰减")

    # 已有的实用反身性追踪器（src/reflexivity.py）
    from src.reflexivity import ReflexivityTracker
    practical_tracker = ReflexivityTracker.load()

    # 图谱层反身性检测器（src/graph/reflexivity.py）
    detector = ReflexivityDetector()

    # 优先用编译器已构建的图谱
    graph = getattr(result, "graph", None) if result else None
    if graph is None:
        try:
            graph = StructureGraph.load_from_store(store, symbol=selected_symbol)
        except Exception:
            graph = None

    # 显示已有追踪器的规则性能
    if practical_tracker.records:
        st.markdown("#### 📈 规则性能追踪（已有数据）")
        rule_names = set(r.rule_name for r in practical_tracker.records)
        for rule_name in sorted(rule_names):
            summary = practical_tracker.summarize(rule_name)
            with st.expander(
                f"{'⚠️' if summary.decay_detected else '✅'} "
                f"{rule_name} — 准确率 {summary.accuracy_10d:.1%} "
                f"{'(衰减)' if summary.decay_detected else ''}",
                expanded=summary.decay_detected,
            ):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("总匹配", summary.total_matches)
                    st.metric("已验证", summary.verified_matches)
                with col_b:
                    st.metric("5日准确率", f"{summary.accuracy_5d:.1%}")
                    st.metric("10日准确率", f"{summary.accuracy_10d:.1%}")
                with col_c:
                    st.metric("20日准确率", f"{summary.accuracy_20d:.1%}")
                    st.metric("建议权重", f"{summary.recommended_weight:.2f}")

    # 图谱层反身性检测
    if graph:
        report = detector.generate_report(graph)
        if report.total_rules > 0:
            st.divider()
            st.markdown("#### 🔄 反身性闭环（图谱层）")
            for rec in report.recommendations:
                st.info(rec)
        # 总览指标
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📋 追踪规则数", report.total_rules)
        with col2:
            st.metric("🔄 活跃闭环", len(report.active_loops))
        with col3:
            stress_color = "normal" if report.systemic_reflexivity < 0.5 else "inverse"
            st.metric("⚡ 系统反身性", f"{report.systemic_reflexivity:.1%}")

        # 建议
        for rec in report.recommendations:
            st.info(rec)

        # 衰减报告
        if report.decay_reports:
            st.markdown("#### 📉 模板有效性衰减")

            for dr in report.decay_reports:
                badge_class = f"kg-badge-{dr.current_tier.lower()}"
                with st.expander(
                    f"{'⚠️' if dr.should_downgrade else '✅'} "
                    f"{dr.rule_id} — 有效率 {dr.success_rate:.1%} "
                    f'<span class="kg-badge {badge_class}">{dr.current_tier}</span>',
                    expanded=dr.should_downgrade,
                ):
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("总匹配", dr.total_matches)
                        st.metric("成功", dr.success_count)
                    with col_b:
                        st.metric("失败", dr.failure_count)
                        st.metric("衰减率", f"{dr.decay_rate:.1%}")
                    with col_c:
                        st.metric("当前层级", dr.current_tier)
                        st.metric("建议层级", dr.recommended_tier)

                    # 有效性曲线
                    if dr.recent_effectiveness:
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            y=dr.recent_effectiveness,
                            mode='lines+markers',
                            name="有效率",
                            line=dict(color="#e94560"),
                        ))
                        fig.add_hline(y=0.5, line_dash="dash", line_color="#f39c12")
                        fig.update_layout(
                            template="plotly_dark", height=200,
                            margin=dict(l=40, r=40, t=20, b=20),
                            yaxis_title="有效率",
                            xaxis_title="窗口",
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    if dr.should_downgrade:
                        st.error(
                            f"🔽 建议降级: {dr.current_tier} → {dr.recommended_tier} | "
                            f"衰减趋势: {dr.decay_trend}"
                        )

        # 反身性闭环
        if report.active_loops:
            st.markdown("#### 🔄 反身性闭环")
            for loop in report.active_loops:
                st.markdown(
                    f'<div class="kg-card">'
                    f'<h3>🔄 {loop.rule_id}</h3>'
                    f'<p>匹配结构: {loop.matched_structure}</p>'
                    f'<p>失效结构: {loop.invalidating_structure}</p>'
                    f'<p>演化链长度: {loop.evolution_length} | '
                    f'持续 {loop.loop_duration_days} 天 | '
                    f'模板有效性: {loop.template_effectiveness:.1%}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("📭 暂无反身性数据。需要先积累规则匹配和失效记录。")
        st.markdown(
            "**使用方法：**\n"
            "1. 运行编译器生成结构\n"
            "2. 规则引擎匹配结构\n"
            "3. 记录后验结果（成功/失败）\n"
            "4. 反身性检测器自动分析衰减和闭环"
        )


# ─── Tab 4: 跨品种传导 ──────────────────────────────────────

def _render_transfer_network(ctx: dict, store: GraphStore) -> None:
    """跨品种差异转移网络"""
    st.markdown("#### 🔀 跨品种差异转移网络")
    st.caption("基于守恒通量的品种间差异转移检测")

    network = TransferNetwork()

    # 从图谱存储加载所有品种的通量数据
    all_structures = store.load_all_structures()
    if not all_structures:
        st.info("📭 图谱中无结构数据。请先在图谱总览中构建图谱。")
        return

    # 按品种分组提取通量
    by_symbol: dict[str, list] = {}
    for s in all_structures:
        sym = s.get("symbol", s.get("product", ""))
        if sym:
            by_symbol.setdefault(sym, []).append(s)

    if len(by_symbol) < 2:
        st.warning("⚠️ 需要至少 2 个品种的数据才能构建转移网络")
        st.info(f"当前只有 {len(by_symbol)} 个品种: {', '.join(by_symbol.keys())}")
        return

    # 构建 FluxRecord
    from src.graph.transfer_network import FluxRecord
    for sym, structs in by_symbol.items():
        for s in structs:
            try:
                ts = datetime.fromisoformat(s.get("t_end", s.get("compile_date", "")))
            except (ValueError, TypeError):
                ts = datetime.now()

            record = FluxRecord(
                symbol=sym,
                timestamp=ts,
                conservation_flux=s.get("conservation_flux", 0.0),
                phase_tendency=s.get("phase_tendency", ""),
                zone_center=s.get("zone_center", 0.0),
                cycle_count=s.get("cycle_count", 0),
                movement_type=s.get("movement_type", ""),
            )
            network.add_flux_record(record)

    # 构建网络
    report = network.build_network()

    # 总览
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📈 品种数", len(report.products))
    with col2:
        st.metric("🔗 转移边", len(report.edges))
    with col3:
        st.metric("🔥 热点", len(report.hot_spots))
    with col4:
        stress_color = "normal" if report.systemic_stress < 0.5 else "inverse"
        st.metric("⚡ 系统压力", f"{report.systemic_stress:.1%}")

    # 转移矩阵热力图
    if report.edges:
        st.markdown("#### 🔥 转移强度矩阵")
        symbols, matrix = network.get_transfer_matrix()

        fig = px.imshow(
            matrix,
            x=symbols, y=symbols,
            color_continuous_scale="RdYlBu_r",
            labels=dict(color="转移强度"),
            template="plotly_dark",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        # 转移网络力导向图
        st.markdown("#### 🌐 转移网络可视化")
        _render_transfer_graph(report)

        # 热点列表
        if report.hot_spots:
            st.markdown("#### 🔥 转移热点")
            for spot in report.hot_spots:
                st.markdown(
                    f'<div class="transfer-hot">'
                    f'🔗 <b>{spot["pair"]}</b> — '
                    f'强度 {spot["strength"]:.2f} | '
                    f'相关性 {spot["correlation"]:.2f} | '
                    f'滞后 {spot["lag_days"]} 天 | '
                    f'证据 {spot["evidence"]} 条 | '
                    f'方向 {spot["direction"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # 品种详情
        st.markdown("#### 📊 品种节点属性")
        product_df = pd.DataFrame([
            {
                "品种": p.symbol,
                "平均通量": p.avg_flux,
                "波动率": p.flux_volatility,
                "主导阶段": p.dominant_phase,
                "中心度": p.transfer_centrality,
                "连接数": p.connected_products,
            }
            for p in report.products
        ])
        if not product_df.empty:
            st.dataframe(product_df, use_container_width=True)
    else:
        st.info("未检测到显著的品种间差异转移关系")


def _render_transfer_graph(report) -> None:
    """渲染转移网络力导向图"""
    if not report.edges:
        return

    # 收集所有品种
    symbols = list(set(
        [e.source_symbol for e in report.edges] +
        [e.target_symbol for e in report.edges]
    ))

    # 简单的圆形布局
    import math
    n = len(symbols)
    pos = {}
    for i, sym in enumerate(symbols):
        angle = 2 * math.pi * i / n
        pos[sym] = (math.cos(angle), math.sin(angle))

    # 边
    edge_traces = []
    for edge in report.edges:
        x0, y0 = pos[edge.source_symbol]
        x1, y1 = pos[edge.target_symbol]
        width = max(1, edge.strength * 5)
        color = f"rgba(233, 69, 96, {edge.strength})"

        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode='lines',
            line=dict(width=width, color=color),
            hoverinfo='none',
            showlegend=False,
        ))

    # 节点
    node_x = [pos[s][0] for s in symbols]
    node_y = [pos[s][1] for s in symbols]

    # 节点大小：根据中心度
    centrality_map = {p.symbol: p.transfer_centrality for p in report.products}
    node_size = [max(15, centrality_map.get(s, 0) * 100 + 15) for s in symbols]

    # 节点颜色：根据主导阶段
    phase_map = {p.symbol: p.dominant_phase for p in report.products}
    phase_colors = {
        "accumulation": "#3498db",
        "compression": "#f39c12",
        "release": "#e74c3c",
        "trending": "#2ecc71",
    }
    node_color = [phase_colors.get(phase_map.get(s, ""), "#95a5a6") for s in symbols]

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(size=node_size, color=node_color, line=dict(width=2, color="#37474f")),
        text=symbols,
        textposition="top center",
        textfont=dict(size=12, color="#1a1a2e"),
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        template="plotly_dark",
        height=400,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Tab 5: 图谱统计 ──────────────────────────────────────

def _render_statistics(ctx: dict, store: GraphStore) -> None:
    """图谱统计"""
    st.markdown("#### 📊 图谱统计")

    try:
        stats = store.stats()
    except Exception:
        stats = {}

    # 基础统计
    structures = store.load_all_structures()
    zones = store.load_all_zones()
    narratives = store.load_all_narratives()
    edges = store.load_all_edges()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("结构", len(structures))
    with col2:
        st.metric("Zone", len(zones))
    with col3:
        st.metric("叙事", len(narratives))
    with col4:
        st.metric("边", len(edges))

    # 按品种分布
    if structures:
        st.markdown("#### 📈 品种分布")
        sym_counts = {}
        for s in structures:
            sym = s.get("symbol", s.get("product", "unknown"))
            sym_counts[sym] = sym_counts.get(sym, 0) + 1

        fig = px.pie(
            values=list(sym_counts.values()),
            names=list(sym_counts.keys()),
            template="plotly_dark",
            hole=0.4,
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    # 边类型分布
    if edges:
        st.markdown("#### 🔗 关系类型分布")
        edge_types = {}
        for e in edges:
            et = e.get("edge_type", "unknown")
            edge_types[et] = edge_types.get(et, 0) + 1

        fig = px.bar(
            x=list(edge_types.keys()),
            y=list(edge_types.values()),
            template="plotly_dark",
            labels={"x": "关系类型", "y": "数量"},
            color=list(edge_types.values()),
            color_continuous_scale="viridis",
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # 快照列表
    st.markdown("#### 📸 历史快照")
    snap_dir = store.snap_dir
    if snap_dir.exists():
        snaps = sorted(snap_dir.glob("*.json"), reverse=True)
        if snaps:
            for snap in snaps[:10]:
                st.caption(f"📸 {snap.name}")
        else:
            st.info("暂无快照")
    else:
        st.info("快照目录不存在")


# ─── Tab 6: 知识注入 ──────────────────────────────────────

def _render_knowledge_injection(ctx: dict, store: GraphStore) -> None:
    """知识注入 — 从 config/products/ 导入品种知识"""
    st.markdown("#### 💉 知识注入")
    st.caption("从 config/products/ 导入品种实体、关系、传导链、定价模型到知识图谱")

    # 加载 registry
    import yaml
    registry_path = "config/products/registry.yaml"
    if not os.path.exists(registry_path):
        st.error("❌ config/products/registry.yaml 不存在")
        return

    with open(registry_path, encoding="utf-8") as f:
        registry = yaml.safe_load(f)

    products = registry.get("products", {})

    # 品种总览
    st.markdown("#### 📋 品种注册表")

    prod_data = []
    for key, prod in products.items():
        prod_data.append({
            "品种": key,
            "代号": prod.get("symbol", ""),
            "名称": prod.get("name", ""),
            "状态": prod.get("status", ""),
            "标签": ", ".join(prod.get("tags", [])),
            "文件数": len(prod.get("files", {})),
        })

    if prod_data:
        st.dataframe(pd.DataFrame(prod_data), use_container_width=True)

    # 导入操作
    st.divider()
    st.markdown("#### 🚀 导入操作")

    col1, col2 = st.columns(2)

    with col1:
        selected_product = st.selectbox(
            "选择品种",
            list(products.keys()),
            format_func=lambda k: f"{k} — {products[k].get('name', k)}",
        )

    with col2:
        force_refresh = st.checkbox("强制刷新（忽略 hash 缓存）", value=False)

    if st.button("💉 导入到图谱", key="kg_ingest"):
        with st.spinner(f"正在导入 {selected_product}..."):
            try:
                ingester = ProductKnowledgeIngester(store, registry_path=registry_path)

                if selected_product == "_shared":
                    stats = ingester.ingest_product("_shared", force=force_refresh)
                    results = {"_shared": stats}
                else:
                    # 先导入 shared，再导入目标品种
                    ingester.ingest_product("_shared", force=False)
                    stats = ingester.ingest_product(selected_product, force=force_refresh)
                    results = {selected_product: stats}

                # 显示结果
                for key, stat in results.items():
                    if stat.skipped:
                        st.info(f"⏭️ {key}: {stat.reason}")
                    else:
                        st.success(
                            f"✅ {key}: "
                            f"{stat.entities} 实体, "
                            f"{stat.relations} 关系, "
                            f"{stat.chains} 传导链, "
                            f"{stat.polarity_rules} 极值, "
                            f"{stat.pricing_models} 定价模型, "
                            f"{stat.edges} 边"
                        )
            except Exception as e:
                st.error(f"❌ 导入失败: {e}")

    # 全量导入
    if st.button("🔄 全量导入所有品种", key="kg_ingest_all"):
        with st.spinner("正在导入所有 active 品种..."):
            try:
                ingester = ProductKnowledgeIngester(store, registry_path=registry_path)
                results = ingester.ingest_all_active_products(force=force_refresh)

                for key, stat in results.items():
                    if stat.skipped:
                        st.info(f"⏭️ {key}: {stat.reason}")
                    else:
                        st.success(
                            f"✅ {key}: "
                            f"{stat.entities} 实体, "
                            f"{stat.relations} 关系, "
                            f"{stat.chains} 传导链"
                        )
            except Exception as e:
                st.error(f"❌ 全量导入失败: {e}")

    # 品种知识详情
    st.divider()
    st.markdown("#### 📖 品种知识详情")

    detail_product = st.selectbox(
        "查看品种详情",
        list(products.keys()),
        format_func=lambda k: f"{k} — {products[k].get('name', k)}",
        key="kg_detail_product",
    )

    prod_config = products.get(detail_product, {})
    files = prod_config.get("files", {})

    if files:
        detail_tabs = st.tabs(list(files.keys()))

        for i, (file_type, rel_path) in enumerate(files.items()):
            with detail_tabs[i]:
                full_path = os.path.join("config/products", rel_path)
                if os.path.exists(full_path):
                    import json
                    with open(full_path, encoding="utf-8") as f:
                        data = json.load(f)

                    # 根据文件类型展示
                    if file_type == "entities":
                        entities = data.get("entities", [])
                        st.caption(f"共 {len(entities)} 个实体")
                        for ent in entities[:20]:  # 只显示前20个
                            importance = ent.get("importance", 5)
                            icon = "🔴" if importance >= 9 else "🟡" if importance >= 7 else "🟢"
                            with st.expander(
                                f"{icon} {ent.get('id', '')} — {ent.get('name', '')} "
                                f"(重要度 {importance})",
                                expanded=False,
                            ):
                                st.markdown(f"**类型:** {ent.get('type', '')}")
                                st.markdown(f"**描述:** {ent.get('description', '')}")
                                if ent.get("controlledBy"):
                                    st.markdown(f"**控制方:** {', '.join(ent['controlledBy'])}")
                                if ent.get("vulnerabilities"):
                                    st.markdown(f"**脆弱性:** {', '.join(ent['vulnerabilities'])}")
                                if ent.get("trackingVariables"):
                                    st.markdown(f"**跟踪变量:** {', '.join(ent['trackingVariables'])}")

                    elif file_type == "relations":
                        relations = data.get("relations", [])
                        st.caption(f"共 {len(relations)} 个关系")
                        for rel in relations[:20]:
                            st.markdown(
                                f"- **{rel.get('id', '')}** {rel.get('from', '')} "
                                f"→ {rel.get('to', '')} "
                                f"(强度 {rel.get('strength', 0):.1%}, {rel.get('direction', '')})"
                            )

                    elif file_type == "chains":
                        chains = data.get("chains", [])
                        st.caption(f"共 {len(chains)} 条传导链")
                        for chain in chains:
                            with st.expander(
                                f"🔗 {chain.get('id', '')} — {chain.get('name', '')} "
                                f"({len(chain.get('steps', []))} 步)",
                                expanded=False,
                            ):
                                st.markdown(f"**触发事件:** {chain.get('triggerEvent', '')}")
                                st.markdown(f"**反转节点:** {chain.get('reversalNode', '')}")
                                st.markdown(f"**反转条件:** {chain.get('reversalCondition', '')}")

                                # 步骤
                                for step in chain.get("steps", []):
                                    st.markdown(
                                        f"  {step.get('seq', '')}. "
                                        f"{step.get('from', '')} → {step.get('to', '')} "
                                        f"(置信度 {step.get('confidence', '')}, "
                                        f"滞后 {step.get('lag', '')})"
                                    )

                                # 历史案例
                                cases = chain.get("historicalCases", [])
                                if cases:
                                    st.markdown("**历史案例:**")
                                    for case in cases:
                                        st.markdown(
                                            f"  - {case.get('year', '')}: {case.get('description', '')}"
                                        )

                    elif file_type == "polarity":
                        entries = data.get("entries", {})
                        st.caption(f"共 {len(entries)} 个极值变量")
                        for var_name, var_info in entries.items():
                            with st.expander(f"📊 {var_name}", expanded=False):
                                st.markdown(
                                    f"**历史范围:** {var_info.get('historicalMin', 'N/A')} ~ "
                                    f"{var_info.get('historicalMax', 'N/A')}"
                                )
                                st.markdown(
                                    f"**近期范围:** {var_info.get('recentMin', 'N/A')} ~ "
                                    f"{var_info.get('recentMax', 'N/A')}"
                                )
                                signals = var_info.get("reversalSignalPatterns", [])
                                if signals:
                                    st.markdown(f"**反转信号:** {', '.join(signals)}")

                    elif file_type == "pricing_models":
                        models = data.get("models", [])
                        st.caption(f"共 {len(models)} 个定价模型")
                        for model in models:
                            with st.expander(
                                f"📐 {model.get('id', '')} — {model.get('name', '')}",
                                expanded=False,
                            ):
                                st.markdown(f"**领域:** {model.get('domain', '')}")
                                st.code(model.get("formula", ""), language=None)
                                if model.get("variables"):
                                    st.markdown(f"**变量:** {', '.join(model['variables'])}")
                    else:
                        st.json(data)
                else:
                    st.warning(f"文件不存在: {full_path}")


# ─── Tab 7: 知识层（L1/L2/L3） ────────────────────────────

def _render_knowledge_layers(ctx: dict) -> None:
    """L1/L2/L3 三层知识可视化"""
    st.markdown("#### 🧠 知识层 — L1/L2/L3 三层知识体系")
    st.caption("判定知识 · 失效知识 · 市场智慧 — 知识图谱的语义层")

    from src.knowledge import KnowledgeEngine

    engine = KnowledgeEngine("knowledge")
    stats = engine.stats

    # 知识库总览
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 L1 判定知识", stats["L1_conditions"])
    with col2:
        st.metric("⚠️ L2 失效知识", stats["L2_invalidation"])
    with col3:
        st.metric("💡 L3 市场知识", stats["L3_wisdom"])
    with col4:
        st.metric("📊 总规则数", stats["total"])

    if stats["total"] == 0:
        st.warning("📭 知识库为空。请在 `knowledge/` 目录下创建 YAML 文件。")
        st.info("详见 `knowledge/README.md`")
        return

    st.divider()

    # 当前结构知识匹配
    result = ctx.get("result")
    structures = getattr(result, "structures", []) if result else []

    if structures:
        st.markdown("#### 🔍 当前结构知识匹配")

        selected_idx = st.selectbox(
            "选择结构",
            range(len(structures)),
            format_func=lambda i: (
                f"结构 {i+1} — Zone {getattr(structures[i].zone, 'price_center', 0):.0f} "
                f"({getattr(structures[i].motion, 'movement_type', 'unknown')})"
            ),
            key="kg_kl_struct_select",
        )

        s = structures[selected_idx]
        kr = engine.evaluate(
            structure=s,
            motion=getattr(s, "motion", None),
            symbol=getattr(s, "symbol", ""),
        )

        # 匹配结果展示
        if kr.total_matched > 0:
            # L1 判定知识
            if kr.conditions:
                st.markdown("**📋 判定知识（该信多少）：**")
                for r in kr.conditions:
                    with st.expander(
                        f"✅ [{r.id}] {r.name} — 置信度 {r.confidence:.0%} | 权重 {r.weight_adjust:+.2f}",
                        expanded=True,
                    ):
                        st.markdown(f"**判定:** {r.verdict}")
                        st.markdown(f"**来源:** {r.source}")
                        if r.confidence:
                            st.progress(r.confidence, text=f"置信度 {r.confidence:.0%}")

            # L2 失效知识
            if kr.invalidations:
                st.markdown("**⚠️ 失效警告（什么条件下作废）：**")
                for r in kr.invalidations:
                    severity_icon = "🔴" if r.severity == "high" else "🟡"
                    with st.expander(
                        f"{severity_icon} [{r.id}] {r.name} — {r.severity}",
                        expanded=r.severity == "high",
                    ):
                        st.markdown(f"**失效判定:** {r.invalidate}")
                        st.markdown(f"**建议动作:** {r.action}")
                        st.markdown(f"**来源:** {r.source}")

            # L3 市场知识
            if kr.wisdoms:
                st.markdown("**💡 市场智慧（有什么值得注意的）：**")
                for r in kr.wisdoms:
                    st.info(f"💡 [{r.id}] {r.wisdom}")

            # 综合评估
            st.divider()
            confidence_boost = kr.confidence_boost
            color = "green" if confidence_boost > 0 else "red" if confidence_boost < 0 else "gray"
            st.markdown(
                f"**综合置信度调整:** :{color}[{confidence_boost:+.2f}] "
                f"| 匹配 {kr.total_matched} 条规则"
            )

            # 知识摘要
            with st.expander("📝 完整知识摘要", expanded=False):
                st.code(kr.summary(), language=None)
        else:
            st.info("当前结构未匹配到任何知识规则")

    st.divider()

    # 知识库详情浏览
    st.markdown("#### 📖 知识库详情")

    detail_tabs = st.tabs(["📋 L1 判定", "⚠️ L2 失效", "💡 L3 智慧"])

    with detail_tabs[0]:
        _render_yaml_rules(engine, "L1", "conditions")

    with detail_tabs[1]:
        _render_yaml_rules(engine, "L2", "invalidations")

    with detail_tabs[2]:
        _render_yaml_rules(engine, "L3", "wisdoms")


def _render_yaml_rules(engine, level: str, attr: str) -> None:
    """渲染 YAML 规则列表"""
    rules = getattr(engine, f"_{attr}", [])
    if not rules:
        st.info(f"📭 {level} 知识库为空")
        return

    for rule in rules:
        rule_id = rule.get("id", "")
        name = rule.get("name", "")
        desc = rule.get("description", "")

        icon = {"L1": "✅", "L2": "⚠️", "L3": "💡"}.get(level, "📋")

        with st.expander(f"{icon} {rule_id} — {name}", expanded=False):
            if desc:
                st.markdown(f"*{desc}*")

            # 条件
            conditions = rule.get("when", [])
            if conditions:
                st.markdown("**条件:**")
                for cond in conditions:
                    field = cond.get("field", "")
                    op = cond.get("op", "")
                    value = cond.get("value", "")
                    st.code(f"{field} {op} {value}", language=None)

            # 输出
            if rule.get("verdict"):
                st.markdown(f"**判定:** {rule['verdict']}")
            if rule.get("invalidate"):
                st.markdown(f"**失效:** {rule['invalidate']}")
            if rule.get("wisdom"):
                st.markdown(f"**智慧:** {rule['wisdom']}")

            # 元数据
            meta_cols = st.columns(3)
            with meta_cols[0]:
                if rule.get("confidence"):
                    st.caption(f"置信度: {rule['confidence']}")
                if rule.get("weight_adjust"):
                    st.caption(f"权重调整: {rule['weight_adjust']:+.2f}")
            with meta_cols[1]:
                if rule.get("severity"):
                    st.caption(f"严重度: {rule['severity']}")
                if rule.get("action"):
                    st.caption(f"建议: {rule['action']}")
            with meta_cols[2]:
                if rule.get("source"):
                    st.caption(f"来源: {rule['source']}")
