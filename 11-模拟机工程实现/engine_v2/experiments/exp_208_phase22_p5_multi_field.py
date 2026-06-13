"""
Phase 22 P5: Multi-Field Competitive Constraints Experiment

Tests 5 hypotheses (H22-P5a through H22-P5e):
- H22-P5a: Field Interference (out-of-phase ->' lower energy)
- H22-P5b: Cooperative Synergy (2 weak fields > 1 medium field)
- H22-P5c: Critical Dominance Ratio (phase transition at R_c ~ 0.7)
- H22-P5d: Spatial Field Separation (even/odd ??' higher entropy)
- H22-P5e: Competitive Coupling (bistable dynamics)

Author: AI Agent (Heartbeat 2026-06-14 03:44)
"""

import sys
import os
import math
import json
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim.multi_field import MultiFieldManager, ConstraintField, MultiFieldConfig
from diffsim.environment_energy import (
    EnvironmentConfig, 
    EnvironmentEnergyField,
    EntropyExhaust,
    OpenSystemCoupling
)


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment run."""
    name: str
    n_bits: int = 48
    n_steps: int = 1000
    seed: int = 42
    
    # Energy parameters
    base_rate: float = 2.0
    constraint_energy_factor: float = 1.5
    exhaust_rate: float = 0.05
    max_energy: float = 200.0
    
    # Multi-field config
    fields: List[ConstraintField] = field(default_factory=list)


def run_single_experiment(config: ExperimentConfig) -> Dict:
    """
    Run a single experiment with multi-field constraints.
    
    Returns dict with metrics: energy_history, entropy_history, injection_history, etc.
    """
    # Set random seed
    np.random.seed(config.seed)
    
    # Initialize bit state (random)
    bits = np.random.randint(0, 2, size=config.n_bits).astype(float)
    
    # Create multi-field config
    mf_config = MultiFieldConfig(
        fields=config.fields,
        normalize_weights=True
    )
    
    # Create environment config with multi-field
    env_config = EnvironmentConfig(
        base_rate=config.base_rate,
        constraint_energy_factor=config.constraint_energy_factor,
        exhaust_rate=config.exhaust_rate,
        max_energy=config.max_energy,
        use_multi_field=True,
        multi_field_config=mf_config
    )
    
    # Create open system coupling
    coupling = OpenSystemCoupling(env_config)
    
    # Tracking histories
    energy_history = []
    entropy_history = []
    injection_history = []
    constraint_history = []
    
    # Initial entropy (Shannon entropy of bit distribution)
    def compute_entropy(bits_array):
        """Compute Shannon entropy of bit array."""
        n_ones = np.sum(bits_array)
        n_zeros = len(bits_array) - n_ones
        if n_ones == 0 or n_zeros == 0:
            return 0.0
        p1 = n_ones / len(bits_array)
        p0 = n_zeros / len(bits_array)
        return -p0 * math.log2(p0) - p1 * math.log2(p1)
    
    # Run simulation
    current_energy = 50.0  # Initial energy
    current_entropy = compute_entropy(bits)
    
    for t in range(config.n_steps):
        # Open system step
        step_result = coupling.step(
            current_energy=current_energy,
            current_entropy=current_entropy,
            layer_bits=bits,
            t=t
        )
        
        # Update energy and entropy
        current_energy = step_result['energy_after']
        current_entropy = step_result['entropy_remaining']
        
        # Record histories
        energy_history.append(current_energy)
        entropy_history.append(current_entropy)
        injection_history.append(step_result['energy_injected'])
        constraint_history.append(coupling.env_field.state.current_constraint)
        
        # Simple bit dynamics (random flip with constraint-modulated probability)
        # Higher constraint ??' less flipping (more stability)
        flip_prob = 0.1 * (1.0 - coupling.env_field.state.current_constraint)
        for i in range(config.n_bits):
            if np.random.random() < flip_prob:
                bits[i] = 1.0 - bits[i]
        
        # Recompute entropy
        current_entropy = compute_entropy(bits)
    
    # Compute summary metrics
    mean_energy = np.mean(energy_history[100:])  # Skip first 100 steps
    mean_entropy = np.mean(entropy_history[100:])
    mean_injection = np.mean(injection_history[100:])
    final_energy = energy_history[-1]
    final_entropy = entropy_history[-1]
    
    # Energy variance (measure of stability)
    energy_std = np.std(energy_history[100:])
    
    return {
        'config_name': config.name,
        'mean_energy': mean_energy,
        'mean_entropy': mean_entropy,
        'mean_injection': mean_injection,
        'final_energy': final_energy,
        'final_entropy': final_entropy,
        'energy_std': energy_std,
        'n_steps': config.n_steps,
        'energy_history': energy_history[::10],  # Downsample for output
        'entropy_history': entropy_history[::10],
        'constraint_history': constraint_history[::10]
    }


def test_hypothesis_p5a():
    """H22-P5a: Field Interference (out-of-phase ??' lower energy)."""
    print("\n" + "="*60)
    print("H22-P5a: Field Interference Test")
    print("="*60)
    
    configs = [
        # In-phase (should produce higher energy)
        ExperimentConfig(
            name="p5a_in_phase",
            fields=[
                ConstraintField("A", strength=0.5, frequency=0.0, phase=0.0),
                ConstraintField("B", strength=0.5, frequency=0.0, phase=0.0)
            ],
        ),
        # Out-of-phase (should produce lower energy)
        ExperimentConfig(
            name="p5a_out_phase",
            fields=[
                ConstraintField("A", strength=0.5, frequency=0.0, phase=0.0),
                ConstraintField("B", strength=0.5, frequency=0.0, phase=math.pi)
            ],
        ),
        # Single field baseline
        ExperimentConfig(
            name="p5a_baseline",
            fields=[
                ConstraintField("single", strength=0.5)
            ],
        )
    ]
    
    results = []
    for cfg in configs:
        print(f"\nRunning {cfg.name}...")
        result = run_single_experiment(cfg)
        results.append(result)
        print(f"  Mean energy: {result['mean_energy']:.2f}")
        print(f"  Mean entropy: {result['mean_entropy']:.4f}")
    
    # Evaluate hypothesis
    in_phase_energy = results[0]['mean_energy']
    out_phase_energy = results[1]['mean_energy']
    baseline_energy = results[2]['mean_energy']
    
    print(f"\nResults:")
    print(f"  Baseline (single field): {baseline_energy:.2f}")
    print(f"  In-phase (2 fields): {in_phase_energy:.2f}")
    print(f"  Out-of-phase (2 fields): {out_phase_energy:.2f}")
    
    # H22-P5a: Out-of-phase should have LOWER energy than in-phase
    if out_phase_energy < in_phase_energy:
        print(f"\n[PASS] H22-P5a PARTIAL PASS: Out-of-phase ({out_phase_energy:.2f}) < In-phase ({in_phase_energy:.2f})")
        return True
    else:
        print(f"\n[FAIL] H22-P5a FAIL: Out-of-phase ({out_phase_energy:.2f}) >= In-phase ({in_phase_energy:.2f})")
        return False


def test_hypothesis_p5b():
    """H22-P5b: Cooperative Synergy (2 weak fields > 1 medium field)."""
    print("\n" + "="*60)
    print("H22-P5b: Cooperative Synergy Test")
    print("="*60)
    
    configs = [
        # Two weak fields (cooperative)
        ExperimentConfig(
            name="p5b_two_weak",
            fields=[
                ConstraintField("A", strength=0.3, frequency=0.0, phase=0.0),
                ConstraintField("B", strength=0.3, frequency=0.0, phase=0.0)
            ],
        ),
        # One medium field
        ExperimentConfig(
            name="p5b_one_medium",
            fields=[
                ConstraintField("single", strength=0.6)
            ],
        )
    ]
    
    results = []
    for cfg in configs:
        print(f"\nRunning {cfg.name}...")
        result = run_single_experiment(cfg)
        results.append(result)
        print(f"  Mean energy: {result['mean_energy']:.2f}")
    
    two_weak_energy = results[0]['mean_energy']
    one_medium_energy = results[1]['mean_energy']
    
    print(f"\nResults:")
    print(f"  Two weak fields (0.3+0.3): {two_weak_energy:.2f}")
    print(f"  One medium field (0.6): {one_medium_energy:.2f}")
    
    # H22-P5b: Two weak cooperative fields should produce HIGHER energy than one medium field
    if two_weak_energy > one_medium_energy:
        print(f"\n[PASS] H22-P5b PASS: Synergy! 0.3+0.3 ({two_weak_energy:.2f}) > 0.6 ({one_medium_energy:.2f})")
        return True
    else:
        print(f"\n[FAIL] H22-P5b FAIL: No synergy. 0.3+0.3 ({two_weak_energy:.2f}) <= 0.6 ({one_medium_energy:.2f})")
        return False


def test_hypothesis_p5c():
    """H22-P5c: Critical Dominance Ratio (phase transition at R_c ~ 0.7)."""
    print("\n" + "="*60)
    print("H22-P5c: Critical Dominance Ratio Test")
    print("="*60)
    
    ratios = [(0.5, 0.5), (0.6, 0.4), (0.7, 0.3), (0.8, 0.2), (0.9, 0.1)]
    results = []
    
    for r1, r2 in ratios:
        cfg = ExperimentConfig(
            name=f"p5c_r{r1}",
            fields=[
                ConstraintField("strong", strength=r1),
                ConstraintField("weak", strength=r2)
            ],
        )
        print(f"\nRunning ratio {r1}:{r2}...")
        result = run_single_experiment(cfg)
        results.append(result)
        print(f"  Mean energy: {result['mean_energy']:.2f}")
    
    # Check for phase transition (non-linear jump in energy)
    energies = [r['mean_energy'] for r in results]
    print(f"\nEnergy vs Ratio:")
    for i, ((r1, r2), e) in enumerate(zip(ratios, energies)):
        print(f"  {r1}:{r2} ??' {e:.2f}")
    
    # Look for critical point (largest energy jump)
    diffs = [energies[i+1] - energies[i] for i in range(len(energies)-1)]
    max_diff_idx = np.argmax(np.abs(diffs))
    critical_ratio = ratios[max_diff_idx + 1]
    
    print(f"\nCritical ratio appears at: {critical_ratio[0]}:{critical_ratio[1]}")
    
    if 0.65 <= critical_ratio[0] <= 0.75:
        print(f"[PASS] H22-P5c PARTIAL PASS: Critical ratio ~ 0.7 ({critical_ratio[0]})")
        return True
    else:
        print(f"[FAIL] H22-P5c FAIL: Critical ratio not at ~0.7 (found at {critical_ratio[0]})")
        return False


def test_hypothesis_p5d():
    """H22-P5d: Spatial Field Separation (even/odd ??' higher total entropy)."""
    print("\n" + "="*60)
    print("H22-P5d: Spatial Field Separation Test")
    print("="*60)
    
    configs = [
        # Two fields on same domain (all)
        ExperimentConfig(
            name="p5d_same_domain",
            fields=[
                ConstraintField("A", strength=0.5, domain="all"),
                ConstraintField("B", strength=0.5, domain="all")
            ],
        ),
        # Two fields on different domains (even/odd)
        ExperimentConfig(
            name="p5d_split_domain",
            fields=[
                ConstraintField("A", strength=0.5, domain="even"),
                ConstraintField("B", strength=0.5, domain="odd")
            ],
        )
    ]
    
    results = []
    for cfg in configs:
        print(f"\nRunning {cfg.name}...")
        result = run_single_experiment(cfg)
        results.append(result)
        print(f"  Mean entropy: {result['mean_entropy']:.4f}")
        print(f"  Energy std: {result['energy_std']:.2f}")
    
    same_domain_entropy = results[0]['mean_entropy']
    split_domain_entropy = results[1]['mean_entropy']
    
    print(f"\nResults:")
    print(f"  Same domain (all+all): {same_domain_entropy:.4f}")
    print(f"  Split domain (even+odd): {split_domain_entropy:.4f}")
    
    # H22-P5d: Spatial separation should produce HIGHER entropy
    if split_domain_entropy > same_domain_entropy:
        print(f"\n[PASS] H22-P5d PASS: Split domain ({split_domain_entropy:.4f}) > Same domain ({same_domain_entropy:.4f})")
        return True
    else:
        print(f"\n[FAIL] H22-P5d FAIL: Split domain ({split_domain_entropy:.4f}) <= Same domain ({same_domain_entropy:.4f})")
        return False


def test_hypothesis_p5e():
    """H22-P5e: Competitive Coupling (bistable dynamics)."""
    print("\n" + "="*60)
    print("H22-P5e: Competitive Coupling Test")
    print("="*60)
    
    config = ExperimentConfig(
        name="p5e_competitive",
        fields=[
            ConstraintField("A", strength=0.5, frequency=0.001, phase=0.0),
            ConstraintField("B", strength=0.5, frequency=0.001, phase=math.pi)
        ],
    )
    
    print(f"\nRunning {config.name}...")
    result = run_single_experiment(config)
    
    # Analyze bistability (constraint history should show switching)
    constraint_history = result['constraint_history']
    
    # Check for switching (variance in constraint)
    constraint_std = np.std(constraint_history)
    constraint_mean = np.mean(constraint_history)
    
    print(f"\nConstraint dynamics:")
    print(f"  Mean: {constraint_mean:.4f}")
    print(f"  Std: {constraint_std:.4f}")
    print(f"  Range: [{min(constraint_history):.4f}, {max(constraint_history):.4f}]")
    
    # H22-P5e: Competitive coupling should produce bistable dynamics (high variance)
    if constraint_std > 0.1:
        print(f"\n[PASS] H22-P5e PARTIAL PASS: Bistable dynamics detected (std={constraint_std:.4f} > 0.1)")
        return True
    else:
        print(f"\n[FAIL] H22-P5e FAIL: No bistability (std={constraint_std:.4f} <= 0.1)")
        return False


def main():
    """Run all Phase 22 P5 experiments."""
    print("="*60)
    print("Phase 22 P5: Multi-Field Competitive Constraints")
    print("="*60)
    
    results = {
        'H22-P5a': test_hypothesis_p5a(),
        'H22-P5b': test_hypothesis_p5b(),
        'H22-P5c': test_hypothesis_p5c(),
        'H22-P5d': test_hypothesis_p5d(),
        'H22-P5e': test_hypothesis_p5e()
    }
    
    # Summary
    print("\n" + "="*60)
    print("Phase 22 P5 Summary")
    print("="*60)
    
    n_pass = sum(1 for v in results.values() if v)
    n_total = len(results)
    
    for hypothesis, passed in results.items():
        status = "[PASS] PASS" if passed else "[FAIL] FAIL"
        print(f"  {hypothesis}: {status}")
    
    print(f"\nTotal: {n_pass}/{n_total} hypotheses passed")
    
    # Save results
    output_file = f"results/exp_208_p5_multi_field_{np.random.randint(1000)}.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    main()
