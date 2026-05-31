"""
tests/test_cross_scale_coupling.py — CrossScaleCoupling 单元测试

Phase 4 P1 新组件测试
"""

import pytest
import torch
from engine.cross_scale_coupling import (
    CrossScaleCoupling,
    TopDownConstraint,
    BottomUpEmergenceEvaluator,
    ScaleBridgingNarrator,
    DEFAULT_CROSS_SCALE_COUPLING_CONFIG,
    EmergenceQuality,
    CouplingDirection,
    TopDownConstraintState,
    EmergenceQualityResult,
    ScaleBridgingNarrative,
    CrossScaleCoherenceResult,
)


# ─── TopDownConstraint 测试 ───

class TestTopDownConstraint:
    """Top-Down 约束单元测试"""

    def test_no_constraints_when_no_high_levels(self):
        """没有高层级时不应产生约束"""
        tdc = TopDownConstraint()
        states = tdc.update({
            'MINI': {'stability_score': 0.8, 'odi': 0.5},
        })
        assert len([s for s in states.values() if s.is_active]) == 0

    def test_constraint_generated_from_stable_high_level(self):
        """稳定的高层级应产生约束"""
        tdc = TopDownConstraint()
        # 跳过响应延迟
        for _ in range(20):
            tdc.update({
                'MINI': {'stability_score': 0.3, 'odi': 0.2},
                'INSTITUTIONAL': {'stability_score': 0.8, 'odi': 0.5, 'structure_vector': torch.randn(128)},
            }, bias_field=torch.randn(128))

        constraints = tdc.get_active_constraints()
        assert len(constraints) > 0
        assert any(c['source'] == 'INSTITUTIONAL' for c in constraints)

    def test_constraint_strength_bounded(self):
        """约束强度应在范围内"""
        tdc = TopDownConstraint()
        for _ in range(20):
            tdc.update({
                'MINI': {'stability_score': 0.3},
                'CIVILIZATION': {'stability_score': 1.0, 'structure_vector': torch.randn(128)},
            }, bias_field=torch.randn(128))

        for c in tdc.get_active_constraints():
            assert c['strength'] <= DEFAULT_CROSS_SCALE_COUPLING_CONFIG['topdown_max_constraint_strength']
            assert c['strength'] >= 0

    def test_constraint_decay(self):
        """约束应随时间衰减"""
        tdc = TopDownConstraint()
        for _ in range(20):
            tdc.update({
                'MINI': {'stability_score': 0.3},
                'INSTITUTIONAL': {'stability_score': 0.9, 'structure_vector': torch.randn(128)},
            }, bias_field=torch.randn(128))

        # 停止更新高层级，观察衰减
        initial_strength = tdc.get_active_constraints()[0]['strength'] if tdc.get_active_constraints() else 0
        for _ in range(50):
            tdc.update({'MINI': {'stability_score': 0.1}})

        final_strength = tdc.get_active_constraints()[0]['strength'] if tdc.get_active_constraints() else 0
        assert final_strength < initial_strength

    def test_response_delay(self):
        """响应延迟内不应施加约束"""
        tdc = TopDownConstraint({'topdown_response_delay': 10})
        for step in range(10):
            states = tdc.update({
                'MINI': {'stability_score': 0.3},
                'INSTITUTIONAL': {'stability_score': 0.9, 'structure_vector': torch.randn(128)},
            }, bias_field=torch.randn(128))
            active = [s for s in states.values() if s.is_active]
            assert len(active) == 0, f"Step {step}: should not be active during delay"


# ─── BottomUpEmergenceEvaluator 测试 ───

class TestBottomUpEmergenceEvaluator:
    """Bottom-Up 涌现质量评估单元测试"""

    def test_strong_emergence(self):
        """高质量涌现应判定为 STRONG"""
        bue = BottomUpEmergenceEvaluator()
        for _ in range(60):
            result = bue.evaluate(
                emergence_id='test_strong',
                source_level='MINI',
                target_level='INSTITUTIONAL',
                stability_score=0.9,
                odi=0.8,
            )
        assert result.quality == EmergenceQuality.STRONG
        assert result.is_surviving

    def test_poor_emergence(self):
        """低质量涌现应判定为 POOR"""
        bue = BottomUpEmergenceEvaluator()
        result = bue.evaluate(
            emergence_id='test_poor',
            source_level='MINI',
            target_level='INSTITUTIONAL',
            stability_score=0.2,
            odi=0.1,
        )
        assert result.quality == EmergenceQuality.POOR
        assert not result.is_surviving

    def test_survival_requires_min_steps(self):
        """存活需要最小稳定步数"""
        bue = BottomUpEmergenceEvaluator({'emergence_min_stability_steps': 50})
        # 50 步高质量
        for _ in range(50):
            result = bue.evaluate(
                emergence_id='test_survival',
                source_level='MINI',
                target_level='INSTITUTIONAL',
                stability_score=0.8,
                odi=0.6,
            )
        assert result.is_surviving

        # 但只有 30 步
        bue2 = BottomUpEmergenceEvaluator({'emergence_min_stability_steps': 50})
        for _ in range(30):
            result = bue2.evaluate(
                emergence_id='test_short',
                source_level='MINI',
                target_level='INSTITUTIONAL',
                stability_score=0.9,
                odi=0.8,
            )
        assert not result.is_surviving

    def test_survival_rate_tracking(self):
        """存活率应正确统计"""
        bue = BottomUpEmergenceEvaluator({'emergence_min_stability_steps': 5})
        # 10 个高质量涌现 — 每个评估 10 次以累积稳定步数
        for i in range(10):
            for _ in range(10):
                bue.evaluate(f'good_{i}', 'MINI', 'INSTITUTIONAL', 0.9, 0.8)
        # 10 个低质量涌现
        for i in range(10):
            for _ in range(10):
                bue.evaluate(f'bad_{i}', 'MINI', 'INSTITUTIONAL', 0.1, 0.1)

        stats = bue.get_candidate_stats()
        assert stats['n_candidates'] == 20
        # 10 个 good 应该存活，10 个 bad 不应该
        assert stats['n_surviving'] == 10
        assert stats['survival_rate'] == 0.5


# ─── ScaleBridgingNarrator 测试 ───

class TestScaleBridgingNarrator:
    """跨尺度叙事桥梁单元测试"""

    def test_coherent_narratives(self):
        """相干叙事应有高相干度"""
        sbn = ScaleBridgingNarrator()
        result = sbn.update(
            mini_narrative='structural_coupling',
            institutional_narrative='structural_coupling',
            civilization_narrative='structural_coupling',
        )
        assert result.coherence > 0.8
        assert result.is_coherent

    def test_incoherent_narratives(self):
        """不相关叙事应有低相干度"""
        sbn = ScaleBridgingNarrator()
        result = sbn.update(
            mini_narrative='emergence',
            institutional_narrative='stability',
            civilization_narrative='decay',
        )
        assert result.coherence < 0.5

    def test_integration_progress(self):
        """整合进度应随相干叙事增加"""
        sbn = ScaleBridgingNarrator({'narrative_integration_rate': 0.1})
        for _ in range(20):
            sbn.update(
                mini_narrative='common_theme',
                institutional_narrative='common_theme',
                civilization_narrative='common_theme',
            )
        status = sbn.get_integration_status()
        assert status['integration_progress'] > 0.5

    def test_integration_decreases_on_incoherence(self):
        """不相关叙事应降低整合进度"""
        sbn = ScaleBridgingNarrator({'narrative_integration_rate': 0.1})
        # 先建立进度
        for _ in range(20):
            sbn.update('common', 'common', 'common')
        progress_before = sbn.get_integration_status()['integration_progress']

        # 然后不相关
        for _ in range(20):
            sbn.update('emergence', 'stability', 'decay')

        progress_after = sbn.get_integration_status()['integration_progress']
        assert progress_after < progress_before


# ─── CrossScaleCoupling 集成测试 ───

class TestCrossScaleCoupling:
    """跨尺度耦合器集成测试"""

    def test_full_step(self):
        """完整一步应返回所有结果"""
        cc = CrossScaleCoupling()
        result = cc.step(
            level_states={
                'MINI': {'stability_score': 0.6, 'odi': 0.4},
                'INSTITUTIONAL': {'stability_score': 0.5, 'odi': 0.3},
                'CIVILIZATION': {'stability_score': 0.3, 'odi': 0.2},
            },
            narrative_labels={
                'MINI': 'structural',
                'INSTITUTIONAL': 'structural',
                'CIVILIZATION': 'structural',
            },
        )

        assert 'top_down_constraints' in result
        assert 'emergence_results' in result
        assert 'narrative_bridge' in result
        assert 'csci' in result
        assert result['csci'].csci >= 0
        assert result['csci'].csci <= 1

    def test_csci_with_emergence(self):
        """有涌现事件时 CSCI 应正确计算"""
        cc = CrossScaleCoupling()
        result = cc.step(
            level_states={
                'MINI': {'stability_score': 0.7, 'odi': 0.5, 'structure_vector': torch.randn(128)},
                'INSTITUTIONAL': {'stability_score': 0.6, 'odi': 0.4, 'structure_vector': torch.randn(128)},
            },
            narrative_labels={'MINI': 'test', 'INSTITUTIONAL': 'test'},
            emergence_events=[{
                'emergence_id': 'e1',
                'source_level': 'MINI',
                'target_level': 'INSTITUTIONAL',
                'stability_score': 0.8,
                'odi': 0.5,
                'structure_vector': torch.randn(128),
            }],
        )

        assert len(result['emergence_results']) == 1
        assert result['emergence_results'][0].source_level == 'MINI'

    def test_csci_trend(self):
        """CSCI 趋势应正确追踪"""
        cc = CrossScaleCoupling()
        for i in range(50):
            cc.step(
                level_states={
                    'MINI': {'stability_score': 0.5 + 0.01 * i},
                    'INSTITUTIONAL': {'stability_score': 0.5},
                    'CIVILIZATION': {'stability_score': 0.3},
                },
                narrative_labels={'MINI': 'theme', 'INSTITUTIONAL': 'theme', 'CIVILIZATION': 'theme'},
            )

        trend = cc.get_csci_trend()
        assert trend['n'] == 50
        assert 0 <= trend['mean'] <= 1

    def test_reset(self):
        """重置应清空所有状态"""
        cc = CrossScaleCoupling()
        for _ in range(20):
            cc.step(
                level_states={'MINI': {'stability_score': 0.5}},
                narrative_labels={'MINI': 'test'},
            )

        cc.reset()
        summary = cc.get_summary()
        assert summary['step'] == 0
        assert summary['csci_trend']['n'] == 0

    def test_topdown_with_bias_field(self):
        """有偏置场时 Top-Down 应生成约束向量"""
        tdc = TopDownConstraint({'topdown_response_delay': 0})
        bias = torch.randn(128)
        vec = torch.randn(128)
        states = tdc.update({
            'MINI': {'stability_score': 0.3},
            'INSTITUTIONAL': {'stability_score': 0.8, 'structure_vector': vec},
        }, bias_field=bias)

        for s in states.values():
            if s.is_active:
                assert s.constraint_vector is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
