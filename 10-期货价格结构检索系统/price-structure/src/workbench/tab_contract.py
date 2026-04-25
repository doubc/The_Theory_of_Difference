"""
Tab 5: 合约检索 — 预置合约 + 自由输入 + 拉取编译 + 展示

从 app.py 提取的独立模块。
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time as _time

from src.data.loader import Bar
from src.data.sina_fetcher import fetch_bars as sina_fetch_bars, detect_source, available_contracts
from src.compiler.pipeline import compile_full, CompilerConfig

from src.workbench.shared import (
    motion_badge, _price_vs_zone, make_candlestick, SENS_MAP,
)


def render(ctx: dict):
    """渲染 Tab 5: 合约检索"""
    st.markdown("#### 🔎 合约检索")
    st.caption("输入任意合约代码（如 cu2507、rb2510、cad），从新浪实时拉取数据 → 编译结构 → 展示分析")

    # ── 合约选择 ──
    contracts = available_contracts()

    col_input, col_freq = st.columns([3, 1])
    with col_input:
        all_presets = []
        for group, codes in contracts.items():
            for c in codes:
                all_presets.append(f"{c} ({group})")

        contract_mode = st.radio(
            "选择方式",
            ["📋 预置合约", "✏️ 自由输入"],
            horizontal=True,
            key="contract_mode",
        )

        if contract_mode == "📋 预置合约":
            preset_sel = st.selectbox(
                "选择合约",
                all_presets,
                key="preset_contract",
            )
            contract_code = preset_sel.split(" ")[0].strip()
        else:
            contract_code = st.text_input(
                "合约代码",
                value="cu0",
                placeholder="输入合约代码，如 cu2507、rb2510、cad、usdcny",
                key="free_contract",
            ).strip().lower()

    with col_freq:
        freq = st.selectbox("数据频率", ["日线", "5分钟线"], key="contract_freq")
        freq_code = "5m" if freq == "5分钟线" else "1d"

        if contract_code:
            src = detect_source(contract_code)
            src_labels = {"inner": "🇨🇳 国内期货", "global": "🌍 外盘期货", "fx": "💱 外汇"}
            st.caption(f"数据源: {src_labels.get(src, src)}")

    # ── 编译参数 ──
    col_sens, col_btn = st.columns([3, 1])
    with col_sens:
        contract_sensitivity = st.select_slider(
            "结构灵敏度",
            options=["粗糙", "标准", "精细"],
            value="标准",
            key="contract_sensitivity",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        run_fetch = st.button("🚀 拉取并编译", type="primary", use_container_width=True, key="btn_contract_fetch")

    # ── 执行 ──
    if run_fetch and contract_code:

        with st.spinner(f"📡 正在从新浪拉取 {contract_code} 的{freq}数据..."):
            _t0 = _time.time()
            bars_data = sina_fetch_bars(contract_code, freq=freq_code, timeout=15)
            fetch_time = _time.time() - _t0

        if not bars_data:
            st.error(f"❌ 未能获取 {contract_code} 的数据")
            st.caption("可能原因：① 合约代码不存在 ② 新浪 API 暂时不可用 ③ 该合约已退市")
        else:
            st.success(f"✅ 获取 {len(bars_data)} 条 {freq}数据 · 用时 {fetch_time:.1f}s · "
                       f"{bars_data[0].timestamp:%Y-%m-%d} → {bars_data[-1].timestamp:%Y-%m-%d}")

            _sens_map = {
                "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3},
                "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2},
                "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2},
            }
            _s = _sens_map[contract_sensitivity]

            with st.spinner("🔧 正在编译价格结构..."):
                cfg = CompilerConfig(
                    min_amplitude=_s["min_amp"], min_duration=_s["min_dur"],
                    min_cycles=_s["min_cycles"],
                    adaptive_pivots=True, fractal_threshold=0.34,
                )
                comp_result = compile_full(bars_data, cfg, symbol=contract_code.upper())

            if not comp_result.structures:
                st.warning("🔍 未识别到显著结构 — 试试降低灵敏度到「精细」")
            else:
                n_structs = len(comp_result.structures)
                n_zones = len(comp_result.zones)
                last_price = bars_data[-1].close

                # v3.1: 自动保存合约检索结果到活动日志
                try:
                    from src.workbench.activity_log import ActivityLog
                    _struct_data = []
                    for s in comp_result.ranked_structures[:5]:
                        m = s.motion
                        _struct_data.append({
                            "zone": s.zone.price_center,
                            "cycles": s.cycle_count,
                            "motion": m.phase_tendency if m else "",
                            "flux": round(m.conservation_flux, 2) if m else 0,
                        })
                    ActivityLog().save_contract(
                        symbol=contract_code.upper(),
                        bars_count=len(bars_data),
                        structures=_struct_data,
                    )
                except Exception:
                    pass

                # ── 概要指标 ──
                st.markdown("---")
                metric_cols = st.columns(6)
                metric_cols[0].metric("最新价", f"{last_price:.2f}")
                metric_cols[1].metric("结构数", n_structs)
                metric_cols[2].metric("Zone 数", n_zones)
                metric_cols[3].metric("数据条数", len(bars_data))
                ss_reliable = sum(1 for ss in comp_result.system_states if ss.is_reliable)
                metric_cols[4].metric("可信结构", ss_reliable)
                blind_count = sum(1 for ss in comp_result.system_states if ss.projection.is_blind)
                metric_cols[5].metric("⚠️ 高压缩", blind_count)

                # ── 结构卡片 ──
                ranked = comp_result.ranked_structures
                breaking = [s for s in ranked if s.motion and "breakout" in s.motion.phase_tendency]
                confirming = [s for s in ranked if s.motion and "confirmation" in s.motion.phase_tendency]
                forming = [s for s in ranked if s.motion and s.motion.phase_tendency in ("forming", "stable", "")]

                if breaking:
                    st.markdown("**🔴 正在破缺**")
                    for s in breaking[:3]:
                        flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                        pos = _price_vs_zone(last_price, s.zone.price_center, s.zone.bandwidth)
                        st.markdown(f"""
                        <div class="structure-card danger">
                            <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                            <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                            · {motion_badge(s.motion.phase_tendency)}
                            · <span class="meta-text">通量 {flux}</span>
                            <div class="meta-text">{pos}</div>
                            <div class="narrative-text">{s.narrative_context or ''}</div>
                        </div>
                        """, unsafe_allow_html=True)

                if confirming:
                    st.markdown("**🟢 趋向确认**")
                    for s in confirming[:3]:
                        flux = f"{s.motion.conservation_flux:+.2f}" if s.motion else "—"
                        pos = _price_vs_zone(last_price, s.zone.price_center, s.zone.bandwidth)
                        st.markdown(f"""
                        <div class="structure-card ok">
                            <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                            <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                            · {motion_badge(s.motion.phase_tendency)}
                            · <span class="meta-text">通量 {flux}</span>
                            <div class="meta-text">{pos}</div>
                            <div class="narrative-text">{s.narrative_context or ''}</div>
                        </div>
                        """, unsafe_allow_html=True)

                if forming:
                    st.markdown("**🔵 形成中**")
                    for s in forming[:5]:
                        proj_warn = " · ⚠️ 高压缩" if (s.projection and s.projection.is_blind) else ""
                        tendency = s.motion.phase_tendency if s.motion else 'unknown'
                        pos = _price_vs_zone(last_price, s.zone.price_center, s.zone.bandwidth)
                        st.markdown(f"""
                        <div class="structure-card">
                            <span class="zone-label">Zone {s.zone.price_center:.0f}</span>
                            <span class="meta-text">(±{s.zone.bandwidth:.0f}) · {s.cycle_count}次试探</span>
                            · {motion_badge(tendency)}{proj_warn}
                            <div class="meta-text">{pos}</div>
                            <div class="narrative-text">{s.narrative_context or ''}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # ── K 线图 + Zone 标注 ──
                st.markdown("---")
                st.markdown(f"**K 线图 · {contract_code.upper()}**")
                fig = make_candlestick(bars_data[-120:])
                for s in ranked[:5]:
                    fig.add_hline(y=s.zone.price_center, line_dash="dot",
                                 line_color="#4a90d9", opacity=0.5,
                                 annotation_text=f"Zone {s.zone.price_center:.0f}")
                    fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                                 fillcolor="#4a90d9", opacity=0.08, line_width=0)
                st.plotly_chart(fig, use_container_width=True)

                # ── 不变量汇总 ──
                if ranked:
                    with st.expander("📊 结构不变量详情"):
                        inv_rows = []
                        for s in ranked[:10]:
                            inv = s.invariants or {}
                            m = s.motion
                            inv_rows.append({
                                "Zone": f"{s.zone.price_center:.0f}",
                                "Cycle数": s.cycle_count,
                                "速度比": f"{s.avg_speed_ratio:.2f}",
                                "时间比": f"{s.avg_time_ratio:.2f}",
                                "带宽": f"{s.zone.relative_bandwidth:.3f}",
                                "运动": m.phase_tendency if m else "—",
                                "通量": f"{m.conservation_flux:+.2f}" if m else "—",
                                "反差": s.zone.context_contrast.value,
                            })
                        st.dataframe(pd.DataFrame(inv_rows), hide_index=True, use_container_width=True)

    elif run_fetch:
        st.warning("请输入合约代码")
