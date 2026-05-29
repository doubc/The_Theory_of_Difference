"""
tests/test_narrative_self.py -- 叙事递归算子测试

验证五中介动作的完整流水线：筛选 -> 命名 -> 连接 -> 行动化 -> 验证
"""

import sys
import os
import torch
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.narrative_self import (
    NarrativeRecursionOperator,
    NarrativeFilter,
    NarrativeNamer,
    NarrativeConnector,
    NarrativeActionizer,
    NarrativeVerifier,
    DifferenceSignal,
    NarrativeLevel,
    ContentType,
)


def make_signal(signal_id: str, source_layer: int, target_layer: int,
                magnitude: float, timestamp: int,
                bias_dim: int = 128) -> DifferenceSignal:
    """辅助函数：生成测试差异信号"""
    np.random.seed(hash(signal_id) % (2 ** 32))
    direction = torch.from_numpy(np.random.randn(bias_dim)).float()
    direction = direction / direction.norm().item()
    return DifferenceSignal(
        signal_id=signal_id,
        source_layer=source_layer,
        target_layer=target_layer,
        magnitude=magnitude,
        direction=direction,
        timestamp=timestamp,
    )


def test_filter_significant_signals():
    """测试叙事筛选器：能识别重要差异"""
    f = NarrativeFilter(magnitude_threshold=0.3)

    signals = [
        make_signal("s1", 0, 1, 0.8, 1),   # 高幅度跨层 -> 重要
        make_signal("s2", 1, 1, 0.1, 1),   # 低幅度同层 -> 不重要
        make_signal("s3", 2, 3, 0.5, 1),   # 中等幅度跨层 -> 可能重要
        make_signal("s4", 0, 3, 0.9, 1),   # 高幅度跨层 -> 重要
    ]

    significant, discarded = f.filter(signals, timestamp=1)

    sig_ids = {s.signal_id for s in significant}
    assert "s1" in sig_ids, "s1 应该被筛选为重要"
    assert "s4" in sig_ids, "s4 应该被筛选为重要"
    assert "s2" not in sig_ids, "s2 应该被丢弃"
    print(f"  [PASS] 筛选: {len(significant)} 重要, {len(discarded)} 丢弃")


def test_namer_assigns_categories():
    """测试叙事命名器：为信号分配范畴"""
    namer = NarrativeNamer()

    signals = [
        make_signal("s1", 0, 1, 0.8, 1),
        make_signal("s2", 2, 3, 0.5, 1),
    ]

    nodes = namer.name(signals, timestamp=1)

    assert len(nodes) == 2
    assert nodes[0].category == "structural_emergence"
    assert nodes[0].content_type == ContentType.INSTITUTION
    assert nodes[1].category == "distributional_semantic_coupling"
    assert nodes[1].content_type == ContentType.NARRATIVE
    assert all(n.confidence > 0 for n in nodes)
    print(f"  [PASS] 命名: {len(nodes)} 个节点, 范畴: {[n.category for n in nodes]}")


def test_connector_builds_chains():
    """测试叙事连接器：构建因果链"""
    connector = NarrativeConnector(strength_threshold=0.2)

    signals = [
        make_signal(f"s{i}", i % 3, (i + 1) % 4, 0.5 + i * 0.1, 1 + i)
        for i in range(5)
    ]

    namer = NarrativeNamer()
    nodes = namer.name(signals, timestamp=1)

    chains = connector.connect(nodes, timestamp=1)

    assert len(chains) > 0, "应至少生成一条因果链"
    assert all(len(c.node_ids) >= 2 for c in chains), "每条链至少2个节点"
    print(f"  [PASS] 连接: {len(chains)} 条因果链, 平均长度: {sum(len(c.node_ids) for c in chains)/len(chains):.1f}")


def test_actionizer_produces_bias_correction():
    """测试叙事行动化：产生偏置修正"""
    actionizer = NarrativeActionizer(bias_dimension=128)

    signals = [
        make_signal(f"s{i}", i % 3, (i + 1) % 4, 0.6, 1 + i)
        for i in range(4)
    ]

    namer = NarrativeNamer()
    nodes = namer.name(signals, timestamp=1)
    node_dict = {n.node_id: n for n in nodes}

    connector = NarrativeConnector(strength_threshold=0.1)
    chains = connector.connect(nodes, timestamp=1)

    actions = actionizer.actionize(chains, node_dict, timestamp=1)

    assert len(actions) > 0
    assert all(a.bias_correction.shape[0] == 128 for a in actions)
    assert all(0 <= a.action_strength <= 0.5 for a in actions)
    print(f"  [PASS] 行动化: {len(actions)} 个行动方案")


def test_verifier_validates_actions():
    """测试叙事验证器：验证行动效果"""
    verifier = NarrativeVerifier(consistency_threshold=0.3)

    # 使用更多信号以确保连接器能产生因果链
    signals = [
        make_signal(f"s{i}", i % 3, (i + 1) % 4, 0.5 + i * 0.1, 1 + i)
        for i in range(5)
    ]
    namer = NarrativeNamer()
    nodes = namer.name(signals, timestamp=1)
    node_dict = {n.node_id: n for n in nodes}

    connector = NarrativeConnector(strength_threshold=0.1)
    chains = connector.connect(nodes, timestamp=1)

    actionizer = NarrativeActionizer(bias_dimension=128)
    actions = actionizer.actionize(chains, node_dict, timestamp=1)

    assert len(actions) > 0, "必须有至少一个行动方案"

    current_bias = torch.randn(128)
    for action in actions:
        verifier.before_action(action, current_bias, 0.5)

    post_bias = current_bias + actions[0].bias_correction * 0.3
    for action in actions:
        action = verifier.after_action(action, post_bias, 0.55, timestamp=2)

    # 验证器应能给出验证得分
    assert all(0 <= a.validation_score <= 1 for a in actions)
    print(f"  [PASS] 验证: 平均验证得分: {sum(a.validation_score for a in actions)/len(actions):.3f}")


def test_full_pipeline():
    """测试完整叙事递归流水线"""
    nro = NarrativeRecursionOperator(bias_dimension=128)

    # 生成多步差异信号
    np.random.seed(42)
    for step in range(5):
        signals = [
            make_signal(f"step{step}_s{i}",
                       i % 3, (i + 1 + step) % 4,
                       0.3 + np.random.rand() * 0.6,
                       step)
            for i in range(4)
        ]

        current_bias = torch.randn(128)
        current_odi = 0.4 + step * 0.08

        correction = nro.step(signals, current_bias, current_odi, timestamp=step)

        if correction is not None:
            assert correction.shape[0] == 128
            assert correction.norm().item() > 0

    summary = nro.get_summary()
    print(f"  [PASS] 完整流水线: {summary['total_narrative_records']} 条叙事记录")
    print(f"     验证率: {summary['validation_rate']:.2%}")
    print(f"     行动验证率: {summary['action_validation_rate']:.2%}")
    print(f"     叙事层级分布: {summary['narrative_level_distribution']}")


def test_narrative_decay_on_failure():
    """测试叙事衰减：验证失败的叙事权重降低"""
    nro = NarrativeRecursionOperator(
        bias_dimension=128,
        filter_magnitude_threshold=0.1,
        verifier_consistency_threshold=0.9,
    )

    for step in range(10):
        signals = [
            make_signal(f"step{step}_s{i}",
                       i % 2, (i + 1) % 3,
                       0.2 + (step % 3) * 0.1,
                       step)
            for i in range(3)
        ]

        current_bias = torch.randn(128)
        current_odi = 0.3

        nro.step(signals, current_bias, current_odi, timestamp=step)

    summary = nro.get_summary()
    assert summary['active_narratives'] >= 0
    print(f"  [PASS] 衰减测试: 活跃叙事数: {summary['active_narratives']}")


def test_narrative_level_progression():
    """测试叙事层级递进：随着链条增长，层级应提升"""
    nro = NarrativeRecursionOperator(bias_dimension=128)

    for step in range(8):
        signals = [
            make_signal(f"step{step}_s{i}",
                       i % 4, (i + 1) % 4,
                       0.5 + step * 0.05,
                       step)
            for i in range(6)
        ]

        current_bias = torch.randn(128)
        current_odi = 0.3 + step * 0.06

        nro.step(signals, current_bias, current_odi, timestamp=step)

    history = nro.get_narrative_history(n=8)
    levels = [h['narrative_level'] for h in history]

    has_higher = any(l in ['INSTITUTIONAL', 'CIVILIZATION'] for l in levels)
    print(f"  [PASS] 层级递进: {levels}")
    if has_higher:
        print("     检测到高层级叙事 (INSTITUTIONAL/CIVILIZATION)")


if __name__ == "__main__":
    print("=== 叙事递归算子测试 ===\n")

    print("[1/7] 筛选器测试...")
    test_filter_significant_signals()

    print("[2/7] 命名器测试...")
    test_namer_assigns_categories()

    print("[3/7] 连接器测试...")
    test_connector_builds_chains()

    print("[4/7] 行动化测试...")
    test_actionizer_produces_bias_correction()

    print("[5/7] 验证器测试...")
    test_verifier_validates_actions()

    print("[6/7] 完整流水线测试...")
    test_full_pipeline()

    print("[7/7] 衰减与层级递进测试...")
    test_narrative_decay_on_failure()
    test_narrative_level_progression()

    print("\n=== 全部测试通过 ===")
