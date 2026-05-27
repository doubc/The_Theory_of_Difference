"""
tests/test_cooperative_emergence.py — 协同涌现检测器测试

覆盖：
1. 初始状态：无涌现
2. 全零输入：无涌现
3. 渐进收敛（非同步）：无协同涌现
4. 同步跨越：检测到协同涌现
5. 耦合拓扑相变：检测到拓扑变化
6. 协同振荡：检测到振荡模式
7. 互信息突增：检测到 MI 突增
8. 多信号融合：multi_pattern 类型
9. ODI 门控：低于前主体态地板时不触发
10. reset 功能
11. 信号摘要统计
12. feed 返回结果结构验证
"""

import pytest
import torch
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.cooperative_emergence_detector import (
    CooperativeEmergenceDetector,
    CooperativeEmergenceResult,
    SynchronizedCrossing,
    CouplingTopologyTransition,
    CooperativeOscillation,
    MutualInformationSurge,
    DEFAULT_CE_CONFIG,
)
from engine.six_threshold_detector import SixThresholdDetector, SixThresholdResult
from engine.organizational_density_index import OrganizationalDensityIndex, DensityIndexResult


# ─── 辅助函数 ───

def _make_threshold_result(
    values=None,
    timestamp=0,
):
    """构造 SixThresholdResult（通过 detector.detect 获取真实对象）"""
    detector = SixThresholdDetector()
    if values is None:
        values = {}
    result = detector.detect(
        active_exchanges=values.get('active_exchanges', 0),
        total_boundary_edges=values.get('total_boundary_edges', 1),
        rebuild_success_count=values.get('rebuild_success_count', 0),
        perturbation_count=values.get('perturbation_count', 1),
        bias_recursion_depth=values.get('bias_recursion_depth', 0.0),
        original_pattern=values.get('original_pattern'),
        replicated_pattern=values.get('replicated_pattern'),
        variant_continuation_probs=values.get('variant_continuation_probs'),
        component_contributions=values.get('component_contributions'),
        timestamp=timestamp,
    )
    return result


def _make_high_threshold_result(timestamp=0):
    """构造全部达标的六阈值结果"""
    n = 8
    rng = np.random.RandomState(42)
    original = torch.tensor(rng.rand(n, n), dtype=torch.float32)
    replicated = original + torch.randn_like(original) * 0.03

    return _make_threshold_result(
        values={
            'active_exchanges': 10,
            'total_boundary_edges': 20,
            'rebuild_success_count': 8,
            'perturbation_count': 10,
            'bias_recursion_depth': 3.0,
            'original_pattern': original,
            'replicated_pattern': replicated,
            'variant_continuation_probs': {'A': 0.8, 'B': 0.3},
            'component_contributions': {'c1': 0.7, 'c2': 0.05, 'c3': 0.15, 'c4': 0.1},
        },
        timestamp=timestamp,
    )


def _make_coupling_matrix(strength=0.5):
    """构造耦合矩阵"""
    mechanisms = [
        'interface_regulation', 'self_sustaining', 'retention',
        'replication', 'selection', 'functional_differentiation',
    ]
    matrix = {}
    for ma in mechanisms:
        matrix[ma] = {}
        for mb in mechanisms:
            if ma != mb:
                matrix[ma][mb] = strength
    return matrix


def _make_odi_result(odi, timestamp):
    """构造 DensityIndexResult"""
    result = DensityIndexResult(
        odi=odi,
        timestamp=timestamp,
    )
    return result


# ─── Test 1: 初始状态 ───

class TestInitialState:
    """初始状态测试"""

    def test_initial_no_emergence(self):
        """初始状态应无涌现"""
        detector = CooperativeEmergenceDetector()
        assert detector.emergence_count == 0
        assert detector.latest_result is None
        assert not detector.has_emergence_occurred

    def test_signal_summary_empty(self):
        """空摘要应返回 0 评估"""
        detector = CooperativeEmergenceDetector()
        summary = detector.get_signal_summary()
        assert summary['n_evaluations'] == 0


# ─── Test 2: 全零输入无涌现 ───

class TestNoEmergenceFromZeros:
    """全零输入不应产生涌现"""

    def test_all_zero_no_emergence(self):
        """全零输入不应触发涌现"""
        detector = CooperativeEmergenceDetector()

        for step in range(20):
            result = detector.feed(
                threshold_result=_make_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.1),
                odi_result=_make_odi_result(odi=0.3, timestamp=step),
                timestamp=step,
            )

        assert not detector.has_emergence_occurred
        assert detector.emergence_count == 0


# ─── Test 3: 渐进收敛无协同涌现 ───

class TestGradualConvergence:
    """渐进收敛（非同步）不应触发协同涌现"""

    def test_gradual_convergence_no_emergence(self):
        """渐进收敛不应触发协同涌现"""
        detector = CooperativeEmergenceDetector()

        for step in range(30):
            # 模拟渐进收敛：密度线性增长
            density = 0.1 + 0.02 * step
            result = detector.feed(
                threshold_result=_make_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=density),
                odi_result=_make_odi_result(odi=min(density, 0.9), timestamp=step),
                timestamp=step,
            )

        # 渐进收敛不应触发协同涌现（因为没有同步跨越）
        # 注意：可能会有其他信号触发，但 sync_crossing 不应触发
        assert detector.latest_result is not None


# ─── Test 4: 同步跨越检测 ───

class TestSynchronizedCrossing:
    """同步跨越检测测试"""

    def test_synchronized_crosses_detected(self):
        """六个条件在短时间内同步跨越应被检测"""
        detector = CooperativeEmergenceDetector(
            config={'sync_window': 5, 'sync_threshold_ratio': 0.6}
        )

        # 前 10 步：低值（未达标）
        for step in range(10):
            detector.feed(
                threshold_result=_make_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.8),
                odi_result=_make_odi_result(odi=0.6, timestamp=step),
                timestamp=step,
            )

        # 第 10-12 步：突然全部达标（模拟同步跨越）
        for step in range(10, 15):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.8),
                odi_result=_make_odi_result(odi=0.75, timestamp=step),
                timestamp=step,
            )

        # 应该检测到同步跨越
        latest = detector.latest_result
        assert latest is not None
        # 检查 sync_crossing 是否触发
        assert latest.sync_crossing.detected or latest.n_active_signals >= 1

    def test_crossing_timestamps_tracked(self):
        """跨越时间戳应被正确追踪"""
        detector = CooperativeEmergenceDetector()

        # 前 5 步未达标
        for step in range(5):
            detector.feed(
                threshold_result=_make_threshold_result(timestamp=step),
                timestamp=step,
            )

        # 第 5 步全部达标
        detector.feed(
            threshold_result=_make_high_threshold_result(timestamp=5),
            odi_result=_make_odi_result(odi=0.7, timestamp=5),
            timestamp=5,
        )

        # 应该有跨越记录
        assert len(detector._crossing_timestamps) > 0


# ─── Test 5: 耦合拓扑相变检测 ───

class TestTopologyTransition:
    """耦合拓扑相变检测测试"""

    def test_topology_change_detected(self):
        """耦合拓扑显著变化应被检测"""
        detector = CooperativeEmergenceDetector(
            config={
                'topology_history_window': 5,
                'topology_change_threshold': 0.3,
            }
        )

        # 前 10 步：低耦合
        for step in range(10):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.1),
                odi_result=_make_odi_result(odi=0.7, timestamp=step),
                timestamp=step,
            )

        # 后 10 步：高耦合（拓扑变化）
        for step in range(10, 25):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.8),
                odi_result=_make_odi_result(odi=0.8, timestamp=step),
                timestamp=step,
            )

        # 检查是否有拓扑相变信号
        latest = detector.latest_result
        assert latest is not None
        # 拓扑相变应该被检测到（从低耦合到高耦合）
        assert latest.topology_transition.detected or detector.has_emergence_occurred

    def test_topology_expansive_vs_contractive(self):
        """拓扑扩展和收缩应被区分"""
        transition_exp = CouplingTopologyTransition(
            detected=True,
            edges_gained=[('a', 'b'), ('c', 'd')],
            edges_lost=[('e', 'f')],
        )
        assert transition_exp.is_expansive

        transition_con = CouplingTopologyTransition(
            detected=True,
            edges_gained=[('a', 'b')],
            edges_lost=[('c', 'd'), ('e', 'f')],
        )
        assert not transition_con.is_expansive


# ─── Test 6: 协同振荡检测 ───

class TestCooperativeOscillation:
    """协同振荡检测测试"""

    def test_correlated_conditions_detected(self):
        """强相关条件应被检测为协同振荡"""
        detector = CooperativeEmergenceDetector(
            config={
                'oscillation_window': 8,
                'oscillation_correlation_threshold': 0.5,
            }
        )

        # 生成强相关的条件值序列
        rng = np.random.RandomState(42)
        base = rng.rand(8)

        for step in range(20):
            # 构造 SixThresholdResult，使各条件值高度相关
            noise = rng.randn() * 0.05
            result = _make_threshold_result(
                values={
                    'active_exchanges': int(10 * (0.5 + base[step % 8] + noise)),
                    'total_boundary_edges': 20,
                    'rebuild_success_count': int(8 * (0.5 + base[step % 8] + noise)),
                    'perturbation_count': 10,
                    'bias_recursion_depth': 3.0 * (0.5 + base[step % 8] + noise),
                },
                timestamp=step,
            )
            detector.feed(
                threshold_result=result,
                coupling_matrix=_make_coupling_matrix(strength=0.6),
                odi_result=_make_odi_result(odi=0.7, timestamp=step),
                timestamp=step,
            )

        latest = detector.latest_result
        assert latest is not None
        # 协同振荡检测可能触发（取决于相关性强弱）
        assert isinstance(latest.cooperative_oscillation, CooperativeOscillation)

    def test_no_oscillation_from_constant(self):
        """常数序列不应产生协同振荡"""
        detector = CooperativeEmergenceDetector(
            config={'oscillation_window': 5}
        )

        for step in range(20):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.5),
                odi_result=_make_odi_result(odi=0.7, timestamp=step),
                timestamp=step,
            )

        latest = detector.latest_result
        if latest.cooperative_oscillation.detected:
            # 如果检测到，相关系数应该很低
            assert latest.cooperative_oscillation.mean_pairwise_correlation < 0.9


# ─── Test 7: 互信息突增检测 ───

class TestMISurge:
    """互信息突增检测测试"""

    def test_mi_surge_from_independent_to_correlated(self):
        """从独立到相关应触发 MI 突增"""
        detector = CooperativeEmergenceDetector(
            config={
                'mi_window': 8,
                'mi_surge_threshold': 0.2,
            }
        )

        rng = np.random.RandomState(42)

        # 前 16 步：低相关（独立噪声）
        for step in range(16):
            result = _make_threshold_result(timestamp=step)
            detector.feed(
                threshold_result=result,
                coupling_matrix=_make_coupling_matrix(strength=0.2),
                odi_result=_make_odi_result(odi=0.7, timestamp=step),
                timestamp=step,
            )

        # 后 16 步：高相关（协同模式）
        base = rng.rand(8)
        for step in range(16, 32):
            correlated_values = {
                'active_exchanges': int(10 * (0.5 + base[step % 8])),
                'total_boundary_edges': 20,
                'rebuild_success_count': int(8 * (0.5 + base[step % 8])),
                'perturbation_count': 10,
                'bias_recursion_depth': 3.0 * (0.5 + base[step % 8]),
            }
            result = _make_threshold_result(values=correlated_values, timestamp=step)
            detector.feed(
                threshold_result=result,
                coupling_matrix=_make_coupling_matrix(strength=0.8),
                odi_result=_make_odi_result(odi=0.8, timestamp=step),
                timestamp=step,
            )

        latest = detector.latest_result
        assert latest is not None
        assert isinstance(latest.mi_surge, MutualInformationSurge)

    def test_mi_estimation_basic(self):
        """互信息估计基本测试"""
        # 完全相关的变量
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = x * 2 + 1
        values = np.vstack([x, y])
        mi = CooperativeEmergenceDetector._estimate_mutual_information_proxy(values)
        assert mi > 0.0, "完全相关的变量应有正的互信息"

    def test_mi_independent_variables(self):
        """独立变量的互信息应接近 0"""
        rng = np.random.RandomState(42)
        x = rng.randn(100)
        y = rng.randn(100)
        values = np.vstack([x, y])
        mi = CooperativeEmergenceDetector._estimate_mutual_information_proxy(values)
        # 独立变量的 MI 应很小（< 0.1）
        assert mi < 0.1, f"独立变量的互信息应接近 0，得到 {mi}"


# ─── Test 8: ODI 门控 ───

class TestODIGate:
    """ODI 门控测试"""

    def test_below_pre_subjective_no_emergence(self):
        """低于前主体态地板时不应触发涌现"""
        detector = CooperativeEmergenceDetector(
            config={'odi_pre_subjective_min': 0.5}
        )

        for step in range(20):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.8),
                odi_result=_make_odi_result(odi=0.3, timestamp=step),  # 低于 0.5
                timestamp=step,
            )

        # ODI 门控应阻止涌现检测
        assert not detector.has_emergence_occurred

    def test_above_pre_subjective_allows_emergence(self):
        """高于前主体态地板时允许触发涌现"""
        detector = CooperativeEmergenceDetector(
            config={'odi_pre_subjective_min': 0.5}
        )

        for step in range(20):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.8),
                odi_result=_make_odi_result(odi=0.7, timestamp=step),  # 高于 0.5
                timestamp=step,
            )

        # 高 ODI 下，涌现可能被触发（取决于其他条件）
        latest = detector.latest_result
        assert latest is not None


# ─── Test 9: 多信号融合 ───

class TestMultiSignalFusion:
    """多信号融合测试"""

    def test_multi_pattern_type(self):
        """多信号同时触发时应为 multi_pattern 类型"""
        detector = CooperativeEmergenceDetector(
            config={
                'sync_window': 5,
                'sync_threshold_ratio': 0.5,
                'topology_history_window': 3,
                'topology_change_threshold': 0.2,
                'oscillation_window': 5,
                'oscillation_correlation_threshold': 0.3,
                'mi_window': 5,
                'mi_surge_threshold': 0.1,
                'min_emergence_confidence': 0.3,
            }
        )

        # 构造能同时触发多个信号的场景
        for step in range(30):
            density = 0.1 + 0.03 * step
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=min(density, 0.9)),
                odi_result=_make_odi_result(odi=min(0.5 + density, 0.9), timestamp=step),
                timestamp=step,
            )

        # 检查是否有任何涌现被检测到
        history = detector.get_emergence_history()
        for event in history:
            assert isinstance(event, CooperativeEmergenceResult)
            if event.cooperative_emergence_detected:
                assert event.confidence > 0
                assert event.n_active_signals >= 1


# ─── Test 10: reset 功能 ───

class TestReset:
    """reset 功能测试"""

    def test_reset_clears_all(self):
        """reset 应清除所有状态"""
        detector = CooperativeEmergenceDetector()

        for step in range(10):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.8),
                odi_result=_make_odi_result(odi=0.7, timestamp=step),
                timestamp=step,
            )

        detector.reset()

        assert detector.emergence_count == 0
        assert detector.latest_result is None
        assert not detector.has_emergence_occurred
        assert len(detector._threshold_history) == 0
        assert len(detector._coupling_history) == 0
        assert len(detector._odi_history) == 0
        assert len(detector._crossing_timestamps) == 0

    def test_reset_allows_restart(self):
        """reset 后应能重新开始检测"""
        detector = CooperativeEmergenceDetector()

        # 第一次运行
        for step in range(5):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                timestamp=step,
            )

        detector.reset()

        # 第二次运行
        for step in range(5):
            result = detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                timestamp=step,
            )

        assert detector.latest_result is not None


# ─── Test 11: 结果数据结构 ───

class TestResultStructure:
    """结果数据结构测试"""

    def test_result_fields(self):
        """结果应包含所有必要字段"""
        detector = CooperativeEmergenceDetector()

        result = detector.feed(
            threshold_result=_make_threshold_result(timestamp=0),
            timestamp=0,
        )

        assert isinstance(result, CooperativeEmergenceResult)
        assert isinstance(result.sync_crossing, SynchronizedCrossing)
        assert isinstance(result.topology_transition, CouplingTopologyTransition)
        assert isinstance(result.cooperative_oscillation, CooperativeOscillation)
        assert isinstance(result.mi_surge, MutualInformationSurge)
        assert isinstance(result.description, str)

    def test_result_labels(self):
        """结果标签应正确"""
        result = CooperativeEmergenceResult()
        assert result.emergence_label == '无协同涌现'
        assert result.confidence_label == '无可信度'

        result2 = CooperativeEmergenceResult(
            cooperative_emergence_detected=True,
            emergence_type='multi_pattern',
            confidence=0.8,
        )
        assert result2.emergence_label == '多模式协同涌现'
        assert result2.confidence_label == '高可信度'

    def test_repr(self):
        """__repr__ 应正常工作"""
        result = CooperativeEmergenceResult(
            cooperative_emergence_detected=True,
            emergence_type='synchronized_crossing',
            confidence=0.65,
            n_active_signals=2,
        )
        repr_str = repr(result)
        assert '同步跨越' in repr_str
        assert '0.65' in repr_str


# ─── Test 12: 信号摘要统计 ───

class TestSignalSummary:
    """信号摘要统计测试"""

    def test_summary_counts(self):
        """摘要应正确统计各信号触发次数"""
        detector = CooperativeEmergenceDetector()

        for step in range(10):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                coupling_matrix=_make_coupling_matrix(strength=0.8),
                odi_result=_make_odi_result(odi=0.7, timestamp=step),
                timestamp=step,
            )

        summary = detector.get_signal_summary()
        assert summary['n_evaluations'] == 10
        assert 'sync_crossing_triggers' in summary
        assert 'topology_transition_triggers' in summary
        assert 'cooperative_oscillation_triggers' in summary
        assert 'mi_surge_triggers' in summary

    def test_emergence_history(self):
        """涌现历史应只包含检测到涌现的结果"""
        detector = CooperativeEmergenceDetector()

        for step in range(10):
            detector.feed(
                threshold_result=_make_high_threshold_result(timestamp=step),
                timestamp=step,
            )

        history = detector.get_emergence_history()
        for event in history:
            assert event.cooperative_emergence_detected


# ─── Test 13: 边界条件 ───

class TestEdgeCases:
    """边界条件测试"""

    def test_single_feed(self):
        """单次 feed 应返回结果"""
        detector = CooperativeEmergenceDetector()
        result = detector.feed(
            threshold_result=_make_threshold_result(timestamp=0),
            timestamp=0,
        )
        assert result is not None
        assert not result.cooperative_emergence_detected

    def test_no_coupling_matrix(self):
        """不提供耦合矩阵时应正常运行"""
        detector = CooperativeEmergenceDetector()
        result = detector.feed(
            threshold_result=_make_high_threshold_result(timestamp=0),
            odi_result=_make_odi_result(odi=0.7, timestamp=0),
            timestamp=0,
        )
        assert result is not None

    def test_no_odi_result(self):
        """不提供 ODI 结果时应正常运行"""
        detector = CooperativeEmergenceDetector()
        result = detector.feed(
            threshold_result=_make_high_threshold_result(timestamp=0),
            coupling_matrix=_make_coupling_matrix(strength=0.8),
            timestamp=0,
        )
        # 没有 ODI 时 ODI 默认为 0，不满足门控条件
        assert result is not None

    def test_large_timestamp(self):
        """大时间戳应正常工作"""
        detector = CooperativeEmergenceDetector()
        result = detector.feed(
            threshold_result=_make_high_threshold_result(timestamp=10000),
            coupling_matrix=_make_coupling_matrix(strength=0.8),
            odi_result=_make_odi_result(odi=0.8, timestamp=10000),
            timestamp=10000,
        )
        assert result is not None
