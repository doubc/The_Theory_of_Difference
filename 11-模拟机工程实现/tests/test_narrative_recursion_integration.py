"""
tests/test_narrative_recursion_integration.py — NarrativeRecursionOperator
与 HierarchicalEvolver 的集成测试

验证：
1. NarrativeRecursionOperator 可作为参数传入 HierarchicalEvolver
2. 在演化过程中，叙事算子能正确接收差异信号并输出偏置修正
3. 偏置修正被正确反馈到 constraints.direction
4. 演化完成后，phase3_summary 包含叙事递归统计
"""

import torch
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hierarchical_evolver import HierarchicalEvolver
from models.narrative_self import (
    NarrativeRecursionOperator,
    DifferenceSignal,
    NarrativeLevel,
)
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.unsealing_mechanism import UnsealingMechanism
from engine.return_flow_channel import ReturnFlowChannel


class TestNarrativeRecursionIntegration:

    def test_narrative_operator_accepted_by_evolver(self):
        """叙事算子可被 HierarchicalEvolver 构造器接受"""
        nro = NarrativeRecursionOperator(bias_dimension=128)
        evolver = HierarchicalEvolver(
            N0=24,
            steps_per_layer=100,
            max_layers=1,
            narrative_recursion_operator=nro,
            device="cpu",
        )
        assert evolver.narrative_recursion_operator is nro

    def test_narrative_step_in_callback_produces_correction(self):
        """叙事算子在回调中执行时能产生偏置修正"""
        nro = NarrativeRecursionOperator(
            bias_dimension=128,
            filter_magnitude_threshold=0.05,
            connector_strength_threshold=0.1,
        )

        # 构造少量差异信号
        signals = [
            DifferenceSignal(
                signal_id=f"sig_{i}",
                source_layer=0,
                target_layer=0,
                magnitude=0.3 + i * 0.05,
                direction=torch.randn(1, 128).float(),
                timestamp=i,
            )
            for i in range(8)
        ]

        current_bias = torch.randn(128).float()
        correction = nro.step(
            signals=signals,
            current_bias=current_bias,
            current_odi=0.3,
            timestamp=1000,
        )

        # 有足够信号时应产生修正
        assert correction is not None
        assert correction.shape == (128,)
        assert correction.norm().item() > 1e-8

    def test_narrative_operator_no_correction_with_weak_signals(self):
        """当差异信号太弱时，叙事算子不产生修正"""
        nro = NarrativeRecursionOperator(
            bias_dimension=128,
            filter_magnitude_threshold=0.5,  # 高阈值
        )

        # 所有信号幅度都低于阈值
        signals = [
            DifferenceSignal(
                signal_id=f"sig_{i}",
                source_layer=0,
                target_layer=0,
                magnitude=0.01,
                direction=torch.randn(1, 128).float(),
                timestamp=i,
            )
            for i in range(5)
        ]

        correction = nro.step(
            signals=signals,
            current_bias=torch.randn(128).float(),
            current_odi=0.1,
            timestamp=100,
        )

        # 信号被筛选后无显著信号，应返回 None
        assert correction is None

    def test_narrative_summary_tracking(self):
        """叙事算子能正确追踪叙事记录统计"""
        nro = NarrativeRecursionOperator(bias_dimension=64)

        for step in range(3):
            signals = [
                DifferenceSignal(
                    signal_id=f"sig_{step}_{i}",
                    source_layer=0,
                    target_layer=0,
                    magnitude=0.4,
                    direction=torch.randn(1, 64).float(),
                    timestamp=step * 1000 + i,
                )
                for i in range(4)
            ]

            nro.step(
                signals=signals,
                current_bias=torch.randn(64).float(),
                current_odi=0.3 + step * 0.1,
                timestamp=step * 1000,
            )

        summary = nro.get_summary()
        assert summary['total_narrative_records'] >= 1
        assert 'validation_rate' in summary
        assert 'narrative_level_distribution' in summary

    def test_narrative_integration_with_evolver_short_run(self):
        """叙事算子集成到 HierarchicalEvolver 的端到端短运行测试"""
        nro = NarrativeRecursionOperator(
            bias_dimension=24,  # 与 N0 匹配
            filter_magnitude_threshold=0.01,
            connector_strength_threshold=0.01,
        )

        evolver = HierarchicalEvolver(
            N0=24,
            steps_per_layer=200,
            max_layers=1,
            narrative_recursion_operator=nro,
            device="cpu",
        )

        results = evolver.run(verbose=False)

        # 验证 phase3_summary 包含叙事信息
        p3 = results['phase3_summary']
        assert p3['narrative_recursion_active'] is True
        assert p3['narrative_summary'] is not None
        assert p3['narrative_summary']['total_narrative_records'] >= 0

    def test_narrative_with_bias_memory_and_odi(self):
        """叙事算子与 PersistentBiasMemory + ODI 联合运行"""
        bias_memory = PersistentBiasMemory()
        odi = OrganizationalDensityIndex(temporal_window=50)

        nro = NarrativeRecursionOperator(
            bias_dimension=24,
            filter_magnitude_threshold=0.01,
        )

        evolver = HierarchicalEvolver(
            N0=24,
            steps_per_layer=150,
            max_layers=1,
            persistent_bias_memory=bias_memory,
            organizational_density_index=odi,
            narrative_recursion_operator=nro,
            device="cpu",
        )

        results = evolver.run(verbose=False)

        p3 = results['phase3_summary']
        assert p3['narrative_recursion_active'] is True
        assert bias_memory.n_entries > 0

    def test_narrative_bias_correction_feedback(self):
        """验证叙事偏置修正被反馈到 constraints.direction"""
        nro = NarrativeRecursionOperator(
            bias_dimension=16,
            filter_magnitude_threshold=0.01,
            connector_strength_threshold=0.01,
        )

        evolver = HierarchicalEvolver(
            N0=16,
            steps_per_layer=100,
            max_layers=1,
            narrative_recursion_operator=nro,
            device="cpu",
        )

        # 记录初始方向
        initial_direction = evolver.hierarchy.get_layer(0).constraints.direction.clone()

        results = evolver.run(verbose=False)

        # 演化后方向应发生变化（因为叙事修正）
        final_direction = evolver.hierarchy.get_layer(0).constraints.direction
        diff = (final_direction.float() - initial_direction.float()).norm().item()

        # 方向应有变化（叙事修正会修改方向场）
        assert diff > 1e-6

    def test_narrative_level_distribution(self):
        """验证叙事层级分布正确统计"""
        nro = NarrativeRecursionOperator(bias_dimension=32)

        # 产生不同强度的信号以触发不同叙事层级
        for strength in [0.2, 0.5, 0.8]:
            signals = [
                DifferenceSignal(
                    signal_id=f"sig_{strength}_{i}",
                    source_layer=0,
                    target_layer=0,
                    magnitude=strength,
                    direction=torch.randn(1, 32).float(),
                    timestamp=i,
                )
                for i in range(6)
            ]

            nro.step(
                signals=signals,
                current_bias=torch.randn(32).float(),
                current_odi=0.3,
                timestamp=1000,
            )

        summary = nro.get_summary()
        level_dist = summary['narrative_level_distribution']
        # 至少有一个层级的叙事被记录
        total = sum(level_dist.values())
        assert total >= 1
