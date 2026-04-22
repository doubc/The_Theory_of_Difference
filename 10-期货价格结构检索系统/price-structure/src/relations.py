"""
关系算子层 — 不存储，纯计算
所有"点间/段间/结构间"的关系在这里定义

V1.6 P0 新增：
- infer_narrative_context: 结构叙事背景推断（V1.6 命题 2.3 可叙事性）
- check_conservation: 差异守恒检查骨架（V1.6 命题 4.1-4.2）
"""

from __future__ import annotations
import math
from typing import Sequence
from src.models import Point, Segment, Zone, Structure, ContrastType, MotionState, Phase


# ─── 点间 ──────────────────────────────────────────────────

def first_diff(p1: Point, p2: Point) -> float:
    return p2.x - p1.x


def log_diff(p1: Point, p2: Point) -> float:
    return p2.log_x - p1.log_x


def second_diff(p1: Point, p2: Point, p3: Point) -> float:
    return p3.x - 2 * p2.x + p1.x


def time_gap_days(p1: Point, p2: Point) -> float:
    return (p2.t - p1.t).days


# ─── 段间 ──────────────────────────────────────────────────

def segment_speed_ratio(s1: Segment, s2: Segment) -> float:
    if s1.abs_rate == 0:
        return float("inf") if s2.abs_rate > 0 else 0.0
    return s2.abs_rate / s1.abs_rate


def segment_log_speed_ratio(s1: Segment, s2: Segment) -> float:
    a, b = abs(s1.log_rate), abs(s2.log_rate)
    if a == 0:
        return float("inf") if b > 0 else 0.0
    return b / a


def segment_time_ratio(s1: Segment, s2: Segment) -> float:
    if s2.duration == 0:
        return 0.0
    return s1.duration / s2.duration


def direction_change(s1: Segment, s2: Segment) -> int:
    prod = s1.direction.value * s2.direction.value
    if prod < 0:
        return 1
    if prod > 0:
        return 0
    return -1


# ─── 点与 Zone ─────────────────────────────────────────────

def distance_to_zone(p: Point, z: Zone) -> float:
    return z.distance_to(p.x)


def relative_distance_to_zone(p: Point, z: Zone) -> float:
    if z.bandwidth == 0:
        return 0.0
    return z.distance_to(p.x) / z.bandwidth


# ─── 极值点聚集度 ──────────────────────────────────────────

def extrema_dispersion(points: Sequence[Point]) -> float:
    if len(points) < 2:
        return 0.0
    prices = [p.x for p in points]
    mean = sum(prices) / len(prices)
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in prices) / len(prices)
    return math.sqrt(var) / mean


def extrema_trend(points: Sequence[Point]) -> float:
    if len(points) < 2:
        return 0.0
    n = len(points)
    xs = list(range(n))
    ys = [p.x for p in points]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    if den == 0 or my == 0:
        return 0.0
    return (num / den) / my


# ─── 结构级不变量 ──────────────────────────────────────────

def structure_invariants(s: Structure) -> dict:
    """把结构的所有不变量打包成 dict（全部归一化为无量纲比率）"""
    highs_above: list[Point] = []
    lows_below: list[Point] = []
    for c in s.cycles:
        for p in (c.entry.start, c.entry.end, c.exit.start, c.exit.end):
            if p.x >= s.zone.price_center:
                highs_above.append(p)
            else:
                lows_below.append(p)

    # 对数速度比均值（消除绝对价格影响）
    log_srs = [c.log_speed_ratio for c in s.cycles if c.log_speed_ratio > 0]
    avg_log_sr = sum(log_srs) / len(log_srs) if log_srs else 0.0

    # 最近稳态统计（V1.6 命题 3.4）
    stable_cycles = [c for c in s.cycles if c.has_stable_state]
    avg_resistance = (
        sum(c.next_stable.resistance_level for c in stable_cycles) / len(stable_cycles)
        if stable_cycles else 1.0
    )

    return {
        "cycle_count": s.cycle_count,
        "avg_speed_ratio": s.avg_speed_ratio,       # 速度比：|v_exit| / |v_entry|
        "avg_log_speed_ratio": avg_log_sr,          # 对数速度比：更稳健的比例度量
        "avg_time_ratio": s.avg_time_ratio,         # 时间比：Δt_entry / Δt_exit
        "high_dispersion": extrema_dispersion(highs_above),  # 高点聚集度 (CV)
        "low_dispersion": extrema_dispersion(lows_below),    # 低点聚集度 (CV)
        "high_trend": extrema_trend(highs_above),   # 高点趋势斜率 (归一化)
        "low_trend": extrema_trend(lows_below),     # 低点趋势斜率 (归一化)
        "zone_rel_bw": s.zone.relative_bandwidth,   # 相对带宽：bw / center
        "zone_strength": s.zone.strength,           # 强度：试探次数加权
        # ── V1.6 P0 新增 ──
        "stable_state_ratio": s.stable_state_ratio,  # 已识别稳态的 cycle 占比
        "avg_resistance_level": avg_resistance,      # 平均阻力评分
        "contrast_type": s.zone.context_contrast.value,  # 共同反差类型
    }


# ═══ V1.6 P0 新增算子 ═════════════════════════════════════


def infer_narrative_context(s: Structure) -> str:
    """
    V1.6 命题 2.3: 可叙事性
    基于结构的反差类型、阶段、速度特征生成人可读的叙事背景。
    """
    contrast = s.zone.context_contrast
    contrast_map = {
        ContrastType.PANIC: "恐慌性结构",
        ContrastType.OVERSUPPLY: "供需失衡结构",
        ContrastType.POLICY: "政策驱动结构",
        ContrastType.LIQUIDITY: "流动性驱动结构",
        ContrastType.SPECULATION: "投机驱动结构",
        ContrastType.UNKNOWN: "",
    }
    base = contrast_map.get(contrast, "")

    # 速度特征
    if s.avg_speed_ratio > 1.5:
        speed_desc = "急跌/急涨型"
    elif s.avg_speed_ratio < 0.67:
        speed_desc = "慢跌/慢涨型"
    else:
        speed_desc = "均衡型"

    # 试探次数
    n = s.cycle_count
    if n >= 4:
        freq_desc = f"{n}次密集试探"
    elif n >= 2:
        freq_desc = f"{n}次试探"
    else:
        freq_desc = ""

    parts = [p for p in [base, speed_desc, freq_desc] if p]
    return " · ".join(parts) if parts else "未分类结构"


def check_conservation(
    s: Structure,
    bars: list | None = None,
) -> dict:
    """
    V1.6 命题 4.1-4.2: 差异守恒检查骨架
    当检测到日线级别波动率下降时，检查差异是否转移到其他维度。

    返回守恒状态报告。
    此函数为骨架，完整实现需要 volume / OI / 低频数据。
    """
    result = {
        "conservation_violated": False,
        "transfer_channels": [],
        "notes": [],
    }

    if not s.cycles:
        return result

    # 检查1：速度比是否在收窄（差异被压缩）
    speed_ratios = [c.speed_ratio for c in s.cycles]
    if len(speed_ratios) >= 3:
        first_half = speed_ratios[: len(speed_ratios) // 2]
        second_half = speed_ratios[len(speed_ratios) // 2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if abs(avg_second - avg_first) / max(avg_first, 0.01) > 0.3:
            result["notes"].append(
                f"速度比变化显著: {avg_first:.2f} → {avg_second:.2f}，"
                f"差异可能在转移"
            )

    # 检查2：zone 带宽是否在压缩（波动率被压平）
    if s.zone.relative_bandwidth < 0.01:
        result["notes"].append(
            f"Zone 相对带宽极窄 ({s.zone.relative_bandwidth:.4f})，"
            f"差异可能被转移到更短周期或成交量维度"
        )
        result["transfer_channels"].append("shorter_timeframe")
        result["transfer_channels"].append("volume")

    # 检查3：最近稳态阻力评分是否异常低（容易到达 → 可能是假稳态）
    stable_cycles = [c for c in s.cycles if c.has_stable_state]
    if stable_cycles:
        avg_res = sum(c.next_stable.resistance_level for c in stable_cycles) / len(stable_cycles)
        if avg_res < 0.2:
            result["notes"].append(
                f"最近稳态阻力评分异常低 ({avg_res:.2f})，"
                f"可能是表面稳态，差异正在隐性积累"
            )

    return result


def compute_motion(s: Structure) -> MotionState:
    """
    V1.6「系统 = 结构 × 运动」
    给定一个 Structure（静态骨架），计算它的 MotionState（运动态）。

    运动不是独立于结构的外部输入，而是从结构自身的演化趋势中推导出来的。
    """
    motion = MotionState()
    motion.structural_age = s.cycle_count

    if not s.cycles:
        return motion

    n = len(s.cycles)

    # ── 1. 阶段转换趋势 ──
    # 从最后几个 cycle 的速度比趋势推断下一个阶段
    if n >= 3:
        recent_srs = [c.speed_ratio for c in s.cycles[-3:]]
        sr_trend = recent_srs[-1] - recent_srs[0]

        # 速度比在加速上升 → 可能走向 breakdown
        if sr_trend > 0.5:
            motion.phase_tendency = "→breakdown"
            motion.phase_confidence = min(abs(sr_trend) / 2.0, 1.0)
        # 速度比在收敛 → 走向 confirmation
        elif sr_trend < -0.3:
            motion.phase_tendency = "→confirmation"
            motion.phase_confidence = min(abs(sr_trend) / 1.0, 1.0)
        # 速度比方向反转 → inversion
        elif (recent_srs[0] > 1) != (recent_srs[-1] > 1):
            motion.phase_tendency = "→inversion"
            motion.phase_confidence = 0.7
        else:
            motion.phase_tendency = "stable"
            motion.phase_confidence = 0.5
    elif n >= 1:
        motion.phase_tendency = "forming"
        motion.phase_confidence = 0.3

    # 计算当前阶段已持续的 cycle 数
    current_phase = s.phases[-1] if s.phases else Phase.FORMATION
    phase_count = 0
    for c in reversed(s.phases):
        if c == current_phase:
            phase_count += 1
        else:
            break
    motion.phase_duration = phase_count

    # ── 2. 差异转移流 ──
    # 从守恒检查中提取转移方向
    conservation = s.invariants.get("conservation", {})
    channels = conservation.get("transfer_channels", [])
    if channels:
        motion.transfer_source = "zone_bandwidth"
        motion.transfer_target = channels[0]
        motion.transfer_strength = 0.5 if len(channels) == 1 else 0.8

    # ── 3. 稳态趋近 ──
    stable_cycles = [c for c in s.cycles if c.has_stable_state]
    if stable_cycles:
        # 平均阻力评分 = 距稳态的归一化距离
        avg_resistance = sum(c.next_stable.resistance_level for c in stable_cycles) / len(stable_cycles)
        motion.stable_distance = avg_resistance

        # 稳态速度: 从最近两个有稳态的 cycle 的阻力变化推断
        if len(stable_cycles) >= 2:
            r_prev = stable_cycles[-2].next_stable.resistance_level
            r_curr = stable_cycles[-1].next_stable.resistance_level
            motion.stable_velocity = r_prev - r_curr  # 正值=在靠近
    else:
        motion.stable_distance = 1.0  # 未识别到稳态 = 距离最远

    # ── 4. 守恒通量 ──
    if n >= 2:
        first_half_srs = [c.speed_ratio for c in s.cycles[:n // 2]]
        second_half_srs = [c.speed_ratio for c in s.cycles[n // 2:]]
        avg_first = sum(first_half_srs) / len(first_half_srs)
        avg_second = sum(second_half_srs) / len(second_half_srs)

        # 正通量 = 速度比上升 = 差异在释放
        # 负通量 = 速度比下降 = 差异在压缩
        motion.conservation_flux = avg_second - avg_first

        if motion.conservation_flux > 0.3:
            motion.flux_detail = f"差异释放中 (sr {avg_first:.2f}→{avg_second:.2f})"
        elif motion.conservation_flux < -0.3:
            motion.flux_detail = f"差异压缩中 (sr {avg_first:.2f}→{avg_second:.2f})"
        else:
            motion.flux_detail = "差异平衡"

    return motion
