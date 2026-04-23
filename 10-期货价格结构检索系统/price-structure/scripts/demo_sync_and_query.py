"""
完整演示：同步数据到 MySQL 并查询

这个脚本演示了完整的工作流程：
1. 连接 MySQL
2. 同步铜主力合约数据
3. 查询并分析数据
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.sina_to_mysql import MySQLManager, DataSync
from src.data.loader import MySQLLoader


def demo():
    """完整演示"""
    
    # 配置（请修改为你的密码）
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': 'root',  # ← 修改为你的密码
    }
    
    print("🚀 新浪期货数据同步演示")
    print("=" * 60)
    
    # 步骤 1: 连接数据库
    print("\n步骤 1: 连接 MySQL 数据库...")
    try:
        db = MySQLManager(**DB_CONFIG)
        db.ensure_database()
        db.use_database()
        print("✓ 连接成功")
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        print("请确保 MySQL 已安装并运行")
        return
    
    # 步骤 2: 同步铜主力合约数据
    print("\n步骤 2: 同步铜主力合约 (cu0) 日线数据...")
    sync = DataSync(db)
    success = sync.sync_contract('cu0', freq='1d')
    
    if not success:
        print("✗ 同步失败")
        db.close()
        return
    
    # 步骤 3: 使用 MySQLLoader 查询数据
    print("\n步骤 3: 查询数据...")
    loader = MySQLLoader(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        db='sina'
    )
    
    # 获取全部数据
    bars = loader.get(symbol='cu0', freq='1d')
    
    if bars:
        print(f"✓ 查询到 {len(bars)} 条数据")
        print(f"\n数据概览:")
        print(f"  时间范围: {bars[0].timestamp.date()} ~ {bars[-1].timestamp.date()}")
        print(f"  最新价格: {bars[-1].close}")
        print(f"  最高价格: {max(b.high for b in bars)}")
        print(f"  最低价格: {min(b.low for b in bars)}")
        
        # 显示最近 5 天数据
        print(f"\n最近 5 个交易日:")
        print("-" * 60)
        print(f"{'日期':<12} {'开盘':<10} {'最高':<10} {'最低':<10} {'收盘':<10} {'成交量':<12}")
        print("-" * 60)
        for bar in bars[-5:]:
            print(f"{bar.timestamp.date()}  {bar.open:<10.2f} {bar.high:<10.2f} {bar.low:<10.2f} {bar.close:<10.2f} {bar.volume:<12.0f}")
    
    # 步骤 4: 查看数据库统计
    print("\n步骤 4: 数据库统计...")
    stats = db.get_stats('cu0', '1d')
    if stats:
        print(f"  表名: cu0")
        print(f"  总行数: {stats['total_rows']}")
        print(f"  起始日期: {stats['start_date']}")
        print(f"  结束日期: {stats['end_date']}")
    
    db.close()
    
    print("\n" + "=" * 60)
    print("✓ 演示完成!")
    print("=" * 60)
    print("\n后续操作:")
    print("  1. 同步更多合约: python scripts/quick_sync.py rb0 al0")
    print("  2. 查看查询示例: python scripts/mysql_query_example.py")
    print("  3. 运行结构分析: python scripts/test_mysql_integration.py")


if __name__ == "__main__":
    demo()
