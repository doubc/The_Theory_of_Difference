"""Quick test: verify exp_151 config works after Unicode fix."""
import sys, os, torch, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from engine.subspace_field import (
    SubspaceField, SubspaceSpec, Rules,
    CouplingTopology, CouplingDirection
)
from engine.subspace_evolver import run_subspace_experiment

SLAVE_NAME = 'S1_slave'
MASTER_NAME = 'S0_master'

master_coupling = CouplingTopology(
    direction=CouplingDirection.UNIDIRECTIONAL_FWD,
    strength=0.0,
    peer_names={SLAVE_NAME},
)
slave_coupling = CouplingTopology(
    direction=CouplingDirection.BIDIRECTIONAL,
    strength=0.0,
    peer_names=set(),
)
subspaces = {
    MASTER_NAME: SubspaceSpec(
        bit_indices=set(range(0, 40)),
        rules=Rules.default(),
        coupling=master_coupling,
        name=MASTER_NAME,
    ),
    SLAVE_NAME: SubspaceSpec(
        bit_indices=set(range(40, 60)),
        rules=Rules.default(),
        coupling=slave_coupling,
        name=SLAVE_NAME,
    ),
}
field = SubspaceField(subspaces=subspaces, global_coupling=False)
print('Field OK, connections:', field._connections)

torch.manual_seed(42)
t0 = time.time()
result = run_subspace_experiment(
    field=field,
    steps_per_layer=10,
    max_layers=2,
    coupling_enabled=False,
    verbose=True
)
elapsed = time.time() - t0
print('Done in', round(elapsed, 1), 's')

summary = result.get('summary', {})
for name, info in summary.get('subspaces', {}).items():
    sealed = info.get('ever_sealed')
    nlayers = len(info.get('layers', []))
    hw = info.get('final_hamming_weight')
    print(f'  {name}: sealed={sealed}, layers={nlayers}, hw={hw}')

print('TEST PASSED')
