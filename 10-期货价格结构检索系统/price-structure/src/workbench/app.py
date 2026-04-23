#!/usr/bin/env python3
"""
价格结构研究工作台 v2.5

按人类问题组织，不是按系统功能组织：
  1. 今天值得关注什么  — 有什么结构在形成/在破缺
  2. 跟历史上哪些像    — 这个结构历史上出现过吗，之后发生了什么
  3. 这个品种的稳态    — 如果崩塌，先到哪
  4. 研究笔记          — 我的观察和想法

运行: streamlit run src/workbench/app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

from src.data.loader import load_cu0, Bar
from src.compiler.pipeline import compile_full, CompilerConfig, CompileResult
from src.dsl.rule import load_rules, scan
from src.retrieval.similarity import similarity
from src.retrieval.engine import RetrievalEngine
from src.sample.store import SampleStore
from src.narrative import generate_daily_summary

# ─── 页面配置 ──────────────────────────────────────────────

st.set_page_config(
    page_title="价格结构研究工作台",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 样式 ──────────────────────────────────────────────────

st.markdown("""
<style>
    .motion-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .badge-breakdown { background: #ef535022; color: #ef5350; }
    .badge-confirmation { background: #26a69a22; color: #26a69a; }
    .badge-stable { background: #ffa72622; color: #ffa726; }
    .badge-forming { background: #42a5f522; color: #42a5f5; }
    .structure-card {
        background: #1a1a2e;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 8px 0;
        border-left: 4px solid #4a90d9;
    }
    .structure-card.warning { border-left-color: #ff9800; }
    .structure-card.danger  { border-left-color: #ef5350; }
    .structure-card.ok      { border-left-color: #26a69a; }
    .section-title {
        font-size: 1.1em;
        font-weight: 600;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ─── 侧栏：极简 ──────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔬 价格结构工作台")
    st.caption("统一语法 · 系统 = 结构 × 运动")
    st.divider()

    # 数据范围
    st.markdown("### 📊 数据范围")
    data_range = st.selectbox(
        "时间范围",
        ["最近60天", "最近120天", "最近半年", "最近一年", "全部数据"],
        index=1,
    )
    range_map = {
        "最近60天": 60, "最近120天": 120,
        "最近半年": 180, "最近一年": 365, "全部数据": 99999,
    }

    st.divider()
    # 灵敏度（只给一个旋钮）
    st.markdown("### 🎛️ 灵敏度")
    sensitivity = st.select_slider(
        "结构识别灵敏度",
        options=["粗糙", "标准", "精细"],
        value="标准",
        help="粗糙=只看大结构，精细=捕捉小波动",
    )
    sens_map = {
        "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3},
        "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2},
        "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2},
    }

    st.divider()
    st.caption(f"数据: CU0 连续合约")
    if st.button("🔄 刷新"):
        st.cache_data.clear()


# ─── 数据加载与编译 ──────────────────────────────────────

@st.cache_data
def load_data():
    loader = load_cu0("data", dedup=True)
    return loader.get()

@st.cache_data
def do_compile(min_amp, min_dur, min_cycles):
    bars = load_data()
    config = CompilerConfig(
        min_amplitude=min_amp, min_duration=min_dur,
        min_cycles=min_cycles,
        adaptive_pivots=True, fractal_threshold=0.34,
    )
    return compile_full(bars, config, symbol="CU000")

bars = load_data()
sens = sens_map[sensitivity]
result = do_compile(sens["min_amp"], sens["min_dur"], sens["min_cycles"])

# 按时间范围过滤显示
days = range_map[data_range]
cutoff = bars[-1].timestamp - pd.Timedelta(days=days)
recent_structures = [s for s in result.ranked_structures
                     if s.t_end and s.t_end >= cutoff]


# ─── 工具函数 ──────────────────────────────────────────────

def motion_badge(tendency: str) -> str:
    cls = "badge-forming"
    if "breakdown" in tendency:
        cls = "badge-breakdown"
    elif "confirmation" in tendency:
        cls = "badge-confirmation"
    elif tendency == "stable":
        cls = "badge-stable"
    return f'<span class="motion-badge {cls}">{tendency}</span>'


def make_candlestick(bars, title=""):
    df = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume,
    } for b in bars])
    fig = go.Figure(data=[go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    )])
    fig.update_layout(
        height=350, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=30, b=0),
        title=title,
    )
    return fig


# ═══════════════════════════════════════════════════════════
# 主页面：按人类问题组织
# ═══════════════════════════════════════════════════════════

st.markdown("### 🔬 价格结构研究工作台")
st.caption(f"{bars[0].timestamp:%Y-%m-%d} → {bars[-1].timestamp:%Y-%m-%d} · "
           f"{len(recent_structures)} 个结构在 {data_range} 内")

tab1, tab2, tab3, tab4 = st.tabs([
    "📡 今天值得关注什么",
    "🔍 跟历史哪些像",
    "🗺️ 稳态地图",
    "📝 研究笔记",
])


# ═══════════════════════════════════════════════════════════
# Tab 1: 今天值得关注什么
# ═══════════════════════════════════════════════════════════

with tab1:
    st.markdown("#### 📡 今天值得关注什么")
    st.caption("有什么结构在形成、在确认、或正在破缺")

    if not recent_structures:
        st.info("当前时间范围内没有显著结构")
    else:
        # 分类：正在破缺的 / 趋向确认的 / 形成中的
        breaking = [s for s in recent_structures
                    if s.motion and "breakdown" in s.motion.phase_tendency]
        confirming = [s for s in recent_structures
                      if s.motion and "confirmation" in s.motion.phase_tendency]
        forming = [s for s in recent_structures
                   if s.motion and s.motion.phase_tendency in ("forming", "stable", "")]

        # 破缺的先显示
        if breaking:
            st.markdown("**🔴 正在破缺**")
            for s in breaking[:3]:
                with st.container():
                    st.markdown(f"""
                    <div class="structure-card danger">
                        <b>Zone {s.zone.price_center:.0f}</b> (±{s.zone.bandwidth:.0f})
                        · {s.cycle_count}次试探
                        · {motion_badge(s.motion.phase_tendency)}
                        · 通量 {s.motion.conservation_flux:+.2f}
                        <br><small>{s.narrative_context}</small>
                    </div>
                    """, unsafe_allow_html=True)

        # 趋向确认的
        if confirming:
            st.markdown("**🟢 趋向确认**")
            for s in confirming[:3]:
                st.markdown(f"""
                <div class="structure-card ok">
                    <b>Zone {s.zone.price_center:.0f}</b> (±{s.zone.bandwidth:.0f})
                    · {s.cycle_count}次试探
                    · {motion_badge(s.motion.phase_tendency)}
                    · 通量 {s.motion.conservation_flux:+.2f}
                    <br><small>{s.narrative_context}</small>
                </div>
                """, unsafe_allow_html=True)

        # 形成中的
        if forming:
            st.markdown("**🔵 形成中**")
            for s in forming[:5]:
                proj_warn = "⚠️ 高压缩" if (s.projection and s.projection.is_blind) else ""
                st.markdown(f"""
                <div class="structure-card">
                    <b>Zone {s.zone.price_center:.0f}</b> (±{s.zone.bandwidth:.0f})
                    · {s.cycle_count}次试探
                    · {motion_badge(s.motion.phase_tendency if s.motion else 'unknown')}
                    {f'· {proj_warn}' if proj_warn else ''}
                    <br><small>{s.narrative_context}</small>
                </div>
                """, unsafe_allow_html=True)

        # K 线图 + Zone 标注
        st.markdown("---")
        st.markdown("**K 线 + 关键区**")
        fig = make_candlestick(bars[-120:])
        for s in recent_structures[:5]:
            fig.add_hline(y=s.zone.price_center, line_dash="dot",
                         line_color="#4a90d9", opacity=0.5,
                         annotation_text=f"Zone {s.zone.price_center:.0f}")
            fig.add_hrect(y0=s.zone.lower, y1=s.zone.upper,
                         fillcolor="#4a90d9", opacity=0.08, line_width=0)
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# Tab 2: 跟历史哪些像
# ═══════════════════════════════════════════════════════════

with tab2:
    st.markdown("#### 🔍 跟历史哪些像")
    st.caption("选一个当前结构，看历史上类似的结构之后发生了什么")

    if not recent_structures:
        st.info("没有可比较的结构")
    else:
        # 选择要查看的结构
        options = [f"Zone {s.zone.price_center:.0f} ({s.cycle_count}次试探, "
                   f"{s.narrative_context or '?'})"
                   for s in recent_structures]
        sel = st.selectbox("选择一个结构", options, index=0)
        idx = options.index(sel)
        query_st = recent_structures[idx]

        # 显示选中结构的详情
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("**选中的结构**")
            m = query_st.motion
            p = query_st.projection
            st.markdown(f"""
            - Zone: {query_st.zone.price_center:.0f} (±{query_st.zone.bandwidth:.0f})
            - 试探次数: {query_st.cycle_count}
            - 叙事: {query_st.narrative_context}
            - 运动: {m.phase_tendency if m else '—'}
            - 通量: {m.conservation_flux:+.2f if m else 0}
            - 压缩度: {p.compression_level:.0% if p else '—'}
            """)

            # 投影觉知建议
            if p and p.recommended_actions:
                st.markdown("**系统建议:**")
                for action in p.recommended_actions:
                    st.markdown(f"  {action}")

        with col2:
            st.markdown("**这个品种历史上**")
            st.caption("这个 Zone 附近，历史上类似结构之后发生了什么")

            # 在样本库中检索
            sample_store = SampleStore("data/samples")
            if sample_store.load_all():
                engine = RetrievalEngine(sample_store)
                result_retrieval = engine.retrieve(query_st, top_k=5)

                if result_retrieval.neighbors:
                    for i, n in enumerate(result_retrieval.neighbors):
                        st.markdown(f"""
                        **#{i+1}** 匹配度 {n.score.total:.0%}
                        · {n.match_reason}
                        """)
                else:
                    st.info("样本库中暂无匹配")

                # 后验统计
                post = result_retrieval.posterior
                if post.sample_size > 0:
                    st.markdown("---")
                    st.markdown("**后验统计** (匹配案例的后续表现)")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("5日收益", f"{post.mean_ret_5d:+.2%}")
                    c2.metric("10日收益", f"{post.mean_ret_10d:+.2%}")
                    c3.metric("20日收益", f"{post.mean_ret_20d:+.2%}")
                    st.metric("10日上涨概率", f"{post.prob_positive_10d:.0%}")
            else:
                st.info("样本库为空，暂无历史匹配")

        # 最近稳态
        stable_cycles = [c for c in query_st.cycles if c.has_stable_state]
        if stable_cycles:
            st.markdown("---")
            st.markdown("**如果崩塌，先到哪？**")
            latest = stable_cycles[-1].next_stable
            if latest.zone:
                st.markdown(f"""
                - 最近稳态价位: **{latest.zone.price_center:.0f}**
                - 到达耗时: {latest.duration_to_arrive:.0f} 天
                - 阻力评分: {latest.resistance_level:.2f} (越低越容易到)
                """)


# ═══════════════════════════════════════════════════════════
# Tab 3: 稳态地图
# ═══════════════════════════════════════════════════════════

with tab3:
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

        # 稳态分布
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

        # 统计
        c1, c2, c3 = st.columns(3)
        c1.metric("平均阻力", f"{sdf['阻力'].mean():.3f}")
        c2.metric("低阻力占比(<0.3)", f"{(sdf['阻力'] < 0.3).mean():.0%}")
        c3.metric("稳态覆盖率", f"{len(sdf) / max(sum(s.cycle_count for s in recent_structures), 1):.0%}")

        low_res = sdf[sdf["阻力"] < 0.2]
        if not low_res.empty:
            st.warning(f"⚠️ {len(low_res)} 个稳态阻力 < 0.2 — 可能是假稳态")
    else:
        st.info("当前没有识别到最近稳态")


# ═══════════════════════════════════════════════════════════
# Tab 4: 研究笔记
# ═══════════════════════════════════════════════════════════

with tab4:
    st.markdown("#### 📝 研究笔记")
    st.caption("记录你的观察和想法")

    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"{today}.md"

    # 自动上下文
    if recent_structures:
        context = f"## 编译上下文 {datetime.now():%Y-%m-%d %H:%M}\n"
        context += f"- 数据: {bars[0].timestamp:%Y-%m-%d} → {bars[-1].timestamp:%Y-%m-%d}\n"
        context += f"- 结构: {len(recent_structures)} 个\n"
        for s in recent_structures[:5]:
            context += f"  - Zone {s.zone.price_center:.0f}: {s.narrative_context or '?'}\n"
        st.code(context, language="markdown")

    # 笔记编辑
    existing = log_file.read_text() if log_file.exists() else ""
    notes = st.text_area("今日笔记", value=existing, height=200,
                         placeholder="记录你的观察、想法、疑问...")
    if st.button("💾 保存"):
        log_file.write_text(notes)
        st.success(f"已保存到 {log_file}")
