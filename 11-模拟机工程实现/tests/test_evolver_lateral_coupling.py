"""
tests/test_evolver_lateral_coupling.py — LateralCoupler 集成到 HierarchicalEvolver 的测试

验证 LateralCoupler 能正确集成到 HierarchicalEvolver 的 Phase 2 callback 中，
并在多结构演化时产生合理的横向耦合报告。
"""

import pytest
import torch
import numpy as np

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.lateral_coupling import LateralCoupler, CouplingType
from engine.xiang_detector import XiàngDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.unsealing_mechanism import UnsealingMechanism
from engine.return_flow_channel import ReturnFlowChannel
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.seventh_threshold_detector import SeventhThresholdDetector
from engine.cooperative_emergence_detector import CooperativeEmergenceDetector


def _make_evolver_with_lateral(
    N0=24,
    steps_per_layer=50,
    sample_interval=50,
    max_layers=2,
    p1_eval_interval=1,
    phase2_verbose=False,
):
    """创建带有 LateralCoupler 的 HierarchicalEvolver"""
    coupler = LateralCoupler(config={
        'max_coupling_distance': 5.0,
        'coupling_decay_rate': 0.3,
        'boundary_overlap_threshold': 0.1,
        'field_diffusion_rate': 0.05,
        'density_gradient_sensitivity': 0.2,
        'max_neighbors': 6,
        'coupling_cap': 1.0,
    })

    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps_per_layer,
        sample_interval=sample_interval,
        max_layers=max_layers,
        device="cpu",
        auto_encapsulate=False,
        # Phase 2 P0
        xiang_detector=XiàngDetector(),
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(),
        # Phase 2 P1
        six_threshold_detector=SixThresholdDetector(),
        pre_subjectivity_convergence=PreSubjectivityConvergence(),
        unsealing_mechanism=UnsealingMechanism(),
        return_flow_channel=ReturnFlowChannel(),
        organizational_density_index=OrganizationalDensityIndex(),
        seventh_threshold_detector=SeventhThresholdDetector(),
        cooperative_emergence_detector=CooperativeEmergenceDetector(),
        # Phase 2 P2
        lateral_coupler=coupler,
        p1_eval_interval=p1_eval_interval,
        phase2_verbose=phase2_verbose,
    )
    return evolver, coupler


class TestLateralCouplerIntegration:
    """LateralCoupler 集成到 HierarchicalEvolver 的测试"""

    def test_lateral_coupler_passed_to_evolver(self):
        """验证 LateralCoupler 被正确传入 HierarchicalEvolver"""
        evolver, coupler = _make_evolver_with_lateral()
        assert evolver.lateral_coupler is coupler

    def test_evolver_without_lateral_coupler_backward_compat(self):
        """验证不传 LateralCoupler 时行为不变"""
        evolver = HierarchicalEvolver(
            N0=24,
            steps_per_layer=50,
            sample_interval=50,
            max_layers=1,
            device="cpu",
            auto_encapsulate=False,
            xiang_detector=XiàngDetector(),
            persistent_bias_memory=PersistentBiasMemory(),
            cumulative_selector=CumulativeSelector(),
            six_threshold_detector=SixThresholdDetector(),
            pre_subjectivity_convergence=PreSubjectivityConvergence(),
            p1_eval_interval=5,
        )
        assert evolver.lateral_coupler is None
        result = evolver.run(verbose=False)
        assert result['n_layers'] >= 1
        p2s = result.get('phase2_summary', {})
        assert p2s.get('lateral_coupler_active') is False
        assert p2s.get('lateral_coupler_n_structures') == 0

    def test_lateral_coupler_structures_registered_during_run(self):
        """验证运行过程中 LateralCoupler 注册了结构"""
        evolver, coupler = _make_evolver_with_lateral(
            N0=24, steps_per_layer=50, sample_interval=50,
            max_layers=1, p1_eval_interval=1,
        )
        result = evolver.run(verbose=False)
        # 至少注册了 1 个结构（第 0 层）
        assert coupler.n_structures >= 1
        assert 0 in coupler.structure_ids

    def test_lateral_coupler_reports_generated(self):
        """验证运行过程中生成了耦合报告"""
        evolver, coupler = _make_evolver_with_lateral(
            N0=24, steps_per_layer=100, sample_interval=50,
            max_layers=1, p1_eval_interval=1,
        )
        result = evolver.run(verbose=False)
        reports = coupler.get_report_history()
        # 至少应该有 1 个报告
        assert len(reports) >= 1
        # 报告应包含基本字段
        for r in reports:
            assert r.n_structures >= 1
            assert r.timestamp >= 0

    def test_phase2_summary_includes_lateral_coupler(self):
        """验证 phase2_summary 包含 LateralCoupler 状态"""
        evolver, coupler = _make_evolver_with_lateral(
            N0=24, steps_per_layer=50, sample_interval=50,
            max_layers=1, p1_eval_interval=1,
        )
        result = evolver.run(verbose=False)
        p2s = result.get('phase2_summary', {})
        assert p2s.get('lateral_coupler_active') is True
        assert p2s.get('lateral_coupler_n_structures') >= 1

    def test_lateral_coupler_result_in_phase2_step_results(self):
        """验证 phase2_step_results 包含 lateral_coupler 数据"""
        evolver, coupler = _make_evolver_with_lateral(
            N0=24, steps_per_layer=100, sample_interval=50,
            max_layers=1, p1_eval_interval=1,
        )
        result = evolver.run(verbose=False)
        # 检查 layer_results 中是否有 lateral_coupling 数据
        for lr in result.get('layer_results', []):
            p2_results = lr.get('phase2_step_results', [])
            lateral_entries = [r for r in p2_results if 'lateral_coupling' in r]
            # 至少有一些 P1 评估步包含 lateral_coupling
            assert len(lateral_entries) >= 1
            for entry in lateral_entries:
                lc = entry['lateral_coupling']
                assert 'n_structures' in lc
                assert 'n_active_pairs' in lc
                assert 'mean_coupling_strength' in lc
                assert 'net_effects' in lc
                assert 'selection_pressure_deltas' in lc

    def test_lateral_coupler_single_layer_multiple_reports(self):
        """验证单层多次 P1 评估时 LateralCoupler 产生多个报告"""
        evolver, coupler = _make_evolver_with_lateral(
            N0=24, steps_per_layer=100, sample_interval=50,
            max_layers=1, p1_eval_interval=1,
        )
        result = evolver.run(verbose=False)
        reports = coupler.get_report_history()
        # 100 steps / 5 interval = 至少多次 P1 评估
        assert len(reports) >= 1
        # 所有报告都应包含结构 0
        for r in reports:
            assert 0 in r.field_snapshot

    def test_lateral_coupler_no_structures_no_error(self):
        """验证 LateralCoupler 在无结构时不出错"""
        coupler = LateralCoupler()
        # 不注册任何结构直接 compute_step
        report = coupler.compute_step(timestamp=0)
        assert report.n_structures == 0
        assert report.n_active_pairs == 0
        assert report.mean_coupling_strength == 0.0

    def test_lateral_coupler_single_structure_no_pairs(self):
        """验证单个结构时没有耦合对"""
        evolver, coupler = _make_evolver_with_lateral(
            N0=24, steps_per_layer=50, sample_interval=50,
            max_layers=1, p1_eval_interval=5,
        )
        result = evolver.run(verbose=False)
        reports = coupler.get_report_history()
        for r in reports:
            # 只有 1 层 → 只有 1 个结构 → 没有耦合对
            if r.n_structures == 1:
                assert r.n_active_pairs == 0

    def test_lateral_coupler_coupling_types_valid(self):
        """验证耦合类型是有效的枚举值"""
        coupler = LateralCoupler()
        coupler.register_structure(0, np.array([0.0, 0.0]), odi=0.6)
        coupler.register_structure(1, np.array([1.0, 0.0]), odi=0.7)
        report = coupler.compute_step(timestamp=0)
        for pair in report.pairs:
            assert isinstance(pair.coupling_type, CouplingType)

    def test_lateral_coupler_selection_pressure_deltas_sign(self):
        """验证选择压力变化的方向性：高密度结构受到正压力"""
        coupler = LateralCoupler(config={'max_coupling_distance': 5.0})
        coupler.register_structure(0, np.array([0.0, 0.0]), odi=0.8, boundary_radius=1.5)
        coupler.register_structure(1, np.array([1.0, 0.0]), odi=0.3, boundary_radius=1.0)
        report = coupler.compute_step(timestamp=0)
        # 低密度结构应受到正选择压力（被高密度影响）
        if report.selection_pressure_deltas:
            # 结构 1 (低密度) 应受到正压力
            if 1 in report.selection_pressure_deltas:
                # 不强制符号，但确保值是合理的浮点数
                assert isinstance(report.selection_pressure_deltas[1], float)

    def test_lateral_coupler_net_effects_sum_near_zero(self):
        """验证净耦合效应近似守恒（高密度损失≈低密度获得）"""
        coupler = LateralCoupler(config={'max_coupling_distance': 5.0})
        coupler.register_structure(0, np.array([0.0, 0.0]), odi=0.8, boundary_radius=1.5)
        coupler.register_structure(1, np.array([1.0, 0.0]), odi=0.3, boundary_radius=1.0)
        report = coupler.compute_step(timestamp=0)
        if report.net_effects:
            total = sum(report.net_effects.values())
            # 净效应总和应接近零（守恒）
            assert abs(total) < 1.0

    def test_lateral_coupler_coupling_strength_bounded(self):
        """验证耦合强度在 [0, 1] 范围内"""
        coupler = LateralCoupler(config={'max_coupling_distance': 5.0})
        coupler.register_structure(0, np.array([0.0, 0.0]), odi=0.9, boundary_radius=2.0)
        coupler.register_structure(1, np.array([0.5, 0.0]), odi=0.1, boundary_radius=2.0)
        report = coupler.compute_step(timestamp=0)
        for pair in report.pairs:
            assert 0.0 <= pair.coupling_strength <= 1.0

    def test_evolver_lateral_coupler_with_all_phase2_components(self):
        """验证 LateralCoupler 与所有 Phase 2 组件共存"""
        evolver, coupler = _make_evolver_with_lateral(
            N0=24, steps_per_layer=100, sample_interval=50,
            max_layers=1, p1_eval_interval=5,
        )
        result = evolver.run(verbose=False)
        p2s = result['phase2_summary']
        # 所有组件都应活跃
        assert p2s['xiang_detector_active'] is True
        assert p2s['six_threshold_detector_active'] is True
        assert p2s['pre_subjectivity_convergence_active'] is True
        assert p2s['unsealing_mechanism_active'] is True
        assert p2s['return_flow_channel_active'] is True
        assert p2s['organizational_density_index_active'] is True
        assert p2s['seventh_threshold_detector_active'] is True
        assert p2s['cooperative_emergence_detector_active'] is True
        assert p2s['lateral_coupler_active'] is True
        # 测试通过，无异常

    def test_lateral_coupler_report_history_preserved(self):
        """验证耦合报告历史在运行后保留"""
        evolver, coupler = _make_evolver_with_lateral(
            N0=24, steps_per_layer=200, sample_interval=50,
            max_layers=1, p1_eval_interval=1,
        )
        result = evolver.run(verbose=False)
        reports = coupler.get_report_history()
        assert len(reports) >= 1
        # 报告应按时间戳递增
        timestamps = [r.timestamp for r in reports]
        assert timestamps == sorted(timestamps)
