"""
test_structure_validator.py — 稳定结构验证器测试

验证五标准：lifetime, boundary, closure, turnover, interaction。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
import pytest
from acl.axiom_base import StableStructure
from validators.structure_validator import StructureValidator, ValidationReport


class TestStructureValidator:
    """验证器测试"""

    def setup_method(self):
        self.validator = StructureValidator(
            min_lifetime=4,
            boundary_stability_threshold=0.3,
            connectivity_threshold=0.5,
            boundary_closure_threshold=0.5,
            max_turnover=0.2,
            interaction_distance=5.0,
        )

    def _make_structure(self, mask, lifetime=10, turnover=0.05,
                        connectivity_ratio=1.0, boundary_closure_score=0.0):
        """创建测试用稳定结构（v2：含审计报告拆分指标）"""
        return StableStructure(
            mask=mask,
            lifetime=lifetime,
            pattern_signature=torch.tensor(0.5),
            boundary_map=mask.float(),
            material_turnover=float(turnover),
            source_layer="L0_binary",
            connectivity_ratio=connectivity_ratio,
            boundary_closure_score=boundary_closure_score,
        )

    def test_empty_structures(self):
        """空结构列表应返回零报告"""
        report = self.validator.validate([], [])
        assert report.total_structures == 0
        assert report.passed_structures == 0
        assert "No structures" in report.summary

    def test_single_structure_pass(self):
        """单个合格结构应通过"""
        mask = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask[:, :, 4:12, 4:12] = True
        struct = self._make_structure(mask, lifetime=16, turnover=0.05)

        history = [torch.rand(1, 1, 16, 16) * 0.3 + 0.3 for _ in range(16)]

        report = self.validator.validate([struct], history)
        assert report.total_structures == 1
        assert report.lifetime_passed == 1
        assert report.turnover_passed == 1

    def test_lifetime_fail(self):
        """寿命不足的结构应失败"""
        mask = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask[:, :, 4:12, 4:12] = True
        struct = self._make_structure(mask, lifetime=2)  # < min_lifetime=4

        report = self.validator.validate([struct], [])
        assert report.lifetime_passed == 0
        assert report.single_validations[0].lifetime_pass is False

    def test_turnover_fail(self):
        """周转率过高的结构应失败"""
        mask = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask[:, :, 4:12, 4:12] = True
        struct = self._make_structure(mask, lifetime=10, turnover=0.5)  # > max_turnover=0.2

        report = self.validator.validate([struct], [])
        assert report.turnover_passed == 0
        assert report.single_validations[0].turnover_pass is False

    def test_closure_connectivity(self):
        """连通区域应有高闭合度"""
        # 创建一个连通的矩形区域
        mask = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask[:, :, 4:12, 4:12] = True
        struct = self._make_structure(mask, lifetime=10, turnover=0.05,
                                    connectivity_ratio=1.0, boundary_closure_score=0.0)

        sv = self.validator.validate_single(0, struct, [])
        assert sv.closure_ratio == 1.0  # 完全连通
        assert sv.closure_pass is True

    def test_closure_disconnected(self):
        """不连通区域应有低闭合度"""
        # 创建两个分离的小区域
        mask = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask[:, :, 2:4, 2:4] = True  # 左上角
        mask[:, :, 12:14, 12:14] = True  # 右下角
        # 单结构面积 4 / 总稳定面积 8 = 0.5
        struct = self._make_structure(mask, lifetime=10, turnover=0.05,
                                    connectivity_ratio=0.5, boundary_closure_score=0.0)

        sv = self.validator.validate_single(0, struct, [])
        assert sv.closure_ratio < 1.0  # 不完全连通
        assert sv.closure_ratio == pytest.approx(0.5, abs=0.01)

    def test_interaction_detection(self):
        """相邻结构应检测到相互作用"""
        mask1 = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask1[:, :, 4:8, 4:8] = True
        struct1 = self._make_structure(mask1, lifetime=10, turnover=0.05)

        mask2 = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask2[:, :, 4:8, 8:12] = True  # 紧邻 struct1
        struct2 = self._make_structure(mask2, lifetime=10, turnover=0.05)

        detected, score = self.validator._check_interaction([struct1, struct2])
        assert detected is True
        assert score > 0

    def test_no_interaction_distant(self):
        """远离的结构不应检测到相互作用"""
        mask1 = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask1[:, :, 1:3, 1:3] = True
        struct1 = self._make_structure(mask1, lifetime=10, turnover=0.05)

        mask2 = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask2[:, :, 13:15, 13:15] = True
        struct2 = self._make_structure(mask2, lifetime=10, turnover=0.05)

        detected, score = self.validator._check_interaction([struct1, struct2])
        assert detected is False
        assert score == 0.0

    def test_boundary_stability(self):
        """边界稳定性应可测量"""
        mask = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask[:, :, 4:12, 4:12] = True
        struct = self._make_structure(mask, lifetime=10, turnover=0.05)

        # 创建稳定的历史（值变化很小）
        history = [torch.ones(1, 1, 16, 16) * 0.5 for _ in range(16)]

        stability = self.validator._measure_boundary_stability(struct, history)
        assert isinstance(stability, float)
        assert stability >= 0

    def test_report_summary(self):
        """报告应包含可读摘要"""
        mask = torch.zeros(1, 1, 16, 16, dtype=torch.bool)
        mask[:, :, 4:12, 4:12] = True
        struct = self._make_structure(mask, lifetime=10, turnover=0.05)

        report = self.validator.validate([struct], [])
        assert "Structure Validation Report" in report.summary
        assert "Lifetime" in report.summary
        assert "Boundary" in report.summary
        assert "Closure" in report.summary
        assert "Turnover" in report.summary
