"""
关系算子层 — 不存储，纯计算
所有"点间/段间/结构间"的关系在这里定义

V1.6 P0 新增：
- infer_narrative_context: 结构叙事背景推断（V1.6 命题 2.3 可叙事性）
- check_conservation: 差异守恒检查骨架（V1.6 命题 4.1-4.2）

V1.6 P1 新增：
- compute_liquidity_stress: 流动性差异度量（D6.3）
- compute_fear_index: 边界恐惧度量（D6.4）
- compute_time_compression: 时间差异度量（D6.2）
- detect_stability_illusion: 错觉检测（D7.2）
- build_system_state: 系统态构建（D9.1）
"""

from __future__ import annotations
import math
from typing import Sequence
from src.models import (
    Point, Segment, Zone, Cycle, Structure, ContrastType,
    MotionState, Phase, ProjectionAwareness,
    StabilityVerdict, SystemState,
    # 复用 models.py 中定义的基础算子
    time_gap, extrema_dispersion,
)

# 向后兼容别名
time_gap_days = time_gap

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


# ─── 极值点聚集度（新增：trend）─────────────────────────────
# extrema_dispersion 已从 models.py 导入，不重复定义

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
    V1.6 命题 2.3: 可叙事性 — v2.5 增强版

    基于结构的反差类型、阶段、速度特征、运动态、守恒状态，
    生成人可读的多维度叙事背景。

    v2.5: 增加运动态描述、守恒通量描述、稳定性描述。
    """
    parts = []

    # ── 维度 1: 反差类型 ──
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
    if base:
        parts.append(base)

    # ── 维度 2: 速度特征 ──
    if s.avg_speed_ratio > 1.5:
        parts.append("急跌/急涨型")
    elif s.avg_speed_ratio < 0.67:
        parts.append("慢跌/慢涨型")
    else:
        parts.append("均衡型")

    # ── 维度 3: 试探次数 + 密集度 ──
    n = s.cycle_count
    if n >= 5:
        parts.append(f"{n}次密集试探")
    elif n >= 3:
        parts.append(f"{n}次试探")
    elif n >= 2:
        parts.append(f"{n}次试探")

    # ── 维度 4: 运动态 (v2.5 新增) ──
    if s.motion:
        if s.motion.phase_tendency:
            tendency_map = {
                "→breakdown": "趋向破坏",
                "→confirmation": "趋向确认",
                "→inversion": "趋向反演",
                "stable": "稳态运行",
                "forming": "形成中",
            }
            desc = tendency_map.get(s.motion.phase_tendency, "")
            if desc:
                parts.append(desc)

        if abs(s.motion.conservation_flux) > 0.3:
            if s.motion.conservation_flux > 0:
                parts.append("差异释放中")
            else:
                parts.append("差异压缩中")

    # ── 维度 5: 稳定性状态 (v2.5 新增) ──
    if s.stability_verdict:
        if s.stability_verdict.surface == "stable" and not s.stability_verdict.verified:
            parts.append("表面稳定待验证")
        elif s.stability_verdict.surface == "unstable":
            parts.append("不稳定")

    # ── 维度 6: 投影觉知 (v2.5 新增) ──
    if s.projection and s.projection.is_blind:
        parts.append("⚠️高压缩")

    return " · ".join(parts) if parts else "未分类结构"


def check_conservation(
    s: Structure,
    bars: list | None = None,
) -> dict:
    """
    差异守恒检查 — v2.5 影子层版

    核心命题（V1.6 Ch4）：
      差异不能被无代价清零，只能转移。

    投影层注意：
      价格 = Π(现实差异)，Π 有损、不可逆、非线性、时变。
      系统在影子层工作，不能从影子反推实体。
      守恒的正确表述：当价格结构的某些特征被压缩时，
      另一些特征会补偿性变化。

    影子层守恒检测：
      不声称"差异转到了某社会差异维度"
      只观测"价格特征A被压缩时，价格特征B是否在补偿性变化"
    """
    result = {
        "conservation_violated": False,
        "transfer_channels": [],      # 目标维度: ["shorter_timeframe", "volume", ...]
        "compensation_signals": [],   # 补偿性变化: ["speed_ratio_expanding", ...]
        "notes": [],
        "flux_score": 0.0,
        "channel_scores": {},
    }

    if not s.cycles:
        return result

    n = len(s.cycles)
    flux_signals = []

    # ── 第一步：检测价格差异是否在被压缩 ──
    price_compressed = False

    # 1a. Zone 带宽压缩
    # v3.2: 与 compute_projection 阈值对齐 (0.8%/1.5%/3%)
    bw = s.zone.relative_bandwidth
    if bw < 0.008:        # 0.8% → 极窄
        price_compressed = True
        result["channel_scores"]["zone_bandwidth"] = -1.0
        flux_signals.append(-0.5)
        result["notes"].append(f"Zone 相对带宽极窄 ({bw:.4f})，价格差异被压缩")
    elif bw < 0.015:     # 1.5% → 窄
        price_compressed = True
        result["channel_scores"]["zone_bandwidth"] = -0.5
        flux_signals.append(-0.3)
        result["notes"].append(f"Zone 相对带宽窄 ({bw:.4f})，价格差异被压缩")
    elif bw < 0.03:      # 3% → 轻度
        result["channel_scores"]["zone_bandwidth"] = -0.2
        flux_signals.append(-0.1)
    else:
        result["channel_scores"]["zone_bandwidth"] = 0.0

    # 1b. 速度比收敛
    if n >= 3:
        speed_ratios = [c.speed_ratio for c in s.cycles]
        first_half = speed_ratios[: n // 2]
        second_half = speed_ratios[n // 2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        sr_change = (avg_second - avg_first) / max(avg_first, 0.01)
        result["channel_scores"]["speed_ratio"] = sr_change
        flux_signals.append(sr_change)

        if sr_change < -0.3:
            price_compressed = True
            result["notes"].append(
                f"速度比收窄: {avg_first:.2f} → {avg_second:.2f}，差异在压缩"
            )

    # 1c. 振幅衰减
    if n >= 3:
        recent_deltas = [c.exit.abs_delta for c in s.cycles[-3:]]
        early_deltas = [c.exit.abs_delta for c in s.cycles[:3]]
        if early_deltas and recent_deltas:
            avg_early = sum(early_deltas) / len(early_deltas)
            avg_recent = sum(recent_deltas) / len(recent_deltas)
            if avg_early > 0:
                amp_decay = avg_recent / avg_early
                result["channel_scores"]["amplitude_decay"] = amp_decay
                if amp_decay < 0.5:
                    price_compressed = True
                    flux_signals.append(-0.3)
                    result["notes"].append(f"振幅衰减 ({amp_decay:.2f})，价格差异在压缩")

    # ── 第二步：如果价格被压缩，检查其他价格特征是否在补偿性变化 ──
    if price_compressed:
        compensations = []      # 补偿性变化信号
        target_channels = []    # 差异可能转移到的目标维度

        # 检查速度比是否在扩张（与带宽压缩相反方向）
        if n >= 3:
            sr = result["channel_scores"].get("speed_ratio", 0)
            if sr > 0.3:
                compensations.append("speed_ratio_expanding")
                result["notes"].append(
                    f"速度比在扩张 ({sr:+.2f})，价格差异在重新分配"
                )

        # 检查时间比是否在变化
        entry_durs = [c.entry.duration for c in s.cycles if c.entry.duration > 0]
        exit_durs = [c.exit.duration for c in s.cycles if c.exit.duration > 0]
        if entry_durs and exit_durs:
            avg_entry = sum(entry_durs) / len(entry_durs)
            avg_exit = sum(exit_durs) / len(exit_durs)
            if avg_exit > 0:
                time_ratio = avg_entry / avg_exit
                result["channel_scores"]["time_ratio"] = time_ratio
                if time_ratio > 1.5:
                    compensations.append("time_ratio_asymmetric")
                    result["notes"].append(
                        f"时间比不对称 ({time_ratio:.1f})，进出节奏在重新分配"
                    )
                elif time_ratio < 0.67:
                    compensations.append("time_ratio_inverse")
                    result["notes"].append(
                        f"时间比反转 ({time_ratio:.1f})，进出节奏在重新分配"
                    )

        # 检查试探密度是否在加速
        if n >= 4 and s.t_start and s.t_end:
            mid_point = s.t_start + (s.t_end - s.t_start) / 2
            first_half_cycles = [c for c in s.cycles if c.entry.start.t <= mid_point]
            second_half_cycles = [c for c in s.cycles if c.entry.start.t > mid_point]
            if first_half_cycles and second_half_cycles:
                first_span = max((mid_point - s.t_start).days, 1)
                second_span = max((s.t_end - mid_point).days, 1)
                density_first = len(first_half_cycles) / first_span
                density_second = len(second_half_cycles) / second_span
                if density_first > 0:
                    density_ratio = density_second / density_first
                    result["channel_scores"]["touch_density"] = density_ratio
                    if density_ratio > 1.5:
                        compensations.append("density_accelerating")
                        result["notes"].append(
                            f"试探密度加速 ({density_ratio:.1f}x)，差异在重新分配"
                        )

        # 将补偿性变化映射到目标维度
        # 语义: transfer_channels = 差异可能去了哪（目标维度）
        #       compensation_signals = 价格层看到了什么变化（观测信号）
        if any(s in c for c in compensations for s in ["speed_ratio_expanding", "density_accelerating"]):
            target_channels.append("shorter_timeframe")
        if "time_ratio_asymmetric" in compensations or "time_ratio_inverse" in compensations:
            target_channels.append("volume")

        result["compensation_signals"] = compensations
        result["transfer_channels"] = target_channels

        # 如果价格被压缩但没有任何补偿性变化
        if not compensations:
            result["notes"].append(
                "价格差异被压缩，但其他价格特征未见补偿性变化——"
                "可能真正稳定，也可能差异转到了影子层看不到的地方"
            )
        else:
            result["notes"].append(
                f"价格差异被压缩，但 {len(compensations)} 个特征在补偿性变化——"
                f"结构正在重新分配差异，不是真正变平"
            )

    # ── 第三步：综合守恒通量 ──
    if flux_signals:
        result["flux_score"] = sum(flux_signals) / len(flux_signals)
        result["conservation_violated"] = abs(result["flux_score"]) > 0.3

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

    # ── 1. 阶段转换趋势（多信号投票）──
    # V1.6 Ch5: 阶段转换应考虑 Zone 完整性、试探密集度、守恒通量、稳态距离
    if n >= 3:
        votes: dict[str, float] = {}  # tendency → confidence 累计

        # 信号 A: 速度比趋势（权重 0.35）
        recent_srs = [c.speed_ratio for c in s.cycles[-3:]]
        sr_trend = recent_srs[-1] - recent_srs[0]
        if sr_trend > 0.5:
            votes["→breakdown"] = votes.get("→breakdown", 0) + 0.35 * min(sr_trend / 2.0, 1.0)
        elif sr_trend < -0.3:
            votes["→confirmation"] = votes.get("→confirmation", 0) + 0.35 * min(abs(sr_trend) / 1.0, 1.0)
        elif (recent_srs[0] > 1) != (recent_srs[-1] > 1):
            votes["→inversion"] = votes.get("→inversion", 0) + 0.35 * 0.7
        else:
            votes["stable"] = votes.get("stable", 0) + 0.35 * 0.5

        # 信号 B: 试探密集度加速（权重 0.25）
        if n >= 4 and s.t_start and s.t_end:
            mid = s.t_start + (s.t_end - s.t_start) / 2
            first_half = [c for c in s.cycles if c.entry.start.t <= mid]
            second_half = [c for c in s.cycles if c.entry.start.t > mid]
            if first_half and second_half:
                span1 = max((mid - s.t_start).days, 1)
                span2 = max((s.t_end - mid).days, 1)
                density_ratio = (len(second_half) / span2) / max(len(first_half) / span1, 1e-9)
                if density_ratio > 1.5:
                    # 密集度加速 → 可能走向 breakdown
                    votes["→breakdown"] = votes.get("→breakdown", 0) + 0.25 * min(density_ratio / 3.0, 1.0)
                elif density_ratio < 0.67:
                    # 密集度放缓 → 走向 confirmation
                    votes["→confirmation"] = votes.get("→confirmation", 0) + 0.25 * 0.5
                else:
                    votes["stable"] = votes.get("stable", 0) + 0.25 * 0.4

        # 信号 C: Zone 带宽变化趋势（权重 0.20）
        # 如果最近 cycle 的 exit 段离 zone 越来越远 → breakdown
        if n >= 3:
            recent_exits = [c.exit for c in s.cycles[-3:]]
            zone = s.zone
            exit_distances = [abs(e.end.x - zone.price_center) / max(zone.bandwidth, 1e-9) for e in recent_exits]
            dist_trend = exit_distances[-1] - exit_distances[0]
            if dist_trend > 1.0:
                votes["→breakdown"] = votes.get("→breakdown", 0) + 0.20 * min(dist_trend / 3.0, 1.0)
            elif dist_trend < -0.5:
                votes["→confirmation"] = votes.get("→confirmation", 0) + 0.20 * 0.4

        # 信号 D: 守恒通量方向（权重 0.20）
        conservation = s.invariants.get("conservation", {})
        flux = conservation.get("flux_score", 0.0)
        if abs(flux) > 0.3:
            if flux < -0.3:
                # 差异压缩 → 走向 confirmation 或稳定
                votes["→confirmation"] = votes.get("→confirmation", 0) + 0.20 * min(abs(flux), 1.0)
            elif flux > 0.3:
                # 差异释放 → 可能走向 breakdown
                votes["→breakdown"] = votes.get("→breakdown", 0) + 0.20 * min(flux, 1.0)
        else:
            votes["stable"] = votes.get("stable", 0) + 0.20 * 0.3

        # 投票决定
        if votes:
            best_tendency = max(votes, key=votes.get)
            motion.phase_tendency = best_tendency
            motion.phase_confidence = min(votes[best_tendency], 1.0)
        else:
            motion.phase_tendency = "stable"
            motion.phase_confidence = 0.3

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
    # v3.2: 复用 check_conservation 的 flux_score，避免重复计算导致不一致
    conservation = s.invariants.get("conservation")
    if conservation is None:
        conservation = check_conservation(s)
    flux_score = conservation.get("flux_score", 0.0)

    # flux_score 已综合多信号（带宽压缩+速度比变化+振幅衰减）
    # 正通量 = 差异在释放，负通量 = 差异在压缩
    motion.conservation_flux = flux_score

    if motion.conservation_flux > 0.3:
        motion.flux_detail = f"差异释放中 (flux={flux_score:+.2f})"
    elif motion.conservation_flux < -0.3:
        motion.flux_detail = f"差异压缩中 (flux={flux_score:+.2f})"
    else:
        motion.flux_detail = "差异平衡"

    return motion


def compute_projection(s: Structure, bars: list | None = None) -> ProjectionAwareness:
    """
    D0 章：投影觉知 + v2.5 D0.3 深化
    价格 = Π(现实差异)，系统分析的是影子。
    此函数评估当前影子的可信度，标记盲区，给出可操作建议。
    """
    proj = ProjectionAwareness()

    if not s.cycles:
        return proj

    # ── 1. 压缩度 ──
    # v3.2: 放宽阈值，适配期货数据特征
    # 原阈值过于严格（<0.5%才触发高压缩），期货品种很少达到
    bw = s.zone.relative_bandwidth
    if bw < 0.008:      # 0.8% → 高压缩
        proj.compression_level = 0.9
    elif bw < 0.015:    # 1.5% → 中等压缩
        proj.compression_level = 0.7
    elif bw < 0.03:     # 3% → 轻度压缩
        proj.compression_level = 0.4
    else:
        proj.compression_level = 0.1

    # ── 2. 盲区通道 ──
    conservation = s.invariants.get("conservation", {})
    channels = conservation.get("transfer_channels", [])
    blind = list(channels)

    if proj.compression_level > 0.6:
        if "shorter_timeframe" not in blind:
            blind.append("shorter_timeframe")
        if "volume" not in blind:
            blind.append("volume")

    proj.blind_channels = blind

    # ── 3. 投影可信度 ──
    n = s.cycle_count
    history_confidence = min(n / 5.0, 1.0)
    compression_penalty = proj.compression_level * 0.3
    proj.projection_confidence = max(history_confidence - compression_penalty, 0.1)

    # ── 4. 人可读观测 ──
    parts = []
    if proj.is_blind:
        parts.append(f"⚠️ 高压缩({proj.compression_level:.0%})，影子可能不代表实体")
        parts.append(f"差异可能藏在: {', '.join(blind)}")
    else:
        parts.append(f"投影压缩度{proj.compression_level:.0%}，可信度{proj.projection_confidence:.0%}")

    proj.observation = " | ".join(parts)

    # ── 5. v2.5: 推荐行动 ──
    actions = []
    evidence = {}

    if proj.compression_level > 0.6:
        actions.append(f"⚠️ Zone 带宽极窄({bw:.1%})，差异可能在其他维度积累")
        if "shorter_timeframe" in blind:
            actions.append("建议：检查更短周期的波动率是否在上升")
            evidence["shorter_timeframe"] = "日线 Zone 带宽压缩，待验证短周期"
        if "volume" in blind:
            actions.append("检查：成交量变异系数是否在放大")
            evidence["volume"] = f"Zone 相对带宽 {bw:.4f}，流动性维度待验证"

    # 从守恒检查提取证据
    flux = conservation.get("flux_score", 0.0)
    if abs(flux) > 0.3:
        direction = "释放" if flux > 0 else "压缩"
        actions.append(f"守恒通量 {flux:+.2f}：差异正在{direction}")
        channel_scores = conservation.get("channel_scores", {})
        for ch, score in channel_scores.items():
            if abs(score) > 0.3:
                evidence[ch] = f"通道异常值 {score:.2f}"

    # 稳态阻力异常
    stable_cycles = [c for c in s.cycles if c.has_stable_state]
    if stable_cycles:
        avg_res = sum(c.next_stable.resistance_level for c in stable_cycles) / len(stable_cycles)
        if avg_res < 0.2:
            actions.append(f"⚠️ 稳态阻力异常低({avg_res:.2f})，可能是假稳态")
            evidence["stable_state"] = f"平均阻力 {avg_res:.2f}，差异可能在隐性积累"

    proj.recommended_actions = actions
    proj.blind_evidence = evidence

    return proj


# ═══ V1.6 P1 新增算子 ═════════════════════════════════════


def compute_liquidity_stress(
    s: Structure,
    bars: list | None = None,
) -> float:
    """
    V1.6 D6.3: 流动性差异度量
    流动性差异 = 能不能把价格变成钱

    通过 Zone 内外成交量变异系数比值衡量：
    > 1.5 → 差异在释放（多空激烈交锋）
    < 0.5 → 差异被压缩（流动性枯竭）
    """
    if not bars or not s.cycles:
        return 0.0

    zone_lower = s.zone.price_center - s.zone.bandwidth
    zone_upper = s.zone.price_center + s.zone.bandwidth

    volumes_in = []
    volumes_out = []

    for bar in bars:
        if zone_lower <= bar.close <= zone_upper:
            volumes_in.append(bar.volume)
        else:
            volumes_out.append(bar.volume)

    if len(volumes_in) < 5 or len(volumes_out) < 5:
        return 0.0

    def cv(vals: list[float]) -> float:
        m = sum(vals) / len(vals)
        if m == 0:
            return 0.0
        var = sum((v - m) ** 2 for v in vals) / len(vals)
        return math.sqrt(var) / m

    cv_in = cv(volumes_in)
    cv_out = cv(volumes_out)

    if cv_out < 0.01:
        return 0.0

    return round(cv_in / cv_out, 4)


def compute_fear_index(
    s: Structure,
    bars: list | None = None,
) -> float:
    """
    V1.6 D6.4: 边界恐惧度量
    怕被踢出局的紧张程度

    由三部分加权：
    - 价格跳空频率（35%）
    - 波动率突变（35%）
    - Zone 试探密集度（30%）
    """
    if not bars or len(bars) < 10:
        return 0.0

    # 1. 跳空频率（最近 30 根 bar）
    recent = bars[-30:]
    gaps = 0
    for i in range(1, len(recent)):
        gap = abs(recent[i].open - recent[i - 1].close) / max(recent[i - 1].close, 1e-9)
        if gap > 0.005:  # > 0.5% 的跳空
            gaps += 1
    gap_freq = gaps / max(len(recent) - 1, 1)

    # 2. 波动率突变（最近 10 根 vs 之前 20 根的波动率比）
    if len(bars) >= 30:
        def daily_range_pct(b) -> float:
            return (b.high - b.low) / max(b.close, 1e-9)

        recent_vol = [daily_range_pct(b) for b in bars[-10:]]
        prev_vol = [daily_range_pct(b) for b in bars[-30:-10]]
        avg_recent = sum(recent_vol) / len(recent_vol)
        avg_prev = sum(prev_vol) / len(prev_vol)
        vol_spike = avg_recent / max(avg_prev, 1e-9) if avg_prev > 0 else 1.0
    else:
        vol_spike = 1.0

    # 3. 试探密集度（cycle 数 / 时间跨度天数）
    if s.cycles and s.t_start and s.t_end:
        span_days = max((s.t_end - s.t_start).days, 1)
        touch_intensity = s.cycle_count / span_days * 30  # 标准化为月频
    else:
        touch_intensity = 0.0

    # 加权合成
    fear = 0.35 * min(gap_freq * 10, 1.0) + 0.35 * min(max(vol_spike - 1, 0), 1.0) + 0.30 * min(touch_intensity, 1.0)
    return round(min(fear, 1.0), 4)


def compute_time_compression(s: Structure) -> float:
    """
    V1.6 D6.2: 时间差异度量
    时间差异 = 谁能等、谁不能等

    = avg_entry_duration / avg_exit_duration
    > 1.5 → 入场慢出场快 = 恐慌性退出 = 时间差异剧烈
    < 0.67 → 入场快出场慢 = 缓慢消化 = 时间差异平缓
    """
    if not s.cycles:
        return 0.0

    entry_durs = [c.entry.duration for c in s.cycles if c.entry.duration > 0]
    exit_durs = [c.exit.duration for c in s.cycles if c.exit.duration > 0]

    if not entry_durs or not exit_durs:
        return 0.0

    avg_entry = sum(entry_durs) / len(entry_durs)
    avg_exit = sum(exit_durs) / len(exit_durs)

    if avg_exit == 0:
        return 0.0

    return round(avg_entry / avg_exit, 4)


def detect_stability_illusion(
    s: Structure,
    bars: list | None = None,
) -> StabilityVerdict:
    """
    V1.6 D7.2 命题 7.4: 错觉检测
    系统不应在波动率下降时立即报告"结构稳定"。
    表面变平 ≠ 真的稳定，差异可能转移到了其他维度。
    """
    verdict = StabilityVerdict()

    if not s.cycles:
        return verdict

    # ── 判断表面稳定性 ──
    bw = s.zone.relative_bandwidth
    is_surface_stable = bw < 0.015  # 相对带宽 < 1.5%

    if not is_surface_stable:
        verdict.surface = "unstable"
        verdict.verdict_label = verdict.traffic_light
        return verdict

    # ── 表面稳定，进入验证 ──
    verdict.surface = "stable"

    # 待验证通道
    pending = []

    # 检查1：速度比是否在收窄（差异被压缩 → 转移风险）
    if s.cycles and len(s.cycles) >= 3:
        recent_srs = [c.speed_ratio for c in s.cycles[-3:]]
        sr_cv = _safe_cv(recent_srs)
        if sr_cv < 0.2:
            # 速度比高度一致 → 可能只是表面收敛
            pending.append("shorter_timeframe")
            pending.append("volume")

    # 检查2：守恒检查是否有转移警告（目标维度）
    conservation = s.invariants.get("conservation", {})
    transfer_channels = conservation.get("transfer_channels", [])
    for ch in transfer_channels:
        if ch not in pending:
            pending.append(ch)
    # 兼容旧格式：compensation_signals 中的映射到目标维度
    compensation = conservation.get("compensation_signals", [])
    for sig in compensation:
        if "speed_ratio" in sig or "density" in sig:
            if "shorter_timeframe" not in pending:
                pending.append("shorter_timeframe")
        if "time_ratio" in sig:
            if "volume" not in pending:
                pending.append("volume")

    # 检查3：最近稳态阻力评分异常低 → 可能是假稳态
    stable_cycles = [c for c in s.cycles if c.has_stable_state]
    if stable_cycles:
        avg_res = sum(c.next_stable.resistance_level for c in stable_cycles) / len(stable_cycles)
        if avg_res < 0.2:
            pending.append("stable_state_validation")

    # 检查4：投影觉知高压缩
    if s.projection and s.projection.is_blind:
        pending.append("projection_blind")

    if pending:
        verdict.verified = False
        verdict.pending_channels = pending
        verdict.verification_window = 20  # 20天观察期
        verdict.verdict_label = verdict.traffic_light
    else:
        verdict.verified = True
        verdict.verdict_label = verdict.traffic_light

    return verdict


def safe_cv(vals: list[float]) -> float:
    """安全计算变异系数（公开函数，供其他模块复用）"""
    from src.utils import safe_cv as _cv
    return _cv(vals)


# 向后兼容别名
_safe_cv = safe_cv


def build_system_state(
    s: Structure,
    bars: list | None = None,
) -> SystemState:
    """
    V1.6 D9.1: 系统态构建
    System = Structure × Motion
    顶层封装函数，将所有分散的计算统一为一个 SystemState。

    ⚠️ 副作用：此函数会原地修改 Structure 对象的以下字段：
      - s.motion (如果为 None)
      - s.projection (如果为 None)
      - s.invariants["conservation"] (如果为 None)
      - s.liquidity_stress
      - s.fear_index
      - s.time_compression
      - s.stability_verdict
    这是设计选择：Structure 作为数据+状态的容器，
    build_system_state 确保其运动态字段被填充。
    """
    # 确保 motion / projection / conservation 已计算
    if s.motion is None:
        s.motion = compute_motion(s)
    if s.projection is None:
        s.projection = compute_projection(s, bars)

    conservation = s.invariants.get("conservation")
    if conservation is None:
        conservation = check_conservation(s, bars)
        s.invariants["conservation"] = conservation

    # 差异分层
    liq = compute_liquidity_stress(s, bars)
    fear = compute_fear_index(s, bars)
    tcomp = compute_time_compression(s)

    # 错觉检测
    stability = detect_stability_illusion(s, bars)

    # 更新 Structure 上的字段
    s.liquidity_stress = liq
    s.fear_index = fear
    s.time_compression = tcomp
    s.stability_verdict = stability

    return SystemState(
        structure=s,
        motion=s.motion,
        projection=s.projection,
        stability=stability,
        liquidity_stress=liq,
        fear_index=fear,
        time_compression=tcomp,
    )
