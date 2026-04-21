"""
结构编译器 — 价格序列 → 结构对象

四层流水线：
  3.1 极值提取 (extract_pivots)
  3.2 段生成 (build_segments)
  3.3 关键区识别 (detect_zones)
  3.4 结构组装 (assemble_structures)
  3.5 丛识别   (detect_bundles)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from src.models import (
    Point, Segment, Zone, Cycle, Structure, Bundle,
    Direction, ZoneSource,
)
from src.data.loader import Bar


# ─── 配置 ─────────────────────────────────────────────────

@dataclass
class CompilerConfig:
    min_amplitude: float = 0.02
    min_duration: int = 2
    noise_filter: float = 0.005
    zone_bandwidth: float = 0.01
    cluster_eps: float = 0.015
    cluster_min_points: int = 2
    min_cycles: int = 2
    tolerance: float = 0.02
    # 丛识别
    bundle_speed_tol: float = 0.4    # 速度比相似容差
    bundle_time_tol: float = 0.5     # 时间比相似容差
    bundle_zone_tol: float = 0.08    # 区距离容差（相对价格比例）


# ─── 3.1 极值提取 ──────────────────────────────────────────

def extract_pivots(bars: list[Bar], config: CompilerConfig) -> list[Point]:
    if len(bars) < config.min_duration * 2 + 1:
        return []

    n = config.min_duration
    candidates: list[tuple[int, str, float, datetime]] = []

    for i in range(n, len(bars) - n):
        h = bars[i].high
        l = bars[i].low

        is_swing_high = all(h >= bars[j].high for j in range(i - n, i + n + 1) if j != i)
        is_swing_low  = all(l <= bars[j].low  for j in range(i - n, i + n + 1) if j != i)

        if is_swing_high:
            candidates.append((i, "high", h, bars[i].timestamp))
        if is_swing_low:
            candidates.append((i, "low", l, bars[i].timestamp))

    if not candidates:
        return []

    candidates.sort(key=lambda c: c[0])

    # 幅度过滤 + 相同类型取极值
    filtered: list[tuple[int, str, float, datetime]] = [candidates[0]]

    for c in candidates[1:]:
        idx, ctype, price, t = c
        last_idx, last_type, last_price, last_t = filtered[-1]

        amplitude = abs(price - last_price) / last_price

        if ctype == last_type:
            if ctype == "high" and price > last_price:
                filtered[-1] = c
            elif ctype == "low" and price < last_price:
                filtered[-1] = c
            continue

        if amplitude >= config.min_amplitude:
            filtered.append(c)
        elif amplitude >= config.noise_filter:
            filtered[-1] = c

    return [Point(t=t, x=price, idx=idx) for idx, ctype, price, t in filtered]


# ─── 3.2 段生成 ────────────────────────────────────────────

def build_segments(pivots: list[Point]) -> list[Segment]:
    return [Segment(start=pivots[i], end=pivots[i + 1]) for i in range(len(pivots) - 1)]


# ─── 3.3 关键区识别 ────────────────────────────────────────

def detect_zones(
    pivots: list[Point],
    segments: list[Segment],
    config: CompilerConfig,
) -> list[Zone]:
    if not pivots:
        return []

    high_points: list[Point] = []
    low_points: list[Point] = []

    for i, p in enumerate(pivots):
        if i == 0 or i == len(pivots) - 1:
            continue
        if p.x > pivots[i - 1].x and p.x > pivots[i + 1].x:
            high_points.append(p)
        elif p.x < pivots[i - 1].x and p.x < pivots[i + 1].x:
            low_points.append(p)

    def cluster_points(points: list[Point], source: ZoneSource) -> list[Zone]:
        if not points:
            return []
        sorted_pts = sorted(points, key=lambda p: p.x)
        clusters: list[list[Point]] = [[sorted_pts[0]]]

        for p in sorted_pts[1:]:
            center = sum(pt.x for pt in clusters[-1]) / len(clusters[-1])
            if abs(p.x - center) / center <= config.cluster_eps:
                clusters[-1].append(p)
            else:
                clusters.append([p])

        result = []
        for cluster in clusters:
            if len(cluster) < config.cluster_min_points:
                continue
            center = sum(p.x for p in cluster) / len(cluster)
            bw = center * config.zone_bandwidth

            # 修复 strength: 用试探次数 + 价格紧凑度，不依赖 stddev
            n_touches = len(cluster)
            price_range = max(p.x for p in cluster) - min(p.x for p in cluster)
            compactness = 1.0 / (1.0 + price_range / center)  # 越紧凑越高
            strength = n_touches * compactness

            result.append(Zone(
                price_center=center,
                bandwidth=bw,
                source=source,
                strength=strength,
                touches=cluster,
            ))
        return result

    zones = []
    zones.extend(cluster_points(high_points, ZoneSource.HIGH_CLUSTER))
    zones.extend(cluster_points(low_points, ZoneSource.LOW_CLUSTER))
    zones.sort(key=lambda z: z.strength, reverse=True)
    return zones


# ─── 3.4 结构组装 ──────────────────────────────────────────

def build_cycles(
    segments: list[Segment],
    zones: list[Zone],
    config: CompilerConfig,
) -> list[Cycle]:
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


def assemble_structures(
    cycles: list[Cycle],
    zones: list[Zone],
    config: CompilerConfig,
) -> list[Structure]:
    if not cycles:
        return []

    zone_cycles: dict[float, list[Cycle]] = {}
    for c in cycles:
        key = c.zone.price_center
        zone_cycles.setdefault(key, []).append(c)

    structures: list[Structure] = []
    for center, cycs in zone_cycles.items():
        if len(cycs) < config.min_cycles:
            continue
        zone = cycs[0].zone
        st = Structure(zone=zone, cycles=cycs)
        st.invariants = {
            "avg_speed_ratio": st.avg_speed_ratio,
            "avg_time_ratio": st.avg_time_ratio,
            "high_cluster_stddev": st.high_cluster_stddev,
            "cycle_count": len(cycs),
        }
        structures.append(st)

    structures.sort(key=lambda s: s.cycle_count, reverse=True)
    return structures


# ─── 3.5 丛识别 (Bundle Detection) ─────────────────────────

def detect_bundles(structures: list[Structure], config: CompilerConfig) -> list[Bundle]:
    """
    丛 = 共享生成约束的多个 Structure 的集合。

    判定规则：
    1. 速度比相近（反映同一类信息传播效率）
    2. 时间比相近（反映同一类节奏模式）
    3. 区的相对距离合理（可在同一尺度内观察到）

    丛的类型：
    - "slow_up_fast_down": 慢涨急跌类（speed_ratio > 1, entry慢 exit快）
    - "fast_up_slow_down": 急涨慢跌类（speed_ratio < 1, entry快 exit慢）
    - "balanced": 均衡类（speed_ratio ≈ 1）
    - "high_volatility": 高波动类（速度比极值大）
    """
    if len(structures) < 2:
        return []

    # 第一步：对每个结构分类
    classified: list[tuple[Structure, str]] = []
    for st in structures:
        sr = st.avg_speed_ratio
        tr = st.avg_time_ratio

        if sr > 1.5 and tr > 1.5:
            bundle_type = "slow_up_fast_down"
        elif sr < 0.67 and tr < 0.67:
            bundle_type = "fast_up_slow_down"
        elif 0.7 < sr < 1.4 and 0.7 < tr < 1.4:
            bundle_type = "balanced"
        else:
            bundle_type = "mixed"

        classified.append((st, bundle_type))

    # 第二步：按类型分组
    type_groups: dict[str, list[Structure]] = {}
    for st, btype in classified:
        type_groups.setdefault(btype, []).append(st)

    # 第三步：在每组内按速度比/时间比进一步聚类
    bundles: list[Bundle] = []
    for btype, group in type_groups.items():
        if len(group) < 2:
            # 单个结构也归入一个丛
            bundles.append(Bundle(
                structures=group,
                generator_constraint=f"type={btype}, single structure",
            ))
            continue

        # 按速度比排序，聚类相似的
        group.sort(key=lambda s: s.avg_speed_ratio)
        clusters: list[list[Structure]] = [[group[0]]]

        for st in group[1:]:
            ref = clusters[-1][0]
            sr_diff = abs(st.avg_speed_ratio - ref.avg_speed_ratio) / max(ref.avg_speed_ratio, 0.01)
            tr_diff = abs(st.avg_time_ratio - ref.avg_time_ratio) / max(ref.avg_time_ratio, 0.01)

            if sr_diff <= config.bundle_speed_tol and tr_diff <= config.bundle_time_tol:
                clusters[-1].append(st)
            else:
                clusters.append([st])

        for cluster in clusters:
            avg_sr = sum(s.avg_speed_ratio for s in cluster) / len(cluster)
            avg_tr = sum(s.avg_time_ratio for s in cluster) / len(cluster)
            constraint = (
                f"type={btype}, "
                f"speed_ratio≈{avg_sr:.2f}, "
                f"time_ratio≈{avg_tr:.2f}, "
                f"n={len(cluster)}"
            )
            bundles.append(Bundle(
                structures=cluster,
                generator_constraint=constraint,
            ))

    # 按丛内结构数排序
    bundles.sort(key=lambda b: len(b.structures), reverse=True)
    return bundles


# ─── 编译结果 ──────────────────────────────────────────────

@dataclass
class CompileResult:
    bars_count: int
    pivots: list[Point]
    segments: list[Segment]
    zones: list[Zone]
    cycles: list[Cycle]
    structures: list[Structure]
    bundles: list[Bundle]
    config: CompilerConfig

    def summary(self) -> dict:
        return {
            "bars": self.bars_count,
            "pivots": len(self.pivots),
            "segments": len(self.segments),
            "zones": len(self.zones),
            "cycles": len(self.cycles),
            "structures": len(self.structures),
            "bundles": len(self.bundles),
            "top_structure": str(self.structures[0]) if self.structures else None,
        }


def compile_full(bars: list[Bar], config: CompilerConfig | None = None) -> CompileResult:
    if config is None:
        config = CompilerConfig()

    pivots = extract_pivots(bars, config)
    segments = build_segments(pivots)
    zones = detect_zones(pivots, segments, config)
    cycles = build_cycles(segments, zones, config)
    structures = assemble_structures(cycles, zones, config)
    bundles = detect_bundles(structures, config)

    return CompileResult(
        bars_count=len(bars),
        pivots=pivots,
        segments=segments,
        zones=zones,
        cycles=cycles,
        structures=structures,
        bundles=bundles,
        config=config,
    )
