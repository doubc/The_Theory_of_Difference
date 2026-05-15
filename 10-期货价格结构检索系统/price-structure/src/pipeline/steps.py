"""
Pipeline steps — 日更流水线的各步骤函数

P1 整改：将 daily_pipeline.py 中的过程代码拆分为独立 step 函数。
每个 step 签名统一：step_xxx(ctx: PipelineContext, cfg: PipelineConfig) -> PipelineContext
step 只负责逻辑，不负责 I/O（报告生成由 report.py 处理）。

流水线步骤：
1. step_load_data    — 加载行情数据
2. step_compile      — 编译结构
3. step_graph_ingest — 知识图谱写入
4. step_rule_scan    — 规则扫描
5. step_quality      — 质量分层
6. step_lifecycle    — 生命周期记录
7. step_retrieval    — 相似结构检索
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from src.pipeline.context import PipelineContext
from src.pipeline.config import PipelineConfig


def step_load_data(ctx: PipelineContext, cfg: PipelineConfig) -> PipelineContext:
    """Step 1: 加载行情数据"""
    try:
        from src.data.loader import load_cu0

        loader = load_cu0(cfg.data.dir, dedup=True)
        bars = loader.get()
        ctx.bars = bars
        ctx.bar_count = len(bars)
        if bars:
            ctx.bar_range = f"{bars[0].timestamp:%Y-%m-%d} ~ {bars[-1].timestamp:%Y-%m-%d}"
        else:
            ctx.bar_range = ""
    except Exception as e:
        ctx.errors.append(f"step_load_data: {e}")
    return ctx


def step_compile(ctx: PipelineContext, cfg: PipelineConfig) -> PipelineContext:
    """Step 2: 编译结构"""
    try:
        from src.compiler.pipeline import compile_full, CompilerConfig

        cc = cfg.compiler
        config = CompilerConfig(
            min_amplitude=cc.min_amplitude,
            min_duration=cc.min_duration,
            noise_filter=cc.noise_filter,
            use_log_price=cc.use_log_price,
            min_segment_delta_pct=cc.min_segment_delta_pct,
            zone_bandwidth=cc.zone_bandwidth,
            cluster_eps=cc.cluster_eps,
            cluster_min_points=cc.cluster_min_points,
            min_cycles=cc.min_cycles,
            tolerance=cc.tolerance,
        )
        result = compile_full(ctx.bars, config)
        ctx.compile_result = result
        ctx.structures = result.structures
        ctx.zones = result.zones
        ctx.bundles = result.bundles
        ctx.system_states = result.system_states
    except Exception as e:
        ctx.errors.append(f"step_compile: {e}")
    return ctx


def step_graph_ingest(ctx: PipelineContext, cfg: PipelineConfig) -> PipelineContext:
    """Step 3: 知识图谱增量写入"""
    try:
        from src.graph.store import GraphStore

        graph_store = GraphStore(base_path=cfg.graph.base_path)
        ctx.graph_store = graph_store

        if ctx.structures:
            graph_result = graph_store.daily_ingest(ctx.structures, symbol=ctx.symbol)
            ctx.graph_result = graph_result
            ctx.graph_stats = {
                "nodes_written": graph_result.get("structures_ingested", 0),
                "edges_written": graph_result.get("edges_ingested", 0),
            }
    except Exception as e:
        ctx.errors.append(f"step_graph_ingest: {e}")
        ctx.graph_store = None
    return ctx


def step_rule_scan(ctx: PipelineContext, cfg: PipelineConfig) -> PipelineContext:
    """Step 4: 规则扫描"""
    try:
        from src.dsl.rule import load_rules, scan

        rules_path = Path(cfg.rules_dir) / cfg.rules_default_file
        rules = load_rules(rules_path)
        matches = scan(ctx.structures, rules)
        ctx.rules = rules
        ctx.matches = matches
    except Exception as e:
        ctx.errors.append(f"step_rule_scan: {e}")
    return ctx


def step_quality(ctx: PipelineContext, cfg: PipelineConfig) -> PipelineContext:
    """Step 5: 质量分层"""
    try:
        from src.quality import stratify_structures

        strat = stratify_structures(ctx.structures, ctx.system_states)
        ctx.quality_result = strat
        ctx.stratification_summary = strat.summary()
    except Exception as e:
        ctx.errors.append(f"step_quality: {e}")
    return ctx


def step_lifecycle(ctx: PipelineContext, cfg: PipelineConfig) -> PipelineContext:
    """Step 6: 生命周期记录"""
    try:
        from src.lifecycle import LifecycleTracker

        tracker = LifecycleTracker(data_dir=str(Path(cfg.data.dir) / "lifecycle"))
        lc_records = tracker.record(
            ctx.symbol, ctx.structures, ctx.system_states,
            date_str=ctx.run_date,
        )
        ctx.lifecycle_records = lc_records
    except Exception as e:
        ctx.errors.append(f"step_lifecycle: {e}")
    return ctx


def step_retrieval(ctx: PipelineContext, cfg: PipelineConfig) -> PipelineContext:
    """Step 7: 相似结构检索"""
    try:
        from src.sample.store import SampleStore
        from src.retrieval.engine import RetrievalEngine

        library_path = str(Path(cfg.samples_dir) / cfg.samples_library_file)
        store = SampleStore(library_path)

        try:
            engine = RetrievalEngine(store, graph_store=ctx.graph_store)
        except TypeError:
            engine = RetrievalEngine(store)

        ctx.retrieval_engine = engine
        rcfg = cfg.retrieval

        retrieval_results = []
        for m in ctx.matches[:cfg.report.max_candidates]:
            ret = engine.retrieve(
                m.structure,
                top_k=rcfg.top_k,
                min_score=rcfg.min_score,
                filter_contrast=rcfg.filter_contrast,
                max_lookback_days=rcfg.max_lookback_days,
                graph_weight=rcfg.graph_weight,
            )
            retrieval_results.append((m, ret))

        ctx.retrieval_results = retrieval_results
    except Exception as e:
        ctx.errors.append(f"step_retrieval: {e}")
    return ctx
