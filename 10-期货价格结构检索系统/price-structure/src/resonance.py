"""
跨品种信号共振检测 — P0-1

当多个同板块品种同时出现 A/B 层结构时，检测板块级别的信号共振。

核心逻辑：
1. 全市场编译 → 质量分层
2. 按板块分组（有色金属、黑色系、能化、农产品等）
3. 计算板块共振评分：同板块内 A/B 层结构占比 × 方向一致性
4. 输出共振信号：板块方向、共振强度、参与品种

共振评分 = 板块质量密度 × 方向一致性 × Zone 聚集度

用法：
    from src.resonance import detect_resonance, ResonanceDetector

    detector = ResonanceDetector()
    signals = detector.detect(compile_results)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict

from src.models import Structure, SystemState
from src.quality import assess_quality, stratify_structures, QualityTier


# ─── 板块分类 ─────────────────────────────────────────────

EXCHANGE_GROUPS = {
    # 有色金属
    "有色金属": ["CU0", "AL0", "ZN0", "PB0", "NI0", "SN0"],
    # 贵金属
    "贵金属": ["AU0", "AG0"],
    # 黑色系
    "黑色系": ["RB0", "HC0", "SS0", "I0", "J0", "JM0"],
    # 能化
    "能化": ["BU0", "RU0", "FU0", "SC0", "L0", "V0", "PP0", "EG0", "EB0", "PG0", "MA0", "TA0"],
    # 农产品
    "农产品": ["M0", "Y0", "P0", "A0", "B0", "C0", "CS0", "SR0", "CF0", "OI0", "RM0"],
    # 建材
    "建材": ["FG0", "SA0", "UR0", "ZC0"],
    # 新能源
    "新能源": ["LC0", "SI0"],
}


def get_sector(symbol: str) -> str:
    """品种 → 板块"""
    sym = symbol.upper().replace("000", "0")  # CU000 → CU0
    for sector, symbols in EXCHANGE_GROUPS.items():
        if sym in [s.upper() for s in symbols]:
            return sector
    return "其他"


def get_sector_peers(symbol: str) -> list[str]:
    """获取同板块品种"""
    sector = get_sector(symbol)
    return [s for s in EXCHANGE_GROUPS.get(sector, []) if s.upper() != symbol.upper()]


# ─── 数据结构 ─────────────────────────────────────────────

@dataclass
class SectorSignal:
    """单个板块的共振信号"""
    sector: str                     # 板块名称
    direction: str                  # "bullish" / "bearish" / "mixed"
    resonance_score: float          # 共振强度 [0, 1]
    quality_density: float          # A/B 层结构占比
    direction_consistency: float    # 方向一致性
    zone_clustering: float          # Zone 聚集度
    participating: list[dict]       # 参与品种 [{symbol, zone, tier, direction, score}]
    top_structure: dict | None      # 最强结构摘要

    @property
    def is_strong(self) -> bool:
        return self.resonance_score > 0.6

    @property
    def direction_label(self) -> str:
        labels = {"bullish": "🔴 看涨共振", "bearish": "🟢 看跌共振", "mixed": "🟡 方向混合"}
        return labels.get(self.direction, "未知")

    def summary(self) -> str:
        parts = [
            f"板块: {self.sector} · {self.direction_label}",
            f"共振强度: {self.resonance_score:.0%}",
            f"参与品种: {len(self.participating)} 个",
        ]
        for p in self.participating[:5]:
            parts.append(f"  {p['symbol']}: Zone {p['zone']:.0f} · {p['tier']}层 · {p['direction']}")
        return "\n".join(parts)


@dataclass
class ResonanceResult:
    """全市场共振检测结果"""
    signals: list[SectorSignal]
    timestamp: str = ""
    total_structures: int = 0
    total_ab: int = 0

    @property
    def strong_signals(self) -> list[SectorSignal]:
        return [s for s in self.signals if s.is_strong]

    def summary(self) -> str:
        lines = [f"共振检测: {len(self.signals)} 个板块有信号, {len(self.strong_signals)} 个强共振"]
        for s in sorted(self.signals, key=lambda x: x.resonance_score, reverse=True):
            lines.append(s.summary())
        return "\n".join(lines)


# ─── 共振检测器 ──────────────────────────────────────────

class ResonanceDetector:
    """
    跨品种信号共振检测器

    输入：全市场编译结果（含质量分层）
    输出：板块共振信号列表
    """

    def __init__(
        self,
        min_quality_tier: str = "B",    # 最低纳入共振的层级
        min_sector_size: int = 2,        # 板块最少品种数
    ):
        self.min_quality_tier = min_quality_tier
        self.min_sector_size = min_sector_size

    def detect(
        self,
        compile_results: dict[str, tuple[list[Structure], list[SystemState] | None]],
    ) -> ResonanceResult:
        """
        全市场共振检测

        Args:
            compile_results: {symbol: (structures, system_states)}

        Returns:
            ResonanceResult
        """
        # 1. 按板块分组 + 质量过滤
        sector_data: dict[str, list[dict]] = defaultdict(list)
        total_structures = 0
        total_ab = 0

        for symbol, (structures, sys_states) in compile_results.items():
            sector = get_sector(symbol)
            total_structures += len(structures)

            for i, s in enumerate(structures):
                ss = sys_states[i] if sys_states and i < len(sys_states) else None
                qa = assess_quality(s, ss)

                # 只纳入 A/B 层
                if qa.tier.value not in ("A", "B"):
                    continue
                total_ab += 1

                # 方向判断
                direction = self._infer_direction(s)

                sector_data[sector].append({
                    "symbol": symbol,
                    "structure": s,
                    "tier": qa.tier.value,
                    "quality_score": qa.score,
                    "direction": direction,
                    "zone_center": s.zone.price_center,
                    "zone_bw": s.zone.bandwidth,
                    "cycle_count": s.cycle_count,
                    "avg_speed_ratio": s.avg_speed_ratio,
                })

        # 2. 计算各板块共振
        signals = []
        for sector, items in sector_data.items():
            if len(items) < self.min_sector_size:
                continue

            signal = self._compute_sector_resonance(sector, items)
            if signal:
                signals.append(signal)

        # 按共振强度排序
        signals.sort(key=lambda s: s.resonance_score, reverse=True)

        return ResonanceResult(
            signals=signals,
            total_structures=total_structures,
            total_ab=total_ab,
        )

    def _infer_direction(self, s: Structure) -> str:
        """从结构推断方向"""
        if not s.cycles:
            return "unknown"

        # 多数 cycle 的方向
        ups = sum(1 for c in s.cycles if c.entry.direction.value > 0)
        downs = sum(1 for c in s.cycles if c.entry.direction.value < 0)

        if ups > downs * 1.5:
            return "bullish"
        elif downs > ups * 1.5:
            return "bearish"
        else:
            return "mixed"

    def _compute_sector_resonance(self, sector: str, items: list[dict]) -> SectorSignal | None:
        """计算单个板块的共振信号"""
        if not items:
            return None

        n = len(items)

        # 1. 质量密度 = A/B 层品种数 / 板块总品种数
        symbols_in_sector = set(i["symbol"] for i in items)
        sector_total = len(EXCHANGE_GROUPS.get(sector, []))
        quality_density = len(symbols_in_sector) / max(sector_total, 1)

        # 2. 方向一致性 = 主要方向占比
        directions = [i["direction"] for i in items]
        bullish = sum(1 for d in directions if d == "bullish")
        bearish = sum(1 for d in directions if d == "bearish")
        dominant = max(bullish, bearish)
        direction_consistency = dominant / n if n > 0 else 0

        if bullish > bearish * 1.3:
            direction = "bullish"
        elif bearish > bullish * 1.3:
            direction = "bearish"
        else:
            direction = "mixed"

        # 3. Zone 聚集度 = Zone 中心的变异系数（越小越聚集）
        zone_centers = [i["zone_center"] for i in items]
        if len(zone_centers) >= 2:
            mean_z = sum(zone_centers) / len(zone_centers)
            if mean_z > 0:
                std_z = (sum((z - mean_z) ** 2 for z in zone_centers) / len(zone_centers)) ** 0.5
                cv = std_z / mean_z
                # CV 小 → 聚集度高 → 分数高
                zone_clustering = max(0, 1 - cv * 10)  # CV=0.1 → score=0
            else:
                zone_clustering = 0
        else:
            zone_clustering = 0.5

        # 4. 综合共振评分
        resonance_score = (
            0.35 * quality_density +
            0.35 * direction_consistency +
            0.30 * zone_clustering
        )

        # 参与品种（按质量分排序）
        participating = sorted(
            [
                {
                    "symbol": i["symbol"],
                    "zone": i["zone_center"],
                    "tier": i["tier"],
                    "direction": i["direction"],
                    "score": i["quality_score"],
                }
                for i in items
            ],
            key=lambda x: x["score"],
            reverse=True,
        )

        # 最强结构
        top = max(items, key=lambda x: x["quality_score"])
        top_structure = {
            "symbol": top["symbol"],
            "zone": top["zone_center"],
            "cycles": top["cycle_count"],
            "speed_ratio": top["avg_speed_ratio"],
        }

        return SectorSignal(
            sector=sector,
            direction=direction,
            resonance_score=resonance_score,
            quality_density=quality_density,
            direction_consistency=direction_consistency,
            zone_clustering=zone_clustering,
            participating=participating,
            top_structure=top_structure,
        )
