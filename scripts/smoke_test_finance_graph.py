#!/usr/bin/env python3
"""
冒烟测试 — 验证 product_ingester 能正确导入所有品种数据到 GraphStore

运行：python3 scripts/smoke_test_finance_graph.py
"""
import sys
import os
import json
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.graph.store import GraphStore
from src.graph.product_ingester import ProductKnowledgeIngester


def main():
    print("=" * 60)
    print("冒烟测试：金融知识图谱导入")
    print("=" * 60)

    # 用临时目录，不污染正式数据
    tmp_dir = tempfile.mkdtemp(prefix="smoke_graph_")
    store = GraphStore(tmp_dir)

    try:
        # 1. 初始化导入器
        print("\n[1] 初始化 ProductKnowledgeIngester...")
        try:
            ingester = ProductKnowledgeIngester(store)
            print(f"    ✓ 注册表加载成功，{len(ingester.registry)} 个品种")
            for key, prod in ingester.registry.items():
                print(f"      {key}: {prod.get('name','')} ({prod.get('status','')})")
        except Exception as e:
            print(f"    ✗ 初始化失败: {e}")
            return False

        # 2. 全量导入
        print("\n[2] 全量导入所有 active 品种...")
        try:
            stats = ingester.ingest_all_active_products(force=True)
            for key, s in stats.items():
                if s.skipped:
                    print(f"    {key}: 跳过 ({s.reason})")
                else:
                    print(f"    {key}: {s.entities}E {s.relations}R {s.chains}C "
                          f"{s.polarity_rules}P {s.pricing_models}M → {s.edges} edges")
        except Exception as e:
            print(f"    ✗ 导入失败: {e}")
            import traceback; traceback.print_exc()
            return False

        # 3. 验证数据写入
        print("\n[3] 验证 GraphStore 数据...")
        structures = store.load_all_structures()
        zones = store.load_all_zones()
        narratives = store.load_all_narratives()
        edges = store.load_all_edges()

        print(f"    structures.jsonl: {len(structures)} 条")
        print(f"    zones.jsonl:      {len(zones)} 条")
        print(f"    narratives.jsonl: {len(narratives)} 条")
        print(f"    edges.jsonl:      {len(edges)} 条")

        total_nodes = len(structures) + len(zones) + len(narratives)
        if total_nodes == 0:
            print("    ✗ 没有任何节点被写入！")
            return False
        if len(edges) == 0:
            print("    ⚠ 没有任何边被写入")

        # 4. 验证命名空间
        print("\n[4] 验证品种命名空间...")
        products_found = set()
        for z in zones:
            zk = z.get("zone_key", "")
            if ":" in zk:
                products_found.add(zk.split(":")[0])
        for s in structures:
            sid = s.get("struct_id", "")
            if ":" in sid:
                products_found.add(sid.split(":")[0])
        for n in narratives:
            nid = n.get("narrative_id", "")
            if ":" in nid:
                products_found.add(nid.split(":")[0])

        print(f"    发现命名空间: {sorted(products_found)}")

        # 5. 验证增量更新（第二次导入应跳过）
        print("\n[5] 验证增量更新（无变化应跳过）...")
        stats2 = ingester.ingest_all_active_products(force=False)
        skipped = sum(1 for s in stats2.values() if s.skipped and s.reason == "no_change")
        print(f"    跳过 {skipped}/{len(stats2)} 个品种 (no_change)")

        # 6. 验证 reload
        print("\n[6] 验证 reload_product...")
        first_product = next(k for k in ingester.registry if k != "_shared")
        try:
            s = ingester.reload_product(first_product)
            print(f"    ✓ {first_product} reload: {s.entities}E {s.relations}R")
        except Exception as e:
            print(f"    ✗ reload 失败: {e}")
            return False

        # 7. 验证快照
        print("\n[7] 保存图谱快照...")
        try:
            snap_path = store.save_snapshot(label="smoke_test")
            print(f"    ✓ 快照: {snap_path}")
            with open(snap_path) as f:
                snap = json.load(f)
            print(f"      {len(snap.get('structures',[]))} structures, "
                  f"{len(snap.get('zones',[]))} zones, "
                  f"{len(snap.get('narratives',[]))} narratives, "
                  f"{len(snap.get('edges',[]))} edges")
        except Exception as e:
            print(f"    ⚠ 快照失败: {e}")

        print("\n" + "=" * 60)
        print("✅ 冒烟测试通过！")
        print("=" * 60)
        return True

    finally:
        # 清理临时目录
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
