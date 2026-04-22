"""
叙事化输出生成器 — V1.6 P1

将 SystemState 转化为自然语言诊断报告，
降低用户对守恒通量、投影觉知、稳态等概念的认知门槛。

核心原则：
  "不要向用户抛出 time_compression_ratio > 1.5 的原始数值，
   而应转化为：入场慢出场快，表明时间差异剧烈。"
"""

from __future__ import annotations
from src.models import SystemState, Structure, ContrastType, StabilityVerdict


def generate_diagnostic_report(ss: SystemState) -> str:
    """
    生成完整的自然语言诊断报告。
    适合在工作台页面或每日报告中展示。
    """
    sections = []
    st = ss.structure

    # ── 1. 结构概述 ──
    sections.append(_section_structure(st))

    # ── 2. 运动态解读 ──
    sections.append(_section_motion(ss))

    # ── 3. 稳定性判定 ──
    sections.append(_section_stability(ss.stability))

    # ── 4. 差异分层 ──
    sections.append(_section_diff_layers(ss))

    # ── 5. 投影觉知 ──
    sections.append(_section_projection(ss))

    # ── 6. 最近稳态分析 ──
    sections.append(_section_stable_state(st))

    return "\n\n".join(s for s in sections if s)


def generate_match_explanation(
    query: Structure,
    matched: Structure,
    similarity_score: float,
    match_reason: str,
    posterior_summary: str = "",
) -> str:
    """
    生成单个匹配结果的归因解释。
    "知其然更知其所以然"
    """
    lines = []
    lines.append(f"匹配度 {similarity_score:.0%}")
    lines.append(f"匹配原因：{match_reason}")

    if posterior_summary:
        lines.append(f"历史后续表现：{posterior_summary}")

    return " | ".join(lines)


def generate_daily_summary(system_states: list[SystemState]) -> str:
    """
    每日扫描结果的叙事化摘要。
    替代"今日发现 3 个结构"的干巴巴报告。
    """
    if not system_states:
        return "今日无显著结构信号。"

    # 按可靠性排序：可靠的放前面
    reliable = [ss for ss in system_states if ss.is_reliable]
    blind = [ss for ss in system_states if ss.projection.is_blind]
    warning = [ss for ss in system_states
               if ss.stability.surface == "stable" and not ss.stability.verified]

    lines = []
    lines.append(f"今日共扫描 {len(system_states)} 个结构：")

    if reliable:
        lines.append(f"  ✅ {len(reliable)} 个可信结构")
        for ss in reliable[:3]:
            st = ss.structure
            lines.append(f"    · {st.symbol or '?'} {st.narrative_context or st.zone.price_center:.0f} "
                         f"— {ss.motion.phase_tendency}")

    if warning:
        lines.append(f"  🟡 {len(warning)} 个表面稳定、待验证")
        for ss in warning[:3]:
            st = ss.structure
            channels = ", ".join(ss.stability.pending_channels[:2])
            lines.append(f"    · {st.symbol or '?'} {st.narrative_context or st.zone.price_center:.0f} "
                         f"— 等待 {channels} 的{ss.stability.verification_window}天观察期")

    if blind:
        lines.append(f"  ⚠️ {len(blind)} 个高压缩结构（影子可能不代表实体）")
        for ss in blind[:3]:
            st = ss.structure
            lines.append(f"    · {st.symbol or '?'} {st.narrative_context or st.zone.price_center:.0f} "
                         f"— 压缩度 {ss.projection.compression_level:.0%}，"
                         f"差异可能藏在 {', '.join(ss.projection.blind_channels[:2])}")

    return "\n".join(lines)


# ─── 私有辅助 ──────────────────────────────────────────────


CONTRAST_LABELS = {
    ContrastType.PANIC: "恐慌性结构",
    ContrastType.OVERSUPPLY: "供需失衡结构",
    ContrastType.POLICY: "政策驱动结构",
    ContrastType.LIQUIDITY: "流动性驱动结构",
    ContrastType.SPECULATION: "投机驱动结构",
    ContrastType.UNKNOWN: "",
}

SPEED_LABELS = {
    lambda sr: sr > 1.5: "急跌/急涨型",
    lambda sr: sr < 0.67: "慢跌/慢涨型",
}


def _section_structure(st: Structure) -> str:
    """结构概述：是什么"""
    parts = []
    parts.append("【结构】")

    if st.narrative_context:
        parts.append(f"  {st.narrative_context}")
    else:
        parts.append(f"  Zone {st.zone.price_center:.0f}（±{st.zone.bandwidth:.0f}），{st.cycle_count}次试探")

    if st.zone.context_contrast != ContrastType.UNKNOWN:
        ct = CONTRAST_LABELS.get(st.zone.context_contrast, "")
        if ct:
            parts.append(f"  共同反差：{ct}")

    return "\n".join(parts)


def _section_motion(ss: SystemState) -> str:
    """运动态解读：在怎么动"""
    parts = []
    parts.append("【运动】")

    m = ss.motion
    if m.phase_tendency:
        parts.append(f"  阶段趋势：{m.phase_tendency}（置信度 {m.phase_confidence:.0%}）")

    if m.flux_detail:
        parts.append(f"  守恒通量：{m.flux_detail}")
    elif m.conservation_flux != 0:
        direction = "释放" if m.conservation_flux > 0 else "压缩"
        parts.append(f"  守恒通量：差异{direction}中（{m.conservation_flux:+.2f}）")

    if m.transfer_target:
        parts.append(f"  差异转移：{m.transfer_source} → {m.transfer_target}（强度 {m.transfer_strength:.0%}）")

    if m.structural_age > 0:
        parts.append(f"  结构年龄：{m.structural_age}个周期，当前阶段已持续{m.phase_duration}个周期")

    return "\n".join(parts)


def _section_stability(sv: StabilityVerdict) -> str:
    """稳定性判定：红绿灯"""
    parts = []
    parts.append("【稳定性】")
    parts.append(f"  {sv.traffic_light}")

    if sv.surface == "stable" and not sv.verified:
        parts.append(f"  → 价格波动收敛，但差异可能已转移到其他维度")
        parts.append(f"  → 需要 {sv.verification_window} 天观察期验证")
        if sv.pending_channels:
            parts.append(f"  → 待验证通道：{', '.join(sv.pending_channels)}")

    return "\n".join(parts)


def _section_diff_layers(ss: SystemState) -> str:
    """差异分层解读：三种差异的显影"""
    parts = []
    any_active = False

    parts.append("【差异分层】")

    if ss.liquidity_stress > 0:
        any_active = True
        if ss.liquidity_stress > 1.5:
            parts.append(f"  流动性：Zone 内成交量异常放大，多空激烈交锋，差异正在释放（应力={ss.liquidity_stress:.1f}）")
        elif ss.liquidity_stress < 0.5:
            parts.append(f"  流动性：Zone 内成交量萎缩，流动性枯竭，差异被压缩（应力={ss.liquidity_stress:.1f}）")
        else:
            parts.append(f"  流动性：正常（应力={ss.liquidity_stress:.1f}）")

    if ss.time_compression > 0:
        any_active = True
        if ss.time_compression > 1.5:
            parts.append(f"  时间差异：入场慢而出场快，恐慌性退出信号（比值={ss.time_compression:.1f}）")
        elif ss.time_compression < 0.67:
            parts.append(f"  时间差异：入场快出场慢，缓慢消化型（比值={ss.time_compression:.1f}）")

    if ss.fear_index > 0:
        any_active = True
        if ss.fear_index > 0.6:
            parts.append(f"  边界恐惧：试探密集+波动率突变，市场紧张（恐惧指数={ss.fear_index:.2f}）")
        elif ss.fear_index > 0.3:
            parts.append(f"  边界恐惧：中等紧张（恐惧指数={ss.fear_index:.2f}）")

    if not any_active:
        parts.append("  暂无成交量/OI数据，三种差异维度未显影")

    return "\n".join(parts)


def _section_projection(ss: SystemState) -> str:
    """投影觉知：可信度"""
    parts = []
    parts.append("【投影觉知】")

    p = ss.projection
    if p.is_blind:
        parts.append(f"  ⚠️ 高压缩（{p.compression_level:.0%}），系统可能在看假象")
        parts.append(f"  差异可能藏在：{', '.join(p.blind_channels)}")
        parts.append(f"  投影可信度：{p.projection_confidence:.0%}")
    else:
        parts.append(f"  投影压缩度：{p.compression_level:.0%}，可信度：{p.projection_confidence:.0%}")

    if p.observation:
        parts.append(f"  观测：{p.observation}")

    return "\n".join(parts)


def _section_stable_state(st: Structure) -> str:
    """最近稳态分析：如果崩塌，先到哪"""
    parts = []
    parts.append("【最近稳态】")

    if not st.cycles:
        parts.append("  无 cycle 数据")
        return "\n".join(parts)

    stable_cycles = [c for c in st.cycles if c.has_stable_state]
    if not stable_cycles:
        parts.append("  未识别到稳态（exit 后价格尚未停驻）")
        parts.append("  这可能意味着：结构仍在运动中，或下一个稳态在更远处")
        return "\n".join(parts)

    # 最近的稳态
    latest = stable_cycles[-1].next_stable
    parts.append(f"  最近稳态价位：{latest.zone.price_center:.0f}" if latest.zone else "  最近稳态价位：未知")
    parts.append(f"  到达耗时：{latest.duration_to_arrive:.0f}天")
    parts.append(f"  阻力评分：{latest.resistance_level:.2f}（越低越容易到达）")

    if latest.resistance_level < 0.2:
        parts.append("  ⚠️ 阻力异常低，可能是表面稳态，差异在隐性积累")

    ratio = st.stable_state_ratio
    parts.append(f"  {len(stable_cycles)}/{len(st.cycles)} 个 cycle 已识别稳态（{ratio:.0%}）")

    return "\n".join(parts)
