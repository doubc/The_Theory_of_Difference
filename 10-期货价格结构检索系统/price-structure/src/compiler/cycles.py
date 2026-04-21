"""
Cycle 与 Structure 组装

修复：
1. build_cycles 用 O(n) 遍历替代 segments.index(seg)
2. assemble_structures 用 id(zone) 替代 price_center 作 dict key
3. 引入 relations.structure_invariants
"""

from __future__ import annotations
from src.models import Point, Segment, Zone, Cycle, Structure, Phase
from src.relations import structure_invariants


def _touches_zone(p: Point, zone: Zone, slack: float = 0.005) -> bool:
    """点是否触及 zone（允许小幅越界）"""
    slack_abs = zone.price_center * slack
    return (zone.lower - slack_abs) <= p.x <= (zone.upper + slack_abs)


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
            cycles.append(Cycle(entry=entry, exit=exit_, zone=z))
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
