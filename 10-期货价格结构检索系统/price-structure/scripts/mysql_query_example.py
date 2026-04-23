"""
MySQL 数据查询示例

展示如何从本地 MySQL 读取期货数据并进行分析
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.loader import MySQLLoader, Bar
from datetime import datetime, timedelta


def example_basic_query():
    """示例1: 基础查询 - 获取铜最近 30 天数据"""
    print("=" * 60)
    print("示例1: 基础查询")
    print("=" * 60)
    
    # 初始化加载器（请修改密码）
    loader = MySQLLoader(
        host='localhost',
        user='root',
        password='',  # ← 修改为你的密码
        db='sina'
    )
    
    # 获取最近 30 天数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    bars = loader.get(
        symbol='cu0',
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d'),
        freq='1d'
    )
    
    print(f"获取到 {len(bars)} 条数据")
    if bars:
        print(f"时间范围: {bars[0].timestamp.date()} ~ {bars[-1].timestamp.date()}")
        print(f"最新价格: 开={bars[-1].open}, 高={bars[-1].high}, 低={bars[-1].low}, 收={bars[-1].close}")
    
    return bars


def example_batch_query():
    """示例2: 批量查询多个合约"""
    print("\n" + "=" * 60)
    print("示例2: 批量查询")
    print("=" * 60)
    
    loader = MySQLLoader(
        host='localhost',
        user='root',
        password='',
        db='sina'
    )
    
    symbols = ['cu0', 'rb0', 'al0']
    results = {}
    
    for symbol in symbols:
        bars = loader.get(symbol=symbol, freq='1d')
        if bars:
            results[symbol] = {
                'count': len(bars),
                'latest_close': bars[-1].close,
                'date_range': f"{bars[0].timestamp.date()} ~ {bars[-1].timestamp.date()}"
            }
            
    print("合约统计:")
    for symbol, info in results.items():
        print(f"  {symbol}: {info['count']} 条, 最新收盘价={info['latest_close']}, 范围={info['date_range']}")
        
    return results


def example_price_change():
    """示例3: 计算涨跌幅"""
    print("\n" + "=" * 60)
    print("示例3: 计算涨跌幅")
    print("=" * 60)
    
    loader = MySQLLoader(
        host='localhost',
        user='root',
        password='',
        db='sina'
    )
    
    bars = loader.get(symbol='cu0', freq='1d')
    
    if len(bars) >= 2:
        latest = bars[-1]
        prev = bars[-2]
        
        change = latest.close - prev.close
        change_pct = (change / prev.close) * 100
        
        print(f"铜主力合约 ({latest.timestamp.date()}):")
        print(f"  昨收: {prev.close:.2f}")
        print(f"  今收: {latest.close:.2f}")
        print(f"  涨跌: {change:+.2f} ({change_pct:+.2f}%)")
        print(f"  最高: {latest.high:.2f}")
        print(f"  最低: {latest.low:.2f}")
        print(f"  成交量: {latest.volume:.0f}")


def example_moving_average():
    """示例4: 计算移动平均线"""
    print("\n" + "=" * 60)
    print("示例4: 计算 20 日均线")
    print("=" * 60)
    
    loader = MySQLLoader(
        host='localhost',
        user='root',
        password='',
        db='sina'
    )
    
    bars = loader.get(symbol='cu0', freq='1d')
    
    if len(bars) >= 20:
        # 计算 20 日均线
        closes = [b.close for b in bars]
        ma20 = sum(closes[-20:]) / 20
        
        latest = bars[-1]
        
        print(f"铜主力合约 ({latest.timestamp.date()}):")
        print(f"  收盘价: {latest.close:.2f}")
        print(f"  MA20:   {ma20:.2f}")
        print(f"  位置:   {'上方' if latest.close > ma20 else '下方'} (偏离 {(latest.close/ma20-1)*100:+.2f}%)")


def main():
    """运行所有示例"""
    print("\n" + "🚀 MySQL 期货数据查询示例".center(60, "=") + "\n")
    
    try:
        example_basic_query()
    except Exception as e:
        print(f"示例1失败: {e}")
        
    try:
        example_batch_query()
    except Exception as e:
        print(f"示例2失败: {e}")
        
    try:
        example_price_change()
    except Exception as e:
        print(f"示例3失败: {e}")
        
    try:
        example_moving_average()
    except Exception as e:
        print(f"示例4失败: {e}")
    
    print("\n" + "=" * 60)
    print("提示: 请确保已运行 sina_to_mysql.py 同步数据到 MySQL")
    print("=" * 60)


if __name__ == "__main__":
    main()
