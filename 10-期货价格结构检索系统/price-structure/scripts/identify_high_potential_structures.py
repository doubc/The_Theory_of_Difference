"""
高潜力结构模板构建 — 阶段四修订版

修订重点：
1. 加入 confirmation_lag，避免用结构结束日当天的数据作为 outcome 起点（防信息泄漏）
2. 保存模板时记录 outcome_start_date，供 daily_scan 审计
3. 增加双向 outcome 分离（分别记录 up_move / down_move，不混用 max）
"""

import sys
import os
import json
import pandas as pd
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.loader import MySQLLoader

CONFIRMATION_LAG = 3  # 结构结束后等待 N 个交易日再开始计算 outcome
LOOKFORWARD_DAYS = 30  # outcome 观察窗口
MIN_MOVE_THRESHOLD = 0.10  # 筛选阈值


def analyze_post_performance(loader, symbol, end_date_str,
                             confirmation_lag=CONFIRMATION_LAG,
                             lookforward_days=LOOKFORWARD_DAYS):
    """
    分析结构结束后（经过确认等待期）的前瞻走势。
    返回 (up_move, down_move, outcome_start_date)
    """
    end_date = pd.to_datetime(end_date_str)
    outcome_start = end_date + timedelta(days=confirmation_lag)
    outcome_end = outcome_start + timedelta(days=lookforward_days)

    bars = loader.get(
        symbol=symbol,
        start=outcome_start.strftime('%Y-%m-%d'),
        end=outcome_end.strftime('%Y-%m-%d'),
        freq='1d'
    )
    if not bars:
        return None

    start_price = bars[0].open
    if start_price <= 0:
        return None

    max_price = max(b.high for b in bars)
    min_price = min(b.low for b in bars)

    up_move = (max_price - start_price) / start_price
    down_move = (start_price - min_price) / start_price

    return {
        "up_move": round(up_move, 4),
        "down_move": round(down_move, 4),
        "max_move": round(max(up_move, down_move), 4),
        "outcome_start_date": outcome_start.strftime('%Y-%m-%d'),
        "outcome_end_date": outcome_end.strftime('%Y-%m-%d'),
        "bars_count": len(bars),
    }


def identify_representative_structures(
        confirmation_lag=CONFIRMATION_LAG,
        lookforward_days=LOOKFORWARD_DAYS,
        min_move=MIN_MOVE_THRESHOLD,
):
    print("正在加载全量结构池...")
    pool_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "library", "full_structure_pool.jsonl"
    )

    loader = MySQLLoader(host='localhost', user='root', password='root', db='sina')
    high_potential_templates = []
    total = 0
    errors = 0

    with open(pool_path, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            record = json.loads(line)
            symbol = record.get('symbol')
            end_date = record.get('end_date')
            if not symbol or not end_date:
                continue

            try:
                outcome = analyze_post_performance(
                    loader, symbol, end_date,
                    confirmation_lag=confirmation_lag,
                    lookforward_days=lookforward_days,
                )
                if outcome is None:
                    continue

                if outcome['max_move'] >= min_move:
                    record['outcome'] = outcome
                    # 明确标注主方向
                    if outcome['up_move'] >= outcome['down_move']:
                        record['primary_direction'] = 'up'
                    else:
                        record['primary_direction'] = 'down'
                    high_potential_templates.append(record)

            except Exception as e:
                errors += 1
                continue

    print(
        f"筛选完成！从 {total} 个结构中识别出 "
        f"{len(high_potential_templates)} 个高潜力模板（错误 {errors} 条）。"
    )
    print(
        f"  confirmation_lag={confirmation_lag}d, "
        f"lookforward={lookforward_days}d, min_move={min_move:.0%}"
    )

    template_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "library", "high_potential_templates.jsonl"
    )
    os.makedirs(os.path.dirname(template_path), exist_ok=True)
    with open(template_path, 'w', encoding='utf-8') as f:
        for t in high_potential_templates:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')

    print(f"模板已保存至: {template_path}")


if __name__ == "__main__":
    identify_representative_structures()
