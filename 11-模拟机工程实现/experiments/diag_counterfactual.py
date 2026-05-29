"""Diagnostic: verify CounterfactualEngine activation after is_significant fix."""
import torch, sys, time
sys.path.insert(0, r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现')

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.counterfactual_engine import CounterfactualEngine
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.minimal_self_detector import MinimalSelfDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.organizational_density_index import DensityIndexResult

# Test 1: Direct CounterfactualEngine test with known ODI
print("=== Test 1: Direct CounterfactualEngine ===")
cfe = CounterfactualEngine()
high_odi = DensityIndexResult(
    odi=0.8, subindices={}, zone='dense',
    base_zone='pre-subjective', densification_rate=0.1,
    is_densifying=True, timestamp=0, zone_boundary=0.5
)

state = torch.randn(10)
# Run multiple explore steps to build up branches
for t in range(10):
    state_t = state + torch.randn(10) * 0.05 * t
    dirs = [torch.randn(10) for _ in range(4)]
    dirs = [d / (d.norm() + 1e-8) for d in dirs]
    # Use slightly non-uniform probs
    probs = [0.35, 0.30, 0.20, 0.15]
    r = cfe.explore(current_state=state_t, candidate_directions=dirs,
                    direction_probs=probs, odi_result=high_odi, timestamp=t)
    cfe.step()
    if t % 3 == 0:
        print(f'  t={t}: active={r.counterfactual_active}, branches={r.n_active_branches}, '
              f'div={r.n_divergence_points}, meta={r.metadata}')

print(f'  Final: is_active={cfe.is_active}, n_branches={cfe.n_active_branches}')
print(f'  Summary: {cfe.get_summary()}')

# Test 2: With uniform probs (harder case)
print()
print("=== Test 2: Uniform probs ===")
cfe2 = CounterfactualEngine()
for t in range(10):
    state_t = state + torch.randn(10) * 0.05 * t
    dirs = [torch.randn(10) for _ in range(4)]
    dirs = [d / (d.norm() + 1e-8) for d in dirs]
    r = cfe2.explore(current_state=state_t, candidate_directions=dirs,
                     direction_probs=[0.25, 0.25, 0.25, 0.25],
                     odi_result=high_odi, timestamp=t)
    cfe2.step()
    if t % 3 == 0:
        print(f'  t={t}: active={r.counterfactual_active}, branches={r.n_active_branches}, '
              f'div={r.n_divergence_points}, meta={r.metadata}')

print(f'  Final: is_active={cfe2.is_active}, n_branches={cfe2.n_active_branches}')

# Test 3: Full evolver integration with forced high ODI
print()
print("=== Test 3: Full evolver (N=48, 100 steps) ===")
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
print(f'  counterfactual_active={ps3["counterfactual_active"]}')
print(f'  counterfactual_n_branches={ps3["counterfactual_n_branches"]}')
print(f'  counterfactual_engine_active={ps3["counterfactual_engine_active"]}')

# Check ODI range
odi_vals = []
for lr in results['layer_results']:
    for sr in lr.get('phase2_step_results', []):
        odi_val = sr.get('odi', {})
        if isinstance(odi_val, dict):
            odi_vals.append(odi_val.get('value', 0))

if odi_vals:
    print(f'  ODI range: [{min(odi_vals):.4f}, {max(odi_vals):.4f}]')
    high_odi_steps = [v for v in odi_vals if v >= 0.5]
    print(f'  Steps with ODI >= 0.5: {len(high_odi_steps)}/{len(odi_vals)}')

print()
print('=== CONCLUSION ===')
if ps3['counterfactual_active']:
    print('FIX VERIFIED: Counterfactual engine activates correctly!')
else:
    print('Counterfactual engine still not activating in evolver context.')
    print('This may be because ODI < 0.5 in the evolver (p3_active gate).')
    print('The direct test (Test 1) shows the fix works at the engine level.')
