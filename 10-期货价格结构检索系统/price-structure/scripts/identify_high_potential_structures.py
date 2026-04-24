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
from src.data.symbol_meta import symbol_name

CONFIRMATION_LAG = 3
LOOKFORWARD_DAYS = 30
MIN_MOVE_THRESHOLD = 0.10


def analyze_post_performance(loader, symbol, end_date_str,
                             confirmation_lag=CONFIRMATION_LAG,
                             lookforward_days=LOOKFORWARD_DAYS):
    """
    分析结构结束后（经过确认等待期）的前瞻走势。
    返回包含 up_move, down_move, days_to_peak/trough, max_drawdown 等全量统计。
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

    # 逐 bar 追踪峰/谷位置
    peak_price, peak_idx = start_price, 0
    trough_price, trough_idx = start_price, 0
    for i, b in enumerate(bars):
        if b.high > peak_price:
            peak_price, peak_idx = b.high, i
        if b.low < trough_price:
            trough_price, trough_idx = b.low, i

    up_move = (peak_price - start_price) / start_price
    down_move = (start_price - trough_price) / start_price

    # 最大回撤
    max_dd = 0.0
    running_max = start_price
    for b in bars:
        if b.high > running_max:
            running_max = b.high
        dd = (running_max - b.low) / running_max if running_max > 0 else 0
        if dd > max_dd:
            max_dd = dd

    direction = "up" if up_move >= down_move else "down"

    return {
        "up_move": round(up_move, 4),
        "down_move": round(down_move, 4),
        "max_move": round(max(up_move, down_move), 4),
        "max_drawdown": round(max_dd, 4),
        "days_to_peak": peak_idx,
        "days_to_trough": trough_idx,
        "outcome_start_date": outcome_start.strftime('%Y-%m-%d'),
        "outcome_end_date": outcome_end.strftime('%Y-%m-%d'),
        "bars_count": len(bars),
        "direction": direction,
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

    loader = MySQLLoader(host='localhost', user='root', password=os.getenv('MYSQL_PASSWORD', 'root'), db='sina')
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
                    record['primary_direction'] = outcome['direction']
                    record['symbol_name'] = symbol_name(record['symbol'])
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
