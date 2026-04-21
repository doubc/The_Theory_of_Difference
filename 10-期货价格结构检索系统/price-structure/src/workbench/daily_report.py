"""
面向研究决策的日报渲染器 —— 三段式布局: 简报 / 重点卡片 / 完整清单
"""
from __future__ import annotations
from datetime import datetime
from src.retrieval.opportunity import Opportunity


def _direction_badge(direction: str, confidence: float) -> str:
    conf_pct = int(confidence * 100)
    if direction == "up":
        return f'<span class="badge up">↗ 看涨 {conf_pct}%</span>'
    if direction == "down":
        return f'<span class="badge down">↘ 看跌 {conf_pct}%</span>'
    return f'<span class="badge neutral">○ 不明</span>'


def _potential_bar(p25: float, median_: float, p75: float) -> str:
    """用一个彩色条展示潜力区间的 p25/中位/p75"""
    width_pct = min(p75 * 100 * 3, 100)  # 20% 幅度对应 60% 条宽
    median_pos = (median_ / p75 * 100) if p75 > 0 else 0
    return f"""
    <div class="potential-bar">
      <div class="bar-outer" style="width:{width_pct}%">
        <div class="bar-marker" style="left:{median_pos}%"></div>
      </div>
      <div class="bar-text">
        <b>{median_ * 100:.1f}%</b>
        <span style="color:#888">  区间 {p25 * 100:.1f}%~{p75 * 100:.1f}%</span>
      </div>
    </div>"""


def _sim_bars(sim_geo: float, sim_rel: float, sim_fam: float) -> str:
    def bar(label, val):
        w = int(val * 100)
        return f"""
        <div class="sim-item">
          <span class="sim-label">{label}</span>
          <div class="sim-bar"><div class="sim-fill" style="width:{w}%"></div></div>
          <span class="sim-val">{val:.2f}</span>
        </div>"""

    return f"""
    <div class="sim-box">
      {bar("形态", sim_geo)}
      {bar("节奏", sim_rel)}
      {bar("家族", sim_fam)}
    </div>"""


def _match_thumbnails(top_matches: list) -> str:
    """最像的三段历史缩略图条"""
    if not top_matches:
        return ""
    cells = []
    for m in top_matches[:3]:
        move_text = f"+{m.up_move * 100:.1f}%" if m.direction == "up" else f"-{m.down_move * 100:.1f}%"
        color = "#26a69a" if m.direction == "up" else "#ef5350"
        cells.append(f"""
        <div class="match-cell">
          <div class="match-head">{m.symbol_name} <span style="color:#888">({m.symbol})</span></div>
          <div class="match-date">{m.end_date[:7]}</div>
          <div class="match-thumb" style="background:linear-gradient(90deg,#2a2a4a 0%,{color}44 100%)">
            <span style="color:{color};font-weight:bold">{move_text}</span>
          </div>
          <div class="match-sim">相似 {m.similarity:.2f}</div>
        </div>""")
    return '<div class="matches-row">' + "".join(cells) + '</div>'


def _opp_card(opp: Opportunity) -> str:
    """单张重点关注卡片"""
    return f"""
    <div class="opp-card">
      <div class="card-head">
        <div class="card-title">
          <span class="attention">{opp.attention_score:.0f}</span>
          <span class="sym-name">{opp.symbol_name}</span>
          <span class="sym-code">{opp.symbol}</span>
          {_direction_badge(opp.direction, opp.direction_confidence)}
        </div>
        <div class="card-price">当前 {opp.current_price:.1f} → 触发 <b>{opp.trigger_price:.1f}</b></div>
      </div>
      <div class="card-body">
        <div class="card-left">
          <div class="label">潜在幅度（同类模板中位数 / 区间）</div>
          {_potential_bar(opp.potential_p25, opp.potential_median, opp.potential_p75)}
          <div class="label" style="margin-top:10px">预期兑现窗口</div>
          <div class="window">≈ {opp.expected_window_days} 个交易日</div>

          <div class="label" style="margin-top:10px">相似性拆解</div>
          {_sim_bars(opp.sim_geometry, opp.sim_relation, opp.sim_family)}
        </div>

        <div class="card-right">
          <div class="label">最像的三段历史（点击对照）</div>
          {_match_thumbnails(opp.top_matches)}

          <div class="label" style="margin-top:10px">下一步研究建议</div>
          <ol class="actions">
            {"".join(f"<li>{a}</li>" for a in opp.next_actions)}
          </ol>
        </div>
      </div>
    </div>"""


def _summary_block(opportunities: list[Opportunity], scan_meta: dict) -> str:
    n = len(opportunities)
    up = sum(1 for o in opportunities if o.direction == "up")
    down = sum(1 for o in opportunities if o.direction == "down")
    unclear = n - up - down
    big = sum(1 for o in opportunities if o.potential_median >= 0.15)
    mid = sum(1 for o in opportunities if 0.10 <= o.potential_median < 0.15)

    return f"""
    <div class="summary">
      <div class="sum-head">今日扫描简报</div>
      <div class="sum-grid">
        <div><span class="big">{scan_meta.get('total_symbols', 0)}</span><span>品种扫描</span></div>
        <div><span class="big">{scan_meta.get('structures_found', 0)}</span><span>识别结构</span></div>
        <div><span class="big">{n}</span><span>产出机会</span></div>
        <div><span class="big up">{up}</span><span>看涨</span></div>
        <div><span class="big down">{down}</span><span>看跌</span></div>
        <div><span class="big neutral">{unclear}</span><span>方向不明</span></div>
        <div><span class="big">{big}</span><span>潜力≥15%</span></div>
        <div><span class="big">{mid}</span><span>潜力10~15%</span></div>
      </div>
    </div>"""


def _full_table(opportunities: list[Opportunity]) -> str:
    if not opportunities:
        return '<div class="empty">今日无完整机会清单。</div>'

    rows = []
    for o in opportunities:
        best = o.top_matches[0] if o.top_matches else None
        best_label = (
            f"{best.symbol_name} {best.end_date[:7]}"
            if best else "—"
        )
        rows.append(f"""
        <tr>
          <td><b>{o.attention_score:.0f}</b></td>
          <td><b>{o.symbol_name}</b><br><small style="color:#888">{o.symbol}</small></td>
          <td>{_direction_badge(o.direction, o.direction_confidence)}</td>
          <td><b>{o.potential_median * 100:.1f}%</b>
              <br><small style="color:#888">{o.potential_p25 * 100:.1f}~{o.potential_p75 * 100:.1f}%</small></td>
          <td>{best_label}</td>
          <td>
            <small>形{o.sim_geometry:.2f} 节{o.sim_relation:.2f} 族{o.sim_family:.2f}</small>
          </td>
          <td style="max-width:280px;color:#aaa;font-size:12px">
            {o.next_actions[0] if o.next_actions else ""}
          </td>
        </tr>""")

    return f"""
    <table class="full-table">
      <thead>
        <tr>
          <th>关注度</th><th>品种</th><th>方向</th>
          <th>潜力(中位/区间)</th><th>最像</th>
          <th>相似度拆解</th><th>研究建议</th>
        </tr>
      </thead>
      <tbody>{"".join(rows)}</tbody>
    </table>"""


# ── CSS ────────────────────────────────────────────────────────────────
_CSS = """
body{background:#0f1020;color:#e5e5e5;font-family:-apple-system,"PingFang SC","Microsoft YaHei",monospace;margin:0;padding:24px}
h1{color:#90caf9;margin:0 0 4px 0}
.page-meta{color:#888;font-size:13px;margin-bottom:18px}

.summary{background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:16px 20px;margin-bottom:22px}
.sum-head{color:#90caf9;font-weight:bold;margin-bottom:12px}
.sum-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.sum-grid div{display:flex;flex-direction:column;align-items:flex-start}
.sum-grid .big{font-size:22px;font-weight:bold;color:#fff}
.sum-grid .big.up{color:#26a69a}
.sum-grid .big.down{color:#ef5350}
.sum-grid .big.neutral{color:#9e9e9e}
.sum-grid span:last-child{color:#888;font-size:12px}

.section-title{color:#90caf9;font-size:15px;margin:28px 0 10px 0;border-bottom:1px solid #2a2a4a;padding-bottom:6px}

.opp-card{background:#1a1a2e;border:1px solid #333;border-left:3px solid #90caf9;
  border-radius:8px;padding:14px 18px;margin-bottom:14px}
.card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.card-title{display:flex;align-items:center;gap:10px}
.attention{background:#90caf9;color:#0f1020;padding:3px 10px;border-radius:4px;font-weight:bold;font-size:14px}
.sym-name{font-size:17px;font-weight:bold}
.sym-code{color:#888;font-size:12px}
.card-price{color:#ccc;font-size:13px}

.badge{padding:2px 8px;border-radius:3px;font-size:12px;font-weight:bold}
.badge.up{background:#26a69a33;color:#26a69a}
.badge.down{background:#ef535033;color:#ef5350}
.badge.neutral{background:#9e9e9e33;color:#9e9e9e}

.card-body{display:grid;grid-template-columns:1fr 1.2fr;gap:20px}
.label{color:#888;font-size:12px;margin-bottom:4px}
.window{color:#fff;font-size:14px;margin-bottom:4px}

.potential-bar .bar-outer{height:6px;background:linear-gradient(90deg,#ef5350 0%,#ffb74d 50%,#26a69a 100%);
  border-radius:3px;position:relative;margin:4px 0 6px 0}
.potential-bar .bar-marker{position:absolute;top:-3px;width:2px;height:12px;background:#fff}
.potential-bar .bar-text{font-size:13px}

.sim-box{display:flex;flex-direction:column;gap:4px}
.sim-item{display:grid;grid-template-columns:40px 1fr 36px;align-items:center;gap:8px}
.sim-label{font-size:11px;color:#aaa}
.sim-bar{height:6px;background:#2a2a4a;border-radius:3px;overflow:hidden}
.sim-fill{height:100%;background:#90caf9}
.sim-val{font-size:11px;color:#ccc;text-align:right}

.matches-row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px}
.match-cell{background:#12132a;border:1px solid #2a2a4a;border-radius:4px;padding:6px 8px;font-size:11px}
.match-head{color:#eee;font-size:12px}
.match-date{color:#888;font-size:10px;margin-bottom:4px}
.match-thumb{height:38px;border-radius:3px;display:flex;align-items:center;justify-content:center;
  font-size:12px;margin-bottom:4px}
.match-sim{color:#90caf9;font-size:10px}

.actions{margin:4px 0 0 18px;padding:0;color:#ccc;font-size:12px}
.actions li{margin-bottom:3px}

.full-table{width:100%;border-collapse:collapse;background:#1a1a2e;border:1px solid #333;border-radius:6px;overflow:hidden}
.full-table th{background:#12132a;color:#90caf9;padding:10px 12px;text-align:left;font-size:12px;border-bottom:1px solid #333}
.full-table td{padding:10px 12px;border-bottom:1px solid #2a2a4a;font-size:13px}
.full-table tr:hover td{background:#22223a}

.empty{padding:40px;text-align:center;color:#888;background:#1a1a2e;border-radius:6px}
"""


def render_daily_report(
        opportunities: list[Opportunity],
        scan_meta: dict,
        filename: str = "daily_scan_report.html",
        output_dir: str = "output",
) -> str:
    """
    三段式 HTML 日报渲染入口。
    opportunities 已按 attention_score 倒序排列。
    """
    import os
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = datetime.now().strftime("%Y-%m-%d")

    focus = opportunities[:5]
    focus_html = (
        "".join(_opp_card(o) for o in focus)
        if focus
        else '<div class="empty">今日无高关注度候选。</div>'
    )

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>价格结构扫描日报 — {date_str}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>价格结构扫描日报</h1>
<div class="page-meta">
  扫描时间 {ts} &nbsp;|&nbsp;
  数据截止 {scan_meta.get('data_cutoff', date_str)} &nbsp;|&nbsp;
  模板库 {scan_meta.get('template_count', 0)} 条 &nbsp;|&nbsp;
  配置 <code>{scan_meta.get('config_hash', '—')[:8]}</code>
</div>

{_summary_block(opportunities, scan_meta)}

<div class="section-title">今日重点关注（按关注度排序前 5）</div>
{focus_html}

<div class="section-title">完整机会清单</div>
{_full_table(opportunities)}

</body>
</html>"""

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
