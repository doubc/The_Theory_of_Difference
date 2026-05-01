#!/usr/bin/env python3
"""
日更流水线 v2.0 — 全品种自动执行

改进：
  1. 支持全品种扫描（不只是 CU0）
  2. 集成知识图谱增强
  3. 自动保存扫描结果到数据流管理器
  4. 自动生成每日摘要
  5. 自动创建复盘条目
  6. 输出结构化报告

用法：
  python3 scripts/daily_pipeline_v2.py                    # 全品种
  python3 scripts/daily_pipeline_v2.py --symbol CU0       # 单品种
  python3 scripts/daily_pipeline_v2.py --output output/   # 指定输出目录
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from src.data.loader import Bar, CSVLoader, MySQLLoader
from src.data.symbol_meta import load_symbol_meta, symbol_name
from src.compiler.pipeline import compile_full, CompilerConfig
from src.quality import assess_quality, QualityTier


def get_all_symbols() -> List[str]:
    """获取所有可用品种"""
    # CSV 品种
    data_dir = Path("data")
    csv_symbols = []
    if data_dir.exists():
        for f in sorted(data_dir.glob("*.csv")):
            sym = f.stem.upper()
            if len(sym) >= 2:
                csv_symbols.append(sym)

    # MySQL 品种
    mysql_symbols = []
    try:
        import os
        password = os.getenv('MYSQL_PASSWORD', '')
        if password:
            from sqlalchemy import create_engine, inspect
            user = os.getenv('MYSQL_USER', 'root')
            host = os.getenv('MYSQL_HOST', 'localhost')
            db = os.getenv('MYSQL_DB', 'sina')
            engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8")
            insp = inspect(engine)
            tables = insp.get_table_names()
            mysql_symbols = [t.upper() for t in tables
                           if not t.endswith("m5") and not t.startswith("test")
                           and not t.startswith("_")]
    except Exception:
        pass

    # symbol_meta 品种
    meta = load_symbol_meta()
    meta_symbols = list(meta.keys())

    return sorted(set(csv_symbols + mysql_symbols + meta_symbols))


def load_bars(symbol: str) -> List[Bar]:
    """加载品种数据"""
    # 尝试 MySQL
    try:
        password = os.getenv('MYSQL_PASSWORD', '')
        if password:
            loader = MySQLLoader(password=password, db="sina")
            bars = loader.get(symbol=symbol, freq="1d")
            if bars:
                return bars
    except Exception:
        pass

    # 降级 CSV
    csv_dir = Path("data")
    for pattern in [f"{symbol.lower()}.csv", f"{symbol}.csv", f"{symbol.upper()}.csv"]:
        path = csv_dir / pattern
        if path.exists():
            try:
                loader = CSVLoader(str(path), symbol=symbol)
                bars = loader.get()
                if bars:
                    return bars
            except Exception:
                continue

    return []


def compile_symbol(symbol: str, min_amp: float = 0.03, min_dur: int = 3,
                   min_cycles: int = 2) -> tuple:
    """编译单个品种"""
    bars = load_bars(symbol)
    if not bars or len(bars) < 30:
        return None, bars

    config = CompilerConfig(
        min_amplitude=min_amp, min_duration=min_dur,
        min_cycles=min_cycles,
        adaptive_pivots=True, fractal_threshold=0.34,
    )
    result = compile_full(bars, config, symbol=symbol)
    return result, bars


def extract_scan_result(symbol: str, result, bars: List[Bar]) -> Dict[str, Any]:
    """从编译结果提取扫描数据"""
    if not result or not result.ranked_structures:
        return None

    # 取最新结构
    structs = sorted(result.ranked_structures,
                    key=lambda s: s.t_end or datetime.min)
    latest = structs[-1]
    m = latest.motion
    p = latest.projection

    zone = latest.zone
    zone_center = zone.price_center if zone else 0
    zone_bw = zone.bandwidth if zone else 0
    last_price = bars[-1].close if bars else 0

    # 质量评估
    ss = result.get_system_state_for(latest) if hasattr(result, 'get_system_state_for') else None
    qa = assess_quality(latest, ss)

    # 运动阶段
    phase_str = m.phase_tendency if m else ""
    n_cycles = latest.cycle_count
    if "breakout" in phase_str:
        motion_label = "破缺"
    elif "confirmation" in phase_str:
        motion_label = "确认"
    elif "forming" in phase_str:
        motion_label = f"形成({n_cycles}次)"
    elif "stable" in phase_str:
        motion_label = "稳态"
    else:
        motion_label = "—"

    # 方向
    if "breakout" in phase_str or "confirmation" in phase_str:
        direction = "up" if last_price > zone_center else "down"
    elif m and abs(m.conservation_flux) > 0.2:
        direction = "up" if m.conservation_flux > 0 else "down"
    else:
        direction = "unclear"

    # 通量
    flux = m.conservation_flux if m else 0.0

    # 信号
    signal_info = None
    try:
        from src.signals import generate_signal
        sig = generate_signal(latest, bars=bars, system_state=ss)
        if sig:
            signal_info = {
                "kind": sig.kind.value,
                "direction": sig.direction,
                "confidence": round(sig.confidence, 3),
                "entry_price": round(sig.entry_price, 1),
                "stop_loss_price": round(sig.stop_loss_price, 1),
                "take_profit_price": round(sig.take_profit_price, 1),
                "rr_ratio": round(sig.rr_ratio, 2),
                "quality_tier": sig.quality_tier,
            }
    except Exception:
        pass

    return {
        "symbol": symbol,
        "symbol_name": symbol_name(symbol),
        "zone_center": round(zone_center, 1),
        "zone_bw": round(zone_bw, 1),
        "cycles": n_cycles,
        "motion": phase_str,
        "motion_label": motion_label,
        "flux": round(flux, 3),
        "score": round(qa.score * 100, 1),
        "tier": qa.tier.value,
        "direction": direction,
        "volume": int(bars[-1].volume) if hasattr(bars[-1], 'volume') else 0,
        "last_price": round(last_price, 1),
        "signal_info": signal_info,
        "is_blind": p.is_blind if p else False,
        "timestamp": datetime.now().isoformat(),
    }


def enrich_with_knowledge(result: Dict[str, Any]) -> Dict[str, Any]:
    """用知识图谱增强扫描结果"""
    try:
        from src.workbench.kg_helper import (
            get_product_knowledge, get_cross_variety_impacts,
            get_chain_peers_from_kg, get_sector_from_kg
        )

        symbol = result["symbol"]
        knowledge = get_product_knowledge(symbol)

        if "error" not in knowledge:
            result["knowledge_graph"] = {
                "entities_count": len(knowledge.get("entities", [])),
                "relations_count": len(knowledge.get("relations", [])),
                "chains_count": len(knowledge.get("chains", [])),
            }

        # 板块信息
        sector_info = get_sector_from_kg(symbol)
        result["sector"] = sector_info.get("sector", "未知")

        # 产业链关联
        peers = get_chain_peers_from_kg(symbol)
        result["chain_peers"] = peers

        # 跨品种影响
        impacts = get_cross_variety_impacts(symbol)
        result["cross_impacts_count"] = len(impacts)

    except Exception:
        pass

    return result


def run_daily_pipeline(symbols: List[str] = None, output_dir: str = "output",
                      min_amp: float = 0.03, min_dur: int = 3,
                      min_cycles: int = 2, enrich_kg: bool = True) -> Dict[str, Any]:
    """执行日更流水线"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    start_time = datetime.now()

    print(f"[{today}] 日更流水线 v2.0 启动")
    print(f"  输出目录: {out}")

    # 获取品种列表
    if symbols is None:
        symbols = get_all_symbols()
    print(f"  品种数量: {len(symbols)}")

    # 编译和扫描
    all_results = []
    errors = []

    for i, sym in enumerate(symbols):
        try:
            result, bars = compile_symbol(sym, min_amp, min_dur, min_cycles)
            if result and bars:
                scan_data = extract_scan_result(sym, result, bars)
                if scan_data:
                    # 知识图谱增强
                    if enrich_kg:
                        scan_data = enrich_with_knowledge(scan_data)
                    all_results.append(scan_data)
                    print(f"  [{i+1}/{len(symbols)}] {sym}: {scan_data['motion_label']} "
                         f"Zone {scan_data['zone_center']:.0f} "
                         f"通量{scan_data['flux']:+.3f} "
                         f"{scan_data['tier']}层({scan_data['score']:.0f}分)")
                else:
                    print(f"  [{i+1}/{len(symbols)}] {sym}: 无结构")
            else:
                print(f"  [{i+1}/{len(symbols)}] {sym}: 数据不足")
        except Exception as e:
            errors.append({"symbol": sym, "error": str(e)})
            print(f"  [{i+1}/{len(symbols)}] {sym}: 错误 - {e}")

    # 排序：按优先级
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 保存到数据流管理器
    try:
        from src.workbench.data_flow import get_flow_manager, ScanResult
        flow = get_flow_manager()
        scan_results = []
        for r in all_results:
            sr = ScanResult(
                symbol=r["symbol"],
                symbol_name=r["symbol_name"],
                zone_center=r["zone_center"],
                zone_bw=r["zone_bw"],
                cycles=r["cycles"],
                motion=r["motion"],
                flux=r["flux"],
                score=r["score"],
                tier=r["tier"],
                direction=r["direction"],
                volume=r.get("volume", 0),
                last_price=r["last_price"],
                priority_score=r["score"],
                phase_code=r["motion"].split("→")[-1].strip() if "→" in r["motion"] else r["motion"],
                price_position="",
                departure_score=0,
                signal_info=r.get("signal_info"),
                knowledge_graph=r.get("knowledge_graph"),
            )
            scan_results.append(sr)
        saved_count = flow.save_scan_results(scan_results)
        print(f"\n  数据流管理器: 保存 {saved_count} 条扫描结果")

        # 生成每日摘要
        summary = flow.generate_daily_summary()
        print(f"  每日摘要: {summary['scan_count']} 个品种, "
             f"📈{summary['up_count']} 📉{summary['down_count']}")

    except Exception as e:
        print(f"\n  数据流管理器保存失败: {e}")

    # 生成报告
    elapsed = (datetime.now() - start_time).total_seconds()
    report = {
        "date": today,
        "elapsed_seconds": round(elapsed, 1),
        "symbols_scanned": len(symbols),
        "structures_found": len(all_results),
        "errors": len(errors),
        "results": all_results,
        "error_details": errors[:10],
    }

    # 保存 JSON 报告
    report_file = out / f"daily_scan_{today}.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 保存 Markdown 报告
    md_lines = [
        f"# 📋 每日扫描报告 {today}",
        "",
        f"**扫描品种**: {len(symbols)} 个",
        f"**发现结构**: {len(all_results)} 个",
        f"**耗时**: {elapsed:.1f} 秒",
        "",
        "## 🎯 Top 10 机会",
        "",
    ]

    for i, r in enumerate(all_results[:10]):
        dir_icon = "📈" if r["direction"] == "up" else "📉" if r["direction"] == "down" else "➡️"
        md_lines.append(f"### #{i+1} {r['symbol']} · {r['symbol_name']}")
        md_lines.append(f"- {dir_icon} {r['motion_label']} · Zone {r['zone_center']:.0f}±{r['zone_bw']:.0f}")
        md_lines.append(f"- 通量: {r['flux']:+.3f} · 质量: {r['tier']}层({r['score']:.0f}分)")
        if r.get("signal_info"):
            sig = r["signal_info"]
            md_lines.append(f"- 信号: {sig.get('kind', '')} · 置信度{sig.get('confidence', 0):.0%}")
        if r.get("sector"):
            md_lines.append(f"- 板块: {r['sector']}")
        if r.get("chain_peers"):
            md_lines.append(f"- 产业链: {', '.join(r['chain_peers'][:5])}")
        md_lines.append("")

    # 板块分布
    md_lines.append("## 📊 板块分布")
    sector_dist = {}
    for r in all_results:
        sector = r.get("sector", "未知")
        sector_dist.setdefault(sector, []).append(r["symbol"])
    for sector, syms in sorted(sector_dist.items(), key=lambda x: -len(x[1])):
        md_lines.append(f"- **{sector}**: {len(syms)} 个 — {', '.join(syms[:5])}")

    md_file = out / f"daily_scan_{today}.md"
    md_file.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n  报告已保存:")
    print(f"    JSON: {report_file}")
    print(f"    Markdown: {md_file}")
    print(f"  耗时: {elapsed:.1f} 秒")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="日更流水线 v2.0")
    parser.add_argument("--symbol", "-s", type=str, help="单品种模式")
    parser.add_argument("--output", "-o", type=str, default="output", help="输出目录")
    parser.add_argument("--min-amp", type=float, default=0.03, help="最小振幅")
    parser.add_argument("--min-dur", type=int, default=3, help="最小持续时间")
    parser.add_argument("--min-cycles", type=int, default=2, help="最小周期数")
    parser.add_argument("--no-kg", action="store_true", help="禁用知识图谱增强")

    args = parser.parse_args()

    symbols = [args.symbol.upper()] if args.symbol else None

    report = run_daily_pipeline(
        symbols=symbols,
        output_dir=args.output,
        min_amp=args.min_amp,
        min_dur=args.min_dur,
        min_cycles=args.min_cycles,
        enrich_kg=not args.no_kg,
    )

    print(f"\n✅ 完成! 发现 {report['structures_found']} 个结构")
