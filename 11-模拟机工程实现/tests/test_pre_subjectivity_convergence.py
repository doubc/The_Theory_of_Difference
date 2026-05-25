"""
tests/test_pre_subjectivity_convergence.py — 前主体态收束判定测试

覆盖：
1. 全部条件满足 → converged
2. 六阈值未达标 → not converged
3. 耦合强度不足 → not converged
4. 稳定性不足 → not converged
5. 语义防火墙检测
6. 历史记录和摘要
7. reset 功能
8. 语义防火墙违规检测
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.pre_subjectivity_convergence import (
    PreSubjectivityConvergence, ConvergenceResult,
    CouplingStatus, SemanticFirewallResult,
    SEMANTIC_FIREWALL_FORBIDDEN, SEMANTIC_FIREWALL_ALLOWED,
)


class TestPreSubjectivityConvergence:

    def _make_converged_params(self):
        """生成满足所有条件的参数"""
        return {
            'threshold_params': {
                'active_exchanges': 8,
                'total_boundary_edges': 10,
                'rebuild_success_count': 8,
                'perturbation_count': 10,
                'bias_recursion_depth': 5.0,
                'replicated_pattern': torch.tensor([1.0, 0.0, 1.0, 0.0]),
                'original_pattern': torch.tensor([1.0, 0.0, 1.0, 0.0]),
                'variant_continuation_probs': {'v1': 0.9, 'v2': 0.1},
                'component_contributions': {'c1': 10.0, 'c2': 1.0},
            },
            'coupling_matrix': {
                'interface_regulation': {
                    'self_sustaining': 0.5, 'retention': 0.5,
                    'replication': 0.5, 'selection': 0.5,
                    'functional_differentiation': 0.5,
                },
                'self_sustaining': {
                    'retention': 0.5, 'replication': 0.5,
                    'selection': 0.5, 'functional_differentiation': 0.5,
                },
                'retention': {
                    'replication': 0.5, 'selection': 0.5,
                    'functional_differentiation': 0.5,
                },
                'replication': {
                    'selection': 0.5, 'functional_differentiation': 0.5,
                },
                'selection': {
                    'functional_differentiation': 0.5,
                },
            },
            'structure_state': torch.tensor([1.0, 0.0, 1.0, 0.0]),
            'structure_fn': lambda s: True,  # 结构始终保持
            'field_names': ['boundary', 'retention', 'selection'],
        }

    def test_all_conditions_met(self):
        """所有条件满足 → converged = True"""
        psc = PreSubjectivityConvergence()
        result = psc.evaluate(**self._make_converged_params())
        assert result.converged is True
        assert result.six_thresholds_met is True
        assert result.coupling_strength_met is True
        assert result.stability_met is True
        assert result.semantic_firewall_passed is True
        assert result.all_conditions_met is True

    def test_thresholds_not_met(self):
        """六阈值未达标 → not converged"""
        params = self._make_converged_params()
        params['threshold_params'] = {}  # 空参数 → 阈值都不达标
        psc = PreSubjectivityConvergence()
        result = psc.evaluate(**params)
        assert result.converged is False
        assert result.six_thresholds_met is False

    def test_coupling_not_met(self):
        """耦合强度不足 → not converged"""
        params = self._make_converged_params()
        params['coupling_matrix'] = None  # 无耦合矩阵
        psc = PreSubjectivityConvergence()
        result = psc.evaluate(**params)
        assert result.converged is False
        assert result.coupling_strength_met is False

    def test_coupling_partial(self):
        """部分机制对耦合 → not converged（需要全部耦合）"""
        params = self._make_converged_params()
        # 只提供一个机制对的耦合
        params['coupling_matrix'] = {
            'interface_regulation': {'self_sustaining': 0.5},
            'self_sustaining': {},
            'retention': {},
            'replication': {},
            'selection': {},
            'functional_differentiation': {},
        }
        psc = PreSubjectivityConvergence()
        result = psc.evaluate(**params)
        assert result.coupling_strength_met is False
        assert result.n_coupled_pairs < 15  # C(6,2) = 15

    def test_stability_not_met(self):
        """稳定性不足 → not converged"""
        params = self._make_converged_params()
        params['structure_fn'] = lambda s: False  # 结构始终不保持
        psc = PreSubjectivityConvergence()
        result = psc.evaluate(**params)
        assert result.converged is False
        assert result.stability_met is False
        assert result.stability_score == 0.0

    def test_stability_partial(self):
        """部分稳定性 → 取决于是否超过阈值"""
        params = self._make_converged_params()
        call_count = {'n': 0}
        def sometimes_stable(s):
            call_count['n'] += 1
            return call_count['n'] <= 2  # 5次中只有2次成功 = 0.4 < 0.5
        params['structure_fn'] = sometimes_stable
        psc = PreSubjectivityConvergence()
        result = psc.evaluate(**params)
        assert result.stability_met is False

    def test_semantic_firewall_passed(self):
        """语义防火墙通过 → 字段名不包含禁止词汇"""
        psc = PreSubjectivityConvergence()
        result = psc._check_semantic_firewall(['boundary', 'retention', 'selection'])
        assert result.passed is True
        assert len(result.violations) == 0

    def test_semantic_firewall_failed_identity(self):
        """字段名包含'identity' → 防火墙违规"""
        psc = PreSubjectivityConvergence()
        result = psc._check_semantic_firewall(['identity_boundary'])
        assert result.passed is False
        assert any('identity_boundary' in v for v in result.violations)

    def test_semantic_firewall_failed_will(self):
        """字段名包含'will' → 防火墙违规"""
        psc = PreSubjectivityConvergence()
        result = psc._check_semantic_firewall(['volition_field'])
        assert result.passed is False

    def test_semantic_firewall_failed_meaning(self):
        """字段名包含'meaning' → 防火墙违规"""
        psc = PreSubjectivityConvergence()
        result = psc._check_semantic_firewall(['meaning_assignment'])
        assert result.passed is False

    def test_semantic_firewall_multiple_violations(self):
        """多个违规 → 全部列出"""
        psc = PreSubjectivityConvergence()
        result = psc._check_semantic_firewall(['identity_field', 'will_power', 'boundary'])
        assert result.passed is False
        assert len(result.violations) == 2  # identity + will

    def test_semantic_firewall_empty_fields(self):
        """空字段列表 → 通过"""
        psc = PreSubjectivityConvergence()
        result = psc._check_semantic_firewall([])
        assert result.passed is True
        assert result.n_checked == 0

    def test_allowed_names_pass(self):
        """允许的结构名称通过防火墙"""
        psc = PreSubjectivityConvergence()
        allowed = ['boundary', 'self_sustaining', 'retention',
                    'replication', 'selection', 'function']
        result = psc._check_semantic_firewall(allowed)
        assert result.passed is True

    def test_history_tracking(self):
        """检测历史正确记录"""
        psc = PreSubjectivityConvergence()
        psc.evaluate()
        psc.evaluate()
        assert len(psc._convergence_history) == 2

    def test_has_converged_property(self):
        """has_converged 反映最近一次结果"""
        psc = PreSubjectivityConvergence()
        assert psc.has_converged is False

        psc.evaluate(**self._make_converged_params())
        assert psc.has_converged is True

    def test_convergence_step(self):
        """convergence_step 返回首次收束的时间戳"""
        psc = PreSubjectivityConvergence()
        assert psc.convergence_step is None

        # 第一次不收束
        psc.evaluate(timestamp=1)
        assert psc.convergence_step is None

        # 第二次收束
        psc.evaluate(**self._make_converged_params(), timestamp=2)
        assert psc.convergence_step == 2

    def test_reset(self):
        """reset 清除所有状态"""
        psc = PreSubjectivityConvergence()
        psc.evaluate()
        psc.evaluate()
        psc.reset()
        assert len(psc._convergence_history) == 0
        assert psc._step_count == 0

    def test_coupling_matrix_symmetric(self):
        """耦合矩阵只需要上三角或下三角，另一方向自动取"""
        psc = PreSubjectivityConvergence()
        # 只提供 ma→mb, 不提供 mb→ma
        matrix = {
            'interface_regulation': {'self_sustaining': 0.5},
            'self_sustaining': {},
            'retention': {},
            'replication': {},
            'selection': {},
            'functional_differentiation': {},
        }
        met, n_coupled, min_c = psc._evaluate_coupling(matrix)
        # 应该能找到 1 个耦合对
        assert n_coupled == 1

    def test_convergence_result_repr(self):
        """ConvergenceResult 的字符串表示"""
        result = ConvergenceResult(converged=True, n_coupled_pairs=15, stability_score=0.8)
        repr_str = repr(result)
        assert 'CONVERGED' in repr_str

        result2 = ConvergenceResult(converged=False, six_thresholds_met=False)
        repr_str2 = repr(result2)
        assert 'NOT_CONVERGED' in repr_str2
        assert 'thresholds' in repr_str2

    def test_all_conditions_met_property(self):
        """all_conditions_met 综合所有条件"""
        result = ConvergenceResult(
            six_thresholds_met=True,
            coupling_strength_met=True,
            stability_met=True,
            semantic_firewall_passed=True,
        )
        assert result.all_conditions_met is True

        result2 = ConvergenceResult(
            six_thresholds_met=True,
            coupling_strength_met=True,
            stability_met=True,
            semantic_firewall_passed=False,  # 防火墙失败
        )
        assert result2.all_conditions_met is False

    def test_get_history_summary(self):
        """历史摘要正确"""
        psc = PreSubjectivityConvergence()
        psc.evaluate(**self._make_converged_params())
        psc.evaluate(**self._make_converged_params())
        psc.evaluate()  # 不收束

        summary = psc.get_history_summary()
        assert summary['n_evaluations'] == 3
        assert summary['n_converged'] == 2
        assert summary['first_convergence_step'] == 1

    def test_timestamp_auto_increment(self):
        """时间戳自动递增"""
        psc = PreSubjectivityConvergence()
        r1 = psc.evaluate()
        r2 = psc.evaluate()
        assert r1.timestamp == 1
        assert r2.timestamp == 2

    def test_stability_exception_handling(self):
        """结构函数抛出异常 → 视为不稳定"""
        params = self._make_converged_params()
        def bad_fn(s):
            raise ValueError("test error")
        params['structure_fn'] = bad_fn
        psc = PreSubjectivityConvergence()
        result = psc.evaluate(**params)
        assert result.stability_met is False
        assert result.stability_score == 0.0
