"""
质量分层集成 — 给现有 app.py 添加质量分层显示的补丁代码

⚠️ 质量分层功能已集成到 app.py Tab 8（"🔬 v3.0 质量与共振"）。
    此文件保留为参考实现，提供可复用的工具函数：
    - quality_badge_html(): 质量徽章 HTML
    - scan_with_quality(): 质量分层扫描
    - quality_weighted_retrieval(): 质量加权检索
    - render_quality_panel(): 质量统计面板
"""

import streamlit as st
from src.quality import (
    assess_quality, stratify_structures,
    QualityTier, QualityAssessment,
    quality_summary_for_display,
)


# ─── 1. 给结构卡片添加质量徽章 ────────────────────────────

def quality_badge_html(s, ss=None) -> str:
    """
    生成质量徽章 HTML，插入到现有结构卡片中。

    用法：在 _render_structure_card() 或 app.py 的卡片渲染中加入：
        {quality_badge_html(s, ss)}
    """
    qa = assess_quality(s, ss)

    colors = {
        "A": ("#1b5e20", "#c8e6c9"),  # 深绿字，浅绿底
        "B": ("#0d47a1", "#bbdefb"),  # 深蓝字，浅蓝底
        "C": ("#e65100", "#ffe0b2"),  # 深橙字，浅橙底
        "D": ("#b71c1c", "#ffcdd2"),  # 深红字，浅红底
    }

    fg, bg = colors.get(qa.tier.value, ("#666", "#eee"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:3px;'
        f'font-size:0.82em;font-weight:700;margin-left:6px">'
        f'{qa.tier.value}层 {qa.score:.0%}</span>'
    )


# ─── 2. 全市场扫描加入质量分层 ────────────────────────────

def scan_with_quality(all_structures, all_system_states=None):
    """
    全市场扫描后，用质量分层过滤和排序。

    替代原来的 ranked_structures 直接展示逻辑。
    """
    strat = stratify_structures(all_structures, all_system_states)

    # 只展示 A+B 层
    display = []
    for s, qa in strat.tiers.get("A", []):
        display.append({"structure": s, "tier": "A", "score": qa.score, "flags": qa.flags})
    for s, qa in strat.tiers.get("B", []):
        display.append({"structure": s, "tier": "B", "score": qa.score, "flags": qa.flags})

    display.sort(key=lambda x: x["score"], reverse=True)
    return display, strat


# ─── 3. 检索引擎质量加权 ──────────────────────────────────

def quality_weighted_retrieval(query, candidates, candidate_weights=None):
    """
    质量加权检索：候选结构的质量分层权重 × 相似度 = 最终排序分。

    替代 RetrievalEngine.retrieve() 中的纯相似度排序。
    """
    from src.retrieval.similarity import similarity

    results = []
    for i, c in enumerate(candidates):
        sim = similarity(query, c)
        w = candidate_weights[i] if candidate_weights else 1.0
        final_score = sim.total * w
        results.append({
            "structure": c,
            "similarity": sim.total,
            "quality_weight": w,
            "final_score": final_score,
        })

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


# ─── 4. Streamlit 质量统计面板 ────────────────────────────

def render_quality_panel(strat):
    """
    渲染质量分层统计面板。

    在全市场扫描结果下方添加。
    """
    st.markdown("##### 📊 结构质量分层")

    col_a, col_b, col_c, col_d, col_total = st.columns(5)
    col_a.metric("A层·高质量", strat.stats.get("A", 0))
    col_b.metric("B层·中等", strat.stats.get("B", 0))
    col_c.metric("C层·低质量", strat.stats.get("C", 0))
    col_d.metric("D层·噪声", strat.stats.get("D", 0))
    col_total.metric("总计", strat.total)

    # 分层详情
    with st.expander("分层详情", expanded=False):
        for tier_val in ["A", "B", "C", "D"]:
            items = strat.tiers.get(tier_val, [])
            if not items:
                continue
            tier = QualityTier(tier_val)
            st.markdown(f"**{tier.label}** ({len(items)} 个)")
            for s, qa in items[:5]:
                flags_str = ", ".join(qa.flags[:2]) if qa.flags else "无标记"
                st.caption(
                    f"  Zone {s.zone.price_center:.0f} · "
                    f"{s.cycle_count} cycles · "
                    f"质量 {qa.score:.0%} · "
                    f"{flags_str}"
                )
