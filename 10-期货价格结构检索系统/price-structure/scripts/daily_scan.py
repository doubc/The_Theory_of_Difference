"""
每日机会扫描脚本 — 阶段四修订版

修订重点：
1. 修复 is_opportunity_viable 的边界逻辑（改为近期 ATR 活跃度过滤）
2. 修复 calculate_distance 的量纲问题（统一归一化）
3. HTML 报告增加结构证据链字段、分项相似度、方向置信度
4. analyze_template_move 离线降级（数据库不可用时返回模板中已存的 outcome）
"""

import sys
import os
import json
import math
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.loader import MySQLLoader
from src.compiler.pipeline import compile_full, CompilerConfig
from src.relations import structure_invariants
from sqlalchemy import create_engine, inspect
import pandas as pd

# ── 归一化尺度（与 similarity.py 的 INVARIANT_SCALES 保持一致）──────────
FEATURE_SCALES = {
    "avg_speed_ratio": 2.0,
    "avg_time_ratio": 2.0,
    "zone_rel_bw": 0.03,
    "high_dispersion": 0.02,
    "low_dispersion": 0.02,
    "zone_strength": 5.0,
}
FEATURES = list(FEATURE_SCALES.keys())

# ── 相似度阈值 ───────────────────────────────────────────────────────────
MAX_DIST_THRESHOLD = 1.5  # 归一化距离超过此值直接丢弃


def calculate_distance(inv1: dict, inv2: dict) -> tuple[float, dict]:
    """
    归一化欧氏距离 + 分项差异。
    返回 (total_dist, diff_detail)
    """
    diff = {}
    dist_sq = 0.0
    for f in FEATURES:
        scale = FEATURE_SCALES[f]
        v1 = (inv1.get(f) or 0) / scale
        v2 = (inv2.get(f) or 0) / scale
        d = abs(v1 - v2)
        diff[f] = round(d, 3)
        dist_sq += d ** 2
    return math.sqrt(dist_sq), diff


def is_opportunity_viable(bars: list, min_atr_pct: float = 0.005) -> bool:
    """
    活跃度过滤：用近 20 根 bar 的平均真实波幅（ATR%）判断品种是否活跃。
    替换原来的"历史绝对位置"过滤——那个逻辑会系统性过滤突破行情。
    """
    if len(bars) < 20:
        return False
    recent = bars[-20:]
    atrs = []
    for i in range(1, len(recent)):
        b = recent[i]
        prev_close = recent[i - 1].close
        tr = max(b.high - b.low, abs(b.high - prev_close), abs(b.low - prev_close))
        atrs.append(tr / prev_close if prev_close > 0 else 0)
    avg_atr_pct = sum(atrs) / len(atrs) if atrs else 0
    return avg_atr_pct >= min_atr_pct


def get_template_outcome(template: dict) -> tuple[str, str, str]:
    """
    从模板已存的 outcome 字段读取走势信息（离线降级方案）。
    避免每次扫描都重新查数据库。
    """
    outcome = template.get('outcome')
    if not outcome:
        return "N/A", "N/A", "N/A"

    direction = template.get('primary_direction', 'unknown')
    up = outcome.get('up_move', 0)
    down = outcome.get('down_move', 0)

    if direction == 'up':
        return f"+{up:.1%}", "看涨", f"{up:.1%}"
    elif direction == 'down':
        return f"-{down:.1%}", "看跌", f"{down:.1%}"
    else:
        return f"±{max(up, down):.1%}", "方向不明", f"{max(up, down):.1%}"


def generate_html_report(opportunities: list, filename: str = "daily_scan_report.html"):
    """
    生成带证据链的 HTML 报告。
    每条机会展示：分项相似度、结构不变量对比、方向置信度、模板 outcome 来源。
    """
    date_str = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    rows_html = ""
    for opp in opportunities:
        sim = opp['similarity']
        sim_color = "#00c853" if sim > 0.8 else "#ff9800" if sim > 0.65 else "#9e9e9e"
        dir_color = "#26a69a" if "涨" in opp['direction'] else "#ef5350" if "跌" in opp['direction'] else "#9e9e9e"

        # 分项差异展示
        diff_html = "".join(
            f"<span style='margin-right:8px;color:#aaa'>"
            f"{k}=<b style='color:{'#ef5350' if v > 0.3 else '#eee'}'>{v:.2f}</b></span>"
            for k, v in opp.get('diff_detail', {}).items()
        )

        # 当前结构不变量
        inv_html = "".join(
            f"<span style='margin-right:8px;color:#aaa'>{k}=<b>{round(v, 3)}</b></span>"
            for k, v in opp.get('current_inv', {}).items()
            if k in FEATURES
        )

        rows_html += f"""
        <tr>
          <td><b style="font-size:15px">{opp['symbol']}</b></td>
          <td><b style="color:{sim_color};font-size:16px">{sim:.3f}</b></td>
          <td style="color:#aaa">{opp['template_date']}<br>
              <small>outcome起点: {opp.get('outcome_start', 'N/A')}</small></td>
          <td>{opp['current_zone']:.1f}</td>
          <td>{opp['hist_move']}</td>
          <td><b style="color:{dir_color}">{opp['direction']}</b></td>
          <td><b>{opp['potential_move']}</b></td>
          <td style="font-size:11px">{diff_html}</td>
          <td style="font-size:11px">{inv_html}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>每日结构机会扫描 — {date_str}</title>
<style>
  body {{ background:#1a1a2e; color:#e0e0e0; font-family:'PingFang SC',sans-serif; margin:0; padding:20px; }}
  h1 {{ color:#90caf9; border-bottom:1px solid #333; padding-bottom:10px; }}
  .meta {{ color:#888; margin-bottom:20px; font-size:13px; }}
  table {{ width:100%; border-collapse:collapse; background:#16213e; border-radius:8px; overflow:hidden; }}
  th {{ background:#0f3460; color:#90caf9; padding:10px 12px; text-align:left; font-size:13px; }}
  td {{ padding:10px 12px; border-bottom:1px solid #1a1a2e; vertical-align:top; font-size:13px; }}
  tr:hover td {{ background:#0d2137; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; }}
  .no-result {{ color:#888; padding:40px; text-align:center; font-size:16px; }}
</style>
</head>
<body>
<h1>每日高潜力结构机会扫描</h1>
<div class="meta">
  扫描时间: {time_str} &nbsp;|&nbsp;
  发现机会: <b style="color:#90caf9">{len(opportunities)}</b> 个 &nbsp;|&nbsp;
  相似度阈值: {1 / (1 + MAX_DIST_THRESHOLD):.2f}
</div>
{"<table><thead><tr><th>品种</th><th>相似度</th><th>模板日期</th><th>当前中枢</th><th>历史走势</th><th>方向</th><th>潜在幅度</th><th>分项差异</th><th>当前不变量</th></tr></thead><tbody>" + rows_html + "</tbody></table>"
    if opportunities else '<div class="no-result">今日未发现符合高潜力约束的市场机会。</div>'}
</body>
</html>"""

    output_path = os.path.join(os.path.dirname(__file__), "..", "output", filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\nHTML 报告已生成: {output_path}")


def load_templates() -> list:
    template_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "library", "high_potential_templates.jsonl"
    )
    templates = []
    with open(template_path, 'r', encoding='utf-8') as f:
        for line in f:
            templates.append(json.loads(line))
    return templates


def get_all_symbols() -> list[str]:
    try:
        engine = create_engine('mysql+pymysql://root:root@localhost/sina?charset=utf8')
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return [t for t in tables if not t.endswith('m5') and not t.startswith('test')]
    except Exception:
        return []


def daily_scan(scan_window_years: int = 3):
    print(f"--- 每日机会扫描 [{datetime.now().strftime('%Y-%m-%d %H:%M')}] ---")

    templates = load_templates()
    current_year = datetime.now().year

    active_templates = [
        t for t in templates
        if current_year - int(t['end_date'][:4]) <= scan_window_years
    ]
    print(
        f"全量模板 {len(templates)} 个，"
        f"近 {scan_window_years} 年活跃参照系 {len(active_templates)} 个。"
    )
    if not active_templates:
        print("活跃模板为空，请先运行 identify_high_potential_structures.py")
        return

    loader = MySQLLoader(host='localhost', user='root', password='root', db='sina')
    config = CompilerConfig(min_amplitude=0.02, min_duration=3, zone_bandwidth=0.01)
    symbols = get_all_symbols()
    opportunities = []

    for symbol in symbols:
        try:
            bars = loader.get(symbol=symbol, freq='1d')
            if len(bars) < 50:
                continue

            # 活跃度过滤（修复原来的位置过滤逻辑）
            if not is_opportunity_viable(bars):
                continue

            result = compile_full(bars, config)
            if not result.structures:
                continue

            # 取最新一个**已确认完成**的结构（排除当前正在演化的最后一个）
            if len(result.structures) < 2:
                continue
            current_st = result.structures[-2]
            current_inv = current_st.invariants or {}

            # 归一化距离匹配
            best_match = None
            min_dist = float('inf')
            best_diff = {}

            for tmpl in active_templates:
                tmpl_inv = tmpl.get('invariants', {})
                dist, diff = calculate_distance(current_inv, tmpl_inv)
                if dist < min_dist:
                    min_dist = dist
                    best_match = tmpl
                    best_diff = diff

            if best_match is None or min_dist >= MAX_DIST_THRESHOLD:
                continue

            similarity = 1 / (1 + min_dist)
            hist_move, direction, potential = get_template_outcome(best_match)

            opportunities.append({
                "symbol": symbol,
                "similarity": round(similarity, 4),
                "template_date": best_match['end_date'],
                "outcome_start": best_match.get('outcome', {}).get('outcome_start_date', 'N/A'),
                "current_zone": current_st.zone.price_center,
                "hist_move": hist_move,
                "direction": direction,
                "potential_move": potential,
                "diff_detail": best_diff,
                "current_inv": current_inv,
            })

        except Exception:
            continue

    if not opportunities:
        print("今日未发现符合高潜力约束的市场机会。")
        generate_html_report([])
        return

    opportunities.sort(key=lambda x: x['similarity'], reverse=True)
    print(f"\n发现 {len(opportunities)} 个潜在机会，正在生成 HTML 报告...")
    generate_html_report(opportunities)


if __name__ == "__main__":
    daily_scan()
