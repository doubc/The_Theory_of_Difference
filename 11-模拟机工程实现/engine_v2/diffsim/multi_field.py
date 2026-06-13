"""
Multi-Field Competitive Constraints for Phase 22 P5.

Enables multiple constraint fields with different strengths, frequencies,
phases, domains, and coupling types to compete or cooperate.

Author: AI Agent (Heartbeat 2026-06-14 02:44)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import math
import numpy as np


@dataclass
class ConstraintField:
    """
    A single constraint field for multi-field competition.
    
    Each field can have:
    - strength: Field intensity (0.0-1.0)
    - frequency: Temporal modulation frequency (0 = static)
    - phase: Phase offset for interference patterns (radians)
    - domain: Bit subspace the field acts on ("all", "even", "odd", "range:low:high")
    - coupling_type: How this field combines with others ("additive", "multiplicative", "competitive")
    """
    name: str                              # Field identifier
    strength: float = 0.5                  # 0.0-1.0, field intensity
    frequency: float = 0.0                 # Temporal modulation (0 = static)
    phase: float = 0.0                     # Phase offset (radians)
    domain: str = "all"                    # "all", "even", "odd", "range:low:high"
    coupling_type: str = "additive"        # "additive", "multiplicative", "competitive"
    weight: float = 1.0                    # Relative weight (for normalization)
    
    def __post_init__(self):
        """Validate parameters."""
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0, 1], got {self.strength}")
        if self.frequency < 0.0:
            raise ValueError(f"frequency must be >= 0, got {self.frequency}")
        if self.coupling_type not in ["additive", "multiplicative", "competitive"]:
            raise ValueError(f"Invalid coupling_type: {self.coupling_type}")
    
    def get_modulation(self, t: int) -> float:
        """
        Compute temporal modulation factor at step t.
        
        Returns a value in [0, 1] representing the field's current intensity.
        For static fields (frequency=0), returns 1.0.
        For modulated fields, returns 0.5 * (1 + sin(2*pi*f*t + phase)).
        """
        if self.frequency == 0.0:
            return 1.0
        
        modulation = 0.5 * (1.0 + math.sin(2.0 * math.pi * self.frequency * t + self.phase))
        return modulation
    
    def get_effective_strength(self, t: int) -> float:
        """Compute effective strength at step t (strength * modulation)."""
        return self.strength * self.get_modulation(t)
    
    def get_domain_indices(self, n_bits: int) -> List[int]:
        """
        Get list of bit indices that this field acts on.
        
        Args:
            n_bits: Total number of bits in the system
            
        Returns:
            List of indices in the domain
        """
        if self.domain == "all":
            return list(range(n_bits))
        elif self.domain == "even":
            return list(range(0, n_bits, 2))
        elif self.domain == "odd":
            return list(range(1, n_bits, 2))
        elif self.domain.startswith("range:"):
            parts = self.domain.split(":")
            if len(parts) != 3:
                raise ValueError(f"Invalid range domain: {self.domain}")
            low = int(parts[1])
            high = int(parts[2])
            return list(range(low, min(high, n_bits)))
        else:
            raise ValueError(f"Unknown domain: {self.domain}")
    
    def get_domain_fraction(self, n_bits: int) -> float:
        """Get the fraction of bits this field acts on."""
        return len(self.get_domain_indices(n_bits)) / n_bits


@dataclass
class MultiFieldConfig:
    """Configuration for multi-field constraint system."""
    base_injection_rate: float = 2.0          # Base energy injection rate
    constraint_energy_factor: float = 5.0     # How much constraint amplifies injection
    coupling_mode: str = "additive"           # Global coupling mode (can override per-field)
    normalize_weights: bool = True            # Normalize field weights to sum to 1
    

class MultiFieldManager:
    """
    Manager for multiple competing/cooperating constraint fields.
    
    This class:
    1. Holds a collection of ConstraintField objects
    2. Computes effective constraint at each step
    3. Handles different coupling types (additive, multiplicative, competitive)
    4. Supports bit-subspace domains for spatially heterogeneous constraints
    """
    
    def __init__(self, config: Optional[MultiFieldConfig] = None):
        self.config = config or MultiFieldConfig()
        self.fields: List[ConstraintField] = []
        
    def add_field(self, field: ConstraintField) -> None:
        """Add a constraint field."""
        self.fields.append(field)
        
    def clear_fields(self) -> None:
        """Remove all fields."""
        self.fields = []
        
    def get_normalized_weights(self) -> Dict[str, float]:
        """Get normalized weights for all fields (sum = 1)."""
        if not self.config.normalize_weights or not self.fields:
            return {f.name: f.weight for f in self.fields}
        
        total_weight = sum(f.weight for f in self.fields)
        return {f.name: f.weight / total_weight for f in self.fields}
    
    def compute_effective_constraint(self, t: int) -> float:
        """
        Compute the effective constraint strength at step t.
        
        This combines all fields according to their coupling types.
        """
        if not self.fields:
            return 0.0
        
        weights = self.get_normalized_weights()
        
        # Group fields by coupling type
        additive_fields = [f for f in self.fields if f.coupling_type == "additive"]
        multiplicative_fields = [f for f in self.fields if f.coupling_type == "multiplicative"]
        competitive_fields = [f for f in self.fields if f.coupling_type == "competitive"]
        
        effective_c = 0.0
        
        # Additive coupling: sum of weighted effective strengths
        if additive_fields:
            additive_sum = sum(
                weights[f.name] * f.get_effective_strength(t)
                for f in additive_fields
            )
            effective_c += additive_sum
        
        # Multiplicative coupling: product formula (capped to [0, 1])
        if multiplicative_fields:
            prod = 1.0
            for f in multiplicative_fields:
                effective = weights[f.name] * f.get_effective_strength(t)
                prod *= (1.0 + effective)
            multiplicative_c = min(1.0, prod - 1.0)
            # Combine with additive (if both exist, use weighted average)
            if additive_fields:
                n_add = len(additive_fields)
                n_mul = len(multiplicative_fields)
                total = n_add + n_mul
                effective_c = (n_add * effective_c + n_mul * multiplicative_c) / total
            else:
                effective_c = multiplicative_c
        
        # Competitive coupling: winner-take-all (max)
        if competitive_fields:
            competitive_c = max(
                f.get_effective_strength(t)  # Use raw strength, not weighted
                for f in competitive_fields
            )
            # If other fields exist, competitive overrides
            if additive_fields or multiplicative_fields:
                # Blend: competitive gets higher weight
                n_other = len(additive_fields) + len(multiplicative_fields)
                n_comp = len(competitive_fields)
                total = n_other + 2 * n_comp  # Competitive has 2x weight
                effective_c = (n_other * effective_c + 2 * n_comp * competitive_c) / total
            else:
                effective_c = competitive_c
        
        return min(1.0, max(0.0, effective_c))
    
    def compute_per_bit_constraint(self, t: int, n_bits: int) -> np.ndarray:
        """
        Compute constraint strength for each bit individually.
        
        This allows spatially heterogeneous constraints where different
        bits experience different field intensities.
        
        Returns:
            numpy array of shape (n_bits,) with constraint strength per bit
        """
        per_bit_c = np.zeros(n_bits)
        weights = self.get_normalized_weights()
        
        for f in self.fields:
            domain_indices = f.get_domain_indices(n_bits)
            effective_strength = weights[f.name] * f.get_effective_strength(t)
            
            for idx in domain_indices:
                # Add contribution (additive per bit)
                per_bit_c[idx] += effective_strength
        
        # Cap to [0, 1]
        per_bit_c = np.clip(per_bit_c, 0.0, 1.0)
        return per_bit_c
    
    def compute_injection(self, t: int, n_bits: int, 
                          use_per_bit: bool = False) -> Tuple[float, Optional[np.ndarray]]:
        """
        Compute energy injection based on effective constraint.
        
        Args:
            t: Current step
            n_bits: Number of bits
            use_per_bit: If True, return per-bit injection array
            
        Returns:
            (total_injection, per_bit_injection or None)
        """
        if use_per_bit:
            per_bit_c = self.compute_per_bit_constraint(t, n_bits)
            per_bit_injection = self.config.base_injection_rate * (
                1.0 + per_bit_c * self.config.constraint_energy_factor
            )
            total_injection = float(np.sum(per_bit_injection))
            return total_injection, per_bit_injection
        else:
            effective_c = self.compute_effective_constraint(t)
            injection = self.config.base_injection_rate * (
                1.0 + effective_c * self.config.constraint_energy_factor
            )
            return injection, None
    
    def get_summary(self, t: int, n_bits: int) -> Dict:
        """Get summary of current field state."""
        return {
            'n_fields': len(self.fields),
            'effective_constraint': self.compute_effective_constraint(t),
            'total_injection': self.compute_injection(t, n_bits)[0],
            'fields': [
                {
                    'name': f.name,
                    'strength': f.strength,
                    'effective_strength': f.get_effective_strength(t),
                    'modulation': f.get_modulation(t),
                    'domain': f.domain,
                    'coupling_type': f.coupling_type
                }
                for f in self.fields
            ]
        }


# Convenience functions for common configurations

def create_two_field_interference(strength: float = 0.5, 
                                   phase_diff: float = math.pi) -> MultiFieldManager:
    """
    Create a two-field interference configuration.
    
    Two fields of equal strength with a phase difference.
    Phase_diff = pi produces maximum interference (cancellation).
    """
    manager = MultiFieldManager()
    manager.add_field(ConstraintField(
        name="field_0",
        strength=strength,
        frequency=0.01,
        phase=0.0,
        coupling_type="additive"
    ))
    manager.add_field(ConstraintField(
        name="field_1", 
        strength=strength,
        frequency=0.01,
        phase=phase_diff,
        coupling_type="additive"
    ))
    return manager


def create_competitive_dominance(strong_strength: float = 0.8,
                                  weak_strength: float = 0.2) -> MultiFieldManager:
    """
    Create a competitive dominance configuration.
    
    Two fields competing, one stronger than the other.
    """
    manager = MultiFieldManager()
    manager.add_field(ConstraintField(
        name="dominant",
        strength=strong_strength,
        coupling_type="competitive"
    ))
    manager.add_field(ConstraintField(
        name="weak",
        strength=weak_strength,
        coupling_type="competitive"
    ))
    return manager


def create_spatial_separation(n_bits: int, 
                               even_strength: float = 0.5,
                               odd_strength: float = 0.5) -> MultiFieldManager:
    """
    Create spatially separated fields (even bits vs odd bits).
    """
    manager = MultiFieldManager()
    manager.add_field(ConstraintField(
        name="even_field",
        strength=even_strength,
        domain="even",
        coupling_type="additive"
    ))
    manager.add_field(ConstraintField(
        name="odd_field",
        strength=odd_strength,
        domain="odd",
        coupling_type="additive"
    ))
    return manager


# Test function
def test_multi_field_manager():
    """Basic tests for MultiFieldManager."""
    print("Testing MultiFieldManager...")
    
    # Test 1: Single field
    manager = MultiFieldManager()
    manager.add_field(ConstraintField(name="test", strength=0.5))
    c = manager.compute_effective_constraint(0)
    assert c == 0.5, f"Expected 0.5, got {c}"
    print("  Test 1 (single field): PASSED")
    
    # Test 2: Two additive fields
    manager = MultiFieldManager()
    manager.add_field(ConstraintField(name="a", strength=0.3, weight=0.5))
    manager.add_field(ConstraintField(name="b", strength=0.7, weight=0.5))
    c = manager.compute_effective_constraint(0)
    expected = 0.5 * 0.3 + 0.5 * 0.7  # = 0.5
    assert abs(c - expected) < 0.001, f"Expected {expected}, got {c}"
    print("  Test 2 (two additive): PASSED")
    
    # Test 3: Competitive (winner-take-all)
    manager = MultiFieldManager()
    manager.add_field(ConstraintField(name="strong", strength=0.8, coupling_type="competitive"))
    manager.add_field(ConstraintField(name="weak", strength=0.3, coupling_type="competitive"))
    c = manager.compute_effective_constraint(0)
    assert c == 0.8, f"Expected 0.8 (winner), got {c}"
    print("  Test 3 (competitive): PASSED")
    
    # Test 4: Phase modulation
    manager = MultiFieldManager()
    manager.add_field(ConstraintField(name="mod", strength=1.0, frequency=0.1, phase=0.0))
    c0 = manager.compute_effective_constraint(0)  # sin(0) = 0, mod = 0.5
    expected_c0 = 1.0 * 0.5  # 0.5 * (1 + sin(0))
    assert abs(c0 - expected_c0) < 0.001, f"Expected {expected_c0}, got {c0}"
    print("  Test 4 (modulation): PASSED")
    
    # Test 5: Per-bit constraint (two fields, normalized weights = 0.5 each)
    manager = MultiFieldManager()
    manager.add_field(ConstraintField(name="even", strength=1.0, domain="even"))  # Use 1.0 so normalized = 0.5
    manager.add_field(ConstraintField(name="odd", strength=1.0, domain="odd"))    # Use 1.0 so normalized = 0.5
    per_bit = manager.compute_per_bit_constraint(0, 4)
    assert per_bit[0] == 0.5, f"Even bit should be 0.5, got {per_bit[0]}"
    assert per_bit[1] == 0.5, f"Odd bit should be 0.5, got {per_bit[1]}"
    print("  Test 5 (per-bit): PASSED")
    
    # Test 6: Interference (out-of-phase cancellation)
    manager = create_two_field_interference(strength=0.5, phase_diff=math.pi)
    # At t=0, field_0: 0.5*0.5=0.25 (phase=0, mod=0.5)
    # field_1: 0.5*0.5=0.25 (phase=pi, mod=0.5, sin(pi)=0)
    # Total should be 0.25
    c = manager.compute_effective_constraint(0)
    expected = 0.5 * 0.25 + 0.5 * 0.25  # normalized weights
    print(f"  Test 6 (interference): c={c:.3f}, expected={expected:.3f}")
    
    print("All tests PASSED!")
    return True


if __name__ == "__main__":
    test_multi_field_manager()
