import json, os, sys
from collections import defaultdict

fpath = 'output/daily_scan_20260425_1534.json'
with open(fpath, encoding='utf-8') as f:
    d = json.load(f)

opps = d['opportunities']
print(f"=== 检索效果总览 ===")
print(f"扫描品种数：47")
print(f"识别结构数：46")
print(f"发现机会数：{len(opps)}")
print()

# 1. 运动类型分布
mt_map = {"trend_up": "上涨趋势", "trend_down": "下跌趋势",
          "oscillation": "震荡", "reversal": "反转", "": "(空)"}
mt_counts = defaultdict(int)
for o in opps:
    mt_counts[o.get('movement_type', '')] += 1
print("【运动类型分布】")
for mt, cnt in sorted(mt_counts.items(), key=lambda x: -x[1]):
    print(f"  {mt_map.get(mt, mt):10s}: {cnt} 个 ({cnt/len(opps)*100:.0f}%)")
print()

# 2. 方向分布
dir_counts = defaultdict(int)
for o in opps:
    dir_counts[o.get('direction', '')] += 1
print("【方向分布】")
for direction, cnt in sorted(dir_counts.items(), key=lambda x: -x[1]):
    label = "↑看涨" if direction == "up" else "↓看跌" if direction == "down" else "?不明"
    print(f"  {label}: {cnt} 个 ({cnt/len(opps)*100:.0f}%)")
print()

# 3. 关注度 Top 10
print("【关注度 Top 10】")
for i, o in enumerate(sorted(opps, key=lambda x: -x.get('attention_score', 0))[:10], 1):
    mt = mt_map.get(o.get('movement_type', ''), o.get('movement_type', ''))
    d = o.get('direction', '?')
    d_emoji = "↑" if d == "up" else "↓" if d == "down" else "?"
    sim = o.get('sim_total', 0)
    print(f"  {i:2d}. {o['symbol']:6s} [{mt:6s}] {d_emoji} score={o['attention_score']:.2f} sim={sim:.3f} 潜在={o['potential_median']:+.2%}")
print()

# 4. 相似度分布
print("【相似度分布】")
bins = [(0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.0)]
for lo, hi in bins:
    cnt = sum(1 for o in opps if lo <= o.get('sim_total', 0) < hi)
    label = f"{lo:.1f}-{hi:.1f}"
    print(f"  {label}: {cnt} 个")
print()

# 5. 运动类型 vs 方向 交叉表
print("【运动类型 × 方向】")
cross = defaultdict(lambda: defaultdict(int))
for o in opps:
    mt = mt_map.get(o.get('movement_type', ''), o.get('movement_type', ''))
    d = o.get('direction', '?')
    cross[mt][d] += 1
print(f"  {'运动类型':12s}  {'上涨':6s}  {'下跌':6s}  {'不明':6s}")
for mt in ["上涨趋势", "下跌趋势", "震荡", "反转"]:
    up = cross[mt].get('up', 0)
    dn = cross[mt].get('down', 0)
    unk = cross[mt].get('unclear', 0)
    print(f"  {mt:12s}  {up:6d}  {dn:6d}  {unk:6d}")
print()

# 6. 典型机会：运动类型和方向匹配的
print("【方向与运动类型匹配分析】")
match = 0
mismatch = []
for o in opps:
    mt = o.get('movement_type', '')
    d = o.get('direction', '')
    if mt == 'trend_up' and d == 'up':
        match += 1
    elif mt == 'trend_down' and d == 'down':
        match += 1
    elif mt == 'trend_up' and d == 'down':
        mismatch.append((o['symbol'], mt, d, o['attention_score']))
    elif mt == 'trend_down' and d == 'up':
        mismatch.append((o['symbol'], mt, d, o['attention_score']))
print(f"  匹配：{match} 个 ({match/len(opps)*100:.0f}%)")
if mismatch:
    print("  ⚠️ 不匹配（趋势方向 ≠ 检索方向）：")
    for sym, mt, d, score in sorted(mismatch, key=lambda x: -x[3]):
        print(f"    {sym}: {mt} 但方向={d} (score={score:.2f})")
print()

# 7. 潜力分布
pos = [o['potential_median'] for o in opps if o['potential_median'] > 0]
neg = [o['potential_median'] for o in opps if o['potential_median'] < 0]
print(f"【潜力分布】")
print(f"  正向机会（看涨）：{len(pos)} 个，平均潜力 {sum(pos)/len(pos):.2%}")
print(f"  负向机会（看跌）：{len(neg)} 个，平均潜力 {sum(neg)/len(neg):.2%}")
print()

# 8. 模板详情：Top 5 机会的 top_matches
print("【Top 5 机会的模板详情】")
for o in sorted(opps, key=lambda x: -x.get('attention_score', 0))[:5]:
    print(f"\n  {o['symbol']} (score={o['attention_score']:.2f}, sim={o['sim_total']:.3f}):")
    for j, tm in enumerate(o.get('top_matches', [])[:3], 1):
        print(f"    [{j}] 方向={tm['direction']} 潜在={tm['up_move']:+.2%}/{-tm['down_move']:.2%} 相似度={tm['similarity']:.3f} 模板ID={tm['bundle_id']}")

# 9. flux 分布
print("\n【保守通量分布】")
fluxes = [o['motion_flux'] for o in opps]
print(f"  均值：{sum(fluxes)/len(fluxes):+.3f}")
print(f"  最小：{min(fluxes):+.3f}  最大：{max(fluxes):+.3f}")
pos_flux = [x for x in fluxes if x > 0]
neg_flux = [x for x in fluxes if x < 0]
print(f"  正通量：{len(pos_flux)} 个  负通量：{len(neg_flux)} 个")