"""
日更流水线 — 统一入口

P1 整改：将 scripts/daily_pipeline.py 的核心逻辑收敛到此处。
scripts/daily_pipeline.py 瘦身为纯入口调用。

用法:
    from src.pipeline.daily import run_daily_pipeline
    ctx = run_daily_pipeline("config.yaml")
    print(ctx.report_path)
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from src.pipeline.config import load_config, PipelineConfig
from src.pipeline.context import PipelineContext
from src.pipeline.steps import (
    step_load_data,
    step_compile,
    step_graph_ingest,
    step_rule_scan,
    step_quality,
    step_lifecycle,
    step_retrieval,
)
from src.pipeline.report import render_daily_report
from src.signals import _apply_signal_config


def _resolve_paths(cfg: PipelineConfig, base_dir: Path) -> None:
    """Resolve relative paths in config against the config file's parent directory"""
    if not Path(cfg.data.dir).is_absolute():
        cfg.data.dir = str(base_dir / cfg.data.dir)
    if not Path(cfg.graph.base_path).is_absolute():
        cfg.graph.base_path = str(base_dir / cfg.graph.base_path)
    if not Path(cfg.report.dir).is_absolute():
        cfg.report.dir = str(base_dir / cfg.report.dir)
    if not Path(cfg.rules_dir).is_absolute():
        cfg.rules_dir = str(base_dir / cfg.rules_dir)
    if not Path(cfg.samples_dir).is_absolute():
        cfg.samples_dir = str(base_dir / cfg.samples_dir)


def run_daily_pipeline(config_path: str = "config.yaml") -> PipelineContext:
    """
    执行日更流水线 — 统一入口

    Args:
        config_path: 配置文件路径

    Returns:
        PipelineContext 含所有步骤结果
    """
    cfg = load_config(config_path)

    # Resolve relative paths against config file's parent directory
    config_dir = Path(config_path).resolve().parent
    _resolve_paths(cfg, config_dir)

    # Apply signal thresholds from config
    _apply_signal_config(cfg)

    ctx = PipelineContext(symbol="CU000")

    print(f"[{ctx.run_date}] 日更流水线启动")

    # Step 1: 加载数据
    print("  [1] 加载数据...")
    ctx = step_load_data(ctx, cfg)
    print(f"      {ctx.bar_count} bars ({ctx.bar_range})")

    # Step 2: 编译
    print("  [2] 编译...")
    ctx = step_compile(ctx, cfg)
    print(f"      {len(ctx.structures)} 结构, {len(ctx.bundles)} 丛")

    # Step 3: 规则扫描
    print("  [3] 规则扫描...")
    ctx = step_rule_scan(ctx, cfg)
    print(f"      {len(ctx.matches)} 匹配")

    # Step 4: 质量分层
    print("  [4] 质量分层...")
    ctx = step_quality(ctx, cfg)
    if ctx.stratification_summary:
        try:
            print(f"      {ctx.stratification_summary}")
        except UnicodeEncodeError:
            # Windows GBK terminal can't handle emoji
            print(f"      Quality stratification: {len(ctx.structures)} structures")

    # Step 5: 生命周期
    print("  [5] 生命周期记录...")
    ctx = step_lifecycle(ctx, cfg)
    print(f"      记录 {len(ctx.lifecycle_records)} 个结构快照")

    # Step 6: 知识图谱写入
    print("  [6] 知识图谱写入...")
    ctx = step_graph_ingest(ctx, cfg)
    if ctx.graph_result:
        print(f"      图谱: {ctx.graph_stats.get('nodes_written', 0)} 节点, {ctx.graph_stats.get('edges_written', 0)} 边")
    elif ctx.errors:
        print(f"      图谱写入失败: {ctx.errors[-1]}")

    # Step 7: 检索
    print("  [7] 相似检索...")
    ctx = step_retrieval(ctx, cfg)

    # Step 8: 报告
    print("  [8] 生成报告...")
    report_text = render_daily_report(ctx, cfg)
    report_dir = Path(cfg.report.dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"daily_{ctx.run_date}.md"
    report_path.write_text(report_text, encoding="utf-8")
    ctx.report_path = report_path
    ctx.report_lines = report_text.split("\n")
    print(f"      报告: {report_path}")

    # 错误汇总
    if ctx.errors:
        print(f"  [WARN] {len(ctx.errors)} errors:")
        for err in ctx.errors:
            try:
                print(f"      - {err}")
            except UnicodeEncodeError:
                print(f"      - (encoding error)")

    print(f"[{ctx.run_date}] 完成")
    return ctx
