"""test_difference_layers.py — 差异分层量化测试"""

import pytest
import torch
from engine.difference_layers import DifferenceLayerAnalyzer, DifferenceLayerReport


class TestDifferenceLayerAnalyzer:

    def test_uniform_state(self):
        """均匀状态：D0=0, D2=0"""
        analyzer = DifferenceLayerAnalyzer()
        state = torch.ones(1, 1, 8, 8) * 0.5
        report = analyzer.analyze(state)
        assert report.d0_distinguishability == pytest.approx(0.0, abs=0.05)
        assert report.d2_distributional == pytest.approx(0.0, abs=0.05)

    def test_random_state(self):
        """随机状态：D0高, D2高"""
        torch.manual_seed(42)
        analyzer = DifferenceLayerAnalyzer()
        state = torch.randn(1, 1, 16, 16)
        report = analyzer.analyze(state)
        assert report.d0_distinguishability > 0.5
        assert report.d2_distributional > 0.1

    def test_structured_state(self):
        """有结构状态：D1高"""
        analyzer = DifferenceLayerAnalyzer()
        state = torch.zeros(1, 1, 16, 16)
        state[0, 0, 4:12, 4:12] = 1.0  # 中心方块
        report = analyzer.analyze(state)
        assert report.d1_structural >= 0.3

    def test_d4_event_detection(self):
        """D4：突变检测"""
        analyzer = DifferenceLayerAnalyzer()
        state = torch.ones(1, 1, 8, 8) * 0.5
        # 平稳历史
        history = [torch.ones(1, 1, 8, 8) * (0.5 + i * 0.001) for i in range(10)]
        report_normal = analyzer.analyze(state, history)
        assert report_normal.d4_event < 0.3
        # 突变历史
        history[-1] = torch.randn(1, 1, 8, 8)  # 最后一步突变
        report_spike = analyzer.analyze(state, history)
        assert report_spike.d4_event > report_normal.d4_event

    def test_total_density(self):
        """综合差异密度"""
        report = DifferenceLayerReport(
            d0_distinguishability=0.5,
            d1_structural=0.5,
            d2_distributional=0.5,
            d4_event=0.5,
        )
        assert report.total_difference_density == pytest.approx(0.5)

    def test_critical_threshold(self):
        """临界差异密度"""
        report_low = DifferenceLayerReport(d0_distinguishability=0.3, d1_structural=0.3,
                                            d2_distributional=0.3, d4_event=0.3)
        assert not report_low.is_critical
        report_high = DifferenceLayerReport(d0_distinguishability=0.9, d1_structural=0.9,
                                             d2_distributional=0.8, d4_event=0.7)
        assert report_high.is_critical


class TestDifferenceLayerReport:

    def test_str(self):
        report = DifferenceLayerReport(
            d0_distinguishability=0.5, d1_structural=0.3,
            d2_distributional=0.7, d4_event=0.2,
        )
        s = str(report)
        assert "D0" in s
        assert "D1" in s
        assert "Kt" in s
