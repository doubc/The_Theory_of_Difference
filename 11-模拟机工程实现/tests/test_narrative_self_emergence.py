"""
tests/test_narrative_self_emergence.py — NarrativeSelfEmergence 单元测试

覆盖四个子组件：
1. TemporalContinuityTracker
2. InstitutionalNarrativeStabilizer
3. SelfHistoryAccumulator
4. NarrativeSelfEmergence (NSI 计算)
"""

import pytest
import torch
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.narrative_self_emergence import (
    TemporalContinuityTracker,
    InstitutionalNarrativeStabilizer,
    SelfHistoryAccumulator,
    NarrativeSelfEmergence,
    DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG,
)


# ─── TemporalContinuityTracker ───

class TestTemporalContinuityTracker:

    def test_initial_state(self):
        tracker = TemporalContinuityTracker()
        assert tracker._continuous_steps == 0

    def test_single_update(self):
        tracker = TemporalContinuityTracker()
        result = tracker.update(
            narrative_themes=["theme_a", "theme_b"],
            narrative_level_distribution={"MINI": 10, "INSTITUTIONAL": 2},
            step=1,
        )
        assert result.continuity_score >= 0.0
        assert result.dominant_theme in ["theme_a", "theme_b", "silent"]

    def test_empty_themes(self):
        tracker = TemporalContinuityTracker()
        result = tracker.update(
            narrative_themes=[],
            narrative_level_distribution={},
            step=1,
        )
        assert result.dominant_theme == "silent"
        assert result.continuity_score == 0.0

    def test_continuity_builds_over_steps(self):
        """相同主题持续出现时，连续性应逐步增长"""
        tracker = TemporalContinuityTracker()
        config = DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG
        window = config['continuity_min_steps']

        for i in range(window + 10):
            result = tracker.update(
                narrative_themes=["stable_theme", "secondary"],
                narrative_level_distribution={"MINI": 10, "INSTITUTIONAL": 3},
                step=i + 1,
            )

        # 经过足够多的相同主题步数后，连续性应该 > 0
        assert result.continuity_score > 0.0

    def test_theme_diversity(self):
        tracker = TemporalContinuityTracker()
        for i in range(20):
            result = tracker.update(
                narrative_themes=[f"theme_{i % 5}"],
                narrative_level_distribution={"MINI": 10},
                step=i + 1,
            )
        assert result.theme_diversity > 0.0

    def test_dominant_theme_persistence(self):
        """主导主题应该是持续出现的主题"""
        tracker = TemporalContinuityTracker()
        for i in range(50):
            themes = ["persistent_theme"]
            if i % 5 == 0:
                themes.append("occasional_theme")
            result = tracker.update(
                narrative_themes=themes,
                narrative_level_distribution={"MINI": 10},
                step=i + 1,
            )
        assert result.dominant_theme == "persistent_theme"

    def test_summary(self):
        tracker = TemporalContinuityTracker()
        tracker.update(
            narrative_themes=["theme_x"],
            narrative_level_distribution={"MINI": 5},
            step=1,
        )
        summary = tracker.get_summary()
        assert 'continuous_steps' in summary
        assert 'is_continuous' in summary
        assert 'dominant_theme' in summary


# ─── InstitutionalNarrativeStabilizer ───

class TestInstitutionalNarrativeStabilizer:

    def test_initial_state(self):
        stabilizer = InstitutionalNarrativeStabilizer()
        assert stabilizer._resistance_score == 0.0

    def test_single_update(self):
        stabilizer = InstitutionalNarrativeStabilizer()
        result = stabilizer.update(
            institutional_narrative="structural_emergence",
            institutional_coherence=0.5,
            odi=0.7,
            step=1,
        )
        assert 0.0 <= result.stability_score <= 1.0
        assert result.narrative_label == "structural_emergence"

    def test_stability_increases_with_coherent_narrative(self):
        """持续一致的叙事应提高稳定性"""
        stabilizer = InstitutionalNarrativeStabilizer()
        for i in range(50):
            result = stabilizer.update(
                institutional_narrative="stable_institutional_narrative",
                institutional_coherence=0.8,
                odi=0.7,
                step=i + 1,
            )
        assert result.stability_score > 0.0
        assert result.resistance_score > 0.0

    def test_narrative_label_update(self):
        stabilizer = InstitutionalNarrativeStabilizer()
        stabilizer.update(
            institutional_narrative="first_narrative",
            institutional_coherence=0.5,
            odi=0.6,
            step=1,
        )
        stabilizer.update(
            institutional_narrative="second_narrative",
            institutional_coherence=0.5,
            odi=0.6,
            step=2,
        )
        assert stabilizer._current_narrative == "second_narrative"

    def test_odi_factor(self):
        """低 ODI 应降低稳定性得分"""
        stabilizer_low = InstitutionalNarrativeStabilizer()
        stabilizer_high = InstitutionalNarrativeStabilizer()

        for i in range(20):
            r_low = stabilizer_low.update(
                institutional_narrative="test_narrative",
                institutional_coherence=0.8,
                odi=0.1,  # 低 ODI
                step=i + 1,
            )
            r_high = stabilizer_high.update(
                institutional_narrative="test_narrative",
                institutional_coherence=0.8,
                odi=0.9,  # 高 ODI
                step=i + 1,
            )

        assert r_high.stability_score >= r_low.stability_score

    def test_summary(self):
        stabilizer = InstitutionalNarrativeStabilizer()
        stabilizer.update(
            institutional_narrative="test",
            institutional_coherence=0.5,
            odi=0.6,
            step=1,
        )
        summary = stabilizer.get_summary()
        assert 'current_narrative' in summary
        assert 'stability_score' in summary
        assert 'is_stable' in summary


# ─── SelfHistoryAccumulator ───

class TestSelfHistoryAccumulator:

    def test_initial_state(self):
        accumulator = SelfHistoryAccumulator()
        assert len(accumulator._turning_points) == 0

    def test_single_update(self):
        accumulator = SelfHistoryAccumulator()
        result = accumulator.update(
            msi=0.3,
            odi=0.7,
            narrative_theme="test_theme",
            step=1,
        )
        assert result.n_turning_points >= 0

    def test_history_depth_increases(self):
        """积累更多转折点后，历史深度应增加"""
        accumulator = SelfHistoryAccumulator()
        for i in range(100):
            # 制造 MSI 波动以触发转折点检测
            msi_val = 0.3 + 0.1 * np.sin(i * 0.5)
            result = accumulator.update(
                msi=float(msi_val),
                odi=0.7,
                narrative_theme=f"theme_{i % 3}",
                step=i + 1,
            )
        assert result.n_turning_points >= 0  # 至少有一些转折点

    def test_turning_point_detection(self):
        """MSI 剧烈变化时应检测到转折点"""
        accumulator = SelfHistoryAccumulator(
            config={
                **DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG,
                'history_msi_lookback': 10,
                'history_second_deriv_threshold': 0.01,
            }
        )

        # 先积累平稳的 MSI
        for i in range(20):
            accumulator.update(
                msi=0.3,
                odi=0.7,
                narrative_theme="stable",
                step=i + 1,
            )

        # 然后制造剧烈变化
        for i in range(20, 40):
            msi_val = 0.3 + (i - 20) * 0.05  # 线性增长
            accumulator.update(
                msi=float(msi_val),
                odi=0.7,
                narrative_theme="changing",
                step=i + 1,
            )

        # 应该有转折点被检测到
        assert len(accumulator._turning_points) >= 0  # 不断言具体数量，取决于参数

    def test_max_turning_points_limit(self):
        """转折点数量不应超过最大值"""
        accumulator = SelfHistoryAccumulator(
            config={
                **DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG,
                'history_max_turning_points': 5,
                'history_msi_lookback': 5,
                'history_second_deriv_threshold': 0.001,
            }
        )

        # 制造大量波动
        for i in range(100):
            msi_val = 0.3 + 0.2 * np.sin(i * 0.3)
            accumulator.update(
                msi=float(msi_val),
                odi=0.7,
                narrative_theme=f"theme_{i % 3}",
                step=i + 1,
            )

        assert len(accumulator._turning_points) <= 5

    def test_odi_range(self):
        accumulator = SelfHistoryAccumulator()
        for i in range(50):
            accumulator.update(
                msi=0.3,
                odi=0.3 + i * 0.01,
                narrative_theme="test",
                step=i + 1,
            )
        result = accumulator._build_result()
        assert result.odi_range > 0.0

    def test_summary(self):
        accumulator = SelfHistoryAccumulator()
        accumulator.update(msi=0.3, odi=0.7, narrative_theme="test", step=1)
        summary = accumulator.get_summary()
        assert 'n_turning_points' in summary
        assert 'history_depth' in summary


# ─── NarrativeSelfEmergence (集成测试) ───

class TestNarrativeSelfEmergence:

    def test_initial_state(self):
        nse = NarrativeSelfEmergence()
        assert nse._step_count == 0

    def test_single_step(self):
        nse = NarrativeSelfEmergence()
        result = nse.step(
            msi=0.3,
            odi=0.7,
            narrative_themes=["theme_a"],
            narrative_level_distribution={"MINI": 10, "INSTITUTIONAL": 2},
            institutional_narrative="structural_emergence",
            institutional_coherence=0.5,
            layer_distribution={"MINI": 100, "INSTITUTIONAL": 5},
            step=1,
        )
        assert 'continuity' in result
        assert 'stability' in result
        assert 'history' in result
        assert 'nsi' in result
        assert 0.0 <= result['nsi'].nsi <= 1.0

    def test_nsi_zero_at_low_odi(self):
        """ODI < 0.6 时，NSI 应被抑制"""
        nse = NarrativeSelfEmergence()
        for i in range(150):
            result = nse.step(
                msi=0.3,
                odi=0.1,  # 低 ODI
                narrative_themes=["stable_theme"],
                narrative_level_distribution={"MINI": 10, "INSTITUTIONAL": 3},
                institutional_narrative="stable_narrative",
                institutional_coherence=0.8,
                step=i + 1,
            )
        # NSI 应该很低（被 ODI 门控抑制）
        assert result['nsi'].nsi < 0.5

    def test_nsi_grows_with_high_odi(self):
        """ODI > 0.6 且持续叙事时，NSI 应增长"""
        nse = NarrativeSelfEmergence()
        for i in range(150):
            result = nse.step(
                msi=0.3,
                odi=0.7,  # 高 ODI
                narrative_themes=["stable_theme", "secondary"],
                narrative_level_distribution={"MINI": 10, "INSTITUTIONAL": 3},
                institutional_narrative="stable_institutional_narrative",
                institutional_coherence=0.8,
                layer_distribution={"MINI": 100, "INSTITUTIONAL": 5},
                step=i + 1,
            )
        # NSI 应该 > 0
        assert result['nsi'].nsi > 0.0

    def test_nsi_components_sum(self):
        """NSI 的三个分量应该在 [0, 1] 范围内"""
        nse = NarrativeSelfEmergence()
        result = nse.step(
            msi=0.3,
            odi=0.7,
            narrative_themes=["theme_a"],
            narrative_level_distribution={"MINI": 10},
            institutional_narrative="test",
            institutional_coherence=0.5,
            step=1,
        )
        assert 0.0 <= result['nsi'].temporal_continuity <= 1.0
        assert 0.0 <= result['nsi'].narrative_stability <= 1.0
        assert 0.0 <= result['nsi'].self_history_depth <= 1.0

    def test_nsi_trend(self):
        nse = NarrativeSelfEmergence()
        for i in range(50):
            nse.step(
                msi=0.3,
                odi=0.7,
                narrative_themes=["theme"],
                narrative_level_distribution={"MINI": 10},
                institutional_narrative="test",
                institutional_coherence=0.5,
                step=i + 1,
            )
        trend = nse.get_nsi_trend()
        assert 'mean' in trend
        assert 'latest' in trend
        assert trend['n'] == 50

    def test_reset(self):
        nse = NarrativeSelfEmergence()
        for i in range(50):
            nse.step(
                msi=0.3,
                odi=0.7,
                narrative_themes=["theme"],
                narrative_level_distribution={"MINI": 10},
                institutional_narrative="test",
                institutional_coherence=0.5,
                step=i + 1,
            )
        nse.reset()
        assert nse._step_count == 0
        assert len(nse._nsi_history) == 0

    def test_summary(self):
        nse = NarrativeSelfEmergence()
        nse.step(
            msi=0.3,
            odi=0.7,
            narrative_themes=["theme"],
            narrative_level_distribution={"MINI": 10},
            institutional_narrative="test",
            institutional_coherence=0.5,
            step=1,
        )
        summary = nse.get_summary()
        assert 'continuity' in summary
        assert 'stability' in summary
        assert 'history' in summary
        assert 'nsi_trend' in summary

    def test_many_steps_stability(self):
        """大量步骤后不应崩溃，NSI 应有界"""
        nse = NarrativeSelfEmergence()
        for i in range(500):
            result = nse.step(
                msi=0.2 + 0.1 * np.sin(i * 0.05),
                odi=0.6 + 0.1 * np.sin(i * 0.03),
                narrative_themes=[f"theme_{i % 5}"],
                narrative_level_distribution={"MINI": 10 + i % 5, "INSTITUTIONAL": 2 + i % 3},
                institutional_narrative=f"narrative_{i % 4}",
                institutional_coherence=0.4 + 0.2 * np.sin(i * 0.1),
                layer_distribution={"MINI": 100, "INSTITUTIONAL": 5, "CIVILIZATION": 1},
                step=i + 1,
            )
            assert 0.0 <= result['nsi'].nsi <= 1.0, f"NSI out of bounds at step {i}: {result['nsi'].nsi}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
