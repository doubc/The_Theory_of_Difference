"""
test_gbc_fix.py - Quick test to verify GBC fix (removal of duplicate P2 GBC block)
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


def run_test(seed=42, steps=200, N0=72):
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
    gbc = GlobalBiasConstraint(coherence_threshold=0.5, balance_threshold=0.3, min_mechanisms_required=4)

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

    # Monkey-patch GBC evaluate to log
    original_evaluate = gbc.evaluate
    gbc_calls = []

    def logged_evaluate(local_biases, coupling_strengths=None):
        bias_info = {}
        for name, vec in local_biases.items():
            bias_info[name] = {
                'norm': float(vec.norm().item()),
                'is_zero': float(vec.norm().item()) < 1e-8,
            }
        result = original_evaluate(local_biases, coupling_strengths)
        gbc_calls.append({
            'n': len(local_biases),
            'mechanisms': list(local_biases.keys()),
            'bias_info': bias_info,
            'coherence': round(result.coherence, 4),
            'balance': round(result.balance, 4),
            'passed': result.passed,
        })
        return result

    gbc.evaluate = logged_evaluate

    print(f'[test_gbc_fix] seed={seed}, steps={steps}, N0={N0}')
    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start
    print(f'[test_gbc_fix] Completed in {elapsed:.1f}s')
    print(f'[test_gbc_fix] GBC evaluate() called {len(gbc_calls)} times')

    if gbc_calls:
        for i, c in enumerate(gbc_calls[:15]):
            print(f'  Call {i}: n={c["n"]}, mech={c["mechanisms"]}, '
                  f'coh={c["coherence"]:.4f}, bal={c["balance"]:.4f}, pass={c["passed"]}')
        if len(gbc_calls) > 15:
            print(f'  ... and {len(gbc_calls) - 15} more calls')

        coherences = [c['coherence'] for c in gbc_calls]
        balances = [c['balance'] for c in gbc_calls]
        passes = [c['passed'] for c in gbc_calls]
        non_zero_coh = [c for c in coherences if c > 0.01]
        print(f'\nGBC summary:')
        print(f'  coherence: min={min(coherences):.4f}, max={max(coherences):.4f}, '
              f'mean={np.mean(coherences):.4f}')
        print(f'  balance:   min={min(balances):.4f}, max={max(balances):.4f}, '
              f'mean={np.mean(balances):.4f}')
        print(f'  passes:    {sum(passes)}/{len(passes)}')
        if non_zero_coh:
            print(f'  non-zero coherence calls: {len(non_zero_coh)}/{len(coherences)} '
                  f'(mean={np.mean(non_zero_coh):.4f})')

        # Check mechanism participation
        mech_counts = {}
        for c in gbc_calls:
            for m in c['mechanisms']:
                mech_counts[m] = mech_counts.get(m, 0) + 1
        print(f'  mechanism participation: {mech_counts}')
    else:
        print('WARNING: GBC was never called!')

    # Also check ODI/MSI
    lr = result['layer_results'][0]
    if 'phase2_step_results' in lr:
        odi_vals = [r['odi']['value'] for r in lr['phase2_step_results'] if 'odi' in r]
        msi_vals = [r['minimal_self']['msi'] for r in lr['phase2_step_results'] if 'minimal_self' in r]
        if odi_vals:
            print(f'\nODI: min={min(odi_vals):.4f}, max={max(odi_vals):.4f}, '
                  f'mean={np.mean(odi_vals):.4f}')
        if msi_vals:
            print(f'MSI: min={min(msi_vals):.4f}, max={max(msi_vals):.4f}, '
                  f'mean={np.mean(msi_vals):.4f}')

    return gbc_calls


if __name__ == '__main__':
    run_test()
