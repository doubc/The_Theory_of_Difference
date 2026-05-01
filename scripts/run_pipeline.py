#!/usr/bin/env python3
"""
阶段 4+5 端到端流程：编译 → 规则扫描 → 样本沉淀

运行: python3 scripts/run_pipeline.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from datetime import datetime

from src.data.loader import load_cu0
from src.compiler.pipeline import compile_full, CompilerConfig
from src.dsl.rule import load_rules, scan
from src.sample.store import SampleStore, Sample, ForwardOutcome
from src.sample.outcome import compute_forward_outcome


def main():
    print("=" * 60)
    print("  编译 → 规则扫描 → 样本沉淀")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1] 加载铜连续合约数据...")
    loader = load_cu0("data", dedup=True)
    all_bars = loader.get()
    print(f"    {len(all_bars)} bars ({all_bars[0].timestamp:%Y-%m-%d} ~ {all_bars[-1].timestamp:%Y-%m-%d})")

    # 2. 编译
    print("\n[2] 编译全量数据...")
    config = CompilerConfig(
        min_amplitude=0.03,
        min_duration=3,
        noise_filter=0.008,
        zone_bandwidth=0.015,
        cluster_eps=0.02,
        cluster_min_points=2,
        min_cycles=2,
        tolerance=0.03,
    )
    result = compile_full(all_bars, config)
    s = result.summary()
    print(f"    极值点: {s['pivots']}  段: {s['segments']}  区: {s['zones']}  "
          f"循环: {s['cycles']}  结构: {s['structures']}  丛: {s['bundles']}")

    # 3. 规则扫描
    print("\n[3] 加载规则并扫描...")
    rules_path = Path("src/dsl/rules/default.yaml")
    rules = load_rules(rules_path)
    print(f"    规则数: {len(rules)}")
    for r in rules:
        print(f"      - {r.name}: {r.description[:30]}...")

    matches = scan(result.structures, rules)
    print(f"\n    匹配结果: {len(matches)} / {len(result.structures)} 个结构命中规则")

    # 统计各规则命中数
    type_counts: dict[str, int] = {}
    for m in matches:
        type_counts[m.rule.name] = type_counts.get(m.rule.name, 0) + 1

    print(f"\n    各类型分布:")
    for name, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"      {name}: {count}")

    # 4. 样本沉淀（增量模式）
    print("\n[4] 沉淀样本...")
    store = SampleStore("data/samples/library.jsonl")

    # 已有样本的 id 集合，用于去重
    existing_ids = {s.id for s in store.load_all()}
    new_count = 0

    for i, m in enumerate(matches):
        sample_id = f"CU_{i:04d}"
        if sample_id in existing_ids:
            continue  # 跳过已存在的样本

        st = m.structure
        # 计算前向演化
        if st.t_end:
            outcome = compute_forward_outcome(all_bars, st.t_end)
        else:
            outcome = ForwardOutcome()

        sample = SampleStore.from_structure(
            s=st,
            label_type=m.rule.name,
            sample_id=f"CU_{i:04d}",
            annotation=f"typicality={m.typicality:.2f}",
            forward=outcome,
        )
        store.append(sample)
        new_count += 1

    print(f"    已写入 {new_count} 个新样本（总计 {store.count()}） → {store.path}")

    # 5. 样本质量检查
    print("\n[5] 样本质量检查...")
    all_samples = store.load_all()

    # 按类型统计
    print(f"    总样本: {len(all_samples)}")
    for name in sorted(type_counts.keys()):
        samples_of_type = [s for s in all_samples if s.label_type == name]
        avg_typ = sum(s.typicality for s in samples_of_type) / len(samples_of_type) if samples_of_type else 0
        has_outcome = sum(1 for s in samples_of_type if s.forward_outcome)
        print(f"      {name}: {len(samples_of_type)} 样本, avg_typicality={avg_typ:.2f}, "
              f"有前向标签={has_outcome}")

    # 典型样本展示
    print(f"\n[6] 典型样本展示（前 3 个）:")
    for s in all_samples[:3]:
        print(f"\n    {s.id} | {s.label_type} | {s.symbol}")
        print(f"    时间: {s.t_start:%Y-%m-%d} ~ {s.t_end:%Y-%m-%d}")
        print(f"    typicality: {s.typicality:.2f}")
        inv = s.structure.get("invariants", {})
        print(f"    不变量: speed_r={inv.get('avg_speed_ratio', 0):.2f}, "
              f"time_r={inv.get('avg_time_ratio', 0):.2f}, "
              f"cycles={inv.get('cycle_count', 0)}")
        if s.forward_outcome:
            fo = s.forward_outcome
            print(f"    前向: ret_5d={fo.get('ret_5d', 0):.2%}, "
                  f"ret_20d={fo.get('ret_20d', 0):.2%}, "
                  f"max_dd={fo.get('max_dd_20d', 0):.2%}")

    print("\n" + "=" * 60)
    print("  阶段 4+5 端到端验证完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
