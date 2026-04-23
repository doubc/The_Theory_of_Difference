"""
快速同步脚本 - 一行命令同步新浪期货数据到 MySQL

常用命令：
    # 同步铜主力合约日线
    python quick_sync.py cu0
    
    # 同步多个合约
    python quick_sync.py cu0 rb0 al0
    
    # 同步5分钟线
    python quick_sync.py cu0 --freq 5m
    
    # 同步所有合约（日线）
    python quick_sync.py --all
    
    # 查看已同步的表
    python quick_sync.py --list
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.sina_to_mysql import MySQLManager, DataSync, available_contracts


def main():
    # 默认配置（请根据你的 MySQL 设置修改）
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': 'root',  # ← 修改为你的密码
    }
    
    # 解析命令行参数
    args = sys.argv[1:]
    
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return
        
    # 检查是否是特殊命令
    if args[0] == '--list':
        db = MySQLManager(**DB_CONFIG)
        db.ensure_database()
        db.use_database()
        tables = db.list_tables()
        print(f"\n已同步的合约数据表 ({len(tables)} 个):")
        for table in sorted(tables):
            print(f"  - {table}")
        db.close()
        return
        
    if args[0] == '--all':
        # 同步所有合约
        freq = '5m' if '--freq' in args and '5m' in args else '1d'
        
        db = MySQLManager(**DB_CONFIG)
        db.ensure_database()
        db.use_database()
        
        sync = DataSync(db)
        contracts = available_contracts()
        sync.sync_all(contracts, freq)
        
        db.close()
        return
        
    # 同步指定合约
    freq = '5m' if '--freq' in args and '5m' in args else '1d'
    symbols = [a for a in args if not a.startswith('--')]
    
    if not symbols:
        print("请指定要同步的合约代码")
        return
        
    db = MySQLManager(**DB_CONFIG)
    db.ensure_database()
    db.use_database()
    
    sync = DataSync(db)
    for symbol in symbols:
        sync.sync_contract(symbol, freq)
        
    db.close()
    print("\n✓ 同步完成!")


if __name__ == "__main__":
    main()
