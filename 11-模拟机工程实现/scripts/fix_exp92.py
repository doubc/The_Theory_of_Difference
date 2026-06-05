#!/usr/bin/env python3
"""Fix exp_92: balanced ILP config + JSON bool serialization."""

with open('experiments/exp_92_ilp_relaxed_validation.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Replace the ILP config with balanced values
old_ilp = """EXP92_ILP_CONFIG = {
    # 转换门控（大幅降低门槛）
    'transition_min_institutional': 25,
    'transition_min_diversity': 2,
    'transition_min_odi': 0.15,
    'transition_cooldown_steps': 15,
    # 积累保护（降低地板和阈值）
    'min_institutional_floor': 20,
    'min_institutional_threshold': 35,
    # 消耗速率（翻倍）
    'max_consumption_rate_per_step': 0.10,
    'consumption_cooldown_steps': 10,
    # 多样性（降低要求）
    'min_categories_for_transition': 2,
}"""

new_ilp = """EXP92_ILP_CONFIG = {
    # 转换门控（适度降低，避免过早开放）
    'transition_min_institutional': 35,
    'transition_min_diversity': 2,
    'transition_min_odi': 0.30,
    'transition_cooldown_steps': 20,
    # 积累保护（适度降低）
    'min_institutional_floor': 25,
    'min_institutional_threshold': 40,
    # 消耗速率（保持5%保守）
    'max_consumption_rate_per_step': 0.05,
    'consumption_cooldown_steps': 15,
    # 多样性（适度降低）
    'min_categories_for_transition': 2,
}"""

content = content.replace(old_ilp, new_ilp)

# Fix 2: Fix JSON serialization for bool values (numpy.bool_ not JSON serializable)
content = content.replace(
    "'h1_pass': h1_pass,\n            'h2_pass': h2_pass,\n            'h3_pass': h3_pass,\n            'h4_pass': h4_pass,",
    "'h1_pass': bool(h1_pass),\n            'h2_pass': bool(h2_pass),\n            'h3_pass': bool(h3_pass),\n            'h4_pass': bool(h4_pass),"
)

with open('experiments/exp_92_ilp_relaxed_validation.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done. Two fixes applied:")
print("  1. Balanced ILP config (transition_min_odi: 0.15->0.30, consumption: 0.10->0.05, etc.)")
print("  2. JSON bool serialization (numpy.bool_ -> bool)")
