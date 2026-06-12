#!/usr/bin/env python3
"""Phase 21 P1 Validation Experiment: Throttle Mechanism Effect

Objective: Verify that throttle factor actually modulates mechanism behavior.

Hypothesis:
- H21-P1a: Low throttle (0.0) → slower sealing (more steps)
- H21-P1b: High throttle (1.0) → normal sealing speed
- H21-P1c: Throttle affects flux (Jaccard flux should be lower with low throttle)

Method:
1. Create Layer with energy system
2. Set different budget levels (affecting throttle)
3. Measure: seal_step, flux, n_organizations
4. Compare across throttle levels

Expected results:
- budget=100 (throttle=1.0): fast sealing, normal flux
- budget=30 (throttle=0.5): slower sealing, reduced flux
- budget=10 (throttle=0.0): very slow/non-sealing, minimal flux
"""

import sys
import os

# Add parent directory to path (where diffsim package is located)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
sys.path.insert(0, _project_root)

from diffsim.world import Layer, Params
from diffsim.core import DifferenceField
from diffsim.energy import EnergyManager, EnergyConfig
import numpy as np
import json


def run_single_layer(budget, seed=42):
    """Run a single layer with specified energy budget."""
    p = Params(max_steps=500)
    f = DifferenceField(
        N=20,
        active=list(range(20)),
        layer=0,
        rng=np.random.default_rng(seed)
    )
    layer = Layer(f, p)
    
    # Add energy system
    energy_cfg = EnergyConfig(
        initial_budget=budget,
        decay_rate=0.0,  # No decay for this test
        injection_rate=0.0   # No injection for this test
    )
    layer.energy = EnergyManager(energy_cfg)
    
    # Run until seal or max_steps
    sealed = layer.run_until_seal(verbose=False)
    
    # Collect metrics
    result = {
        'budget': budget,
        'throttle': layer.energy.throttle_factor(),
        'sealed': sealed,
        'seal_step': f.seal_step if sealed else None,
        'flux': layer.autonomous_flux(),
        'n_orgs': len(f.organizations),
        'final_budget': layer.energy.budget,
    }
    
    return result


def main():
    print("\n" + "=" * 60)
    print("Phase 21 P1 Validation: Throttle Mechanism Effect")
    print("=" * 60 + "\n")
    
    # Test configurations
    budgets = [100.0, 50.0, 30.0, 10.0]
    seeds = [42, 123, 456]
    
    all_results = []
    
    for budget in budgets:
        print(f"\n--- Budget = {budget} (expected throttle = {budget/100:.2f}) ---")
        
        for seed in seeds:
            result = run_single_layer(budget, seed)
            all_results.append(result)
            
            print(f"  Seed {seed}: "
                  f"sealed={result['sealed']}, "
                  f"step={result['seal_step']}, "
                  f"throttle={result['throttle']:.3f}, "
                  f"flux={result['flux']:.4f}, "
                  f"orgs={result['n_orgs']}")
    
    # Analysis
    print("\n" + "=" * 60)
    print("Analysis")
    print("=" * 60)
    
    # Group by budget
    for budget in budgets:
        budget_results = [r for r in all_results if r['budget'] == budget]
        
        n_sealed = sum(1 for r in budget_results if r['sealed'])
        avg_step = np.mean([r['seal_step'] for r in budget_results if r['seal_step']])
        avg_flux = np.mean([r['flux'] for r in budget_results])
        avg_orgs = np.mean([r['n_orgs'] for r in budget_results])
        
        print(f"\nBudget = {budget}:")
        print(f"  Seal rate: {n_sealed}/{len(budget_results)}")
        print(f"  Avg seal step: {avg_step:.1f}")
        print(f"  Avg flux: {avg_flux:.4f}")
        print(f"  Avg organizations: {avg_orgs:.1f}")
    
    # Validate hypotheses
    print("\n" + "=" * 60)
    print("Hypothesis Validation")
    print("=" * 60)
    
    # H21-P1a: Low throttle → slower sealing
    high_budget = [r for r in all_results if r['budget'] == 100.0 and r['sealed']]
    low_budget = [r for r in all_results if r['budget'] == 10.0 and r['sealed']]
    
    if high_budget and low_budget:
        avg_step_high = np.mean([r['seal_step'] for r in high_budget])
        avg_step_low = np.mean([r['seal_step'] for r in low_budget])
        
        print(f"\nH21-P1a: Low throttle → slower sealing")
        print(f"  High budget (100.0): avg step = {avg_step_high:.1f}")
        print(f"  Low budget (10.0): avg step = {avg_step_low:.1f}")
        
        if avg_step_low > avg_step_high:
            print(f"  [PASS] Low throttle is slower")
        else:
            print(f"  [FAIL] Expected low throttle to be slower")
    else:
        print(f"\nH21-P1a: Cannot validate (insufficient sealed layers)")
    
    # H21-P1c: Throttle affects flux
    high_flux = [r['flux'] for r in all_results if r['budget'] == 100.0]
    low_flux = [r['flux'] for r in all_results if r['budget'] == 10.0]
    
    avg_flux_high = np.mean(high_flux) if high_flux else 0.0
    avg_flux_low = np.mean(low_flux) if low_flux else 0.0
    
    print(f"\nH21-P1c: Throttle affects flux")
    print(f"  High budget (100.0): avg flux = {avg_flux_high:.4f}")
    print(f"  Low budget (10.0): avg flux = {avg_flux_low:.4f}")
    
    if avg_flux_high > avg_flux_low:
        print(f"  [PASS] High throttle → higher flux")
    else:
        print(f"  [FAIL] Expected high throttle → higher flux")
    
    # Save results
    output_file = "results/phase21_p1_validation.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
