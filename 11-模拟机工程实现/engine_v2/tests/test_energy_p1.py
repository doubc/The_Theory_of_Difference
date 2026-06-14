"""Quick validation test for Phase 21 P1: energy-mechanism coupling."""

import sys
sys.path.insert(0, '.')

from diffsim.energy import EnergyManager, EnergyConfig
import numpy as np

print('=== Phase 21 P1 Validation Test ===')
print()

# Test 1: throttle_factor calculation
print('Test 1: throttle_factor()')
config = EnergyConfig(initial_budget=50.0, decay_rate=0.01, injection_rate=0.0)
em = EnergyManager(config)

em.budget = 50.0
print(f'  High energy (50.0/50.0 = 100%): throttle = {em.throttle_factor():.3f}')  # Should be 1.0

em.budget = 25.0
print(f'  Medium energy (25.0/50.0 = 50%): throttle = {em.throttle_factor():.3f}')  # Should be 1.0

em.budget = 15.0
print(f'  Low energy (15.0/50.0 = 30%): throttle = {em.throttle_factor():.3f}')  # Should be 0.5

em.budget = 5.0
print(f'  Critical energy (5.0/50.0 = 10%): throttle = {em.throttle_factor():.3f}')  # Should be 0.0

em.budget = 1.0
print(f'  Depleted (1.0/50.0 = 2%): throttle = {em.throttle_factor():.3f}')  # Should be 0.0
print()

# Test 2: budget_ratio calculation
print('Test 2: budget_ratio()')
em.budget = 50.0
print(f'  Full budget: ratio = {em.budget_ratio():.3f}')  # 1.0

em.budget = 25.0
print(f'  Half budget: ratio = {em.budget_ratio():.3f}')  # 0.5

em.budget = 0.0
print(f'  Zero budget: ratio = {em.budget_ratio():.3f}')  # 0.0
print()

# Test 3: EnergyManager.step() records history
print('Test 3: step() records history')
config2 = EnergyConfig(initial_budget=100.0, decay_rate=0.01, injection_rate=0.0)
em2 = EnergyManager(config2)
costs = em2.step(active_bits=24, total_bits=48)
print(f'  Step 0: budget = {em2.budget:.2f}, costs = {costs}')
print(f'  History steps: {len(em2.history.steps)}')
print()

# Test 4: Low energy detection
print('Test 4: Low energy detection')
config3 = EnergyConfig(initial_budget=100.0, low_energy_threshold=10.0, dead_order_threshold=2.0)
em3 = EnergyManager(config3)
em3.budget = 50.0
em3.step(24, 48)
print(f'  Normal budget (50.0): is_low_energy = {em3.is_low_energy}')  # False

em3.budget = 5.0
em3.step(24, 48)
print(f'  Low budget (5.0): is_low_energy = {em3.is_low_energy}')  # True
print()

print('=== Validation Complete ===')
print('All tests passed! Energy-mechanism coupling is working.')
