"""
exp_78: GBC 零偏置根因诊断

问题：exp_77 中 GBC coherence/balance 全部为零，说明 evaluate() 从未被成功调用。
可能原因：
  1. P1 块中 6 个偏置提取大部分返回零/None，导致 n_mechanisms < 4
  2. P2 块中 self.self_sustaining_circulation/replicate_pattern/functional_differentiation 从未被注入

本实验：逐步运行，在 P1 周期内详细记录每个机制的偏置提取状态（向量范数、是否为零），
定位到底是哪些机制的偏置提取失败了。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
import json
import time

from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.six_threshold_detector import SixThresholdDetector
from engine.unsealing_mechanism import UnsealingMechanism
from engine.return_flow_channel import ReturnFlowChannel
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.minimal_self_detector import MinimalSelfDetector
from models.narrative_self import NarrativeRecursionOperator
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine
from engine.global_bias_constraint import GlobalBiasConstraint
from engine.hierarchical_evolver import HierarchicalEvolver
from engine.self_sustaining_circulation import SelfSustainingCirculation
from engine.replicate_pattern import ReplicatePattern
from engine.functional_differentiation import FunctionalDifferentiation


def run_diagnostic(seed: int = 42, steps: int = 200, N0: int = 72):
    """运行短演化，详细记录每个 P1 步中各机制的偏置提取状态"""

    torch.manual_seed(seed)
    np.random.seed(seed)

    # 创建组件（与 exp_77 相同）
    pbm = PersistentBiasMemory()
    cs = CumulativeSelector(window_size=20)
    odi = OrganizationalDensityIndex()
    six_threshold = SixThresholdDetector()
    unsealing = UnsealingMechanism(
        base_probability=0.05,
        min_frozen_steps=10,
        bias_pressure_weight=0.3,
    )
    rfc = ReturnFlowChannel(
        upstream_dim=N0,
        downstream_dim=N0,
        capacity=50,
    )
    pre_subj = PreSubjectivityConvergence(
        N=N0,
        odi_floor=0.5,
        msi_activation_threshold=0.20,
        msi_emergence_threshold=0.35,
        min_active_conditions=1,
    )
    msi = MinimalSelfDetector(
        bias_dimension=N0,
        filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1,
        verifier_consistency_threshold=0.3,
    )
    narrative = NarrativeRecursionOperator(
        bias_dimension=128,
        filter_magnitude_threshold=0.02,
        connector_strength_threshold=0.1,
        verifier_consistency_threshold=0.3,
        narrative_decay_rate=0.9,
    )
    anticipatory = AnticipatoryBiasEngine(
        memory=PersistentBiasMemory(),
        config={'default_horizon': 5, 'learning_rate': 0.01},
    )
    counterfactual = CounterfactualEngine(config={
        'divergence_threshold': 0.1,
        'max_branches': 4,
    })
    gbc = GlobalBiasConstraint(
        coherence_threshold=0.5,
        balance_threshold=0.3,
        min_mechanisms_required=4,
        geometric_weighting=True,
    )

    # Create the three missing components that GBC P2 block needs
    ssc = SelfSustainingCirculation()
    rp = ReplicatePattern()
    fd = FunctionalDifferentiation()

    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps,
        sample_interval=5,
        max_layers=1,
        p1_eval_interval=5,
        phase2_verbose=True,
        phase3_verbose=False,
        persistent_bias_memory=pbm,
        cumulative_selector=cs,
        organizational_density_index=odi,
        six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing,
        return_flow_channel=rfc,
        pre_subjectivity_convergence=pre_subj,
        minimal_self_detector=msi,
        anticipatory_bias_engine=anticipatory,
        counterfactual_engine=counterfactual,
        narrative_recursion_operator=narrative,
        global_bias_constraint=gbc,
    )

    # INJECT the three missing components (monkey-patch)
    # These are used by the P2 GBC block (line ~1270)
    evolver.self_sustaining_circulation = ssc
    evolver.replicate_pattern = rp
    evolver.functional_differentiation = fd

    # Monkey-patch GBC evaluate to log detailed bias info
    original_evaluate = gbc.evaluate
    gbc_call_log = []

    def logged_evaluate(local_biases, coupling_strengths=None):
        # Log each bias vector's norm
        bias_info = {}
        for name, vec in local_biases.items():
            if isinstance(vec, torch.Tensor):
                bias_info[name] = {
                    'norm': float(vec.norm().item()),
                    'mean_abs': float(vec.abs().mean().item()),
                    'shape': list(vec.shape),
                    'is_zero': float(vec.norm().item()) < 1e-8,
                }
            else:
                bias_info[name] = {'type': str(type(vec)), 'is_zero': True}

        result = original_evaluate(local_biases, coupling_strengths)

        log_entry = {
            'n_biases': len(local_biases),
            'bias_info': bias_info,
            'passed': result.passed,
            'coherence': result.coherence,
            'balance': result.balance,
            'violating': result.violating_mechanisms,
            'description': result.description[:120],
        }
        gbc_call_log.append(log_entry)
        return result

    gbc.evaluate = logged_evaluate

    # Also check what components are missing from evolver
    missing_components = {
        'self_sustaining_circulation': evolver.self_sustaining_circulation,
        'replicate_pattern': evolver.replicate_pattern,
        'functional_differentiation': evolver.functional_differentiation,
    }

    print(f"\n[exp_78] GBC Bias Diagnostic — seed={seed}, steps={steps}, N0={N0}")
    print(f"\n=== Missing Component Check ===")
    for name, val in missing_components.items():
        status = "MISSING (None)" if val is None else f"present: {type(val).__name__}"
        print(f"  {name}: {status}")

    print(f"\n=== Running evolution ===")
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f"[exp_78] Completed in {elapsed:.1f}s")

    # Analyze GBC call log
    print(f"\n=== GBC Call Analysis ===")
    print(f"Total GBC evaluate() calls: {len(gbc_call_log)}")

    if len(gbc_call_log) == 0:
        print("WARNING: GBC evaluate() was NEVER called!")
        print("This means local_biases dict was always empty (no mechanism passed norm > 1e-8)")
    else:
        # Summarize which mechanisms appeared and their typical norms
        mechanism_stats = {}
        for entry in gbc_call_log:
            for mech, info in entry.get('bias_info', {}).items():
                if mech not in mechanism_stats:
                    mechanism_stats[mech] = {'count': 0, 'norms': [], 'zero_count': 0}
                mechanism_stats[mech]['count'] += 1
                mechanism_stats[mech]['norms'].append(info.get('norm', 0))
                if info.get('is_zero', False):
                    mechanism_stats[mech]['zero_count'] += 1

        print("\nMechanism bias statistics (across all GBC calls):")
        for mech, stats in mechanism_stats.items():
            norms = stats['norms']
            print(f"  {mech}: called {stats['count']}x, "
                  f"norm range [{min(norms):.6f}, {max(norms):.6f}], "
                  f"zero {stats['zero_count']}/{stats['count']}")

        # Count how many times n_biases >= 4 (enough for GBC to run)
        enough = sum(1 for e in gbc_call_log if e['n_biases'] >= 4)
        print(f"\nCalls with n_biases >= 4: {enough}/{len(gbc_call_log)}")

        # Show first few call details
        print("\nFirst 5 GBC calls:")
        for i, entry in enumerate(gbc_call_log[:5]):
            print(f"  Call {i}: n_biases={entry['n_biases']}, "
                  f"mechanisms={list(entry['bias_info'].keys())}, "
                  f"passed={entry['passed']}, "
                  f"coh={entry['coherence']:.3f}, bal={entry['balance']:.3f}")
            for mech, info in entry['bias_info'].items():
                print(f"    {mech}: norm={info.get('norm',0):.6f}, "
                      f"mean_abs={info.get('mean_abs',0):.6f}, "
                      f"zero={info.get('is_zero',True)}")

    # Now let's also manually check: what does the P1 block see?
    # Let's directly check what constraints.direction looks like
    print(f"\n=== Manual Component State Check ===")

    layer_0 = result.get('layer_results', [{}])[0]
    step_results = layer_0.get('phase2_step_results', [])
    print(f"Step results recorded: {len(step_results)}")

    # Check PBM state
    print(f"PBM entries: {pbm.n_entries}")
    if pbm.n_entries > 0:
        acc_field = pbm.get_accumulated(0, n_bits=N0)
        if acc_field is not None:
            print(f"PBM accumulated field norm: {acc_field.norm().item():.6f}")
            print(f"PBM accumulated field mean_abs: {acc_field.abs().mean().item():.6f}")
        else:
            print("PBM accumulated field: None")
    else:
        print("PBM: no entries")

    # Check CS state
    cs_variants = cs._variants if hasattr(cs, '_variants') else {}
    print(f"CumulativeSelector variants: {len(cs_variants)}")
    if cs_variants:
        # Try to get selection pressure vector
        sp_vec = cs.get_selection_pressure_vector() if hasattr(cs, 'get_selection_pressure_vector') else None
        if sp_vec is not None:
            print(f"CS selection_pressure_vector norm: {sp_vec.norm().item():.6f}")
        else:
            print("CS selection_pressure_vector: None")

    # Save results
    output = {
        'experiment': 'exp_78_gbc_bias_diagnostic',
        'seed': seed,
        'steps': steps,
        'N0': N0,
        'missing_components': {k: v is None for k, v in missing_components.items()},
        'gbc_call_log': gbc_call_log,
        'pbm_entries': pbm.n_entries,
        'cs_variant_count': len(cs_variants) if hasattr(cs, '_variants') else 0,
    }

    out_path = os.path.join(os.path.dirname(__file__),
                            f'exp_78_results_{time.strftime("%Y%m%d_%H%M%S")}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved to: {out_path}")

    return output


if __name__ == '__main__':
    run_diagnostic()
