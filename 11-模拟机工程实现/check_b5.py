import json
with open('C:/Users/Administrator/Documents/the_theory_of_difference/11-模拟机工程实现/experiments/exp_118_b5_results.json', 'r') as f:
    data = json.load(f)
seed = data['seeds'][0]
print('=== Seed 42 Detailed Results ===')
print('Baseline H1-H8:', seed['baseline_passes'])
print('Track B:', seed['track_b_passes'])
print()
print('LNT Summary:')
for k, v in seed['lnt_summary'].items():
    print('  ', k, ':', v)
print()
print('CSC Summary:')
for k, v in seed['csc_summary'].items():
    print('  ', k, ':', v)
print()
print('Per-hypothesis:')
for hk in ['H30','H31','H32','H33','H35','H36','H37','H1','H2','H3','H4','H5','H6','H7','H8']:
    h = seed['hypotheses'][hk]
    status = 'PASS' if h['pass'] else 'FAIL'
    print('  ', hk, ':', status, h)
