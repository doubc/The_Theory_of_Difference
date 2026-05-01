"""
统一数据流管理器 — 连接扫描→研究闭环→复盘的完整数据流

核心职责：
  1. 扫描结果自动沉淀为研究上下文
  2. 研究闭环的分析结果自动流入复盘
  3. 知识图谱数据增强各环节
  4. 信号生成结果自动跟踪
  5. 提供跨模块的数据查询接口
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

log = logging.getLogger(__name__)


# ─── 数据目录 ──────────────────────────────────────────────

DATA_DIR = Path("data")
FLOW_DIR = DATA_DIR / "flow"
FLOW_DIR.mkdir(parents=True, exist_ok=True)


# ─── 数据类 ─────────────────────────────────────────────────

@dataclass
class ScanResult:
    """扫描结果"""
    symbol: str
    symbol_name: str
    zone_center: float
    zone_bw: float
    cycles: int
    motion: str
    flux: float
    score: float
    tier: str
    direction: str
    volume: int
    last_price: float
    priority_score: float
    phase_code: str
    price_position: str
    departure_score: float
    signal_info: Optional[dict] = None
    knowledge_graph: Optional[dict] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ResearchContext:
    """研究上下文 — 从扫描结果自动构建"""
    symbol: str
    scan_result: Optional[ScanResult] = None
    knowledge_summary: str = ""
    cross_impacts: List[dict] = field(default_factory=list)
    chain_peers: List[str] = field(default_factory=list)
    key_relations: List[dict] = field(default_factory=list)
    polarity_reference: dict = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class SignalRecord:
    """信号记录"""
    symbol: str
    signal_type: str  # breakout_confirm, fake_breakout, pullback_confirm, etc.
    direction: str  # long, short, neutral
    confidence: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    rr_ratio: float
    zone_center: float
    zone_bw: float
    phase: str
    flux: float
    quality_tier: str
    knowledge_context: Optional[dict] = None
    status: str = "open"  # open, hit_target, hit_stop, expired, cancelled
    actual_exit_price: float = 0.0
    actual_pnl: float = 0.0
    actual_holding_days: int = 0
    notes: str = ""
    created_at: str = ""
    closed_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class JournalEntry:
    """复盘日志条目"""
    symbol: str
    entry_type: str  # 结构观察, 交易想法, 复盘总结, 信号跟踪
    sentiment: str
    content: str
    linked_zone: str = ""
    tags: List[str] = field(default_factory=list)
    structures_snapshot: List[dict] = field(default_factory=list)
    knowledge_context: Optional[dict] = None
    signal_record: Optional[SignalRecord] = None
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


# ─── 数据流管理器 ──────────────────────────────────────────

class DataFlowManager:
    """
    统一数据流管理器

    连接扫描→研究→复盘的完整数据流，提供跨模块数据查询。
    """

    def __init__(self):
        self.scan_file = FLOW_DIR / "scan_results.jsonl"
        self.context_file = FLOW_DIR / "research_contexts.jsonl"
        self.signal_file = FLOW_DIR / "signals.jsonl"
        self.journal_file = FLOW_DIR / "journal.jsonl"
        self.daily_summary_file = FLOW_DIR / "daily_summary.json"

    # ─── 扫描结果管理 ─────────────────────────────────────

    def save_scan_results(self, results: List[ScanResult]) -> int:
        """保存扫描结果"""
        count = 0
        with open(self.scan_file, "a", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
                count += 1
        return count

    def get_latest_scan(self, symbol: Optional[str] = None, limit: int = 50) -> List[ScanResult]:
        """获取最新扫描结果"""
        if not self.scan_file.exists():
            return []

        results = []
        with open(self.scan_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    r = ScanResult(**data)
                    if symbol and r.symbol != symbol:
                        continue
                    results.append(r)
                except Exception:
                    continue

        # 按时间倒序，去重（同一品种只保留最新）
        results.sort(key=lambda x: x.timestamp, reverse=True)
        if symbol:
            return results[:limit]

        # 去重：每个品种只保留最新
        seen = set()
        unique = []
        for r in results:
            if r.symbol not in seen:
                seen.add(r.symbol)
                unique.append(r)
        return unique[:limit]

    # ─── 研究上下文管理 ───────────────────────────────────

    def build_research_context(self, symbol: str) -> ResearchContext:
        """从扫描结果和知识图谱构建研究上下文"""
        ctx = ResearchContext(symbol=symbol)

        # 1. 获取最新扫描结果
        scan_results = self.get_latest_scan(symbol=symbol, limit=1)
        if scan_results:
            ctx.scan_result = scan_results[0]

        # 2. 获取知识图谱数据
        try:
            from src.workbench.kg_helper import (
                get_product_knowledge, get_cross_variety_impacts,
                get_chain_peers_from_kg, get_key_relations,
                get_polarity_reference, generate_knowledge_summary
            )

            knowledge = get_product_knowledge(symbol)
            if "error" not in knowledge:
                ctx.knowledge_summary = generate_knowledge_summary(symbol)
                ctx.cross_impacts = get_cross_variety_impacts(symbol)
                ctx.chain_peers = get_chain_peers_from_kg(symbol)
                ctx.key_relations = get_key_relations(symbol, limit=5)
                ctx.polarity_reference = get_polarity_reference(symbol)
        except Exception:
            log.debug("知识图谱数据加载失败: %s", symbol, exc_info=True)

        # 保存上下文
        self._save_context(ctx)
        return ctx

    def _save_context(self, ctx: ResearchContext):
        """保存研究上下文"""
        with open(self.context_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(ctx), ensure_ascii=False) + "\n")

    def get_latest_context(self, symbol: str) -> Optional[ResearchContext]:
        """获取最新研究上下文"""
        if not self.context_file.exists():
            return None

        with open(self.context_file, "r", encoding="utf-8") as f:
            for line in reversed(f.readlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("symbol") == symbol:
                        return ResearchContext(**data)
                except Exception:
                    continue
        return None

    # ─── 信号跟踪管理 ─────────────────────────────────────

    def save_signal(self, signal: SignalRecord) -> str:
        """保存信号记录"""
        with open(self.signal_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(signal), ensure_ascii=False) + "\n")
        return signal.created_at

    def get_open_signals(self, symbol: Optional[str] = None) -> List[SignalRecord]:
        """获取未平仓信号"""
        if not self.signal_file.exists():
            return []

        signals = []
        with open(self.signal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    sig = SignalRecord(**data)
                    if sig.status == "open":
                        if symbol and sig.symbol != symbol:
                            continue
                        signals.append(sig)
                except Exception:
                    continue
        return signals

    def close_signal(self, symbol: str, created_at: str, exit_price: float,
                     status: str = "manual", notes: str = "") -> bool:
        """平仓信号"""
        if not self.signal_file.exists():
            return False

        lines = self.signal_file.read_text(encoding="utf-8").strip().split("\n")
        updated = False

        with open(self.signal_file, "w", encoding="utf-8") as f:
            for line in lines:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("symbol") == symbol and data.get("created_at") == created_at:
                        data["status"] = status
                        data["actual_exit_price"] = exit_price
                        data["actual_pnl"] = exit_price - data.get("entry_price", 0)
                        data["actual_holding_days"] = (
                            datetime.now() - datetime.fromisoformat(created_at)
                        ).days
                        data["closed_at"] = datetime.now().isoformat()
                        data["notes"] = notes
                        updated = True
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
                except Exception:
                    f.write(line + "\n")

        return updated

    def get_signal_stats(self) -> dict:
        """获取信号统计"""
        if not self.signal_file.exists():
            return {"total": 0, "open": 0, "closed": 0, "hit_rate": 0}

        total = 0
        open_count = 0
        closed_count = 0
        hit_target = 0
        hit_stop = 0
        total_pnl = 0.0

        with open(self.signal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    total += 1
                    if data.get("status") == "open":
                        open_count += 1
                    else:
                        closed_count += 1
                        if data.get("status") == "hit_target":
                            hit_target += 1
                        elif data.get("status") == "hit_stop":
                            hit_stop += 1
                        total_pnl += data.get("actual_pnl", 0)
                except Exception:
                    continue

        hit_rate = hit_target / max(closed_count, 1)
        return {
            "total": total,
            "open": open_count,
            "closed": closed_count,
            "hit_target": hit_target,
            "hit_stop": hit_stop,
            "hit_rate": hit_rate,
            "total_pnl": total_pnl,
        }

    # ─── 日报生成 ─────────────────────────────────────────

    def generate_daily_summary(self) -> dict:
        """生成每日摘要"""
        today = datetime.now().strftime("%Y-%m-%d")

        # 扫描结果
        scan_results = self.get_latest_scan(limit=100)

        # 信号统计
        signal_stats = self.get_signal_stats()

        # 开仓信号
        open_signals = self.get_open_signals()

        # 板块分布
        sector_dist = {}
        for r in scan_results:
            try:
                from src.workbench.kg_helper import get_sector_from_kg
                sector_info = get_sector_from_kg(r.symbol)
                sector = sector_info.get("sector", "未知")
            except Exception:
                sector = "未知"
            sector_dist.setdefault(sector, []).append(r.symbol)

        # 方向分布
        up_count = sum(1 for r in scan_results if r.direction == "up")
        down_count = sum(1 for r in scan_results if r.direction == "down")

        summary = {
            "date": today,
            "scan_count": len(scan_results),
            "up_count": up_count,
            "down_count": down_count,
            "sector_distribution": {k: len(v) for k, v in sector_dist.items()},
            "signal_stats": signal_stats,
            "open_signals": len(open_signals),
            "top_opportunities": [
                {
                    "symbol": r.symbol,
                    "symbol_name": r.symbol_name,
                    "direction": r.direction,
                    "motion": r.motion,
                    "priority_score": r.priority_score,
                }
                for r in sorted(scan_results, key=lambda x: x.priority_score, reverse=True)[:5]
            ],
        }

        # 保存
        daily_file = FLOW_DIR / f"summary_{today}.json"
        daily_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        return summary

    # ─── 自动复盘条目 ─────────────────────────────────────

    def auto_create_journal_entry(self, symbol: str, entry_type: str = "结构观察",
                                  content: str = "", sentiment: str = "中性 ➡️") -> JournalEntry:
        """自动创建复盘条目"""
        # 获取研究上下文
        ctx = self.build_research_context(symbol)

        # 构建内容
        if not content and ctx.scan_result:
            r = ctx.scan_result
            content = f"[自动记录] {symbol} {r.motion} · Zone {r.zone_center:.0f}±{r.zone_bw:.0f}"
            content += f" · 通量{r.flux:+.3f} · {r.tier}层({r.score:.0f}分)"
            if r.signal_info:
                content += f" · 信号: {r.signal_info.get('kind', '')}"

        entry = JournalEntry(
            symbol=symbol,
            entry_type=entry_type,
            sentiment=sentiment,
            content=content,
            structures_snapshot=[{
                "zone": ctx.scan_result.zone_center if ctx.scan_result else 0,
                "cycles": ctx.scan_result.cycles if ctx.scan_result else 0,
                "motion": ctx.scan_result.motion if ctx.scan_result else "",
                "flux": ctx.scan_result.flux if ctx.scan_result else 0,
            }] if ctx.scan_result else [],
            knowledge_context={
                "key_relations": [r.get("from", "") + "→" + r.get("to", "") for r in ctx.key_relations[:3]],
                "chain_peers": ctx.chain_peers[:5],
                "cross_impacts_count": len(ctx.cross_impacts),
            } if ctx.key_relations else None,
        )

        # 保存
        with open(self.journal_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

        return entry

    def get_journal_entries(self, symbol: Optional[str] = None,
                           entry_type: Optional[str] = None,
                           limit: int = 50) -> List[JournalEntry]:
        """获取复盘条目"""
        if not self.journal_file.exists():
            return []

        entries = []
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if symbol and data.get("symbol") != symbol:
                        continue
                    if entry_type and data.get("entry_type") != entry_type:
                        continue
                    entries.append(JournalEntry(**data))
                except Exception:
                    continue

        entries.sort(key=lambda x: x.created_at, reverse=True)
        return entries[:limit]


# ─── 全局实例 ──────────────────────────────────────────────

_flow_manager: Optional[DataFlowManager] = None


def get_flow_manager() -> DataFlowManager:
    """获取全局数据流管理器实例"""
    global _flow_manager
    if _flow_manager is None:
        _flow_manager = DataFlowManager()
    return _flow_manager
