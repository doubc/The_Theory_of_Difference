"""
价格结构信号提示工具 — PythonGO v2 策略（差异论驱动 · 实盘增强版 v4.1）

基于差异论（Theory of Difference）的价格结构信号检测策略，运行在无限易 PythonGO v2 环境中。

v4.1 变更（相对 v4.0）：
- 迁移至 PythonGO v2 框架（pythongo.base + KLineGenerator）
- Params 增加 exchange/instrument_id 标准字段（分号分隔）
- 移除 on_bar，改用 KLineGenerator 合成 K 线
- 平仓改用 auto_close_position（自动处理平今/平昨）
- 新增：止损/止盈使用 tick 级触发（更精确，避免漏过针尖价格）
- 新增：信号 TTL 自动清理过期信号
- 新增：策略暂停时自动平掉所有持仓

差异论 → 信号映射：
    A1(source)/A8(sink) → Zone 源端/汇端 = 入场/出场区域
    A2(discrete)        → 二元状态：持有 or 观望
    A3(local)           → CNN 3×3 局域性 = 只看近端 K 线
    A4(minimal_change)  → 最小变易 = 交易频率惩罚
    A5(conservation)    → flux 守恒 = 通量方向过滤
    A6(flow_coupling)   → 流耦合 = 板块共振
    A7(stability)       → 稳定性验证 = 结构持续性
    A9(ascent_trigger)  → 结构老化/突破触发

功能：
- 7 种假突破模式检测（PIN/DPIKE/VOLDIV/BLIND_WHIP/WICK_CLUSTER/TIME_TRAP/GAP）
- 5 维突破评分 + 回踩确认 + 结构老化
- ATR 驱动止损/目标/盈亏比
- 信号 TTL（有效期）
- 跨品种共振检测
- 自动生成交易计划（4 行格式）
- 可选自动下单 + 止损/止盈执行
- tick 级止损止盈触发（v4.1 新增）

作者：差异论价格结构系统 v4.1
"""

import math
import statistics as _stats
import time as _time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, NamedTuple, Literal

# ═══ PythonGO v2 正确导入 ═══
from pythongo.base import BaseParams, BaseState, BaseStrategy, Field
from pythongo.classdef import KLineData, TickData, OrderData, TradeData
from pythongo.utils import KLineGenerator

# K 线周期类型（v2 中 KLineStyleType 是 Literal 别名，这里显式定义以稳妥）
KLineStyle = Literal["M1", "M3", "M5", "M15", "M30", "M60"]

# ═══════════════════════════════════════════════════════════
# 常量配置
# ═══════════════════════════════════════════════════════════

# ATR 驱动止损乘数（按质量层）
ATR_MULTIPLIER = {"A": 1.5, "B": 2.0, "C": 2.5, "D": 3.0}

# 信号 TTL（K 线根数）
SIGNAL_TTL_BARS = {
    "fake_breakout": 2,
    "breakout_confirm": 5,
    "pullback_confirm": 5,
    "blind_breakout": 3,
    "structure_expired": 0,
}

# 入场容忍度（相对 bandwidth 的比例）
ENTRY_TOLERANCE_RATIO = 0.3

# 突破阈值
BREAKOUT_STRONG = 0.65
BREAKOUT_WEAK = 0.35

# 假突破模式常量
FAKE_PENETRATION_THRESHOLD = 0.3
FAKE_VOLUME_CLIMAX = 2.0
FAKE_VOLUME_DIV = 0.7
FAKE_FLUX_WEAK = 0.15
FAKE_SHADOW_RATIO = 2.0
FAKE_WICK_MIN_BARS = 3
FAKE_WICK_MAX_BARS = 5
FAKE_WICK_SHADOW_RATIO = 1.5
FAKE_TIME_TRAP_MIN_BARS = 2
FAKE_TIME_TRAP_MAX_BARS = 5

# 结构老化的 K 线阈值（替代日线）
AGING_BARS_THRESHOLD = 50


# ═══════════════════════════════════════════════════════════
# 轻量级 K 线适配器
# ═══════════════════════════════════════════════════════════

class BarLite(NamedTuple):
    """轻量 K 线（适配假突破检测函数）"""
    open: float
    high: float
    low: float
    close: float
    volume: float


# ═══════════════════════════════════════════════════════════
# 轻量级结构分析引擎（内联，不依赖外部模块）
# ═══════════════════════════════════════════════════════════

@dataclass
class Pivot:
    """极值点"""
    idx: int
    price: float
    direction: int  # 1=高, -1=低


@dataclass
class Zone:
    """关键稳态区（差异论 A1 源端 / A8 汇端）"""
    center: float
    bandwidth: float
    touches: int = 0
    strength: float = 0.0
    pivot_indices: List[int] = field(default_factory=list)
    first_idx: int = -1
    last_idx: int = -1

    @property
    def upper(self):
        return self.center + self.bandwidth

    @property
    def lower(self):
        return self.center - self.bandwidth

    def contains(self, price):
        return self.lower <= price <= self.upper


@dataclass
class LightweightStructure:
    """轻量级结构（PythonGO 内使用）"""
    zone: Zone
    previous_zone: Optional[Zone]
    cycle_count: int
    avg_speed_ratio: float
    avg_time_ratio: float
    direction: str  # "bullish" / "bearish" / "mixed"
    quality_score: float
    quality_tier: str  # A/B/C/D
    phase_tendency: str
    conservation_flux: float  # A5 守恒通量
    is_blind: bool
    trend_delta: float = 0.0
    formation_bar_idx: int = -1  # 结构形成的 K 线索引

    @property
    def is_actionable(self):
        return not self.is_blind and self.quality_tier in ("A", "B")


@dataclass
class SignalInfo:
    """交易信号信息（差异论驱动）"""
    signal_type: str  # "fake_breakout" / "breakout_confirm" / "pullback_confirm" / "blind_breakout" / "structure_expired"
    direction: str  # "bullish" / "bearish" / "neutral"
    quality_tier: str  # A/B/C/D
    quality_score: float
    entry_price: float
    stop_loss: float
    take_profit: float
    rr_ratio: float  # 盈亏比
    position_factor: float  # 仓位系数 0.0-1.0
    flux_aligned: bool  # A5: 通量方向一致
    stability_ok: bool  # A7: 稳定性验证
    is_blind: bool  # 盲区标记
    ttl_bars: int  # 有效期（K 线根数）
    signal_bar_idx: int  # 信号触发的 K 线索引
    atr_value: float
    note: str
    fake_pattern: str = ""  # 假突破子模式

    @property
    def direction_cn(self) -> str:
        return {"bullish": "做多", "bearish": "做空", "neutral": "观望"}.get(self.direction, "?")

    @property
    def signal_type_cn(self) -> str:
        return {
            "fake_breakout": "假突破反向",
            "breakout_confirm": "突破确认",
            "pullback_confirm": "回踩确认",
            "blind_breakout": "盲区突破",
            "structure_expired": "结构老化",
        }.get(self.signal_type, self.signal_type)

    @property
    def icon(self) -> str:
        return {
            "fake_breakout": "🔻",
            "breakout_confirm": "🔺",
            "pullback_confirm": "↩️",
            "blind_breakout": "👁️",
            "structure_expired": "⏰",
        }.get(self.signal_type, "❓")

    @property
    def is_expired(self) -> bool:
        """信号是否过期（需要当前 K 线索引来判断）"""
        return False  # 由调用方判断

    def format_trade_plan(self, instrument: str, timeframe: str, current_price: float) -> str:
        """生成 4 行交易计划（差异论格式）

        格式：
            CU000 M5 | 📈做多·假突破反向(PIN)
            入场 77500(Zone下沿) | 当前 77620 | 止损 77200(-0.4%) | 目标 79000(+1.9%)
            仓位 60%(B层) | 盈亏比 3.0:1 | 🟢绿灯
            ⚠️ 有效期: 2根K线内 | 通量方向一致 ✅
        """
        if self.direction == "neutral":
            return f"{instrument} {timeframe} | ➡️观望 · {self.note}"

        # 第 1 行：品种 + 周期 + 方向 + 信号类型
        pattern_suffix = f"({self.fake_pattern})" if self.fake_pattern else ""
        line1 = f"{instrument} {timeframe} | {'📈' if self.direction == 'bullish' else '📉'}{self.direction_cn}·{self.signal_type_cn}{pattern_suffix}"

        # 第 2 行：入场 + 当前 + 止损 + 目标
        parts = []
        if self.entry_price > 0:
            parts.append(f"入场 {self.entry_price:.0f}")
        if current_price > 0:
            parts.append(f"当前 {current_price:.0f}")
        if self.stop_loss > 0 and self.entry_price > 0:
            sl_pct = abs(self.stop_loss - self.entry_price) / self.entry_price * 100
            parts.append(f"止损 {self.stop_loss:.0f}(-{sl_pct:.1f}%)")
        if self.take_profit > 0 and self.entry_price > 0:
            tp_pct = abs(self.take_profit - self.entry_price) / self.entry_price * 100
            parts.append(f"目标 {self.take_profit:.0f}(+{tp_pct:.1f}%)")
        line2 = " | ".join(parts)

        # 第 3 行：仓位 + 盈亏比 + 稳定性
        parts3 = []
        if self.position_factor > 0:
            parts3.append(f"仓位 {self.position_factor:.0%}({self.quality_tier}层)")
        if self.rr_ratio > 0:
            parts3.append(f"盈亏比 {self.rr_ratio:.1f}:1")
        if self.stability_ok:
            parts3.append("🟢绿灯")
        else:
            parts3.append("⚠️稳定性存疑")
        line3 = " | ".join(parts3)

        # 第 4 行：有效期 + 通量 + 盲区
        parts4 = []
        if self.ttl_bars > 0:
            parts4.append(f"⚠️ 有效期: {self.ttl_bars}根K线内")
        if self.flux_aligned:
            parts4.append("通量方向一致 ✅")
        else:
            parts4.append("通量方向不一致 ⚠️")
        if self.atr_value > 0:
            parts4.append(f"ATR={self.atr_value:.1f}")
        if self.is_blind:
            parts4.append("⚠️盲区·低仓位")
        line4 = " | ".join(parts4) if parts4 else ""

        lines = [line1, line2, line3]
        if line4:
            lines.append(line4)
        return "\n".join(lines)


def extract_pivots_light(prices, window=3, min_amp=0.02):
    """轻量级极值提取"""
    n = len(prices)
    if n < window * 2 + 1:
        return []

    pivots = []
    for i in range(window, n - window):
        is_high = all(prices[j] < prices[i] for j in range(i - window, i + window + 1) if j != i)
        is_low = all(prices[j] > prices[i] for j in range(i - window, i + window + 1) if j != i)

        if not is_high and not is_low:
            continue

        mid = (prices[max(0, i - window)] + prices[min(n - 1, i + window)]) / 2
        amp = abs(prices[i] - mid) / mid if mid > 0 else 0
        if amp < min_amp:
            continue

        pivots.append(Pivot(idx=i, price=prices[i], direction=1 if is_high else -1))

    if not pivots:
        return []

    result = [pivots[0]]
    for p in pivots[1:]:
        if p.direction != result[-1].direction:
            result.append(p)
        else:
            if (p.direction == 1 and p.price > result[-1].price) or \
                    (p.direction == -1 and p.price < result[-1].price):
                result[-1] = p

    return result


def detect_zones_light(pivots, bandwidth_pct=0.015):
    """轻量级 Zone 检测（带时间信息）"""
    if len(pivots) < 2:
        return []

    zones = []
    used = set()

    for i, p in enumerate(pivots):
        if i in used:
            continue

        cluster = [p]
        used.add(i)

        bw = max(abs(p.price) * bandwidth_pct, 1e-8)

        for j, q in enumerate(pivots):
            if j in used:
                continue
            if abs(p.price - q.price) <= bw:
                cluster.append(q)
                used.add(j)

        if len(cluster) >= 2:
            center = sum(c.price for c in cluster) / len(cluster)
            indices = [c.idx for c in cluster]
            zones.append(Zone(
                center=center,
                bandwidth=bw,
                touches=len(cluster),
                strength=sum(0.9 ** k for k in range(len(cluster))),
                pivot_indices=indices,
                first_idx=min(indices),
                last_idx=max(indices),
            ))

    zones.sort(key=lambda z: z.last_idx)
    return zones


def infer_trend_from_zones(zones: List[Zone]):
    """根据最近两个稳态区判断趋势"""
    if not zones or len(zones) < 2:
        return "mixed", None, 0.0

    recent_zone = zones[-1]
    previous_zone = zones[-2]

    ref_bw = max(recent_zone.bandwidth, previous_zone.bandwidth, 1e-8)
    delta = recent_zone.center - previous_zone.center

    threshold = ref_bw * 0.5

    if delta > threshold:
        return "bullish", previous_zone, delta
    elif delta < -threshold:
        return "bearish", previous_zone, delta
    else:
        return "mixed", previous_zone, delta


def compute_quality_light(cycle_count, speed_ratio, zone_strength, is_blind=False):
    """轻量级质量评分"""
    score = 0.0

    if cycle_count >= 5:
        score += 0.3
    elif cycle_count >= 3:
        score += 0.2
    elif cycle_count >= 2:
        score += 0.1

    if zone_strength >= 2.5:
        score += 0.3
    elif zone_strength >= 1.5:
        score += 0.2
    elif zone_strength >= 0.5:
        score += 0.1

    if 0.3 <= speed_ratio <= 5.0:
        score += 0.2
    elif 0.1 <= speed_ratio <= 10.0:
        score += 0.1

    if not is_blind:
        score += 0.2
    else:
        score += 0.05

    if score >= 0.75:
        tier = "A"
    elif score >= 0.50:
        tier = "B"
    elif score >= 0.25:
        tier = "C"
    else:
        tier = "D"

    return score, tier


def _stddev(arr):
    if len(arr) < 2:
        return 0
    mean = sum(arr) / len(arr)
    return math.sqrt(sum((x - mean) ** 2 for x in arr) / len(arr))


def analyze_structure_light(prices, window=3, min_amp=0.02, bw_pct=0.015):
    """轻量级结构分析（完整流程）"""
    if len(prices) < 20:
        return None

    pivots = extract_pivots_light(prices, window=window, min_amp=min_amp)
    if len(pivots) < 4:
        return None

    zones = detect_zones_light(pivots, bandwidth_pct=bw_pct)
    if not zones:
        return None

    best_zone = zones[-1]
    direction, previous_zone, trend_delta = infer_trend_from_zones(zones)

    cycle_count = best_zone.touches

    speed_ratios = []
    for i in range(1, len(pivots)):
        if pivots[i].direction != pivots[i - 1].direction:
            amp_curr = abs(pivots[i].price - pivots[i - 1].price)
            if i >= 2:
                amp_prev = abs(pivots[i - 1].price - pivots[i - 2].price)
                if amp_prev > 0:
                    speed_ratios.append(amp_curr / amp_prev)

    avg_sr = sum(speed_ratios) / len(speed_ratios) if speed_ratios else 1.0

    recent = prices[-20:]
    vol = _stddev(recent) / (sum(recent) / len(recent)) if recent else 0
    is_blind = vol < 0.005

    quality_score, quality_tier = compute_quality_light(
        cycle_count, avg_sr, best_zone.strength, is_blind
    )

    if previous_zone is not None:
        ref_bw = max(best_zone.bandwidth, previous_zone.bandwidth, 1e-8)
        normalized_shift = abs(trend_delta) / ref_bw
        if normalized_shift >= 1.0:
            quality_score = min(1.0, quality_score + 0.05)
        elif normalized_shift >= 0.5:
            quality_score = min(1.0, quality_score + 0.02)

        if quality_score >= 0.75:
            quality_tier = "A"
        elif quality_score >= 0.50:
            quality_tier = "B"
        elif quality_score >= 0.25:
            quality_tier = "C"
        else:
            quality_tier = "D"

    if len(speed_ratios) >= 2:
        recent_sr = sum(speed_ratios[-2:]) / 2
        early_sr = sum(speed_ratios[:2]) / 2
        flux = (recent_sr - early_sr) / max(early_sr, 0.01)
        flux = max(-1, min(1, flux))
    else:
        flux = 0

    if flux > 0.3:
        phase = "→breakdown"
    elif flux < -0.3:
        phase = "→confirmation"
    else:
        phase = "stable"

    return LightweightStructure(
        zone=best_zone,
        previous_zone=previous_zone,
        cycle_count=cycle_count,
        avg_speed_ratio=avg_sr,
        avg_time_ratio=1.0,
        direction=direction,
        quality_score=quality_score,
        quality_tier=quality_tier,
        phase_tendency=phase,
        conservation_flux=flux,
        is_blind=is_blind,
        trend_delta=trend_delta,
    )


# ═══════════════════════════════════════════════════════════
# ATR 计算
# ═══════════════════════════════════════════════════════════

def compute_atr(bars: List[BarLite], period: int = 14) -> float:
    """计算 ATR（Average True Range）

    TR = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = SMA(TR, period)
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
# 止损/目标/盈亏比计算（ATR 驱动）
# ═══════════════════════════════════════════════════════════

def _compute_risk_reward(
        direction: str,
        entry_price: float,
        upper: float,
        lower: float,
        bandwidth: float,
        atr: float = 0.0,
        quality_tier: str = "B",
) -> Tuple[float, float, float]:
    """计算止损价、目标价、盈亏比

    止损逻辑（ATR 驱动）：
        - 有 ATR 时：止损 = entry ∓ n×ATR（n 按质量层调整）
        - 无 ATR 时：止损 = Zone 边界 ∓ 0.3×bandwidth

    目标逻辑：
        - Zone 等幅测量：目标 = entry + bandwidth

    Returns:
        (stop_loss, take_profit, rr_ratio)
    """
    if entry_price <= 0:
        return 0.0, 0.0, 0.0

    multiplier = ATR_MULTIPLIER.get(quality_tier, 2.0)

    if direction == "bullish":
        if atr > 0:
            stop_loss = entry_price - multiplier * atr
        elif bandwidth > 0:
            stop_loss = lower - 0.3 * bandwidth
        else:
            return 0.0, 0.0, 0.0
        take_profit = entry_price + bandwidth if bandwidth > 0 else entry_price + (entry_price - stop_loss) * 3
        risk = entry_price - stop_loss
        reward = take_profit - entry_price

    elif direction == "bearish":
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
    return round(stop_loss, 4), round(take_profit, 4), round(rr, 2)


# ═══════════════════════════════════════════════════════════
# 仓位系数（差异论 A2: 离散分层）
# ═══════════════════════════════════════════════════════════

def _position_factor(quality_tier: str, is_blind: bool) -> float:
    """仓位系数 = 质量层 × 盲区折扣"""
    tier_map = {"A": 1.0, "B": 0.6, "C": 0.3, "D": 0.0}
    base = tier_map.get(quality_tier, 0.3)
    if is_blind:
        base *= 0.5
    return base


# ═══════════════════════════════════════════════════════════
# 假突破检测（7 种模式 — 差异论 A9 上升触发器）
# ═══════════════════════════════════════════════════════════

def _detect_fake_gap(
        bars: List[BarLite], upper: float, lower: float, flux: float,
) -> Tuple[bool, float]:
    """模式 5: FAKE_GAP（跳空回补）

    条件: 跳空突破 Zone，当日回补，flux 反向
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
        bars: List[BarLite], upper: float, lower: float, bandwidth: float, flux: float,
) -> Tuple[bool, float]:
    """模式 1: FAKE_PIN（探针型）

    条件: 盘中穿透 Zone 边界，收盘回到 Zone 内，flux 反向
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
        conf = 0.70 + min(penetration, 0.5) * 0.4
        return True, min(conf, 0.95)
    return False, 0.0


def _detect_fake_dspike(
        bars: List[BarLite], upper: float, lower: float, flux: float,
        median_vol: float,
) -> Tuple[bool, float]:
    """模式 2: FAKE_DSPIKE（单 K 极端）

    条件: 单根 K 线极端价格，大部分时间在 Zone 内，量能峰值，通量弱
    """
    last_bar = bars[-1]
    body = abs(last_bar.close - last_bar.open)
    shadow_up = last_bar.high - max(last_bar.open, last_bar.close)
    shadow_down = min(last_bar.open, last_bar.close) - last_bar.low
    max_shadow = max(shadow_up, shadow_down)

    in_zone = lower < last_bar.open < upper and lower < last_bar.close < upper
    volume_climax = median_vol > 0 and last_bar.volume > median_vol * FAKE_VOLUME_CLIMAX
    flux_weak = abs(flux) < FAKE_FLUX_WEAK

    if in_zone and body > 0 and max_shadow / body > FAKE_SHADOW_RATIO and volume_climax and flux_weak:
        return True, 0.75
    return False, 0.0


def _detect_fake_voldiv(
        bars: List[BarLite], upper: float, lower: float, flux: float,
        median_vol: float,
) -> Tuple[bool, float]:
    """模式 3: FAKE_VOLDIV（量能背离）

    条件: 价格突破 Zone，但量能萎缩，flux 反向或接近 0
    """
    last_bar = bars[-1]
    breakout_up = last_bar.close > upper
    breakout_down = last_bar.close < lower

    if not (breakout_up or breakout_down):
        return False, 0.0

    volume_low = median_vol > 0 and last_bar.volume < median_vol * FAKE_VOLUME_DIV
    flux_against = (breakout_up and flux < 0) or (breakout_down and flux > 0)
    flux_neutral = abs(flux) < FAKE_FLUX_WEAK

    if volume_low and (flux_against or flux_neutral):
        conf = 0.65
        if flux_against:
            conf += 0.15
        return True, min(conf, 0.90)
    return False, 0.0


def _detect_fake_blind_whip(
        bars: List[BarLite], upper: float, lower: float, flux: float,
        is_blind: bool,
) -> Tuple[bool, float]:
    """模式 4: FAKE_BLIND_WHIP（盲区抽鞭）

    条件: 盲区快速突破后无后续，flux 衰减
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
        bars: List[BarLite], upper: float, lower: float, bandwidth: float, flux: float,
) -> Tuple[bool, float]:
    """模式 6: FAKE_WICK_CLUSTER（连续影线簇）

    条件: 最近 3-5 根 K 线的影线在 Zone 外，但实体在 Zone 内
    """
    if len(bars) < FAKE_WICK_MIN_BARS:
        return False, 0.0

    best_count = 0
    best_direction = None

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

            if body_bottom < lower or body_top > upper:
                continue

            if b.high > upper:
                shadow_up = b.high - body_top
                if shadow_up / body >= FAKE_WICK_SHADOW_RATIO:
                    up_wick_count += 1

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
        bars: List[BarLite], upper: float, lower: float, flux: float,
) -> Tuple[bool, float]:
    """模式 7: FAKE_TIME_TRAP（时间陷阱）

    条件: 价格突破 Zone 后在 Zone 外停留 2-5 根 K 线，没有后续动能，然后回归 Zone 内
    """
    if len(bars) < FAKE_TIME_TRAP_MIN_BARS + 1:
        return False, 0.0

    last_bar = bars[-1]
    if not (lower < last_bar.close < upper):
        return False, 0.0

    best_streak = 0
    best_direction = None

    for lookback in range(FAKE_TIME_TRAP_MIN_BARS, min(FAKE_TIME_TRAP_MAX_BARS + 1, len(bars))):
        segment = bars[-(lookback + 1):-1]
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

    trap_bars = bars[-(best_streak + 1):-1]
    mid = len(trap_bars) // 2
    vol_declining = False
    if mid > 0:
        early_vol = sum(b.volume for b in trap_bars[:mid]) / mid
        late_vol = sum(b.volume for b in trap_bars[mid:]) / (len(trap_bars) - mid)
        vol_declining = late_vol < early_vol * 0.9

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


# 假突破模式注册表（优先级顺序）
FAKE_PATTERN_REGISTRY = [
    ("GAP", _detect_fake_gap, lambda u, l, bw, flux, mv, blind: (u, l, flux)),
    ("PIN", _detect_fake_pin, lambda u, l, bw, flux, mv, blind: (u, l, bw, flux)),
    ("DSPIKE", _detect_fake_dspike, lambda u, l, bw, flux, mv, blind: (u, l, flux, mv)),
    ("VOLDIV", _detect_fake_voldiv, lambda u, l, bw, flux, mv, blind: (u, l, flux, mv)),
    ("WICK_CLUSTER", _detect_fake_wick_cluster, lambda u, l, bw, flux, mv, blind: (u, l, bw, flux)),
    ("TIME_TRAP", _detect_fake_time_trap, lambda u, l, bw, flux, mv, blind: (u, l, flux)),
    ("BLIND_WHIP", _detect_fake_blind_whip, lambda u, l, bw, flux, mv, blind: (u, l, flux, blind)),
]


def detect_fake_breakout_all(
        bars: List[BarLite],
        zone: Zone,
        flux: float,
        is_blind: bool,
) -> Tuple[bool, str, float]:
    """检测全部 7 种假突破模式（差异论 A9 触发器）

    按优先级顺序检测，第一个匹配即返回。

    Returns:
        (是否假突破, 模式名称, 置信度)
    """
    if len(bars) < 5 or zone.bandwidth <= 0:
        return False, "", 0.0

    upper = zone.upper
    lower = zone.lower
    bandwidth = zone.bandwidth

    volumes = [b.volume for b in bars[-20:]] if len(bars) >= 20 else [b.volume for b in bars]
    median_vol = _stats.median(volumes) if volumes else 1.0

    for pattern_name, detect_fn, arg_builder in FAKE_PATTERN_REGISTRY:
        args = arg_builder(upper, lower, bandwidth, flux, median_vol, is_blind)
        matched, conf = detect_fn(bars, *args)
        if matched:
            return True, pattern_name, conf

    return False, "", 0.0


# ═══════════════════════════════════════════════════════════
# 5 维突破评分（差异论 A5+A7）
# ═══════════════════════════════════════════════════════════

def score_breakout_5d(
        bars: List[BarLite],
        zone: Zone,
        flux: float,
        cycle_count: int,
        structural_age: int,
) -> Tuple[float, str]:
    """5 维突破评分

    维度权重:
        - 收盘穿透深度: 0.25
        - 量能扩张比: 0.25
        - 通量一致性(A5): 0.15
        - 压缩蓄势度: 0.20
        - 驻留时间比(A7): 0.15

    Returns:
        (评分 0-1, 评分说明)
    """
    if not bars or zone.bandwidth <= 0:
        return 0.0, "数据不足"

    last_bar = bars[-1]
    upper = zone.upper
    lower = zone.lower
    bandwidth = zone.bandwidth

    if last_bar.close > upper:
        direction = 1
        penetration = (last_bar.close - upper) / bandwidth
    elif last_bar.close < lower:
        direction = -1
        penetration = (lower - last_bar.close) / bandwidth
    else:
        return 0.0, "未突破 Zone"

    # 1. 收盘穿透深度 (0.25)
    score_pen = min(penetration / 0.5, 1.0)

    # 2. 量能扩张比 (0.25)
    volumes = [b.volume for b in bars[-20:]] if len(bars) >= 20 else [b.volume for b in bars]
    median_vol = _stats.median(volumes) if volumes else 1.0
    vol_ratio = last_bar.volume / median_vol if median_vol > 0 else 1.0
    score_vol = min(vol_ratio / 2.0, 1.0)

    # 3. 通量一致性 (0.15) — A5
    flux_aligned = (flux * direction) > 0
    if flux_aligned and abs(flux) > 0.3:
        score_flux = 1.0
    elif flux_aligned:
        score_flux = 0.5
    else:
        score_flux = 0.0

    # 4. 压缩蓄势度 (0.20)
    score_comp = min(cycle_count / 5, 1.0)

    # 5. 驻留时间比 (0.15) — A7
    score_dwell = min(structural_age / 30, 1.0)

    total = (
            score_pen * 0.25 +
            score_vol * 0.25 +
            score_flux * 0.15 +
            score_comp * 0.20 +
            score_dwell * 0.15
    )

    note = f"穿透{score_pen:.0%}/量能{score_vol:.0%}/通量{score_flux:.0%}/压缩{score_comp:.0%}/驻留{score_dwell:.0%}"
    return round(total, 3), note


# ═══════════════════════════════════════════════════════════
# 回踩确认（差异论 A1/A8 Zone 回归）
# ═══════════════════════════════════════════════════════════

def detect_pullback_confirmation(
        bars: List[BarLite],
        zone: Zone,
) -> Tuple[bool, float, str]:
    """检测回踩确认

    逻辑: 价格曾突破 Zone，现在回到边界附近测试，但未进入中心

    Returns:
        (是否确认, 置信度, 说明)
    """
    if len(bars) < 10 or zone.bandwidth <= 0:
        return False, 0.0, "数据不足"

    upper = zone.upper
    lower = zone.lower
    bandwidth = zone.bandwidth
    center = zone.center

    last_bar = bars[-1]
    last_close = last_bar.close

    # 检查历史是否有过突破
    had_breakout_up = any(b.close > upper for b in bars[-10:-1])
    had_breakout_down = any(b.close < lower for b in bars[-10:-1])

    if not (had_breakout_up or had_breakout_down):
        return False, 0.0, "无历史突破"

    # 当前必须在 Zone 内
    if not (lower < last_close < upper):
        return False, 0.0, "不在 Zone 内"

    near_upper = abs(last_close - upper) < bandwidth * 0.3
    near_lower = abs(last_close - lower) < bandwidth * 0.3

    # 多头回踩: 曾向上突破，现在在 upper 附近
    if had_breakout_up and near_upper and last_close > center:
        recent_vols = [b.volume for b in bars[-5:]]
        earlier_vols = [b.volume for b in bars[-10:-5]]
        if _stats.mean(recent_vols) < _stats.mean(earlier_vols) * 0.8:
            return True, 0.75, "缩量回踩上边界"
        return True, 0.60, "回踩上边界"

    # 空头回踩: 曾向下突破，现在在 lower 附近
    if had_breakout_down and near_lower and last_close < center:
        recent_vols = [b.volume for b in bars[-5:]]
        earlier_vols = [b.volume for b in bars[-10:-5]]
        if _stats.mean(recent_vols) < _stats.mean(earlier_vols) * 0.8:
            return True, 0.75, "缩量回踩下边界"
        return True, 0.60, "回踩下边界"

    return False, 0.0, "未满足回踩条件"


# ═══════════════════════════════════════════════════════════
# 结构老化检测（差异论 A7 稳定性衰减）
# ═══════════════════════════════════════════════════════════

def detect_structure_aging(
        structure: LightweightStructure,
        current_bar_idx: int,
) -> Tuple[bool, float, str]:
    """检测结构老化/失效

    条件:
        - 结构存在超过 AGING_BARS_THRESHOLD 根 K 线
        - 且仍处于 "→confirmation" 阶段（长时间未成熟）

    Returns:
        (是否老化, 置信度, 说明)
    """
    if structure.formation_bar_idx < 0:
        return False, 0.0, ""

    age = current_bar_idx - structure.formation_bar_idx
    phase = structure.phase_tendency

    if age > AGING_BARS_THRESHOLD and phase == "→confirmation":
        conf = min(0.60 + (age - AGING_BARS_THRESHOLD) * 0.01, 0.90)
        return True, conf, f"形成{age}根K线仍处confirmation阶段"

    if age > AGING_BARS_THRESHOLD * 2:
        conf = min(0.50 + (age - AGING_BARS_THRESHOLD * 2) * 0.01, 0.80)
        return True, conf, f"结构已老化{age}根K线"

    return False, 0.0, ""


# ═══════════════════════════════════════════════════════════
# 跨品种共振检测（差异论 A6 流耦合）
# ═══════════════════════════════════════════════════════════

SECTOR_MAP = {
    "cu": "有色金属", "al": "有色金属", "zn": "有色金属",
    "pb": "有色金属", "ni": "有色金属", "sn": "有色金属",
    "au": "贵金属", "ag": "贵金属",
    "rb": "黑色系", "hc": "黑色系", "ss": "黑色系",
    "i": "黑色系", "j": "黑色系", "jm": "黑色系",
    "bu": "能化", "ru": "能化", "fu": "能化", "sc": "能化",
    "l": "能化", "v": "能化", "pp": "能化", "eg": "能化",
    "eb": "能化", "pg": "能化", "ma": "能化", "ta": "能化",
    "m": "农产品", "y": "农产品", "p": "农产品", "a": "农产品",
    "b": "农产品", "c": "农产品", "cs": "农产品",
    "sr": "农产品", "cf": "农产品", "oi": "农产品", "rm": "农产品",
    "fg": "建材", "sa": "建材", "ur": "建材", "zc": "建材",
    "lc": "新能源", "si": "新能源",
}


def _get_sector(exchange_code: str) -> str:
    code = exchange_code.split(".")[-1].lower() if "." in exchange_code else exchange_code.lower()
    # 从合约代码中提取品种前缀（去掉数字月份）
    import re
    base_code = re.match(r"([a-zA-Z]+)", code)
    if base_code:
        code = base_code.group(1)
    return SECTOR_MAP.get(code, "其他")


@dataclass
class SignalRecord:
    """信号记录（用于共振检测）"""
    instrument: str
    sector: str
    direction: str
    signal_type: str
    quality_tier: str
    quality_score: float
    zone_center: float
    timestamp: float


@dataclass
class ResonanceAlert:
    """共振信号"""
    sector: str
    direction: str
    participating: List[str]
    resonance_level: int
    avg_quality: float
    signal_type_summary: str

    @property
    def is_strong(self) -> bool:
        return self.resonance_level >= 3

    def format(self) -> str:
        icon = "🔥" if self.is_strong else "⚡"
        dir_text = {"bullish": "看涨", "bearish": "看跌", "mixed": "混合"}.get(self.direction, "?")
        level_text = "强共振" if self.is_strong else "共振"
        lines = [
            f"{icon} {level_text} [{self.sector}] {dir_text} x{self.resonance_level}",
            f"   参与: {', '.join(self.participating)}",
            f"   平均质量: {self.avg_quality:.0%}",
            f"   类型: {self.signal_type_summary}",
        ]
        return "\n".join(lines)


class ResonanceTracker:
    """跨品种共振追踪器（A6 流耦合）"""

    def __init__(self, window_seconds: int = 600):
        self.window = window_seconds
        self.history: List[SignalRecord] = []
        self._last_resonance: Dict[str, float] = {}

    def record(self, record: SignalRecord):
        self.history.append(record)
        self._cleanup()

    def check_resonance(self, new_record: SignalRecord) -> Optional[ResonanceAlert]:
        sector = new_record.sector
        now = new_record.timestamp

        last = self._last_resonance.get(sector, 0)
        if now - last < 300:
            return None

        by_instrument = self._find_recent_signals(sector, now)
        if len(by_instrument) < 2:
            return None

        instruments = list(by_instrument.keys())
        direction = self._check_direction_consistency(by_instrument, instruments)
        avg_quality = sum(by_instrument[i].quality_score for i in instruments) / len(instruments)
        types = [by_instrument[i].signal_type for i in instruments]
        type_summary = " / ".join(f"{t}x{types.count(t)}" for t in set(types))

        self._last_resonance[sector] = now

        return ResonanceAlert(
            sector=sector,
            direction=direction,
            participating=instruments,
            resonance_level=len(instruments),
            avg_quality=avg_quality,
            signal_type_summary=type_summary,
        )

    def _find_recent_signals(self, sector: str, now: float) -> Dict[str, SignalRecord]:
        window_start = now - self.window
        recent = [
            r for r in self.history
            if r.sector == sector and r.timestamp >= window_start
        ]
        if len(recent) < 2:
            return {}

        by_instrument: Dict[str, SignalRecord] = {}
        for r in recent:
            if r.instrument not in by_instrument or r.timestamp > by_instrument[r.instrument].timestamp:
                by_instrument[r.instrument] = r
        return by_instrument

    @staticmethod
    def _check_direction_consistency(
            by_instrument: Dict[str, SignalRecord], instruments: List[str]
    ) -> str:
        polarities = []
        for i in instruments:
            d = by_instrument[i].direction
            polarities.append(1 if d == "bullish" else -1 if d == "bearish" else 0)
        positive = sum(1 for p in polarities if p > 0)
        negative = sum(1 for p in polarities if p < 0)

        if positive > negative * 1.5:
            return "bullish"
        elif negative > positive * 1.5:
            return "bearish"
        return "mixed"

    def get_sector_status(self) -> Dict[str, dict]:
        now = _time.time()
        window_start = now - self.window
        recent = [r for r in self.history if r.timestamp >= window_start]

        status = {}
        for r in recent:
            if r.sector not in status:
                status[r.sector] = {"count": 0, "instruments": set(), "directions": []}
            status[r.sector]["count"] += 1
            status[r.sector]["instruments"].add(r.instrument)
            status[r.sector]["directions"].append(r.direction)

        return {
            sector: {
                "signal_count": info["count"],
                "instruments": list(info["instruments"]),
                "direction": max(set(info["directions"]), key=info["directions"].count)
                if info["directions"] else "unknown",
            }
            for sector, info in status.items()
        }

    def _cleanup(self):
        cutoff = _time.time() - self.window * 2
        self.history = [r for r in self.history if r.timestamp >= cutoff]


# ═══════════════════════════════════════════════════════════
# PythonGO v2 策略
# ═══════════════════════════════════════════════════════════

class Params(BaseParams):
    """参数映射（PythonGO v2 规范）"""
    # v2 强制要求字段：用分号分隔多合约
    exchange: str = Field(default="SHFE;SHFE;SHFE", title="交易所（;分隔）")
    instrument_id: str = Field(default="cu2606;al2606;zn2606", title="合约（;分隔）")

    # 分析参数
    lookback: int = Field(default=100, title="分析回看K线数")
    min_amplitude: float = Field(default=0.02, title="最小摆动幅度")
    pivot_window: int = Field(default=3, title="极值检测窗口")
    zone_bandwidth_pct: float = Field(default=0.015, title="Zone带宽比例")
    min_quality_tier: Literal["A", "B", "C"] = Field(default="B", title="最低信号层级")
    kline_style: KLineStyle = Field(default="M5", title="K线周期")

    # 信号设置
    enable_alert: bool = Field(default=True, title="启用信号提示")
    enable_sound: bool = Field(default=True, title="启用声音提示")
    alert_cooldown: int = Field(default=300, title="信号冷却(秒)")
    resonance_window: int = Field(default=600, title="共振窗口(秒)")
    status_interval: int = Field(default=1800, title="状态输出间隔(秒)")

    # 交易设置
    enable_trade: bool = Field(default=False, title="启用自动下单")
    trade_volume: int = Field(default=1, title="基础下单手数")
    pay_up: float = Field(default=0, title="超价")
    enable_stop_loss: bool = Field(default=True, title="启用自动止损")
    enable_take_profit: bool = Field(default=True, title="启用自动止盈")
    close_all_on_stop: bool = Field(default=True, title="策略停止时平掉所有持仓")


class State(BaseState):
    """状态映射"""
    last_signal_time: str = Field(default="", title="上次信号时间")
    signal_count: int = Field(default=0, title="信号总数")
    active_positions: int = Field(default=0, title="当前持仓数")


class pythongo_signal(BaseStrategy):
    """
    价格结构信号策略 v4.1（差异论驱动 · PythonGO v2）

    差异论核心映射：
        A1/A8 → Zone 源端/汇端 = 入场/出场区域
        A2    → 离散状态：持有 or 观望
        A3    → CNN 3×3 局域性 = 只看近端 K 线
        A5    → conservation_flux = 通量方向过滤
        A6    → 流耦合 = 板块共振
        A7    → 稳定性验证 = 结构持续性
        A9    → 上升触发器 = 假突破/突破/结构老化

    信号优先级：
        假突破反向 > 突破确认 > 回踩确认 > 盲区突破 > 结构老化
    """

    def __init__(self) -> None:
        super().__init__()
        self.params_map = Params()
        self.state_map = State()

        # K 线合成器（v2 方式）
        self.kline_generators: Dict[str, KLineGenerator] = {}

        # 缓存
        self.bar_cache: Dict[str, deque] = {}
        self.price_cache: Dict[str, List[float]] = {}
        self._last_signal_ts: Dict[str, float] = {}
        self._bar_counters: Dict[str, int] = {}
        self._last_structure: Dict[str, Optional[LightweightStructure]] = {}
        # 持仓结构：{instrument_key: {direction, entry_price, stop_loss, take_profit, ...}}
        self._positions: Dict[str, dict] = {}

        # 共振追踪
        self.resonance_tracker = ResonanceTracker(window_seconds=600)
        self._last_status_time: float = 0.0

        self._tier_threshold = {"A": 0.75, "B": 0.50, "C": 0.25, "D": 0.0}

    # ─── 生命周期 ─────────────────────────────────────────
    def on_start(self) -> None:
        """策略启动：父类会自动订阅 exchange_list × instrument_list"""
        super().on_start()

        self.output("=" * 55)
        self.output("📡 价格结构信号策略 v4.1（差异论 · PythonGO v2）")
        self.output(f"  交易所: {self.params_map.exchange}")
        self.output(f"  合约:   {self.params_map.instrument_id}")
        self.output(f"  周期:   {self.params_map.kline_style}")
        self.output(f"  最低层级: {self.params_map.min_quality_tier}")
        self.output(f"  自动下单: {'是' if self.params_map.enable_trade else '否'}")
        self.output("=" * 55)

        # 板块分组显示
        sectors: Dict[str, list] = {}
        for exchange, code in zip(self.exchange_list, self.instrument_list):
            sector = _get_sector(f"{exchange}.{code}")
            sectors.setdefault(sector, []).append(code)
        self.output("板块分组:")
        for sector, codes in sectors.items():
            self.output(f"  {sector}: {', '.join(codes)}")
        self.output("")

        # 为每个合约创建 K 线合成器与缓存
        for exchange, instrument_id in zip(self.exchange_list, self.instrument_list):
            inst_key = f"{exchange}.{instrument_id}"

            # 闭包保留 exchange/instrument_id
            def make_callback(ex: str, iid: str):
                def _on_bar(bar: KLineData) -> None:
                    self._handle_bar(ex, iid, bar)

                return _on_bar

            self.kline_generators[inst_key] = KLineGenerator(
                callback=make_callback(exchange, instrument_id),
                exchange=exchange,
                instrument_id=instrument_id,
                style=self.params_map.kline_style,
            )

            self.bar_cache[inst_key] = deque(maxlen=self.params_map.lookback)
            self.price_cache[inst_key] = []
            self._bar_counters[inst_key] = 0
            self._last_structure[inst_key] = None
            self._positions[inst_key] = {}
            self.output(f"  ✓ 已初始化 {inst_key}")

    def on_stop(self) -> None:
        """策略停止：可选平掉所有持仓"""
        if self.params_map.close_all_on_stop and self.params_map.enable_trade:
            for inst_key, pos in list(self._positions.items()):
                if pos.get("direction"):
                    self._close_position(inst_key, reason="策略停止平仓")
        self.output(f"策略停止 · 累计信号: {self.state_map.signal_count}")
        super().on_stop()

    # ─── 行情回调 ─────────────────────────────────────────
    def on_tick(self, tick: TickData) -> None:
        """tick 级别：驱动 K 线合成 + 止损/止盈实时触发（更精确）"""
        super().on_tick(tick)
        inst_key = f"{tick.exchange}.{tick.instrument_id}"

        # 1. tick 触发 K 线合成
        if inst_key in self.kline_generators:
            self.kline_generators[inst_key].tick_to_kline(tick)

        # 2. tick 级止损止盈（比 bar 级更精确，避免漏过针尖价格）
        last_price = getattr(tick, "last_price", 0.0)
        if last_price > 0:
            self._check_sl_tp_by_tick(inst_key, last_price)

    def _handle_bar(self, exchange: str, instrument_id: str, bar: KLineData) -> None:
        """K 线完成回调 — 核心分析入口"""
        inst_key = f"{exchange}.{instrument_id}"
        if inst_key not in self.price_cache:
            return

        # 更新 OHLCV 缓存
        bar_lite = BarLite(
            open=bar.open, high=bar.high, low=bar.low,
            close=bar.close, volume=getattr(bar, "volume", 0),
        )
        self.bar_cache[inst_key].append(bar_lite)
        self.price_cache[inst_key].append(bar.close)
        if len(self.price_cache[inst_key]) > self.params_map.lookback:
            self.price_cache[inst_key] = self.price_cache[inst_key][-self.params_map.lookback:]

        self._bar_counters[inst_key] += 1
        current_bar_idx = self._bar_counters[inst_key]

        self._maybe_show_status()

        prices = self.price_cache[inst_key]
        bars_list = list(self.bar_cache[inst_key])
        if len(prices) < 30:
            return

        # 结构分析
        try:
            structure = analyze_structure_light(
                prices,
                window=self.params_map.pivot_window,
                min_amp=self.params_map.min_amplitude,
                bw_pct=self.params_map.zone_bandwidth_pct,
            )
        except Exception as e:
            self.output(f"⚠️ {inst_key} 分析异常: {e}")
            return

        if structure is None:
            return

        # 追踪 formation_bar_idx
        prev_structure = self._last_structure.get(inst_key)
        if prev_structure is None or (
                structure.zone.center != prev_structure.zone.center
                and abs(structure.zone.center - prev_structure.zone.center) > structure.zone.bandwidth * 0.5
        ):
            structure.formation_bar_idx = current_bar_idx
        elif prev_structure is not None:
            structure.formation_bar_idx = prev_structure.formation_bar_idx
        self._last_structure[inst_key] = structure

        # ATR + 差异论参数
        atr = compute_atr(bars_list)
        flux = structure.conservation_flux
        is_blind = structure.is_blind
        zone = structure.zone
        last_close = bar.close

        if last_close > zone.upper:
            price_position, direction = "above", "bullish"
        elif last_close < zone.lower:
            price_position, direction = "below", "bearish"
        else:
            price_position, direction = "inside", "mixed"

        flux_aligned = (flux > 0 and direction == "bullish") or (flux < 0 and direction == "bearish")

        signal = self._detect_signal(
            instrument=inst_key, bars_list=bars_list, structure=structure,
            atr=atr, flux=flux, direction=direction, price_position=price_position,
            flux_aligned=flux_aligned, is_blind=is_blind,
            current_bar_idx=current_bar_idx, last_close=last_close,
        )

        if signal is None:
            return

        # 质量层过滤
        if signal.quality_tier < self.params_map.min_quality_tier and signal.direction != "neutral":
            return

        if not self._can_emit_signal(inst_key):
            return

        self._emit_signal(inst_key, exchange, instrument_id, last_close, signal)
        self._mark_signal_emitted(inst_key)

    # ─── 信号检测（差异论驱动）──────────────────────────
    def _detect_signal(
            self, instrument: str, bars_list: List[BarLite],
            structure: LightweightStructure, atr: float,
            flux: float, direction: str, price_position: str,
            flux_aligned: bool, is_blind: bool,
            current_bar_idx: int, last_close: float,
    ) -> Optional[SignalInfo]:
        """差异论信号检测流水线

        优先级：假突破(A9) > 突破确认(A5+A7) > 回踩确认(A1/A8) > 盲区突破 > 结构老化(A7)
        """
        zone = structure.zone
        bandwidth = zone.bandwidth

        # ── 1. 假突破检测（A9 上升触发器，最高优先级） ──
        is_fake, fake_pattern, fake_conf = detect_fake_breakout_all(
            bars_list, zone, flux, is_blind
        )
        if is_fake:
            reverse_dir = "bearish" if price_position == "above" else "bullish" if price_position == "below" else "mixed"
            if reverse_dir == "mixed":
                return None

            fake_flux_aligned = (flux > 0 and reverse_dir == "bullish") or (flux < 0 and reverse_dir == "bearish")

            if reverse_dir == "bullish":
                entry = zone.lower
            else:
                entry = zone.upper

            sl, tp, rr = _compute_risk_reward(
                reverse_dir, entry, zone.upper, zone.lower, bandwidth,
                atr=atr, quality_tier=structure.quality_tier,
            )

            return SignalInfo(
                signal_type="fake_breakout",
                direction=reverse_dir,
                quality_tier=structure.quality_tier,
                quality_score=fake_conf,
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                rr_ratio=rr,
                position_factor=_position_factor(structure.quality_tier, is_blind),
                flux_aligned=fake_flux_aligned,
                stability_ok=structure.phase_tendency == "stable",
                is_blind=is_blind,
                ttl_bars=SIGNAL_TTL_BARS["fake_breakout"],
                signal_bar_idx=current_bar_idx,
                atr_value=atr,
                note=f"假突破·{fake_pattern}: flux反向确认",
                fake_pattern=fake_pattern,
            )

        # ── 2. 突破确认（A5+A7 联合验证） ──
        if price_position != "inside":
            breakout_score, breakout_note = score_breakout_5d(
                bars_list, zone, flux, structure.cycle_count,
                current_bar_idx - structure.formation_bar_idx if structure.formation_bar_idx > 0 else 0,
            )
            if breakout_score >= BREAKOUT_WEAK:
                if breakout_score >= BREAKOUT_STRONG:
                    conf = 0.85 + (breakout_score - BREAKOUT_STRONG) * 0.5
                else:
                    conf = 0.60 + (breakout_score - BREAKOUT_WEAK) / (BREAKOUT_STRONG - BREAKOUT_WEAK) * 0.25

                stability_ok = structure.phase_tendency == "stable"
                if not stability_ok:
                    conf = min(conf, 0.50)
                if is_blind:
                    conf *= 0.6

                sl, tp, rr = _compute_risk_reward(
                    direction, last_close, zone.upper, zone.lower, bandwidth,
                    atr=atr, quality_tier=structure.quality_tier,
                )

                return SignalInfo(
                    signal_type="breakout_confirm",
                    direction=direction,
                    quality_tier=structure.quality_tier,
                    quality_score=min(conf, 0.95),
                    entry_price=last_close,
                    stop_loss=sl,
                    take_profit=tp,
                    rr_ratio=rr,
                    position_factor=_position_factor(structure.quality_tier, is_blind),
                    flux_aligned=flux_aligned,
                    stability_ok=stability_ok,
                    is_blind=is_blind,
                    ttl_bars=SIGNAL_TTL_BARS["breakout_confirm"],
                    signal_bar_idx=current_bar_idx,
                    atr_value=atr,
                    note=f"突破确认: {breakout_note}",
                )

        # ── 3. 回踩确认（A1/A8 Zone 回归） ──
        is_pullback, pullback_conf, pullback_note = detect_pullback_confirmation(bars_list, zone)
        if is_pullback:
            stability_ok = structure.phase_tendency == "stable"
            conf = pullback_conf
            if not stability_ok:
                conf = min(conf, 0.50)
            if is_blind:
                conf *= 0.6

            sl, tp, rr = _compute_risk_reward(
                direction, last_close, zone.upper, zone.lower, bandwidth,
                atr=atr, quality_tier=structure.quality_tier,
            )

            return SignalInfo(
                signal_type="pullback_confirm",
                direction=direction if direction != "mixed" else ("bullish" if last_close > zone.center else "bearish"),
                quality_tier=structure.quality_tier,
                quality_score=min(conf, 0.90),
                entry_price=last_close,
                stop_loss=sl,
                take_profit=tp,
                rr_ratio=rr,
                position_factor=_position_factor(structure.quality_tier, is_blind) * 0.9,
                flux_aligned=flux_aligned,
                stability_ok=stability_ok,
                is_blind=is_blind,
                ttl_bars=SIGNAL_TTL_BARS["pullback_confirm"],
                signal_bar_idx=current_bar_idx,
                atr_value=atr,
                note=f"回踩确认: {pullback_note}",
            )

        # ── 4. 盲区突破观察 ──
        if is_blind and price_position != "inside":
            conf = 0.50
            if flux_aligned:
                conf += 0.15

            sl, tp, rr = _compute_risk_reward(
                direction, last_close, zone.upper, zone.lower, bandwidth,
                atr=atr, quality_tier=structure.quality_tier,
            )

            return SignalInfo(
                signal_type="blind_breakout",
                direction=direction,
                quality_tier=structure.quality_tier,
                quality_score=min(conf, 0.70),
                entry_price=last_close,
                stop_loss=sl,
                take_profit=tp,
                rr_ratio=rr * 0.5,
                position_factor=_position_factor(structure.quality_tier, True) * 0.5,
                flux_aligned=flux_aligned,
                stability_ok=False,
                is_blind=True,
                ttl_bars=SIGNAL_TTL_BARS["blind_breakout"],
                signal_bar_idx=current_bar_idx,
                atr_value=atr,
                note="盲区突破: 信号可靠性降低，建议观察",
            )

        # ── 5. 结构老化检测（A7 稳定性衰减） ──
        is_aging, aging_conf, aging_note = detect_structure_aging(structure, current_bar_idx)
        if is_aging:
            return SignalInfo(
                signal_type="structure_expired",
                direction="neutral",
                quality_tier=structure.quality_tier,
                quality_score=aging_conf,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                rr_ratio=0.0,
                position_factor=0.0,
                flux_aligned=False,
                stability_ok=False,
                is_blind=is_blind,
                ttl_bars=SIGNAL_TTL_BARS["structure_expired"],
                signal_bar_idx=current_bar_idx,
                atr_value=atr,
                note=f"结构老化: {aging_note}",
            )

        return None

    # ─── 止损止盈（tick 级，更精确）─────────────────────
    def _check_sl_tp_by_tick(self, inst_key: str, last_price: float) -> None:
        """tick 级止损止盈触发（比 bar 级更精确，避免漏过针尖价格）"""
        pos = self._positions.get(inst_key, {})
        if not pos or not pos.get("direction"):
            return

        direction = pos["direction"]
        sl = pos.get("stop_loss", 0)
        tp = pos.get("take_profit", 0)

        should_close = False
        reason = ""
        if direction == "bullish":
            if sl > 0 and last_price <= sl:
                should_close, reason = True, f"止损 (last={last_price:.2f} ≤ SL={sl:.2f})"
            elif tp > 0 and last_price >= tp:
                should_close, reason = True, f"止盈 (last={last_price:.2f} ≥ TP={tp:.2f})"
        elif direction == "bearish":
            if sl > 0 and last_price >= sl:
                should_close, reason = True, f"止损 (last={last_price:.2f} ≥ SL={sl:.2f})"
            elif tp > 0 and last_price <= tp:
                should_close, reason = True, f"止盈 (last={last_price:.2f} ≤ TP={tp:.2f})"

        if should_close:
            self.output(f"  🔔 {inst_key} {reason}")
            self._close_position(inst_key, reason=reason, ref_price=last_price)

    def _close_position(self, inst_key: str, reason: str = "", ref_price: float = 0.0) -> None:
        """v2 推荐使用 auto_close_position 自动处理平今/平昨"""
        pos = self._positions.get(inst_key, {})
        if not pos.get("direction"):
            return

        exchange, instrument_id = inst_key.split(".", 1)
        close_dir = "sell" if pos["direction"] == "bullish" else "buy"
        price = ref_price if ref_price > 0 else pos.get("entry_price", 0)
        price += (self.params_map.pay_up if close_dir == "buy" else -self.params_map.pay_up)

        if self.params_map.enable_trade:
            self.auto_close_position(
                exchange=exchange,
                instrument_id=instrument_id,
                volume=self.params_map.trade_volume,
                price=price,
                order_direction=close_dir,
                memo=reason,
            )

        self._positions[inst_key] = {}
        self.state_map.active_positions = sum(1 for p in self._positions.values() if p.get("direction"))

    # ─── 信号输出 ─────────────────────────────────────────
    def _emit_signal(self, inst_key: str, exchange: str, instrument_id: str,
                     last_price: float, signal: SignalInfo) -> None:
        timeframe = str(self.params_map.kline_style)
        trade_plan = signal.format_trade_plan(inst_key, timeframe, last_price)
        self.output("")
        self.output(trade_plan)

        if self.params_map.enable_sound:
            self.play_sound()

        if self.params_map.enable_trade and signal.direction in ("bullish", "bearish"):
            self._execute_trade(exchange, instrument_id, inst_key, last_price, signal)

        self._check_and_emit_resonance(
            instrument=inst_key, direction=signal.direction,
            signal_type=signal.signal_type, quality_tier=signal.quality_tier,
            quality_score=signal.quality_score, zone_center=0,
        )

    def _execute_trade(self, exchange: str, instrument_id: str, inst_key: str,
                       last_price: float, signal: SignalInfo) -> None:
        """v2 规范：开仓用 send_order，平仓用 auto_close_position"""
        pos = self._positions.get(inst_key, {})

        if pos.get("direction") == signal.direction:
            return  # 同向持仓不重复开

        # 反向持仓先平
        if pos.get("direction") and pos["direction"] != signal.direction:
            self._close_position(inst_key, reason="反向信号平仓", ref_price=last_price)

        # 开仓
        volume = max(1, int(self.params_map.trade_volume * signal.position_factor))
        direction = "buy" if signal.direction == "bullish" else "sell"
        price = last_price + (self.params_map.pay_up if direction == "buy" else -self.params_map.pay_up)

        order_id = self.send_order(
            exchange=exchange,
            instrument_id=instrument_id,
            volume=volume,
            price=price,
            order_direction=direction,
            memo=signal.signal_type,
        )

        if order_id and order_id > 0:
            self._positions[inst_key] = {
                "direction": signal.direction,
                "entry_price": last_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "signal_info": signal,
                "open_bar_idx": signal.signal_bar_idx,
            }
            self.state_map.active_positions = sum(
                1 for p in self._positions.values() if p.get("direction")
            )
            self.output(f"  📈 下单 #{order_id}: {direction} {volume}手 @ {price:.2f}")
            if signal.stop_loss > 0:
                self.output(f"     🛑 止损: {signal.stop_loss:.2f}")
            if signal.take_profit > 0:
                self.output(f"     🎯 止盈: {signal.take_profit:.2f}")

    # ─── 成交回调 ─────────────────────────────────────────
    def on_order(self, order: OrderData) -> None:
        super().on_order(order)

    def on_trade(self, trade: TradeData, log: bool = False) -> None:
        super().on_trade(trade, log)
        self.output(f"  ✅ 成交: {trade.instrument_id} {trade.direction} "
                    f"{trade.volume}手 @ {trade.price:.2f}")

    def on_error(self, error: dict) -> None:
        super().on_error(error)
        self.output(f"  ❌ 报单错误: {error.get('errMsg', '未知')}")

    # ─── 辅助方法 ─────────────────────────────────────────
    def _maybe_show_status(self) -> None:
        now = _time.time()
        if now - self._last_status_time < self.params_map.status_interval:
            return
        self._last_status_time = now
        status = self.resonance_tracker.get_sector_status()
        if not status:
            return
        self.output("")
        self.output("📊 ── 板块信号状态 ──")
        for sector, info in sorted(status.items()):
            icon = {"bullish": "🔴", "bearish": "🟢", "mixed": "🟡"}.get(info["direction"], "⚪")
            self.output(
                f"  {icon} {sector}: {info['signal_count']}条信号 · "
                f"{', '.join(info['instruments'])}"
            )
        self.output("")

    def _can_emit_signal(self, instrument: str) -> bool:
        now = _time.time()
        last = self._last_signal_ts.get(instrument, 0)
        return (now - last) >= self.params_map.alert_cooldown

    def _mark_signal_emitted(self, instrument: str) -> None:
        now = _time.time()
        self._last_signal_ts[instrument] = now
        self.state_map.signal_count += 1
        self.state_map.last_signal_time = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(now))

    def _check_and_emit_resonance(
            self, instrument: str, direction: str,
            signal_type: str, quality_tier: str,
            quality_score: float, zone_center: float,
    ):
        """记录信号并检查共振（A6 流耦合）"""
        sector = _get_sector(instrument)

        record = SignalRecord(
            instrument=instrument,
            sector=sector,
            direction=direction,
            signal_type=signal_type,
            quality_tier=quality_tier,
            quality_score=quality_score,
            zone_center=zone_center,
            timestamp=_time.time(),
        )

        self.resonance_tracker.record(record)

        resonance = self.resonance_tracker.check_resonance(record)
        if resonance:
            self.output("")
            self.output(resonance.format())
            self.output("")

            if resonance.is_strong:
                self.output(f"🔥🔥🔥 强共振！{sector}板块 {resonance.resonance_level} 个品种同时触发！")
                if self.params_map.enable_sound:
                    self.play_sound()
                    _time.sleep(0.3)
                    self.play_sound()

    def play_sound(self):
        try:
            import winsound
            winsound.Beep(1000, 500)
        except Exception:
            pass

    @property
    def main_indicator_data(self) -> Dict[str, float]:
        return {}
