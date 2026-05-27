"""
tests/test_semantic_firewall_guard.py — 回流通道语义防火墙守卫测试

测试 SemanticFirewallGuard 和 ReturnFlowChannel 的防火墙集成。
覆盖：
1. SemanticFirewallGuard 四层审查逻辑
2. SemanticFlowFirewallResult 数据类
3. ReturnFlowChannel 防火墙集成（有/无 guard、拦截计数等）
"""

import pytest
import torch
import numpy as np

from engine.return_flow_channel import (
    SemanticFirewallGuard,
    SemanticFlowFirewallResult,
    ReturnFlowChannel,
    HighSemanticPayload,
    AnchorPoint,
)


# ─── Fixtures ───

@pytest.fixture
def guard():
    """默认 SemanticFirewallGuard 实例"""
    return SemanticFirewallGuard()


@pytest.fixture
def strict_guard():
    """严格模式：降低向量范数阈值"""
    return SemanticFirewallGuard(max_safe_norm=1.0)


@pytest.fixture
def channel_no_guard():
    """无防火墙的回流通道"""
    return ReturnFlowChannel()


@pytest.fixture
def channel_with_guard():
    """带防火墙守卫的回流通道"""
    return ReturnFlowChannel(firewall_guard=SemanticFirewallGuard())


@pytest.fixture
def sample_payload():
    """标准测试载荷"""
    return HighSemanticPayload(
        payload_id="test_meaning_001",
        content_type="meaning",
        content_vector=torch.randn(8),
        created_at=0,
    )


@pytest.fixture
def strong_payload():
    """强范数载荷（超过默认阈值 10.0）"""
    return HighSemanticPayload(
        payload_id="test_strong_001",
        content_type="identity",
        content_vector=torch.randn(8) * 5.0,  # norm ≈ 5 * sqrt(8) ≈ 14.14 > 10.0
        created_at=0,
    )


@pytest.fixture
def available_structures():
    """标准可用结构"""
    return [
        {
            'structure_id': 0,
            'mechanisms': {
                'boundary': 0.8,
                'self_sustaining': 0.6,
                'retention': 0.7,
                'replication': 0.3,
                'selection': 0.5,
                'function': 0.9,
            }
        },
        {
            'structure_id': 1,
            'mechanisms': {
                'boundary': 0.4,
                'self_sustaining': 0.8,
                'retention': 0.3,
                'replication': 0.7,
                'selection': 0.6,
                'function': 0.5,
            }
        },
    ]


# ─── SemanticFlowFirewallResult ───

class TestSemanticFlowFirewallResult:

    def test_default_is_clean(self):
        result = SemanticFlowFirewallResult()
        assert result.passed is True
        assert result.is_clean is True
        assert result.violations == []

    def test_failed_not_clean(self):
        result = SemanticFlowFirewallResult(
            passed=False,
            violations=["some violation"],
        )
        assert result.is_clean is False

    def test_repr_passed(self):
        result = SemanticFlowFirewallResult(
            passed=True,
            content_type_checked='meaning',
            mechanism_checked='function',
        )
        repr_str = repr(result)
        assert "PASSED" in repr_str
        assert "meaning" in repr_str

    def test_repr_failed(self):
        result = SemanticFlowFirewallResult(
            passed=False,
            violations=["dangerous combination"],
        )
        repr_str = repr(result)
        assert "FAILED" in repr_str
        assert "dangerous combination" in repr_str


# ─── SemanticFirewallGuard 初始化 ───

class TestSemanticFirewallGuardInit:

    def test_default_init(self, guard):
        assert guard.max_safe_norm == 10.0
        assert 'identity' in guard.forbidden_terms
        assert 'boundary' in guard.allowed_mechanisms

    def test_custom_max_norm(self, strict_guard):
        assert strict_guard.max_safe_norm == 1.0

    def test_custom_forbidden_terms(self):
        custom_forbidden = {'custom_term'}
        guard = SemanticFirewallGuard(forbidden_terms=custom_forbidden)
        assert guard.forbidden_terms == custom_forbidden

    def test_custom_allowed_mechanisms(self):
        custom_allowed = {'boundary', 'function'}
        guard = SemanticFirewallGuard(allowed_mechanisms=custom_allowed)
        assert guard.allowed_mechanisms == custom_allowed


# ─── 层1：内容类型白名单检查 ───

class TestContentTypeCheck:

    def test_valid_content_types(self, guard):
        for ct in ['meaning', 'institution', 'narrative', 'identity']:
            assert guard.check_content_type(ct) is True

    def test_invalid_content_type(self, guard):
        assert guard.check_content_type('consciousness') is False
        assert guard.check_content_type('self_awareness') is False
        assert guard.check_content_type('') is False

    def test_check_anchor_invalid_content_type(self, guard):
        result = guard.check_anchor(
            content_type='consciousness',
            mechanism='function',
        )
        assert result.passed is False
        assert any("not in allowed high-semantic" in v for v in result.violations)


# ─── 层2：锚点机制白名单检查 ───

class TestMechanismCheck:

    def test_valid_mechanisms(self, guard):
        for mech in ['boundary', 'self_sustaining', 'retention',
                      'replication', 'selection', 'function']:
            assert guard.check_mechanism(mech) is True

    def test_invalid_mechanism(self, guard):
        assert guard.check_mechanism('identity') is False
        assert guard.check_mechanism('will') is False
        assert guard.check_mechanism('consciousness') is False

    def test_check_anchor_invalid_mechanism(self, guard):
        result = guard.check_anchor(
            content_type='meaning',
            mechanism='consciousness',
        )
        assert result.passed is False
        assert any("not in low-semantic" in v for v in result.violations)


# ─── 层3：危险组合检查 ───

class TestDangerousCombination:

    def test_identity_not_on_function(self, guard):
        result = guard.check_anchor(
            content_type='identity',
            mechanism='function',
        )
        assert result.passed is False
        assert any("dangerous combination" in v for v in result.violations)

    def test_meaning_not_on_boundary(self, guard):
        result = guard.check_anchor(
            content_type='meaning',
            mechanism='boundary',
        )
        assert result.passed is False
        assert any("dangerous combination" in v for v in result.violations)

    def test_institution_not_on_replication(self, guard):
        result = guard.check_anchor(
            content_type='institution',
            mechanism='replication',
        )
        assert result.passed is False

    def test_narrative_not_on_function(self, guard):
        result = guard.check_anchor(
            content_type='narrative',
            mechanism='function',
        )
        assert result.passed is False

    def test_safe_combinations_pass(self, guard):
        safe_combos = [
            ('meaning', 'function'),
            ('meaning', 'selection'),
            ('institution', 'boundary'),
            ('institution', 'self_sustaining'),
            ('narrative', 'retention'),
            ('narrative', 'replication'),
            ('identity', 'boundary'),
            ('identity', 'self_sustaining'),
        ]
        for ct, mech in safe_combos:
            result = guard.check_anchor(content_type=ct, mechanism=mech)
            assert result.passed is True, f"Expected {ct}+{mech} to pass"

    def test_custom_dangerous_combinations(self):
        custom_dangerous = {
            'meaning': {'retention'},
        }
        guard = SemanticFirewallGuard(dangerous_combinations=custom_dangerous)
        result = guard.check_anchor(content_type='meaning', mechanism='retention')
        assert result.passed is False

    def test_get_safe_mechanisms(self, guard):
        safe = guard.get_safe_mechanisms('identity')
        assert 'function' not in safe
        assert 'boundary' in safe
        assert 'self_sustaining' in safe

    def test_get_safe_mechanisms_all_safe(self, guard):
        safe = guard.get_safe_mechanisms('meaning')
        assert 'boundary' not in safe
        assert 'function' in safe


# ─── 层4：向量范数检查 ───

class TestVectorNormCheck:

    def test_normal_vector_passes(self, guard):
        vec = torch.randn(8)  # norm ≈ sqrt(8) ≈ 2.83 < 10.0
        result = guard.check_anchor(
            content_type='meaning',
            mechanism='function',
            content_vector=vec,
        )
        assert result.passed is True

    def test_strong_vector_fails(self, guard):
        vec = torch.ones(8) * 5.0  # norm = sqrt(8 * 25) = sqrt(200) ≈ 14.14 > 10.0
        result = guard.check_anchor(
            content_type='meaning',
            mechanism='function',
            content_vector=vec,
        )
        assert result.passed is False
        assert any("norm" in v and "exceeds" in v for v in result.violations)

    def test_strict_guard_low_threshold(self, strict_guard):
        vec = torch.ones(8) * 0.5  # norm = sqrt(8 * 0.25) = sqrt(2) ≈ 1.41 > 1.0
        result = strict_guard.check_anchor(
            content_type='meaning',
            mechanism='function',
            content_vector=vec,
        )
        assert result.passed is False

    def test_no_vector_skips_norm_check(self, guard):
        result = guard.check_anchor(
            content_type='meaning',
            mechanism='function',
            content_vector=None,
        )
        assert result.passed is True
        assert result.n_checked == 3  # 层1+2+3，层4跳过

    def test_zero_vector_passes(self, guard):
        vec = torch.zeros(8)
        result = guard.check_anchor(
            content_type='meaning',
            mechanism='function',
            content_vector=vec,
        )
        assert result.passed is True


# ─── 完整四层审查 ───

class TestFullFourLayerCheck:

    def test_all_layers_pass(self, guard):
        result = guard.check_anchor(
            content_type='meaning',
            mechanism='function',
            content_vector=torch.randn(4),
            payload_id='test_001',
        )
        assert result.passed is True
        assert result.n_checked == 4
        assert result.content_type_checked == 'meaning'
        assert result.mechanism_checked == 'function'

    def test_multiple_violations(self, guard):
        """多个层同时违规"""
        result = guard.check_anchor(
            content_type='invalid_type',
            mechanism='invalid_mech',
            content_vector=torch.ones(100) * 2.0,  # norm = 20.0 > 10.0
            payload_id='test_multi',
        )
        assert result.passed is False
        # 层1 (invalid_type) + 层2 (invalid_mech) + 层4 (norm exceed) = 3 violations
        # 层3 不触发因为 'invalid_type' 不在 DANGEROUS_COMBINATIONS 中
        assert len(result.violations) >= 3

    def test_n_checked_counts_correctly(self, guard):
        """n_checked 应正确反映检查层数"""
        # 无向量：3层
        r1 = guard.check_anchor('meaning', 'function')
        assert r1.n_checked == 3

        # 有向量：4层
        r2 = guard.check_anchor('meaning', 'function', content_vector=torch.randn(4))
        assert r2.n_checked == 4


# ─── ReturnFlowChannel 防火墙集成 ───

class TestReturnFlowChannelFirewallIntegration:

    def test_channel_without_guard_works(self, channel_no_guard, sample_payload, available_structures):
        """无防火墙的通道应正常工作（向后兼容）"""
        assert channel_no_guard.has_firewall is False
        event = channel_no_guard.attempt_anchor(sample_payload, available_structures, timestamp=0)
        assert event.success is True

    def test_channel_with_guard_works(self, channel_with_guard, sample_payload, available_structures):
        """有防火墙的通道在载荷安全时应正常锚定"""
        assert channel_with_guard.has_firewall is True
        event = channel_with_guard.attempt_anchor(sample_payload, available_structures, timestamp=0)
        assert event.success is True

    def test_firewall_blocks_dangerous_combination(self, channel_with_guard, available_structures):
        """防火墙应拦截危险组合"""
        payload = HighSemanticPayload(
            payload_id="test_identity_001",
            content_type="identity",
            content_vector=torch.randn(4),
        )
        # identity 的最佳锚点是 boundary（权重 0.5），但 structure 0 的 boundary=0.8
        # identity + boundary 是安全的，需要构造一个会选到 function 的场景
        structures = [{
            'structure_id': 0,
            'mechanisms': {
                'boundary': 0.1,  # 低分，不会选
                'self_sustaining': 0.1,
                'function': 0.9,   # 高分，会被选为最佳
            }
        }]
        event = channel_with_guard.attempt_anchor(payload, structures, timestamp=0)
        # identity + function 是危险组合，应被拦截
        assert event.success is False
        assert "dangerous combination" in event.reason or "firewall" in event.reason.lower()

    def test_firewall_block_count_increments(self, channel_with_guard):
        """防火墙拦截计数应正确递增"""
        assert channel_with_guard.firewall_block_count == 0
        # 构造一个会被拦截的载荷
        payload = HighSemanticPayload(
            payload_id="block_test",
            content_type="identity",
            content_vector=torch.randn(4),
        )
        structures = [{
            'structure_id': 0,
            'mechanisms': {
                'boundary': 0.1,
                'function': 0.9,
            }
        }]
        channel_with_guard.attempt_anchor(payload, structures, timestamp=0)
        assert channel_with_guard.firewall_block_count == 1

    def test_set_firewall_guard(self, channel_no_guard):
        """应能动态设置/移除防火墙守卫"""
        assert channel_no_guard.has_firewall is False
        guard = SemanticFirewallGuard()
        channel_no_guard.set_firewall_guard(guard)
        assert channel_no_guard.has_firewall is True
        channel_no_guard.set_firewall_guard(None)
        assert channel_no_guard.has_firewall is False

    def test_get_firewall_guard(self, channel_with_guard):
        guard = channel_with_guard.get_firewall_guard()
        assert isinstance(guard, SemanticFirewallGuard)

    def test_clear_resets_firewall_blocks(self, channel_with_guard):
        """clear 应重置防火墙拦截计数"""
        payload = HighSemanticPayload(
            payload_id="block_test",
            content_type="identity",
            content_vector=torch.randn(4),
        )
        structures = [{
            'structure_id': 0,
            'mechanisms': {'boundary': 0.1, 'function': 0.9}
        }]
        channel_with_guard.attempt_anchor(payload, structures, timestamp=0)
        assert channel_with_guard.firewall_block_count >= 1
        channel_with_guard.clear()
        assert channel_with_guard.firewall_block_count == 0

    def test_backward_compat_no_guard(self):
        """完全不传 guard 的通道应与旧行为一致"""
        channel = ReturnFlowChannel(
            anchor_threshold=0.3,
            decay_rate=0.01,
            min_retention_steps=10,
        )
        assert channel.has_firewall is False
        assert channel.firewall_block_count == 0

        payload = HighSemanticPayload(
            payload_id="compat_test",
            content_type="meaning",
            content_vector=torch.randn(4),
        )
        structures = [{
            'structure_id': 0,
            'mechanisms': {'function': 0.9, 'selection': 0.5}
        }]
        event = channel.attempt_anchor(payload, structures, timestamp=0)
        assert event.success is True

    def test_firewall_with_strong_vector(self):
        """防火墙应拦截范数过大的载荷"""
        guard = SemanticFirewallGuard(max_safe_norm=1.0)
        channel = ReturnFlowChannel(firewall_guard=guard)
        payload = HighSemanticPayload(
            payload_id="strong_test",
            content_type="meaning",
            content_vector=torch.ones(8) * 2.0,  # norm ≈ 5.66 > 1.0
        )
        structures = [{
            'structure_id': 0,
            'mechanisms': {'function': 0.9}
        }]
        event = channel.attempt_anchor(payload, structures, timestamp=0)
        assert event.success is False
        assert channel.firewall_block_count == 1

    def test_step_still_works_with_guard(self, channel_with_guard, sample_payload, available_structures):
        """有防火墙的通道，step 应正常工作"""
        channel_with_guard.attempt_anchor(sample_payload, available_structures, timestamp=0)
        events = channel_with_guard.step(timestamp=1)
        # step 应正常执行，返回列表（可能为空）
        assert isinstance(events, list)

    def test_rollout_with_firewall(self, channel_with_guard):
        """有防火墙的通道应能完成多步 rollout"""
        for t in range(20):
            if t % 5 == 0:
                payload = HighSemanticPayload(
                    payload_id=f"rollout_{t}",
                    content_type="meaning",
                    content_vector=torch.randn(4) * 0.5,  # 低范数，安全
                )
                structures = [{
                    'structure_id': 0,
                    'mechanisms': {'function': 0.8, 'selection': 0.6}
                }]
                channel_with_guard.attempt_anchor(payload, structures, timestamp=t)
            channel_with_guard.step(timestamp=t)
        # 应正常完成，无异常
        assert channel_with_guard.get_total_events() > 0
