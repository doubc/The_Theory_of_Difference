"""
每日知识图谱增量更新

流程：
1. 从 MySQL 加载所有品种的日线数据
2. 逐品种编译结构（compile_full + graph_store 持久化）
3. 重建索引 + 保存当日快照
4. 输出图谱统计

使用方式：
    python scripts/daily_graph_update.py                    # 全量更新
    python scripts/daily_graph_update.py --symbol CU000     # 单品种更新
    python scripts/daily_graph_update.py --stats            # 仅查看统计

依赖：
    - MySQL sina 数据库（或 CSV 数据）
    - GraphStore 自动创建 data/graph/ 目录
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.compiler.pipeline import compile_full, CompilerConfig
from src.graph import StructureGraph
from src.graph.store import GraphStore


def get_symbols_from_mysql() -> list[str]:
    """从 MySQL 获取所有品种列表"""
    try:
        from sqlalchemy import create_engine, inspect
        password = os.getenv("MYSQL_PASSWORD", "")
        pwd_part = f":{password}" if password else ""
        engine = create_engine(f"mysql+pymysql://root{pwd_part}@localhost/sina?charset=utf8")
        tables = inspect(engine).get_table_names()
        return [t for t in tables if not t.endswith("m5") and not t.startswith("test")]
    except Exception as e:
        print(f"⚠️ MySQL 连接失败: {e}")
        return []


def load_bars_for_symbol(symbol: str):
    """加载某品种的日线数据"""
    try:
        from src.data.loader import MySQLLoader
        password = os.getenv("MYSQL_PASSWORD", "")
        loader = MySQLLoader(host="localhost", user="root", password=password, db="sina")
        return loader.get(symbol=symbol, freq="1d")
    except Exception:
        # 降级到 CSV
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", f"{symbol.lower()}.csv")
        if os.path.exists(csv_path):
            from src.data.loader import CSVLoader
            return CSVLoader().get(path=csv_path)
        return []


def update_graph(
        symbols: list[str] | None = None,
        graph_dir: str = "data/graph",
        config: CompilerConfig | None = None,
) -> dict:
    """
    每日知识图谱增量更新主函数。

    Args:
        symbols: 品种列表，None 时自动从 MySQL 获取
        graph_dir: 图谱存储目录
        config: 编译配置

    Returns:
        更新统计
    """
    if config is None:
        config = CompilerConfig(min_amplitude=0.02, min_duration=3, zone_bandwidth=0.01)

    if symbols is None:
        symbols = get_symbols_from_mysql()

    if not symbols:
        print("❌ 无品种数据，请先运行 sina_to_mysql.py 同步数据")
        return {"error": "no_symbols"}

    store = GraphStore(base_path=graph_dir)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"=== 每日知识图谱更新 [{ts}] ===")
    print(f"品种数: {len(symbols)}")
    print(f"存储目录: {graph_dir}")
    print()

    total_structures = 0
    total_errors = 0
    symbol_results = {}

    for sym in symbols:
        try:
            bars = load_bars_for_symbol(sym)
            if len(bars) < 50:
                continue

            # compile_full 自动调用 graph_store.daily_ingest()
            result = compile_full(bars, config=config, symbol=sym, graph_store=store)

            n_structures = len(result.structures)
            total_structures += n_structures
            symbol_results[sym] = n_structures

            if n_structures > 0:
                print(f"  ✓ {sym}: {n_structures} 结构")

        except Exception as e:
            total_errors += 1
            print(f"  ✗ {sym}: {e}")
            continue

    # 保存当日快照 + 重建索引
    snap_path = store.save_snapshot()
    idx_stats = store.rebuild_indexes()

    # 统计
    graph_stats = store.stats()

    print()
    print(f"=== 更新完成 ===")
    print(f"编译品种: {len(symbol_results)}")
    print(f"新增结构: {total_structures}")
    print(f"错误数: {total_errors}")
    print(f"图谱总计: {graph_stats['structures']} 结构 / {graph_stats['zones']} Zone / {graph_stats['edges']} 边")
    print(f"快照: {snap_path}")

    return {
        "date": ts,
        "symbols_processed": len(symbol_results),
        "structures_added": total_structures,
        "errors": total_errors,
        "snapshot": snap_path,
        **graph_stats,
    }


def show_stats(graph_dir: str = "data/graph"):
    """显示图谱统计"""
    store = GraphStore(base_path=graph_dir)
    stats = store.stats()

    print(f"=== 知识图谱统计 ===")
    print(f"结构节点: {stats['structures']}")
    print(f"Zone 节点: {stats['zones']}")
    print(f"叙事节点: {stats['narratives']}")
    print(f"边总数: {stats['edges']}")
    print()
    print("边类型分布:")
    for et, count in sorted(stats.get("edge_types", {}).items(), key=lambda x: -x[1]):
        print(f"  {et}: {count}")
    print()
    print("品种分布:")
    for sym, count in sorted(stats.get("symbols", {}).items(), key=lambda x: -x[1]):
        print(f"  {sym}: {count}")
    print()
    print(f"快照: {', '.join(stats.get('snapshots', [])) or '无'}")


def main():
    parser = argparse.ArgumentParser(description="每日知识图谱增量更新")
    parser.add_argument("--symbol", type=str, help="单品种更新")
    parser.add_argument("--symbols", type=str, help="逗号分隔的品种列表")
    parser.add_argument("--stats", action="store_true", help="仅查看统计")
    parser.add_argument("--graph-dir", default="data/graph", help="图谱存储目录")
    args = parser.parse_args()

    if args.stats:
        show_stats(args.graph_dir)
        return

    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        symbols = None  # 自动获取

    update_graph(symbols=symbols, graph_dir=args.graph_dir)


if __name__ == "__main__":
    main()
