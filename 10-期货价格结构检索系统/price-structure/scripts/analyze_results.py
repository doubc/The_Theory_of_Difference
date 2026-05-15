import json
path = r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure\output\daily_scan_20260425_1123.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
opps = data['opportunities']
print(f'总机会数: {len(opps)}')
opps.sort(key=lambda x: x['attention_score'], reverse=True)
print('\nTop 15 机会 (按关注度):')
print('%-8s %-12s %-6s %-8s %-8s %-10s %-5s' % ('品种','名称','分','方向','潜力','触发价','窗口'))
print('-' * 65)
for o in opps[:15]:
    dir_icon = {'up':'↑','down':'↓','unclear':'?'}.get(o['direction'],'?')
    print('%-8s %-12s %5.1f %5s %6.1f%% %10.1f %4sd' % (
        o['symbol'], o['symbol_name'][:10], o['attention_score'], dir_icon,
        o['potential_median']*100, o['trigger_price'], o['expected_window_days']))
print()
print('方向分布:')
from collections import Counter
dc = Counter(o['direction'] for o in opps)
for d,c in dc.most_common():
    print('  %s: %d 个' % (d, c))
print()
print('潜力分布:')
for thresh in [0.20, 0.15, 0.10]:
    cnt = sum(1 for o in opps if o['potential_median'] >= thresh)
    print('  >=%.0f%%: %d 个' % (thresh*100, cnt))
print()
print('Top 5 详细分析:')
for o in opps[:5]:
    print()
    print('=== %s (%s) ===' % (o['symbol'], o['symbol_name']))
    print('  关注度: %.1f 分' % o['attention_score'])
    print('  方向: %s (置信 %.0f%%)' % (o['direction'], o['direction_confidence']*100))
    print('  当前价: %.2f  触发价: %.2f' % (o['current_price'], o['trigger_price']))
    print('  潜力中位: %.2f%%  (P25=%.2f%%  P75=%.2f%%)' % (
        o['potential_median']*100, o['potential_p25']*100, o['potential_p75']*100))
    print('  预期窗口: %d 天' % o['expected_window_days'])
    print('  相似度: %.3f  几何=%.3f  关系=%.3f  家族=%.3f' % (
        o['sim_total'], o['sim_geometry'], o['sim_relation'], o['sim_family']))
    if o['top_matches']:
        best = o['top_matches'][0]
        print('  最佳匹配: %s %s (距离=%.2f)' % (best['symbol'], best['end_date'], best['distance']))
    if o['next_actions']:
        print('  建议: %s' % o['next_actions'][0])sina_futures