import json
from collections import Counter

with open('output/daily_scan_20260612_1637.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

meta = data['scan_meta']
opps = data['opportunities']

print(f'=== Scan Summary ===')
print(f'Symbols: {meta["total_symbols"]} | Structures: {meta["structures_found"]} | Opportunities: {len(opps)} | Active Templates: {meta["template_count"]}')

# Top 10 by attention_score
sorted_opps = sorted(opps, key=lambda x: x['attention_score'], reverse=True)
print(f'\n=== Top 10 Attention Score ===')
for i, o in enumerate(sorted_opps[:10], 1):
    direction = o['direction']
    name = o['symbol_name']
    price = o['current_price']
    score = o['attention_score']
    trigger = o.get('trigger_price', 'N/A')
    conf = o.get('direction_confidence', 0)
    pot_med = o.get('potential_median', 0)
    pot_p25 = o.get('potential_p25', 0)
    pot_p75 = o.get('potential_p75', 0)
    print(f'{i}. {name}({o["symbol"]}) | dir={direction} | price={price} | attention={score:.1f} | trigger={trigger} | conf={conf:.0%} | potential=[{pot_p25:.1%},{pot_med:.1%},{pot_p75:.1%}]')

# Signal type counts
dirs = Counter(o['direction'] for o in opps)
print(f'\nDirection distribution: {dict(dirs)}')

# Top symbols with most opportunities
sym_counts = Counter(o['symbol'] for o in opps)
print(f'\nTop 10 symbols by opportunity count:')
for s, c in sym_counts.most_common(10):
    # Get the name
    name = next(o['symbol_name'] for o in opps if o['symbol'] == s)
    print(f'  {name}({s}): {c} ops')

# Notable movers (biggest price changes from yesterday)
print(f'\n=== Notable Movers (Today) ===')
# Collect latest prices by symbol
prices = {}
for o in opps:
    s = o['symbol']
    if s not in prices:
        prices[s] = (o['current_price'], o['symbol_name'])
print(f'Total unique symbols with opportunities: {len(prices)}')
