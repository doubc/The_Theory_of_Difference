import json

with open('output/daily_scan_20260612_1637.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

down = [o for o in d['opportunities'] if o['direction'] == 'down']
down.sort(key=lambda x: x['attention_score'], reverse=True)
print('=== Top Down Opportunities ===')
for i, o in enumerate(down[:10], 1):
    print(f'{i}. {o["symbol_name"]}({o["symbol"]}) | price={o["current_price"]} | attention={o["attention_score"]:.1f} | trigger={o.get("trigger_price")} | conf={o.get("direction_confidence",0):.0%} | pot=[{o.get("potential_p25",0):.1%},{o.get("potential_median",0):.1%},{o.get("potential_p75",0):.1%}]')

print('\n=== Up/Down count ===')
ups = sum(1 for o in d['opportunities'] if o['direction'] == 'up')
downs = sum(1 for o in d['opportunities'] if o['direction'] == 'down')
unclear = sum(1 for o in d['opportunities'] if o['direction'] == 'unclear')
print(f'UP: {ups}, DOWN: {downs}, UNCLEAR: {unclear}')
print(f'Total: {len(d["opportunities"])}')
