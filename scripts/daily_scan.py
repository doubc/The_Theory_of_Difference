"""
每日机会扫描 v3 —— 只做候选识别与 top_k 匹配，聚合与渲染外包。

流程:
1. 编译每个品种的最新结构
2. 活跃度过滤
3. 对活跃模板计算归一化距离,取 top_k
4. 委托 opportunity.aggregate_opportunity() 生成 Opportunity
5. 委托 daily_report.render_daily_report() 渲染 HTML
6. 同步落一份 JSON 快照供复盘
"""
import hashlib
import json
import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, inspect
from src.data.loader import MySQLLoader
from src.data.symbol_meta import symbol_name
from src.compiler.pipeline import compile_full, CompilerConfig
from src.retrieval.opportunity import (
    TemplateMatch, aggregate_opportunity, FEATURE_SCALES, FEATURES,
)
from src.workbench.daily_report import render_daily_report
from src.relations import compute_motion
from src.graph.store import GraphStore

MAX_DIST_THRESHOLD = 1.5
TOP_K = 5


def _distance(inv1: dict, inv2: dict) -> tuple[float, dict]:
    """归一化欧氏距离 + 分项差异"""
    diff = {}
    sq = 0.0
    for f in FEATURES:
        scale = FEATURE_SCALES[f]
        v1 = (inv1.get(f) or 0) / scale
        v2 = (inv2.get(f) or 0) / scale
        d = abs(v1 - v2)
        diff[f] = round(d, 3)
        sq += d ** 2
    return math.sqrt(sq), diff


def _is_active(bars, min_atr_pct: float = 0.005) -> bool:
    """活跃度过滤：近 20 根 bar 的平均 ATR% 判断品种是否活跃"""
    if len(bars) < 20:
        return False
    recent = bars[-20:]
    atrs = []
    for i in range(1, len(recent)):
        b = recent[i]
        prev_close = recent[i - 1].close
        tr = max(b.high - b.low, abs(b.high - prev_close), abs(b.low - prev_close))
        atrs.append(tr / prev_close if prev_close > 0 else 0)
    return (sum(atrs) / len(atrs) if atrs else 0) >= min_atr_pct


def _config_hash(cfg: CompilerConfig) -> str:
    s = json.dumps(cfg.__dict__, sort_keys=True, default=str)
    return hashlib.md5(s.encode()).hexdigest()


def _load_templates() -> list[dict]:
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "library", "high_potential_templates.jsonl"
    )
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
    return out


def _get_symbols() -> list[str]:
    try:
        import os
        password = os.getenv('MYSQL_PASSWORD', '')
        pwd_part = f":{password}" if password else ""
        engine = create_engine(f"mysql+pymysql://root{pwd_part}@localhost/sina?charset=utf8")
        tables = inspect(engine).get_table_names()
        return [t for t in tables if not t.endswith("m5") and not t.startswith("test")]
    except Exception:
        return []


def _build_template_match(tmpl: dict, distance: float, diff: dict) -> TemplateMatch:
    oc = tmpl.get("outcome", {})
    return TemplateMatch(
        symbol=tmpl["symbol"],
        symbol_name=tmpl.get("symbol_name") or symbol_name(tmpl["symbol"]),
        end_date=tmpl["end_date"],
        outcome_start=oc.get("outcome_start_date", "N/A"),
        direction=tmpl.get("primary_direction", oc.get("direction", "unclear")),
        up_move=oc.get("up_move", 0.0),
        down_move=oc.get("down_move", 0.0),
        days_to_peak=oc.get("days_to_peak", 0),
        days_to_trough=oc.get("days_to_trough", 0),
        bundle_id=tmpl.get("bundle_id"),
        diff_detail=diff,
        distance=round(distance, 4),
        similarity=round(1 / (1 + distance), 4),
    )


def daily_scan(scan_window_years: int = 3):
    print(f"=== 每日结构机会扫描  [{datetime.now():%Y-%m-%d %H:%M}] ===")

    # 1. 加载活跃参照系
    all_templates = _load_templates()
    cur_year = datetime.now().year
    active_templates = [
        t for t in all_templates
        if cur_year - int(t["end_date"][:4]) <= scan_window_years
    ]
    print(f"模板库 {len(all_templates)} 条，活跃参照系 {len(active_templates)} 条。")
    if not active_templates:
        print("活跃模板为空，请先运行 identify_high_potential_structures.py")
        return

    # 2. 扫描全市场
    import os
    password = os.getenv('MYSQL_PASSWORD', '')
    loader = MySQLLoader(host="localhost", user="root", password=password, db="sina")
    config = CompilerConfig(min_amplitude=0.02, min_duration=3, zone_bandwidth=0.01)
    cfg_hash = _config_hash(config)
    symbols = _get_symbols()

    # 知识图谱：每日增量更新（与扫描同步）
    graph_dir = os.path.join(os.path.dirname(__file__), "..", "data", "graph")
    graph_store = GraphStore(base_path=graph_dir)

    structures_found = 0
    opportunities = []
    data_cutoff = datetime.now().strftime("%Y-%m-%d")

    for sym in symbols:
        try:
            bars = loader.get(symbol=sym, freq="1d")
            if len(bars) < 50:
                continue
            if not _is_active(bars):
                continue

            result = compile_full(bars, config, symbol=sym, graph_store=graph_store)
            if not result.structures:
                continue
            structures_found += 1

            current_st = result.structures[-1]

            # V1.6: 计算运动态（含 movement_type）
            # compile_full 已建 motion（默认 OSCILLATION），强制重新计算真值
            current_st.motion = compute_motion(current_st)
            current_inv = current_st.invariants or {}
            current_price = bars[-1].close
            confirmed_at = getattr(current_st, "t_end", None) or str(bars[-1].timestamp)

            # 3. top_k 匹配（不再只留 best_match）
            scored = []
            for tmpl in active_templates:
                dist, diff = _distance(current_inv, tmpl.get("invariants", {}))
                if dist < MAX_DIST_THRESHOLD:
                    scored.append((dist, diff, tmpl))
            if not scored:
                continue
            scored.sort(key=lambda x: x[0])
            top = scored[:TOP_K]
            top_matches = [_build_template_match(t, d, diff) for d, diff, t in top]

            # 4. 委托聚合层
            evidence = {
                "config_hash": cfg_hash,
                "data_cutoff": data_cutoff,
                "template_pool_size": len(active_templates),
                "scan_window_years": scan_window_years,
                "top_k": TOP_K,
            }
            opp = aggregate_opportunity(
                symbol=sym,
                symbol_name=symbol_name(sym),
                current_price=round(current_price, 2),
                confirmed_at=str(confirmed_at),
                current_inv=current_inv,
                top_matches=top_matches,
                evidence=evidence,
                structure=current_st,  # V1.6: 传入结构以提取 movement_type
            )
            if opp is not None:
                opportunities.append(opp)

        except Exception:
            continue

    # 5. 排序 + 渲染 + 落快照
    opportunities.sort(key=lambda o: o.attention_score, reverse=True)
    scan_meta = {
        "total_symbols": len(symbols),
        "structures_found": structures_found,
        "template_count": len(active_templates),
        "data_cutoff": data_cutoff,
        "config_hash": cfg_hash,
    }

    print(
        f"扫描 {len(symbols)} 品种 / 识别 {structures_found} 结构 / "
        f"产出 {len(opportunities)} 机会"
    )

    # 知识图谱统计
    try:
        graph_stats = graph_store.stats()
        print(f"知识图谱: {graph_stats['structures']} 结构 / {graph_stats['zones']} Zone / {graph_stats['edges']} 边")
        graph_store.save_snapshot()
    except Exception:
        pass

    html_path = render_daily_report(opportunities, scan_meta)
    print(f"HTML 日报: {html_path}")

    snap_path = os.path.join(
        os.path.dirname(__file__), "..", "output",
        f"daily_scan_{datetime.now():%Y%m%d_%H%M}.json",
    )
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump(
            {"scan_meta": scan_meta,
             "opportunities": [o.to_dict() for o in opportunities]},
            f, ensure_ascii=False, indent=2,
        )
    print(f"JSON 快照: {snap_path}")


if __name__ == "__main__":
    daily_scan()
