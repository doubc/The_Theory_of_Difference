"""
Tab 0: 今天值得关注什么 — 全市场机会扫描、今日三选、跨品种一致性、每日变化报告

从 app.py 提取的独立模块。
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
import json

from src.data.loader import Bar
from src.data.symbol_meta import symbol_name, symbol_description
from src.compiler.pipeline import compile_full, CompilerConfig
from src.quality import assess_quality, QualityTier
from src.retrieval.progress import progress_retrieve

from src.workbench.shared import (
    motion_badge, TIER_COLORS, _extract_key, _price_vs_zone,
    make_candlestick, SENS_MAP,
)
from src.workbench.data_layer import load_bars, compile_structures


def _judgment_html(j: dict | None) -> str:
    """定性判断 → HTML 片段"""
    if not j:
        return ""
    icon = j.get("icon", "")
    stage = j.get("stage", "")
    detail = j.get("detail", "")
    conf = j.get("confidence", 0)
    # 颜色：上行绿、下行红、反转橙、震荡黄、其他灰
    color = "#4caf50" if "趋势上行" in stage else \
            "#ef5350" if "趋势下行" in stage or "突破失败" in stage else \
            "#ff9800" if "反转" in stage else \
            "#ffc107" if "震荡" in stage or "高波动" in stage else \
            "#999"
    return f'<span style="color:{color};font-weight:600">{icon} {stage}</span> <span style="color:#888;font-size:0.85em">({detail}·{conf:.0%})</span>'


def render(ctx: dict):
    """渲染 Tab 0: 今天值得关注什么"""
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

    st.markdown("#### 📡 今天值得关注什么")
    st.caption("有什么结构在形成、在确认、或正在破缺")

    # ── 全市场机会扫描 ──
    @st.cache_data(ttl=300)
    def _scan_all_symbols(sens_key: str) -> list[dict]:
        """
        扫描所有品种，返回按关注度排序的 Top 机会列表。

        v3.1 修复：
        - 只加载最近 N 天数据（避免全量历史导致旧结构上榜）
        - 只保留最近 30 天内仍有活动的结构
        - 排序加入 recency 权重
        """
        from datetime import timedelta
        _sens = {
            "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3, "lookback_days": 240},
            "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2, "lookback_days": 180},
            "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2, "lookback_days": 120},
        }
        _s = _sens.get(sens_key, _sens["标准"])
        lookback = _s["lookback_days"]
        recency_cutoff_days = 30  # 结构必须在最近 N 天内有活动

        now = datetime.now()
        results = []
        for sym in ALL_SYMBOLS:
            bars_data = load_bars(sym)
            if not bars_data or len(bars_data) < 30:
                continue

            # 只取最近 lookback 天的数据
            if len(bars_data) > lookback:
                bars_data = bars_data[-lookback:]

            cfg = CompilerConfig(
                min_amplitude=_s["min_amp"], min_duration=_s["min_dur"],
                min_cycles=_s["min_cycles"],
                adaptive_pivots=True, fractal_threshold=0.34,
            )
            cr = compile_full(bars_data, cfg, symbol=sym)
            if not cr.ranked_structures:
                continue

            last_price = bars_data[-1].close
            last_ts = bars_data[-1].timestamp

            for idx_s, s in enumerate(cr.ranked_structures[:5]):
                # 只保留最近 recency_cutoff_days 内有活动的结构
                if s.t_end and (last_ts - s.t_end).days > recency_cutoff_days:
                    continue

                m = s.motion
                p = s.projection
                # v3.2: 修复索引错位 — 使用结构对象查找对应的 SystemState
                ss = cr.get_system_state_for(s)
                qa = assess_quality(s, ss)
                score_100 = round(qa.score * 100, 1)

                direction = "unclear"
                if m and "breakout" in m.phase_tendency:
                    direction = "down" if m.conservation_flux < 0 else "up"
                elif m and "confirmation" in m.phase_tendency:
                    direction = "up" if m.conservation_flux > 0 else "down"

                suggestions = []
                if direction == "up":
                    suggestions.append(f"观察价格突破 Zone 上沿 {s.zone.price_center + s.zone.bandwidth:.0f} 后的放量情况")
                elif direction == "down":
                    suggestions.append(f"观察价格跌破 Zone 下沿 {s.zone.price_center - s.zone.bandwidth:.0f} 后的反抽力度")
                else:
                    suggestions.append("方向不明，等待明确信号再介入研究")
                if m and "breakout" in m.phase_tendency:
                    suggestions.append("处于破缺阶段，关注是否能稳住在新价位")
                if p and p.is_blind:
                    suggestions.append("高压缩结构，突破后波动可能放大，注意节奏")
                for rec in qa.recommendations[:2]:
                    suggestions.append(f"📋 {rec}")

                if qa.tier == QualityTier.A:
                    risk_level = "高"
                    risk_pct = "5-8%"
                elif qa.tier == QualityTier.B:
                    risk_level = "中"
                    risk_pct = "3-5%"
                else:
                    risk_level = "低"
                    risk_pct = "1-3%"

                # recency score: 越近越高 (0~1)
                days_since_end = (last_ts - s.t_end).days if s.t_end else recency_cutoff_days
                recency = max(0, 1.0 - days_since_end / recency_cutoff_days)

                # v4.0: 生成交易信号
                from src.signals import generate_signal
                signal = generate_signal(s, bars_data, ss, quality_tier_override=qa.tier.value)

                # 定性判断
                from src.relations import qualitative_judgment
                dir_for_judgment = {"up": "long", "down": "short"}.get(direction)
                judgment = qualitative_judgment(s, m, signal, direction=dir_for_judgment)

                results.append({
                    "symbol": sym,
                    "symbol_name": symbol_name(sym),
                    "zone_center": s.zone.price_center,
                    "zone_bw": s.zone.bandwidth,
                    "cycles": s.cycle_count,
                    "motion": m.phase_tendency if m else "—",
                    "flux": round(m.conservation_flux, 2) if m else 0,
                    "score": score_100,
                    "tier": qa.tier.value,
                    "direction": direction,
                    "is_blind": p.is_blind if p else False,
                    "contrast": s.zone.context_contrast.value if s.zone else "",
                    "narrative": s.narrative_context or "",
                    "last_price": last_price,
                    "suggestions": suggestions,
                    "risk_level": risk_level,
                    "risk_pct": risk_pct,
                    "quality_flags": qa.flags[:3],
                    "recency": recency,
                    "days_since_end": days_since_end,
                    "signal": signal.to_dict() if signal else None,
                    "judgment": judgment,
                })

        # v3.3: 品种去重 — 每个合约代码只保留得分最高的结构
        # 避免同一品种占多个显示位，让 Top 10 覆盖更多品种
        best_per_symbol = {}
        for r in results:
            sym = r["symbol"]
            if sym not in best_per_symbol or r["score"] > best_per_symbol[sym]["score"]:
                best_per_symbol[sym] = r
        results = sorted(best_per_symbol.values(), key=lambda x: x["score"], reverse=True)
        
        # 排序：质量 70% + recency 30%
        results.sort(key=lambda x: x["score"] * 0.7 + x["recency"] * 30, reverse=True)
        return results

    scan_col1, scan_col2, scan_col3 = st.columns([1, 2, 1])
    with scan_col1:
        run_scan = st.button("🔍 全市场扫描", type="primary", use_container_width=True, key="btn_market_scan")
    with scan_col2:
        st.caption("扫描所有品种的活跃结构，按关注度评分排序，展示 Top 10 机会")
    with scan_col3:
        with st.popover("ℹ️ 评分说明"):
            st.markdown("""
            **质量评分**（满分 100）基于 `quality.py` 五维度评估：

            | 维度 | 权重 | 说明 |
            |---|---|---|
            | 结构完整性 | 25% | cycle 数、zone 强度、不变量完整度 |
            | 运动可信度 | 25% | 稳定性验证、投影非盲、运动态置信度 |
            | 守恒一致性 | 20% | 通量合理性、速度比/时间比范围 |
            | 时间成熟度 | 15% | cycle 数适中（3-8 为佳）|
            | 后验可追溯 | 15% | 标签、典型度、叙事背景 |

            **分层标准**：A 层 ≥75 · B 层 50-74 · C 层 25-49 · D 层 <25
            """)

    sensitivity = ctx.get("sensitivity", "标准")

    if run_scan:
        from src.lifecycle import LifecycleTracker, LifecycleRecord
        total_syms = len(ALL_SYMBOLS)
        with st.spinner(f"🔍 正在扫描 {total_syms} 个品种的结构..."):
            prog = st.progress(0, text=f"准备扫描 {total_syms} 个品种...")
            scan_results = _scan_all_symbols(sensitivity)
            prog.progress(1.0, text=f"✅ 扫描完成，发现 {len(scan_results)} 个活跃结构")

        if scan_results:
            _tracker = LifecycleTracker()
            _today_str = datetime.now().strftime("%Y-%m-%d")
            _recorded = 0
            for r in scan_results[:20]:
                try:
                    zc = r["zone_center"]
                    lifecycle_id = _tracker._match_existing_zone(r["symbol"], zc, _today_str)
                    rec = LifecycleRecord(
                        date=_today_str,
                        symbol=r["symbol"],
                        zone_center=zc,
                        zone_bw=r["zone_bw"],
                        cycle_count=r["cycles"],
                        quality_tier=r.get("tier", "?"),
                        quality_score=r["score"] / 100.0,
                        phase_tendency=r["motion"],
                        conservation_flux=r["flux"],
                        speed_ratio=0,
                        direction=r["direction"],
                        is_blind=r["is_blind"],
                        stability="unknown",
                        lifecycle_id=lifecycle_id,
                    )
                    _tracker._append_records(r["symbol"], [rec])
                    _recorded += 1
                except Exception:
                    pass
            if _recorded:
                st.caption(f"📝 已记录 {_recorded} 个品种的生命周期")

            # v3.1: 自动保存扫描结果到活动日志
            try:
                from src.workbench.activity_log import ActivityLog
                ActivityLog().save_scan(scan_results, sensitivity=sensitivity)
            except Exception:
                pass

        if scan_results:
            top10 = scan_results[:10]
            st.markdown("---")
            st.markdown(f"**🏆 Top 10 关注机会**（共扫描 {len(scan_results)} 个活跃结构）")

            dir_up = sum(1 for r in top10 if r["direction"] == "up")
            dir_down = sum(1 for r in top10 if r["direction"] == "down")
            dir_unclear = sum(1 for r in top10 if r["direction"] == "unclear")
            stat_c = st.columns(4)
            stat_c[0].metric("总机会", len(top10))
            stat_c[1].metric("📈 偏多", dir_up)
            stat_c[2].metric("📉 偏空", dir_down)
            stat_c[3].metric("➡️ 不明", dir_unclear)

            for i, r in enumerate(top10):
                try:
                    dir_icon = "📈" if r.get("direction") == "up" else "📉" if r.get("direction") == "down" else "➡️"
                    card_cls = "danger" if r.get("direction") == "up" else "ok" if r.get("direction") == "down" else ""
                    motion_html = motion_badge(r.get("motion") or "—")
                    blind_tag = " · ⚠️高压缩" if r.get("is_blind") else ""
                    contrast_tag = f' · {r.get("contrast", "")}' if r.get("contrast") else ""
                    price_pos = _price_vs_zone(r.get("last_price", 0), r.get("zone_center", 0), r.get("zone_bw", 0))

                    tier = r.get("tier", "?")
                    tier_fg, tier_bg = TIER_COLORS.get(tier, ("#666", "#eee"))
                    tier_badge = f'<span style="background:{tier_bg};color:{tier_fg};padding:1px 6px;border-radius:3px;font-size:0.8em;font-weight:700">{tier}层</span>'

                    risk_color = {"高": "#ef5350", "中": "#ff9800", "低": "#26a69a"}.get(r.get("risk_level", "低"), "#999")

                    # 结构时效性 — 交易导向表述
                    ds = r.get("days_since_end", 0) or 0
                    if ds <= 1:
                        fresh_tag = '<span style="color:#4caf50;font-weight:600">🔥 实时结构</span>'
                    elif ds <= 3:
                        fresh_tag = '<span style="color:#4caf50;font-weight:600">✅ 结构活跃</span>'
                    elif ds <= 7:
                        fresh_tag = '<span style="color:#ff9800;font-weight:600">⚡ 需刷新确认</span>'
                    elif ds <= 14:
                        fresh_tag = '<span style="color:#ff9800;font-weight:600">⚠️ 结构老化</span>'
                    else:
                        fresh_tag = '<span style="color:#999">📋 仅作参考</span>'

                    # v4.0: 交易信号显示
                    signal_html = ""
                    sig = r.get("signal")
                    if sig:
                        sig_conf = sig.get("confidence", 0)
                        sig_kind = sig.get("kind", "")
                        sig_dir = sig.get("display_direction", "")
                        sig_label = sig.get("display_label", "")
                        sig_flux = sig.get("flux_aligned", False)
                        sig_stable = sig.get("stability_ok", False)

                        # 信号颜色: 高置信绿/中置信黄/低置信灰
                        if sig_conf >= 0.80 and sig_stable and sig_flux:
                            sig_color = "#4caf50"  # 绿
                        elif sig_conf >= 0.55 and sig_stable:
                            sig_color = "#ff9800"  # 黄
                        else:
                            sig_color = "#999"  # 灰

                        # 信号图标
                        sig_icon = "🚨" if sig_kind == "fake_breakout" else "✅" if sig_kind == "breakout_confirm" else "📍" if sig_kind == "pullback_confirm" else "⚠️" if sig_kind == "structure_expired" else "👁️"

                        signal_html = f'<div style="margin-top:6px"><span style="color:{sig_color};font-weight:600">{sig_icon} {sig_label} {sig_dir} (置信{sig_conf:.0%})</span></div>'

                    st.markdown(f"""
                    <div class="structure-card {card_cls}">
                        <b>#{i+1}</b> {dir_icon}
                        <span class="zone-label">{r.get('symbol', '')} · {r.get('symbol_name', '')}</span>
                        {tier_badge}
                        <span class="meta-text"> Zone {r.get('zone_center', 0):.0f} (±{r.get('zone_bw', 0):.0f}) · {r.get('cycles', 0)}次试探</span>
                        · {motion_html} · 通量 {r.get('flux', 0) or 0:+.2f}{blind_tag}{contrast_tag}
                        · <b>质量 {r.get('score', 0):.0f}分</b>
                        · <span style="color:{risk_color};font-weight:700">⚖️ {r.get('risk_level', '低')}关注度</span>
                        · {fresh_tag}
                        {signal_html}
                        <div class="meta-text">{price_pos} · 现价 {r.get('last_price', 0):.1f} · {_judgment_html(r.get('judgment'))}</div>
                        <div class="narrative-text">{r.get('narrative', '')}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # 候选剧本摘要
                    try:
                        sym = r.get("symbol", "")
                        sym_bars = load_bars(sym)
                        if sym_bars and len(sym_bars) > 120:
                            # 编译历史结构
                            hist_cfg = CompilerConfig(
                                min_amplitude=sens["min_amp"],
                                min_duration=sens["min_dur"],
                                min_cycles=sens["min_cycles"],
                            )
                            hist_result = compile_full(sym_bars, hist_cfg, symbol=sym)
                            if hist_result.structures:
                                # 找到当前结构对应的 Structure 对象
                                cr_sym, _ = compile_structures(sym, sens["min_amp"], sens["min_dur"], sens["min_cycles"])
                                if cr_sym and cr_sym.structures:
                                    # 取 zone 最接近的结构作为 query
                                    zc = r.get("zone_center", 0)
                                    query_s = min(cr_sym.structures,
                                                  key=lambda s: abs(s.zone.price_center - zc))
                                    playbook, _ = progress_retrieve(
                                        query=query_s,
                                        history_structures=hist_result.structures,
                                        history_bars=sym_bars,
                                        after_window=120,
                                        min_similarity=0.2,
                                        top_k=10,
                                    )
                                    if playbook.n_matches > 0:
                                        pb_dir = {"bullish": "📈看涨", "bearish": "📉看跌", "unclear": "➡️不明"}
                                        r["_playbook"] = (
                                            f"🎬 剧本: {pb_dir.get(playbook.direction, '?')} "
                                            f"({playbook.confidence}) "
                                            f"上涨{playbook.prob_up:.0%}/下跌{playbook.prob_down:.0%} "
                                            f"中位{playbook.median_move:+.1%} "
                                            f"({playbook.n_matches}例)"
                                        )
                    except Exception:
                        pass

                    with st.expander(f"💡 #{i+1} {r.get('symbol', '')} 研究建议 · {tier}层", expanded=False):
                        # 品种独立描述
                        sym_desc = symbol_description(r.get('symbol', ''))
                        if sym_desc:
                            with st.container(border=True):
                                st.markdown(f"**📋 {r.get('symbol', '')} · {r.get('symbol_name', '')} 品种特征**")
                                st.markdown(sym_desc)
                        
                        st.markdown(f"**风控建议**：{tier}层质量（{r.get('score', 0):.0f}分），建议单笔关注不超过总资金的 **{r.get('risk_pct', '1-3%')}**")
                        flags = r.get("quality_flags", [])
                        if flags:
                            st.markdown("**质量标记**：" + " · ".join(flags))
                        # 候选剧本
                        if r.get("_playbook"):
                            st.info(r["_playbook"])
                        st.markdown("**下一步研究动作**：")
                        for j, sug in enumerate(r.get("suggestions", []), 1):
                            st.markdown(f"  {j}. {sug}")
                except Exception as card_ex:
                    st.caption(f"卡片渲染跳过: {card_ex}")

            # ── 今日三选 ──
            st.markdown("---")
            st.markdown("#### 🎯 今日三选")
            st.caption("从 Top 10 中精选三种策略类型 — 激进 / 稳健 / 潜伏")

            aggressive = [r for r in scan_results[:20]
                          if r["motion"] and "breakout" in r["motion"]]
            aggressive.sort(key=lambda r: abs(r["flux"]), reverse=True)

            stable = [r for r in scan_results[:20]
                      if r["motion"] and "confirmation" in r["motion"]]
            stable.sort(key=lambda r: r["score"], reverse=True)

            latent = [r for r in scan_results[:20]
                      if r["motion"] in ("forming", "stable", "") and (r["is_blind"] or r["score"] >= 50)]
            latent.sort(key=lambda r: r["score"], reverse=True)

            trio = [
                ("🔴 激进型", "突破 + 高通量，波动大", aggressive),
                ("🟢 稳健型", "confirmation，方向明确", stable),
                ("🔵 潜伏型", "forming + 高压缩，等待突破", latent),
            ]

            trio_cols = st.columns(3)
            for col, (label, desc, candidates) in zip(trio_cols, trio):
                with col:
                    st.markdown(f"**{label}**")
                    st.caption(desc)
                    if candidates:
                        r = candidates[0]
                        pos = _price_vs_zone(r["last_price"], r["zone_center"], r["zone_bw"])
                        risk_color = {"高": "#ef5350", "中": "#ff9800", "低": "#26a69a"}.get(r["risk_level"], "#999")
                        t = r.get("tier", "?")
                        st.markdown(f"""
                        <div class="structure-card">
                            <span class="zone-label">{r['symbol']} · {r['symbol_name']}</span>
                            <span style="background:{TIER_COLORS.get(t, ('#666','#eee'))[1]};color:{TIER_COLORS.get(t, ('#666','#eee'))[0]};padding:1px 6px;border-radius:3px;font-size:0.8em;font-weight:700">{t}层</span><br>
                            <span class="meta-text">Zone {r['zone_center']:.0f} (±{r['zone_bw']:.0f}) · {motion_badge(r['motion'])} · 通量 {r['flux']:+.2f}</span><br>
                            <span class="meta-text">{pos}</span><br>
                            <span style="color:{risk_color};font-weight:700">质量 {r['score']:.0f}分 · {r['risk_level']}关注度</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption(f"💡 {r['suggestions'][0]}" if r['suggestions'] else "")
                    else:
                        st.info("暂无符合条件的结构")

            # ── 跨品种信号一致性分析 ──
            st.markdown("---")
            st.markdown("#### 🔗 跨品种信号一致性")

            try:
                exchange_groups = {}
                for r in scan_results[:20]:
                    info = META.get(r["symbol"], META.get(r["symbol"].upper(), {}))
                    ex = (info.get("exchange") or "其他") if isinstance(info, dict) else "其他"
                    exchange_groups.setdefault(ex, []).append(r)

                for ex, items in sorted(exchange_groups.items()):
                    if len(items) < 2:
                        continue
                    up_n = sum(1 for r in items if r.get("direction") == "up")
                    down_n = sum(1 for r in items if r.get("direction") == "down")
                    total = len(items)
                    names = ", ".join(f"{r.get('symbol', '?')}" for r in items[:5])

                    if up_n > down_n and up_n >= total * 0.6:
                        st.success(f"**{ex}** 板块偏多：{up_n}/{total} 偏多 · {names}")
                    elif down_n > up_n and down_n >= total * 0.6:
                        st.error(f"**{ex}** 板块偏空：{down_n}/{total} 偏空 · {names}")
                    else:
                        st.warning(f"**{ex}** 板块信号分歧：📈{up_n} / 📉{down_n} / ➡️{total - up_n - down_n} · {names}")
            except Exception as ex:
                st.caption(f"跨品种分析跳过: {ex}")

            # ── 每日变化报告 ──
            st.markdown("---")
            st.markdown("#### 📋 每日变化报告")

            _today_key = datetime.now().strftime("%Y-%m-%d")
            _prev_results = st.session_state.get("prev_scan_results", {})
            _prev_date = st.session_state.get("prev_scan_date", "")

            if _prev_date == _today_key and _prev_results:
                prev_map = {(r["symbol"], r["zone_center"]): r for r in _prev_results}
                curr_map = {(r["symbol"], r["zone_center"]): r for r in scan_results[:20]}

                new_items = [(k, v) for k, v in curr_map.items() if k not in prev_map]
                gone_items = [(k, v) for k, v in prev_map.items() if k not in curr_map]
                changed_items = []
                for k, v in curr_map.items():
                    if k in prev_map:
                        pv = prev_map[k]
                        if pv["motion"] != v["motion"] or abs(pv["flux"] - v["flux"]) > 0.3:
                            changed_items.append((k, v, pv))

                if new_items:
                    st.markdown("**🆕 新增结构**")
                    for (sym, zone), r in new_items:
                        st.markdown(f"  - {sym} Zone {zone:.0f} · {r['motion']} · 关注度 {r['score']:.0f}分")

                if changed_items:
                    st.markdown("**🔄 状态变化**")
                    for (sym, zone), r, pv in changed_items:
                        motion_change = f"{pv['motion']} → {r['motion']}" if pv['motion'] != r['motion'] else ""
                        flux_change = f"通量 {pv['flux']:+.2f} → {r['flux']:+.2f}" if abs(pv['flux'] - r['flux']) > 0.3 else ""
                        parts = [p for p in [motion_change, flux_change] if p]
                        st.markdown(f"  - {sym} Zone {zone:.0f} · {' · '.join(parts)}")

                if gone_items:
                    st.markdown("**❌ 退出 Top 20**")
                    for (sym, zone), r in gone_items:
                        st.markdown(f"  - {sym} Zone {zone:.0f} · 原关注度 {r['score']:.0f}分")

                if not new_items and not changed_items and not gone_items:
                    st.caption("与上次扫描相比无变化")
            else:
                st.caption(f"首次扫描（{_today_key}），下次扫描将自动对比变化")

            # ── 导出扫描结果 ──
            st.markdown("---")
            st.markdown("#### 📤 导出扫描结果")

            # 按阶段分类筛选
            stage_groups = {}
            for r in scan_results:
                stage = (r.get("judgment") or {}).get("stage", "未分类")
                stage_groups.setdefault(stage, []).append(r)

            stage_options = ["全部"] + sorted(stage_groups.keys(), key=lambda s: -len(stage_groups[s]))
            selected_stage = st.selectbox("按阶段筛选", stage_options, index=0, key="export_stage_filter")

            if selected_stage == "全部":
                export_results = scan_results[:50]
            else:
                export_results = stage_groups.get(selected_stage, [])[:50]

            # 阶段分布摘要
            dist_parts = [f"{s}({len(stage_groups[s])})" for s in sorted(stage_groups, key=lambda s: -len(stage_groups[s]))]
            st.caption(f"分布：{' · '.join(dist_parts)}")

            exp_c1, exp_c2 = st.columns(2)
            with exp_c1:
                scan_export = {
                    "date": _today_key,
                    "sensitivity": sensitivity,
                    "filter": selected_stage,
                    "total": len(export_results),
                    "stage_distribution": {s: len(v) for s, v in stage_groups.items()},
                    "results": [{
                        "rank": i + 1,
                        "symbol": r["symbol"],
                        "symbol_name": r["symbol_name"],
                        "zone_center": r["zone_center"],
                        "cycles": r["cycles"],
                        "motion": r["motion"],
                        "flux": r["flux"],
                        "score": r["score"],
                        "tier": r.get("tier", "?"),
                        "direction": r["direction"],
                        "stage": (r.get("judgment") or {}).get("stage", ""),
                        "judgment_detail": (r.get("judgment") or {}).get("detail", ""),
                        "stop_loss_price": (r.get("signal") or {}).get("stop_loss_price", 0),
                        "take_profit_price": (r.get("signal") or {}).get("take_profit_price", 0),
                        "rr_ratio": (r.get("signal") or {}).get("rr_ratio", 0),
                        "narrative": r["narrative"],
                        "last_price": r["last_price"],
                        "days_since_end": r.get("days_since_end", 0),
                    } for i, r in enumerate(export_results)],
                    "exported_at": datetime.now().isoformat(),
                }
                st.download_button(
                    "📥 导出 JSON",
                    data=json.dumps(scan_export, ensure_ascii=False, indent=2),
                    file_name=f"scan_{_today_key}_{selected_stage}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with exp_c2:
                md_lines = [f"# 全市场扫描 {_today_key}\n灵敏度: {sensitivity} · 筛选: {selected_stage} · 结果: {len(export_results)}\n"]
                for i, r in enumerate(export_results, 1):
                    dir_icon = "📈" if r["direction"] == "up" else "📉" if r["direction"] == "down" else "➡️"
                    j = r.get("judgment") or {}
                    stage_icon = j.get("icon", "")
                    stage_name = j.get("stage", "")
                    sig = r.get("signal") or {}
                    sl = sig.get("stop_loss_price", 0)
                    tp = sig.get("take_profit_price", 0)
                    rr = sig.get("rr_ratio", 0)

                    md_lines.append(f"## #{i} {r['symbol']} ({r['symbol_name']})")
                    md_lines.append(f"- {dir_icon} {stage_icon} **{stage_name}** · Zone {r['zone_center']:.0f} · {r['cycles']}次试探")
                    md_lines.append(f"- 质量 {r['score']:.0f}分 · {r.get('tier', '?')}层 · 通量{r['flux']:+.2f}")
                    md_lines.append(f"- 现价{r['last_price']:.1f} · {r.get('days_since_end', 0)}天前活跃")
                    if sl > 0:
                        md_lines.append(f"- 止损 {sl:.1f} · 目标 {tp:.1f} · 盈亏比 {rr:.1f}")
                    md_lines.append("")
                st.download_button(
                    "📥 导出 Markdown",
                    data="\n".join(md_lines),
                    file_name=f"scan_{_today_key}_{selected_stage}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            st.session_state["prev_scan_results"] = scan_results[:20]
            st.session_state["prev_scan_date"] = _today_key
        else:
            st.warning("🔍 未扫描到活跃结构")
            st.caption("可能原因：① 数据源无数据（检查 MySQL 连接或 data/ 目录）② 当前灵敏度下无满足条件的结构 — 试试侧栏调为「精细」")

        st.markdown("---")

    # ── 当前品种结构展示（保留原有内容）──
    if not recent_structures:
        st.info("当前时间范围内没有显著结构")
    else:
        breaking = [s for s in recent_structures
                    if s.motion and "breakout" in s.motion.phase_tendency]
        confirming = [s for s in recent_structures
                      if s.motion and "confirmation" in s.motion.phase_tendency]
        forming = [s for s in recent_structures
                   if s.motion and s.motion.phase_tendency in ("forming", "stable", "")]

        if breaking:
            st.markdown("**🔴 正在破缺**")
            for s in breaking[:3]:
                flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                st.markdown(f"""
                <div class="structure-card danger">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(s.motion.phase_tendency)}
                    · <span class="meta-text">通量 {flux}</span>
                    <div class="narrative-text">{s.narrative_context or ''}</div>
                </div>
                """, unsafe_allow_html=True)

        if confirming:
            st.markdown("**🟢 趋向确认**")
            for s in confirming[:3]:
                flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                st.markdown(f"""
                <div class="structure-card ok">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(s.motion.phase_tendency)}
                    · <span class="meta-text">通量 {flux}</span>
                    <div class="narrative-text">{s.narrative_context or ''}</div>
                </div>
                """, unsafe_allow_html=True)

        if forming:
            st.markdown("**🔵 形成中**")
            for s in forming[:5]:
                proj_warn = " · ⚠️ 高压缩" if (s.projection and s.projection.is_blind) else ""
                tendency = s.motion.phase_tendency if s.motion else 'unknown'
                st.markdown(f"""
                <div class="structure-card">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(tendency)}{proj_warn}
                    <div class="narrative-text">{s.narrative_context or ''}</div>
                </div>
                """, unsafe_allow_html=True)

        # K 线图 + Zone 标注
        st.markdown("---")
        col_chart, col_info = st.columns([2, 1])
        with col_chart:
            st.markdown("**K 线 + 关键区**")
            fig = make_candlestick(bars[-120:])
            for s in recent_structures[:5]:
                fig.add_hline(y=s.zone.price_center, line_dash="dot",
                             line_color="#4a90d9", opacity=0.5,
                             annotation_text=f"Zone {s.zone.price_center:.0f}")
                fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                             fillcolor="#4a90d9", opacity=0.08, line_width=0)
            st.plotly_chart(fig, use_container_width=True)
        with col_info:
            st.markdown("**结构汇总**")
            st.metric("结构总数", len(result.structures))
            st.metric("Zone 数", len(result.zones))
            st.metric("Bundle 数", len(result.bundles))
            ss_count = sum(1 for ss in result.system_states if ss.is_reliable)
            st.metric("可信结构", ss_count)
            blind_count = sum(1 for ss in result.system_states if ss.projection.is_blind)
            if blind_count:
                st.metric("⚠️ 高压缩", blind_count)
