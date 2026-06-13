"""
environment_energy.py — Open system energy-entropy flow for Phase 22

Implements:
- EnvironmentEnergyField: Active energy injection from environment
- EntropyExhaust: Entropy export channel to environment

Phase 22 extends Phase 21's fixed energy budget to continuous open-system flow.
"""

from dataclasses import dataclass, field
from typing import Optional, List
import numpy as np


@dataclass
class EnvironmentConfig:
    """Configuration for open system energy dynamics."""
    
    # Energy injection from environment
    base_rate: float = 2.0       # Base energy injection rate per step
    constraint_strength: float = 0.5  # 0.0-1.0, stronger constraint = more injection
    
    # Entropy exhaust
    exhaust_rate: float = 0.05   # Fraction of entropy exported per step (0.0-1.0)
    
    # Energy cap
    max_energy: float = 200.0    # Maximum system energy (prevents runaway)
    
    # Constraint energy coupling
    # Stronger constraint provides more "focused" energy
    constraint_energy_factor: float = 1.5  # multiplier when constraint_strength=1.0


@dataclass
class EnvironmentState:
    """Runtime state for environment energy field."""
    
    # Cumulative energy injected from environment
    total_injected: float = 0.0
    
    # Cumulative entropy exhausted to environment
    total_exhausted: float = 0.0
    
    # Step-by-step history
    injection_history: List[float] = field(default_factory=list)
    exhaust_history: List[float] = field(default_factory=list)
    constraint_strength_history: List[float] = field(default_factory=list)
    
    # Dynamic constraint (can vary over time)
    current_constraint: float = 0.5


class EnvironmentEnergyField:
    """
    Active energy field that injects energy into the system from environment.
    
    Key insight: Environment constraint (e.g., selection pressure, physical
    boundary conditions) doesn't drain energy — it FOCUSES energy, making
    the system more efficient at maintaining differences.
    
    Formula: injection = base_rate * (1 + constraint_strength * constraint_energy_factor)
    
    Example:
        base_rate=2.0, constraint_strength=0.5, factor=1.5
        -> injection = 2.0 * (1 + 0.5 * 1.5) = 2.0 * 1.75 = 3.5
    """
    
    def __init__(self, config: Optional[EnvironmentConfig] = None):
        self.config = config or EnvironmentConfig()
        self.state = EnvironmentState(
            current_constraint=self.config.constraint_strength
        )
    
    def inject(self, current_energy: float, layer_bits: Optional[np.ndarray] = None) -> float:
        """
        Inject energy from environment into the system.
        
        Args:
            current_energy: Current system energy level
            layer_bits: Optional bit array for context-dependent injection
        
        Returns:
            float: Amount of energy injected this step
        """
        cfg = self.config
        
        # Dynamic constraint: can modulate based on system state
        constraint = self.state.current_constraint
        
        # Energy injection formula
        injection = cfg.base_rate * (1.0 + constraint * cfg.constraint_energy_factor)
        
        # Cap at max_energy
        if current_energy + injection > cfg.max_energy:
            injection = max(0.0, cfg.max_energy - current_energy)
        
        # Record history
        self.state.total_injected += injection
        self.state.injection_history.append(injection)
        self.state.constraint_strength_history.append(constraint)
        
        return injection
    
    def update_constraint(self, new_strength: float):
        """
        Update the constraint strength (can vary over time).
        
        Args:
            new_strength: New constraint strength in [0.0, 1.0]
        """
        self.state.current_constraint = max(0.0, min(1.0, new_strength))
    
    def get_injection_rate(self) -> float:
        """Get the current injection rate (for analysis)."""
        cfg = self.config
        constraint = self.state.current_constraint
        return cfg.base_rate * (1.0 + constraint * cfg.constraint_energy_factor)


class EntropyExhaust:
    """
    Entropy export channel — removes entropy from system to environment.
    
    Key insight: Real open systems export entropy to the environment,
    preventing the "heat death" that occurs in closed systems.
    
    Formula: entropy_remaining = entropy_current * (1 - exhaust_rate)
    
    Without exhaust (Phase 21): entropy accumulates -> dead order
    With exhaust (Phase 22): entropy exports -> sustained dynamics
    """
    
    def __init__(self, config: Optional[EnvironmentConfig] = None):
        # Use exhaust_rate from EnvironmentConfig
        cfg = config or EnvironmentConfig()
        self.exhaust_rate = cfg.exhaust_rate
        self.state = EnvironmentState()  # Reuse EnvironmentState for exhaust tracking
    
    def exhaust(self, current_entropy: float, current_energy: Optional[float] = None) -> float:
        """
        Export entropy to environment.
        
        Args:
            current_entropy: Current system entropy level
            current_energy: Optional energy level (for adaptive exhaust)
        
        Returns:
            float: Remaining entropy after exhaust
        """
        # Adaptive exhaust: if energy is high, exhaust more (system is "healthy")
        adaptive_rate = self.exhaust_rate
        if current_energy is not None:
            # Normalize energy (assume 100.0 is baseline)
            energy_ratio = current_energy / 100.0
            # High energy -> exhaust more; low energy -> exhaust less
            adaptive_rate = self.exhaust_rate * min(1.5, max(0.5, energy_ratio))
        
        # Calculate exhaust
        exhausted = current_entropy * adaptive_rate
        remaining = current_entropy - exhausted
        
        # Record history
        self.state.total_exhausted += exhausted
        self.state.exhaust_history.append(exhausted)
        
        return max(0.0, remaining)
    
    def get_exhaust_rate(self) -> float:
        """Get current exhaust rate."""
        return self.exhaust_rate


class OpenSystemCoupling:
    """
    Full open-system coupling combining energy injection + entropy exhaust.
    
    Integrates EnvironmentEnergyField and EntropyExhaust into a single
    coupling interface that can be attached to any layer.
    """
    
    def __init__(self, config: Optional[EnvironmentConfig] = None):
        self.config = config or EnvironmentConfig()
        self.env_field = EnvironmentEnergyField(self.config)
        self.entropy_exhaust = EntropyExhaust(self.config)
        
        # Layer-specific state
        self.total_energy_injected = 0.0
        self.total_entropy_exhausted = 0.0
    
    def step(self, current_energy: float, current_entropy: float,
             layer_bits: Optional[np.ndarray] = None) -> dict:
        """
        Perform one step of open-system coupling.
        
        Args:
            current_energy: Current layer energy
            current_entropy: Current layer entropy
            layer_bits: Optional layer bit array
        
        Returns:
            dict with injection, exhaust, and remaining values
        """
        # 1. Inject energy from environment
        injection = self.env_field.inject(current_energy, layer_bits)
        new_energy = current_energy + injection
        
        # Cap at max
        if new_energy > self.config.max_energy:
            new_energy = self.config.max_energy
        
        # 2. Exhaust entropy to environment
        new_entropy = self.entropy_exhaust.exhaust(current_entropy, new_energy)
        exhausted_this_step = current_entropy - new_entropy
        
        # Track totals
        self.total_energy_injected += injection
        self.total_entropy_exhausted += exhausted_this_step
        
        return {
            'energy_injected': injection,
            'energy_after': new_energy,
            'entropy_exhausted': exhausted_this_step,
            'entropy_remaining': new_entropy,
            'cumulative_injected': self.total_energy_injected,
            'cumulative_exhausted': self.total_entropy_exhausted
        }
    
    def state_exhausted(self) -> float:
        """Get total entropy exhausted so far."""
        return self.entropy_exhaust.state.total_exhausted
    
    def state_injected(self) -> float:
        """Get total energy injected so far."""
        return self.env_field.state.total_injected
    
    def get_summary(self) -> dict:
        """Get coupling summary."""
        return {
            'total_energy_injected': self.total_energy_injected,
            'total_entropy_exhausted': self.total_entropy_exhausted,
            'current_injection_rate': self.env_field.get_injection_rate(),
            'current_exhaust_rate': self.entropy_exhaust.get_exhaust_rate(),
            'constraint_strength': self.env_field.state.current_constraint
        }