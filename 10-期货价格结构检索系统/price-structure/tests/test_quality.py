"""质量分层系统测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.data.loader import load_cu0
from src.compiler.pipeline import compile_full, CompilerConfig
from src.quality import (
    assess_quality, stratify_structures, QualityTier,
    QualityAssessment, StratificationResult,
    quality_weighted_candidates, quality_summary_for_display,
)


@pytest.fixture
def compiled():
    """加载 CU0 数据并编译"""
    bars = load_cu0()
    data = bars.get(start='2025-01-01', end='2026-04-01')
    result = compile_full(data, CompilerConfig(min_amplitude=0.03), symbol='CU000')
    return result


class TestAssessQuality:
    """单结构质量评估"""

    def test_returns_assessment(self, compiled):
        """正常结构返回 QualityAssessment"""
        s = compiled.structures[0]
        ss = compiled.system_states[0]
        qa = assess_quality(s, ss)
        assert isinstance(qa, QualityAssessment)
        assert 0 <= qa.score <= 1
        assert qa.tier in QualityTier

    def test_without_system_state(self, compiled):
        """无 SystemState 也能评估"""
        s = compiled.structures[0]
        qa = assess_quality(s, None)
        assert isinstance(qa, QualityAssessment)
        assert qa.score > 0

    def test_breakdown_has_5_dims(self, compiled):
        """breakdown 包含 5 个维度"""
        s = compiled.structures[0]
        qa = assess_quality(s)
        assert len(qa.breakdown) == 5
        assert "完整性" in qa.breakdown
        assert "运动可信" in qa.breakdown
        assert "守恒一致" in qa.breakdown
        assert "时间成熟" in qa.breakdown
        assert "后验可追溯" in qa.breakdown

    def test_tier_thresholds(self, compiled):
        """分层阈值：A>=0.75, B>=0.50, C>=0.25, D<0.25"""
        for s in compiled.structures:
            qa = assess_quality(s)
            if qa.score >= 0.75:
                assert qa.tier == QualityTier.A
            elif qa.score >= 0.50:
                assert qa.tier == QualityTier.B
            elif qa.score >= 0.25:
                assert qa.tier == QualityTier.C
            else:
                assert qa.tier == QualityTier.D

    def test_flags_are_warnings(self, compiled):
        """flags 只包含 ⚠ 和 🔴 开头的"""
        for s in compiled.structures:
            qa = assess_quality(s)
            for f in qa.flags:
                assert f.startswith("⚠") or f.startswith("🔴")


class TestStratify:
    """批量分层"""

    def test_returns_stratification(self, compiled):
        strat = stratify_structures(compiled.structures, compiled.system_states)
        assert isinstance(strat, StratificationResult)
        assert strat.total == len(compiled.structures)

    def test_tier_sum_equals_total(self, compiled):
        strat = stratify_structures(compiled.structures)
        tier_sum = sum(strat.stats.get(t, 0) for t in ["A", "B", "C", "D"])
        assert tier_sum == strat.total

    def test_ab_structures_subset(self, compiled):
        strat = stratify_structures(compiled.structures)
        assert len(strat.ab_structures) <= strat.total

    def test_empty_input(self):
        strat = stratify_structures([])
        assert strat.total == 0
        assert strat.ab_structures == []


class TestQualityWeighted:
    """质量加权检索"""

    def test_candidates_have_weights(self, compiled):
        strat = stratify_structures(compiled.structures)
        candidates = quality_weighted_candidates(strat)
        for s, w in candidates:
            assert 0 < w <= 1.0

    def test_a_layer_weight_higher(self, compiled):
        """A 层权重 > B 层权重"""
        strat = stratify_structures(compiled.structures)
        candidates = quality_weighted_candidates(strat)
        a_weights = [w for s, w in candidates if any(
            qa.tier == QualityTier.A for s2, qa in strat.tiers.get("A", []) if s2 is s
        )]
        b_weights = [w for s, w in candidates if any(
            qa.tier == QualityTier.B for s2, qa in strat.tiers.get("B", []) if s2 is s
        )]
        if a_weights and b_weights:
            assert max(a_weights) > max(b_weights)


class TestQualitySummary:
    """质量摘要"""

    def test_summary_dict_keys(self, compiled):
        s = compiled.structures[0]
        summary = quality_summary_for_display(s)
        assert "tier" in summary
        assert "quality_score" in summary
        assert "retrieval_weight" in summary
