"""
engine/cross_layer_evolver.py — Cross-Layer Evolver for Phase 15 Path C

Architecture:
  L0: SpatialLongRangeEvolver (runs until sealing)
  L1: Layer1Evolver (independent N1 bits, constrained by L0 sealed structure)
  L0→L1 mapping: sealed clusters → L1 hierarchy groups

The core hypothesis: dead order is a topological invariant of the single-layer
world. By introducing a second layer with structurally constrained but
dynamically independent bits, L2 emergence may become possible.

Theory background:
  - Sealing = completed compression (Phase 13 P4)
  - Dead order = topological invariant (Phase 14 P4)
  - Cross-layer architecture = escaping the single-layer topology
"""

import torch
import numpy as np
from typing import List, Optional, Dict, Tuple, Set, Callable
from dataclasses import dataclass, field
import json

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver, SpatialSnapshot
from acl.axioms_v2 import AxiomConstraints


# =============================================================================
# L1Constraints: constraint bundle from L0 → L1
# =============================================================================

@dataclass
class L1Constraints:
    """Constraint bundle passed from L0 to L1.

    Attributes:
        hierarchy_map: List[int] of length N1, each entry = cluster_id or -1 (lateral)
        binding_bias: Tensor (N1,) initial binding strength per bit (from cluster cohesion)
        direction_preference: Tensor (N1,) preferred flip direction (from L0 direction field)
        cluster_sizes: Dict[int, int] mapping cluster_id → number of bits in L0
        sealed_hw: int Hamming weight of L0 at seal time
        seal_step: int step at which L0 sealed
    """
    hierarchy_map: List[int]
    binding_bias: torch.Tensor
    direction_preference: torch.Tensor
    cluster_sizes: Dict[int, int]
    sealed_hw: int
    seal_step: int


# =============================================================================
# CrossLayerMapper
# =============================================================================

class CrossLayerMapper:
    """Maps L0 sealed structure → L1 constraint conditions.

    Mapping rules (from phase15_planning_v1.md Section 3.2.2):
    1. Each L0 cluster → one hierarchy group in L1
    2. Cluster size → number of hierarchy bits in L1 group
    3. Unsealed L0 bits → lateral bits in L1 (template)
    4. Direction field → L1 direction preference
    """

    def __init__(self, N0: int, N1: int, device: str = "cpu"):
        self.N0 = N0
        self.N1 = N1
        self.device = device

    def map_from_l0_result(
        self,
        l0_evolver: SpatialLongRangeEvolver,
        l0_result: Dict,
    ) -> L1Constraints:
        """Extract L1 constraints from L0 evolution result.

        Args:
            l0_evolver: the L0 evolver object (has .constraints, .seal_step, etc.)
            l0_result: dict returned by l0_evolver.run()

        Returns:
            L1Constraints object
        """
        N0 = self.N0
        N1 = self.N1
        device = self.device

        final_state = l0_result['final_state']
        seal_step = l0_evolver.seal_step if l0_evolver.seal_step >= 0 else 0

        # ── 1. Get cluster info from L0 result ──
        # l0_result['clusters'] is a LIST OF LISTS (each sublist = one cluster)
        raw_clusters = l0_result.get('clusters', [])
        # Convert to {cluster_id: Set[int]} format
        clusters = {}
        for cid, cbits in enumerate(raw_clusters):
            clusters[cid] = set(cbits)
        n_clusters = len(clusters)

        # Also get all sealed bit indices (flat set)
        sealed_bits = set()
        for cbits in clusters.values():
            sealed_bits.update(cbits)
        n_sealed = len(sealed_bits)

        if n_clusters == 0:
            # No clusters — treat all as one cluster
            clusters = {0: set(range(N0))}
            sealed_bits = set(range(N0))
            n_sealed = N0
            n_clusters = 1

        # ── 2. Map clusters → L1 hierarchy groups ──
        hierarchy_map = [-1] * N1  # -1 = lateral bit (no cluster assignment)

        cluster_ids = sorted(clusters.keys())
        cluster_sizes = {}
        total_clustered = sum(len(bits) for bits in clusters.values())

        # Allocate L1 hierarchy bits proportionally, but cap TOTAL at N1//3
        # (leave 2/3 for lateral bits, matching SpatialLongRangeEvolver default)
        max_hierarchy = max(1, N1 // 3)
        raw_allocs = {}
        for cid in cluster_ids:
            cbits = clusters[cid]
            cluster_sizes[cid] = len(cbits)
            # Proportional allocation (floating point)
            raw = N1 * len(cbits) / max(total_clustered, 1)
            raw_allocs[cid] = max(1.0, raw)  # at least 1 bit per cluster

        total_raw = sum(raw_allocs.values())
        # Scale to fit within max_hierarchy
        if total_raw > max_hierarchy:
            scale = max_hierarchy / total_raw
            allocs = {cid: max(1, int(round(v * scale))) for cid, v in raw_allocs.items()}
        else:
            allocs = {cid: int(round(v)) for cid, v in raw_allocs.items()}

        # Make sure total doesn't exceed max_hierarchy (adjust rounding errors)
        total_alloc = sum(allocs.values())
        while total_alloc > max_hierarchy:
            # Remove 1 from the largest cluster allocation
            largest_cid = max(allocs, key=allocs.get)
            allocs[largest_cid] = max(1, allocs[largest_cid] - 1)
            total_alloc = sum(allocs.values())

        l1_idx = 0
        for cid in cluster_ids:
            n_bits = allocs.get(cid, 0)
            for i in range(n_bits):
                if l1_idx < N1:
                    hierarchy_map[l1_idx] = cid
                    l1_idx += 1

        # ── 3. Compute binding_bias and direction_preference ──
        binding_bias = torch.zeros(N1, device=device, dtype=torch.float32)
        direction_preference = torch.zeros(N1, device=device, dtype=torch.float32)

        l0_direction = l0_evolver.constraints.direction.clone()  # (N0,)

        for i in range(N1):
            cid = hierarchy_map[i]
            if cid >= 0:
                # This L1 bit belongs to a cluster
                binding_bias[i] = min(1.0, cluster_sizes[cid] / max(N0, 1) * 2.0)
                # Direction: average of L0 direction values in this cluster
                if cid in clusters:
                    dir_vals = [l0_direction[b].item() for b in clusters[cid] if b < N0]
                    if dir_vals:
                        direction_preference[i] = float(np.mean(dir_vals))
            else:
                # Lateral bit — lower binding
                binding_bias[i] = 0.1
                direction_preference[i] = 0.0

        # Clamp
        binding_bias.clamp_(0.0, 1.0)
        direction_preference.clamp_(-1.0, 1.0)

        return L1Constraints(
            hierarchy_map=hierarchy_map,
            binding_bias=binding_bias,
            direction_preference=direction_preference,
            cluster_sizes=cluster_sizes,
            sealed_hw=int(final_state.sum().item()),
            seal_step=seal_step,
        )


# =============================================================================
# Layer1Evolver
# =============================================================================

class Layer1Evolver:
    """L1 evolver: independent bit space constrained by L0 sealed structure.

    Key differences from plain SpatialLongRangeEvolver:
    1. Initial state biased by L0 direction preferences
    2. Binding strengths initialized from L0 cluster cohesion
    3. Step callback applies L0-derived constraints as soft nudges
    """

    def __init__(
        self,
        N1: int = 48,
        total_steps: int = 5000,
        sample_interval: int = 100,
        device: str = "cpu",
        l0_constraints: Optional[L1Constraints] = None,
        feedback_from_l0: bool = False,
    ):
        self.N1 = N1
        self.total_steps = total_steps
        self.sample_interval = sample_interval
        self.device = device
        self.l0_constraints = l0_constraints
        self.feedback_from_l0 = feedback_from_l0

        # Count hierarchy bits from constraints
        n_hierarchy = 0
        if l0_constraints:
            n_hierarchy = len([x for x in l0_constraints.hierarchy_map if x >= 0])
            n_hierarchy = max(1, n_hierarchy)
        else:
            n_hierarchy = N1 // 3

        self.evolve = SpatialLongRangeEvolver(
            N=N1,
            total_steps=total_steps,
            sample_interval=sample_interval,
            device=device,
            n_hierarchy_bits=n_hierarchy,
        )

        # Apply L0 constraints
        if l0_constraints is not None:
            self._apply_constraints(l0_constraints)

        # Results
        self.l1_sealed = False
        self.l1_seal_step = -1
        self.l1_final_state = None
        self.l1_snapshots: List[SpatialSnapshot] = []
        self.l1_result: Optional[Dict] = None
        self._initial_state: Optional[torch.Tensor] = None

    def _apply_constraints(self, constraints: L1Constraints):
        """Apply L0-derived constraints to L1 evolver.

        Stores:
        - _initial_state: biased init state (set before run())
        - _binding_bias, _direction_pref: for step_callback nudges
        - _constraint_callback: installed as step_callback in run()
        """
        N1 = self.N1
        device = self.device

        # ── 1. Compute initial state bias ──
        pref = constraints.direction_preference  # (N1,)
        init_state = torch.zeros(N1, device=device, dtype=torch.float32)

        # Pick bits with strongest |preference| as initial 1s (sparse)
        n_init = max(1, N1 // 3)
        if pref.abs().max().item() > 0:
            _, top_idx = torch.topk(pref.abs(), min(n_init, N1))
            for idx in top_idx:
                idx_i = idx.item()
                init_state[idx_i] = 1.0 if pref[idx_i] > 0 else 0.0
            # Ensure at least some 1s
            if init_state.sum() == 0:
                init_state[0] = 1.0
        else:
            init_state[0] = 1.0

        self._initial_state = init_state

        # ── 2. Store for step_callback use ──
        self._binding_bias = constraints.binding_bias.clone().to(device)
        self._direction_pref = constraints.direction_preference.clone().to(device)
        self._hierarchy_map = constraints.hierarchy_map.copy()

    def run(self) -> Dict:
        """Run L1 evolution with L0 constraints.

        Returns:
            Dict with keys: sealed, seal_step, final_state, snapshots, etc.
        """
        ev = self.evolve
        init = getattr(self, '_initial_state', None)
        cb = getattr(self, '_constraint_callback', None)

        result = ev.run(
            initial_state=init,
            verbose=True,
            step_callback=cb,
        )

        self.l1_result = result
        self.l1_snapshots = result.get('snapshots', [])
        self.l1_final_state = result.get('final_state', None)
        self.l1_sealed = result.get('sealed', False)
        self.l1_seal_step = ev.seal_step

        return {
            'sealed': self.l1_sealed,
            'seal_step': self.l1_seal_step,
            'final_state': self.l1_final_state,
            'snapshots': self.l1_snapshots,
            'hw_history': result.get('hamming_weight_history', []),
            'n_steps': len(self.l1_snapshots),
            'l0_constraints': self.l0_constraints,
        }

    def _install_constraint_callback(self):
        """Install step callback that nudges L1 evolution toward L0 constraints.

        Called by run() — the callback is passed to evolver.run(step_callback=...).
        """
        _binding_bias = self._binding_bias
        _direction_pref = self._direction_pref

        def _l1_constraint_callback(step, state, snapshot, constraints_obj):
            """Called at each sample interval.

            Softly nudges:
            - binding_strength: toward L0-derived values
            - direction: toward L0 direction preferences
            """
            alpha = 0.05  # nudge rate per sample interval
            n = min(len(_binding_bias), constraints_obj.N)
            if n > 0:
                constraints_obj.binding_strength[:n] = (
                    (1 - alpha) * constraints_obj.binding_strength[:n]
                    + alpha * _binding_bias[:n].to(constraints_obj.binding_strength.device)
                )

            # Nudge direction for bits with strong L0 preference
            for i in range(min(n, constraints_obj.N)):
                dp = _direction_pref[i].item()
                if abs(dp) > 0.3:
                    cur_dir = constraints_obj.direction[i].item()
                    if dp > 0:
                        constraints_obj.direction[i] = max(cur_dir, 0.3)
                    else:
                        constraints_obj.direction[i] = min(cur_dir, -0.3)

        self._constraint_callback = _l1_constraint_callback


# =============================================================================
# CrossLayerEvolver: top-level orchestrator
# =============================================================================

class CrossLayerEvolver:
    """Top-level orchestrator for L0→L1 cross-layer evolution (Phase 15 Path C).

    Flow:
    1. Run L0 (SpatialLongRangeEvolver) until sealing
    2. Extract L0 sealed structure → L1 constraints (CrossLayerMapper)
    3. Run L1 (Layer1Evolver) with L0 constraints
    4. Analyze: did L1 produce structurally non-random sealing?

    Success indicators:
    - L1 seals with pattern reflecting L0 constraints (not random)
    - L1 hamming weight trajectory differs from baseline L0-only run
    """

    def __init__(
        self,
        N0: int = 48,
        N1: int = 48,
        L0_steps: int = 5000,
        L1_steps: int = 5000,
        sample_interval: int = 100,
        device: str = "cpu",
        l0_config: Optional[Dict] = None,
        l1_config: Optional[Dict] = None,
        enable_l0_feedback: bool = False,
    ):
        self.N0 = N0
        self.N1 = N1
        self.L0_steps = L0_steps
        self.L1_steps = L1_steps
        self.sample_interval = sample_interval
        self.device = device
        self.enable_l0_feedback = enable_l0_feedback

        self.l0_config = l0_config or {}
        self.l1_config = l1_config or {}

        # Components
        self.mapper = CrossLayerMapper(N0=N0, N1=N1, device=device)
        self.l0_evolver: Optional[SpatialLongRangeEvolver] = None
        self.l1_evolver: Optional[Layer1Evolver] = None

        # Results
        self.l0_result: Optional[Dict] = None
        self.l1_result: Optional[Dict] = None
        self.l1_constraints: Optional[L1Constraints] = None

    def run(self) -> Dict:
        """Execute full L0→L1 cross-layer evolution."""
        # ── Phase 1: Run L0 until sealing ──
        print(f"[CrossLayer] Phase 1: Running L0 (N={self.N0}, steps={self.L0_steps})")
        self.l0_evolver = SpatialLongRangeEvolver(
            N=self.N0,
            total_steps=self.L0_steps,
            sample_interval=self.sample_interval,
            device=self.device,
            **self.l0_config,
        )
        self.l0_result = self.l0_evolver.run()

        l0_sealed = self.l0_result.get('sealed', False)
        l0_seal_step = self.l0_evolver.seal_step
        print(f"[CrossLayer] L0 sealed: {l0_sealed} at step {l0_seal_step}")

        if not l0_sealed:
            print("[CrossLayer] L0 did not seal — cannot proceed to L1")
            return {
                'l0_result': self.l0_result,
                'l0_sealed': False,
                'l0_seal_step': l0_seal_step,
                'l1_result': None,
                'l1_sealed': False,
                'l1_seal_step': -1,
                'error': 'L0 did not seal',
            }

        # ── Phase 2: Map L0 → L1 constraints ──
        print("[CrossLayer] Phase 2: Mapping L0 structure → L1 constraints")
        self.l1_constraints = self.mapper.map_from_l0_result(
            l0_evolver=self.l0_evolver,
            l0_result=self.l0_result,
        )
        n_clusters = len(self.l1_constraints.cluster_sizes)
        sealed_hw = self.l1_constraints.sealed_hw
        print(f"[CrossLayer] L1 constraints built: {n_clusters} clusters, HW={sealed_hw}")

        # ── Phase 3: Run L1 with constraints ──
        print(f"[CrossLayer] Phase 3: Running L1 (N={self.N1}, steps={self.L1_steps})")
        self.l1_evolver = Layer1Evolver(
            N1=self.N1,
            total_steps=self.L1_steps,
            sample_interval=self.sample_interval,
            device=self.device,
            l0_constraints=self.l1_constraints,
            feedback_from_l0=self.enable_l0_feedback,
        )
        # Install constraint callback before run
        self.l1_evolver._install_constraint_callback()
        self.l1_result = self.l1_evolver.run()

        # ── Phase 4 (optional): L0 feedback from L1 ──
        l1_sealed = self.l1_result.get('sealed', False) if self.l1_result else False
        if self.enable_l0_feedback and l1_sealed:
            print("[CrossLayer] Phase 4: Applying L1→L0 feedback")
            self._apply_l1_feedback()

        return self._compile_results()

    def _apply_l1_feedback(self):
        """Apply L1 sealing as L0 perturbation."""
        if self.l0_evolver is None or self.l1_result is None:
            return

        l1_final = self.l1_result.get('final_state')
        if l1_final is None:
            return

        # Perturb a small number of L0 bits
        n_perturb = max(1, self.N0 // 10)
        perturb_indices = torch.randperm(self.N0, device=self.device)[:n_perturb]

        with torch.no_grad():
            # Access L0 state via the constraints object
            if hasattr(self.l0_evolver.constraints, '_state'):
                state = self.l0_evolver.constraints._state
            elif hasattr(self.l0_evolver.constraints, 'state'):
                state = self.l0_evolver.constraints.state
            else:
                # Falback: try to get state from l0_result
                state = self.l0_result.get('final_state') if self.l0_result else None
            if state is not None:
                perturb_indices = perturb_indices.to(state.device)
                state[perturb_indices] = 1.0 - state[perturb_indices]
                print(f"[CrossLayer] L1→L0 feedback: perturbed {n_perturb} L0 bits")

    def _compile_results(self) -> Dict:
        """Compile cross-layer results for analysis."""
        results = {
            'l0_sealed': self.l0_result.get('sealed', False) if self.l0_result else False,
            'l1_sealed': self.l1_result.get('sealed', False) if self.l1_result else False,
            'l0_seal_step': self.l0_evolver.seal_step if self.l0_evolver else -1,
            'l1_seal_step': self.l1_result.get('seal_step', -1) if self.l1_result else -1,
            'n0': self.N0,
            'n1': self.N1,
        }

        # L0 metrics
        if self.l0_result:
            results['l0_hw_history'] = self.l0_result.get('hamming_weight_history', [])
            results['l0_n_snapshots'] = len(self.l0_result.get('snapshots', []))

        # L1 metrics
        if self.l1_result:
            results['l1_hw_history'] = self.l1_result.get('hw_history', [])
            results['l1_n_steps'] = self.l1_result.get('n_steps', 0)

        # Cross-layer metrics
        if self.l1_constraints is not None:
            results['n_clusters'] = len(self.l1_constraints.cluster_sizes)
            results['l0_hw_at_seal'] = self.l1_constraints.sealed_hw
            results['hierarchy_map'] = self.l1_constraints.hierarchy_map

            # L1 structure analysis
            l1_hw = self.l1_result.get('hw_history', []) if self.l1_result else []
            if l1_hw:
                results['l1_hw_final'] = l1_hw[-1] if l1_hw else 0
                results['l1_hw_variance'] = float(
                    torch.tensor(l1_hw, dtype=torch.float32).var()
                )

        return results

    def save_results(self, filepath: str):
        """Save results to JSON file."""
        results = self._compile_results()
        # Convert to JSON-serializable types
        if 'l1_hw_history' in results:
            results['l1_hw_history'] = list(results['l1_hw_history'])
        if 'l0_hw_history' in results:
            results['l0_hw_history'] = list(results['l0_hw_history'])
        if 'hierarchy_map' in results:
            results['hierarchy_map'] = list(results['hierarchy_map'])
        # Remove non-serializable
        results.pop('l0_result', None)
        results.pop('l1_result', None)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"[CrossLayer] Results saved to {filepath}")


# =============================================================================
# CLI / Smoke test
# =============================================================================

if __name__ == "__main__":
    print("=== CrossLayerEvolver Smoke Test ===")
    ev = CrossLayerEvolver(
        N0=48,
        N1=48,
        L0_steps=5000,
        L1_steps=5000,
        device="cpu",
    )
    results = ev.run()
    print(f"L0 sealed: {results.get('l0_sealed')} at step {results.get('l0_seal_step')}")
    print(f"L1 sealed: {results.get('l1_sealed')} at step {results.get('l1_seal_step')}")
    print(f"N clusters: {results.get('n_clusters', 'N/A')}")
    print("=== Test Complete ===")
