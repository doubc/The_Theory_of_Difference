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
# 常量配置（统一从 src.config 导入）
# ═══════════════════════════════════════════════════════════
from src.config import (
    FAKE_PENETRATION_THRESHOLD,
    FAKE_VOLUME_CLIMAX,
    FAKE_VOLUME_DIV,
    FAKE_FLUX_WEAK,
    FAKE_SHADOW_RATIO,
    BREAKOUT_STRONG,
    BREAKOUT_WEAK,
    AGING_DAYS_THRESHOLD,
    ATR_MULTIPLIER,
    ATR_PERIOD,
    ENTRY_TOLERANCE_RATIO,
    SIGNAL_TTL_BARS,
    FAKE_WICK_MIN_BARS,
    FAKE_WICK_MAX_BARS,
    FAKE_WICK_SHADOW_RATIO,
    FAKE_TIME_TRAP_MIN_BARS,
    FAKE_TIME_TRAP_MAX_BARS,
)

# 向后兼容别名（旧代码可能直接引用 signals.FAKE_VOLUME_CLIMIX）
FAKE_VOLUME_CLIMIX = FAKE_VOLUME_CLIMAX


# ═══════════════════════════════════════════════════════════
# ATR 计算
# ═══════════════════════════════════════════════════════════

def compute_atr(bars: List[Bar], period: int = ATR_PERIOD) -> float:
    """
    计算 ATR（Average True Range）。

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = SMA(TR, period)

    Args:
        bars: K线序列（至少 period+1 根）
        period: ATR周期，默认14

    Returns:
        ATR值，数据不足时返回0
    """
    if len(bars) < period + 1:
        return 0.0

    true_ranges = []
    for i in range(1, len(bars)):
        h = bars[i].high
        l = bars[i].low
        pc = bars[i - 1].close
        tr = max(h - l, abs(h - pc), abs(l - pc))
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return 0.0

    return sum(true_ranges[-period:]) / period


# ═══════════════════════════════════════════════════════════
# 止损/目标/盈亏比计算（ATR驱动）
# ═══════════════════════════════════════════════════════════

def _compute_risk_reward(
    direction: str,
    entry_price: float,
    upper: float,
    lower: float,
    bandwidth: float,
    atr: float = 0.0,
    quality_tier: str = "B",
) -> tuple[float, float, float]:
    """
    计算止损价、目标价、盈亏比。

    止损逻辑（ATR驱动）：
        - 有ATR时：止损 = entry ∓ n×ATR（n按质量层调整）
        - 无ATR时（fallback）：止损 = Zone边界 ∓ 0.3×bandwidth

    目标逻辑：
        - Zone等幅测量：目标 = entry + bandwidth（做多）或 entry - bandwidth（做空）

    Returns:
        (stop_loss_price, take_profit_price, rr_ratio)
    """
    if entry_price <= 0:
        return 0.0, 0.0, 0.0

    multiplier = ATR_MULTIPLIER.get(quality_tier, 2.0)

    if direction == "long":
        if atr > 0:
            stop_loss = entry_price - multiplier * atr
        elif bandwidth > 0:
            stop_loss = lower - 0.3 * bandwidth
        else:
            return 0.0, 0.0, 0.0
        take_profit = entry_price + bandwidth if bandwidth > 0 else entry_price + (entry_price - stop_loss) * 3
        risk = entry_price - stop_loss
        reward = take_profit - entry_price

    elif direction == "short":
        if atr > 0:
            stop_loss = entry_price + multiplier * atr
        elif bandwidth > 0:
            stop_loss = upper + 0.3 * bandwidth
        else:
            return 0.0, 0.0, 0.0
        take_profit = entry_price - bandwidth if bandwidth > 0 else entry_price - (stop_loss - entry_price) * 3
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
    timeframe: str = "",
) -> Optional[Signal]:
    """
    为给定结构生成交易信号

    逻辑流程:
        1. 前置过滤（质量层D/红灯）
        2. 计算ATR（用于止损）
        3. 检测假突破7模式（优先级最高）
        4. 检测突破确认
        5. 检测回踩确认
        6. 检测结构老化
        7. 返回最高优先级信号

    Args:
        structure: 价格结构
        bars: K线序列（至少包含最近20根）
        system_state: 系统状态（可选，用于获取motion/projection等）
        quality_tier_override: 外部传入的质量层（避免重复计算，优先使用）
        timeframe: 时间框架标记（"60min"/"15min"/"daily"等）

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

    # 计算ATR（用于止损）
    atr = compute_atr(bars)

    # 预计算成交量中位数（避免 detect_fake_breakout 和 score_breakout 重复计算）
    _vols = [b.volume for b in bars[-20:]] if len(bars) >= 20 else [b.volume for b in bars]
    median_vol = statistics.median(_vols) if _vols else 1.0

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
    stability_ok = stability.surface == "stable" and stability.verified
    is_blind = projection.is_blind if projection else False

    # K线索引（用于TTL计算）
    bars_idx = len(bars) - 1

    # ═══════════════════════════════════════════════════════
    # 信号检测（按优先级顺序）
    # ═══════════════════════════════════════════════════════

    candidates: List[Signal] = []

    # 1. 假突破检测（最高优先级）
    is_fake, fake_pattern, fake_conf = detect_fake_breakout(structure, bars, ss, median_vol=median_vol)
    if is_fake and fake_pattern:
        # 假突破反向信号
        reverse_direction = "short" if price_position == "above" else "long" if price_position == "below" else "neutral"
        fake_flux_aligned = (flux > 0 and reverse_direction == "long") or (flux < 0 and reverse_direction == "short")

        # 入场价：假突破确认后在 Zone 边界入场
        # 做多（假下穿后回归）→ Zone 下沿；做空（假上穿后回归）→ Zone 上沿
        if reverse_direction == "long":
            entry_price = lower
            entry_limit_upper = lower + ENTRY_TOLERANCE_RATIO * bandwidth
            entry_limit_lower = 0.0
        elif reverse_direction == "short":
            entry_price = upper
            entry_limit_upper = 0.0
            entry_limit_lower = upper - ENTRY_TOLERANCE_RATIO * bandwidth
        else:
            entry_price = last_close
            entry_limit_upper = 0.0
            entry_limit_lower = 0.0

        sl, tp, rr = _compute_risk_reward(
            reverse_direction, entry_price, upper, lower, bandwidth,
            atr=atr, quality_tier=quality_tier,
        )

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
            entry_price=entry_price,
            entry_limit_upper=entry_limit_upper,
            entry_limit_lower=entry_limit_lower,
            stop_loss_hint=f"止损 {sl:.1f}" if sl else "",
            stop_loss_price=sl,
            take_profit_price=tp,
            rr_ratio=rr,
            position_size_factor=calculate_position_factor(quality_tier, is_blind),
            timeframe=timeframe,
            signal_bars_index=bars_idx,
            ttl_bars=SIGNAL_TTL_BARS.get("fake_breakout", 2),
            atr_value=atr,
        )
        candidates.append(sig)

    # 2. 突破确认检测
    breakout_score, breakout_note = score_breakout_confirmation(structure, bars, ss, median_vol=median_vol)
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

        sl, tp, rr = _compute_risk_reward(
            direction, last_close, upper, lower, bandwidth,
            atr=atr, quality_tier=quality_tier,
        )

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
            entry_price=last_close,
            stop_loss_hint=f"止损 {sl:.1f}" if sl else "",
            stop_loss_price=sl,
            take_profit_price=tp,
            rr_ratio=rr,
            position_size_factor=calculate_position_factor(quality_tier, is_blind),
            timeframe=timeframe,
            signal_bars_index=bars_idx,
            ttl_bars=SIGNAL_TTL_BARS.get("breakout_confirm", 5),
            atr_value=atr,
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

        sl, tp, rr = _compute_risk_reward(
            direction, last_close, upper, lower, bandwidth,
            atr=atr, quality_tier=quality_tier,
        )

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
            entry_price=last_close,
            stop_loss_hint=f"止损 {sl:.1f}" if sl else "",
            stop_loss_price=sl,
            take_profit_price=tp,
            rr_ratio=rr,
            position_size_factor=calculate_position_factor(quality_tier, is_blind) * 0.9,
            timeframe=timeframe,
            signal_bars_index=bars_idx,
            ttl_bars=SIGNAL_TTL_BARS.get("pullback_confirm", 5),
            atr_value=atr,
        )
        candidates.append(sig)

    # 4. 盲区突破观察（当is_blind且价格突破时）
    if is_blind and price_position != "inside":
        conf = 0.50
        if flux_aligned:
            conf += 0.15

        sl, tp, rr = _compute_risk_reward(
            direction, last_close, upper, lower, bandwidth,
            atr=atr, quality_tier=quality_tier,
        )

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
            entry_price=last_close,
            stop_loss_hint=f"止损 {sl:.1f} (盲区·低仓位)" if sl else "",
            stop_loss_price=sl,
            take_profit_price=tp,
            rr_ratio=rr * 0.5,  # 盲区盈亏比打折
            position_size_factor=calculate_position_factor(quality_tier, True) * 0.5,
            timeframe=timeframe,
            signal_bars_index=bars_idx,
            ttl_bars=SIGNAL_TTL_BARS.get("blind_breakout", 3),
            atr_value=atr,
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
            timeframe=timeframe,
            signal_bars_index=bars_idx,
            ttl_bars=SIGNAL_TTL_BARS.get("structure_expired", 0),
        )
        candidates.append(sig)

    # 返回最高优先级的信号
    # 返回最高优先级的信号
    if candidates:
        return min(candidates, key=lambda s: s.priority)

    return None


# ═══════════════════════════════════════════════════════════
# 假突破检测（5 种模式，主函数 + 5 个子函数）
# ═══════════════════════════════════════════════════════════

def _detect_fake_gap(
    bars: List[Bar], upper: float, lower: float, flux: float,
) -> Tuple[bool, float]:
    """
    模式5: FAKE_GAP (跳空回补)
    条件: 跳空突破Zone，当日回补，flux反向
    优先级最高，避免被 FAKE_PIN 误判。
    """
    if len(bars) < 2:
        return False, 0.0
    last_bar = bars[-1]
    prev_bar = bars[-2]

    gap_up = prev_bar.close < upper and last_bar.open > upper
    gap_down = prev_bar.close > lower and last_bar.open < lower
    fill_up = gap_up and last_bar.close < upper
    fill_down = gap_down and last_bar.close > lower

    if (fill_up and flux < 0) or (fill_down and flux > 0):
        return True, 0.85
    return False, 0.0


def _detect_fake_pin(
    bars: List[Bar], upper: float, lower: float, bandwidth: float, flux: float,
) -> Tuple[bool, float]:
    """
    模式1: FAKE_PIN (探针型)
    条件: 盘中穿透Zone边界，收盘回到Zone内，flux反向
    """
    last_bar = bars[-1]
    pin_up = last_bar.high > upper and last_bar.close < upper
    pin_down = last_bar.low < lower and last_bar.close > lower

    if not (pin_up or pin_down):
        return False, 0.0

    if pin_up:
        penetration = (last_bar.high - upper) / bandwidth
        flux_opposite = flux < 0
    else:
        penetration = (lower - last_bar.low) / bandwidth
        flux_opposite = flux > 0

    if penetration > FAKE_PENETRATION_THRESHOLD and flux_opposite:
        conf = 0.70 + min(penetration, 0.5) * 0.4  # 0.70-0.90
        return True, min(conf, 0.95)
    return False, 0.0


def _detect_fake_dspike(
    bars: List[Bar], upper: float, lower: float, flux: float,
    median_vol: float,
) -> Tuple[bool, float]:
    """
    模式2: FAKE_DSPIKE (单K极端)
    条件: 单根K线极端价格，大部分时间在Zone内，量能峰值，通量弱
    """
    last_bar = bars[-1]
    body = abs(last_bar.close - last_bar.open)
    shadow_up = last_bar.high - max(last_bar.open, last_bar.close)
    shadow_down = min(last_bar.open, last_bar.close) - last_bar.low
    max_shadow = max(shadow_up, shadow_down)

    in_zone = lower < last_bar.open < upper and lower < last_bar.close < upper
    volume_climax = last_bar.volume > median_vol * FAKE_VOLUME_CLIMAX
    flux_weak = abs(flux) < FAKE_FLUX_WEAK

    if in_zone and body > 0 and max_shadow / body > FAKE_SHADOW_RATIO and volume_climax and flux_weak:
        return True, 0.75
    return False, 0.0


def _detect_fake_voldiv(
    bars: List[Bar], upper: float, lower: float, flux: float,
    median_vol: float,
) -> Tuple[bool, float]:
    """
    模式3: FAKE_VOLDIV (量能背离)
    条件: 价格突破Zone，但量能萎缩，flux反向或接近0
    """
    last_bar = bars[-1]
    breakout_up = last_bar.close > upper
    breakout_down = last_bar.close < lower

    if not (breakout_up or breakout_down):
        return False, 0.0

    volume_low = last_bar.volume < median_vol * FAKE_VOLUME_DIV
    flux_against = (breakout_up and flux < 0) or (breakout_down and flux > 0)
    flux_neutral = abs(flux) < FAKE_FLUX_WEAK

    if volume_low and (flux_against or flux_neutral):
        conf = 0.65
        if flux_against:
            conf += 0.15
        return True, min(conf, 0.90)
    return False, 0.0


def _detect_fake_blind_whip(
    bars: List[Bar], upper: float, lower: float, flux: float,
    is_blind: bool,
) -> Tuple[bool, float]:
    """
    模式4: FAKE_BLIND_WHIP (盲区抽鞭)
    条件: 盲区快速突破后无后续，flux衰减
    """
    if not is_blind or len(bars) < 3:
        return False, 0.0

    last_bar = bars[-1]
    prev_close = bars[-2].close
    prev_prev_close = bars[-3].close

    was_breakout_up = prev_close > upper and prev_prev_close <= upper
    was_breakout_down = prev_close < lower and prev_prev_close >= lower
    now_back = lower < last_bar.close < upper

    if (was_breakout_up or was_breakout_down) and now_back:
        if abs(flux) < FAKE_FLUX_WEAK:
            return True, 0.70
    return False, 0.0


def _detect_fake_wick_cluster(
    bars: List[Bar], upper: float, lower: float, bandwidth: float, flux: float,
) -> Tuple[bool, float]:
    """
    模式6: FAKE_WICK_CLUSTER (连续影线簇)
    条件: 最近3-5根K线的影线在Zone外，但实体在Zone内
    典型场景: 盘整末期，多方/空方反复试探但无法站稳

    检测逻辑:
        1. 取最近 N 根 K 线 (N = FAKE_WICK_MIN_BARS ~ FAKE_WICK_MAX_BARS)
        2. 每根 K 线: 实体(open,close) 在 Zone 内，但 high > upper 或 low < lower
        3. 影线/实体比 > FAKE_WICK_SHADOW_RATIO
        4. flux 反向或弱
    """
    if len(bars) < FAKE_WICK_MIN_BARS:
        return False, 0.0

    # 检查最近 3~5 根
    best_count = 0
    best_direction = None  # "up" = 上影线簇, "down" = 下影线簇

    for lookback in range(FAKE_WICK_MIN_BARS, min(FAKE_WICK_MAX_BARS + 1, len(bars))):
        recent = bars[-lookback:]
        up_wick_count = 0
        down_wick_count = 0

        for b in recent:
            body_top = max(b.open, b.close)
            body_bottom = min(b.open, b.close)
            body = body_top - body_bottom

            if body <= 0:
                continue

            # 实体在 Zone 内
            if body_bottom < lower or body_top > upper:
                continue

            # 上影线探出 Zone 上沿
            if b.high > upper:
                shadow_up = b.high - body_top
                if shadow_up / body >= FAKE_WICK_SHADOW_RATIO:
                    up_wick_count += 1

            # 下影线探出 Zone 下沿
            if b.low < lower:
                shadow_down = body_bottom - b.low
                if shadow_down / body >= FAKE_WICK_SHADOW_RATIO:
                    down_wick_count += 1

        if up_wick_count >= FAKE_WICK_MIN_BARS and up_wick_count > best_count:
            best_count = up_wick_count
            best_direction = "up"
        if down_wick_count >= FAKE_WICK_MIN_BARS and down_wick_count > best_count:
            best_count = down_wick_count
            best_direction = "down"

    if best_count == 0 or best_direction is None:
        return False, 0.0

    # flux 应与试探方向相反（上影线簇→flux应为负，下影线簇→flux应为正）
    flux_opposite = (
        (best_direction == "up" and flux < 0) or
        (best_direction == "down" and flux > 0)
    )
    flux_neutral = abs(flux) < FAKE_FLUX_WEAK

    if flux_opposite or flux_neutral:
        conf = 0.65 + min(best_count - FAKE_WICK_MIN_BARS, 2) * 0.05
        if flux_opposite:
            conf += 0.10
        return True, min(conf, 0.85)

    return False, 0.0


def _detect_fake_time_trap(
    bars: List[Bar], upper: float, lower: float, flux: float,
) -> Tuple[bool, float]:
    """
    模式7: FAKE_TIME_TRAP (时间陷阱)
    条件: 价格突破Zone后在Zone外停留2-5天，没有后续动能，然后回归Zone内
    与 FAKE_BLIND_WHIP 的区别: 不要求盲区，关注"停留天数"

    检测逻辑:
        1. 当前 K 线回到 Zone 内
        2. 往前看 2~5 根 K 线，它们都在 Zone 外（同方向突破）
        3. Zone 外停留期间量能递减或 flux 衰减
    """
    if len(bars) < FAKE_TIME_TRAP_MIN_BARS + 1:
        return False, 0.0

    last_bar = bars[-1]
    # 当前必须回到 Zone 内
    if not (lower < last_bar.close < upper):
        return False, 0.0

    # 往前看 2~5 根，找连续在 Zone 外的区段
    best_streak = 0
    best_direction = None

    for lookback in range(FAKE_TIME_TRAP_MIN_BARS, min(FAKE_TIME_TRAP_MAX_BARS + 1, len(bars))):
        segment = bars[-(lookback + 1):-1]  # 不含当前K线
        if len(segment) < FAKE_TIME_TRAP_MIN_BARS:
            break

        all_above = all(b.close > upper for b in segment)
        all_below = all(b.close < lower for b in segment)

        if all_above and len(segment) > best_streak:
            best_streak = len(segment)
            best_direction = "above"
        if all_below and len(segment) > best_streak:
            best_streak = len(segment)
            best_direction = "below"

    if best_streak == 0 or best_direction is None:
        return False, 0.0

    # 检查 Zone 外停留期间是否有动能衰减
    trap_bars = bars[-(best_streak + 1):-1]
    # 量能递减: 后半段量 < 前半段量
    mid = len(trap_bars) // 2
    if mid > 0:
        early_vol = sum(b.volume for b in trap_bars[:mid]) / mid
        late_vol = sum(b.volume for b in trap_bars[mid:]) / (len(trap_bars) - mid)
        vol_declining = late_vol < early_vol * 0.9
    else:
        vol_declining = False

    # flux 反向
    flux_opposite = (
        (best_direction == "above" and flux < 0) or
        (best_direction == "below" and flux > 0)
    )
    flux_neutral = abs(flux) < FAKE_FLUX_WEAK

    if flux_opposite or flux_neutral or vol_declining:
        conf = 0.60 + min(best_streak - FAKE_TIME_TRAP_MIN_BARS, 3) * 0.05
        if flux_opposite:
            conf += 0.10
        if vol_declining:
            conf += 0.05
        return True, min(conf, 0.85)

    return False, 0.0


def detect_fake_breakout(
    structure: Structure,
    bars: List[Bar],
    ss: Optional[SystemState],
    median_vol: float = 0.0,
) -> Tuple[bool, Optional[FakeBreakoutPattern], float]:
    """
    检测假突破及模式识别（主函数：准备共享状态，按优先级调用子函数）

    7种模式优先级:
        FAKE_GAP > FAKE_PIN > FAKE_DSPIKE > FAKE_VOLDIV > FAKE_WICK_CLUSTER > FAKE_TIME_TRAP > FAKE_BLIND_WHIP

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

    flux = motion.conservation_flux if motion else 0.0
    is_blind = projection.is_blind if projection else False

    volumes = [b.volume for b in bars[-20:]] if len(bars) >= 20 else [b.volume for b in bars]
    if median_vol <= 0:
        median_vol = statistics.median(volumes) if volumes else 1.0

    # 按优先级调用（第一个匹配即返回）
    patterns = [
        (_detect_fake_gap,         (bars, upper, lower, flux),                    FakeBreakoutPattern.FAKE_GAP),
        (_detect_fake_pin,         (bars, upper, lower, bandwidth, flux),         FakeBreakoutPattern.FAKE_PIN),
        (_detect_fake_dspike,      (bars, upper, lower, flux, median_vol),        FakeBreakoutPattern.FAKE_DSPIKE),
        (_detect_fake_voldiv,      (bars, upper, lower, flux, median_vol),        FakeBreakoutPattern.FAKE_VOLDIV),
        (_detect_fake_wick_cluster,(bars, upper, lower, bandwidth, flux),         FakeBreakoutPattern.FAKE_WICK_CLUSTER),
        (_detect_fake_time_trap,   (bars, upper, lower, flux),                    FakeBreakoutPattern.FAKE_TIME_TRAP),
        (_detect_fake_blind_whip,  (bars, upper, lower, flux, is_blind),          FakeBreakoutPattern.FAKE_BLIND_WHIP),
    ]

    for detect_fn, args, pattern in patterns:
        matched, conf = detect_fn(*args)
        if matched:
            return True, pattern, conf

    return False, None, 0.0


# ═══════════════════════════════════════════════════════════
# 突破评分
# ═══════════════════════════════════════════════════════════

def score_breakout_confirmation(
    structure: Structure,
    bars: List[Bar],
    ss: Optional[SystemState],
    median_vol: float = 0.0,
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
    if median_vol <= 0:
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


# ═══════════════════════════════════════════════════════════
# 交易计划摘要
# ═══════════════════════════════════════════════════════════

def generate_trade_plan(
    signal: Signal,
    structure: Structure,
    symbol: str | None = None,
    current_price: float = 0.0,
) -> str:
    """
    生成人可读的交易计划摘要（实盘增强版）。

    格式：
        CU000 60min | 📈做多·假突破反向(PIN)
        入场 77500(Zone下沿) | 当前 77620 | 止损 77200(-0.4%) | 目标 79000(+1.9%)
        仓位 60%(B层) | 盈亏比 3.0:1 | 🟢绿灯
        ⚠️ 有效期: 2根K线内 | 通量方向一致 ✅

    Args:
        signal: 交易信号
        structure: 价格结构
        symbol: 品种代码（可选，默认从 structure 取）
        current_price: 当前市价（可选，用于对比入场价）

    Returns:
        交易计划字符串（多行）
    """
    sym = symbol or structure.symbol or "???"
    direction = signal.display_direction  # 📈做多 / 📉做空 / ➡️观望
    entry = signal.entry_price
    sl = signal.stop_loss_price
    tp = signal.take_profit_price
    rr = signal.rr_ratio
    pos = signal.position_size_factor
    tier = signal.quality_tier or "?"
    tf = signal.timeframe or ""

    if signal.direction == "neutral":
        # 观望信号
        plan = f"{sym} {tf} | {direction} · {signal.entry_note}"
        return plan

    # 第一行：品种 + 时间框架 + 方向 + 信号类型
    sig_type = signal.signal_type_label
    line1 = f"{sym} {tf} | {direction}·{sig_type}" if tf else f"{sym} | {direction}·{sig_type}"

    # 第二行：入场 + 当前价 + 止损 + 目标
    parts = []
    if entry > 0:
        # 入场价来源标注
        if signal.fake_pattern:
            entry_src = "Zone边界"
        else:
            entry_src = ""
        entry_str = f"入场 {entry:.0f}" + (f"({entry_src})" if entry_src else "")
        # 偏差容忍度
        if signal.entry_limit_upper > 0:
            entry_str += f" | 可接受 ≤{signal.entry_limit_upper:.0f}"
        elif signal.entry_limit_lower > 0:
            entry_str += f" | 可接受 ≥{signal.entry_limit_lower:.0f}"
        parts.append(entry_str)

    if current_price > 0:
        parts.append(f"当前 {current_price:.0f}")

    if sl > 0:
        sl_pct = abs(sl - entry) / entry * 100 if entry > 0 else 0
        parts.append(f"止损 {sl:.0f}(-{sl_pct:.1f}%)")

    if tp > 0:
        tp_pct = abs(tp - entry) / entry * 100 if entry > 0 else 0
        parts.append(f"目标 {tp:.0f}(+{tp_pct:.1f}%)")

    line2 = " | ".join(parts)

    # 第三行：仓位 + 盈亏比 + 稳定性灯
    parts3 = []
    if pos > 0:
        parts3.append(f"仓位 {pos:.0%}({tier}层)")
    if rr > 0:
        parts3.append(f"盈亏比 {rr:.1f}:1")
    parts3.append(signal.traffic_light)
    if signal.stability_ok:
        parts3.append("绿灯")
    else:
        parts3.append("⚠️稳定性存疑")
    line3 = " | ".join(parts3)

    # 第四行：有效期 + 通量 + ATR
    parts4 = []
    if signal.ttl_bars > 0:
        parts4.append(f"⚠️ 有效期: {signal.ttl_bars}根K线内")
    if signal.flux_aligned:
        parts4.append("通量方向一致 ✅")
    else:
        parts4.append("通量方向不一致 ⚠️")
    if signal.atr_value > 0:
        parts4.append(f"ATR={signal.atr_value:.1f}")
    if signal.is_blind:
        parts4.append("⚠️盲区·低仓位")
    line4 = " | ".join(parts4)

    return f"{line1}\n{line2}\n{line3}\n{line4}"
