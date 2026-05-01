"""
扫描计算管线 — _departure_score + _build_dashboard_data

从 tab_scan.py 迁移，负责扫描计算、字段补充、诊断日志。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def departure_score(r: dict) -> float:
    """
    离稳态活跃度评分（0-100），衡量结构正在离开均衡态的程度。

    四维度各25分：
      - 阶段转换 (25): 是否有 "→" 阶段跳变（如 →confirmation）
      - 通量强度 (25): 守恒通量绝对值越大越活跃
      - 离稳态速度 (25): stable_velocity 为负 = 正在远离稳态
      - 信号质量 (25): 交易信号置信度 + 通量一致性
    """
    pts = 0.0

    if r.get("phase_transition"):
        pts += 25.0

    flux = r.get("flux_magnitude", 0)
    pts += min(flux / 0.5, 1.0) * 25.0

    dep_vel = r.get("departure_velocity", 0)
    pts += min(dep_vel / 0.5, 1.0) * 25.0

    sig_s = r.get("signal_score", 0)
    pts += sig_s * 25.0

    return pts


def build_dashboard_data(
    ALL_SYMBOLS: list[str],
    load_bars_fn,
    compile_fn,
    sens_key: str,
    min_volume: float = 20000,
) -> list[dict]:
    """
    成交量驱动的全景仪表盘数据构建。

    为每个最新日成交量 > min_volume 的合约，提取：
    - 稳态序列（所有 Zone 按时间排序）
    - 趋势方向、稳态关系
    - 当前价格相对最近稳态的位置
    - 运动阶段、通量、质量
    """
    from src.data.symbol_meta import symbol_name as _symbol_name, get_sector
    from src.quality import assess_quality, QualityTier

    _sens = {
        "粗糙": {"min_amp": 0.05, "min_dur": 5, "min_cycles": 3, "lookback_days": 240},
        "标准": {"min_amp": 0.03, "min_dur": 3, "min_cycles": 2, "lookback_days": 180},
        "精细": {"min_amp": 0.015, "min_dur": 2, "min_cycles": 2, "lookback_days": 120},
    }
    _s = _sens.get(sens_key, _sens["标准"])
    lookback = _s["lookback_days"]

    results = []
    for sym in ALL_SYMBOLS:
        bars_data = load_bars_fn(sym)
        if not bars_data or len(bars_data) < 30:
            continue

        latest_vol = bars_data[-1].volume
        if latest_vol < min_volume:
            continue

        if len(bars_data) > lookback:
            bars_data = bars_data[-lookback:]

        last_price = bars_data[-1].close
        last_date = bars_data[-1].timestamp.strftime("%Y-%m-%d")

        from src.compiler.pipeline import CompilerConfig
        cfg = CompilerConfig(
            min_amplitude=_s["min_amp"], min_duration=_s["min_dur"],
            min_cycles=_s["min_cycles"],
            adaptive_pivots=True, fractal_threshold=0.34,
        )
        cr = compile_fn(bars_data, cfg, symbol=sym)
        if not cr.ranked_structures:
            continue

        structs = sorted(cr.ranked_structures, key=lambda s: s.t_start or datetime.min)
        zones_info = []
        for s in structs:
            if s.zone:
                t_start_str = s.t_start.strftime("%m/%d") if s.t_start else "?"
                t_end_str = s.t_end.strftime("%m/%d") if s.t_end else "?"
                zones_info.append({
                    "center": round(s.zone.price_center, 1),
                    "bw": round(s.zone.bandwidth, 1),
                    "upper": round(s.zone.upper, 1),
                    "lower": round(s.zone.lower, 1),
                    "date_range": f"{t_start_str}~{t_end_str}",
                    "cycles": s.cycle_count,
                    "t_start": s.t_start,
                    "t_end": s.t_end,
                })

        if not zones_info:
            continue

        latest_zone = zones_info[-1]
        prev_zone = zones_info[-2] if len(zones_info) >= 2 else None

        # 稳态趋势
        if len(zones_info) >= 2:
            centers = [z["center"] for z in zones_info]
            avg_change = (centers[-1] - centers[0]) / len(centers) if len(centers) > 1 else 0
            if avg_change > latest_zone["bw"] * 0.3:
                zone_trend = "上行"
            elif avg_change < -latest_zone["bw"] * 0.3:
                zone_trend = "下行"
            else:
                zone_trend = "持平"
        else:
            zone_trend = "—"

        # 稳态关系
        if prev_zone:
            center_diff = abs(latest_zone["center"] - prev_zone["center"])
            combined_bw = latest_zone["bw"] + prev_zone["bw"]
            overlap = min(latest_zone["upper"], prev_zone["upper"]) - max(latest_zone["lower"], prev_zone["lower"])
            overlap_ratio = overlap / combined_bw if combined_bw > 0 else 0

            if overlap_ratio > 0.5:
                zone_relation = "延续"
            elif center_diff < combined_bw * 0.8:
                zone_relation = "收窄"
            else:
                zone_relation = "跃迁"
        else:
            zone_relation = "—"

        # 价格位置
        from src.workbench.ui_formatters import classify_price_position
        z_upper = latest_zone["upper"]
        z_lower = latest_zone["lower"]
        z_center = latest_zone["center"]
        z_bw = latest_zone["bw"]

        price_position, price_position_code = classify_price_position(
            last_price, z_upper, z_lower, z_center, z_bw
        )

        # 运动阶段
        latest_struct = structs[-1]
        m = latest_struct.motion
        p = latest_struct.projection
        ss = cr.get_system_state_for(latest_struct)
        qa = assess_quality(latest_struct, ss)

        phase_str = m.phase_tendency if m else ""
        if "breakout" in phase_str:
            motion_label = "🔴 破缺"
        elif "confirmation" in phase_str:
            motion_label = "🟢 确认"
        elif "forming" in phase_str:
            motion_label = "🔵 形成"
        elif "stable" in phase_str:
            motion_label = "⚪ 稳态"
        elif "breakdown" in phase_str:
            motion_label = "🟠 回落"
        else:
            motion_label = "—"

        # 方向
        direction = "unclear"
        if m and "breakout" in m.phase_tendency:
            direction = "down" if m.conservation_flux < 0 else "up"
        elif m and "confirmation" in m.phase_tendency:
            direction = "up" if m.conservation_flux > 0 else "down"

        # 破缺确认日
        breakout_date = ""
        if m and ("breakout" in m.phase_tendency or "confirmation" in m.phase_tendency):
            if latest_struct.t_end:
                breakout_date = latest_struct.t_end.strftime("%m/%d")

        flux_val = round(m.conservation_flux, 3) if m else 0.0

        # 离稳态活跃度
        dep_score = departure_score({
            "phase_transition": "→" in phase_str,
            "flux_magnitude": abs(flux_val),
            "departure_velocity": max(0, -(m.stable_velocity if m else 0)),
            "signal_score": qa.score,
        })

        # 信号详情
        signal_info = None
        try:
            from src.signals import generate_signal
            sig = generate_signal(latest_struct, bars=bars_data, system_state=ss)
            if sig:
                signal_info = {
                    "kind": sig.kind.value,
                    "direction": sig.direction,
                    "confidence": round(sig.confidence, 3),
                    "flux_aligned": sig.flux_aligned,
                    "stability_ok": sig.stability_ok,
                    "entry_note": sig.entry_note,
                    "breakout_score": round(sig.breakout_score, 3),
                    "fake_pattern": sig.fake_pattern.value if sig.fake_pattern else None,
                    "quality_tier": sig.quality_tier,
                    "entry_price": round(sig.entry_price, 1),
                    "stop_loss_price": round(sig.stop_loss_price, 1),
                    "take_profit_price": round(sig.take_profit_price, 1),
                    "rr_ratio": round(sig.rr_ratio, 2),
                    "position_size_factor": round(sig.position_size_factor, 2),
                    "signal_type_label": sig.signal_type_label(),
                    "display_label": sig.display_label,
                }
        except Exception:
            log.warning("信号生成失败: %s", sym, exc_info=True)

        # Phase 1: 新增字段
        phase_code = phase_str.split("→")[-1].strip() if "→" in phase_str else phase_str
        if not phase_code or phase_code == "—":
            phase_code = "stable"

        sector = get_sector(sym)

        # 优先级
        from src.workbench.scan_filters import compute_priority_score
        priority_score = compute_priority_score(
            dep_score=dep_score, qa_score=qa.score, phase_code=phase_code,
            price_position_code=price_position_code, latest_vol=latest_vol,
            results_so_far=results,
        )

        results.append({
            "symbol": sym,
            "symbol_name": _symbol_name(sym),
            "volume": int(latest_vol),
            "last_price": round(last_price, 1),
            "last_date": last_date,
            "zones": zones_info,
            "latest_zone_center": latest_zone["center"],
            "latest_zone_bw": latest_zone["bw"],
            "zone_trend": zone_trend,
            "zone_relation": zone_relation,
            "zone_count": len(zones_info),
            "price_position": price_position,
            "price_position_code": price_position_code,
            "motion": phase_str or "—",
            "motion_label": motion_label,
            "phase_code": phase_code,
            "flux": flux_val,
            "direction": direction,
            "breakout_date": breakout_date,
            "tier": qa.tier.value,
            "score": round(qa.score * 100, 1),
            "cycles": latest_struct.cycle_count,
            "is_blind": p.is_blind if p else False,
            "departure_score": round(dep_score, 1),
            "sector": sector,
            "priority_score": round(priority_score * 100, 1),
            "signal_info": signal_info,
        })

    results.sort(key=lambda x: x["volume"], reverse=True)
    return results
