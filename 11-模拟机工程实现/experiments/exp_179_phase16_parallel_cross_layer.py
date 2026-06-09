"""
exp_179_phase16_parallel_cross_layer.py -- Phase 16 Path D1: Parallel Multi-layer Evolution

Hypothesis H16-D1: Parallel evolution (all layers evolving concurrently) enables
L2 emergence that is structurally non-trivial (not just a copy of L1).

Core idea: In all previous experiments (Paths A/B/C), L0 and L1 evolved serially.
Path D1 reverses this: L1 (and L2) start BEFORE L0 seals, enabling cross-layer
structural coupling during active evolution.

Configs (7):
  baseline_serial: L1 starts after L0 seals [control]
  d1_early:        τ₁=50,  τ₂=150,  update=200, α=0.05
  d1_medium:       τ₁=200, τ₂=500,  update=200, α=0.03
  d1_late:         τ₁=500, τ₂=1000, update=200, α=0.03
  d1_continuous:   τ₁=50,  τ₂=150,  update=50,  α=0.10
  d1_feedback_only:τ₁=50,  τ₂=150,  update=∞,   α=0.10
  d1_burst:        τ₁=50,  τ₂=150,  update=500, α=0.15

Usage:
    python exp_179_phase16_parallel_cross_layer.py [--config d1_medium] [--n_runs 5]
"""

import sys
import os
import json
import time
import math
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
# Utility functions
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
            else:
                n_inject = 0
        else:
            n_inject = 0

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
            else:
                n_absorb = 0

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
# Live cross-layer mapping
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


def apply_live_feedback(src_state, dst_state, constraints, feedback_alpha=0.05):
    """Apply live cross-layer feedback."""
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
# MultiLayerCoordinator
# =========================================================================

class MultiLayerCoordinator:
    """Orchestrates parallel L0/L1/L2 evolution with live cross-layer mapping."""

    def __init__(self,
                 N0=48, N1=48, N2=48,
                 t_lag_l1=50, t_lag_l2=150,
                 l1_update_interval=200, l2_update_interval=200,
                 feedback_alpha=0.05, total_steps=5000,
                 sample_interval=100, device="cpu",
                 config_name="default"):
        """
        sealing_threshold_mult: Multiplier for sealing_activation_threshold.
                                Default 3 means L0 needs 3*N unique active bits to seal.
                                This delays sealing and gives L1/L2 time to start.
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

        # L0 bootstrap: just 1 seed bit (matching original SpatialLongRangeEvolver.run)
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

    def run(self, verbose=True) -> Dict:
        """Run parallel multi-layer evolution."""
        if not self._initialized:
            self._init_layers()

        t_start = time.time()

        for step in range(self.total_steps):
            # Activate layers
            if not self.l1_active and step >= self.t_lag_l1:
                self.l1_active = True
                # Immediate live map for initial seeding
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

            # Live feedback L1→L0
            if self.l1_active and self.feedback_alpha > 0:
                apply_live_feedback(self.l1_state, self.l0_state,
                                    self.l0_evolver.constraints,
                                    feedback_alpha=self.feedback_alpha)

            # Live feedback L2→L1
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

            # Early exit: all layers that have been given their chance must be sealed.
            # If we haven't reached t_lag_l1 yet, keep running (L1 hasn't had its shot).
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
            print(f"\n[ParallelCrossLayer] Done in {elapsed:.1f}s")
            print(f"  L0 sealed: {self.l0_sealed} @ step {self.l0_seal_step}, "
                  f"HW={self.l0_state.sum().item():.0f}, H={_compute_binary_entropy(self.l0_state):.4f}")
            if self.l1_active:
                print(f"  L1 sealed: {self.l1_sealed} @ step {self.l1_seal_step}, "
                      f"HW={self.l1_state.sum().item():.0f}, H={_compute_binary_entropy(self.l1_state):.4f}")
            if self.l2_active:
                print(f"  L2 sealed: {self.l2_sealed} @ step {self.l2_seal_step}, "
                      f"HW={self.l2_state.sum().item():.0f}, H={_compute_binary_entropy(self.l2_state):.4f}")
        return results

    def _collect_results(self) -> Dict:
        """Compile results for analysis."""
        r = {
            'config_name': self.config_name,
            'params': {
                'N0': self.N0, 'N1': self.N1, 'N2': self.N2,
                't_lag_l1': self.t_lag_l1, 't_lag_l2': self.t_lag_l2,
                'l1_update_interval': self.l1_update_interval,
                'l2_update_interval': self.l2_update_interval,
                'feedback_alpha': self.feedback_alpha,
                'total_steps': self.total_steps,
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
        }
        # Structure analysis: compute pairwise reflection between layers
        if self.l0_state is not None and self.l1_state is not None:
            r['l0_l1_reflection'] = round(self._compute_reflection(
                self.l0_state, self.l1_state), 4)
        if self.l1_state is not None and self.l2_state is not None:
            r['l1_l2_reflection'] = round(self._compute_reflection(
                self.l1_state, self.l2_state), 4)
        if self.l0_state is not None and self.l2_state is not None:
            r['l0_l2_reflection'] = round(self._compute_reflection(
                self.l0_state, self.l2_state), 4)

        return r

    def _compute_reflection(self, state_a, state_b) -> float:
        """Compute structural reflection between two states.

        1.0 = identical structure, 0.0 = opposite, ~0.5 = uncorrelated.
        """
        # Resample to same size if needed
        n = min(state_a.numel(), state_b.numel())
        a = state_a[:n].cpu()
        b = state_b[:n].cpu()
        if a.sum() == 0 or b.sum() == 0:
            return 0.5
        agreement = (a == b).float().mean().item()
        return agreement


# =========================================================================
# Experiment configuration
# =========================================================================

CONFIGS = {
    # NOTE: L0 with N=48 seals at ~step 10 (threshold=36).
    # All timing configs are designed around this fast sealing timescale.
    'baseline_serial': {
        't_lag_l1': 999999,
        't_lag_l2': 999999,
        'l1_update_interval': 0,
        'l2_update_interval': 0,
        'feedback_alpha': 0.0,
        'desc': 'Control: L1 starts only after L0 seals (serial, no parallel)',
    },
    'd1_early': {
        't_lag_l1': 3,
        't_lag_l2': 7,
        'l1_update_interval': 5,
        'l2_update_interval': 5,
        'feedback_alpha': 0.05,
        'desc': 'L1 at step 3 (before L0 seal~10), L2 at step 7, update=5',
    },
    'd1_medium': {
        't_lag_l1': 5,
        't_lag_l2': 12,
        'l1_update_interval': 5,
        'l2_update_interval': 5,
        'feedback_alpha': 0.03,
        'desc': 'L1 at step 5 (during L0 seal), L2 at step 12 (after L0 seal)',
    },
    'd1_late': {
        't_lag_l1': 20,
        't_lag_l2': 40,
        'l1_update_interval': 10,
        'l2_update_interval': 10,
        'feedback_alpha': 0.03,
        'desc': 'L1 at step 20 (after L0 seals), L2 at step 40, update=10',
    },
    'd1_continuous': {
        't_lag_l1': 2,
        't_lag_l2': 5,
        'l1_update_interval': 2,
        'l2_update_interval': 2,
        'feedback_alpha': 0.10,
        'desc': 'Very early: L1 step 2, L2 step 5, update=2, alpha=0.10',
    },
    'd1_feedback_only': {
        't_lag_l1': 2,
        't_lag_l2': 5,
        'l1_update_interval': 0,
        'l2_update_interval': 0,
        'feedback_alpha': 0.10,
        'desc': 'L1 step 2, L2 step 5, NO constraint updates, only feedback',
    },
    'd1_burst': {
        't_lag_l1': 3,
        't_lag_l2': 7,
        'l1_update_interval': 50,
        'l2_update_interval': 50,
        'feedback_alpha': 0.15,
        'desc': 'L1 step 3, L2 step 7, mapping never fires, strong feedback alpha=0.15',
    },
}


# =========================================================================
# CLI and experiment runner
# =========================================================================

def run_single_trial(config_name: str, trial_id: int, total_steps: int = 5000,
                     device: str = 'cpu') -> Dict:
    """Run a single trial with the given config."""
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
    coord._config_desc = CONFIGS[config_name].get('desc', '')

    print(f"\n{'='*60}")
    print(f"Trial {trial_id}: config={config_name}, "
          f"t_lag_l1={cfg.get('t_lag_l1','N/A')}, "
          f"t_lag_l2={cfg.get('t_lag_l2','N/A')}, "
          f"update={cfg.get('l1_update_interval','N/A')}, "
          f"alpha={cfg.get('feedback_alpha','N/A')}")
    print(f"  {CONFIGS[config_name]['desc']}")
    print('='*60)

    return coord.run(verbose=True)


def run_all_configs(n_runs: int = 5, total_steps: int = 5000,
                    device: str = 'cpu') -> Dict:
    """Run all configs for n_runs trials each."""
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

        # Summary
        sealed_l0 = sum(1 for r in config_results if r.get('l0_sealed', False))
        sealed_l1 = sum(1 for r in config_results if r.get('l1_sealed', False))
        sealed_l2 = sum(1 for r in config_results if r.get('l2_sealed', False))
        l2_entropies = [r.get('l2_entropy_final', 1.0) for r in config_results
                        if r.get('l2_entropy_final', None) is not None]
        avg_l2_entropy = np.mean(l2_entropies) if l2_entropies else -1
        l2_reflections = [r.get('l1_l2_reflection', 0.5) for r in config_results
                          if r.get('l1_l2_reflection', None) is not None]
        avg_l2_reflection = np.mean(l2_reflections) if l2_reflections else -1

        print(f"\n{'='*60}")
        print(f"SUMMARY [{config_name}] ({n_runs} trials):")
        print(f"  L0 seal: {sealed_l0}/{n_runs}")
        print(f"  L1 seal: {sealed_l1}/{n_runs}")
        print(f"  L2 seal: {sealed_l2}/{n_runs}")
        print(f"  Avg L2 entropy: {avg_l2_entropy:.4f}")
        print(f"  Avg L1-L2 reflection: {avg_l2_reflection:.4f}")
        print('='*60)

    # Save results
    results_dir = Path(__file__).parent.parent / 'experiments' / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)
    filepath = results_dir / f'exp_179_results_{timestamp}.json'

    # Convert to serializable
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


# =========================================================================
# Main
# =========================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='exp_179: Parallel Multi-layer Evolution (Path D1)')
    parser.add_argument('--config', type=str, default='d1_medium',
                        choices=list(CONFIGS.keys()) + ['all'],
                        help='Configuration to run (default: d1_medium)')
    parser.add_argument('--n_runs', type=int, default=5,
                        help='Number of trials per config (default: 5)')
    parser.add_argument('--total_steps', type=int, default=300,
                        help='Total evolution steps (default: 300)')
    parser.add_argument('--all_configs', action='store_true',
                        help='Run all configs')
    parser.add_argument('--device', type=str, default='cpu',
                        help='Device (cpu or cuda)')

    args = parser.parse_args()

    n_runs = args.n_runs
    if args.all_configs or args.config == 'all':
        print(f"Running ALL {len(CONFIGS)} configs, {n_runs} trials each...")
        run_all_configs(n_runs=n_runs, total_steps=args.total_steps, device=args.device)
    else:
        print(f"Running config={args.config}, {n_runs} trial(s)...")
        for trial in range(n_runs):
            result = run_single_trial(args.config, trial, args.total_steps, args.device)

        # Quick summary
        print(f"\n{'='*60}")
        print(f"SUMMARY [{args.config}] ({n_runs} trial(s)):")
        print(f"  L0 sealed: {result.get('l0_sealed', '?')} @ step {result.get('l0_seal_step', '?')}")
        print(f"  L1 sealed: {result.get('l1_sealed', '?')} @ step {result.get('l1_seal_step', '?')}")
        print(f"  L2 sealed: {result.get('l2_sealed', '?')} @ step {result.get('l2_seal_step', '?')}")
        print(f"  L2 entropy: {result.get('l2_entropy_final', '?'):.4f}")
        print(f"  L1-L2 reflection: {result.get('l1_l2_reflection', '?'):.4f}")
        print(f"  Time: {result.get('elapsed_seconds', '?'):.1f}s")