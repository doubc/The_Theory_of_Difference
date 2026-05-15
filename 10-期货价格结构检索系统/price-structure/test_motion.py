import json

with open('output/daily_scan_20260425_1509.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

opps = d['opportunities'][:3]
for opp in opps:
    symbol = opp.get('symbol', 'unknown')
    direction = opp.get('direction', 'N/A')
    opp_type = opp.get('opportunity_type', 'N/A')
    motion_type = opp.get('motion_type', 'N/A')
    
    print(f"品种: {symbol}")
    print(f"  方向: {direction}")
    print(f"  机会类型: {opp_type}")
    print(f"  运动类型: {motion_type}")
    
    # Check if new fields exist
    print(f"  状态描述: {opp.get('status_description', 'N/A')}")
    print(f"  候选剧本: {opp.get('candidate_scenarios', 'N/A')}")
    print(f"  失效条件: {opp.get('invalidation_conditions', 'N/A')}")
    print()