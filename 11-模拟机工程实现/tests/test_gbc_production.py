"""Test GBC with production thresholds (coherence>=0.6, balance>=0.5)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch, numpy as np, time
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

for seed in [42, 142]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    pbm = PersistentBiasMemory()
    cs = CumulativeSelector(window_size=20)
    odi = OrganizationalDensityIndex()
    six_threshold = SixThresholdDetector()
    unsealing = UnsealingMechanism(l1_coupling_threshold=0.20, l1_stability_threshold=0.35, l2_coupling_threshold=0.40, l2_stability_threshold=0.55)
    rfc = ReturnFlowChannel(anchor_threshold=0.2, decay_rate=0.01, min_retention_steps=10)
    pre_subj = PreSubjectivityConvergence(coupling_threshold=0.25, stability_threshold=0.40, dynamic_threshold=True)
    msi = MinimalSelfDetector(config={'odi_activation_threshold': 0.35, 'asymmetry_threshold': 0.15, 'history_dependency_threshold': 0.15, 'self_reference_threshold': 0.05})
    narrative = NarrativeRecursionOperator(bias_dimension=128)
    gbc = GlobalBiasConstraint(coherence_threshold=0.6, balance_threshold=0.5, min_mechanisms_required=4)

    evolver = HierarchicalEvolver(N0=72, steps_per_layer=200, sample_interval=10, max_layers=1, p1_eval_interval=5, phase2_verbose=False, phase3_verbose=False, persistent_bias_memory=pbm, cumulative_selector=cs, organizational_density_index=odi, six_threshold_detector=six_threshold, unsealing_mechanism=unsealing, return_flow_channel=rfc, pre_subjectivity_convergence=pre_subj, minimal_self_detector=msi, narrative_recursion_operator=narrative, global_bias_constraint=gbc)

    start = time.time()
    result = evolver.run()
    elapsed = time.time() - start

    history = gbc.get_history()
    if history:
        latest = history[-1]
        coh_pass = latest.coherence >= 0.6
        bal_pass = latest.balance >= 0.5
        print(f"seed={seed}: coh={latest.coherence:.4f} ({'PASS' if coh_pass else 'FAIL'}), "
              f"bal={latest.balance:.4f} ({'PASS' if bal_pass else 'FAIL'}), "
              f"passed={latest.passed}, violating={latest.violating_mechanisms}, "
              f"n_mech={len(latest.local_biases)}, time={elapsed:.1f}s")
        # Per-mechanism
        for m, c in sorted(latest.coherence_by_mechanism.items(), key=lambda x: x[1]):
            tag = "OK" if c >= 0.6 else "LOW"
            print(f"  {m:<20} cos_sim={c:.4f} [{tag}]")
    else:
        print(f"seed={seed}: No GBC history!")
