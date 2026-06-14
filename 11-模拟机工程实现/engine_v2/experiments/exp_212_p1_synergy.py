# -*- coding: utf-8 -*-
"""exp_212 Phase 23 P1 — 能量-自指协同增强 (2×2 Factorial Design).

Design:
    4 groups in 2×2 factorial:
        G1: No Energy + No Self-ref (control)
        G2: Energy + No Self-ref (energy only)
        G3: No Energy + Self-ref (self-ref only)
        G4: Energy + Self-ref (both — synergy prediction)

Metrics:
    - n_layers: emergence depth (L0 counts as 1)
    - L1 flux:叙事活跃度
    - L2+ emergence rate: whether L2+ layers appear
    - mean_flux: average flux across all layers

H23-1: Synergy ratio > 1.2
    synergy_ratio = G4.metric / max(G2.metric, G3.metric)
    If G4 effect > 1.2 × max(G2, G3) individually, synergy confirmed.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from diffsim.world_v2 import RecursiveWorld, Params
from diffsim.energy_v2 import EnergyConfig
import json
import numpy as np
from datetime import datetime

# Reproducibility
SEEDS = [42, 123, 256, 789, 1024]
N0 = 48
ENERGY_BUDGET = 200
MAX_LAYERS = 6


def run_group(label: str, has_energy: bool, has_self_ref: bool, seeds: list) -> dict:
    """Run one experimental group across multiple seeds."""
    results = []
    for seed in seeds:
        cfg = {
            'N0': N0,
            'self_encapsulate': has_self_ref,
            'seed': seed,
            'energy_cfg': EnergyConfig(initial_budget=ENERGY_BUDGET) if has_energy else None,
        }
        world = RecursiveWorld(**cfg)
        outcome = world.run(max_layers=MAX_LAYERS, verbose=False)

        # Extract metrics
        layers_info = outcome['layers']
        n_layers = outcome['n_layers']
        l1_flux = layers_info[1]['flux'] if len(layers_info) > 1 else 0.0
        l2_exists = any(l['layer'] >= 2 for l in layers_info)
        mean_flux = np.mean([l['flux'] for l in layers_info]) if layers_info else 0.0
        depth = outcome['depth']  # n_layers - 1

        results.append({
            'seed': seed,
            'n_layers': n_layers,
            'depth': depth,
            'l1_flux': l1_flux,
            'l2_exists': l2_exists,
            'mean_flux': mean_flux,
        })

    # Aggregate
    agg = {
        'label': label,
        'has_energy': has_energy,
        'has_self_ref': has_self_ref,
        'n_seeds': len(seeds),
        'avg_n_layers': np.mean([r['n_layers'] for r in results]),
        'avg_depth': np.mean([r['depth'] for r in results]),
        'avg_l1_flux': np.mean([r['l1_flux'] for r in results]),
        'l2_emergence_rate': np.mean([r['l2_exists'] for r in results]),
        'avg_mean_flux': np.mean([r['mean_flux'] for r in results]),
        'std_l1_flux': np.std([r['l1_flux'] for r in results]),
        'std_n_layers': np.std([r['n_layers'] for r in results]),
        'per_seed': results,
    }
    return agg


def compute_synergy(g1, g2, g3, g4) -> dict:
    """Compute H23-1 synergy metrics."""
    metrics = {}

    # For each metric, compute synergy ratio
    for metric_key in ['avg_l1_flux', 'avg_mean_flux', 'avg_depth', 'l2_emergence_rate']:
        v1, v2, v3, v4 = g1[metric_key], g2[metric_key], g3[metric_key], g4[metric_key]
        
        # Individual contributions (above control)
        delta_energy = v2 - v1
        delta_self_ref = v3 - v1
        linear_sum = v1 + delta_energy + delta_self_ref  # expected if additive
        
        # Actual combined effect
        actual = v4
        
        # Synergy ratio: actual vs max of individual effects (above control)
        max_individual = max(delta_energy, delta_self_ref)
        control = v1
        
        if abs(max_individual) > 1e-6 and abs(control) > 1e-6:
            # Ratio of combined improvement to best single improvement
            combined_improvement = actual - control
            ratio = combined_improvement / max_individual
        else:
            ratio = 0.0

        metrics[metric_key] = {
            'control_g1': v1,
            'energy_only_g2': v2,
            'self_ref_only_g3': v3,
            'combined_g4': v4,
            'delta_energy': delta_energy,
            'delta_self_ref': delta_self_ref,
            'linear_expected': linear_sum,
            'actual_g4': actual,
            'synergy_ratio': ratio,
        }

    return metrics


def main():
    print("=" * 60)
    print("exp_212 Phase 23 P1: Energy × Self-reference Synergy")
    print(f"  N0={N0}, energy_budget={ENERGY_BUDGET}, seeds={SEEDS}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    groups = []
    
    # G1: Control (no energy, no self-ref)
    print("\n[G1] Control: No Energy + No Self-ref")
    g1 = run_group("G1_control", False, False, SEEDS)
    groups.append(g1)
    print(f"  avg_depth={g1['avg_depth']:.2f}, avg_l1_flux={g1['avg_l1_flux']:.4f}, "
          f"l2_rate={g1['l2_emergence_rate']:.2f}")

    # G2: Energy only
    print("\n[G2] Energy Only")
    g2 = run_group("G2_energy", True, False, SEEDS)
    groups.append(g2)
    print(f"  avg_depth={g2['avg_depth']:.2f}, avg_l1_flux={g2['avg_l1_flux']:.4f}, "
          f"l2_rate={g2['l2_emergence_rate']:.2f}")

    # G3: Self-ref only
    print("\n[G3] Self-ref Only")
    g3 = run_group("G3_selfref", False, True, SEEDS)
    groups.append(g3)
    print(f"  avg_depth={g3['avg_depth']:.2f}, avg_l1_flux={g3['avg_l1_flux']:.4f}, "
          f"l2_rate={g3['l2_emergence_rate']:.2f}")

    # G4: Both (synergy prediction)
    print("\n[G4] Energy + Self-ref (Synergy)")
    g4 = run_group("G4_both", True, True, SEEDS)
    groups.append(g4)
    print(f"  avg_depth={g4['avg_depth']:.2f}, avg_l1_flux={g4['avg_l1_flux']:.4f}, "
          f"l2_rate={g4['l2_emergence_rate']:.2f}")

    # Compute synergy
    print("\n" + "=" * 60)
    print("H23-1 Synergy Analysis")
    print("=" * 60)
    synergy = compute_synergy(g1, g2, g3, g4)

    hypotheses = {}
    for metric_key, m in synergy.items():
        ratio = m['synergy_ratio']
        pass_str = "[PASS]" if ratio > 1.2 else "[FAIL]"
        print(f"\n  {metric_key}:")
        print(f"    G1(ctrl)={m['control_g1']:.4f}, G2(E)={m['energy_only_g2']:.4f}, "
              f"G3(SR)={m['self_ref_only_g3']:.4f}, G4(E+SR)={m['actual_g4']:.4f}")
        print(f"    Δ(E)={m['delta_energy']:.4f}, Δ(SR)={m['delta_self_ref']:.4f}")
        print(f"    Synergy ratio = {ratio:.4f}  {pass_str}")
        hypotheses[metric_key] = {
            'ratio': ratio,
            'pass': ratio > 1.2,
        }

    # Summary
    n_pass = sum(1 for h in hypotheses.values() if h['pass'])
    n_total = len(hypotheses)
    print(f"\n{'=' * 60}")
    print(f"H23-1 Result: {n_pass}/{n_total} metrics show synergy ratio > 1.2")
    print(f"Overall: {'[PASS]' if n_pass >= 3 else '[FAIL]'}")
    print("=" * 60)

    # Save results
    output = {
        'experiment': 'exp_212_p1_synergy',
        'hypothesis': 'H23-1: Energy-SelfRef synergy > 1.2×',
        'timestamp': datetime.now().isoformat(),
        'config': {'N0': N0, 'energy_budget': ENERGY_BUDGET, 'seeds': SEEDS, 'max_layers': MAX_LAYERS},
        'groups': {g['label']: {k: v for k, v in g.items() if k != 'per_seed'} for g in groups},
        'per_seed': {g['label']: g['per_seed'] for g in groups},
        'synergy': synergy,
        'hypothesis_results': hypotheses,
        'summary': {
            'n_pass': n_pass,
            'n_total': n_total,
            'overall_pass': n_pass >= 3,
        },
    }

    results_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, 'exp_212_p1_synergy.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved to: {os.path.abspath(out_path)}")

    return output


if __name__ == '__main__':
    main()
