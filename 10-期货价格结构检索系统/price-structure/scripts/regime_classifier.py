"""
市场 Regime 分类器 v2 - 纯 ASCII 输出，避免编码问题
"""
import json, os, sys

SNAP = r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure\output\daily_scan_20260425_1123.json'

def classify(opp):
    sim = opp.get('sim_total', 0.5)
    dir_conf = opp.get('direction_confidence', 0.5)
    potential = opp.get('potential_median', 0)
    sim_geo = opp.get('sim_geometry', 0.5)
    direction = opp.get('direction', 'unclear')
    sym = opp.get('symbol', '')
    sym_name = opp.get('symbol_name', '')

    # 分类规则
    if sim > 0.85 and dir_conf > 0.75:
        regime = 'trend_up' if direction == 'up' else ('trend_down' if direction == 'down' else 'range')
        conf = min(sim * 0.5 + dir_conf * 0.5, 1.0)
        reason = 'high similarity + strong direction consensus => stable continuation'
    elif potential > 0.18 and sim < 0.70:
        regime = 'reversal'
        conf = 0.7
        reason = 'high potential + low similarity => rare structure, possible reversal'
    elif dir_conf < 0.65 and potential > 0.15:
        regime = 'range'
        conf = 0.6
        reason = 'unclear direction + large potential => wide-range consolidation'
    elif sim_geo > 0.80 and opp.get('sim_relation', 0.5) < 0.70:
        regime = 'range'
        conf = 0.65
        reason = 'similar geometry but mismatched ratio => range-bound'
    elif sim > 0.80 and potential < 0.12:
        regime = 'trend_up' if direction == 'up' else ('trend_down' if direction == 'down' else 'range')
        conf = 0.6
        reason = 'high similarity + low potential => minor trend continuation'
    else:
        regime = 'range'
        conf = 0.55
        reason = 'mixed signals => range-bound'

    dir_icon = {'up': 'UP', 'down': 'DOWN', 'unclear': 'FLAT'}.get(direction, 'N/A')
    reg_icon = {
        'trend_up': '[TREND+]',
        'trend_down': '[TREND-]',
        'range': '[RANGE]',
        'reversal': '[REVERSAL]'
    }.get(regime, regime)

    return {
        'symbol': sym,
        'name': sym_name,
        'direction': dir_icon,
        'regime': regime,
        'regime_icon': reg_icon,
        'conf': round(conf, 2),
        'reason': reason,
        'score': opp.get('attention_score', 0),
        'potential': opp.get('potential_median', 0),
        'trigger': opp.get('trigger_price', 0),
        'price': opp.get('current_price', 0),
        'sim': sim,
        'dir_conf': dir_conf,
        'keywords': []
    }

with open(SNAP, 'r', encoding='utf-8') as f:
    data = json.load(f)
opps = data.get('opportunities', [])

results = [classify(o) for o in opps]
results.sort(key=lambda x: x['conf'], reverse=True)

total = len(results)
tu = [r for r in results if r['regime'] == 'trend_up']
td = [r for r in results if r['regime'] == 'trend_down']
ra = [r for r in results if r['regime'] == 'range']
re = [r for r in results if r['regime'] == 'reversal']

print('=' * 72)
print('  DAILY TIMEFRAME - MARKET REGIME CLASSIFICATION REPORT')
print('  2026-04-25  |  Total: {} opportunities'.format(total))
print('=' * 72)

print('\n[GLOBAL OVERVIEW]')
print('-' * 72)
print('  {:<20} {:>4} opportunities  ({:>5.1f}%)'.format('UP TREND   [TREND+]', len(tu), len(tu)/total*100))
print('  {:<20} {:>4} opportunities  ({:>5.1f}%)'.format('DOWN TREND [TREND-]', len(td), len(td)/total*100))
print('  {:<20} {:>4} opportunities  ({:>5.1f}%)'.format('RANGE BOUND [RANGE]', len(ra), len(ra)/total*100))
print('  {:<20} {:>4} opportunities  ({:>5.1f}%)'.format('REVERSAL   [REVERSAL]', len(re), len(re)/total*100))

def print_group(label, icon, items):
    if not items:
        return
    print('\n[{}] {} ({} opportunities)'.format(icon, label, len(items)))
    print('-' * 72)
    print('  {:6} {:12} {:5} {:6} {:7} {:>7}  {:>7}  {}'.format(
        'SYM', 'NAME', 'SCORE', 'CONF', 'REGIME', 'POT%', 'PRICE', 'REASON'))
    print('  ' + '-' * 68)
    for r in sorted(items, key=lambda x: x['score'], reverse=True):
        pot_str = '{:.1f}%'.format(r['potential'] * 100)
        reason_short = r['reason'][:60]
        print('  {:6} {:12} {:>5.1f} {:>5.0f}% {:7} {:>7} {:>10.1f}  {}'.format(
            r['symbol'], r['name'][:10], r['score'], r['conf']*100,
            r['regime'].upper(), pot_str, r['price'], reason_short))

print_group('UP TREND (bullish continuation)', 'TREND+', tu)
print_group('DOWN TREND (bearish continuation)', 'TREND-', td)
print_group('RANGE BOUND (consolidation)', 'RANGE', ra)
print_group('REVERSAL (potential direction change)', 'REVERSAL', re)

# High confidence special
high_conf = [r for r in results if r['conf'] >= 0.70]
if high_conf:
    print('\n\n[IMPORTANT] High Confidence (>=70%)')
    print('-' * 72)
    for r in sorted(high_conf, key=lambda x: x['score'], reverse=True):
        reg = r['regime'].upper()
        print('  !! {} {} {} conf={:.0f}% pot={:.1f}% reason: {}'.format(
            r['symbol'], r['name'][:10], reg,
            r['conf']*100, r['potential']*100, r['reason'][:60]))

# Output JSON too
out_json = os.path.join(os.path.dirname(SNAP), 'regime_classification_20260425.json')
with open(out_json, 'w', encoding='utf-8') as f:
    json.dump({'results': results, 'summary': {
        'total': total,
        'trend_up': len(tu), 'trend_down': len(td),
        'range': len(ra), 'reversal': len(re)
    }}, f, ensure_ascii=False, indent=2)
print('\n\nJSON saved: ' + out_json)sina_futures