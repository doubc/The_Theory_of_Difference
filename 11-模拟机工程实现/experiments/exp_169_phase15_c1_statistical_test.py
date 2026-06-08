"""
exp_169_phase15_c1_statistical_test.py — Phase 15 Path C1 Statistical Test

Runs N=20 trials per config to statistically test H15-C1:
  "Cross-layer architecture (L0 sealed structure constraining L1)
   creates conditions for L2 emergence that are impossible in single-layer topology."

Configs to test:
  1. pilot_cluster_map (L0 clusters → L1 constraints)
  2. pilot_random_map (baseline: random L1)
  3. pilot_cluster_map_with_feedback (L0→L1→L0 feedback)

Metrics:
  - L1 seal rate (%)
  - L1 sealing step distribution
  - L1 HW trajectory similarity to L0
  - Structure correlation (H vs L bits in L1)

Date: 2026-06-08
"""

import sys, os, json, time, argparse
from datetime import datetime
from typing import Dict, List, Any
from collections import Counter

import torch
import numpy as np

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine.cross_layer_evolver import CrossLayerEvolver, L1Constraints


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

    # Extract key metrics
    r = {
        'config_name': cfg['name'],
        'l0_sealed': results.get('l0_sealed', False),
        'l0_seal_step': results.get('l0_seal_step', -1),
        'l1_sealed': results.get('l1_sealed', False),
        'l1_seal_step': results.get('l1_seal_step', -1),
        'n_clusters': results.get('n_clusters', 0),
        'l0_hw_at_seal': results.get('l0_hw_at_seal', 0),
        'elapsed_sec': round(elapsed, 2),
    }

    # L1 HW analysis
    l1_hw = results.get('l1_hw_history', [])
    if l1_hw:
        r['l1_hw_final'] = l1_hw[-1] if l1_hw else 0
        r['l1_hw_mean'] = float(np.mean(l1_hw))
        r['l1_hw_std'] = float(np.std(l1_hw))

    # L0 HW analysis (for comparison)
    l0_hw = results.get('l0_hw_history', [])
    if l0_hw:
        r['l0_hw_final'] = l0_hw[-1] if l0_hw else 0
        r['l0_hw_mean'] = float(np.mean(l0_hw))

    return r


def run_statistical_test(configs: List[Dict], n_trials: int = 20, device: str = 'cpu'):
    """Run N trials per config and collect statistics."""
    all_results = []

    for cfg in configs:
        print(f"\n{'='*70}")
        print(f"Config: {cfg['name']} (N={n_trials} trials)")
        print(f"{'='*70}")

        config_results = []
        for trial in range(n_trials):
            print(f"  Trial {trial+1}/{n_trials}...", end=' ', flush=True)
            try:
                r = run_single_experiment(cfg, device=device)
                config_results.append(r)
                l0_seal = r.get('l0_sealed', False)
                l1_seal = r.get('l1_sealed', False)
                l1_step = r.get('l1_seal_step', -1)
                print(f"L0 seal: {l0_seal}, L1 seal: {l1_seal} (step {l1_step})")
            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()
                config_results.append({
                    'config_name': cfg['name'],
                    'error': str(e),
                    'trial': trial,
                })

        all_results.extend(config_results)

        # Print interim summary
        l1_seal_count = sum(1 for r in config_results if r.get('l1_sealed', False))
        print(f"  → L1 seal rate: {l1_seal_count}/{n_trials} = {l1_seal_count/n_trials*100:.1f}%")

    return all_results


def analyze_results(all_results: List[Dict]):
    """Analyze and print statistical summary."""
    # Group by config
    by_config = {}
    for r in all_results:
        name = r.get('config_name', 'unknown')
        if name not in by_config:
            by_config[name] = []
        by_config[name].append(r)

    print(f"\n{'='*70}")
    print("STATISTICAL SUMMARY")
    print(f"{'='*70}")

    for name, results in by_config.items():
        n = len(results)
        l1_sealed = [r for r in results if r.get('l1_sealed', False)]
        l1_seal_rate = len(l1_sealed) / n * 100 if n > 0 else 0

        print(f"\n{name} (N={n}):")
        print(f"  L1 seal rate: {len(l1_sealed)}/{n} = {l1_seal_rate:.1f}%")

        if l1_sealed:
            steps = [r.get('l1_seal_step', -1) for r in l1_sealed]
            print(f"  L1 seal step: mean={np.mean(steps):.1f}, std={np.std(steps):.1f}, median={np.median(steps):.1f}")

            hw_final = [r.get('l1_hw_final', 0) for r in l1_sealed]
            print(f"  L1 HW final: mean={np.mean(hw_final):.1f}, std={np.std(hw_final):.1f}")

        # L0 seal rate
        l0_sealed = [r for r in results if r.get('l0_sealed', False)]
        l0_seal_rate = len(l0_sealed) / n * 100 if n > 0 else 0
        print(f"  L0 seal rate: {len(l0_sealed)}/{n} = {l0_seal_rate:.1f}%")


def main():
    parser = argparse.ArgumentParser(description='Phase 15 C1: Statistical Test (N=20)')
    parser.add_argument('--device', type=str, default='cpu', help='cpu or cuda')
    parser.add_argument('--n-trials', type=int, default=20, help='Number of trials per config')
    parser.add_argument('--configs', type=str, nargs='+', default=None, help='Config names to run (default: all)')
    args = parser.parse_args()

    device = args.device
    n_trials = args.n_trials
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Define configs
    all_configs = [
        {
            'name': 'pilot_cluster_map',
            'N0': 48,
            'N1': 48,
            'L0_steps': 5000,
            'L1_steps': 5000,
            'mapping': 'cluster',
            'enable_l0_feedback': False,
        },
        {
            'name': 'pilot_random_map',
            'N0': 48,
            'N1': 48,
            'L0_steps': 5000,
            'L1_steps': 5000,
            'mapping': 'random',
            'enable_l0_feedback': False,
        },
        {
            'name': 'pilot_cluster_map_with_feedback',
            'N0': 48,
            'N1': 48,
            'L0_steps': 5000,
            'L1_steps': 5000,
            'mapping': 'cluster',
            'enable_l0_feedback': True,
        },
    ]

    # Filter configs if specified
    if args.configs:
        configs = [c for c in all_configs if c['name'] in args.configs]
        if not configs:
            print(f"Unknown config(s): {args.configs}")
            return
    else:
        configs = all_configs

    print(f"\nPhase 15 Path C1 Statistical Test")
    print(f"N trials per config: {n_trials}")
    print(f"Configs: {[c['name'] for c in configs]}")
    print(f"Device: {device}")
    print(f"{'='*70}\n")

    t0 = time.time()
    all_results = run_statistical_test(configs, n_trials=n_trials, device=device)
    total_elapsed = time.time() - t0

    # Save results
    results_dir = os.path.join(PROJECT_ROOT, 'experiments', 'results')
    os.makedirs(results_dir, exist_ok=True)
    results_file = os.path.join(results_dir, f'exp169_phase15_c1_statistical_{timestamp}.json')

    # Convert to JSON-serializable
    save_data = []
    for r in all_results:
        d = {}
        for k, v in r.items():
            try:
                json.dumps({k: v}, default=str)
                d[k] = v
            except (TypeError, ValueError):
                d[k] = str(v)
        save_data.append(d)

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, default=str, ensure_ascii=False)

    print(f"\nResults saved to: {results_file}")
    print(f"Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")

    # Print analysis
    analyze_results(all_results)


if __name__ == '__main__':
    main()
