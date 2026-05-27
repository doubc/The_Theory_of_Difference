"""
tests/test_unsealing.py — 解封机制单元测试

覆盖场景：
1. Level 0 → Level 1 解封升级
2. Level 1 → Level 2 → Level 3 逐级升级
3. 等级回退（降级）
4. 等级不变（无事件）
5. 高语义承载容量计算
6. 事件历史查询
7. 按等级分组查询
8. 重置功能
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import torch
from engine.unsealing_mechanism import (
    UnsealingMechanism,
    UnsealingEvent,
    InterfacePatternStability,
    InterfaceExchangeRecord,
)
from engine.pre_subjectivity_convergence import ConvergenceResult


# ─── 测试辅助：构造 ConvergenceResult ───

def make_convergence(
    converged: bool = True,
    six_thresholds_met: bool = True,
    coupling_strength_met: bool = True,
    stability_met: bool = True,
    semantic_firewall_passed: bool = True,
    n_coupled_pairs: int = 15,
    min_coupling: float = 0.5,
    stability_score: float = 0.7,
    timestamp: int = 0,
) -> ConvergenceResult:
    """构造一个测试用的 ConvergenceResult"""
    return ConvergenceResult(
        converged=converged,
        six_thresholds_met=six_thresholds_met,
        coupling_strength_met=coupling_strength_met,
        stability_met=stability_met,
        semantic_firewall_passed=semantic_firewall_passed,
        n_coupled_pairs=n_coupled_pairs,
        min_coupling=min_coupling,
        stability_score=stability_score,
        timestamp=timestamp,
    )


class TestUnsealingMechanism:
    """UnsealingMechanism 单元测试"""

    def test_level_0_to_level_1(self):
        """未达前主体态 → 达到 Level 1 条件"""
        mech = UnsealingMechanism(
            l1_coupling_threshold=0.3,
            l1_stability_threshold=0.5,
        )
        # 初始状态：Level 0
        assert mech.get_current_level(1) == 0
        assert mech.get_level_name(1) == "封闭"

        # 构造刚好达到 Level 1 的收束结果
        result = make_convergence(
            min_coupling=0.35,  # >= 0.3
            stability_score=0.55,  # >= 0.5
        )

        event = mech.evaluate(structure_id=1, convergence_result=result, timestamp=100)

        assert event is not None
        assert event.unsealing_level == 1
        assert event.previous_level == 0
        assert event.reason.startswith("解封升级")
        assert event.high_semantic_capacity > 0.0
        assert mech.get_current_level(1) == 1
        assert mech.get_level_name(1) == "边界开放"

    def test_level_1_to_level_2_to_level_3(self):
        """逐级升级：Level 1 → 2 → 3"""
        mech = UnsealingMechanism(
            l1_coupling_threshold=0.3, l1_stability_threshold=0.5,
            l2_coupling_threshold=0.5, l2_stability_threshold=0.7,
            l3_coupling_threshold=0.7, l3_stability_threshold=0.85,
        )

        # Level 1
        r1 = make_convergence(min_coupling=0.4, stability_score=0.6)
        e1 = mech.evaluate(1, r1, timestamp=100)
        assert e1.unsealing_level == 1

        # Level 2
        r2 = make_convergence(min_coupling=0.55, stability_score=0.75)
        e2 = mech.evaluate(1, r2, timestamp=200)
        assert e2 is not None
        assert e2.unsealing_level == 2
        assert e2.previous_level == 1

        # Level 3
        r3 = make_convergence(min_coupling=0.75, stability_score=0.9)
        e3 = mech.evaluate(1, r3, timestamp=300)
        assert e3 is not None
        assert e3.unsealing_level == 3
        assert e3.previous_level == 2

        # 事件历史
        history = mech.get_event_history(structure_id=1)
        assert len(history) == 3

    def test_no_change_when_level_stable(self):
        """等级不变时不生成事件"""
        mech = UnsealingMechanism(
            l1_coupling_threshold=0.3, l1_stability_threshold=0.5,
        )

        # 第一次评估 → Level 1
        r1 = make_convergence(min_coupling=0.4, stability_score=0.6)
        e1 = mech.evaluate(1, r1, timestamp=100)
        assert e1 is not None

        # 第二次评估 → 仍为 Level 1（条件仍满足）
        r2 = make_convergence(min_coupling=0.45, stability_score=0.65)
        e2 = mech.evaluate(1, r2, timestamp=200)
        assert e2 is None  # 无变化

        assert mech.get_current_level(1) == 1
        assert len(mech.get_event_history(1)) == 1

    def test_level_degradation(self):
        """条件不满足时等级回退"""
        mech = UnsealingMechanism(
            l1_coupling_threshold=0.3, l1_stability_threshold=0.5,
            l2_coupling_threshold=0.5, l2_stability_threshold=0.7,
        )

        # 先升级到 Level 2
        r_high = make_convergence(min_coupling=0.6, stability_score=0.8)
        mech.evaluate(1, r_high, timestamp=100)
        assert mech.get_current_level(1) == 2

        # 条件恶化 → 降级到 Level 1
        r_low = make_convergence(min_coupling=0.35, stability_score=0.55)
        e = mech.evaluate(1, r_low, timestamp=200)

        assert e is not None
        assert e.unsealing_level == 1
        assert e.previous_level == 2
        assert "降级" in e.reason

    def test_level_0_when_not_converged(self):
        """未收束时强制 Level 0"""
        mech = UnsealingMechanism()

        # 构造未收束的结果
        r = ConvergenceResult(
            converged=False,
            six_thresholds_met=False,
            coupling_strength_met=False,
            stability_met=False,
            semantic_firewall_passed=True,
            min_coupling=0.9,  # 即使耦合很高
            stability_score=0.95,  # 即使稳定性很高
        )

        event = mech.evaluate(1, r, timestamp=100)
        # 因为 all_conditions_met = False，应返回 Level 0
        # 如果当前是 Level 0 则无事件
        assert event is None
        assert mech.get_current_level(1) == 0

        # 但如果之前是更高等级，应降级到 0
        mech._unsealing_levels[1] = 2  # 手动设为 Level 2
        event2 = mech.evaluate(1, r, timestamp=200)
        assert event2 is not None
        assert event2.unsealing_level == 0
        assert event2.previous_level == 2

    def test_high_semantic_capacity_calculation(self):
        """高语义承载容量计算"""
        mech = UnsealingMechanism()

        # 全满足：容量 = min_coupling × stability × 1.0
        r = make_convergence(min_coupling=0.8, stability_score=0.9, six_thresholds_met=True)
        event = mech.evaluate(1, r, timestamp=100)
        expected_capacity = min(1.0, 0.8 * 0.9 * 1.0)
        assert abs(event.high_semantic_capacity - expected_capacity) < 1e-6

        # six_thresholds 不满足：容量 = 0
        r2 = ConvergenceResult(
            converged=False, six_thresholds_met=False,
            coupling_strength_met=True, stability_met=True,
            semantic_firewall_passed=True,
            min_coupling=0.8, stability_score=0.9,
        )
        event2 = mech.evaluate(2, r2, timestamp=200)
        assert event2 is None  # 等级无变化（都是 0）

    def test_event_history_queries(self):
        """事件历史查询接口"""
        mech = UnsealingMechanism()

        # 多个结构的多个事件
        mech.evaluate(1, make_convergence(min_coupling=0.4, stability_score=0.6), 100)
        mech.evaluate(2, make_convergence(min_coupling=0.6, stability_score=0.8), 100)
        mech.evaluate(1, make_convergence(min_coupling=0.6, stability_score=0.8), 200)

        # 全部事件
        all_events = mech.get_event_history()
        assert len(all_events) == 3

        # 单个结构事件
        struct1_events = mech.get_event_history(structure_id=1)
        assert len(struct1_events) == 2
        assert all(e.structure_id == 1 for e in struct1_events)

    def test_get_structures_by_level(self):
        """按解封等级分组"""
        mech = UnsealingMechanism(
            l1_coupling_threshold=0.3, l1_stability_threshold=0.5,
            l2_coupling_threshold=0.5, l2_stability_threshold=0.7,
        )

        # structure 1 → Level 1
        mech.evaluate(1, make_convergence(min_coupling=0.4, stability_score=0.6), 100)
        # structure 2 → Level 2
        mech.evaluate(2, make_convergence(min_coupling=0.6, stability_score=0.8), 100)
        # structure 3 → Level 0 (未评估，默认 — 不在分组中，因为 get_structures_by_level
        # 只返回有结构的等级，Level 0 的 structure 3 从未被 evaluate 过)
        # structure 4 → Level 1
        mech.evaluate(4, make_convergence(min_coupling=0.35, stability_score=0.55), 100)
        # structure 5 → Level 0 (显式降级到 0)
        mech._unsealing_levels[5] = 0  # 手动设置 Level 0

        grouped = mech.get_structures_by_level()

        # get_structures_by_level 过滤空列表，所以只有被 evaluate 过的等级才出现
        # structure 3 从未 evaluate，不在 _unsealing_levels 中，所以不会出现在任何等级
        assert 1 in grouped  # structures 1, 4
        assert 2 in grouped  # structure 2
        assert 0 in grouped  # structure 5 (显式 Level 0)
        assert set(grouped[1]) == {1, 4}
        assert set(grouped[2]) == {2}
        assert set(grouped[0]) == {5}

    def test_get_all_structures_status(self):
        """所有结构状态摘要"""
        mech = UnsealingMechanism()
        mech.evaluate(1, make_convergence(min_coupling=0.4, stability_score=0.6), 100)
        mech.evaluate(2, make_convergence(min_coupling=0.6, stability_score=0.8), 200)

        status = mech.get_all_structures_status()

        assert 1 in status
        assert status[1]['level'] == 1
        assert status[1]['event_count'] == 1
        assert status[2]['level'] == 2
        assert status[2]['event_count'] == 1

    def test_reset(self):
        """重置所有状态"""
        mech = UnsealingMechanism()
        mech.evaluate(1, make_convergence(min_coupling=0.4, stability_score=0.6), 100)
        mech.evaluate(2, make_convergence(min_coupling=0.6, stability_score=0.8), 200)

        assert len(mech.get_event_history()) == 2
        assert mech.get_current_level(1) == 1

        mech.reset()

        assert len(mech.get_event_history()) == 0
        assert mech.get_current_level(1) == 0
        assert mech.get_current_level(2) == 0
        assert str(mech) == "UnsealingMechanism[empty]"

    def test_repr(self):
        """字符串表示"""
        mech = UnsealingMechanism()
        assert "empty" in str(mech)

        mech.evaluate(1, make_convergence(min_coupling=0.4, stability_score=0.6), 100)
        mech.evaluate(2, make_convergence(min_coupling=0.6, stability_score=0.8), 200)

        s = str(mech)
        assert "structures=2" in s
        assert "events=2" in s

    def test_unsealing_event_repr(self):
        """UnsealingEvent 字符串表示"""
        event = UnsealingEvent(
            structure_id=1,
            timestamp=100,
            convergence_report=make_convergence(),
            unsealing_level=2,
            previous_level=1,
            reason="解封升级: 边界开放 → 内部耦合",
            high_semantic_capacity=0.72,
        )
        s = repr(event)
        assert "structure=1" in s
        assert "level=升级 1→2" in s
        assert "capacity=0.720" in s
        assert "ts=100" in s


class TestUnsealingIntegration:
    """解封机制与 HierarchicalEvolver 的集成测试"""

    def test_evolver_with_unsealing(self):
        """HierarchicalEvolver 集成解封机制"""
        from engine.hierarchical_evolver import HierarchicalEvolver
        from engine.pre_subjectivity_convergence import PreSubjectivityConvergence

        hev = HierarchicalEvolver(
            N0=24,
            steps_per_layer=200,
            max_layers=1,
            unsealing_mechanism=UnsealingMechanism(),
            pre_subjectivity_convergence=PreSubjectivityConvergence(),
            phase2_verbose=False,
        )

        results = hev.run(verbose=False)

        # 验证 phase2_summary 包含解封信息
        p2 = results['phase2_summary']
        assert p2['unsealing_mechanism_active'] is True
        assert 'unsealing_events' in p2
        assert 'unsealing_summary' in p2

        # 验证查询接口
        events = hev.get_unsealing_events()
        assert isinstance(events, list)

        status = hev.get_unsealing_status()
        assert isinstance(status, dict)

    def test_evolver_with_return_flow(self):
        """HierarchicalEvolver 集成回流通道"""
        from engine.hierarchical_evolver import HierarchicalEvolver
        from engine.return_flow_channel import ReturnFlowChannel

        hev = HierarchicalEvolver(
            N0=24,
            steps_per_layer=200,
            max_layers=1,
            return_flow_channel=ReturnFlowChannel(),
            phase2_verbose=False,
        )

        results = hev.run(verbose=False)

        p2 = results['phase2_summary']
        assert p2['return_flow_channel_active'] is True
        assert 'return_flow_anchored_count' in p2
        assert 'return_flow_success_rate' in p2

        # 验证查询接口
        flow_events = hev.get_return_flow_events()
        assert isinstance(flow_events, list)

        flow_status = hev.get_return_flow_status()
        assert isinstance(flow_status, dict)
        assert 'anchored_count' in flow_status

    def test_evolver_with_both_phase2_components(self):
        """完整 Phase 2：解封 + 回流同时启用"""
        from engine.hierarchical_evolver import HierarchicalEvolver
        from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
        from engine.unsealing_mechanism import UnsealingMechanism
        from engine.return_flow_channel import ReturnFlowChannel

        hev = HierarchicalEvolver(
            N0=24,
            steps_per_layer=200,
            max_layers=1,
            unsealing_mechanism=UnsealingMechanism(),
            return_flow_channel=ReturnFlowChannel(),
            pre_subjectivity_convergence=PreSubjectivityConvergence(),
            phase2_verbose=False,
        )

        results = hev.run(verbose=False)

        p2 = results['phase2_summary']
        assert p2['unsealing_mechanism_active'] is True
        assert p2['return_flow_channel_active'] is True
        assert p2['pre_subjectivity_convergence_active'] is True


class TestInterfaceExchangeRecord:
    """InterfaceExchangeRecord 单元测试"""

    def test_openness_calculation(self):
        rec = InterfaceExchangeRecord(
            timestamp=100,
            channel_pattern={'A': 0.6, 'B': 0.4},
            total_active=60,
            total_edges=100,
        )
        assert rec.openness == 0.6

    def test_openness_zero_edges(self):
        rec = InterfaceExchangeRecord(timestamp=1, total_edges=0)
        assert rec.openness == 0.0

    def test_openness_full(self):
        rec = InterfaceExchangeRecord(
            timestamp=1, total_active=10, total_edges=10,
        )
        assert rec.openness == 1.0

    def test_repr(self):
        rec = InterfaceExchangeRecord(
            timestamp=42,
            channel_pattern={'X': 1.0},
            total_active=5,
            total_edges=10,
        )
        s = repr(rec)
        assert "ts=42" in s
        assert "openness=0.500" in s
        assert "channels=1" in s


class TestInterfacePatternStability:
    """InterfacePatternStability 单元测试"""

    def test_initial_state(self):
        ips = InterfacePatternStability(window_size=5, stability_threshold=0.7)
        assert ips.current_stability == 0.0
        assert ips.is_stable is False
        assert ips.is_ready is False
        assert ips.n_records == 0

    def test_single_record_not_ready(self):
        ips = InterfacePatternStability()
        rec = InterfaceExchangeRecord(
            timestamp=1,
            channel_pattern={'A': 0.5, 'B': 0.5},
            total_active=50, total_edges=100,
        )
        stability = ips.record(rec)
        assert stability == 0.0  # 不足2条记录
        assert ips.is_ready is False
        assert ips.n_records == 1

    def test_two_identical_patterns_stable(self):
        ips = InterfacePatternStability(window_size=5, stability_threshold=0.7)
        pattern = {'inhibitory': 0.3, 'excitatory': 0.5, 'modulatory': 0.2}
        ips.record(InterfaceExchangeRecord(
            timestamp=1, channel_pattern=pattern, total_active=50, total_edges=100,
        ))
        stability = ips.record(InterfaceExchangeRecord(
            timestamp=2, channel_pattern=pattern, total_active=50, total_edges=100,
        ))
        assert stability == 1.0  # 完全相同模式
        assert ips.is_stable is True
        assert ips.is_ready is True

    def test_two_different_patterns_unstable(self):
        ips = InterfacePatternStability(window_size=5, stability_threshold=0.7)
        ips.record(InterfaceExchangeRecord(
            timestamp=1,
            channel_pattern={'A': 1.0},
            total_active=50, total_edges=100,
        ))
        stability = ips.record(InterfaceExchangeRecord(
            timestamp=2,
            channel_pattern={'B': 1.0},
            total_active=50, total_edges=100,
        ))
        assert stability == 0.0  # 完全不重叠
        assert ips.is_stable is False

    def test_partial_similarity(self):
        ips = InterfacePatternStability(window_size=5, stability_threshold=0.7)
        ips.record(InterfaceExchangeRecord(
            timestamp=1,
            channel_pattern={'A': 0.8, 'B': 0.2},
            total_active=50, total_edges=100,
        ))
        stability = ips.record(InterfaceExchangeRecord(
            timestamp=2,
            channel_pattern={'A': 0.6, 'B': 0.4},
            total_active=50, total_edges=100,
        ))
        assert 0.0 < stability < 1.0  # 部分相似

    def test_sliding_window_eviction(self):
        ips = InterfacePatternStability(window_size=3, stability_threshold=0.99)
        # 交替两种完全不同的模式
        pattern_x = {'X': 1.0}
        pattern_y = {'Y': 1.0}
        for i in range(10):
            p = pattern_x if i % 2 == 0 else pattern_y
            ips.record(InterfaceExchangeRecord(
                timestamp=i, channel_pattern=p, total_active=50, total_edges=100,
            ))
        # 窗口只保留最近 3 条
        assert ips.n_records == 3

    def test_stability_trend(self):
        ips = InterfacePatternStability(window_size=5, stability_threshold=0.7)
        pattern = {'A': 0.5, 'B': 0.5}
        for i in range(5):
            ips.record(InterfaceExchangeRecord(
                timestamp=i, channel_pattern=pattern, total_active=50, total_edges=100,
            ))
        trend = ips.get_stability_trend()
        assert len(trend) == 5
        # 第一次是 0.0（不足2条），后面都是 ~1.0（完全相同，允许浮点误差）
        assert trend[0] == 0.0
        assert all(abs(t - 1.0) < 1e-6 for t in trend[1:])

    def test_dominant_channels(self):
        ips = InterfacePatternStability(window_size=5, stability_threshold=0.7)
        for i in range(3):
            ips.record(InterfaceExchangeRecord(
                timestamp=i,
                channel_pattern={'A': 0.6, 'B': 0.3, 'C': 0.1},
                total_active=50, total_edges=100,
            ))
        dominant = ips.dominant_channels
        assert dominant == ['A', 'B', 'C']

    def test_dominant_channels_empty(self):
        ips = InterfacePatternStability()
        assert ips.dominant_channels == []

    def test_reset(self):
        ips = InterfacePatternStability()
        ips.record(InterfaceExchangeRecord(
            timestamp=1, channel_pattern={'A': 1.0}, total_active=50, total_edges=100,
        ))
        ips.record(InterfaceExchangeRecord(
            timestamp=2, channel_pattern={'A': 1.0}, total_active=50, total_edges=100,
        ))
        assert ips.n_records == 2
        ips.reset()
        assert ips.n_records == 0
        assert ips.current_stability == 0.0
        assert ips.is_stable is False

    def test_pattern_cosine_sim_both_empty(self):
        sim = InterfacePatternStability._pattern_cosine_sim({}, {})
        assert sim == 1.0

    def test_pattern_cosine_sim_one_empty(self):
        sim = InterfacePatternStability._pattern_cosine_sim({'A': 1.0}, {})
        assert sim == 0.0

    def test_pattern_cosine_sim_identical(self):
        sim = InterfacePatternStability._pattern_cosine_sim(
            {'A': 0.5, 'B': 0.5}, {'A': 0.5, 'B': 0.5})
        assert abs(sim - 1.0) < 1e-8

    def test_pattern_cosine_sim_orthogonal(self):
        sim = InterfacePatternStability._pattern_cosine_sim(
            {'A': 1.0}, {'B': 1.0})
        assert sim == 0.0

    def test_repr(self):
        ips = InterfacePatternStability(window_size=3, stability_threshold=0.8)
        ips.record(InterfaceExchangeRecord(
            timestamp=1, channel_pattern={'A': 1.0}, total_active=50, total_edges=100,
        ))
        ips.record(InterfaceExchangeRecord(
            timestamp=2, channel_pattern={'A': 1.0}, total_active=50, total_edges=100,
        ))
        s = repr(ips)
        assert "records=2/3" in s
        assert "stability=1.000" in s
        assert "stable=True" in s


class TestUnsealingWithInterfaceStability:
    """解封机制 + 界面模式稳定性集成测试"""

    def test_record_interface_exchange(self):
        mech = UnsealingMechanism()
        stability = mech.record_interface_exchange(
            structure_id=1,
            timestamp=1,
            channel_pattern={'A': 0.6, 'B': 0.4},
            total_active=60,
            total_edges=100,
        )
        # 第一条记录，稳定性为 0
        assert stability == 0.0
        assert mech.is_interface_stable(1) is False

    def test_interface_stability_convergence(self):
        mech = UnsealingMechanism(
            interface_stability_window=5,
            interface_stability_threshold=0.7,
        )
        pattern = {'inhibitory': 0.3, 'excitatory': 0.5, 'modulatory': 0.2}
        for i in range(5):
            stability = mech.record_interface_exchange(
                structure_id=1,
                timestamp=i,
                channel_pattern=pattern,
                total_active=50,
                total_edges=100,
            )
        # 5条相同记录后应稳定
        assert stability == 1.0
        assert mech.is_interface_stable(1) is True

    def test_get_interface_stability_tracker(self):
        mech = UnsealingMechanism()
        assert mech.get_interface_stability(1) is None

        mech.record_interface_exchange(
            structure_id=1,
            timestamp=1,
            channel_pattern={'A': 1.0},
            total_active=50,
            total_edges=100,
        )
        tracker = mech.get_interface_stability(1)
        assert tracker is not None
        assert isinstance(tracker, InterfacePatternStability)
        assert tracker.n_records == 1

    def test_multiple_structures_independent(self):
        mech = UnsealingMechanism()
        # 结构1：稳定模式
        stable_pattern = {'A': 0.5, 'B': 0.5}
        for i in range(3):
            mech.record_interface_exchange(
                1, i, stable_pattern, 50, 100,
            )
        # 结构2：不稳定模式
        mech.record_interface_exchange(
            2, 0, {'X': 1.0}, 50, 100,
        )
        mech.record_interface_exchange(
            2, 1, {'Y': 1.0}, 50, 100,
        )

        assert mech.is_interface_stable(1) is True
        assert mech.is_interface_stable(2) is False

    def test_reset_clears_interface_stability(self):
        mech = UnsealingMechanism()
        for i in range(3):
            mech.record_interface_exchange(
                1, i, {'A': 1.0}, 50, 100,
            )
        assert mech.is_interface_stable(1) is True

        mech.reset()
        assert mech.is_interface_stable(1) is False
        assert mech.get_interface_stability(1) is None

    def test_unsealing_event_repr_with_interface(self):
        """解封事件与界面稳定性共存时 repr 正常"""
        mech = UnsealingMechanism()
        mech.record_interface_exchange(
            1, 0, {'A': 0.5, 'B': 0.5}, 50, 100,
        )
        result = make_convergence(min_coupling=0.4, stability_score=0.6)
        event = mech.evaluate(1, result, timestamp=100)
        assert event is not None
        s = repr(event)
        assert "structure=1" in s


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
