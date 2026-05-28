"""test_xiangjie.py — 象界显现链测试

验证八章门槛检测器的功能与边界条件。
"""

import pytest
import torch
from dataclasses import dataclass
from typing import Optional
from xiangjie.chain import (
    XiangjieChain,
    XiangjieReport,
    ThresholdReport,
    BoundaryGate,
    InterfaceGate,
    SelfMaintenanceGate,
    MemoryGate,
    ReplicationGate,
    SelectionGate,
    FunctionGate,
    PreSubjectiveGate,
)


# =============================================================================
# 辅助：构造测试用的 StableStructure（内联替代已删除的 acl.axiom_base.StableStructure）
# =============================================================================

@dataclass
class StableStructure:
    mask: torch.Tensor
    lifetime: int
    pattern_signature: torch.Tensor
    boundary_map: torch.Tensor
    material_turnover: float
    source_layer: str
    connectivity_ratio: float = 0.0
    boundary_closure_score: float = 0.0


def make_struct(
    size=8,
    lifetime=32,
    turnover=0.15,
    connectivity=0.8,
    boundary_closure=0.2,
    pattern_mean=0.5,
):
    """创建一个测试用的稳定结构"""
    mask = torch.zeros(size, size, dtype=torch.bool)
    mask[2:6, 2:6] = True  # 4x4 中心区域

    # 边界：4x4 的外圈
    boundary = torch.zeros(size, size, dtype=torch.bool)
    boundary[2, 2:6] = True
    boundary[5, 2:6] = True
    boundary[2:6, 2] = True
    boundary[2:6, 5] = True

    pattern = torch.tensor([pattern_mean])

    return StableStructure(
        mask=mask,
        lifetime=lifetime,
        pattern_signature=pattern,
        boundary_map=boundary,
        material_turnover=turnover,
        source_layer="hamming_layer",
        connectivity_ratio=connectivity,
        boundary_closure_score=boundary_closure,
    )


# =============================================================================
# 八章门槛测试
# =============================================================================

class TestBoundaryGate:
    def test_passes_for_well_bounded_structure(self):
        gate = BoundaryGate()
        struct = make_struct(size=8, boundary_closure=0.2)
        report = gate.evaluate(struct)
        assert report.passed
        assert report.score > 0

    def test_fails_for_open_structure(self):
        gate = BoundaryGate()
        # 大边界比例 → 不闭合
        mask = torch.ones(8, 8, dtype=torch.bool)
        boundary = torch.ones(8, 8, dtype=torch.bool)
        struct = StableStructure(
            mask=mask, lifetime=32,
            pattern_signature=torch.tensor([0.5]),
            boundary_map=boundary, material_turnover=0.1,
            source_layer="L0",
            connectivity_ratio=1.0,
            boundary_closure_score=0.9,
        )
        report = gate.evaluate(struct)
        assert not report.passed

    def test_zero_area_structure(self):
        gate = BoundaryGate()
        mask = torch.zeros(4, 4, dtype=torch.bool)
        struct = StableStructure(
            mask=mask, lifetime=0,
            pattern_signature=torch.tensor([0.0]),
            boundary_map=torch.zeros(4, 4, dtype=torch.bool),
            material_turnover=0.0,
            source_layer="L0",
        )
        report = gate.evaluate(struct)
        assert report.score == 0.0


class TestSelfMaintenanceGate:
    def test_passes_for_active_structure(self):
        gate = SelfMaintenanceGate()
        struct = make_struct(turnover=0.15)
        report = gate.evaluate(struct)
        assert report.passed

    def test_fails_for_frozen_structure(self):
        gate = SelfMaintenanceGate()
        struct = make_struct(turnover=0.01)
        report = gate.evaluate(struct)
        assert not report.passed

    def test_fails_for_chaotic_structure(self):
        gate = SelfMaintenanceGate()
        struct = make_struct(turnover=0.50)
        report = gate.evaluate(struct)
        assert not report.passed


class TestMemoryGate:
    def test_passes_for_long_lived_structure(self):
        gate = MemoryGate()
        struct = make_struct(lifetime=32)
        report = gate.evaluate(struct)
        assert report.passed
        assert report.score >= 1.0

    def test_fails_for_short_lived_structure(self):
        gate = MemoryGate()
        struct = make_struct(lifetime=8)
        report = gate.evaluate(struct)
        assert not report.passed


class TestSelectionGate:
    def test_passes_for_connected_structure(self):
        gate = SelectionGate()
        struct = make_struct(connectivity=0.8)
        report = gate.evaluate(struct)
        assert report.passed

    def test_fails_for_fragmented_structure(self):
        gate = SelectionGate()
        struct = make_struct(connectivity=0.3)
        report = gate.evaluate(struct)
        assert not report.passed

    def test_with_multiple_structures(self):
        gate = SelectionGate()
        strong = make_struct(connectivity=0.9)
        weak = make_struct(connectivity=0.2)
        report = gate.evaluate(strong, [strong, weak])
        assert report.passed


class TestFunctionGate:
    def test_passes_for_contribution(self):
        gate = FunctionGate()
        struct = make_struct(pattern_mean=0.7, connectivity=0.8)
        report = gate.evaluate(struct, global_activity=0.5)
        assert report.passed

    def test_fails_for_low_contribution(self):
        gate = FunctionGate()
        struct = make_struct(pattern_mean=0.1, connectivity=0.2)
        report = gate.evaluate(struct, global_activity=0.5)
        assert not report.passed


class TestPreSubjectiveGate:
    def test_passes_when_most_gates_passed(self):
        gate = PreSubjectiveGate()
        sub_reports = [
            ThresholdReport("边界", "I", True, 0.8, 0.3, ""),
            ThresholdReport("界面", "II", True, 0.7, 0.15, ""),
            ThresholdReport("自维持", "III", True, 0.6, 0.4, ""),
            ThresholdReport("记忆", "IV", True, 0.9, 16, ""),
            ThresholdReport("复制", "V", True, 0.8, 0.7, ""),
            ThresholdReport("筛选", "VI", True, 0.7, 0.5, ""),
            ThresholdReport("功能", "VII", False, 0.3, 0.4, ""),
        ]
        struct = make_struct(connectivity=0.8)
        report = gate.evaluate(sub_reports, struct)
        assert report.passed

    def test_fails_when_too_few_gates_passed(self):
        gate = PreSubjectiveGate()
        sub_reports = [
            ThresholdReport("边界", "I", True, 0.6, 0.3, ""),
            ThresholdReport("界面", "II", False, 0.1, 0.15, ""),
            ThresholdReport("自维持", "III", False, 0.2, 0.4, ""),
            ThresholdReport("记忆", "IV", False, 0.1, 16, ""),
            ThresholdReport("复制", "V", False, 0.2, 0.7, ""),
            ThresholdReport("筛选", "VI", True, 0.6, 0.5, ""),
            ThresholdReport("功能", "VII", False, 0.1, 0.4, ""),
        ]
        struct = make_struct(connectivity=0.4)
        report = gate.evaluate(sub_reports, struct)
        assert not report.passed


# =============================================================================
# 完整链测试
# =============================================================================

class TestXiangjieChain:
    def test_empty_structures(self):
        chain = XiangjieChain()
        report = chain.evaluate([], [])
        assert report.overall_score == 0.0
        assert report.max_stage_reached == 0
        assert not report.is_pre_subjective

    def test_well_formed_structure(self):
        chain = XiangjieChain()
        struct = make_struct(
            lifetime=48,
            turnover=0.15,
            connectivity=0.9,
            boundary_closure=0.15,
            pattern_mean=0.6,
        )
        # 创建历史
        state = torch.rand(1, 1, 8, 8) * 0.5 + 0.3
        history = [state.clone() for _ in range(20)]

        report = chain.evaluate([struct], history)
        assert report.overall_score > 0
        assert len(report.thresholds) == 8
        assert isinstance(report.max_stage_name, str)

    def test_report_str(self):
        chain = XiangjieChain()
        struct = make_struct()
        history = [torch.rand(1, 1, 8, 8) for _ in range(16)]
        report = chain.evaluate([struct], history)
        text = str(report)
        assert "Xiangjie Chain Report" in text
        assert "边界" in text
        assert "前主体态" in text

    def test_multiple_structures_picks_best(self):
        chain = XiangjieChain()
        strong = make_struct(lifetime=64, turnover=0.12, connectivity=0.95)
        weak = make_struct(lifetime=4, turnover=0.01, connectivity=0.1)
        history = [torch.rand(1, 1, 8, 8) for _ in range(16)]
        report = chain.evaluate([strong, weak], history)
        # 应该选择 strong 作为代表
        assert report.overall_score > 0.3
