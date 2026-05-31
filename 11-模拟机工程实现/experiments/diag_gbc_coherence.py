"""
diag_gbc_coherence.py - Detailed per-mechanism GBC coherence diagnostic
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
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
from engine.global_bias_constraint import GlobalBiasConstraint
from engine.hierarchical_evolver import HierarchicalEvolver


def run_diagnostic(seed=42, steps=200, N0=72):
    torch.manual_seed(seed)
    np.random.seed(seed)

    pbm = PersistentBiasMemory()
    cs = CumulativeSelector(window_size=20)
    odi = OrganizationalDensityIndex()
    six_threshold = SixThresholdDetector()
    unsealing = UnsealingMechanism(
        l1_coupling_threshold=0.20,
        l1_stability_threshold=0.35,
        l2_coupling_threshold=0.40,
        l2_stability_threshold=0.55,
    )
    rfc = ReturnFlowChannel(anchor_threshold=0.2, decay_rate=0.01, min_retention_steps=10)
    pre_subj = PreSubjectivityConvergence(
        coupling_threshold=0.25,
        stability_threshold=0.40,
        dynamic_threshold=True,
    )
    msi = MinimalSelfDetector(config={
        'odi_activation_threshold': 0.35,
        'asymmetry_threshold': 0.15,
        'history_dependency_threshold': 0.15,
        'self_reference_threshold': 0.05,
    })
    narrative = NarrativeRecursionOperator(bias_dimension=128)
    gbc = GlobalBiasConstraint(coherence_threshold=0.6, balance_threshold=0.5, min_mechanisms_required=4)

    # Monkey-patch to capture per-mechanism details
    original_evaluate = gbc.evaluate
    detailed_calls = []

    def logged_evaluate(local_biases, coupling_strengths=None):
        result = original_evaluate(local_biases, coupling_strengths)
        call_info = {
            'n': len(local_biases),
            'mechanisms': list(local_biases.keys()),
            'coherence': result.coherence,
            'balance': result.balance,
            'passed': result.passed,
            'coherence_by_mechanism': dict(result.coherence_by_mechanism),
            'violating': result.violating_mechanisms,
            'bias_norms': {name: float(v.norm().item()) for name, v in local_biases.items()},
            'bias_mean_abs': {name: float(v.abs().mean().item()) for name, v in local_biases.items()},
            'bias_signs': {name: float(v.sum().item()) for name, v in local_biases.items()},
        }
        detailed_calls.append(call_info)
        return result

    gbc.evaluate = logged_evaluate

    evolver = HierarchicalEvolver(
        N0=N0,
        steps_per_layer=steps,
        sample_interval=10,
        max_layers=1,
        p1_eval_interval=5,
        phase2_verbose=False,
        phase3_verbose=False,
        persistent_bias_memory=pbm,
        cumulative_selector=cs,
        organizational_density_index=odi,
        six_threshold_detector=six_threshold,
        unsealing_mechanism=unsealing,
        return_flow_channel=rfc,
        pre_subjectivity_convergence=pre_subj,
        minimal_self_detector=msi,
        narrative_recursion_operator=narrative,
        global_bias_constraint=gbc,
    )

    print(f'[diag_gbc] seed={seed}, steps={steps}, N0={N0}')
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f'[diag_gbc] Completed in {elapsed:.1f}s')
    print(f'[diag_gbc] GBC evaluate() called {len(detailed_calls)} times\n')

    # Analyze per-mechanism coherence
    mech_coherences = {m: [] for m in ['boundary', 'self_sustaining', 'memory', 'replication', 'selection', 'function']}
    mech_norms = {m: [] for m in ['boundary', 'self_sustaining', 'memory', 'replication', 'selection', 'function']}
    mech_signs = {m: [] for m in ['boundary', 'self_sustaining', 'memory', 'replication', 'selection', 'function']}

    for c in detailed_calls:
        for m, coh in c['coherence_by_mechanism'].items():
            mech_coherences[m].append(coh)
        for m, n in c['bias_norms'].items():
            mech_norms[m].append(n)
        for m, s in c['bias_signs'].items():
            mech_signs[m].append(s)

    print('=== Per-Mechanism Coherence Statistics ===')
    print(f'{"Mechanism":<20} {"N":>4} {"Mean":>8} {"Std":>8} {"Min":>8} {"Max":>8} {"Mean|bias|":>10} {"Mean Sum":>10}')
    print('-' * 90)
    for m in ['boundary', 'self_sustaining', 'memory', 'replication', 'selection', 'function']:
        if mech_coherences[m]:
            cs = mech_coherences[m]
            ns = mech_norms[m]
            ss = mech_signs[m]
            print(f'{m:<20} {len(cs):>4} {np.mean(cs):>8.4f} {np.std(cs):>8.4f} '
                  f'{np.min(cs):>8.4f} {np.max(cs):>8.4f} {np.mean(ns):>10.4f} {np.mean(ss):>10.4f}')
        else:
            print(f'{m:<20} {"N/A":>4} (never participated)')

    # Show worst and best calls
    print(f'\n=== Worst GBC Calls (lowest coherence) ===')
    sorted_calls = sorted(detailed_calls, key=lambda c: c['coherence'])
    for c in sorted_calls[:5]:
        print(f'  coh={c["coherence"]:.4f} bal={c["balance"]:.4f} n={c["n"]} '
              f'violating={c["violating"]}')
        for m, coh in sorted(c['coherence_by_mechanism'].items(), key=lambda x: x[1]):
            sign = "+" if c['bias_signs'][m] >= 0 else "-"
            print(f'    {m:<20} cos_sim={coh:>8.4f}  norm={c["bias_norms"][m]:.4f} '
                  f'mean_abs={c["bias_mean_abs"][m]:.4f} sum_sign={sign}')

    print(f'\n=== Best GBC Calls (highest coherence) ===')
    for c in sorted_calls[-5:]:
        print(f'  coh={c["coherence"]:.4f} bal={c["balance"]:.4f} n={c["n"]} '
              f'violating={c["violating"]}')
        for m, coh in sorted(c['coherence_by_mechanism'].items(), key=lambda x: -x[1]):
            sign = "+" if c['bias_signs'][m] >= 0 else "-"
            print(f'    {m:<20} cos_sim={coh:>8.4f}  norm={c["bias_norms"][m]:.4f} '
                  f'mean_abs={c["bias_mean_abs"][m]:.4f} sum_sign={sign}')

    # Mechanism participation rate
    print(f'\n=== Mechanism Participation ===')
    mech_participation = {}
    for c in detailed_calls:
        for m in c['mechanisms']:
            mech_participation[m] = mech_participation.get(m, 0) + 1
    total_calls = len(detailed_calls)
    for m in ['boundary', 'self_sustaining', 'memory', 'replication', 'selection', 'function']:
        count = mech_participation.get(m, 0)
        print(f'  {m:<20} {count}/{total_calls} ({100*count/max(1,total_calls):.1f}%)')


if __name__ == '__main__':
    run_diagnostic()
