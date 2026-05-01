#!/usr/bin/env python3
"""
阶段 6 端到端：编译 → 扫描 → 沉淀 → 检索

给定当前结构，从样本库中找最相似的历史案例，输出后验统计。
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
from src.retrieval.engine import RetrievalEngine
from src.retrieval.similarity import similarity


def main():
    print("=" * 60)
    print("  编译 → 扫描 → 沉淀 → 检索")
    print("=" * 60)

    # 1. 加载 + 编译
    print("\n[1] 加载 & 编译...")
    loader = load_cu0("data", dedup=True)
    all_bars = loader.get()

    config = CompilerConfig(
        min_amplitude=0.03, min_duration=3, noise_filter=0.008,
        zone_bandwidth=0.015, cluster_eps=0.02, cluster_min_points=2,
        min_cycles=2, tolerance=0.03,
    )
    result = compile_full(all_bars, config)
    print(f"    {len(result.structures)} 个结构")

    # 2. 扫描 + 沉淀
    print("\n[2] 规则扫描 & 样本沉淀...")
    rules = load_rules(Path("src/dsl/rules/default.yaml"))
    matches = scan(result.structures, rules)
    print(f"    {len(matches)} 个匹配")

    store = SampleStore("data/samples/library.jsonl")
    store.clear()
    for i, m in enumerate(matches):
        st = m.structure
        outcome = compute_forward_outcome(all_bars, st.t_end) if st.t_end else ForwardOutcome()
        store.append(SampleStore.from_structure(
            s=st, label_type=m.rule.name,
            sample_id=f"CU_{i:04d}", forward=outcome,
        ))
    print(f"    {store.count()} 样本已沉淀")

    # 3. 模拟"当前"：用全量数据最后 10% 编译一个查询结构
    print("\n[3] 模拟检索场景...")
    split_idx = int(len(all_bars) * 0.9)
    recent_bars = all_bars[split_idx:]
    recent_result = compile_full(recent_bars, config)
    recent_matches = scan(recent_result.structures, rules)

    if not recent_matches:
        print("    近期无匹配结构，退出")
        return

    # 取第一个匹配的结构做查询
    query_match = recent_matches[0]
    query = query_match.structure
    print(f"    查询结构: {query.label} | zone={query.zone.price_center:.0f} | "
          f"cycles={query.cycle_count} | speed_r={query.avg_speed_ratio:.2f}")

    # 4. 检索
    print(f"\n[4] 从样本库检索相似结构...")
    engine = RetrievalEngine(store)
    result = engine.retrieve(query, top_k=5, min_score=0.3)

    print(f"\n    近邻 ({len(result.neighbors)} 个):")
    for i, n in enumerate(result.neighbors):
        print(f"      [{i+1}] {n.sample.id} | {n.sample.label_type} | "
              f"score={n.score.total:.3f} "
              f"(geo={n.score.geometric:.2f} rel={n.score.relational:.2f} fam={n.score.family:.2f})")
        print(f"          {n.sample.t_start:%Y-%m-%d} ~ {n.sample.t_end:%Y-%m-%d} | "
              f"typicality={n.sample.typicality:.2f}")

    p = result.posterior
    print(f"\n    后验统计 (n={p.sample_size}):")
    print(f"      mean_ret_5d:   {p.mean_ret_5d:+.2%}")
    print(f"      mean_ret_10d:  {p.mean_ret_10d:+.2%}")
    print(f"      mean_ret_20d:  {p.mean_ret_20d:+.2%}")
    print(f"      median_ret_20d: {p.median_ret_20d:+.2%}")
    print(f"      prob_positive_10d: {p.prob_positive_10d:.0%}")
    print(f"      mean_max_dd:   {p.mean_max_dd_20d:+.2%}")
    print(f"      mean_max_rise: {p.mean_max_rise_20d:+.2%}")

    print("\n" + "=" * 60)
    print("  检索完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
