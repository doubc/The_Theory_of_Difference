"""
Pipeline context — 流水线运行上下文

P1 整改：将 daily_pipeline.py 中散落的临时变量收敛到一个 dataclass，
各 step 函数通过 ctx 传递数据，消除隐式依赖。

设计原则：
1. 每个字段都有默认值，step 函数按需填充
2. 不可变思想：step 返回新 ctx，不原地修改（但 dataclass 暂不做 frozen）
3. 所有 step 函数签名统一：step_xxx(ctx, cfg) -> PipelineContext
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PipelineContext:
    """
    日更流水线的运行上下文 — 所有 step 的共享状态

    字段按流水线阶段分组，step 函数按序填充。
    任何 step 可以读取前面 step 写入的字段。
    """

    # ── 基础标识 ──
    symbol: str = "CU000"
    run_date: str = ""                    # YYYY-MM-DD

    # ── Step 1: 加载数据 ──
    bars: list[Any] = field(default_factory=list)
    bar_count: int = 0
    bar_range: str = ""                   # "2025-01-01 ~ 2026-04-25"

    # ── Step 2: 编译 ──
    compile_result: Any = None            # CompileResult from compiler.pipeline
    structures: list[Any] = field(default_factory=list)
    zones: list[Any] = field(default_factory=list)
    bundles: list[Any] = field(default_factory=list)
    system_states: list[Any] = field(default_factory=list)

    # ── Step 3: 规则扫描 ──
    rules: Any = None                     # list of Rule
    matches: list[Any] = field(default_factory=list)  # list of Match

    # ── Step 4: 质量分层 ──
    quality_result: Any = None            # StratificationResult
    stratification_summary: str = ""

    # ── Step 5: 生命周期 ──
    lifecycle_records: list[Any] = field(default_factory=list)

    # ── Step 6: 知识图谱 ──
    graph_store: Any = None               # GraphStore
    graph_result: dict[str, Any] = field(default_factory=dict)
    graph_stats: dict[str, int] = field(default_factory=dict)

    # ── Step 7: 检索 ──
    retrieval_results: list[tuple[Any, Any]] = field(default_factory=list)  # [(Match, RetrievalResult)]
    retrieval_engine: Any = None          # RetrievalEngine

    # ── 输出 ──
    report_path: Path | None = None
    report_lines: list[str] = field(default_factory=list)

    # ── 运行指标 ──
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.run_date:
            self.run_date = datetime.now().strftime("%Y-%m-%d")
