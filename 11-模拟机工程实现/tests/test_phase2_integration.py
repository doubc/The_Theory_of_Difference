"""
tests/test_phase2_integration.py — Phase 2 端到端集成测试

覆盖完整的 Phase 2 管线：
  底象检测(XiangDetector) → 象界显现链(XiangjieChain) → 前主体态收束(PreSubjectivityConvergence)
  → 解封机制(UnsealingMechanism) → 回流通道(ReturnFlowChannel)

测试策略：不运行完整演化（太慢），而是用合成数据驱动各组件，
验证数据流和状态转换的正确性。
"""

import sys
import os
import torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.unsealing_mechanism import UnsealingMechanism
from engine.return_flow_channel import (
    ReturnFlowChannel,
    HighSemanticPayload,
    LOW_SEMANTIC_MECHANISMS,
)
from engine.xiang_detector import XiàngDetector
from xiangjie.chain import XiangjieChain


# ─── 辅助：合成高语义载荷 ───

def _make_payload(pid, ctype, dim=4):
    """创建测试用高语义载荷"""
    return HighSemanticPayload(
        payload_id=pid,
        content_type=ctype,
        content_vector=torch.randn(dim),
        created_at=0,
    )


def _make_structures(n=3):
    """创建测试用低语义结构列表"""
    structures = []
    for i in range(n):
        structures.append({
            'structure_id': i,
            'mechanisms': {
                'boundary': 0.3 + 0.2 * i,
                'self_sustaining': 0.2 + 0.15 * i,
                'retention': 0.1 + 0.1 * i,
                'replication': 0.2 + 0.1 * i,
                'selection': 0.15 + 0.1 * i,
                'function': 0.25 + 0.2 * i,
            },
        })
    return structures


# ─── 测试 1: 完整管线 — 从底象检测到回流锚定 ───

def test_full_phase2_pipeline():
    """端到端：底象 → 象界链 → 收束 → 解封 → 回流锚定"""
    # 1. 底象检测
    xiang = XiàngDetector()
    N = 8
    # 创建一个差异矩阵：高组织密度
    D = torch.zeros(N, N)
    for i in range(N):
        for j in range(N):
            D[i, j] = 1.0 if abs(i - j) <= 2 else 0.1
    D.fill_diagonal_(0)
    D = (D + D.T) / 2

    xiang_result = xiang.detect(D, timestamp=0)
    # 底象检测至少能运行（不一定形成，取决于参数）
    assert xiang_result is not None
    print(f"  [Xiàng] formed={xiang_result.xiang_formed}, "
          f"density={xiang_result.organization_density:.3f}")

    # 2. 象界显现链
    from layers.hamming_layer import StableStructure
    chain = XiangjieChain()
    state = torch.ones(N) * 0.5
    # 构造最小 StableStructure 列表
    mask = torch.ones(N, dtype=torch.bool)
    struct = StableStructure(
        mask=mask,
        lifetime=10,
        pattern_signature=state,
        boundary_map=mask.float(),
        material_turnover=0.1,
        source_layer="hamming_layer",
    )
    report = chain.evaluate([struct], history=[state], current_state=state)
    assert report is not None
    assert report.max_stage_reached >= 0
    print(f"  [Xiangjie] max_stage={report.max_stage_name}({report.max_stage_reached}), "
          f"pre_subjective={report.is_pre_subjective}")

    # 3. 前主体态收束
    convergence = PreSubjectivityConvergence()
    six_detector = SixThresholdDetector()

    # 构造满足 SixThresholdDetector 的参数 (6/6 thresholds)
    threshold_params = {
        'active_exchanges': 8,
        'total_boundary_edges': 10,
        'rebuild_success_count': 6,
        'perturbation_count': 10,
        'bias_recursion_depth': 5.0,
        'replicated_pattern': torch.ones(8),
        'original_pattern': torch.ones(8),
        'variant_continuation_probs': {
            'var_A': 0.9, 'var_B': 0.2,
        },
        'component_contributions': {
            'comp_A': 0.8, 'comp_B': 0.1, 'comp_C': 0.1,
        },
    }

    # 构造强耦合矩阵
    mechanisms = PreSubjectivityConvergence.MECHANISMS
    coupling_matrix = {}
    for ma in mechanisms:
        coupling_matrix[ma] = {}
        for mb in mechanisms:
            if ma == mb:
                coupling_matrix[ma][mb] = 1.0
            else:
                coupling_matrix[ma][mb] = 0.8  # 强耦合

    # 构造结构状态
    structure_state = torch.ones(8) * 0.6
    w_lo, w_hi = 3.0, 6.0
    def structure_fn(s):
        w = s.float().sum().item()
        return w_lo <= w <= w_hi

    conv_result = convergence.evaluate(
        threshold_params=threshold_params,
        coupling_matrix=coupling_matrix,
        structure_state=structure_state,
        structure_fn=structure_fn,
        timestamp=100,
    )
    assert conv_result.all_conditions_met, (
        f"Expected all conditions met, got: {conv_result}"
    )
    assert conv_result.converged
    print(f"  [Convergence] converged=True, stability={conv_result.stability_score:.3f}")

    # 4. 解封机制
    unsealing = UnsealingMechanism()
    event = unsealing.evaluate(
        structure_id=0,
        convergence_result=conv_result,
        timestamp=100,
    )
    assert event is not None, "Expected unsealing event on first evaluation"
    assert event.unsealing_level >= 1
    assert event.high_semantic_capacity > 0
    print(f"  [Unsealing] level={event.unsealing_level}, "
          f"capacity={event.high_semantic_capacity:.3f}")

    # 5. 回流通道锚定
    return_flow = ReturnFlowChannel(anchor_threshold=0.2)
    payload = _make_payload("meaning_test", "meaning")
    structures = _make_structures(3)

    rf_event = return_flow.attempt_anchor(payload, structures, timestamp=100)
    assert rf_event.success, f"Expected anchor success, got: {rf_event.reason}"
    assert rf_event.anchor.structure_id >= 0
    assert rf_event.anchor.mechanism in LOW_SEMANTIC_MECHANISMS
    print(f"  [ReturnFlow] anchored to struct#{rf_event.anchor.structure_id}/"
          f"{rf_event.anchor.mechanism}, strength={rf_event.residual_strength:.3f}")

    print("[PASS] test_full_phase2_pipeline: full pipeline executed successfully")


# ─── 测试 2: 解封等级升级与降级 ───

def test_unsealing_level_progression():
    """测试解封等级随收束强度变化而升级/降级"""
    unsealing = UnsealingMechanism(
        l1_coupling_threshold=0.3,
        l1_stability_threshold=0.5,
        l2_coupling_threshold=0.5,
        l2_stability_threshold=0.7,
        l3_coupling_threshold=0.7,
        l3_stability_threshold=0.85,
    )
    convergence = PreSubjectivityConvergence()

    # Step 1: 弱收束 → Level 1
    from engine.pre_subjectivity_convergence import ConvergenceResult
    weak_result = ConvergenceResult(
        converged=True,
        six_thresholds_met=True,
        coupling_strength_met=True,
        stability_met=True,
        semantic_firewall_passed=True,
        n_coupled_pairs=10,
        min_coupling=0.35,
        stability_score=0.55,
        timestamp=1,
    )
    event = unsealing.evaluate(0, weak_result, timestamp=1)
    assert event is not None
    assert event.unsealing_level == 1

    # Step 2: 强收束 → Level 3
    strong_result = ConvergenceResult(
        converged=True,
        six_thresholds_met=True,
        coupling_strength_met=True,
        stability_met=True,
        semantic_firewall_passed=True,
        n_coupled_pairs=15,
        min_coupling=0.8,
        stability_score=0.9,
        timestamp=2,
    )
    event = unsealing.evaluate(0, strong_result, timestamp=2)
    assert event is not None
    assert event.unsealing_level == 3

    # Step 3: 收束失败 → Level 0
    fail_result = ConvergenceResult(
        converged=False,
        six_thresholds_met=False,
        coupling_strength_met=False,
        stability_met=False,
        semantic_firewall_passed=True,
        n_coupled_pairs=2,
        min_coupling=0.1,
        stability_score=0.2,
        timestamp=3,
    )
    event = unsealing.evaluate(0, fail_result, timestamp=3)
    assert event is not None
    assert event.unsealing_level == 0

    print("[PASS] test_unsealing_level_progression: L1→L3→L0 progression correct")


# ─── 测试 3: 回流通道完整生命周期 ───

def test_return_flow_lifecycle():
    """测试回流通道完整生命周期：锚定 → 衰减 → 剥离"""
    channel = ReturnFlowChannel(
        anchor_threshold=0.25,
        decay_rate=0.05,
        min_retention_steps=3,
    )
    structures = _make_structures(3)

    # 锚定 4 种不同类型
    types = ['meaning', 'institution', 'narrative', 'identity']
    for i, ctype in enumerate(types):
        payload = _make_payload(f"payload_{ctype}", ctype)
        event = channel.attempt_anchor(payload, structures, timestamp=100)
        assert event.success, f"Failed to anchor {ctype}: {event.reason}"

    assert channel.get_anchored_count() == 4
    assert channel.get_success_rate() == 1.0

    # 衰减 + 剥离
    strip_count = 0
    for t in range(200, 220):
        events = channel.step(timestamp=t)
        strip_count += len(events)

    # 所有内容最终都应被剥离
    assert channel.get_anchored_count() == 0
    assert strip_count == 4
    print(f"[PASS] test_return_flow_lifecycle: 4 payloads anchored, "
          f"{strip_count} stripped, count=0")


# ─── 测试 4: 多结构独立解封 ───

def test_multi_structure_unsealing():
    """Test multiple structures with independent unsealing levels"""
    from engine.pre_subjectivity_convergence import ConvergenceResult
    unsealing = UnsealingMechanism()

    def make_result(coupling, stability):
        return ConvergenceResult(
            converged=True, six_thresholds_met=True,
            coupling_strength_met=True, stability_met=True,
            semantic_firewall_passed=True, n_coupled_pairs=10,
            min_coupling=coupling, stability_score=stability, timestamp=0,
        )

    # Structure 0: Level 1
    r1 = make_result(0.35, 0.55)
    e1 = unsealing.evaluate(0, r1, timestamp=1)
    assert e1 is not None and e1.unsealing_level == 1

    # Structure 1: Level 3
    r2 = make_result(0.8, 0.9)
    e2 = unsealing.evaluate(1, r2, timestamp=1)
    assert e2 is not None and e2.unsealing_level == 3

    # Structure 2: upgrade to L1, then downgrade to L0
    r3_up = make_result(0.35, 0.55)
    e3_up = unsealing.evaluate(2, r3_up, timestamp=1)
    assert e3_up is not None and e3_up.unsealing_level == 1

    r3_down = ConvergenceResult(
        converged=False, six_thresholds_met=False,
        coupling_strength_met=False, stability_met=False,
        semantic_firewall_passed=True, n_coupled_pairs=0,
        min_coupling=0.0, stability_score=0.0, timestamp=2,
    )
    e3 = unsealing.evaluate(2, r3_down, timestamp=2)
    assert e3 is not None and e3.unsealing_level == 0

    assert unsealing.get_current_level(0) == 1
    assert unsealing.get_current_level(1) == 3
    assert unsealing.get_current_level(2) == 0

    by_level = unsealing.get_structures_by_level()
    assert 1 in by_level and 3 in by_level

    print("[PASS] test_multi_structure_unsealing: 3 structures with independent levels")


def test_semantic_firewall_with_return_flow():
    """测试语义防火墙阻止高语义类型锚定到非低语义机制"""
    channel = ReturnFlowChannel()
    payload = _make_payload("meaning_001", "meaning")

    # 使用包含高语义机制名称的结构（应该被防火墙拦截）
    bad_structures = [
        {'structure_id': 1, 'mechanisms': {
            'meaning': 0.9,  # ← 高语义机制，不是低语义锚点
            'identity': 0.8,  # ← 同上
        }},
    ]

    # 注意：当前实现中，_select_best_anchor 会从 ANCHOR_WEIGHTS 中选择
    # 而 ANCHOR_WEIGHTS 的键都是 LOW_SEMANTIC_MECHANISMS 的子集
    # 所以 'meaning' 和 'identity' 不会被匹配到，返回 None → "无可用锚点"
    event = channel.attempt_anchor(payload, bad_structures, timestamp=0)
    assert not event.success
    assert channel.get_anchored_count() == 0

    # 正常低语义结构应成功
    good_structures = [
        {'structure_id': 1, 'mechanisms': {
            'function': 0.9,
            'selection': 0.8,
        }},
    ]
    event = channel.attempt_anchor(payload, good_structures, timestamp=1)
    assert event.success

    print("[PASS] test_semantic_firewall_with_return_flow: high-sem mechanism rejected")


# ─── 测试 6: HierarchicalEvolver Phase 2 集成 ───

def test_hierarchical_evolver_phase2_integration():
    """测试 HierarchicalEvolver 与 Phase 2 组件的完整集成"""
    from engine.hierarchical_evolver import HierarchicalEvolver
    from engine.unsealing_mechanism import UnsealingMechanism
    from engine.return_flow_channel import ReturnFlowChannel
    from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
    from engine.six_threshold_detector import SixThresholdDetector
    from engine.xiang_detector import XiàngDetector
    from engine.persistent_bias_memory import PersistentBiasMemory
    from engine.cumulative_selector import CumulativeSelector

    # 创建 Phase 2 组件
    xiang = XiàngDetector()
    bias_memory = PersistentBiasMemory()
    selector = CumulativeSelector()
    six = SixThresholdDetector()
    convergence = PreSubjectivityConvergence()
    unsealing = UnsealingMechanism()
    return_flow = ReturnFlowChannel()

    # 创建 HierarchicalEvolver（小参数，快速运行）
    # 使用 max_layers=1 避免封装未触发时访问不存在的层
    # 重点验证 Phase 2 组件在演化中的集成，而非多层封装
    evolver = HierarchicalEvolver(
        N0=12,
        steps_per_layer=50,
        sample_interval=25,
        max_layers=1,
        auto_encapsulate=False,
        xiang_detector=xiang,
        persistent_bias_memory=bias_memory,
        cumulative_selector=selector,
        six_threshold_detector=six,
        pre_subjectivity_convergence=convergence,
        unsealing_mechanism=unsealing,
        return_flow_channel=return_flow,
        p1_eval_interval=10,
        phase2_verbose=False,
    )

    # 运行短演化
    results = evolver.run(verbose=False)

    # 验证 Phase 2 组件被激活
    p2 = results['phase2_summary']
    assert p2['xiang_detector_active']
    assert p2['six_threshold_detector_active']
    assert p2['pre_subjectivity_convergence_active']
    assert p2['unsealing_mechanism_active']
    assert p2['return_flow_channel_active']

    # 验证有层结果
    assert len(p2['layers_with_results']) > 0

    # 验证查询接口
    unsealing_status = evolver.get_unsealing_status()
    assert isinstance(unsealing_status, dict)

    rf_status = evolver.get_return_flow_status()
    assert isinstance(rf_status, dict)
    assert 'anchored_count' in rf_status

    print(f"[PASS] test_hierarchical_evolver_phase2_integration: "
          f"all Phase 2 components active, "
          f"layers={p2['layers_with_results']}, "
          f"bias_entries={p2['bias_memory_entries']}")


# ─── 测试 7: 界面模式稳定性追踪 ───

def test_interface_pattern_stability_integration():
    """测试界面模式稳定性追踪在解封机制中的集成"""
    unsealing = UnsealingMechanism(
        interface_stability_window=3,
        interface_stability_threshold=0.7,
    )

    # 记录 3 次相同的界面交换模式
    for t in range(3):
        stability = unsealing.record_interface_exchange(
            structure_id=0,
            timestamp=t,
            channel_pattern={'A': 0.6, 'B': 0.3, 'C': 0.1},
            total_active=10,
            total_edges=20,
        )

    # 3 次相同模式 → 稳定性应达到 1.0
    assert unsealing.is_interface_stable(0)

    tracker = unsealing.get_interface_stability(0)
    assert tracker is not None
    assert tracker.n_records == 3
    assert tracker.dominant_channels == ['A', 'B', 'C']

    print("[PASS] test_interface_pattern_stability_integration: "
          f"stability={tracker.current_stability:.3f}, stable={tracker.is_stable}")


if __name__ == "__main__":
    test_full_phase2_pipeline()
    test_unsealing_level_progression()
    test_return_flow_lifecycle()
    test_multi_structure_unsealing()
    test_semantic_firewall_with_return_flow()
    test_hierarchical_evolver_phase2_integration()
    test_interface_pattern_stability_integration()
    print("\n[OK] All Phase 2 integration tests passed!")
