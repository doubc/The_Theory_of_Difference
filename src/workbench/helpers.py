def _build_current_structure_dict(result) -> dict:
    """把 compile_full 结果转成 research_loop.render 需要的字典"""
    s = result.structures[0]  # 最新结构
    cycles = getattr(s, "cycles", []) or []
    last_test_day = cycles[-1].end_date if cycles else None
    return {
        "phase": s.motion.phase_tendency,
        "activity": int(getattr(s, "deviation_activity", 30)),
        "quality": int(getattr(s, "quality_score", 60)),
        "quality_tier": getattr(s, "quality_tier", "B"),
        "position_tag": _position_tag(s),
        "test_count": len(cycles),
        "duration_days": (cycles[-1].end_date - cycles[0].start_date).days if cycles else 0,
        "time_since_last_test": (result.last_bar_date - last_test_day).days if last_test_day else 999,
        "test_amplitudes": [abs(c.amplitude) for c in cycles],
        "flux": float(s.motion.conservation_flux),
        "zone_center": float(s.zone.price_center),
        "current_price": float(result.last_close),
    }


def _load_mtf_snapshots(symbol: str) -> dict:
    """分别调用 5m / 1h / D 三个尺度的编译器，返回 TFSnapshot 字典"""
    from src.multitimeframe.consistency import TFSnapshot
    # 这里按你们现有的多时间维度编译入口改写
    result_d = compile_full(load_bars(symbol, freq="D"), CompilerConfig(min_amplitude=0.03), symbol=symbol)
    result_h = compile_full(load_bars(symbol, freq="1h"), CompilerConfig(min_amplitude=0.01), symbol=symbol)
    result_m = compile_full(load_bars(symbol, freq="5m"), CompilerConfig(min_amplitude=0.005), symbol=symbol)

    def _to_snap(res, tf):
        s = res.structures[0]
        return TFSnapshot(
            timeframe=tf,
            trend=s.motion.trend,
            flux_sign=1 if s.motion.conservation_flux >= 0 else -1,
            phase=s.motion.phase_tendency,
            zone_center=float(s.zone.price_center),
            zone_half_width=float(s.zone.half_width),
            quality_score=int(getattr(s, "quality_score", 60)),
        )

    return {"D": _to_snap(result_d, "D"), "1h": _to_snap(result_h, "1h"), "5m": _to_snap(result_m, "5m")}


def _load_history_transitions(symbol: str) -> list:
    """从 MySQL 或 data/transitions/*.parquet 读历史转移记录"""
    import pandas as pd
    from pathlib import Path
    p = Path(f"data/transitions/{symbol}.parquet")
    if not p.exists():
        return []
    df = pd.read_parquet(p)
    return df.to_dict("records")
