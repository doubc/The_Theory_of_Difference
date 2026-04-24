"""
Tab 2: 跨品种对比 — 对比表格 + 雷达图 + K线并排

从 app.py 提取的独立模块。
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.data.symbol_meta import symbol_name
from src.retrieval.similarity import INVARIANT_SCALES

from src.workbench.shared import (
    motion_badge, make_candlestick, make_comparison_chart,
)


def render(ctx: dict):
    """渲染 Tab 2: 跨品种对比"""
    selected_symbol = ctx["selected_symbol"]
    bars = ctx["bars"]
    recent_structures = ctx["recent_structures"]
    compare_codes = ctx["compare_codes"]
    compare_results = ctx["compare_results"]
    META = ctx["META"]
    ds_name = ctx["ds_name"]

    # 计算 cutoff（与 app.py 一致）
    import pandas as _pd
    cutoff = bars[-1].timestamp - _pd.Timedelta(days=ctx.get("days", 120))

    st.markdown("#### 📊 跨品种结构对比")
    st.caption("选择侧栏的对比品种，自动并排展示同类型结构")

    if not compare_codes:
        st.info("请在侧栏选择 1~4 个对比品种")
    else:
        # 对比表格
        compare_rows = []

        # 主品种
        for s in recent_structures[:3]:
            compare_rows.append({
                "品种": f"{selected_symbol} ({ds_name})",
                "Zone": f"{s.zone.price_center:.0f}",
                "Cycle数": s.cycle_count,
                "速度比": f"{s.avg_speed_ratio:.2f}",
                "时间比": f"{s.avg_time_ratio:.2f}",
                "带宽": f"{s.zone.relative_bandwidth:.3f}",
                "运动": s.motion.phase_tendency if s.motion else "—",
                "通量": f"{s.motion.conservation_flux:+.2f}" if s.motion else "—",
                "反差": s.zone.context_contrast.value,
            })

        # 对比品种
        for csym in compare_codes:
            if csym not in compare_results:
                continue
            cr, cbars = compare_results[csym]
            cs_name = symbol_name(csym)
            cs_recent = [s for s in cr.ranked_structures
                        if s.t_end and s.t_end >= cutoff]
            for s in cs_recent[:3]:
                compare_rows.append({
                    "品种": f"{csym} ({cs_name})",
                    "Zone": f"{s.zone.price_center:.0f}",
                    "Cycle数": s.cycle_count,
                    "速度比": f"{s.avg_speed_ratio:.2f}",
                    "时间比": f"{s.avg_time_ratio:.2f}",
                    "带宽": f"{s.zone.relative_bandwidth:.3f}",
                    "运动": s.motion.phase_tendency if s.motion else "—",
                    "通量": f"{s.motion.conservation_flux:+.2f}" if s.motion else "—",
                    "反差": s.zone.context_contrast.value,
                })

        if compare_rows:
            df_compare = pd.DataFrame(compare_rows)
            st.dataframe(df_compare, use_container_width=True, hide_index=True)

        # ── 不变量雷达图对比 ──
        if recent_structures and any(c in compare_results for c in compare_codes):
            st.markdown("---")
            st.markdown("**不变量雷达图**")

            main_s = recent_structures[0]
            main_inv = main_s.invariants or {}

            radar_keys = ["cycle_count", "avg_speed_ratio", "avg_time_ratio",
                         "zone_rel_bw", "zone_strength"]
            radar_labels = ["Cycle数", "速度比", "时间比", "相对带宽", "强度"]

            fig = go.Figure()

            main_vals = [(main_inv.get(k, 0) or 0) / INVARIANT_SCALES.get(k, 1)
                        for k in radar_keys]
            fig.add_trace(go.Scatterpolar(
                r=main_vals + [main_vals[0]],
                theta=radar_labels + [radar_labels[0]],
                fill='toself',
                name=f"{selected_symbol} ({ds_name})",
                line_color="#4a90d9",
            ))

            colors = ["#26a69a", "#ef5350", "#ff9800", "#ab47bc"]
            for ci, csym in enumerate(compare_codes):
                if csym not in compare_results:
                    continue
                cr, _ = compare_results[csym]
                if not cr.ranked_structures:
                    continue
                cs_inv = cr.ranked_structures[0].invariants or {}
                cs_vals = [(cs_inv.get(k, 0) or 0) / INVARIANT_SCALES.get(k, 1)
                          for k in radar_keys]
                cs_name = symbol_name(csym)
                fig.add_trace(go.Scatterpolar(
                    r=cs_vals + [cs_vals[0]],
                    theta=radar_labels + [radar_labels[0]],
                    fill='toself',
                    name=f"{csym} ({cs_name})",
                    line_color=colors[ci % len(colors)],
                    opacity=0.6,
                ))

            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                height=400, template="plotly_dark",
                margin=dict(l=60, r=60, t=30, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── 跨品种 K 线并排 ──
        if compare_codes and len(compare_codes) == 1:
            csym = compare_codes[0]
            if csym in compare_results:
                st.markdown("---")
                st.markdown(f"**K 线对比: {selected_symbol} vs {csym}**")
                _, cbars = compare_results[csym]
                fig = make_comparison_chart(
                    bars[-120:], cbars[-120:],
                    f"{selected_symbol} ({ds_name})",
                    f"{csym} ({symbol_name(csym)})",
                )
                st.plotly_chart(fig, use_container_width=True)
