"""
Research Loop Page

This file can work in two modes:

1. Imported by app.py:
   render(symbol, current_structure, mtf_snapshots, history_transitions)

2. Opened directly as a Streamlit page:
   streamlit runs this file and calls _run_standalone_page()
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# ============================================================================
# Path setup
# ============================================================================

_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[3]

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ============================================================================
# Optional real business modules
# ============================================================================

try:
    from src.sector.mapping import get_sector as real_get_sector
except Exception:
    real_get_sector = None

try:
    from src.sector.mapping import get_chain_peers as real_get_chain_peers
except Exception:
    real_get_chain_peers = None

try:
    from src.scoring.priority import compute_priority as real_compute_priority
except Exception:
    real_compute_priority = None

try:
    from src.scoring.priority import compute_amplitude_convergence as real_compute_amplitude_convergence
except Exception:
    real_compute_amplitude_convergence = None

try:
    from src.retrieval.transition import build_transition_distribution as real_build_transition_distribution
except Exception:
    real_build_transition_distribution = None

try:
    from src.retrieval.transition import format_transition_report as real_format_transition_report
except Exception:
    real_format_transition_report = None

try:
    from src.multitimeframe.consistency import compute_mci as real_compute_mci
except Exception:
    real_compute_mci = None

try:
    from src.validation.falsification_card import create_card as real_create_card
except Exception:
    real_create_card = None

try:
    from src.validation.falsification_card import append_to_ledger as real_append_to_ledger
except Exception:
    real_append_to_ledger = None

try:
    from src.validation.falsification_card import compute_hit_rate as real_compute_hit_rate
except Exception:
    real_compute_hit_rate = None


# ============================================================================
# Data classes
# ============================================================================

@dataclass
class SectorInfo:
    sector: str = "未知"
    sub_sector: str = "未知"
    chain_role: str = "未知"


@dataclass
class PriorityResult:
    total: int
    breakdown: Dict[str, Any]


@dataclass
class MCIReport:
    mci: float
    verdict: str
    details: str


# ============================================================================
# Safe converters
# ============================================================================

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except Exception:
        return int(default)


def safe_str(value: Any, default: str = "") -> str:
    try:
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


def to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None

    if isinstance(obj, dict):
        return obj

    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]

    try:
        return asdict(obj)
    except Exception:
        pass

    try:
        return obj.__dict__
    except Exception:
        return str(obj)


# ============================================================================
# Current structure normalization
# ============================================================================

def default_current_structure(symbol: str = "CU0") -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "has_data": False,

        "phase": "unknown",
        "activity": 0,
        "quality": 0,
        "quality_tier": "D",
        "position_tag": "unknown",

        "test_count": 0,
        "duration_days": 0,
        "time_since_last_test": 0,
        "test_amplitudes": [],

        "flux": 0.0,
        "current_price": 0.0,
        "zone_center": 0.0,
        "zone_half_width": 0.0,

        "movement_type": "unknown",

        "deviation_activity": 0,
        "quality_score": 0,
        "center": 0.0,
        "half_width": 0.0,
        "tests": 0,
        "tier": "D",
        "score": 0,
    }


def normalize_current_structure(
        symbol: str,
        current_structure: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    base = default_current_structure(symbol)

    if not isinstance(current_structure, dict):
        return base

    merged = dict(base)
    merged.update(current_structure)

    merged["symbol"] = safe_str(merged.get("symbol") or symbol, symbol)

    merged["zone_center"] = safe_float(
        merged.get("zone_center", merged.get("center", 0.0)),
        0.0,
    )
    merged["center"] = merged["zone_center"]

    merged["zone_half_width"] = safe_float(
        merged.get("zone_half_width", merged.get("half_width", 0.0)),
        0.0,
    )
    merged["half_width"] = merged["zone_half_width"]

    merged["test_count"] = safe_int(
        merged.get("test_count", merged.get("tests", 0)),
        0,
    )
    merged["tests"] = merged["test_count"]

    merged["quality"] = safe_int(
        merged.get("quality", merged.get("quality_score", merged.get("score", 0))),
        0,
    )
    merged["quality_score"] = merged["quality"]
    merged["score"] = merged["quality"]

    merged["quality_tier"] = safe_str(
        merged.get("quality_tier", merged.get("tier", "D")),
        "D",
    )
    merged["tier"] = merged["quality_tier"]

    merged["activity"] = safe_int(
        merged.get("activity", merged.get("deviation_activity", 0)),
        0,
    )
    merged["deviation_activity"] = merged["activity"]

    merged["phase"] = safe_str(merged.get("phase", "unknown"), "unknown")
    merged["position_tag"] = safe_str(merged.get("position_tag", "unknown"), "unknown")
    merged["duration_days"] = safe_int(merged.get("duration_days", 0), 0)
    merged["time_since_last_test"] = safe_int(merged.get("time_since_last_test", 0), 0)
    merged["flux"] = safe_float(merged.get("flux", 0.0), 0.0)
    merged["current_price"] = safe_float(merged.get("current_price", 0.0), 0.0)
    merged["movement_type"] = safe_str(merged.get("movement_type", "unknown"), "unknown")

    test_amplitudes = merged.get("test_amplitudes", [])
    if not isinstance(test_amplitudes, list):
        test_amplitudes = []
    merged["test_amplitudes"] = test_amplitudes

    return merged


# ============================================================================
# Sector helpers
# ============================================================================

def get_sector_safe(symbol: str) -> SectorInfo:
    if real_get_sector is not None:
        try:
            info = real_get_sector(symbol)
            return SectorInfo(
                sector=safe_str(getattr(info, "sector", "未知"), "未知"),
                sub_sector=safe_str(getattr(info, "sub_sector", "未知"), "未知"),
                chain_role=safe_str(getattr(info, "chain_role", "未知"), "未知"),
            )
        except Exception:
            pass

    s = symbol.upper()

    if s in {"CU0", "AL0", "ZN0", "NI0", "PB0", "SN0"}:
        return SectorInfo("有色金属", "基础金属", "midstream")

    if s in {"AU0", "AG0"}:
        return SectorInfo("贵金属", "贵金属", "asset")

    if s in {"RB0", "HC0", "I0", "JM0", "J0"}:
        return SectorInfo("黑色金属", "钢矿煤焦", "midstream")

    if s in {"M0", "A0", "P0", "RM0", "CF0", "SR0"}:
        return SectorInfo("农产品", "农产品", "upstream")

    if s in {"TA0", "MA0", "BU0", "V0", "EG0", "L0", "PP0"}:
        return SectorInfo("能源化工", "化工", "midstream")

    return SectorInfo()


def get_chain_peers_safe(symbol: str) -> List[str]:
    if real_get_chain_peers is not None:
        try:
            peers = real_get_chain_peers(symbol)
            if isinstance(peers, list):
                return peers
        except Exception:
            pass

    peer_map = {
        "CU0": ["AL0", "ZN0", "NI0"],
        "AL0": ["CU0", "ZN0", "NI0"],
        "ZN0": ["CU0", "AL0", "NI0"],
        "NI0": ["CU0", "AL0", "ZN0"],
        "RB0": ["HC0", "I0", "JM0"],
        "HC0": ["RB0", "I0", "JM0"],
        "M0": ["A0", "P0", "RM0"],
        "TA0": ["MA0", "EG0", "PF0"],
        "AU0": ["AG0"],
        "AG0": ["AU0"],
    }

    return peer_map.get(symbol.upper(), [])


# ============================================================================
# Priority helpers
# ============================================================================

def compute_amplitude_convergence_safe(test_amplitudes: List[float]) -> float:
    if real_compute_amplitude_convergence is not None:
        try:
            return safe_float(real_compute_amplitude_convergence(test_amplitudes), 0.0)
        except Exception:
            pass

    if not test_amplitudes or len(test_amplitudes) < 2:
        return 0.0

    try:
        first = abs(float(test_amplitudes[0]))
        last = abs(float(test_amplitudes[-1]))
        if first <= 0:
            return 0.0
        value = 1.0 - last / first
        return max(0.0, min(1.0, value))
    except Exception:
        return 0.0


def compute_priority_safe(
        current_structure: Dict[str, Any],
        amplitude_convergence: float,
) -> PriorityResult:
    if real_compute_priority is not None:
        try:
            score = real_compute_priority(
                phase=current_structure["phase"],
                activity=current_structure["activity"],
                quality=current_structure["quality"],
                position_tag=current_structure["position_tag"],
                test_count=current_structure["test_count"],
                duration_days=current_structure["duration_days"],
                amplitude_convergence=amplitude_convergence,
                time_since_last_test=current_structure["time_since_last_test"],
            )

            total = safe_int(getattr(score, "total", 0), 0)
            breakdown = getattr(score, "breakdown", {})

            if not isinstance(breakdown, dict):
                breakdown = {"detail": str(breakdown)}

            return PriorityResult(total=total, breakdown=breakdown)
        except Exception:
            pass

    phase = current_structure.get("phase", "unknown")
    activity = safe_int(current_structure.get("activity", 0), 0)
    quality = safe_int(current_structure.get("quality", 0), 0)
    test_count = safe_int(current_structure.get("test_count", 0), 0)
    position_tag = current_structure.get("position_tag", "unknown")
    time_since_last_test = safe_int(current_structure.get("time_since_last_test", 0), 0)

    phase_score_map = {
        "forming": 10,
        "formation": 10,
        "stable": 8,
        "confirmation": 16,
        "->confirmation": 16,
        "→confirmation": 16,
        "breakout": 20,
        "->breakout": 20,
        "→breakout": 20,
        "inversion": 12,
        "->inversion": 12,
        "→inversion": 12,
        "unknown": 0,
    }

    phase_score = phase_score_map.get(phase, 8)
    activity_score = min(25, int(activity * 0.3))
    quality_score = min(20, int(quality * 0.25))
    test_score = min(15, test_count * 3)
    convergence_score = int(max(0.0, min(1.0, amplitude_convergence)) * 10)

    if position_tag in {"above", "below", "far_above", "far_below"}:
        position_score = 10
    elif position_tag == "inside":
        position_score = 6
    else:
        position_score = 3

    recency_score = max(0, 10 - min(time_since_last_test, 10))

    total = min(
        100,
        phase_score
        + activity_score
        + quality_score
        + test_score
        + convergence_score
        + position_score
        + recency_score,
    )

    breakdown = {
        "phase": phase_score,
        "activity": activity_score,
        "quality": quality_score,
        "test_count": test_score,
        "amplitude_convergence": convergence_score,
        "position": position_score,
        "recency": recency_score,
    }

    return PriorityResult(total=total, breakdown=breakdown)


# ============================================================================
# Transition helpers
# ============================================================================

def build_transition_distribution_safe(
        history_transitions: List[Any],
        current_structure: Dict[str, Any],
) -> Any:
    context = {
        "phase": current_structure.get("phase", "unknown"),
        "quality": current_structure.get("quality_tier", "D"),
        "flux_sign": "+" if safe_float(current_structure.get("flux", 0.0), 0.0) >= 0 else "-",
    }

    if real_build_transition_distribution is not None:
        try:
            return real_build_transition_distribution(
                history_transitions=history_transitions or [],
                current_context=context,
            )
        except Exception:
            pass

    if not history_transitions:
        return {
            "sample_size": 0,
            "context": context,
            "items": [],
            "message": "暂无历史转移样本。需要先运行历史扫描或转移提取脚本。",
        }

    return {
        "sample_size": len(history_transitions),
        "context": context,
        "items": history_transitions,
    }


def format_transition_report_safe(
        dist: Any,
        current_price: float,
        zone_center: float,
) -> str:
    if real_format_transition_report is not None:
        try:
            return real_format_transition_report(dist, current_price, zone_center)
        except Exception:
            pass

    if isinstance(dist, dict):
        sample_size = dist.get("sample_size", 0)
        context = dist.get("context", {})
        message = dist.get("message", "")

        lines = [
            f"当前价格：{current_price:.2f}",
            f"Zone 中心：{zone_center:.2f}",
            f"样本数量：{sample_size}",
            f"匹配上下文：`{context}`",
        ]

        if message:
            lines.append("")
            lines.append(message)

        if sample_size == 0:
            lines.append("")
            lines.append("当前没有可统计的条件转移分布。页面接口已保留，后续接入 history_transitions 后会自动显示结果。")

        return "\n\n".join(lines)

    return str(dist)


# ============================================================================
# MTF helpers
# ============================================================================

def compute_mci_safe(mtf_snapshots: Dict[str, Any]) -> MCIReport:
    if real_compute_mci is not None:
        try:
            report = real_compute_mci(mtf_snapshots)
            return MCIReport(
                mci=safe_float(getattr(report, "mci", 0.0), 0.0),
                verdict=safe_str(getattr(report, "verdict", "未知"), "未知"),
                details=safe_str(getattr(report, "details", ""), ""),
            )
        except Exception:
            pass

    return MCIReport(
        mci=0.0,
        verdict="未计算",
        details="缺少真实 MTF 快照或 compute_mci 不可用。",
    )


# ============================================================================
# Falsification card helpers
# ============================================================================

def create_card_safe(
        symbol: str,
        current_structure: Dict[str, Any],
        transition_dist: Any,
        holding_days: int,
) -> Dict[str, Any]:
    if real_create_card is not None:
        try:
            card = real_create_card(
                symbol=symbol,
                zone_center=current_structure["zone_center"],
                current_price=current_structure["current_price"],
                phase=current_structure["phase"],
                quality_tier=current_structure["quality_tier"],
                transition_dist=transition_dist,
                holding_days=holding_days,
            )
            card_data = to_jsonable(card)
            if isinstance(card_data, dict):
                return card_data
            return {"card": card_data}
        except Exception:
            pass

    return {
        "card_id": f"{symbol}-{current_structure.get('phase', 'unknown')}-{holding_days}",
        "symbol": symbol,
        "zone_center": current_structure["zone_center"],
        "current_price": current_structure["current_price"],
        "phase": current_structure["phase"],
        "quality_tier": current_structure["quality_tier"],
        "holding_days": holding_days,
        "status": "open",
        "note": "fallback card",
    }


def append_to_ledger_safe(card: Dict[str, Any]) -> bool:
    if real_append_to_ledger is not None:
        try:
            real_append_to_ledger(card)
            return True
        except Exception:
            pass

    try:
        log_dir = _PROJECT_ROOT / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "falsification_cards.jsonl"

        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")

        return True
    except Exception:
        return False


def compute_hit_rate_safe() -> Dict[str, Any]:
    if real_compute_hit_rate is not None:
        try:
            stats = real_compute_hit_rate()
            if isinstance(stats, dict):
                return stats

            stats_json = to_jsonable(stats)
            if isinstance(stats_json, dict):
                return stats_json

            return {"stats": stats_json}
        except Exception:
            pass

    return {
        "closed": 0,
        "hit_rate": None,
        "message": "暂无已结算卡片，或真实 compute_hit_rate 不可用。",
    }


# ============================================================================
# Main render function
# ============================================================================

def render(
        symbol: str = "CU0",
        current_structure: Optional[Dict[str, Any]] = None,
        mtf_snapshots: Optional[Dict[str, Any]] = None,
        history_transitions: Optional[List[Any]] = None,
) -> None:
    symbol = safe_str(symbol, "CU0").upper()
    current_structure = normalize_current_structure(symbol, current_structure)
    mtf_snapshots = mtf_snapshots or {}
    history_transitions = history_transitions or []

    st.markdown(f"### {symbol} 研究闭环")

    if not current_structure.get("has_data", False):
        st.warning("当前页面没有收到真实结构上下文，正在使用占位数据渲染界面。")
        st.caption(
            "如果你是直接打开 /research_loop 页面，这是正常现象。若要显示真实结构，请从主工作台 Tab 进入，或在 app.py 中传入 current_structure。")

    # 1. Sector and chain
    info = get_sector_safe(symbol)
    peers = get_chain_peers_safe(symbol)

    col1, col2, col3 = st.columns(3)
    col1.metric("板块", info.sector)
    col2.metric("细分", info.sub_sector)
    col3.metric("产业链角色", info.chain_role)

    st.caption(f"同链共振候选：{', '.join(peers) if peers else '无'}")

    # 2. Current structure overview
    st.markdown("#### 当前结构概览")

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("运动阶段", current_structure["phase"])
    a2.metric("质量层", current_structure["quality_tier"])
    a3.metric("质量分", current_structure["quality"])
    a4.metric("离稳态活跃度", current_structure["activity"])

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("当前价格", f"{current_structure['current_price']:.2f}")
    b2.metric("Zone 中心", f"{current_structure['zone_center']:.2f}")
    b3.metric("试探次数", current_structure["test_count"])
    b4.metric("通量", f"{current_structure['flux']:+.2f}")

    with st.expander("查看标准化后的 current_structure"):
        st.json(current_structure)

    # 3. Priority score
    st.markdown("#### 优先级打分")

    convergence = compute_amplitude_convergence_safe(
        current_structure.get("test_amplitudes", [])
    )
    priority = compute_priority_safe(current_structure, convergence)

    p1, p2, p3 = st.columns([1, 1, 2])
    p1.metric("优先级", f"P{priority.total}")
    p2.metric("振幅收敛", f"{convergence:.2f}")
    p3.progress(min(max(priority.total / 100.0, 0.0), 1.0))

    st.code(f"P{priority.total} = {priority.breakdown}", language="python")

    # 4. Transition distribution
    st.markdown("#### 条件转移分布")

    dist = build_transition_distribution_safe(
        history_transitions,
        current_structure,
    )
    report = format_transition_report_safe(
        dist,
        current_structure["current_price"],
        current_structure["zone_center"],
    )

    st.markdown(report)

    with st.expander("查看原始 transition distribution"):
        st.json(to_jsonable(dist))

    # 5. MTF consistency
    st.markdown("#### 多时间维度一致性指数")

    required_keys = {"5m", "1h", "D"}
    current_keys = set(mtf_snapshots.keys())

    if mtf_snapshots and required_keys.issubset(current_keys):
        mci_report = compute_mci_safe(mtf_snapshots)

        m1, m2 = st.columns([1, 3])
        m1.metric("MCI", f"{mci_report.mci:.2f}")
        m2.markdown(f"**​{mci_report.verdict}​**\n\n{mci_report.details}")
    else:
        st.info("需要提供 5m / 1h / D 三个尺度的快照后，才能计算多时间维度一致性。")
        st.caption(f"当前已提供尺度：{', '.join(sorted(current_keys)) if current_keys else '无'}")

    with st.expander("查看 mtf_snapshots"):
        st.json(to_jsonable(mtf_snapshots))

    # 6. Falsification card
    st.markdown("#### 登记可证伪研究卡片")

    holding_days = st.slider("评估时间窗（交易日）", 3, 30, 10)

    if st.button("生成并入库", type="primary"):
        card = create_card_safe(
            symbol=symbol,
            current_structure=current_structure,
            transition_dist=dist,
            holding_days=holding_days,
        )

        ok = append_to_ledger_safe(card)

        card_id = (
                card.get("card_id")
                or card.get("id")
                or f"{symbol}-{current_structure['phase']}-{holding_days}"
        )

        if ok:
            st.success(f"已入库，卡片 ID: {card_id}")
        else:
            st.warning(f"卡片已生成，但写入 ledger 失败。卡片 ID: {card_id}")

        st.json(card)

    # 7. Hit rate
    st.markdown("#### 历史卡片命中率")

    stats = compute_hit_rate_safe()

    if isinstance(stats, dict) and stats.get("closed", 0) > 0:
        st.json(stats)
    else:
        st.caption("尚无已结算卡片，等到期自动回填。")
        with st.expander("查看命中率统计状态"):
            st.json(stats)


# ============================================================================
# Standalone page entry
# ============================================================================

def _run_standalone_page() -> None:
    try:
        st.set_page_config(
            page_title="研究闭环",
            page_icon="🔬",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass

    st.sidebar.markdown("## 研究闭环")
    st.sidebar.caption("独立页面模式")

    default_symbol = st.sidebar.text_input("品种代码", value="CU0").upper()

    st.sidebar.divider()
    st.sidebar.caption("从主工作台 Tab 进入时，会使用真实结构上下文；直接打开本页时，会使用占位上下文。")

    ctx = st.session_state.get("research_loop_ctx")

    if not ctx:
        st.warning("⚠️ 未检测到结构上下文数据。")
        st.info(
            "请从主工作台的「🎯 研究闭环」Tab 进入本页面，以获取真实的结构分析数据。\n\n"
            "或者在侧栏输入品种代码，使用占位数据预览页面功能。"
        )
        # 用占位数据渲染，不空白
        ctx = {}

    symbol = ctx.get("symbol", default_symbol)
    current_structure = ctx.get("current_structure")
    mtf_snapshots = ctx.get("mtf_snapshots", {})
    history_transitions = ctx.get("history_transitions", [])

    render(
        symbol=symbol,
        current_structure=current_structure,
        mtf_snapshots=mtf_snapshots,
        history_transitions=history_transitions,
    )


if __name__ == "__main__":
    _run_standalone_page()
