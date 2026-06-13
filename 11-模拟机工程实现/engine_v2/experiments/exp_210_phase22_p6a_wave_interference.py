"""
Phase 22 P6a: Wave Interference Coupling Experiment (exp_210)

PURPOSE: Re-test H22-P5a and H22-P5d with the new interference coupling mode.
These two hypotheses FAILED in exp_209 because the engine used additive coupling
(linear intensity combination) instead of wave superposition (amplitude sum).

With interference coupling:
- H22-P5a: Out-of-phase fields should destructively interfere → lower constraint
- H22-P5d: Anti-phase fields should produce spatial interference patterns

KEY CHANGE: coupling_type="interference", coupling_mode="amplitude"
- Additive:  c = |A1|^2 + |A2|^2 (intensity sum, no cancellation)
- Interference: c = |A1 + A2|^2 = |A1|^2 + |A2|^2 + 2|A1||A2|cos(Δφ)
  → When Δφ = π: c = |A1 - A2|^2 = 0 (perfect cancellation for equal amplitudes)

Also tests two new interference-specific hypotheses:
- H22-P6a-1: Partial interference (Δφ = π/2) → intermediate constraint
- H22-P6a-2: Spatial fringe pattern in per-bit constraint

Author: AI Agent (Heartbeat 2026-06-14 06:14)
"""

import sys
import os
import math
import json
import numpy as np
from dataclasses import dataclass
from typing import List, Dict

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim.multi_field import (
    MultiFieldManager, ConstraintField, MultiFieldConfig,
    create_two_field_interference
)


def compute_constraint_time_series(manager: MultiFieldManager, n_steps: int) -> List[float]:
    """Compute constraint time series."""
    return [manager.compute_effective_constraint(float(t)) for t in range(n_steps)]


def test_h22_p5a_interference():
    """
    H22-P5a (RETEST): Field Interference — out-of-phase → lower constraint.
    
    exp_209 FAIL reason: Used additive coupling, no wave cancellation.
    exp_210 FIX: Use interference coupling (wave superposition).
    
    Expected: out-of-phase mean << in-phase mean (destructive interference)
    """
    print("\n" + "="*60)
    print("H22-P5a (RETEST): Field Interference with Wave Superposition")
    print("="*60)
    
    n_steps = 1000
    strength = 0.5
    
    # All three configs use interference coupling now
    configs = {
        "single_field": MultiFieldConfig(fields=[
            ConstraintField("single", strength=strength, frequency=0.02, phase=0.0,
                           coupling_type="interference", coupling_mode="amplitude")
        ]),
        "in_phase": MultiFieldConfig(fields=[
            ConstraintField("A", strength=strength, frequency=0.02, phase=0.0,
                          coupling_type="interference", coupling_mode="amplitude"),
            ConstraintField("B", strength=strength, frequency=0.02, phase=0.0,
                          coupling_type="interference", coupling_mode="amplitude")
        ]),
        "out_of_phase": MultiFieldConfig(fields=[
            ConstraintField("A", strength=strength, frequency=0.02, phase=0.0,
                          coupling_type="interference", coupling_mode="amplitude"),
            ConstraintField("B", strength=strength, frequency=0.02, phase=math.pi,
                          coupling_type="interference", coupling_mode="amplitude")
        ])
    }
    
    results = {}
    for name, cfg in configs.items():
        manager = MultiFieldManager(cfg)
        constraints = compute_constraint_time_series(manager, n_steps)
        results[name] = {
            'mean': np.mean(constraints),
            'std': np.std(constraints),
            'min': min(constraints),
            'max': max(constraints)
        }
        print(f"\n  {name}:")
        print(f"    Mean: {results[name]['mean']:.4f}, Std: {results[name]['std']:.4f}")
        print(f"    Range: [{results[name]['min']:.4f}, {results[name]['max']:.4f}]")
    
    in_mean = results['in_phase']['mean']
    out_mean = results['out_of_phase']['mean']
    single_mean = results['single_field']['mean']
    
    print(f"\n  Analysis:")
    print(f"    Single field baseline: {single_mean:.4f}")
    print(f"    In-phase (constructive): {in_mean:.4f}")
    print(f"    Out-of-phase (destructive): {out_mean:.4f}")
    print(f"    Reduction: {((in_mean - out_mean) / max(in_mean, 0.001) * 100):.1f}%")
    
    # PASS if out-of-phase is significantly lower than in-phase
    # With perfect interference: out ≈ 0, in ≈ 1
    if out_mean < in_mean * 0.5:
        print(f"\n  [PASS] H22-P5a PASS: Destructive interference confirmed!")
        print(f"    Out-of-phase ({out_mean:.4f}) < 50% of in-phase ({in_mean:.4f})")
        return True
    else:
        print(f"\n  [FAIL] H22-P5a FAIL: Insufficient interference effect")
        return False


def test_h22_p5d_interference():
    """
    H22-P5d (RETEST): Spatial Field Separation — anti-phase → spatial entropy.
    
    exp_209 FAIL reason: Additive coupling, no spatial interference.
    exp_210 FIX: Interference coupling creates spatial fringe patterns.
    
    With anti-phase fields and spatial phase offsets, per-bit constraints
    should show interference fringes (alternating high/low).
    """
    print("\n" + "="*60)
    print("H22-P5d (RETEST): Spatial Interference Fringes")
    print("="*60)
    
    n_bits = 32
    n_steps = 500
    
    # Anti-phase fields with interference coupling
    cfg = MultiFieldConfig(fields=[
        ConstraintField("A", strength=0.5, frequency=0.02, phase=0.0,
                       coupling_type="interference", coupling_mode="amplitude"),
        ConstraintField("B", strength=0.5, frequency=0.02, phase=math.pi,
                       coupling_type="interference", coupling_mode="amplitude")
    ])
    
    # Also test in-phase for comparison
    cfg_same = MultiFieldConfig(fields=[
        ConstraintField("A", strength=0.5, frequency=0.02, phase=0.0,
                       coupling_type="interference", coupling_mode="amplitude"),
        ConstraintField("B", strength=0.5, frequency=0.02, phase=0.0,
                       coupling_type="interference", coupling_mode="amplitude")
    ])
    
    manager_anti = MultiFieldManager(cfg)
    manager_same = MultiFieldManager(cfg_same)
    
    # Collect per-bit constraints over time
    per_bit_anti = np.zeros(n_bits)
    per_bit_same = np.zeros(n_bits)
    
    for t in range(n_steps):
        per_bit_anti += manager_anti.compute_per_bit_constraint(float(t), n_bits)
        per_bit_same += manager_same.compute_per_bit_constraint(float(t), n_bits)
    
    per_bit_anti /= n_steps
    per_bit_same /= n_steps
    
    # Compute spatial entropy (variance across bits)
    anti_entropy = np.std(per_bit_anti)
    same_entropy = np.std(per_bit_same)
    
    print(f"\n  Anti-phase per-bit std (spatial entropy): {anti_entropy:.6f}")
    print(f"  In-phase per-bit std (spatial entropy): {same_entropy:.6f}")
    print(f"\n  Per-bit constraint profile (anti-phase, first 8 bits):")
    for i in range(8):
        print(f"    bit[{i:2d}]: {per_bit_anti[i]:.6f}")
    
    # For anti-phase with spatial phase, different bits should see different
    # interference patterns → high spatial variance
    # For in-phase, all bits should see similar (constructive) pattern
    if anti_entropy > same_entropy * 1.5:
        print(f"\n  [PASS] H22-P5d PASS: Spatial interference fringes detected!")
        print(f"    Anti-phase entropy ({anti_entropy:.6f}) >> In-phase ({same_entropy:.6f})")
        return True
    else:
        print(f"\n  [FAIL] H22-P5d FAIL: No significant spatial pattern")
        return False


def test_h22_p6a_1_partial_interference():
    """
    H22-P6a-1: Partial interference (Δφ = π/2) → intermediate constraint.
    
    When phase difference is π/2, the interference term is zero:
    c = |A1|^2 + |A2|^2 (orthogonal, no enhancement or cancellation)
    
    This should be between in-phase (max) and out-of-phase (min).
    """
    print("\n" + "="*60)
    print("H22-P6a-1: Partial Interference (Δφ = π/2)")
    print("="*60)
    
    n_steps = 1000
    strength = 0.5
    
    phase_diffs = [0.0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi]
    results = {}
    
    for phase_diff in phase_diffs:
        cfg = MultiFieldConfig(fields=[
            ConstraintField("A", strength=strength, frequency=0.02, phase=0.0,
                          coupling_type="interference", coupling_mode="amplitude"),
            ConstraintField("B", strength=strength, frequency=0.02, phase=phase_diff,
                          coupling_type="interference", coupling_mode="amplitude")
        ])
        manager = MultiFieldManager(cfg)
        constraints = compute_constraint_time_series(manager, n_steps)
        results[phase_diff] = np.mean(constraints)
    
    print(f"\n  Phase sweep (Δφ → mean constraint):")
    for pd, mean_c in results.items():
        print(f"    Δφ = {pd:5.3f} rad ({pd/math.pi:.2f}π): mean_c = {mean_c:.4f}")
    
    # Check monotonic decrease: 0 > π/4 > π/2 > 3π/4 > π
    phases_ordered = [0.0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi]
    means_ordered = [results[p] for p in phases_ordered]
    
    monotonic = all(means_ordered[i] >= means_ordered[i+1] for i in range(len(means_ordered)-1))
    
    # Check π/2 is between 0 and π
    mid_mean = results[math.pi/2]
    max_mean = results[0.0]
    min_mean = results[math.pi]
    
    print(f"\n  Monotonic decrease: {monotonic}")
    print(f"  Δφ=π/2 ({mid_mean:.4f}) between Δφ=0 ({max_mean:.4f}) and Δφ=π ({min_mean:.4f}): {min_mean < mid_mean < max_mean}")
    
    if monotonic and (min_mean < mid_mean < max_mean):
        print(f"\n  [PASS] H22-P6a-1 PASS: Phase-dependent interference confirmed!")
        print(f"    Constraint smoothly varies with phase difference")
        return True
    else:
        print(f"\n  [FAIL] H22-P6a-1 FAIL: Interference doesn't follow expected pattern")
        return False


def test_h22_p6a_2_spatial_fringes():
    """
    H22-P6a-2: Spatial fringe pattern in per-bit constraint.
    
    Two fields with slight frequency difference → spatial interference fringes
    that shift over time. The per-bit constraint should show periodic spatial pattern.
    """
    print("\n" + "="*60)
    print("H22-P6a-2: Spatial Fringe Pattern Analysis")
    print("="*60)
    
    n_bits = 64
    n_steps = 200
    
    # Two fields with slight frequency offset → moving fringes
    cfg = MultiFieldConfig(fields=[
        ConstraintField("A", strength=0.5, frequency=0.01, phase=0.0,
                       coupling_type="interference", coupling_mode="amplitude"),
        ConstraintField("B", strength=0.5, frequency=0.012, phase=0.0,
                       coupling_type="interference", coupling_mode="amplitude")
    ])
    
    manager = MultiFieldManager(cfg)
    
    # Collect per-bit snapshots at different times
    per_bit_series = []
    for t in range(n_steps):
        pbc = manager.compute_per_bit_constraint(float(t), n_bits)
        per_bit_series.append(pbc)
    
    per_bit_series = np.array(per_bit_series)
    
    # Analyze spatial structure: FFT to find periodic patterns
    mean_spatial = np.mean(per_bit_series, axis=0)  # Time-averaged spatial profile
    spatial_fft = np.abs(np.fft.rfft(mean_spatial))
    spatial_freqs = np.fft.rfftfreq(n_bits, d=1.0)
    
    # Find dominant spatial frequency
    if len(spatial_fft) > 1:
        # Skip DC component
        dominant_idx = np.argmax(spatial_fft[1:]) + 1
        dominant_freq = spatial_freqs[dominant_idx]
        dominant_amp = spatial_fft[dominant_idx]
        dc_amp = spatial_fft[0]
        
        print(f"\n  Spatial FFT analysis:")
        print(f"    DC component: {dc_amp:.4f}")
        print(f"    Dominant frequency: {dominant_freq:.4f} cycles/bit")
        print(f"    Dominant amplitude: {dominant_amp:.4f}")
        print(f"    Spatial contrast (dominant/DC): {dominant_amp/max(dc_amp, 0.001):.4f}")
        
        # Show spatial profile
        print(f"\n  Spatial profile (time-averaged, first 16 bits):")
        for i in range(16):
            bar = '#' * int(mean_spatial[i] * 40)
            print(f"    bit[{i:2d}]: {mean_spatial[i]:.4f} {bar}")
        
        # PASS if there's a clear spatial pattern (high contrast)
        contrast = dominant_amp / max(dc_amp, 0.001)
        if contrast > 0.05:
            print(f"\n  [PASS] H22-P6a-2 PASS: Spatial fringe pattern detected!")
            print(f"    Spatial contrast = {contrast:.4f}")
            return True
        else:
            print(f"\n  [FAIL] H22-P6a-2 FAIL: No clear spatial pattern (contrast={contrast:.4f})")
            return False
    else:
        print(f"\n  [FAIL] H22-P6a-2 FAIL: Insufficient data for FFT")
        return False


def main():
    """Run all Phase 22 P6a experiments."""
    print("=" * 60)
    print("Phase 22 P6a: Wave Interference Coupling (exp_210)")
    print("=" * 60)
    print("\nRe-testing H22-P5a and H22-P5d with interference coupling.")
    print("Also testing new interference-specific hypotheses.")
    
    results = {
        'H22-P5a': test_h22_p5a_interference(),       # RETEST: was FAIL in exp_209
        'H22-P5d': test_h22_p5d_interference(),        # RETEST: was FAIL in exp_209
        'H22-P6a-1': test_h22_p6a_1_partial_interference(),  # NEW
        'H22-P6a-2': test_h22_p6a_2_spatial_fringes()        # NEW
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("Phase 22 P6a Summary (exp_210)")
    print("=" * 60)
    
    n_pass = sum(1 for v in results.values() if v)
    n_total = len(results)
    
    for hypothesis, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        note = " (RETEST - was FAIL)" if hypothesis in ["H22-P5a", "H22-P5d"] else " (NEW)"
        print(f"  {status} {hypothesis}{note}")
    
    print(f"\nTotal: {n_pass}/{n_total} hypotheses passed")
    
    if results.get('H22-P5a') and results.get('H22-P5d'):
        print("\n★ KEY RESULT: Both previously-failed hypotheses now PASS!")
        print("  Wave interference coupling resolves P5 failures.")
    
    # Save results
    output_dir = "C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现/engine_v2/results"
    os.makedirs(output_dir, exist_ok=True)
    
    result_data = {
        'experiment': 'exp_210_phase22_p6a_wave_interference',
        'timestamp': '2026-06-14_0614',
        'results': {k: ('PASS' if v else 'FAIL') for k, v in results.items()},
        'summary': f"{n_pass}/{n_total} passed",
        'note': 'Re-test of P5a/P5d with interference coupling + new hypotheses'
    }
    
    output_file = os.path.join(output_dir, "exp_210_p6a_wave_interference.json")
    with open(output_file, 'w') as f:
        json.dump(result_data, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    main()
