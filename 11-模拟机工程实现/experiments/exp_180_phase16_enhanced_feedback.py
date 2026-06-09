"""
exp_180_phase16_enhanced_feedback.py -- Phase 16 Path D2: Enhanced Cross-layer Feedback

Hypothesis H16-D2: Enhanced cross-layer feedback (beyond simple perturbation) enables
L2 emergence that is structurally non-trivial.

Three enhanced feedback types (beyond D1's basic perturbation):
  1. CONSTRAINT MODULATION:  L1→L0 adjusts binding_strength, direction, hw_target
  2. TRANSITION MATRIX:      L2→L1 modulates comparison matrix based on L2 entropy
  3. TOPOLOGY REORGANIZATION: L1 sealed clusters create long-range connections in L0

Configs (5):
  d2_baseline:      Only basic perturbation [control]
  d2_constraint:    Constraint modulation (binding + direction)
  d2_matrix:        Transition matrix modulation
  d2_topology:      Topology reorganization (dynamic)
  d2_full:          All three combined

Usage:
    python exp_180_phase16_enhanced_feedback.py [--config d2_constraint] [--n_runs 5]
    python exp_180_phase16_enhanced_feedback.py --all_configs --n_runs 5
"""

import sys
import os
import json
import time
import math
import random as _random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.spatial_evolver_v2 import SpatialLongRangeEvolver, SpatialSnapshot
from engine.cross_layer_evolver import CrossLayerMapper, Layer1Evolver, L1Constraints
from acl.axioms_v2 import AxiomConstraints


# =========================================================================
# Utility functions (adapted from exp_179)
# =========================================================================

def _compute_binary_entropy(state: torch.Tensor) -> float:
    p = state.mean().item()
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def _coords_3d_approx(state, N):
    w = state.sum().item() if state.numel() > 0 else 0
    return np.array([w / max(N, 1), 0.0, 0.0], dtype=np.float32)


def _spatial_source_weights_simple(evolver, state):
    try:
        return evolver._spatial_source_weights(state)
    except Exception:
        return torch.ones(evolver.N)


def _spatial_sink_weights_simple(evolver, state):
    try:
        return evolver._spatial_sink_weights(state)
    except Exception:
        return torch.ones(evolver.N)


def _step_layer(evolver: SpatialLongRangeEvolver,
                state: torch.Tensor,
                step: int,
                sample_interval: int = 100,
                step_callback: Optional[callable] = None) -> Dict:
    """Execute ONE evolution step, mutating state and constraints in-place."""
    constraints = evolver.constraints

    # Sealing trigger
    if constraints.sealed and not getattr(evolver, '_seal_triggered', False):
        evolver._seal_triggered = True
        if evolver.seal_step < 0:
            evolver.seal_step = step
        if getattr(evolver, 'post_seal_config', None):
            cfg = evolver.post_seal_config
            if 'source_multiplier' in cfg:
                evolver._source_multiplier = cfg['source_multiplier']

    # 1. Source injection
    source_strength = constraints.get_A8_source_strength(state)
    if getattr(evolver, '_source_multiplier', 1.0) != 1.0:
        source_strength = max(1, int(source_strength * evolver._source_multiplier))
    actual_inject = 0
    n_inject = 0
    if source_strength > 0:
        h_candidates = [i for i in constraints.hierarchy_indices
                        if state[i] < 0.5 and constraints.direction[i].item() >= 0]
        l_candidates = [i for i in constraints.lateral_indices
                        if state[i] < 0.5 and constraints.direction[i].item() >= 0]
        all_candidates = h_candidates + l_candidates
        if all_candidates:
            n_inject = min(source_strength, len(all_candidates))
            ok, _ = constraints.check_A5_inject(state, n_inject)
            if ok:
                spatial_w = _spatial_source_weights_simple(evolver, state)
                candidate_weights = spatial_w[all_candidates]
                candidate_weights = candidate_weights / candidate_weights.sum()
                n_choose = min(n_inject, len(all_candidates))
                indices = torch.multinomial(candidate_weights, n_choose, replacement=False)
                chosen = [all_candidates[idx.item()] for idx in indices]
                for idx in chosen:
                    a9_ok, _ = constraints.check_A9(idx, partial_sealing=evolver.partial_sealing)
                    if not a9_ok:
                        continue
                    state[idx] = 1.0
                    constraints.record_inject(1)
                    constraints.record_active(idx)
                    constraints.direction[idx] = 1
                    actual_inject += 1

    # 2. Internal flip
    flip_idx = -1
    allowed = constraints.get_allowed_flips(state)
    if allowed:
        weights = constraints.get_A8_weights(state)
        allowed_weights = weights[allowed]
        allowed_weights = allowed_weights / allowed_weights.sum()
        flip_idx = allowed[torch.multinomial(allowed_weights, 1).item()]
        a9_ok, _ = constraints.check_A9(flip_idx, partial_sealing=evolver.partial_sealing)
        if a9_ok:
            old_val = state[flip_idx].item()
            state[flip_idx] = 1.0 - state[flip_idx]
            new_val = state[flip_idx].item()
            constraints.update_A6_direction(flip_idx, old_val, new_val)
            constraints.record_active(flip_idx)
        else:
            flip_idx = -1

    # 3. Lateral evolution
    lateral_pairs = constraints.get_A1_prime_candidates(state)
    n_lateral = 0
    for (i, j) in lateral_pairs:
        if state[i] > 0.5 and state[j] < 0.5:
            a9_ok_i, _ = constraints.check_A9(i, partial_sealing=evolver.partial_sealing)
            a9_ok_j, _ = constraints.check_A9(j, partial_sealing=evolver.partial_sealing)
            if not a9_ok_i or not a9_ok_j:
                continue
            state[i] = 0.0
            state[j] = 1.0
            constraints.update_A6_direction(i, 1.0, 0.0)
            constraints.update_A6_direction(j, 0.0, 1.0)
            constraints.record_active(i)
            constraints.record_active(j)
            constraints.strengthen_binding(i, j, amount=0.1)
            n_lateral += 1

    # 4. Absorb
    sink_strength = constraints.get_A8_sink_strength(state, n_inject)
    n_absorb = 0
    if sink_strength > 0:
        allowed_abs = constraints.get_allowed_absorbs(state)
        lateral_abs = [i for i in allowed_abs if i in constraints.lateral_indices]
        hierarchy_abs = [i for i in allowed_abs if i in constraints.hierarchy_indices]
        absorb_targets = lateral_abs + hierarchy_abs
        n_absorb = min(sink_strength, len(absorb_targets))
        if n_absorb > 0:
            ok, _ = constraints.check_A5_absorb(state, n_absorb)
            if ok:
                spatial_w = _spatial_sink_weights_simple(evolver, state)
                if len(absorb_targets) <= n_absorb:
                    chosen = absorb_targets
                else:
                    target_weights = spatial_w[absorb_targets]
                    target_weights = target_weights / target_weights.sum()
                    n_choose = min(n_absorb, len(absorb_targets))
                    indices = torch.multinomial(target_weights, n_choose, replacement=False)
                    chosen = [absorb_targets[idx.item()] for idx in indices]
                for idx in chosen:
                    state[idx] = 0.0
                    constraints.record_absorb(1)
                    if idx in constraints.lateral_indices:
                        constraints.direction[idx] = 0
                    else:
                        constraints.direction[idx] = -1

    # 5. A7 cycle check
    constraints.check_A7(state)

    # 6. Record
    w_after = state.sum().long().item()
    evolver.hamming_weight_history.append(w_after)
    evolver.inject_history.append(actual_inject)
    evolver.absorb_history.append(n_absorb)
    evolver.lateral_history.append(n_lateral)

    # 7. Snapshot
    snapshot = None
    if step % sample_interval == 0:
        coords_3d = _coords_3d_approx(state, evolver.N)
        snapshot = SpatialSnapshot(
            step=step, state=state, flip_idx=flip_idx,
            n_inject=n_inject, n_absorb=n_absorb,
            n_lateral=n_lateral, w=w_after,
            coords_3d=coords_3d,
        )
        evolver.snapshots.append(snapshot)
        constraints.set_current_step(step)
        if step_callback:
            step_callback(step, state, snapshot, constraints)

    return {'flip_idx': flip_idx, 'n_inject': actual_inject, 'n_absorb': n_absorb,
            'n_lateral': n_lateral, 'hw': w_after, 'snapshot': snapshot}


# =========================================================================
# Live cross-layer mapping (adapted from exp_179)
# =========================================================================

def live_map_state_to_l1_constraints(
    l0_state: torch.Tensor,
    l0_constraints: AxiomConstraints,
    N1: int,
    l0_N: int,
) -> L1Constraints:
    """Build L1 constraints from L0's current (evolving) state."""
    device = l0_state.device

    # Get clusters
    try:
        raw_clusters = l0_constraints.get_clusters()
        clusters = {}
        for cid, cbits in enumerate(raw_clusters):
            clusters[cid] = set(int(b) for b in cbits)
    except Exception:
        active_mask = l0_state > 0.5
        active_indices = active_mask.nonzero(as_tuple=True)[0]
        clusters = {}
        if len(active_indices) > 1:
            sorted_idx = sorted(active_indices.tolist())
            chunk = max(1, len(sorted_idx) // 3)
            for cid in range(3):
                start = cid * chunk
                end = (cid + 1) * chunk if cid < 2 else len(sorted_idx)
                clusters[cid] = set(sorted_idx[start:end])
        elif len(active_indices) == 1:
            clusters[0] = {int(active_indices[0])}
        else:
            clusters[0] = set()

    sealed_bits = set()
    for cbits in clusters.values():
        sealed_bits.update(cbits)
    n_sealed = len(sealed_bits)

    if n_sealed == 0:
        clusters = {0: set(range(min(8, l0_N)))}
        sealed_bits = set(range(min(8, l0_N)))

    # Allocate L1 hierarchy bits
    hierarchy_map = [-1] * N1
    max_hierarchy = max(1, N1 // 4)
    cluster_ids = sorted(clusters.keys())
    cluster_sizes = {}
    total_clustered = sum(len(bits) for bits in clusters.values())

    raw_allocs = {}
    for cid in cluster_ids:
        cbits = clusters[cid]
        cluster_sizes[cid] = len(cbits)
        raw_allocs[cid] = max(1.0, N1 * len(cbits) / max(total_clustered, 1))

    total_raw = sum(raw_allocs.values())
    if total_raw > max_hierarchy:
        scale = max_hierarchy / total_raw
        allocs = {cid: max(1, int(round(v * scale))) for cid, v in raw_allocs.items()}
    else:
        allocs = {cid: int(round(v)) for cid, v in raw_allocs.items()}

    total_alloc = sum(allocs.values())
    while total_alloc > max_hierarchy:
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

    # Binding bias (live: weaker than post-seal, scaled by L0 structure)
    binding_bias = torch.zeros(N1, device=device, dtype=torch.float32)
    direction_preference = torch.zeros(N1, device=device, dtype=torch.float32)

    l0_hw_ratio = l0_state.sum().item() / max(l0_N, 1)
    live_strength = 0.3 + 0.4 * l0_hw_ratio

    for i in range(N1):
        cid = hierarchy_map[i]
        if cid >= 0 and cid in clusters:
            cluster_size = cluster_sizes.get(cid, 1)
            binding_bias[i] = min(live_strength, cluster_size / max(l0_N, 1) * 3.0)
            cluster_bits = list(clusters.get(cid, set()))
            if cluster_bits:
                dir_vals = [l0_constraints.direction[b].item()
                            for b in cluster_bits if b < l0_N]
                if dir_vals:
                    direction_preference[i] = float(np.mean(dir_vals))
        else:
            binding_bias[i] = 0.1
            direction_preference[i] = 0.0

    binding_bias.clamp_(0.0, 1.0)
    direction_preference.clamp_(-1.0, 1.0)

    return L1Constraints(
        hierarchy_map=hierarchy_map,
        binding_bias=binding_bias,
        direction_preference=direction_preference,
        cluster_sizes=cluster_sizes,
        sealed_hw=int(l0_state.sum().item()),
        seal_step=0,
    )


# =========================================================================
# Enhanced feedback mechanisms (NEW for exp_180)
# =========================================================================

def apply_constraint_modulation(
    src_state: torch.Tensor,
    src_constraints,
    dst_constraints,
    dst_state: torch.Tensor,
    strength: float = 0.05,
):
    """ENHANCED FEEDBACK TYPE 1: L1→L0 constraint modulation.

    Instead of just flipping bits, modulate the constraint parameters of L0
    based on L1's structure:
      - binding_strength: L1 activated bits increase binding in corresponding rows
      - direction: L1 structure biases direction preference
      - hw_target: L1 HW ratio nudges source/sink balance
    """
    if strength <= 0 or src_state.numel() == 0:
        return 0

    n_modulated = 0
    N_dst = dst_state.numel()
    src_ratio = src_state.sum().item() / max(src_state.numel(), 1)

    # 1a. Modulate binding_strength (48x48 pairwise matrix)
    # Increase binding for rows corresponding to active src bits
    src_active = (src_state > 0.5).nonzero(as_tuple=True)[0]
    if len(src_active) > 0:
        n_strengthen = min(len(src_active), max(1, int(N_dst * strength * 0.5)))
        for i in range(n_strengthen):
            src_idx = src_active[i % len(src_active)].item()
            dst_idx = src_idx % N_dst
            # binding_strength is (48,48) matrix - modulate row probability
            row = dst_constraints.binding_strength[dst_idx]
            delta = strength * 0.3 * (1.0 - row.abs().mean().item())
            # Strengthen binding to all connected bits
            dst_constraints.binding_strength[dst_idx] = row * (1.0 + delta)
            n_modulated += 1

    # 1b. Modulate direction preference
    dir_bias = (src_ratio - 0.5) * strength * 0.3
    if abs(dir_bias) > 0.01:
        n_dir = min(10, N_dst)
        dir_indices = torch.randperm(N_dst, device=dst_state.device)[:n_dir]
        for idx in dir_indices:
            cur = dst_constraints.direction[idx].item()
            dst_constraints.direction[idx] = max(-1.0, min(1.0, cur + dir_bias))
            n_modulated += 1

    # 1c. Modulate source multiplier
    src_entropy = _compute_binary_entropy(src_state)
    if src_entropy < 0.7 and src_ratio > 0.3:
        src_mult = 1.0 + strength * (1.0 - src_entropy) * 0.5
        cur_mult = getattr(dst_constraints, '_source_multiplier', 1.0)
        dst_constraints._source_multiplier = min(3.0, cur_mult * src_mult)
        n_modulated += 1

    return n_modulated


def apply_transition_matrix_modulation(
    src_state: torch.Tensor,
    dst_evolver: SpatialLongRangeEvolver,
    strength: float = 0.10,
):
    """ENHANCED FEEDBACK TYPE 2: L2→L1 transition matrix modulation.

    L2's structure entropy modulates L1's comparison matrix:
      - Low L2 entropy (highly structured) → L1 becomes more conservative (fewer flips)
      - High L2 entropy (chaotic) → L1 becomes more exploratory
    """
    if strength <= 0 or src_state.numel() == 0:
        return 0.0

    src_entropy = _compute_binary_entropy(src_state)
    # Modulation factor: [1-strength, 1+strength]
    # entropy 0 → modulation = 1 - strength (conservative)
    # entropy 1 → modulation = 1 + strength (exploratory)
    modulation = 1.0 + strength * (src_entropy - 0.5) * 2.0

    # Apply to comparison matrix scale factor if available
    try:
        dst_evolver._comparison_modulation = getattr(
            dst_evolver, '_comparison_modulation', 1.0) * modulation
    except Exception:
        pass

    return src_entropy


def apply_topology_reorganization(
    src_state: torch.Tensor,
    src_constraints,
    dst_evolver: SpatialLongRangeEvolver,
    step: int,
    strength: float = 0.10,
    max_connections: int = 5,
):
    """ENHANCED FEEDBACK TYPE 3: Topology reorganization.

    L1 sealed clusters create long-range connections in L0's interaction network.
    The number of connections grows over time.

    Returns number of connections created.
    """
    if strength <= 0 or src_state.numel() == 0:
        return 0, []

    n_connections = min(max_connections, max(1, step // 1000 + 1))
    n_connections = max(1, int(n_connections * strength))

    # Find activated clusters in source
    try:
        raw_clusters = src_constraints.get_clusters()
    except Exception:
        raw_clusters = []

    connections_created = []
    if raw_clusters:
        # Pick clusters with high activation
        active_clusters = []
        for cid, cbits in enumerate(raw_clusters):
            cbits_list = [int(b) for b in cbits]
            if cbits_list:
                active_ratio = sum(1 for b in cbits_list
                                   if b < src_state.numel() and src_state[b] > 0.5)
                active_ratio /= len(cbits_list)
                if active_ratio > 0.5:
                    active_clusters.append((cid, cbits_list, active_ratio))

        if len(active_clusters) >= 2:
            for _ in range(n_connections):
                # Pick two different clusters
                c1, c2 = _random.sample(active_clusters, 2) if len(active_clusters) >= 2 else (active_clusters[0], active_clusters[0])
                # Map cluster members to dst indices
                dst_N = dst_evolver.N
                src1 = _random.choice(c1[1]) % dst_N
                src2 = _random.choice(c2[1]) % dst_N
                if src1 != src2:
                    try:
                        dst_evolver.add_long_range_connection(src1, src2)
                        connections_created.append((src1, src2))
                    except Exception:
                        pass
    else:
        # Fallback: use random active bits
        active_bits = (src_state > 0.5).nonzero(as_tuple=True)[0]
        if len(active_bits) >= 2:
            dst_N = dst_evolver.N
            for _ in range(n_connections):
                idx1, idx2 = _random.sample(active_bits.tolist(), 2)
                src1, src2 = idx1 % dst_N, idx2 % dst_N
                if src1 != src2:
                    try:
                        dst_evolver.add_long_range_connection(src1, src2)
                        connections_created.append((src1, src2))
                    except Exception:
                        pass

    return len(connections_created), connections_created


# =========================================================================
# MultiLayerCoordinator (enhanced for D2)
# =========================================================================

class MultiLayerCoordinator:
    """Orchestrates parallel L0/L1/L2 evolution with ENHANCED cross-layer feedback.

    Extends exp_179's coordinator with three additional feedback mechanisms:
      - constraint_modulation
      - transition_matrix_modulation
      - topology_reorganization
    """

    def __init__(self,
                 N0=48, N1=48, N2=48,
                 t_lag_l1=50, t_lag_l2=150,
                 l1_update_interval=200, l2_update_interval=200,
                 feedback_alpha=0.05, total_steps=5000,
                 sample_interval=100, device="cpu",
                 config_name="default",
                 # Enhanced feedback params
                 constraint_mod_strength=0.0,
                 matrix_mod_strength=0.0,
                 topology_mod_strength=0.0,
                 ):
        """
        constraint_mod_strength: Strength of L1→L0 constraint modulation (type 1)
        matrix_mod_strength:     Strength of L2→L1 transition matrix modulation (type 2)
        topology_mod_strength:   Strength of L1→L0 topology reorganization (type 3)
        """
        self.N0 = N0
        self.N1 = N1
        self.N2 = N2
        self.t_lag_l1 = t_lag_l1
        self.t_lag_l2 = t_lag_l2
        self.l1_update_interval = l1_update_interval
        self.l2_update_interval = l2_update_interval
        self.feedback_alpha = feedback_alpha
        self.total_steps = total_steps
        self.sample_interval = sample_interval
        self.device = device
        self.config_name = config_name

        # Enhanced feedback strengths
        self.constraint_mod_strength = constraint_mod_strength
        self.matrix_mod_strength = matrix_mod_strength
        self.topology_mod_strength = topology_mod_strength

        self.l0_evolver = None
        self.l1_evolver = None
        self.l2_evolver = None
        self.l0_state = None
        self.l1_state = None
        self.l2_state = None
        self.l1_constraints = None
        self.l2_constraints = None

        self.l0_sealed = False
        self.l1_sealed = False
        self.l2_sealed = False
        self.l0_seal_step = -1
        self.l1_seal_step = -1
        self.l2_seal_step = -1
        self.l1_active = False
        self.l2_active = False

        self.l0_hw_history = []
        self.l1_hw_history = []
        self.l2_hw_history = []
        self.live_map_steps = []
        self._initialized = False

        # Feedback statistics (for analysis)
        self.constraint_mod_count = 0
        self.matrix_mod_entropies = []
        self.topology_connections_total = 0
        self.feedback_type_active = []  # track which types fired

    def _init_layers(self):
        self.l0_evolver = SpatialLongRangeEvolver(
            N=self.N0, total_steps=self.total_steps,
            sample_interval=self.sample_interval, device=self.device)
        self.l1_evolver = SpatialLongRangeEvolver(
            N=self.N1, total_steps=self.total_steps,
            sample_interval=self.sample_interval, device=self.device,
            n_hierarchy_bits=max(1, self.N1 // 3))
        self.l2_evolver = SpatialLongRangeEvolver(
            N=self.N2, total_steps=self.total_steps,
            sample_interval=self.sample_interval, device=self.device,
            n_hierarchy_bits=max(1, self.N2 // 3))

        self.l0_state = torch.zeros(self.N0, device=self.device)
        self.l1_state = torch.zeros(self.N1, device=self.device)
        self.l2_state = torch.zeros(self.N2, device=self.device)

        # L0 bootstrap: just 1 seed bit
        self.l0_state[0] = 1.0

        for ev in [self.l0_evolver, self.l1_evolver, self.l2_evolver]:
            ev.snapshots = []
            ev.hamming_weight_history = []
            ev.inject_history = []
            ev.absorb_history = []
            ev.lateral_history = []
            ev.flip_history = []
            ev.coords_history = []

        self._initialized = True

    def _seed_from_constraints(self, N, constraints: Optional[L1Constraints],
                               device):
        state = torch.zeros(N, device=device)
        if constraints is None:
            state[0] = 1.0
            return state
        pref = constraints.direction_preference.to(device)
        n_init = max(1, N // 4)
        if pref.abs().max().item() > 0:
            _, top_idx = torch.topk(pref.abs(), min(n_init, N))
            for idx in top_idx:
                state[idx] = 1.0 if pref[idx] > 0 else 0.0
        if state.sum() == 0:
            state[0] = 1.0
        return state

    def _apply_live_constraints(self, evolver, constraints: L1Constraints):
        N = evolver.N
        n = min(len(constraints.binding_bias), N)
        alpha = 0.1
        if n > 0:
            evolver.constraints.binding_strength[:n] = (
                (1 - alpha) * evolver.constraints.binding_strength[:n]
                + alpha * constraints.binding_bias[:n].to(
                    evolver.constraints.binding_strength.device))
        for i in range(min(n, N)):
            dp = constraints.direction_preference[i].item()
            if abs(dp) > 0.2:
                cur_dir = evolver.constraints.direction[i].item()
                evolver.constraints.direction[i] = max(cur_dir, 0.2) if dp > 0 else min(cur_dir, -0.2)

    def _make_l1_callback(self):
        """Create step_callback for L1 evolution that maintains L0 constraints."""
        l1_c = self.l1_constraints
        if l1_c is None:
            return None

        _binding_bias = l1_c.binding_bias.clone() if l1_c.binding_bias is not None else None
        _direction_pref = l1_c.direction_preference.clone() if l1_c.direction_preference is not None else None

        if _binding_bias is None:
            return None

        def _callback(step, state, snapshot, constraints_obj):
            n = min(len(_binding_bias), constraints_obj.N)
            if n > 0:
                alpha = 0.05
                constraints_obj.binding_strength[:n] = (
                    (1 - alpha) * constraints_obj.binding_strength[:n]
                    + alpha * _binding_bias[:n].to(constraints_obj.binding_strength.device))
            if _direction_pref is not None:
                for i in range(min(n, constraints_obj.N)):
                    dp = _direction_pref[i].item()
                    if abs(dp) > 0.3:
                        cur_dir = constraints_obj.direction[i].item()
                        constraints_obj.direction[i] = max(cur_dir, 0.3) if dp > 0 else min(cur_dir, -0.3)

        return _callback

    def _update_l1_mapping(self, step, verbose):
        if self.l0_state is None:
            return
        self.l1_constraints = live_map_state_to_l1_constraints(
            self.l0_state, self.l0_evolver.constraints, self.N1, self.N0)
        self._apply_live_constraints(self.l1_evolver, self.l1_constraints)
        self.live_map_steps.append(step)
        if verbose:
            nc = len(self.l1_constraints.cluster_sizes)
            hw = self.l0_state.sum().item()
            print(f"    Live L0→L1 map at step {step}: {nc} clusters, L0 HW={hw:.0f}")

    def _update_l2_mapping(self, step, verbose):
        if self.l1_state is None:
            return
        self.l2_constraints = live_map_state_to_l1_constraints(
            self.l1_state, self.l1_evolver.constraints, self.N2, self.N1)
        self._apply_live_constraints(self.l2_evolver, self.l2_constraints)
        if verbose:
            nc = len(self.l2_constraints.cluster_sizes)
            hw = self.l1_state.sum().item()
            print(f"    Live L1→L2 map at step {step}: {nc} clusters, L1 HW={hw:.0f}")

    def _check_sealing(self, evolver, layer_name, step):
        sealed = getattr(evolver.constraints, 'sealed', False)
        if sealed:
            if layer_name == 'l0' and not self.l0_sealed:
                self.l0_sealed = True
                self.l0_seal_step = step
            elif layer_name == 'l1' and not self.l1_sealed:
                self.l1_sealed = True
                self.l1_seal_step = step
            elif layer_name == 'l2' and not self.l2_sealed:
                self.l2_sealed = True
                self.l2_seal_step = step

    def _apply_enhanced_feedback(self, step: int, verbose: bool):
        """Apply all three enhanced feedback types based on config settings."""
        feedback_fired = []

        # TYPE 1: Constraint Modulation (L1→L0)
        if (self.constraint_mod_strength > 0 and self.l1_active
                and self.l1_state is not None and self.l0_state is not None):
            n_mod = apply_constraint_modulation(
                self.l1_state, self.l1_evolver.constraints,
                self.l0_evolver.constraints, self.l0_state,
                strength=self.constraint_mod_strength)
            self.constraint_mod_count += n_mod
            if n_mod > 0:
                feedback_fired.append('constraint')
            if verbose and n_mod > 0 and step % (self.sample_interval * 5) == 0:
                print(f"    [D2-CONSTRAINT] Modulated {n_mod} params @ step {step}")

        # TYPE 2: Transition Matrix Modulation (L2→L1)
        if (self.matrix_mod_strength > 0 and self.l2_active
                and self.l2_state is not None and self.l1_evolver is not None):
            l2_entropy = apply_transition_matrix_modulation(
                self.l2_state, self.l1_evolver,
                strength=self.matrix_mod_strength)
            self.matrix_mod_entropies.append(l2_entropy)
            feedback_fired.append('matrix')
            if verbose and step % (self.sample_interval * 5) == 0:
                print(f"    [D2-MATRIX] L2 entropy={l2_entropy:.4f}, mod applied @ step {step}")

        # TYPE 3: Topology Reorganization (L1→L0)
        if (self.topology_mod_strength > 0 and self.l1_active
                and self.l1_state is not None and self.l0_evolver is not None
                and step < 50):  # only during early active phase
            topo_src = self.l1_constraints if self.l1_constraints is not None else self.l1_state
            n_conn, conns = apply_topology_reorganization(
                self.l1_state, topo_src,
                self.l0_evolver, step,
                strength=self.topology_mod_strength,
                max_connections=3)
            self.topology_connections_total += n_conn
            if n_conn > 0:
                feedback_fired.append('topology')
            if verbose and n_conn > 0:
                print(f"    [D2-TOPOLOGY] Created {n_conn} connections @ step {step}")

        if feedback_fired:
            for fb in feedback_fired:
                if fb not in self.feedback_type_active:
                    self.feedback_type_active.append(fb)

    def run(self, verbose=True) -> Dict:
        """Run parallel multi-layer evolution with enhanced feedback."""
        if not self._initialized:
            self._init_layers()

        t_start = time.time()

        for step in range(self.total_steps):
            # Activate layers
            if not self.l1_active and step >= self.t_lag_l1:
                self.l1_active = True
                self._update_l1_mapping(step, verbose)
                self.l1_state = self._seed_from_constraints(
                    self.N1, self.l1_constraints, self.device)
                if verbose:
                    print(f"  Step {step}: L1 activated, HW={self.l1_state.sum().item():.0f}")

            if not self.l2_active and step >= self.t_lag_l2:
                self.l2_active = True
                self._update_l2_mapping(step, verbose)
                self.l2_state = self._seed_from_constraints(
                    self.N2, self.l2_constraints, self.device)
                if verbose:
                    print(f"  Step {step}: L2 activated, HW={self.l2_state.sum().item():.0f}")

            # Live mapping at update intervals
            if self.l1_active and self.l1_update_interval > 0 and \
               step > 0 and step % self.l1_update_interval == 0:
                self._update_l1_mapping(step, verbose)
            if self.l2_active and self.l2_update_interval > 0 and \
               step > 0 and step % self.l2_update_interval == 0:
                self._update_l2_mapping(step, verbose)

            # Step L1 (before L0 for ordering variety)
            if self.l1_active and not self.l1_sealed:
                r = _step_layer(self.l1_evolver, self.l1_state, step,
                                sample_interval=self.sample_interval,
                                step_callback=self._make_l1_callback())
                self.l1_hw_history.append(r['hw'])
                self._check_sealing(self.l1_evolver, 'l1', step)

            # Step L2
            if self.l2_active and not self.l2_sealed:
                r = _step_layer(self.l2_evolver, self.l2_state, step,
                                sample_interval=self.sample_interval)
                self.l2_hw_history.append(r['hw'])
                self._check_sealing(self.l2_evolver, 'l2', step)

            # Step L0 (always active)
            if not self.l0_sealed:
                r = _step_layer(self.l0_evolver, self.l0_state, step,
                                sample_interval=self.sample_interval)
                self.l0_hw_history.append(r['hw'])
                self._check_sealing(self.l0_evolver, 'l0', step)

            # ENHANCED FEEDBACK (NEW in exp_180)
            # These happen BEFORE basic perturbation so the enhanced effects
            # have time to propagate through the system
            self._apply_enhanced_feedback(step, verbose)

            # Basic feedback L1→L0 (same as exp_179)
            if self.l1_active and self.feedback_alpha > 0:
                apply_live_feedback(self.l1_state, self.l0_state,
                                    self.l0_evolver.constraints,
                                    feedback_alpha=self.feedback_alpha)

            # Basic feedback L2→L1 (same as exp_179)
            if self.l2_active and self.feedback_alpha > 0:
                apply_live_feedback(self.l2_state, self.l1_state,
                                    self.l1_evolver.constraints,
                                    feedback_alpha=self.feedback_alpha * 0.5)

            # Logging
            if verbose and step % (self.sample_interval * 5) == 0:
                l0_hw = self.l0_state.sum().item()
                l1_hw = self.l1_state.sum().item() if self.l1_active else -1
                l2_hw = self.l2_state.sum().item() if self.l2_active else -1
                l0_e = _compute_binary_entropy(self.l0_state)
                l1_e = _compute_binary_entropy(self.l1_state) if self.l1_active else -1
                l2_e = _compute_binary_entropy(self.l2_state) if self.l2_active else -1
                print(f"  Step {step:5d}: L0 HW={l0_hw:3.0f} H={l0_e:.3f}  "
                      f"L1 HW={l1_hw:3.0f} H={l1_e:.3f}  "
                      f"L2 HW={l2_hw:3.0f} H={l2_e:.3f}")

            # Early exit: all layers finished
            if self.l0_sealed:
                should_exit = True
                if step >= self.t_lag_l1:
                    should_exit = should_exit and self.l1_sealed
                if step >= self.t_lag_l2:
                    should_exit = should_exit and self.l2_sealed
                if should_exit:
                    if verbose:
                        print(f"  Step {step}: All layers finished — early exit")
                    break

        elapsed = time.time() - t_start
        results = self._collect_results()
        results['elapsed_seconds'] = round(elapsed, 1)
        if verbose:
            print(f"\n[MultiLayerCoordinator D2] Done in {elapsed:.1f}s")
            print(f"  L0 sealed: {self.l0_sealed} @ step {self.l0_seal_step}, "
                  f"HW={self.l0_state.sum().item():.0f}, H={_compute_binary_entropy(self.l0_state):.4f}")
            if self.l1_active:
                print(f"  L1 sealed: {self.l1_sealed} @ step {self.l1_seal_step}, "
                      f"HW={self.l1_state.sum().item():.0f}, H={_compute_binary_entropy(self.l1_state):.4f}")
            if self.l2_active:
                print(f"  L2 sealed: {self.l2_sealed} @ step {self.l2_seal_step}, "
                      f"HW={self.l2_state.sum().item():.0f}, H={_compute_binary_entropy(self.l2_state):.4f}")
            fb_types = ', '.join(self.feedback_type_active) if self.feedback_type_active else 'none'
            print(f"  Feedback types fired: {fb_types}")
            if self.constraint_mod_strength > 0:
                print(f"  Constraint mod count: {self.constraint_mod_count}")
            if self.matrix_mod_strength > 0:
                avg_ent = np.mean(self.matrix_mod_entropies) if self.matrix_mod_entropies else -1
                print(f"  Matrix mod L2 entropies (avg): {avg_ent:.4f}")
            if self.topology_mod_strength > 0:
                print(f"  Topology connections created: {self.topology_connections_total}")
        return results

    def _collect_results(self) -> Dict:
        """Compile results for analysis, including enhanced feedback metrics."""
        r = {
            'config_name': self.config_name,
            'params': {
                'N0': self.N0, 'N1': self.N1, 'N2': self.N2,
                't_lag_l1': self.t_lag_l1, 't_lag_l2': self.t_lag_l2,
                'l1_update_interval': self.l1_update_interval,
                'l2_update_interval': self.l2_update_interval,
                'feedback_alpha': self.feedback_alpha,
                'total_steps': self.total_steps,
                'constraint_mod_strength': self.constraint_mod_strength,
                'matrix_mod_strength': self.matrix_mod_strength,
                'topology_mod_strength': self.topology_mod_strength,
            },
            'l0_sealed': self.l0_sealed,
            'l1_sealed': self.l1_sealed,
            'l2_sealed': self.l2_sealed,
            'l0_seal_step': self.l0_seal_step,
            'l1_seal_step': self.l1_seal_step,
            'l2_seal_step': self.l2_seal_step,
            'l0_hw_final': int(self.l0_state.sum().item()) if self.l0_state is not None else 0,
            'l1_hw_final': int(self.l1_state.sum().item()) if self.l1_state is not None else 0,
            'l2_hw_final': int(self.l2_state.sum().item()) if self.l2_state is not None else 0,
            'l0_entropy_final': round(_compute_binary_entropy(self.l0_state), 4) if self.l0_state is not None else 0,
            'l1_entropy_final': round(_compute_binary_entropy(self.l1_state), 4) if self.l1_state is not None else 0,
            'l2_entropy_final': round(_compute_binary_entropy(self.l2_state), 4) if self.l2_state is not None else 0,
            'n_live_maps': len(self.live_map_steps),
            'l0_hw_history': [int(h) for h in self.l0_hw_history],
            'l1_hw_history': [int(h) for h in self.l1_hw_history],
            'l2_hw_history': [int(h) for h in self.l2_hw_history],
            # Enhanced feedback metrics
            'feedback_types_active': self.feedback_type_active,
            'constraint_mod_count': self.constraint_mod_count,
            'topology_connections_total': self.topology_connections_total,
            'avg_matrix_mod_entropy': round(np.mean(self.matrix_mod_entropies), 4)
                if self.matrix_mod_entropies else -1,
        }
        # Structure analysis: pairwise reflection
        if self.l0_state is not None and self.l1_state is not None:
            r['l0_l1_reflection'] = round(self._compute_reflection(
                self.l0_state, self.l1_state), 4)
        if self.l1_state is not None and self.l2_state is not None:
            r['l1_l2_reflection'] = round(self._compute_reflection(
                self.l1_state, self.l2_state), 4)
        if self.l0_state is not None and self.l2_state is not None:
            r['l0_l2_reflection'] = round(self._compute_reflection(
                self.l0_state, self.l2_state), 4)

        # L2 structural quality (success criteria)
        l2_e = r.get('l2_entropy_final', 1.0)
        r['l2_structure_ok'] = l2_e < 0.5  # entropy < 0.5 = non-random
        l2_ref = r.get('l1_l2_reflection', 0.5)
        r['l2_novel'] = l2_ref < 0.9  # reflection < 0.9 = not just copy
        r['l2_emergence_ok'] = r['l2_sealed'] and r['l2_structure_ok'] and r['l2_novel']

        return r

    def _compute_reflection(self, state_a, state_b) -> float:
        """Compute structural reflection between two states.
        1.0 = identical structure, 0.0 = opposite, ~0.5 = uncorrelated."""
        n = min(state_a.numel(), state_b.numel())
        a = state_a[:n].cpu()
        b = state_b[:n].cpu()
        if a.sum() == 0 or b.sum() == 0:
            return 0.5
        agreement = (a == b).float().mean().item()
        return agreement


# =========================================================================
# Basic live feedback (same as exp_179)
# =========================================================================

def apply_live_feedback(src_state, dst_state, constraints, feedback_alpha=0.05):
    """Apply basic cross-layer feedback via bit perturbation."""
    if feedback_alpha <= 0 or src_state.numel() == 0:
        return
    src_entropy = _compute_binary_entropy(src_state)
    n_perturb = max(1, int(dst_state.numel() * feedback_alpha * 0.1))
    if src_entropy < 0.5:
        perturb_indices = torch.randperm(dst_state.numel(), device=dst_state.device)[:n_perturb]
        for idx in perturb_indices:
            src_idx = idx.item() % src_state.numel()
            target_val = 1.0 if src_state[src_idx] > 0.5 else 0.0
            if (dst_state[idx] < 0.5 and target_val > 0.5) or \
               (dst_state[idx] > 0.5 and target_val < 0.5):
                dst_state[idx] = 1.0 - dst_state[idx]
    else:
        perturb_indices = torch.randperm(dst_state.numel(), device=dst_state.device)[:n_perturb]
        for idx in perturb_indices:
            if torch.rand(1).item() < 0.3:
                dst_state[idx] = 1.0 - dst_state[idx]


# =========================================================================
# Experiment configuration - 5 D2 configs
# =========================================================================

CONFIGS = {
    'd2_baseline': {
        't_lag_l1': 3, 't_lag_l2': 7,
        'l1_update_interval': 5, 'l2_update_interval': 5,
        'feedback_alpha': 0.05,
        'constraint_mod_strength': 0.0,
        'matrix_mod_strength': 0.0,
        'topology_mod_strength': 0.0,
        'desc': 'Control: basic perturbation only',
    },
    'd2_constraint': {
        't_lag_l1': 3, 't_lag_l2': 7,
        'l1_update_interval': 5, 'l2_update_interval': 5,
        'feedback_alpha': 0.05,
        'constraint_mod_strength': 0.05,
        'matrix_mod_strength': 0.0,
        'topology_mod_strength': 0.0,
        'desc': 'Constraint modulation: L1 to L0',
    },
    'd2_matrix': {
        't_lag_l1': 3, 't_lag_l2': 7,
        'l1_update_interval': 5, 'l2_update_interval': 5,
        'feedback_alpha': 0.05,
        'constraint_mod_strength': 0.0,
        'matrix_mod_strength': 0.10,
        'topology_mod_strength': 0.0,
        'desc': 'Transition matrix modulation: L2 to L1',
    },
    'd2_topology': {
        't_lag_l1': 3, 't_lag_l2': 7,
        'l1_update_interval': 5, 'l2_update_interval': 5,
        'feedback_alpha': 0.05,
        'constraint_mod_strength': 0.0,
        'matrix_mod_strength': 0.0,
        'topology_mod_strength': 0.10,
        'desc': 'Topology reorganization: L1 to L0',
    },
    'd2_full': {
        't_lag_l1': 3, 't_lag_l2': 7,
        'l1_update_interval': 5, 'l2_update_interval': 5,
        'feedback_alpha': 0.05,
        'constraint_mod_strength': 0.05,
        'matrix_mod_strength': 0.10,
        'topology_mod_strength': 0.10,
        'desc': 'Full: all three enhanced types combined',
    },
}


def run_single_trial(config_name: str, trial_id: int, total_steps: int = 300,
                     device: str = 'cpu') -> Dict:
    cfg = CONFIGS[config_name].copy()
    cfg.pop('desc', None)
    coord = MultiLayerCoordinator(
        N0=48, N1=48, N2=48,
        total_steps=total_steps,
        sample_interval=100,
        device=device,
        config_name=config_name,
        **cfg,
    )
    print(f"\n{'='*60}")
    print(f"Trial {trial_id}: config={config_name} - {CONFIGS[config_name].get('desc', '')}")
    print('='*60)
    return coord.run(verbose=True)


def run_all_configs(n_runs: int = 5, total_steps: int = 300,
                    device: str = 'cpu') -> Dict:
    all_results = {}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    for config_name in CONFIGS:
        config_results = []
        for trial in range(n_runs):
            try:
                result = run_single_trial(config_name, trial, total_steps, device)
                config_results.append(result)
            except Exception as e:
                print(f"  ERROR in {config_name} trial {trial}: {e}")
                import traceback
                traceback.print_exc()
                config_results.append({'error': str(e), 'config_name': config_name, 'trial': trial})

        all_results[config_name] = config_results

        sealed_l0 = sum(1 for r in config_results if r.get('l0_sealed', False))
        sealed_l1 = sum(1 for r in config_results if r.get('l1_sealed', False))
        sealed_l2 = sum(1 for r in config_results if r.get('l2_sealed', False))
        l2_entropies = [r.get('l2_entropy_final', 1.0) for r in config_results
                        if r.get('l2_entropy_final', None) is not None]
        avg_l2_entropy = np.mean(l2_entropies) if l2_entropies else -1
        l2_reflections = [r.get('l1_l2_reflection', 0.5) for r in config_results
                          if r.get('l1_l2_reflection', None) is not None]
        avg_l2_reflection = np.mean(l2_reflections) if l2_reflections else -1
        emergence_ok = sum(1 for r in config_results if r.get('l2_emergence_ok', False))

        print(f"\n{'='*60}")
        print(f"SUMMARY [{config_name}] ({n_runs} trials):")
        print(f"  L0 seal: {sealed_l0}/{n_runs}")
        print(f"  L1 seal: {sealed_l1}/{n_runs}")
        print(f"  L2 seal: {sealed_l2}/{n_runs}")
        print(f"  Avg L2 entropy: {avg_l2_entropy:.4f}")
        print(f"  Avg L1-L2 reflection: {avg_l2_reflection:.4f}")
        print(f"  L2 emergence OK: {emergence_ok}/{n_runs}")
        avg_constraint = np.mean([r.get('constraint_mod_count', 0) for r in config_results])
        avg_topology = np.mean([r.get('topology_connections_total', 0) for r in config_results])
        if avg_constraint > 0:
            print(f"  Avg constraint mods/trial: {avg_constraint:.1f}")
        if avg_topology > 0:
            print(f"  Avg topology connections/trial: {avg_topology:.1f}")
        print('='*60)

    results_dir = Path(__file__).parent.parent / 'experiments' / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)
    filepath = results_dir / f'exp_180_results_{timestamp}.json'
    serializable = {}
    for config_name, config_results in all_results.items():
        serializable[config_name] = []
        for r in config_results:
            r_clean = {k: v for k, v in r.items()
                       if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
            serializable[config_name].append(r_clean)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, indent=2, default=str)
    print(f"\nResults saved to {filepath}")
    return all_results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='exp_180: Enhanced Feedback (Path D2)')
    parser.add_argument('--config', type=str, default='d2_baseline',
                        choices=list(CONFIGS.keys()) + ['all'],
                        help='Configuration to run')
    parser.add_argument('--n_runs', type=int, default=5, help='Trials per config')
    parser.add_argument('--total_steps', type=int, default=300, help='Total steps')
    parser.add_argument('--all_configs', action='store_true', help='Run all configs')
    parser.add_argument('--device', type=str, default='cpu', help='Device (cpu or cuda)')
    args = parser.parse_args()

    if args.all_configs or args.config == 'all':
        print(f"Running ALL {len(CONFIGS)} configs, {args.n_runs} trials each...")
        run_all_configs(n_runs=args.n_runs, total_steps=args.total_steps, device=args.device)
    else:
        print(f"Running config={args.config}, {args.n_runs} trial(s)...")
        for trial in range(args.n_runs):
            result = run_single_trial(args.config, trial, args.total_steps, args.device)
        print(f"\n{'='*60}")
        print(f"SUMMARY [{args.config}] ({args.n_runs} trial(s)):")
        print(f"  L0 sealed: {result.get('l0_sealed', '?')} @ step {result.get('l0_seal_step', '?')}")
        print(f"  L1 sealed: {result.get('l1_sealed', '?')} @ step {result.get('l1_seal_step', '?')}")
        print(f"  L2 sealed: {result.get('l2_sealed', '?')} @ step {result.get('l2_seal_step', '?')}")
        print(f"  L2 entropy: {result.get('l2_entropy_final', '?'):.4f}")
        print(f"  L1-L2 reflection: {result.get('l1_l2_reflection', '?'):.4f}")
        print(f"  L2 emergence OK: {result.get('l2_emergence_ok', '?')}")
        print(f"  Time: {result.get('elapsed_seconds', '?'):.1f}s")