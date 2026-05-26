"""
experiments/exp_55_phase2_coupling_fix.py — Phase 2 耦合矩阵 + 结构函数修复实验

验证三项修复：
1. 3.5 选择压力：改用 CumulativeSelector.get_fate_divergence() 全局命运分岔
2. coupling_matrix：从方向场相关性计算机制间耦合强度
3. structure_fn：汉明重量 ±20% 结构保持函数

对比基线：exp_54（N=48, 5000 steps/layer）
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from engine.hierarchical_evolver import HierarchicalEvolver
from engine.xiang_detector import XiàngDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence


def run_exp_55():
    print("=" * 70)
    print("EXP-55: Phase 2 coupling_matrix + structure_fn fix")
    print("=" * 70)

    N = 48
    steps_per_layer = 5000
    sample_interval = 500

    # Phase 2 组件
    xiang_detector = XiàngDetector()
    bias_memory = PersistentBiasMemory()
    cumulative_selector = CumulativeSelector()
    six_threshold = SixThresholdDetector()
    convergence = PreSubjectivityConvergence(
        coupling_threshold=0.3,
        stability_threshold=0.5,
        n_perturbation_tests=5,
        perturbation_scale=0.1,
    )

    evolver = HierarchicalEvolver(
        N0=N,
        steps_per_layer=steps_per_layer,
        sample_interval=sample_interval,
        max_layers=3,
        device="cpu",
        auto_encapsulate=True,
        xiang_detector=xiang_detector,
        persistent_bias_memory=bias_memory,
        cumulative_selector=cumulative_selector,
        six_threshold_detector=six_threshold,
        pre_subjectivity_convergence=convergence,
        p1_eval_interval=5,
        phase2_verbose=True,
    )

    t0 = time.time()
    results = evolver.run(verbose=True)
    elapsed = time.time() - t0

    print(f"\n{'=' * 70}")
    print(f"EXP-55 RESULTS ({elapsed:.1f}s)")
    print(f"{'=' * 70}")

    # 层级结构
    print("\n--- Layer Structure ---")
    for lr in results['layer_results']:
        n_active = len(lr['active_bits'])
        n_frozen = lr['N'] - n_active
        print(f"  L{lr['layer']}: N={lr['N']}, w={lr['w']}, "
              f"active={n_active}, frozen={n_frozen}, "
              f"sealed={lr['sealed']}, steps={lr['steps']}, "
              f"inj={lr['inj']}, abs={lr['abs']}, cycles={lr['cycles']}")

    # Phase 2: SixThreshold 汇总
    print("\n--- SixThresholdDetector Summary ---")
    history = six_threshold._history
    if history:
        recent = history[-10:]
        pass_count = sum(1 for r in recent if r.all_met)
        avg_met = sum(r.n_met for r in recent) / len(recent)
        print(f"  Total detections: {len(history)}")
        print(f"  Recent {len(recent)}: {pass_count} ALL_MET, avg {avg_met:.1f}/6")

        # 各阈值通过率
        threshold_pass = {f"{i+1}.{j}": 0 for j in range(1, 7) for i in [0]}
        names = ['3.1', '3.2', '3.3', '3.4', '3.5', '3.6']
        for r in recent:
            for s in r.threshold_statuses:
                if s.is_met:
                    threshold_pass[s.threshold_id] = threshold_pass.get(s.threshold_id, 0) + 1
        print("  Threshold pass rates (recent):")
        for name in names:
            rate = threshold_pass.get(name, 0) / len(recent) * 100
            print(f"    {name}: {rate:.1f}% ({threshold_pass.get(name, 0)}/{len(recent)})")

    # Phase 2: Convergence 汇总
    print("\n--- PreSubjectivityConvergence Summary ---")
    conv_history = convergence._convergence_history
    if conv_history:
        recent_c = conv_history[-10:]
        conv_pass = sum(1 for r in recent_c if r.converged)
        print(f"  Total evaluations: {len(conv_history)}")
        print(f"  Recent {len(recent_c)}: {conv_pass} CONVERGED")
        print(f"  Conditions (recent):")
        print(f"    thresholds: {sum(1 for r in recent_c if r.six_thresholds_met)}/{len(recent_c)}")
        print(f"    coupling:   {sum(1 for r in recent_c if r.coupling_strength_met)}/{len(recent_c)}")
        print(f"    stability:  {sum(1 for r in recent_c if r.stability_met)}/{len(recent_c)}")
        print(f"    firewall:   {sum(1 for r in recent_c if r.semantic_firewall_passed)}/{len(recent_c)}")
        avg_coupled = sum(r.n_coupled_pairs for r in recent_c) / len(recent_c)
        avg_stability = sum(r.stability_score for r in recent_c) / len(recent_c)
        print(f"  Avg coupled pairs: {avg_coupled:.1f}/15")
        print(f"  Avg stability score: {avg_stability:.3f}")

    # Phase 2: XiàngDetector 汇总
    print("\n--- XiàngDetector Summary ---")
    for lr in results['layer_results']:
        if 'phase2_xiang_summary' in lr:
            xs = lr['phase2_xiang_summary']
            print(f"  L{lr['layer']}: checks={xs['n_checks']}, "
                  f"formed={xs['n_formed']}, "
                  f"max_density={xs['max_density']:.3f}, "
                  f"max_trace={xs['max_trace']:.3f}, "
                  f"first_step={xs['first_formed_step']}")

    # CumulativeSelector 命运分岔
    print("\n--- CumulativeSelector Fate Divergence ---")
    fate = cumulative_selector.get_fate_divergence()
    if fate:
        probs = list(fate.values())
        print(f"  Total variants: {len(fate)}")
        print(f"  Fate range: [{min(probs):.3f}, {max(probs):.3f}], "
              f"spread={max(probs)-min(probs):.3f}")
        top = cumulative_selector.get_dominant_variants(5)
        print(f"  Top variants: {top[:3]}")

    print(f"\n{'=' * 70}")
    print("EXP-55 COMPLETE")
    print(f"{'=' * 70}")

    return results


if __name__ == '__main__':
    run_exp_55()
