"""
tests/test_encapsulation.py — 封装引擎测试

覆盖：
1. Union-Find 分组正确性
2. 封装比特生成（多数表决）
3. 索引映射正确性
4. 封装值更新（基底变化）
5. 解封检测
6. 引力势计算
7. 端到端封装流程
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.encapsulation_engine import (
    UnionFind, EncapsulatedBit, IndexMapping,
    EncapsulationEngine
)


# ====== Union-Find 测试 ======

class TestUnionFind:

    def test_single_element(self):
        uf = UnionFind(1)
        assert uf.find(0) == 0
        groups = uf.groups()
        assert groups == {0: [0]}

    def test_two_disconnected(self):
        uf = UnionFind(2)
        groups = uf.groups()
        assert len(groups) == 2

    def test_two_connected(self):
        uf = UnionFind(2)
        uf.union(0, 1)
        groups = uf.groups()
        assert len(groups) == 1
        members = list(groups.values())[0]
        assert set(members) == {0, 1}

    def test_transitive(self):
        """传递性：0-1, 1-2 → 0,1,2 同一组"""
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)
        assert uf.find(0) == uf.find(1) == uf.find(2)
        assert uf.find(0) != uf.find(3)
        groups = uf.groups()
        # 3 组：{0,1,2}, {3}, {4}
        assert len(groups) == 3

    def test_large_chain(self):
        """大链：0-1-2-3-...-99"""
        uf = UnionFind(100)
        for i in range(99):
            uf.union(i, i + 1)
        groups = uf.groups()
        assert len(groups) == 1
        assert len(list(groups.values())[0]) == 100

    def test_path_compression(self):
        """路径压缩后 find 直接指向根"""
        uf = UnionFind(5)
        uf.union(0, 1)
        uf.union(1, 2)
        uf.union(2, 3)
        root = uf.find(0)
        # 路径压缩后，0 的 parent 应该是根
        assert uf.find(0) == root


# ====== EncapsulatedBit 测试 ======

class TestEncapsulatedBit:

    def test_init(self):
        enc = EncapsulatedBit(
            bit_id=0, layer=1,
            source_bits=[1, 2, 3],
            initial_value=1.0,
            binding_score=0.5
        )
        assert enc.bit_id == 0
        assert enc.layer == 1
        assert enc.source_bits == [1, 2, 3]
        assert enc.value == 1.0
        assert enc.binding_score == 0.5
        assert not enc.is_frozen
        assert enc.direction == 0

    def test_update_value_majority_ones(self):
        enc = EncapsulatedBit(0, 1, [0, 1, 2, 3], 0.0, 0.5)
        state = torch.tensor([1.0, 1.0, 1.0, 0.0])
        enc.update_value(state)
        assert enc.value == 1.0  # 3/4 > 0.5

    def test_update_value_majority_zeros(self):
        enc = EncapsulatedBit(0, 1, [0, 1, 2, 3], 1.0, 0.5)
        state = torch.tensor([1.0, 0.0, 0.0, 0.0])
        enc.update_value(state)
        assert enc.value == 0.0  # 1/4 < 0.5

    def test_update_value_tie(self):
        """平局：2个1, 2个0 → 0.0（不超过半数）"""
        enc = EncapsulatedBit(0, 1, [0, 1, 2, 3], 1.0, 0.5)
        state = torch.tensor([1.0, 1.0, 0.0, 0.0])
        enc.update_value(state)
        assert enc.value == 0.0  # 2/4 不 > 0.5

    def test_should_unseal_changed(self):
        enc = EncapsulatedBit(0, 1, [0, 1, 2], 1.0, 0.5)
        # 基底变化：从多数1变为多数0
        state = torch.tensor([0.0, 0.0, 0.0])
        assert enc.should_unseal(state)  # 值从1→0，变化=1.0 > 0.5

    def test_should_not_unseal_unchanged(self):
        enc = EncapsulatedBit(0, 1, [0, 1, 2], 1.0, 0.5)
        # 基底变化但多数表决不变
        state = torch.tensor([1.0, 1.0, 0.0])
        assert not enc.should_unseal(state)  # 值仍为1，变化=0

    def test_empty_source_bits(self):
        enc = EncapsulatedBit(0, 1, [], 0.0, 0.0)
        state = torch.tensor([1.0, 1.0])
        enc.update_value(state)
        assert enc.value == 0.0  # 空源 → 不变
        assert not enc.should_unseal(state)


# ====== IndexMapping 测试 ======

class TestIndexMapping:

    def test_map_active(self):
        m = IndexMapping()
        m.map_active(5, 0)
        m.map_active(10, 1)
        assert m.get_high_idx(5) == 0
        assert m.get_high_idx(10) == 1
        assert m.get_high_idx(99) == -1  # 未映射

    def test_map_encapsulated(self):
        m = IndexMapping()
        m.map_encapsulated(3, [0, 1, 2])
        assert m.get_high_idx(0) == 3
        assert m.get_high_idx(1) == 3
        assert m.get_high_idx(2) == 3
        assert m.get_low_bits(3) == [0, 1, 2]

    def test_mixed_mapping(self):
        """活跃比特 + 封装比特混合映射"""
        m = IndexMapping()
        # 活跃比特：5→0, 10→1
        m.map_active(5, 0)
        m.map_active(10, 1)
        # 封装比特：低位[0,1,2]→高层2
        m.map_encapsulated(2, [0, 1, 2])
        assert m.get_high_idx(5) == 0
        assert m.get_high_idx(10) == 1
        assert m.get_high_idx(0) == 2
        assert m.get_low_bits(2) == [0, 1, 2]


# ====== EncapsulationEngine 测试 ======

class TestEncapsulationEngine:

    def test_no_frozen_bits(self):
        """没有冻结比特 → 不封装"""
        engine = EncapsulationEngine()
        state = torch.tensor([1.0, 0.0, 1.0, 0.0])
        binding = torch.zeros(4, 4)
        frozen = set()
        active = {0, 1, 2, 3}
        new_state, enc_bits, mapping = engine.encapsulate(
            state, frozen, binding, active, layer=0)
        assert len(enc_bits) == 0
        assert len(new_state) == 4
        assert torch.equal(new_state, state)

    def test_all_frozen_no_binding(self):
        """全部冻结但无绑定 → 不封装（组大小 < min_group_size）"""
        engine = EncapsulationEngine(min_group_size=2)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0])
        binding = torch.zeros(4, 4)  # 全零绑定
        frozen = {0, 1, 2, 3}
        active = set()
        new_state, enc_bits, mapping = engine.encapsulate(
            state, frozen, binding, active, layer=0)
        # 无绑定 → 每个比特各自一组 → 组大小=1 < 2 → 不封装
        assert len(enc_bits) == 0
        assert len(new_state) == 0

    def test_simple_encapsulation(self):
        """简单封装：2个高绑定冻结比特 → 1个封装比特"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0])
        binding = torch.zeros(4, 4)
        binding[0, 1] = binding[1, 0] = 0.5  # 比特0和1高绑定
        frozen = {0, 1}
        active = {2, 3}
        new_state, enc_bits, mapping = engine.encapsulate(
            state, frozen, binding, active, layer=0)

        # 活跃比特 2,3 → 新索引 0,1
        assert len(new_state) == 3  # 2活跃 + 1封装
        assert new_state[0] == state[2]  # 活跃比特2的值
        assert new_state[1] == state[3]  # 活跃比特3的值

        # 封装比特：源[0,1]，值=多数表决(1,0)=0
        assert len(enc_bits) == 1
        assert enc_bits[0].source_bits == [0, 1]
        assert enc_bits[0].value == 0.0  # 1个1, 1个0 → 平局 → 0

    def test_majority_vote(self):
        """多数表决：3个冻结比特，2个1 → 封装值=1"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        state = torch.tensor([1.0, 1.0, 0.0, 0.0])
        binding = torch.zeros(4, 4)
        binding[0, 1] = binding[1, 0] = 0.5
        binding[0, 2] = binding[2, 0] = 0.5
        binding[1, 2] = binding[2, 1] = 0.5
        frozen = {0, 1, 2}
        active = {3}
        new_state, enc_bits, mapping = engine.encapsulate(
            state, frozen, binding, active, layer=0)

        assert len(enc_bits) == 1
        assert enc_bits[0].value == 1.0  # 2/3 > 0.5

    def test_multiple_groups(self):
        """多组封装：两个独立的高绑定组"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        # 比特0-1一组，比特2-3一组
        state = torch.tensor([1.0, 1.0, 0.0, 0.0, 1.0, 0.0])
        binding = torch.zeros(6, 6)
        binding[0, 1] = binding[1, 0] = 0.5
        binding[2, 3] = binding[3, 2] = 0.5
        frozen = {0, 1, 2, 3}
        active = {4, 5}
        new_state, enc_bits, mapping = engine.encapsulate(
            state, frozen, binding, active, layer=0)

        # 2活跃 + 2封装 = 4
        assert len(new_state) == 4
        assert len(enc_bits) == 2
        # 第一组 [0,1]: 2个1 → 1.0
        assert enc_bits[0].value == 1.0
        # 第二组 [2,3]: 2个0 → 0.0
        assert enc_bits[1].value == 0.0

    def test_index_mapping_correct(self):
        """索引映射正确性"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0])
        binding = torch.zeros(5, 5)
        binding[0, 1] = binding[1, 0] = 0.5
        frozen = {0, 1}
        active = {2, 3, 4}
        new_state, enc_bits, mapping = engine.encapsulate(
            state, frozen, binding, active, layer=0)

        # 活跃比特：2→0, 3→1, 4→2
        assert mapping.get_high_idx(2) == 0
        assert mapping.get_high_idx(3) == 1
        assert mapping.get_high_idx(4) == 2
        # 封装比特：0,1 → 3
        assert mapping.get_high_idx(0) == 3
        assert mapping.get_high_idx(1) == 3
        assert mapping.get_low_bits(3) == [0, 1]

    def test_update_encapsulated_values(self):
        """封装值随基底状态更新"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0])
        binding = torch.zeros(4, 4)
        binding[0, 1] = binding[1, 0] = 0.5
        frozen = {0, 1}
        active = {2, 3}
        engine.encapsulate(state, frozen, binding, active, layer=0)

        # 基底状态变化
        new_base = torch.tensor([1.0, 1.0, 0.0, 0.0])
        engine.update_encapsulated_values(new_base, layer=0)

        enc = engine.encapsulated_bits[1][0]
        assert enc.value == 1.0  # 2个1 → 1.0

    def test_check_unseal(self):
        """解封检测"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0])
        binding = torch.zeros(4, 4)
        binding[0, 1] = binding[1, 0] = 0.5
        frozen = {0, 1}
        active = {2, 3}
        engine.encapsulate(state, frozen, binding, active, layer=0)

        # 基底变化导致封装值翻转
        new_base = torch.tensor([1.0, 1.0, 0.0, 0.0])
        unsealed = engine.check_unseal(new_base, layer=0)
        assert len(unsealed) > 0  # 应该解封

    def test_compute_base_gravity(self):
        """基底引力势计算"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        state = torch.tensor([1.0, 0.0, 0.0, 0.0])
        binding = torch.zeros(4, 4)
        frozen = set()
        active = {0, 1, 2, 3}
        engine.encapsulate(state, frozen, binding, active, layer=0)

        # 基底中有1个1（索引0）
        gravity = engine.compute_base_gravity(state, layer=0)
        assert len(gravity) == 4
        # 索引0距离最近（d=1），引力势最大（负值最小）
        assert gravity[0] < 0  # 引力势为负

    def test_get_summary(self):
        """封装摘要"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0])
        binding = torch.zeros(4, 4)
        binding[0, 1] = binding[1, 0] = 0.5
        frozen = {0, 1}
        active = {2, 3}
        engine.encapsulate(state, frozen, binding, active, layer=0)

        # 封装比特记录在 layer=1（封装后的新层）
        summary = engine.get_summary(enc_layer=1)
        assert summary['enc_layer'] == 1
        assert summary['base_layer'] == 0
        assert summary['n_encapsulated_bits'] == 1
        assert summary['n_active_mapped'] == 2

    def test_binding_score_preserved(self):
        """封装比特的绑定强度 = 组内平均绑定强度"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)
        state = torch.tensor([1.0, 1.0, 0.0])
        binding = torch.zeros(3, 3)
        binding[0, 1] = binding[1, 0] = 0.6
        frozen = {0, 1}
        active = {2}
        _, enc_bits, _ = engine.encapsulate(
            state, frozen, binding, active, layer=0)
        assert len(enc_bits) == 1
        assert abs(enc_bits[0].binding_score - 0.6) < 1e-6


# ====== 端到端测试 ======

class TestEndToEnd:

    def test_full_encapsulation_pipeline(self):
        """完整封装流程：状态 → 分组 → 封装 → 新状态"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)

        N = 12
        state = torch.zeros(N)
        # 设置一些1
        state[0] = 1.0
        state[1] = 1.0
        state[2] = 0.0
        state[3] = 0.0
        state[4] = 1.0
        state[5] = 0.0
        state[6] = 1.0
        state[7] = 1.0
        state[8] = 0.0
        state[9] = 0.0
        state[10] = 1.0
        state[11] = 0.0

        binding = torch.zeros(N, N)
        # 组1: 0-1-2-3（高绑定）
        for i in range(4):
            for j in range(4):
                if i != j:
                    binding[i, j] = 0.5
        # 组2: 4-5-6-7（高绑定）
        for i in range(4, 8):
            for j in range(4, 8):
                if i != j:
                    binding[i, j] = 0.5

        frozen = {0, 1, 2, 3, 4, 5, 6, 7}
        active = {8, 9, 10, 11}

        new_state, enc_bits, mapping = engine.encapsulate(
            state, frozen, binding, active, layer=0)

        # 4活跃 + 2封装 = 6
        assert len(new_state) == 6
        assert len(enc_bits) == 2

        # 活跃比特值不变
        for new_idx, old_idx in enumerate(sorted(active)):
            assert new_state[new_idx] == state[old_idx]

        # 组1: [0,1,2,3] → 2个1, 2个0 → 0.0
        assert enc_bits[0].value == 0.0
        # 组2: [4,5,6,7] → state[4]=1, state[5]=0, state[6]=1, state[7]=1 → 3个1 → 1.0
        assert enc_bits[1].value == 1.0

    def test_two_layer_cascade(self):
        """两层级联封装"""
        engine = EncapsulationEngine(binding_threshold=0.1, min_group_size=2)

        # Layer 0: 8比特
        N0 = 8
        state0 = torch.tensor([1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0])
        binding0 = torch.zeros(N0, N0)
        # 组1: 0-1, 组2: 2-3
        binding0[0, 1] = binding0[1, 0] = 0.5
        binding0[2, 3] = binding0[3, 2] = 0.5

        frozen0 = {0, 1, 2, 3}
        active0 = {4, 5, 6, 7}

        state1, enc1, map1 = engine.encapsulate(
            state0, frozen0, binding0, active0, layer=0)

        # Layer 1: 4活跃 + 2封装 = 6比特
        assert len(state1) == 6

        # Layer 1 再次封口
        frozen1 = {0, 1}  # 前两个活跃比特被冻结
        active1 = {2, 3, 4, 5}
        binding1 = torch.zeros(6, 6)
        binding1[0, 1] = binding1[1, 0] = 0.5

        state2, enc2, map2 = engine.encapsulate(
            state1, frozen1, binding1, active1, layer=1)

        # Layer 2: 4活跃 + 1封装 = 5比特
        assert len(state2) == 5
        assert len(enc2) == 1

        # 验证层级记录
        assert 1 in engine.encapsulated_bits
        assert 2 in engine.encapsulated_bits


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
