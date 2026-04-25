"""
Tab 1: 历史对照（主动拉取） — 精细检索条件 + 检索执行 + 结果展示 + 综合研判

从 app.py 提取的独立模块。
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import json
import time as _time

from src.data.loader import Bar
from src.data.symbol_meta import symbol_name
from src.compiler.pipeline import compile_full, CompilerConfig
from src.retrieval.similarity import similarity, INVARIANT_KEYS, INVARIANT_SCALES
from src.retrieval.progress import progress_retrieve

from src.workbench.shared import (
    motion_badge, TIER_COLORS, _extract_key, _price_vs_zone,
    make_candlestick, _invariant_diff_table, SENS_MAP,
)
from src.workbench.data_layer import load_bars, compile_structures


def render(ctx: dict):
    """渲染 Tab 1: 历史对照"""
    selected_symbol = ctx["selected_symbol"]
    bars = ctx["bars"]
    result = ctx["result"]
    recent_structures = ctx["recent_structures"]
    sens = ctx["sens"]
    ALL_SYMBOLS = ctx["ALL_SYMBOLS"]
    MYSQL_SYMBOLS = ctx["MYSQL_SYMBOLS"]
    CSV_SYMBOLS = ctx["CSV_SYMBOLS"]
    META = ctx["META"]
    ds_name = ctx["ds_name"]
    today = datetime.now().strftime("%Y-%m-%d")

    st.markdown("#### 🔍 历史对照 — 主动拉取比较")
    st.caption("从 MySQL/CSV 加载全量历史 → 编译 → 找最相似的历史段 → 对比详情")

    if not recent_structures:
        st.info("📡 当前时间范围内没有显著结构 — 试试侧栏扩大时间范围或降低灵敏度")
    else:
        # ── 选择要查询的结构 ──
        col_sel, col_params = st.columns([1, 1])
        with col_sel:
            options = [f"Zone {s.zone.price_center:.0f} ({s.cycle_count}次, "
                       f"{s.narrative_context or '?'})"
                       for s in recent_structures]
            sel = st.selectbox("选择当前结构", options, index=0)
            idx = options.index(sel)
            query_st = recent_structures[idx]

        with col_params:
            search_years = st.slider("历史检索范围（年）", 1, 10, 3)
            top_k = st.slider("返回案例数", 3, 20, 8)

        # ── 检索颗粒度 ──
        col_gran, col_scope, col_btn = st.columns([1, 2, 1])
        with col_gran:
            search_granularity = st.select_slider(
                "检索颗粒度",
                options=["粗粒度", "中等", "细粒度"],
                value="细粒度",
                help="粗粒度=只匹配大结构(高振幅/长周期)，细粒度=捕捉小波动结构",
            )
            search_sens_map = {
                "粗粒度": {"min_amp": 0.06, "min_dur": 6, "min_cycles": 3},
                "中等":   {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2},
                "细粒度": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2},
            }
            search_sens = search_sens_map[search_granularity]

        with col_scope:
            search_scope = st.radio(
                "检索范围",
                ["仅当前品种", "全品种（MySQL + CSV）"],
                horizontal=True,
                help="全品种模式会加载所有可用品种的历史数据进行对比",
            )
            is_cross_symbol = "全品种" in search_scope

        # ── 精细检索条件 ──
        with st.expander("🎛️ 精细检索条件（可选）", expanded=False):
            fin_col1, fin_col2, fin_col3 = st.columns(3)

            with fin_col1:
                date_col1, date_col2 = st.columns(2)
                with date_col1:
                    search_date_start = st.date_input(
                        "起始日期",
                        value=datetime.now().date() - timedelta(days=search_years * 365),
                        key="search_date_start",
                    )
                with date_col2:
                    search_date_end = st.date_input(
                        "结束日期",
                        value=datetime.now().date(),
                        key="search_date_end",
                    )
                search_zone_range = st.slider(
                    "Zone 价位范围",
                    min_value=0.0, max_value=100000.0,
                    value=(0.0, 100000.0),
                    step=100.0,
                    key="search_zone_range",
                    help="筛选 Zone price_center 在此范围内的案例",
                )

            with fin_col2:
                search_dir_filter = st.multiselect(
                    "方向筛选",
                    ["📈 上涨(up)", "📉 下跌(down)", "➡️ 不明(unclear)"],
                    default=[],
                    key="search_dir_filter",
                    help="只看指定方向的案例，留空=全部",
                )
                search_contrast_filter = st.multiselect(
                    "反差类型",
                    ["恐慌(panic)", "过剩(oversupply)", "政策(policy)",
                     "流动性(liquidity)", "投机(speculation)", "未知(unknown)"],
                    default=[],
                    key="search_contrast_filter",
                    help="筛选 zone.context_contrast 类型",
                )
                search_motion_filter = st.multiselect(
                    "运动状态",
                    ["🔻 破缺(→breakout)", "✅ 确认(→confirmation)",
                     "⚖️ 稳定(stable)", "🔄 形成中(forming)"],
                    default=[],
                    key="search_motion_filter",
                    help="筛选结构的 phase_tendency",
                )

            with fin_col3:
                search_min_sim = st.slider(
                    "最小相似度",
                    min_value=0.0, max_value=1.0,
                    value=0.0, step=0.05,
                    key="search_min_sim",
                    help="过滤掉相似度低于此值的案例",
                )
                search_sort_by = st.radio(
                    "结果排序",
                    ["按相似度", "按后续涨幅", "按日期"],
                    key="search_sort_by",
                    help="选择检索结果的排序方式",
                )

        with col_btn:
            run_search = st.button("🚀 开始检索", type="primary", use_container_width=True)

        # 当前结构概要
        m = query_st.motion
        p = query_st.projection
        flux_str = f"{m.conservation_flux:+.2f}" if m else "—"
        tendency_str = m.phase_tendency if m else "—"
        st.markdown(f"""
        **当前结构** · Zone {query_st.zone.price_center:.0f} (±{query_st.zone.bandwidth:.0f})
        · {query_st.cycle_count}次试探 · {query_st.narrative_context or '?'}
        · 运动: {tendency_str} · 通量: {flux_str}
        """)

        # ── 执行检索 ──
        if run_search:
            search_symbols = ALL_SYMBOLS if is_cross_symbol else [selected_symbol]
            all_candidates = []
            total_syms = len(search_symbols)
            _t0 = _time.time()

            progress = st.progress(0, text=f"准备检索 {total_syms} 个品种...")

            for si, sym in enumerate(search_symbols):
                elapsed = _time.time() - _t0
                if si > 0:
                    eta = elapsed / si * (total_syms - si)
                    time_text = f"⏱️ 已用 {elapsed:.0f}s · 预估剩余 {eta:.0f}s"
                else:
                    time_text = "⏱️ 启动中..."
                progress.progress(
                    si / max(total_syms, 1),
                    text=f"[{si+1}/{total_syms}] {sym} ({symbol_name(sym)}) · {time_text}"
                )

                sym_bars = load_bars(sym)
                if not sym_bars or len(sym_bars) < 30:
                    continue

                sym_config = CompilerConfig(
                    min_amplitude=search_sens["min_amp"],
                    min_duration=search_sens["min_dur"],
                    min_cycles=search_sens["min_cycles"],
                    adaptive_pivots=True, fractal_threshold=0.34,
                )
                sym_result = compile_full(sym_bars, sym_config, symbol=sym)
                if not sym_result.structures:
                    continue

                for hs in sym_result.structures:
                    if sym == selected_symbol and hs is query_st:
                        continue
                    if sym == selected_symbol:
                        if hs.t_end and query_st.t_start and hs.t_end >= query_st.t_start:
                            continue

                    sc = similarity(query_st, hs)

                    direction, move = "unclear", 0.0
                    if hs.t_end:
                        outcome_start = hs.t_end + timedelta(days=3)
                        outcome_end = outcome_start + timedelta(days=30)
                        future = [b for b in sym_bars if outcome_start <= b.timestamp <= outcome_end]
                        if future:
                            start_p = future[0].open
                            if start_p > 0:
                                peak = max(b.high for b in future)
                                trough = min(b.low for b in future)
                                up = (peak - start_p) / start_p
                                down = (start_p - trough) / start_p
                                direction = "up" if up >= down else "down"
                                move = max(up, down)

                    all_candidates.append({
                        "structure": hs,
                        "score": sc,
                        "direction": direction,
                        "move": move,
                        "symbol": sym,
                        "symbol_name": symbol_name(sym),
                        "period_start": hs.t_start.strftime("%Y-%m-%d") if hs.t_start else "",
                        "period_end": hs.t_end.strftime("%Y-%m-%d") if hs.t_end else "",
                    })

            progress.progress(0.95, text="应用精细筛选...")

            # ── 应用精细筛选 ──
            filtered_candidates = []
            _min_sim = st.session_state.get("search_min_sim", 0.0)
            _d_start = st.session_state.get("search_date_start")
            _d_end = st.session_state.get("search_date_end")
            _zr = st.session_state.get("search_zone_range", (0.0, 100000.0))
            _dir_f_raw = st.session_state.get("search_dir_filter", [])
            _contrast_f_raw = st.session_state.get("search_contrast_filter", [])
            _motion_f_raw = st.session_state.get("search_motion_filter", [])

            _dir_f = [_extract_key(v) for v in _dir_f_raw]
            _contrast_f = [_extract_key(v) for v in _contrast_f_raw]
            _motion_f = [_extract_key(v) for v in _motion_f_raw]

            for c in all_candidates:
                hs = c["structure"]
                if c["score"].total < _min_sim:
                    continue
                if hs.t_start:
                    d = hs.t_start.date()
                    if _d_start and d < _d_start:
                        continue
                    if _d_end and d > _d_end:
                        continue
                if not (_zr[0] <= hs.zone.price_center <= _zr[1]):
                    continue
                if _dir_f and c["direction"] not in _dir_f:
                    continue
                if _contrast_f:
                    hs_contrast = hs.zone.context_contrast.value if hs.zone else ""
                    if hs_contrast not in _contrast_f:
                        continue
                if _motion_f:
                    hs_motion = hs.motion.phase_tendency if hs.motion else ""
                    if hs_motion not in _motion_f:
                        continue
                filtered_candidates.append(c)

            all_candidates = filtered_candidates

            _sort_by = st.session_state.get("search_sort_by", "按相似度")
            if _sort_by == "按相似度":
                all_candidates.sort(key=lambda c: c["score"].total, reverse=True)
            elif _sort_by == "按后续涨幅":
                all_candidates.sort(key=lambda c: c["move"], reverse=True)
            elif _sort_by == "按日期":
                all_candidates.sort(key=lambda c: c["structure"].t_start or datetime.min, reverse=True)

            progress.progress(1.0, text=f"✅ 检索完成 · {_time.time() - _t0:.1f}s · {len(all_candidates)} 个匹配")
            top_cases = all_candidates[:top_k]

            # v3.1: 自动保存检索结果到活动日志
            if top_cases:
                try:
                    from src.workbench.activity_log import ActivityLog
                    _neighbors = []
                    for c in top_cases[:10]:
                        _neighbors.append({
                            "symbol": c.get("symbol", ""),
                            "period": f"{c.get('period_start', '')}~{c.get('period_end', '')}",
                            "similarity": round(c.get("similarity", 0), 4),
                            "direction": c.get("direction", ""),
                            "outcome": round(c.get("outcome_move", 0), 4),
                        })
                    ActivityLog().save_retrieval(
                        symbol=selected_symbol,
                        query_zone=query_st.zone.price_center,
                        neighbors=_neighbors,
                        search_window=f"{search_date_start}~{search_date_end}",
                    )
                except Exception:
                    pass

            if top_cases:
                sym_distribution = {}
                for c in top_cases:
                    s = c["symbol"]
                    sym_distribution[s] = sym_distribution.get(s, 0) + 1

                st.markdown("---")
                scope_label = f"全品种 {len(search_symbols)} 个" if is_cross_symbol else selected_symbol
                st.markdown(f"**找到 {len(top_cases)} 个历史相似案例**（检索范围: {scope_label} · 颗粒度: {search_granularity}）")

                if is_cross_symbol and len(sym_distribution) > 1:
                    dist_text = " · ".join(
                        f"**{s}**({symbol_name(s)}) ×{n}"
                        for s, n in sorted(sym_distribution.items(), key=lambda x: -x[1])
                    )
                    st.caption(f"来源分布: {dist_text}")

                up_cases = [c for c in top_cases if c["direction"] == "up"]
                down_cases = [c for c in top_cases if c["direction"] == "down"]
                all_moves = [c["move"] for c in top_cases if c["move"] > 0]
                n = len(top_cases)

                stat_cols = st.columns(6)
                stat_cols[0].metric("总案例", n)
                stat_cols[1].metric("上涨", f"{len(up_cases)} ({len(up_cases)/n:.0%})")
                stat_cols[2].metric("下跌", f"{len(down_cases)} ({len(down_cases)/n:.0%})")
                if up_cases:
                    avg_up = sum(c["move"] for c in up_cases) / len(up_cases)
                    stat_cols[3].metric("平均涨幅", f"{avg_up:.1%}")
                if down_cases:
                    avg_down = sum(c["move"] for c in down_cases) / len(down_cases)
                    stat_cols[4].metric("平均跌幅", f"{avg_down:.1%}")
                if all_moves:
                    median_move = sorted(all_moves)[len(all_moves) // 2]
                    stat_cols[5].metric("中位数收益", f"{median_move:.1%}")

                # ── 实时过滤控件 ──
                st.markdown("---")
                rt_col1, rt_col2 = st.columns(2)
                with rt_col1:
                    rt_dir_filter = st.multiselect(
                        "🔎 按方向筛选显示",
                        ["📈 上涨(up)", "📉 下跌(down)", "➡️ 不明(unclear)"],
                        default=[],
                        key="rt_dir_filter",
                    )
                with rt_col2:
                    rt_sort = st.selectbox(
                        "🔃 按相似度排序",
                        ["相似度降序", "相似度升序"],
                        key="rt_sort",
                    )

                display_cases = top_cases
                if rt_dir_filter:
                    rt_dir_keys = [_extract_key(v) for v in rt_dir_filter]
                    display_cases = [c for c in display_cases if c["direction"] in rt_dir_keys]
                if rt_sort == "相似度升序":
                    display_cases = sorted(display_cases, key=lambda c: c["score"].total)

                st.markdown("---")

                for i, case in enumerate(display_cases):
                    hs = case["structure"]
                    sc = case["score"]
                    direction = case["direction"]
                    move = case["move"]
                    case_sym = case["symbol"]
                    case_sym_name = case["symbol_name"]

                    direction_icon = "📈" if direction == "up" else "📉" if direction == "down" else "➡️"

                    contrast_val = hs.zone.context_contrast.value if hs.zone else ""
                    motion_val = hs.motion.phase_tendency if hs.motion else ""
                    tag_parts = []
                    if contrast_val:
                        tag_parts.append(f"[{contrast_val}]")
                    if motion_val:
                        tag_parts.append(f"[{motion_val}]")
                    tag_str = " ".join(tag_parts) + " " if tag_parts else ""

                    sym_tag = f"[{case_sym}] " if is_cross_symbol else ""
                    with st.expander(
                        f"{direction_icon} #{i+1}  {sym_tag}{tag_str}"
                        f"{hs.t_start:%Y-%m-%d} ~ {hs.t_end:%Y-%m-%d}  "
                        f"相似度 {sc.total:.0%}  "
                        f"后续{'涨' if direction=='up' else '跌' if direction=='down' else '横'}{move:.1%}",
                        expanded=(i == 0),
                    ):
                        col_left, col_right = st.columns([1, 1])

                        with col_left:
                            st.markdown("**不变量对比**")
                            diff_df = _invariant_diff_table(
                                query_st.invariants or {},
                                hs.invariants or {},
                                "当前", f"历史({case_sym})",
                            )
                            st.dataframe(diff_df, hide_index=True, use_container_width=True)

                        with col_right:
                            st.markdown("**相似度分层**")
                            sim_cols = st.columns(2)
                            sim_cols[0].metric("几何", f"{sc.geometric:.0%}")
                            sim_cols[1].metric("关系", f"{sc.relational:.0%}")

                            st.markdown("**结构特征**")
                            st.caption(f"品种: {case_sym} ({case_sym_name})\n\n"
                                      f"Cycle: {hs.cycle_count} · "
                                      f"SR: {hs.avg_speed_ratio:.2f} · "
                                      f"TR: {hs.avg_time_ratio:.2f} · "
                                      f"BW: {hs.zone.relative_bandwidth:.3f}")

                            if contrast_val or motion_val:
                                st.markdown(f"**反差类型**: {contrast_val or '—'} · "
                                           f"**运动状态**: {motion_val or '—'}")

                            if direction != "unclear":
                                st.markdown(f"**后续走势**: {direction} {move:.1%}")

                        if hs.t_start and hs.t_end:
                            case_bars = load_bars(case_sym)
                            margin = timedelta(days=15)
                            hist_bars = [b for b in case_bars
                                        if hs.t_start - margin <= b.timestamp <= hs.t_end + margin]
                            if hist_bars:
                                fig = make_candlestick(hist_bars,
                                    title=f"{case_sym} {hs.t_start:%Y-%m-%d} ~ {hs.t_end:%Y-%m-%d}")
                                fig.add_hline(y=hs.zone.price_center, line_dash="dot",
                                             line_color="#4a90d9",
                                             annotation_text=f"Zone {hs.zone.price_center:.0f}")
                                fig.add_hrect(y0=hs.zone.lower, y1=hs.zone.upper,
                                             fillcolor="#4a90d9", opacity=0.08, line_width=0)
                                st.plotly_chart(fig, use_container_width=True)

                # ── 综合研判 ──
                st.markdown("---")
                st.markdown("#### 📋 综合研判")

                if len(up_cases) > len(down_cases):
                    st.success(f"**偏多**：{len(up_cases)}/{n} 个历史案例后续上涨，"
                              f"平均涨幅 {sum(c['move'] for c in up_cases)/len(up_cases):.1%}")
                elif len(down_cases) > len(up_cases):
                    st.error(f"**偏空**：{len(down_cases)}/{n} 个历史案例后续下跌，"
                            f"平均跌幅 {sum(c['move'] for c in down_cases)/len(down_cases):.1%}")
                else:
                    st.warning(f"**分歧**：上涨 {len(up_cases)} / 下跌 {len(down_cases)}，方向不明")

                if is_cross_symbol and len(sym_distribution) > 1:
                    st.markdown("---")
                    st.markdown("#### 🔗 跨品种洞察")
                    for sym, count in sym_distribution.items():
                        sym_cases = [c for c in top_cases if c["symbol"] == sym]
                        sym_up = sum(1 for c in sym_cases if c["direction"] == "up")
                        sym_down = sum(1 for c in sym_cases if c["direction"] == "down")
                        avg_sim = sum(c["score"].total for c in sym_cases) / len(sym_cases)
                        st.markdown(
                            f"**{sym} ({symbol_name(sym)})** × {count} 例 · "
                            f"平均相似度 {avg_sim:.0%} · "
                            f"📈{sym_up} / 📉{sym_down}"
                        )

                # ── 候选剧本（结构进度检索）──
                st.markdown("---")
                st.markdown("#### 🎬 候选剧本 — 历史前半程后续走势")

                try:
                    all_hist_structures = []
                    for sym in list(sym_distribution.keys()) if is_cross_symbol else [selected_symbol]:
                        sym_bars = load_bars(sym)
                        _, sym_result = compile_structures(
                            sym, sens["min_amp"], sens["min_dur"], sens["min_cycles"]
                        )
                        if sym_result:
                            all_hist_structures.extend(sym_result.structures)

                    playbook, pb_cases = progress_retrieve(
                        query=query_st,
                        history_structures=all_hist_structures,
                        history_bars=bars,
                        after_window=120,
                        min_similarity=0.2,
                        top_k=15,
                    )

                    if playbook.n_matches > 0:
                        # 方向指示
                        if playbook.direction == "bullish":
                            st.success(f"**{playbook.summary}**")
                        elif playbook.direction == "bearish":
                            st.error(f"**{playbook.summary}**")
                        else:
                            st.warning(f"**{playbook.summary}**")

                        # 关键指标
                        pb_cols = st.columns(5)
                        pb_cols[0].metric("匹配数", f"{playbook.n_matches}")
                        pb_cols[1].metric("上涨概率", f"{playbook.prob_up:.0%}")
                        pb_cols[2].metric("中位收益", f"{playbook.median_move:+.1%}")
                        pb_cols[3].metric("兑现天数", f"{playbook.median_days}天")
                        pb_cols[4].metric("置信度", playbook.confidence)

                        # 匹配案例展开
                        with st.expander(f"📂 查看 {len(pb_cases)} 个历史前半程案例", expanded=False):
                            for i, c in enumerate(pb_cases[:8]):
                                dir_icon = "📈" if c.after_direction == "up" else "📉" if c.after_direction == "down" else "➡️"
                                st.markdown(
                                    f"{dir_icon} **#{i+1}** {c.period} · "
                                    f"zone={c.zone_center:.0f} · cycles={c.cycle_count} · "
                                    f"sim={c.similarity.total:.0%} · "
                                    f"后半程: {c.after_direction} {c.after_move:+.1%} ({c.after_days}天) · "
                                    f"max涨{c.after_max_rise:+.1%}/max跌{c.after_max_dd:.1%}"
                                )
                                st.caption(f"匹配原因: {c.match_reason}")
                    else:
                        st.info("📋 无足够相似的历史前半程案例，无法生成候选剧本")

                except Exception as ex:
                    st.warning(f"候选剧本生成异常: {ex}")

                # ── 导出 & 录入 ──
                st.markdown("---")
                st.markdown("#### 📤 导出 & 录入")

                export_col1, export_col2, export_col3 = st.columns(3)

                with export_col1:
                    # 导出为 JSON
                    export_data = {
                        "query": {
                            "symbol": selected_symbol,
                            "zone_center": query_st.zone.price_center,
                            "search_window": f"{search_date_start}~{search_date_end}",
                            "scope": scope_label,
                            "granularity": search_granularity,
                        },
                        "results": [{
                            "symbol": c["symbol"],
                            "period_start": c["period_start"],
                            "period_end": c["period_end"],
                            "similarity": round(c["score"].total, 4),
                            "sim_geometry": round(c["score"].geometric, 4),
                            "sim_relation": round(c["score"].relational, 4),
                            "sim_motion": round(c["score"].motion, 4),
                            "sim_family": round(c["score"].family, 4),
                            "direction": c["direction"],
                            "outcome_move": c["move"],
                            "outcome_days": c["days"],
                            "cycle_count": c["structure"].cycle_count,
                            "zone_center": c["structure"].zone.price_center,
                        } for c in top_cases],
                        "summary": {
                            "total": n,
                            "up": len(up_cases),
                            "down": len(down_cases),
                            "avg_up": round(sum(c["move"] for c in up_cases) / len(up_cases), 4) if up_cases else 0,
                            "avg_down": round(sum(c["move"] for c in down_cases) / len(down_cases), 4) if down_cases else 0,
                        },
                        "exported_at": datetime.now().isoformat(),
                    }
                    json_str = json.dumps(export_data, ensure_ascii=False, indent=2, default=str)
                    st.download_button(
                        "📥 导出 JSON",
                        data=json_str,
                        file_name=f"retrieval_{selected_symbol}_{query_st.zone.price_center:.0f}_{today}.json",
                        mime="application/json",
                        use_container_width=True,
                    )

                with export_col2:
                    # 导出为 Markdown
                    md_lines = [
                        f"# 检索结果: {selected_symbol} Zone {query_st.zone.price_center:.0f}",
                        f"日期: {today} · 范围: {scope_label} · 颗粒度: {search_granularity}",
                        "",
                        f"## 综合研判",
                        f"- 总案例: {n} · 上涨 {len(up_cases)} · 下跌 {len(down_cases)}",
                    ]
                    if up_cases:
                        md_lines.append(f"- 上涨平均涨幅: {sum(c['move'] for c in up_cases)/len(up_cases):.1%}")
                    if down_cases:
                        md_lines.append(f"- 下跌平均跌幅: {sum(c['move'] for c in down_cases)/len(down_cases):.1%}")
                    md_lines.append("")
                    md_lines.append("## 相似案例")
                    for i, c in enumerate(top_cases, 1):
                        md_lines.append(f"### #{i} {c['symbol']} {c['period_start']}~{c['period_end']}")
                        md_lines.append(f"- 相似度: {c['score'].total:.3f} (几何{c['score'].geometric:.2f} 关系{c['score'].relational:.2f} 运动{c['score'].motion:.2f})")
                        md_lines.append(f"- 方向: {c['direction']} · 后续 {c['move']:.1%} ({c['days']}天)")
                        md_lines.append(f"- Cycle数: {c['structure'].cycle_count} · Zone: {c['structure'].zone.price_center:.0f}")
                        md_lines.append("")
                    md_str = "\n".join(md_lines)
                    st.download_button(
                        "📥 导出 Markdown",
                        data=md_str,
                        file_name=f"retrieval_{selected_symbol}_{query_st.zone.price_center:.0f}_{today}.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )

                with export_col3:
                    # 录入样本库
                    if st.button("💾 录入样本库", use_container_width=True,
                                 help="将当前检索结果保存到 data/samples/library.jsonl，供后续检索使用"):
                        try:
                            from src.sample.store import SampleStore
                            sample_dir = Path("data/samples")
                            sample_dir.mkdir(parents=True, exist_ok=True)
                            store = SampleStore(str(sample_dir / "library.jsonl"))

                            recorded = 0
                            for c in top_cases[:20]:
                                hs = c["structure"]
                                sample_id = f"{selected_symbol}_{query_st.zone.price_center:.0f}_{today}_{recorded}"
                                store.append(
                                    symbol=selected_symbol,
                                    structure=hs,
                                    label_type=hs.label or "retrieval_match",
                                    label_phase=c["direction"],
                                    typicality=c["score"].total,
                                    annotation=f"检索匹配: {c['symbol']} {c['period_start']}~{c['period_end']} 相似度{c['score'].total:.2f}",
                                    forward_outcome={
                                        "direction": c["direction"],
                                        "move": c["move"],
                                        "days": c["days"],
                                    },
                                )
                                recorded += 1

                            st.success(f"✅ 已录入 {recorded} 个样本到样本库")
                        except Exception as ex:
                            st.error(f"录入失败: {ex}")

            else:
                st.warning("🔍 匹配不足 — 试试：① 降低「最小相似度」阈值 ② 切换到「粗粒度」③ 扩大检索范围到「全品种」④ 增加历史检索年数")
