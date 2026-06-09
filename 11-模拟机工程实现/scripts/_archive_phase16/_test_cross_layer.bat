@echo off
cd /d "C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现"
python -c "
from engine.cross_layer_evolver import CrossLayerEvolver
print('Import OK')
ev = CrossLayerEvolver(N0=24, N1=24, L0_steps=2000, L1_steps=2000, device='cpu')
print('Init OK')
results = ev.run()
print('L0 sealed:', results['l0_sealed'])
print('L1 sealed:', results['l1_sealed'])
" 2>&1
