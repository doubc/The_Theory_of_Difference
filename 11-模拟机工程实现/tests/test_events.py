"""
test_events.py — 事件分类器 + 底图事件系统测试
"""

import pytest
import torch
from engine.events import (
    EventClassifier, EventType, PossibilitySpace,
    BaseMapOperator, StructuralEvent, BaseMapEvent,
)


# =============================================================================
# PossibilitySpace 测试
# =============================================================================

class TestPossibilitySpace:

    def test_from_uniform_state(self):
        """均匀状态：activity=mean, volatility=0"""
        state = torch.ones(1, 1, 8, 8) * 0.5
        ps = PossibilitySpace.from_state(state)
        assert ps.mean == pytest.approx(0.5, abs=1e-4)
        assert ps.activity == pytest.approx(0.5, abs=1e-4)
        assert ps.std == pytest.approx(0.0, abs=1e-4)
        assert ps.volatility == 0.0

    def test_from_random_state(self):
        """随机状态：std > 0"""
        torch.manual_seed(42)
        state = torch.randn(1, 1, 16, 16)
        ps = PossibilitySpace.from_state(state)
        assert ps.std > 0.0
        assert 0.0 < ps.mean < 1.0

    def test_volatility_from_history(self):
        """有历史时计算波动度"""
        state = torch.ones(1, 1, 4, 4) * 0.5
        history = [torch.ones(1, 1, 4, 4) * (0.5 + i * 0.1) for i in range(5)]
        ps = PossibilitySpace.from_state(state, history)
        assert ps.volatility > 0.0

    def test_persistence_high(self):
        """高持续性：连续相似状态"""
        state = torch.ones(1, 1, 4, 4) * 0.5
        history = [torch.ones(1, 1, 4, 4) * 0.5 for _ in range(10)]
        ps = PossibilitySpace.from_state(state, history)
        assert ps.persistence > 0.9

    def test_persistence_low(self):
        """低持续性：随机状态"""
        torch.manual_seed(42)
        state = torch.randn(1, 1, 4, 4)
        history = [torch.randn(1, 1, 4, 4) for _ in range(10)]
        ps = PossibilitySpace.from_state(state, history)
        assert ps.persistence < 0.5

    def test_distance(self):
        """两个不同可能性空间的距离 > 0"""
        ps1 = PossibilitySpace(mean=0.5, std=0.1, activity=0.5,
                               volatility=0.01, persistence=0.9, unique_ratio=0.1)
        ps2 = PossibilitySpace(mean=0.8, std=0.3, activity=0.8,
                               volatility=0.2, persistence=0.3, unique_ratio=0.5)
        d = ps1.distance_to(ps2)
        assert d > 0.0

    def test_distance_self(self):
        """与自身距离为0"""
        ps = PossibilitySpace(mean=0.5, std=0.1)
        assert ps.distance_to(ps) == pytest.approx(0.0, abs=1e-6)


# =============================================================================
# EventClassifier 测试
# =============================================================================

class TestEventClassifier:

    def test_structural_event(self):
        """微小变化 → 结构事件"""
        clf = EventClassifier(base_map_threshold=0.3)
        s1 = torch.ones(1, 1, 8, 8) * 0.5
        s2 = s1 + torch.randn_like(s1) * 0.01  # 微小扰动
        event = clf.classify(s1, s2, step=0)
        assert isinstance(event, StructuralEvent)
        assert clf.structural_count == 1
        assert clf.base_map_count == 0

    def test_base_map_event(self):
        """大幅变化 → 底图事件"""
        clf = EventClassifier(base_map_threshold=0.3)
        s1 = torch.ones(1, 1, 8, 8) * 0.5
        s2 = torch.randn_like(s1)  # 完全不同
        event = clf.classify(s1, s2, step=0)
        assert isinstance(event, BaseMapEvent)
        assert clf.base_map_count == 1

    def test_external_trigger(self):
        """外部触发 → 底图事件（即使变化小）"""
        clf = EventClassifier(base_map_threshold=0.3)
        s1 = torch.ones(1, 1, 8, 8) * 0.5
        s2 = s1.clone()
        event = clf.classify(s1, s2, step=0, external_trigger="manual reset")
        assert isinstance(event, BaseMapEvent)
        assert "manual reset" in event.trigger

    def test_intensity(self):
        """底图事件强度在 [0, 1]"""
        clf = EventClassifier(base_map_threshold=0.3)
        s1 = torch.zeros(1, 1, 8, 8)
        s2 = torch.ones(1, 1, 8, 8) * 0.6  # delta=0.6, threshold=0.3
        event = clf.classify(s1, s2, step=0)
        assert isinstance(event, BaseMapEvent)
        assert event.intensity == pytest.approx(1.0)  # capped at 1.0

    def test_summary(self):
        """统计摘要"""
        clf = EventClassifier(base_map_threshold=0.3)
        s1 = torch.ones(1, 1, 8, 8) * 0.5
        for i in range(5):
            s2 = s1 + torch.randn_like(s1) * 0.01
            clf.classify(s1, s2, step=i)
            s1 = s2
        s2 = torch.randn_like(s1)
        clf.classify(s1, s2, step=5)
        summary = clf.summary()
        assert "6 total" in summary
        assert "5 structural" in summary
        assert "1 base-map" in summary


# =============================================================================
# BaseMapOperator 测试
# =============================================================================

class TestBaseMapOperator:

    def test_region_reset(self):
        """区域重置：指定区域被清零"""
        state = torch.ones(1, 1, 8, 8)
        region = torch.zeros(1, 1, 8, 8, dtype=torch.bool)
        region[0, 0, :4, :4] = True  # 左上象限
        result = BaseMapOperator.region_reset(state, region, value=0.0)
        assert result[0, 0, :4, :4].sum().item() == pytest.approx(0.0)
        assert result[0, 0, 4:, 4:].sum().item() == pytest.approx(16.0)  # 右下不变

    def test_noise_injection(self):
        """噪声注入：状态改变"""
        torch.manual_seed(42)
        state = torch.ones(1, 1, 8, 8) * 0.5
        result = BaseMapOperator.noise_injection(state, intensity=0.5)
        assert not torch.allclose(state, result)

    def test_noise_injection_region(self):
        """区域性噪声：只影响指定区域"""
        torch.manual_seed(42)
        state = torch.ones(1, 1, 8, 8) * 0.5
        region = torch.zeros(1, 1, 8, 8, dtype=torch.bool)
        region[0, 0, :4, :] = True
        result = BaseMapOperator.noise_injection(state, intensity=0.5, region=region)
        # 区域内应改变
        assert not torch.allclose(state[0, 0, :4, :], result[0, 0, :4, :])
        # 区域外应不变
        assert torch.allclose(state[0, 0, 4:, :], result[0, 0, 4:, :])

    def test_boundary_shift(self):
        """边界条件突变"""
        state = torch.ones(1, 1, 4, 4) * 0.5
        result = BaseMapOperator.boundary_shift(state, shift=0.3)
        assert result.mean().item() == pytest.approx(0.8, abs=1e-4)

    def test_activity_compression(self):
        """活动度压缩：向均值靠拢"""
        state = torch.tensor([[[[0.1, 0.9]]]])
        result = BaseMapOperator.activity_compression(state, factor=0.5)
        mean = state.mean().item()
        # 压缩后更接近均值
        assert abs(result[0, 0, 0, 0].item() - mean) < abs(state[0, 0, 0, 0].item() - mean)
        assert abs(result[0, 0, 0, 1].item() - mean) < abs(state[0, 0, 0, 1].item() - mean)

    def test_activity_expansion(self):
        """活动度扩张：远离均值"""
        state = torch.tensor([[[[0.4, 0.6]]]])
        result = BaseMapOperator.activity_expansion(state, factor=2.0)
        mean = state.mean().item()
        # 扩张后更远离均值
        assert abs(result[0, 0, 0, 0].item() - mean) >= abs(state[0, 0, 0, 0].item() - mean)


# =============================================================================
# 集成测试
# =============================================================================

class TestIntegration:

    def test_event_sequence(self):
        """模拟一次包含结构事件和底图事件的序列"""
        clf = EventClassifier(base_map_threshold=0.3)
        state = torch.ones(1, 1, 8, 8) * 0.5

        # 3步结构事件
        for i in range(3):
            next_state = state + torch.randn_like(state) * 0.01
            event = clf.classify(state, next_state, step=i)
            assert isinstance(event, StructuralEvent)
            state = next_state

        # 1步底图事件
        new_state = BaseMapOperator.noise_injection(state, intensity=0.5)
        event = clf.classify(state, new_state, step=3)
        assert isinstance(event, BaseMapEvent)

        assert clf.structural_count == 3
        assert clf.base_map_count == 1

    def test_possibility_space_tracking(self):
        """可能性空间随演化变化"""
        clf = EventClassifier()
        state = torch.ones(1, 1, 8, 8) * 0.5
        history = [state]

        for i in range(10):
            next_state = state + torch.randn_like(state) * 0.02
            clf.classify(state, next_state, step=i, history=history)
            history.append(next_state)
            state = next_state

        # 应有10个可能性空间记录
        assert len(clf.possibility_spaces) == 10
        # 第一个和最后一个应不同
        assert clf.possibility_spaces[0].distance_to(clf.possibility_spaces[-1]) > 0.0
