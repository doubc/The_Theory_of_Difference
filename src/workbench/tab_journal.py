"""
Tab 4: 复盘日志 — 写日志 + 历史回顾

从 app.py 提取的独立模块。
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
import json

from src.workbench.shared import motion_badge


def render(ctx: dict):
    """渲染 Tab 4: 复盘日志"""
    selected_symbol = ctx["selected_symbol"]
    bars = ctx["bars"]
    recent_structures = ctx["recent_structures"]
    ds_name = ctx["ds_name"]

    st.markdown("#### 📝 复盘日志")
    st.caption("结构化记录 · 自动保存到本地 · 可回溯查看")

    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    journal_file = log_dir / "journal.jsonl"
    today = datetime.now().strftime("%Y-%m-%d")
    md_file = log_dir / f"{today}.md"

    # ── 子 Tab：写日志 / 知识图谱 / 活动日志 / 历史回顾 ──
    sub_tab_write, sub_tab_kg, sub_tab_activity, sub_tab_history = st.tabs(["✏️ 写日志", "📚 知识图谱", "📊 活动日志", "📂 历史回顾"])

    # ════════════════════════════════════════════════════════
    # 写日志
    # ════════════════════════════════════════════════════════
    with sub_tab_write:
        st.markdown("**新建一条复盘记录**")

        auto_context = ""
        if recent_structures:
            auto_context = f"[{selected_symbol}] {len(recent_structures)}个结构活跃: "
            auto_context += ", ".join(
                f"Zone {s.zone.price_center:.0f}({s.motion.movement_type.value if s.motion and hasattr(s.motion, 'movement_type') else s.motion.phase_tendency if s.motion else '?'})"
                for s in recent_structures[:3]
            )

        col_a, col_b = st.columns([1, 1])
        with col_a:
            entry_type = st.selectbox(
                "记录类型",
                ["结构观察", "交易想法", "复盘总结", "疑问待解", "其他"],
                index=0,
            )
        with col_b:
            sentiment = st.selectbox(
                "倾向判断",
                ["偏多 📈", "偏空 📉", "中性 ➡️", "不确定 ❓"],
                index=2,
            )

        if recent_structures:
            zone_options = ["不关联"] + [
                f"Zone {s.zone.price_center:.0f} ({s.cycle_count}次试探)"
                for s in recent_structures
            ]
            linked_zone = st.selectbox("关联结构", zone_options, index=0)
        else:
            linked_zone = "不关联"

        content = st.text_area(
            "日志内容",
            value="",
            height=180,
            placeholder=f"记录你的观察、判断、理由...\n\n自动上下文：{auto_context}",
        )

        tags_input = st.text_input("标签（逗号分隔）", placeholder="例如: 铜,关键区突破,需要验证")

        col_save, col_info = st.columns([1, 2])
        with col_save:
            if st.button("💾 保存日志", type="primary", use_container_width=True):
                if content.strip():
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "date": today,
                        "symbol": selected_symbol,
                        "symbol_name": ds_name,
                        "type": entry_type,
                        "sentiment": sentiment,
                        "linked_zone": linked_zone if linked_zone != "不关联" else "",
                        "content": content.strip(),
                        "tags": [t.strip() for t in tags_input.split(",") if t.strip()],
                        "structures_snapshot": [
                            {
                                "zone": s.zone.price_center,
                                "cycles": s.cycle_count,
                                "tendency": s.motion.phase_tendency if s.motion else "",
                                "movement_type": s.motion.movement_type.value if s.motion and hasattr(s.motion, 'movement_type') else "",
                                "flux": round(s.motion.conservation_flux, 2) if s.motion else 0,
                            }
                            for s in recent_structures[:5]
                        ],
                    }
                    with open(journal_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    st.success(f"✅ 已保存 · {entry_type} · {selected_symbol} · {today}")
                else:
                    st.warning("请输入日志内容")

        with col_info:
            st.caption(f"保存位置: `{journal_file}`")
            st.caption("JSONL 格式，每行一条记录，可用 Python/pandas 直接读取分析")

        if recent_structures:
            with st.expander("📋 当前编译上下文（自动记录）"):
                ctx_str = f"品种: {selected_symbol} ({ds_name})\n"
                ctx_str += f"数据: {bars[0].timestamp:%Y-%m-%d} → {bars[-1].timestamp:%Y-%m-%d}\n"
                ctx_str += f"结构: {len(recent_structures)} 个\n"
                for s in recent_structures[:5]:
                    m = s.motion
                    ctx_str += f"  Zone {s.zone.price_center:.0f}: {s.narrative_context or '?'}"
                    if m:
                        ctx_str += f" [{m.movement_type.value if hasattr(m, 'movement_type') else m.phase_tendency}, 通量{m.conservation_flux:+.2f}]"
                    ctx_str += "\n"
                st.code(ctx_str, language="text")

    # ════════════════════════════════════════════════════════
    # 知识图谱分析 — 品种知识图谱 + 跨品种影响
    # ════════════════════════════════════════════════════════
    with sub_tab_kg:
        st.markdown("**📚 知识图谱分析** — 品种知识图谱 + 跨品种影响 + 传导链")
        st.caption("基于 config/products/ 配置，展示品种的核心实体、关系、传导链和跨品种影响")

        try:
            from src.workbench.kg_helper import (
                get_product_knowledge, get_cross_variety_impacts, get_chain_peers_from_kg,
                get_key_relations, get_key_chains, get_polarity_reference, generate_knowledge_summary
            )

            # 品种选择
            kg_col1, kg_col2 = st.columns([2, 1])
            with kg_col1:
                kg_symbol = st.selectbox(
                    "选择品种",
                    [selected_symbol] + [c for c in ctx.get("compare_codes", [])],
                    key="kg_symbol_select"
                )
            with kg_col2:
                if st.button("🔄 刷新知识图谱", key="refresh_kg"):
                    st.rerun()

            # 获取知识图谱数据
            knowledge = get_product_knowledge(kg_symbol)

            if "error" in knowledge:
                st.warning(f"⚠️ {knowledge['error']}")
                st.info("请确认 config/products/ 目录下有该品种的配置文件")
            else:
                # 概览
                st.markdown("---")
                st.markdown(f"#### 📊 {kg_symbol} 知识图谱概览")

                kg_stat_cols = st.columns(5)
                kg_stat_cols[0].metric("实体", len(knowledge.get("entities", [])))
                kg_stat_cols[1].metric("关系", len(knowledge.get("relations", [])))
                kg_stat_cols[2].metric("传导链", len(knowledge.get("chains", [])))
                kg_stat_cols[3].metric("极值项", len(knowledge.get("polarity", {})))
                kg_stat_cols[4].metric("定价模型", len(knowledge.get("pricing_models", [])))

                # 核心关系
                st.markdown("---")
                st.markdown("#### 🔗 核心关系")
                key_relations = get_key_relations(kg_symbol, limit=8)
                for r in key_relations:
                    r_from = r.get("from", "")
                    r_to = r.get("to", "")
                    r_type = r.get("type", "")
                    strength = r.get("strength", 0)
                    direction = r.get("direction", "")
                    desc = r.get("description", "")[:80]

                    strength_color = "#4caf50" if strength >= 0.7 else "#ff9800" if strength >= 0.5 else "#999"
                    dir_icon = "→" if direction == "正向" else "←" if direction == "反向" else "↔"

                    st.markdown(f"""
                    <div style="border-left:3px solid {strength_color};padding:6px 10px;margin:4px 0;
                                background:#f8f9fa;border-radius:4px">
                        <b>{r_from}</b> {dir_icon} <b>{r_to}</b>
                        <span style="color:{strength_color};font-weight:600;margin-left:8px">{strength:.0%}</span>
                        <span style="color:#6c757d;margin-left:8px">{r_type}</span>
                        <div style="font-size:0.82em;color:#6c757d;margin-top:2px">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # 传导链
                st.markdown("---")
                st.markdown("#### ⛓️ 传导链")
                chains = get_key_chains(kg_symbol, limit=3)
                for c in chains:
                    name = c.get("name", "")
                    trigger = c.get("triggerEvent", "")
                    domain = c.get("domain", "")
                    steps = c.get("steps", [])

                    with st.expander(f"⛓️ {name} ({domain})", expanded=False):
                        st.markdown(f"**触发条件**: {trigger}")
                        st.markdown("**传导步骤**:")
                        for step in steps:
                            seq = step.get("seq", "")
                            from_node = step.get("from", "")
                            to_node = step.get("to", "")
                            confidence = step.get("confidence", "")
                            lag = step.get("lag", "")
                            mechanism = step.get("mechanism", "")
                            st.markdown(f"  {seq}. **{from_node}** → **{to_node}**")
                            st.caption(f"     置信度: {confidence} · 时滞: {lag} · 机制: {mechanism}")

                        reversal = c.get("reversalCondition", "")
                        if reversal:
                            st.info(f"🔄 反转条件: {reversal}")

                # 跨品种影响
                st.markdown("---")
                st.markdown("#### 🌐 跨品种影响")
                impacts = get_cross_variety_impacts(kg_symbol)

                if impacts:
                    # 按类型分组
                    impact_groups = {}
                    for r in impacts:
                        r_type = r.get("type", "其他")
                        impact_groups.setdefault(r_type, []).append(r)

                    for group_name, group_items in impact_groups.items():
                        st.markdown(f"**{group_name}** ({len(group_items)} 条)")
                        for r in group_items[:3]:
                            r_from = r.get("from", "")
                            r_to = r.get("to", "")
                            strength = r.get("strength", 0)
                            desc = r.get("description", "")[:60]
                            st.markdown(f"  - {r_from} → {r_to} (强度{strength:.0%}): {desc}")
                else:
                    st.caption("暂无跨品种影响数据")

                # 产业链同链品种
                st.markdown("---")
                st.markdown("#### 🔗 产业链关联品种")
                peers = get_chain_peers_from_kg(kg_symbol)
                if peers:
                    peer_cols = st.columns(min(len(peers), 6))
                    for i, peer in enumerate(peers[:6]):
                        with peer_cols[i % len(peer_cols)]:
                            if st.button(f"📊 {peer}", key=f"kg_peer_{peer}", use_container_width=True):
                                st.session_state["kg_symbol_select"] = peer
                                st.rerun()
                else:
                    st.caption("暂无产业链关联数据")

                # 极值参考
                polarity = get_polarity_reference(kg_symbol)
                if polarity:
                    st.markdown("---")
                    st.markdown("#### 📏 极值参考")
                    for var_name, var_info in polarity.items():
                        hist_min = var_info.get("historicalMin", "—")
                        hist_max = var_info.get("historicalMax", "—")
                        recent_min = var_info.get("recentMin", "—")
                        recent_max = var_info.get("recentMax", "—")
                        patterns = var_info.get("reversalSignalPatterns", [])

                        with st.expander(f"📏 {var_name}", expanded=False):
                            pc1, pc2 = st.columns(2)
                            with pc1:
                                st.metric("历史区间", f"{hist_min} ~ {hist_max}")
                            with pc2:
                                st.metric("近期区间", f"{recent_min} ~ {recent_max}")
                            if patterns:
                                st.markdown("**反转信号模式**:")
                                for p in patterns:
                                    st.markdown(f"  - {p}")

                # 生成文字摘要
                st.markdown("---")
                st.markdown("#### 📝 知识图谱摘要")
                summary = generate_knowledge_summary(kg_symbol)
                st.markdown(summary)

        except Exception as ex:
            st.error(f"知识图谱加载失败: {ex}")
            import traceback
            st.code(traceback.format_exc())

    # ════════════════════════════════════════════════════════
    # 活动日志 — 自动沉淀的扫描/检索/对比结果
    # ════════════════════════════════════════════════════════
    with sub_tab_activity:
        st.markdown("**📊 活动日志** — 扫描、检索、对比的结果自动沉淀")
        st.caption("每次全市场扫描、历史检索、合约检索的结果自动记录，形成可回溯的研究轨迹")

        try:
            from src.workbench.activity_log import ActivityLog
            act_log = ActivityLog()
            stats = act_log.get_stats()

            if stats["total"] == 0:
                st.info("暂无活动记录 — 使用「今天值得关注」「历史对照」「合约检索」后，结果会自动保存到这里")
            else:
                # 统计概要
                stat_cols = st.columns(4)
                stat_cols[0].metric("总记录", stats["total"])
                type_labels = {"scan": "扫描", "retrieval": "检索", "compare": "对比",
                               "contract": "合约", "insight": "洞察"}
                for i, (t, label) in enumerate(type_labels.items()):
                    count = stats.get("by_type", {}).get(t, 0)
                    if count > 0 and i < 3:
                        stat_cols[i + 1].metric(label, count)

                # 筛选
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    act_types = list(stats.get("by_type", {}).keys())
                    f_type = st.selectbox("类型", ["全部"] + act_types, key="act_f_type")
                with f_col2:
                    act_syms = list(stats.get("by_symbol", {}).keys())[:15]
                    f_sym = st.selectbox("品种", ["全部"] + act_syms, key="act_f_sym")
                with f_col3:
                    f_days = st.selectbox("时间", [7, 14, 30, 90], index=1, key="act_f_days")

                entries = act_log.search(
                    symbol=f_sym if f_sym != "全部" else None,
                    type=f_type if f_type != "全部" else None,
                    days=f_days,
                    limit=30,
                )

                st.caption(f"最近 {f_days} 天 · {len(entries)} 条记录")

                # 类型图标
                type_icons = {
                    "scan": "📡", "retrieval": "🔍", "compare": "📊",
                    "contract": "🔎", "insight": "💡",
                }

                for e in entries:
                    icon = type_icons.get(e.type, "📝")
                    type_label = type_labels.get(e.type, e.type)
                    header = f"{icon} {e.date} · {type_label}"
                    if e.symbol:
                        header += f" · {e.symbol}"

                    with st.expander(f"{header} — {e.summary[:60]}", expanded=False):
                        st.markdown(f"**{e.summary}**")
                        st.caption(f"时间: {e.timestamp[:19]} · 标签: {', '.join(e.tags)}")

                        # 按类型展示详情
                        d = e.details
                        if e.type == "scan" and "top10" in d:
                            st.markdown("**Top 10 机会：**")
                            for j, r in enumerate(d["top10"]):
                                dir_icon = "📈" if r.get("direction") == "up" else "📉" if r.get("direction") == "down" else "➡️"
                                st.markdown(f"  {j+1}. {dir_icon} {r['symbol']} Zone {r['zone_center']:.0f} "
                                           f"· {r.get('motion', '')} · 通量{r.get('flux', 0):+.2f} · {r.get('score', 0):.0f}分")

                        elif e.type == "retrieval" and "neighbors" in d:
                            st.markdown(f"**相似案例 ({d.get('neighbor_count', 0)} 个)：**")
                            for nb in d["neighbors"][:5]:
                                st.markdown(f"  - {nb.get('symbol', '')} {nb.get('period', '')} "
                                           f"· 相似度 {nb.get('similarity', 0):.2f} · {nb.get('direction', '')}")
                            if d.get("posterior"):
                                p = d["posterior"]
                                st.caption(f"后验: 10d均收益 {p.get('mean_ret_10d', 0):.2%} · "
                                          f"上涨概率 {p.get('prob_positive_10d', 0):.0%}")

                        elif e.type == "contract" and "structures" in d:
                            st.markdown(f"**K线 {d.get('bars_count', 0)} 根 · 结构：**")
                            for s in d["structures"]:
                                st.markdown(f"  - Zone {s.get('zone', 0):.0f} · {s.get('cycles', 0)}次试探 "
                                           f"· {s.get('motion', '')} · 通量{s.get('flux', 0):+.2f}")

                # 活动趋势图
                if len(stats.get("by_date", {})) >= 3:
                    st.markdown("---")
                    st.markdown("**📈 活动趋势**")
                    dates = sorted(stats["by_date"].keys())[-14:]
                    counts = [stats["by_date"][d] for d in dates]
                    import plotly.graph_objects as go
                    fig = go.Figure(go.Bar(x=dates, y=counts, marker_color="#4a90d9"))
                    fig.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0),
                                     xaxis_title="", yaxis_title="记录数")
                    st.plotly_chart(fig, use_container_width=True)

        except Exception as ex:
            st.warning(f"活动日志加载失败: {ex}")

    # ════════════════════════════════════════════════════════
    # 历史回顾
    # ════════════════════════════════════════════════════════
    with sub_tab_history:
        st.markdown("**浏览历史复盘记录**")

        if not journal_file.exists():
            st.info("暂无复盘记录，在「写日志」标签页开始记录")
        else:
            entries = []
            with open(journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

            if not entries:
                st.info("暂无复盘记录")
            else:
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    filter_symbols = list(set(e.get("symbol", "") for e in entries))
                    filter_sym = st.selectbox("品种筛选", ["全部"] + sorted(filter_symbols))
                with col_f2:
                    filter_types = list(set(e.get("type", "") for e in entries))
                    filter_type = st.selectbox("类型筛选", ["全部"] + sorted(filter_types))
                with col_f3:
                    filter_dates = sorted(set(e.get("date", "") for e in entries), reverse=True)
                    filter_date = st.selectbox("日期筛选", ["全部"] + filter_dates)

                filtered = entries
                if filter_sym != "全部":
                    filtered = [e for e in filtered if e.get("symbol") == filter_sym]
                if filter_type != "全部":
                    filtered = [e for e in filtered if e.get("type") == filter_type]
                if filter_date != "全部":
                    filtered = [e for e in filtered if e.get("date") == filter_date]

                filtered = list(reversed(filtered))

                st.caption(f"共 {len(filtered)} 条记录")

                for entry in filtered[:20]:
                    ts = entry.get("timestamp", "")
                    try:
                        dt = datetime.fromisoformat(ts)
                        time_str = dt.strftime("%m-%d %H:%M")
                    except Exception:
                        time_str = ts[:16]

                    sym = entry.get("symbol", "")
                    sym_name = entry.get("symbol_name", "")
                    etype = entry.get("type", "")
                    sentiment = entry.get("sentiment", "")
                    zone = entry.get("linked_zone", "")
                    content = entry.get("content", "")
                    tags = entry.get("tags", [])

                    if "偏多" in sentiment:
                        tag_cls = "tag-bullish"
                    elif "偏空" in sentiment:
                        tag_cls = "tag-bearish"
                    else:
                        tag_cls = "tag-neutral"

                    header_parts = [f"🕐 {time_str}", f"**{sym}** ({sym_name})", etype]
                    if zone:
                        header_parts.append(f"🔗 {zone}")
                    header = " · ".join(header_parts)

                    with st.expander(f"{time_str} | {sym} | {etype} | {sentiment}", expanded=False):
                        st.markdown(f"""
                        <div class="journal-entry">
                            <div class="entry-header">{header}</div>
                            <div class="entry-body">{content}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        if tags:
                            tags_html = " ".join(
                                f'<span class="journal-tag {tag_cls}">{t}</span>' for t in tags
                            )
                            st.markdown(tags_html, unsafe_allow_html=True)
                        snapshot = entry.get("structures_snapshot", [])
                        if snapshot:
                            snap_text = "当时结构: " + ", ".join(
                                f"Zone {s['zone']:.0f}({s['tendency']}, 通量{s['flux']:+.2f})"
                                for s in snapshot
                            )
                            st.caption(snap_text)

                st.markdown("---")
                col_export1, col_export2 = st.columns(2)
                with col_export1:
                    if st.button("📥 导出为 Markdown"):
                        md_lines = [f"# 复盘日志导出 {today}\n"]
                        for e in filtered:
                            md_lines.append(f"## {e.get('date', '')} {e.get('symbol', '')} {e.get('type', '')}")
                            md_lines.append(f"倾向: {e.get('sentiment', '')}")
                            if e.get("linked_zone"):
                                md_lines.append(f"关联: {e['linked_zone']}")
                            md_lines.append(f"\n{e.get('content', '')}\n")
                            if e.get("tags"):
                                md_lines.append(f"标签: {', '.join(e['tags'])}")
                            md_lines.append("---\n")
                        export_path = log_dir / f"export_{today}.md"
                        export_path.write_text("\n".join(md_lines), encoding="utf-8")
                        st.success(f"已导出到 {export_path}")
                with col_export2:
                    st.caption(f"数据文件: `{journal_file}`")
