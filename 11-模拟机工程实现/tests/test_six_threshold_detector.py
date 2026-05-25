"""
tests/test_six_threshold_detector.py — 六阈值同步检测器测试

覆盖：
1. 全部阈值达标 → all_met
2. 部分阈值达标 → not all_met, 正确识别瓶颈
3. 零输入 → 全部未达标
4. 结构相似性计算
5. Gini系数计算
6. 历史记录和摘要
7. 自定义阈值参数
8. reset 功能
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.six_threshold_detector import SixThresholdDetector, ThresholdStatus


class TestSixThresholdDetector:

    def test_all_met(self):
        """所有阈值都达标 → all_met = True"""
        detector = SixThresholdDetector()
        result = detector.detect(
            active_exchanges=8,
            total_boundary_edges=10,          # 3.1: 0.8 > 0.3 ✓
            rebuild_success_count=8,
            perturbation_count=10,            # 3.2: 0.8 > 0.5 ✓
            bias_recursion_depth=5.0,         # 3.3: 5.0 > 2.0 ✓
            replicated_pattern=torch.tensor([1.0, 0.0, 1.0, 0.0]),
            original_pattern=torch.tensor([1.0, 0.0, 1.0, 0.0]),  # 3.4: 1.0 > 0.6 ✓
            variant_continuation_probs={'v1': 0.9, 'v2': 0.1},     # 3.5: 0.8 > 0.2 ✓
            component_contributions={'c1': 10.0, 'c2': 1.0},       # 3.6: Gini ≈ 0.41 > 0.3 ✓
        )
        assert result.all_met is True
        assert result.n_met == 6
        assert result.bottleneck is None

    def test_none_met(self):
        """所有阈值都不达标 → all_met = False"""
        detector = SixThresholdDetector()
        result = detector.detect(
            active_exchanges=0,
            total_boundary_edges=10,
            rebuild_success_count=0,
            perturbation_count=10,
            bias_recursion_depth=0.0,
            replicated_pattern=None,
            original_pattern=None,
            variant_continuation_probs=None,
            component_contributions=None,
        )
        assert result.all_met is False
        assert result.n_met == 0

    def test_partial_met(self):
        """部分阈值达标 → 正确计数和识别瓶颈"""
        detector = SixThresholdDetector()
        result = detector.detect(
            active_exchanges=8,
            total_boundary_edges=10,          # 3.1: 0.8 > 0.3 ✓
            rebuild_success_count=2,
            perturbation_count=10,            # 3.2: 0.2 < 0.5 ✗
            bias_recursion_depth=1.0,         # 3.3: 1.0 < 2.0 ✗
            replicated_pattern=torch.tensor([1.0, 0.0]),
            original_pattern=torch.tensor([0.0, 1.0]),  # 3.4: ≈ 0 < 0.6 ✗
            variant_continuation_probs={'v1': 0.6, 'v2': 0.5},  # 3.5: 0.1 < 0.2 ✗
            component_contributions={'c1': 5.0, 'c2': 5.0},      # 3.6: Gini = 0 < 0.3 ✗
        )
        assert result.all_met is False
        assert result.n_met == 1
        assert result.bottleneck is not None

    def test_bottleneck_identification(self):
        """瓶颈应该是差距最大的未达标阈值"""
        detector = SixThresholdDetector()
        # 3.1 差 0.2 (0.1 vs 0.3), 3.2 差 0.4 (0.1 vs 0.5)
        result = detector.detect(
            active_exchanges=1,
            total_boundary_edges=10,          # 3.1: 0.1, gap=0.2
            rebuild_success_count=1,
            perturbation_count=10,            # 3.2: 0.1, gap=0.4 ← biggest gap
            bias_recursion_depth=0.5,         # 3.3: 0.5, gap=1.5
        )
        assert result.all_met is False
        # 3.3 gap=1.5 is largest
        assert result.bottleneck == '3.3'

    def test_structural_similarity_identical(self):
        """相同模式的相似度为1"""
        detector = SixThresholdDetector()
        pattern = torch.tensor([1.0, 0.0, 1.0, 0.0])
        result = detector.detect(
            replicated_pattern=pattern,
            original_pattern=pattern.clone(),
        )
        # 3.4 should be met (similarity = 1.0 > 0.6)
        status_34 = [s for s in result.threshold_statuses if s.threshold_id == '3.4'][0]
        assert status_34.value == pytest.approx(1.0, abs=1e-6)
        assert status_34.is_met is True

    def test_structural_similarity_orthogonal(self):
        """正交模式的相似度接近0"""
        detector = SixThresholdDetector()
        original = torch.tensor([1.0, 0.0])
        replicated = torch.tensor([0.0, 1.0])
        result = detector.detect(
            replicated_pattern=replicated,
            original_pattern=original,
        )
        status_34 = [s for s in result.threshold_statuses if s.threshold_id == '3.4'][0]
        assert status_34.value == pytest.approx(0.0, abs=1e-6)
        assert status_34.is_met is False

    def test_structural_similarity_different_sizes(self):
        """不同尺寸的模式应该能处理（截断到最小长度）"""
        detector = SixThresholdDetector()
        original = torch.tensor([1.0, 0.0, 1.0])
        replicated = torch.tensor([1.0, 0.0])
        result = detector.detect(
            replicated_pattern=replicated,
            original_pattern=original,
        )
        status_34 = [s for s in result.threshold_statuses if s.threshold_id == '3.4'][0]
        # 截断后 [1.0, 0.0] vs [1.0, 0.0] → similarity = 1.0
        assert status_34.value == pytest.approx(1.0, abs=1e-6)

    def test_gini_coefficient_uniform(self):
        """均匀分布的Gini系数为0"""
        detector = SixThresholdDetector()
        result = detector.detect(
            component_contributions={'c1': 5.0, 'c2': 5.0, 'c3': 5.0},
        )
        status_36 = [s for s in result.threshold_statuses if s.threshold_id == '3.6'][0]
        assert status_36.value == pytest.approx(0.0, abs=1e-6)

    def test_gini_coefficient_max_unequal(self):
        """极度不均匀的Gini系数接近1"""
        detector = SixThresholdDetector()
        result = detector.detect(
            component_contributions={'c1': 100.0, 'c2': 0.001},
        )
        status_36 = [s for s in result.threshold_statuses if s.threshold_id == '3.6'][0]
        assert status_36.value > 0.4  # 接近 0.5 for 2 elements

    def test_custom_thresholds(self):
        """自定义阈值参数覆盖默认值"""
        detector = SixThresholdDetector(thresholds={
            '3.1_interface_regulation': 0.9,  # 很高的阈值
        })
        result = detector.detect(
            active_exchanges=8,
            total_boundary_edges=10,  # 0.8 < 0.9 → not met
        )
        status_31 = [s for s in result.threshold_statuses if s.threshold_id == '3.1'][0]
        assert status_31.is_met is False
        assert status_31.threshold == 0.9

    def test_history_tracking(self):
        """检测历史正确记录"""
        detector = SixThresholdDetector()
        detector.detect()
        detector.detect()
        detector.detect()
        assert len(detector._history) == 3
        summary = detector.get_history_summary()
        assert summary['n_detections'] == 3

    def test_is_all_met_property(self):
        """is_all_met 属性反映最近一次检测结果"""
        detector = SixThresholdDetector()
        assert detector.is_all_met is False  # 无检测记录

        detector.detect()  # 全部默认 → 不达标
        assert detector.is_all_met is False

    def test_current_result_property(self):
        """current_result 返回最近一次结果"""
        detector = SixThresholdDetector()
        assert detector.current_result is None

        result = detector.detect()
        assert detector.current_result is result

    def test_reset(self):
        """reset 清除所有状态"""
        detector = SixThresholdDetector()
        detector.detect()
        detector.detect()
        detector.reset()
        assert len(detector._history) == 0
        assert detector._step_count == 0
        assert detector.current_result is None

    def test_timestamp_auto_increment(self):
        """时间戳自动递增"""
        detector = SixThresholdDetector()
        r1 = detector.detect()
        r2 = detector.detect()
        r3 = detector.detect()
        assert r1.timestamp == 1
        assert r2.timestamp == 2
        assert r3.timestamp == 3

    def test_timestamp_explicit(self):
        """显式时间戳覆盖自动递增"""
        detector = SixThresholdDetector()
        r1 = detector.detect(timestamp=42)
        assert r1.timestamp == 42

    def test_selection_pressure_single_variant(self):
        """单变体无法计算选择压力 → 0"""
        detector = SixThresholdDetector()
        result = detector.detect(
            variant_continuation_probs={'v1': 0.9},
        )
        status_35 = [s for s in result.threshold_statuses if s.threshold_id == '3.5'][0]
        assert status_35.value == 0.0

    def test_boundary_edges_zero(self):
        """边界边数为0时界面调节度为0"""
        detector = SixThresholdDetector()
        result = detector.detect(
            active_exchanges=0,
            total_boundary_edges=0,
        )
        status_31 = [s for s in result.threshold_statuses if s.threshold_id == '3.1'][0]
        assert status_31.value == 0.0

    def test_threshold_status_repr(self):
        """ThresholdStatus 的字符串表示"""
        s = ThresholdStatus(threshold_id='3.1', name='界面调节度',
                            value=0.5, threshold=0.3, is_met=True)
        repr_str = repr(s)
        assert '✓' in repr_str
        assert '3.1' in repr_str
        assert '界面调节度' in repr_str
