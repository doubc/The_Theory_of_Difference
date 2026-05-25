"""
tests/test_replicate_pattern.py — 复制模式测试

Phase 2 P2 组件 #3 测试
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.replicate_pattern import (
    ReplicatePattern, ReplicationResult, KeyRelation
)


class TestReplicatePattern:
    """ReplicatePattern 测试套件"""

    def setup_method(self):
        self.rp = ReplicatePattern(
            fidelity_threshold=0.6,
            key_relation_threshold=0.7,
        )
        self.state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])

    def test_initial_state(self):
        """初始状态"""
        assert not self.rp.is_replicating
        assert self.rp.avg_fidelity == 0.0
        assert self.rp.n_replications == 0

    def test_set_original(self):
        """设置原始模式"""
        self.rp.set_original(self.state)
        assert len(self.rp._original_relations) > 0

    def test_extract_key_relations(self):
        """提取关键关系"""
        relations = self.rp.extract_key_relations(self.state)
        assert isinstance(relations, set)
        assert len(relations) > 0

    def test_extract_key_relations_with_binding(self):
        """带绑定强度的关键关系提取"""
        n = len(self.state)
        binding = torch.zeros(n, n)
        binding[0, 1] = 0.5
        binding[1, 0] = 0.5
        binding[2, 3] = 0.3
        binding[3, 2] = 0.3

        relations = self.rp.extract_key_relations(
            self.state, binding_strength=binding)
        binding_relations = [r for r in relations if r.relation_type == "binding"]
        assert len(binding_relations) >= 2

    def test_replicate_zero_noise(self):
        """零噪声复制 → 高保真"""
        result = self.rp.replicate(self.state, noise_level=0.0)
        assert result.fidelity > 0.9

    def test_replicate_with_noise(self):
        """有噪声复制 → 保真度降低"""
        result_clean = self.rp.replicate(self.state, noise_level=0.0)
        rp2 = ReplicatePattern()
        result_noisy = rp2.replicate(self.state, noise_level=0.5)
        assert result_noisy.fidelity <= result_clean.fidelity

    def test_replicate_sets_original_on_first_call(self):
        """首次复制自动设置原始模式"""
        result = self.rp.replicate(self.state, noise_level=0.0)
        assert len(self.rp._original_relations) > 0

    def test_replicate_multiple_times(self):
        """多次复制"""
        for _ in range(5):
            self.rp.replicate(self.state, noise_level=0.05)
        assert self.rp.n_replications == 5

    def test_structural_similarity(self):
        """结构相似性"""
        state_a = torch.tensor([1.0, 0.0, 1.0, 0.0])
        state_b = torch.tensor([1.0, 0.0, 1.0, 0.0])
        sim = self.rp.get_structural_similarity(state_a, state_b)
        assert sim > 0.5

    def test_structural_similarity_different(self):
        """不同状态的结构相似性"""
        state_a = torch.tensor([1.0, 1.0, 1.0, 1.0])
        state_b = torch.tensor([0.0, 0.0, 0.0, 0.0])
        sim = self.rp.get_structural_similarity(state_a, state_b)
        assert sim < 1.0

    def test_cross_instance_stability(self):
        """跨实例稳定性"""
        for _ in range(5):
            self.rp.replicate(self.state, noise_level=0.0)
        stability = self.rp.evaluate_cross_instance_stability()
        assert stability > 0.5

    def test_replication_result_dataclass(self):
        """ReplicationResult 数据类"""
        result = ReplicationResult(
            fidelity=0.8,
            key_relations_preserved=8,
            key_relations_total=10,
            is_successful=True,
        )
        assert result.is_successful
        assert result.fidelity == 0.8

    def test_key_relation_dataclass(self):
        """KeyRelation 数据类"""
        rel = KeyRelation(
            relation_type="binding",
            source="0",
            target="1",
            strength=0.5,
        )
        assert rel.relation_type == "binding"
        assert rel.source == "0"
        assert rel.target == "1"

    def test_key_relation_equality(self):
        """KeyRelation 相等性"""
        rel1 = KeyRelation(relation_type="binding", source="0", target="1")
        rel2 = KeyRelation(relation_type="binding", source="0", target="1")
        assert rel1 == rel2

    def test_key_relation_hash(self):
        """KeyRelation 哈希（可用于集合）"""
        rel1 = KeyRelation(relation_type="binding", source="0", target="1")
        rel2 = KeyRelation(relation_type="binding", source="0", target="1")
        s = {rel1, rel2}
        assert len(s) == 1

    def test_get_fidelity_for_detector(self):
        """获取 SixThresholdDetector 格式"""
        state_a = torch.tensor([1.0, 0.0, 1.0, 0.0])
        state_b = torch.tensor([1.0, 0.0, 1.0, 0.0])
        fidelity = self.rp.get_fidelity_for_detector(state_a, state_b)
        assert isinstance(fidelity, float)
        assert 0.0 <= fidelity <= 1.0

    def test_summary(self):
        """摘要信息"""
        self.rp.replicate(self.state, noise_level=0.0)
        summary = self.rp.get_summary()
        assert 'n_replications' in summary
        assert 'avg_fidelity' in summary
        assert 'is_replicating' in summary
        assert 'cross_instance_stability' in summary

    def test_reset(self):
        """重置状态"""
        self.rp.replicate(self.state, noise_level=0.0)
        self.rp.reset()
        assert self.rp.n_replications == 0
        assert len(self.rp._original_relations) == 0
        assert len(self.rp._instances) == 0

    def test_replicate_with_transform(self):
        """自定义变换复制"""
        state = torch.tensor([1.0, 0.0, 1.0, 0.0])

        def flip_transform(s):
            return 1.0 - s

        result = self.rp.replicate_with_transform(state, flip_transform)
        assert isinstance(result, ReplicationResult)
        assert self.rp.n_replications == 1

    def test_max_instances_limit(self):
        """最大实例数限制"""
        rp = ReplicatePattern(max_instances=5)
        for _ in range(10):
            rp.replicate(self.state, noise_level=0.0)
        assert len(rp._instances) == 5

    def test_is_replicating_after_successful(self):
        """成功复制后 is_replicating 为 True"""
        rp = ReplicatePattern(fidelity_threshold=0.5, key_relation_threshold=0.5)
        rp.replicate(self.state, noise_level=0.0)
        assert rp.is_replicating


class TestReplicatePatternEdgeCases:
    """边界情况测试"""

    def setup_method(self):
        self.rp = ReplicatePattern(
            fidelity_threshold=0.6,
            key_relation_threshold=0.7,
        )

    def test_empty_state(self):
        """空状态"""
        state = torch.tensor([])
        result = self.rp.replicate(state, noise_level=0.0)
        assert isinstance(result, ReplicationResult)

    def test_single_element(self):
        """单元素状态"""
        state = torch.tensor([1.0])
        result = self.rp.replicate(state, noise_level=0.0)
        assert isinstance(result, ReplicationResult)

    def test_no_relations(self):
        """无关系状态（全零）"""
        state = torch.zeros(8)
        result = self.rp.replicate(state, noise_level=0.0)
        assert result.fidelity == 1.0

    def test_structural_similarity_both_empty(self):
        """两个空状态的相似性"""
        sim = self.rp.get_structural_similarity(torch.tensor([]), torch.tensor([]))
        assert sim == 1.0

    def test_structural_similarity_one_empty(self):
        """一个空一个非空的相似性"""
        sim = self.rp.get_structural_similarity(
            torch.tensor([]), torch.tensor([1.0, 0.0]))
        assert sim == 0.0

    def test_cross_instance_stability_before_replication(self):
        """复制前的跨实例稳定性"""
        stability = self.rp.evaluate_cross_instance_stability()
        assert stability == 0.0

    def test_summary_before_replication(self):
        """复制前获取摘要"""
        summary = self.rp.get_summary()
        assert summary['n_replications'] == 0
        assert summary['avg_fidelity'] == 0.0
        assert summary['cross_instance_stability'] == 0.0
