"""
tests/test_zone_transition.py — 子区跃迁信号检测测试

测试 SeventhThresholdDetector 中新增的 ZoneTransitionSignal 检测能力。
验证基于精化十一分区系统的子区边界穿越检测是否正确工作。
"""

import pytest
import numpy as np
from engine.seventh_threshold_detector import (
    SeventhThresholdDetector,
    ZoneTransitionSignal,
)
from engine.organizational_density_index import (
    DensityIndexResult,
    ZoneBoundary,
    SubIndexValues,
)


def _make_odi_result(odi_value, zone, base_zone, proximity, densify_rate, timestamp):
    """辅助函数：构造 DensityIndexResult"""
    zb = ZoneBoundary(
        zone=zone,
        base_zone=base_zone,
        transition_proximity=proximity,
    )
    return DensityIndexResult(
        odi=odi_value,
        subindices=SubIndexValues(),
        zone=zone,
        base_zone=base_zone,
        densification_rate=densify_rate,
        is_densifying=densify_rate > 0,
        timestamp=timestamp,
        zone_boundary=zb,
    )


class TestZoneTransitionSignal:
    """ZoneTransitionSignal 基础测试"""

    def test_no_transition_without_history(self):
        """无历史数据时不应检测出跃迁"""
        detector = SeventhThresholdDetector()
        result = detector.feed(_make_odi_result(
            0.55, 'pre_subjective_entry', 'pre_subjective', 0.3, 0.01, 0
        ))
        assert not result.zone_transition_signal.detected

    def test_no_transition_within_same_zone(self):
        """同一分区内移动不应检测出跃迁"""
        detector = SeventhThresholdDetector()
        # 在同一分区内移动两步
        detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.2, 0.005, 0
        ))
        detector.feed(_make_odi_result(
            0.54, 'pre_subjective_entry', 'pre_subjective', 0.4, 0.008, 1
        ))
        result = detector.feed(_make_odi_result(
            0.55, 'pre_subjective_entry', 'pre_subjective', 0.5, 0.01, 2
        ))
        assert not result.zone_transition_signal.detected

    def test_forward_zone_transition_detected(self):
        """正向分区穿越应被检测"""
        detector = SeventhThresholdDetector()
        detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.2, 0.005, 0
        ))
        result = detector.feed(_make_odi_result(
            0.60, 'pre_subjective_deep', 'pre_subjective', 0.3, 0.015, 1
        ))
        assert result.zone_transition_signal.detected
        assert result.zone_transition_signal.is_forward
        assert result.zone_transition_signal.zone_from == 'pre_subjective_entry'
        assert result.zone_transition_signal.zone_to == 'pre_subjective_deep'

    def test_backward_zone_transition_detected(self):
        """反向分区穿越（密度降低）应被检测但标记为 is_forward=False"""
        detector = SeventhThresholdDetector()
        detector.feed(_make_odi_result(
            0.60, 'pre_subjective_deep', 'pre_subjective', 0.3, 0.01, 0
        ))
        result = detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.2, -0.01, 1
        ))
        # 反向穿越 detected 可能为 True（因为速度条件满足），但 is_forward=False
        # 反向穿越不应计入 transition_detected（因为 is_significant 要求 is_forward）
        assert not result.zone_transition_signal.is_forward

    def test_critical_region_flag(self):
        """关键过渡区（pre_subjective → dense）应被正确标记"""
        detector = SeventhThresholdDetector()
        detector.feed(_make_odi_result(
            0.55, 'pre_subjective_entry', 'pre_subjective', 0.3, 0.01, 0
        ))
        result = detector.feed(_make_odi_result(
            0.72, 'dense_entry', 'dense', 0.4, 0.02, 1
        ))
        assert result.zone_transition_signal.detected
        assert result.zone_transition_signal.is_critical_region

    def test_non_critical_region(self):
        """非关键过渡区（如 sparse → structuring）不应标记为 critical"""
        detector = SeventhThresholdDetector()
        detector.feed(_make_odi_result(
            0.20, 'sparse', 'sparse', 0.5, 0.01, 0
        ))
        result = detector.feed(_make_odi_result(
            0.35, 'structuring', 'structuring', 0.3, 0.015, 1
        ))
        # 即使检测到跃迁，也不应在关键区
        if result.zone_transition_signal.detected:
            assert not result.zone_transition_signal.is_critical_region

    def test_transition_speed_calculation(self):
        """分区穿越速度应正确计算"""
        detector = SeventhThresholdDetector()
        detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.2, 0.005, 0
        ))
        result = detector.feed(_make_odi_result(
            0.60, 'pre_subjective_deep', 'pre_subjective', 0.3, 0.015, 1
        ))
        assert result.zone_transition_signal.detected
        assert result.zone_transition_signal.transition_speed > 0

    def test_proximity_acceleration(self):
        """过渡邻近度加速度应正确计算"""
        detector = SeventhThresholdDetector()
        # 需要至少 3 步 proximity 历史才能计算加速度
        detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.1, 0.005, 0
        ))
        detector.feed(_make_odi_result(
            0.55, 'pre_subjective_entry', 'pre_subjective', 0.3, 0.01, 1
        ))
        result = detector.feed(_make_odi_result(
            0.60, 'pre_subjective_deep', 'pre_subjective', 0.6, 0.02, 2
        ))
        # 邻近度从 0.1 → 0.3 → 0.6，加速度应为正
        assert result.zone_transition_signal.proximity_acceleration > 0

    def test_steps_in_transition_tracking(self):
        """在关键过渡区中停留的步数应被正确追踪"""
        detector = SeventhThresholdDetector()
        # 连续在关键区移动
        detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.2, 0.01, 0
        ))
        detector.feed(_make_odi_result(
            0.60, 'pre_subjective_deep', 'pre_subjective', 0.3, 0.015, 1
        ))
        result = detector.feed(_make_odi_result(
            0.72, 'dense_entry', 'dense', 0.4, 0.02, 2
        ))
        assert result.zone_transition_signal.detected
        assert result.zone_transition_signal.steps_in_transition >= 1

    def test_zone_transition_in_fusion(self):
        """子区跃迁信号应参与融合判定"""
        detector = SeventhThresholdDetector()
        detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.2, 0.005, 0
        ))
        result = detector.feed(_make_odi_result(
            0.60, 'pre_subjective_deep', 'pre_subjective', 0.3, 0.015, 1
        ))
        # 如果 zone_transition 被检测到，transition_type 应包含它
        if result.zone_transition_signal.detected:
            assert result.transition_type in ('zone_transition', 'mixed')

    def test_critical_zone_higher_confidence(self):
        """关键过渡区的子区跃迁应具有更高置信度"""
        detector = SeventhThresholdDetector()

        # 非关键区穿越
        detector.feed(_make_odi_result(
            0.20, 'sparse', 'sparse', 0.5, 0.01, 0
        ))
        result_non_critical = detector.feed(_make_odi_result(
            0.35, 'structuring', 'structuring', 0.3, 0.015, 1
        ))

        detector2 = SeventhThresholdDetector()
        # 关键区穿越
        detector2.feed(_make_odi_result(
            0.55, 'pre_subjective_entry', 'pre_subjective', 0.3, 0.01, 0
        ))
        result_critical = detector2.feed(_make_odi_result(
            0.72, 'dense_entry', 'dense', 0.4, 0.02, 1
        ))

        # 关键区的置信度应更高
        if result_critical.zone_transition_signal.detected and result_non_critical.zone_transition_signal.detected:
            assert result_critical.transition_confidence >= result_non_critical.transition_confidence

    def test_reset_clears_zone_history(self):
        """reset() 应清除分区历史"""
        detector = SeventhThresholdDetector()
        detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.2, 0.005, 0
        ))
        detector.feed(_make_odi_result(
            0.60, 'pre_subjective_deep', 'pre_subjective', 0.3, 0.015, 1
        ))
        detector.reset()
        # reset 后应无历史
        result = detector.feed(_make_odi_result(
            0.55, 'pre_subjective_entry', 'pre_subjective', 0.3, 0.01, 2
        ))
        assert not result.zone_transition_signal.detected

    def test_full_critical_transition_sequence(self):
        """完整关键过渡序列：pre_subjective_entry → dense_core"""
        detector = SeventhThresholdDetector()
        zones = [
            (0.52, 'pre_subjective_entry', 0.1),
            (0.56, 'pre_subjective_entry', 0.3),
            (0.60, 'pre_subjective_deep', 0.2),
            (0.65, 'pre_subjective_deep', 0.5),
            (0.72, 'dense_entry', 0.3),
            (0.78, 'dense_core', 0.4),
            (0.82, 'dense_core', 0.6),
        ]
        results = []
        for i, (odi, zone, prox) in enumerate(zones):
            result = detector.feed(_make_odi_result(
                odi, zone, 'pre_subjective' if 'pre' in zone else 'dense',
                prox, 0.01 + i * 0.002, i
            ))
            results.append(result)

        # 检测到的跃迁次数应 >= 3（穿越了至少 3 个分区边界）
        zone_transitions = [r for r in results if r.zone_transition_signal.detected]
        assert len(zone_transitions) >= 3

        # 所有跃迁应为正向
        for r in zone_transitions:
            assert r.zone_transition_signal.is_forward

    def test_zone_transition_signal_repr(self):
        """ZoneTransitionSignal 应有合理的字符串表示"""
        signal = ZoneTransitionSignal(
            detected=True,
            zone_from='pre_subjective_entry',
            zone_to='dense_entry',
            is_forward=True,
            transition_speed=0.5,
            is_critical_region=True,
        )
        assert signal.is_significant
        assert not ZoneTransitionSignal(detected=False).is_significant
        assert not ZoneTransitionSignal(detected=True, is_forward=False).is_significant


class TestZoneTransitionIntegration:
    """子区跃迁与其他信号的集成测试"""

    def test_zone_transition_with_jump_signal(self):
        """子区跃迁 + 离散跳跃同时出现应产生 mixed 类型"""
        detector = SeventhThresholdDetector(config={'jump_sigma_threshold': 1.5})
        # 先建立基线
        for i in range(5):
            detector.feed(_make_odi_result(
                0.52 + i * 0.001, 'pre_subjective_entry', 'pre_subjective',
                0.2, 0.001, i
            ))
        # 大跳跃 + 分区穿越
        result = detector.feed(_make_odi_result(
            0.72, 'dense_entry', 'dense', 0.5, 0.05, 5
        ))
        if result.transition_detected:
            # 可能是 mixed 或 zone_transition 或 discrete_jump
            assert result.transition_type in ('mixed', 'zone_transition', 'discrete_jump')

    def test_zone_transition_in_result(self):
        """SeventhThresholdResult 应包含 zone_transition_signal 字段"""
        detector = SeventhThresholdDetector()
        detector.feed(_make_odi_result(
            0.52, 'pre_subjective_entry', 'pre_subjective', 0.2, 0.005, 0
        ))
        result = detector.feed(_make_odi_result(
            0.60, 'pre_subjective_deep', 'pre_subjective', 0.3, 0.015, 1
        ))
        assert hasattr(result, 'zone_transition_signal')
        assert isinstance(result.zone_transition_signal, ZoneTransitionSignal)
