path = r'C:\Users\Administrator\Documents\the_theory_of_difference\11-模拟机工程实现\tests\test_phase2_integration.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_text = """    # 构造满足 SixThresholdDetector 的参数
    threshold_params = {
        'active_exchanges': 8,
        'total_boundary_edges': 10,
        'rebuild_success_count': 6,
        'perturbation_count': 10,
        'bias_recursion_depth': 5.0,
        'variant_continuation_probs': {
            'var_A': 0.9, 'var_B': 0.2,
        },
        'component_contributions': {
            'comp_A': 0.5, 'comp_B': 0.3, 'comp_C': 0.2,
        },
    }"""

new_text = """    # 构造满足 SixThresholdDetector 的参数 (6/6 thresholds)
    threshold_params = {
        'active_exchanges': 8,
        'total_boundary_edges': 10,
        'rebuild_success_count': 6,
        'perturbation_count': 10,
        'bias_recursion_depth': 5.0,
        'replicated_pattern': torch.ones(8),
        'original_pattern': torch.ones(8),
        'variant_continuation_probs': {
            'var_A': 0.9, 'var_B': 0.2,
        },
        'component_contributions': {
            'comp_A': 0.8, 'comp_B': 0.1, 'comp_C': 0.1,
        },
    }"""

if old_text in content:
    content = content.replace(old_text, new_text)
    print("Fixed threshold_params!")
else:
    print("ERROR: old_text not found!")
    # Show what's around line 105
    lines = content.split('\n')
    for i in range(100, 125):
        print(f'{i+1}: {lines[i]}')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
