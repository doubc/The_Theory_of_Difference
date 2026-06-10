#!/usr/bin/env python3
import json

with open(r'C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure\output\daily_scan_20260609_1634.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

opps = data.get('opportunities', [])
opps_sorted = sorted(opps, key=lambda x: x.get('attention_score', 0), reverse=True)

# Show full fields of top 1
print("=== Top 1 opp full fields ===")
print(json.dumps(opps_sorted[0], ensure_ascii=False, indent=2))
print()

# Also check for changed signals or notable changes by comparing with yesterday's
# Show all fields of the 6th item for variety
print("=== Top 3 opp full fields ===")
for i in range(3):
    print(json.dumps(opps_sorted[i], ensure_ascii=False, indent=2)[:800])
    print("---")
