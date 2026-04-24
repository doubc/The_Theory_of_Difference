"""
Tab 3: 稳态地图 — 如果结构崩塌，市场最可能先滑向哪里

从 app.py 提取的独立模块。
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def render(ctx: dict):
    """渲染 Tab 3: 稳态地图"""
    recent_structures = ctx["recent_structures"]

    st.markdown("#### 🗺️ 稳态地图")
    st.caption("如果结构崩塌，市场最可能先滑向哪里")

    stable_data = []
    for si, st_obj in enumerate(recent_structures):
        for ci, c in enumerate(st_obj.cycles):
            if c.has_stable_state:
                ns = c.next_stable
                stable_data.append({
                    "结构": f"Zone {st_obj.zone.price_center:.0f}",
                    "Cycle": ci + 1,
                    "Exit方向": "↑" if c.exit.delta > 0 else "↓",
                    "稳态价位": ns.zone.price_center if ns.zone else 0,
                    "到达天数": ns.duration_to_arrive,
                    "阻力": ns.resistance_level,
                })

    if stable_data:
        sdf = pd.DataFrame(stable_data)
        st.dataframe(sdf, use_container_width=True, hide_index=True)

        col_hist, col_stats = st.columns([2, 1])
        with col_hist:
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=sdf["稳态价位"], nbinsx=20,
                marker_color="#ff9800", name="最近稳态",
            ))
            fig.update_layout(
                height=300, template="plotly_dark",
                xaxis_title="价位", yaxis_title="频次",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_stats:
            st.metric("平均阻力", f"{sdf['阻力'].mean():.3f}")
            st.metric("低阻力占比(<0.3)", f"{(sdf['阻力'] < 0.3).mean():.0%}")
            st.metric("稳态覆盖率",
                     f"{len(sdf) / max(sum(s.cycle_count for s in recent_structures), 1):.0%}")

            low_res = sdf[sdf["阻力"] < 0.2]
            if not low_res.empty:
                st.warning(f"⚠️ {len(low_res)} 个稳态阻力 < 0.2 — 可能是假稳态")
    else:
        st.info("当前没有识别到最近稳态")
