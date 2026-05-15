"""
Pipeline configuration — 从 config.yaml 加载流水线配置

P1 整改：将硬编码参数收敛到配置文件，支持 dataclass 类型安全访问。

用法:
    from src.pipeline.config import load_config, PipelineConfig
    cfg = load_config()          # 默认读 config.yaml
    cfg = load_config("other.yaml")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ─── 子配置 dataclass ──────────────────────────────────────

@dataclass
class ProjectSettings:
    """项目元信息"""
    name: str = "价格结构形式系统"
    version: str = "3.1.0"


@dataclass
class DataSettings:
    """数据层配置"""
    dir: str = "data"
    cache_dir: str = "data/cache"
    local_dir: str = "data/local"
    symbols: list[dict[str, Any]] = field(default_factory=list)
    mysql: dict[str, Any] = field(default_factory=dict)
    parquet: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompilerSettings:
    """编译器参数 — 与 CompilerConfig dataclass 一一对应"""
    min_amplitude: float = 0.03
    min_duration: int = 3
    noise_filter: float = 0.008
    use_log_price: bool = True
    min_segment_delta_pct: float = 0.005
    zone_bandwidth: float = 0.015
    cluster_eps: float = 0.02
    cluster_min_points: int = 2
    min_cycles: int = 2
    tolerance: float = 0.03
    bundle_speed_tol: float = 0.4
    bundle_time_tol: float = 0.5
    multi_freq: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalSettings:
    """检索引擎配置"""
    top_k: int = 10
    min_score: float = 0.3
    filter_contrast: bool = True
    max_lookback_days: int = 0
    graph_weight: float = 0.10
    # 排序权重
    rank_weights: dict[str, float] = field(default_factory=lambda: {
        "base": 0.78,
        "graph": 0.12,
        "recency": 0.05,
        "quality": 0.05,
    })


@dataclass
class GraphSettings:
    """知识图谱配置"""
    base_path: str = "data/graph"
    enable_embedding: bool = True
    enable_evolution: bool = True
    enable_narrative_chain: bool = True


@dataclass
class QualitySettings:
    """质量分层配置"""
    tier_a_threshold: float = 0.75
    tier_b_threshold: float = 0.50
    tier_c_threshold: float = 0.25
    dimension_weights: dict[str, float] = field(default_factory=lambda: {
        "完整性": 0.25,
        "运动可信": 0.25,
        "守恒一致": 0.20,
        "时间成熟": 0.15,
        "后验可追溯": 0.15,
    })


@dataclass
class SignalSettings:
    """信号检测阈值配置"""
    fake_penetration_threshold: float = 0.3
    fake_volume_climax: float = 1.5
    fake_volume_div: float = 0.8
    fake_flux_weak: float = 0.3
    fake_shadow_ratio: float = 2.0
    breakout_strong: float = 0.80
    breakout_weak: float = 0.55
    aging_days_threshold: int = 14


@dataclass
class ReportSettings:
    """报告输出配置"""
    dir: str = "output"
    charts: bool = True
    report: bool = True
    max_candidates: int = 10


@dataclass
class PipelineConfig:
    """流水线总配置 — 聚合所有子配置"""
    project: ProjectSettings = field(default_factory=ProjectSettings)
    data: DataSettings = field(default_factory=DataSettings)
    compiler: CompilerSettings = field(default_factory=CompilerSettings)
    retrieval: RetrievalSettings = field(default_factory=RetrievalSettings)
    graph: GraphSettings = field(default_factory=GraphSettings)
    quality: QualitySettings = field(default_factory=QualitySettings)
    report: ReportSettings = field(default_factory=ReportSettings)
    signals: SignalSettings = field(default_factory=SignalSettings)

    # 规则引擎和样本库（兼容旧 config.yaml 字段）
    rules_dir: str = "src/dsl/rules"
    rules_default_file: str = "default.yaml"
    samples_dir: str = "data/samples"
    samples_library_file: str = "library.jsonl"


# ─── 加载函数 ──────────────────────────────────────────────

def load_config(path: str | Path = "config.yaml") -> PipelineConfig:
    """
    从 YAML 文件加载流水线配置

    Args:
        path: 配置文件路径，默认为项目根目录的 config.yaml

    Returns:
        PipelineConfig 实例

    Raises:
        FileNotFoundError: 配置文件不存在
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"配置文件不存在: {p}")

    with open(p, encoding="utf-8") as f:
        raw: dict = yaml.safe_load(f) or {}

    # ── project ──
    proj = raw.get("project", {})
    project = ProjectSettings(
        name=proj.get("name", "价格结构形式系统"),
        version=proj.get("version", "3.1.0"),
    )

    # ── data ──
    dat = raw.get("data", {})
    data = DataSettings(
        dir=dat.get("dir", "data"),
        cache_dir=dat.get("cache_dir", "data/cache"),
        local_dir=dat.get("local_dir", "data/local"),
        symbols=dat.get("symbols", []),
        mysql=dat.get("mysql", {}),
        parquet=dat.get("parquet", {}),
    )

    # ── compiler ──
    comp = raw.get("compiler", {})
    compiler = CompilerSettings(
        min_amplitude=comp.get("min_amplitude", 0.03),
        min_duration=comp.get("min_duration", 3),
        noise_filter=comp.get("noise_filter", 0.008),
        use_log_price=comp.get("use_log_price", True),
        min_segment_delta_pct=comp.get("min_segment_delta_pct", 0.005),
        zone_bandwidth=comp.get("zone_bandwidth", 0.015),
        cluster_eps=comp.get("cluster_eps", 0.02),
        cluster_min_points=comp.get("cluster_min_points", 2),
        min_cycles=comp.get("min_cycles", 2),
        tolerance=comp.get("tolerance", 0.03),
        bundle_speed_tol=comp.get("bundle_speed_tol", 0.4),
        bundle_time_tol=comp.get("bundle_time_tol", 0.5),
        multi_freq=comp.get("multi_freq", {}),
    )

    # ── retrieval ──
    ret = raw.get("retrieval", {})
    retrieval = RetrievalSettings(
        top_k=ret.get("top_k", 10),
        min_score=ret.get("min_score", 0.3),
        filter_contrast=ret.get("filter_contrast", True),
        max_lookback_days=ret.get("max_lookback_days", 0),
        graph_weight=ret.get("graph_weight", 0.10),
        rank_weights=ret.get("rank_weights", {
            "base": 0.78, "graph": 0.12, "recency": 0.05, "quality": 0.05,
        }),
    )

    # ── graph ──
    grp = raw.get("graph", {})
    graph = GraphSettings(
        base_path=grp.get("base_path", "data/graph"),
        enable_embedding=grp.get("enable_embedding", True),
        enable_evolution=grp.get("enable_evolution", True),
        enable_narrative_chain=grp.get("enable_narrative_chain", True),
    )

    # ── quality ──
    qua = raw.get("quality", {})
    quality = QualitySettings(
        tier_a_threshold=qua.get("tier_a_threshold", 0.75),
        tier_b_threshold=qua.get("tier_b_threshold", 0.50),
        tier_c_threshold=qua.get("tier_c_threshold", 0.25),
        dimension_weights=qua.get("dimension_weights", {
            "完整性": 0.25, "运动可信": 0.25, "守恒一致": 0.20,
            "时间成熟": 0.15, "后验可追溯": 0.15,
        }),
    )

    # ── signals ──
    sig = raw.get("signals", {})
    signals = SignalSettings(
        fake_penetration_threshold=sig.get("fake_penetration_threshold", 0.3),
        fake_volume_climax=sig.get("fake_volume_climax", 1.5),
        fake_volume_div=sig.get("fake_volume_div", 0.8),
        fake_flux_weak=sig.get("fake_flux_weak", 0.3),
        fake_shadow_ratio=sig.get("fake_shadow_ratio", 2.0),
        breakout_strong=sig.get("breakout_strong", 0.80),
        breakout_weak=sig.get("breakout_weak", 0.55),
        aging_days_threshold=sig.get("aging_days_threshold", 14),
    )

    # ── report ──
    rep = raw.get("report", raw.get("output", {}))
    report = ReportSettings(
        dir=rep.get("dir", "output"),
        charts=rep.get("charts", True),
        report=rep.get("report", True),
        max_candidates=rep.get("max_candidates", 10),
    )

    # ── 兼容旧字段 ──
    rules_dir = raw.get("rules", {}).get("dir", "src/dsl/rules")
    rules_default_file = raw.get("rules", {}).get("default_file", "default.yaml")
    samples_dir = raw.get("samples", {}).get("dir", "data/samples")
    samples_library_file = raw.get("samples", {}).get("library_file", "library.jsonl")

    return PipelineConfig(
        project=project,
        data=data,
        compiler=compiler,
        retrieval=retrieval,
        graph=graph,
        quality=quality,
        report=report,
        rules_dir=rules_dir,
        rules_default_file=rules_default_file,
        samples_dir=samples_dir,
        samples_library_file=samples_library_file,
        signals=signals,
    )
