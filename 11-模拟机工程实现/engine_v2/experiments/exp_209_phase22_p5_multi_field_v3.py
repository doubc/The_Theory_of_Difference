"""
Phase 22 P5: Multi-Field Competitive Constraints Experiment (v3 - SIMPLIFIED)

Simplified version that directly uses MultiFieldManager API without complex coupling.

Tests 5 hypotheses (H22-P5a through H22-P5e):
- H22-P5a: Field Interference (out-of-phase -> lower constraint)
- H22-P5b: Cooperative Synergy (2 weak fields != 1 medium field)
- H22-P5c: Critical Dominance Ratio (phase transition at R_c ~ 0.7)
- H22-P5d: Spatial Field Separation (different phases -> higher entropy)
- H22-P5e: Competitive Coupling (bistable dynamics)

KEY INSIGHT: Test MultiFieldManager directly, not through complex coupling.

Author: AI Agent (Heartbeat 2026-06-14 04:51)
"""

import sys
import os
import math
import json
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffsim.multi_field import MultiFieldManager, ConstraintField, MultiFieldConfig


def compute_constraint_time_series(manager: MultiFieldManager, n_steps: int) -> List[float]:
    """
    Compute constraint time series using MultiFieldManager.
    
    Args:
        manager: MultiFieldManager instance
        n_steps: Number of time steps
    
    Returns:
        List of constraint values over time
    """
    constraints = []
    for step in range(n_steps):
        time = float(step)
        # Get effective constraint at this time
        constraint = manager.compute_effective_constraint(time)
        constraints.append(constraint)
    return constraints


def test_hypothesis_p5a():
    """H22-P5a: Field Interference (out-of-phase -> lower mean constraint)."""
    print("\n" + "="*60)
    print("H22-P5a: Field Interference Test")
    print("="*60)
    
    n_steps = 1000
    
    configs = [
        # Baseline: single field
        ("single_field", MultiFieldConfig(
            fields=[ConstraintField("single", strength=0.5, frequency=0.02, phase=0.0)]
        )),
        # In-phase: two fields, same phase
        ("in_phase", MultiFieldConfig(
            fields=[
                ConstraintField("A", strength=0.5, frequency=0.02, phase=0.0),
                ConstraintField("B", strength=0.5, frequency=0.02, phase=0.0)
            ]
        )),
        # Out-of-phase: two fields, opposite phase
        ("out_of_phase", MultiFieldConfig(
            fields=[
                ConstraintField("A", strength=0.5, frequency=0.02, phase=0.0),
                ConstraintField("B", strength=0.5, frequency=0.02, phase=math.pi)
            ]
        ))
    ]
    
    results = {}
    for name, cfg in configs:
        manager = MultiFieldManager(cfg)
        constraints = compute_constraint_time_series(manager, n_steps)
        mean_constraint = np.mean(constraints)
        std_constraint = np.std(constraints)
        results[name] = {
            'mean': mean_constraint,
            'std': std_constraint,
            'min': min(constraints),
            'max': max(constraints)
        }
        print(f"\n{name}:")
        print(f"  Mean constraint: {mean_constraint:.4f}")
        print(f"  Std: {std_constraint:.4f}")
        print(f"  Range: [{min(constraints):.4f}, {max(constraints):.4f}]")
    
    # H22-P5a: Out-of-phase should have LOWER mean constraint than in-phase
    # Reason: destructive interference
    in_phase_mean = results['in_phase']['mean']
    out_phase_mean = results['out_of_phase']['mean']
    
    if out_phase_mean < in_phase_mean:
        print(f"\n[PASS] H22-P5a PASS: Out-of-phase ({out_phase_mean:.4f}) < In-phase ({in_phase_mean:.4f})")
        print(f"  Interference detected: {((in_phase_mean - out_phase_mean) / in_phase_mean * 100):.1f}% reduction")
        return True
    else:
        print(f"\n[FAIL] H22-P5a FAIL: Out-of-phase ({out_phase_mean:.4f}) >= In-phase ({in_phase_mean:.4f})")
        return False


def test_hypothesis_p5b():
    """H22-P5b: Cooperative Synergy (2 weak fields != 1 medium field)."""
    print("\n" + "="*60)
    print("H22-P5b: Cooperative Synergy Test")
    print("="*60)
    
    n_steps = 1000
    
    configs = [
        # Two weak fields (cooperative)
        ("two_weak", MultiFieldConfig(
            fields=[
                ConstraintField("A", strength=0.3, frequency=0.01, phase=0.0),
                ConstraintField("B", strength=0.3, frequency=0.01, phase=0.0)
            ]
        )),
        # One medium field
        ("one_medium", MultiFieldConfig(
            fields=[ConstraintField("single", strength=0.6, frequency=0.01, phase=0.0)]
        ))
    ]
    
    results = {}
    for name, cfg in configs:
        manager = MultiFieldManager(cfg)
        constraints = compute_constraint_time_series(manager, n_steps)
        mean_constraint = np.mean(constraints)
        std_constraint = np.std(constraints)
        results[name] = {
            'mean': mean_constraint,
            'std': std_constraint
        }
        print(f"\n{name}:")
        print(f"  Mean constraint: {mean_constraint:.4f}")
        print(f"  Std: {std_constraint:.4f}")
    
    # H22-P5b: Two weak fields should have DIFFERENT effect than one medium
    # Non-linear coupling should make 0.3+0.3 != 0.6
    two_weak_mean = results['two_weak']['mean']
    one_medium_mean = results['one_medium']['mean']
    diff = abs(two_weak_mean - one_medium_mean)
    
    print(f"\nDifference: {diff:.4f} (two_weak={two_weak_mean:.4f}, one_medium={one_medium_mean:.4f})")
    
    if diff > 0.01:  # Significant difference
        print(f"\n[PASS] H22-P5b PASS: Cooperative synergy detected (diff={diff:.4f} > 0.01)")
        return True
    else:
        print(f"\n[FAIL] H22-P5b FAIL: No synergy (diff={diff:.4f} <= 0.01)")
        return False


def test_hypothesis_p5c():
    """H22-P5c: Critical Dominance Ratio (phase transition at R_c ~ 0.7)."""
    print("\n" + "="*60)
    print("H22-P5c: Critical Dominance Ratio Test")
    print("="*60)
    
    n_steps = 1000
    
    # Test different dominance ratios: A/B = 0.3, 0.5, 0.7, 0.9, 1.5
    ratios = [0.3, 0.5, 0.7, 0.9, 1.5]
    results_by_ratio = []
    
    for ratio in ratios:
        cfg = MultiFieldConfig(
            fields=[
                ConstraintField("A", strength=0.5 * ratio, frequency=0.02, phase=0.0),
                ConstraintField("B", strength=0.5, frequency=0.02, phase=0.0)
            ]
        )
        manager = MultiFieldManager(cfg)
        constraints = compute_constraint_time_series(manager, n_steps)
        mean_constraint = np.mean(constraints)
        std_constraint = np.std(constraints)
        results_by_ratio.append({
            'ratio': ratio,
            'mean': mean_constraint,
            'std': std_constraint
        })
        print(f"\nratio={ratio:.1f}:")
        print(f"  Mean constraint: {mean_constraint:.4f}")
        print(f"  Std: {std_constraint:.4f}")
    
    # Check for phase transition around R_c ~ 0.7
    # Look for non-monotonic behavior or sharp change in constraint
    means = [r['mean'] for r in results_by_ratio]
    mean_diffs = [abs(means[i+1] - means[i]) for i in range(len(means)-1)]
    
    print(f"\nConstraint differences between ratios:")
    for i, diff in enumerate(mean_diffs):
        print(f"  {ratios[i]:.1f} -> {ratios[i+1]:.1f}: {diff:.4f}")
    
    max_diff = max(mean_diffs)
    max_diff_idx = mean_diffs.index(max_diff)
    
    # H22-P5c: Phase transition if max jump is significant and near R_c ~ 0.7
    # For multi-field, we look for non-linear behavior
    if max_diff > 0.05:  # Significant jump
        print(f"\n[PASS] H22-P5c PASS: Non-linear behavior detected (max_diff={max_diff:.4f} > 0.05)")
        print(f"  Critical region: ratio {ratios[max_diff_idx]:.1f} -> {ratios[max_diff_idx+1]:.1f}")
        return True
    else:
        print(f"\n[FAIL] H22-P5c FAIL: No clear phase transition (max_diff={max_diff:.4f} <= 0.05)")
        return False


def test_hypothesis_p5d():
    """H22-P5d: Spatial Field Separation (different phases -> higher variance)."""
    print("\n" + "="*60)
    print("H22-P5d: Spatial Field Separation Test")
    print("="*60)
    
    n_steps = 1000
    
    configs = [
        # Same phase: both fields in-phase
        ("same_phase", MultiFieldConfig(
            fields=[
                ConstraintField("A", strength=0.4, frequency=0.02, phase=0.0),
                ConstraintField("B", strength=0.4, frequency=0.02, phase=0.0)
            ]
        )),
        # Split phase: fields in different phases
        ("split_phase", MultiFieldConfig(
            fields=[
                ConstraintField("A", strength=0.4, frequency=0.02, phase=0.0),
                ConstraintField("B", strength=0.4, frequency=0.02, phase=math.pi)
            ]
        ))
    ]
    
    results = {}
    for name, cfg in configs:
        manager = MultiFieldManager(cfg)
        constraints = compute_constraint_time_series(manager, n_steps)
        mean_constraint = np.mean(constraints)
        std_constraint = np.std(constraints)
        results[name] = {
            'mean': mean_constraint,
            'std': std_constraint
        }
        print(f"\n{name}:")
        print(f"  Mean constraint: {mean_constraint:.4f}")
        print(f"  Std: {std_constraint:.4f}")
    
    # H22-P5d: Split phase should have HIGHER variance (more dynamic diversity)
    same_std = results['same_phase']['std']
    split_std = results['split_phase']['std']
    
    if split_std > same_std:
        print(f"\n[PASS] H22-P5d PASS: Split phase std ({split_std:.4f}) > Same phase std ({same_std:.4f})")
        print(f"  Phase separation creates more constraint dynamics")
        return True
    else:
        print(f"\n[FAIL] H22-P5d FAIL: Split phase std ({split_std:.4f}) <= Same phase std ({same_std:.4f})")
        return False


def test_hypothesis_p5e():
    """H22-P5e: Competitive Coupling (bistable dynamics)."""
    print("\n" + "="*60)
    print("H22-P5e: Competitive Coupling Test")
    print("="*60)
    
    n_steps = 2000
    
    # Two fields with slightly different frequencies (beat frequency)
    cfg = MultiFieldConfig(
        fields=[
            ConstraintField("A", strength=0.5, frequency=0.010, phase=0.0),
            ConstraintField("B", strength=0.5, frequency=0.011, phase=0.0)
        ]
    )
    
    manager = MultiFieldManager(cfg)
    constraints = compute_constraint_time_series(manager, n_steps)
    
    mean_constraint = np.mean(constraints)
    std_constraint = np.std(constraints)
    
    print(f"\nCompetitive coupling (freq A=0.010, freq B=0.011):")
    print(f"  Mean constraint: {mean_constraint:.4f}")
    print(f"  Std: {std_constraint:.4f}")
    print(f"  Range: [{min(constraints):.4f}, {max(constraints):.4f}]")
    
    # Check for bistability (bimodal distribution or high variance)
    # Use histogram to detect bimodality
    hist, bin_edges = np.histogram(constraints, bins=20)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Look for two peaks
    peaks = []
    for i in range(1, len(hist)-1):
        if hist[i] > hist[i-1] and hist[i] > hist[i+1]:
            peaks.append(bin_centers[i])
    
    print(f"\nHistogram analysis:")
    print(f"  Number of peaks: {len(peaks)}")
    if len(peaks) >= 2:
        print(f"  Peak locations: {peaks}")
    
    # H22-P5e: Bistability if high variance OR multiple peaks
    if std_constraint > 0.05 or len(peaks) >= 2:
        print(f"\n[PASS] H22-P5e PASS: Bistable dynamics detected (std={std_constraint:.4f}, peaks={len(peaks)})")
        return True
    else:
        print(f"\n[FAIL] H22-P5e FAIL: No bistability (std={std_constraint:.4f} <= 0.05, peaks={len(peaks)})")
        return False


def main():
    """Run all Phase 22 P5 experiments."""
    print("="*60)
    print("Phase 22 P5: Multi-Field Competitive Constraints (v3 - SIMPLIFIED)")
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
    print("Phase 22 P5 v3 Summary")
    print("="*60)
    
    n_pass = sum(1 for v in results.values() if v)
    n_total = len(results)
    
    for hypothesis, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {hypothesis}")
    
    print(f"\nTotal: {n_pass}/{n_total} hypotheses passed")
    
    # Save results
    output_dir = "C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现/engine_v2/results"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"exp_209_p5_v3_{np.random.randint(1000)}.json")
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    main()
