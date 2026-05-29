"""Diagnostic: check exact threshold values."""
import torch, sys, math
sys.path.insert(0, r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现')

from engine.counterfactual_engine import DivergencePointTracker, DEFAULT_COUNTERFACTUAL_CONFIG

print(f"entropy_threshold: {DEFAULT_COUNTERFACTUAL_CONFIG['divergence_entropy_threshold']}")
print(f"ratio_threshold: {DEFAULT_COUNTERFACTUAL_CONFIG['divergence_ratio_threshold']}")
print()

tracker = DivergencePointTracker()
state = torch.randn(10)

# Test various probability distributions
test_cases = [
    ("Uniform 4", [0.25, 0.25, 0.25, 0.25]),
    ("Uniform 3", [0.33, 0.33, 0.34]),
    ("Slight skew", [0.35, 0.30, 0.20, 0.15]),
    ("Moderate skew", [0.40, 0.30, 0.20, 0.10]),
    ("Strong skew", [0.50, 0.30, 0.15, 0.05]),
    ("Dominant", [0.95, 0.03, 0.02]),
    ("Binary equal", [0.50, 0.50]),
    ("Binary skew", [0.70, 0.30]),
]

for name, probs in test_cases:
    t = DivergencePointTracker()
    dirs = [torch.randn(10) for _ in range(len(probs))]
    div = t.detect_divergence(current_state=state, candidate_directions=dirs, direction_probs=probs)
    if div is not None:
        n = len(probs)
        max_ent = math.log(n)
        norm_ent = div.entropy / max_ent if max_ent > 0 else 0
        ratio = div.significance
        print(f"{name:20s}: norm_entropy={norm_ent:.4f}, ratio={ratio:.4f}, "
              f"is_significant={div.is_significant}")
    else:
        print(f"{name:20s}: NOT DETECTED (returned None)")
