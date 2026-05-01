"""
共享工具函数 & 常量

提取自 app.py，供各 Tab 页面复用：
  - CSS 样式常量
  - TIER_COLORS / SENS_MAP 字典
  - motion_badge, _extract_key, _price_vs_zone
  - make_candlestick, make_comparison_chart
  - _invariant_diff_table
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.retrieval.similarity import INVARIANT_KEYS, INVARIANT_SCALES


# ═══════════════════════════════════════════════════════════
# CSS 样式常量
# ═══════════════════════════════════════════════════════════

CSS_STYLE = """
<style>
    /* 运动标签 */
    .motion-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .badge-breakout { background: rgba(239,83,80,0.15); color: #ff6b6b; }
    .badge-confirmation { background: rgba(38,166,154,0.15); color: #4ecdc4; }
    .badge-stable { background: rgba(255,167,38,0.15); color: #ffb74d; }
    .badge-forming { background: rgba(66,165,245,0.15); color: #64b5f6; }

    /* 结构卡片 — 浅色背景 + 深色文字，确保可读性 */
    .structure-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 10px;
        padding: 14px 18px;
        margin: 8px 0;
        border-left: 5px solid #4a90d9;
        color: #212529;
        font-size: 0.92em;
        line-height: 1.6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .structure-card b { color: #1a1a2e; }
    .structure-card .zone-label { font-size: 1.05em; font-weight: 700; color: #0d1b2a; }
    .structure-card .meta-text { color: #495057; font-size: 0.88em; }
    .structure-card .narrative-text { color: #6c757d; font-size: 0.85em; margin-top: 4px; }
    .structure-card.warning { border-left-color: #ff9800; }
    /* A股惯例：红涨绿跌 — danger=看多(红), ok=看空(绿) */
    .structure-card.danger  { border-left-color: #ef5350; background: linear-gradient(135deg, #fff5f5 0%, #ffe0e0 100%); }
    .structure-card.ok      { border-left-color: #26a69a; background: linear-gradient(135deg, #f0faf8 0%, #d4efea 100%); }

    /* 复盘日志条目 */
    .journal-entry {
        background: #ffffff;
        border-radius: 8px;
        padding: 14px 18px;
        margin: 8px 0;
        border: 1px solid #dee2e6;
        color: #212529;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .journal-entry .entry-header {
        font-weight: 700;
        color: #0d1b2a;
        font-size: 0.95em;
        margin-bottom: 6px;
        border-bottom: 1px solid #e9ecef;
        padding-bottom: 6px;
    }
    .journal-entry .entry-body {
        color: #343a40;
        font-size: 0.9em;
        line-height: 1.7;
        white-space: pre-wrap;
    }
    .journal-tag {
        display: inline-block;
        padding: 1px 8px;
        border-radius: 3px;
        font-size: 0.8em;
        margin-right: 4px;
    }
    /* A股惯例：红涨绿跌 */
    .tag-bullish { background: #f8d7da; color: #721c24; }
    .tag-bearish { background: #d4edda; color: #155724; }
    .tag-neutral { background: #fff3cd; color: #856404; }
</style>
"""


# ═══════════════════════════════════════════════════════════
# 常量字典
# ═══════════════════════════════════════════════════════════

TIER_COLORS = {
    "A": ("#1b5e20", "#c8e6c9"),
    "B": ("#0d47a1", "#bbdefb"),
    "C": ("#e65100", "#ffe0b2"),
    "D": ("#b71c1c", "#ffcdd2"),
}

SENS_MAP = {
    "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3},
    "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2},
    "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2},
}


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def motion_badge(tendency: str) -> str:
    cls = "badge-forming"
    if "breakout" in tendency:
        cls = "badge-breakout"
    elif "confirmation" in tendency:
        cls = "badge-confirmation"
    elif tendency == "stable":
        cls = "badge-stable"
    return f'<span class="motion-badge {cls}">{tendency}</span>'


def movement_badge(movement_type: str) -> str:
    """运动类型标签：A股习惯 — 红涨绿跌"""
    mapping = {
        "trend_up": ("📈 上涨趋势", "#ef5350"),
        "trend_down": ("📉 下跌趋势", "#4caf50"),
        "oscillation": ("🔄 震荡", "#ffc107"),
        "reversal": ("🔀 反转", "#ff9800"),
    }
    label, color = mapping.get(movement_type, (movement_type, "#999"))
    return f'<span style="color:{color};font-weight:600">{label}</span>'


def struct_status(s) -> str:
    """从 Structure 对象生成状态描述（运动类型 + 阶段 + 通量）"""
    parts = []
    m = s.motion
    if m:
        mt = m.movement_type.value if hasattr(m, 'movement_type') else ""
        mt_cn = {"trend_up": "上涨趋势", "trend_down": "下跌趋势",
                 "oscillation": "震荡", "reversal": "反转"}.get(mt, "")
        if mt_cn:
            parts.append(mt_cn)
        phase_cn = {"→breakout": "正在突破", "→confirmation": "确认中",
                    "→inversion": "趋向反演", "stable": "运行稳定",
                    "forming": "形成中"}.get(m.phase_tendency, "")
        if phase_cn and phase_cn != mt_cn:
            parts.append(phase_cn)
        flux = m.conservation_flux
        if abs(flux) > 0.3:
            parts.append("差异释放中" if flux > 0 else "差异压缩中")
    if s.projection and s.projection.is_blind:
        parts.append("⚠️高压缩")
    return " · ".join(parts)


def struct_scenario(s) -> str:
    """从 Structure 对象生成候选剧本"""
    m = s.motion
    if not m:
        return ""
    mt = m.movement_type.value if hasattr(m, 'movement_type') else ""
    flux = m.conservation_flux
    cycles = s.cycle_count
    zc = s.zone.price_center
    zb = s.zone.bandwidth

    if mt == "trend_up":
        return "📈 上涨趋势延续中 — 关注能否站稳 Zone 上沿发起突破"
    elif mt == "trend_down":
        return "📉 下跌趋势延续中 — 关注能否守住 Zone 下沿"
    elif mt == "reversal":
        return "🔀 反转刚发生 — 回踩不破反转点是好信号"
    elif mt == "oscillation":
        if cycles >= 5:
            return f"🔄 已 {cycles} 次密集试探 — 关注方向选择"
        elif flux < -0.3:
            return "🔄 差异压缩中 — 可能是突破前的蓄力"
        else:
            return "🔄 Zone 内正常震荡 — 高抛低吸区间"
    if "breakout" in m.phase_tendency:
        return "⚡ 突破阶段 — 观察是否站稳 Zone 外侧"
    if "confirmation" in m.phase_tendency:
        return "✅ 确认阶段 — 关注通量方向"
    return ""


def struct_invalidation(s) -> str:
    """从 Structure 对象生成失效条件"""
    m = s.motion
    if not m:
        return ""
    mt = m.movement_type.value if hasattr(m, 'movement_type') else ""
    zc = s.zone.price_center
    zb = s.zone.bandwidth
    zone_upper = zc + zb
    zone_lower = zc - zb

    if mt == "trend_up":
        return f"❌ 失效：价格跌回 {zone_lower:.0f} 以下 → 趋势中断"
    elif mt == "trend_down":
        return f"❌ 失效：价格涨回 {zone_upper:.0f} 以上 → 趋势中断"
    elif mt == "reversal":
        return f"❌ 失效：价格回到 {zc:.0f}±{zb:.0f} 内 → 反转失败"
    elif mt == "oscillation":
        return f"❌ 转向：突破 {zone_upper:.0f} 或 {zone_lower:.0f} → 震荡结束"
    return ""


def _extract_key(label: str) -> str:
    """从中文标签中提取英文 key，如 '📈 上涨(up)' → 'up'"""
    if "(" in label and ")" in label:
        return label[label.index("(") + 1 : label.index(")")]
    return label


def _price_vs_zone(last_price: float, zone_center: float, zone_bw: float) -> str:
    """当前价格相对于 Zone 的位置描述"""
    if zone_bw <= 0:
        return ""
    upper = zone_center + zone_bw
    lower = zone_center - zone_bw
    if lower <= last_price <= upper:
        dist_pct = (last_price - zone_center) / zone_bw * 100
        return f"📍 价格在 Zone 内（偏{'上' if dist_pct > 0 else '下'}{abs(dist_pct):.0f}%）"
    elif last_price > upper:
        pct = (last_price - zone_center) / zone_center * 100
        return f"📍 价格在 Zone 上方 +{pct:.1f}%"
    else:
        pct = (zone_center - last_price) / zone_center * 100
        return f"📍 价格在 Zone 下方 -{pct:.1f}%"


def make_candlestick(bars_list, title="", height=350):
    df = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume,
    } for b in bars_list])
    fig = go.Figure(data=[go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
    )])
    fig.update_layout(
        height=height, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=30, b=0),
        title=title,
    )
    return fig


def make_comparison_chart(bars_a, bars_b, name_a, name_b, zones_a=None, zones_b=None):
    """并排 K 线对比图"""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=False,
        subplot_titles=[f"{name_a}", f"{name_b}"],
        vertical_spacing=0.08,
    )

    # 上方：品种 A
    df_a = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close,
    } for b in bars_a])
    fig.add_trace(go.Candlestick(
        x=df_a["date"], open=df_a["open"], high=df_a["high"],
        low=df_a["low"], close=df_a["close"],
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
        name=name_a,
    ), row=1, col=1)

    # 下方：品种 B
    df_b = pd.DataFrame([{
        "date": b.timestamp, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close,
    } for b in bars_b])
    fig.add_trace(go.Candlestick(
        x=df_b["date"], open=df_b["open"], high=df_b["high"],
        low=df_b["low"], close=df_b["close"],
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
        name=name_b,
    ), row=2, col=1)

    # Zone 标注
    if zones_a:
        for z in zones_a:
            fig.add_hline(y=z, line_dash="dot", line_color="#4a90d9",
                         opacity=0.5, row=1, col=1)
    if zones_b:
        for z in zones_b:
            fig.add_hline(y=z, line_dash="dot", line_color="#ff9800",
                         opacity=0.5, row=2, col=1)

    fig.update_layout(
        height=600, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False,
    )
    return fig


def _invariant_diff_table(inv1: dict, inv2: dict, name1: str, name2: str) -> pd.DataFrame:
    """生成两段结构的不变量对比表"""
    rows = []
    for k in INVARIANT_KEYS:
        v1 = inv1.get(k, 0) or 0
        v2 = inv2.get(k, 0) or 0
        scale = INVARIANT_SCALES.get(k, 1.0)
        diff = abs(v1 - v2) / scale if scale > 0 else 0
        rows.append({
            "指标": k,
            name1: round(v1, 4),
            name2: round(v2, 4),
            "归一化差异": round(diff, 3),
            "匹配度": "✅" if diff < 0.3 else "⚠️" if diff < 0.6 else "❌",
        })
    return pd.DataFrame(rows)
