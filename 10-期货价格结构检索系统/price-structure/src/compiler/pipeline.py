"""
结构编译器 — 统一入口

四层流水线：
  3.1 极值提取 (pivots.py)
  3.2 段生成   (segments.py)
  3.3 关键区识别 (zones.py)
  3.4 结构组装 (cycles.py)
  3.5 丛识别   (bundles.py)

关系算子层：relations.py（独立模块）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.models import Point, Segment, Zone, Cycle, Structure, Bundle, SystemState
from src.data.loader import Bar

from src.compiler.pivots import extract_pivots
from src.compiler.segments import build_segments, merge_micro_segments
from src.compiler.zones import detect_zones
from src.compiler.cycles import build_cycles, assemble_structures
from src.compiler.bundles import detect_bundles
from src.relations import (
    infer_narrative_context,
    build_system_state,
)
from src.graph import StructureGraph


# ─── 配置 ─────────────────────────────────────────────────

@dataclass
class CompilerConfig:
    min_amplitude: float = 0.02
    min_duration: int = 2
    noise_filter: float = 0.005
    use_log_price: bool = True
    min_segment_delta_pct: float = 0.005
    zone_bandwidth: float = 0.01
    cluster_eps: float = 0.015
    cluster_min_points: int = 2
    min_cycles: int = 2
    tolerance: float = 0.02
    bundle_speed_tol: float = 0.4
    bundle_time_tol: float = 0.5
    # ── V1.6 P1 新增 ──
    volume_weighted: bool = False   # 是否启用成交量加权极值提取 (D6.3)
    volume_boost: float = 0.3       # 成交量加权系数
    # ── v2.5 新增 ──
    adaptive_pivots: bool = True    # 自适应极值窗口
    fractal_threshold: float = 0.34 # 分形一致性阈值

    def __post_init__(self):
        """参数合理性校验"""
        errors = []
        if self.min_amplitude <= 0:
            errors.append(f"min_amplitude must be > 0, got {self.min_amplitude}")
        if self.min_duration < 1:
            errors.append(f"min_duration must be >= 1, got {self.min_duration}")
        if self.noise_filter < 0:
            errors.append(f"noise_filter must be >= 0, got {self.noise_filter}")
        if self.zone_bandwidth <= 0:
            errors.append(f"zone_bandwidth must be > 0, got {self.zone_bandwidth}")
        if self.cluster_eps <= 0:
            errors.append(f"cluster_eps must be > 0, got {self.cluster_eps}")
        if self.min_cycles < 1:
            errors.append(f"min_cycles must be >= 1, got {self.min_cycles}")
        if not 0 <= self.fractal_threshold <= 1:
            errors.append(f"fractal_threshold must be in [0,1], got {self.fractal_threshold}")
        if errors:
            raise ValueError(f"CompilerConfig validation failed:\n" + "\n".join(f"  - {e}" for e in errors))


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
    system_states: list[SystemState] = field(default_factory=list)
    graph: StructureGraph | None = None  # V1.6 P2: 知识图谱

    @property
    def ranked_structures(self) -> list[Structure]:
        """
        按 cycle_count + zone_strength 排序的结构列表。
        用于展示层（工作台、报告），不用于编译层。
        编译层保持先天完备性：候选结构逻辑平等。
        """
        return sorted(
            self.structures,
            key=lambda s: (s.cycle_count, s.zone.strength),
            reverse=True,
        )

    def summary(self) -> dict:
        result = {
            "bars": self.bars_count,
            "pivots": len(self.pivots),
            "segments": len(self.segments),
            "zones": len(self.zones),
            "cycles": len(self.cycles),
            "structures": len(self.structures),
            "bundles": len(self.bundles),
            "top_structure": str(self.structures[0]) if self.structures else None,
        }
        if self.system_states:
            result["system_states"] = len(self.system_states)
            result["reliable_count"] = sum(1 for ss in self.system_states if ss.is_reliable)
            result["blind_count"] = sum(1 for ss in self.system_states if ss.projection.is_blind)
        return result


# ─── 统一入口 ──────────────────────────────────────────────

def compile_full(bars: list[Bar], config: CompilerConfig | None = None, symbol: str | None = None) -> CompileResult:
    """
    价格序列 → 结构对象

    完整编译流程：极值 → 段 → 段合并 → 区 → 循环 → 结构 → 丛
    """
    if config is None:
        config = CompilerConfig()

    if not bars:
        return CompileResult(
            bars_count=0, pivots=[], segments=[], zones=[],
            cycles=[], structures=[], bundles=[], config=config,
        )

    # 3.1 极值提取
    pivots = extract_pivots(
        bars,
        min_amplitude=config.min_amplitude,
        min_duration=config.min_duration,
        noise_filter=config.noise_filter,
        use_log=config.use_log_price,
        volume_weighted=config.volume_weighted,
        volume_boost=config.volume_boost,
        adaptive=config.adaptive_pivots,
        fractal_threshold=config.fractal_threshold,
    )

    # 3.2 段生成 + 微段合并
    segments = build_segments(pivots)
    segments = merge_micro_segments(segments, config.min_segment_delta_pct)

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

    # ── V1.6 P0+: 叙事 + 守恒 + 运动 + 投影觉知 ──
    # ── V1.6 P1: 升级为 SystemState（结构×运动 + 差异分层 + 错觉检测）──
    # 优化：为每个结构预过滤相关 bars，避免 build_system_state 内部重复遍历全量 bars
    system_states = []
    for st in structures:
        st.narrative_context = infer_narrative_context(st)
        # 预过滤：只传入结构时间窗口 ± 30天 的 bars（减少 compute_fear_index 等的遍历量）
        if st.t_start and st.t_end:
            from datetime import timedelta
            margin = timedelta(days=30)
            window_bars = [b for b in bars if st.t_start - margin <= b.timestamp <= st.t_end + margin]
        else:
            window_bars = bars
        ss = build_system_state(st, window_bars)
        system_states.append(ss)

    # 3.5 丛识别
    bundles = detect_bundles(
        structures,
        speed_tol=config.bundle_speed_tol,
        time_tol=config.bundle_time_tol,
    )

    # 3.6 知识图谱构建（V1.6 P2）
    graph = StructureGraph.from_structures(structures)

    return CompileResult(
        bars_count=len(bars),
        pivots=pivots,
        segments=segments,
        zones=zones,
        cycles=cycles,
        structures=structures,
        bundles=bundles,
        config=config,
        system_states=system_states,
        graph=graph,
    )
