import json, os

out_dir = 'output'
files = sorted([f for f in os.listdir(out_dir) if f.startswith('daily_scan_') and f.endswith('.json')])
latest = os.path.join(out_dir, files[-1])
print(f"Reading: {files[-1]}\n")

with open(latest, encoding='utf-8') as f:
    d = json.load(f)

opps = d['opportunities']

# Map symbol -> opportunity
opp_map = {o['symbol']: o for o in opps}

# Sort by attention_score descending
sorted_opps = sorted(opps, key=lambda x: -x['attention_score'])

# State emoji mapping
import json, os, sys
# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STATE_TEXT = {
    'trend_up': '趋势上涨',
    'trend_down': '趋势下跌',
    'oscillation': '震荡整理',
    'reversal': '反转信号',
    '': '未知',
    None: '未知',
}

DIR_TEXT = {
    'up': '看多',
    'down': '看空',
}

print(f"{'品种':<8} {'状态':<10} {'方向':<6} {'关注':<8} {'当前价':<14} {'触发价':<14} {'潜力':<10} {'关键位置'}")
print("-" * 105)

for o in sorted_opps:
    sym = o['symbol'].upper()
    mt = STATE_TEXT.get(o.get('movement_type', '') or '', '未知')
    direction = DIR_TEXT.get(o.get('direction', '') or '', '—')
    score = o['attention_score']
    current_price = o.get('current_price', 0)
    trigger_price = o.get('trigger_price', 0)
    pot = o.get('potential_median', 0)
    
    if o.get('direction') == 'up':
        key_level = f"突破 {trigger_price:,.0f}"
    elif o.get('direction') == 'down':
        key_level = f"跌破 {trigger_price:,.0f}"
    else:
        key_level = f"{trigger_price:,.0f}"
    
    pot_str = f"{pot:+.2%}"
    
    print(f"{sym:<8} {mt:<10} {direction:<6} {score:>6.2f}  {current_price:>14,.2f}  {trigger_price:>14,.2f}  {pot_str:>10}  {key_level}")

print(f"\n共 {len(opps)} 个机会 | 数据日期: {d.get('scan_date', 'N/A')}")
print(f"扫描配置哈希: {d.get('config_hash', 'N/A')}")
