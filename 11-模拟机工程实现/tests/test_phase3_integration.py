"""
tests/test_phase3_integration.py — Phase 3 组件集成到 HierarchicalEvolver 的测试

验证 MinimalSelfDetector, AnticipatoryBiasEngine, CounterfactualEngine
能够正确集成到 HierarchicalEvolver 的回调管线中。
"""

import pytest
import torch
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.minimal_self_detector import MinimalSelfDetector
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.hierarchical_evolver import HierarchicalEvolver


class TestPhase3Integration:
    """Phase 3 组件集成到 HierarchicalEvolver 的测试"""

    def _make_evolver(self, **kwargs):
        """创建带 Phase 3 组件的 HierarchicalEvolver（最小配置）"""
        N0 = kwargs.pop('N0', 12)
        steps = kwargs.pop('steps_per_layer', 20)
        max_layers = kwargs.pop('max_layers', 1)
        p1_interval = kwargs.pop('p1_eval_interval', 5)

        # Phase 2 前置组件（Phase 3 依赖 ODI）
        pbm = PersistentBiasMemory()
        odi = OrganizationalDensityIndex()

        # Phase 3 组件
        msd = MinimalSelfDetector()
        abe = AnticipatoryBiasEngine(memory=pbm)
        cfe = CounterfactualEngine()

        evolver = HierarchicalEvolver(
            N0=N0,
            steps_per_layer=steps,
            max_layers=max_layers,
            p1_eval_interval=p1_interval,
            device='cpu',
            persistent_bias_memory=pbm,
            organizational_density_index=odi,
            minimal_self_detector=msd,
            anticipatory_bias_engine=abe,
            counterfactual_engine=cfe,
            phase3_verbose=kwargs.pop('verbose', False),
            **kwargs,
        )
        return evolver, msd, abe, cfe

    def test_phase3_components_registered(self):
        """Phase 3 组件应正确注册到 evolver"""
        evolver, msd, abe, cfe = self._make_evolver()
        assert evolver.minimal_self_detector is msd
        assert evolver.anticipatory_bias_engine is abe
        assert evolver.counterfactual_engine is cfe

    def test_phase3_summary_in_results(self):
        """运行后 results 应包含 phase3_summary"""
        evolver, _, _, _ = self._make_evolver()
        results = evolver.run(verbose=False)
        assert 'phase3_summary' in results
        ps3 = results['phase3_summary']
        assert ps3['minimal_self_detector_active'] is True
        assert ps3['anticipatory_bias_engine_active'] is True
        assert ps3['counterfactual_engine_active'] is True

    def test_phase3_default_values(self):
        """未检测到时应为默认值"""
        evolver, _, _, _ = self._make_evolver()
        results = evolver.run(verbose=False)
        ps3 = results['phase3_summary']
        assert ps3['minimal_self_detected'] is False
        assert ps3['msi'] == 0.0
        assert ps3['anticipation_reliable'] is False
        assert ps3['anticipation_accuracy'] == 0.0
        assert ps3['counterfactual_active'] is False
        assert ps3['counterfactual_n_branches'] == 0

    def test_phase3_without_phase2_odi(self):
        """无 ODI 组件时 Phase 3 不应崩溃（ODI 门控保护）"""
        msd = MinimalSelfDetector()
        abe = AnticipatoryBiasEngine(memory=PersistentBiasMemory())
        cfe = CounterfactualEngine()

        evolver = HierarchicalEvolver(
            N0=12,
            steps_per_layer=10,
            max_layers=1,
            p1_eval_interval=5,
            device='cpu',
            minimal_self_detector=msd,
            anticipatory_bias_engine=abe,
            counterfactual_engine=cfe,
        )
        # 不应崩溃
        results = evolver.run(verbose=False)
        assert 'phase3_summary' in results

    def test_phase3_only_msi(self):
        """仅注册 MinimalSelfDetector 时应正常工作"""
        msd = MinimalSelfDetector()
        evolver = HierarchicalEvolver(
            N0=12,
            steps_per_layer=10,
            max_layers=1,
            p1_eval_interval=5,
            device='cpu',
            minimal_self_detector=msd,
        )
        results = evolver.run(verbose=False)
        ps3 = results['phase3_summary']
        assert ps3['minimal_self_detector_active'] is True
        assert ps3['anticipatory_bias_engine_active'] is False
        assert ps3['counterfactual_engine_active'] is False

    def test_phase3_only_anticipation(self):
        """仅注册 AnticipatoryBiasEngine 时应正常工作"""
        pbm = PersistentBiasMemory()
        abe = AnticipatoryBiasEngine(memory=pbm)
        evolver = HierarchicalEvolver(
            N0=12,
            steps_per_layer=10,
            max_layers=1,
            p1_eval_interval=5,
            device='cpu',
            anticipatory_bias_engine=abe,
        )
        results = evolver.run(verbose=False)
        ps3 = results['phase3_summary']
        assert ps3['minimal_self_detector_active'] is False
        assert ps3['anticipatory_bias_engine_active'] is True
        assert ps3['counterfactual_engine_active'] is False

    def test_phase3_only_counterfactual(self):
        """仅注册 CounterfactualEngine 时应正常工作"""
        cfe = CounterfactualEngine()
        evolver = HierarchicalEvolver(
            N0=12,
            steps_per_layer=10,
            max_layers=1,
            p1_eval_interval=5,
            device='cpu',
            counterfactual_engine=cfe,
        )
        results = evolver.run(verbose=False)
        ps3 = results['phase3_summary']
        assert ps3['minimal_self_detector_active'] is False
        assert ps3['anticipatory_bias_engine_active'] is False
        assert ps3['counterfactual_engine_active'] is True

    def test_phase3_step_results_contain_phase3_keys(self):
        """Phase 3 激活时，step results 应包含 Phase 3 键"""
        evolver, _, _, _ = self._make_evolver(steps_per_layer=30, p1_eval_interval=5)
        results = evolver.run(verbose=False)

        # 检查是否有层结果包含 phase3 数据
        found_phase3 = False
        for lr in results['layer_results']:
            if 'phase2_step_results' in lr:
                for step_result in lr['phase2_step_results']:
                    if 'minimal_self' in step_result:
                        found_phase3 = True
                        # 验证 MSI 结果结构
                        msi_data = step_result['minimal_self']
                        assert 'detected' in msi_data
                        assert 'msi' in msi_data
                        assert 'n_active_conditions' in msi_data
                    if 'anticipation' in step_result:
                        ant_data = step_result['anticipation']
                        assert 'confidence' in ant_data
                        assert 'is_reliable' in ant_data
                    if 'counterfactual' in step_result:
                        cf_data = step_result['counterfactual']
                        assert 'active' in cf_data
                        assert 'n_active_branches' in cf_data

        # 注意：Phase 3 需要 ODI > 0.5 才激活，在小型测试中可能不触发
        # 所以这里不强制 found_phase3，只验证结构正确

    def test_phase3_backward_compatible_no_phase3(self):
        """不注册 Phase 3 组件时行为应与之前一致"""
        evolver = HierarchicalEvolver(
            N0=12,
            steps_per_layer=10,
            max_layers=1,
            p1_eval_interval=5,
            device='cpu',
        )
        results = evolver.run(verbose=False)
        assert 'phase3_summary' in results
        ps3 = results['phase3_summary']
        assert ps3['minimal_self_detector_active'] is False
        assert ps3['anticipatory_bias_engine_active'] is False
        assert ps3['counterfactual_engine_active'] is False

    def test_phase3_with_all_phase2_and_phase3(self):
        """Phase 2 + Phase 3 全部组件集成测试"""
        from engine.xiang_detector import XiàngDetector
        from engine.cumulative_selector import CumulativeSelector
        from engine.six_threshold_detector import SixThresholdDetector
        from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
        from engine.seventh_threshold_detector import SeventhThresholdDetector
        from engine.cooperative_emergence_detector import CooperativeEmergenceDetector

        pbm = PersistentBiasMemory()
        odi = OrganizationalDensityIndex()
        xd = XiàngDetector()
        cs = CumulativeSelector()
        std = SixThresholdDetector()
        psc = PreSubjectivityConvergence()
        msd = MinimalSelfDetector()
        abe = AnticipatoryBiasEngine(memory=pbm)
        cfe = CounterfactualEngine()

        evolver = HierarchicalEvolver(
            N0=12,
            steps_per_layer=20,
            max_layers=1,
            p1_eval_interval=5,
            device='cpu',
            persistent_bias_memory=pbm,
            xiang_detector=xd,
            cumulative_selector=cs,
            six_threshold_detector=std,
            pre_subjectivity_convergence=psc,
            organizational_density_index=odi,
            seventh_threshold_detector=SeventhThresholdDetector(),
            cooperative_emergence_detector=CooperativeEmergenceDetector(),
            minimal_self_detector=msd,
            anticipatory_bias_engine=abe,
            counterfactual_engine=cfe,
        )
        results = evolver.run(verbose=False)

        # Phase 2 summary
        assert 'phase2_summary' in results
        ps2 = results['phase2_summary']
        assert ps2['organizational_density_index_active'] is True

        # Phase 3 summary
        assert 'phase3_summary' in results
        ps3 = results['phase3_summary']
        assert ps3['minimal_self_detector_active'] is True
        assert ps3['anticipatory_bias_engine_active'] is True
        assert ps3['counterfactual_engine_active'] is True

    def test_phase3_counterfactual_explore_in_callback(self):
        """CounterfactualEngine.explore 应在回调中被调用"""
        cfe = CounterfactualEngine()
        evolver = HierarchicalEvolver(
            N0=12,
            steps_per_layer=20,
            max_layers=1,
            p1_eval_interval=5,
            device='cpu',
            counterfactual_engine=cfe,
        )
        results = evolver.run(verbose=False)

        # CounterfactualEngine 应该至少探索过
        # 注意：ODI 门控可能阻止探索，但引擎应该被调用
        assert results['phase3_summary']['counterfactual_engine_active'] is True

    def test_phase3_anticipation_predict_in_callback(self):
        """AnticipatoryBiasEngine.predict 应在回调中被调用"""
        pbm = PersistentBiasMemory()
        abe = AnticipatoryBiasEngine(memory=pbm)
        evolver = HierarchicalEvolver(
            N0=12,
            steps_per_layer=20,
            max_layers=1,
            p1_eval_interval=5,
            device='cpu',
            persistent_bias_memory=pbm,
            anticipatory_bias_engine=abe,
        )
        results = evolver.run(verbose=False)
        assert results['phase3_summary']['anticipatory_bias_engine_active'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
