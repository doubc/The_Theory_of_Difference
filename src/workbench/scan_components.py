"""
扫描页面渲染组件

从 tab_scan.py 迁移：板块热度图、机会队列、全景表格、详情面板、观察池、日报按钮
"""
from __future__ import annotations

import json
import streamlit as st
from datetime import datetime

from src.workbench.ui_formatters import (
    fmt_direction, fmt_flux_color, fmt_tier_color, fmt_departure_color,
    fmt_priority_color, fmt_volume, build_risk_tags,
)
from src.workbench.scan_filters import pick_today_three, build_market_overview


# ═══════════════════════════════════════════════════════════
# 板块热度图
# ═══════════════════════════════════════════════════════════

def render_sector_cards(filtered: list[dict]):
    """渲染板块热度图卡片"""
    st.markdown("#### 🗺️ 板块热度图")

    sector_groups = {}
    for r in filtered:
        sec = r.get("sector", "未知")
        sector_groups.setdefault(sec, []).append(r)

    if not sector_groups:
        st.caption("无板块数据")
        return sector_groups

    sector_cols = st.columns(len(sector_groups))
    for idx, (sec_name, sec_items) in enumerate(sorted(sector_groups.items())):
        with sector_cols[idx]:
            s_up = sum(1 for r in sec_items if r["direction"] == "up")
            s_down = sum(1 for r in sec_items if r["direction"] == "down")
            s_total = len(sec_items)

            if s_up > s_down and s_up >= s_total * 0.5:
                sentiment = "📈 偏多"
                card_bg = "#e8f5e9"
                card_border = "#4caf50"
            elif s_down > s_up and s_down >= s_total * 0.5:
                sentiment = "📉 偏空"
                card_bg = "#ffebee"
                card_border = "#ef5350"
            else:
                sentiment = "⚖️ 分歧"
                card_bg = "#fff8e1"
                card_border = "#ff9800"

            top_item = max(sec_items, key=lambda x: x.get("priority_score", 0))
            top_sym = top_item['symbol']
            top_score = top_item.get("priority_score", 0)
            top_phase = top_item.get("motion_label", "—")
            s_breakout = sum(1 for r in sec_items if r.get("phase_code") == "breakout")
            s_confirm = sum(1 for r in sec_items if r.get("phase_code") == "confirmation")

            st.markdown(f"""
            <div style="background:{card_bg};border-left:4px solid {card_border};border-radius:8px;padding:10px 12px;margin-bottom:4px">
                <div style="font-weight:700;font-size:1.0em">{sec_name}</div>
                <div style="font-size:0.85em;color:#555">{sentiment} · {s_total}个</div>
                <div style="font-size:0.8em;margin-top:4px">📈{s_up} 📉{s_down} · 🔴{s_breakout} 🟢{s_confirm}</div>
                <div style="font-size:0.8em;margin-top:4px;color:#1565c0">🏆 {top_sym} P{top_score:.0f} · {top_phase}</div>
            </div>
            """, unsafe_allow_html=True)

    return sector_groups


# ═══════════════════════════════════════════════════════════
# 机会队列
# ═══════════════════════════════════════════════════════════

def render_opportunity_table(sector_groups: dict):
    """渲染按板块分组的机会队列"""
    st.markdown("#### 🎯 机会队列")
    st.caption("按板块分组，展示各板块优先级最高的机会")

    for sec_name, sec_items in sorted(sector_groups.items(), key=lambda x: -len(x[1])):
        sec_sorted = sorted(sec_items, key=lambda x: x.get("priority_score", 0), reverse=True)
        top3 = sec_sorted[:3]

        with st.expander(f"{sec_name} — {len(sec_items)}个 · 🏆{top3[0]['symbol']} P{top3[0].get('priority_score', 0):.0f}"):
            for r in top3:
                dir_icon = fmt_direction(r["direction"])
                ps = r.get("priority_score", 0)
                phase = r.get("motion_label", "—")
                pos = r.get("price_position", "—")
                flux = r.get("flux", 0)
                dep = r.get("departure_score", 0)
                tier = r.get("tier", "?")
                vol = r.get("volume", 0)
                ps_color = fmt_priority_color(ps)
                st.markdown(f"""
                <div style="border-left:3px solid {ps_color};padding:4px 8px;margin:4px 0;background:#fafafa;border-radius:4px">
                    <b>{r['symbol']}</b> · {r['symbol_name']}
                    <span style="color:{ps_color};font-weight:600"> P{ps:.0f}</span>
                    · {dir_icon} · {phase} · {pos} · 通量{flux:+.2f} · 离稳态{dep:.0f} · {tier}层 · 量{fmt_volume(vol)}
                </div>
                """, unsafe_allow_html=True)
            remaining = len(sec_sorted) - 3
            if remaining > 0:
                st.caption(f"... 还有 {remaining} 个合约，见下方全景表格")


# ═══════════════════════════════════════════════════════════
# 全景表格
# ═══════════════════════════════════════════════════════════

def render_panorama_table(filtered: list[dict]):
    """渲染全景仪表盘表格 + 分页"""
    st.markdown(f"#### 📊 合约结构全景（{len(filtered)} 个）")

    col_page, col_size = st.columns([3, 1])
    with col_size:
        page_size = st.selectbox("每页", [10, 20, 50], index=1, key="dash_page_size")
    total_pages = max((len(filtered) + page_size - 1) // page_size, 1)
    with col_page:
        if total_pages > 1:
            page_idx = st.number_input("页码", min_value=1, max_value=total_pages, value=1, key="dash_page") - 1
        else:
            page_idx = 0

    start_idx = page_idx * page_size
    end_idx = min(start_idx + page_size, len(filtered))
    paged = filtered[start_idx:end_idx]
    st.caption(f"显示 {start_idx+1}-{end_idx} / 共 {len(filtered)} 个")

    table_rows = []
    for r in paged:
        zones = r.get("zones", [])
        if len(zones) >= 2:
            zone_summary = " → ".join(f"{z['center']:.0f}" for z in zones[-3:])
        elif zones:
            zone_summary = f"{zones[0]['center']:.0f}"
        else:
            zone_summary = "—"

        dir_icon = fmt_direction(r["direction"])
        flux_val = r.get("flux", 0)
        breakout_date = r.get("breakout_date", "")

        table_rows.append({
            "品种": f"{r['symbol']} · {r['symbol_name']}",
            "成交量": fmt_volume(r['volume']),
            "现价": f"{r['last_price']:.0f}",
            "趋势": f"{dir_icon} {r['zone_trend']}",
            "稳态序列": zone_summary,
            "稳态关系": r["zone_relation"],
            "价格位置": r["price_position"],
            "运动阶段": r["motion_label"],
            "确认日": breakout_date,
            "通量": f"{flux_val:+.3f}",
            "质量": f"{r['tier']}层 {r['score']:.0f}",
            "离稳态": f"{r['departure_score']:.0f}",
            "_r": r,
        })

    if not table_rows:
        st.info("当前筛选条件下无匹配合约")
        return []

    html_parts = ['<div style="overflow-x:auto">']
    html_parts.append('<table style="width:100%;border-collapse:collapse;font-size:0.85em">')
    html_parts.append('<thead><tr style="background:#f0f2f6;border-bottom:2px solid #ddd">')
    for col in ["品种", "成交量", "现价", "趋势", "稳态序列", "稳态关系", "价格位置", "运动阶段", "确认日", "通量", "质量", "离稳态"]:
        html_parts.append(f'<th style="padding:6px 8px;text-align:left;white-space:nowrap">{col}</th>')
    html_parts.append('</tr></thead><tbody>')

    for row in table_rows:
        r = row["_r"]
        bg = "#fff8e1" if r.get("is_blind") else "#fff"
        html_parts.append(f'<tr style="border-bottom:1px solid #eee;background:{bg}">')
        html_parts.append(f'<td style="padding:5px 8px;font-weight:600">{row["品种"]}</td>')
        html_parts.append(f'<td style="padding:5px 8px;text-align:right">{row["成交量"]}</td>')
        html_parts.append(f'<td style="padding:5px 8px;text-align:right">{row["现价"]}</td>')
        html_parts.append(f'<td style="padding:5px 8px">{row["趋势"]}</td>')
        html_parts.append(f'<td style="padding:5px 8px;font-family:monospace;font-size:0.85em">{row["稳态序列"]}</td>')
        html_parts.append(f'<td style="padding:5px 8px">{row["稳态关系"]}</td>')
        html_parts.append(f'<td style="padding:5px 8px">{row["价格位置"]}</td>')
        html_parts.append(f'<td style="padding:5px 8px">{row["运动阶段"]}</td>')
        html_parts.append(f'<td style="padding:5px 8px">{row["确认日"]}</td>')
        flux_color = fmt_flux_color(r.get("flux", 0))
        html_parts.append(f'<td style="padding:5px 8px;color:{flux_color}">{row["通量"]}</td>')
        tier_color = fmt_tier_color(r.get("tier", "?"))
        html_parts.append(f'<td style="padding:5px 8px;color:{tier_color}">{row["质量"]}</td>')
        dep = r.get("departure_score", 0)
        dep_color = fmt_departure_color(dep)
        html_parts.append(f'<td style="padding:5px 8px;color:{dep_color}">{row["离稳态"]}</td>')
        html_parts.append('</tr>')
    html_parts.append('</tbody></table></div>')

    st.markdown("".join(html_parts), unsafe_allow_html=True)
    return table_rows


# ═══════════════════════════════════════════════════════════
# 选中合约详情面板
# ═══════════════════════════════════════════════════════════

def render_selected_contract_panel(table_rows: list[dict], dashboard_data: list[dict]):
    """渲染可展开的合约详情面板（含观察池按钮）"""
    from src.workbench.shared import TIER_COLORS

    st.markdown("---")
    st.markdown("**📋 点击展开查看详情**")
    for i, row in enumerate(table_rows[:20]):
        r = row["_r"]
        ps = r.get("priority_score", 0)
        sector = r.get("sector", "未知")
        phase_code = r.get("phase_code", "—")
        pp_code = r.get("price_position_code", "—")
        ps_color = fmt_priority_color(ps)
        with st.expander(f"#{i+1} {r['symbol']} · {r['symbol_name']} — {r['motion_label']} · P{ps:.0f} · {sector}", expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**当前价格**: {r['last_price']:.0f}")
                st.markdown(f"**成交量**: {fmt_volume(r['volume'])}")
                st.markdown(f"**最近稳态**: Zone {r['latest_zone_center']:.0f} (±{r['latest_zone_bw']:.0f})")
                st.markdown(f"**价格位置**: {r['price_position']} ({pp_code})")
                st.markdown(f"**趋势**: {r['zone_trend']} · **稳态关系**: {r['zone_relation']}")
            with c2:
                st.markdown(f"**运动阶段**: {r['motion']} ({phase_code})")
                st.markdown(f"**通量**: {r['flux']:+.3f}")
                st.markdown(f"**质量**: {r['tier']}层 ({r['score']:.0f}分)")
                st.markdown(f"**离稳态活跃度**: {r['departure_score']:.0f}")
                if r.get("breakout_date"):
                    st.markdown(f"**破缺确认日**: {r['breakout_date']}")
            with c3:
                st.markdown(f"**优先级分数**: <span style='color:{ps_color};font-weight:600'>P{ps:.0f}</span>", unsafe_allow_html=True)
                st.markdown(f"**板块**: {sector}")
                phase_map_score = {"breakout": 1.0, "confirmation": 0.8, "forming": 0.5, "stable": 0.3, "breakdown": 0.2}
                pos_map_score = {"H": 1.0, "M": 0.6, "L": 0.8}
                dep_pct = r.get('departure_score', 0) * 0.30
                qual_pct = r.get('score', 0) / 100 * 0.20 * 100
                phase_pct = phase_map_score.get(phase_code, 0) * 0.20 * 100
                pos_pct = pos_map_score.get(pp_code, 0) * 0.15 * 100
                st.caption(f"构成: 离稳态{dep_pct:.0f} + 质量{qual_pct:.0f} + 阶段{phase_pct:.0f} + 位置{pos_pct:.0f}")
                # 加入观察池按钮
                watch_key = f"watch_{r['symbol']}"
                if st.button("⭐ 加入观察池", key=watch_key):
                    _add_to_watch_pool(r)

            # 信号详情
            sig = r.get("signal_info")
            if sig:
                _render_signal_detail(sig)

            # 稳态序列详情
            zones = r.get("zones", [])
            if zones:
                st.markdown("**稳态序列**:")
                for zi, z in enumerate(zones):
                    st.markdown(f"  {zi+1}. Zone {z['center']:.0f} (±{z['bw']:.0f}) · {z['date_range']} · {z['cycles']}次试探")


def _render_signal_detail(sig: dict):
    """渲染信号详情区块"""
    st.markdown("---")
    st.markdown("**📢 信号详情**")
    kind_labels = {
        "breakout_confirm": "✅ 突破确认",
        "fake_breakout": "⚠️ 假突破",
        "pullback_confirm": "🔄 回踩确认",
        "structure_expired": "💀 结构失效",
        "blind_breakout": "👁 盲区突破",
    }
    sig_label = kind_labels.get(sig["kind"], sig["kind"])
    dir_labels = {"long": "📈 多", "short": "📉 空", "neutral": "➡️ 中性"}
    sig_dir = dir_labels.get(sig["direction"], sig["direction"])
    conf_pct = sig["confidence"] * 100
    flux_ico = "✅" if sig["flux_aligned"] else "❌"
    stab_ico = "✅" if sig["stability_ok"] else "❌"
    st.markdown(f"{sig_label} · {sig_dir} · 置信度 {conf_pct:.0f}%")
    st.caption(f"通量一致 {flux_ico} · 稳定性 {stab_ico} · 突破评分 {sig['breakout_score']:.2f}")
    if sig["fake_pattern"]:
        fake_labels = {
            "fake_pin": "探针型", "fake_dspike": "单K极端", "fake_voldiv": "量能背离",
            "fake_blind_whip": "盲区抽鞭", "fake_gap": "跳空回补",
            "fake_wick_cluster": "影线簇", "fake_time_trap": "时间陷阱",
        }
        st.warning(f"⚠️ 假突破模式：{fake_labels.get(sig['fake_pattern'], sig['fake_pattern'])}")
    if sig.get("entry_note"):
        st.info(f"💡 {sig['entry_note']}")
    if sig.get("entry_price", 0) > 0 or sig.get("stop_loss_price", 0) > 0:
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            st.metric("入场价", f"{sig['entry_price']:.1f}")
        with rc2:
            st.metric("止损", f"{sig['stop_loss_price']:.1f}")
        with rc3:
            st.metric("目标", f"{sig['take_profit_price']:.1f}")
        if sig.get("rr_ratio", 0) > 0:
            rr = sig["rr_ratio"]
            rr_color = "green" if rr >= 2 else "orange" if rr >= 1 else "red"
            st.markdown(
                f"盈亏比 <span style='color:{rr_color};font-weight:600'>{rr:.1f}"
                f"</span> · 仓位系数 {sig.get('position_size_factor', 1.0):.1f}",
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════
# 观察池
# ═══════════════════════════════════════════════════════════

def _add_to_watch_pool(r: dict):
    """将合约加入观察池"""
    from src.workbench.tab_scan import load_watch_pool, save_watch_pool
    if "watch_pool" not in st.session_state:
        st.session_state["watch_pool"] = load_watch_pool()
    st.session_state["watch_pool"][r['symbol']] = {
        "symbol": r['symbol'],
        "symbol_name": r['symbol_name'],
        "priority_score": r.get("priority_score", 0),
        "sector": r.get("sector", "未知"),
        "phase_code": r.get("phase_code", "—"),
        "direction": r['direction'],
        "flux": r['flux'],
        "last_price": r['last_price'],
        "latest_zone_center": r['latest_zone_center'],
        "latest_zone_bw": r['latest_zone_bw'],
        "added_at": datetime.now().isoformat(),
    }
    save_watch_pool(st.session_state["watch_pool"])
    st.success(f"✅ {r['symbol']} 已加入观察池")


def render_watch_pool(dashboard_data: list[dict]):
    """渲染观察池 + 自选提醒"""
    from src.workbench.tab_scan import load_watch_pool, save_watch_pool

    st.markdown("#### ⭐ 观察池")

    if "watch_pool" not in st.session_state:
        st.session_state["watch_pool"] = load_watch_pool()

    watch_pool = st.session_state.get("watch_pool", {})
    if not watch_pool:
        st.caption("尚无观察池合约，在合约详情中点击「⭐ 加入观察池」")
        return

    st.caption(f"已关注 {len(watch_pool)} 个合约")

    wp_cols = st.columns([3, 1])
    with wp_cols[0]:
        for sym, info in sorted(watch_pool.items(), key=lambda x: -x[1].get("priority_score", 0)):
            dir_icon = fmt_direction(info.get("direction", "unclear"))
            ps = info.get("priority_score", 0)
            ps_color = fmt_priority_color(ps)
            sector = info.get("sector", "未知")
            phase = info.get("phase_code", "—")

            # 自选提醒
            current_data = next((r for r in dashboard_data if r["symbol"] == sym), None)
            alert_parts = []
            if current_data:
                old_phase = info.get("phase_code", "")
                new_phase = current_data.get("phase_code", "")
                if old_phase != new_phase:
                    phase_labels = {"breakout": "破缺", "confirmation": "确认", "forming": "形成", "stable": "稳态", "breakdown": "回落"}
                    alert_parts.append(f'⚠️ 阶段变化: {phase_labels.get(old_phase, old_phase)} → {phase_labels.get(new_phase, new_phase)}')
                zone_bw = current_data.get("latest_zone_bw", 0)
                last_price = current_data.get("last_price", 0)
                zone_center = current_data.get("latest_zone_center", 0)
                if zone_bw > 0:
                    deviation = abs(last_price - zone_center) / zone_bw
                    if deviation > 1.5:
                        alert_parts.append('🔔 价格远离稳态！')
            else:
                alert_parts.append('已退出扫描范围')

            remove_key = f"remove_watch_{sym}"
            rm_col, info_col = st.columns([1, 8])
            with rm_col:
                if st.button("❌", key=remove_key, help=f"移除 {sym}"):
                    if sym in st.session_state.get("watch_pool", {}):
                        del st.session_state["watch_pool"][sym]
                        save_watch_pool(st.session_state["watch_pool"])
                        st.rerun()
            with info_col:
                alert_html = ' · '.join(f'<span style="color:#e65100;font-weight:600">{a}</span>' for a in alert_parts) if alert_parts else ""
                st.markdown(f"""
                <div style="border-left:3px solid {ps_color};padding:4px 8px;margin:2px 0;background:#fafafa;border-radius:4px">
                    <b>{sym}</b> · {info.get('symbol_name', '')}
                    · <span style="color:{ps_color};font-weight:600">P{ps:.0f}</span>
                    · {dir_icon} · {sector} · {phase}
                    · 稳态 {info.get('latest_zone_center', 0):.0f}±{info.get('latest_zone_bw', 0):.0f}
                    {'<br>' + alert_html if alert_html else ''}
                </div>
                """, unsafe_allow_html=True)

    with wp_cols[1]:
        if st.button("🗑️ 清空观察池", key="clear_watch_pool"):
            st.session_state["watch_pool"] = {}
            save_watch_pool({})
            st.rerun()


# ═══════════════════════════════════════════════════════════
# 跨品种一致性
# ═══════════════════════════════════════════════════════════

def render_cross_commodity_consistency(dashboard_data: list[dict], META: dict):
    """渲染跨品种信号一致性分析"""
    st.markdown("#### 🔗 跨品种信号一致性")

    try:
        exchange_groups = {}
        for r in dashboard_data[:20]:
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


# ═══════════════════════════════════════════════════════════
# 每日变化报告
# ═══════════════════════════════════════════════════════════

def render_daily_change_report(dashboard_data: list[dict]):
    """渲染每日变化报告（与上次扫描对比）"""
    st.markdown("#### 📋 每日变化报告")

    _today_key = datetime.now().strftime("%Y-%m-%d")
    _prev_results = st.session_state.get("prev_scan_results", {})
    _prev_date = st.session_state.get("prev_scan_date", "")

    if _prev_date == _today_key and _prev_results:
        prev_map = {(r["symbol"], r["latest_zone_center"]): r for r in _prev_results}
        curr_map = {(r["symbol"], r["latest_zone_center"]): r for r in dashboard_data[:20]}

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


# ═══════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════

def render_export_section(dashboard_data: list[dict], sensitivity: str):
    """渲染导出扫描结果区块"""
    _today_key = datetime.now().strftime("%Y-%m-%d")

    st.markdown("#### 📤 导出扫描结果")

    stage_groups = {}
    for r in dashboard_data:
        stage = r.get("motion_label", "未分类")
        stage_groups.setdefault(stage, []).append(r)

    stage_options = ["全部"] + sorted(stage_groups.keys(), key=lambda s: -len(stage_groups[s]))
    selected_stage = st.selectbox("按阶段筛选", stage_options, index=0, key="export_stage_filter")

    if selected_stage == "全部":
        export_results = dashboard_data[:50]
    else:
        export_results = stage_groups.get(selected_stage, [])[:50]

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
                "volume": r["volume"],
                "last_price": r["last_price"],
                "latest_zone_center": r["latest_zone_center"],
                "latest_zone_bw": r["latest_zone_bw"],
                "cycles": r["cycles"],
                "motion": r["motion"],
                "motion_label": r["motion_label"],
                "flux": r["flux"],
                "score": r["score"],
                "tier": r.get("tier", "?"),
                "direction": r["direction"],
                "zone_trend": r["zone_trend"],
                "zone_relation": r["zone_relation"],
                "price_position": r["price_position"],
                "breakout_date": r.get("breakout_date", ""),
                "departure_score": r.get("departure_score", 0),
                "zones": [{"center": z["center"], "bw": z["bw"], "date_range": z["date_range"]} for z in r.get("zones", [])],
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
            dir_icon = fmt_direction(r["direction"])
            sig = r.get("signal") or {}
            sl = sig.get("stop_loss_price", 0)
            tp = sig.get("take_profit_price", 0)
            rr = sig.get("rr_ratio", 0)

            md_lines.append(f"## #{i} {r['symbol']} ({r['symbol_name']})")
            md_lines.append(f"- {dir_icon} · Zone {r['latest_zone_center']:.0f} · {r['cycles']}次试探 · {r['zone_trend']}")
            md_lines.append(f"- 质量 {r['score']:.0f}分 · {r.get('tier', '?')}层 · 通量{r['flux']:+.2f}")
            md_lines.append(f"- 现价{r['last_price']:.1f} · {r['price_position']} · 离稳态{r.get('departure_score', 0):.0f}")
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


# ═══════════════════════════════════════════════════════════
# 日报生成（Task 7-3）
# ═══════════════════════════════════════════════════════════

def generate_daily_report_markdown(
    dashboard_data: list[dict],
    sensitivity: str,
    prev_scan_data: list[dict] | None = None,
    prev_scan_date: str = "",
) -> str:
    """
    生成每日研究报告 Markdown 文本。

    结构：日期标题 → 市场概览 → 今日三选 → 观察池变化 → 明日跟踪清单

    Args:
        dashboard_data: 完整扫描结果
        sensitivity: 灵敏度
        prev_scan_data: 上次扫描结果（用于观察池变化对比）
        prev_scan_date: 上次扫描日期

    Returns:
        Markdown 格式的日报文本
    """
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []

    # 日期标题
    lines.append(f"# 每日研究报告 — {today}")
    lines.append(f"灵敏度: {sensitivity} · 扫描时间: {datetime.now().strftime('%H:%M')}")
    lines.append("")

    # 市场概览
    overview = build_market_overview(dashboard_data)
    lines.append("## 市场概览")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 活跃合约数 | {overview['active_count']} |")
    lines.append(f"| 高离稳态数 | {overview['departure_count']} |")
    lines.append(f"| 破缺数 | {overview['breakout_count']} |")
    lines.append(f"| 确认数 | {overview['confirmation_count']} |")
    lines.append("")

    # 今日三选
    today_three = pick_today_three(dashboard_data)
    lines.append("## 今日三选")
    lines.append("")
    if today_three:
        lines.append("| 排名 | 品种 | 名称 | 理由 | 优先级 | 阶段 | 方向 | 通量 | 离稳态 |")
        lines.append("|------|------|------|------|--------|------|------|------|--------|")
        for i, r in enumerate(today_three, 1):
            dir_icon = fmt_direction(r["direction"])
            lines.append(
                f"| {i} | {r['symbol']} | {r['symbol_name']} | {r.get('pick_reason', '')} "
                f"| P{r.get('priority_score', 0):.0f} | {r.get('motion_label', '—')} "
                f"| {dir_icon} {r['direction']} | {r.get('flux', 0):+.3f} | {r.get('departure_score', 0):.0f} |"
            )
    else:
        lines.append("今日无符合条件的三选。")
    lines.append("")

    # 观察池变化
    lines.append("## 观察池变化")
    lines.append("")

    watch_pool = {}
    try:
        from src.workbench.tab_scan import load_watch_pool
        watch_pool = load_watch_pool()
    except Exception:
        pass

    if watch_pool:
        current_map = {r["symbol"]: r for r in dashboard_data}
        changes = []
        for sym, info in watch_pool.items():
            curr = current_map.get(sym)
            if curr:
                old_phase = info.get("phase_code", "")
                new_phase = curr.get("phase_code", "")
                if old_phase != new_phase:
                    changes.append(f"- **{sym}** {info.get('symbol_name', '')}: 阶段 {old_phase} → {new_phase}")
                elif abs(curr.get("flux", 0) - info.get("flux", 0)) > 0.3:
                    changes.append(f"- **{sym}** {info.get('symbol_name', '')}: 通量 {info.get('flux', 0):+.2f} → {curr.get('flux', 0):+.2f}")
            else:
                changes.append(f"- **{sym}** {info.get('symbol_name', '')}: 已退出扫描范围")

        if changes:
            lines.extend(changes)
        else:
            lines.append("观察池无变化。")
    else:
        lines.append("观察池为空。")
    lines.append("")

    # 与上次扫描对比
    if prev_scan_data:
        lines.append(f"## 与 {prev_scan_date} 对比")
        lines.append("")
        prev_map = {r["symbol"]: r for r in prev_scan_data}
        curr_map = {r["symbol"]: r for r in dashboard_data[:20]}

        new_syms = set(curr_map) - set(prev_map)
        gone_syms = set(prev_map) - set(curr_map)
        changed = []
        for sym in set(curr_map) & set(prev_map):
            if curr_map[sym]["motion"] != prev_map[sym]["motion"]:
                changed.append(sym)

        if new_syms:
            lines.append(f"**新增**: {', '.join(sorted(new_syms))}")
        if gone_syms:
            lines.append(f"**退出**: {', '.join(sorted(gone_syms))}")
        if changed:
            lines.append(f"**阶段变化**: {', '.join(sorted(changed))}")
        if not new_syms and not gone_syms and not changed:
            lines.append("Top 20 无变化。")
        lines.append("")

    # 明日跟踪清单
    lines.append("## 明日跟踪清单")
    lines.append("")
    # 优先级最高的 5 个 + 观察池中的合约
    top5 = sorted(dashboard_data, key=lambda x: x.get("priority_score", 0), reverse=True)[:5]
    tracked = set()
    for r in top5:
        risk_tags = build_risk_tags(r)
        tag_str = " ".join(risk_tags) if risk_tags else ""
        lines.append(f"- [ ] **{r['symbol']}** {r['symbol_name']} — {r.get('motion_label', '—')} · P{r.get('priority_score', 0):.0f} {tag_str}")
        tracked.add(r["symbol"])

    # 观察池中不在 top5 的也加入
    for sym in watch_pool:
        if sym not in tracked:
            info = watch_pool[sym]
            lines.append(f"- [ ] **{sym}** {info.get('symbol_name', '')} — 观察池 · P{info.get('priority_score', 0):.0f}")
    lines.append("")

    lines.append("---")
    lines.append(f"*由价格结构研究工作台自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def render_daily_report_button(dashboard_data: list[dict], sensitivity: str):
    """在页面底部提供「生成日报」按钮"""
    st.markdown("---")
    st.markdown("#### 📝 生成每日研究报告")

    if st.button("📝 生成日报", type="primary", key="btn_generate_daily_report", use_container_width=True):
        prev_data = st.session_state.get("prev_scan_results")
        prev_date = st.session_state.get("prev_scan_date", "")

        md_text = generate_daily_report_markdown(
            dashboard_data=dashboard_data,
            sensitivity=sensitivity,
            prev_scan_data=prev_data,
            prev_scan_date=prev_date,
        )

        # 保存到 session_state 供预览
        st.session_state["daily_report_md"] = md_text

    # 如果已有日报，展示预览和下载
    if "daily_report_md" in st.session_state:
        md_text = st.session_state["daily_report_md"]

        # 预览
        with st.expander("📋 日报预览", expanded=True):
            st.markdown(md_text)

        # 下载
        today = datetime.now().strftime("%Y-%m-%d")
        st.download_button(
            "📥 下载日报 Markdown",
            data=md_text,
            file_name=f"daily_report_{today}.md",
            mime="text/markdown",
            use_container_width=True,
        )
