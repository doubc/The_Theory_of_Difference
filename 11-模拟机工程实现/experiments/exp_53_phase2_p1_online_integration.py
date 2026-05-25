"""
experiments/exp_53_phase2_p1_online_integration.py
  Phase 2 P1 Online Integration Test

楠岃瘉 SixThresholdDetector + PreSubjectivityConvergence
鍦ㄦ紨鍖栧惊鐜腑鐨勫湪绾块泦鎴愩€?
涓?exp_52 鐨勫尯鍒細
- exp_52: 鍙泦鎴?P0 缁勪欢锛圶i脿ngDetector + PersistentBiasMemory + CumulativeSelector锛?- exp_53: 鍚屾椂闆嗘垚 P0 + P1 缁勪欢锛圫ixThresholdDetector + PreSubjectivityConvergence锛?
杩欐槸 Phase 2 浠?绂荤嚎鍒嗘瀽"鍒?瀹屾暣鍦ㄧ嚎鍒ゅ畾"鐨勫叧閿竴姝ャ€?
Acceptance criteria:
  1. 鎵€鏈?6 涓?Phase 2 缁勪欢鍦ㄦ紨鍖栧惊鐜腑琚皟鐢?  2. SixThresholdDetector 姣?p1_eval_interval 姝ヨ緭鍑洪槇鍊兼娴嬬粨鏋?  3. PreSubjectivityConvergence 姣?p1_eval_interval 姝ヨ緭鍑烘敹鏉熷垽瀹?  4. 婕斿寲缁撴潫鍚?phase2_summary 鍖呭惈 P1 鐘舵€?  5. 瀹為獙鎬昏€楁椂 < 60s锛圢=32, 2000 steps/layer锛?"""

import torch
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.xiang_detector import Xi脿ngDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence


def main():
    print("=" * 70)
    print("exp_53: Phase 2 P1 Online Integration Test")
    print("  P0: Xi脿ngDetector + PersistentBiasMemory + CumulativeSelector")
    print("  P1: SixThresholdDetector + PreSubjectivityConvergence")
    print("=" * 70)

    # Parameters
    N0 = 32
    steps_per_layer = 2000
    sample_interval = 200
    max_layers = 3

    # Init Phase 2 P0 components
    xiang = Xi脿ngDetector(rho_threshold=0.3, tau_threshold=0.5)
    bias_mem = PersistentBiasMemory(max_history_depth=50)
    selector = CumulativeSelector(window_size=10, trend_threshold=0.5)

    # Init Phase 2 P1 components
    six_thresh = SixThresholdDetector()
    convergence = PreSubjectivityConvergence(
        coupling_threshold=0.3,
        stability_threshold=0.5,
    )

    # Create evolver with all Phase 2 components
    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps_per_layer,
        sample_interval=sample_interval,
        max_layers=max_layers,
        device="cpu",
        auto_encapsulate=True,
        # P0
        xiang_detector=xiang,
        persistent_bias_memory=bias_mem,
        cumulative_selector=selector,
        # P1
        six_threshold_detector=six_thresh,
        pre_subjectivity_convergence=convergence,
        p1_eval_interval=5,
        phase2_verbose=True,
    )

    # Run
    t0 = time.time()
    results = evolver.run(verbose=True)
    elapsed = time.time() - t0

    # 鈹€鈹€ Results 鈹€鈹€
    print("\n" + "=" * 70)
    print("exp_53 RESULTS")
    print("=" * 70)

    p2s = results['phase2_summary']
    print(f"\n  Phase 2 Summary:")
    print(f"    P0 Xi脿ngDetector active:     {p2s['xiang_detector_active']}")
    print(f"    P0 bias_memory_entries:      {p2s['bias_memory_entries']}")
    print(f"    P0 CumulativeSelector active:{p2s['cumulative_selector_active']}")
    print(f"    P1 SixThreshold active:      {p2s['six_threshold_detector_active']}")
    print(f"    P1 Convergence active:       {p2s['pre_subjectivity_convergence_active']}")
    print(f"    P1 converged:                {p2s['pre_subjectivity_converged']}")
    print(f"    P1 convergence_step:         {p2s['convergence_step']}")
    print(f"    Layers with results:         {p2s['layers_with_results']}")

    # Per-layer Xi脿ng summary
    for lr in results['layer_results']:
        layer_id = lr['layer']
        print(f"\n  Layer {layer_id}: N={lr['N']}, w={lr['w']}, "
              f"sealed={lr['sealed']}, steps={lr['steps']}")
        if 'phase2_xiang_summary' in lr:
            xs = lr['phase2_xiang_summary']
            print(f"    Xi脿ng: first_formed={xs['first_formed_step']}, "
                  f"max_density={xs['max_density']:.3f}, "
                  f"max_trace={xs['max_trace']:.3f}, "
                  f"checks={xs['n_checks']}, formed={xs['n_formed']}")

    # SixThreshold history summary
    if six_thresh._history:
        print(f"\n  SixThresholdDetector history ({len(six_thresh._history)} evaluations):")
        history_summary = six_thresh.get_history_summary(last_n=10)
        print(f"    avg_n_met: {history_summary.get('avg_n_met', 0):.2f}")
        print(f"    all_met_count: {history_summary.get('all_met_count', 0)}")
        print(f"    latest_bottleneck: {history_summary.get('latest_bottleneck', 'N/A')}")
        # Show last 3 evaluations
        for r in six_thresh._history[-3:]:
            print(f"    step={r.timestamp}: {r.n_met}/6 "
                  f"{'PASS' if r.all_met else 'FAIL bottleneck=' + str(r.bottleneck)}")

    # Convergence history summary
    if convergence._convergence_history:
        print(f"\n  PreSubjectivityConvergence history ({len(convergence._convergence_history)} evaluations):")
        conv_summary = convergence.get_history_summary(last_n=10)
        print(f"    n_converged: {conv_summary.get('n_converged', 0)}")
        print(f"    first_convergence_step: {conv_summary.get('first_convergence_step', 'N/A')}")
        print(f"    avg_stability: {conv_summary.get('avg_stability', 0):.3f}")
        # Show last 3 evaluations
        for r in convergence._convergence_history[-3:]:
            print(f"    step={r.timestamp}: "
                  f"{'CONVERGED' if r.converged else 'NOT converged'} "
                  f"(thresholds={r.six_thresholds_met}, "
                  f"coupling={r.coupling_strength_met}, "
                  f"stability={r.stability_met})")

    print(f"\n  Wall time: {elapsed:.1f}s")

    # 鈹€鈹€ Acceptance checks 鈹€鈹€
    print("\n" + "-" * 70)
    print("ACCEPTANCE CHECKS")
    print("-" * 70)

    checks = []

    # 1. All 6 components active
    all_active = (p2s['xiang_detector_active'] and
                  p2s['cumulative_selector_active'] and
                  p2s['six_threshold_detector_active'] and
                  p2s['pre_subjectivity_convergence_active'])
    checks.append(("All Phase 2 components active", all_active))

    # 2. SixThresholdDetector was called
    st_called = len(six_thresh._history) > 0
    checks.append(("SixThresholdDetector called", st_called))

    # 3. PreSubjectivityConvergence was called
    conv_called = len(convergence._convergence_history) > 0
    checks.append(("PreSubjectivityConvergence called", conv_called))

    # 4. phase2_summary contains P1
    p1_summary = (p2s['six_threshold_detector_active'] and
                  p2s['pre_subjectivity_convergence_active'])
    checks.append(("phase2_summary contains P1", p1_summary))

    # 5. Time < 60s
    time_ok = elapsed < 60
    checks.append((f"Wall time < 60s ({elapsed:.1f}s)", time_ok))

    all_pass = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")

    print("-" * 70)
    if all_pass:
        print("ALL CHECKS PASSED 鉁?)
    else:
        print("SOME CHECKS FAILED 鉁?)
    print("-" * 70)

    return all_pass


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)

