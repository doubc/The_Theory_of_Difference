"""
Open System Extension for Phase 16

Implements open system dynamics to allow the simulator to interact with an environment,
enabling continuous evolution after sealing and potentially leading to L2 emergence.

Theoretical Basis:
- Closed systems (current implementation) reach equilibrium and stop evolving
- Open systems exchange energy/information with environment, maintaining non-equilibrium
- Life and consciousness are open systems far from equilibrium

Key Components:
1. Environment Bits: External bits that fluctuate randomly (Brownian motion)
2. Energy Flow: Energy injection and dissipation dynamics  
3. Thermodynamic Extension: System maintains non-equilibrium steady state
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class OpenSystemConfig:
    """Configuration for open system extension"""
    # Environment coupling
    enable_environment_bits: bool = True
    env_bit_ratio: float = 0.2  # ratio of environment bits to grid bits
    env_flip_prob: float = 0.1  # probability of environment bit flipping per step
    
    # Energy dynamics
    enable_energy_flow: bool = True
    initial_energy: float = 100.0  # initial system energy
    energy_injection_rate: float = 0.05  # energy injected per step from environment
    energy_dissipation_rate: float = 0.02  # energy dissipated per step
    energy_per_flip: float = 1.0  # energy cost for each bit flip
    
    # Thermodynamic parameters
    enable_thermodynamic: bool = True
    temperature: float = 1.0  # system temperature (controls thermal noise)
    coupling_strength: float = 0.5  # environment-system coupling strength
    
    # Sealing dynamics in open system
    enable_dynamic_sealing: bool = True
    unseal_energy_threshold: float = 30.0  # energy threshold to trigger unsealing
    reseal_energy_threshold: float = 70.0  # energy threshold to allow resealing


class EnvironmentBits:
    """
    Environment bits that interact with the system boundary.
    
    Models:
    - Random fluctuations (Brownian motion of environment)
    - Energy exchange with system boundary bits
    - Stochastic boundary conditions
    """
    
    def __init__(
        self, 
        grid_shape: Tuple[int, ...],
        config: OpenSystemConfig
    ):
        self.grid_shape = grid_shape
        self.config = config
        
        # Calculate number of environment bits
        total_grid_bits = np.prod(grid_shape)
        self.num_env_bits = int(total_grid_bits * config.env_bit_ratio)
        
        # Initialize environment bits randomly
        self.state = torch.randint(0, 2, (self.num_env_bits,), dtype=torch.float32)
        
        # Track environment energy
        self.energy = config.initial_energy * 0.5
        
        print(f"[EnvironmentBits] Initialized with {self.num_env_bits} bits "
              f"(ratio={config.env_bit_ratio}), flip_prob={config.env_flip_prob}")
    
    def step(self, boundary_bits: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Update environment bits and compute coupling with system boundary.
        
        Args:
            boundary_bits: Boundary bits of the system (optional, for coupling)
        
        Returns:
            coupling_signal: Signal to be added to system boundary dynamics
        """
        # 1. Random flips (Brownian motion)
        flip_mask = torch.rand(self.num_env_bits) < self.config.env_flip_prob
        self.state[flip_mask] = 1.0 - self.state[flip_mask]
        
        # 2. Compute coupling with boundary bits (if provided)
        coupling_signal = torch.zeros_like(self.state)
        if boundary_bits is not None:
            # Simplified coupling: environment bits influence boundary
            # In practice, this would be a more complex boundary condition
            boundary_flat = boundary_bits.flatten()
            min_len = min(len(boundary_flat), self.num_env_bits)
            coupling_strength = self.config.coupling_strength
            
            # Environment bits correlate with nearby boundary bits
            # Positive correlation: environment tends to align with boundary
            # Negative correlation: environment tends to oppose boundary (frustration)
            coupling_signal[:min_len] = coupling_strength * (
                boundary_flat[:min_len] - self.state[:min_len]
            )
        
        # 3. Energy exchange
        # Environment gains energy from random fluctuations
        self.energy += torch.rand(1).item() * 0.1
        
        # Environment loses energy to system if coupled
        if boundary_bits is not None:
            self.energy -= coupling_strength * 0.5
        
        return coupling_signal
    
    def inject_energy(self, amount: float):
        """Inject energy into the environment"""
        self.energy += amount
    
    def get_coupling_field(self, grid_shape: Tuple[int, ...]) -> torch.Tensor:
        """
        Return a coupling field that can be added to the system's update rule.
        
        This creates a boundary condition where environment bits influence
        the system's boundary bits.
        """
        # Simplified: create a field that affects boundary regions
        field = torch.zeros(grid_shape)
        
        # Add environment influence to boundaries
        # For 2D grid: affect outermost pixels
        if len(grid_shape) == 2:
            h, w = grid_shape
            env_influence = self.state[:2*h + 2*(w-2)]  # approximate boundary length
            idx = 0
            
            # Top boundary
            field[0, :] = env_influence[idx:idx+w]
            idx += w
            
            # Bottom boundary
            field[h-1, :] = env_influence[idx:idx+w]
            idx += w
            
            # Left boundary (excluding corners)
            field[1:h-1, 0] = env_influence[idx:idx+(h-2)]
            idx += (h-2)
            
            # Right boundary (excluding corners)
            field[1:h-1, -1] = env_influence[idx:idx+(h-2)]
        
        return self.config.coupling_strength * field


class EnergyDynamics:
    """
    Energy flow dynamics for open system.
    
    Models:
    - Energy injection from environment
    - Energy dissipation through bit flips
    - Non-equilibrium steady state maintenance
    """
    
    def __init__(self, config: OpenSystemConfig):
        self.config = config
        self.system_energy = config.initial_energy
        self.dissipated_energy = 0.0
        self.injected_energy = 0.0
        
        print(f"[EnergyDynamics] Initialized with E={config.initial_energy}, "
              f"inject_rate={config.energy_injection_rate}, "
              f"dissipate_rate={config.energy_dissipation_rate}")
    
    def step(
        self, 
        num_flips: int,
        coupling_energy: float = 0.0
    ) -> dict:
        """
        Update energy dynamics for one step.
        
        Args:
            num_flips: Number of bit flips in this step
            coupling_energy: Energy exchanged with environment
        
        Returns:
            energy_report: Dictionary with energy metrics
        """
        # 1. Energy cost of bit flips
        flip_energy_cost = num_flips * self.config.energy_per_flip
        self.system_energy -= flip_energy_cost
        self.dissipated_energy += flip_energy_cost
        
        # 2. Energy injection from environment
        injected = self.config.energy_injection_rate * self.system_energy
        self.system_energy += injected
        self.injected_energy += injected
        
        # 3. Energy dissipation (thermal)
        dissipated = self.config.energy_dissipation_rate * self.system_energy
        self.system_energy -= dissipated
        self.dissipated_energy += dissipated
        
        # 4. Coupling energy exchange
        self.system_energy += coupling_energy
        
        # 5. Ensure non-negative energy
        self.system_energy = max(0.0, self.system_energy)
        
        return {
            'system_energy': self.system_energy,
            'flip_energy_cost': flip_energy_cost,
            'injected_energy': injected,
            'dissipated_energy': dissipated,
            'coupling_energy': coupling_energy,
            'net_energy_change': injected - flip_energy_cost - dissipated + coupling_energy
        }
    
    def get_energy_gradient(self) -> float:
        """Return energy gradient (dE/dt) for thermodynamic analysis"""
        # Simplified: use recent energy change as gradient
        return self.system_energy - self.dissipated_energy + self.injected_energy
    
    def check_non_equilibrium(self) -> bool:
        """
        Check if system is in non-equilibrium steady state.
        
        Returns:
            True if system is far from equilibrium (energy flowing)
        """
        energy_flow = self.config.energy_injection_rate - self.config.energy_dissipation_rate
        return abs(energy_flow) > 1e-6 and self.system_energy > 0


class OpenSystemSimulator:
    """
    Wrapper that extends BitFlipSimulation with open system dynamics.
    
    Enables:
    - Continuous evolution after sealing
    - Environment-system coupling
    - Energy flow maintenance
    - Potential for L2 emergence through sustained non-equilibrium
    """
    
    def __init__(
        self,
        base_simulation,  # BitFlipSimulation instance
        config: Optional[OpenSystemConfig] = None
    ):
        self.base_sim = base_simulation
        self.config = config or OpenSystemConfig()
        
        # Initialize open system components
        grid_shape = base_simulation.grid.shape
        self.env_bits = EnvironmentBits(grid_shape, self.config)
        self.energy_dynamics = EnergyDynamics(self.config)
        
        # Tracking
        self.steps_in_non_equilibrium = 0
        self.seal_breaks = 0
        
        print(f"\n[OpenSystemSimulator] Initialized")
        print(f"  Environment bits: {self.env_bits.num_env_bits}")
        print(f"  Energy flow enabled: {self.config.enable_energy_flow}")
        print(f"  Dynamic sealing enabled: {self.config.enable_dynamic_sealing}")
    
    def step(self) -> dict:
        """
        Perform one step with open system dynamics.
        
        Returns:
            step_report: Dictionary with step metrics
        """
        # 1. Get current system state
        current_grid = self.base_sim.grid
        boundary_bits = self._extract_boundary(current_grid)
        
        # 2. Update environment
        coupling_signal = self.env_bits.step(boundary_bits)
        coupling_field = self.env_bits.get_coupling_field(current_grid.shape)
        
        # 3. Apply coupling to system (modify update rule)
        # This is a simplified implementation
        # In practice, would modify the base_sim's update rule
        modified_grid = current_grid + coupling_field
        
        # 4. Count bit flips (for energy calculation)
        # Simplified: assume 1% of bits flip per step
        num_flips = int(0.01 * np.prod(current_grid.shape))
        
        # 5. Update energy dynamics
        coupling_energy = torch.sum(coupling_field).item()
        energy_report = self.energy_dynamics.step(num_flips, coupling_energy)
        
        # 6. Check if system is in non-equilibrium
        if self.energy_dynamics.check_non_equilibrium():
            self.steps_in_non_equilibrium += 1
        
        # 7. Dynamic sealing logic
        seal_status = self._check_dynamic_sealing(energy_report)
        
        return {
            'energy_report': energy_report,
            'coupling_signal_strength': torch.norm(coupling_signal).item(),
            'steps_in_non_equilibrium': self.steps_in_non_equilibrium,
            'seal_status': seal_status,
            'env_energy': self.env_bits.energy,
            'system_energy': energy_report['system_energy']
        }
    
    def _extract_boundary(self, grid: torch.Tensor) -> torch.Tensor:
        """Extract boundary bits from grid"""
        if len(grid.shape) == 2:
            h, w = grid.shape
            boundary = torch.cat([
                grid[0, :],  # top
                grid[h-1, :],  # bottom
                grid[1:h-1, 0],  # left (excluding corners)
                grid[1:h-1, w-1]  # right (excluding corners)
            ])
            return boundary
        else:
            # For 1D or other shapes, return the grid itself
            return grid.flatten()
    
    def _check_dynamic_sealing(self, energy_report: dict) -> str:
        """
        Check if sealing status should change based on energy dynamics.
        
        Returns:
            seal_status: 'sealed', 'unsealed', or 'resealing'
        """
        if not self.config.enable_dynamic_sealing:
            return 'sealed' if self.base_sim.is_sealed() else 'unsealed'
        
        system_energy = energy_report['system_energy']
        
        # Check if should unseal
        if (self.base_sim.is_sealed() and 
            system_energy < self.config.unseal_energy_threshold):
            self.seal_breaks += 1
            print(f"  [Dynamic Sealing] Energy {system_energy:.1f} < threshold "
                  f"{self.config.unseal_energy_threshold}, UNSEALING")
            return 'unsealed'
        
        # Check if can reseal
        if (not self.base_sim.is_sealed() and 
            system_energy > self.config.reseal_energy_threshold):
            print(f"  [Dynamic Sealing] Energy {system_energy:.1f} > threshold "
                  f"{self.config.reseal_energy_threshold}, RESEALING")
            return 'resealing'
        
        return 'sealed' if self.base_sim.is_sealed() else 'unsealed'
    
    def run_with_open_dynamics(self, steps: int = 1000) -> dict:
        """
        Run simulation with open system dynamics for specified steps.
        
        Returns:
            final_report: Summary of the run
        """
        print(f"\n[OpenSystemSimulator] Running open dynamics for {steps} steps...")
        
        history = {
            'system_energy': [],
            'env_energy': [],
            'seal_status': [],
            'steps_in_non_equilibrium': []
        }
        
        for step in range(steps):
            step_report = self.step()
            
            # Record history
            history['system_energy'].append(step_report['system_energy'])
            history['env_energy'].append(step_report['env_energy'])
            history['seal_status'].append(step_report['seal_status'])
            history['steps_in_non_equilibrium'].append(
                step_report['steps_in_non_equilibrium']
            )
            
            # Print progress
            if step % 100 == 0:
                print(f"  Step {step}: E_sys={step_report['system_energy']:.1f}, "
                      f"E_env={step_report['env_energy']:.1f}, "
                      f"seal={step_report['seal_status']}")
        
        # Final analysis
        final_report = {
            'total_steps': steps,
            'final_system_energy': history['system_energy'][-1],
            'final_env_energy': history['env_energy'][-1],
            'total_seal_breaks': self.seal_breaks,
            'total_non_eq_steps': self.steps_in_non_equilibrium,
            'energy_history': history['system_energy'],
            'seal_history': history['seal_status']
        }
        
        print(f"\n[OpenSystemSimulator] Run complete:")
        print(f"  Total seal breaks: {self.seal_breaks}")
        print(f"  Steps in non-equilibrium: {self.steps_in_non_equilibrium}")
        print(f"  Final system energy: {final_report['final_system_energy']:.1f}")
        
        return final_report


def test_open_system_extension():
    """Test the open system extension with a simple simulation"""
    print("=" * 60)
    print("Testing Open System Extension (Phase 16)")
    print("=" * 60)
    
    # This is a placeholder - would need actual BitFlipSimulation
    # For now, just test the components
    
    config = OpenSystemConfig(
        enable_environment_bits=True,
        env_bit_ratio=0.2,
        enable_energy_flow=True,
        initial_energy=100.0
    )
    
    # Test EnvironmentBits
    print("\n1. Testing EnvironmentBits...")
    env_bits = EnvironmentBits(grid_shape=(32, 32), config=config)
    coupling = env_bits.step()
    print(f"   Coupling signal shape: {coupling.shape}")
    print(f"   Environment energy: {env_bits.energy:.1f}")
    
    # Test EnergyDynamics
    print("\n2. Testing EnergyDynamics...")
    energy_dyn = EnergyDynamics(config)
    report = energy_dyn.step(num_flips=10)
    print(f"   System energy after step: {report['system_energy']:.1f}")
    print(f"   Net energy change: {report['net_energy_change']:.1f}")
    
    # Test non-equilibrium check
    is_non_eq = energy_dyn.check_non_equilibrium()
    print(f"   Non-equilibrium state: {is_non_eq}")
    
    print("\n" + "=" * 60)
    print("Open System Extension test complete!")
    print("=" * 60)
    
    return {
        'env_bits': env_bits,
        'energy_dynamics': energy_dyn,
        'config': config
    }


if __name__ == "__main__":
    test_open_system_extension()
