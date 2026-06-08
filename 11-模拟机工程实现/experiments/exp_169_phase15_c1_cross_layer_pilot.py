"""
exp_169_phase15_c1_cross_layer_pilot.py — Phase 15 Path C1 Pilot

Cross-layer evolver proof-of-concept.
Runs L0→L1 cross-layer evolution and analyzes whether L1
produces structurally non-random sealing patterns.

Hypothesis (H15-C1):
  Cross-layer architecture (L0 sealed structure constraining L1)
  creates conditions for L2 emergence that are impossible in single-layer topology.

Success criteria:
  - L1 seals (secondary sealing event)
  - L1 sealing pattern reflects L0 cluster structure (non-random)
  - L1 hamming weight trajectory differs significantly from L0 baseline

Runs: 4 pilot runs (2 mapping modes × 2 L1 sizes)
Date: 2026-06-08
"""

import sys, os, json, time, argparse
from datetime import datetime
from typing import Dict, List, Any

import torch
import numpy as np

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine.cross_layer_evolver import CrossLayerEvolver, L1Constraints

# =============================================================================
# Analysis helpers
# =============================================================================

def analyze_l1_structure(l1_result: Dict, l1_constraints: L1Constraints) -> Dict:
    """Analyze whether L1 sealing pattern is non-random.

    Checks:
    1. Hamming weight at seal vs. expected random (N/3)
    2. Hierarchy map correlation with L1 final state
    3. HW variance (plateau = sealing)
    """
    analysis = {}

    hw_history = l1_result.get('hw_history', [])
    final_state = l1_result.get('final_state', None)

    if not hw_history:
        analysis['status'] = 'no_hw_history'
        return analysis

    analysis['hw_final'] = hw_history[-1] if hw_history else 0
    analysis['hw_mean'] = float(np.mean(hw_history))
    analysis['hw_std'] = float(np.std(hw_history))
    analysis['hw_variance'] = float(np.var(hw_history))

    # Sealing detection: HW plateau
    window = 20
    plateau_step = -1
    for i in range(window, len(hw_history)):
        w = hw_history[i-window:i]
        if max(w) - min(w) == 0:
            plateau_step = i
            break
    analysis['plateau_step'] = plateau_step
    analysis['sealed'] = plateau_step >= 0

    # Correlation: do hierarchy-mapped bits have different flip rates?
    hierarchy_map = l1_constraints.hierarchy_map
    if final_state is not None:
        n1 = len(hierarchy_map)
        h_idx = [i for i in range(n1) if hierarchy_map[i] >= 0]
        l_idx = [i for i in range(n1) if hierarchy_map[i] == -1]

        if h_idx and l_idx:
            h_state = final_state[h_idx].cpu().numpy() if hasattr(final_state, 'cpu') else np.array([final_state[i] for i in h_idx])
            l_state = final_state[l_idx].cpu().numpy() if hasattr(final_state, 'cpu') else np.array([final_state[i] for i in l_idx])
            analysis['hierarchy_hw'] = float(h_state.mean()) if len(h_state) > 0 else 0.0
            analysis['lateral_hw'] = float(l_state.mean()) if len(l_state) > 0 else 0.0
            analysis['hw_diff_h_vs_l'] = analysis['hierarchy_hw'] - analysis['lateral_hw']
        else:
            analysis['hierarchy_hw'] = 0.0
            analysis['lateral_hw'] = 0.0
            analysis['hw_diff_h_vs_l'] = 0.0

    return analysis


def run_pilot_configs() -> List[Dict]:
    """Run pilot configurations for exp_169.

    Configs:
      A. cluster mapping (hierarchy_map from L0 clusters)
      B. random mapping (baseline: L1 has no L0 structural info)
    """
    configs = [
        {
            'name': 'pilot_cluster_map',
            'N0': 48,
            'N1': 48,
            'L0_steps': 5000,
            'L1_steps': 5000,
            'mapping': 'cluster',   # Use L0 cluster structure
            'enable_l0_feedback': False,
        },
        {
            'name': 'pilot_random_map',
            'N0': 48,
            'N1': 48,
            'L0_steps': 5000,
            'L1_steps': 5000,
            'mapping': 'random',     # Random L1 (baseline)
            'enable_l0_feedback': False,
        },
        {
            'name': 'pilot_cluster_map_N1_24',
            'N0': 48,
            'N1': 24,
            'L0_steps': 5000,
            'L1_steps': 5000,
            'mapping': 'cluster',
            'enable_l0_feedback': False,
        },
        {
            'name': 'pilot_cluster_map_with_feedback',
            'N0': 48,
            'N1': 48,
            'L0_steps': 5000,
            'L1_steps': 5000,
            'mapping': 'cluster',
            'enable_l0_feedback': True,   # L1 seal → L0 perturbation
        },
    ]
    return configs


def run_single_experiment(cfg: Dict, device: str = 'cpu') -> Dict:
    """Run a single cross-layer experiment."""
    t0 = time.time()

    ev = CrossLayerEvolver(
        N0=cfg['N0'],
        N1=cfg['N1'],
        L0_steps=cfg['L0_steps'],
        L1_steps=cfg['L1_steps'],
        sample_interval=100,
        device=device,
        enable_l0_feedback=cfg.get('enable_l0_feedback', False),
    )

    results = ev.run()
    elapsed = time.time() - t0

    # Analyze L1 structure
    if results.get('l1_result') is not None and ev.l1_constraints is not None:
        l1_analysis = analyze_l1_structure(
            results['l1_result'],
            ev.l1_constraints,
        )
        results['l1_analysis'] = l1_analysis

    results['elapsed_sec'] = round(elapsed, 2)
    results['config'] = cfg

    return results


def main():
    parser = argparse.ArgumentParser(description='Phase 15 C1: Cross-Layer Evolver Pilot')
    parser.add_argument('--device', type=str, default='cpu', help='cpu or cuda')
    parser.add_argument('--pilot', action='store_true', help='Run pilot configs')
    parser.add_argument('--single', type=str, default=None, help='Run single config by name')
    args = parser.parse_args()

    device = args.device
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if args.single:
        configs = [c for c in run_pilot_configs() if c['name'] == args.single]
        if not configs:
            print(f"Unknown config: {args.single}")
            return
    elif args.pilot:
        configs = run_pilot_configs()
    else:
        configs = run_pilot_configs()

    all_results = []
    for cfg in configs:
        print(f"\n{'='*60}")
        print(f"Running: {cfg['name']}")
        print(f"{'='*60}")
        t0 = time.time()
        try:
            r = run_single_experiment(cfg, device=device)
            all_results.append(r)
            print(f"  L0 sealed: {r.get('l0_sealed')} (step {r.get('l0_seal_step')})")
            print(f"  L1 sealed: {r.get('l1_sealed')} (step {r.get('l1_seal_step')})")
            if 'l1_analysis' in r:
                a = r['l1_analysis']
                print(f"  L1 HW final: {a.get('hw_final', 'N/A')}")
                print(f"  L1 plateau: {a.get('plateau_step', 'N/A')}")
                print(f"  L1 H vs L HW diff: {a.get('hw_diff_h_vs_l', 'N/A'):.4f}")
            print(f"  Elapsed: {r.get('elapsed_sec', 0):.1f}s")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()
            all_results.append({'config': cfg, 'error': str(e)})
        print(f"  Time: {time.time()-t0:.1f}s")

    # Save results
    results_dir = os.path.join(PROJECT_ROOT, 'experiments', 'results')
    os.makedirs(results_dir, exist_ok=True)
    results_file = os.path.join(results_dir, f'exp169_phase15_c1_pilot_{timestamp}.json')

    # Convert to JSON-serializable
    save_data = []
    for r in all_results:
        d = {}
        for k, v in r.items():
            if k in ('l0_result', 'l1_result', 'l0_evolver', 'l1_evolver'):
                continue  # skip non-serializable
            try:
                json.dumps({k: v}, default=str)
                d[k] = v
            except (TypeError, ValueError):
                d[k] = str(v)
        save_data.append(d)

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, default=str, ensure_ascii=False)

    print(f"\nResults saved to: {results_file}")

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in all_results:
        name = r.get('config', {}).get('name', 'unknown')
        l0_sealed = r.get('l0_sealed', False)
        l1_sealed = r.get('l1_sealed', False)
        l0_step = r.get('l0_seal_step', -1)
        l1_step = r.get('l1_seal_step', -1)
        print(f"  {name:40s} | L0 seal: {str(l0_sealed):5s} (step {l0_step:5d}) | L1 seal: {str(l1_sealed):5s} (step {l1_step:5d})")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
