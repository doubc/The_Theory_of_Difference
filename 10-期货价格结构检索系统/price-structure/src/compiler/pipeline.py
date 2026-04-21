"""
结构编译器 — 统一入口

四层流水线：
  3.1 极值提取 (pivots.py)
  3.2 段生成   (segments.py)
  3.3 关键区识别 (zones.py)
  3.4 结构组装 (cycles.py)
  3.5 丛识别   (bundles.py)
"""

from __future__ import annotations

from dataclasses import dataclass
from src.models import Point, Segment, Zone, Cycle, Structure, Bundle
from src.data.loader import Bar

# 子模块导入（保持对外 API 不变）
from src.compiler.pivots import extract_pivots
from src.compiler.segments import build_segments
from src.compiler.zones import detect_zones
from src.compiler.cycles import build_cycles, assemble_structures
from src.compiler.bundles import detect_bundles


# ─── 配置 ─────────────────────────────────────────────────

@dataclass
class CompilerConfig:
    min_amplitude: float = 0.02
    min_duration: int = 2
    noise_filter: float = 0.005
    zone_bandwidth: float = 0.01
    cluster_eps: float = 0.015
    cluster_min_points: int = 2
    min_cycles: int = 2
    tolerance: float = 0.02
    # 丛识别
    bundle_speed_tol: float = 0.4
    bundle_time_tol: float = 0.5


# ─── 编译结果 ──────────────────────────────────────────────

@dataclass
class CompileResult:
    bars_count: int
    pivots: list[Point]
    segments: list[Segment]
    zones: list[Zone]
    cycles: list[Cycle]
    structures: list[Structure]
    bundles: list[Bundle]
    config: CompilerConfig

    def summary(self) -> dict:
        return {
            "bars": self.bars_count,
            "pivots": len(self.pivots),
            "segments": len(self.segments),
            "zones": len(self.zones),
            "cycles": len(self.cycles),
            "structures": len(self.structures),
            "bundles": len(self.bundles),
            "top_structure": str(self.structures[0]) if self.structures else None,
        }


# ─── 统一入口 ──────────────────────────────────────────────

def compile_full(bars: list[Bar], config: CompilerConfig | None = None, symbol: str | None = None) -> CompileResult:
    """
    价格序列 → 结构对象

    完整编译流程：极值 → 段 → 区 → 循环 → 结构 → 丛
    """
    if config is None:
        config = CompilerConfig()

    # 3.1 极值提取
    pivots = extract_pivots(
        bars,
        min_amplitude=config.min_amplitude,
        min_duration=config.min_duration,
        noise_filter=config.noise_filter,
    )

    # 3.2 段生成
    segments = build_segments(pivots)

    # 3.3 关键区识别
    zones = detect_zones(
        pivots,
        zone_bandwidth=config.zone_bandwidth,
        cluster_eps=config.cluster_eps,
        cluster_min_points=config.cluster_min_points,
    )

    # 3.4 Cycle + Structure 组装
    cycles = build_cycles(segments, zones, min_cycles=config.min_cycles)
    sym = symbol or (bars[0].symbol if bars else None)
    structures = assemble_structures(cycles, zones, min_cycles=config.min_cycles, symbol=sym)

    # 3.5 丛识别
    bundles = detect_bundles(
        structures,
        speed_tol=config.bundle_speed_tol,
        time_tol=config.bundle_time_tol,
    )

    return CompileResult(
        bars_count=len(bars),
        pivots=pivots,
        segments=segments,
        zones=zones,
        cycles=cycles,
        structures=structures,
        bundles=bundles,
        config=config,
    )
