"""
5分钟结构日内节奏分析 — P0-3

分析 5 分钟结构在一天内的节奏规律：
- 开盘时段 vs 盘中 vs 收盘时段：速度比分布差异
- 日内 cycle 频率的时段偏好
- 不同时段的 Zone 形成模式
- 日内质量分层的时段分布

核心发现方向：
- 开盘 30 分钟是否倾向于快速破缺？
- 午盘是否倾向于形成新 Zone？
- 尾盘是否倾向于确认？

用法：
    from src.intraday_rhythm import IntradayRhythmAnalyzer

    analyzer = IntradayRhythmAnalyzer()
    report = analyzer.analyze(bars_5m, structures_5m, date_range=("2026-01-01", "2026-04-01"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from collections import defaultdict

from src.models import Structure, SystemState
from src.data.loader import Bar
from src.quality import assess_quality


# ─── 交易时段定义 ─────────────────────────────────────────

# 国内期货交易时段（夜盘+日盘）
TRADING_SESSIONS = {
    "night_1":   (time(21, 0), time(23, 0)),   # 夜盘前段
    "night_2":   (time(23, 0), time(2, 30)),    # 夜盘后段（跨日）
    "morning_1": (time(9, 0), time(10, 15)),    # 上午前段
    "morning_2": (time(10, 30), time(11, 30)),  # 上午后段
    "afternoon": (time(13, 30), time(15, 0)),   # 下午
}

SESSION_LABELS = {
    "night_1":   "🌙 夜盘前段 (21:00-23:00)",
    "night_2":   "🌙 夜盘后段 (23:00-02:30)",
    "morning_1": "🌅 上午前段 (9:00-10:15)",
    "morning_2": "☀️ 上午后段 (10:30-11:30)",
    "afternoon": "🌇 下午 (13:30-15:00)",
}


def get_session(t: datetime) -> str:
    """判断时间属于哪个交易时段"""
    tm = t.time()
    for session, (start, end) in TRADING_SESSIONS.items():
        if session == "night_2":
            # 跨日
            if tm >= start or tm <= end:
                return session
        else:
            if start <= tm <= end:
                return session
    return "off_hours"


# ─── 数据结构 ─────────────────────────────────────────────

@dataclass
class SessionStats:
    """单个时段的统计"""
    session: str
    label: str
    bar_count: int = 0
    structure_count: int = 0
    avg_speed_ratio: float = 0.0
    avg_cycle_count: float = 0.0
    quality_distribution: dict[str, int] = field(default_factory=dict)  # A/B/C/D
    avg_quality_score: float = 0.0
    dominant_direction: str = "mixed"
    phase_distribution: dict[str, int] = field(default_factory=dict)
    movement_type_distribution: dict[str, int] = field(default_factory=dict)  # trend_up/trend_down/oscillation/reversal
    avg_amplitude: float = 0.0  # 该时段的平均振幅


@dataclass
class RhythmReport:
    """日内节奏分析报告"""
    symbol: str
    date_range: tuple[str, str]
    session_stats: list[SessionStats]
    total_bars: int = 0
    total_structures: int = 0
    best_session: str = ""       # 结构最多的时段
    fastest_session: str = ""    # 速度比最高的时段
    highest_quality_session: str = ""  # 质量最高的时段

    def summary(self) -> str:
        lines = [
            f"=== {self.symbol} 日内节奏分析 ===",
            f"时间范围: {self.date_range[0]} ~ {self.date_range[1]}",
            f"总 bars: {self.total_bars} · 总结构: {self.total_structures}",
            "",
        ]

        for ss in self.session_stats:
            if ss.bar_count == 0:
                continue
            quality_str = " / ".join(f"{k}:{v}" for k, v in ss.quality_distribution.items() if v > 0)
            lines.append(f"{ss.label}")
            lines.append(f"  bars: {ss.bar_count} · 结构: {ss.structure_count}")
            lines.append(f"  速度比: {ss.avg_speed_ratio:.2f} · 周期数: {ss.avg_cycle_count:.1f}")
            lines.append(f"  质量: {quality_str} · 平均分: {ss.avg_quality_score:.2f}")
            lines.append(f"  方向: {ss.dominant_direction}")
            lines.append("")

        if self.best_session:
            lines.append(f"📊 结构最多: {SESSION_LABELS.get(self.best_session, self.best_session)}")
        if self.fastest_session:
            lines.append(f"⚡ 速度最快: {SESSION_LABELS.get(self.fastest_session, self.fastest_session)}")
        if self.highest_quality_session:
            lines.append(f"🏆 质量最高: {SESSION_LABELS.get(self.highest_quality_session, self.highest_quality_session)}")

        return "\n".join(lines)


# ─── 分析器 ──────────────────────────────────────────────

class IntradayRhythmAnalyzer:
    """
    日内节奏分析器

    分析 5 分钟结构在不同交易时段的分布和特征。
    """

    def analyze(
        self,
        bars_5m: list[Bar],
        structures: list[Structure],
        system_states: list[SystemState] | None = None,
        date_range: tuple[str, str] | None = None,
    ) -> RhythmReport:
        """
        分析日内节奏

        Args:
            bars_5m: 5 分钟 Bar 列表
            structures: 5 分钟编译出的结构列表
            system_states: 对应系统态列表
            date_range: (start, end) 日期范围

        Returns:
            RhythmReport
        """
        symbol = bars_5m[0].symbol if bars_5m else "UNKNOWN"

        # 1. 按时段分组 bars
        session_bars: dict[str, list[Bar]] = defaultdict(list)
        for b in bars_5m:
            if date_range:
                ds = b.timestamp.strftime("%Y-%m-%d")
                if ds < date_range[0] or ds > date_range[1]:
                    continue
            session = get_session(b.timestamp)
            session_bars[session].append(b)

        # 2. 按时段分组结构
        session_structures: dict[str, list[tuple[Structure, SystemState | None]]] = defaultdict(list)
        for i, s in enumerate(structures):
            if not s.cycles:
                continue
            # 用第一个 cycle 的 entry start 时间判断时段
            first_cycle_time = s.cycles[0].entry.start.t if s.cycles else None
            if not first_cycle_time:
                continue
            if date_range:
                ds = first_cycle_time.strftime("%Y-%m-%d")
                if ds < date_range[0] or ds > date_range[1]:
                    continue
            session = get_session(first_cycle_time)
            ss = system_states[i] if system_states and i < len(system_states) else None
            session_structures[session].append((s, ss))

        # 3. 计算各时段统计
        session_stats = []
        for session in ["night_1", "night_2", "morning_1", "morning_2", "afternoon"]:
            bars = session_bars.get(session, [])
            structs = session_structures.get(session, [])

            ss = self._compute_session_stats(session, bars, structs)
            session_stats.append(ss)

        # 4. 找最佳时段
        non_empty = [ss for ss in session_stats if ss.structure_count > 0]
        best = max(non_empty, key=lambda x: x.structure_count) if non_empty else None
        fastest = max(non_empty, key=lambda x: x.avg_speed_ratio) if non_empty else None
        highest_q = max(non_empty, key=lambda x: x.avg_quality_score) if non_empty else None

        return RhythmReport(
            symbol=symbol,
            date_range=date_range or ("all", "all"),
            session_stats=session_stats,
            total_bars=len(bars_5m),
            total_structures=len(structures),
            best_session=best.session if best else "",
            fastest_session=fastest.session if fastest else "",
            highest_quality_session=highest_q.session if highest_q else "",
        )

    def _compute_session_stats(
        self,
        session: str,
        bars: list[Bar],
        structures: list[tuple[Structure, SystemState | None]],
    ) -> SessionStats:
        """计算单个时段的统计"""
        ss = SessionStats(
            session=session,
            label=SESSION_LABELS.get(session, session),
            bar_count=len(bars),
            structure_count=len(structures),
        )

        if not structures:
            return ss

        # 速度比
        speed_ratios = [s.avg_speed_ratio for s, _ in structures if s.avg_speed_ratio > 0]
        ss.avg_speed_ratio = sum(speed_ratios) / len(speed_ratios) if speed_ratios else 0

        # 周期数
        cycle_counts = [s.cycle_count for s, _ in structures]
        ss.avg_cycle_count = sum(cycle_counts) / len(cycle_counts) if cycle_counts else 0

        # 质量分布
        quality_scores = []
        for s, sys_s in structures:
            qa = assess_quality(s, sys_s)
            ss.quality_distribution[qa.tier.value] = ss.quality_distribution.get(qa.tier.value, 0) + 1
            quality_scores.append(qa.score)
        ss.avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        # 方向
        directions = []
        for s, _ in structures:
            if s.cycles:
                ups = sum(1 for c in s.cycles if c.entry.direction.value > 0)
                downs = sum(1 for c in s.cycles if c.entry.direction.value < 0)
                directions.append("bullish" if ups > downs else "bearish")
        if directions:
            bullish = sum(1 for d in directions if d == "bullish")
            bearish = sum(1 for d in directions if d == "bearish")
            if bullish > bearish * 1.3:
                ss.dominant_direction = "bullish"
            elif bearish > bullish * 1.3:
                ss.dominant_direction = "bearish"
            else:
                ss.dominant_direction = "mixed"

        # 阶段分布 + 运动类型分布
        for s, _ in structures:
            if s.motion:
                phase = s.motion.phase_tendency or "unknown"
                ss.phase_distribution[phase] = ss.phase_distribution.get(phase, 0) + 1
                if hasattr(s.motion, 'movement_type') and s.motion.movement_type:
                    mt = s.motion.movement_type.value
                    ss.movement_type_distribution[mt] = ss.movement_type_distribution.get(mt, 0) + 1

        # 平均振幅
        if bars:
            amplitudes = [(b.high - b.low) / b.close * 100 for b in bars if b.close > 0]
            ss.avg_amplitude = sum(amplitudes) / len(amplitudes) if amplitudes else 0

        return ss

    def compare_sessions(
        self,
        bars_5m: list[Bar],
        structures: list[Structure],
        system_states: list[SystemState] | None = None,
    ) -> dict:
        """
        时段对比分析

        返回一个 dict，可直接用于 Streamlit 图表。
        """
        report = self.analyze(bars_5m, structures, system_states)

        sessions = []
        struct_counts = []
        speed_ratios = []
        quality_scores = []
        amplitudes = []

        for ss in report.session_stats:
            if ss.bar_count == 0:
                continue
            sessions.append(ss.label.split("(")[0].strip())
            struct_counts.append(ss.structure_count)
            speed_ratios.append(ss.avg_speed_ratio)
            quality_scores.append(ss.avg_quality_score)
            amplitudes.append(ss.avg_amplitude)

        return {
            "sessions": sessions,
            "structure_counts": struct_counts,
            "speed_ratios": speed_ratios,
            "quality_scores": quality_scores,
            "amplitudes": amplitudes,
            "report": report,
        }
