"""
结构生命周期追踪 — P0-2

追踪结构从 formation → confirmation → breakout 的完整轨迹。
每日扫描结果 append 到本地 JSONL，构建结构的时间线。

核心思想：
- 结构不是静态快照，而是有生命的——它在不同日期之间的演化应该被追踪
- 质量分在生命周期中如何变化？A 层结构会降级吗？C 层能升级吗？
- 阶段转换的时间间隔有什么规律？

数据格式（JSONL 每行一条）：
{
    "date": "2026-04-24",
    "symbol": "CU0",
    "zone_center": 72500,
    "zone_bw": 800,
    "cycle_count": 4,
    "quality_tier": "A",
    "quality_score": 0.82,
    "phase_tendency": "→confirmation",
    "movement_type": "oscillation",
    "conservation_flux": -0.35,
    "speed_ratio": 1.2,
    "direction": "bullish",
    "is_blind": false,
    "stability": "unstable",
    "lifecycle_id": "CU0_72500_20260401",  # 品种_ZoneCenter_首次出现日期
}

用法：
    from src.lifecycle import LifecycleTracker

    tracker = LifecycleTracker()
    tracker.record("CU0", structures, system_states, date="2026-04-24")
    history = tracker.get_history("CU0", zone_center=72500)
    transitions = tracker.detect_transitions("CU0")
"""

from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, asdict

from src.models import Structure, SystemState
from src.quality import assess_quality


# ─── 配置 ─────────────────────────────────────────────────

LIFECYCLE_DIR = "data/lifecycle"
ZONE_MATCH_TOLERANCE = 0.02  # Zone 中心匹配容差（相对比例）


# ─── 数据结构 ─────────────────────────────────────────────

@dataclass
class LifecycleRecord:
    """单日结构快照"""
    date: str
    symbol: str
    zone_center: float
    zone_bw: float
    cycle_count: int
    quality_tier: str
    quality_score: float
    phase_tendency: str
    movement_type: str              # trend_up / trend_down / oscillation / reversal
    conservation_flux: float
    speed_ratio: float
    direction: str
    is_blind: bool
    stability: str
    lifecycle_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> LifecycleRecord:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class LifecycleTrack:
    """一个结构的完整生命周期"""
    lifecycle_id: str
    symbol: str
    zone_center: float
    records: list[LifecycleRecord]
    first_seen: str = ""
    last_seen: str = ""
    duration_days: int = 0

    @property
    def quality_trend(self) -> str:
        """质量趋势：上升/下降/稳定"""
        if len(self.records) < 2:
            return "insufficient"
        recent = [r.quality_score for r in self.records[-5:]]
        early = [r.quality_score for r in self.records[:5]]
        avg_recent = sum(recent) / len(recent)
        avg_early = sum(early) / len(early)
        diff = avg_recent - avg_early
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        return "stable"

    @property
    def phase_progression(self) -> list[str]:
        """阶段演进序列"""
        return [r.phase_tendency for r in self.records]

    @property
    def current_tier(self) -> str:
        return self.records[-1].quality_tier if self.records else "D"

    def summary(self) -> str:
        lines = [
            f"生命周期: {self.lifecycle_id}",
            f"品种: {self.symbol} · Zone {self.zone_center:.0f}",
            f"存续: {self.duration_days} 天 ({self.first_seen} → {self.last_seen})",
            f"记录数: {len(self.records)}",
            f"当前层级: {self.current_tier} · 趋势: {self.quality_trend}",
        ]
        return "\n".join(lines)


@dataclass
class Transition:
    """阶段转换事件"""
    date: str
    symbol: str
    lifecycle_id: str
    from_phase: str
    to_phase: str
    from_tier: str
    to_tier: str
    quality_at_transition: float


# ─── 生命周期追踪器 ──────────────────────────────────────

class LifecycleTracker:
    """
    结构生命周期追踪器

    核心功能：
    - record(): 每日扫描后记录结构快照
    - get_history(): 获取某个结构的完整历史
    - detect_transitions(): 检测阶段转换事件
    - get_active_lifecycles(): 获取当前活跃的生命周期
    """

    def __init__(self, data_dir: str = LIFECYCLE_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _lifecycle_file(self, symbol: str) -> Path:
        return self.data_dir / f"{symbol.upper()}.jsonl"

    def _generate_lifecycle_id(self, symbol: str, zone_center: float, date_str: str) -> str:
        """生成生命周期 ID：品种_ZoneCenter_日期"""
        zc = int(zone_center)
        return f"{symbol.upper()}_{zc}_{date_str.replace('-', '')}"

    def _match_existing_zone(self, symbol: str, zone_center: float, date_str: str) -> str:
        """检查是否有已存在的生命周期匹配此 Zone"""
        records = self._load_records(symbol)
        if not records:
            return self._generate_lifecycle_id(symbol, zone_center, date_str)

        # 查找最近 30 天内 Zone 中心接近的记录
        try:
            current_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            current_date = datetime.now()

        for rec in reversed(records):
            try:
                rec_date = datetime.strptime(rec.date, "%Y-%m-%d")
                days_diff = (current_date - rec_date).days
                if days_diff > 30:
                    break  # 太老了

                # Zone 匹配
                # 同一天同品种同 Zone → 去重，复用已有 lifecycle_id
                if rec.date == date_str and rec.zone_center > 0:
                    rel_diff = abs(zone_center - rec.zone_center) / rec.zone_center
                    if rel_diff < ZONE_MATCH_TOLERANCE:
                        return rec.lifecycle_id

                if rec.zone_center > 0:
                    rel_diff = abs(zone_center - rec.zone_center) / rec.zone_center
                    if rel_diff < ZONE_MATCH_TOLERANCE:
                        return rec.lifecycle_id
            except (ValueError, TypeError):
                continue

        return self._generate_lifecycle_id(symbol, zone_center, date_str)

    def record(
        self,
        symbol: str,
        structures: list[Structure],
        system_states: list[SystemState] | None = None,
        date_str: str | None = None,
    ) -> list[LifecycleRecord]:
        """
        记录某品种某日的结构快照

        Args:
            symbol: 品种代码
            structures: 当日编译出的结构列表
            system_states: 对应的系统态列表
            date_str: 日期字符串（默认今天）

        Returns:
            本次写入的记录列表
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # 加载已有记录，用于去重检查
        existing_records = self._load_records(symbol)
        existing_keys = {(r.lifecycle_id, r.date) for r in existing_records}

        records = []
        for i, s in enumerate(structures):
            ss = system_states[i] if system_states and i < len(system_states) else None
            qa = assess_quality(s, ss)

            # 只追踪 A/B/C 层（D 层太噪声）
            if qa.tier.value == "D":
                continue

            # 匹配或创建生命周期 ID
            lifecycle_id = self._match_existing_zone(symbol, s.zone.price_center, date_str)

            # 同一天同 lifecycle_id → 跳过，不重复写入
            if (lifecycle_id, date_str) in existing_keys:
                continue

            # 方向
            direction = "unknown"
            if s.cycles:
                ups = sum(1 for c in s.cycles if c.entry.direction.value > 0)
                downs = sum(1 for c in s.cycles if c.entry.direction.value < 0)
                if ups > downs:
                    direction = "bullish"
                elif downs > ups:
                    direction = "bearish"

            record = LifecycleRecord(
                date=date_str,
                symbol=symbol.upper(),
                zone_center=s.zone.price_center,
                zone_bw=s.zone.bandwidth,
                cycle_count=s.cycle_count,
                quality_tier=qa.tier.value,
                quality_score=qa.score,
                phase_tendency=s.motion.phase_tendency if s.motion else "",
                movement_type=s.motion.movement_type.value if s.motion and hasattr(s.motion, 'movement_type') else "",
                conservation_flux=s.motion.conservation_flux if s.motion else 0,
                speed_ratio=s.avg_speed_ratio,
                direction=direction,
                is_blind=s.projection.is_blind if s.projection else False,
                stability=ss.stability.surface if ss and ss.stability else "unstable",
                lifecycle_id=lifecycle_id,
            )
            records.append(record)
            existing_keys.add((lifecycle_id, date_str))

        # 追加写入
        if records:
            self._append_records(symbol, records)

        return records

    def get_history(
        self,
        symbol: str,
        lifecycle_id: str | None = None,
        zone_center: float | None = None,
        days: int | None = None,
    ) -> list[LifecycleRecord]:
        """
        获取某结构的完整历史

        Args:
            symbol: 品种代码
            lifecycle_id: 指定生命周期 ID
            zone_center: 指定 Zone 中心（自动匹配）
            days: 最近 N 天
        """
        records = self._load_records(symbol)

        if lifecycle_id:
            records = [r for r in records if r.lifecycle_id == lifecycle_id]
        elif zone_center:
            records = [r for r in records
                       if r.zone_center > 0
                       and abs(r.zone_center - zone_center) / r.zone_center < ZONE_MATCH_TOLERANCE]

        if days:
            cutoff = datetime.now().strftime("%Y-%m-%d")
            records = records[-days:]

        return records

    def get_active_lifecycles(self, symbol: str, max_age_days: int = 30) -> list[LifecycleTrack]:
        """
        获取当前活跃的生命周期

        活跃 = 最近 max_age_days 天内有记录
        """
        records = self._load_records(symbol)
        if not records:
            return []

        # 按 lifecycle_id 分组
        groups: dict[str, list[LifecycleRecord]] = {}
        for r in records:
            groups.setdefault(r.lifecycle_id, []).append(r)

        # 筛选活跃的
        try:
            cutoff = datetime.now().timestamp() - max_age_days * 86400
        except Exception:
            cutoff = 0

        active = []
        for lid, recs in groups.items():
            try:
                last_date = datetime.strptime(recs[-1].date, "%Y-%m-%d").timestamp()
                if last_date >= cutoff:
                    first = recs[0].date
                    last = recs[-1].date
                    try:
                        dur = (datetime.strptime(last, "%Y-%m-%d") - datetime.strptime(first, "%Y-%m-%d")).days
                    except ValueError:
                        dur = 0

                    active.append(LifecycleTrack(
                        lifecycle_id=lid,
                        symbol=symbol.upper(),
                        zone_center=recs[-1].zone_center,
                        records=recs,
                        first_seen=first,
                        last_seen=last,
                        duration_days=dur,
                    ))
            except (ValueError, TypeError):
                continue

        active.sort(key=lambda t: t.last_seen, reverse=True)
        return active

    def detect_transitions(self, symbol: str, days: int = 60) -> list[Transition]:
        """
        检测阶段转换事件

        遍历历史记录，找相邻记录之间 phase 或 tier 发生变化的时刻。
        """
        records = self._load_records(symbol)
        if len(records) < 2:
            return []

        # 按 lifecycle_id 分组
        groups: dict[str, list[LifecycleRecord]] = {}
        for r in records:
            groups.setdefault(r.lifecycle_id, []).append(r)

        transitions = []
        for lid, recs in groups.items():
            for i in range(1, len(recs)):
                prev, curr = recs[i - 1], recs[i]

                phase_changed = prev.phase_tendency != curr.phase_tendency
                tier_changed = prev.quality_tier != curr.quality_tier

                if phase_changed or tier_changed:
                    transitions.append(Transition(
                        date=curr.date,
                        symbol=symbol.upper(),
                        lifecycle_id=lid,
                        from_phase=prev.phase_tendency,
                        to_phase=curr.phase_tendency,
                        from_tier=prev.quality_tier,
                        to_tier=curr.quality_tier,
                        quality_at_transition=curr.quality_score,
                    ))

        return transitions

    # ── 内部 ──

    def _load_records(self, symbol: str) -> list[LifecycleRecord]:
        path = self._lifecycle_file(symbol)
        if not path.exists():
            return []
        records = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(LifecycleRecord.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, TypeError):
                        continue
        return records

    def _append_records(self, symbol: str, records: list[LifecycleRecord]):
        path = self._lifecycle_file(symbol)
        with open(path, "a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
