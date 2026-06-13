"""
world.py — World simulation with energy and entropy integration (Phase 21)

Implements the main world class that integrates all mechanisms (m1-m9)
with energy flow and entropy tracking.
"""

import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

from .energy import EnergyConfig, EnergyManager
from .entropy import EntropyConfig, EntropyTracker
from .environment_energy import EnvironmentConfig as OpenSystemConfig, OpenSystemCoupling
# Note: Mechanism functions are called internally, not imported here
# from .mechanisms import (
#     m1_differentiate,
#     m2_cluster,
#     m3_conserve,
#     m4_stabilize,
#     m5_break_symmetry,
#     m6_check_stability,
#     m7_bind,
#     m8_encapsulate,
#     m9_should_seal,
#     m9_seal
# )


@dataclass
class WorldConfig:
    """Configuration for world simulation."""
    
    # World parameters
    n_bits: int = 48  # Number of bits (N0)
    n_colors: int = 6   # Number of meta-colors (k)
    
    # Sealing parameters
    binding_threshold: float = 1.0
    seal_threshold: float = 0.4
    
    # Energy/Entropy configs
    energy_config: Optional[EnergyConfig] = None
    entropy_config: Optional[EntropyConfig] = None
    
    # Open System config (Phase 22)
    open_system_config: Optional[OpenSystemConfig] = None
    
    # Simulation parameters
    max_steps: int = 2000
    snapshot_interval: int = 10
    
    # Layer parameters
    min_org_size: int = 3
    n_meta_colors: int = 4


@dataclass
class WorldState:
    """Current state of the world."""
    
    # Current step
    step: int = 0
    
    # Bits (current state)
    bits: np.ndarray = None  # Will be initialized as zeros
    
    # Organizations (clusters of bits)
    organizations: List[set] = field(default_factory=list)
    
    # Sealing state
    is_sealed: bool = False
    seal_step: Optional[int] = None
    frozen_bits: set = field(default_factory=set)
    
    # Layer information
    layer: int = 0
    parent_world = None  # Reference to parent (for L1+)
    
    # Energy and entropy managers
    energy_manager: Optional[EnergyManager] = None
    entropy_tracker: Optional[EntropyTracker] = None
    
    # Open System coupling (Phase 22)
    open_system: Optional[OpenSystemCoupling] = None
    
    # Snapshot history
    snapshots: list = field(default_factory=list)
    
    def __post_init__(self):
        if self.bits is None:
            self.bits = np.zeros(48, dtype=bool)


class World:
    """
    Main world class implementing differential theory mechanisms
    with energy and entropy integration.
    """
    
    def __init__(self, config: Optional[WorldConfig] = None):
        self.config = config or WorldConfig()
        self.state = WorldState()
        
        # Initialize bits
        self.state.bits = np.zeros(self.config.n_bits, dtype=bool)
        
        # Initialize energy manager
        if self.config.energy_config:
            self.energy_manager = EnergyManager(self.config.energy_config)
        else:
            # Default energy config
            self.energy_manager = EnergyManager(EnergyConfig())
        
        # Initialize entropy tracker
        if self.config.entropy_config:
            self.entropy_tracker = EntropyTracker(self.config.entropy_config)
        else:
            # Default entropy config
            self.entropy_tracker = EntropyTracker(EntropyConfig())
        
        # Initialize Open System coupling (Phase 22)
        if self.config.open_system_config:
            self.open_system = OpenSystemCoupling(self.config.open_system_config)
            self.state.open_system = self.open_system
        else:
            self.open_system = None
            self.state.open_system = None
        
        # Mechanism states (m1-m9)
        self._init_mechanisms()
    
    def _init_mechanisms(self):
        """Initialize all 9 mechanisms (m1-m9)."""
        # m1: Differentiation (create differences)
        self.m1_active = True
        
        # m2: Clustering (form organizations)
        self.m2_active = True
        
        # m3: Conservation (preserve differences)
        self.m3_active = True
        
        # m4: Stabilization (stabilize clusters)
        self.m4_active = True
        
        # m5: Symmetry breaking (create asymmetry)
        self.m5_active = True
        
        # m6: Stability check (check if stable)
        self.m6_active = True
        
        # m7: Binding (bind bits to organizations)
        self.m7_active = True
        
        # m8: Encapsulation (encapsulate organizations)
        self.m8_active = True
        
        # m9: Self-reference (seal = self-referential closure)
        self.m9_active = True
    
    def step(self) -> Dict:
        """
        Perform one step of world simulation with energy/entropy integration.
        
        Returns:
            dict with step metrics
        """
        cfg = self.config
        st = self.state
        
        # Check if sealed (dead order)
        if st.is_sealed:
            return self._step_sealed()
        
        # === PHASE 22: Open System Coupling — Energy Injection Phase ===
        open_system_info = None
        if self.open_system:
            current_energy = self.energy_manager.state.energy if self.energy_manager else 0.0
            # Phase 22 Step 1: Inject energy from environment
            # (Entropy exhaust happens AFTER entropy computation, below)
            injection = self.open_system.env_field.inject(current_energy, st.bits)
            if self.energy_manager:
                self.energy_manager.state.energy = min(
                    current_energy + injection,
                    self.open_system.config.max_energy
                )
        
        # Check if energy too low (dead order)
        if self.energy_manager and self.energy_manager.is_depleted:
            st.is_sealed = True  # Enter dead order
            return self._step_sealed()
        
        # === Calculate throttle factor ===
        throttle = 1.0
        if self.energy_manager:
            throttle = self.energy_manager.throttle_factor()
        
        # === m1: Differentiation (with throttle) ===
        bits_new = m1_differentiate(st.bits, throttle=throttle)
        
        # === m2: Clustering ===
        orgs_new = m2_cluster(bits_new, st.organizations, cfg.min_org_size)
        
        # === m3: Conservation (energy cost) ===
        if self.energy_manager:
            n_active = np.sum(bits_new)
            energy_info = self.energy_manager.step(n_active, has_sealed=False)
        
        # === m4: Stabilization ===
        bits_stable = m4_stabilize(bits_new, getattr(self, '_stability_history', []), throttle=throttle)
        
        # Track stability history
        if not hasattr(self, '_stability_history'):
            self._stability_history = []
        self._stability_history.append(bits_stable.copy())
        if len(self._stability_history) > 10:
            self._stability_history.pop(0)
        
        # === m5: Symmetry breaking (with throttle) ===
        bits_broken = m5_break_symmetry(bits_stable, throttle=throttle)
        
        # === m6: Stability check (with throttle) ===
        prev_bits = getattr(self, '_prev_bits', None)
        is_stable = m6_check_stability(bits_broken, prev_bits, throttle=throttle)
        self._prev_bits = bits_broken.copy()
        
        # === m7: Binding (with throttle) ===
        bindings = m7_bind(bits_broken, orgs_new, cfg.binding_threshold, throttle=throttle)
        
        # === m8: Encapsulation (with throttle) ===
        orgs_encapsulated = m8_encapsulate(orgs_new, st.frozen_bits, throttle=throttle)
        
        # === m9: Self-reference (sealing) ===
        # Check if should seal
        binding_count = len(bindings)
        should_seal = m9_should_seal(bits_broken, orgs_new, is_stable, binding_count, cfg.binding_threshold)
        
        if should_seal:
            # Get adjusted seal threshold (modulated by energy)
            seal_threshold = cfg.seal_threshold
            if self.energy_manager:
                seal_threshold = self.energy_manager.get_adjusted_seal_threshold(cfg.seal_threshold)
            
            # Check energy before sealing
            if self.energy_manager and self.energy_manager.can_execute_mechanism('m9'):
                seal_result = m9_seal(bits_broken, orgs_new, seal_threshold, throttle=throttle)
                
                if seal_result['sealed']:
                    st.is_sealed = True
                    st.seal_step = st.step
                    st.frozen_bits = seal_result['frozen_bits']
                    
                    # Energy cost for sealing
                    if self.energy_manager:
                        self.energy_manager.step(np.sum(bits_broken), has_sealed=True)
        
        # === Entropy tracking + PHASE 22: Entropy exhaust ===
        if self.entropy_tracker:
            energy_after_injection = self.energy_manager.state.energy if self.energy_manager else 0.0
            entropy_info = self.entropy_tracker.step(
                bits=bits_broken,
                organizations=orgs_new,
                energy=energy_after_injection
            )
            
            # Phase 22 Step 2: Exhaust entropy AFTER computation (not before)
            # This removes excess entropy generated by this step, keeping system dynamic
            if self.open_system:
                computed_entropy = entropy_info.get('entropy', 0.0)
                # Only exhaust when there IS entropy to exhaust
                if computed_entropy > 0.0:
                    remaining = self.open_system.entropy_exhaust.exhaust(
                        computed_entropy,
                        energy_after_injection
                    )
                    exhausted = computed_entropy - remaining
                    self.entropy_tracker.state.entropy = remaining
                    entropy_info['entropy_exhausted'] = exhausted
                    entropy_info['entropy_after_exhaust'] = remaining
                    
                    # Update open system tracking totals
                    self.open_system.total_energy_injected += injection if self.open_system else 0
                    self.open_system.total_entropy_exhausted += exhausted
                    
                    # Build open_system_info for metrics
                    open_system_info = {
                        'energy_injected': injection if self.open_system else 0.0,
                        'entropy_exhausted': exhausted,
                        'cumulative_injected': self.open_system.total_energy_injected,
                        'cumulative_exhausted': self.open_system.total_entropy_exhausted
                    }
                else:
                    open_system_info = {
                        'energy_injected': injection if self.open_system else 0.0,
                        'entropy_exhausted': 0.0,
                        'cumulative_injected': self.open_system.total_energy_injected,
                        'cumulative_exhausted': self.open_system.total_entropy_exhausted
                    }
                    entropy_info['entropy_exhausted'] = 0.0
                    entropy_info['entropy_after_exhaust'] = 0.0
        else:
            entropy_info = None
        st.bits = bits_broken
        st.organizations = orgs_new
        st.step += 1
        
        # Take snapshot
        if st.step % cfg.snapshot_interval == 0:
            self._take_snapshot()
        
        # Return metrics (with open system data)
        return self._collect_metrics(bits_broken, orgs_new, energy_info, entropy_info, open_system_info)
    
    def _step_sealed(self) -> Dict:
        """Step when world is already sealed (dead order)."""
        metrics = {
            'step': self.state.step,
            'is_sealed': True,
            'bits': self.state.bits.copy(),
            'organizations': [set(org) for org in self.state.organizations],
            'energy': self.energy_manager.state.energy if self.energy_manager else 0.0,
            'entropy': self.entropy_tracker.state.entropy if self.entropy_tracker else 0.0
        }
        # Include open system stats even when sealed
        if self.open_system:
            metrics['open_system'] = self.open_system.get_summary()
        return metrics
    
    def _mechanism_m1_differentiate(self, bits: np.ndarray) -> np.ndarray:
        """m1: Create differences (random bit flips)."""
        new_bits = bits.copy()
        
        # Simple differentiation: flip 1-2 random bits
        n_flips = np.random.randint(1, 3)
        flip_indices = np.random.choice(len(bits), size=n_flips, replace=False)
        new_bits[flip_indices] = ~new_bits[flip_indices]
        
        return new_bits
    
    def _mechanism_m2_cluster(self, bits: np.ndarray, orgs: List[set]) -> List[set]:
        """m2: Form clusters (organizations)."""
        # Simplified: if no organizations, create based on bit values
        if not orgs:
            # Create organizations based on contiguous True bits
            indices = np.where(bits)[0]
            if len(indices) > 0:
                orgs = [set([i]) for i in indices[:self.config.min_org_size]]
        
        return orgs
    
    def _mechanism_m3_conserve(self, bits: np.ndarray, orgs: List[set]) -> float:
        """m3: Conservation (preserve differences). Returns conservation score."""
        # Simplified: count how many bits match previous state
        if not hasattr(self, '_prev_bits'):
            self._prev_bits = bits.copy()
            return 1.0
        
        matches = np.sum(bits == self._prev_bits)
        self._prev_bits = bits.copy()
        
        return matches / len(bits)
    
    def _mechanism_m4_stabilize(self, bits: np.ndarray, orgs: List[set]) -> np.ndarray:
        """m4: Stabilization (reduce noise)."""
        # Simplified: if bit has been stable for a while, keep it
        return bits  # No-op for now
    
    def _mechanism_m5_break_symmetry(self, bits: np.ndarray) -> np.ndarray:
        """m5: Symmetry breaking (create asymmetry)."""
        # Simplified: if all bits same, flip one
        if np.all(bits == bits[0]):
            new_bits = bits.copy()
            new_bits[0] = ~new_bits[0]
            return new_bits
        
        return bits
    
    def _mechanism_m6_check_stability(self, bits: np.ndarray, orgs: List[set]) -> bool:
        """m6: Check if system is stable."""
        # Simplified: stable if >50% bits unchanged from previous step
        if not hasattr(self, '_m6_prev_bits'):
            self._m6_prev_bits = bits.copy()
            return False
        
        unchanged = np.sum(bits == self._m6_prev_bits)
        self._m6_prev_bits = bits.copy()
        
        return (unchanged / len(bits)) > 0.5
    
    def _mechanism_m7_bind(self, bits: np.ndarray, orgs: List[set]) -> List[Tuple]:
        """m7: Bind bits to organizations."""
        # Simplified: bind each bit to nearest organization
        bindings = []
        for i, bit in enumerate(bits):
            if bit and orgs:
                # Bind to first org (simplified)
                bindings.append((i, 0))
        
        return bindings
    
    def _mechanism_m8_encapsulate(self, bits: np.ndarray, orgs: List[set]) -> List[set]:
        """m8: Encapsulate organizations."""
        # Simplified: just return orgs as-is
        return orgs
    
    def _mechanism_m9_should_seal(self, bits: np.ndarray, orgs: List[set], is_stable: bool) -> bool:
        """m9: Check if should seal (self-referential closure)."""
        # Conditions for sealing:
        # 1. Has organizations
        # 2. Is stable
        # 3. Enough bits frozen
        
        if not orgs or not is_stable:
            return False
        
        # Check binding threshold
        n_bound = sum(1 for bit in bits if bit)
        return n_bound >= self.config.binding_threshold
    
    def _mechanism_m9_seal(self, bits: np.ndarray, orgs: List[set]) -> Dict:
        """m9: Perform sealing (self-referential closure)."""
        st = self.state
        
        # Create frozen bits (simplified: freeze 40% of bits)
        n_freeze = int(len(bits) * self.config.seal_threshold)
        freeze_indices = np.random.choice(len(bits), size=n_freeze, replace=False)
        st.frozen_bits = set(freeze_indices)
        
        return {
            'frozen_bits': st.frozen_bits.copy(),
            'n_frozen': len(st.frozen_bits),
            'seal_step': st.step
        }
    
    def _take_snapshot(self):
        """Take a snapshot of current state."""
        st = self.state
        
        snapshot = {
            'step': st.step,
            'bits': st.bits.copy(),
            'organizations': [set(org) for org in st.organizations],
            'is_sealed': st.is_sealed,
            'frozen_bits': st.frozen_bits.copy(),
            'energy': self.energy_manager.state.energy if self.energy_manager else 0.0,
            'entropy': self.entropy_tracker.state.entropy if self.entropy_tracker else 0.0
        }
        
        st.snapshots.append(snapshot)
    
    def _collect_metrics(self, bits: np.ndarray, orgs: List[set],
                        energy_info: Optional[Dict], entropy_info: Optional[Dict],
                        open_system_info: Optional[Dict] = None) -> Dict:
        """Collect metrics for this step."""
        st = self.state
        
        metrics = {
            'step': st.step,
            'is_sealed': st.is_sealed,
            'seal_step': st.seal_step,
            'n_active_bits': int(np.sum(bits)),
            'n_organizations': len(orgs),
            'frozen_bits': st.frozen_bits.copy()
        }
        
        if energy_info:
            metrics['energy'] = energy_info
        
        if entropy_info:
            metrics['entropy'] = entropy_info
        
        if open_system_info:
            metrics['open_system'] = {
                'energy_injected': open_system_info['energy_injected'],
                'entropy_exhausted': open_system_info['entropy_exhausted'],
                'cumulative_injected': open_system_info.get('cumulative_injected', 0.0),
                'cumulative_exhausted': open_system_info.get('cumulative_exhausted', 0.0),
                'constraint': self.open_system.config.constraint_strength if self.open_system else None
            }
        
        return metrics
    
    def run(self, n_steps: Optional[int] = None) -> Dict:
        """
        Run simulation for n_steps or until sealed.
        
        Args:
            n_steps: Number of steps (uses config.max_steps if None)
        
        Returns:
            Final state dict
        """
        n_steps = n_steps or self.config.max_steps
        
        for i in range(n_steps):
            metrics = self.step()
            
            if self.state.is_sealed:
                break
        
        return self.get_summary()
    
    def get_summary(self) -> Dict:
        """Get summary of simulation."""
        st = self.state
        
        summary = {
            'total_steps': st.step,
            'is_sealed': st.is_sealed,
            'seal_step': st.seal_step,
            'n_snapshots': len(st.snapshots),
            'final_n_active_bits': int(np.sum(st.bits)),
            'final_n_organizations': len(st.organizations)
        }
        
        if self.energy_manager:
            summary['energy'] = self.energy_manager.get_summary()
        
        if self.entropy_tracker:
            summary['entropy'] = self.entropy_tracker.get_summary()
        
        if self.open_system:
            summary['open_system'] = self.open_system.get_summary()
        
        return summary
