"""
交易信号层 — 基于差异论V1.6的信号判断模块

职责：
    - 基于现有扫描数据生成交易信号
    - 不发起额外市场数据请求
    - 独立于扫描逻辑

核心设计原则（来自4视角头脑风暴交集）：
    1. conservation_flux 必须参与所有信号过滤
    2. stability_verdict 红灯覆盖方向性判断
    3. 假突破判定关键 = flux方向与价格突破方向相反
    4. 信号优先级：假突破反向 > 突破确认 > 回踩确认 > 结构老化
"""

from __future__ import annotations

import statistics
from typing import List, Optional, Tuple

from src.data.loader import Bar
from src.models import (
    FakeBreakoutPattern,
    MotionState,
    ProjectionAwareness,
    Signal,
    SignalKind,
    StabilityVerdict,
    Structure,
    SystemState,
)


# ═══════════════════════════════════════════════════════════
# 常量配置
# ═══════════════════════════════════════════════════════════

# 假突破检测阈值
FAKE_PENETRATION_THRESHOLD = 0.3  # 穿透幅度阈值 (× bandwidth)
FAKE_VOLUME_CLIMIX = 1.5  # 量能峰值倍数
FAKE_VOLUME_DIV = 0.8  # 量能萎缩阈值
FAKE_FLUX_WEAK = 0.3  # 弱通量阈值
FAKE_SHADOW_RATIO = 2.0  # 影线/实体比

# 突破评分阈值
BREAKOUT_STRONG = 0.80
BREAKOUT_WEAK = 0.55

# 结构老化阈值
AGING_DAYS_THRESHOLD = 14


# ═══════════════════════════════════════════════════════════
# 止损/目标/盈亏比计算
# ═══════════════════════════════════════════════════════════

def _compute_risk_reward(
    direction: str,
    entry_price: float,
    upper: float,
    lower: float,
    bandwidth: float,
) -> tuple[float, float, float]:
    """
    计算止损价、目标价、盈亏比。

    Returns:
        (stop_loss_price, take_profit_price, rr_ratio)
    """
    if bandwidth <= 0 or entry_price <= 0:
        return 0.0, 0.0, 0.0

    if direction == "long":
        # 止损: Zone 下沿 - 0.3×bandwidth（给一点缓冲）
        stop_loss = lower - 0.3 * bandwidth
        # 目标: Zone 上沿 + 1×bandwidth（突破后等幅测量）
        take_profit = upper + bandwidth
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
    elif direction == "short":
        # 止损: Zone 上沿 + 0.3×bandwidth
        stop_loss = upper + 0.3 * bandwidth
        # 目标: Zone 下沿 - 1×bandwidth
        take_profit = lower - bandwidth
        risk = stop_loss - entry_price
        reward = entry_price - take_profit
    else:
        return 0.0, 0.0, 0.0

    if risk <= 0:
        return stop_loss, take_profit, 0.0

    rr = reward / risk
    return round(stop_loss, 2), round(take_profit, 2), round(rr, 2)


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def generate_signal(
    structure: Structure,
    bars: List[Bar],
    system_state: Optional[SystemState] = None,
    quality_tier_override: Optional[str] = None,
) -> Optional[Signal]:
    """
    为给定结构生成交易信号

    逻辑流程:
        1. 前置过滤（质量层D/红灯）
        2. 检测假突破5模式（优先级最高）
        3. 检测突破确认
        4. 检测回踩确认
        5. 检测结构老化
        6. 返回最高优先级信号

    Args:
        structure: 价格结构
        bars: K线序列（至少包含最近20根）
        system_state: 系统状态（可选，用于获取motion/projection等）
        quality_tier_override: 外部传入的质量层（避免重复计算，优先使用）

    Returns:
        Signal对象或None（无有效信号）
    """
    if not bars:
        return None

    # 提取辅助信息（修复：处理 ss 存在但属性为 None 的情况）
    ss = system_state
    motion = ss.motion if ss and ss.motion else MotionState()
    projection = ss.projection if ss and ss.projection else ProjectionAwareness()
    stability = ss.stability if ss and ss.stability else StabilityVerdict()

    # 获取质量层（v3.2: 优先使用外部传入，避免与 tab_scan.py 重复计算导致不一致）
    if quality_tier_override:
        quality_tier = quality_tier_override
    else:
        from src.quality import assess_quality
        qa = assess_quality(structure, ss)
        quality_tier = qa.tier.value

    # 前置过滤：质量层D不生成信号
    if quality_tier == "D":
        return None

    # 提取最新价格和Zone信息
    last_bar = bars[-1]
    last_close = last_bar.close
    upper = structure.zone.upper if structure.zone else 0
    lower = structure.zone.lower if structure.zone else 0
    bandwidth = structure.zone.bandwidth if structure.zone else 0
    center = (upper + lower) / 2 if bandwidth > 0 else last_close

    # 确定当前价格相对于Zone的位置
    if last_close > upper:
        price_position = "above"
        direction = "long"
    elif last_close < lower:
        price_position = "below"
        direction = "short"
    else:
        price_position = "inside"
        direction = "neutral"

    # 获取flux信息
    flux = motion.conservation_flux if motion else 0.0
    flux_aligned = (flux > 0 and direction == "long") or (flux < 0 and direction == "short")

    # 检查stability_verdict
    # v3.2 修复: StabilityVerdict.surface 只有 "stable"/"unstable" 两个值
    # 红灯 = unstable 或 stable 但未验证(黄灯)
    # 稳定且已验证 = 绿灯，才认为 stability_ok
    stability_ok = stability.surface == "stable" and stability.verified
    is_blind = projection.is_blind if projection else False

    # ═══════════════════════════════════════════════════════
    # 信号检测（按优先级顺序）
    # ═══════════════════════════════════════════════════════

    candidates: List[Signal] = []

    # 1. 假突破检测（最高优先级）
    is_fake, fake_pattern, fake_conf = detect_fake_breakout(structure, bars, ss)
    if is_fake and fake_pattern:
        # 假突破反向信号
        reverse_direction = "short" if price_position == "above" else "long" if price_position == "below" else "neutral"
        fake_flux_aligned = (flux > 0 and reverse_direction == "long") or (flux < 0 and reverse_direction == "short")

        sl, tp, rr = _compute_risk_reward(reverse_direction, last_close, upper, lower, bandwidth)

        sig = Signal(
            kind=SignalKind.FAKE_BREAKOUT,
            direction=reverse_direction,
            confidence=min(fake_conf * 0.9, 0.95),
            flux_aligned=fake_flux_aligned,
            stability_ok=stability_ok,
            entry_note=f"假突破·{fake_pattern.name}: 价格{'上' if price_position == 'above' else '下'}穿后回归，flux反向确认",
            fake_pattern=fake_pattern,
            quality_tier=quality_tier,
            is_blind=is_blind,
            days_since_formation=motion.structural_age if motion else 0,
            stop_loss_hint=f"止损 {sl:.1f}" if sl else "",
            stop_loss_price=sl,
            take_profit_price=tp,
            rr_ratio=rr,
            position_size_factor=calculate_position_factor(quality_tier, is_blind),
        )
        candidates.append(sig)

    # 2. 突破确认检测
    breakout_score, breakout_note = score_breakout_confirmation(structure, bars, ss)
    if breakout_score >= BREAKOUT_WEAK and price_position != "inside":
        # 根据评分确定置信度
        if breakout_score >= BREAKOUT_STRONG:
            conf = 0.85 + (breakout_score - BREAKOUT_STRONG) * 0.5  # 0.85-0.95
        else:
            conf = 0.60 + (breakout_score - BREAKOUT_WEAK) / (BREAKOUT_STRONG - BREAKOUT_WEAK) * 0.25  # 0.60-0.85

        # stability红灯封顶
        if not stability_ok:
            conf = min(conf, 0.50)

        # 盲区降级
        if is_blind:
            conf *= 0.6

        sl, tp, rr = _compute_risk_reward(direction, last_close, upper, lower, bandwidth)

        sig = Signal(
            kind=SignalKind.BREAKOUT_CONFIRM,
            direction=direction,
            confidence=min(conf, 0.95),
            flux_aligned=flux_aligned,
            stability_ok=stability_ok,
            entry_note=f"突破确认: {breakout_note}",
            breakout_score=breakout_score,
            quality_tier=quality_tier,
            is_blind=is_blind,
            days_since_formation=motion.structural_age if motion else 0,
            stop_loss_hint=f"止损 {sl:.1f}" if sl else "",
            stop_loss_price=sl,
            take_profit_price=tp,
            rr_ratio=rr,
            position_size_factor=calculate_position_factor(quality_tier, is_blind),
        )
        candidates.append(sig)

    # 3. 回踩确认检测
    is_pullback, pullback_conf, pullback_note = detect_pullback_confirmation(structure, bars, ss)
    if is_pullback:
        conf = pullback_conf
        if not stability_ok:
            conf = min(conf, 0.50)
        if is_blind:
            conf *= 0.6

        sl, tp, rr = _compute_risk_reward(direction, last_close, upper, lower, bandwidth)

        sig = Signal(
            kind=SignalKind.PULLBACK_CONFIRM,
            direction=direction,
            confidence=min(conf, 0.90),
            flux_aligned=flux_aligned,
            stability_ok=stability_ok,
            entry_note=f"回踩确认: {pullback_note}",
            quality_tier=quality_tier,
            is_blind=is_blind,
            days_since_formation=motion.structural_age if motion else 0,
            stop_loss_hint=f"止损 {sl:.1f}" if sl else "",
            stop_loss_price=sl,
            take_profit_price=tp,
            rr_ratio=rr,
            position_size_factor=calculate_position_factor(quality_tier, is_blind) * 0.9,
        )
        candidates.append(sig)

    # 4. 盲区突破观察（当is_blind且价格突破时）
    if is_blind and price_position != "inside":
        conf = 0.50
        if flux_aligned:
            conf += 0.15

        sl, tp, rr = _compute_risk_reward(direction, last_close, upper, lower, bandwidth)

        sig = Signal(
            kind=SignalKind.BLIND_BREAKOUT,
            direction=direction,
            confidence=min(conf, 0.70),
            flux_aligned=flux_aligned,
            stability_ok=stability_ok,
            entry_note="盲区突破: 价格进入投影盲区，信号可靠性降低，建议观察",
            quality_tier=quality_tier,
            is_blind=True,
            days_since_formation=motion.structural_age if motion else 0,
            stop_loss_hint=f"止损 {sl:.1f} (盲区·低仓位)" if sl else "",
            stop_loss_price=sl,
            take_profit_price=tp,
            rr_ratio=rr * 0.5,  # 盲区盈亏比打折
            position_size_factor=calculate_position_factor(quality_tier, True) * 0.5,
        )
        candidates.append(sig)

    # 5. 结构老化检测
    is_aging, aging_conf, aging_note = detect_structure_aging(structure, ss)
    if is_aging:
        sig = Signal(
            kind=SignalKind.STRUCTURE_EXPIRED,
            direction="neutral",
            confidence=aging_conf,
            flux_aligned=False,
            stability_ok=stability_ok,
            entry_note=f"结构老化: {aging_note}",
            quality_tier=quality_tier,
            is_blind=is_blind,
            days_since_formation=motion.structural_age if motion else 0,
            stop_loss_hint="建议平仓观望",
            position_size_factor=0.0,  # 老化结构不建仓
        )
        candidates.append(sig)

    # 返回最高优先级的信号
    # 返回最高优先级的信号
    if candidates:
        return min(candidates, key=lambda s: s.priority)

    return None


# ═══════════════════════════════════════════════════════════
# 假突破检测
# ═══════════════════════════════════════════════════════════

def detect_fake_breakout(
    structure: Structure,
    bars: List[Bar],
    ss: Optional[SystemState],
) -> Tuple[bool, Optional[FakeBreakoutPattern], float]:
    """
    检测假突破及模式识别

    Returns:
        (是否假突破, 模式类型, 置信度)
    """
    if len(bars) < 5:
        return False, None, 0.0

    motion = ss.motion if ss else MotionState()
    projection = ss.projection if ss else ProjectionAwareness()

    upper = structure.zone.upper if structure.zone else 0
    lower = structure.zone.lower if structure.zone else 0
    bandwidth = structure.zone.bandwidth if structure.zone else 0

    if bandwidth <= 0:
        return False, None, 0.0

    # 获取最近几根K线
    recent_bars = bars[-5:]
    last_bar = bars[-1]
    prev_bar = bars[-2] if len(bars) >= 2 else last_bar

    # 获取flux
    flux = motion.conservation_flux if motion else 0.0

    # 计算成交量统计
    volumes = [b.volume for b in bars[-20:]] if len(bars) >= 20 else [b.volume for b in bars]
    median_vol = statistics.median(volumes) if volumes else 1.0
    current_vol = last_bar.volume

    # ═══════════════════════════════════════════════════════
    # 模式5: FAKE_GAP (跳空回补) - 优先检查，避免被FAKE_PIN误判
    # ═══════════════════════════════════════════════════════
    # 条件: 跳空突破Zone，当日回补，flux反向
    if len(bars) >= 2:
        gap_up = prev_bar.close < upper and last_bar.open > upper
        gap_down = prev_bar.close > lower and last_bar.open < lower

        fill_up = gap_up and last_bar.close < upper
        fill_down = gap_down and last_bar.close > lower

        if (fill_up and flux < 0) or (fill_down and flux > 0):
            return True, FakeBreakoutPattern.FAKE_GAP, 0.85

    # ═══════════════════════════════════════════════════════
    # 模式1: FAKE_PIN (探针型)
    # ═══════════════════════════════════════════════════════
    # 条件: 盘中穿透Zone边界，收盘回到Zone内，flux反向
    pin_up = last_bar.high > upper and last_bar.close < upper
    pin_down = last_bar.low < lower and last_bar.close > lower

    if pin_up or pin_down:
        penetration = 0.0
        if pin_up:
            penetration = (last_bar.high - upper) / bandwidth
            flux_opposite = flux < 0
        else:
            penetration = (lower - last_bar.low) / bandwidth
            flux_opposite = flux > 0

        if penetration > FAKE_PENETRATION_THRESHOLD and flux_opposite:
            conf = 0.70 + min(penetration, 0.5) * 0.4  # 0.70-0.90
            return True, FakeBreakoutPattern.FAKE_PIN, min(conf, 0.95)

    # ═══════════════════════════════════════════════════════
    # 模式2: FAKE_DSPIKE (单K极端)
    # ═══════════════════════════════════════════════════════
    # 条件: 单根K线极端价格，大部分时间在Zone内，量能峰值，通量弱
    body = abs(last_bar.close - last_bar.open)
    shadow_up = last_bar.high - max(last_bar.open, last_bar.close)
    shadow_down = min(last_bar.open, last_bar.close) - last_bar.low
    max_shadow = max(shadow_up, shadow_down)

    in_zone = lower < last_bar.open < upper and lower < last_bar.close < upper
    volume_climax = current_vol > median_vol * FAKE_VOLUME_CLIMIX
    flux_weak = abs(flux) < FAKE_FLUX_WEAK

    if in_zone and body > 0 and max_shadow / body > FAKE_SHADOW_RATIO and volume_climax and flux_weak:
        return True, FakeBreakoutPattern.FAKE_DSPIKE, 0.75

    # ═══════════════════════════════════════════════════════
    # 模式3: FAKE_VOLDIV (量能背离)
    # ═══════════════════════════════════════════════════════
    # 条件: 价格突破Zone，但量能萎缩，flux反向或接近0
    breakout_up = last_bar.close > upper
    breakout_down = last_bar.close < lower

    if breakout_up or breakout_down:
        volume_low = current_vol < median_vol * FAKE_VOLUME_DIV
        flux_against = (breakout_up and flux < 0) or (breakout_down and flux > 0)
        flux_neutral = abs(flux) < FAKE_FLUX_WEAK

        if volume_low and (flux_against or flux_neutral):
            conf = 0.65
            if flux_against:
                conf += 0.15
            return True, FakeBreakoutPattern.FAKE_VOLDIV, min(conf, 0.90)

    # ═══════════════════════════════════════════════════════
    # 模式4: FAKE_BLIND_WHIP (盲区抽鞭)
    # ═══════════════════════════════════════════════════════
    # 条件: 盲区快速突破后无后续，flux衰减
    is_blind = projection.is_blind if projection else False

    if is_blind and len(bars) >= 3:
        # 检查是否突破后回归
        prev_close = bars[-2].close
        prev_prev_close = bars[-3].close

        was_breakout_up = prev_close > upper and prev_prev_close <= upper
        was_breakout_down = prev_close < lower and prev_prev_close >= lower

        now_back = lower < last_bar.close < upper

        if (was_breakout_up or was_breakout_down) and now_back:
            # 检查flux是否衰减
            flux_weak_now = abs(flux) < FAKE_FLUX_WEAK
            if flux_weak_now:
                return True, FakeBreakoutPattern.FAKE_BLIND_WHIP, 0.70

    return False, None, 0.0


# ═══════════════════════════════════════════════════════════
# 突破评分
# ═══════════════════════════════════════════════════════════

def score_breakout_confirmation(
    structure: Structure,
    bars: List[Bar],
    ss: Optional[SystemState],
) -> Tuple[float, str]:
    """
    5维突破评分

    5维度权重:
        - 收盘穿透深度: 0.25
        - 量能扩张比: 0.25
        - 通量一致性: 0.15
        - 压缩蓄势度: 0.20
        - 驻留时间比: 0.15

    Returns:
        (评分0-1, 评分说明)
    """
    if not bars:
        return 0.0, "无数据"

    motion = ss.motion if ss else MotionState()

    upper = structure.zone.upper if structure.zone else 0
    lower = structure.zone.lower if structure.zone else 0
    bandwidth = structure.zone.bandwidth if structure.zone else 0

    if bandwidth <= 0:
        return 0.0, "Zone无效"

    last_bar = bars[-1]
    last_close = last_bar.close

    # 确定突破方向
    if last_close > upper:
        direction = 1
        penetration = (last_close - upper) / bandwidth
    elif last_close < lower:
        direction = -1
        penetration = (lower - last_close) / bandwidth
    else:
        return 0.0, "未突破Zone"

    # 1. 收盘穿透深度 (0.25)
    score_penetration = min(penetration / 0.5, 1.0)  # 0.5带宽为满分

    # 2. 量能扩张比 (0.25)
    volumes = [b.volume for b in bars[-20:]] if len(bars) >= 20 else [b.volume for b in bars]
    median_vol = statistics.median(volumes) if volumes else 1.0
    current_vol = last_bar.volume
    volume_ratio = current_vol / median_vol if median_vol > 0 else 1.0
    score_volume = min(volume_ratio / 2.0, 1.0)  # 2倍量为满分

    # 3. 通量一致性 (0.15)
    flux = motion.conservation_flux if motion else 0.0
    flux_aligned = (flux * direction) > 0
    flux_strength = abs(flux)
    if flux_aligned and flux_strength > 0.3:
        score_flux = 1.0
    elif flux_aligned:
        score_flux = 0.5
    else:
        score_flux = 0.0

    # 4. 压缩蓄势度 (0.20)
    # 使用cycle_count估算试探次数
    n_tests = structure.cycle_count if structure.cycle_count else 0
    score_compression = min(n_tests / 5, 1.0)  # 5次试探为满分

    # 5. 驻留时间比 (0.15)
    # 结构形成天数
    days = motion.structural_age if motion else 0
    score_dwell = min(days / 10, 1.0)  # 10天为满分

    # 加权总分
    total_score = (
        score_penetration * 0.25 +
        score_volume * 0.25 +
        score_flux * 0.15 +
        score_compression * 0.20 +
        score_dwell * 0.15
    )

    note = (
        f"穿透{score_penetration:.0%}/"
        f"量能{score_volume:.0%}/"
        f"通量{score_flux:.0%}/"
        f"压缩{score_compression:.0%}/"
        f"驻留{score_dwell:.0%}"
    )

    return total_score, note


# ═══════════════════════════════════════════════════════════
# 回踩确认检测
# ═══════════════════════════════════════════════════════════

def detect_pullback_confirmation(
    structure: Structure,
    bars: List[Bar],
    ss: Optional[SystemState],
) -> Tuple[bool, float, str]:
    """
    检测回踩确认

    逻辑: 价格曾突破Zone，现在回到边界附近测试，但未进入中心

    Returns:
        (是否确认, 置信度, 说明)
    """
    if len(bars) < 10:
        return False, 0.0, "数据不足"

    motion = ss.motion if ss else MotionState()

    upper = structure.zone.upper if structure.zone else 0
    lower = structure.zone.lower if structure.zone else 0
    bandwidth = structure.zone.bandwidth if structure.zone else 0
    center = (upper + lower) / 2 if bandwidth > 0 else 0

    if bandwidth <= 0:
        return False, 0.0, "Zone无效"

    last_bar = bars[-1]
    last_close = last_bar.close

    # 检查历史是否有过突破
    had_breakout_up = any(b.close > upper for b in bars[-10:-1])
    had_breakout_down = any(b.close < lower for b in bars[-10:-1])

    if not (had_breakout_up or had_breakout_down):
        return False, 0.0, "无历史突破"

    # 检查当前是否在边界附近但未进入中心
    near_upper = abs(last_close - upper) < bandwidth * 0.3
    near_lower = abs(last_close - lower) < bandwidth * 0.3
    inside_zone = lower < last_close < upper

    if not inside_zone:
        return False, 0.0, "不在Zone内"

    # 多头回踩: 曾向上突破，现在在upper附近
    if had_breakout_up and near_upper and last_close > center:
        # 检查是否缩量
        recent_vols = [b.volume for b in bars[-5:]]
        earlier_vols = [b.volume for b in bars[-10:-5]]
        if statistics.mean(recent_vols) < statistics.mean(earlier_vols) * 0.8:
            return True, 0.75, "缩量回踩上边界"
        return True, 0.60, "回踩上边界"

    # 空头回踩: 曾向下突破，现在在lower附近
    if had_breakout_down and near_lower and last_close < center:
        recent_vols = [b.volume for b in bars[-5:]]
        earlier_vols = [b.volume for b in bars[-10:-5]]
        if statistics.mean(recent_vols) < statistics.mean(earlier_vols) * 0.8:
            return True, 0.75, "缩量回踩下边界"
        return True, 0.60, "回踩下边界"

    return False, 0.0, "未满足回踩条件"


# ═══════════════════════════════════════════════════════════
# 结构老化检测
# ═══════════════════════════════════════════════════════════

def detect_structure_aging(
    structure: Structure,
    ss: Optional[SystemState],
) -> Tuple[bool, float, str]:
    """
    检测结构老化/失效

    条件:
        - 结构形成天数 > AGING_DAYS_THRESHOLD
        - 且运动态仍为forming（说明长时间未成熟）

    Returns:
        (是否老化, 置信度, 说明)
    """
    motion = ss.motion if ss else MotionState()

    days = motion.structural_age if motion else 0
    phase = motion.phase_tendency if motion else ""

    if days > AGING_DAYS_THRESHOLD and phase == "forming":
        conf = min(0.60 + (days - AGING_DAYS_THRESHOLD) * 0.02, 0.90)
        return True, conf, f"形成{days}天仍处forming阶段，结构可能失效"

    if days > AGING_DAYS_THRESHOLD * 2:
        conf = min(0.50 + (days - AGING_DAYS_THRESHOLD * 2) * 0.01, 0.80)
        return True, conf, f"结构已老化{days}天"

    return False, 0.0, ""


# ═══════════════════════════════════════════════════════════
# 仓位系数计算
# ═══════════════════════════════════════════════════════════

def calculate_position_factor(quality_tier: str, is_blind: bool) -> float:
    """
    计算仓位系数

    Args:
        quality_tier: 质量层 (A/B/C/D)
        is_blind: 是否盲区

    Returns:
        仓位系数 0.0-1.0
    """
    tier_factors = {
        "A": 1.0,
        "B": 0.6,
        "C": 0.3,
        "D": 0.0,
    }

    base = tier_factors.get(quality_tier, 0.3)

    # 盲区额外降仓
    if is_blind:
        base *= 0.5

    return base
