"""Final diagnostic: verify CounterfactualEngine activation after fix."""
import torch, sys, time, json
from datetime import datetime
sys.path.insert(0, r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现')

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.counterfactual_engine import CounterfactualEngine
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.minimal_self_detector import MinimalSelfDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.organizational_density_index import OrganizationalDensityIndex, DensityIndexResult
from engine.counterfactual_engine import DivergencePointTracker

print("=" * 60)
print("Counterfactual Engine Fix Verification")
print(f"Timestamp: {datetime.now().isoformat()}")
print("=" * 60)

# Test 1: Divergence detection with various distributions
print("\n--- Test 1: Divergence Detection ---")
tracker = DivergencePointTracker()
state = torch.randn(10)

cases = [
    ("Uniform 4-dir", [0.25, 0.25, 0.25, 0.25], True),
    ("Slight skew", [0.35, 0.30, 0.20, 0.15], True),
    ("Dominant", [0.95, 0.03, 0.02], False),
]

all_pass = True
for name, probs, expected_sig in cases:
    t = DivergencePointTracker()
    dirs = [torch.randn(10) for _ in range(len(probs))]
    div = t.detect_divergence(current_state=state, candidate_directions=dirs, direction_probs=probs)
    if div is not None:
        actual_sig = div.is_significant
        status = "PASS" if actual_sig == expected_sig else "FAIL"
        print(f"  {status} {name}: entropy={div.entropy:.4f}, ratio={div.significance:.4f}, "
              f"is_significant={actual_sig} (expected {expected_sig})")
    else:
        status = "PASS" if not expected_sig else "FAIL"
        print(f"  {status} {name}: NOT DETECTED (expected significant={expected_sig})")
    if status == "FAIL":
        all_pass = False

# Test 2: CounterfactualEngine activation
print("\n--- Test 2: CounterfactualEngine Activation ---")
cfe = CounterfactualEngine()
high_odi = DensityIndexResult(
    odi=0.8, subindices={}, zone='dense',
    base_zone='pre-subjective', densification_rate=0.1,
    is_densifying=True, timestamp=0, zone_boundary=0.5
)

for t in range(10):
    state_t = state + torch.randn(10) * 0.05 * t
    dirs = [torch.randn(10) for _ in range(4)]
    dirs = [d / (d.norm() + 1e-8) for d in dirs]
    r = cfe.explore(current_state=state_t, candidate_directions=dirs,
                    direction_probs=None, odi_result=high_odi, timestamp=t)
    cfe.step()

print(f"  ODI=0.8, 10 steps: active={cfe.is_active}, branches={cfe.n_active_branches}, "
      f"div_points={cfe.divergence_tracker.n_divergence_points}")
test2_pass = cfe.is_active
print(f"  {'PASS' if test2_pass else 'FAIL'}: Counterfactual engine activation")

# Test 3: Full evolver integration
print("\n--- Test 3: Full Evolver Integration ---")
pbm = PersistentBiasMemory()
odi = OrganizationalDensityIndex()
msd = MinimalSelfDetector()
abe = AnticipatoryBiasEngine(memory=pbm)
cfe3 = CounterfactualEngine()

evolver = HierarchicalEvolver(
    N0=48, steps_per_layer=100, max_layers=1, p1_eval_interval=5,
    device='cpu',
    persistent_bias_memory=pbm,
    organizational_density_index=odi,
    minimal_self_detector=msd,
    anticipatory_bias_engine=abe,
    counterfactual_engine=cfe3,
)

results = evolver.run(verbose=False)
ps3 = results['phase3_summary']

print(f"  counterfactual_engine_active: {ps3['counterfactual_engine_active']}")
print(f"  counterfactual_active: {ps3['counterfactual_active']}")
print(f"  counterfactual_n_branches: {ps3['counterfactual_n_branches']}")

# Check ODI
odi_vals = []
for lr in results['layer_results']:
    for sr in lr.get('phase2_step_results', []):
        odi_val = sr.get('odi', {})
        if isinstance(odi_val, dict) and odi_val.get('value', 0) > 0:
            odi_vals.append(odi_val['value'])

if odi_vals:
    print(f"  ODI range (non-zero): [{min(odi_vals):.4f}, {max(odi_vals):.4f}]")
else:
    print(f"  ODI: all zeros (p3_active never triggered)")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Test 1 (Divergence detection): {'PASS' if all_pass else 'FAIL'}")
print(f"  Test 2 (Engine activation):    {'PASS' if test2_pass else 'FAIL'}")
print(f"  Test 3 (Evolver integration):  counterfactual_engine_active={ps3['counterfactual_engine_active']}")
print()
if all_pass and test2_pass:
    print("ALL TESTS PASSED - Fix verified!")
else:
    print("SOME TESTS FAILED")
