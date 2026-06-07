"""
Smoke test for TemporalTrace — validates framework correctness
"""
import sys
sys.path.insert(0, r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现')

from observations.temporal_trace import TemporalTrace
import torch
import numpy as np

print("=" * 60)
print("TemporalTrace Smoke Test")
print("=" * 60)

# Test 1: Framework correctness — N=48 with 28 initial ones (dense seed)
# This should seal consistently
print("\n--- Test 1: N=48, dense seed ---")
trace = TemporalTrace(N=48, sample_interval=1, total_steps=800, verbose=False)
initial = torch.zeros(48)
# Seed 28 ones (0..27) — enough density to cross threshold
initial[:28] = 1.0

result = trace.run(initial_state=initial, verbose=False)

print("History len: %d" % len(trace.history))
print("Sealed: %s, step %d" % (trace.sealed, trace.seal_step))
print("Sealed bits: %d" % len(trace._seal_step_per_bit))

# Test 2: Analysis methods work regardless of seal status
print("\n--- Test 2: Analysis API ---")
summary = trace.get_summary()
print("Summary: %s" % summary)

seal_order = trace.get_seal_order()
print("Seal order: %d bits" % len(seal_order))

cascade = trace.get_cascade_series()
print("Cascade series (sample): %s" % cascade[:5])
print("Max cascade: %d" % (max(cascade) if cascade else 0))

seal_rate = trace.get_seal_rate_series()
print("Seal rate series (first 5): %s" % seal_rate[:5])

convergence = trace.get_convergence_trace()
print("Weight range: %.0f - %.0f" % (convergence.min(), convergence.max()))

flip_freq = trace.get_flip_frequency(window=30)
print("Flip freq (mean, max): %.2f, %.0f" % (flip_freq.mean(), flip_freq.max()))

pre_seal = trace.get_pre_seal_activity(lookback=20)
if pre_seal['pre_seal_weight'].size > 0:
    print("Pre-seal activity shape: %s" % str(pre_seal['pre_seal_weight'].shape))
else:
    print("Pre-seal: no data (expected if not sealed)")

# Test 3: Multi-run via SingleTrace
print("\n--- Test 3: SingleTrace batch ---")
from observations.temporal_trace import SingleTrace
st = SingleTrace(N=48, sample_interval=1, total_steps=500, verbose=False)
summaries = st.run_batch(n_runs=3, verbose=False)
sealed_count = sum(1 for s in summaries if s.get('seal_step', -1) >= 0)
print("Batch runs: %d, sealed: %d/3" % (len(summaries), sealed_count))
if sealed_count > 0:
    seal_steps = [s['seal_step'] for s in summaries if s['seal_step'] >= 0]
    print("Seal steps: %s" % seal_steps)

# Test 4: run without initial state (all zeros)
print("\n--- Test 4: No initial state ---")
trace2 = TemporalTrace(N=48, sample_interval=1, total_steps=200, verbose=False)
result2 = trace2.run(verbose=False)
print("History len: %d" % len(trace2.history))
print("Sealed: %s" % trace2.sealed)

# Verify core functionality always works
assert len(trace.history) > 0, "No history recorded"
assert isinstance(trace.get_summary(), dict), "get_summary() not returning dict"
assert isinstance(trace.get_seal_order(), list), "get_seal_order() not returning list"
assert isinstance(trace.get_cascade_series(), list), "get_cascade_series() not returning list"
assert isinstance(trace.get_seal_rate_series(), np.ndarray), "get_seal_rate_series() not ndarray"
assert isinstance(trace.get_convergence_trace(), np.ndarray), "get_convergence_trace() not ndarray"

print("\n=== ALL TESTS PASSED ===")