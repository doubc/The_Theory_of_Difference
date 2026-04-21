"""
主动匹配引擎 —— 用户带着观点来查，系统找历史相似并给出对比指引。

与 daily_scan（系统推）的区别：
- daily_scan: 全市场扫描 → 按关注度排序的机会清单
- active_match: 用户指定品种+时间窗+上下文 → 历史相似段对比指引
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Sequence

from src.models import Structure
from src.data.loader import Bar, MySQLLoader
from src.data.symbol_meta import symbol_name
from src.compiler.pipeline import compile_full, CompilerConfig
from src.retrieval.similarity import similarity, INVARIANT_KEYS, INVARIANT_SCALES


# ─── 数据结构 ──────────────────────────────────────────────

@dataclass
class ActiveMatchQuery:
    """用户查询"""
    symbols: list[str]
    search_start: str               # 检索窗口起始 "2023-01-01"
    search_end: str                 # 检索窗口结束 "2026-04-21"
    context_note: str = ""          # 用户观点描述
    profit_per_unit: float | None = None
    avg_cost: float | None = None
    price_context: str | None = None
    min_cycles: int = 2
    top_k: int = 10
    compiler_config: CompilerConfig | None = None

    def __post_init__(self):
        if self.compiler_config is None:
            self.compiler_config = CompilerConfig(
                min_amplitude=0.02,
                min_duration=3,
                zone_bandwidth=0.01,
            )


@dataclass
class HistoricalCase:
    """一段历史相似案例"""
    symbol: str
    symbol_name: str
    period_start: str               # "2019-03-01"
    period_end: str                 # "2019-06-15"
    similarity: float
    sim_geometry: float
    sim_relation: float
    sim_family: float
    diff_detail: dict[str, float]
    direction: str                  # 后续方向 up/down/unclear
    outcome_move: float             # 后续幅度（百分比）
    outcome_days: int               # 兑现天数
    cycle_count: int
    avg_speed_ratio: float
    avg_time_ratio: float
    zone_center: float
    zone_bandwidth: float
    description: str                # 一句话描述

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchedStructure:
    """用户窗口内编译出的一段结构 + 历史相似"""
    structure: Structure
    invariants: dict
    symbol: str
    symbol_name: str
    period_start: str
    period_end: str
    historical_cases: list[HistoricalCase]
    comparison_guide: list[str]     # 对比指引

    def to_dict(self) -> dict:
        d = {
            "symbol": self.symbol,
            "symbol_name": self.symbol_name,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "invariants": self.invariants,
            "cycle_count": self.structure.cycle_count,
            "historical_cases": [c.to_dict() for c in self.historical_cases],
            "comparison_guide": self.comparison_guide,
        }
        return d


@dataclass
class ActiveMatchResult:
    """主动匹配结果"""
    query: ActiveMatchQuery
    matched_structures: list[MatchedStructure]
    scan_meta: dict

    def to_dict(self) -> dict:
        return {
            "query": {
                "symbols": self.query.symbols,
                "search_start": self.query.search_start,
                "search_end": self.query.search_end,
                "context_note": self.query.context_note,
                "profit_per_unit": self.query.profit_per_unit,
                "avg_cost": self.query.avg_cost,
                "price_context": self.query.price_context,
            },
            "matched_structures": [m.to_dict() for m in self.matched_structures],
            "scan_meta": self.scan_meta,
        }


# ─── 核心逻辑 ──────────────────────────────────────────────

def _compute_outcome(bars: list[Bar], end_date: datetime, window_days: int = 30) -> dict:
    """计算结构结束后的前向表现"""
    outcome_start = end_date + timedelta(days=3)
    outcome_end = outcome_start + timedelta(days=window_days)

    future = [b for b in bars if outcome_start <= b.timestamp <= outcome_end]
    if not future:
        return {"direction": "unclear", "move": 0.0, "days": 0}

    start_price = future[0].open
    if start_price <= 0:
        return {"direction": "unclear", "move": 0.0, "days": 0}

    peak_price, peak_idx = start_price, 0
    trough_price, trough_idx = start_price, 0
    for i, b in enumerate(future):
        if b.high > peak_price:
            peak_price, peak_idx = b.high, i
        if b.low < trough_price:
            trough_price, trough_idx = b.low, i

    up = (peak_price - start_price) / start_price
    down = (start_price - trough_price) / start_price

    if up >= down:
        return {"direction": "up", "move": round(up, 4), "days": peak_idx}
    else:
        return {"direction": "down", "move": round(down, 4), "days": trough_idx}


def _diff_detail(inv1: dict, inv2: dict) -> dict[str, float]:
    """分项差异（归一化尺度下）"""
    diff = {}
    for k in INVARIANT_KEYS:
        scale = INVARIANT_SCALES.get(k, 1.0)
        v1 = (inv1.get(k) or 0) / scale if scale > 0 else 0
        v2 = (inv2.get(k) or 0) / scale if scale > 0 else 0
        diff[k] = round(abs(v1 - v2), 4)
    return diff


def _case_description(case: HistoricalCase) -> str:
    """自动生成一句话描述"""
    d = case.direction
    mv = case.outcome_move
    dy = case.outcome_days
    if d == "up":
        return f"{case.symbol_name} {case.period_start[:7]}~{case.period_end[:7]}: " \
               f"后续 {dy} 天内上涨 {mv:.1%}，速度比 {case.avg_speed_ratio:.2f}"
    elif d == "down":
        return f"{case.symbol_name} {case.period_start[:7]}~{case.period_end[:7]}: " \
               f"后续 {dy} 天内下跌 {mv:.1%}，速度比 {case.avg_speed_ratio:.2f}"
    else:
        return f"{case.symbol_name} {case.period_start[:7]}~{case.period_end[:7]}: " \
               f"后续方向不明，cycle={case.cycle_count}"


def _generate_comparison_guide(
    matched: Structure,
    cases: list[HistoricalCase],
    query: ActiveMatchQuery,
) -> list[str]:
    """生成对比指引（文字）"""
    guides = []

    if not cases:
        guides.append("未找到足够相似的历史案例，建议扩大检索窗口或降低 min_cycles")
        return guides

    # 方向统计
    up_cases = [c for c in cases if c.direction == "up"]
    down_cases = [c for c in cases if c.direction == "down"]
    n = len(cases)
    up_pct = len(up_cases) / n * 100 if n else 0
    down_pct = len(down_cases) / n * 100 if n else 0

    if up_pct > 60:
        guides.append(f"历史 {n} 段中 {len(up_cases)} 段({up_pct:.0f}%)后续上涨，"
                      f"平均涨幅 {sum(c.outcome_move for c in up_cases)/len(up_cases):.1%}，"
                      f"平均兑现 {sum(c.outcome_days for c in up_cases)//len(up_cases)} 天")
    elif down_pct > 60:
        guides.append(f"历史 {n} 段中 {len(down_cases)} 段({down_pct:.0f}%)后续下跌，"
                      f"平均跌幅 {sum(c.outcome_move for c in down_cases)/len(down_cases):.1%}，"
                      f"平均兑现 {sum(c.outcome_days for c in down_cases)//len(down_cases)} 天")
    else:
        guides.append(f"历史方向分歧：上涨 {len(up_cases)} 段 / 下跌 {len(down_cases)} 段 / "
                      f"不明 {n - len(up_cases) - len(down_cases)} 段")

    # 具体对照建议
    if up_cases:
        best_up = max(up_cases, key=lambda c: c.similarity)
        guides.append(f"最像的上涨案例：{best_up.description}，建议重点对照此段结构细节")
    if down_cases:
        best_down = max(down_cases, key=lambda c: c.similarity)
        guides.append(f"最像的下跌案例：{best_down.description}，注意对比其顶部结构形态")

    # 用户上下文关联
    if query.profit_per_unit and query.avg_cost:
        margin_pct = query.profit_per_unit / query.avg_cost * 100
        if margin_pct > 50:
            guides.append(f"当前利润/成本比 {margin_pct:.0f}% 处于极端水平，"
                          f"历史上类似极值对应的结构通常出现在周期顶部附近")
        elif margin_pct > 30:
            guides.append(f"当前利润/成本比 {margin_pct:.0f}% 偏高，"
                          f"关注结构是否出现衰竭信号（速度比下降、Cycle 缩短）")

    # 建议下一步
    guides.append(f"建议：调出最相似的 2~3 段历史 K 线图，逐根对比 "
                  f"Zone 周围的 Cycle 节奏变化，特别关注 speed_ratio 的转折点")

    return guides


def _load_all_bars_mysql(symbol: str) -> list[Bar]:
    """从 MySQL 加载全部历史数据"""
    try:
        loader = MySQLLoader(host="localhost", user="root", password="root", db="sina")
        return loader.get(symbol=symbol, freq="1d")
    except Exception:
        return []


def _load_all_bars_csv(symbol: str, data_dir: str = "data") -> list[Bar]:
    """从 CSV 降级加载（cu0.csv 硬编码，后续可扩展）"""
    from pathlib import Path
    from src.data.loader import CSVLoader
    # 品种代码到 CSV 文件的映射
    csv_map = {
        "CU0": "cu0.csv", "CU000": "cu0.csv",
        "AL0": "cu0.csv",  # 铝暂无独立 CSV，用铜数据演示
    }
    fname = csv_map.get(symbol.upper(), f"{symbol.lower()}.csv")
    path = Path(data_dir) / fname
    if not path.exists():
        return []
    loader = CSVLoader(str(path), symbol=symbol)
    return loader.bars


def _load_all_bars(symbol: str, data_dir: str = "data") -> list[Bar]:
    """加载全量数据：先尝试 MySQL，失败则降级 CSV"""
    bars = _load_all_bars_mysql(symbol)
    if bars:
        return bars
    return _load_all_bars_csv(symbol, data_dir)


def _compile_structures(
    bars: list[Bar],
    config: CompilerConfig,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
) -> list[Structure]:
    """编译指定时间窗口内的结构"""
    if start or end:
        from src.data.loader import _to_dt
        filtered = bars
        if start:
            s = _to_dt(start)
            filtered = [b for b in filtered if b.timestamp >= s]
        if end:
            e = _to_dt(end)
            filtered = [b for b in filtered if b.timestamp <= e]
        bars = filtered

    if len(bars) < 30:
        return []

    result = compile_full(bars, config, symbol=symbol)
    return result.structures


def active_match(query: ActiveMatchQuery, data_dir: str = "data") -> ActiveMatchResult:
    """
    核心匹配函数。

    对每个指定品种：
    1. 加载全量历史数据（MySQL 优先，CSV 降级）
    2. 在用户指定窗口内编译结构
    3. 对每个编译出的结构，在全量历史中找最相似的段
    4. 生成对比指引
    """
    config = query.compiler_config

    matched_structures: list[MatchedStructure] = []
    total_structures = 0
    total_cases = 0

    for sym in query.symbols:
        # 加载全量数据
        all_bars = _load_all_bars(sym, data_dir=data_dir)
        if len(all_bars) < 100:
            continue

        sname = symbol_name(sym)

        # 编译全量历史结构（作为检索库）
        all_structures = _compile_structures(all_bars, config, sym)

        # 编译用户窗口内的结构
        window_structures = _compile_structures(
            all_bars, config, sym,
            start=query.search_start,
            end=query.search_end,
        )
        total_structures += len(window_structures)

        # 对窗口内的每个结构，找全量历史中的相似段
        for ws in window_structures:
            ws_inv = ws.invariants or {}
            ws_start = ws.t_start.strftime("%Y-%m-%d") if ws.t_start else ""
            ws_end = ws.t_end.strftime("%Y-%m-%d") if ws.t_end else ""

            # 排除自身（时间重叠的算自身）
            candidates = []
            for hs in all_structures:
                if hs is ws:
                    continue
                # 跳过时间窗口内的（已经在窗口中了，找的是历史）
                if hs.t_end and ws.t_start and hs.t_end >= ws.t_start:
                    continue

                sc = similarity(ws, hs)
                hs_inv = hs.invariants or {}

                # 计算后续表现
                outcome = _compute_outcome(all_bars, hs.t_end) if hs.t_end else {
                    "direction": "unclear", "move": 0.0, "days": 0
                }

                case = HistoricalCase(
                    symbol=sym,
                    symbol_name=sname,
                    period_start=hs.t_start.strftime("%Y-%m-%d") if hs.t_start else "",
                    period_end=hs.t_end.strftime("%Y-%m-%d") if hs.t_end else "",
                    similarity=round(sc.total, 4),
                    sim_geometry=round(sc.geometric, 4),
                    sim_relation=round(sc.relational, 4),
                    sim_family=round(sc.family, 4),
                    diff_detail=_diff_detail(ws_inv, hs_inv),
                    direction=outcome["direction"],
                    outcome_move=outcome["move"],
                    outcome_days=outcome["days"],
                    cycle_count=hs.cycle_count,
                    avg_speed_ratio=round(hs.avg_speed_ratio, 4),
                    avg_time_ratio=round(hs.avg_time_ratio, 4),
                    zone_center=round(hs.zone.price_center, 2),
                    zone_bandwidth=round(hs.zone.bandwidth, 2),
                    description="",
                )
                case.description = _case_description(case)
                candidates.append(case)

            # 按相似度排序取 top_k
            candidates.sort(key=lambda c: c.similarity, reverse=True)
            top = candidates[:query.top_k]
            total_cases += len(top)

            # 生成对比指引
            guide = _generate_comparison_guide(ws, top, query)

            matched_structures.append(MatchedStructure(
                structure=ws,
                invariants=ws_inv,
                symbol=sym,
                symbol_name=sname,
                period_start=ws_start,
                period_end=ws_end,
                historical_cases=top,
                comparison_guide=guide,
            ))

    # 按结构的 cycle_count 降序排列（更丰富的结构优先）
    matched_structures.sort(
        key=lambda m: (m.structure.cycle_count, len(m.historical_cases)),
        reverse=True,
    )

    scan_meta = {
        "symbols_scanned": len(query.symbols),
        "structures_in_window": total_structures,
        "total_historical_cases": total_cases,
        "search_window": f"{query.search_start} ~ {query.search_end}",
        "config_hash": str(hash(str(config.__dict__)))[:8],
    }

    return ActiveMatchResult(
        query=query,
        matched_structures=matched_structures,
        scan_meta=scan_meta,
    )
