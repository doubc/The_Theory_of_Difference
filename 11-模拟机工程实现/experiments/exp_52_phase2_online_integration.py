"""
experiments/exp_52_phase2_online_integration.py
  Phase 2 Online Integration Test

验证 XiàngDetector + PersistentBiasMemory + CumulativeSelector
在演化循环中的实时集成。

与 exp_50/exp_51 的区别：
- exp_50/exp_51: 演化结束后，用保存的数据进行离线检测
- exp_52: 演化过程中，每 sample_interval 步实时调用 Phase 2 组件

这是 Phase 2 从"离线分析"到"在线集成"的关键一步。

Generation chain (online):
  evolution step → XiàngDetector (per sample_interval)
                  → PersistentBiasMemory (per sample_interval)
                  → CumulativeSelector (per sample_interval)
  → post-hoc summary: first_formed_step, max_density, max_trace, etc.
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


def main():
    print("=" * 70)
    print("exp_52: Phase 2 Online Integration Test")
    print("  XiàngDetector + PersistentBiasMemory + CumulativeSelector")
    print("  integrated into HierarchicalEvolver step loop")
    print("=" * 70)

    # Parameters
    N0 = 32
    steps_per_layer = 2000
    sample_interval = 200
    max_layers = 3

    # Init Phase 2 components
    xiang = XiàngDetector(rho_threshold=0.3, tau_threshold=0.5)
    bias_mem = PersistentBiasMemory(max_history_depth=50)
    selector = CumulativeSelector(window_size=10, trend_threshold=0.5)

    print(f"\n[Config]")
    print(f"  N0={N0}, steps/layer={steps_per_layer}, "
          f"sample_interval={sample_interval}, max_layers={max_layers}")
    print(f"  XiàngDetector: rho={xiang.rho_threshold}, tau={xiang.tau_threshold}")
    print(f"  PersistentBiasMemory: max_history={bias_mem.max_history_depth}")
    print(f"  CumulativeSelector: window={selector.window_size}, "
          f"trend_threshold={selector.trend_threshold}")

    # Create evolver WITH Phase 2 components
    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps_per_layer,
        sample_interval=sample_interval,
        max_layers=max_layers,
        device="cpu",
        binding_threshold=0.1,
        min_group_size=2,
        auto_encapsulate=True,
        # Phase 2 集成
        xiang_detector=xiang,
        persistent_bias_memory=bias_mem,
        cumulative_selector=selector,
        phase2_verbose=True,
    )

    # Run evolution
    print(f"\n[Evolution with online Phase 2 detection]")
    t0 = time.time()
    evo = evolver.run(verbose=True)
    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s")

    # ── Phase 2 Online Results ──
    print("\n" + "=" * 70)
    print("Phase 2 Online Detection Results")
    print("=" * 70)

    p2_summary = evo.get('phase2_summary', {})
    print(f"\n[Phase 2 Summary]")
    print(f"  XiàngDetector active: {p2_summary.get('xiang_detector_active', False)}")
    print(f"  Bias memory entries:  {p2_summary.get('bias_memory_entries', 0)}")
    print(f"  CumulativeSelector active: "
          f"{p2_summary.get('cumulative_selector_active', False)}")
    print(f"  Layers with results: {p2_summary.get('layers_with_results', [])}")

    for lr in evo['layer_results']:
        li = lr['layer']
        print(f"\n--- L{li} (N={lr['N']}, cycles={lr['cycles']}, "
              f"clusters={len(lr['clusters'])}) ---")

        # Xiàng summary
        xiang_summary = lr.get('phase2_xiang_summary')
        if xiang_summary:
            print(f"  XiàngDetector ({xiang_summary['n_checks']} checks):")
            print(f"    First formed at step: {xiang_summary['first_formed_step']}")
            print(f"    Max density:          {xiang_summary['max_density']:.4f}")
            print(f"    Max trace:            {xiang_summary['max_trace']:.4f}")
            print(f"    Max continuity:       {xiang_summary['max_continuity']}")
            print(f"    Formed count:         {xiang_summary['n_formed']}"
                  f"/{xiang_summary['n_checks']}")
        else:
            print(f"  XiàngDetector: no results")

        # Step-by-step detail (last 5)
        step_results = lr.get('phase2_step_results', [])
        if step_results:
            print(f"  Step detail (last 5 of {len(step_results)}):")
            for sr in step_results[-5:]:
                step = sr['step']
                xiang_part = ""
                if 'xiang' in sr:
                    x = sr['xiang']
                    tag = "Y" if x['formed'] else "N"
                    xiang_part = (f"  Xiàng[{tag}] d={x['density']:.3f} "
                                  f"t={x['trace']:.3f} c={x['continuity']}")
                bias_part = ""
                if 'bias_memory' in sr:
                    b = sr['bias_memory']
                    bias_part = f"  Bias[entries={b['entries']}, s={b['strength']:.3f}]"
                print(f"    step={step}{xiang_part}{bias_part}")

    # ── Acceptance ──
    print("\n" + "=" * 70)
    print("Acceptance")
    print("=" * 70)

    checks = {
        'Multi-layer (>=2)': evo['n_layers'] >= 2,
        'Phase 2 integrated': p2_summary.get('xiang_detector_active', False),
        'Xiàng online checks': any(
            lr.get('phase2_xiang_summary', {}).get('n_checks', 0) > 0
            for lr in evo['layer_results']
        ),
        'Bias memory recorded': p2_summary.get('bias_memory_entries', 0) > 0,
        'Cumulative selector active': p2_summary.get('cumulative_selector_active', False),
        'Xiàng formed (any layer)': any(
            lr.get('phase2_xiang_summary', {}).get('n_formed', 0) > 0
            for lr in evo['layer_results']
        ),
    }

    for name, ok in checks.items():
        tag = "[PASS]" if ok else "[WARN]"
        print(f"  {tag} {name}")

    all_ok = all(checks.values())
    result_str = ('[PASS] Phase 2 online integration test passed'
                   if all_ok else '[WARN] Some checks not passed')
    print(f"\n{result_str}")
    print(f"Runtime: {elapsed:.1f}s")

    # ── Comparison with exp_51 (offline) ──
    print("\n" + "=" * 70)
    print("Comparison: exp_51 (offline) vs exp_52 (online)")
    print("=" * 70)
    print("  exp_51: Post-hoc analysis using saved snapshots")
    print("          XiàngDetector run AFTER evolution completes")
    print("  exp_52: Online detection during evolution")
    print("          XiàngDetector called EVERY sample_interval steps")
    print()
    print("  Both should produce similar Xiàng detection results.")
    print("  exp_52 additionally enables:")
    print("    - PersistentBiasMemory accumulation during evolution")
    print("    - CumulativeSelector tracking during evolution")
    print("    - Future: real-time feedback from Phase 2 to evolution")

    return evo


if __name__ == "__main__":
    main()
