"""Quick test for ConstraintBiasedCoupling"""
import sys
import os
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from engine.cross_scale_coupling import ConstraintBiasedCoupling

# 初始化
config = {'l1_bias_strength': 0.4, 'l1_frozen_gravity': 0.3}
cbc = ConstraintBiasedCoupling(config)
print('Init OK')

# 模拟几步
np.random.seed(42)
for step in range(100):
    l0_stability = 0.5 + np.random.randn() * 0.02
    l0_stability = np.clip(l0_stability, 0.0, 1.0)
    l1_stability = 0.4 + np.random.randn() * 0.01
    l1_stability = np.clip(l1_stability, 0.0, 1.0)
    l1_frozen_bits = {1, 2, 3} if step > 50 else set()
    
    l0_state = {
        'stability_score': float(l0_stability),
        'odi': 0.3,
        'structure_vector': None,
        'active_bits': set(range(48)),
    }
    l1_state = {
        'stability_score': float(l1_stability),
        'odi': 0.2,
        'structure_vector': None,
        'frozen_bits': l1_frozen_bits,
    }
    
    l2_state = cbc.update(l0_state, l1_state)
    if step % 20 == 0:
        print(f"Step {step}: L2_stability={l2_state['stability_score']:.3f}, "
              f"bias_effect={l2_state.get('l1_bias_effect', 0):.4f}, "
              f"bias_strength={l2_state.get('l1_bias_strength', 0):.4f}")

# 获取摘要
summary = cbc.get_summary()
print('Summary:', summary)
print('Test PASSED')
