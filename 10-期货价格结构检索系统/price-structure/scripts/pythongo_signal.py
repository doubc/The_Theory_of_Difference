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
# PythonGO 策略
# ═══════════════════════════════════════════════════════════

class Params(BaseParams):
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
        self.output(f"   自动下单: {'是' if self.params_map.enable_trade else '否'}")
        self.output("=" * 50)

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

        prices = self.price_cache[instrument]
        if len(prices) < 30:
            return

        # 运行结构分析
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

        if structure is None:
            return

        # 检查信号条件
        if not structure.is_actionable:
            return

        if structure.quality_score < self._min_tier_score:
            return

        # 冷却检查
        import time
        now = time.time()
        last = self._last_signal_ts.get(instrument, 0)
        if now - last < self.params_map.alert_cooldown:
            return

        # ── 触发信号 ──
        self._last_signal_ts[instrument] = now
        self.state_map.signal_count += 1

        # 信号文本
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

        # 声音提示
        if self.params_map.enable_sound:
            self.play_sound()

        # 弹窗提示
        if self.params_map.enable_alert:
            self.show_alert(signal_text)

        # 自动下单（可选）
        if self.params_map.enable_trade:
            self._auto_trade(bar, structure)

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

    def output(self, msg: str):
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
