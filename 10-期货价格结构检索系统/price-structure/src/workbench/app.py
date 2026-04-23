#!/usr/bin/env python3
"""
价格结构形式系统 — 研究工作台 v2.0

运行: streamlit run src/workbench/app.py

五页布局:
  1. 系统总览  — 全市场结构态一览（结构×运动×投影）
  2. 结构深潜  — 单个结构的完整解剖
  3. 主动匹配  — 带观点检索历史相似
  4. 稳态地图  — 最近稳态分布与验证
  5. 研究日志  — 笔记与发现
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
from src.retrieval.similarity import similarity, motion_similarity
from src.retrieval.engine import RetrievalEngine
from src.sample.store import SampleStore

# ─── 页面配置 ──────────────────────────────────────────────

st.set_page_config(
    page_title="价格结构研究工作台",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 自定义样式 ────────────────────────────────────────────

st.markdown("""
<style>
    .metric-card {
        background: #1a1a2e;
        border-radius: 8px;
        padding: 12px 16px;
        border-left: 3px solid #4a90d9;
    }
    .metric-card.warning { border-left-color: #ff9800; }
    .metric-card.danger  { border-left-color: #ef5350; }
    .metric-card.ok      { border-left-color: #26a69a; }
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
    .stable-card {
        background: #1e1e3a;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)


# ─── 侧栏：数据与参数 ──────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔬 价格结构研究工作台")
    st.caption("差异论 V1.6 · 系统 = 结构 × 运动")
    st.divider()

    st.markdown("### ⚙️ 编译参数")
    min_amplitude = st.slider("最小摆动幅度", 0.01, 0.10, 0.03, 0.005)
    min_duration = st.slider("最小持续天数", 1, 10, 3)
    noise_filter = st.slider("噪声过滤", 0.001, 0.02, 0.008, 0.001)
    zone_bandwidth = st.slider("Zone 带宽", 0.005, 0.05, 0.015, 0.005)
    cluster_eps = st.slider("聚类距离", 0.005, 0.05, 0.02, 0.005)
    min_cycles = st.slider("最小 Cycle 数", 1, 5, 2)

    st.divider()
    st.markdown("### 🧠 v2.5 参数")
    adaptive_pivots = st.checkbox("自适应极值窗口", value=True,
        help="根据局部波动率自动调整 swing 检测窗口")
    fractal_threshold = st.slider("分形一致性阈值", 0.0, 1.0, 0.34, 0.01,
        help="至少多少比例的窗口确认才保留极值点") if adaptive_pivots else 0.34
    volume_weighted = st.checkbox("成交量加权极值", value=False,
        help="高成交量极值更容易保留")

    st.divider()
    st.markdown("### 🔍 检索参数")
    top_k = st.slider("返回近邻数", 3, 20, 5)
    min_score = st.slider("最低相似度", 0.1, 0.8, 0.3, 0.05)

    st.divider()
    st.caption(f"数据: CU0 连续合约")
    if st.button("🔄 重新编译"):
        st.cache_data.clear()


# ─── 数据加载 ──────────────────────────────────────────────

@st.cache_data
def load_data():
    loader = load_cu0("data", dedup=True)
    return loader.get()

@st.cache_data
def do_compile(min_amp, min_dur, noise, zbw, eps, mc,
               adaptive=True, fractal=0.34, vol_weighted=False):
    bars = load_data()
    config = CompilerConfig(
        min_amplitude=min_amp, min_duration=min_dur, noise_filter=noise,
        zone_bandwidth=zbw, cluster_eps=eps, cluster_min_points=2,
        min_cycles=mc, tolerance=0.03,
        adaptive_pivots=adaptive, fractal_threshold=fractal,
        volume_weighted=vol_weighted,
    )
    return compile_full(bars, config, symbol="CU000")

@st.cache_data
def do_rules():
    return load_rules(Path("src/dsl/rules/default.yaml"))

bars = load_data()
result = do_compile(min_amplitude, min_duration, noise_filter,
                     zone_bandwidth, cluster_eps, min_cycles,
                     adaptive_pivots, fractal_threshold, volume_weighted)
rules = do_rules()
matches = scan(result.structures, rules)


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


def flux_bar(flux: float) -> str:
    """守恒通量可视化条"""
    if flux > 0.5:
        color, label = "#ef5350", "释放"
    elif flux < -0.5:
        color, label = "#26a69a", "压缩"
    else:
        color, label = "#ffa726", "平衡"
    w = min(abs(flux) * 30, 100)
    return f'<div style="display:flex;align-items:center;gap:8px"><div style="background:{color};width:{w:.0f}%;height:6px;border-radius:3px"></div><span style="color:{color};font-size:0.85em">{flux:+.2f} {label}</span></div>'


def price_chart(bars: list[Bar], zone_center: float = 0, zone_bw: float = 0,
                stable_zones: list[float] = None) -> go.Figure:
    """带 zone 和稳态标注的 K 线图"""
    df = pd.DataFrame([{
        "date": b.timestamp,
        "open": b.open, "high": b.high,
        "low": b.low, "close": b.close,
    } for b in bars])

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        name="K线",
    ))

    # Zone 标注
    if zone_center > 0 and zone_bw > 0:
        fig.add_hline(y=zone_center, line_dash="dash", line_color="#4a90d9",
                      annotation_text=f"Zone {zone_center:.0f}")
        fig.add_hrect(y0=zone_center - zone_bw, y1=zone_center + zone_bw,
                      fillcolor="#4a90d9", opacity=0.1)

    # 最近稳态标注
    if stable_zones:
        for sz in set(stable_zones):
            fig.add_hline(y=sz, line_dash="dot", line_color="#ff9800",
                          annotation_text=f"稳态 {sz:.0f}", annotation_position="bottom right")

    fig.update_layout(
        height=400, margin=dict(l=0, r=0, t=30, b=0),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title="",
    )
    return fig


# ═══════════════════════════════════════════════════════════
# 主布局：5 个 Tab
# ═══════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📡 系统总览",
    "🔬 结构深潜",
    "🎯 主动匹配",
    "🗺️ 稳态地图",
    "📝 研究日志",
])


# ═══════════════════════════════════════════════════════════
# Tab 1: 系统总览 — 结构 × 运动 × 投影
# ═══════════════════════════════════════════════════════════

with tab1:
    st.markdown("### 📡 系统总览")
    st.caption(f"数据: {bars[0].timestamp:%Y-%m-%d} → {bars[-1].timestamp:%Y-%m-%d} · {len(bars)} bars · "
               f"编译: {len(result.structures)} 结构 · {len(matches)} 规则匹配")

    # K 线总览
    st.plotly_chart(price_chart(bars), use_container_width=True)

    # 结构卡片矩阵
    st.markdown("#### 结构态一览")
    cols = st.columns(min(len(result.structures), 4))
    for i, st_obj in enumerate(result.structures[:4]):
        with cols[i % 4]:
            m = st_obj.motion
            p = st_obj.projection
            contrast = st_obj.zone.context_contrast.value

            # 运动标签
            tendency = m.phase_tendency if m else "?"
            flux = m.conservation_flux if m else 0
            stable_d = m.stable_distance if m else 0

            # 投影状态
            compression = p.compression_level if p else 0
            proj_warn = "⚠️" if (p and p.is_blind) else ""

            # 规则标签
            label = st_obj.label or "未匹配"

            card_class = "warning" if proj_warn else ("danger" if "breakdown" in tendency else "ok")

            st.markdown(f"""
            <div class="metric-card {card_class}">
                <div style="font-size:1.1em;font-weight:700">
                    Zone {st_obj.zone.price_center:.0f}
                    {motion_badge(tendency)}
                </div>
                <div style="margin-top:8px;font-size:0.9em;color:#aaa">
                    {label} · {st_obj.cycle_count} cycles · 反差:{contrast}
                </div>
                <div style="margin-top:6px">
                    守恒通量 {flux_bar(flux)}
                </div>
                <div style="margin-top:4px;font-size:0.85em;color:#888">
                    稳态距:{stable_d:.2f} · 投影:{compression:.0%} {proj_warn}
                </div>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# Tab 2: 结构深潜 — 单个结构的完整解剖
# ═══════════════════════════════════════════════════════════

with tab2:
    st.markdown("### 🔬 结构深潜")

    if result.structures:
        idx = st.selectbox(
            "选择结构",
            range(len(result.structures)),
            format_func=lambda i: (
                f"#{i+1} Zone={result.structures[i].zone.price_center:.0f} "
                f"({result.structures[i].label or '?'}) "
                f"{result.structures[i].motion.phase_tendency if result.structures[i].motion else ''}"
            ),
            key="deep_idx",
        )
        st_obj = result.structures[idx]
        m = st_obj.motion
        p = st_obj.projection

        # K 线图 + zone + 稳态
        stable_z = []
        for c in st_obj.cycles:
            if c.has_stable_state:
                stable_z.append(c.next_stable.zone.price_center)

        bars_window = bars  # 全量，后续可缩小
        st.plotly_chart(
            price_chart(bars_window, st_obj.zone.price_center,
                       st_obj.zone.bandwidth, stable_z),
            use_container_width=True,
        )

        # 三栏：结构 / 运动 / 投影
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("#### 🦴 结构（骨架）")
            st.markdown(f"""
            - **Zone**: {st_obj.zone.price_center:.0f} ±{st_obj.zone.bandwidth:.0f}
            - **来源**: {st_obj.zone.source.value}
            - **反差**: {st_obj.zone.context_contrast.value} {st_obj.zone.contrast_label}
            - **强度**: {st_obj.zone.strength:.1f}
            - **Cycles**: {st_obj.cycle_count}
            - **Phases**: {', '.join(p.value for p in st_obj.phases)}
            - **标签**: {st_obj.label or '未匹配'}
            - **叙事**: {st_obj.narrative_context}
            """)

        with c2:
            st.markdown("#### 🌊 运动（趋势）")
            if m:
                st.markdown(f"""
                - **阶段趋势**: {motion_badge(m.phase_tendency)} 置信度 {m.phase_confidence:.0%}
                - **守恒通量**: {flux_bar(m.conservation_flux)}
                - **通量说明**: {m.flux_detail}
                - **稳态距离**: {m.stable_distance:.2f}
                - **趋近速度**: {m.stable_velocity:+.3f}
                - **转移流**: {m.transfer_source} → {m.transfer_target}
                - **系统时间**: {m.structural_age} cycles / 阶段持续 {m.phase_duration}
                """, unsafe_allow_html=True)
            else:
                st.info("运动态未计算")

        with c3:
            st.markdown("#### 👁️ 投影（觉知）")
            if p:
                proj_color = "#ef5350" if p.is_blind else "#26a69a"
                st.markdown(f"""
                - **压缩度**: <span style="color:{proj_color}">{p.compression_level:.0%}</span>
                - **可信度**: {p.projection_confidence:.0%}
                - **盲区**: {', '.join(p.blind_channels) if p.blind_channels else '无'}
                - **观测**: {p.observation}
                """, unsafe_allow_html=True)

                # v2.5: 推荐行动
                if p.recommended_actions:
                    st.markdown("**建议:**")
                    for action in p.recommended_actions:
                        st.markdown(f"  {action}")

                # v2.5: 盲区证据
                if p.blind_evidence:
                    st.markdown("**盲区证据:**")
                    for channel, evidence in p.blind_evidence.items():
                        st.markdown(f"  · {channel}: {evidence}")
            else:
                st.info("投影觉知未计算")

        # Cycle 表格
        st.markdown("#### 📋 Cycle 详情")
        cycle_rows = []
        for i, c in enumerate(st_obj.cycles):
            stable_info = ""
            if c.has_stable_state:
                ns = c.next_stable
                stable_info = f"Zone {ns.zone.price_center:.0f} (阻力 {ns.resistance_level:.2f})"

            cycle_rows.append({
                "#": i + 1,
                "Entry": f"{'↑' if c.entry.delta > 0 else '↓'} {c.entry.abs_delta:.0f} ({c.entry.duration:.0f}d)",
                "Exit": f"{'↑' if c.exit.delta > 0 else '↓'} {c.exit.abs_delta:.0f} ({c.exit.duration:.0f}d)",
                "Speed R": f"{c.speed_ratio:.2f}",
                "Time R": f"{c.time_ratio:.2f}",
                "最近稳态": stable_info or "—",
            })
        st.dataframe(pd.DataFrame(cycle_rows), use_container_width=True, hide_index=True)

        # 守恒检查
        cons = st_obj.invariants.get("conservation", {})
        if cons.get("notes"):
            st.markdown("#### ⚠️ 守恒警告")
            for note in cons["notes"]:
                st.warning(note)


# ═══════════════════════════════════════════════════════════
# Tab 3: 主动匹配 — 带观点检索
# ═══════════════════════════════════════════════════════════

with tab3:
    st.markdown("### 🎯 主动匹配")
    st.caption("选择一个当前结构，系统检索历史相似并给出对比指引")

    if result.structures:
        idx = st.selectbox(
            "选择查询结构",
            range(len(result.structures)),
            format_func=lambda i: f"#{i+1} Zone={result.structures[i].zone.price_center:.0f}",
            key="match_idx",
        )
        query_st = result.structures[idx]

        # 当前结构态
        m = query_st.motion
        col1, col2, col3 = st.columns(3)
        col1.metric("Zone", f"{query_st.zone.price_center:.0f}")
        col2.metric("运动", m.phase_tendency if m else "?")
        col3.metric("通量", f"{m.conservation_flux:+.2f}" if m else "—")

        # 两结构间相似性对比
        st.markdown("#### 与其他结构的相似性")
        sim_rows = []
        for j, other in enumerate(result.structures):
            if j == idx:
                continue
            sc = similarity(query_st, other)
            sim_rows.append({
                "#": j + 1,
                "Zone": f"{other.zone.price_center:.0f}",
                "标签": other.label or "—",
                "Total": f"{sc.total:.3f}",
                "几何": f"{sc.geometric:.3f}",
                "关系": f"{sc.relational:.3f}",
                "运动": f"{sc.motion:.3f}",
                "族": f"{sc.family:.3f}",
            })
        if sim_rows:
            st.dataframe(pd.DataFrame(sim_rows), use_container_width=True, hide_index=True)

        # 样本库检索
        st.markdown("#### 历史相似案例")
        store = SampleStore("data/samples/library.jsonl")
        if store.count() > 0:
            engine = RetrievalEngine(store)
            ret = engine.retrieve(query_st, top_k=top_k, min_score=min_score)

            if ret.neighbors:
                for i, n in enumerate(ret.neighbors[:5]):
                    with st.expander(
                        f"[{i+1}] {n.sample.label_type} — "
                        f"score={n.score.total:.3f} "
                        f"({n.sample.t_start:%Y-%m} ~ {n.sample.t_end:%Y-m})"
                    ):
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            st.write(f"**ID**: {n.sample.id}")
                            st.write(f"**典型度**: {n.sample.typicality:.2f}")
                            if n.sample.forward_outcome:
                                fo = n.sample.forward_outcome
                                st.write(f"**5d**: {fo.get('ret_5d', 0):+.2%}")
                                st.write(f"**10d**: {fo.get('ret_10d', 0):+.2%}")
                                st.write(f"**20d**: {fo.get('ret_20d', 0):+.2%}")
                        with cc2:
                            st.write(f"几何: {n.score.geometric:.3f}")
                            st.write(f"关系: {n.score.relational:.3f}")
                            st.write(f"运动: {n.score.motion:.3f}")
                            st.write(f"族: {n.score.family:.3f}")

                # 后验统计
                p = ret.posterior
                st.markdown("#### 后验分布")
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("样本数", p.sample_size)
                mc2.metric("ret_5d", f"{p.mean_ret_5d:+.2%}")
                mc3.metric("ret_10d", f"{p.mean_ret_10d:+.2%}")
                mc4.metric("ret_20d", f"{p.mean_ret_20d:+.2%}")
            else:
                st.info("无足够相似样本")
        else:
            st.warning("样本库为空")


# ═══════════════════════════════════════════════════════════
# Tab 4: 稳态地图 — 最近稳态分布与验证
# ═══════════════════════════════════════════════════════════

with tab4:
    st.markdown("### 🗺️ 稳态地图")
    st.caption("V1.6 命题 3.4/3.5：系统先滑向最近能稳住的安排，不是最优解")

    # 收集所有稳态信息
    stable_data = []
    for si, st_obj in enumerate(result.structures):
        for ci, c in enumerate(st_obj.cycles):
            if c.has_stable_state:
                ns = c.next_stable
                stable_data.append({
                    "结构": f"S{si}",
                    "Cycle": ci + 1,
                    "Zone": st_obj.zone.price_center,
                    "Exit方向": "↑" if c.exit.delta > 0 else "↓",
                    "Exit幅度": c.exit.abs_delta,
                    "稳态价位": ns.zone.price_center if ns.zone else 0,
                    "到达天数": ns.duration_to_arrive,
                    "阻力": ns.resistance_level,
                })

    if stable_data:
        sdf = pd.DataFrame(stable_data)
        st.dataframe(sdf, use_container_width=True, hide_index=True)

        # 稳态分布图
        st.markdown("#### 稳态价位分布")
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=sdf["稳态价位"],
            nbinsx=20,
            marker_color="#ff9800",
            name="最近稳态",
        ))
        fig.update_layout(
            height=300, template="plotly_dark",
            xaxis_title="价位", yaxis_title="频次",
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        # 阻力分布
        st.markdown("#### 阻力评分分布")
        c1, c2, c3 = st.columns(3)
        c1.metric("平均阻力", f"{sdf['阻力'].mean():.3f}")
        c2.metric("低阻力占比(<0.3)", f"{(sdf['阻力'] < 0.3).mean():.0%}")
        c3.metric("稳态覆盖率", f"{len(sdf) / sum(st.cycle_count for st in result.structures):.0%}")

        # 低阻力警告
        low_res = sdf[sdf["阻力"] < 0.2]
        if not low_res.empty:
            st.warning(
                f"⚠️ {len(low_res)} 个 Cycle 的稳态阻力 < 0.2 — "
                f"可能是假稳态，差异正在隐性积累"
            )
    else:
        st.info("当前编译结果中未识别到最近稳态")


# ═══════════════════════════════════════════════════════════
# Tab 5: 研究日志
# ═══════════════════════════════════════════════════════════

with tab5:
    st.markdown("### 📝 研究日志")

    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 自动生成上下文摘要
    if result.structures:
        context_lines = [
            f"## 编译上下文 {datetime.now():%Y-%m-%d %H:%M}",
            f"- 数据: {bars[0].timestamp:%Y-%m-%d} → {bars[-1].timestamp:%Y-%m-%d} ({len(bars)} bars)",
            f"- 结构: {len(result.structures)} 个",
        ]
        for i, s in enumerate(result.structures[:4]):
            m = s.motion
            context_lines.append(
                f"- S{i}: zone={s.zone.price_center:.0f} "
                f"cycles={s.cycle_count} "
                f"motion={m.phase_tendency if m else '?'} "
                f"flux={m.conservation_flux:+.2f if m else 0}"
            )
        default_note = "\n".join(context_lines)
    else:
        default_note = ""

    note = st.text_area("记录研究笔记", value=default_note, height=200)
    if st.button("保存日志"):
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        log_file = log_dir / f"{ts}.md"
        log_file.write_text(note, encoding="utf-8")
        st.success(f"已保存 → {log_file}")

    # 历史日志
    logs = sorted(log_dir.glob("*.md"), reverse=True)
    if logs:
        st.markdown("#### 历史日志")
        for log_file in logs[:10]:
            with st.expander(f"📄 {log_file.stem}"):
                st.text(log_file.read_text(encoding="utf-8"))
