"""
Cycle 与 Structure 组装
"""

from __future__ import annotations

from src.models import Point, Segment, Zone, Cycle, Structure, Phase


def build_cycles(
    segments: list[Segment],
    zones: list[Zone],
    min_cycles: int = 2,
) -> list[Cycle]:
    """
    识别围绕 Zone 的 Cycle。

    定义：一个 Cycle = 进入 zone 的段 + 离开 zone 的段
    具体：段的终点落在 zone 内但起点在 zone 外 → 该段为 entry
          紧接的下一段离开 zone → 该段为 exit
    """
    if not segments or not zones:
        return []

    cycles: list[Cycle] = []
    for seg in segments:
        for zone in zones:
            if zone.contains(seg.end.x) and not zone.contains(seg.start.x):
                seg_idx = segments.index(seg)
                if seg_idx + 1 < len(segments):
                    exit_seg = segments[seg_idx + 1]
                    if not zone.contains(exit_seg.end.x):
                        cycles.append(Cycle(entry=seg, exit=exit_seg, zone=zone))
                        break
    return cycles


def _infer_phases(cycles: list[Cycle], zone: Zone) -> list[Phase]:
    """
    推断结构的生命周期阶段

    启发式规则：
    - FORMATION: Cycle 数少于 3，或速度比不稳定
    - CONFIRMATION: Cycle 数 >= 3，速度比标准差小
    - BREAKDOWN: 最后一个 exit 段突破 zone 边界且方向一致
    - INVERSION: 最近的 cycle 速度比反转（exit 变慢 → exit 变快或反之）
    """
    if not cycles:
        return [Phase.FORMATION]

    n = len(cycles)
    phases = []

    # FORMATION: 刚开始
    if n < 3:
        phases.append(Phase.FORMATION)
        return phases

    # 计算速度比稳定性
    speed_ratios = [c.speed_ratio for c in cycles]
    avg_sr = sum(speed_ratios) / n
    std_sr = (sum((x - avg_sr) ** 2 for x in speed_ratios) / n) ** 0.5 if n > 1 else 0

    # CONFIRMATION: 稳定期
    if std_sr / max(avg_sr, 0.01) < 0.5:  # 变异系数 < 50%
        phases.append(Phase.CONFIRMATION)

    # BREAKDOWN: 最后 cycle 的 exit 远离 zone
    last = cycles[-1]
    last_exit_dist = zone.distance_to(last.exit.end.x)
    if last_exit_dist > zone.bandwidth * 2:  # 距离超过 2 倍带宽
        phases.append(Phase.BREAKDOWN)

    # INVERSION: 速度比反转（前半 vs 后半）
    if n >= 4:
        first_half_avg = sum(speed_ratios[:n // 2]) / (n // 2)
        second_half_avg = sum(speed_ratios[n // 2:]) / (n - n // 2)
        # 如果前后半段速度比方向相反（一个 >1 一个 <1）
        if (first_half_avg > 1) != (second_half_avg > 1):
            phases.append(Phase.INVERSION)

    # 如果没有命中任何阶段，默认 FORMATION
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

    zone_cycles: dict[float, list[Cycle]] = {}
    for c in cycles:
        key = c.zone.price_center
        zone_cycles.setdefault(key, []).append(c)

    structures: list[Structure] = []
    for center, cycs in zone_cycles.items():
        if len(cycs) < min_cycles:
            continue
        zone = cycs[0].zone
        # 从 Cycle 推导时间范围
        all_times = []
        for c in cycs:
            all_times.extend([c.entry.start.t, c.entry.end.t, c.exit.start.t, c.exit.end.t])
        st = Structure(
            zone=zone,
            cycles=cycs,
            phases=_infer_phases(cycs, zone),
            symbol=symbol,
            t_start=min(all_times) if all_times else None,
            t_end=max(all_times) if all_times else None,
        )
        st.invariants = {
            "avg_speed_ratio": st.avg_speed_ratio,
            "avg_time_ratio": st.avg_time_ratio,
            "high_cluster_stddev": st.high_cluster_stddev,
            "cycle_count": len(cycs),
        }
        structures.append(st)

    structures.sort(key=lambda s: s.cycle_count, reverse=True)
    return structures
