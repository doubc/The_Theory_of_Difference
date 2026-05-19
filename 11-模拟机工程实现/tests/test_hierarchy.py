"""
tests/test_hierarchy.py — 层级管理器测试

覆盖：
1. 层级初始化
2. 层内演化
3. 封装触发
4. 多层级联
5. 层级摘要
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hierarchy_manager import HierarchyManager, LayerState
from acl.axioms_v2 import AxiomConstraints


class TestLayerState:

    def test_init(self):
        state = torch.tensor([1.0, 0.0, 1.0])
        constraints = AxiomConstraints(3)
        layer = LayerState(0, state, constraints, {0, 1, 2}, set())
        assert layer.layer_id == 0
        assert layer.n_bits == 3
        assert layer.hamming_weight == 2
        assert not layer.is_sealed

    def test_hamming_weight(self):
        state = torch.tensor([1.0, 1.0, 0.0, 1.0])
        constraints = AxiomConstraints(4)
        layer = LayerState(0, state, constraints, {0, 1, 2, 3}, set())
        assert layer.hamming_weight == 3


class TestHierarchyManager:

    def test_init(self):
        hm = HierarchyManager(N0=12)
        assert hm.n_layers == 1
        assert hm.current.layer_id == 0
        assert hm.current.n_bits == 12

    def test_current_layer(self):
        hm = HierarchyManager(N0=8)
        assert hm.current_layer == 0
        assert hm.current.n_bits == 8

    def test_get_layer(self):
        hm = HierarchyManager(N0=8)
        layer = hm.get_layer(0)
        assert layer.layer_id == 0

    def test_get_layer_out_of_range(self):
        hm = HierarchyManager(N0=8)
        with pytest.raises(IndexError):
            hm.get_layer(1)

    def test_step_layer(self):
        """层内演化一步"""
        hm = HierarchyManager(N0=12, n_hierarchy_bits=4)
        result = hm.step_layer(0, n_steps=10)
        assert result['layer'] == 0
        assert result['steps'] == 10
        assert result['final_w'] >= 0

    def test_step_layer_multiple(self):
        """层内演化多步"""
        hm = HierarchyManager(N0=24, n_hierarchy_bits=8)
        result = hm.step_layer(0, n_steps=100)
        assert result['steps'] == 100
        # 应该有注入和吸收
        assert result['total_inject'] > 0 or result['total_absorb'] > 0

    def test_encapsulate_creates_new_layer(self):
        """封装创建新层"""
        hm = HierarchyManager(N0=12, binding_threshold=0.1, min_group_size=2)

        # 先手动设置一些冻结比特
        layer = hm.get_layer(0)
        layer.frozen_bits = {0, 1, 2, 3}
        layer.active_bits = {4, 5, 6, 7, 8, 9, 10, 11}
        # 设置绑定强度
        for i in range(4):
            for j in range(4):
                if i != j:
                    layer.constraints.binding_strength[i, j] = 0.5

        # 手动设置封口状态
        layer.constraints.sealed = True
        layer.constraints.sealed_bits = {0, 1, 2, 3}
        layer.constraints.active_bits = set(range(12))

        info = hm.check_and_encapsulate()
        assert info is not None
        assert info['from_layer'] == 0
        assert info['to_layer'] == 1
        assert hm.n_layers == 2
        assert hm.current_layer == 1

    def test_encapsulate_preserves_active_bits(self):
        """封装后活跃比特值不变"""
        hm = HierarchyManager(N0=8, binding_threshold=0.1, min_group_size=2)

        layer = hm.get_layer(0)
        # 设置状态
        layer.state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        layer.frozen_bits = {0, 1, 2, 3}
        layer.active_bits = {4, 5, 6, 7}
        for i in range(4):
            for j in range(4):
                if i != j:
                    layer.constraints.binding_strength[i, j] = 0.5
        layer.constraints.sealed = True
        layer.constraints.sealed_bits = {0, 1, 2, 3}
        layer.constraints.active_bits = set(range(8))

        info = hm.check_and_encapsulate()

        new_layer = hm.get_layer(1)
        # 4活跃 + 1封装 = 5，pad到3的倍数=6
        assert new_layer.n_bits == 6
        # 活跃比特值不变
        assert new_layer.state[0] == layer.state[4]
        assert new_layer.state[1] == layer.state[5]
        assert new_layer.state[2] == layer.state[6]
        assert new_layer.state[3] == layer.state[7]

    def test_no_encapsulate_without_seal(self):
        """未封口时 check_and_encapsulate 返回 None"""
        hm = HierarchyManager(N0=12)
        result = hm.check_and_encapsulate()
        assert result is None
        assert hm.n_layers == 1

    def test_two_layer_hierarchy(self):
        """两层级联"""
        hm = HierarchyManager(N0=12, binding_threshold=0.1, min_group_size=2)

        # 第一层封口
        layer0 = hm.get_layer(0)
        layer0.state = torch.tensor([1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        layer0.frozen_bits = {0, 1, 2, 3, 4, 5}
        layer0.active_bits = {6, 7, 8, 9, 10, 11}
        for i in range(6):
            for j in range(6):
                if i != j:
                    layer0.constraints.binding_strength[i, j] = 0.5
        layer0.constraints.sealed = True
        layer0.constraints.sealed_bits = {0, 1, 2, 3, 4, 5}
        layer0.constraints.active_bits = set(range(12))

        info1 = hm.check_and_encapsulate()
        assert info1 is not None

        # 第二层封口
        layer1 = hm.get_layer(1)
        n1 = layer1.n_bits
        if n1 >= 4:
            half = n1 // 2
            layer1.frozen_bits = set(range(half))
            layer1.active_bits = set(range(half, n1))
            for i in range(half):
                for j in range(half):
                    if i != j:
                        layer1.constraints.binding_strength[i, j] = 0.5
            layer1.constraints.sealed = True
            layer1.constraints.sealed_bits = set(range(half))
            layer1.constraints.active_bits = set(range(n1))

            info2 = hm.check_and_encapsulate()
            if info2 is not None:
                assert hm.n_layers == 3

    def test_hierarchy_summary(self):
        """层级摘要"""
        hm = HierarchyManager(N0=12)
        summary = hm.get_hierarchy_summary()
        assert summary['n_layers'] == 1
        assert summary['current_layer'] == 0
        assert len(summary['layers']) == 1
        assert summary['layers'][0]['id'] == 0
        assert summary['layers'][0]['N'] == 12

    def test_step_on_sealed_layer(self):
        """封口后的层仍然可以运行（冻结比特不参与）"""
        hm = HierarchyManager(N0=8, binding_threshold=0.1, min_group_size=2)
        layer = hm.get_layer(0)
        layer.frozen_bits = {0, 1}
        layer.active_bits = {2, 3, 4, 5, 6, 7}
        layer.constraints.sealed = True
        layer.constraints.sealed_bits = {0, 1}
        layer.constraints.active_bits = set(range(8))

        result = hm.step_layer(0, n_steps=10)
        assert result['steps'] == 10
        # 冻结比特的值不应改变
        assert layer.state[0] == 0.0  # 初始为0，不会被翻转
        assert layer.state[1] == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
