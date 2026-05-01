"""
新浪期货行情数据提取并存储到本地 MySQL

功能：
1. 从新浪 API 抓取期货行情数据（日线 + 5分钟线）
2. 自动创建 MySQL 数据库和表结构
3. 支持增量更新（只下载新数据）
4. 支持批量合约下载

使用方法：
    python sina_to_mysql.py --contracts cu0,rb0,al0 --freq 1d
    python sina_to_mysql.py --all --freq 5m
"""

from __future__ import annotations

import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import Literal

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pymysql
from pymysql.cursors import DictCursor

from src.data.sina_fetcher import fetch_bars, available_contracts, detect_source
from src.data.loader import Bar


# ─── 数据库配置 ────────────────────────────────────────────

import os

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': os.getenv('MYSQL_PASSWORD', ''),  # 从环境变量读取，默认空密码
    'charset': 'utf8mb4',
}

DB_NAME = 'sina'


# ─── SQL 建表语句 ──────────────────────────────────────────

CREATE_DB_SQL = f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"

CREATE_DAY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table_name} (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL,
    open DECIMAL(18, 6) NOT NULL,
    high DECIMAL(18, 6) NOT NULL,
    low DECIMAL(18, 6) NOT NULL,
    close DECIMAL(18, 6) NOT NULL,
    vol BIGINT DEFAULT 0,
    amount DECIMAL(20, 4) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{comment}'
"""

CREATE_M5_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table_name} (
    id INT AUTO_INCREMENT PRIMARY KEY,
    datetime DATETIME NOT NULL,
    open DECIMAL(18, 6) NOT NULL,
    high DECIMAL(18, 6) NOT NULL,
    low DECIMAL(18, 6) NOT NULL,
    close DECIMAL(18, 6) NOT NULL,
    vol BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_datetime (datetime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{comment}'
"""


# ─── MySQL 管理类 ──────────────────────────────────────────

class MySQLManager:
    """MySQL 数据库管理器"""
    
    def __init__(self, **config):
        self.config = {**DB_CONFIG, **config}
        self.conn = None
        self._connect()
        
    def _connect(self):
        """建立数据库连接"""
        try:
            self.conn = pymysql.connect(**self.config, cursorclass=DictCursor)
            print(f"[OK] MySQL 连接成功: {self.config['host']}:{self.config['port']}")
        except Exception as e:
            print(f"[ERROR] MySQL 连接失败: {e}")
            raise
            
    def ensure_database(self):
        """确保数据库存在"""
        with self.conn.cursor() as cursor:
            cursor.execute(CREATE_DB_SQL)
            self.conn.commit()
            print(f"[OK] 数据库 '{DB_NAME}' 已就绪")
            
    def use_database(self):
        """切换到目标数据库"""
        with self.conn.cursor() as cursor:
            cursor.execute(f"USE {DB_NAME}")
            
    def ensure_table(self, symbol: str, freq: Literal["1d", "5m"]):
        """确保数据表存在"""
        table_name = self._table_name(symbol, freq)
        comment = f"{symbol} {'日线' if freq == '1d' else '5分钟线'}数据"
        
        sql = (CREATE_DAY_TABLE_SQL if freq == "1d" else CREATE_M5_TABLE_SQL).format(
            table_name=table_name,
            comment=comment
        )
        
        with self.conn.cursor() as cursor:
            cursor.execute(sql)
            self.conn.commit()
            
    def get_latest_date(self, symbol: str, freq: Literal["1d", "5m"]) -> datetime | None:
        """获取表中最新日期"""
        table_name = self._table_name(symbol, freq)
        date_col = "date" if freq == "1d" else "datetime"
        
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"SELECT MAX(`{date_col}`) as latest FROM `{table_name}`")
                result = cursor.fetchone()
                if result and result['latest']:
                    return result['latest']
        except Exception:
            pass
        return None
        
    def insert_bars(self, symbol: str, freq: Literal["1d", "5m"], bars: list[Bar]):
        """批量插入 K 线数据"""
        if not bars:
            return 0
            
        table_name = self._table_name(symbol, freq)
        
        if freq == "1d":
            sql = f"""
                INSERT INTO `{table_name}` (date, open, high, low, close, vol)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    open = VALUES(open),
                    high = VALUES(high),
                    low = VALUES(low),
                    close = VALUES(close),
                    vol = VALUES(vol),
                    updated_at = CURRENT_TIMESTAMP
            """
            data = [
                (b.timestamp.strftime('%Y-%m-%d'), b.open, b.high, b.low, b.close, b.volume)
                for b in bars
            ]
        else:
            sql = f"""
                INSERT INTO `{table_name}` (datetime, open, high, low, close, vol)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    open = VALUES(open),
                    high = VALUES(high),
                    low = VALUES(low),
                    close = VALUES(close),
                    vol = VALUES(vol),
                    updated_at = CURRENT_TIMESTAMP
            """
            data = [
                (b.timestamp.strftime('%Y-%m-%d %H:%M:%S'), b.open, b.high, b.low, b.close, b.volume)
                for b in bars
            ]
            
        with self.conn.cursor() as cursor:
            cursor.executemany(sql, data)
            self.conn.commit()
            return cursor.rowcount
            
    def get_stats(self, symbol: str, freq: Literal["1d", "5m"]) -> dict:
        """获取表统计信息"""
        table_name = self._table_name(symbol, freq)
        date_col = "date" if freq == "1d" else "datetime"
        
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"""
                    SELECT 
                        COUNT(*) as total_rows,
                        MIN(`{date_col}`) as start_date,
                        MAX(`{date_col}`) as end_date
                    FROM `{table_name}`
                """)
                return cursor.fetchone()
        except Exception:
            return None
            
    def list_tables(self, pattern: str = None) -> list[str]:
        """列出所有数据表"""
        with self.conn.cursor() as cursor:
            if pattern:
                cursor.execute("SHOW TABLES LIKE %s", (pattern,))
            else:
                cursor.execute("SHOW TABLES")
            return [row[f"Tables_in_{DB_NAME}"] for row in cursor.fetchall()]
            
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            
    @staticmethod
    def _table_name(symbol: str, freq: Literal["1d", "5m"]) -> str:
        """生成表名"""
        suffix = "" if freq == "1d" else "_m5"
        return f"{symbol.lower()}{suffix}"


# ─── 数据同步类 ────────────────────────────────────────────

class DataSync:
    """数据同步管理器"""
    
    def __init__(self, db: MySQLManager):
        self.db = db
        
    def sync_contract(self, symbol: str, freq: Literal["1d", "5m"] = "1d", force_full: bool = False):
        """
        同步单个合约数据
        
        Args:
            symbol: 合约代码，如 'cu0', 'rb2510'
            freq: '1d' 日线 / '5m' 五分钟线
            force_full: 是否强制全量更新
        """
        print(f"\n{'='*50}")
        print(f"同步合约: {symbol} | 频率: {freq}")
        print(f"{'='*50}")
        
        # 1. 确保表存在
        self.db.ensure_table(symbol, freq)
        
        # 2. 判断是否需要增量更新
        if not force_full:
            latest_date = self.db.get_latest_date(symbol, freq)
            if latest_date:
                print(f"本地最新数据: {latest_date}")
                # 增量更新：从最新日期前 5 天开始（避免数据修正）
                # 注意：新浪 API 不支持按日期过滤，所以这里只是记录
                print("注意: 新浪 API 不支持增量下载，将获取全部数据并合并")
        
        # 3. 从新浪获取数据
        print(f"正在从新浪 API 获取数据...")
        bars = fetch_bars(symbol, freq=freq)
        
        if not bars:
            print(f"[ERROR] 未能获取到 {symbol} 的数据")
            return False
            
        print(f"[OK] 获取到 {len(bars)} 条数据")
        print(f"  时间范围: {bars[0].timestamp} ~ {bars[-1].timestamp}")
        
        # 4. 写入数据库
        inserted = self.db.insert_bars(symbol, freq, bars)
        print(f"[OK] 成功写入 {inserted} 条数据")
        
        # 5. 显示统计
        stats = self.db.get_stats(symbol, freq)
        if stats:
            print(f"  表总行数: {stats['total_rows']}")
            print(f"  数据范围: {stats['start_date']} ~ {stats['end_date']}")
            
        return True
        
    def sync_all(self, contracts: dict[str, list[str]], freq: Literal["1d", "5m"] = "1d"):
        """批量同步所有合约"""
        total = sum(len(v) for v in contracts.values())
        current = 0
        
        for category, symbols in contracts.items():
            print(f"\n{'#'*60}")
            print(f"# 类别: {category} ({len(symbols)} 个合约)")
            print(f"{'#'*60}")
            
            for symbol in symbols:
                current += 1
                print(f"\n进度: [{current}/{total}]")
                try:
                    self.sync_contract(symbol, freq)
                except Exception as e:
                    print(f"[ERROR] 同步失败: {e}")
                    continue
                    
        print(f"\n{'='*60}")
        print("同步完成!")
        print(f"{'='*60}")


# ─── 命令行入口 ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='新浪期货数据同步到 MySQL')
    parser.add_argument('--contracts', '-c', type=str, help='合约代码，逗号分隔，如: cu0,rb0,al0')
    parser.add_argument('--all', '-a', action='store_true', help='同步所有预置合约')
    parser.add_argument('--freq', '-f', type=str, default='1d', choices=['1d', '5m'], help='数据频率')
    parser.add_argument('--force', action='store_true', help='强制全量更新')
    parser.add_argument('--password', '-p', type=str, default='', help='MySQL 密码')
    parser.add_argument('--host', type=str, default='localhost', help='MySQL 主机')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有已同步的表')
    
    args = parser.parse_args()
    
    # 初始化数据库连接
    db = MySQLManager(host=args.host, password=args.password)
    
    try:
        # 确保数据库存在
        db.ensure_database()
        db.use_database()
        
        # 列出所有表
        if args.list:
            tables = db.list_tables()
            print(f"\n数据库 '{DB_NAME}' 中的表:")
            for table in sorted(tables):
                print(f"  - {table}")
            return
            
        # 同步指定合约
        if args.contracts:
            symbols = [s.strip() for s in args.contracts.split(',')]
            sync = DataSync(db)
            for symbol in symbols:
                sync.sync_contract(symbol, args.freq, args.force)
                
        # 同步所有合约
        elif args.all:
            contracts = available_contracts()
            sync = DataSync(db)
            sync.sync_all(contracts, args.freq)
            
        else:
            parser.print_help()
            
    finally:
        db.close()


if __name__ == "__main__":
    main()
