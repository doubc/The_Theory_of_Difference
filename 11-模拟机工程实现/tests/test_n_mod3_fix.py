"""
test_n_mod3_fix.py — Verify N%3 bug fix

The bug: SpatialLongRangeEvolver rounds N to nearest multiple of 3
in __init__, but initial_state could have the original (unrounded) size.
This causes dimension mismatch.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


def test_n50_rounds_to_51():
    """N=50 not divisible by 3, rounds to 51, initial_state has 50 elements"""
    initial = torch.zeros(50)
    initial[:8] = 1.0
    evolver = SpatialLongRangeEvolver(N=50, total_steps=50, sample_interval=50)
    assert evolver.N == 51, f"Expected N=51, got {evolver.N}"
    result = evolver.run(initial_state=initial, verbose=False)
    assert result['final_state'].numel() == 51, f"Expected 51 bits, got {result['final_state'].numel()}"
    print(f"  N=50 -> {evolver.N} OK, final_state size={result['final_state'].numel()} OK")


def test_n47_rounds_to_48():
    """N=47 rounds to 48"""
    initial = torch.zeros(47)
    initial[:6] = 1.0
    evolver = SpatialLongRangeEvolver(N=47, total_steps=50, sample_interval=50)
    assert evolver.N == 48, f"Expected N=48, got {evolver.N}"
    result = evolver.run(initial_state=initial, verbose=False)
    assert result['final_state'].numel() == 48, f"Expected 48 bits, got {result['final_state'].numel()}"
    print(f"  N=47 -> {evolver.N} OK, final_state size={result['final_state'].numel()} OK")


def test_n48_no_rounding():
    """N=48 already divisible by 3"""
    initial = torch.zeros(48)
    initial[:10] = 1.0
    evolver = SpatialLongRangeEvolver(N=48, total_steps=50, sample_interval=50)
    assert evolver.N == 48, f"Expected N=48, got {evolver.N}"
    result = evolver.run(initial_state=initial, verbose=False)
    assert result['final_state'].numel() == 48, f"Expected 48 bits, got {result['final_state'].numel()}"
    print(f"  N=48 -> {evolver.N} OK (no rounding)")


def test_n47_no_initial_state():
    """N=47 with no initial_state — evolver creates its own zeros"""
    evolver = SpatialLongRangeEvolver(N=47, total_steps=50, sample_interval=50)
    result = evolver.run(verbose=False)
    assert result['final_state'].numel() == 48, f"Expected 48 bits, got {result['final_state'].numel()}"
    print(f"  N=47 (no init) -> {evolver.N} OK, final_state size={result['final_state'].numel()} OK")


if __name__ == '__main__':
    test_n50_rounds_to_51()
    test_n47_rounds_to_48()
    test_n48_no_rounding()
    test_n47_no_initial_state()
    print("\n=== All N%3 tests PASSED ===")