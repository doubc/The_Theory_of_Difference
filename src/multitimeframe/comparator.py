"""
多时间维度对比器 — 5分钟 / 1小时 / 日线 结构交叉验证

核心思想：
同一品种在不同时间尺度上编译出的结构，如果一致 → 信号更可靠。
不一致 → 可能是噪声或尺度错配。

功能：
1. 同品种多尺度编译 + 结构对比
2. 5分钟结构 vs 日线结构的一致性评分
3. 1小时结构 vs 日线结构的一致性评分
4. 跨周期结构对齐 + 偏移检测
5. 多尺度一致性报告

用法：
    from src.multitimeframe import MultiTimeframeComparator

    comp = MultiTimeframeComparator(store)
    report = comp.compare("CU0", start="2026-01-01", end="2026-04-01")
    print(report.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from src.data.loader import Bar
from src.data.local_store import LocalStore
from src.compiler.pipeline import compile_full, CompilerConfig, CompileResult
from src.models import Structure, Zone, Cycle


# ─── 数据结构 ─────────────────────────────────────────────

@dataclass
class TimeframeResult:
    """单个时间维度的编译结果"""
    freq: str                   # "1d" / "1h" / "5m"
    bars_count: int
    compile_result: CompileResult | None
    structures: list[Structure]
    error: str = ""

    @property
    def has_structures(self) -> bool:
        return len(self.structures) > 0


@dataclass
class CrossTimeframeMatch:
    """跨时间维度的结构匹配"""
    structure_a: Structure       # 较大时间维度
    structure_b: Structure       # 较小时间维度
    freq_a: str
    freq_b: str
    zone_overlap: float          # Zone 重叠度 [0, 1]
    direction_match: bool        # 方向是否一致
    speed_ratio_diff: float      # 速度比差异
    consistency_score: float     # 综合一致性 [0, 1]

    @property
    def is_consistent(self) -> bool:
        return self.consistency_score > 0.6


@dataclass
class MultiTimeframeReport:
    """多时间维度对比报告"""
    symbol: str
    start: str
    end: str
    timeframe_results: dict[str, TimeframeResult]  # freq → result
    cross_matches: list[CrossTimeframeMatch]
    consistency_score: float     # 总体一致性 [0, 1]
    summary_text: str = ""

    def summary(self) -> str:
        parts = [f"=== {self.symbol} 多时间维度分析 ==="]
        parts.append(f"时间范围: {self.start} ~ {self.end}")
        parts.append(f"总体一致性: {self.consistency_score:.2f}")
        parts.append("")

        for freq, tr in self.timeframe_results.items():
            if tr.error:
                parts.append(f"  {freq}: ❌ {tr.error}")
            else:
                parts.append(f"  {freq}: {len(tr.structures)} 个结构")

        if self.cross_matches:
            parts.append(f"\n跨维度匹配 ({len(self.cross_matches)} 对):")
            for m in self.cross_matches:
                status = "✓" if m.is_consistent else "✗"
                parts.append(
                    f"  {status} {m.freq_a}↔{m.freq_b}: "
                    f"zone重叠={m.zone_overlap:.2f}, "
                    f"方向={'一致' if m.direction_match else '不一致'}, "
                    f"一致性={m.consistency_score:.2f}"
                )

        if self.summary_text:
            parts.append(f"\n{self.summary_text}")

        return "\n".join(parts)


# ─── 时间维度对齐 ─────────────────────────────────────────

def resample_bars(bars: list[Bar], target_freq: str) -> list[Bar]:
    """
    将高频数据重采样为低频数据

    Args:
        bars: 原始 Bar 列表
        target_freq: 目标频率 "1h" / "4h" / "1d"

    Returns:
        重采样后的 Bar 列表
    """
    if not bars:
        return []

    if target_freq == "1d":
        # 5分钟 → 日线
        return _resample_to_daily(bars)
    elif target_freq == "1h":
        # 5分钟 → 1小时
        return _resample_to_hourly(bars)
    else:
        return bars


def _resample_to_daily(bars: list[Bar]) -> list[Bar]:
    """5分钟线 → 日线"""
    if not bars:
        return []

    # 按日期分组
    by_date: dict[str, list[Bar]] = {}
    for b in bars:
        date_str = b.timestamp.strftime("%Y-%m-%d")
        if date_str not in by_date:
            by_date[date_str] = []
        by_date[date_str].append(b)

    result = []
    for date_str in sorted(by_date.keys()):
        day_bars = by_date[date_str]
        if not day_bars:
            continue

        result.append(Bar(
            symbol=day_bars[0].symbol,
            timestamp=day_bars[0].timestamp.replace(hour=0, minute=0, second=0),
            open=day_bars[0].open,
            high=max(b.high for b in day_bars),
            low=min(b.low for b in day_bars),
            close=day_bars[-1].close,
            volume=sum(b.volume for b in day_bars),
        ))

    return result


def _resample_to_hourly(bars: list[Bar]) -> list[Bar]:
    """5分钟线 → 1小时线"""
    if not bars:
        return []

    # 按小时分组
    by_hour: dict[str, list[Bar]] = {}
    for b in bars:
        hour_key = b.timestamp.strftime("%Y-%m-%d %H")
        if hour_key not in by_hour:
            by_hour[hour_key] = []
        by_hour[hour_key].append(b)

    result = []
    for hour_key in sorted(by_hour.keys()):
        hour_bars = by_hour[hour_key]
        if not hour_bars:
            continue

        result.append(Bar(
            symbol=hour_bars[0].symbol,
            timestamp=hour_bars[0].timestamp.replace(minute=0, second=0),
            open=hour_bars[0].open,
            high=max(b.high for b in hour_bars),
            low=min(b.low for b in hour_bars),
            close=hour_bars[-1].close,
            volume=sum(b.volume for b in hour_bars),
        ))

    return result


# ─── 结构一致性计算 ───────────────────────────────────────

def compute_zone_overlap(z1: Zone, z2: Zone) -> float:
    """两个 Zone 的重叠度 [0, 1]"""
    overlap_lo = max(z1.lower, z2.lower)
    overlap_hi = min(z1.upper, z2.upper)

    if overlap_lo >= overlap_hi:
        return 0.0

    overlap = overlap_hi - overlap_lo
    union = (z1.upper - z1.lower) + (z2.upper - z2.lower) - overlap

    return overlap / union if union > 0 else 0.0


def compute_direction_match(s1: Structure, s2: Structure) -> bool:
    """两个结构的方向是否一致"""
    if not s1.cycles or not s2.cycles:
        return False

    # 取主要方向（多数 cycle 的方向）
    def dominant_direction(s: Structure) -> int:
        dirs = [c.entry.direction.value for c in s.cycles]
        return 1 if sum(d for d in dirs) > 0 else -1

    return dominant_direction(s1) == dominant_direction(s2)


def compute_speed_ratio_diff(s1: Structure, s2: Structure) -> float:
    """速度比差异 [0, 1]，0=完全相同"""
    sr1 = s1.avg_speed_ratio
    sr2 = s2.avg_speed_ratio
    if sr1 == 0 and sr2 == 0:
        return 0.0
    max_sr = max(abs(sr1), abs(sr2), 1e-9)
    return abs(sr1 - sr2) / max_sr


def cross_timeframe_consistency(
    sa: Structure,
    sb: Structure,
    freq_a: str = "1d",
    freq_b: str = "5m",
) -> CrossTimeframeMatch:
    """
    计算两个跨时间维度结构的一致性

    Args:
        sa: 较大时间维度的结构
        sb: 较小时间维度的结构
        freq_a, freq_b: 时间维度标签

    Returns:
        CrossTimeframeMatch
    """
    zone_overlap = compute_zone_overlap(sa.zone, sb.zone)
    direction_match = compute_direction_match(sa, sb)
    speed_ratio_diff = compute_speed_ratio_diff(sa, sb)

    # 综合一致性评分
    score = 0.0
    score += 0.4 * zone_overlap           # Zone 重叠度权重最高
    score += 0.3 * (1.0 if direction_match else 0.0)  # 方向一致性
    score += 0.3 * (1.0 - speed_ratio_diff)  # 速度比相似度

    return CrossTimeframeMatch(
        structure_a=sa,
        structure_b=sb,
        freq_a=freq_a,
        freq_b=freq_b,
        zone_overlap=zone_overlap,
        direction_match=direction_match,
        speed_ratio_diff=speed_ratio_diff,
        consistency_score=score,
    )


# ─── 多时间维度编译器 ────────────────────────────────────

class MultiTimeframeCompiler:
    """
    多时间维度编译器

    对同一品种在多个时间维度上编译结构，然后交叉验证。
    """

    def __init__(
        self,
        store: LocalStore,
        config_1d: CompilerConfig | None = None,
        config_1h: CompilerConfig | None = None,
        config_5m: CompilerConfig | None = None,
    ):
        self.store = store
        self.config_1d = config_1d or CompilerConfig()
        self.config_1h = config_1h or CompilerConfig(
            min_amplitude=0.01,    # 1小时需要更小的阈值
            min_duration=2,
            zone_bandwidth=0.008,
        )
        self.config_5m = config_5m or CompilerConfig(
            min_amplitude=0.005,   # 5分钟需要更小的阈值
            min_duration=2,
            zone_bandwidth=0.005,
        )

    def compile_timeframe(
        self,
        bars: list[Bar],
        freq: str,
        config: CompilerConfig,
        symbol: str = "",
    ) -> TimeframeResult:
        """在单个时间维度上编译"""
        if not bars:
            return TimeframeResult(
                freq=freq, bars_count=0,
                compile_result=None, structures=[],
                error="无数据",
            )

        try:
            result = compile_full(bars, config, symbol=symbol)
            return TimeframeResult(
                freq=freq,
                bars_count=len(bars),
                compile_result=result,
                structures=result.structures,
            )
        except Exception as e:
            return TimeframeResult(
                freq=freq, bars_count=len(bars),
                compile_result=None, structures=[],
                error=str(e),
            )

    def compile_all_timeframes(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, TimeframeResult]:
        """
        在所有可用时间维度上编译

        自动检测本地有哪些频率的数据，从高频重采样到低频。
        """
        results = {}

        # 检查可用数据
        has_5m = len(self.store.list_symbols("5m")) > 0
        has_1d = len(self.store.list_symbols("1d")) > 0

        # 日线编译
        if has_1d:
            bars_1d = self.store.load_bars(symbol, freq="1d", start=start, end=end)
            results["1d"] = self.compile_timeframe(bars_1d, "1d", self.config_1d, symbol)

        # 5分钟线编译
        if has_5m:
            bars_5m = self.store.load_bars(symbol, freq="5m", start=start, end=end)
            results["5m"] = self.compile_timeframe(bars_5m, "5m", self.config_5m, symbol)

            # 从5分钟线重采样为1小时线
            if bars_5m:
                bars_1h = resample_bars(bars_5m, "1h")
                results["1h"] = self.compile_timeframe(bars_1h, "1h", self.config_1h, symbol)

        return results


# ─── 多时间维度对比器 ────────────────────────────────────

class MultiTimeframeComparator:
    """
    多时间维度对比器

    核心功能：
    1. 多尺度编译
    2. 跨维度结构匹配
    3. 一致性评分
    4. 报告生成
    """

    def __init__(self, store: LocalStore):
        self.compiler = MultiTimeframeCompiler(store)
        self.store = store

    def compare(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> MultiTimeframeReport:
        """
        多时间维度对比分析

        Args:
            symbol: 品种代码
            start, end: 时间范围

        Returns:
            MultiTimeframeReport
        """
        # 1. 多尺度编译
        tf_results = self.compiler.compile_all_timeframes(symbol, start, end)

        # 2. 跨维度匹配
        cross_matches = self._find_cross_matches(tf_results)

        # 3. 计算总体一致性
        if cross_matches:
            consistency = sum(m.consistency_score for m in cross_matches) / len(cross_matches)
        else:
            consistency = 0.0

        # 4. 生成摘要
        summary = self._generate_summary(symbol, tf_results, cross_matches, consistency)

        return MultiTimeframeReport(
            symbol=symbol,
            start=start or "",
            end=end or "",
            timeframe_results=tf_results,
            cross_matches=cross_matches,
            consistency_score=consistency,
            summary_text=summary,
        )

    def _find_cross_matches(
        self,
        tf_results: dict[str, TimeframeResult],
    ) -> list[CrossTimeframeMatch]:
        """在不同时间维度之间寻找匹配的结构"""
        matches = []

        freqs = sorted(tf_results.keys(), key=_freq_to_minutes)

        for i, freq_a in enumerate(freqs):
            for freq_b in freqs[i + 1:]:
                tr_a = tf_results[freq_a]
                tr_b = tf_results[freq_b]

                if not tr_a.has_structures or not tr_b.has_structures:
                    continue

                # 寻找最佳匹配对
                for sa in tr_a.structures:
                    best_match = None
                    best_score = -1

                    for sb in tr_b.structures:
                        match = cross_timeframe_consistency(sa, sb, freq_a, freq_b)
                        if match.consistency_score > best_score:
                            best_score = match.consistency_score
                            best_match = match

                    if best_match and best_match.consistency_score > 0.3:
                        matches.append(best_match)

        # 按一致性排序
        matches.sort(key=lambda m: m.consistency_score, reverse=True)
        return matches

    def _generate_summary(
        self,
        symbol: str,
        tf_results: dict[str, TimeframeResult],
        cross_matches: list[CrossTimeframeMatch],
        consistency: float,
    ) -> str:
        """生成自然语言摘要"""
        parts = []

        # 各维度概况
        for freq, tr in tf_results.items():
            if tr.error:
                parts.append(f"{freq}: 数据错误 - {tr.error}")
            elif tr.structures:
                top = tr.structures[0]
                parts.append(
                    f"{freq}: {len(tr.structures)}个结构, "
                    f"最强结构 Zone={top.zone.price_center:.0f}, "
                    f"{top.cycle_count}次试探"
                )
            else:
                parts.append(f"{freq}: 无结构")

        # 一致性判断
        if consistency > 0.7:
            parts.append(f"\n🟢 多尺度高度一致 ({consistency:.0%})，信号可靠性高")
        elif consistency > 0.4:
            parts.append(f"\n🟡 多尺度部分一致 ({consistency:.0%})，需关注尺度差异")
        else:
            parts.append(f"\n🔴 多尺度不一致 ({consistency:.0%})，可能存在噪声信号")

        # 关键匹配
        if cross_matches:
            best = cross_matches[0]
            parts.append(
                f"最佳跨尺度匹配: {best.freq_a}↔{best.freq_b}, "
                f"Zone重叠={best.zone_overlap:.0%}, "
                f"方向{'一致' if best.direction_match else '不一致'}"
            )

        return "\n".join(parts)


def _freq_to_minutes(freq: str) -> int:
    """频率转分钟数（用于排序）"""
    mapping = {"5m": 5, "1h": 60, "4h": 240, "1d": 1440}
    return mapping.get(freq, 9999)


# ─── 便捷函数 ─────────────────────────────────────────────

def compare_timeframes(
    symbol: str,
    store: LocalStore,
    start: str | None = None,
    end: str | None = None,
) -> MultiTimeframeReport:
    """
    一键多时间维度对比

    用法：
        from src.multitimeframe import compare_timeframes
        from src.data.local_store import open_store

        store = open_store()
        report = compare_timeframes("CU0", store, start="2026-01-01")
        print(report.summary())
    """
    comparator = MultiTimeframeComparator(store)
    return comparator.compare(symbol, start, end)
