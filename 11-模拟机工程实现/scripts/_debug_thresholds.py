import sys, json
sys.path.insert(0, r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现')
import torch, numpy as np
from engine.hierarchical_evolver import HierarchicalEvolver
from engine.return_flow_channel import ReturnFlowChannel
from engine.unsealing_mechanism import UnsealingMechanism
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.minimal_self_detector import MinimalSelfDetector
from engine.global_bias_constraint import GlobalBiasConstraint
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from models.narrative_self import NarrativeRecursionOperator
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine

torch.manual_seed(42)
np.random.seed(42)

evolver = HierarchicalEvolver(N0=72, steps_per_layer=50, max_layers=1, p1_eval_interval=5,
    phase2_verbose=False, phase3_verbose=False,
    persistent_bias_memory=PersistentBiasMemory(),
    cumulative_selector=CumulativeSelector(window_size=20),
    organizational_density_index=OrganizationalDensityIndex(temporal_window=5),
    unsealing_mechanism=UnsealingMechanism(l1_coupling_threshold=0.20, l1_stability_threshold=0.35),
    return_flow_channel=ReturnFlowChannel(anchor_threshold=0.05),
    pre_subjectivity_convergence=PreSubjectivityConvergence(),
    minimal_self_detector=MinimalSelfDetector(config={'min_active_conditions':1}),
    anticipatory_bias_engine=AnticipatoryBiasEngine(memory=PersistentBiasMemory(), config={'default_horizon':5}),
    counterfactual_engine=CounterfactualEngine(),
    narrative_recursion_operator=NarrativeRecursionOperator(bias_dimension=128),
    global_bias_constraint=GlobalBiasConstraint(min_mechanisms_required=4))

result = evolver.run()
layer0 = result['layer_results'][0]
steps = layer0['phase2_step_results']
print(f"Total entries: {len(steps)}")
for entry in steps[-3:]:
    st = entry.get('six_threshold', {})
    print(f"\nstep={entry.get('step')}")
    print(f"  six_threshold keys: {list(st.keys())}")
    print(f"  statuses len: {len(st.get('statuses', []))}")
    for s in st.get('statuses', []):
        print(f"    {s['id']} {s['name']}: value={s['value']:.4f} thr={s['threshold']} met={s['is_met']} gap={s['gap']:.4f}")
