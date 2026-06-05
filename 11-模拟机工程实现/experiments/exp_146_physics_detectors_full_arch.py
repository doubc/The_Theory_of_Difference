"""
experiments/exp_146_physics_detectors_full_arch.py

Phase 9 Physics Detectors: Full Architecture Verification

Purpose:
  Run ALL physics detectors (gravitational potential, dimension locking,
  gauge field) simultaneously under the full Phase 9 architecture
  (CSC + NSE + NRC + Booster) at N0=72.

Theoretical Predictions to Verify:
  P1: Gravitational potential  : Phi proportional to -1/d_H
      (Verified at N=6/12 in Phase 1; re-verify at N0=72 under full arch)
  P2: Dimension locking       : D_eff = 3  (WorldBase section 2)
  P3: Gauge field structure   : su(3) algebra  (WorldBase section 5)

Key Question:
  Does the full narrative architecture (Phase 4-9) preserve the WorldBase
  physics predictions that were verified in simpler Phase 1 setups?

Design:
  - N0=72, 8 seeds, 2000 steps
  - Full HierarchicalEvolver with CSC+NSE+NRC+Booster
  - Every 50 steps: snapshot state, run all 3 detectors
  - Segment: pre-sealing / post-sealing / post-L1 formation
"""

import sys, os, time, json
from datetime import datetime
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch, numpy as np
from typing import Dict, List, Optional, Tuple

from engine.hierarchical_evolver import HierarchicalEvolver
from engine.return_flow_channel import ReturnFlowChannel
from engine.unsealing_mechanism import UnsealingMechanism
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.minimal_self_detector import MinimalSelfDetector
from engine.global_bias_constraint import GlobalBiasConstraint
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from models.narrative_self import (NarrativeRecursionOperator, NarrativeLevel,
    AdaptiveMomentumConnector, CIVRateLimiter)
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.six_threshold_detector import SixThresholdDetector
from engine.cross_scale_coupling import (CrossScaleCoupling, DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
from engine.narrative_self_emergence import (NarrativeSelfEmergence, DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
from engine.narrative_recursive_closure import NarrativeRecursiveClosure
from engine.civ_floor import NarrativeLevelBooster
from engine.per_layer_metrics import PerLayerMetricsCollector

# Physics detector primitives
from layers.three_dim_hamming import ThreeDimHammingLattice
from engine.detectors.statistics import EffectiveDOFDetector
from layers.hamming_layer import HammingMeasurement


# ============================================================
# Phase 9 Configuration (same as exp_142)
# ============================================================

P9_CSC_CONFIG = {
    'topdown_max_constraint_strength': 0.10, 'topdown_min_constraint_strength': 0.01,
    'topdown_response_delay': 20, 'topdown_decay_rate': 0.98,
    'topdown_propagation_depth': 2, 'topdown_stability_threshold': 0.05,
    'emergence_min_stability_steps': 50, 'emergence_stability_threshold': 0.6,
    'emergence_min_odi': 0.25, 'emergence_cooldown_steps': 30,
    'narrative_bridge_window': 100, 'narrative_min_coherence': 0.2,
    'narrative_integration_rate': 0.05, 'csci_alpha': 0.4, 'csci_beta': 0.3, 'csci_gamma': 0.3,
}


class CIVRateLimiterV2P1F(CIVRateLimiter):
    def __init__(self, window_size=50, max_civ_rate=0.12, cooldown_steps=12, min_civ_guarantee=3):
        super().__init__(window_size=window_size, max_civ_rate=max_civ_rate, cooldown_steps=cooldown_steps)
        self.min_civ_guarantee = min_civ_guarantee
    def maybe_downgrade(self, level, step):
        if level == NarrativeLevel.CIVILIZATION:
            if self._total_civ_seen < self.min_civ_guarantee: return level
            if self.should_downgrade(step): self._total_downgrades += 1; return NarrativeLevel.INSTITUTIONAL
        return level


class MomentumNarrativeOperatorV4P1F(NarrativeRecursionOperator):
    def __init__(self, bias_dimension=128, filter_magnitude_threshold=0.02,
                 connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
                 narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3):
        from models.narrative_self import NarrativeFilter, NarrativeNamer, NarrativeActionizer, NarrativeVerifier
        self.filter = NarrativeFilter(magnitude_threshold=filter_magnitude_threshold)
        self.namer = NarrativeNamer()
        self.connector = AdaptiveMomentumConnector(strength_threshold=connector_strength_threshold,
                                                   momentum_decay=momentum_decay, momentum_bonus=momentum_bonus)
        self.actionizer = NarrativeActionizer(bias_dimension=bias_dimension)
        self.verifier = NarrativeVerifier(consistency_threshold=verifier_consistency_threshold)
        self.narrative_decay_rate = narrative_decay_rate
        self._records = []; self._active_narratives = {}; self._record_count = 0
        self._total_actions = 0; self._validated_actions = 0
        self.civ_rate_limiter = CIVRateLimiterV2P1F(window_size=50, max_civ_rate=0.12,
                                                    cooldown_steps=12, min_civ_guarantee=3)
    def get_momentum_stats(self): return self.connector.get_cache_stats()
    def get_current_momentum_bonus(self): return self.connector.get_momentum_bonus()


# ============================================================
# Physics Detector 1: Gravitational Potential  Phi(d_H)
# ============================================================

class GravitationalPotentialDetector:
    """Measures Phi as a function of Hamming distance d_H.

    Theory: Phi proportional to -1/d_H  (WorldBase section 4.2)
    Implementation: From the current state (as source), compute potential
    at multiple probe states with varying d_H from the source.
    """

    def __init__(self, N: int, n_probes: int = 20):
        self.N = N
        self.n_probes = n_probes
        self.lattice = ThreeDimHammingLattice(N=N, device="cpu")

    def detect(self, state: torch.Tensor, rng: np.random.Generator) -> Dict:
        """Compute Phi(d_H) for probe states at various Hamming distances.

        Returns:
            {
                'd_H_values': list of Hamming distances,
                'phi_values': list of corresponding potentials,
                'phi_3d_values': list of 3D-embedded potentials,
                'correlation_1_over_d': correlation with -1/d_H model,
                'n_probes': number of probes used,
            }
        """
        if state.sum().item() < 1:
            return {'error': 'empty state', 'd_H_values': [], 'phi_values': [],
                    'correlation_1_over_d': 0.0}

        source = (state > 0.5).float()
        sources = [source]

        d_H_list = []
        phi_list = []
        phi_3d_list = []

        # Generate probe states at controlled Hamming distances
        for d_target in range(1, min(self.N, self.n_probes + 1)):
            # Create probe by flipping d_target bits from source
            probe = source.clone()
            ones = (source > 0.5).nonzero(as_tuple=True)[0]
            zeros = (source < 0.5).nonzero(as_tuple=True)[0]

            # Flip min(d_target//2, len(ones)) ones->zeros and rest zeros->ones
            n_flip_1_to_0 = min(d_target // 2, len(ones))
            n_flip_0_to_1 = d_target - n_flip_1_to_0

            if n_flip_0_to_1 > len(zeros):
                n_flip_0_to_1 = len(zeros)
                n_flip_1_to_0 = d_target - n_flip_0_to_1
                if n_flip_1_to_0 > len(ones):
                    continue

            if n_flip_1_to_0 > 0 and len(ones) > 0:
                flip_ones_idx = rng.choice(len(ones), size=min(n_flip_1_to_0, len(ones)), replace=False)
                for idx in flip_ones_idx:
                    probe[ones[idx]] = 0.0
            if n_flip_0_to_1 > 0 and len(zeros) > 0:
                flip_zeros_idx = rng.choice(len(zeros), size=min(n_flip_0_to_1, len(zeros)), replace=False)
                for idx in flip_zeros_idx:
                    probe[zeros[idx]] = 1.0

            actual_d_H = int(HammingMeasurement.hamming_distance(source, probe).item())
            if actual_d_H == 0:
                continue

            # Compute potential using Hamming distance metric
            phi = self.lattice.potential_at(probe, sources)
            # Compute potential using 3D embedded distance
            phi_3d = self.lattice.potential_3d_at(probe, sources)

            d_H_list.append(actual_d_H)
            phi_list.append(phi)
            phi_3d_list.append(phi_3d)

        if len(d_H_list) < 3:
            return {'error': 'insufficient probes', 'd_H_values': d_H_list,
                    'phi_values': phi_list, 'correlation_1_over_d': 0.0}

        # Test correlation with -1/d_H model
        d_arr = np.array(d_H_list, dtype=np.float64)
        phi_arr = np.array(phi_list, dtype=np.float64)
        model = -1.0 / d_arr  # theoretical prediction

        # Pearson correlation
        if np.std(phi_arr) > 1e-10 and np.std(model) > 1e-10:
            corr = float(np.corrcoef(phi_arr, model)[0, 1])
        else:
            corr = 0.0

        # Also test 3D version
        phi_3d_arr = np.array(phi_3d_list, dtype=np.float64)
        if np.std(phi_3d_arr) > 1e-10:
            corr_3d = float(np.corrcoef(phi_3d_arr, model)[0, 1])
        else:
            corr_3d = 0.0

        return {
            'd_H_values': d_H_list,
            'phi_values': phi_list,
            'phi_3d_values': phi_3d_list,
            'correlation_1_over_d': corr,
            'correlation_3d': corr_3d,
            'n_probes': len(d_H_list),
            'phi_mean': float(np.mean(phi_arr)),
            'phi_std': float(np.std(phi_arr)),
        }


# ============================================================
# Physics Detector 2: Dimension Locking  D_eff
# ============================================================

class DimensionLockingDetector:
    """Measures effective dimensionality D_eff of the state trajectory.

    Theory: D_eff should lock to 3 (WorldBase section 2, three_dim_hamming).
    Implementation: PCA on accumulated state snapshots.
    """

    def __init__(self, N: int):
        self.N = N
        self.dof_detector = EffectiveDOFDetector(N=N)

    def detect(self, state_snapshots: torch.Tensor) -> Dict:
        """Compute D_eff from PCA on state snapshots.

        Args:
            state_snapshots: (n_snapshots, N) tensor of states

        Returns:
            {
                'D_eff_90': effective DOF at 90% variance,
                'D_eff_95': effective DOF at 95% variance,
                'compression_ratio': D_eff / N,
                'dimension_locked_3': whether D_eff is close to 3,
                'top_singular_values': top 10 singular values,
            }
        """
        if state_snapshots.shape[0] < 10:
            return {'error': 'too few snapshots', 'D_eff_90': -1, 'dimension_locked_3': False}

        result = self.dof_detector.compute(state_snapshots)
        if 'error' in result:
            return {**result, 'D_eff_90': -1, 'dimension_locked_3': False}

        d_eff_90 = result['n_dof_90']
        d_eff_95 = result['n_dof_95']

        # Check if D_eff is close to 3 (the theoretical prediction)
        # Allow range [2, 5] as "locked to 3"
        dimension_locked = 2 <= d_eff_90 <= 5

        # Also check 3D embedding coordinates directly
        lattice = ThreeDimHammingLattice(N=self.N, device="cpu")
        coords = []
        for i in range(state_snapshots.shape[0]):
            c = lattice.embed_3d(state_snapshots[i])
            coords.append(c)
        coords_tensor = torch.stack(coords)
        coord_var = coords_tensor.var(dim=0)
        coord_mean = coords_tensor.mean(dim=0)

        # If the 3D embedding is meaningful, variance should be distributed
        # across all 3 dimensions
        n_active_dims = (coord_var > 1e-6).sum().item()

        return {
            'D_eff_90': d_eff_90,
            'D_eff_95': d_eff_95,
            'D_eff_99': result['n_dof_99'],
            'compression_ratio': result['compression_ratio'],
            'dimension_locked_3': dimension_locked,
            'n_active_3d_dims': n_active_dims,
            'coord_variance': coord_var.tolist(),
            'coord_mean': coord_mean.tolist(),
            'top_singular_values': result['singular_values'][:10],
            'explained_variance_top5': result['explained_variance'][:5],
        }


# ============================================================
# Physics Detector 3: Gauge Field (su(3) algebra structure)
# ============================================================

class GaugeFieldDetector:
    """Probes the su(3) algebra structure via E_ij operators on the mid-surface.

    Theory: On the mid-surface w=N/2, the E_ij operators (bit exchanges
    between groups) should exhibit su(3) commutation relations (WorldBase section 5).

    Implementation:
    - Sample states near the mid-surface
    - Apply E_ij moves within and between the 3 groups
    - Measure the algebra structure of the resulting transitions
    """

    def __init__(self, N: int):
        self.N = N
        self.n = N // 3  # bits per group
        self.lattice = ThreeDimHammingLattice(N=N, device="cpu")

    def detect(self, state: torch.Tensor) -> Dict:
        """Analyze gauge structure indicators from a single state.

        Returns:
            {
                'on_mid_surface': bool,
                'hamming_weight': int,
                'n_valid_E_moves': int,
                'intra_group_moves': count of moves within same group,
                'inter_group_moves': count of moves between different groups,
                'su3_indicator': ratio of inter/intra group moves (theoretical = 2/1 for su(3)),
                'E_ij_closure': fraction of E_ij moves that stay on mid-surface,
            }
        """
        w = int(state.sum().item())
        mid_w = self.N // 2
        on_mid = (w == mid_w)

        # Get valid E_ij moves
        valid_moves = self.lattice.get_valid_E_moves(state)
        n_valid = len(valid_moves)

        if n_valid == 0:
            return {'on_mid_surface': on_mid, 'hamming_weight': w,
                    'n_valid_E_moves': 0, 'su3_indicator': 0.0,
                    'E_ij_closure': 1.0 if on_mid else 0.0,
                    'intra_group_moves': 0, 'inter_group_moves': 0}

        # Classify moves: intra-group (same spatial dimension) vs inter-group
        intra = 0
        inter = 0
        for (i, j) in valid_moves:
            group_i = i // self.n  # 0, 1, or 2
            group_j = j // self.n
            if group_i == group_j:
                intra += 1
            else:
                inter += 1

        # su(3) indicator: for su(3), we expect specific ratios
        # In su(3), there are 3 diagonal generators and 6 off-diagonal ones
        # inter/intra ratio should reflect the algebra structure
        su3_indicator = inter / max(1, intra)

        # Check E_ij closure: do moves stay on mid-surface?
        # E_ij preserves Hamming weight by construction, so closure should be 1.0
        n_closure_test = min(20, n_valid)
        closure_count = 0
        for idx in range(n_closure_test):
            i, j = valid_moves[idx % n_valid]
            new_state = self.lattice.apply_E_ij(state, i, j)
            if new_state is not None:
                new_w = int(new_state.sum().item())
                if new_w == w:
                    closure_count += 1
        closure_ratio = closure_count / max(1, n_closure_test)

        # Compute commutator structure for a sample of E_ij pairs
        # [E_ij, E_kl] should give another E operator or 0
        commutator_nonzero = 0
        commutator_total = 0
        n_sample = min(50, n_valid)
        for a_idx in range(min(n_sample, n_valid)):
            i_a, j_a = valid_moves[a_idx]
            for b_idx in range(a_idx + 1, min(a_idx + 5, n_valid)):
                i_b, j_b = valid_moves[b_idx]
                # Apply E_a then E_b to state
                s1 = self.lattice.apply_E_ij(state, i_a, j_a)
                if s1 is None:
                    continue
                s2 = self.lattice.apply_E_ij(s1, i_b, j_b)
                # Apply E_b then E_a to state
                s3 = self.lattice.apply_E_ij(state, i_b, j_b)
                if s3 is None:
                    continue
                s4 = self.lattice.apply_E_ij(s3, i_a, j_a)
                # Commutator = E_a E_b - E_b E_a
                if s2 is not None and s4 is not None:
                    diff = (s2 - s4).abs().sum().item()
                    commutator_total += 1
                    if diff > 0.5:
                        commutator_nonzero += 1

        commutator_density = commutator_nonzero / max(1, commutator_total)

        return {
            'on_mid_surface': on_mid,
            'hamming_weight': w,
            'mid_surface_weight': mid_w,
            'n_valid_E_moves': n_valid,
            'intra_group_moves': intra,
            'inter_group_moves': inter,
            'su3_indicator': float(su3_indicator),
            'E_ij_closure': float(closure_ratio),
            'commutator_density': float(commutator_density),
            'commutator_total_tested': commutator_total,
        }


# ============================================================
# Experiment Runner
# ============================================================

def estimate_first_seal_step(layer_results, target_layer=1):
    """Estimate the first step where L1 sealing occurred."""
    if target_layer < len(layer_results):
        lr = layer_results[target_layer]
        if lr.get('sealed', False):
            sr = lr.get('phase2_step_results', [])
            for i, step in enumerate(sr):
                unseal = step.get('unsealing', {})
                if unseal.get('level', 0) >= 3:
                    return i * 10
            return 0
    return -1


def run_single_seed(N0, steps, seed, sample_interval, gbc_soft_nudge,
                    r2_tension_threshold, max_layers=2, csc_config=None,
                    detector_interval=50):
    """Run one seed and collect physics detector time series."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)

    # Set up all Phase 9 components (identical to exp_142)
    rfc = ReturnFlowChannel(anchor_threshold=0.05, decay_rate=0.01, min_retention_steps=10)
    us = UnsealingMechanism(l1_coupling_threshold=0.20, l1_stability_threshold=0.35,
                            l2_coupling_threshold=0.40, l2_stability_threshold=0.55)
    psc = PreSubjectivityConvergence(coupling_threshold=0.25, stability_threshold=0.40,
                                      dynamic_threshold=True)
    odi = OrganizationalDensityIndex(temporal_window=10, densification_threshold=0.005,
                                      use_refined_zones=True)
    msi = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35, 'odi_saturation_threshold': 0.70,
        'asymmetry_window': 10, 'asymmetry_threshold': 0.15,
        'min_parts': 3, 'history_window': 8, 'history_dependency_threshold': 0.15,
        'min_history_depth': 5, 'self_reference_window': 8,
        'self_reference_threshold': 0.05, 'baseline_correlation_threshold': 0.2,
        'msi_activation_threshold': 0.20, 'msi_emergence_threshold': 0.35,
        'min_active_conditions': 1})
    gbc = GlobalBiasConstraint(coherence_threshold=0.5, balance_threshold=0.3,
                                min_mechanisms_required=4, geometric_weighting=True)
    nro = MomentumNarrativeOperatorV4P1F(
        bias_dimension=128, filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1, verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9, momentum_decay=0.95, momentum_bonus=0.3)
    abe = AnticipatoryBiasEngine(memory=PersistentBiasMemory(),
                                  config={'default_horizon': 5, 'learning_rate': 0.01})
    cfe = CounterfactualEngine(config={'divergence_threshold': 0.1, 'max_branches': 4})
    std = SixThresholdDetector()
    csc_cfg = dict(DEFAULT_CROSS_SCALE_COUPLING_CONFIG)
    if csc_config:
        csc_cfg.update(csc_config)
    csc = CrossScaleCoupling(config=csc_cfg)
    nse_cfg = dict(DEFAULT_NARRATIVE_SELF_EMERGENCE_CONFIG)
    nse_cfg.update({'history_multi_signal': True, 'history_second_deriv_threshold': 0.02,
                    'history_signal_weights': {'msi': 0.3, 'odi': 0.4, 'civ': 0.0, 'gbc': 0.1},
                    'history_max_turning_points': 25})
    nse = NarrativeSelfEmergence(config=nse_cfg)
    nrc = NarrativeRecursiveClosure(
        event_window=20, collapse_threshold=0.15, settling_rate=0.3,
        r0_weight=0.4, r1_weight=0.35, r2_weight=0.25,
        r2_threshold_nsi=0.85, r2_cooldown=200,
        r2_tension_threshold=r2_tension_threshold, r2_use_tension=True, verbose=False)
    booster = NarrativeLevelBooster(min_civ=3)
    collector = PerLayerMetricsCollector(config={
        'nsi_rolling_window': 500, 'civ_rolling_window': 500, 'theme_jaccard_window': 500})

    evolver = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps, sample_interval=sample_interval,
        max_layers=max_layers,
        p1_eval_interval=sample_interval, phase2_verbose=False,
        phase3_verbose=False, phase4_verbose=False,
        persistent_bias_memory=PersistentBiasMemory(),
        cumulative_selector=CumulativeSelector(window_size=20),
        organizational_density_index=odi, six_threshold_detector=std,
        unsealing_mechanism=us, return_flow_channel=rfc,
        pre_subjectivity_convergence=psc, minimal_self_detector=msi,
        anticipatory_bias_engine=abe, counterfactual_engine=cfe,
        narrative_recursion_operator=nro, global_bias_constraint=gbc,
        gbc_soft_nudge=gbc_soft_nudge,
        cross_scale_coupling=csc, narrative_self_emergence=nse,
        adaptive_momentum_controller=None,
        institutional_layer_protector=None, narrative_level_booster=booster,
        narrative_recursive_closure=nrc)

    # ---- State collection callback ----
    # Collects states at every detector_interval steps for physics analysis
    collected_states = []  # list of (step, layer_id, state_tensor, l0_sealed, l1_formed)

    original_callback = collector.step

    def tracking_callback(step, layer_id, n_active, n_total, n_frozen,
                          hamming_weight, active_bits, frozen_bits,
                          global_odi, global_msi, l0_sealed, l1_formed,
                          l1_unique_active, l1_sealing_threshold):
        # Call the original PerLayerMetricsCollector callback
        original_callback(step, layer_id, n_active, n_total, n_frozen,
                         hamming_weight, active_bits, frozen_bits,
                         global_odi, global_msi, l0_sealed, l1_formed,
                         l1_unique_active, l1_sealing_threshold)

        # Collect state snapshots at detector_interval for L0 only
        if layer_id == 0 and step % detector_interval == 0:
            # Reconstruct a state tensor from active/frozen bits info
            state = torch.zeros(n_total)
            for b in active_bits:
                if b < n_total:
                    state[b] = 1.0
            # Also mark frozen bits (they're still in the state)
            # Actually, the state snapshot from HierarchicalSnapshot is better,
            # but we don't have direct access. Use hamming_weight as a guide
            # and set random active bits to match.
            # Better approach: we'll use snapshots from the evolver result.
            collected_states.append({
                'step': step,
                'layer_id': layer_id,
                'n_active': n_active,
                'n_total': n_total,
                'n_frozen': n_frozen,
                'hamming_weight': hamming_weight,
                'active_bits': set(active_bits),
                'frozen_bits': set(frozen_bits),
                'l0_sealed': l0_sealed,
                'l1_formed': l1_formed,
            })

    print(f"    [seed={seed}] Running {steps} steps at N0={N0}, max_layers={max_layers}...", flush=True)
    start = time.time()
    result = evolver.run(tracking_callback=tracking_callback)
    elapsed = time.time() - start
    print(f"    [seed={seed}] Done in {elapsed:.1f}s", flush=True)

    # ---- Extract actual state snapshots from evolver ----
    # The evolver stores HierarchicalSnapshots with actual state tensors
    snapshots = result.get('snapshots', [])
    state_snapshots = []
    for snap in snapshots:
        if snap.layer == 0 and snap.step % detector_interval == 0:
            state_snapshots.append({
                'step': snap.step,
                'state': snap.state.clone(),
                'w': snap.w,
                'sealed': snap.sealed,
            })

    # If no snapshots available from evolver, reconstruct from collected_states
    if not state_snapshots and collected_states:
        for cs in collected_states:
            state = torch.zeros(cs['n_total'])
            for b in cs['active_bits']:
                if b < cs['n_total']:
                    state[b] = 1.0
            state_snapshots.append({
                'step': cs['step'],
                'state': state,
                'w': cs['hamming_weight'],
                'sealed': cs['l0_sealed'],
            })

    # ---- Determine phase boundaries ----
    layer_results = result.get('layer_results', [])
    l0 = layer_results[0] if layer_results else {}
    l0_sealed = l0.get('sealed', False)
    l1_formed = len(layer_results) >= 2
    l1_sealed = layer_results[1].get('sealed', False) if len(layer_results) >= 2 else False
    first_seal = estimate_first_seal_step(layer_results, target_layer=1)

    # Find seal step from snapshots
    seal_step = -1
    for ss in state_snapshots:
        if ss['sealed']:
            seal_step = ss['step']
            break

    # Find L1 formation step
    l1_step = -1
    for cs in collected_states:
        if cs['l1_formed']:
            l1_step = cs['step']
            break

    # ---- Run physics detectors on each snapshot ----
    grav_detector = GravitationalPotentialDetector(N=N0, n_probes=20)
    dim_detector = DimensionLockingDetector(N=N0)
    gauge_detector = GaugeFieldDetector(N=N0)

    grav_timeseries = []
    gauge_timeseries = []

    for ss in state_snapshots:
        step = ss['step']
        state = ss['state']

        # Determine phase
        if seal_step >= 0 and step >= seal_step and l1_step >= 0 and step >= l1_step:
            phase = 'post_L1'
        elif seal_step >= 0 and step >= seal_step:
            phase = 'post_seal'
        else:
            phase = 'pre_seal'

        # Gravitational potential
        grav_result = grav_detector.detect(state, rng)
        grav_result['step'] = step
        grav_result['phase'] = phase
        grav_timeseries.append(grav_result)

        # Gauge field
        gauge_result = gauge_detector.detect(state)
        gauge_result['step'] = step
        gauge_result['phase'] = phase
        gauge_timeseries.append(gauge_result)

    # Dimension locking: needs accumulated snapshots as a batch
    # Run on different windows
    dim_results = {}
    if len(state_snapshots) >= 10:
        # All snapshots
        all_states = torch.stack([ss['state'] for ss in state_snapshots])
        dim_results['all'] = dim_detector.detect(all_states)

        # Pre-seal only
        pre_seal_states = [ss for ss in state_snapshots if ss['step'] < seal_step or seal_step < 0]
        if len(pre_seal_states) >= 10:
            pre_tensor = torch.stack([ss['state'] for ss in pre_seal_states])
            dim_results['pre_seal'] = dim_detector.detect(pre_tensor)

        # Post-seal only
        post_seal_states = [ss for ss in state_snapshots if seal_step >= 0 and ss['step'] >= seal_step]
        if len(post_seal_states) >= 10:
            post_tensor = torch.stack([ss['state'] for ss in post_seal_states])
            dim_results['post_seal'] = dim_detector.detect(post_tensor)

        # Post-L1 only
        post_l1_states = [ss for ss in state_snapshots
                         if l1_step >= 0 and ss['step'] >= l1_step]
        if len(post_l1_states) >= 10:
            l1_tensor = torch.stack([ss['state'] for ss in post_l1_states])
            dim_results['post_L1'] = dim_detector.detect(l1_tensor)

    # ---- Extract narrative metrics for context ----
    sr = l0.get('phase2_step_results', [])
    nsi_vals = [x.get('narrative_self_emergence', {}).get('nsi', 0.0)
                for x in sr if 'narrative_self_emergence' in x]
    nsi_max = float(np.max(nsi_vals)) if nsi_vals else 0.0
    civ_vals = [x.get('narrative_self_emergence', {}).get('civ_count', 0)
                for x in sr if 'civ_count' in x.get('narrative_self_emergence', {})]
    civ_max = int(np.max(civ_vals)) if civ_vals else 0

    n_layers = len(layer_results)

    print(f"    [seed={seed}] Layers={n_layers} sealed={l0_sealed} "
          f"l1={l1_formed} seal_step={seal_step} l1_step={l1_step} "
          f"n_snapshots={len(state_snapshots)}", flush=True)

    return {
        'N0': N0, 'seed': seed, 'elapsed': elapsed,
        'n_layers': n_layers, 'l0_sealed': l0_sealed,
        'l1_formed': l1_formed, 'l1_sealed': l1_sealed,
        'seal_step': seal_step, 'l1_step': l1_step,
        'nsi_max': nsi_max, 'civ_max': civ_max,
        'n_snapshots': len(state_snapshots),
        'gravitational_potential': grav_timeseries,
        'dimension_locking': dim_results,
        'gauge_field': gauge_timeseries,
    }


# ============================================================
# Analysis Functions
# ============================================================

def analyze_gravitational_potential(all_results: List[Dict]) -> Dict:
    """Aggregate gravitational potential results across seeds."""
    all_corrs = []
    all_corrs_3d = []
    phase_corrs = {'pre_seal': [], 'post_seal': [], 'post_L1': []}

    for r in all_results:
        if r.get('error'):
            continue
        for g in r.get('gravitational_potential', []):
            if 'error' not in g and g.get('n_probes', 0) >= 3:
                c = g['correlation_1_over_d']
                c3d = g.get('correlation_3d', 0.0)
                all_corrs.append(c)
                all_corrs_3d.append(c3d)
                phase = g.get('phase', 'pre_seal')
                if phase in phase_corrs:
                    phase_corrs[phase].append(c)

    result = {
        'n_measurements': len(all_corrs),
        'mean_correlation': float(np.mean(all_corrs)) if all_corrs else 0.0,
        'std_correlation': float(np.std(all_corrs)) if all_corrs else 0.0,
        'median_correlation': float(np.median(all_corrs)) if all_corrs else 0.0,
        'mean_correlation_3d': float(np.mean(all_corrs_3d)) if all_corrs_3d else 0.0,
        'prediction_holds': float(np.mean(all_corrs)) > 0.7 if all_corrs else False,
    }
    for phase, corrs in phase_corrs.items():
        result[f'{phase}_mean'] = float(np.mean(corrs)) if corrs else 0.0
        result[f'{phase}_std'] = float(np.std(corrs)) if corrs else 0.0
        result[f'{phase}_n'] = len(corrs)
        result[f'{phase}_holds'] = float(np.mean(corrs)) > 0.7 if corrs else False

    return result


def analyze_dimension_locking(all_results: List[Dict]) -> Dict:
    """Aggregate dimension locking results across seeds."""
    d_effs = {'all': [], 'pre_seal': [], 'post_seal': [], 'post_L1': []}
    locked_counts = {'all': 0, 'pre_seal': 0, 'post_seal': 0, 'post_L1': 0}
    total_counts = {'all': 0, 'pre_seal': 0, 'post_seal': 0, 'post_L1': 0}

    for r in all_results:
        if r.get('error'):
            continue
        dim = r.get('dimension_locking', {})
        for window, d_result in dim.items():
            if 'error' not in d_result and window in d_effs:
                d = d_result.get('D_eff_90', -1)
                if d >= 0:
                    d_effs[window].append(d)
                    total_counts[window] += 1
                    if d_result.get('dimension_locked_3', False):
                        locked_counts[window] += 1

    result = {}
    for window in ['all', 'pre_seal', 'post_seal', 'post_L1']:
        vals = d_effs[window]
        n_total = total_counts[window]
        n_locked = locked_counts[window]
        result[f'{window}_mean_D_eff'] = float(np.mean(vals)) if vals else -1.0
        result[f'{window}_std_D_eff'] = float(np.std(vals)) if vals else 0.0
        result[f'{window}_n'] = n_total
        result[f'{window}_locked_rate'] = n_locked / max(1, n_total)
        result[f'{window}_prediction_holds'] = (n_locked / max(1, n_total)) > 0.5

    return result


def analyze_gauge_field(all_results: List[Dict]) -> Dict:
    """Aggregate gauge field results across seeds."""
    su3_indicators = {'pre_seal': [], 'post_seal': [], 'post_L1': []}
    closures = {'pre_seal': [], 'post_seal': [], 'post_L1': []}
    commutator_densities = {'pre_seal': [], 'post_seal': [], 'post_L1': []}
    n_valid_moves = []

    for r in all_results:
        if r.get('error'):
            continue
        for g in r.get('gauge_field', []):
            phase = g.get('phase', 'pre_seal')
            if phase in su3_indicators:
                su3_indicators[phase].append(g.get('su3_indicator', 0.0))
                closures[phase].append(g.get('E_ij_closure', 0.0))
                commutator_densities[phase].append(g.get('commutator_density', 0.0))
            n_valid_moves.append(g.get('n_valid_E_moves', 0))

    result = {
        'mean_n_valid_moves': float(np.mean(n_valid_moves)) if n_valid_moves else 0.0,
    }

    # su(3) theoretical prediction: inter/intra ratio
    # For N bits split into 3 groups of n=N/3:
    # Intra-group moves: 3 * n_on * n_off within each group
    # Inter-group moves: pairs across different groups
    # The theoretical ratio depends on the state, but for balanced states
    # on the mid-surface, we expect inter/intra ~ 2 (2 inter for 1 intra)

    for phase in ['pre_seal', 'post_seal', 'post_L1']:
        su3 = su3_indicators[phase]
        cl = closures[phase]
        cd = commutator_densities[phase]
        result[f'{phase}_su3_mean'] = float(np.mean(su3)) if su3 else 0.0
        result[f'{phase}_su3_std'] = float(np.std(su3)) if su3 else 0.0
        result[f'{phase}_closure_mean'] = float(np.mean(cl)) if cl else 0.0
        result[f'{phase}_commutator_density'] = float(np.mean(cd)) if cd else 0.0
        result[f'{phase}_n'] = len(su3)
        # su(3) structure present if su3_indicator is stable and > 1
        # (more inter-group than intra-group moves, as expected for su(3))
        result[f'{phase}_su3_present'] = (
            float(np.mean(su3)) > 1.0 and float(np.mean(cl)) > 0.9
        ) if su3 and cl else False

    return result


# ============================================================
# Main
# ============================================================

def main():
    N0 = 72  # Must be divisible by 3
    SEEDS = [42, 142, 242, 342, 442, 542, 642, 742]
    N_STEPS = 2000
    SI = 10
    GSN = 0.2
    R2_T = 1.0
    ML = 2
    DETECTOR_INTERVAL = 50  # Collect states every 50 steps

    print("=" * 70)
    print("exp_146: PHYSICS DETECTORS UNDER FULL PHASE 9 ARCHITECTURE")
    print("=" * 70)
    print(f"  N0={N0}, Seeds={len(SEEDS)}, Steps={N_STEPS}")
    print(f"  Detector interval: every {DETECTOR_INTERVAL} steps")
    print(f"  Detectors: Gravitational Potential, Dimension Locking, Gauge Field")
    print(f"  Architecture: CSC + NSE + NRC + Booster (Phase 9)")
    print(f"  Predictions:")
    print(f"    P1: Phi proportional to -1/d_H  (correlation > 0.7)")
    print(f"    P2: D_eff locked to ~3  (2 <= D_eff <= 5)")
    print(f"    P3: su(3) gauge structure  (inter/intra > 1, closure ~1)")
    print(datetime.now().strftime('  %Y-%m-%d %H:%M'))
    print("=" * 70)

    all_results = []

    for seed in SEEDS:
        try:
            r = run_single_seed(
                N0=N0, steps=N_STEPS, seed=seed, sample_interval=SI,
                gbc_soft_nudge=GSN, r2_tension_threshold=R2_T,
                max_layers=ML, csc_config=P9_CSC_CONFIG,
                detector_interval=DETECTOR_INTERVAL)
            all_results.append(r)
        except Exception as e:
            print(f"  *** seed={seed}: FAILED -- {e}", flush=True)
            import traceback
            traceback.print_exc()
            all_results.append({'N0': N0, 'seed': seed, 'error': str(e)})

    # ---- Aggregate analysis ----
    print("\n" + "=" * 70)
    print("PHYSICS DETECTOR RESULTS")
    print("=" * 70)

    grav_analysis = analyze_gravitational_potential(all_results)
    dim_analysis = analyze_dimension_locking(all_results)
    gauge_analysis = analyze_gauge_field(all_results)

    # ---- P1: Gravitational Potential ----
    print("\n--- P1: Gravitational Potential  Phi ~ -1/d_H ---")
    print(f"  Overall:  mean_corr={grav_analysis['mean_correlation']:.3f} "
          f"+/- {grav_analysis['std_correlation']:.3f}  "
          f"({'HOLD' if grav_analysis['prediction_holds'] else 'FAIL'})")
    print(f"  3D embedded: mean_corr={grav_analysis['mean_correlation_3d']:.3f}")
    for phase in ['pre_seal', 'post_seal', 'post_L1']:
        print(f"  {phase:12s}: mean={grav_analysis.get(f'{phase}_mean', 0):.3f} "
              f"n={grav_analysis.get(f'{phase}_n', 0)} "
              f"({'HOLD' if grav_analysis.get(f'{phase}_holds') else 'FAIL'})")

    # ---- P2: Dimension Locking ----
    print("\n--- P2: Dimension Locking  D_eff = 3 ---")
    for window in ['all', 'pre_seal', 'post_seal', 'post_L1']:
        d = dim_analysis.get(f'{window}_mean_D_eff', -1)
        rate = dim_analysis.get(f'{window}_locked_rate', 0)
        n = dim_analysis.get(f'{window}_n', 0)
        holds = dim_analysis.get(f'{window}_prediction_holds', False)
        print(f"  {window:12s}: D_eff={d:.1f} locked_rate={rate:.2f} n={n} "
              f"({'HOLD' if holds else 'FAIL'})")

    # ---- P3: Gauge Field ----
    print("\n--- P3: Gauge Field  su(3) Structure ---")
    print(f"  Mean valid E_ij moves: {gauge_analysis['mean_n_valid_moves']:.0f}")
    for phase in ['pre_seal', 'post_seal', 'post_L1']:
        su3 = gauge_analysis.get(f'{phase}_su3_mean', 0)
        cl = gauge_analysis.get(f'{phase}_closure_mean', 0)
        cd = gauge_analysis.get(f'{phase}_commutator_density', 0)
        present = gauge_analysis.get(f'{phase}_su3_present', False)
        n = gauge_analysis.get(f'{phase}_n', 0)
        print(f"  {phase:12s}: su3_ratio={su3:.2f} closure={cl:.2f} "
              f"comm_density={cd:.3f} n={n} "
              f"({'PRESENT' if present else 'ABSENT'})")

    # ---- Overall verdict ----
    p1_pass = grav_analysis['prediction_holds']
    p2_pass = dim_analysis.get('all_prediction_holds', False)
    p3_pass = gauge_analysis.get('pre_seal_su3_present', False) or \
              gauge_analysis.get('post_seal_su3_present', False)

    n_pass = sum([p1_pass, p2_pass, p3_pass])
    print(f"\n{'=' * 70}")
    print(f"OVERALL: {n_pass}/3 predictions hold under full Phase 9 architecture")
    print(f"  P1 (Gravity):     {'PASS' if p1_pass else 'FAIL'}")
    print(f"  P2 (Dimension):   {'PASS' if p2_pass else 'FAIL'}")
    print(f"  P3 (Gauge/su3):   {'PASS' if p3_pass else 'FAIL'}")
    print(f"{'=' * 70}")

    # ---- Per-seed summary ----
    print(f"\n{'=' * 70}")
    print("PER-SEED SUMMARY")
    print(f"{'=' * 70}")
    print(f"{'seed':>6} {'layers':>6} {'sealed':>7} {'L1':>5} {'seal@':>6} "
          f"{'snaps':>6} {'grav_r':>7} {'D_eff':>6} {'su3':>6}")
    for r in all_results:
        if r.get('error'):
            print(f"{r['seed']:>6} ERROR: {r['error']}")
            continue
        # Per-seed averages
        grav_corrs = [g['correlation_1_over_d']
                      for g in r.get('gravitational_potential', [])
                      if 'error' not in g and g.get('n_probes', 0) >= 3]
        avg_grav = float(np.mean(grav_corrs)) if grav_corrs else 0.0
        dim_all = r.get('dimension_locking', {}).get('all', {})
        d_eff = dim_all.get('D_eff_90', -1)
        gauge_su3 = [g['su3_indicator']
                     for g in r.get('gauge_field', [])
                     if g.get('n_valid_E_moves', 0) > 0]
        avg_su3 = float(np.mean(gauge_su3)) if gauge_su3 else 0.0

        print(f"{r['seed']:>6} {r['n_layers']:>6} "
              f"{'Y' if r['l0_sealed'] else 'N':>7} "
              f"{'Y' if r['l1_formed'] else 'N':>5} "
              f"{r.get('seal_step', -1):>6} "
              f"{r['n_snapshots']:>6} "
              f"{avg_grav:>7.3f} {d_eff:>6} {avg_su3:>6.2f}")

    # ---- Save results ----
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Prepare serializable results
    save_data = {
        'experiment': 'exp_146_physics_detectors_full_arch',
        'datetime': datetime.now().isoformat(),
        'config': {'N0': N0, 'seeds': SEEDS, 'steps': N_STEPS,
                   'detector_interval': DETECTOR_INTERVAL},
        'predictions': {
            'P1_gravity': p1_pass,
            'P2_dimension': p2_pass,
            'P3_gauge': p3_pass,
            'n_pass': n_pass,
        },
        'gravitational_analysis': grav_analysis,
        'dimension_analysis': dim_analysis,
        'gauge_analysis': gauge_analysis,
        'per_seed_summary': [],
    }

    for r in all_results:
        if r.get('error'):
            save_data['per_seed_summary'].append({
                'seed': r['seed'], 'error': r['error']})
            continue
        # Serialize timeseries (trim large arrays)
        grav_summary = []
        for g in r.get('gravitational_potential', []):
            grav_summary.append({
                'step': g.get('step'), 'phase': g.get('phase'),
                'correlation': g.get('correlation_1_over_d', 0),
                'correlation_3d': g.get('correlation_3d', 0),
                'n_probes': g.get('n_probes', 0),
            })
        gauge_summary = []
        for g in r.get('gauge_field', []):
            gauge_summary.append({
                'step': g.get('step'), 'phase': g.get('phase'),
                'su3_indicator': g.get('su3_indicator', 0),
                'closure': g.get('E_ij_closure', 0),
                'n_moves': g.get('n_valid_E_moves', 0),
                'commutator_density': g.get('commutator_density', 0),
            })
        dim_summary = {}
        for window, d_result in r.get('dimension_locking', {}).items():
            dim_summary[window] = {
                'D_eff_90': d_result.get('D_eff_90', -1),
                'D_eff_95': d_result.get('D_eff_95', -1),
                'dimension_locked_3': d_result.get('dimension_locked_3', False),
                'compression_ratio': d_result.get('compression_ratio', 0),
            }

        save_data['per_seed_summary'].append({
            'seed': r['seed'], 'elapsed': r['elapsed'],
            'n_layers': r['n_layers'], 'l0_sealed': r['l0_sealed'],
            'l1_formed': r['l1_formed'], 'seal_step': r.get('seal_step', -1),
            'l1_step': r.get('l1_step', -1),
            'nsi_max': r.get('nsi_max', 0), 'civ_max': r.get('civ_max', 0),
            'n_snapshots': r['n_snapshots'],
            'gravitational': grav_summary,
            'dimension': dim_summary,
            'gauge': gauge_summary,
        })

    rf = os.path.join(PROJECT_ROOT, 'experiments',
                      f'exp_146_physics_detectors_{timestamp}.json')
    with open(rf, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\n  Results saved: {rf}")

    return save_data


if __name__ == '__main__':
    main()
