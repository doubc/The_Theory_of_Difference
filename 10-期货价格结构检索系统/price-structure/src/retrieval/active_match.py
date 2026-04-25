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
    max_lookback_days: int = 60     # 顺时序：历史对比最大回溯天数（默认 2 个月）
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
    """计算结构结束后的前向表现（v3.1: 用二分查找加速）"""
    outcome_start = end_date + timedelta(days=3)
    outcome_end = outcome_start + timedelta(days=window_days)

    # 二分查找过滤
    try:
        import numpy as np
        from src.fast import binary_filter_bars
        ts = np.array([int(b.timestamp.timestamp()) for b in bars], dtype=np.int64)
        s, e = binary_filter_bars(ts, int(outcome_start.timestamp()), int(outcome_end.timestamp()))
        future = bars[s:e]
    except (ImportError, Exception):
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

    # ── V1.6 P0: 最近稳态分析 ──
    # 从当前结构的 cycles 中提取最近稳态信息
    stable_cycles = [c for c in matched.cycles if c.has_stable_state]
    if stable_cycles:
        # 统计最近稳态的价位分布
        stable_zones = {}
        for c in stable_cycles:
            z = c.next_stable.zone
            key = f"{z.price_center:.0f}"
            stable_zones[key] = stable_zones.get(key, 0) + 1
        
        avg_resistance = sum(c.next_stable.resistance_level for c in stable_cycles) / len(stable_cycles)
        most_common_zone = max(stable_zones, key=stable_zones.get)
        
        guides.append(
            f"【最近稳态分析】{len(stable_cycles)}/{len(matched.cycles)} 个 Cycle 已识别最近稳态，"
            f"最常停驻价位 {most_common_zone}，"
            f"平均阻力 {avg_resistance:.2f}"
            f"{'（低阻力=容易到达=可能是假稳态）' if avg_resistance < 0.25 else ''}"
        )
        
        # 如果当前结构在 breakdown 阶段，强调稳态分析
        phases = [p.value for p in matched.phases]
        if "breakout" in phases:
            guides.append(
                f"⚠️ 结构处于突破阶段——"
                f"历史上类似结构崩塌后，最先停驻的价位通常是最近稳态，"
                f"而非最低点或最优反弹位"
            )

    # ── V1.6 P0: 运动态分析 ──
    if matched.motion:
        m = matched.motion
        mt = m.movement_type.value if hasattr(m, 'movement_type') else ""
        mt_cn = {"trend_up": "上涨趋势", "trend_down": "下跌趋势",
                 "oscillation": "震荡", "reversal": "反转"}.get(mt, "")
        if mt_cn:
            guides.append(
                f"【运动类型】{mt_cn}"
                f"（守恒通量 {m.conservation_flux:+.2f}，"
                f"距最近稳态 {m.stable_distance:.2f}）"
            )
        if m.phase_tendency == "→breakout":
            guides.append(
                f"【运动态】阶段趋势 →突破（置信度 {m.phase_confidence:.0%}），"
                f"守恒通量 {m.conservation_flux:+.2f}（{'差异在释放' if m.conservation_flux > 0 else '差异在压缩'}），"
                f"距最近稳态 {m.stable_distance:.2f}"
            )
        elif m.phase_tendency == "→confirmation":
            guides.append(
                f"【运动态】阶段趋势 →confirmation（置信度 {m.phase_confidence:.0%}），"
                f"结构正在自我确认中"
            )

    # ── V1.6 P0: 投影觉知 ──
    if matched.projection and matched.projection.is_blind:
        guides.append(
            f"⚠️ 【投影觉知】当前结构压缩度 {matched.projection.compression_level:.0%}，"
            f"价格可能不是差异的真实反映——差异可能藏在: "
            f"{', '.join(matched.projection.blind_channels)}"
        )

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

    # ── V1.6: 最近稳态在历史案例中的验证 ──
    if stable_cycles and (down_cases or up_cases):
        guides.append(
            f"【稳态验证】建议对照历史案例中类似结构崩塌/突破后的实际停驻价位，"
            f"与当前最近稳态预测做比较——如果历史实际停驻位与预测一致，"
            f"说明当前结构的稳态识别可靠"
        )

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
        import os
        password = os.getenv('MYSQL_PASSWORD', '')
        if not password:
            return []
        loader = MySQLLoader(password=password, db="sina")
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
    """编译指定时间窗口内的结构（v3.1: 用二分查找过滤时间窗口）"""
    if start or end:
        from src.data.loader import _to_dt
        try:
            import numpy as np
            from src.fast import binary_filter_bars
            ts = np.array([int(b.timestamp.timestamp()) for b in bars], dtype=np.int64)
            s_ts = int(_to_dt(start).timestamp()) if start else -2**62
            e_ts = int(_to_dt(end).timestamp()) if end else 2**62
            s_idx, e_idx = binary_filter_bars(ts, s_ts, e_ts)
            bars = bars[s_idx:e_idx]
        except (ImportError, Exception):
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


def _load_cross_symbol_pool(data_dir: str = "data") -> list[dict]:
    """加载全市场丛结构池（跨品种检索库）"""
    from pathlib import Path
    import json
    
    pool_path = Path(data_dir) / "library" / "full_structure_pool.jsonl"
    if not pool_path.exists():
        return []
    
    pool = []
    with open(pool_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                pool.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return pool


def active_match(query: ActiveMatchQuery, data_dir: str = "data", use_cross_symbol: bool = True) -> ActiveMatchResult:
    """
    核心匹配函数。

    对每个指定品种：
    1. 加载全量历史数据（MySQL 优先，CSV 降级）
    2. 在用户指定窗口内编译结构
    3. 对每个编译出的结构，在以下范围找最相似的段：
       - 自身历史（同品种不同时间段）
       - 跨品种丛结构库（如果 use_cross_symbol=True）
    4. 生成对比指引
    """
    config = query.compiler_config

    matched_structures: list[MatchedStructure] = []
    total_structures = 0
    total_cases = 0

    # 加载跨品种丛结构池（可选）
    cross_pool = _load_cross_symbol_pool(data_dir) if use_cross_symbol else []
    print(f"  [检索模式] {'跨品种+自身历史' if use_cross_symbol and cross_pool else '仅自身历史'}")
    if cross_pool:
        print(f"  [丛结构库] {len(cross_pool)} 条全市场结构")

    for sym in query.symbols:
        # 加载全量数据
        all_bars = _load_all_bars(sym, data_dir=data_dir)
        if len(all_bars) < 100:
            continue

        sname = symbol_name(sym)

        # 编译全量历史结构（作为自身检索库）
        all_structures = _compile_structures(all_bars, config, sym)

        # 编译用户窗口内的结构
        window_structures = _compile_structures(
            all_bars, config, sym,
            start=query.search_start,
            end=query.search_end,
        )
        total_structures += len(window_structures)

        # 对窗口内的每个结构，找相似段
        for ws in window_structures:
            ws_inv = ws.invariants or {}
            ws_start = ws.t_start.strftime("%Y-%m-%d") if ws.t_start else ""
            ws_end = ws.t_end.strftime("%Y-%m-%d") if ws.t_end else ""

            candidates = []

            # ── 1. 自身历史对比 ──
            for hs in all_structures:
                if hs is ws:
                    continue
                # 跳过时间窗口内的
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

            # ── 2. 跨品种丛结构库对比 ──
            if cross_pool:
                for entry in cross_pool:
                    # 跳过同品种（已在自身历史中处理）
                    if entry.get("symbol") == sym:
                        continue

                    pool_inv = entry.get("invariants", {})
                    if not pool_inv:
                        continue

                    # 用 invariants 直接计算相似度（简化版）
                    sc_geom = 1.0 / (1.0 + abs((ws_inv.get('avg_speed_ratio', 0) - pool_inv.get('avg_speed_ratio', 0)) / max(pool_inv.get('avg_speed_ratio', 1), 0.01)))
                    sc_rel = 1.0 / (1.0 + abs((ws_inv.get('avg_time_ratio', 0) - pool_inv.get('avg_time_ratio', 0)) / max(pool_inv.get('avg_time_ratio', 1), 0.01)))
                    sc_fam = 1.0 / (1.0 + abs((ws_inv.get('zone_rel_bw', 0) - pool_inv.get('zone_rel_bw', 0)) / 0.01))
                    sc_total = (sc_geom * 0.4 + sc_rel * 0.4 + sc_fam * 0.2)

                    cross_sym = entry.get("symbol", "unknown")
                    cross_sname = symbol_name(cross_sym)

                    case = HistoricalCase(
                        symbol=cross_sym,
                        symbol_name=cross_sname,
                        period_start=entry.get("start_date", "N/A"),
                        period_end=entry.get("end_date", "N/A"),
                        similarity=round(sc_total, 4),
                        sim_geometry=round(sc_geom, 4),
                        sim_relation=round(sc_rel, 4),
                        sim_family=round(sc_fam, 4),
                        diff_detail=_diff_detail(ws_inv, pool_inv),
                        direction="cross_ref",  # 跨品种标记
                        outcome_move=0.0,
                        outcome_days=0,
                        cycle_count=entry.get("cycle_count", 0),
                        avg_speed_ratio=round(pool_inv.get('avg_speed_ratio', 0), 4),
                        avg_time_ratio=round(pool_inv.get('avg_time_ratio', 0), 4),
                        zone_center=round(pool_inv.get('zone_center', 0), 2),
                        zone_bandwidth=round(pool_inv.get('zone_rel_bw', 0), 4),
                        description=f"{cross_sname}({cross_sym}) {entry.get('start_date', '')[:7]}~{entry.get('end_date', '')[:7]}: 丛结构 cycles={entry.get('cycle_count', 0)}, SR={pool_inv.get('avg_speed_ratio', 0):.2f}",
                    )
                    candidates.append(case)

            # 按相似度排序取 top_k（混合自身历史+跨品种）
            candidates.sort(key=lambda c: c.similarity, reverse=True)
            top = candidates[:query.top_k]
            total_cases += len(top)

            # 统计来源分布
            self_count = sum(1 for c in top if c.symbol == sym)
            cross_count = len(top) - self_count
            if cross_count > 0:
                guide_prefix = f"[跨品种 {cross_count} 条 + 自身 {self_count} 条]\n"
            else:
                guide_prefix = ""

            # 生成对比指引
            guide = _generate_comparison_guide(ws, top, query)
            if guide_prefix:
                guide.insert(0, guide_prefix)

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
