#!/usr/bin/env python3
import json

with open(r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure\output\daily_scan_20260609_1634.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

meta = data.get('scan_meta', {})
print('=== 扫描元数据 ===')
for k, v in meta.items():
    print(f'  {k}: {v}')

opps = data.get('opportunities', [])
opps_sorted = sorted(opps, key=lambda x: x.get('attention_score', 0), reverse=True)

print(f'\n=== 机会总数: {len(opps)} ===')
print(f'\n=== Top 8 机会 ===')
for i, opp in enumerate(opps_sorted[:8], 1):
    print(f'{i}. [{opp.get("symbol","?")}] {opp.get("symbol_name","?")} | '
          f'价={opp.get("current_price","?")} | 分={opp.get("attention_score",0)} | '
          f'信号={opp.get("signal_type","?")} | 方向={opp.get("direction","?")} | '
          f'阶段={opp.get("phase_tendency","?")} | 位置={opp.get("price_position","?")}')

# Check what signals appear
from collections import Counter
sig_counts = Counter(opp.get('signal_type','?') for opp in opps)
dir_counts = Counter(opp.get('direction','?') for opp in opps)
print(f'\n=== 信号分布 ===')
for k, v in sig_counts.most_common():
    print(f'  {k}: {v}')
print(f'\n=== 方向分布 ===')
for k, v in dir_counts.most_common():
    print(f'  {k}: {v}')
