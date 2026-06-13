"""
exp_205_phase22_p0_open_system.py — Phase 22 P0: Open System Energy Flow

Tests the integration of EnvironmentEnergyField + EntropyExhaust into the World.
Compares closed vs open system dynamics with meaningful dynamics.

Hypotheses:
- H22-P0a: Open system maintains higher final energy than closed
- H22-P0b: Open system has lower final entropy than closed (entropy exhaust)
- H22-P0c: Open system energy min is higher than closed (energy floor effect)
- H22-P0d: Higher constraint strength → more energy injected
- H22-P0e: Higher exhaust rate → lower final entropy
"""

import sys
import os
import json
import numpy as np
from datetime import datetime

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from diffsim.energy import EnergyConfig
from diffsim.entropy import EntropyConfig
from diffsim.environment_energy import EnvironmentConfig as OpenSystemConfig
from diffsim.world import WorldConfig, World


def run_closed_system(seed: int, n_steps: int = 1000) -> dict:
    """Run baseline closed system (no open system coupling)."""
    np.random.seed(seed)
    
    energy_config = EnergyConfig(
        initial_energy=100.0,
        decay_rate=0.05,
        injection_rate=2.0,    # Phase 21 baseline injection
        injection_max=150.0,
        m9_seal_cost=10.0
    )
    
    entropy_config = EntropyConfig(
        temperature=1.0,
        production_threshold=0.01,
        use_bit_entropy=True,
        group_by_organization=True
    )
    
    world_config = WorldConfig(
        n_bits=48,
        binding_threshold=20,  # Allow dynamics before sealing
        seal_threshold=0.4,
        energy_config=energy_config,
        entropy_config=entropy_config,
        open_system_config=None,
        max_steps=n_steps
    )
    
    world = World(world_config)
    summary = world.run()
    
    # Extract traces from snapshots
    energy_trace = []
    entropy_trace = []
    for s in world.state.snapshots:
        e = s.get('energy', {})
        ent = s.get('entropy', {})
        energy_trace.append(e.get('energy', float(e)) if isinstance(e, dict) else float(e))
        entropy_trace.append(ent.get('entropy', float(ent)) if isinstance(ent, dict) else float(ent))
    
    energy_summary = summary.get('energy', {}) if isinstance(summary.get('energy'), dict) else {}
    entropy_summary = summary.get('entropy', {}) if isinstance(summary.get('entropy'), dict) else {}
    
    return {
        'seed': seed,
        'system_type': 'closed',
        'is_sealed': summary.get('is_sealed', False),
        'seal_step': summary.get('seal_step'),
        'total_steps': summary.get('total_steps', 0),
        'final_energy': energy_summary.get('current_energy', 0.0),
        'final_entropy': entropy_summary.get('current_entropy', 0.0),
        'min_energy': energy_summary.get('min_energy', 0.0),
        'max_entropy': entropy_summary.get('current_entropy', 0.0),
        'energy_trace': energy_trace,
        'entropy_trace': entropy_trace,
    }


def run_open_system(seed: int, n_steps: int = 1000,
                    base_rate: float = 3.0, constraint_strength: float = 0.5,
                    exhaust_rate: float = 0.1) -> dict:
    """Run open system with environment energy field."""
    np.random.seed(seed)
    
    energy_config = EnergyConfig(
        initial_energy=100.0,
        decay_rate=0.05,
        injection_rate=2.0,    # Phase 21 baseline injection
        injection_max=150.0,
        m9_seal_cost=10.0
    )
    
    entropy_config = EntropyConfig(
        temperature=1.0,
        production_threshold=0.01,
        use_bit_entropy=True,
        group_by_organization=True
    )
    
    open_config = OpenSystemConfig(
        base_rate=base_rate,
        constraint_strength=constraint_strength,
        exhaust_rate=exhaust_rate,
        max_energy=200.0,
        constraint_energy_factor=1.5
    )
    
    world_config = WorldConfig(
        n_bits=48,
        binding_threshold=20,
        seal_threshold=0.4,
        energy_config=energy_config,
        entropy_config=entropy_config,
        open_system_config=open_config,
        max_steps=n_steps
    )
    
    world = World(world_config)
    summary = world.run()
    
    # Extract traces
    energy_trace = []
    entropy_trace = []
    injected_trace = []
    exhausted_trace = []
    for s in world.state.snapshots:
        e = s.get('energy', {})
        ent = s.get('entropy', {})
        energy_trace.append(e.get('energy', float(e)) if isinstance(e, dict) else float(e))
        entropy_trace.append(ent.get('entropy', float(ent)) if isinstance(ent, dict) else float(ent))
        os_info = s.get('open_system', {})
        if os_info:
            injected_trace.append(os_info.get('energy_injected', 0.0))
            exhausted_trace.append(os_info.get('entropy_exhausted', 0.0))
    
    energy_summary = summary.get('energy', {}) if isinstance(summary.get('energy'), dict) else {}
    entropy_summary = summary.get('entropy', {}) if isinstance(summary.get('entropy'), dict) else {}
    open_summary = summary.get('open_system', {}) if isinstance(summary.get('open_system'), dict) else {}
    
    return {
        'seed': seed,
        'system_type': 'open',
        'base_rate': base_rate,
        'constraint_strength': constraint_strength,
        'exhaust_rate': exhaust_rate,
        'is_sealed': summary.get('is_sealed', False),
        'seal_step': summary.get('seal_step'),
        'total_steps': summary.get('total_steps', 0),
        'final_energy': energy_summary.get('current_energy', 0.0),
        'final_entropy': entropy_summary.get('current_entropy', 0.0),
        'min_energy': energy_summary.get('min_energy', 0.0),
        'total_injected': open_summary.get('total_energy_injected', 0.0),
        'total_exhausted': open_summary.get('total_entropy_exhausted', 0.0),
        'energy_trace': energy_trace,
        'entropy_trace': entropy_trace,
        'injected_trace': injected_trace,
        'exhausted_trace': exhausted_trace,
    }


def verify_hypotheses(results: list) -> dict:
    """Verify all Phase 22 P0 hypotheses from results."""
    closed = [r for r in results if r['system_type'] == 'closed']
    open_default = [r for r in results if r['system_type'] == 'open' 
                    and r['base_rate'] == 3.0 and r['constraint_strength'] == 0.5
                    and r['exhaust_rate'] == 0.1]
    
    hypotheses = {}
    
    # H22-P0a: Open system maintains higher final energy
    if closed and open_default:
        closed_e = np.mean([r['final_energy'] for r in closed])
        open_e = np.mean([r['final_energy'] for r in open_default])
        h22_p0a = open_e > closed_e
        hypotheses['H22-P0a'] = {
            'pass': bool(h22_p0a),
            'detail': f'Closed E_mean={closed_e:.2f} vs Open E_mean={open_e:.2f}',
            'closed_energy': float(closed_e),
            'open_energy': float(open_e)
        }
    
    # H22-P0b: Open system has lower final entropy
    if closed and open_default:
        closed_s = np.mean([r['final_entropy'] for r in closed])
        open_s = np.mean([r['final_entropy'] for r in open_default])
        h22_p0b = open_s < closed_s
        hypotheses['H22-P0b'] = {
            'pass': bool(h22_p0b),
            'detail': f'Closed S_mean={closed_s:.4f} vs Open S_mean={open_s:.4f}',
            'closed_entropy': float(closed_s),
            'open_entropy': float(open_s)
        }
    
    # H22-P0c: Open system has higher minimum energy
    if closed and open_default:
        closed_min = np.mean([r['min_energy'] for r in closed])
        open_min = np.mean([r['min_energy'] for r in open_default])
        h22_p0c = open_min > closed_min
        hypotheses['H22-P0c'] = {
            'pass': bool(h22_p0c),
            'detail': f'Closed E_min={closed_min:.2f} vs Open E_min={open_min:.2f}',
            'closed_min_energy': float(closed_min),
            'open_min_energy': float(open_min)
        }
    
    # H22-P0d: Higher constraint → more injection
    constraint_groups = {}
    for r in results:
        if r['system_type'] == 'open':
            cs = r['constraint_strength']
            if cs not in constraint_groups:
                constraint_groups[cs] = []
            constraint_groups[cs].append(r['total_injected'])
    
    if len(constraint_groups) >= 2:
        sorted_cs = sorted(constraint_groups.keys())
        low_cs, high_cs = sorted_cs[0], sorted_cs[-1]
        low_inj = np.mean(constraint_groups[low_cs])
        high_inj = np.mean(constraint_groups[high_cs])
        h22_p0d = high_inj > low_inj
        hypotheses['H22-P0d'] = {
            'pass': bool(h22_p0d),
            'detail': f'cs={low_cs}: inj={low_inj:.1f}, cs={high_cs}: inj={high_inj:.1f}',
            'low_cs_injection': float(low_inj),
            'high_cs_injection': float(high_inj)
        }
    
    # H22-P0e: Higher exhaust → lower entropy
    exhaust_groups = {}
    for r in results:
        if r['system_type'] == 'open':
            er = r['exhaust_rate']
            if er not in exhaust_groups:
                exhaust_groups[er] = []
            exhaust_groups[er].append(r['final_entropy'])
    
    if len(exhaust_groups) >= 2:
        sorted_er = sorted(exhaust_groups.keys())
        low_er, high_er = sorted_er[0], sorted_er[-1]
        low_s = np.mean(exhaust_groups[low_er])
        high_s = np.mean(exhaust_groups[high_er])
        h22_p0e = high_s < low_s
        hypotheses['H22-P0e'] = {
            'pass': bool(h22_p0e),
            'detail': f'er={low_er}: S={low_s:.4f}, er={high_er}: S={high_s:.4f}',
            'low_er_entropy': float(low_s),
            'high_er_entropy': float(high_s)
        }
    
    n_pass = sum(1 for h in hypotheses.values() if h['pass'])
    n_total = len(hypotheses)
    
    return {
        'n_pass': n_pass,
        'n_total': n_total,
        'pass_rate': n_pass / n_total if n_total > 0 else 0.0,
        'hypotheses': hypotheses
    }


def main():
    """Run Phase 22 P0 experiment."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    n_steps = 1500
    
    results = []
    
    # === Config A: Baseline comparison (closed vs open, 8 seeds each) ===
    print("=== Config A: Baseline closed vs open comparison (8 seeds) ===")
    
    for seed in [42, 43, 44, 45, 46, 47, 48, 49]:
        r = run_closed_system(seed, n_steps)
        results.append(r)
        print(f"  Closed seed {seed}: sealed at step {r['seal_step']}, "
              f"E={r['final_energy']:.1f}, S={r['final_entropy']:.4f}")
    
    for seed in [42, 43, 44, 45, 46, 47, 48, 49]:
        r = run_open_system(seed, n_steps, base_rate=3.0, constraint_strength=0.5, exhaust_rate=0.1)
        results.append(r)
        print(f"  Open seed {seed}: sealed at step {r['seal_step']}, "
              f"E={r['final_energy']:.1f}, S={r['final_entropy']:.4f}, "
              f"inj={r['total_injected']:.1f}, exh={r['total_exhausted']:.3f}")
    
    # === Config B: Constraint strength sweep ===
    print("\n=== Config B: Constraint strength sweep ===")
    for cs, label in [(0.1, 'low'), (0.5, 'medium'), (0.9, 'high')]:
        for seed in [50, 51, 52]:
            r = run_open_system(seed, n_steps, base_rate=3.0, constraint_strength=cs, exhaust_rate=0.1)
            results.append(r)
            print(f"  cs={cs} ({label}) seed {seed}: sealed at {r['seal_step']}, "
                  f"inj={r['total_injected']:.1f}")
    
    # === Config C: Exhaust rate sweep ===
    print("\n=== Config C: Exhaust rate sweep ===")
    for er, label in [(0.01, 'low'), (0.1, 'medium'), (0.3, 'high')]:
        for seed in [60, 61, 62]:
            r = run_open_system(seed, n_steps, base_rate=3.0, constraint_strength=0.5, exhaust_rate=er)
            results.append(r)
            print(f"  er={er} ({label}) seed {seed}: sealed at {r['seal_step']}, "
                  f"S={r['final_entropy']:.4f}, exh={r['total_exhausted']:.3f}")
    
    # === Verify hypotheses ===
    print("\n=== Hypothesis Verification ===")
    hypo_results = verify_hypotheses(results)
    
    print(f"\nHypotheses: {hypo_results['n_pass']}/{hypo_results['n_total']} PASS")
    for h_name, h_data in hypo_results['hypotheses'].items():
        status = "PASS" if h_data['pass'] else "FAIL"
        print(f"  [{status}] {h_name}: {h_data['detail']}")
    
    # Save results
    results_dir = os.path.dirname(os.path.abspath(__file__)) + "/../results"
    os.makedirs(results_dir, exist_ok=True)
    
    serializable = []
    for r in results:
        sr = {k: v for k, v in r.items() if k not in ('energy_trace', 'entropy_trace', 'injected_trace', 'exhausted_trace')}
        serializable.append(sr)
    
    output = {
        'experiment': 'exp_205_phase22_p0_open_system',
        'timestamp': timestamp,
        'n_runs': len(results),
        'n_steps': n_steps,
        'hypothesis_results': hypo_results,
        'runs': serializable
    }
    
    results_path = f"{results_dir}/exp_205_phase22_p0_open_system_{timestamp}.json"
    with open(results_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nResults saved to: {results_path}")
    print(f"Phase 22 P0 experiment complete: {hypo_results['n_pass']}/{hypo_results['n_total']} hypotheses validated")
    
    return output


if __name__ == '__main__':
    main()
