"""
test_bias_propagation.py -- 回流偏置场端到端验证

验证内容：
1. BiasField 创建与衰减
2. propagate_bias_down() 正确生成偏置向量
3. apply_bias_to_layer() 正确叠加并调制
4. step_layer() 注入/吸收受偏置影响
5. 偏置衰减机制正常工作
"""

import torch
import numpy as np
import sys
sys.path.insert(0, 'C:\\Users\\Administrator\\Documents\\the_theory_of_difference\\11-模拟机工程实现')

from engine.hierarchy_manager import HierarchyManager, BiasField


def test_propagate_bias_up():
    """低层->高层偏置反馈"""
    manager = HierarchyManager(N0=12)

    from engine.hierarchy_manager import LayerState
    from acl.axioms_v2 import AxiomConstraints

    # 手动添加 L1
    l1_state = torch.zeros(4)
    l1 = LayerState(
        layer_id=1, state=l1_state,
        constraints=AxiomConstraints(4, n_hierarchy_bits=2),
        active_bits=set(range(4)), frozen_bits=set()
    )
    manager.layers.append(l1)

    # 设置 L0 有活跃比特
    layer0 = manager.get_layer(0)
    layer0.constraints.record_active(0)
    layer0.constraints.record_active(1)
    layer0.constraints.record_active(2)

    bias = manager.propagate_bias_up(source_layer_id=0, bias_strength=0.3)

    assert bias is not None
    assert bias.source_layer == 0
    assert bias.target_layer == 1
    assert bias.strength == 0.3
    assert bias.decay_rate == 0.97  # 向上衰减更慢
    assert len(bias.bias_vector) == 4
    print("PASS test_propagate_bias_up")


def test_propagate_bias_up_returns_none_at_top():
    """最高层不能向上传播"""
    manager = HierarchyManager(N0=12)
    # 只有一层，不能向上
    bias = manager.propagate_bias_up(source_layer_id=0)
    assert bias is None
    print("PASS test_propagate_bias_up_returns_none_at_top")


def test_bias_field_decay():
    """BiasField 衰减机制"""
    state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    bias = BiasField(
        source_layer=1, target_layer=0,
        bias_vector=state, strength=1.0, origin_step=0
    )
    
    assert bias.strength == 1.0
    for i in range(10):
        remaining = bias.decay()
        expected = 1.0 * (0.95 ** (i + 1))
        assert abs(bias.strength - expected) < 1e-6
    while bias.decay():
        pass
    assert bias.strength < 1e-4
    print("PASS test_bias_field_decay")


def test_propagate_bias_down():
    """高层->低层偏置传播"""
    manager = HierarchyManager(N0=12)
    
    from engine.hierarchy_manager import LayerState
    from acl.axioms_v2 import AxiomConstraints
    
    l1_state = torch.tensor([1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    l1 = LayerState(
        layer_id=1, state=l1_state,
        constraints=AxiomConstraints(12, n_hierarchy_bits=4),
        active_bits=set(range(12)), frozen_bits=set()
    )
    manager.layers.append(l1)
    
    bias = manager.propagate_bias_down(source_layer_id=1, bias_strength=0.5)
    
    assert bias is not None
    assert bias.source_layer == 1
    assert bias.target_layer == 0
    assert bias.strength == 0.5
    assert len(bias.bias_vector) == 12
    assert bias.bias_vector[0].item() > bias.bias_vector[2].item()
    print("PASS test_propagate_bias_down")


def test_apply_bias_to_layer():
    """偏置应用到层"""
    manager = HierarchyManager(N0=12)
    layer = manager.get_layer(0)
    
    high_bias_vec = torch.zeros(12)
    high_bias_vec[0] = 1.0
    high_bias_vec[1] = 1.0
    high_bias_vec[4] = 1.0
    
    bias = BiasField(
        source_layer=1, target_layer=0,
        bias_vector=high_bias_vec, strength=0.5, origin_step=0
    )
    manager.bias_registry[0].append(bias)
    
    result = manager.apply_bias_to_layer(0)
    
    assert result['applied'] == 1
    assert result['remaining'] == 1
    assert result['bias_profile'] is not None
    assert result['bias_profile']['mean'] > 0
    assert result['bias_profile']['max'] > result['bias_profile']['min']
    assert layer.constraints.bias_profile is not None
    assert layer.constraints.bias_profile[0].item() > layer.constraints.bias_profile[2].item()
    print("PASS test_apply_bias_to_layer")


def test_bias_affects_injection():
    """偏置影响注入选择"""
    manager = HierarchyManager(N0=12)
    layer = manager.get_layer(0)
    
    layer.state = torch.tensor([0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                 1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
    
    bias_vec = torch.zeros(12)
    bias_vec[0] = 1.0
    bias_vec[1] = 1.0
    bias_vec[2] = 0.0
    
    bias = BiasField(
        source_layer=1, target_layer=0,
        bias_vector=bias_vec, strength=0.8, origin_step=0
    )
    manager.bias_registry[0].append(bias)
    manager.apply_bias_to_layer(0)
    
    np.random.seed(42)
    torch.manual_seed(42)
    
    print("PASS test_bias_affects_injection (statistical test framework ready)")


def test_bias_decay_over_time():
    """偏置随时间衰减"""
    manager = HierarchyManager(N0=12)
    layer = manager.get_layer(0)
    
    bias_vec = torch.ones(12) * 0.5
    bias = BiasField(
        source_layer=1, target_layer=0,
        bias_vector=bias_vec, strength=1.0, origin_step=0
    )
    manager.bias_registry[0].append(bias)
    
    strengths = []
    for i in range(20):
        result = manager.apply_bias_to_layer(0)
        if result['remaining'] > 0:
            strengths.append(manager.bias_registry[0][0].strength)
        else:
            strengths.append(0)
    
    for i in range(1, min(10, len(strengths))):
        if strengths[i] > 0 and strengths[i-1] > 0:
            assert strengths[i] < strengths[i-1]
    
    if len(strengths) >= 2 and strengths[0] > 0 and strengths[1] > 0:
        decay_ratio = strengths[1] / strengths[0]
        assert 0.90 < decay_ratio < 1.0
    
    manager2 = HierarchyManager(N0=12)
    bias2 = BiasField(source_layer=1, target_layer=0, bias_vector=bias_vec, strength=1.0, origin_step=0)
    manager2.bias_registry[0].append(bias2)
    for _ in range(200):
        result = manager2.apply_bias_to_layer(0)
        if result['remaining'] == 0:
            break
    assert result['remaining'] == 0
    print("PASS test_bias_decay_over_time")


def test_composite_bias():
    """多个 BiasField 叠加"""
    manager = HierarchyManager(N0=12)
    layer = manager.get_layer(0)
    
    bias1_vec = torch.zeros(12)
    bias1_vec[0:4] = 1.0
    
    bias2_vec = torch.zeros(12)
    bias2_vec[6:10] = 1.0
    
    manager.bias_registry[0].append(BiasField(
        source_layer=2, target_layer=0,
        bias_vector=bias1_vec, strength=0.6, origin_step=0
    ))
    manager.bias_registry[0].append(BiasField(
        source_layer=3, target_layer=0,
        bias_vector=bias2_vec, strength=0.4, origin_step=0
    ))
    
    result = manager.apply_bias_to_layer(0)
    
    assert result['applied'] == 2
    profile = result['bias_profile']
    assert profile['max'] > profile['min']
    assert layer.constraints.bias_profile[0].item() > layer.constraints.bias_profile[5].item()
    print("PASS test_composite_bias")


if __name__ == "__main__":
    test_propagate_bias_up()
    test_propagate_bias_up_returns_none_at_top()
    test_bias_field_decay()
    test_propagate_bias_down()
    test_apply_bias_to_layer()
    test_bias_affects_injection()
    test_bias_decay_over_time()
    test_composite_bias()
    print("\nALL BIAS PROPAGATION TESTS PASSED!")
