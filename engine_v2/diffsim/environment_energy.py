"""
Phase 22: Open Systems with Energy Flow
=======================================

Implement EnvironmentEnergyField and EntropyExhaust classes.

Core idea: Open energy injection can sustain "infinite" emergence depth
by continuously supplying energy to counter entropy production.

Classes:
- EnvironmentEnergyField: Manages open energy injection from environment
- EntropyExhaust: Manages entropy dissipation to environment
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import numpy as np


@dataclass
class EnvironmentConfig:
    """Configuration for open energy system."""
    
    # Energy injection parameters
    injection_rate: float = 1.0  # Energy injected per step (budget units)
    injection_pattern: str = "constant"  # "constant", "decay", "burst", "adaptive"
    adaptive_threshold: float = 0.3  # Energy ratio threshold for adaptive injection
    
    # Entropy dissipation parameters
    enable_entropy_exhaust: bool = True
    exhaust_rate: float = 0.1  # Fraction of entropy dissipated per step
    
    # System boundaries
    max_energy: float = 200.0  # Maximum energy budget (safety limit)
    min_energy: float = 1.0  # Minimum energy to continue (dead order threshold)
    
    # Layer-specific parameters
    per_layer_injection: bool = True  # Independent energy budget per layer
    cross_layer_coupling: float = 0.1  # Energy transfer between layers


class EnvironmentEnergyField:
    """
    Manages open energy injection from environment.
    
    In closed systems (Phase 21), energy decays → emergence depth limited.
    In open systems (Phase 22), energy can be replenished → sustained emergence.
    """
    
    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.current_energy: float = config.max_energy / 2.0  # Start at 50%
        self.total_injected: float = 0.0
        self.total_consumed: float = 0.0
        self.injection_history: List[float] = []
        self.energy_history: List[float] = []
        
    def inject_energy(self, step: int, system_state: Optional[Dict] = None) -> float:
        """
        Inject energy from environment based on pattern.
        
        Args:
            step: Current simulation step
            system_state: Optional system state for adaptive injection
            
        Returns:
            injected_amount: Energy injected this step
        """
        if self.config.injection_pattern == "constant":
            injected = self.config.injection_rate
            
        elif self.config.injection_pattern == "decay":
            # Exponential decay of injection rate
            decay_factor = 0.999
            injected = self.config.injection_rate * (decay_factor ** step)
            
        elif self.config.injection_pattern == "burst":
            # Periodic burst injection
            burst_interval = 100
            if step % burst_interval == 0:
                injected = self.config.injection_rate * 5.0
            else:
                injected = self.config.injection_rate * 0.2
                
        elif self.config.injection_pattern == "adaptive":
            # Adaptive injection based on system energy ratio
            energy_ratio = self.current_energy / self.config.max_energy
            if energy_ratio < self.config.adaptive_threshold:
                injected = self.config.injection_rate * 2.0  # High injection
            else:
                injected = self.config.injection_rate * 0.5  # Low injection
                
        else:
            injected = self.config.injection_rate  # Default to constant
            
        # Apply safety limit
        injected = min(injected, self.config.max_energy - self.current_energy)
        injected = max(injected, 0.0)  # No negative injection
        
        self.current_energy += injected
        self.total_injected += injected
        self.injection_history.append(injected)
        self.energy_history.append(self.current_energy)
        
        return injected
    
    def consume_energy(self, amount: float) -> float:
        """
        Consume energy for mechanism execution.
        
        Args:
            amount: Requested energy amount
            
        Returns:
            actual_consumed: Actually consumed energy (may be less if insufficient)
        """
        actual_consumed = min(amount, self.current_energy)
        actual_consumed = max(actual_consumed, 0.0)
        
        self.current_energy -= actual_consumed
        self.total_consumed += actual_consumed
        
        return actual_consumed
    
    def get_energy_ratio(self) -> float:
        """Get current energy as fraction of max."""
        return self.current_energy / self.config.max_energy
    
    def is_depleted(self) -> bool:
        """Check if energy is below minimum threshold."""
        return self.current_energy < self.config.min_energy
    
    def get_statistics(self) -> Dict[str, float]:
        """Get energy field statistics."""
        return {
            "current_energy": self.current_energy,
            "total_injected": self.total_injected,
            "total_consumed": self.total_consumed,
            "energy_ratio": self.get_energy_ratio(),
            "n_steps": len(self.injection_history)
        }


class EntropyExhaust:
    """
    Manages entropy dissipation to environment.
    
    In closed systems, entropy accumulates → system approaches heat death.
    In open systems, entropy can be dissipated → sustained far-from-equilibrium.
    """
    
    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.total_exhausted: float = 0.0
        self.exhaust_history: List[float] = []
        
    def dissipate_entropy(self, current_entropy: float, step: int) -> float:
        """
        Dissipate entropy to environment.
        
        Args:
            current_entropy: Current system entropy
            step: Current simulation step
            
        Returns:
            dissipated: Amount of entropy dissipated
        """
        if not self.config.enable_entropy_exhaust:
            return 0.0
        
        # Dissipate fraction of current entropy
        dissipated = current_entropy * self.config.exhaust_rate
        
        # Ensure non-negative
        dissipated = max(dissipated, 0.0)
        
        self.total_exhausted += dissipated
        self.exhaust_history.append(dissipated)
        
        return dissipated
    
    def get_statistics(self) -> Dict[str, float]:
        """Get entropy exhaust statistics."""
        return {
            "total_exhausted": self.total_exhausted,
            "n_steps": len(self.exhaust_history),
            "avg_exhaust_rate": np.mean(self.exhaust_history) if self.exhaust_history else 0.0
        }


def test_environment_energy_field():
    """Test EnvironmentEnergyField functionality."""
    print("=== Testing EnvironmentEnergyField ===")
    
    config = EnvironmentConfig(
        injection_rate=2.0,
        injection_pattern="constant",
        max_energy=100.0
    )
    field = EnvironmentEnergyField(config)
    
    # Test 1: Constant injection
    print("\nTest 1: Constant injection")
    for step in range(10):
        injected = field.inject_energy(step)
        print(f"  Step {step}: injected={injected:.2f}, energy={field.current_energy:.2f}")
    
    assert field.current_energy == 70.0, f"Expected 70.0, got {field.current_energy}"
    print("  [PASS] Constant injection works correctly")
    
    # Test 2: Energy consumption
    print("\nTest 2: Energy consumption")
    consumed = field.consume_energy(5.0)
    assert consumed == 5.0, f"Expected 5.0, got {consumed}"
    assert field.current_energy == 65.0, f"Expected 65.0, got {field.current_energy}"
    print("  [PASS] Energy consumption works correctly")
    
    # Test 3: Adaptive injection
    print("\nTest 3: Adaptive injection")
    config_adaptive = EnvironmentConfig(
        injection_rate=1.0,
        injection_pattern="adaptive",
        adaptive_threshold=0.5,
        max_energy=100.0
    )
    field_adaptive = EnvironmentEnergyField(config_adaptive)
    field_adaptive.current_energy = 20.0  # 20% of max → below threshold
    
    injected = field_adaptive.inject_energy(0)
    assert injected == 2.0, f"Expected 2.0 (high injection), got {injected}"
    print("  [PASS] Adaptive injection works correctly")
    
    print("\n=== All tests passed! ===")
    return True


def test_entropy_exhaust():
    """Test EntropyExhaust functionality."""
    print("\n=== Testing EntropyExhaust ===")
    
    config = EnvironmentConfig(enable_entropy_exhaust=True, exhaust_rate=0.2)
    exhaust = EntropyExhaust(config)
    
    # Test 1: Basic dissipation
    print("\nTest 1: Basic dissipation")
    dissipated = exhaust.dissipate_entropy(current_entropy=10.0, step=0)
    assert dissipated == 2.0, f"Expected 2.0, got {dissipated}"
    print(f"  Dissipated: {dissipated:.2f}")
    print("  [PASS] Basic dissipation works correctly")
    
    # Test 2: Disabled exhaust
    print("\nTest 2: Disabled exhaust")
    config_disabled = EnvironmentConfig(enable_entropy_exhaust=False)
    exhaust_disabled = EntropyExhaust(config_disabled)
    dissipated = exhaust_disabled.dissipate_entropy(current_entropy=10.0, step=0)
    assert dissipated == 0.0, f"Expected 0.0, got {dissipated}"
    print("  [PASS] Disabled exhaust works correctly")
    
    print("\n=== All tests passed! ===")
    return True


if __name__ == "__main__":
    test_environment_energy_field()
    test_entropy_exhaust()
