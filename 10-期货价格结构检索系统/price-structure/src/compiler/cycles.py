"""
Cycle 与 Structure 组装

修复：
1. build_cycles 用 O(n) 遍历替代 segments.index(seg)
2. assemble_structures 用 id(zone) 替代 price_center 作 dict key
3. 引入 relations.structure_invariants

V1.6 P0 新增：
4. 最近稳态检测 — V1.6 命题 3.4/3.5, 4.4/4.5
   exit 之后扫描后续极值，寻找价格最先停驻的位置
"""

from __future__ import annotations
from src.models import (
    Point, Segment, Zone, Cycle, Structure, Phase,
    NearestStableState, Direction, ZoneSource,
)
from src.relations import structure_invariants


def _touches_zone(p: Point, zone: Zone, slack: float = 0.005) -> bool:
    """点是否触及 zone（允许小幅越界）"""
    slack_abs = zone.price_center * slack
    return (zone.lower - slack_abs) <= p.x <= (zone.upper + slack_abs)


def _find_nearest_stable(
    exit_seg: Segment,
    subsequent_segments: list[Segment],
    all_zones: list[Zone],
    max_lookahead: int = 8,
    stable_threshold: float = 0.015,
) -> NearestStableState | None:
    """
    V1.6 命题 3.4: 最近稳态检测
    exit 之后，沿最小变易方向扫描后续段，找到价格最先停驻的位置。

    判定逻辑：
    1. exit 方向决定搜索方向（exit 向上 → 搜索上方，向下 → 搜索下方）
    2. 扫描后续 max_lookahead 个段
    3. 找到第一个：段的终点重新触及某个 zone，或段的幅度开始递减（减速 = 接近稳态）
    4. 阻力评分 = 到达稳态所需段数 / max_lookahead（越小越好）
    """
    if not subsequent_segments:
        return None

    exit_direction = exit_seg.direction
    if exit_direction == Direction.FLAT:
        return None

    # 扫描后续段，寻找最先停驻的位置
    for k, seg in enumerate(subsequent_segments[:max_lookahead]):
        if k == 0:
            continue  # 跳过 exit 本身之后的第一段（通常是反向段）

        # 判定1：该段终点触及某个已知 zone → 最近稳态
        for z in all_zones:
            if _touches_zone(seg.end, z):
                return NearestStableState(
                    zone=z,
                    arrival_point=seg.end,
                    duration_to_arrive=(
                        (seg.end.t - exit_seg.end.t).days
                        if hasattr(seg.end.t, '__sub__') else 0.0
                    ),
                    resistance_level=(k + 1) / max_lookahead,
                )

        # 判定2：连续两段幅度递减 → 减速，该段终点就是稳态候选
        if k >= 1:
            prev_seg = subsequent_segments[k - 1]
            if prev_seg.abs_delta > 0 and seg.abs_delta < prev_seg.abs_delta * 0.5:
                # 价格在减速，构造一个临时 zone 作为稳态
                center = seg.end.x
                bw = center * stable_threshold
                stable_zone = Zone(
                    price_center=center,
                    bandwidth=bw,
                    source=ZoneSource.PIVOT,
                    strength=0.5,
                )
                return NearestStableState(
                    zone=stable_zone,
                    arrival_point=seg.end,
                    duration_to_arrive=(
                        (seg.end.t - exit_seg.end.t).days
                        if hasattr(seg.end.t, '__sub__') else 0.0
                    ),
                    resistance_level=(k + 1) / max_lookahead,
                )

    return None


def build_cycles(
    segments: list[Segment],
    zones: list[Zone],
    min_cycles: int = 2,  # 兼容旧签名
) -> list[Cycle]:
    """
    识别围绕 Zone 的 Cycle。

    规则：
    - entry.end 触及 zone
    - entry.start 不在 zone 内
    - 紧邻的下一段 exit 方向反向且 exit.end 离开 zone

    V1.6 P0: 每个 Cycle 附加最近稳态检测
    """
    cycles: list[Cycle] = []
    if len(segments) < 2 or not zones:
        return cycles

    for i in range(len(segments) - 1):
        entry = segments[i]
        exit_ = segments[i + 1]
        # 方向反向
        if entry.direction.value * exit_.direction.value >= 0:
            continue
        for z in zones:
            if not _touches_zone(entry.end, z):
                continue
            if z.contains(entry.start.x):
                continue
            if _touches_zone(exit_.end, z):
                continue

            # ── V1.6 P0: 最近稳态检测 ──
            subsequent = segments[i + 2:] if i + 2 < len(segments) else []
            next_stable = _find_nearest_stable(exit_, subsequent, zones)

            cycles.append(Cycle(
                entry=entry,
                exit=exit_,
                zone=z,
                next_stable=next_stable,
            ))
    return cycles


def _infer_phases(cycles: list[Cycle], zone: Zone) -> list[Phase]:
    """推断结构生命周期阶段"""
    if not cycles:
        return [Phase.FORMATION]

    n = len(cycles)
    phases: list[Phase] = []

    if n < 3:
        phases.append(Phase.FORMATION)
        return phases

    speed_ratios = [c.speed_ratio for c in cycles]
    avg_sr = sum(speed_ratios) / n
    std_sr = (sum((x - avg_sr) ** 2 for x in speed_ratios) / n) ** 0.5 if n > 1 else 0

    if avg_sr > 0 and std_sr / avg_sr < 0.5:
        phases.append(Phase.CONFIRMATION)

    last = cycles[-1]
    if zone.distance_to(last.exit.end.x) > zone.bandwidth * 2:
        phases.append(Phase.BREAKDOWN)

    if n >= 4:
        half = n // 2
        first_half_avg = sum(speed_ratios[:half]) / half
        second_half_avg = sum(speed_ratios[half:]) / (n - half)
        if (first_half_avg > 1) != (second_half_avg > 1):
            phases.append(Phase.INVERSION)

    if not phases:
        phases.append(Phase.FORMATION)
    return phases


def assemble_structures(
    cycles: list[Cycle],
    zones: list[Zone],
    min_cycles: int = 2,
    symbol: str | None = None,
) -> list[Structure]:
    """对每个 Zone 组装 Structure 候选"""
    if not cycles:
        return []

    # 用 id(zone) 作为 key，避免浮点数不稳定
    zone_cycles: dict[int, list[Cycle]] = {}
    for c in cycles:
        zone_cycles.setdefault(id(c.zone), []).append(c)

    structures: list[Structure] = []
    for zone_id, cycs in zone_cycles.items():
        if len(cycs) < min_cycles:
            continue
        zone = cycs[0].zone

        all_times = []
        for c in cycs:
            all_times.extend([c.entry.start.t, c.entry.end.t,
                              c.exit.start.t, c.exit.end.t])

        st = Structure(
            zone=zone,
            cycles=cycs,
            phases=_infer_phases(cycs, zone),
            symbol=symbol,
            t_start=min(all_times),
            t_end=max(all_times),
        )
        st.invariants = structure_invariants(st)
        structures.append(st)

    structures.sort(
        key=lambda s: (s.cycle_count, s.zone.strength),
        reverse=True,
    )
    return structures
