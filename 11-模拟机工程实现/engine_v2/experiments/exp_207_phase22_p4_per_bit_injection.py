"""
exp_207_phase22_p4_per_bit_injection.py

Phase 22 P4: Per-Bit Energy Injection Scaling

HYPOTHESIS: If injection_rate is proportional to N0, the energy scaling
direction will REVERSE from exp_206 (where E ∝ N0^(-0.184) with fixed injection).

In exp_206 (P3):
- Fixed injection rate per step → small N0 systems have higher energy DENSITY
- E ∝ N0^(-0.184) (energy decreases with N0)

In exp_207 (P4):
- Per-bit injection: rate = base_rate × N0 / N_ref
- Expected: E_total ∝ N0 (linear scaling), E_per_bit = constant

TEST CONFIGS:
- N0 = 24, 48, 72, 96
- Injection mode: "fixed" (baseline) vs "per_bit" (test)
- Open system only (closed doesn't have injection)

HYPOTHESES:
- H22-P4a: Per-bit injection → E_total ∝ N0 (linear or super-linear)
- H22-P4b: Per-bit injection → E_per_bit ≈ constant across N0
- H22-P4c: Per-bit injection → S_per_bit ≈ constant
- H22-P4d: E-S correlation phase transition still at N0 ≈ 60-72
"""

import sys
import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from diffsim.energy import EnergyConfig
from diffsim.entropy import EntropyConfig
from diffsim.environment_energy import EnvironmentConfig as OpenSystemConfig
from diffsim.world import World, WorldConfig


def run_experiment(
    n_bits: int,
    seed: int,
    injection_mode: str = "fixed",  # "fixed" or "per_bit"
    base_injection: float = 3.0,
    n_ref: int = 48,
    max_steps: int = 2000
) -> Dict[str, Any]:
    """
    Run a single world simulation with specified injection mode.
    
    Args:
        n_bits: Number of bits (N0)
        seed: Random seed
        injection_mode: "fixed" (constant rate) or "per_bit" (rate ∝ N0)
        base_injection: Base injection rate
        n_ref: Reference N0 for per-bit scaling
        max_steps: Maximum simulation steps
    
    Returns:
        Dict with final metrics
    """
    np.random.seed(seed)
    
    # Calculate injection rate based on mode
    if injection_mode == "per_bit":
        # Per-bit scaling: rate ∝ N0
        injection_rate = base_injection * (n_bits / n_ref)
    else:
        # Fixed injection (same as exp_206)
        injection_rate = base_injection
    
    # Create energy config
    energy_config = EnergyConfig(
        initial_budget=100.0,
        decay_rate=0.05,
        injection_rate=2.0,  # baseline
        m9_cost=1.0,
        m3_cost=0.5,
        m6_cost=0.5,
        m1_cost=0.3
    )
    
    # Create open system config with calculated injection rate
    open_config = OpenSystemConfig(
        base_rate=injection_rate,
        constraint_strength=0.5,
        exhaust_rate=0.1,
        max_energy=300.0,
        constraint_energy_factor=1.5
    )
    
    # Create entropy config
    entropy_config = EntropyConfig(
        temperature=1.0,
        production_threshold=0.01
    )
    
    # Create world config
    world_config = WorldConfig(
        n_bits=n_bits,
        binding_threshold=20,  # Allow dynamics before sealing
        seal_threshold=0.4,
        energy_config=energy_config,
        entropy_config=entropy_config,
        open_system_config=open_config,
        max_steps=max_steps
    )
    
    # Create and run world
    world = World(world_config)
    summary = world.run()
    
    # Extract energy and entropy traces
    energy_trace = []
    entropy_trace = []
    for s in world.state.snapshots:
        e = s.get('energy', {})
        ent = s.get('entropy', {})
        energy_trace.append(e.get('energy', float(e)) if isinstance(e, dict) else float(e))
        entropy_trace.append(ent.get('entropy', float(ent)) if isinstance(ent, dict) else float(ent))
    
    # Get final metrics
    energy_summary = summary.get('energy', {}) if isinstance(summary.get('energy'), dict) else {}
    entropy_summary = summary.get('entropy', {}) if isinstance(summary.get('entropy'), dict) else {}
    open_summary = summary.get('open_system', {}) if isinstance(summary.get('open_system'), dict) else {}
    
    final_energy = energy_trace[-1] if energy_trace else 0.0
    final_entropy = entropy_trace[-1] if entropy_trace else 0.0
    energy_per_bit = final_energy / n_bits if n_bits > 0 else 0.0
    entropy_per_bit = final_entropy / n_bits if n_bits > 0 else 0.0
    
    return {
        'n_bits': n_bits,
        'seed': seed,
        'injection_mode': injection_mode,
        'injection_rate': injection_rate,
        'final_energy': final_energy,
        'final_entropy': final_entropy,
        'energy_per_bit': energy_per_bit,
        'entropy_per_bit': entropy_per_bit,
        'sealed': summary.get('is_sealed', False),
        'seal_step': summary.get('seal_step'),
        'total_steps': summary.get('total_steps', 0),
        'total_injected': open_summary.get('total_energy_injected', 0.0),
        'total_exhausted': open_summary.get('total_entropy_exhausted', 0.0),
        'energy_trace': energy_trace,
        'entropy_trace': entropy_trace
    }


def compute_scaling_exponent(results: List[Dict], metric: str, n_bits_list: List[int]) -> Dict:
    """
    Compute scaling exponent: metric ∝ N0^exponent
    
    Uses log-log regression: log(metric) = log(C) + exponent * log(N0)
    """
    # Group by N0
    n0_means = {}
    for n0 in n_bits_list:
        values = [r[metric] for r in results if r['n_bits'] == n0]
        if values:
            n0_means[n0] = np.mean(values)
    
    if len(n0_means) < 2:
        return {'exponent': None, 'r_squared': None}
    
    # Log-log regression
    log_n0 = np.log(list(n0_means.keys()))
    log_metric = np.log(list(n0_means.values()))
    
    # Linear regression
    coeffs = np.polyfit(log_n0, log_metric, 1)
    exponent = coeffs[0]
    
    # R-squared
    predicted = np.polyval(coeffs, log_n0)
    ss_res = np.sum((log_metric - predicted) ** 2)
    ss_tot = np.sum((log_metric - np.mean(log_metric)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    return {
        'exponent': exponent,
        'r_squared': r_squared,
        'n0_means': n0_means
    }


def compute_es_correlation(results: List[Dict], n_bits: int) -> float:
    """Compute E-S correlation for a given N0."""
    energies = [r['final_energy'] for r in results if r['n_bits'] == n_bits]
    entropies = [r['final_entropy'] for r in results if r['n_bits'] == n_bits]
    
    if len(energies) < 3:
        return 0.0
    
    # Pearson correlation
    if np.std(energies) == 0 or np.std(entropies) == 0:
        return 0.0
    
    correlation = np.corrcoef(energies, entropies)[0, 1]
    return correlation


def main():
    """Run Phase 22 P4 experiment."""
    print("=" * 70)
    print("Phase 22 P4: Per-Bit Energy Injection Scaling (exp_207)")
    print("=" * 70)
    
    # Configuration
    n_bits_list = [24, 48, 72, 96]
    seeds = [42, 142, 242, 342, 542, 742]  # 6 seeds
    injection_modes = ["fixed", "per_bit"]
    base_injection = 3.0
    n_ref = 48
    
    results = []
    
    # Run experiments
    total_runs = len(n_bits_list) * len(seeds) * len(injection_modes)
    print(f"\nTotal runs: {total_runs}")
    print(f"N0: {n_bits_list}")
    print(f"Seeds: {seeds}")
    print(f"Modes: {injection_modes}")
    print()
    
    run_idx = 0
    for mode in injection_modes:
        print(f"\n{'='*50}")
        print(f"Injection Mode: {mode}")
        print(f"{'='*50}")
        
        for n_bits in n_bits_list:
            for seed in seeds:
                run_idx += 1
                print(f"\r[{run_idx}/{total_runs}] N0={n_bits}, seed={seed}, mode={mode}    ", end="", flush=True)
                
                result = run_experiment(
                    n_bits=n_bits,
                    seed=seed,
                    injection_mode=mode,
                    base_injection=base_injection,
                    n_ref=n_ref
                )
                results.append(result)
    
    print("\n\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    
    # Analyze results
    print("\n### Scaling Analysis\n")
    
    for mode in injection_modes:
        print(f"\n#### Mode: {mode}\n")
        mode_results = [r for r in results if r['injection_mode'] == mode]
        
        # Energy scaling
        energy_scaling = compute_scaling_exponent(mode_results, 'final_energy', n_bits_list)
        print(f"Energy scaling: E = {energy_scaling['n0_means'].get(24, 0):.2f} * N0^{energy_scaling['exponent']:.3f} (R2={energy_scaling['r_squared']:.3f})")
        
        # Energy per bit scaling
        epb_scaling = compute_scaling_exponent(mode_results, 'energy_per_bit', n_bits_list)
        print(f"Energy/bit scaling: E/N0 = {epb_scaling['n0_means'].get(24, 0):.3f} * N0^{epb_scaling['exponent']:.3f} (R2={epb_scaling['r_squared']:.3f})")
        
        # Entropy per bit scaling
        ent_scaling = compute_scaling_exponent(mode_results, 'entropy_per_bit', n_bits_list)
        print(f"Entropy/bit scaling: S/N0 = {ent_scaling['n0_means'].get(24, 0):.4f} * N0^{ent_scaling['exponent']:.3f} (R2={ent_scaling['r_squared']:.3f})")
        
        # E-S correlation by N0
        print(f"\nE-S Correlation by N0:")
        for n0 in n_bits_list:
            corr = compute_es_correlation(mode_results, n0)
            print(f"  N0={n0}: r = {corr:.3f}")
    
    # Hypothesis evaluation
    print("\n" + "=" * 70)
    print("HYPOTHESIS EVALUATION")
    print("=" * 70)
    
    per_bit_results = [r for r in results if r['injection_mode'] == "per_bit"]
    fixed_results = [r for r in results if r['injection_mode'] == "fixed"]
    
    # H22-P4a: Per-bit injection -> E_total ∝ N0 (linear or super-linear)
    energy_scaling_per_bit = compute_scaling_exponent(per_bit_results, 'final_energy', n_bits_list)
    h_p4a = energy_scaling_per_bit['exponent'] >= 1.0
    print(f"\nH22-P4a: Per-bit injection -> E ∝ N0^>=1.0")
    print(f"  Result: E ∝ N0^{energy_scaling_per_bit['exponent']:.3f}")
    print(f"  Verdict: {'PASS' if h_p4a else 'FAIL'}")
    
    # H22-P4b: Per-bit injection -> E_per_bit constant
    epb_scaling_per_bit = compute_scaling_exponent(per_bit_results, 'energy_per_bit', n_bits_list)
    h_p4b = abs(epb_scaling_per_bit['exponent']) < 0.2  # Close to 0
    print(f"\nH22-P4b: Per-bit injection -> E/N0 constant (exponent 0)")
    print(f"  Result: E/N0 ∝ N0^{epb_scaling_per_bit['exponent']:.3f}")
    print(f"  Verdict: {'PASS' if h_p4b else 'FAIL'}")
    
    # H22-P4c: Per-bit injection -> S_per_bit constant
    ent_scaling_per_bit = compute_scaling_exponent(per_bit_results, 'entropy_per_bit', n_bits_list)
    h_p4c = abs(ent_scaling_per_bit['exponent']) < 0.2
    print(f"\nH22-P4c: Per-bit injection -> S/N0 constant (exponent 0)")
    print(f"  Result: S/N0 ∝ N0^{ent_scaling_per_bit['exponent']:.3f}")
    print(f"  Verdict: {'PASS' if h_p4c else 'FAIL'}")
    
    # H22-P4d: E-S correlation phase transition at N0 60-72
    print(f"\nH22-P4d: E-S correlation phase transition at N0 60-72")
    correlations = []
    for n0 in n_bits_list:
        corr = compute_es_correlation(per_bit_results, n0)
        correlations.append((n0, corr))
        print(f"  N0={n0}: r = {corr:.3f}")
    
    # Check for sign flip
    n0_24_corr = correlations[0][1]
    n0_96_corr = correlations[-1][1]
    h_p4d = n0_24_corr * n0_96_corr < 0  # Sign flip indicates phase transition
    print(f"  Correlation flip: {n0_24_corr:.3f} -> {n0_96_corr:.3f}")
    print(f"  Verdict: {'PASS (phase transition detected)' if h_p4d else 'FAIL'}")
    
    # Save results
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"exp_207_p4_per_bit_injection_{timestamp}.json"
    
    # Convert energy_trace/entropy_trace lists to serializable format
    serializable_results = []
    for r in results:
        sr = {k: v for k, v in r.items() if k not in ['energy_trace', 'entropy_trace']}
        serializable_results.append(sr)
    
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'config': {
                'n_bits_list': n_bits_list,
                'seeds': seeds,
                'injection_modes': injection_modes,
                'base_injection': base_injection,
                'n_ref': n_ref
            },
            'results': serializable_results,
            'analysis': {
                'fixed': {
                    'energy_scaling': compute_scaling_exponent(fixed_results, 'final_energy', n_bits_list),
                    'epb_scaling': compute_scaling_exponent(fixed_results, 'energy_per_bit', n_bits_list),
                    'ent_scaling': compute_scaling_exponent(fixed_results, 'entropy_per_bit', n_bits_list)
                },
                'per_bit': {
                    'energy_scaling': energy_scaling_per_bit,
                    'epb_scaling': epb_scaling_per_bit,
                    'ent_scaling': ent_scaling_per_bit
                }
            },
            'hypotheses': {
                'H22-P4a': h_p4a,
                'H22-P4b': h_p4b,
                'H22-P4c': h_p4c,
                'H22-P4d': h_p4d
            }
        }, f, indent=2, default=str)
    
    print(f"\n\nResults saved to: {results_file}")
    
    # Summary
    passed = sum([h_p4a, h_p4b, h_p4c, h_p4d])
    print(f"\n{'='*70}")
    print(f"PHASE 22 P4 SUMMARY: {passed}/4 PASS")
    print(f"{'='*70}")
    
    return results


if __name__ == "__main__":
    main()
