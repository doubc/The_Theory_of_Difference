"""
全量日线结构数据集构建脚本 (Build Full Structure Library)

目标：
从 MySQL sina 库中提取所有主力合约的日线数据，编译出完整的结构池。
不区分品种，将所有结构视为“信息差异展开”的通用案例存入统一数据集。
"""

import sys
import os
import json
import pandas as pd
from sqlalchemy import create_engine, inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.loader import MySQLLoader
from src.compiler.pipeline import compile_full, CompilerConfig

def get_all_symbols(db_name='sina'):
    """获取数据库中所有日线级别的表名（即品种代码）"""
    engine = create_engine('mysql+pymysql://root:root@localhost/sina?charset=utf8')
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    # 过滤掉非行情表，通常主力连续合约表名为字母+数字，如 cu0, rb0
    symbols = [t for t in tables if not t.endswith('m5') and not t.startswith('test')]
    return symbols

def build_library():
    import os
    print("正在连接数据库并获取全量品种列表...")
    password = os.getenv('MYSQL_PASSWORD', 'root')
    loader = MySQLLoader(host='localhost', user='root', password=password, db='sina')
    symbols = get_all_symbols()
    
    config = CompilerConfig(
        min_amplitude=0.02, 
        min_duration=3, 
        zone_bandwidth=0.01,
        cluster_eps=0.015,
        min_cycles=2
    )

    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "library", "full_structure_pool.jsonl")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    total_structures = 0
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for symbol in symbols:
            try:
                print(f"正在处理品种: {symbol} ...")
                bars = loader.get(symbol=symbol, freq='1d')
                
                if len(bars) < 100:  # 数据太少无法形成有效结构
                    continue

                result = compile_full(bars, config)
                
                # 序列化并写入
                for st in result.structures:
                    record = {
                        "symbol": symbol,
                        "start_date": str(st.cycles[0].entry.start.t.date()),
                        "end_date": str(st.cycles[-1].exit.end.t.date()),
                        "zone_center": st.zone.price_center,
                        "invariants": st.invariants,
                        "cycle_count": st.cycle_count
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
                    total_structures += 1
                
                print(f"  -> 识别出 {len(result.structures)} 个结构")

            except Exception as e:
                print(f"  -> 处理 {symbol} 时出错: {e}")

    print(f"\n构建完成！共收录 {total_structures} 个结构实例至: {output_path}")

if __name__ == "__main__":
    build_library()
