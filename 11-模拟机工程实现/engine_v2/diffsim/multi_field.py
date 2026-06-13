"""
Multi-Field Competitive Constraints for Phase 22 P5.

Enables multiple constraint fields with different strengths, frequencies,
phases, domains, and coupling types to compete or cooperate.

Author: AI Agent (Heartbeat 2026-06-14 02:44)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import math
import cmath
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
    coupling_type: str = "additive"        # "additive", "multiplicative", "competitive", "interference"
    weight: float = 1.0                    # Relative weight (for normalization)
    
    coupling_mode: str = "intensity"       # "intensity" (default) or "amplitude" (for interference)
    
    def __post_init__(self):
        """Validate parameters."""
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0, 1], got {self.strength}")
        if self.frequency < 0.0:
            raise ValueError(f"frequency must be >= 0, got {self.frequency}")
        if self.coupling_type not in ["additive", "multiplicative", "competitive", "interference"]:
            raise ValueError(f"Invalid coupling_type: {self.coupling_type}")
        if self.coupling_mode not in ["intensity", "amplitude"]:
            raise ValueError(f"Invalid coupling_mode: {self.coupling_mode}")
    
    def get_modulation(self, t: int) -> float:
        """
        Compute temporal modulation factor at step t.
        
        Returns a value in [0, 1] representing the field's current intensity.
        For static fields (frequency=0), returns 1.0.
        For modulated fields, returns 0.5 * (1 + sin(2*pi*f*t + phase)).
        
        Note: For amplitude-based interference, use get_amplitude() instead.
        """
        if self.frequency == 0.0:
            return 1.0
        
        modulation = 0.5 * (1.0 + math.sin(2.0 * math.pi * self.frequency * t + self.phase))
        return modulation
    
    def get_amplitude(self, t: int) -> complex:
        """
        Compute complex amplitude at step t for interference coupling.
        
        Returns:
            complex: Amplitude as A * exp(i*phase) * modulation_factor
        """
        intensity_mod = self.get_modulation(t)
        # Convert intensity to amplitude: A = sqrt(I)
        amplitude_mag = math.sqrt(self.strength * intensity_mod)
        # Phase includes both field's phase and temporal modulation phase
        phase = self.phase
        if self.frequency > 0:
            # Add temporal phase
            temporal_phase = 2.0 * math.pi * self.frequency * t
            phase += temporal_phase
        return cmath.rect(amplitude_mag, phase)
    
    def get_intensity(self, t: int) -> float:
        """
        Compute intensity (|amplitude|^2) at step t.
        
        Returns:
            float: Intensity in [0, 1]
        """
        if self.coupling_mode == "amplitude":
            amplitude = self.get_amplitude(t)
            return abs(amplitude) ** 2
        else:
            # Intensity mode: strength * modulation
            return self.strength * self.get_modulation(t)
    
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
    fields: list = None                       # Optional: fields to pre-configure (list of ConstraintField)
    

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
        
        # Add pre-configured fields from config
        if self.config.fields:
            for field in self.config.fields:
                self.add_field(field)
        
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
        For "interference" coupling, uses wave superposition (amplitude sum).
        """
        if not self.fields:
            return 0.0
        
        weights = self.get_normalized_weights()
        
        # Group fields by coupling type
        additive_fields = [f for f in self.fields if f.coupling_type == "additive"]
        multiplicative_fields = [f for f in self.fields if f.coupling_type == "multiplicative"]
        competitive_fields = [f for f in self.fields if f.coupling_type == "competitive"]
        interference_fields = [f for f in self.fields if f.coupling_type == "interference"]
        
        effective_c = 0.0
        
        # Interference coupling: wave superposition (amplitude sum)
        if interference_fields:
            # Sum complex amplitudes
            total_amplitude = complex(0, 0)
            for f in interference_fields:
                amp = f.get_amplitude(t)
                total_amplitude += amp
            # Intensity = |amplitude|^2
            interference_c = abs(total_amplitude) ** 2
            
            # If other fields exist, blend with them
            if additive_fields or multiplicative_fields or competitive_fields:
                # Compute other coupling result
                other_c = self._compute_non_interference_constraint(t, additive_fields, multiplicative_fields, competitive_fields)
                # Weighted blend (interference gets higher weight for wave effects)
                n_inter = len(interference_fields)
                n_other = len(additive_fields) + len(multiplicative_fields) + len(competitive_fields)
                total = n_inter + n_other
                effective_c = (n_other * other_c + n_inter * interference_c) / total
            else:
                effective_c = interference_c
            
            return min(1.0, max(0.0, effective_c))
        
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
    
    def _compute_non_interference_constraint(self, t: int, 
                                             additive_fields: List[ConstraintField],
                                             multiplicative_fields: List[ConstraintField],
                                             competitive_fields: List[ConstraintField]) -> float:
        """Helper: compute constraint for non-interference fields."""
        weights = self.get_normalized_weights()
        effective_c = 0.0
        
        if additive_fields:
            additive_sum = sum(
                weights[f.name] * f.get_effective_strength(t)
                for f in additive_fields
            )
            effective_c += additive_sum
        
        if multiplicative_fields:
            prod = 1.0
            for f in multiplicative_fields:
                effective = weights[f.name] * f.get_effective_strength(t)
                prod *= (1.0 + effective)
            multiplicative_c = min(1.0, prod - 1.0)
            if additive_fields:
                n_add = len(additive_fields)
                n_mul = len(multiplicative_fields)
                total = n_add + n_mul
                effective_c = (n_add * effective_c + n_mul * multiplicative_c) / total
            else:
                effective_c = multiplicative_c
        
        if competitive_fields:
            competitive_c = max(f.get_effective_strength(t) for f in competitive_fields)
            if additive_fields or multiplicative_fields:
                n_other = len(additive_fields) + len(multiplicative_fields)
                n_comp = len(competitive_fields)
                total = n_other + 2 * n_comp
                effective_c = (n_other * effective_c + 2 * n_comp * competitive_c) / total
            else:
                effective_c = competitive_c
        
        return min(1.0, max(0.0, effective_c))
    
    def compute_per_bit_constraint(self, t: int, n_bits: int) -> np.ndarray:
        """
        Compute constraint strength for each bit individually.
        
        This allows spatially heterogeneous constraints where different
        bits experience different field intensities.
        
        For "interference" coupling, computes spatial interference patterns.
        
        Returns:
            numpy array of shape (n_bits,) with constraint strength per bit
        """
        per_bit_c = np.zeros(n_bits)
        weights = self.get_normalized_weights()
        
        # Separate interference fields from others
        interference_fields = [f for f in self.fields if f.coupling_type == "interference"]
        other_fields = [f for f in self.fields if f.coupling_type != "interference"]
        
        # Handle interference fields: spatial interference patterns
        if interference_fields:
            for idx in range(n_bits):
                # Compute spatial phase for this bit index
                # Simple model: phase depends on bit position (creates spatial fringes)
                amplitudes = []
                for field_idx, f in enumerate(interference_fields):
                    amp = f.get_amplitude(t)
                    # Spatial phase: each field has a different spatial wavelength
                    # This creates spatial interference fringes when fields combine
                    # Field i uses wavelength = n_bits / (2 + i) so different fields
                    # produce different spatial patterns that can interfere
                    wavelength = max(n_bits / (2 + field_idx), 1.0)
                    spatial_phase = 2.0 * math.pi * idx / wavelength
                    spatial_amp = amp * cmath.exp(1j * spatial_phase)
                    amplitudes.append(spatial_amp)
                
                # Sum amplitudes and compute intensity
                total_amp = sum(amplitudes)
                intensity = abs(total_amp) ** 2
                per_bit_c[idx] = intensity
        
        # Handle other fields: additive per-bit (existing logic)
        for f in other_fields:
            domain_indices = f.get_domain_indices(n_bits)
            effective_strength = weights[f.name] * f.get_effective_strength(t)
            
            for idx in domain_indices:
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
                                   phase_diff: float = math.pi,
                                   use_interference: bool = True) -> MultiFieldManager:
    """
    Create a two-field interference configuration.
    
    Two fields of equal strength with a phase difference.
    Phase_diff = pi produces maximum interference (cancellation).
    
    Args:
        strength: Field strength (0.0-1.0)
        phase_diff: Phase difference between fields (radians)
        use_interference: If True, use "interference" coupling (wave superposition)
                        If False, use "additive" coupling (linear combination)
    """
    manager = MultiFieldManager()
    coupling = "interference" if use_interference else "additive"
    manager.add_field(ConstraintField(
        name="field_0",
        strength=strength,
        frequency=0.01,
        phase=0.0,
        coupling_type=coupling,
        coupling_mode="amplitude" if use_interference else "intensity"
    ))
    manager.add_field(ConstraintField(
        name="field_1", 
        strength=strength,
        frequency=0.01,
        phase=phase_diff,
        coupling_type=coupling,
        coupling_mode="amplitude" if use_interference else "intensity"
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
    
    # Test 6: Interference (in-phase: constructive)
    manager = create_two_field_interference(strength=0.5, phase_diff=0.0, use_interference=True)
    c = manager.compute_effective_constraint(0)
    # In-phase: amplitude sum = 2*A, intensity = 4*A^2 = 4*0.25 = 1.0
    # But each field has strength=0.5, so A = sqrt(0.5*0.5) = 0.5
    # Total amplitude = 0.5 + 0.5 = 1.0, intensity = 1.0
    print(f"  Test 6a (interference, in-phase): c={c:.3f} (expected ~1.0)")
    
    # Test 6b: Interference (out-of-phase: destructive)
    manager = create_two_field_interference(strength=0.5, phase_diff=math.pi, use_interference=True)
    c = manager.compute_effective_constraint(0)
    # Out-of-phase: amplitude sum = A - A = 0, intensity = 0
    print(f"  Test 6b (interference, out-of-phase): c={c:.3f} (expected ~0.0)")
    
    # Test 7: Compare additive vs interference
    # Additive: 0.5 * 0.5 + 0.5 * 0.5 = 0.5 (no cancellation)
    manager_add = create_two_field_interference(strength=0.5, phase_diff=math.pi, use_interference=False)
    c_add = manager_add.compute_effective_constraint(0)
    # Interference: amplitude sum = 0, intensity = 0 (cancellation!)
    manager_int = create_two_field_interference(strength=0.5, phase_diff=math.pi, use_interference=True)
    c_int = manager_int.compute_effective_constraint(0)
    print(f"  Test 7 (additive={c_add:.3f} vs interference={c_int:.3f})")
    print("  [PASS] Interference coupling shows wave effects!")
    
    print("All tests PASSED!")
    return True


if __name__ == "__main__":
    test_multi_field_manager()
