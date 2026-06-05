"""
tests/test_bias_field.py — 回流偏置场测试

覆盖 propagate_bias_down, propagate_bias_up, apply_bias_to_layer,
check_unseal_with_backflow 等回流通道机制。
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hierarchy_manager import HierarchyManager, LayerState, BiasField
from acl.axioms_v2 import AxiomConstraints


def _setup_two_layer_hierarchy():
    """辅助：创建已封装的两层结构"""
    hm = HierarchyManager(N0=12, binding_threshold=0.1, min_group_size=2)

    layer0 = hm.get_layer(0)
    layer0.frozen_bits = {0, 1, 2, 3}
    layer0.active_bits = {4, 5, 6, 7, 8, 9, 10, 11}
    for i in range(4):
        for j in range(4):
            if i != j:
                layer0.constraints.binding_strength[i, j] = 0.5
    layer0.constraints.sealed = True
    layer0.constraints.sealed_bits = {0, 1, 2, 3}
    layer0.constraints.active_bits = {i: 0 for i in range(12)}

    hm.check_and_encapsulate()
    return hm


class TestPropagateBiasDown:
    """向下传播偏置测试"""

    def test_basic(self):
        """高层状态向下传播偏置"""
        hm = _setup_two_layer_hierarchy()
        assert hm.n_layers == 2

        layer1 = hm.get_layer(1)
        layer1.state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
        layer1.step_count = 10

        bias = hm.propagate_bias_down(source_layer_id=1, bias_strength=0.3)
        assert bias is not None
        assert bias.source_layer == 1
        assert bias.target_layer == 0
        assert bias.strength == pytest.approx(0.3)
        assert len(bias.bias_vector) == hm.get_layer(0).n_bits

    def test_decay(self):
        """偏置强度随时间衰减"""
        hm = _setup_two_layer_hierarchy()
        hm.get_layer(1).state = torch.tensor([1.0, 0.0, 0.0])

        bias = hm.propagate_bias_down(1, bias_strength=0.5)
        assert bias.strength == pytest.approx(0.5)

        bias.decay()
        assert bias.strength == pytest.approx(0.5 * 0.95)

        for _ in range(200):
            bias.decay()
        assert bias.strength < 1e-4

    def test_l0_cannot_propagate_down(self):
        """L0 没有更低的层"""
        hm = HierarchyManager(N0=12)
        bias = hm.propagate_bias_down(0)
        assert bias is None


class TestPropagateBiasUp:
    """向上传播偏置测试"""

    def test_basic(self):
        """低层活跃模式向上反馈至高层"""
        hm = _setup_two_layer_hierarchy()
        assert hm.n_layers == 2

        layer0 = hm.get_layer(0)
        layer0.constraints.active_bits = {i: 0 for i in [4, 5, 6, 7, 8, 9]}

        bias = hm.propagate_bias_up(source_layer_id=0, bias_strength=0.2)
        assert bias is not None
        assert bias.source_layer == 0
        assert bias.target_layer == 1
        assert len(bias.bias_vector) == hm.get_layer(1).n_bits
        assert bias.decay_rate == pytest.approx(0.97)

    def test_no_active_pattern(self):
        """低层无活跃模式时不生成偏置"""
        hm = _setup_two_layer_hierarchy()

        layer0 = hm.get_layer(0)
        layer0.constraints.active_bits = {}

        bias = hm.propagate_bias_up(0)
        assert bias is None

    def test_top_layer_cannot_propagate_up(self):
        """最高层不能向上传播偏置"""
        hm = _setup_two_layer_hierarchy()
        bias = hm.propagate_bias_up(1)
        assert bias is None

    def test_bias_vector_content_correct_indexing(self):
        """验证向上传播的偏置向量索引正确（修复 encapsulated_idx bug 后的回归测试）

        设计说明：propagate_bias_up 使用 constraints.active_bits（历史活跃记录）
        而非 state > 0.5（当前激活）来构建 active_pattern。这符合"前主体态是
        诸机制汇聚的整体状态"的理论——活跃是历史累积的，不是瞬时状态。

        场景：L0 有 4 个冻结比特（0-3）封装为 L1 的封装比特，
        L0 的活跃比特（4-11）全部在 active_bits 中，验证偏置向量正确映射。
        """
        hm = _setup_two_layer_hierarchy()
        assert hm.n_layers == 2

        layer0 = hm.get_layer(0)
        layer1 = hm.get_layer(1)

        # 封装组：{0,1,2,3} -> L1 的封装比特 0
        # 活跃比特：4-11 直接映射到 L1 的位置 0-7
        # L1 总比特数 = 8 活跃 + 1 封装 = 9
        layer0.constraints.active_bits = {i: 0 for i in range(4, 12)}

        bias = hm.propagate_bias_up(source_layer_id=0, bias_strength=0.2)
        assert bias is not None

        # 验证：封装比特（L1 位置 = n_active + 0）的偏置值
        # 封装组的源比特是 {0,1,2,3}，不在 active_bits 中 -> 偏置 = 0
        # 注意：encapsulated_bits 以基底层号存储，L0 的封装结果存在 key=0
        encap_bits = hm.encap_engine.encapsulated_bits.get(0, [])
        assert len(encap_bits) == 1
        enc_bit = encap_bits[0]
        n_active_in_l1 = layer1.n_bits - len(encap_bits)
        encap_idx = n_active_in_l1 + enc_bit.bit_id
        if encap_idx < layer1.n_bits:
            # 封装比特源全部不在 active_bits 中，偏置应为 0
            assert bias.bias_vector[encap_idx].item() == pytest.approx(0.0, abs=1e-6)

        # 活跃比特（4-11）在 L1 中直接映射到位置 0-7，偏置应为 1.0
        for local_idx in range(n_active_in_l1):
            assert bias.bias_vector[local_idx].item() == pytest.approx(1.0, abs=1e-6)

    def test_bias_up_with_partial_active(self):
        """部分活跃比特向上传播：验证偏置向量的空间分布"""
        hm = _setup_two_layer_hierarchy()
        layer0 = hm.get_layer(0)
        layer1 = hm.get_layer(1)

        # 封装组：{0,1,2,3} -> L1 封装比特 0（位置 = n_active + 0 = 8）
        # 活跃比特：0,1（封装源的一部分）+ 4,5（纯活跃）
        # 直接映射：未被封装的比特按索引排序后依次映射到 L1 位置 0-7
        #   未被封装的比特 = [4,5,6,7,8,9,10,11]（排序后）
        #   L1 pos 0 <- L0 bit 4 (active=1), pos 1 <- L0 bit 5 (active=1)
        #   pos 2-7 <- L0 bit 6-11 (all inactive=0)
        layer0.constraints.active_bits = {i: 0 for i in [0, 1, 4, 5]}

        bias = hm.propagate_bias_up(source_layer_id=0, bias_strength=0.2)
        assert bias is not None

        encap_bits = hm.encap_engine.encapsulated_bits.get(0, [])
        assert len(encap_bits) == 1
        n_active_in_l1 = layer1.n_bits - len(encap_bits)

        # 直接映射：L1 pos 0 <- L0 bit 4 (active), pos 1 <- L0 bit 5 (active)
        assert bias.bias_vector[0].item() == pytest.approx(1.0, abs=1e-6)
        assert bias.bias_vector[1].item() == pytest.approx(1.0, abs=1e-6)
        # pos 2-7 <- L0 bit 6-11 (all inactive)
        for i in range(2, n_active_in_l1):
            assert bias.bias_vector[i].item() == pytest.approx(0.0, abs=1e-6)
        # 封装比特位置（L1 pos 8）：源比特 {0,1,2,3} 中 {0,1} 活跃 -> 偏置 = 2/4 = 0.5
        encap_idx = n_active_in_l1 + encap_bits[0].bit_id
        if encap_idx < layer1.n_bits:
            assert bias.bias_vector[encap_idx].item() == pytest.approx(0.5, abs=1e-6)


class TestApplyBiasToLayer:
    """偏置应用测试"""

    def test_with_bias(self):
        """有偏置时正确应用"""
        hm = _setup_two_layer_hierarchy()
        hm.get_layer(1).state = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0])

        hm.propagate_bias_down(1, bias_strength=0.3)

        result = hm.apply_bias_to_layer(0)
        assert result['applied'] == 1
        assert result['remaining'] >= 0
        assert result['bias_profile'] is not None
        assert result['bias_profile']['n_bits'] == 12
        assert 0.0 <= result['bias_profile']['mean'] <= 1.0

        assert hasattr(hm.get_layer(0).constraints, 'bias_profile')
        assert hm.get_layer(0).constraints.bias_profile is not None

    def test_empty(self):
        """无偏置时返回空结果"""
        hm = HierarchyManager(N0=12)
        result = hm.apply_bias_to_layer(0)
        assert result['applied'] == 0
        assert result['remaining'] == 0
        assert result['bias_profile'] is None

    def test_multiple_fields叠加(self):
        """多个偏置场叠加"""
        hm = _setup_two_layer_hierarchy()
        hm.get_layer(1).state = torch.tensor([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        hm.propagate_bias_down(1, bias_strength=0.3)
        hm.propagate_bias_down(1, bias_strength=0.2)

        assert len(hm.bias_registry[0]) == 2

        result = hm.apply_bias_to_layer(0)
        assert result['applied'] == 2
        assert result['bias_profile'] is not None


class TestCheckUnsealWithBackflow:
    """解封触发回流测试"""

    def test_backflow_on_unseal(self):
        """解封时触发回流"""
        hm = _setup_two_layer_hierarchy()
        assert hm.n_layers == 2

        hm.get_layer(1).state = torch.tensor([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        result = hm.check_unseal_with_backflow(1)
        assert 'unsealed' in result
        assert 'backflow' in result
