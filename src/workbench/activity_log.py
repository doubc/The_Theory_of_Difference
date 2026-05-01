"""
统一活动日志 — 所有检索/扫描/对照/对比的结果自动沉淀

解决的问题：每次工作（扫描、检索、对照）的输出用完就丢，没有形成积累。

数据格式：JSONL，每行一条活动记录，存 data/activity/activity.jsonl

活动类型：
  - scan        全市场扫描（Top 10 结果）
  - retrieval   历史检索（相似结构 + 后验统计）
  - compare     跨品种对比
  - contract    合约检索（新浪拉取 + 编译）
  - insight     人工洞察（从复盘日志升级）

用法：
    from src.workbench.activity_log import ActivityLog
    log = ActivityLog()

    # 保存扫描结果
    log.save_scan(scan_results, sensitivity="标准")

    # 保存检索结果
    log.save_retrieval(symbol, query_zone, neighbors, posterior)

    # 搜索历史
    entries = log.search(symbol="CU0", type="retrieval", days=30)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# ─── 配置 ─────────────────────────────────────────────────

ACTIVITY_DIR = Path("data/activity")
ACTIVITY_FILE = ACTIVITY_DIR / "activity.jsonl"


# ─── 数据结构 ─────────────────────────────────────────────

@dataclass
class ActivityEntry:
    """一条活动记录"""
    timestamp: str                          # ISO 格式
    date: str                               # YYYY-MM-DD
    type: str                               # scan/retrieval/compare/contract/insight
    symbol: str = ""                        # 品种（scan 可能为空）
    summary: str = ""                       # 一句话摘要
    details: dict = field(default_factory=dict)  # 详细数据（按类型不同）
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ActivityEntry:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── 核心类 ───────────────────────────────────────────────

class ActivityLog:
    """统一活动日志"""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else ACTIVITY_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, entry: ActivityEntry):
        """追加一条记录"""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def _load_all(self) -> list[ActivityEntry]:
        """加载全部记录"""
        if not self.path.exists():
            return []
        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(ActivityEntry.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, TypeError):
                        continue
        return entries

    # ─── 保存各类结果 ─────────────────────────────────

    def save_scan(self, scan_results: list[dict], sensitivity: str = "标准",
                  extra_tags: list[str] | None = None):
        """
        保存全市场扫描结果

        Args:
            scan_results: _scan_all_symbols 的输出
            sensitivity: 灵敏度
            extra_tags: 额外标签
        """
        if not scan_results:
            return

        top10 = scan_results[:10]
        symbols = [r["symbol"] for r in top10]
        directions = {"up": 0, "down": 0, "unclear": 0}
        for r in top10:
            directions[r.get("direction", "unclear")] = directions.get(r.get("direction", "unclear"), 0) + 1

        summary_parts = [
            f"{len(scan_results)}个活跃结构",
            f"Top10: {', '.join(symbols[:5])}",
        ]
        if directions["up"] > 0:
            summary_parts.append(f"📈{directions['up']}")
        if directions["down"] > 0:
            summary_parts.append(f"📉{directions['down']}")

        # 存储完整结果（最多100条），包含各维度数据供回看对照
        full_results = []
        for r in scan_results[:100]:
            full_results.append({
                "symbol": r["symbol"],
                "symbol_name": r.get("symbol_name", ""),
                "zone_center": r["zone_center"],
                "zone_bw": r.get("zone_bw", 0),
                "cycles": r["cycles"],
                "motion": r["motion"],
                "movement_type": r.get("movement_type", ""),
                "flux": r["flux"],
                "score": r["score"],
                "direction": r["direction"],
                "tier": r.get("tier", "?"),
                "is_blind": r.get("is_blind", False),
                "contrast": r.get("contrast", ""),
                "last_price": r.get("last_price", 0),
                "days_since_end": r.get("days_since_end", 0),
                "recency": r.get("recency", 0),
                "signal": r.get("signal"),
                "narrative": r.get("narrative", ""),
                "suggestions": r.get("suggestions", []),
                "risk_level": r.get("risk_level", ""),
                "quality_flags": r.get("quality_flags", []),
                "judgment": r.get("judgment"),
                # 离稳态各维度数据
                "phase_transition": r.get("phase_transition", False),
                "flux_magnitude": r.get("flux_magnitude", 0),
                "departure_velocity": r.get("departure_velocity", 0),
                "stable_distance": r.get("stable_distance", 0),
                "signal_score": r.get("signal_score", 0),
            })

        entry = ActivityEntry(
            timestamp=datetime.now().isoformat(),
            date=datetime.now().strftime("%Y-%m-%d"),
            type="scan",
            summary=" · ".join(summary_parts),
            details={
                "sensitivity": sensitivity,
                "total_structures": len(scan_results),
                "top10": [{
                    "symbol": r["symbol"],
                    "zone_center": r["zone_center"],
                    "cycles": r["cycles"],
                    "motion": r["motion"],
                    "flux": r["flux"],
                    "score": r["score"],
                    "direction": r["direction"],
                    "tier": r.get("tier", "?"),
                } for r in top10],
                "full_results": full_results,
                "directions": directions,
            },
            tags=["scan", sensitivity] + (extra_tags or []),
        )
        self._append(entry)

    def save_retrieval(self, symbol: str, query_zone: float,
                       neighbors: list[dict], posterior: dict | None = None,
                       search_window: str = ""):
        """
        保存历史检索结果

        Args:
            symbol: 品种
            query_zone: 查询 Zone 中心
            neighbors: 邻居列表 [{symbol, period, similarity, direction, outcome}]
            posterior: 后验统计
            search_window: 检索窗口
        """
        n = len(neighbors)
        up_count = sum(1 for nb in neighbors if nb.get("direction") == "up")
        down_count = sum(1 for nb in neighbors if nb.get("direction") == "down")
        avg_sim = sum(nb.get("similarity", 0) for nb in neighbors) / n if n else 0

        summary_parts = [
            f"{symbol} Zone {query_zone:.0f}",
            f"{n}个相似案例",
            f"平均相似度 {avg_sim:.2f}",
        ]
        if up_count > down_count:
            summary_parts.append(f"历史偏多({up_count}/{n})")
        elif down_count > up_count:
            summary_parts.append(f"历史偏空({down_count}/{n})")

        entry = ActivityEntry(
            timestamp=datetime.now().isoformat(),
            date=datetime.now().strftime("%Y-%m-%d"),
            type="retrieval",
            symbol=symbol,
            summary=" · ".join(summary_parts),
            details={
                "query_zone": query_zone,
                "search_window": search_window,
                "neighbor_count": n,
                "avg_similarity": round(avg_sim, 4),
                "up_ratio": round(up_count / n, 2) if n else 0,
                "down_ratio": round(down_count / n, 2) if n else 0,
                "neighbors": neighbors[:10],  # 只存 top 10
                "posterior": posterior,
            },
            tags=["retrieval", symbol],
        )
        self._append(entry)

    def save_compare(self, symbols: list[str], compare_data: list[dict]):
        """
        保存跨品种对比结果

        Args:
            symbols: 对比品种列表
            compare_data: 对比数据
        """
        entry = ActivityEntry(
            timestamp=datetime.now().isoformat(),
            date=datetime.now().strftime("%Y-%m-%d"),
            type="compare",
            summary=f"对比 {', '.join(symbols)}: {len(compare_data)} 个结构",
            details={
                "symbols": symbols,
                "structures": compare_data[:20],
            },
            tags=["compare"] + symbols,
        )
        self._append(entry)

    def save_contract(self, symbol: str, bars_count: int, structures: list[dict]):
        """
        保存合约检索结果

        Args:
            symbol: 合约代码
            bars_count: K 线数量
            structures: 编译出的结构列表
        """
        entry = ActivityEntry(
            timestamp=datetime.now().isoformat(),
            date=datetime.now().strftime("%Y-%m-%d"),
            type="contract",
            symbol=symbol,
            summary=f"{symbol}: {bars_count}根K线, {len(structures)}个结构",
            details={
                "bars_count": bars_count,
                "structures": structures[:10],
            },
            tags=["contract", symbol],
        )
        self._append(entry)

    def save_insight(self, content: str, symbol: str = "",
                     linked_zone: float | None = None,
                     tags: list[str] | None = None):
        """
        保存人工洞察（从复盘日志或主动记录）

        Args:
            content: 洞察内容
            symbol: 关联品种
            linked_zone: 关联 Zone
            tags: 标签
        """
        entry = ActivityEntry(
            timestamp=datetime.now().isoformat(),
            date=datetime.now().strftime("%Y-%m-%d"),
            type="insight",
            symbol=symbol,
            summary=content[:100],
            details={
                "content": content,
                "linked_zone": linked_zone,
            },
            tags=tags or ["insight"],
        )
        self._append(entry)

    # ─── 查询 ─────────────────────────────────────────

    def search(self, symbol: str | None = None,
               type: str | None = None,
               days: int | None = None,
               tag: str | None = None,
               limit: int = 50) -> list[ActivityEntry]:
        """
        搜索历史活动

        Args:
            symbol: 按品种筛选
            type: 按类型筛选
            days: 最近 N 天
            tag: 按标签筛选
            limit: 最大返回数

        Returns:
            匹配的活动列表（最新在前）
        """
        entries = self._load_all()

        if symbol:
            entries = [e for e in entries if e.symbol == symbol or symbol in e.tags]
        if type:
            entries = [e for e in entries if e.type == type]
        if days:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            entries = [e for e in entries if e.date >= cutoff]
        if tag:
            entries = [e for e in entries if tag in e.tags]

        # 最新在前
        entries.reverse()
        return entries[:limit]

    def get_stats(self) -> dict:
        """获取活动统计"""
        entries = self._load_all()
        if not entries:
            return {"total": 0}

        type_counts = {}
        symbol_counts = {}
        date_counts = {}
        for e in entries:
            type_counts[e.type] = type_counts.get(e.type, 0) + 1
            if e.symbol:
                symbol_counts[e.symbol] = symbol_counts.get(e.symbol, 0) + 1
            date_counts[e.date] = date_counts.get(e.date, 0) + 1

        return {
            "total": len(entries),
            "by_type": type_counts,
            "by_symbol": dict(sorted(symbol_counts.items(), key=lambda x: -x[1])[:10]),
            "by_date": dict(sorted(date_counts.items(), reverse=True)[:14]),
            "first_entry": entries[0].date if entries else "",
            "last_entry": entries[-1].date if entries else "",
        }

    def get_timeline(self, symbol: str, days: int = 30) -> list[dict]:
        """
        获取某个品种的活动时间线

        Returns:
            [{date, type, summary, details}, ...]
        """
        entries = self.search(symbol=symbol, days=days, limit=200)
        timeline = []
        for e in entries:
            timeline.append({
                "date": e.date,
                "type": e.type,
                "summary": e.summary,
                "details": e.details,
            })
        return timeline

    def get_scan_by_date(self, date_str: str) -> list[dict] | None:
        """
        获取指定日期的完整扫描结果

        Args:
            date_str: "YYYY-MM-DD" 格式

        Returns:
            扫描结果列表（最多100条），无记录返回 None
        """
        entries = self.search(type="scan", days=365, limit=50)
        for e in entries:
            if e.date == date_str:
                return e.details.get("full_results", e.details.get("top10", []))
        return None

    def get_available_scan_dates(self, days: int = 90) -> list[str]:
        """
        获取有扫描记录的日期列表

        Returns:
            日期字符串列表，最新在前
        """
        entries = self.search(type="scan", days=days, limit=200)
        dates = sorted(set(e.date for e in entries), reverse=True)
        return dates
