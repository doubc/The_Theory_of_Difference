"""exp_9_base_map_event.py — 底图事件注入实验"""
import torch
from acl.axiom_base import AxiomEngine
from acl.axioms import (
    A1_DifferenceSource, A2_DiscreteEncoding, A3_Locality,
    A4_MinimalVariation, A5_Conservation, A6_FlowCoupling,
    A7_Stability, A8_SymmetrySink, A9_MinimalSufficient,
)
from layers.L0_binary_lattice import L0BinaryLattice
from models.local_conv_model import LocalConvModel
from engine.world_engine import WorldEngine

torch.manual_seed(42)
layer = L0BinaryLattice(shape=(16, 16))
model = LocalConvModel(channels=1)
axioms = [
    A1_DifferenceSource(), A2_DiscreteEncoding(), A3_Locality(),
    A4_MinimalVariation(), A5_Conservation(), A6_FlowCoupling(),
    A7_Stability(), A8_SymmetrySink(), A9_MinimalSufficient(),
]
engine = WorldEngine(
    model=model, layer=layer, axiom_engine=AxiomEngine(axioms),
    xiangjie_check_interval=64, base_map_interval=32,
)

print("=== exp_9: Base-Map Event Injection ===")
result = engine.run(max_steps=128, ascent_check_interval=999)
print(f"Steps: {result['total_steps']}")
print(f"Structures: {result['structures_detected']}")
print(f"Event summary: {result['event_summary']}")
print(f"Base-map events: {len(result['base_map_log'])}")
for bm in result['base_map_log']:
    print(f"  step={bm['step']}, op={bm['operation']}, intensity={bm['intensity']:.3f}")
if result['xiangjie_reports']:
    print(f"Xiangjie reports: {len(result['xiangjie_reports'])}")
    print(result['xiangjie_reports'][-1])
print("=== DONE ===")
