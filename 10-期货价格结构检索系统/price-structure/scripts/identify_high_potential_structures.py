"""
高潜力结构识别与约束模板构建

目标：
从全量结构池中，筛选出那些在结构显现后，曾引发 >10% 价格波动的“代表性结构”。
这些结构将作为后续每日扫描的“约束模板”。
"""

import sys
import os
import json
import pandas as pd
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.loader import MySQLLoader

def analyze_post_performance(symbol, end_date_str, lookforward_days=20):
    """分析结构结束后的最大潜在波动幅度"""
    loader = MySQLLoader(host='localhost', user='root', password='root', db='sina')
    end_date = pd.to_datetime(end_date_str)
    start_look = end_date
    end_look = end_date + timedelta(days=lookforward_days)
    
    bars = loader.get(symbol=symbol, start=start_look.strftime('%Y-%m-%d'), 
                      end=end_look.strftime('%Y-%m-%d'), freq='1d')
    
    if not bars:
        return 0.0
    
    start_price = bars[0].open
    max_price = max(b.high for b in bars)
    min_price = min(b.low for b in bars)
    
    # 计算双向最大波动幅度
    up_move = (max_price - start_price) / start_price
    down_move = (start_price - min_price) / start_price
    
    return max(up_move, down_move)

def identify_representative_structures():
    print("正在加载全量结构池...")
    pool_path = os.path.join(os.path.dirname(__file__), "..", "data", "library", "full_structure_pool.jsonl")
    
    high_potential_templates = []
    
    with open(pool_path, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            symbol = record['symbol']
            end_date = record['end_date']
            
            # 检查该结构结束后是否出现了 >10% 的波动
            try:
                max_move = analyze_post_performance(symbol, end_date, lookforward_days=30)
                
                if max_move >= 0.10:
                    record['post_max_move'] = max_move
                    high_potential_templates.append(record)
            except Exception as e:
                continue

    print(f"筛选完成！从 {sum(1 for _ in open(pool_path))} 个结构中识别出 {len(high_potential_templates)} 个高潜力模板。")
    
    # 保存为约束模板文件
    template_path = os.path.join(os.path.dirname(__file__), "..", "data", "library", "high_potential_templates.jsonl")
    with open(template_path, 'w', encoding='utf-8') as f:
        for t in high_potential_templates:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')
            
    print(f"模板已保存至: {template_path}")

if __name__ == "__main__":
    identify_representative_structures()
