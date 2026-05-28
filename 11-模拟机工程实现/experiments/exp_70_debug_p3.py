"""Quick debug: check if p3_active is ever True and what MSI values look like."""
import sys, os, time
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import torch
import numpy as np
from engine.hierarchical_evolver import HierarchicalEvolver
from engine.persistent_bias_memory import PersistentBiasMemory
from engine.cumulative_selector import CumulativeSelector
from engine.six_threshold_detector import SixThresholdDetector
from engine.pre_subjectivity_convergence import PreSubjectivityConvergence
from engine.unsealing_mechanism import UnsealingMechanism
from engine.return_flow_channel import ReturnFlowChannel
from engine.organizational_density_index import OrganizationalDensityIndex
from engine.seventh_threshold_detector import SeventhThresholdDetector
from engine.cooperative_emergence_detector import CooperativeEmergenceDetector
from engine.lateral_coupling import LateralCoupler
from engine.minimal_self_detector import MinimalSelfDetector
from engine.anticipatory_bias_engine import AnticipatoryBiasEngine
from engine.counterfactual_engine import CounterfactualEngine

pbm = PersistentBiasMemory()
cs = CumulativeSelector()
six_td = SixThresholdDetector()
psc = PreSubjectivityConvergence(coupling_mode='weighted', coupling_threshold=0.30)
um = UnsealingMechanism()
rfc = ReturnFlowChannel()
odi = OrganizationalDensityIndex()
std = SeventhThresholdDetector()
ced = CooperativeEmergenceDetector()
lc = LateralCoupler()
msd = MinimalSelfDetector()
abe = AnticipatoryBiasEngine(memory=pbm)
cfe = CounterfactualEngine()

evolver = HierarchicalEvolver(
    N0=72, steps_per_layer=300, sample_interval=5, max_layers=1,
    p1_eval_interval=5, device='cpu',
    persistent_bias_memory=pbm, cumulative_selector=cs,
    six_threshold_detector=six_td, pre_subjectivity_convergence=psc,
    unsealing_mechanism=um, return_flow_channel=rfc,
    organizational_density_index=odi, seventh_threshold_detector=std,
    cooperative_emergence_detector=ced, lateral_coupler=lc,
    minimal_self_detector=msd, anticipatory_bias_engine=abe,
    counterfactual_engine=cfe,
    phase2_verbose=True, phase3_verbose=True,
)

results = evolver.run(verbose=True)

# Analyze
layer_results = results.get('layer_results', [])
p3_active_count = 0
msi_nonzero_count = 0
total_p1 = 0
for lr in layer_results:
    for sr in lr.get('phase2_step_results', []):
        has_odi = 'odi' in sr and sr['odi'] is not None
        if has_odi:
            total_p1 += 1
            odi_val = sr['odi'].get('value', 0.0)
            p3_active = odi_val >= 0.5
            if p3_active:
                p3_active_count += 1
            has_msi = 'minimal_self' in sr and sr['minimal_self'] is not None
            if has_msi:
                msi_val = sr['minimal_self'].get('msi', 0.0)
                if msi_val > 0:
                    msi_nonzero_count += 1
                print(f"  Step {sr.get('step', '?')}: ODI={odi_val:.4f}, p3_active={p3_active}, MSI={msi_val:.4f}, detected={sr['minimal_self'].get('detected', False)}")
            else:
                print(f"  Step {sr.get('step', '?')}: ODI={odi_val:.4f}, p3_active={p3_active}, NO minimal_self entry")

print(f"\nSummary:")
print(f"  Total P1 evaluations: {total_p1}")
print(f"  p3_active count: {p3_active_count}")
print(f"  MSI > 0 count: {msi_nonzero_count}")

# Also check the latest result from evolver
p3s = results.get('phase3_summary', {})
print(f"\nPhase 3 summary from evolver:")
print(f"  minimal_self_detected: {p3s.get('minimal_self_detected', False)}")
print(f"  msi: {p3s.get('msi', 0.0):.4f}")
print(f"  anticipation_reliable: {p3s.get('anticipation_reliable', False)}")
print(f"  counterfactual_active: {p3s.get('counterfactual_active', False)}")
