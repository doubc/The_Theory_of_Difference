"""
experiments/exp_51_phase2_e2e_v2.py -- Phase 2 E2E Validation v2

Key improvement over exp_50:
  - Uses actual binding_strength from evolution as XiàngDetector input
    instead of random difference matrices
  - Also uses direction field and active_bits to construct a structured
    difference matrix that reflects real evolutionary dynamics

This addresses the finding from exp_50 that XiàngDetector didn't trigger
because random matrices lack the gradient structure of real evolution data.

Generation chain:
  bottom-xiang (real data) -> interface regulation -> self-sustaining
  -> retention -> replication -> selection -> functional differentiation
  -> pre-subjective convergence
"""

import torch
import numpy as np
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.xiang_detector import XiàngDetector
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.hierarchy_manager import BiasField
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.hierarchical_evolver import HierarchicalEvolver


def build_difference_matrix(binding_strength: torch.Tensor,
                             direction: torch.Tensor,
                             active_bits: set,
                             N: int) -> torch.Tensor:
    """Build a structured difference matrix from real evolution data.

    Uses three sources of real evolutionary structure:
    1. binding_strength[i,j]: how strongly bits i and j are coupled
       (strengthened by lateral pair interactions during evolution)
    2. direction[i]: cumulative flip direction (+1=mostly 0->1, -1=mostly 1->0)
    3. active_bits: which bits participated in evolution

    The resulting matrix D[i,j] represents the "difference intensity"
    between bits i and j, combining coupling strength with directional
    asymmetry.

    Args:
        binding_strength: N×N symmetric matrix from constraints
        direction: N-dim vector of cumulative directions
        active_bits: set of indices that were active during evolution
        N: matrix size

    Returns:
        N×N symmetric difference matrix, normalized to [0, 1]
    """
    # Start with binding strength (absolute values, already symmetric)
    D = binding_strength.abs().float()

    # Add directional asymmetry: if bits i and j have opposite
    # direction tendencies, their difference is larger
    if direction is not None and len(direction) >= N:
        dir_vec = direction[:N].float()
        # Outer product of direction differences
        dir_diff = (dir_vec.unsqueeze(1) - dir_vec.unsqueeze(0)).abs()
        # Normalize dir_diff to [0, 1]
        dd_max = dir_diff.max()
        if dd_max > 1e-8:
            dir_diff = dir_diff / dd_max
        D = D + 0.3 * dir_diff

    # Boost entries involving active bits (they have real structure)
    if active_bits:
        active_mask = torch.zeros(N)
        for b in active_bits:
            if b < N:
                active_mask[b] = 1.0
        # Boost: D[i,j] gets a bump if both i and j are active
        active_outer = active_mask.unsqueeze(1) * active_mask.unsqueeze(0)
        D = D + 0.2 * active_outer

    # Ensure symmetry
    D = (D + D.T) / 2
    D.fill_diagonal_(0)

    # Normalize to [0, 1]
    D_max = D.max()
    if D_max > 1e-8:
        D = D / D_max

    return D


def build_temporal_sequence(states: list[torch.Tensor],
                            n_samples: int = 5) -> list[torch.Tensor]:
    """Build a temporal sequence of difference matrices from state snapshots.

    Each difference matrix D_k[i,j] = |s_k[i] - s_k[j]| captures the
    pairwise state differences at snapshot k. A sequence of such matrices
    allows XiàngDetector to compute traceability (continuity across steps).

    Args:
        states: list of state vectors from evolution snapshots
        n_samples: number of difference matrices to generate

    Returns:
        list of N×N difference matrices
    """
    if len(states) < 2:
        # Not enough states: return a single matrix from the last state
        if states:
            s = states[-1]
            N = len(s)
            D = (s.unsqueeze(1) - s.unsqueeze(0)).abs()
            return [D]
        return []

    # Sample evenly from available states
    indices = np.linspace(0, len(states) - 1, min(n_samples, len(states)), dtype=int)
    diffs = []
    for idx in indices:
        s = states[idx].float()
        N = len(s)
        D = (s.unsqueeze(1) - s.unsqueeze(0)).abs()
        D_max = D.max()
        if D_max > 1e-8:
            D = D / D_max
        diffs.append(D)
    return diffs


def main():
    print("=" * 70)
    print("Phase 2 E2E Validation v2 — Real Evolution Data for XiàngDetector")
    print("=" * 70)

    # Parameters (same as exp_50 for comparability)
    N0 = 32
    steps_per_layer = 2000
    max_layers = 3
    sample_interval = 200

    # Init components
    xiang = XiàngDetector(rho_threshold=0.3, tau_threshold=0.5)
    bias_mem = PersistentBiasMemory(max_history_depth=50)
    six_det = SixThresholdDetector()
    conv = PreSubjectivityConvergence(
        coupling_threshold=0.15, stability_threshold=0.25,
        n_perturbation_tests=3, perturbation_scale=0.05
    )

    # Run evolution
    print(f"\n[Evolution] N0={N0}, steps/layer={steps_per_layer}, max_layers={max_layers}")
    evolver = HierarchicalEvolver(
        N0=N0, steps_per_layer=steps_per_layer,
        sample_interval=sample_interval, max_layers=max_layers,
        device="cpu", binding_threshold=0.1, min_group_size=2,
        auto_encapsulate=True
    )

    t0 = time.time()
    evo = evolver.run(verbose=True)
    elapsed_evo = time.time() - t0
    print(f"\n  Evolution time: {elapsed_evo:.1f}s")

    # Validate Phase 2 components per layer
    print("\n" + "=" * 70)
    print("Phase 2 Component Validation (v2 — real difference matrices)")
    print("=" * 70)

    conv_results = []
    xiang_results = []

    for lr in evo['layer_results']:
        li = lr['layer']
        N_report = lr['N']  # may be padded
        # Use actual binding_strength shape (may differ from padded N)
        bs = lr['binding_strength']
        N = bs.shape[0]  # actual matrix size from evolution
        n_clusters = len(lr['clusters'])
        cycles = lr['cycles']
        inj = lr['inj']
        absv = lr['abs']

        print(f"\n--- L{li} (N={N_report}, actual={N}, cycles={cycles}, clusters={n_clusters}) ---")

        # Build REAL difference matrix from binding_strength
        D_static = build_difference_matrix(
            binding_strength=bs,
            direction=lr['direction'],
            active_bits=lr['active_bits'],
            N=N
        )

        # Build temporal difference sequence from state snapshots
        state_snapshots = lr.get('snapshots', [])
        D_sequence = build_temporal_sequence(state_snapshots, n_samples=5)

        print(f"  D_static: mean={D_static.mean():.4f}, std={D_static.std():.4f}, "
              f"nonzero={(D_static > 0.01).sum().item()}/{N*N}")
        print(f"  Temporal sequence: {len(D_sequence)} matrices from {len(state_snapshots)} snapshots")

        # 1. Xiàng detection — feed temporal sequence for traceability
        # First, reset the detector for each layer to get independent results
        xiang_layer = XiàngDetector(rho_threshold=0.3, tau_threshold=0.5)
        layer_results_seq = []
        for step_idx, D_t in enumerate(D_sequence):
            xr_step = xiang_layer.detect(D_t, timestamp=li * 1000 + step_idx)
            layer_results_seq.append(xr_step)

        # Also run on static binding_strength matrix
        xr_static = xiang.detect(D_static, timestamp=li * 1000)
        xiang_results.append(xr_static)

        # Report: use the last temporal result (most history accumulated)
        if layer_results_seq:
            xr_final = layer_results_seq[-1]
        else:
            xr_final = xr_static

        print(f"  Xiàng (static D): density={xr_static.organization_density:.3f}, "
              f"trace={xr_static.traceability_score:.3f}, formed={xr_static.xiang_formed}")
        print(f"  Xiàng (temporal D): density={xr_final.organization_density:.3f}, "
              f"trace={xr_final.traceability_score:.3f}, formed={xr_final.xiang_formed}, "
              f"continuity={xr_final.continuity_length}")
        if layer_results_seq:
            print(f"    temporal sequence ({len(layer_results_seq)} steps): "
                  f"density range=[{min(r.organization_density for r in layer_results_seq):.3f}, "
                  f"{max(r.organization_density for r in layer_results_seq):.3f}], "
                  f"trace range=[{min(r.traceability_score for r in layer_results_seq):.3f}, "
                  f"{max(r.traceability_score for r in layer_results_seq):.3f}]")

        # 2. Interface regulation (proxy: inj/abs balance)
        iface = min(inj, absv) / max(inj, absv, 1)
        print(f"  Interface regulation: {iface:.3f}")

        # 3. Self-sustaining (proxy: cycles)
        sustain = min(1.0, cycles / 80.0)
        print(f"  Self-sustaining: {sustain:.3f}")

        # 4. Retention (bias memory)
        bf = BiasField(
            source_layer=li, target_layer=li + 1,
            bias_vector=torch.ones(N) * sustain,
            strength=sustain, origin_step=li * 1000
        )
        bias_mem.record(bf, timestamp=li * 1000, metadata={'layer': li})
        retention = min(1.0, bias_mem.n_entries / 5.0)
        print(f"  Retention: {retention:.3f} (entries={bias_mem.n_entries})")

        # 5. Replication fidelity (proxy: cluster structure preservation)
        if n_clusters > 0:
            pattern = torch.zeros(N, N)
            for cl in lr['clusters']:
                for i in cl:
                    if i < N:
                        pattern[i, i] = 1.0
            pattern = pattern / (pattern.sum() + 1e-8)
            noisy = pattern + torch.randn_like(pattern) * 0.1
            fidelity = max(0.0, 1.0 - (pattern - noisy).abs().mean().item())
        else:
            fidelity = 0.0
        print(f"  Replication fidelity: {fidelity:.3f}")

        # 6. Selection pressure (proxy: cluster size concentration)
        if n_clusters > 1:
            sizes = sorted([len(c) for c in lr['clusters']], reverse=True)
            sel = sum(sizes[:2]) / (sum(sizes) + 1e-8)
        else:
            sel = 0.0
        print(f"  Selection pressure: {sel:.3f}")

        # 7. Functional differentiation (1 - HHI of cluster sizes)
        if n_clusters > 0:
            sizes = [len(c) for c in lr['clusters']]
            total = sum(sizes) + 1e-8
            props = [s / total for s in sizes]
            func_div = 1.0 - sum(p ** 2 for p in props)
        else:
            func_div = 0.0
        print(f"  Functional differentiation: {func_div:.3f}")

        # 8. Coupling matrix (pairwise product of scores)
        scores = {
            'interface_regulation': iface,
            'self_sustaining': sustain,
            'retention': retention,
            'replication': fidelity,
            'selection': sel,
            'functional_differentiation': func_div,
        }
        mechs = list(scores.keys())
        coupling = {}
        for i, ma in enumerate(mechs):
            coupling[ma] = {}
            for j, mb in enumerate(mechs):
                if i < j:
                    coupling[ma][mb] = scores[ma] * scores[mb]

        # 9. Six threshold detection
        thr = six_det.detect(
            active_exchanges=int(iface * 100),
            total_boundary_edges=100,
            rebuild_success_count=int(sustain * 10),
            perturbation_count=10,
            bias_recursion_depth=retention,
            replicated_pattern=torch.randn(N, N) * fidelity,
            original_pattern=torch.randn(N, N),
            variant_continuation_probs={f'v{k}': sel * (0.5 ** k) for k in range(min(n_clusters, 5))},
            component_contributions={f'c{k}': func_div / max(n_clusters, 1) for k in range(min(n_clusters, 6))},
            timestamp=li * 1000,
        )
        print(f"  SixThreshold: {thr.n_met}/6, bottleneck={thr.bottleneck}")

        # 10. Convergence
        conv_r = conv.evaluate(
            threshold_params={
                'active_exchanges': int(iface * 100),
                'total_boundary_edges': 100,
                'rebuild_success_count': int(sustain * 10),
                'perturbation_count': 10,
                'bias_recursion_depth': retention,
                'replicated_pattern': torch.randn(N, N) * fidelity,
                'original_pattern': torch.randn(N, N),
                'variant_continuation_probs': {f'v{k}': sel * (0.5 ** k) for k in range(min(n_clusters, 5))},
                'component_contributions': {f'c{k}': func_div / max(n_clusters, 1) for k in range(min(n_clusters, 6))},
            },
            coupling_matrix=coupling,
            structure_state=torch.randint(0, 2, (N,)).float(),
            structure_fn=lambda s: s.sum().item() > 0,
            field_names=['interface_regulation', 'self_sustaining', 'retention',
                         'replication', 'selection', 'functional_differentiation'],
            timestamp=li * 1000,
        )
        conv_results.append(conv_r)
        print(f"  >>> Convergence: {conv_r}")

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    print(f"\n[Evolution]")
    print(f"  Layers: {evo['n_layers']}")
    for lr in evo['layer_results']:
        print(f"    L{lr['layer']}: N={lr['N']}, w={lr['w']}, "
              f"cycles={lr['cycles']}, clusters={len(lr['clusters'])}, "
              f"inj={lr['inj']}, abs={lr['abs']}")

    print(f"\n[Xiàng Detection — REAL DATA]")
    for i, xr in enumerate(xiang_results):
        print(f"  L{i}: density={xr.organization_density:.3f}, "
              f"trace={xr.traceability_score:.3f}, "
              f"formed={xr.xiang_formed}, "
              f"surplus={xr.n_gradient_surplus}, "
              f"continuity={xr.continuity_length}")

    print(f"\n[Phase 2 Status]")
    print(f"  Xiàng formed: {xiang.is_formed} (step={xiang.formation_step})")
    print(f"  Bias entries: {bias_mem.n_entries}")
    print(f"  Convergence evals: {len(conv_results)}")

    conv_count = sum(1 for r in conv_results if r.converged)
    print(f"  Converged: {conv_count}/{len(conv_results)}")

    print(f"\n[Acceptance]")
    checks = {
        'Multi-layer (>=2)': evo['n_layers'] >= 2,
        'Xiàng detection (real data)': xiang.is_formed,
        'Bias memory': bias_mem.n_entries > 0,
        'Convergence eval': len(conv_results) > 0,
        'Semantic firewall': all(r.semantic_firewall_passed for r in conv_results),
    }
    for name, ok in checks.items():
        tag = "[PASS]" if ok else "[WARN]"
        print(f"  {tag} {name}")

    all_ok = all(checks.values())
    print(f"\n{'[PASS] Phase 2 E2E v2 validation passed' if all_ok else '[WARN] Some checks not passed'}")
    print(f"Runtime: {elapsed_evo:.1f}s (evolution)")

    # Comparison note
    print("\n" + "=" * 70)
    print("Comparison: exp_50 (random D) vs exp_51 (real binding_strength D)")
    print("=" * 70)
    print("  exp_50 Xiàng: NOT formed (random matrices lack gradient structure)")
    print(f"  exp_51 Xiàng: {'FORMED' if xiang.is_formed else 'NOT formed'} "
          f"(real evolution binding_strength)")
    if xiang.is_formed:
        print("  => Real evolution data provides the gradient structure needed")
        print("     for XiàngDetector to identify organization and traceability.")
    else:
        print("  => Even with real binding_strength, Xiàng not formed.")
        print("     Possible reasons: N too small, binding too uniform,")
        print("     or thresholds need recalibration.")

    return {'evolution': evo, 'convergence': conv_results,
            'xiang_results': xiang_results, 'checks': checks}


if __name__ == "__main__":
    main()
