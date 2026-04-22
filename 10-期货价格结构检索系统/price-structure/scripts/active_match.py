#!/usr/bin/env python3
"""
主动匹配 CLI —— 用户带着观点来查，系统找历史相似并给出对比指引。

用法:
    python scripts/active_match.py \\
        --symbols AL0 \\
        --window 2023-01-01:2026-04-21 \\
        --context "铝价历史极高水平，单位利润12000，平均成本14000" \\
        --profit 12000 --cost 14000 \\
        --top-k 10
"""

import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.retrieval.active_match import ActiveMatchQuery, active_match


def _render_console(result):
    """终端输出"""
    q = result.query
    meta = result.scan_meta
    structures = result.matched_structures

    print()
    print("=" * 72)
    print("  主动匹配结果")
    print("=" * 72)
    print(f"  品种:      {', '.join(q.symbols)}")
    print(f"  检索窗口:  {q.search_start} ~ {q.search_end}")
    if q.context_note:
        print(f"  用户观点:  {q.context_note}")
    if q.profit_per_unit:
        print(f"  单位利润:  {q.profit_per_unit}")
    if q.avg_cost:
        print(f"  平均成本:  {q.avg_cost}")
    print(f"  窗口结构:  {meta['structures_in_window']} 个")
    print(f"  历史案例:  {meta['total_historical_cases']} 个")
    print()

    if not structures:
        print("  未在指定窗口内找到结构。")
        print("  建议：扩大时间窗口或调整编译器参数。")
        print("=" * 72)
        return

    for i, ms in enumerate(structures):
        print(f"─── 结构 {i+1}: {ms.symbol_name} ({ms.symbol}) "
              f"{ms.period_start} ~ {ms.period_end} ───")
        inv = ms.invariants
        print(f"    Cycles: {ms.structure.cycle_count}  "
              f"Speed Ratio: {inv.get('avg_speed_ratio', 0):.3f}  "
              f"Time Ratio: {inv.get('avg_time_ratio', 0):.3f}  "
              f"Zone: {inv.get('zone_rel_bw', 0):.4f}")
        print()

        if ms.historical_cases:
            print(f"    最相似的 {len(ms.historical_cases)} 段历史:")
            for j, c in enumerate(ms.historical_cases):
                d_marker = "↗" if c.direction == "up" else "↘" if c.direction == "down" else "○"
                print(f"    [{j+1}] {d_marker} 相似度={c.similarity:.3f}  "
                      f"形={c.sim_geometry:.2f} 节={c.sim_relation:.2f} 族={c.sim_family:.2f}")
                print(f"        {c.description}")
            print()

        if ms.comparison_guide:
            print("    对比指引:")
            for g in ms.comparison_guide:
                print(f"      → {g}")
        print()


def _render_html(result, output_dir="output"):
    """HTML 输出"""
    os.makedirs(output_dir, exist_ok=True)
    q = result.query
    meta = result.scan_meta
    structures = result.matched_structures
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y%m%d")

    # 结构卡片
    cards = []
    for ms in structures:
        inv = ms.invariants
        # 历史案例表
        case_rows = []
        for c in ms.historical_cases:
            # 国内习惯：红涨绿跌
            d_color = "#ef5350" if c.direction == "up" else "#26a69a" if c.direction == "down" else "#9e9e9e"
            d_text = "↗涨" if c.direction == "up" else "↘跌" if c.direction == "down" else "○不明"
            case_rows.append(f"""
            <tr>
              <td><b>{c.similarity:.3f}</b></td>
              <td style="font-size:11px">形{c.sim_geometry:.2f} 节{c.sim_relation:.2f}</td>
              <td>{ms.symbol_name} {c.period_start[:7]}~{c.period_end[:7]}</td>
              <td style="color:{d_color};font-weight:bold">{d_text}</td>
              <td>{c.outcome_move:.1%}</td>
              <td>{c.outcome_days}天</td>
              <td style="font-size:11px;color:#aaa">{c.description}</td>
            </tr>""")

        # 指引列表
        guide_items = "".join(f'<li>{g}</li>' for g in ms.comparison_guide)

        cards.append(f"""
        <div class="struct-card">
          <div class="struct-head">
            <span class="sym-badge">{ms.symbol_name}</span>
            <span class="sym-code">{ms.symbol}</span>
            <span class="period">{ms.period_start} ~ {ms.period_end}</span>
            <span class="cycle-badge">{ms.structure.cycle_count} cycles</span>
          </div>
          <div class="struct-meta">
            SR={inv.get('avg_speed_ratio',0):.3f} &nbsp;|&nbsp;
            TR={inv.get('avg_time_ratio',0):.3f} &nbsp;|&nbsp;
            LogSR={inv.get('avg_log_speed_ratio',0):.3f} &nbsp;|&nbsp;
            Zone={inv.get('zone_rel_bw',0):.4f} &nbsp;|&nbsp;
            Strength={inv.get('zone_strength',0):.1f}
          </div>
          <table class="case-table">
            <thead><tr>
              <th>相似度</th><th>拆解</th><th>历史段</th>
              <th>方向</th><th>幅度</th><th>天数</th><th>描述</th>
            </tr></thead>
            <tbody>{"".join(case_rows)}</tbody>
          </table>
          <div class="guide-box">
            <div class="guide-title">对比指引</div>
            <ol>{guide_items}</ol>
          </div>
        </div>""")

    ctx_lines = []
    if q.context_note:
        ctx_lines.append(f'<div class="ctx-line"><b>用户观点：</b>{q.context_note}</div>')
    if q.profit_per_unit:
        ctx_lines.append(f'<div class="ctx-line"><b>单位利润：</b>{q.profit_per_unit} &nbsp;|&nbsp; <b>平均成本：</b>{q.avg_cost or "N/A"}</div>')
    ctx_html = "\n".join(ctx_lines)

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>主动匹配报告 — {', '.join(q.symbols)} — {date_str}</title>
<style>
body{{background:#0f1020;color:#e5e5e5;font-family:-apple-system,"PingFang SC","Microsoft YaHei",monospace;margin:0;padding:24px}}
h1{{color:#90caf9;margin:0 0 4px 0}}
.meta{{color:#888;font-size:13px;margin-bottom:6px}}
.ctx-line{{color:#ccc;font-size:14px;margin:6px 0;padding:8px 12px;background:#1a1a2e;border-left:3px solid #ffb74d;border-radius:4px}}
.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}}
.summary .s{{background:#1a1a2e;border:1px solid #333;border-radius:6px;padding:12px;text-align:center}}
.summary .s .n{{font-size:22px;font-weight:bold;color:#fff}}
.summary .s .l{{color:#888;font-size:12px}}

.struct-card{{background:#1a1a2e;border:1px solid #333;border-left:3px solid #90caf9;border-radius:8px;padding:16px 20px;margin:18px 0}}
.struct-head{{display:flex;align-items:center;gap:12px;margin-bottom:8px}}
.sym-badge{{background:#90caf9;color:#0f1020;padding:3px 10px;border-radius:4px;font-weight:bold}}
.sym-code{{color:#888;font-size:12px}}
.period{{color:#ccc;font-size:14px}}
.cycle-badge{{background:#333;color:#aaa;padding:2px 8px;border-radius:3px;font-size:12px}}
.struct-meta{{color:#aaa;font-size:12px;margin-bottom:12px}}

.case-table{{width:100%;border-collapse:collapse;font-size:13px}}
.case-table th{{background:#12132a;color:#90caf9;padding:8px 10px;text-align:left;border-bottom:1px solid #333}}
.case-table td{{padding:8px 10px;border-bottom:1px solid #2a2a4a}}
.case-table tr:hover td{{background:#22223a}}

.guide-box{{margin-top:14px;padding:12px 16px;background:#12132a;border:1px solid #2a2a4a;border-radius:6px}}
.guide-title{{color:#ffb74d;font-weight:bold;margin-bottom:8px}}
.guide-box ol{{margin:0 0 0 18px;padding:0;color:#ccc;font-size:13px}}
.guide-box li{{margin-bottom:4px}}

.empty{{padding:40px;text-align:center;color:#888;background:#1a1a2e;border-radius:8px}}
</style>
</head>
<body>
<h1>主动匹配报告</h1>
<div class="meta">
  扫描时间 {ts} &nbsp;|&nbsp;
  品种 {', '.join(q.symbols)} &nbsp;|&nbsp;
  窗口 {q.search_start} ~ {q.search_end}
</div>

{ctx_html}

<div class="summary">
  <div class="s"><div class="n">{meta['structures_in_window']}</div><div class="l">窗口内结构</div></div>
  <div class="s"><div class="n">{meta['total_historical_cases']}</div><div class="l">历史相似案例</div></div>
  <div class="s"><div class="n">{len(structures)}</div><div class="l">匹配结果组</div></div>
  <div class="s"><div class="n">{q.top_k}</div><div class="l">每组 Top K</div></div>
</div>

{"".join(cards) if cards else '<div class="empty">未在指定窗口内找到结构。</div>'}

</body>
</html>"""

    filename = f"active_match_{'_'.join(q.symbols)}_{date_str}.html"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def main():
    parser = argparse.ArgumentParser(description="主动匹配：用户带着观点检索历史相似结构")
    parser.add_argument("--symbols", "-s", required=True,
                        help="品种列表，逗号分隔，如 AL0 或 AL0,RB0,CU0")
    parser.add_argument("--window", "-w", required=True,
                        help="检索窗口，格式 起始:结束，如 2023-01-01:2026-04-21")
    parser.add_argument("--context", "-c", default="",
                        help="用户观点描述，如 '铝价历史极高水平，利润12000/吨'")
    parser.add_argument("--profit", type=float, default=None,
                        help="当前单位利润")
    parser.add_argument("--cost", type=float, default=None,
                        help="历史平均成本")
    parser.add_argument("--price-context", default=None,
                        help="价格定性描述，如 '历史极高水平'")
    parser.add_argument("--top-k", "-k", type=int, default=10,
                        help="每个结构返回最相似的 K 段历史 (默认 10)")
    parser.add_argument("--min-cycles", type=int, default=2,
                        help="最小 cycle 数 (默认 2)")
    parser.add_argument("--data-dir", "-d", default="data",
                        help="数据目录 (默认 data)")
    parser.add_argument("--output", "-o", default="output",
                        help="输出目录 (默认 output)")
    parser.add_argument("--json", action="store_true",
                        help="同时输出 JSON 快照")

    args = parser.parse_args()

    # 解析窗口
    parts = args.window.split(":")
    if len(parts) != 2:
        print("错误：--window 格式应为 起始日期:结束日期，如 2023-01-01:2026-04-21")
        sys.exit(1)

    query = ActiveMatchQuery(
        symbols=[s.strip() for s in args.symbols.split(",")],
        search_start=parts[0].strip(),
        search_end=parts[1].strip(),
        context_note=args.context,
        profit_per_unit=args.profit,
        avg_cost=args.cost,
        price_context=args.price_context,
        top_k=args.top_k,
        min_cycles=args.min_cycles,
    )

    print(f"=== 主动匹配 [{datetime.now():%Y-%m-%d %H:%M}] ===")
    print(f"    品种: {query.symbols}")
    print(f"    窗口: {query.search_start} ~ {query.search_end}")
    if query.context_note:
        print(f"    观点: {query.context_note}")
    print()

    result = active_match(query, data_dir=args.data_dir)

    # 终端输出
    _render_console(result)

    # HTML 输出
    html_path = _render_html(result, output_dir=args.output)
    print(f"HTML 报告: {html_path}")

    # JSON 快照
    if args.json:
        snap_path = os.path.join(
            args.output,
            f"active_match_{'_'.join(query.symbols)}_{datetime.now():%Y%m%d_%H%M}.json",
        )
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"JSON 快照: {snap_path}")

    print(f"\n=== 完成 ===")


if __name__ == "__main__":
    main()
