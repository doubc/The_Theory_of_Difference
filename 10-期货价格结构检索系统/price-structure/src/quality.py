"""
结构质量分层系统 — 将编译出的结构按质量分为 A/B/C/D 四层

核心问题：
    当前系统把所有结构等价对待——一个 5 cycle 强 Zone 的结构
    和一个 2 cycle 弱 Zone 的结构在检索时权重相同。
    这导致后验统计被低质量结构稀释，检索结果信噪比低。

解决方案：
    多维度质量评分 → 自动分层 → 检索/统计时按层加权

质量维度（5 个）：
    1. 结构完整性 — cycle 数、zone 强度、不变量完整度
    2. 运动可信度 — 稳定性验证、投影非盲
    3. 守恒一致性 — 守恒通量方向合理、无异常
    4. 时间成熟度 — 结构年龄适中（不太新不太老）
    5. 后验可追溯 — 有历史样本库匹配、有已知结果

分层标准：
    A 层 (Score ≥ 0.75): 高质量 — 可直接用于检索和统计
    B 层 (0.50 ≤ Score < 0.75): 中等质量 — 检索时降权
    C 层 (0.25 ≤ Score < 0.50): 低质量 — 仅参考，不进入后验统计
    D 层 (Score < 0.25): 噪声 — 丢弃或标记为"待验证"

用法：
    from src.quality import assess_quality, stratify_structures, QualityTier

    # 单个结构评估
    qa = assess_quality(structure, system_state)
    print(qa.tier, qa.score, qa.dimension_scores)

    # 批量分层
    tiers = stratify_structures(structures, system_states)
    a_structures = tiers["A"]  # 高质量结构
"""

from src.knowledge.engine import KnowledgeEngine
from src.knowledge.result import KnowledgeResult


# ─── 质量等级 ─────────────────────────────────────────────

class QualityTier(Enum):
    """结构质量等级"""
    A = "A"  # 高质量 — 可直接用于检索和统计
    B = "B"  # 中等质量 — 检索时降权
    C = "C"  # 低质量 — 仅参考
    D = "D"  # 噪声 — 丢弃或待验证

    @property
    def label(self) -> str:
        labels = {
            "A": "🟢 A层·高质量",
            "B": "🔵 B层·中等",
            "C": "🟡 C层·低质量",
            "D": "🔴 D层·噪声",
        }
        return labels[self.value]

    @property
    def retrieval_weight(self) -> float:
        """检索时的权重系数"""
        return {"A": 1.0, "B": 0.6, "C": 0.25, "D": 0.0}[self.value]

    @property
    def include_in_posterior(self) -> bool:
        """是否纳入后验统计"""
        return self.value in ("A", "B")


# ─── 质量评估结果 ─────────────────────────────────────────

@dataclass
class QualityAssessment:
    """单个结构的质量评估结果"""
    tier: QualityTier
    score: float                # 综合质量分 [0, 1]
    dimension_scores: dict[str, float] # 各维度得分
    flags: list[str]            # 质量标记（问题/亮点）
    recommendations: list[str]  # 改进建议

    def summary(self) -> str:
        parts = [f"{self.tier.label} ({self.score:.0%})"]
        for dim, val in self.dimension_scores.items():
            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
            parts.append(f"  {dim}: {bar} {val:.2f}")
        if self.flags:
            parts.append(f"  标记: {', '.join(self.flags)}")
        return "\n".join(parts)


# ─── 质量维度评分函数 ─────────────────────────────────────

def _score_completeness(s: Structure) -> tuple[float, list[str]]:
    """
    维度 1: 结构完整性

    评估标准：
    - Cycle 数量 (≥3 为佳)
    - Zone 强度 (触及次数)
    - 不变量完整度 (关键字段是否齐全)
    """
    flags = []
    score = 0.0

    # Cycle 数量 (0.4 权重)
    n_cycles = s.cycle_count
    if n_cycles >= 5:
        cycle_score = 1.0
        flags.append(f"✓ {n_cycles}次试探（充分）")
    elif n_cycles >= 3:
        cycle_score = 0.7
    elif n_cycles >= 2:
        cycle_score = 0.4
    else:
        cycle_score = 0.1
        flags.append(f"⚠ 仅{n_cycles}次试探（不足）")
    score += 0.4 * cycle_score

    # Zone 强度 (0.3 权重)
    zone_strength = s.zone.strength if s.zone else 0
    if zone_strength >= 3:
        zone_score = 1.0
    elif zone_strength >= 1.5:
        zone_score = 0.6
    elif zone_strength >= 0.5:
        zone_score = 0.3
    else:
        zone_score = 0.1
        flags.append("⚠ Zone 强度低")
    score += 0.3 * zone_score

    # 不变量完整度 (0.3 权重)
    inv = s.invariants or {}
    key_fields = ["cycle_count", "avg_speed_ratio", "avg_time_ratio", "zone_rel_bw"]
    filled = sum(1 for k in key_fields if inv.get(k) is not None and inv.get(k) != 0)
    inv_score = filled / len(key_fields)
    if inv_score < 0.5:
        flags.append("⚠ 不变量不完整")
    score += 0.3 * inv_score

    return min(score, 1.0), flags


def _score_motion_credibility(s: Structure, ss: SystemState | None) -> tuple[float, list[str]]:
    """
    维度 2: 运动可信度

    评估标准：
    - 稳定性判定是否经过验证（绿灯 > 黄灯 > 红灯）
    - 投影觉知是否为盲（非盲 > 盲）
    - 运动态置信度
    """
    flags = []
    score = 0.0

    if ss is None:
        # 无 SystemState → 只看 motion
        m = s.motion
        if m:
            score = 0.3  # 有运动态但无验证
            if m.phase_confidence > 0.7:
                score += 0.2
        else:
            score = 0.1
            flags.append("⚠ 无运动态")
        return score, flags

    # 稳定性判定 (0.4 权重)
    stability = ss.stability
    if stability and stability.verified and stability.surface == "stable":
        stab_score = 1.0
        flags.append("✓ 绿灯·已验证稳定")
    elif stability and stability.surface == "stable" and not stability.verified:
        stab_score = 0.5  # 表面稳定但未验证
        flags.append("⚠ 黄灯·表面稳定待验证")
    elif stability and stability.surface == "unstable":
        stab_score = 0.2
    else:
        stab_score = 0.1
    score += 0.4 * stab_score

    # 投影觉知 (0.35 权重)
    proj = ss.projection
    if proj:
        if proj.is_blind:
            proj_score = 0.2
            flags.append(f"⚠ 高压缩{proj.compression_level:.0%}·投影可能为假象")
        elif proj.compression_level > 0.5:
            proj_score = 0.5
        else:
            proj_score = 1.0
    else:
        proj_score = 0.3
    score += 0.35 * proj_score

    # 运动态置信度 (0.25 权重)
    m = s.motion
    if m:
        conf = m.phase_confidence
        if conf > 0.8:
            mot_score = 1.0
        elif conf > 0.5:
            mot_score = 0.6
        else:
            mot_score = 0.3
            flags.append(f"⚠ 运动态置信度低({conf:.0%})")

        # 运动类型加成
        if hasattr(m, 'movement_type') and m.movement_type:
            mt = m.movement_type.value
            if mt in ("trend_up", "trend_down"):
                mot_score = min(mot_score * 1.15, 1.0)  # 有明确趋势方向加分
            elif mt == "reversal":
                mot_score = min(mot_score * 1.1, 1.0)   # 反转是明确事件
    else:
        mot_score = 0.1
    score += 0.25 * mot_score

    return min(score, 1.0), flags


def _score_conservation(s: Structure, ss: SystemState | None) -> tuple[float, list[str]]:
    """
    维度 3: 守恒一致性

    评估标准：
    - 守恒通量方向是否合理（不能太极端）
    - 差异分层是否异常
    - 速度比/时间比是否在合理范围
    """
    flags = []
    score = 0.0

    # 守恒通量 (0.4 权重)
    m = s.motion
    if m:
        flux = m.conservation_flux
        if -1.0 <= flux <= 1.0:
            flux_score = 1.0
        elif -2.0 <= flux <= 2.0:
            flux_score = 0.6
            flags.append(f"⚠ 通量偏极端({flux:+.2f})")
        else:
            flux_score = 0.2
            flags.append(f"🔴 通量异常({flux:+.2f})")
    else:
        flux_score = 0.3
    score += 0.4 * flux_score

    # 速度比合理性 (0.3 权重)
    sr = s.avg_speed_ratio
    if 0.2 <= sr <= 5.0:
        sr_score = 1.0
    elif 0.1 <= sr <= 10.0:
        sr_score = 0.5
        flags.append(f"⚠ 速度比异常({sr:.2f})")
    else:
        sr_score = 0.1
        flags.append(f"🔴 速度比极端({sr:.2f})")
    score += 0.3 * sr_score

    # 差异分层 (0.3 权重)
    if ss:
        layer_score = 1.0
        if ss.liquidity_stress > 3.0:
            layer_score -= 0.3
            flags.append("⚠ 流动性应力异常")
        if ss.fear_index > 0.8:
            layer_score -= 0.3
            flags.append("⚠ 边界恐惧极高")
        if ss.time_compression > 3.0 or (0 < ss.time_compression < 0.3):
            layer_score -= 0.2
        layer_score = max(0, layer_score)
    else:
        layer_score = 0.5
    score += 0.3 * layer_score

    return min(score, 1.0), flags


def _score_maturity(s: Structure) -> tuple[float, list[str]]:
    """
    维度 4: 时间成熟度

    评估标准：
    - 结构年龄（cycle 数）适中：3-8 为佳
    - 阶段持续时间合理
    - 不太新（≥2 cycles）不太老（≤15 cycles）
    """
    flags = []
    n = s.cycle_count

    if 3 <= n <= 8:
        score = 1.0
    elif n == 2:
        score = 0.5
        flags.append("⚠ 结构较年轻（2 cycles）")
    elif 9 <= n <= 12:
        score = 0.7
    elif n > 12:
        score = 0.4
        flags.append(f"⚠ 结构过老（{n} cycles），可能即将破缺")
    else:
        score = 0.2

    # 阶段信息
    m = s.motion
    if m:
        if "breakout" in m.phase_tendency:
            score *= 0.7  # 正在破缺的结构质量打折
            flags.append("⚠ 正在破缺")
        elif "confirmation" in m.phase_tendency:
            score = min(score * 1.1, 1.0)  # 确认中的结构加分

    return min(score, 1.0), flags


def _score_traceability(s: Structure) -> tuple[float, list[str]]:
    """
    维度 5: 后验可追溯性

    评估标准：
    - 是否有标签（rule engine 打的标）
    - 是否有典型度（typicality）
    - 是否有样本库匹配
    """
    flags = []
    score = 0.0

    # 标签 (0.4)
    if s.label:
        score += 0.4
    else:
        score += 0.1
        flags.append("⚠ 无结构标签")

    # 典型度 (0.3)
    if s.typicality > 0.7:
        score += 0.3
    elif s.typicality > 0.3:
        score += 0.15
    else:
        score += 0.05

    # 叙事背景 (0.3)
    if s.narrative_context and len(s.narrative_context) > 10:
        score += 0.3
    elif s.narrative_context:
        score += 0.15
    else:
        score += 0.05
        flags.append("⚠ 无叙事背景")

    return min(score, 1.0), flags


def _score_knowledge(kr: KnowledgeResult) -> tuple[float, list[str]]:
    """
    维度 6: 知识置信度

    基于 L1/L2/L3 三层知识匹配结果评估：
    - L1 判定知识：正向加权
    - L2 失效知识：负向减权（高严重度直接降层）
    - L3 市场知识：参考加成
    """
    flags = []
    score = 0.5  # 基准分

    # L1 判定知识：每条 +0.10，上限 0.30
    l1_boost = min(len(kr.conditions) * 0.10, 0.30)
    score += l1_boost
    for r in kr.conditions:
        flags.append(f"✅ [{r.id}] {r.name}")

    # L2 失效知识：高严重度 -0.20，中严重度 -0.10
    for r in kr.invalidations:
        if r.severity == "high":
            score -= 0.20
            flags.append(f"🔴 [{r.id}] {r.name}")
        elif r.severity == "medium":
            score -= 0.10
            flags.append(f"⚠️ [{r.id}] {r.name}")
        else:
            score -= 0.05

    # L3 市场知识：每条 +0.03，上限 0.15
    l3_boost = min(len(kr.wisdoms) * 0.03, 0.15)
    score += l3_boost

    return max(0.0, min(score, 1.0)), flags


# ─── 综合质量评估 ─────────────────────────────────────────

# 维度权重
DIMENSION_WEIGHTS = {
    "完整性": 0.25,
    "运动可信": 0.25,
    "守恒一致": 0.20,
    "时间成熟": 0.15,
    "后验可追溯": 0.15,
}


def assess_quality(
    s: Structure,
    ss: SystemState | None = None,
    knowledge_result: KnowledgeResult | None = None,
) -> QualityAssessment:
    """
    评估单个结构的质量

    Args:
        s: 结构对象
        ss: 系统态（可选，有则评估更准确）
        knowledge_result: 知识引擎匹配结果（可选，有则增加知识维度）

    Returns:
        QualityAssessment
    """
    all_flags = []
    all_recommendations = []
    dimension_scores = {}

    # 各维度评分
    c_score, c_flags = _score_completeness(s)
    dimension_scores["完整性"] = c_score
    all_flags.extend(c_flags)

    m_score, m_flags = _score_motion_credibility(s, ss)
    dimension_scores["运动可信"] = m_score
    all_flags.extend(m_flags)

    con_score, con_flags = _score_conservation(s, ss)
    dimension_scores["守恒一致"] = con_score
    all_flags.extend(con_flags)

    t_score, t_flags = _score_maturity(s)
    dimension_scores["时间成熟"] = t_score
    all_flags.extend(t_flags)

    r_score, r_flags = _score_traceability(s)
    dimension_scores["后验可追溯"] = r_score
    all_flags.extend(r_flags)

    # ── 第 6 维度：知识置信度 ──
    if knowledge_result is not None and knowledge_result.total_matched > 0:
        k_score, k_flags = _score_knowledge(knowledge_result)
        dimension_scores["知识置信"] = k_score
        all_flags.extend(k_flags)
        # 加权综合分（知识维度占 10%，其他维度按比例缩减）
        base_total = (
            0.225 * c_score +  # 原 0.25 × 0.9
            0.225 * m_score +
            0.18 * con_score +  # 原 0.20 × 0.9
            0.135 * t_score +  # 原 0.15 × 0.9
            0.135 * r_score    # 原 0.15 × 0.9
        )
        total = base_total + 0.10 * k_score
    else:
        # 无知识：原始 5 维度
        total = (
            DIMENSION_WEIGHTS["完整性"] * c_score +
            DIMENSION_WEIGHTS["运动可信"] * m_score +
            DIMENSION_WEIGHTS["守恒一致"] * con_score +
            DIMENSION_WEIGHTS["时间成熟"] * t_score +
            DIMENSION_WEIGHTS["后验可追溯"] * r_score
        )

    # 分层
    if total >= 0.75:
        tier = QualityTier.A
    elif total >= 0.50:
        tier = QualityTier.B
    elif total >= 0.25:
        tier = QualityTier.C
    else:
        tier = QualityTier.D

    # 生成建议
    if c_score < 0.5:
        all_recommendations.append("增加更多 cycle 或提高 zone 强度")
    if m_score < 0.5:
        all_recommendations.append("等待稳定性验证或降低投影压缩度")
    if con_score < 0.5:
        all_recommendations.append("检查守恒通量和速度比是否异常")
    if t_score < 0.5:
        all_recommendations.append("等待更多数据或检查结构阶段")
    if r_score < 0.5:
        all_recommendations.append("补充标签、叙事背景或样本库匹配")

    return QualityAssessment(
        tier=tier,
        score=total,
        dimension_scores=dimension_scores,
        flags=[f for f in all_flags if f.startswith("⚠") or f.startswith("🔴")],
        recommendations=all_recommendations,
    )


# ─── 批量分层 ─────────────────────────────────────────────

@dataclass
class StratificationResult:
    """批量分层结果"""
    tiers: dict[str, list[tuple[Structure, QualityAssessment]]]  # tier → [(structure, assessment)]
    stats: dict[str, int]   # 每层的数量
    total: int

    @property
    def a_structures(self) -> list[Structure]:
        return [s for s, _ in self.tiers.get("A", [])]

    @property
    def b_structures(self) -> list[Structure]:
        return [s for s, _ in self.tiers.get("B", [])]

    @property
    def ab_structures(self) -> list[Structure]:
        """A+B 层：可用于检索和后验统计的结构"""
        return self.a_structures + self.b_structures

    def summary(self) -> str:
        lines = [f"结构分层: {self.total} 个"]
        for tier in ["A", "B", "C", "D"]:
            n = self.stats.get(tier, 0)
            pct = n / self.total * 100 if self.total else 0
            lines.append(f"  {QualityTier(tier).label}: {n} ({pct:.0f}%)")
        return "\n".join(lines)


def stratify_structures(
    structures: list[Structure],
    system_states: list[SystemState] | None = None,
) -> StratificationResult:
    """
    批量结构分层

    Args:
        structures: 编译出的结构列表
        system_states: 对应的系统态列表（可选）

    Returns:
        StratificationResult
    """
    tiers: dict[str, list] = {"A": [], "B": [], "C": [], "D": []}

    for i, s in enumerate(structures):
        ss = system_states[i] if system_states and i < len(system_states) else None
        qa = assess_quality(s, ss)
        tiers[qa.tier.value].append((s, qa))

    # 按质量分排序（每层内）
    for tier in tiers:
        tiers[tier].sort(key=lambda x: x[1].score, reverse=True)

    stats = {t: len(items) for t, items in tiers.items()}

    return StratificationResult(
        tiers=tiers,
        stats=stats,
        total=len(structures),
    )


# ─── 质量加权检索辅助 ─────────────────────────────────────

def quality_weighted_candidates(
    strat: StratificationResult,
    include_tiers: tuple[str, ...] = ("A", "B"),
) -> list[tuple[Structure, float]]:
    """
    从分层结果中提取检索候选，附带质量权重

    Args:
        strat: 分层结果
        include_tiers: 纳入检索的层级

    Returns:
        [(structure, weight), ...] — weight = 层级权重 × 质量分
    """
    candidates = []
    for tier_val in include_tiers:
        for s, qa in strat.tiers.get(tier_val, []):
            weight = qa.tier.retrieval_weight * qa.score
            candidates.append((s, weight))
    return candidates


def quality_summary_for_display(s: Structure, ss: SystemState | None = None) -> dict:
    """
    为 Streamlit 展示生成质量摘要

    返回一个 dict，可直接用于 st.metric / st.dataframe
    """
    qa = assess_quality(s, ss)
    return {
        "tier": qa.tier.value,
        "tier_label": qa.tier.label,
        "quality_score": qa.score,
        "completeness": qa.dimension_scores.get("完整性", 0),
        "motion_cred": qa.dimension_scores.get("运动可信", 0),
        "conservation": qa.dimension_scores.get("守恒一致", 0),
        "maturity": qa.dimension_scores.get("时间成熟", 0),
        "traceability": qa.dimension_scores.get("后验可追溯", 0),
        "flags": "; ".join(qa.flags[:3]),
        "recommendations": "; ".join(qa.recommendations[:2]),
        "retrieval_weight": qa.tier.retrieval_weight,
        "include_in_posterior": qa.tier.include_in_posterior,
    }


# ─── 知识增强评估 ─────────────────────────────────────────

# 全局知识引擎实例（惰性初始化）
_global_knowledge_engine: KnowledgeEngine | None = None


def get_knowledge_engine(knowledge_dir: str = "knowledge") -> KnowledgeEngine:
    """获取全局知识引擎实例"""
    global _global_knowledge_engine
    if _global_knowledge_engine is None:
        _global_knowledge_engine = KnowledgeEngine(knowledge_dir)
    return _global_knowledge_engine


def assess_quality_with_knowledge(
    s: Structure,
    ss: SystemState | None = None,
    knowledge_dir: str = "knowledge",
) -> tuple[QualityAssessment, KnowledgeResult]:
    """
    评估单个结构的质量（含知识引擎）

    Returns:
        (QualityAssessment, KnowledgeResult)
    """
    engine = get_knowledge_engine(knowledge_dir)
    kr = engine.evaluate(structure=s, motion=getattr(s, "motion", None))
    qa = assess_quality(s, ss, knowledge_result=kr)
    return qa, kr
