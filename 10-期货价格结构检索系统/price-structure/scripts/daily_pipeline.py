#!/usr/bin/env python3
"""
日更流水线 — 每日自动执行

1. update_data()         — 更新数据（当前为 CSV 重读）
2. recompile()           — 重新编译结构
3. rule_engine.scan()    — 规则扫描
4. retrieve_similar()    — 对每个候选检索相似案例
5. render_report()       — 输出 Markdown 报告
6. log_research_notes()  — 记录运行日志
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


def run_daily(output_dir: str = "output"):
    """执行日更流水线"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"[{today}] 日更流水线启动")

    # 1. 数据
    print("  [1] 加载数据...")
    loader = load_cu0("data", dedup=True)
    bars = loader.get()
    print(f"      {len(bars)} bars ({bars[0].timestamp:%Y-%m-%d} ~ {bars[-1].timestamp:%Y-%m-%d})")

    # 2. 编译
    print("  [2] 编译...")
    config = CompilerConfig(
        min_amplitude=0.03, min_duration=3, noise_filter=0.008,
        zone_bandwidth=0.015, cluster_eps=0.02, cluster_min_points=2,
        min_cycles=2, tolerance=0.03,
    )
    result = compile_full(bars, config)
    print(f"      {len(result.structures)} 结构, {len(result.bundles)} 丛")

    # 3. 规则扫描
    print("  [3] 规则扫描...")
    rules = load_rules(Path("src/dsl/rules/default.yaml"))
    matches = scan(result.structures, rules)
    print(f"      {len(matches)} 匹配")

    # 4. 检索
    print("  [4] 相似检索...")
    store = SampleStore("data/samples/library.jsonl")
    engine = RetrievalEngine(store)

    retrieval_results = []
    for m in matches[:10]:  # 前 10 个候选
        ret = engine.retrieve(m.structure, top_k=5)
        retrieval_results.append((m, ret))

    # 5. 报告
    print("  [5] 生成报告...")
    report_lines = [
        f"# 日更报告 — {today}\n",
        f"**数据**: {len(bars)} bars ({bars[0].timestamp:%Y-%m-%d} ~ {bars[-1].timestamp:%Y-%m-%d})\n",
        f"**编译**: {len(result.structures)} 结构, {len(result.zones)} 区, {len(result.bundles)} 丛\n",
        f"**规则匹配**: {len(matches)} / {len(result.structures)}\n",
        "---\n",
    ]

    for i, (m, ret) in enumerate(retrieval_results):
        report_lines.append(f"## 候选 {i+1}: {m.rule.name}\n")
        report_lines.append(f"- Zone: {m.structure.zone.price_center:.0f} (±{m.structure.zone.bandwidth:.0f})")
        report_lines.append(f"- Cycles: {m.structure.cycle_count}")
        report_lines.append(f"- speed_r: {m.structure.avg_speed_ratio:.2f}, time_r: {m.structure.avg_time_ratio:.2f}")
        report_lines.append(f"- typicality: {m.typicality:.2f}\n")

        if ret.neighbors:
            p = ret.posterior
            report_lines.append(f"**后验 (n={p.sample_size})**:")
            report_lines.append(f"- ret_5d: {p.mean_ret_5d:+.2%}")
            report_lines.append(f"- ret_10d: {p.mean_ret_10d:+.2%}")
            report_lines.append(f"- ret_20d: {p.mean_ret_20d:+.2%}")
            report_lines.append(f"- P(正): {p.prob_positive_10d:.0%}")
            report_lines.append(f"- max_dd: {p.mean_max_dd_20d:+.2%}")
            report_lines.append(f"- max_rise: {p.mean_max_rise_20d:+.2%}\n")
        else:
            report_lines.append("无足够相似样本\n")

    report_path = out / f"daily_{today}.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"      报告: {report_path}")

    print(f"[{today}] 完成")
    return report_path


if __name__ == "__main__":
    run_daily()
