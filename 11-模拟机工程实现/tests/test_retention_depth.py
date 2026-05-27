"""
tests/test_retention_depth.py — 保持可重调用性测试

测试 PersistentBiasMemory 的保持深度追踪功能（缺口2）。

理论依据（ABA §3.3）：
- 保持不是惰性标记，而是能偏置未来构型的操作力
- 保持的可重调用性：偏置需要在递归重建中持续存在
- 保持深度 = 成功重调用次数 / 重建循环次数
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.persistent_bias_memory import (
    PersistentBiasMemory,
    RetentionDepthTracker,
    BiasEntry,
    RetentionDepthRecord,
)
from engine.hierarchy_manager import BiasField


class TestRetentionDepthTracker:
    """测试 RetentionDepthTracker 核心功能"""

    def test_begin_cycle_snapshots_state(self):
        """begin_cycle 应记录当前活跃偏置的状态快照"""
        tracker = RetentionDepthTracker()
        entries = [
            BiasEntry(
                entry_id="e1", source_layer=0, target_layer=1,
                bias_vector=torch.tensor([1.0, 0.0, 0.0]),
                initial_strength=0.8, current_strength=0.8,
                timestamp=0, decay_rate=0.95, is_frozen=False,
            ),
        ]
        tracker.begin_cycle(entries)
        assert tracker.n_cycles_tracked == 0  # 尚未完成循环

    def test_end_cycle_detects_reinvocation(self):
        """end_cycle 应检测到偏置被成功重调用"""
        tracker = RetentionDepthTracker(
            similarity_threshold=0.7,
            strength_persistence_threshold=0.3,
        )
        entries = [
            BiasEntry(
                entry_id="e1", source_layer=0, target_layer=1,
                bias_vector=torch.tensor([1.0, 0.0, 0.0]),
                initial_strength=0.8, current_strength=0.8,
                timestamp=0, decay_rate=0.95, is_frozen=False,
            ),
        ]
        tracker.begin_cycle(entries)

        # 模拟重建后偏置方向一致、强度持续
        post_entries = [
            BiasEntry(
                entry_id="e1", source_layer=0, target_layer=1,
                bias_vector=torch.tensor([0.9, 0.1, 0.0]),
                initial_strength=0.8, current_strength=0.7,
                timestamp=1, decay_rate=0.95, is_frozen=False,
            ),
        ]
        results = tracker.end_cycle(post_entries, timestamp=1)
        assert results["e1"] is True
        assert tracker.n_cycles_tracked == 1

    def test_end_cycle_detects_direction_change(self):
        """end_cycle 应检测到偏置方向改变（重调用失败）"""
        tracker = RetentionDepthTracker(
            similarity_threshold=0.7,
            strength_persistence_threshold=0.3,
        )
        entries = [
            BiasEntry(
                entry_id="e1", source_layer=0, target_layer=1,
                bias_vector=torch.tensor([1.0, 0.0, 0.0]),
                initial_strength=0.8, current_strength=0.8,
                timestamp=0, decay_rate=0.95, is_frozen=False,
            ),
        ]
        tracker.begin_cycle(entries)

        # 模拟重建后偏置方向完全相反
        post_entries = [
            BiasEntry(
                entry_id="e1", source_layer=0, target_layer=1,
                bias_vector=torch.tensor([-1.0, 0.0, 0.0]),
                initial_strength=0.8, current_strength=0.7,
                timestamp=1, decay_rate=0.95, is_frozen=False,
            ),
        ]
        results = tracker.end_cycle(post_entries, timestamp=1)
        assert results["e1"] is False

    def test_end_cycle_detects_strength_loss(self):
        """end_cycle 应检测到偏置强度严重下降"""
        tracker = RetentionDepthTracker(
            similarity_threshold=0.7,
            strength_persistence_threshold=0.3,
        )
        entries = [
            BiasEntry(
                entry_id="e1", source_layer=0, target_layer=1,
                bias_vector=torch.tensor([1.0, 0.0, 0.0]),
                initial_strength=0.8, current_strength=0.8,
                timestamp=0, decay_rate=0.95, is_frozen=False,
            ),
        ]
        tracker.begin_cycle(entries)

        # 模拟重建后强度极低
        post_entries = [
            BiasEntry(
                entry_id="e1", source_layer=0, target_layer=1,
                bias_vector=torch.tensor([1.0, 0.0, 0.0]),
                initial_strength=0.8, current_strength=0.01,
                timestamp=1, decay_rate=0.95, is_frozen=False,
            ),
        ]
        results = tracker.end_cycle(post_entries, timestamp=1)
        assert results["e1"] is False

    def test_end_cycle_missing_entry(self):
        """end_cycle 应标记已失效的条目为重调用失败"""
        tracker = RetentionDepthTracker()
        entries = [
            BiasEntry(
                entry_id="e1", source_layer=0, target_layer=1,
                bias_vector=torch.tensor([1.0, 0.0, 0.0]),
                initial_strength=0.8, current_strength=0.8,
                timestamp=0, decay_rate=0.95, is_frozen=False,
            ),
        ]
        tracker.begin_cycle(entries)

        # 重建后条目已失效（不在活跃列表中）
        post_entries = []
        results = tracker.end_cycle(post_entries, timestamp=1)
        assert results["e1"] is False

    def test_multiple_cycles_accumulation(self):
        """多次重建循环应累积保持深度"""
        tracker = RetentionDepthTracker(
            similarity_threshold=0.7,
            strength_persistence_threshold=0.3,
        )

        # 创建初始条目
        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0, 0.0, 0.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95, is_frozen=False,
        )

        for cycle in range(5):
            tracker.begin_cycle([entry])
            # 每次重建后方向一致、强度略降
            entry.current_strength = 0.8 * (0.95 ** cycle)
            entry.bias_vector = torch.tensor([1.0, 0.01 * cycle, 0.0])
            results = tracker.end_cycle([entry], timestamp=cycle + 1)

        assert tracker.n_cycles_tracked == 5
        stats = tracker.get_retention_stats("e1")
        assert stats is not None
        assert stats["n_cycles"] == 5
        assert stats["n_successful_reinvocations"] == 5
        assert stats["retention_depth"] == 1.0

    def test_retention_stats_partial_success(self):
        """部分成功的重调用应产生介于 0 和 1 之间的保持深度"""
        tracker = RetentionDepthTracker(
            similarity_threshold=0.7,
            strength_persistence_threshold=0.3,
        )

        # 创建条目，初始方向 [1,0,0]
        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0, 0.0, 0.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95, is_frozen=False,
        )

        # 循环0: pre=[1,0,0] post=[1,0,0] → 方向一致 → 成功
        tracker.begin_cycle([entry])
        entry.current_strength = 0.7
        tracker.end_cycle([entry], timestamp=1)

        # 循环1: pre=[1,0,0] post=[1,0,0] → 方向一致 → 成功
        #   (注意: begin_cycle 快照的是上一轮结束时的状态)
        tracker.begin_cycle([entry])
        entry.current_strength = 0.65
        tracker.end_cycle([entry], timestamp=2)

        # 循环2: pre=[1,0,0] post=[-1,0,0] → 方向相反 → 失败
        tracker.begin_cycle([entry])
        entry.bias_vector = torch.tensor([-1.0, 0.0, 0.0])
        entry.current_strength = 0.6
        tracker.end_cycle([entry], timestamp=3)

        # 循环3: pre=[-1,0,0] post=[-1,0,0] → 方向一致 → 成功
        tracker.begin_cycle([entry])
        entry.current_strength = 0.55
        tracker.end_cycle([entry], timestamp=4)

        stats = tracker.get_retention_stats("e1")
        assert stats["n_cycles"] == 4
        assert stats["n_successful_reinvocations"] == 3
        assert stats["retention_depth"] == 0.75

    def test_deep_retention_threshold(self):
        """深度保持判定：重调用 >= 3 次且循环 >= 3 次"""
        tracker = RetentionDepthTracker(
            similarity_threshold=0.7,
            strength_persistence_threshold=0.3,
        )

        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0, 0.0, 0.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95, is_frozen=False,
        )

        for cycle in range(3):
            tracker.begin_cycle([entry])
            entry.current_strength = 0.7
            tracker.end_cycle([entry], timestamp=cycle + 1)

        deep_entries = tracker.get_deep_retention_entries()
        assert "e1" in deep_entries

    def test_not_deep_retention_with_few_cycles(self):
        """循环次数不足 3 次时不应判定为深度保持"""
        tracker = RetentionDepthTracker(
            similarity_threshold=0.7,
            strength_persistence_threshold=0.3,
        )

        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0, 0.0, 0.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95, is_frozen=False,
        )

        for cycle in range(2):
            tracker.begin_cycle([entry])
            entry.current_strength = 0.7
            tracker.end_cycle([entry], timestamp=cycle + 1)

        deep_entries = tracker.get_deep_retention_entries()
        assert "e1" not in deep_entries

    def test_aggregate_retention_depth(self):
        """聚合保持深度应为所有条目的平均值"""
        tracker = RetentionDepthTracker(
            similarity_threshold=0.7,
            strength_persistence_threshold=0.3,
        )

        e1 = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0, 0.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95,
        )
        e2 = BiasEntry(
            entry_id="e2", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([0.0, 1.0]),
            initial_strength=0.6, current_strength=0.6,
            timestamp=0, decay_rate=0.95,
        )

        # 循环0: e1 方向一致(成功), e2 方向一致(成功)
        tracker.begin_cycle([e1, e2])
        e1.current_strength = 0.7
        e2.current_strength = 0.5
        tracker.end_cycle([e1, e2], timestamp=1)

        # 循环1: e1 方向一致(成功), e2 方向相反(失败)
        tracker.begin_cycle([e1, e2])
        e1.current_strength = 0.65
        e2.bias_vector = torch.tensor([0.0, -1.0])
        e2.current_strength = 0.45
        tracker.end_cycle([e1, e2], timestamp=2)

        # e1: 2/2 = 1.0, e2: 1/2 = 0.5 → avg = 0.75
        agg = tracker.get_aggregate_retention_depth()
        assert agg == pytest.approx(0.75, abs=0.01)

    def test_cosine_similarity_helper(self):
        """余弦相似度计算应正确"""
        tracker = RetentionDepthTracker()

        # 相同方向
        a = torch.tensor([1.0, 0.0, 0.0])
        b = torch.tensor([1.0, 0.0, 0.0])
        assert tracker._cosine_similarity(a, b) == pytest.approx(1.0, abs=0.01)

        # 正交
        a = torch.tensor([1.0, 0.0])
        b = torch.tensor([0.0, 1.0])
        assert tracker._cosine_similarity(a, b) == pytest.approx(0.0, abs=0.01)

        # 相反方向
        a = torch.tensor([1.0, 0.0])
        b = torch.tensor([-1.0, 0.0])
        assert tracker._cosine_similarity(a, b) == pytest.approx(-1.0, abs=0.01)

    def test_cosine_similarity_different_lengths(self):
        """不同长度的向量应通过截断对齐计算"""
        tracker = RetentionDepthTracker()
        a = torch.tensor([1.0, 0.0, 0.5])
        b = torch.tensor([1.0, 0.0])
        # 截断到 min_len=2: [1,0]·[1,0] / (1*1) = 1.0
        assert tracker._cosine_similarity(a, b) == pytest.approx(1.0, abs=0.01)

    def test_empty_tracker_stats(self):
        """空追踪器应返回 0 聚合深度"""
        tracker = RetentionDepthTracker()
        assert tracker.get_aggregate_retention_depth() == 0.0
        assert tracker.get_deep_retention_entries() == []


class TestPersistentBiasMemoryRetention:
    """测试 PersistentBiasMemory 的保持深度集成功能"""

    def _make_bias_field(self, layer=0, strength=0.8, n_bits=4):
        """辅助：创建 BiasField"""
        return BiasField(
            source_layer=layer,
            target_layer=layer + 1,
            bias_vector=torch.ones(n_bits) * 0.5,
            strength=strength,
            origin_step=0,
        )

    def test_retention_tracking_enabled_by_default(self):
        """默认应启用保持深度追踪"""
        mem = PersistentBiasMemory()
        assert mem._enable_retention_tracking is True

    def test_retention_tracking_can_be_disabled(self):
        """应可以禁用保持深度追踪"""
        mem = PersistentBiasMemory(enable_retention_tracking=False)
        assert mem._enable_retention_tracking is False
        mem.begin_reconstruction_cycle()  # 不应报错
        results = mem.end_reconstruction_cycle(timestamp=1)
        assert results == {}

    def test_begin_and_end_cycle(self):
        """begin/end 重建循环应正常工作"""
        mem = PersistentBiasMemory()
        bf = self._make_bias_field()
        mem.record(bf, timestamp=0)

        mem.begin_reconstruction_cycle()
        results = mem.end_reconstruction_cycle(timestamp=1)

        assert mem.n_cycles_tracked == 1
        assert len(results) > 0

    def test_retention_stats_after_cycles(self):
        """多次循环后应能获取保持深度统计"""
        mem = PersistentBiasMemory()
        bf = self._make_bias_field(strength=0.8)
        entry_id = mem.record(bf, timestamp=0)

        for i in range(3):
            mem.begin_reconstruction_cycle()
            # 模拟重建：偏置方向不变
            results = mem.end_reconstruction_cycle(timestamp=i + 1)

        stats = mem.get_retention_stats(entry_id)
        assert stats is not None
        assert stats["n_cycles"] == 3

    def test_aggregate_retention_depth(self):
        """应能获取聚合保持深度"""
        mem = PersistentBiasMemory()
        bf1 = self._make_bias_field(strength=0.8)
        bf2 = self._make_bias_field(strength=0.6)
        mem.record(bf1, timestamp=0)
        mem.record(bf2, timestamp=0)

        for i in range(2):
            mem.begin_reconstruction_cycle()
            mem.end_reconstruction_cycle(timestamp=i + 1)

        agg = mem.get_aggregate_retention_depth()
        assert 0.0 <= agg <= 1.0

    def test_deep_retention_entries(self):
        """应能获取深度保持条目列表"""
        mem = PersistentBiasMemory()
        bf = self._make_bias_field(strength=0.8)
        entry_id = mem.record(bf, timestamp=0)

        for i in range(5):
            mem.begin_reconstruction_cycle()
            mem.end_reconstruction_cycle(timestamp=i + 1)

        deep = mem.get_deep_retention_entries()
        assert entry_id in deep

    def test_summary_includes_retention(self):
        """get_summary 应包含保持深度信息"""
        mem = PersistentBiasMemory()
        bf = self._make_bias_field()
        mem.record(bf, timestamp=0)

        summary = mem.get_summary()
        assert "retention_tracking_enabled" in summary
        assert "n_cycles_tracked" in summary
        assert "aggregate_retention_depth" in summary
        assert summary["retention_tracking_enabled"] is True

    def test_existing_functionality_preserved(self):
        """现有功能（record/freeze/unseal/decay）应不受影响"""
        mem = PersistentBiasMemory()
        bf = self._make_bias_field(strength=0.9)
        entry_id = mem.record(bf, timestamp=0)

        # 记录
        assert mem.n_entries == 1

        # 冻结
        assert mem.freeze(entry_id) is True
        assert mem.n_frozen_entries == 1

        # 解封
        vec = mem.unseal(entry_id)
        assert vec is not None
        assert mem.n_frozen_entries == 0

        # 衰减
        bf2 = self._make_bias_field(strength=0.5)
        mem.record(bf2, timestamp=1)
        assert mem.n_entries == 2

    def test_get_accumulated_with_retention(self):
        """累积偏置计算应与保持深度追踪兼容"""
        mem = PersistentBiasMemory()
        bf = self._make_bias_field(layer=0, strength=0.8, n_bits=4)
        mem.record(bf, timestamp=0)

        accumulated = mem.get_accumulated(target_layer=1, n_bits=4)
        assert accumulated.shape == torch.Size([4])

    def test_reset_clears_retention(self):
        """reset 应清除所有保持深度状态"""
        mem = PersistentBiasMemory()
        bf = self._make_bias_field()
        mem.record(bf, timestamp=0)

        mem.begin_reconstruction_cycle()
        mem.end_reconstruction_cycle(timestamp=1)

        assert mem.n_cycles_tracked == 1  # 确认循环确实被追踪

        mem.reset()
        assert mem.n_entries == 0
        assert mem.n_cycles_tracked == 0
        assert mem.get_aggregate_retention_depth() == 0.0


class TestBiasEntryRetentionProperties:
    """测试 BiasEntry 的保持相关属性"""

    def test_retention_depth_zero_when_no_cycles(self):
        """无重建循环时保持深度应为 0"""
        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95,
        )
        assert entry.retention_depth == 0.0

    def test_retention_depth_perfect(self):
        """所有循环都成功时应为 1.0"""
        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95,
            n_reconstruction_cycles=5,
            n_successful_reinvocations=5,
        )
        assert entry.retention_depth == 1.0

    def test_retention_depth_partial(self):
        """部分成功时应为比例值"""
        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95,
            n_reconstruction_cycles=4,
            n_successful_reinvocations=1,
        )
        assert entry.retention_depth == 0.25

    def test_retention_span(self):
        """保持跨度应正确计算"""
        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95,
            first_active_timestamp=10,
            last_active_timestamp=25,
        )
        assert entry.retention_span == 15

    def test_retention_span_zero_when_not_active(self):
        """未激活时保持跨度应为 0"""
        entry = BiasEntry(
            entry_id="e1", source_layer=0, target_layer=1,
            bias_vector=torch.tensor([1.0]),
            initial_strength=0.8, current_strength=0.8,
            timestamp=0, decay_rate=0.95,
        )
        assert entry.retention_span == 0


class TestRetentionDepthRecord:
    """测试 RetentionDepthRecord"""

    def test_strength_ratio(self):
        """强度比应正确计算"""
        record = RetentionDepthRecord(
            entry_id="e1", cycle_index=1,
            strength_before=0.8, strength_after=0.6,
            was_reinvoked=True, cosine_similarity=0.9, timestamp=1,
        )
        assert record.strength_ratio == pytest.approx(0.75, abs=0.01)

    def test_strength_ratio_zero_when_no_strength(self):
        """重建前强度为 0 时强度比应为 0"""
        record = RetentionDepthRecord(
            entry_id="e1", cycle_index=1,
            strength_before=0.0, strength_after=0.0,
            was_reinvoked=False, cosine_similarity=0.0, timestamp=1,
        )
        assert record.strength_ratio == 0.0
