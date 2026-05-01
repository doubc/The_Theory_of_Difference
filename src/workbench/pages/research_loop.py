"""
研究闭环页 — 从结构到决策的完整研究流程

子模块：
  1. 板块 & 产业链定位
  2. 知识图谱增强
  3. 当前结构概览（卡片 + Zone 位置图）
  4. 优先级打分（可视化分项）
  5. 条件转移分布
  6. 多时间维度一致性
  7. 证伪卡片登记
  8. 历史命中率
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import plotly.graph_objects as go

_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════
# 安全转换
# ═══════════════════════════════════════════════════════════

def _f(v, d=0.0):
    try: return float(v) if v is not None else float(d)
    except: return float(d)

def _i(v, d=0):
    try: return int(v) if v is not None else int(d)
    except: return int(d)

def _s(v, d=""):
    try: return str(v) if v is not None else d
    except: return d


# ═══════════════════════════════════════════════════════════
# 板块 & 产业链
# ═══════════════════════════════════════════════════════════

_SECTOR_MAP = {
    "CU": ("有色金属", "🔩"), "AL": ("有色金属", "🔩"), "ZN": ("有色金属", "🔩"),
    "NI": ("有色金属", "🔩"), "PB": ("有色金属", "🔩"), "SN": ("有色金属", "🔩"),
    "AU": ("贵金属", "🥇"), "AG": ("贵金属", "🥇"), "PT": ("贵金属", "🥇"),
    "RB": ("黑色系", "⚫"), "HC": ("黑色系", "⚫"), "I": ("黑色系", "⚫"),
    "J": ("黑色系", "⚫"), "JM": ("黑色系", "⚫"), "SF": ("黑色系", "⚫"),
    "M": ("农产品", "🌾"), "A": ("农产品", "🌾"), "P": ("农产品", "🌾"),
    "RM": ("农产品", "🌾"), "CF": ("农产品", "🌾"), "SR": ("农产品", "🌾"),
    "Y": ("农产品", "🌾"), "OI": ("农产品", "🌾"),
    "TA": ("能化", "⛽"), "MA": ("能化", "⛽"), "BU": ("能化", "⛽"),
    "V": ("能化", "⛽"), "EG": ("能化", "⛽"), "L": ("能化", "⛽"),
    "PP": ("能化", "⛽"), "SC": ("能化", "⛽"), "FU": ("能化", "⛽"),
    "FG": ("建材", "🏗️"), "SA": ("建材", "🏗️"), "UR": ("建材", "🏗️"),
    "LC": ("新能源", "🔋"), "SI": ("新能源", "🔋"),
}

_PEER_MAP = {
    "CU": ["AL", "ZN", "NI", "PB"], "AL": ["CU", "ZN", "NI"],
    "ZN": ["CU", "AL", "NI", "PB"], "NI": ["CU", "AL", "ZN"],
    "RB": ["HC", "I", "JM", "SF"], "I": ["RB", "HC", "J", "JM"],
    "M": ["A", "P", "RM", "Y"], "Y": ["M", "P", "OI"],
    "TA": ["MA", "EG"], "MA": ["TA", "EG", "PP"],
    "AU": ["AG", "PT"], "AG": ["AU", "PT"],
    "FG": ["SA"], "SA": ["FG"], "LC": ["SI"], "SI": ["LC"],
}


def _get_sector(symbol: str) -> tuple:
    """返回 (板块名, emoji)"""
    # 先从知识图谱查
    try:
        from src.workbench.kg_helper import get_sector_from_kg
        kg = get_sector_from_kg(symbol)
        sec = kg.get("sector", "未知")
        if sec != "未知":
            return (sec, "📊")
    except:
        pass
    code = symbol.upper().rstrip("0123456789")
    return _SECTOR_MAP.get(code, ("未知", "❓"))


def _get_peers(symbol: str) -> List[str]:
    try:
        from src.workbench.kg_helper import get_chain_peers_from_kg
        peers = get_chain_peers_from_kg(symbol)
        if peers:
            return peers
    except:
        pass
    code = symbol.upper().rstrip("0123456789")
    return _PEER_MAP.get(code, [])


# ═══════════════════════════════════════════════════════════
# 数据标准化
# ═══════════════════════════════════════════════════════════

def _normalize(symbol: str, cs: Optional[Dict]) -> Dict:
    base = {
        "symbol": symbol, "has_data": False,
        "phase": "unknown", "activity": 0, "quality": 0, "quality_tier": "D",
        "position_tag": "unknown", "test_count": 0, "duration_days": 0,
        "time_since_last_test": 0, "flux": 0.0, "current_price": 0.0,
        "zone_center": 0.0, "zone_half_width": 0.0, "movement_type": "unknown",
        "test_amplitudes": [],
    }
    if not isinstance(cs, dict):
        return base
    m = {**base, **cs}
    m["symbol"] = _s(m.get("symbol") or symbol, symbol)
    m["zone_center"] = _f(m.get("zone_center", m.get("center", 0)))
    m["zone_half_width"] = _f(m.get("zone_half_width", m.get("half_width", 0)))
    m["test_count"] = _i(m.get("test_count", m.get("tests", 0)))
    m["quality"] = _i(m.get("quality", m.get("quality_score", m.get("score", 0))))
    m["quality_tier"] = _s(m.get("quality_tier", m.get("tier", "D")), "D")
    m["activity"] = _i(m.get("activity", m.get("deviation_activity", 0)))
    m["flux"] = _f(m.get("flux", 0))
    m["current_price"] = _f(m.get("current_price", 0))
    m["phase"] = _s(m.get("phase", "unknown"), "unknown")
    m["movement_type"] = _s(m.get("movement_type", "unknown"), "unknown")
    m["position_tag"] = _s(m.get("position_tag", "unknown"), "unknown")
    m["duration_days"] = _i(m.get("duration_days", 0))
    m["time_since_last_test"] = _i(m.get("time_since_last_test", 0))
    amps = m.get("test_amplitudes", [])
    m["test_amplitudes"] = amps if isinstance(amps, list) else []
    return m


# ═══════════════════════════════════════════════════════════
# 优先级计算
# ═══════════════════════════════════════════════════════════

def _compute_priority(cs: Dict) -> Dict:
    """返回 {"total": int, "breakdown": {维度: 分数}}"""
    phase = cs.get("phase", "unknown")
    activity = _i(cs.get("activity", 0))
    quality = _i(cs.get("quality", 0))
    test_count = _i(cs.get("test_count", 0))
    pos = cs.get("position_tag", "unknown")
    recency = _i(cs.get("time_since_last_test", 0))
    amps = cs.get("test_amplitudes", [])

    # 振幅收敛
    if amps and len(amps) >= 2:
        try:
            convergence = max(0, min(1, 1 - abs(float(amps[-1])) / max(abs(float(amps[0])), 1e-9)))
        except:
            convergence = 0
    else:
        convergence = 0

    phase_map = {
        "breakout": 20, "→breakout": 20, "->breakout": 20,
        "confirmation": 16, "→confirmation": 16, "->confirmation": 16,
        "inversion": 12, "→inversion": 12,
        "forming": 10, "formation": 10,
        "stable": 8, "unknown": 0,
    }
    bd = {
        "阶段": min(20, phase_map.get(phase, 8)),
        "活跃度": min(25, int(activity * 0.3)),
        "质量": min(20, int(quality * 0.25)),
        "试探次数": min(15, test_count * 3),
        "振幅收敛": int(convergence * 10),
        "位置": 10 if pos in ("above", "below", "far_above", "far_below") else 6 if pos == "inside" else 3,
        "新鲜度": max(0, 10 - min(recency, 10)),
    }
    return {"total": min(100, sum(bd.values())), "breakdown": bd, "convergence": convergence}


# ═══════════════════════════════════════════════════════════
# 渲染子模块
# ═══════════════════════════════════════════════════════════

def _render_sector_bar(symbol: str, cs: Dict):
    """板块定位 + 产业链 + 同链品种"""
    sector, emoji = _get_sector(symbol)
    peers = _get_peers(symbol)

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
                border-radius:12px;padding:16px 24px;margin-bottom:16px;
                border-left:4px solid #64ffda">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
                <span style="font-size:1.4em;font-weight:700;color:#ccd6f6">{symbol}</span>
                <span style="font-size:1.1em;color:#8892b0;margin-left:12px">{emoji} {sector}</span>
            </div>
            <div style="text-align:right">
                <span style="font-size:0.85em;color:#64ffda">研究闭环</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if peers:
        peer_chips = " ".join(
            f'<span style="background:#112240;color:#8892b0;padding:3px 10px;'
            f'border-radius:12px;font-size:0.82em;margin-right:4px;border:1px solid #233554">{p}</span>'
            for p in peers
        )
        st.markdown(f"**同链共振** {peer_chips}", unsafe_allow_html=True)


def _render_kg_section(symbol: str):
    """知识图谱：核心关系 + 传导链 + 跨品种影响"""
    try:
        from src.workbench.kg_helper import get_key_relations, get_key_chains, get_cross_variety_impacts
    except:
        return

    rels = get_key_relations(symbol, limit=5)
    chains = get_key_chains(symbol, limit=3)
    impacts = get_cross_variety_impacts(symbol)

    if not rels and not chains and not impacts:
        return

    with st.expander("📚 知识图谱增强", expanded=False):
        t1, t2, t3 = st.tabs(["🔗 核心关系", "⛓️ 传导链", "🌐 跨品种影响"])

        with t1:
            if rels:
                for r in rels:
                    fr = r.get("from", "")
                    to = r.get("to", "")
                    tp = r.get("type", "")
                    strength = _f(r.get("strength", 0))
                    desc = r.get("description", "")[:80]
                    bar_w = int(strength * 100)
                    color = "#4caf50" if strength >= 0.7 else "#ff9800" if strength >= 0.5 else "#999"
                    st.markdown(f"""
                    <div style="display:flex;align-items:center;gap:8px;margin:6px 0">
                        <span style="font-weight:600;color:#ccd6f6;min-width:60px">{fr}</span>
                        <span style="color:#64ffda">→</span>
                        <span style="font-weight:600;color:#ccd6f6;min-width:60px">{to}</span>
                        <span style="color:#8892b0;font-size:0.85em">{tp}</span>
                        <div style="flex:1;background:#233554;border-radius:4px;height:8px;margin:0 8px">
                            <div style="width:{bar_w}%;background:{color};height:100%;border-radius:4px"></div>
                        </div>
                        <span style="color:{color};font-weight:600;font-size:0.85em">{strength:.0%}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if desc:
                        st.caption(f"  {desc}")
            else:
                st.caption("暂无核心关系数据")

        with t2:
            if chains:
                for c in chains:
                    name = c.get("name", "")
                    trigger = c.get("triggerEvent", "")
                    steps = c.get("steps", [])
                    st.markdown(f"**{name}**")
                    if trigger:
                        st.caption(f"触发事件: {trigger}")
                    for step in steps[:5]:
                        seq = step.get("seq", "")
                        fr = step.get("from", "")
                        to = step.get("to", "")
                        st.markdown(f"  <span style='color:#64ffda'>{seq}.</span> {fr} → {to}", unsafe_allow_html=True)
            else:
                st.caption("暂无传导链数据")

        with t3:
            if impacts:
                for r in impacts[:5]:
                    fr = r.get("from", "")
                    to = r.get("to", "")
                    tp = r.get("type", "")
                    st.markdown(f"**{fr}** → **{to}** · {tp}")
            else:
                st.caption("暂无跨品种影响数据")


def _render_structure_card(cs: Dict):
    """当前结构概览 — 卡片 + Zone 位置可视化"""
    st.markdown("#### 📊 当前结构概览")

    # 状态色彩
    phase = cs.get("phase", "unknown")
    mt = cs.get("movement_type", "unknown")
    tier = cs.get("quality_tier", "D")

    phase_label = {
        "breakout": "🔴 突破中", "→breakout": "🔴 突破中",
        "confirmation": "🟢 确认中", "→confirmation": "🟢 确认中",
        "stable": "🔵 稳态运行", "forming": "🟡 形成中",
        "inversion": "🟠 反演中", "unknown": "⚪ 未知",
    }.get(phase, phase)

    mt_label = {
        "trend_up": "📈 上涨趋势", "trend_down": "📉 下跌趋势",
        "oscillation": "🔄 震荡", "reversal": "🔀 反转", "unknown": "—",
    }.get(mt, mt)

    tier_colors = {"A": "#1b5e20", "B": "#0d47a1", "C": "#e65100", "D": "#b71c1c"}
    tier_bg = {"A": "#e8f5e9", "B": "#e3f2fd", "C": "#fff3e0", "D": "#ffebee"}

    flux = _f(cs.get("flux", 0))
    flux_arrow = "↑" if flux > 0 else "↓" if flux < 0 else "→"
    flux_color = "#ef5350" if flux > 0 else "#26a69a" if flux < 0 else "#ffc107"

    # 指标卡片行
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("运动阶段", phase_label)
    c2.metric("运动类型", mt_label)
    c3.metric("质量层", f"{tier} 层")
    c4.metric("通量", f"{flux:+.3f} {flux_arrow}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("当前价格", f"{_f(cs.get('current_price', 0)):.1f}")
    c6.metric("Zone 中心", f"{_f(cs.get('zone_center', 0)):.1f}")
    c7.metric("试探次数", str(_i(cs.get("test_count", 0))))
    c8.metric("活跃度", str(_i(cs.get("activity", 0))))

    # Zone 位置可视化
    zc = _f(cs.get("zone_center", 0))
    zw = _f(cs.get("zone_half_width", 0))
    cp = _f(cs.get("current_price", 0))

    if zc > 0 and zw > 0 and cp > 0:
        upper = zc + zw
        lower = zc - zw
        fig = go.Figure()

        # Zone 区域
        fig.add_hrect(y0=lower, y1=upper, fillcolor="#4a90d9", opacity=0.15, line_width=0)
        fig.add_hline(y=zc, line_dash="dot", line_color="#4a90d9", opacity=0.6,
                      annotation_text=f"Zone {zc:.0f}", annotation_position="top left")

        # Zone 边界
        fig.add_hline(y=upper, line_dash="dash", line_color="#8892b0", opacity=0.3)
        fig.add_hline(y=lower, line_dash="dash", line_color="#8892b0", opacity=0.3)

        # 当前价格
        price_color = "#ef5350" if cp > upper else "#26a69a" if cp < lower else "#ffc107"
        fig.add_hline(y=cp, line_color=price_color, line_width=2,
                      annotation_text=f"现价 {cp:.0f}", annotation_position="top right")

        fig.update_layout(
            height=200, template="plotly_dark",
            margin=dict(l=60, r=60, t=30, b=10),
            yaxis_title="价格", xaxis_visible=False,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # 位置文字描述
        if lower <= cp <= upper:
            pct = (cp - zc) / zw * 100
            st.info(f"📍 价格在 Zone 内部，偏{'上' if pct > 0 else '下'} {abs(pct):.0f}%")
        elif cp > upper:
            pct = (cp - zc) / zc * 100
            st.warning(f"📍 价格在 Zone 上方 +{pct:.1f}%，可能正在突破")
        else:
            pct = (zc - cp) / zc * 100
            st.warning(f"📍 价格在 Zone 下方 -{pct:.1f}%，可能正在破位")


def _render_priority(cs: Dict):
    """优先级打分 — 分项条形图"""
    st.markdown("#### 🎯 优先级打分")

    pri = _compute_priority(cs)
    total = pri["total"]
    bd = pri["breakdown"]
    convergence = pri["convergence"]

    # 总分
    color = "#4caf50" if total >= 70 else "#ff9800" if total >= 40 else "#ef5350"
    st.markdown(f"""
    <div style="text-align:center;padding:12px;margin-bottom:12px">
        <span style="font-size:3em;font-weight:800;color:{color}">P{total}</span>
        <span style="font-size:1em;color:#8892b0;margin-left:12px">振幅收敛 {convergence:.2f}</span>
    </div>
    """, unsafe_allow_html=True)

    # 分项条形图
    labels = list(bd.keys())
    values = list(bd.values())
    max_vals = [20, 25, 20, 15, 10, 10, 10]
    colors = ["#4caf50" if v / mx >= 0.7 else "#ff9800" if v / mx >= 0.4 else "#ef5350"
              for v, mx in zip(values, max_vals)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=values, orientation="h",
        marker_color=colors,
        text=[f"{v}/{mx}" for v, mx in zip(values, max_vals)],
        textposition="auto",
    ))
    fig.update_layout(
        height=250, template="plotly_dark",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="分数", xaxis_range=[0, 25],
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_transition(cs: Dict, history_transitions: List):
    """条件转移分布"""
    st.markdown("#### 🔄 条件转移分布")

    if not history_transitions:
        st.info("暂无历史转移样本。需要先运行历史扫描或转移提取脚本。")
        st.caption("接口已保留，后续接入 history_transitions 后会自动显示结果。")
        return

    st.caption(f"匹配样本: {len(history_transitions)} 条")
    st.json(history_transitions[:3])


def _render_mtf(mtf_snapshots: Dict):
    """多时间维度一致性"""
    st.markdown("#### ⏱️ 多时间维度一致性")

    required = {"5m", "1h", "D"}
    current = set(mtf_snapshots.keys())

    if not mtf_snapshots or not required.issubset(current):
        missing = required - current
        st.info(f"需要提供 5m / 1h / D 三个尺度的快照。当前缺少: {', '.join(missing) if missing else '无'}")
        st.caption("从主工作台 Tab 进入时会自动传入。独立打开时需手动提供。")
        return

    # 有真实数据时计算 MCI
    try:
        from src.multitimeframe.consistency import compute_mci
        report = compute_mci(mtf_snapshots)
        mci = _f(getattr(report, "mci", 0))
        verdict = _s(getattr(report, "verdict", ""))
        details = _s(getattr(report, "details", ""))

        color = "#4caf50" if mci >= 0.7 else "#ff9800" if mci >= 0.4 else "#ef5350"
        st.markdown(f"""
        <div style="text-align:center;padding:12px">
            <span style="font-size:2.5em;font-weight:800;color:{color}">{mci:.2f}</span>
            <span style="font-size:1.1em;color:#8892b0;margin-left:12px">{verdict}</span>
        </div>
        """, unsafe_allow_html=True)
        if details:
            st.caption(details)
    except:
        st.caption("compute_mci 不可用")


def _render_falsification(symbol: str, cs: Dict):
    """证伪卡片登记"""
    st.markdown("#### 🔬 证伪研究卡片")

    st.caption("记录一个可验证的预测，到期后回填结果，追踪命中率。")

    col1, col2 = st.columns(2)
    with col1:
        holding = st.slider("评估窗口（交易日）", 3, 30, 10, key="rl_holding")
    with col2:
        prediction = st.selectbox("预测方向", ["看涨", "看跌", "中性"], key="rl_pred")

    note = st.text_area("研究笔记", placeholder="记录你的判断依据...", key="rl_note",
                       height=80, label_visibility="collapsed")

    if st.button("📝 登记卡片", type="primary", use_container_width=True):
        card = {
            "card_id": f"{symbol}-{cs.get('phase', 'x')}-{holding}",
            "symbol": symbol,
            "zone_center": _f(cs.get("zone_center")),
            "current_price": _f(cs.get("current_price")),
            "phase": cs.get("phase", ""),
            "quality_tier": cs.get("quality_tier", "D"),
            "prediction": prediction,
            "holding_days": holding,
            "note": note,
            "status": "open",
        }

        # 写入 ledger
        try:
            log_dir = _PROJECT_ROOT / "data" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            path = log_dir / "falsification_cards.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(card, ensure_ascii=False) + "\n")
            st.success(f"✅ 已登记 · ID: {card['card_id']} · {holding}个交易日后回填")
        except Exception as e:
            st.error(f"写入失败: {e}")

    # 历史命中率
    try:
        path = _PROJECT_ROOT / "data" / "logs" / "falsification_cards.jsonl"
        if path.exists():
            cards = [json.loads(l) for l in path.read_text().strip().split("\n") if l.strip()]
            closed = [c for c in cards if c.get("status") == "closed"]
            if closed:
                hits = sum(1 for c in closed if c.get("hit"))
                rate = hits / len(closed) * 100
                st.metric("历史命中率", f"{rate:.0f}% ({hits}/{len(closed)})")
    except:
        pass


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def render(
    symbol: str = "CU0",
    current_structure: Optional[Dict] = None,
    mtf_snapshots: Optional[Dict] = None,
    history_transitions: Optional[List] = None,
):
    symbol = _s(symbol, "CU0").upper()
    cs = _normalize(symbol, current_structure)
    mtf = mtf_snapshots or {}
    transitions = history_transitions or []

    # 1. 板块定位
    _render_sector_bar(symbol, cs)

    # 2. 知识图谱
    _render_kg_section(symbol)

    # 3. 结构概览
    _render_structure_card(cs)

    # 4. 优先级
    _render_priority(cs)

    # 5-6. 转移 & MTF（双列）
    col_left, col_right = st.columns(2)
    with col_left:
        _render_transition(cs, transitions)
    with col_right:
        _render_mtf(mtf)

    # 7. 证伪卡片
    _render_falsification(symbol, cs)
