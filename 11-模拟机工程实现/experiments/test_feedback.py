"""Quick test of CrossLayerEvolver with feedback"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.cross_layer_evolver import CrossLayerEvolver

print("Testing CrossLayerEvolver with feedback...")
ev = CrossLayerEvolver(
    N0=48, N1=48,
    L0_steps=5000, L1_steps=5000,
    device='cpu',
    enable_l0_feedback=True,
)
print("Running...")
results = ev.run()
print(f"L0 sealed: {results.get('l0_sealed')}")
print(f"L1 sealed: {results.get('l1_sealed')}")
print(f"L0 seal step: {results.get('l0_seal_step')}")
print(f"L1 seal step: {results.get('l1_seal_step')}")
print("SUCCESS!")
