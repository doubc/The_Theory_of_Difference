"""
experiments/exp_54_phase2_large_scale.py
  Phase 2 Large-Scale Experiment - N=48, 5000 steps/layer

Purpose:
  Run full Phase 2 online detection at larger scale (N=48) and longer
  duration (5000 steps/layer) to observe:
  1. Whether SixThresholdDetector gets closer to convergence
  2. Whether PreSubjectivityConvergence can converge at larger N
  3. XiàngDetector bottom-xiang formation patterns across layers
  4. How bottleneck threshold (currently 3.6 functional differentiation) changes at larger N

Difference from exp_53:
  - exp_53: N=32, 2000 steps/layer, 3 layers
  - exp_54: N=48, 5000 steps/layer, 3 layers

Acceptance criteria:
  1. All 6 Phase 2 components called during evolution
  2. SixThresholdDetector executes >= 10 evaluations
  3. PreSubjectivityConvergence executes >= 10 evaluations
  4. At least 2 layers complete evolution
  5. Total wall time < 120s
  6. Per-layer bottleneck analysis output
"""

import torch
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.xiang_detector import XiàngDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence


def main():
    print("=" * 70)
    print("exp_54: Phase 2 Large-Scale Experiment")
    print("  N=48, 5000 steps/layer, 3 layers")
    print("  P0: XiàngDetector + PersistentBiasMemory + CumulativeSelector")
    print("  P1: SixThresholdDetector + PreSubjectivityConvergence")
    print("=" * 70)

    # Parameters
    N0 = 48
    steps_per_layer = 5000
    sample_interval = 500
    max_layers = 3

    # Init Phase 2 P0 components
    xiang = XiàngDetector(rho_threshold=0.3, tau_threshold=0.5)
    bias_mem = PersistentBiasMemory(max_history_depth=100)
    selector = CumulativeSelector(window_size=20, trend_threshold=0.5)

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

    # --- Results ---
    print("\n" + "=" * 70)
    print("exp_54 RESULTS")
    print("=" * 70)

    p2s = results['phase2_summary']
    print(f"\n  Phase 2 Summary:")
    print(f"    P0 XiàngDetector active:     {p2s['xiang_detector_active']}")
    print(f"    P0 bias_memory_entries:      {p2s['bias_memory_entries']}")
    print(f"    P0 CumulativeSelector active:{p2s['cumulative_selector_active']}")
    print(f"    P1 SixThreshold active:      {p2s['six_threshold_detector_active']}")
    print(f"    P1 Convergence active:       {p2s['pre_subjectivity_convergence_active']}")
    print(f"    P1 converged:                {p2s['pre_subjectivity_converged']}")
    print(f"    P1 convergence_step:         {p2s['convergence_step']}")
    print(f"    Layers with results:         {p2s['layers_with_results']}")

    # Per-layer summary
    for lr in results['layer_results']:
        layer_id = lr['layer']
        print(f"\n  Layer {layer_id}: N={lr['N']}, w={lr['w']}, "
              f"sealed={lr['sealed']}, steps={lr['steps']}")
        if 'phase2_xiang_summary' in lr:
            xs = lr['phase2_xiang_summary']
            print(f"    Xiàng: first_formed={xs['first_formed_step']}, "
                  f"max_density={xs['max_density']:.3f}, "
                  f"max_trace={xs['max_trace']:.3f}, "
                  f"checks={xs['n_checks']}, formed={xs['n_formed']}")

    # SixThreshold detailed analysis
    if six_thresh._history:
        print(f"\n  SixThresholdDetector analysis ({len(six_thresh._history)} evaluations):")
        history_summary = six_thresh.get_history_summary(last_n=len(six_thresh._history))
        print(f"    avg_n_met: {history_summary.get('avg_n_met', 0):.2f}/6")
        print(f"    all_met_count: {history_summary.get('all_met_count', 0)}")
        print(f"    latest_bottleneck: {history_summary.get('latest_bottleneck', 'N/A')}")

        # Per-threshold pass rate
        threshold_pass_counts = {tid: 0 for tid in ['3.1', '3.2', '3.3', '3.4', '3.5', '3.6']}
        for r in six_thresh._history:
            for s in r.threshold_statuses:
                if s.is_met:
                    threshold_pass_counts[s.threshold_id] += 1
        total = len(six_thresh._history)
        print(f"\n    Per-threshold pass rates ({total} evaluations):")
        for tid, count in threshold_pass_counts.items():
            rate = count / total if total > 0 else 0
            n_bars = int(rate * 20)
            bar = '#' * n_bars + '-' * (20 - n_bars)
            print(f"      {tid}: {bar} {rate:.1%} ({count}/{total})")

        # Show last 5 evaluations
        print(f"\n    Last 5 evaluations:")
        for r in six_thresh._history[-5:]:
            print(f"      step={r.timestamp}: {r.n_met}/6 "
                  f"{'PASS' if r.all_met else 'FAIL bottleneck=' + str(r.bottleneck)}")

    # Convergence detailed analysis
    if convergence._convergence_history:
        print(f"\n  PreSubjectivityConvergence analysis ({len(convergence._convergence_history)} evaluations):")
        conv_summary = convergence.get_history_summary(last_n=len(convergence._convergence_history))
        print(f"    n_converged: {conv_summary.get('n_converged', 0)}")
        print(f"    first_convergence_step: {conv_summary.get('first_convergence_step', 'N/A')}")
        print(f"    avg_stability: {conv_summary.get('avg_stability', 0):.3f}")
        print(f"    avg_coupled_pairs: {conv_summary.get('avg_coupled_pairs', 0):.1f}")

        # Condition pass rates
        cond_counts = {
            'thresholds': 0, 'coupling': 0, 'stability': 0, 'firewall': 0,
        }
        for r in convergence._convergence_history:
            if r.six_thresholds_met:
                cond_counts['thresholds'] += 1
            if r.coupling_strength_met:
                cond_counts['coupling'] += 1
            if r.stability_met:
                cond_counts['stability'] += 1
            if r.semantic_firewall_passed:
                cond_counts['firewall'] += 1
        total = len(convergence._convergence_history)
        print(f"\n    Convergence condition pass rates ({total} evaluations):")
        for cond, count in cond_counts.items():
            rate = count / total if total > 0 else 0
            n_bars = int(rate * 20)
            bar = '#' * n_bars + '-' * (20 - n_bars)
            print(f"      {cond:12s}: {bar} {rate:.1%} ({count}/{total})")

        # Show last 3 evaluations
        print(f"\n    Last 3 evaluations:")
        for r in convergence._convergence_history[-3:]:
            print(f"      step={r.timestamp}: "
                  f"{'CONVERGED' if r.converged else 'NOT converged'} "
                  f"(thresholds={r.six_thresholds_met}, "
                  f"coupling={r.coupling_strength_met}, "
                  f"stability={r.stability_met})")

    print(f"\n  Wall time: {elapsed:.1f}s")

    # --- Acceptance checks ---
    print("\n" + "-" * 70)
    print("ACCEPTANCE CHECKS")
    print("-" * 70)

    checks = []

    # 1. All components active
    all_active = (p2s['xiang_detector_active'] and
                  p2s['cumulative_selector_active'] and
                  p2s['six_threshold_detector_active'] and
                  p2s['pre_subjectivity_convergence_active'])
    checks.append(("All Phase 2 components active", all_active))

    # 2. SixThresholdDetector >= 10 evaluations
    st_count = len(six_thresh._history)
    checks.append((f"SixThresholdDetector >= 10 evals ({st_count})", st_count >= 10))

    # 3. PreSubjectivityConvergence >= 10 evaluations
    conv_count = len(convergence._convergence_history)
    checks.append((f"PreSubjectivityConvergence >= 10 evals ({conv_count})", conv_count >= 10))

    # 4. At least 2 layers completed
    n_layers = len(results['layer_results'])
    checks.append((f"At least 2 layers completed ({n_layers})", n_layers >= 2))

    # 5. Time < 120s
    time_ok = elapsed < 120
    checks.append((f"Wall time < 120s ({elapsed:.1f}s)", time_ok))

    # 6. Bottleneck analysis available
    has_bottleneck = six_thresh._history and six_thresh._history[-1].bottleneck is not None
    checks.append(("Bottleneck analysis available", has_bottleneck))

    all_pass = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")

    print("-" * 70)
    if all_pass:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
    print("-" * 70)

    return all_pass


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
