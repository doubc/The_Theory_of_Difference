# -*- coding: utf-8 -*-
"""
信号效果分析脚本 - 期货价格结构检索系统
"""
import json
import os
from collections import defaultdict

# 统计所有品种的结构数据
lifecycle_dir = r'D:\PythonWork\The_Theory_of_Difference\10-期货价格结构检索系统\price-structure\data\lifecycle'

# 统计维度
total_structures = 0
quality_tier_dist = defaultdict(int)
symbol_stats = defaultdict(lambda: {
    'count': 0, 
    'tiers': defaultdict(int), 
    'phases': defaultdict(int), 
    'blind_count': 0, 
    'flux_values': [],
    'directions': defaultdict(int),
    'stability': defaultdict(int),
    'cycle_counts': []
})

for filename in os.listdir(lifecycle_dir):
    if filename.endswith('.jsonl'):
        symbol = filename.replace('.jsonl', '')
        filepath = os.path.join(lifecycle_dir, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    total_structures += 1
                    
                    # 质量层分布
                    tier = data.get('quality_tier', 'Unknown')
                    quality_tier_dist[tier] += 1
                    
                    # 品种统计
                    symbol_stats[symbol]['count'] += 1
                    symbol_stats[symbol]['tiers'][tier] += 1
                    
                    # 阶段分布
                    phase = data.get('phase_tendency', 'unknown')
                    symbol_stats[symbol]['phases'][phase] += 1
                    
                    # 方向分布
                    direction = data.get('direction', 'unknown')
                    symbol_stats[symbol]['directions'][direction] += 1
                    
                    # 稳定性分布
                    stability = data.get('stability', 'unknown')
                    symbol_stats[symbol]['stability'][stability] += 1
                    
                    # 盲区统计
                    if data.get('is_blind', False):
                        symbol_stats[symbol]['blind_count'] += 1
                    
                    # Flux统计
                    flux = data.get('conservation_flux', 0)
                    symbol_stats[symbol]['flux_values'].append(flux)
                    
                    # Cycle count统计
                    cycle_count = data.get('cycle_count', 0)
                    symbol_stats[symbol]['cycle_counts'].append(cycle_count)
                    
                except Exception as e:
                    continue

# 输出统计结果
print('=' * 70)
print('信号效果分析报告 - 期货价格结构检索系统')
print('=' * 70)

print('\n【一、总体统计】')
print(f'总结构数: {total_structures}')
print(f'品种数量: {len(symbol_stats)}')
print(f'平均每品种结构数: {total_structures/len(symbol_stats):.1f}')

# 计算平均信号频率（假设数据覆盖约30天）
assumed_days = 30
signals_per_day = total_structures / (len(symbol_stats) * assumed_days)
print(f'估算信号频率: 每品种每天约 {signals_per_day:.2f} 个结构')

print('\n【二、质量层分布】')
for tier in ['A', 'B', 'C', 'D']:
    count = quality_tier_dist.get(tier, 0)
    pct = count / total_structures * 100 if total_structures > 0 else 0
    bar = '█' * int(pct / 2)
    print(f'  {tier}层: {count:3d} ({pct:5.1f}%) {bar}')

print('\n【三、品种信号频率TOP20】')
sorted_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['count'], reverse=True)
print(f'  {"品种":<6} {"结构数":>6} {"A层":>4} {"B层":>4} {"盲区%":>6} {"平均cycle":>9}')
print('  ' + '-' * 50)
for symbol, stats in sorted_symbols[:20]:
    flux_values = stats['flux_values']
    avg_flux = sum(flux_values) / len(flux_values) if flux_values else 0
    blind_pct = stats['blind_count'] / stats['count'] * 100 if stats['count'] > 0 else 0
    avg_cycles = sum(stats['cycle_counts']) / len(stats['cycle_counts']) if stats['cycle_counts'] else 0
    print(f'  {symbol:<6} {stats["count"]:>6} {stats["tiers"].get("A",0):>4} {stats["tiers"].get("B",0):>4} {blind_pct:>6.0f} {avg_cycles:>9.1f}')

print('\n【四、阶段分布（信号类型推断）】')
phase_dist = defaultdict(int)
for symbol, stats in symbol_stats.items():
    for phase, count in stats['phases'].items():
        phase_dist[phase] += count

phase_names = {
    'forming': '形成中（观望）',
    'stable': '稳定期（持仓）',
    '->confirmation': '突破确认（入场）',
    '->breakdown': '破坏突破（反向）',
    '->inversion': '反演转换（变盘）',
    'unknown': '未知'
}

for phase, count in sorted(phase_dist.items(), key=lambda x: x[1], reverse=True):
    pct = count / total_structures * 100
    name = phase_names.get(phase, phase)
    bar = '█' * int(pct / 2)
    print(f'  {phase:<20} {count:3d} ({pct:5.1f}%) {bar}')

print('\n【五、方向分布】')
direction_dist = defaultdict(int)
for symbol, stats in symbol_stats.items():
    for direction, count in stats['directions'].items():
        direction_dist[direction] += count

for direction, count in sorted(direction_dist.items(), key=lambda x: x[1], reverse=True):
    pct = count / total_structures * 100
    print(f'  {direction}: {count} ({pct:.1f}%)')

print('\n【六、稳定性分布】')
stability_dist = defaultdict(int)
for symbol, stats in symbol_stats.items():
    for stability, count in stats['stability'].items():
        stability_dist[stability] += count

for stability, count in sorted(stability_dist.items(), key=lambda x: x[1], reverse=True):
    pct = count / total_structures * 100
    print(f'  {stability}: {count} ({pct:.1f}%)')

# 信号类型推断分析
print('\n【七、信号类型分布估算】')
# 基于phase_tendency推断信号类型
signal_type_dist = defaultdict(int)
for symbol, stats in symbol_stats.items():
    for phase, count in stats['phases'].items():
        if 'breakdown' in phase:
            signal_type_dist['假突破/反向'] += count
        elif 'confirmation' in phase:
            signal_type_dist['突破确认'] += count
        elif 'forming' in phase:
            signal_type_dist['盲区/观望'] += count
        elif 'stable' in phase:
            signal_type_dist['持仓/老化'] += count
        else:
            signal_type_dist['其他'] += count

for signal_type, count in sorted(signal_type_dist.items(), key=lambda x: x[1], reverse=True):
    pct = count / total_structures * 100
    bar = '█' * int(pct / 2)
    print(f'  {signal_type:<12} {count:3d} ({pct:5.1f}%) {bar}')

print('\n【八、潜在问题识别】')

# 问题1: 过度信号品种
print('\n  1. 过度信号品种（结构数>15）:')
over_signal = [(s, st) for s, st in sorted_symbols if st['count'] > 15]
if over_signal:
    for symbol, stats in over_signal:
        print(f'     {symbol}: {stats["count"]}个结构 - 可能存在过度细分')
else:
    print('     无')

# 问题2: 盲区占比过高
print('\n  2. 盲区占比过高的品种（盲区>20%）:')
high_blind = []
for symbol, stats in symbol_stats.items():
    if stats['count'] > 0:
        blind_pct = stats['blind_count'] / stats['count'] * 100
        if blind_pct > 20:
            high_blind.append((symbol, blind_pct))
if high_blind:
    for symbol, pct in sorted(high_blind, key=lambda x: x[1], reverse=True)[:10]:
        print(f'     {symbol}: {pct:.0f}% 盲区')
else:
    print('     无')

# 问题3: 低质量结构占比
print('\n  3. 低质量结构（C/D层）占比:')
low_quality_count = quality_tier_dist.get('C', 0) + quality_tier_dist.get('D', 0)
low_quality_pct = low_quality_count / total_structures * 100 if total_structures > 0 else 0
print(f'     C/D层共 {low_quality_count} 个，占比 {low_quality_pct:.1f}%')
if low_quality_pct > 20:
    print('     [WARN] 低质量结构占比过高，建议调整质量评估阈值')
else:
    print('     [OK] 质量分布正常')

# 问题4: 信号分布不均
print('\n  4. 信号分布不均分析:')
max_signals = sorted_symbols[0][1]['count'] if sorted_symbols else 0
min_signals = sorted_symbols[-1][1]['count'] if sorted_symbols else 0
if max_signals > 0:
    ratio = max_signals / min_signals if min_signals > 0 else float('inf')
    print(f'     最多信号: {max_signals}个 ({sorted_symbols[0][0]})')
    print(f'     最少信号: {min_signals}个 ({sorted_symbols[-1][0]})')
    print(f'     极值比: {ratio:.1f}:1')
    if ratio > 10:
        print('     [WARN] 信号分布极不均衡，部分品种可能遗漏')

print('\n' + '=' * 70)
print('分析完成 - 详细报告已生成')
print('=' * 70)

# 生成JSON报告
import json
report = {
    'summary': {
        'total_structures': total_structures,
        'symbol_count': len(symbol_stats),
        'avg_per_symbol': round(total_structures/len(symbol_stats), 1),
        'signals_per_day': round(signals_per_day, 2)
    },
    'quality_distribution': dict(quality_tier_dist),
    'phase_distribution': dict(phase_dist),
    'direction_distribution': dict(direction_dist),
    'signal_type_estimate': dict(signal_type_dist),
    'top_symbols': [
        {
            'symbol': s,
            'count': st['count'],
            'tier_a': st['tiers'].get('A', 0),
            'tier_b': st['tiers'].get('B', 0),
            'blind_pct': round(st['blind_count'] / st['count'] * 100, 1) if st['count'] > 0 else 0
        }
        for s, st in sorted_symbols[:15]
    ]
}

with open('signal_analysis_report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print('\n详细JSON报告已保存至: signal_analysis_report.json')
