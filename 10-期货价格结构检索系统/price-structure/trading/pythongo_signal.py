"""
价格结构信号提示工具 — PythonGO 策略

基于价格结构检索系统的信号检测策略，运行在无限易 PythonGO 环境中。

功能：
- 订阅多个品种的 K 线数据
- 每根 K 线收盘后运行轻量级结构分析
- 检测到 A/B 层质量结构时发出信号提示
- 支持多品种共振检测
- 可选自动下单

使用方法：
1. 将此文件放入 PythonGO 策略目录
2. 在无限易中加载策略
3. 设置参数：品种列表、灵敏度、是否自动下单
4. 启动策略

作者：价格结构形式系统 v3.0
"""

from datetime import time as dtime
from collections import deque
from dataclasses import dataclass, field
import math
import json

from pythongo.base import BaseParams, BaseState, Field
from pythongo.classdef import KLineData, TickData, OrderData, TradeData
from pythongo.core import KLineStyleType
from pythongo.ui import BaseStrategy


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
    """关键区"""
    center: float
    bandwidth: float
    touches: int = 0
    strength: float = 0.0

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
    cycle_count: int
    avg_speed_ratio: float
    avg_time_ratio: float
    direction: str  # "bullish" / "bearish" / "mixed"
    quality_score: float
    quality_tier: str  # A/B/C/D
    phase_tendency: str
    conservation_flux: float
    is_blind: bool

    @property
    def is_actionable(self):
        return self.quality_tier in ("A", "B") and not self.is_blind


def extract_pivots_light(prices, window=3, min_amp=0.02):
    """轻量级极值提取"""
    n = len(prices)
    if n < window * 2 + 1:
        return []

    pivots = []
    for i in range(window, n - window):
        # 检查高点
        is_high = all(prices[j] < prices[i] for j in range(i - window, i + window + 1) if j != i)
        is_low = all(prices[j] > prices[i] for j in range(i - window, i + window + 1) if j != i)

        if not is_high and not is_low:
            continue

        # 幅度过滤
        mid = (prices[max(0, i - window)] + prices[min(n - 1, i + window)]) / 2
        amp = abs(prices[i] - mid) / mid if mid > 0 else 0
        if amp < min_amp:
            continue

        pivots.append(Pivot(idx=i, price=prices[i], direction=1 if is_high else -1))

    # 强制交替
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
    """轻量级 Zone 检测"""
    if len(pivots) < 2:
        return []

    # 按价格聚类
    zones = []
    used = set()

    for i, p in enumerate(pivots):
        if i in used:
            continue
        cluster = [p]
        used.add(i)
        bw = p.price * bandwidth_pct

        for j, q in enumerate(pivots):
            if j in used:
                continue
            if abs(p.price - q.price) < bw:
                cluster.append(q)
                used.add(j)

        if len(cluster) >= 2:
            center = sum(c.price for c in cluster) / len(cluster)
            zones.append(Zone(
                center=center,
                bandwidth=bw,
                touches=len(cluster),
                strength=sum(0.9 ** k for k in range(len(cluster))),
            ))

    return zones


def compute_quality_light(cycle_count, speed_ratio, zone_strength, is_blind=False):
    """轻量级质量评分"""
    score = 0.0

    # Cycle 数量 (0.3)
    if cycle_count >= 5:
        score += 0.3
    elif cycle_count >= 3:
        score += 0.2
    elif cycle_count >= 2:
        score += 0.1

    # Zone 强度 (0.3)
    if zone_strength >= 2.5:
        score += 0.3
    elif zone_strength >= 1.5:
        score += 0.2
    elif zone_strength >= 0.5:
        score += 0.1

    # 速度比合理性 (0.2)
    if 0.3 <= speed_ratio <= 5.0:
        score += 0.2
    elif 0.1 <= speed_ratio <= 10.0:
        score += 0.1

    # 投影 (0.2)
    if not is_blind:
        score += 0.2
    else:
        score += 0.05

    # 分层
    if score >= 0.75:
        tier = "A"
    elif score >= 0.50:
        tier = "B"
    elif score >= 0.25:
        tier = "C"
    else:
        tier = "D"

    return score, tier


def analyze_structure_light(prices, window=3, min_amp=0.02, bw_pct=0.015):
    """
    轻量级结构分析（完整流程）

    返回最佳结构或 None
    """
    if len(prices) < 20:
        return None

    # 1. 极值提取
    pivots = extract_pivots_light(prices, window=window, min_amp=min_amp)
    if len(pivots) < 4:
        return None

    # 2. Zone 检测
    zones = detect_zones_light(pivots, bandwidth_pct=bw_pct)
    if not zones:
        return None

    # 3. 取最强 Zone
    best_zone = max(zones, key=lambda z: z.strength)

    # 4. 计算 cycle 特征
    # 简化：用极值点进出 Zone 的次数近似 cycle
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

    # 5. 方向
    ups = sum(1 for p in pivots if p.direction == 1)
    downs = sum(1 for p in pivots if p.direction == -1)
    if ups > downs * 1.3:
        direction = "bullish"
    elif downs > ups * 1.3:
        direction = "bearish"
    else:
        direction = "mixed"

    # 6. 质量评分
    # 检查投影压缩（简化：用最近价格波动率）
    recent = prices[-20:]
    vol = _stddev(recent) / (sum(recent) / len(recent)) if recent else 0
    is_blind = vol < 0.005  # 波动率极低 → 高压缩

    quality_score, quality_tier = compute_quality_light(
        cycle_count, avg_sr, best_zone.strength, is_blind
    )

    # 7. 守恒通量（简化）
    if len(speed_ratios) >= 2:
        recent_sr = sum(speed_ratios[-2:]) / 2
        early_sr = sum(speed_ratios[:2]) / 2
        flux = (recent_sr - early_sr) / max(early_sr, 0.01)
        flux = max(-1, min(1, flux))
    else:
        flux = 0

    # 8. 阶段判断
    if flux > 0.3:
        phase = "→breakdown"
    elif flux < -0.3:
        phase = "→confirmation"
    else:
        phase = "stable"

    return LightweightStructure(
        zone=best_zone,
        cycle_count=cycle_count,
        avg_speed_ratio=avg_sr,
        avg_time_ratio=1.0,  # 简化
        direction=direction,
        quality_score=quality_score,
        quality_tier=quality_tier,
        phase_tendency=phase,
        conservation_flux=flux,
        is_blind=is_blind,
    )


def _stddev(arr):
    if len(arr) < 2:
        return 0
    mean = sum(arr) / len(arr)
    return math.sqrt(sum((x - mean) ** 2 for x in arr) / len(arr))


# ═══════════════════════════════════════════════════════════
# 假突破反转信号 — 日内高质量信号
# ═══════════════════════════════════════════════════════════

@dataclass
class BreakoutReversalSignal:
    """
    假突破反转信号

    信号类型：
    - 上破回落 (bearish_reversal): 价格突破 Zone 上方 → 反折回到 Zone 下方 → 看跌
    - 下破反弹 (bullish_reversal): 价格跌破 Zone 下方 → 反弹回到 Zone 上方 → 看涨

    质量评分因子：
    1. 突破幅度：突破 Zone 越远，反转信号越强（突破被充分验证后失败）
    2. 回落速度：回落越快，信号越强（急跌/急涨反转）
    3. Zone 强度：Zone 触及次数越多，支撑/阻力越可靠
    4. 成交量配合：回落时放量更佳（需外部数据）
    """
    signal_type: str           # "bearish_reversal" / "bullish_reversal"
    zone: Zone
    breakout_price: float      # 突破时的价格极值
    reversal_price: float      # 反转后的当前价格
    breakout_depth: float      # 突破 Zone 的幅度（相对 bandwidth）
    reversal_speed: float      # 反转速度（回落幅度 / 突破幅度）
    quality_score: float       # 综合质量分 [0, 1]
    quality_tier: str          # A/B/C/D
    bar_index: int             # 信号触发的 K 线索引

    @property
    def direction(self) -> str:
        return "bearish" if self.signal_type == "bearish_reversal" else "bullish"

    @property
    def is_actionable(self) -> bool:
        return self.quality_tier in ("A", "B")


def detect_breakout_reversal(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    zones: list[Zone],
    lookback: int = 10,
    min_breakout_pct: float = 0.3,
) -> BreakoutReversalSignal | None:
    """
    检测假突破反转信号

    逻辑：
    1. 在最近 lookback 根 K 线中，找到价格突破 Zone 的时刻
    2. 检查当前价格是否已经反转回到 Zone 的另一侧
    3. 如果满足条件，生成信号

    Args:
        highs: 最高价序列（按时间升序）
        lows: 最低价序列
        closes: 收盘价序列
        zones: 检测到的 Zone 列表
        lookback: 回看 K 线数
        min_breakout_pct: 最小突破幅度（相对 Zone bandwidth）

    Returns:
        BreakoutReversalSignal 或 None
    """
    n = len(closes)
    if n < lookback + 1 or not zones:
        return None

    current_close = closes[-1]
    best_signal = None

    for zone in zones:
        if zone.bandwidth <= 0:
            continue

        # ── 信号 1: 上破回落 (bearish_reversal) ──
        # 在过去 lookback 根 K 线中，检查是否有 high 突破 Zone 上方
        max_high_above = 0
        max_high_idx = -1
        for i in range(max(0, n - lookback - 1), n - 1):
            if highs[i] > zone.upper:
                depth = (highs[i] - zone.upper) / zone.bandwidth
                if depth > max_high_above:
                    max_high_above = depth
                    max_high_idx = i

        # 如果有突破，且当前价格已回到 Zone 下方
        if max_high_above >= min_breakout_pct and current_close < zone.center:
            # 计算反转速度：从突破极值到当前价的回落 / 突破幅度
            breakout_extreme = highs[max_high_idx]
            reversal_distance = breakout_extreme - current_close
            breakout_distance = breakout_extreme - zone.upper
            reversal_speed = reversal_distance / breakout_distance if breakout_distance > 0 else 0

            # 质量评分
            score = _score_breakout_reversal(
                breakout_depth=max_high_above,
                reversal_speed=reversal_speed,
                zone_strength=zone.strength,
                zone_touches=zone.touches,
                bars_since_breakout=(n - 1) - max_high_idx,
            )

            tier = "A" if score >= 0.75 else "B" if score >= 0.50 else "C" if score >= 0.25 else "D"

            signal = BreakoutReversalSignal(
                signal_type="bearish_reversal",
                zone=zone,
                breakout_price=breakout_extreme,
                reversal_price=current_close,
                breakout_depth=max_high_above,
                reversal_speed=reversal_speed,
                quality_score=score,
                quality_tier=tier,
                bar_index=n - 1,
            )

            if best_signal is None or signal.quality_score > best_signal.quality_score:
                best_signal = signal

        # ── 信号 2: 下破反弹 (bullish_reversal) ──
        # 在过去 lookback 根 K 线中，检查是否有 low 跌破 Zone 下方
        min_low_below = 0
        min_low_idx = -1
        for i in range(max(0, n - lookback - 1), n - 1):
            if lows[i] < zone.lower:
                depth = (zone.lower - lows[i]) / zone.bandwidth
                if depth > min_low_below:
                    min_low_below = depth
                    min_low_idx = i

        # 如果有跌破，且当前价格已回到 Zone 上方
        if min_low_below >= min_breakout_pct and current_close > zone.center:
            # 计算反转速度
            breakout_extreme = lows[min_low_idx]
            reversal_distance = current_close - breakout_extreme
            breakout_distance = zone.lower - breakout_extreme
            reversal_speed = reversal_distance / breakout_distance if breakout_distance > 0 else 0

            score = _score_breakout_reversal(
                breakout_depth=min_low_below,
                reversal_speed=reversal_speed,
                zone_strength=zone.strength,
                zone_touches=zone.touches,
                bars_since_breakout=(n - 1) - min_low_idx,
            )

            tier = "A" if score >= 0.75 else "B" if score >= 0.50 else "C" if score >= 0.25 else "D"

            signal = BreakoutReversalSignal(
                signal_type="bullish_reversal",
                zone=zone,
                breakout_price=breakout_extreme,
                reversal_price=current_close,
                breakout_depth=min_low_below,
                reversal_speed=reversal_speed,
                quality_score=score,
                quality_tier=tier,
                bar_index=n - 1,
            )

            if best_signal is None or signal.quality_score > best_signal.quality_score:
                best_signal = signal

    return best_signal


def _score_breakout_reversal(
    breakout_depth: float,
    reversal_speed: float,
    zone_strength: float,
    zone_touches: int,
    bars_since_breakout: int,
) -> float:
    """
    假突破反转信号质量评分

    评分维度：
    1. 突破幅度 (0.3): 突破越远 → 反转越有意义
    2. 反转速度 (0.3): 回落越快 → 信号越强
    3. Zone 强度 (0.25): Zone 越强 → 支撑/阻力越可靠
    4. 时间窗口 (0.15): 突破后越快反转越好（太久说明趋势可能成立）
    """
    score = 0.0

    # 1. 突破幅度 (0.3)
    # depth=0.5 → 0.5分, depth=1.0 → 0.7分, depth=2.0 → 0.9分
    depth_score = min(1.0, 0.3 + breakout_depth * 0.3)
    score += 0.3 * depth_score

    # 2. 反转速度 (0.3)
    # speed=0.5 → 0.4分, speed=1.0 → 0.7分, speed=2.0 → 1.0分
    speed_score = min(1.0, reversal_speed * 0.5)
    score += 0.3 * speed_score

    # 3. Zone 强度 (0.25)
    # touches=2 → 0.3分, touches=4 → 0.6分, touches=6+ → 0.9分
    strength_score = min(1.0, zone_touches * 0.15)
    score += 0.25 * strength_score

    # 4. 时间窗口 (0.15)
    # 越快反转越好：1-3根K线最佳，超过5根打折
    if bars_since_breakout <= 3:
        time_score = 1.0
    elif bars_since_breakout <= 5:
        time_score = 0.6
    else:
        time_score = max(0.2, 1.0 - bars_since_breakout * 0.1)
    score += 0.15 * time_score

    return min(score, 1.0)


# ═══════════════════════════════════════════════════════════
# PythonGO 策略
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# 跨品种共振检测 — 多品种同步监测 + 板块联动
# ═══════════════════════════════════════════════════════════

import time as _time

# 板块映射（品种代码 → 板块）
SECTOR_MAP = {
    # 有色金属
    "cu": "有色金属", "al": "有色金属", "zn": "有色金属",
    "pb": "有色金属", "ni": "有色金属", "sn": "有色金属",
    # 贵金属
    "au": "贵金属", "ag": "贵金属",
    # 黑色系
    "rb": "黑色系", "hc": "黑色系", "ss": "黑色系",
    "i": "黑色系", "j": "黑色系", "jm": "黑色系",
    # 能化
    "bu": "能化", "ru": "能化", "fu": "能化", "sc": "能化",
    "l": "能化", "v": "能化", "pp": "能化", "eg": "能化",
    "eb": "能化", "pg": "能化", "ma": "能化", "ta": "能化",
    # 农产品
    "m": "农产品", "y": "农产品", "p": "农产品", "a": "农产品",
    "b": "农产品", "c": "农产品", "cs": "农产品",
    "sr": "农产品", "cf": "农产品", "oi": "农产品", "rm": "农产品",
    # 建材
    "fg": "建材", "sa": "建材", "ur": "建材", "zc": "建材",
    # 新能源
    "lc": "新能源", "si": "新能源",
}


def _get_sector(exchange_code: str) -> str:
    """从 'SHFE.cu' 提取板块"""
    code = exchange_code.split(".")[-1].lower() if "." in exchange_code else exchange_code.lower()
    return SECTOR_MAP.get(code, "其他")


def _get_direction_polarity(direction: str) -> int:
    """方向转极性：bullish=+1, bearish=-1, mixed=0"""
    if direction == "bullish":
        return 1
    elif direction == "bearish":
        return -1
    return 0


@dataclass
class SignalRecord:
    """单条信号记录"""
    instrument: str
    sector: str
    direction: str       # "bullish" / "bearish"
    signal_type: str     # "structure" / "breakout_reversal"
    quality_tier: str
    quality_score: float
    zone_center: float
    timestamp: float     # time.time()


@dataclass
class ResonanceAlert:
    """共振信号"""
    sector: str
    direction: str               # "bullish" / "bearish" / "mixed"
    participating: list[str]     # 参与品种列表
    resonance_level: int         # 2=共振, 3+=强共振
    avg_quality: float
    signal_type_summary: str     # 各品种信号类型摘要

    @property
    def is_strong(self) -> bool:
        return self.resonance_level >= 3

    def format(self) -> str:
        icon = "🔥" if self.is_strong else "⚡"
        dir_text = {"bullish": "看涨", "bearish": "看跌", "mixed": "混合"}.get(self.direction, "?")
        level_text = "强共振" if self.is_strong else "共振"
        parts = [
            f"{icon} {level_text} [{self.sector}] {dir_text} ×{self.resonance_level}",
            f"   参与: {', '.join(self.participating)}",
            f"   平均质量: {self.avg_quality:.0%}",
        ]
        return "\n".join(parts)


class ResonanceTracker:
    """
    跨品种共振追踪器

    在一个滑动时间窗口内，追踪所有品种的信号。
    当同板块多个品种同时触发信号时，检测到共振。

    逻辑：
    1. 每个信号记录 instrument + sector + direction + timestamp
    2. 在 window 秒内的信号视为"同时"
    3. 同板块 ≥2 个品种同时触发 → 共振
    4. 同板块 ≥3 个品种同时触发 → 强共振
    5. 方向一致性检查：同向 > 异向
    """

    def __init__(self, window_seconds: int = 600):
        self.window = window_seconds
        self.history: list[SignalRecord] = []
        self._last_resonance: dict[str, float] = {}  # sector → last resonance time

    def record(self, record: SignalRecord):
        """记录一个信号"""
        self.history.append(record)
        self._cleanup()

    def check_resonance(self, new_record: SignalRecord) -> ResonanceAlert | None:
        """
        检查新信号是否触发共振

        Returns:
            ResonanceAlert 如果检测到共振，否则 None
        """
        sector = new_record.sector
        now = new_record.timestamp

        # 获取同板块、同时间窗口内的信号
        window_start = now - self.window
        recent = [
            r for r in self.history
            if r.sector == sector and r.timestamp >= window_start
        ]

        if len(recent) < 2:
            return None

        # 去重：每个品种只取最新的一条
        by_instrument: dict[str, SignalRecord] = {}
        for r in recent:
            if r.instrument not in by_instrument or r.timestamp > by_instrument[r.instrument].timestamp:
                by_instrument[r.instrument] = r

        instruments = list(by_instrument.keys())
        if len(instruments) < 2:
            return None

        # 共振冷却：同板块 5 分钟内不重复触发
        last = self._last_resonance.get(sector, 0)
        if now - last < 300:
            return None

        # 方向一致性
        polarities = [_get_direction_polarity(by_instrument[i].direction) for i in instruments]
        positive = sum(1 for p in polarities if p > 0)
        negative = sum(1 for p in polarities if p < 0)

        if positive > negative * 1.5:
            direction = "bullish"
        elif negative > positive * 1.5:
            direction = "bearish"
        else:
            direction = "mixed"

        # 平均质量
        avg_quality = sum(by_instrument[i].quality_score for i in instruments) / len(instruments)

        # 信号类型摘要
        types = [by_instrument[i].signal_type for i in instruments]
        type_summary = " / ".join(f"{t}×{types.count(t)}" for t in set(types))

        self._last_resonance[sector] = now

        return ResonanceAlert(
            sector=sector,
            direction=direction,
            participating=instruments,
            resonance_level=len(instruments),
            avg_quality=avg_quality,
            signal_type_summary=type_summary,
        )

    def get_sector_status(self) -> dict[str, dict]:
        """获取各板块当前信号状态"""
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

        # 转为可序列化格式
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
        """清理过期记录"""
        cutoff = _time.time() - self.window * 2
        self.history = [r for r in self.history if r.timestamp >= cutoff]


# ═══════════════════════════════════════════════════════════
# PythonGO 策略
    """参数映射"""
    # 品种设置（逗号分隔多个品种）
    instruments: str = Field(
        default="SHFE.cu,SHFE.al,SHFE.zn",
        title="品种列表（交易所.合约,交易所.合约）"
    )

    # 分析参数
    lookback: int = Field(default=100, title="分析回看K线数")
    min_amplitude: float = Field(default=0.02, title="最小摆动幅度")
    pivot_window: int = Field(default=3, title="极值检测窗口")
    zone_bandwidth_pct: float = Field(default=0.015, title="Zone带宽比例")
    min_quality_tier: str = Field(default="B", title="最低信号层级（A/B/C）")

    # K 线周期
    kline_style: KLineStyleType = Field(default="M5", title="K线周期")

    # 信号设置
    enable_alert: bool = Field(default=True, title="启用信号提示")
    enable_sound: bool = Field(default=True, title="启用声音提示")
    alert_cooldown: int = Field(default=300, title="信号冷却时间（秒）")
    resonance_window: int = Field(default=600, title="共振检测窗口（秒）")
    status_interval: int = Field(default=1800, title="市场状态输出间隔（秒）")

    # 交易设置（可选）
    enable_trade: bool = Field(default=False, title="启用自动下单")
    trade_volume: int = Field(default=1, title="下单手数")
    pay_up: float = Field(default=0, title="超价")


class State(BaseState):
    """状态映射"""
    last_signal_time: str = Field(default="", title="上次信号时间")
    signal_count: int = Field(default=0, title="信号总数")
    current_structures: str = Field(default="{}", title="当前结构JSON")


class PriceStructureSignal(BaseStrategy):
    """
    价格结构信号提示策略

    基于轻量级结构分析，在 PythonGO 环境中实时检测高质量结构信号。

    信号触发条件：
    1. 结构质量为 A 或 B 层
    2. 非高压缩状态（投影非盲）
    3. 距上次信号超过冷却时间

    信号类型：
    - 🟢 A层看涨：高质量看涨结构
    - 🔵 A层看跌：高质量看跌结构
    - 🟡 B层看涨：中等看涨结构
    - 🟡 B层看跌：中等看跌结构
    """

    def __init__(self):
        super().__init__()
        self.params_map = Params()
        self.state_map = State()

        # K 线缓存 {instrument: deque}
        self.kline_cache: dict[str, deque] = {}
        self.price_cache: dict[str, list] = {}

        # 信号冷却
        self._last_signal_ts: dict[str, float] = {}

        # 跨品种共振追踪
        self.resonance_tracker = ResonanceTracker(
            window_seconds=self.params_map.resonance_window
        )
        self._last_status_time: float = 0

        # 解析品种列表
        self.instrument_list = self._parse_instruments(self.params_map.instruments)

        # 质量层级阈值
        self._tier_threshold = {"A": 0.75, "B": 0.50, "C": 0.25}
        self._min_tier_score = self._tier_threshold.get(
            self.params_map.min_quality_tier, 0.50
        )

    def _parse_instruments(self, raw: str) -> list[tuple[str, str]]:
        """解析品种列表：'SHFE.cu,SHFE.al' → [('SHFE', 'cu'), ...]"""
        result = []
        for item in raw.split(","):
            item = item.strip()
            if "." in item:
                exchange, code = item.split(".", 1)
                result.append((exchange.strip(), code.strip()))
        return result

    # ─── 生命周期 ──────────────────────────────────────────

    def on_start(self):
        """策略启动"""
        super().on_start()
        self.output("=" * 50)
        self.output("📡 价格结构信号提示策略 v3.0")
        self.output(f"   品种: {self.params_map.instruments}")
        self.output(f"   周期: {self.params_map.kline_style}")
        self.output(f"   回看: {self.params_map.lookback} 根K线")
        self.output(f"   最低层级: {self.params_map.min_quality_tier}")
        self.output(f"   共振窗口: {self.params_map.resonance_window}秒")
        self.output(f"   状态间隔: {self.params_map.status_interval}秒")
        self.output(f"   自动下单: {'是' if self.params_map.enable_trade else '否'}")
        self.output("=" * 50)

        # 显示板块分组
        sectors: dict[str, list] = {}
        for exchange, code in self.instrument_list:
            sector = _get_sector(f"{exchange}.{code}")
            sectors.setdefault(sector, []).append(code)
        self.output("板块分组:")
        for sector, codes in sectors.items():
            self.output(f"   {sector}: {', '.join(codes)}")
        self.output("")

        # 订阅所有品种
        for exchange, code in self.instrument_list:
            self.sub_market_data(exchange=exchange, instrument_id=code)
            self.kline_cache[f"{exchange}.{code}"] = deque(maxlen=self.params_map.lookback)
            self.price_cache[f"{exchange}.{code}"] = []
            self.output(f"   ✓ 订阅 {exchange}.{code}")

    def on_stop(self):
        """策略停止"""
        super().on_stop()
        self.output(f"策略停止 · 累计信号: {self.state_map.signal_count}")

        for exchange, code in self.instrument_list:
            self.unsub_market_data(exchange=exchange, instrument_id=code)

    # ─── 行情回调 ──────────────────────────────────────────

    def on_tick(self, tick: TickData) -> None:
        """Tick 推送"""
        super().on_tick(tick)

    def on_bar(self, bar: KLineData) -> None:
        """
        K 线推送 — 核心分析入口

        每根 K 线收盘后：
        1. 更新价格缓存
        2. 运行结构分析
        3. 检查信号条件
        4. 触发信号提示
        """
        super().on_bar(bar)

        instrument = f"{bar.exchange}.{bar.instrument_id}"
        if instrument not in self.price_cache:
            return

        # 更新缓存
        self.price_cache[instrument].append(bar.close)
        if len(self.price_cache[instrument]) > self.params_map.lookback:
            self.price_cache[instrument] = self.price_cache[instrument][-self.params_map.lookback:]

        # 更新高低价缓存
        if not hasattr(self, 'high_cache'):
            self.high_cache: dict[str, list] = {}
            self.low_cache: dict[str, list] = {}
        self.high_cache.setdefault(instrument, []).append(bar.high)
        self.low_cache.setdefault(instrument, []).append(bar.low)
        if len(self.high_cache[instrument]) > self.params_map.lookback:
            self.high_cache[instrument] = self.high_cache[instrument][-self.params_map.lookback:]
            self.low_cache[instrument] = self.low_cache[instrument][-self.params_map.lookback:]

        prices = self.price_cache[instrument]
        if len(prices) < 30:
            return

        # ── 信号 1: 结构分析信号 ──
        try:
            structure = analyze_structure_light(
                prices,
                window=self.params_map.pivot_window,
                min_amp=self.params_map.min_amplitude,
                bw_pct=self.params_map.zone_bandwidth_pct,
            )
        except Exception as e:
            self.output(f"⚠️ {instrument} 分析异常: {e}")
            return

        # ── 信号 2: 假突破反转信号 ──
        breakout_signal = None
        if structure and structure.zone:
            try:
                breakout_signal = detect_breakout_reversal(
                    highs=self.high_cache.get(instrument, []),
                    lows=self.low_cache.get(instrument, []),
                    closes=prices,
                    zones=[structure.zone],
                    lookback=10,
                    min_breakout_pct=0.3,
                )
            except Exception:
                pass

        # ── 处理假突破信号（优先级更高）──
        if breakout_signal and breakout_signal.is_actionable:
            if self._check_cooldown(instrument):
                self._emit_breakout_signal(instrument, bar, breakout_signal)
                return  # 假突破信号优先，不再触发普通信号

        # ── 处理结构信号 ──
        if structure is None:
            return

        if not structure.is_actionable:
            return

        if structure.quality_score < self._min_tier_score:
            return

        if not self._check_cooldown(instrument):
            return

        self._emit_structure_signal(instrument, bar, structure)

        # ── 定期输出市场状态 ──
        self._maybe_show_status()

    def _maybe_show_status(self):
        """定期输出各板块信号状态"""
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
                f"   {icon} {sector}: {info['signal_count']}条信号 · "
                f"{', '.join(info['instruments'])}"
            )
        self.output("")

    # ─── 交易逻辑 ──────────────────────────────────────────

    def _auto_trade(self, bar: KLineData, structure: LightweightStructure):
        """
        自动下单逻辑

        仅在 A 层 + 方向明确时下单。
        """
        if structure.quality_tier != "A":
            return
        if structure.direction == "mixed":
            return

        instrument = f"{bar.exchange}.{bar.instrument_id}"
        current_price = bar.close

        # 检查持仓
        position = self.get_position(bar.instrument_id)
        # position 需要根据实际 API 调整

        if structure.direction == "bullish":
            # 看涨信号 → 买入
            self.send_order(
                exchange=bar.exchange,
                instrument_id=bar.instrument_id,
                volume=self.params_map.trade_volume,
                price=current_price + self.params_map.pay_up,
                order_direction="buy",
            )
            self.output(f"   📈 买入 {bar.instrument_id} @ {current_price:.2f}")

        elif structure.direction == "bearish":
            # 看跌信号 → 卖出
            self.send_order(
                exchange=bar.exchange,
                instrument_id=bar.instrument_id,
                volume=self.params_map.trade_volume,
                price=current_price - self.params_map.pay_up,
                order_direction="sell",
            )
            self.output(f"   📉 卖出 {bar.instrument_id} @ {current_price:.2f}")

    # ─── 成交回调 ──────────────────────────────────────────

    def on_order(self, order: OrderData) -> None:
        """委托回调"""
        super().on_order(order)

    def on_trade(self, trade: TradeData, log: bool = False) -> None:
        """成交回调"""
        super().on_trade(trade, log)
        self.output(
            f"   ✅ 成交: {trade.instrument_id} "
            f"{trade.direction} {trade.volume}手 @ {trade.price:.2f}"
        )

    def on_order_cancel(self, order: OrderData) -> None:
        """撤单回调"""
        super().on_order_cancel(order)

    # ─── 辅助方法 ──────────────────────────────────────────

    def _check_cooldown(self, instrument: str) -> bool:
        """检查信号冷却"""
        import time
        now = time.time()
        last = self._last_signal_ts.get(instrument, 0)
        if now - last < self.params_map.alert_cooldown:
            return False
        self._last_signal_ts[instrument] = now
        self.state_map.signal_count += 1
        return True

    def _emit_structure_signal(self, instrument: str, bar: KLineData, structure):
        """输出结构信号 + 共振检测"""
        direction_icon = "🔴" if structure.direction == "bullish" else "🟢"
        tier_icon = {"A": "🟢", "B": "🔵", "C": "🟡"}.get(structure.quality_tier, "⚪")

        signal_text = (
            f"{tier_icon} [{structure.quality_tier}层] {direction_icon} {instrument}\n"
            f"   Zone: {structure.zone.center:.0f} (±{structure.zone.bandwidth:.0f})\n"
            f"   {structure.cycle_count}次试探 · 速度比 {structure.avg_speed_ratio:.2f}\n"
            f"   阶段: {structure.phase_tendency} · 通量 {structure.conservation_flux:+.2f}\n"
            f"   质量分: {structure.quality_score:.0%} · 方向: {structure.direction}"
        )

        self.output(signal_text)

        if self.params_map.enable_sound:
            self.play_sound()
        if self.params_map.enable_alert:
            self.show_alert(signal_text)
        if self.params_map.enable_trade:
            self._auto_trade(bar, structure)

        # ── 共振检测 ──
        self._check_and_emit_resonance(
            instrument=instrument,
            direction=structure.direction,
            signal_type="structure",
            quality_tier=structure.quality_tier,
            quality_score=structure.quality_score,
            zone_center=structure.zone.center,
        )

    def _emit_breakout_signal(self, instrument: str, bar: KLineData, signal: BreakoutReversalSignal):
        """输出假突破反转信号 + 共振检测"""
        if signal.signal_type == "bearish_reversal":
            icon = "🔻"
            label = "上破回落"
            direction_text = "看跌"
            direction = "bearish"
        else:
            icon = "🔺"
            label = "下破反弹"
            direction_text = "看涨"
            direction = "bullish"

        tier_icon = {"A": "🟢", "B": "🔵", "C": "🟡"}.get(signal.quality_tier, "⚪")

        signal_text = (
            f"{tier_icon} [{signal.quality_tier}层] {icon} {label} {instrument}\n"
            f"   Zone: {signal.zone.center:.0f} (±{signal.zone.bandwidth:.0f})\n"
            f"   突破极值: {signal.breakout_price:.0f} → 当前: {signal.reversal_price:.0f}\n"
            f"   突破深度: {signal.breakout_depth:.1f}bw · 反转速度: {signal.reversal_speed:.1f}x\n"
            f"   质量分: {signal.quality_score:.0%} · {direction_text}"
        )

        self.output(signal_text)

        if self.params_map.enable_sound:
            self.play_sound()
        if self.params_map.enable_alert:
            self.show_alert(signal_text)

        # 假突破自动下单逻辑
        if self.params_map.enable_trade:
            if signal.signal_type == "bearish_reversal":
                self.send_order(
                    exchange=bar.exchange,
                    instrument_id=bar.instrument_id,
                    volume=self.params_map.trade_volume,
                    price=bar.close - self.params_map.pay_up,
                    order_direction="sell",
                )
                self.output(f"   📉 卖出 {bar.instrument_id} @ {bar.close:.2f} (假突破反转)")
            else:
                self.send_order(
                    exchange=bar.exchange,
                    instrument_id=bar.instrument_id,
                    volume=self.params_map.trade_volume,
                    price=bar.close + self.params_map.pay_up,
                    order_direction="buy",
                )
                self.output(f"   📈 买入 {bar.instrument_id} @ {bar.close:.2f} (假突破反转)")

        # ── 共振检测 ──
        self._check_and_emit_resonance(
            instrument=instrument,
            direction=direction,
            signal_type="breakout_reversal",
            quality_tier=signal.quality_tier,
            quality_score=signal.quality_score,
            zone_center=signal.zone.center,
        )

    def _check_and_emit_resonance(
        self, instrument: str, direction: str,
        signal_type: str, quality_tier: str,
        quality_score: float, zone_center: float,
    ):
        """
        记录信号并检查共振

        如果检测到板块共振，输出共振提示。
        """
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

        # 检查共振
        resonance = self.resonance_tracker.check_resonance(record)
        if resonance:
            self.output("")
            self.output(resonance.format())
            self.output("")

            # 强共振额外提示
            if resonance.is_strong:
                self.output(f"🔥🔥🔥 强共振！{sector}板块 {resonance.resonance_level} 个品种同时触发！")
                if self.params_map.enable_sound:
                    # 强共振：连续提示音
                    self.play_sound()
                    _time.sleep(0.3)
                    self.play_sound()
        """输出到控制台"""
        print(f"[结构信号] {msg}")

    def play_sound(self):
        """播放提示音"""
        try:
            import winsound
            winsound.Beep(1000, 500)
        except Exception:
            pass

    def show_alert(self, msg: str):
        """弹窗提示"""
        try:
            # PythonGO 可能支持的弹窗方式
            self.output(f"🔔 提示: {msg}")
        except Exception:
            pass

    def get_position(self, instrument_id: str) -> dict:
        """获取持仓（简化版）"""
        try:
            # 调用 PythonGO 的持仓查询
            return {"long": 0, "short": 0, "net": 0}
        except Exception:
            return {"long": 0, "short": 0, "net": 0}

    @property
    def main_indicator_data(self) -> dict[str, float]:
        """主图指标（在 K 线图上显示）"""
        return {}
