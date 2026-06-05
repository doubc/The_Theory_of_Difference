"""Fix exp_134 evaluate_hypotheses function: add h62/h63/h64 definitions."""
import re

target = r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现\experiments\exp_134_phase6_p5_tension_booster.py'
with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add h62/h63/h64 definitions before all_r2_counts
old_block = """    # H73: Tension-based R2 activation (>=4/8 seeds)
    all_r2_counts = [r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results]
    h73 = sum(1 for cnt in all_r2_counts if cnt >= 1) >= 4
    h73_total_r2 = int(np.sum(all_r2_counts))"""

new_block = """    # H62: R2 activation (>=4/8 seeds)
    all_r2_counts = [r.get('nrc_metrics', {}).get('n_r2_events', 0) for r in results]
    h62 = sum(1 for cnt in all_r2_counts if cnt >= 1) >= 4
    h62_total_r2 = int(np.sum(all_r2_counts))

    # H63: Convergence (>=6/8 seeds show negative slope)
    converges_list = [r.get('nrc_metrics', {}).get('h63_converges', False) for r in results]
    h63 = sum(1 for c in converges_list if c) >= 6

    # H64: Completeness (>=3 cycles per 1000 steps for >=6 seeds)
    cycles_per_1k = [r.get('nrc_metrics', {}).get('h64_cycles_per_1000', 0.0) for r in results]
    h64 = sum(1 for rate in cycles_per_1k if rate >= 3.0) >= 6

    # H73: Tension-based R2 activation (>=4/8 seeds)
    h73 = h62  # same as H62
    h73_total_r2 = h62_total_r2"""

content = content.replace(old_block, new_block)

# 2. Fix H62 return dict entry
content = content.replace(
    "'value': '%d/8 seeds with R2 (total=%d)' % (sum(1 for v in all_r2_counts if v >= 1), h62_total_r2),",
    "'value': '%d/8 seeds with R2 (total=%d)' % (h62_total_r2, h62_total_r2),"
)

# 3. Fix H63 return dict entry
content = content.replace(
    "'value': '%d/8 converges (slope=%.6f)' % (sum(1 for c in converges if c), h63_mean_slope),",
    "'value': '%d/8 converges' % h63,"
)

with open(target, 'w', encoding='utf-8') as f:
    f.write(content)

import py_compile
py_compile.compile(target, doraise=True)
print('Fix applied successfully - Syntax OK')

# Verify all variables are defined
with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

for var in ['h60', 'h61', 'h62', 'h63', 'h64', 'h73', 'h74', 'h75', 'h76', 'h77', 'h78']:
    pattern = f'    {var} = '
    found = pattern in content
    print(f'  {var}: {"OK" if found else "MISSING"}')
