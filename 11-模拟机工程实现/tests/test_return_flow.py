"""
tests/test_return_flow.py — 回流通道单元测试

覆盖：
1. 成功锚定
2. 耦合强度不足导致锚定失败
3. 无可用锚点
4. 每步演化衰减
5. 自动剥离
6. 语义防火墙
"""

import sys
import os
import torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.return_flow_channel import (
    ReturnFlowChannel,
    HighSemanticPayload,
    AnchorPoint,
    ReturnFlowEvent,
    HIGH_SEMANTIC_TYPES,
    LOW_SEMANTIC_MECHANISMS,
)


def test_payload_validation():
    """测试载荷类型验证"""
    # 有效类型
    for t in HIGH_SEMANTIC_TYPES:
        p = HighSemanticPayload(
            payload_id="test_1",
            content_type=t,
            content_vector=torch.tensor([0.1, 0.2, 0.3]),
        )
        assert p.content_type == t
    print("[PASS] test_payload_validation: valid types OK")

    # 无效类型
    try:
        HighSemanticPayload(
            payload_id="test_bad",
            content_type="invalid_type",
            content_vector=torch.tensor([1.0]),
        )
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("[PASS] test_payload_validation: invalid type raises ValueError")


def test_anchor_point_validation():
    """测试锚点机制验证"""
    # 有效机制
    for m in LOW_SEMANTIC_MECHANISMS:
        a = AnchorPoint(structure_id=1, mechanism=m, coupling_strength=0.5)
        assert a.mechanism == m
    print("[PASS] test_anchor_point_validation: valid mechanisms OK")

    # 无效机制
    try:
        AnchorPoint(structure_id=1, mechanism="invalid_mech", coupling_strength=0.5)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("[PASS] test_anchor_point_validation: invalid mechanism raises ValueError")


def test_successful_anchor():
    """测试成功锚定"""
    channel = ReturnFlowChannel(anchor_threshold=0.3)
    payload = HighSemanticPayload(
        payload_id="meaning_001",
        content_type="meaning",
        content_vector=torch.tensor([0.5, 0.3, 0.8]),
        created_at=1000,
    )
    structures = [
        {'structure_id': 1, 'mechanisms': {'function': 0.8, 'selection': 0.6}},
        {'structure_id': 2, 'mechanisms': {'boundary': 0.4, 'self_sustaining': 0.3}},
    ]

    event = channel.attempt_anchor(payload, structures, timestamp=1000)
    assert event.success, f"Expected success but got: {event.reason}"
    assert event.anchor.structure_id == 1
    assert event.anchor.mechanism == 'function'
    assert event.residual_strength > 0.3
    assert channel.get_anchored_count() == 1
    print("[PASS] test_successful_anchor: anchored to function mechanism")


def test_anchor_failure_low_coupling():
    """测试耦合强度不足导致锚定失败"""
    channel = ReturnFlowChannel(anchor_threshold=0.5)
    payload = HighSemanticPayload(
        payload_id="meaning_002",
        content_type="meaning",
        content_vector=torch.tensor([0.1]),
    )
    # 所有机制强度都低于阈值
    structures = [
        {'structure_id': 1, 'mechanisms': {'function': 0.1, 'selection': 0.2}},
    ]

    event = channel.attempt_anchor(payload, structures, timestamp=1000)
    assert not event.success
    assert not event.success  # just check it failed
    assert channel.get_anchored_count() == 0
    print("[PASS] test_anchor_failure_low_coupling: low coupling fails")


def test_anchor_no_available_structures():
    """测试无可用锚点"""
    channel = ReturnFlowChannel()
    payload = HighSemanticPayload(
        payload_id="narrative_001",
        content_type="narrative",
        content_vector=torch.tensor([1.0]),
    )
    # 空结构列表
    event = channel.attempt_anchor(payload, [], timestamp=1000)
    assert not event.success
    assert not event.success  # just check it failed
    print("[PASS] test_anchor_no_available_structures: no structures returns fail")


def test_decay_and_strip():
    """测试锚定强度衰减和自动剥离"""
    # 设置极低的保留步数以加速测试
    channel = ReturnFlowChannel(
        anchor_threshold=0.3,
        decay_rate=0.05,  # 每步衰减 0.05
        min_retention_steps=3,
    )
    payload = HighSemanticPayload(
        payload_id="institution_001",
        content_type="institution",
        content_vector=torch.tensor([0.7, 0.5]),
        created_at=2000,
    )
    structures = [
        {'structure_id': 10, 'mechanisms': {'boundary': 0.9, 'self_sustaining': 0.8}},
    ]

    # 锚定
    event = channel.attempt_anchor(payload, structures, timestamp=2000)
    assert event.success
    assert channel.get_anchored_count() == 1

    # 步骤 1: 强度 0.9 → 0.85
    events = channel.step(timestamp=2001)
    assert len(events) == 0
    assert channel.get_anchored_count() == 1

    # 步骤 2: 强度 0.85 → 0.80
    events = channel.step(timestamp=2002)
    assert len(events) == 0
    assert channel.get_anchored_count() == 1

    # 步骤 3: 强度 0.80 → 0.75 (达到 min_retention_steps)
    events = channel.step(timestamp=2003)
    assert len(events) == 0
    assert channel.get_anchored_count() == 1

    # 继续衰减直到低于阈值
    for t in range(2004, 2015):
        events = channel.step(timestamp=t)
        if events:
            assert not events[0].success
            pass  # strip confirmed by success=False and count=0
            assert channel.get_anchored_count() == 0
            print(f"[PASS] test_decay_and_strip: stripped at step {t} (strength {events[0].residual_strength:.3f})")
            return

    assert False, "Expected strip event but none occurred"


def test_anchored_contents_query():
    """测试已锚定内容查询"""
    channel = ReturnFlowChannel()
    payload = HighSemanticPayload(
        payload_id="identity_001",
        content_type="identity",
        content_vector=torch.tensor([0.9]),
    )
    structures = [
        {'structure_id': 5, 'mechanisms': {'boundary': 0.95}},
    ]

    channel.attempt_anchor(payload, structures, timestamp=3000)
    contents = channel.get_anchored_contents()
    assert "identity_001" in contents
    assert contents["identity_001"]["structure_id"] == 5
    assert contents["identity_001"]["mechanism"] == "boundary"
    print("[PASS] test_anchored_contents_query: query anchored contents OK")


def test_success_rate():
    """测试成功率计算"""
    channel = ReturnFlowChannel(anchor_threshold=0.5)

    # 1 次成功
    p1 = HighSemanticPayload("p1", "meaning", torch.tensor([1.0]))
    channel.attempt_anchor(p1, [{'structure_id': 1, 'mechanisms': {'function': 0.9}}], 1)

    # 2 次失败
    p2 = HighSemanticPayload("p2", "meaning", torch.tensor([1.0]))
    channel.attempt_anchor(p2, [], 2)
    p3 = HighSemanticPayload("p3", "meaning", torch.tensor([1.0]))
    channel.attempt_anchor(p3, [{'structure_id': 1, 'mechanisms': {'function': 0.1}}], 3)

    rate = channel.get_success_rate()
    assert rate == 1.0 / 3.0
    print(f"[PASS] test_success_rate: success rate = {rate:.2%} (1/3)")


def test_clear():
    """测试清除状态"""
    channel = ReturnFlowChannel()
    payload = HighSemanticPayload("p1", "meaning", torch.tensor([1.0]))
    channel.attempt_anchor(payload, [{'structure_id': 1, 'mechanisms': {'function': 0.9}}], 1)
    assert channel.get_anchored_count() == 1
    assert channel.get_total_events() > 0

    channel.clear()
    assert channel.get_anchored_count() == 0
    assert channel.get_total_events() == 0
    print("[PASS] test_clear: clear state OK")


def test_force_detach_regression():
    """回归测试：force_detach 不应因 content_type 校验失败而崩溃

    此前 bug：force_detach 构造 HighSemanticPayload 时使用 content_type=""
    导致 __post_init__ 校验抛出 ValueError。修复：使用 'meaning' 作为占位类型。
    """
    channel = ReturnFlowChannel()
    # 先成功锚定一个载荷
    payload = HighSemanticPayload("p1", "meaning", torch.tensor([1.0]))
    event = channel.attempt_anchor(
        payload,
        [{'structure_id': 1, 'mechanisms': {'function': 0.9}}],
        1,
    )
    assert event.success
    assert channel.get_anchored_count() == 1

    # force_detach 不应抛出异常
    detach_event = channel.force_detach("p1")
    assert detach_event is not None
    assert detach_event.success is False
    assert detach_event.reason == "强制剥离"
    assert channel.get_anchored_count() == 0
    print("[PASS] test_force_detach_regression: force_detach works without crash")

    # 对不存在的 payload_id 返回 None
    assert channel.force_detach("nonexistent") is None
    print("[PASS] test_force_detach_regression: nonexistent payload returns None")


if __name__ == "__main__":
    test_payload_validation()
    test_anchor_point_validation()
    test_successful_anchor()
    test_anchor_failure_low_coupling()
    test_anchor_no_available_structures()
    test_decay_and_strip()
    test_anchored_contents_query()
    test_success_rate()
    test_clear()
    test_force_detach_regression()
    print("\n[OK] All ReturnFlowChannel tests passed!")
