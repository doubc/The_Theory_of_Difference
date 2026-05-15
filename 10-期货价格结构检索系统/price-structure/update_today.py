"""
更新期货数据到 MySQL (sina_futures)
自动从 Sina API 抓取今日数据并写入数据库
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
from datetime import datetime, date

# 导入项目 Sina 抓取器
from src.data.sina_fetcher import fetch_bars, available_contracts, INNER_MAIN

TODAY = date.today().isoformat()
print(f"[{datetime.now().strftime('%H:%M:%S')}] 更新日期: {TODAY}")

# ─── MySQL 连接 ────────────────────────────────────────────
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', database='sina_futures')
cursor = conn.cursor()

updated = []
failed = []

# ─── 合约列表（国内期货全部） ──────────────────────────────
CODES = (
    INNER_MAIN
    + ["sc0"]  # 原油主力（不在 INNER_MAIN 里）
)

# ─── 抓取并写入 ────────────────────────────────────────────
codes_to_fetch = CODES

for code in codes_to_fetch:
    try:
        bars = fetch_bars(code, freq='1d', timeout=8)
        if not bars:
            failed.append(code)
            continue

        # 取最近一根
        latest = bars[-1]
        ts = latest.timestamp
        if hasattr(ts, 'date'):
            bar_date = ts.date().isoformat()
        elif isinstance(ts, str):
            bar_date = str(ts)[:10]
        else:
            bar_date = ts.strftime('%Y-%m-%d')

        # INSERT OR REPLACE
        sql = f"INSERT INTO `{code}` (date, open, high, low, close, vol) VALUES (%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close), vol=VALUES(vol)"
        cursor.execute(sql, (bar_date, latest.open, latest.high, latest.low, latest.close, latest.volume))
        conn.commit()

        change_pct = 0.0
        if len(bars) >= 2:
            prev = bars[-2].close
            change_pct = round((latest.close - prev) / prev * 100, 2)

        updated.append(f"{code}: {latest.close} ({change_pct:+.2f}%) [{bar_date}]")
        print(f"  {code}: close={latest.close}, date={bar_date}")

    except Exception as e:
        failed.append(f"{code}({e})")
        print(f"  FAIL {code}: {e}")

cursor.close()
conn.close()

print(f"\n=== 更新完成 ===")
print(f"成功: {len(updated)} | 失败: {len(failed)}")
print("\n成功列表:")
for u in updated:
    print(f"  {u}")
if failed:
    print("\n失败:")
    for f in failed:
        print(f"  {f}")