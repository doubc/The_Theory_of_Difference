"""
Tab 0: 今天值得关注什么 — 全市场机会扫描、今日三选、跨品种一致性、每日变化报告

从 app.py 提取的独立模块。
"""
from __future__ import annotations

import streamlit as st
from datetime import datetime
from pathlib import Path
import json
import os

# 观察池持久化路径
WATCH_POOL_FILE = Path(__file__).parent.parent / "data" / "watch_pool.json"


def load_watch_pool():
    """从文件加载观察池"""
    if WATCH_POOL_FILE.exists():
        try:
            return json.loads(WATCH_POOL_FILE.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def save_watch_pool(wp):
    """保存观察池到文件"""
    try:
        WATCH_POOL_FILE.write_text(json.dumps(wp, ensure_ascii=False, indent=2), "utf-8")
    except Exception:
        pass

from src.compiler.pipeline import compile_full, CompilerConfig
from src.workbench.shared import (
    motion_badge, movement_badge, struct_status, struct_scenario, struct_invalidation,
    TIER_COLORS, make_candlestick,
)
from src.workbench.data_layer import load_bars
from src.workbench.scan_pipeline import departure_score as _departure_score


def _build_dashboard_data(ALL_SYMBOLS, load_bars_fn, compile_fn, sens_key: str,
                          min_volume: float = 20000) -> list[dict]:
    """
    成交量驱动的全景仪表盘数据构建。

    为每个最新日成交量 > min_volume 的合约，提取：
    - 稳态序列（所有 Zone 按时间排序）
    - 趋势方向、稳态关系
    - 当前价格相对最近稳态的位置
    - 运动阶段、通量、质量
    """
    from datetime import timedelta
    from src.data.symbol_meta import symbol_name as _symbol_name
    from src.quality import assess_quality, QualityTier

    _sens = {
        "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3, "lookback_days": 240},
        "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2, "lookback_days": 180},
        "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2, "lookback_days": 120},
    }
    _s = _sens.get(sens_key, _sens["标准"])
    lookback = _s["lookback_days"]

    results = []
    for sym in ALL_SYMBOLS:
        bars_data = load_bars_fn(sym)
        if not bars_data or len(bars_data) < 30:
            continue

        # 成交量筛选：最新一根Bar的成交量
        latest_vol = bars_data[-1].volume
        if latest_vol < min_volume:
            continue

        # 取最近 lookback 天
        if len(bars_data) > lookback:
            bars_data = bars_data[-lookback:]

        last_price = bars_data[-1].close
        last_date = bars_data[-1].timestamp.strftime("%Y-%m-%d")

        cfg = CompilerConfig(
            min_amplitude=_s["min_amp"], min_duration=_s["min_dur"],
            min_cycles=_s["min_cycles"],
            adaptive_pivots=True, fractal_threshold=0.34,
        )
        cr = compile_fn(bars_data, cfg, symbol=sym)
        if not cr.ranked_structures:
            continue

        # ── 提取稳态序列（所有 Structure 的 Zone，按 t_start 排序）──
        structs = sorted(cr.ranked_structures, key=lambda s: s.t_start or datetime.min)
        zones_info = []
        for s in structs:
            if s.zone:
                t_start_str = s.t_start.strftime("%m/%d") if s.t_start else "?"
                t_end_str = s.t_end.strftime("%m/%d") if s.t_end else "?"
                zones_info.append({
                    "center": round(s.zone.price_center, 1),
                    "bw": round(s.zone.bandwidth, 1),
                    "upper": round(s.zone.upper, 1),
                    "lower": round(s.zone.lower, 1),
                    "date_range": f"{t_start_str}~{t_end_str}",
                    "cycles": s.cycle_count,
                    "t_start": s.t_start,
                    "t_end": s.t_end,
                })

        if not zones_info:
            continue

        # 最近稳态 = 最后一个 Structure 的 Zone
        latest_zone = zones_info[-1]
        prev_zone = zones_info[-2] if len(zones_info) >= 2 else None

        # ── 稳态趋势 ──
        if len(zones_info) >= 2:
            centers = [z["center"] for z in zones_info]
            avg_change = (centers[-1] - centers[0]) / len(centers) if len(centers) > 1 else 0
            if avg_change > latest_zone["bw"] * 0.3:
                zone_trend = "上行"
            elif avg_change < -latest_zone["bw"] * 0.3:
                zone_trend = "下行"
            else:
                zone_trend = "持平"
        else:
            zone_trend = "—"

        # ── 稳态关系 ──
        if prev_zone:
            center_diff = abs(latest_zone["center"] - prev_zone["center"])
            combined_bw = latest_zone["bw"] + prev_zone["bw"]
            overlap = min(latest_zone["upper"], prev_zone["upper"]) - max(latest_zone["lower"], prev_zone["lower"])
            overlap_ratio = overlap / combined_bw if combined_bw > 0 else 0

            if overlap_ratio > 0.5:
                zone_relation = "延续"
            elif center_diff < combined_bw * 0.8:
                zone_relation = "收窄"
            else:
                zone_relation = "跃迁"
        else:
            zone_relation = "—"

        # ── 价格位置 ──
        z_upper = latest_zone["upper"]
        z_lower = latest_zone["lower"]
        z_center = latest_zone["center"]
        z_bw = latest_zone["bw"]

        # Zone 过期判定：价格离 Zone 中心超过 20% 认为 Zone 已过期
        zone_distance_pct = abs(last_price - z_center) / z_center * 100 if z_center > 0 else 0
        zone_is_stale = zone_distance_pct > 20.0

        if zone_is_stale:
            price_position = f"⚠️ 过期({zone_distance_pct:.0f}%偏离)"
        elif last_price > z_upper:
            pct_above = (last_price - z_center) / z_bw if z_bw > 0 else 0
            if pct_above > 3.0:
                price_position = f"⚠️ 过期({pct_above:.1f}x偏离)"
            else:
                price_position = f"↑ 破缺上行 +{pct_above:.1f}x"
        elif last_price < z_lower:
            pct_below = (z_center - last_price) / z_bw if z_bw > 0 else 0
            if pct_below > 3.0:
                price_position = f"⚠️ 过期({pct_below:.1f}x偏离)"
            else:
                price_position = f"↓ 破缺下行 -{pct_below:.1f}x"
        else:
            dist_to_upper = (z_upper - last_price) / z_bw if z_bw > 0 else 0.5
            dist_to_lower = (last_price - z_lower) / z_bw if z_bw > 0 else 0.5
            if dist_to_upper < 0.15 or dist_to_lower < 0.15:
                price_position = " ! 试探边界"
            else:
                price_position = " · 稳态内"

        # ── 运动阶段（取最新 Structure）──
        latest_struct = structs[-1]
        m = latest_struct.motion
        p = latest_struct.projection
        ss = cr.get_system_state_for(latest_struct)
        qa = assess_quality(latest_struct, ss)

        phase_str = m.phase_tendency if m else ""
        n_cycles = latest_struct.cycle_count
        if "breakout" in phase_str:
            motion_label = "🔴 破缺"
        elif "confirmation" in phase_str:
            motion_label = "🟢 确认"
        elif "forming" in phase_str:
            # 区分早期形成（少周期）和成熟形成（多周期，接近投票阈值）
            if n_cycles >= 2:
                motion_label = f"🔵 形成({n_cycles}次)"
            else:
                motion_label = "🔵 初形成"
        elif "stable" in phase_str:
            motion_label = "⚪ 稳态"
        elif "breakdown" in phase_str:
            motion_label = "🟠 回落"
        else:
            motion_label = "—"

        # 方向：综合价格位置 + 通量，避免趋势与价格位置矛盾
        if zone_is_stale:
            # Zone 过期时方向不可靠
            direction = "unclear"
        elif "breakout" in phase_str:
            # 破缺方向以价格位置为准
            direction = "up" if last_price > z_center else "down"
        elif "confirmation" in phase_str:
            # 确认方向以价格位置为准
            direction = "up" if last_price > z_center else "down"
        elif m and abs(m.conservation_flux) > 0.2:
            # 非破缺/确认时，用通量方向
            direction = "up" if m.conservation_flux > 0 else "down"
        else:
            direction = "unclear"

        # 破缺确认日
        breakout_date = ""
        if m and ("breakout" in m.phase_tendency or "confirmation" in m.phase_tendency):
            if latest_struct.t_end:
                breakout_date = latest_struct.t_end.strftime("%m/%d")

        # 通量：结构周期数不足时通量不可靠，标记为参考值
        flux_val = round(m.conservation_flux, 3) if m else 0.0
        flux_reliable = n_cycles >= 3  # 至少3个周期通量才有参考价值

        # 离稳态活跃度
        dep_score = _departure_score({
            "phase_transition": "→" in phase_str,
            "flux_magnitude": abs(flux_val),
            "departure_velocity": max(0, -(m.stable_velocity if m else 0)),
            "signal_score": qa.score,  # 使用质量评估的实际分数
        })

        # ── 4-1: 信号详情 ──
        signal_info = None
        try:
            from src.signals import generate_signal
            sig = generate_signal(latest_struct, bars=bars_data, system_state=ss)
            if sig:
                signal_info = {
                    "kind": sig.kind.value,
                    "direction": sig.direction,
                    "confidence": round(sig.confidence, 3),
                    "flux_aligned": sig.flux_aligned,
                    "stability_ok": sig.stability_ok,
                    "entry_note": sig.entry_note,
                    "breakout_score": round(sig.breakout_score, 3),
                    "fake_pattern": sig.fake_pattern.value if sig.fake_pattern else None,
                    "quality_tier": sig.quality_tier,
                    "entry_price": round(sig.entry_price, 1),
                    "stop_loss_price": round(sig.stop_loss_price, 1),
                    "take_profit_price": round(sig.take_profit_price, 1),
                    "rr_ratio": round(sig.rr_ratio, 2),
                    "position_size_factor": round(sig.position_size_factor, 2),
                    "signal_type_label": sig.signal_type_label(),
                    "display_label": sig.display_label,
                }
        except Exception:
            pass

        # ── Phase 1: 新增字段 ──
        # price_position_code (1-2)
        if zone_is_stale:
            price_position_code = "S"  # Stale = Zone过期
        elif last_price > z_upper:
            price_position_code = "H"
        elif last_price < z_lower:
            price_position_code = "L"
        else:
            price_position_code = "M"

        # phase_code (1-3)
        phase_code = phase_str.split("→")[-1].strip() if "→" in phase_str else phase_str
        if not phase_code or phase_code == "—":
            phase_code = "stable"

        # sector (1-4)
        from src.data.symbol_meta import get_sector
        sector = get_sector(sym)

        # priority_score (1-5)
        phase_map_score = {"breakout": 1.0, "confirmation": 0.8, "forming": 0.5, "stable": 0.3, "breakdown": 0.2}
        pos_map_score = {"H": 1.0, "M": 0.6, "L": 0.8, "S": 0.2}
        dep_score_norm = min(dep_score / 100, 1.0)
        quality_score_norm = qa.score
        phase_score = phase_map_score.get(phase_code, 0.3)
        position_score = pos_map_score.get(price_position_code, 0.5)
        max_vol = max((r.get("volume", 1) for r in results), default=1) if results else 1
        volume_score = min(latest_vol / max(max_vol, 1), 1.0)
        priority_score = dep_score_norm * 0.30 + quality_score_norm * 0.20 + phase_score * 0.20 + position_score * 0.15 + volume_score * 0.15

        results.append({
            "symbol": sym,
            "symbol_name": _symbol_name(sym),
            "volume": int(latest_vol),
            "last_price": round(last_price, 1),
            "last_date": last_date,
            # 稳态序列
            "zones": zones_info,
            "latest_zone_center": latest_zone["center"],
            "latest_zone_bw": latest_zone["bw"],
            "zone_trend": zone_trend,
            "zone_relation": zone_relation,
            "zone_count": len(zones_info),
            # 价格位置
            "price_position": price_position,
            "price_position_code": price_position_code,  # 1-2
            # 运动
            "motion": phase_str or "—",
            "motion_label": motion_label,
            "phase_code": phase_code,  # 1-3
            "flux": flux_val,
            "flux_reliable": flux_reliable,
            "direction": direction,
            # 确认日
            "breakout_date": breakout_date,
            # 质量
            "tier": qa.tier.value,
            "score": round(qa.score * 100, 1),
            "cycles": latest_struct.cycle_count,
            "is_blind": p.is_blind if p else False,
            # 离稳态
            "departure_score": round(dep_score, 1),
            # 板块
            "sector": sector,  # 1-4
            # 优先级
            "priority_score": round(priority_score * 100, 1),  # 1-5
            # 信号详情 (4-1)
            "signal_info": signal_info,
        })

    # 默认按成交量降序
    results.sort(key=lambda x: x["volume"], reverse=True)
    return results


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


    scan_col1, scan_col2, scan_col3 = st.columns([1, 2, 1])
    with scan_col1:
        run_scan = st.button("🔍 全市场扫描", type="primary", use_container_width=True, key="btn_market_scan")
    with scan_col2:
        st.caption("扫描所有成交量>2万手的合约，展示结构状态全景")
    with scan_col3:
        with st.popover("ℹ️ 仪表盘说明"):
            st.markdown("""
            **成交量驱动的全景仪表盘**

            列出所有最新日成交量 > 2万手的合约，按成交量降序排列。

            **每行展示**：
            - 趋势类型（上行/下行/持平）
            - 稳态序列及稳态间关系（延续/收窄/跃迁）
            - 当前价格相对最近稳态的位置
            - 运动阶段（破缺/确认/形成/稳态/回落）
            - 通量、质量层、离稳态活跃度

            **自由排序**：成交量、现价、趋势、通量、质量、离稳态分数等
            """)

    sensitivity = ctx.get("sensitivity", "标准")

    if run_scan:
        total_syms = len(ALL_SYMBOLS)
        with st.spinner(f"🔍 正在扫描 {total_syms} 个品种..."):
            prog = st.progress(0, text=f"准备扫描 {total_syms} 个品种...")
            dashboard_data = _build_dashboard_data(ALL_SYMBOLS, load_bars, compile_full, sensitivity)
            prog.progress(1.0, text=f"✅ 扫描完成，发现 {len(dashboard_data)} 个活跃合约")

        if dashboard_data:
            # 自动保存到活动日志
            try:
                from src.workbench.activity_log import ActivityLog
                scan_for_log = [{
                    "symbol": r["symbol"], "symbol_name": r["symbol_name"],
                    "zone_center": r["latest_zone_center"], "zone_bw": r["latest_zone_bw"],
                    "cycles": r["cycles"], "motion": r["motion"],
                    "flux": r["flux"], "score": r["score"], "direction": r["direction"],
                    "tier": r["tier"], "is_blind": r["is_blind"],
                } for r in dashboard_data]
                ActivityLog().save_scan(scan_for_log, sensitivity=sensitivity)
            except Exception:
                pass

            # 持久化到 session_state
            _today_key = datetime.now().strftime("%Y-%m-%d")
            st.session_state["scan_results_full"] = dashboard_data
            st.session_state["prev_scan_results"] = dashboard_data[:20]
            st.session_state["prev_scan_date"] = _today_key
    else:
        # 非扫描时从 session_state 恢复（筛选器变化触发 rerun）
        dashboard_data = st.session_state.get("scan_results_full", [])

    if dashboard_data:

        # ── 筛选 + 排序控制面板 ──
        st.markdown("---")
        fc1, fc2, fc3, fc4, fc5, fc6, fc7, fc8 = st.columns(8)

        with fc1:
            sort_options = {
                "优先级↓": ("priority_score", False),
                "成交量↓": ("volume", False),
                "成交量↑": ("volume", True),
                "现价↓": ("last_price", False),
                "现价↑": ("last_price", True),
                "通量↓": ("flux", False),
                "通量↑": ("flux", True),
                "质量↓": ("score", False),
                "离稳态↓": ("departure_score", False),
                "Zone价格↓": ("latest_zone_center", False),
                "信号分↓": ("signal_score", False),
            }
            sort_label = st.selectbox("排序", list(sort_options.keys()), key="dash_sort")

        with fc2:
            dir_filter = st.selectbox("方向", ["全部", "📈 偏多", "📉 偏空", "➡️ 不明"], key="dash_dir")

        with fc3:
            motion_filter = st.selectbox("运动阶段", ["全部", "破缺", "确认", "形成", "稳态", "回落"], key="dash_motion")

        with fc4:
            price_pos_filter = st.selectbox("价格位置", ["全部", "高位", "中位", "低位", "过期"], key="dash_price_pos")

        with fc5:
            tier_filter = st.selectbox("质量层", ["全部", "A", "B", "C"], key="dash_tier")

        with fc6:
            zone_trend_filter = st.selectbox("趋势", ["全部", "上行", "下行", "持平"], key="dash_trend")

        with fc7:
            sector_filter = st.selectbox("板块", ["全部", "黑色金属", "有色金属", "能源化工", "农产品", "贵金属"], key="dash_sector")

        with fc8:
            min_vol = st.number_input("最低成交量", value=20000, step=5000, key="dash_min_vol")

        # 应用筛选
        filtered = dashboard_data
        if dir_filter != "全部":
            dir_map = {"📈 偏多": "up", "📉 偏空": "down", "➡️ 不明": "unclear"}
            filtered = [r for r in filtered if r["direction"] == dir_map[dir_filter]]
        if motion_filter != "全部":
            motion_map = {"破缺": "breakout", "确认": "confirmation", "形成": "forming", "稳态": "stable", "回落": "breakdown"}
            target_code = motion_map[motion_filter]
            filtered = [r for r in filtered if r.get("phase_code") == target_code]
        if price_pos_filter != "全部":
            pos_map = {"高位": "H", "中位": "M", "低位": "L", "过期": "S"}
            target_code = pos_map[price_pos_filter]
            filtered = [r for r in filtered if r.get("price_position_code") == target_code]
        if tier_filter != "全部":
            filtered = [r for r in filtered if r.get("tier") == tier_filter]
        if zone_trend_filter != "全部":
            filtered = [r for r in filtered if r.get("zone_trend") == zone_trend_filter]
        if sector_filter != "全部":
            filtered = [r for r in filtered if r.get("sector") == sector_filter]
        if min_vol > 0:
            filtered = [r for r in filtered if r["volume"] >= min_vol]

        # 应用排序
        sort_key, sort_asc = sort_options[sort_label]
        filtered.sort(key=lambda x: x.get(sort_key, 0), reverse=not sort_asc)

        # ── 统计摘要 ──
        st.markdown("---")
        n_up = sum(1 for r in filtered if r["direction"] == "up")
        n_down = sum(1 for r in filtered if r["direction"] == "down")
        n_breakout = sum(1 for r in filtered if "breakout" in (r.get("motion") or ""))
        n_confirm = sum(1 for r in filtered if "confirmation" in (r.get("motion") or ""))

        stat_c = st.columns(5)
        stat_c[0].metric("活跃合约", len(filtered))
        stat_c[1].metric("📈 偏多", n_up)
        stat_c[2].metric("📉 偏空", n_down)
        stat_c[3].metric("🔴 破缺中", n_breakout)
        stat_c[4].metric("🟢 确认中", n_confirm)

        # ── 3-1: 板块热度图 ──
        st.markdown("---")
        st.markdown("#### 🗺️ 板块热度图")

        sector_groups = {}
        for r in filtered:
            sec = r.get("sector", "未知")
            sector_groups.setdefault(sec, []).append(r)

        if sector_groups:
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
        else:
            st.caption("无板块数据")

        # ── 3-2: 机会队列 ──
        st.markdown("---")
        st.markdown("#### 🎯 机会队列")
        st.caption("按板块分组，展示各板块优先级最高的机会")

        for sec_name, sec_items in sorted(sector_groups.items(), key=lambda x: -len(x[1])):
            sec_sorted = sorted(sec_items, key=lambda x: x.get("priority_score", 0), reverse=True)
            top3 = sec_sorted[:3]

            with st.expander(f"{sec_name} — {len(sec_items)}个 · 🏆{top3[0]['symbol']} P{top3[0].get('priority_score', 0):.0f}"):
                for r in top3:
                    dir_icon = "📈" if r["direction"] == "up" else "📉" if r["direction"] == "down" else "➡️"
                    ps = r.get("priority_score", 0)
                    phase = r.get("motion_label", "—")
                    pos = r.get("price_position", "—")
                    flux = r.get("flux", 0)
                    dep = r.get("departure_score", 0)
                    tier = r.get("tier", "?")
                    vol = r.get("volume", 0)
                    flux_str = f"{flux:+.2f}" if r.get("flux_reliable", True) else "—"
                    ps_color = "#4caf50" if ps >= 60 else "#ff9800" if ps >= 40 else "#999"
                    st.markdown(f"""
                    <div style="border-left:3px solid {ps_color};padding:4px 8px;margin:4px 0;background:#fafafa;border-radius:4px">
                        <b>{r['symbol']}</b> · {r['symbol_name']}
                        <span style="color:{ps_color};font-weight:600"> P{ps:.0f}</span>
                        · {dir_icon} · {phase} · {pos} · 通量{flux_str} · 离稳态{dep:.0f} · {tier}层 · 量{vol:,}
                    </div>
                    """, unsafe_allow_html=True)
                remaining = len(sec_sorted) - 3
                if remaining > 0:
                    st.caption(f"... 还有 {remaining} 个合约，见下方全景表格")

        # ── 全景仪表盘表格 ──
        st.markdown("---")
        st.markdown(f"#### 📊 合约结构全景（{len(filtered)} 个）")

        # 分页控制
        col_page, col_size = st.columns([3, 1])
        with col_size:
            page_size = st.selectbox("每页", [10, 20, 50], index=1, key="dash_page_size")
        total_pages = (len(filtered) + page_size - 1) // page_size
        with col_page:
            if total_pages > 1:
                page_idx = st.number_input("页码", min_value=1, max_value=total_pages, value=1, key="dash_page") - 1
            else:
                page_idx = 0
        start_idx = page_idx * page_size
        end_idx = min(start_idx + page_size, len(filtered))
        paged = filtered[start_idx:end_idx]
        st.caption(f"显示 {start_idx+1}-{end_idx} / 共 {len(filtered)} 个")

        # 构建表格数据
        table_rows = []
        for r in paged:
            # 稳态序列摘要
            zones = r.get("zones", [])
            if len(zones) >= 2:
                zone_summary = " → ".join(f"{z['center']:.0f}" for z in zones[-3:])
            elif zones:
                zone_summary = f"{zones[0]['center']:.0f}"
            else:
                zone_summary = "—"

            # 方向图标
            dir_icon = "📈" if r["direction"] == "up" else "📉" if r["direction"] == "down" else "➡️"

            # 通量颜色
            flux_val = r.get("flux", 0)

            # 破缺日期
            breakout_date = r.get("breakout_date", "")

            table_rows.append({
                "品种": f"{r['symbol']} · {r['symbol_name']}",
                "成交量": f"{r['volume']:,}",
                "现价": f"{r['last_price']:.0f}",
                "趋势": f"{dir_icon} {r['zone_trend']}",
                "稳态序列": zone_summary,
                "稳态关系": r["zone_relation"],
                "价格位置": r["price_position"],
                "运动阶段": r["motion_label"],
                "确认日": breakout_date,
                "通量": f"{flux_val:+.3f}" if r.get("flux_reliable", True) else "—",
                "质量": f"{r['tier']}层 {r['score']:.0f}",
                "离稳态": f"{r['departure_score']:.0f}",
                "_r": r,
            })

        # 渲染表格
        if table_rows:
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
                flux_color = "#4caf50" if r.get("flux", 0) > 0.2 else "#ef5350" if r.get("flux", 0) < -0.2 else "#999"
                html_parts.append(f'<td style="padding:5px 8px;color:{flux_color}">{row["通量"]}</td>')
                tier_color = {"A": "#4caf50", "B": "#2196f3", "C": "#ff9800"}.get(r.get("tier", "?"), "#999")
                html_parts.append(f'<td style="padding:5px 8px;color:{tier_color}">{row["质量"]}</td>')
                dep = r.get("departure_score", 0)
                dep_color = "#4caf50" if dep > 50 else "#ff9800" if dep > 25 else "#999"
                html_parts.append(f'<td style="padding:5px 8px;color:{dep_color}">{row["离稳态"]}</td>')
                html_parts.append('</tr>')
            html_parts.append('</tbody></table></div>')

            st.markdown("".join(html_parts), unsafe_allow_html=True)

            # 展开详情
            st.markdown("---")
            st.markdown("**📋 点击展开查看详情**")
            for i, row in enumerate(table_rows[:20]):
                r = row["_r"]
                ps = r.get("priority_score", 0)
                sector = r.get("sector", "未知")
                phase_code = r.get("phase_code", "—")
                pp_code = r.get("price_position_code", "—")
                ps_color = "#4caf50" if ps >= 60 else "#ff9800" if ps >= 40 else "#999"
                with st.expander(f"#{i+1} {r['symbol']} · {r['symbol_name']} — {r['motion_label']} · P{ps:.0f} · {sector}", expanded=False):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"**当前价格**: {r['last_price']:.0f}")
                        st.markdown(f"**成交量**: {r['volume']:,}")
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
                        pos_map_score = {"H": 1.0, "M": 0.6, "L": 0.8, "S": 0.2}
                        dep_pct = r.get('departure_score', 0) * 0.30
                        qual_pct = r.get('score', 0) / 100 * 0.20 * 100
                        phase_pct = phase_map_score.get(phase_code, 0) * 0.20 * 100
                        pos_pct = pos_map_score.get(pp_code, 0) * 0.15 * 100
                        st.caption(f"构成: 离稳态{dep_pct:.0f} + 质量{qual_pct:.0f} + 阶段{phase_pct:.0f} + 位置{pos_pct:.0f}")
                        # 操作按钮行
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            watch_key = f"watch_{r['symbol']}"
                            if st.button("⭐ 加入观察池", key=watch_key, use_container_width=True):
                                if "watch_pool" not in st.session_state:
                                    st.session_state["watch_pool"] = load_watch_pool()
                                st.session_state["watch_pool"][r['symbol']] = {
                                    "symbol": r['symbol'],
                                    "symbol_name": r['symbol_name'],
                                    "priority_score": ps,
                                    "sector": sector,
                                    "phase_code": phase_code,
                                    "direction": r['direction'],
                                "flux": r['flux'],
                                "last_price": r['last_price'],
                                "latest_zone_center": r['latest_zone_center'],
                                "latest_zone_bw": r['latest_zone_bw'],
                                "added_at": datetime.now().isoformat(),
                            }
                            st.success(f"✅ {r['symbol']} 已加入观察池")
                        with btn_col2:
                            analyze_key = f"analyze_{r['symbol']}"
                            if st.button("🔎 分析此合约", key=analyze_key, use_container_width=True):
                                st.session_state["analyze_symbol"] = r['symbol']
                                st.rerun()

                    # 4-1: Signal detail display
                    sig = r.get("signal_info")
                    if sig:
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
                                "fake_pin": "探针型",
                                "fake_dspike": "单K极端",
                                "fake_voldiv": "量能背离",
                                "fake_blind_whip": "盲区抽鞭",
                                "fake_gap": "跳空回补",
                                "fake_wick_cluster": "影线簇",
                                "fake_time_trap": "时间陷阱",
                            }
                            st.warning(f"⚠️ 假突破模式：{fake_labels.get(sig['fake_pattern'], sig['fake_pattern'])}")
                        if sig.get("entry_note"):
                            st.info(f"💡 {sig['entry_note']}")
                        # risk management
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

                    # 稳态序列详情
                    zones = r.get("zones", [])
                    if zones:
                        st.markdown("**稳态序列**:")
                        for zi, z in enumerate(zones):
                            st.markdown(f"  {zi+1}. Zone {z['center']:.0f} (±{z['bw']:.0f}) · {z['date_range']} · {z['cycles']}次试探")
        else:
            st.info("当前筛选条件下无匹配合约")

        # ── 3-4 + 3-5: 观察池 + 自选提醒 ──
        st.markdown("---")
        st.markdown("#### ⭐ 观察池")

        watch_pool = st.session_state.get("watch_pool", {})
        if watch_pool:
            st.caption(f"已关注 {len(watch_pool)} 个合约")

            wp_cols = st.columns([3, 1])
            with wp_cols[0]:
                for sym, info in sorted(watch_pool.items(), key=lambda x: -x[1].get("priority_score", 0)):
                    dir_icon = "📈" if info.get("direction") == "up" else "📉" if info.get("direction") == "down" else "➡️"
                    ps = info.get("priority_score", 0)
                    ps_color = "#4caf50" if ps >= 60 else "#ff9800" if ps >= 40 else "#999"
                    sector = info.get("sector", "未知")
                    phase = info.get("phase_code", "—")

                    # 3-5: 自选提醒 - 检查是否仍在活跃
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
        else:
            st.caption("尚无观察池合约，在合约详情中点击「⭐ 加入观察池」")

        # ── 跨品种信号一致性分析 ──
        st.markdown("---")
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

        # ── 每日变化报告 ──
        st.markdown("---")
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

        # ── 导出扫描结果 ──
        st.markdown("---")
        st.markdown("#### 📤 导出扫描结果")

        # 按运动阶段分类筛选
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

        # prev_scan 已在扫描完成后保存
    else:
        st.warning("🔍 未扫描到活跃结构")
        st.caption("可能原因：① 数据源无数据（检查 MySQL 连接或 data/ 目录）② 当前灵敏度下无满足条件的结构 — 试试侧栏调为「精细」")

    # ── 历史扫描回看 ──
    st.markdown("---")
    st.markdown("#### 📅 历史扫描回看")
    st.caption("选择过去的日期，查看当天的扫描结果，方便对照和回顾")

    try:
        from src.workbench.activity_log import ActivityLog
        _alog = ActivityLog()
        available_dates = _alog.get_available_scan_dates(days=90)

        if available_dates:
            def _scan_date_label(d: str) -> str:
                delta = (datetime.now().date() - datetime.strptime(d, "%Y-%m-%d").date()).days
                if delta == 0:
                    return "今天"
                elif delta == 1:
                    return "昨天"
                elif delta < 7:
                    return f"{delta}天前"
                return ""

            selected_date = st.selectbox(
                "选择日期",
                available_dates,
                format_func=lambda d: f"{d} ({_scan_date_label(d)})" if _scan_date_label(d) else d,
                key="hist_scan_date",
            )

            hist_results = _alog.get_scan_by_date(selected_date)

            if hist_results:
                # 按同样的综合评分排序
                hist_sorted = sorted(
                    hist_results,
                    key=lambda x: (
                        x.get("score", 0) * 0.40
                        + _departure_score(x) * 0.30
                        + x.get("recency", 0) * 30.0
                    ),
                    reverse=True,
                )

                st.markdown(f"**{selected_date} 扫描结果** — 共 {len(hist_results)} 个结构")

                # 历史结果筛选
                hf1, hf2, hf3 = st.columns(3)
                with hf1:
                    h_dir = st.selectbox("方向", ["全部", "📈 偏多", "📉 偏空", "➡️ 不明"], key="hist_dir_filter")
                with hf2:
                    h_motion = st.selectbox("运动阶段", ["全部", "breakout", "confirmation", "forming", "stable"], key="hist_motion_filter")
                with hf3:
                    h_min_dep = st.slider("最低离稳态分数", 0, 100, 0, key="hist_min_departure")

                hist_filtered = hist_sorted
                if h_dir != "全部":
                    h_dir_map = {"📈 偏多": "up", "📉 偏空": "down", "➡️ 不明": "unclear"}
                    hist_filtered = [r for r in hist_filtered if r.get("direction") == h_dir_map[h_dir]]
                if h_motion != "全部":
                    hist_filtered = [r for r in hist_filtered if h_motion in (r.get("motion") or "")]
                if h_min_dep > 0:
                    hist_filtered = [r for r in hist_filtered if _departure_score(r) >= h_min_dep]

                for i, r in enumerate(hist_filtered[:10]):
                    try:
                        dir_icon = "📈" if r.get("direction") == "up" else "📉" if r.get("direction") == "down" else "➡️"
                        t = r.get("tier", "?")
                        tier_fg, tier_bg = TIER_COLORS.get(t, ("#666", "#eee"))
                        tier_badge = f'<span style="background:{tier_bg};color:{tier_fg};padding:1px 6px;border-radius:3px;font-size:0.8em;font-weight:700">{t}层</span>'
                        motion_html = motion_badge(r.get("motion", "—"))
                        blind_tag = " · ⚠️高压缩" if r.get("is_blind") else ""
                        ds = r.get("days_since_end", 0) or 0
                        if ds <= 1:
                            fresh_tag = '<span style="color:#4caf50;font-weight:600">🔥 实时</span>'
                        elif ds <= 3:
                            fresh_tag = '<span style="color:#4caf50">✅ 活跃</span>'
                        elif ds <= 7:
                            fresh_tag = '<span style="color:#ff9800">⚡ 需刷新</span>'
                        else:
                            fresh_tag = '<span style="color:#999">📋 参考</span>'

                        dep_score = _departure_score(r)
                        dep_html = f'<span style="color:#2196f3;font-size:0.8em">离稳态 {dep_score:.0f}</span>' if dep_score > 30 else ""

                        st.markdown(f"""
                        <div class="structure-card">
                            <b>#{i+1}</b> {dir_icon}
                            <span class="zone-label">{r.get('symbol', '')} · {r.get('symbol_name', '')}</span>
                            {tier_badge}
                            <span class="meta-text"> Zone {r.get('zone_center', 0):.0f} (±{r.get('zone_bw', 0):.0f}) · {r.get('cycles', 0)}次试探</span>
                            · {motion_html} · 通量 {r.get('flux', 0):+.2f}{blind_tag}
                            · 质量 {r.get('score', 0):.0f}分 · {fresh_tag}
                            {f' · {dep_html}' if dep_html else ''}
                        </div>
                        """, unsafe_allow_html=True)
                    except Exception:
                        pass

                # 与今天对比
                if st.session_state.get("prev_scan_results") and st.button("🔄 与今天对比", key="compare_hist_today"):
                    today_results = st.session_state["prev_scan_results"]
                    today_date = st.session_state.get("prev_scan_date", "今天")
                    st.markdown(f"**📊 {selected_date} vs {today_date} 对比**")

                    today_syms = {r["symbol"]: r for r in today_results}
                    hist_syms = {r["symbol"]: r for r in hist_results}

                    # 仅在两个日期都有的品种上对比
                    common = set(today_syms) & set(hist_syms)
                    if common:
                        for sym in sorted(common):
                            t_r = today_syms[sym]
                            h_r = hist_syms[sym]
                            t_motion = t_r.get("motion", "—")
                            h_motion = h_r.get("motion", "—")
                            t_flux = t_r.get("flux", 0)
                            h_flux = h_r.get("flux", 0)
                            t_dir = t_r.get("direction", "unclear")
                            h_dir = h_r.get("direction", "unclear")
                            t_dep = _departure_score(t_r)
                            h_dep = _departure_score(h_r)

                            motion_changed = t_motion != h_motion
                            dir_changed = t_dir != h_dir
                            flag = " ⚠️" if motion_changed else (" ↗️" if t_dep > h_dep + 10 else "")

                            st.markdown(
                                f"**{sym}** {t_r.get('symbol_name', '')} · "
                                f"运动 {h_motion} → {t_motion}{flag} · "
                                f"通量 {h_flux:+.2f} → {t_flux:+.2f} · "
                                f"方向 {h_dir} → {t_dir} · "
                                f"离稳态 {h_dep:.0f} → {t_dep:.0f}"
                            )
                    else:
                        st.info("两个日期无重叠品种")
            else:
                st.info("该日期无扫描记录")
        else:
            st.info("暂无历史扫描记录，运行一次扫描后即可回看")
    except Exception as e:
        st.caption(f"历史回看加载失败: {e}")

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
                mt = s.motion.movement_type.value if s.motion and hasattr(s.motion, 'movement_type') else ""
                mt_html = f" · {movement_badge(mt)}" if mt else ""
                status = struct_status(s)
                scenario = struct_scenario(s)
                invalidation = struct_invalidation(s)
                # 主卡片核心信息
                st.markdown(f"""
                <div class="structure-card danger">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(s.motion.phase_tendency)}{mt_html}
                    · <span class="meta-text">通量 {flux}</span>
                    <div class="narrative-text">{s.narrative_context or ''}</div>
                </div>
                """, unsafe_allow_html=True)
                # 详细信息折叠
                with st.expander("📋 详情", expanded=False):
                    if status:
                        st.markdown(f"**状态**: {status}")
                    if scenario:
                        st.markdown(f"**剧本**: {scenario}")
                    if invalidation:
                        st.markdown(f"**失效条件**: {invalidation}")

        if confirming:
            st.markdown("**🟢 趋向确认**")
            for s in confirming[:3]:
                flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                mt = s.motion.movement_type.value if s.motion and hasattr(s.motion, 'movement_type') else ""
                mt_html = f" · {movement_badge(mt)}" if mt else ""
                status = struct_status(s)
                status_html = f'<div style="margin-top:4px;padding:4px 8px;background:#f5f5f5;border-radius:4px;font-size:0.9em;color:#333">{status}</div>' if status else ""
                scenario = struct_scenario(s)
                scenario_html = f'<div style="margin-top:4px;padding:4px 8px;background:#e8f5e9;border-radius:4px;font-size:0.88em;color:#2e7d32">{scenario}</div>' if scenario else ""
                invalidation = struct_invalidation(s)
                inv_html = f'<div style="margin-top:2px;padding:3px 8px;background:#fff3e0;border-radius:4px;font-size:0.85em;color:#e65100">{invalidation}</div>' if invalidation else ""
                st.markdown(f"""
                <div class="structure-card ok">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(s.motion.phase_tendency)}{mt_html}
                    · <span class="meta-text">通量 {flux}</span>
                    {status_html}
                    {scenario_html}
                    {inv_html}
                    <div class="narrative-text">{s.narrative_context or ''}</div>
                </div>
                """, unsafe_allow_html=True)

        if forming:
            st.markdown("**🔵 结构积累**")
            for s in forming[:5]:
                proj_warn = " · ⚠️ 高压缩" if (s.projection and s.projection.is_blind) else ""
                tendency = s.motion.phase_tendency if s.motion else 'unknown'
                mt = s.motion.movement_type.value if s.motion and hasattr(s.motion, 'movement_type') else ""
                mt_html = f" · {movement_badge(mt)}" if mt else ""
                status = struct_status(s)
                status_html = f'<div style="margin-top:4px;padding:4px 8px;background:#f5f5f5;border-radius:4px;font-size:0.9em;color:#333">{status}</div>' if status else ""
                scenario = struct_scenario(s)
                scenario_html = f'<div style="margin-top:4px;padding:4px 8px;background:#e8f5e9;border-radius:4px;font-size:0.88em;color:#2e7d32">{scenario}</div>' if scenario else ""
                invalidation = struct_invalidation(s)
                inv_html = f'<div style="margin-top:2px;padding:3px 8px;background:#fff3e0;border-radius:4px;font-size:0.85em;color:#e65100">{invalidation}</div>' if invalidation else ""
                st.markdown(f"""
                <div class="structure-card">
                    <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                    <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                    · {motion_badge(tendency)}{mt_html}{proj_warn}
                    {status_html}
                    {scenario_html}
                    {inv_html}
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

    # ── 内嵌合约分析（点击"分析此合约"后显示）──
    analyze_sym = st.session_state.get("analyze_symbol")
    if analyze_sym:
        st.markdown("---")
        st.markdown(f"#### 🔎 {analyze_sym} 快速分析")
        if st.button("❌ 关闭分析", key="close_analysis"):
            del st.session_state["analyze_symbol"]
            st.rerun()

        from src.data.sina_fetcher import fetch_bars as _sina_fetch, detect_source as _detect_src
        from src.compiler.pipeline import compile_full as _cf
        from src.workbench.shared import (
            motion_badge as _mb, movement_badge as _mgb,
            struct_status as _ss, struct_scenario as _sc, struct_invalidation as _si,
            make_candlestick as _mc,
        )

        _src = _detect_src(analyze_sym)
        _src_label = {"inner": "🇨🇳 国内期货", "global": "🌍 外盘期货", "fx": "💱 外汇"}.get(_src, _src)
        st.caption(f"数据源: {_src_label}")

        with st.spinner(f"📡 正在拉取 {analyze_sym} 数据..."):
            _bars = _sina_fetch(analyze_sym, freq="1d", timeout=15)

        if not _bars:
            st.error(f"❌ 未能获取 {analyze_sym} 的数据")
        else:
            st.success(f"✅ {_bars[0].timestamp:%Y-%m-%d} → {_bars[-1].timestamp:%Y-%m-%d} · {len(_bars)} 条")
            _cfg = CompilerConfig(min_amplitude=0.03, min_duration=3, min_cycles=2,
                                 adaptive_pivots=True, fractal_threshold=0.34)
            with st.spinner("🔧 编译结构..."):
                _cr = _cf(_bars, _cfg, symbol=analyze_sym)

            if not _cr.structures:
                st.warning("🔍 未识别到显著结构 — 试试在合约检索 tab 降低灵敏度")
            else:
                _last = _bars[-1].close
                _mc1, _mc2, _mc3, _mc4, _mc5 = st.columns(5)
                _mc1.metric("最新价", f"{_last:.2f}")
                _mc2.metric("结构数", len(_cr.structures))
                _mc3.metric("Zone 数", len(_cr.zones))
                _ss_r = sum(1 for s in _cr.system_states if s.is_reliable)
                _mc4.metric("可信结构", _ss_r)
                _blind = sum(1 for s in _cr.system_states if s.projection.is_blind)
                _mc5.metric("⚠️ 高压缩", _blind)

                for _s in _cr.ranked_structures[:3]:
                    _m = _s.motion
                    _flux = f"{_m.conservation_flux:+.2f}" if _m else "—"
                    _tendency = _m.phase_tendency if _m else ""
                    _mt = _m.movement_type.value if _m and hasattr(_m, 'movement_type') else ""
                    _mt_html = f" · {_mgb(_mt)}" if _mt else ""
                    _status = _ss(_s)
                    _scenario = _sc(_s)
                    _invalidation = _si(_s)

                    if "breakout" in _tendency:
                        _card_cls = "danger"
                    elif "confirmation" in _tendency:
                        _card_cls = "ok"
                    else:
                        _card_cls = ""

                    st.markdown(f"""
                    <div class="structure-card {_card_cls}">
                        <span class="zone-label">Zone {_s.zone.price_center:.0f}</span>
                        <span class="meta-text">(±{_s.zone.bandwidth:.0f}) · {_s.cycle_count}次试探</span>
                        · {_mb(_tendency)}{_mt_html}
                        · <span class="meta-text">通量 {_flux}</span>
                        <div class="narrative-text">{_s.narrative_context or ''}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    if _status:
                        st.markdown(f"**状态**: {_status}")
                    if _scenario:
                        st.markdown(f"**剧本**: {_scenario}")
                    if _invalidation:
                        st.markdown(f"**失效条件**: {_invalidation}")

                _fig = _mc(_bars[-120:])
                for _s in _cr.ranked_structures[:5]:
                    _fig.add_hline(y=_s.zone.price_center, line_dash="dot",
                                   line_color="#4a90d9", opacity=0.5,
                                   annotation_text=f"Zone {_s.zone.price_center:.0f}")
                    _fig.add_hrect(y0=_s.zone.lower, y1=_s.zone.upper,
                                   fillcolor="#4a90d9", opacity=0.08, line_width=0)
                st.plotly_chart(_fig, use_container_width=True)
