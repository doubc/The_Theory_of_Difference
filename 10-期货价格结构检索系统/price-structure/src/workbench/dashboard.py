#!/usr/bin/env python3
"""
研究工作台 — Streamlit 面板

运行: streamlit run src/workbench/dashboard.py

功能：
1. 今日候选结构清单（按典型度排序）
2. 每个结构详情：对象可视化 + 约束达成表
3. 历史相似案例 + 后验分布
4. 参数调试器（修改阈值重新编译）
5. 研究日志
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

from src.data.loader import load_cu0
from src.compiler.pipeline import compile_full, CompilerConfig
from src.dsl.rule import load_rules, scan
from src.sample.store import SampleStore
from src.sample.outcome import compute_forward_outcome, ForwardOutcome
from src.retrieval.engine import RetrievalEngine
from src.learning.features import extract_features, FEATURE_NAMES
from src.learning.embedding import embed, cosine_similarity


# ─── 页面配置 ──────────────────────────────────────────────

st.set_page_config(page_title="价格结构研究工作台", layout="wide")
st.title("🔬 价格结构形式系统 — 研究工作台")


# ─── 侧栏：参数调试 ──────────────────────────────────────

with st.sidebar:
    st.header("⚙️ 编译参数")

    min_amplitude = st.slider("最小摆动幅度", 0.01, 0.10, 0.03, 0.005)
    min_duration = st.slider("最小持续天数", 1, 10, 3)
    noise_filter = st.slider("噪声过滤", 0.001, 0.02, 0.008, 0.001)
    zone_bandwidth = st.slider("Zone 带宽", 0.005, 0.05, 0.015, 0.005)
    cluster_eps = st.slider("聚类距离", 0.005, 0.05, 0.02, 0.005)
    min_cycles = st.slider("最小 Cycle 数", 1, 5, 2)

    st.divider()
    st.header("🔍 检索参数")
    top_k = st.slider("返回近邻数", 3, 20, 5)
    min_score = st.slider("最低相似度", 0.1, 0.8, 0.3, 0.05)


# ─── 数据加载（缓存）──────────────────────────────────────

@st.cache_data
def load_data():
    loader = load_cu0("data", dedup=True)
    return loader.get()


@st.cache_data
def compile_structures_cached(min_amp, min_dur, noise, zbw, eps, mc):
    bars = load_data()
    config = CompilerConfig(
        min_amplitude=min_amp, min_duration=min_dur, noise_filter=noise,
        zone_bandwidth=zbw, cluster_eps=eps, cluster_min_points=2,
        min_cycles=mc, tolerance=0.03,
    )
    return compile_full(bars, config)


@st.cache_data
def load_rules_cached():
    return load_rules(Path("src/dsl/rules/default.yaml"))


bars = load_data()
config = CompilerConfig(
    min_amplitude=min_amplitude, min_duration=min_duration, noise_filter=noise_filter,
    zone_bandwidth=zone_bandwidth, cluster_eps=cluster_eps, cluster_min_points=2,
    min_cycles=min_cycles, tolerance=0.03,
)
result = compile_structures_cached(min_amplitude, min_duration, noise_filter,
                                   zone_bandwidth, cluster_eps, min_cycles)
rules = load_rules_cached()


# ─── Tab 布局 ──────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["📊 结构总览", "🔎 结构详情", "📚 相似检索", "📝 研究日志"])


# ─── Tab 1: 结构总览 ──────────────────────────────────────

with tab1:
    st.subheader(f"编译结果: {len(result.structures)} 个结构, {len(result.zones)} 个关键区")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("极值点", len(result.pivots))
    col2.metric("段", len(result.segments))
    col3.metric("结构", len(result.structures))
    col4.metric("丛", len(result.bundles))

    # 丛分类
    st.subheader("丛 (Bundle) 分类")
    bundle_data = []
    for i, b in enumerate(result.bundles):
        bundle_data.append({
            "丛": i + 1,
            "类型": b.generator_constraint,
            "结构数": len(b.structures),
            "avg_speed_r": f"{sum(s.avg_speed_ratio for s in b.structures) / len(b.structures):.2f}" if b.structures else "-",
            "avg_time_r": f"{sum(s.avg_time_ratio for s in b.structures) / len(b.structures):.2f}" if b.structures else "-",
        })
    st.dataframe(pd.DataFrame(bundle_data), use_container_width=True)

    # 结构列表
    st.subheader("结构列表")
    struct_data = []
    for i, s in enumerate(result.structures):
        inv = s.invariants
        struct_data.append({
            "#": i + 1,
            "Zone": f"{s.zone.price_center:.0f}",
            "来源": s.zone.source.value,
            "Cycles": s.cycle_count,
            "speed_r": f"{s.avg_speed_ratio:.2f}",
            "time_r": f"{s.avg_time_ratio:.2f}",
            "stddev": f"{s.high_cluster_stddev:.0f}",
            "strength": f"{s.zone.strength:.1f}",
        })
    st.dataframe(pd.DataFrame(struct_data), use_container_width=True)


# ─── Tab 2: 结构详情 ──────────────────────────────────────

with tab2:
    if result.structures:
        idx = st.selectbox("选择结构", range(len(result.structures)),
                           format_func=lambda i: f"#{i+1} Zone={result.ranked_structures[i].zone.price_center:.0f}")
        st_obj = result.ranked_structures[idx]

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Zone**: {st_obj.zone.price_center:.0f} (±{st_obj.zone.bandwidth:.0f})")
            st.write(f"**来源**: {st_obj.zone.source.value}")
            st.write(f"**强度**: {st_obj.zone.strength:.1f}")
            st.write(f"**相对带宽**: {st_obj.zone.relative_bandwidth:.4f}")
        with col2:
            st.write(f"**Cycles**: {st_obj.cycle_count}")
            st.write(f"**avg_speed_ratio**: {st_obj.avg_speed_ratio:.3f}")
            st.write(f"**avg_time_ratio**: {st_obj.avg_time_ratio:.3f}")
            st.write(f"**high_cluster_cv**: {st_obj.high_cluster_cv:.4f}")

        # 特征向量
        st.subheader("特征向量")
        features = extract_features(st_obj)
        feat_df = pd.DataFrame({"特征": FEATURE_NAMES, "值": [f"{v:.4f}" for v in features]})
        st.dataframe(feat_df, use_container_width=True)

        # Cycle 详情
        st.subheader("Cycle 详情")
        cycle_data = []
        for i, c in enumerate(st_obj.cycles[:10]):
            cycle_data.append({
                "#": i + 1,
                "entry": f"{'↑' if c.entry.delta > 0 else '↓'} {c.entry.delta:+.0f} in {c.entry.duration:.0f}d",
                "exit": f"{'↑' if c.exit.delta > 0 else '↓'} {c.exit.delta:+.0f} in {c.exit.duration:.0f}d",
                "speed_r": f"{c.speed_ratio:.2f}",
                "time_r": f"{c.time_ratio:.2f}",
                "amp_r": f"{c.amplitude_ratio:.2f}",
            })
        st.dataframe(pd.DataFrame(cycle_data), use_container_width=True)


# ─── Tab 3: 相似检索 ──────────────────────────────────────

with tab3:
    if result.structures:
        # 规则扫描
        matches = scan(result.structures, rules)
        st.subheader(f"规则匹配: {len(matches)} / {len(result.structures)}")

        match_data = []
        for m in matches:
            match_data.append({
                "结构": m.structure.zone.price_center,
                "规则": m.rule.name,
                "typicality": f"{m.typicality:.2f}",
            })
        if match_data:
            st.dataframe(pd.DataFrame(match_data), use_container_width=True)

        # 选一个结构做检索
        idx = st.selectbox("选择查询结构", range(len(result.structures)),
                           format_func=lambda i: f"#{i+1} Zone={result.ranked_structures[i].zone.price_center:.0f} ({result.ranked_structures[i].label or 'unlabeled'})",
                           key="retrieval_idx")
        query = result.ranked_structures[idx]

        # 样本库检索
        store = SampleStore("data/samples/library.jsonl")
        if store.count() > 0:
            engine = RetrievalEngine(store)
            ret = engine.retrieve(query, top_k=top_k, min_score=min_score)

            if ret.neighbors:
                st.subheader(f"近邻 ({len(ret.neighbors)} 个)")
                for i, n in enumerate(ret.neighbors):
                    with st.expander(f"[{i+1}] {n.sample.label_type} — score={n.score.total:.3f}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"**ID**: {n.sample.id}")
                            st.write(f"**时间**: {n.sample.t_start:%Y-%m-%d} ~ {n.sample.t_end:%Y-%m-%d}")
                            st.write(f"**typicality**: {n.sample.typicality:.2f}")
                        with c2:
                            st.write(f"**几何相似**: {n.score.geometric:.3f}")
                            st.write(f"**关系相似**: {n.score.relational:.3f}")
                            st.write(f"**族相似**: {n.score.family:.3f}")
                        if n.sample.forward_outcome:
                            fo = n.sample.forward_outcome
                            st.write(f"前向: 5d={fo.get('ret_5d', 0):.2%} | 10d={fo.get('ret_10d', 0):.2%} | "
                                    f"20d={fo.get('ret_20d', 0):.2%} | max_dd={fo.get('max_dd_20d', 0):.2%}")

                # 后验统计
                p = ret.posterior
                st.subheader("后验统计")
                cols = st.columns(4)
                cols[0].metric("样本数", p.sample_size)
                cols[1].metric("ret_5d", f"{p.mean_ret_5d:+.2%}")
                cols[2].metric("ret_10d", f"{p.mean_ret_10d:+.2%}")
                cols[3].metric("ret_20d", f"{p.mean_ret_20d:+.2%}")
                cols = st.columns(3)
                cols[0].metric("P(正收益 10d)", f"{p.prob_positive_10d:.0%}")
                cols[1].metric("max_dd", f"{p.mean_max_dd_20d:+.2%}")
                cols[2].metric("max_rise", f"{p.mean_max_rise_20d:+.2%}")
            else:
                st.info("无足够相似样本")
        else:
            st.warning("样本库为空，请先运行 scripts/run_pipeline.py 沉淀样本")


# ─── Tab 4: 研究日志 ──────────────────────────────────────

with tab4:
    st.subheader("📝 研究日志")

    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    note = st.text_area("记录研究笔记", height=150)
    if st.button("保存"):
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        log_file = log_dir / f"{ts}.md"
        log_file.write_text(f"# {datetime.now():%Y-%m-%d %H:%M}\n\n{note}\n", encoding="utf-8")
        st.success(f"已保存到 {log_file}")

    # 展示已有日志
    logs = sorted(log_dir.glob("*.md"), reverse=True)
    if logs:
        st.subheader("历史日志")
        for log_file in logs[:5]:
            with st.expander(log_file.stem):
                st.text(log_file.read_text(encoding="utf-8"))
