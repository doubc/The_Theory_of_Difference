"""
扫描筛选与排序逻辑

从 tab_scan.py 迁移：apply_scan_filters、compute_priority_score、pick_today_three
"""
from __future__ import annotations


def compute_priority_score(
    dep_score: float,
    qa_score: float,
    phase_code: str,
    price_position_code: str,
    latest_vol: int,
    results_so_far: list[dict],
) -> float:
    """
    计算综合优先级分数（0~1）。

    Args:
        dep_score: 离稳态活跃度 (0-100)
        qa_score: 质量分数 (0-1)
        phase_code: 阶段代码 (breakout/confirmation/forming/stable/breakdown)
        price_position_code: 价格位置 (H/M/L)
        latest_vol: 最新成交量
        results_so_far: 已累积的结果（用于计算相对成交量）

    Returns:
        0~1 的优先级分数
    """
    phase_map = {"breakout": 1.0, "confirmation": 0.8, "forming": 0.5, "stable": 0.3, "breakdown": 0.2}
    pos_map = {"H": 1.0, "M": 0.6, "L": 0.8}

    dep_norm = min(dep_score / 100, 1.0)
    phase_score = phase_map.get(phase_code, 0.3)
    position_score = pos_map.get(price_position_code, 0.5)
    max_vol = max((r.get("volume", 1) for r in results_so_far), default=1) if results_so_far else 1
    volume_score = min(latest_vol / max(max_vol, 1), 1.0)

    return (
        dep_norm * 0.30
        + qa_score * 0.20
        + phase_score * 0.20
        + position_score * 0.15
        + volume_score * 0.15
    )


def apply_scan_filters(
    data: list[dict],
    direction: str = "全部",
    motion: str = "全部",
    price_pos: str = "全部",
    tier: str = "全部",
    zone_trend: str = "全部",
    sector: str = "全部",
    min_volume: int = 0,
) -> list[dict]:
    """
    应用筛选条件到扫描结果。

    Args:
        data: _build_dashboard_data 的输出
        direction: "全部"/"偏多"/"偏空"/"不明"
        motion: "全部"/"破缺"/"确认"/"形成"/"稳态"/"回落"
        price_pos: "全部"/"高位"/"中位"/"低位"
        tier: "全部"/"A"/"B"/"C"
        zone_trend: "全部"/"上行"/"下行"/"持平"
        sector: "全部"/具体板块名
        min_volume: 最低成交量

    Returns:
        筛选后的列表
    """
    filtered = data

    if direction != "全部":
        dir_map = {"偏多": "up", "偏空": "down", "不明": "unclear"}
        target = dir_map.get(direction, direction)
        filtered = [r for r in filtered if r["direction"] == target]

    if motion != "全部":
        motion_map = {"破缺": "breakout", "确认": "confirmation", "形成": "forming", "稳态": "stable", "回落": "breakdown"}
        target = motion_map.get(motion, motion)
        filtered = [r for r in filtered if r.get("phase_code") == target]

    if price_pos != "全部":
        pos_map = {"高位": "H", "中位": "M", "低位": "L"}
        target = pos_map.get(price_pos, price_pos)
        filtered = [r for r in filtered if r.get("price_position_code") == target]

    if tier != "全部":
        filtered = [r for r in filtered if r.get("tier") == tier]

    if zone_trend != "全部":
        filtered = [r for r in filtered if r.get("zone_trend") == zone_trend]

    if sector != "全部":
        filtered = [r for r in filtered if r.get("sector") == sector]

    if min_volume > 0:
        filtered = [r for r in filtered if r["volume"] >= min_volume]

    return filtered


def pick_today_three(data: list[dict]) -> list[dict]:
    """
    今日三选 — 按三个规则各取一个最高优先级合约：
      1. 最强 confirmation
      2. 最强 breakout
      3. 最强边界试探（price_position 包含 "试探边界"）

    若不足三个，用综合优先级补足。

    Args:
        data: 完整扫描结果列表

    Returns:
        最多 3 个 dict 的列表，每个 dict 额外包含 pick_reason 字段
    """
    picked = []
    used_symbols = set()

    # 1. 最强 confirmation
    confirmations = [r for r in data if r.get("phase_code") == "confirmation"]
    if confirmations:
        best = max(confirmations, key=lambda x: x.get("priority_score", 0))
        entry = {**best, "pick_reason": "最强确认"}
        picked.append(entry)
        used_symbols.add(best["symbol"])

    # 2. 最强 breakout
    breakouts = [r for r in data if r.get("phase_code") == "breakout" and r["symbol"] not in used_symbols]
    if breakouts:
        best = max(breakouts, key=lambda x: x.get("priority_score", 0))
        entry = {**best, "pick_reason": "最强破缺"}
        picked.append(entry)
        used_symbols.add(best["symbol"])

    # 3. 最强边界试探
    boundary_tests = [
        r for r in data
        if "试探边界" in r.get("price_position", "") and r["symbol"] not in used_symbols
    ]
    if boundary_tests:
        best = max(boundary_tests, key=lambda x: x.get("priority_score", 0))
        entry = {**best, "pick_reason": "最强边界试探"}
        picked.append(entry)
        used_symbols.add(best["symbol"])

    # 补足到 3 个
    if len(picked) < 3:
        remaining = [r for r in data if r["symbol"] not in used_symbols]
        remaining.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        for r in remaining:
            if len(picked) >= 3:
                break
            entry = {**r, "pick_reason": "综合优先级"}
            picked.append(entry)
            used_symbols.add(r["symbol"])

    return picked


def build_market_overview(data: list[dict]) -> dict:
    """
    构建市场概览统计。

    Returns:
        {
            "active_count": int,       # 活跃合约数
            "departure_count": int,    # 高离稳态数（departure_score > 50）
            "breakout_count": int,     # 破缺数
            "confirmation_count": int, # 确认数
        }
    """
    return {
        "active_count": len(data),
        "departure_count": sum(1 for r in data if r.get("departure_score", 0) > 50),
        "breakout_count": sum(1 for r in data if "breakout" in (r.get("motion") or "")),
        "confirmation_count": sum(1 for r in data if "confirmation" in (r.get("motion") or "")),
    }
