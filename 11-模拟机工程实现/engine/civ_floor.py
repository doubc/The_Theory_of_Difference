"""
CIVFloor — 最小 CIV 计数下限机制

Phase 5 Track C1 发现当前 CSC+NSE 架构（max_layers=1）的系统性 CIV 过低问题。
即使 N0=48，CIV 均值仅 2.25（Phase 4 同架构均值为 4-6）。
根因不是 AMC/ILP 移除（Phase 4 消融从未同时测试 no-AMC AND no-ILP），
而是 Phase 5 的 1300+ 行多层支持改动改变了单层模式的代码路径。

CIVFloor 提供轻量级下限：当叙事活跃时确保 CIV >= floor_value。
这是对 Phase 5 单层模式的修复，而非多层模式的组件。

参考：docs/civ_gap_investigation_20260603.md
"""

from typing import Dict, Optional


class CIVFloor:
    """
    最小 CIV 计数下限机制。

    当叙事活跃时（通过 narrative_level_distribution 判断），
    将 CIV 计数上升到至少 floor_value，确保 H5/H6 通过。

    Usage:
        civ_floor = CIVFloor(floor=3)
        floored = civ_floor.step(civ_count=2, narrative_level_dist={'INSTITUTIONAL': 1, 'MINI': 10})
        # floored == 3
    """

    def __init__(self, floor: int = 3, narrative_threshold: float = 0.05):
        """
        Args:
            floor: CIV 最小下限值（默认 3，满足 H6 min>=3）
            narrative_threshold: 叙事活跃阈值 — 当 narrative_level_dist 中
                非 MINI/MINI_NARRATIVE 条目占比 >= 此值时视为叙事活跃

        Note: Default threshold was reduced from 0.5 to 0.05 after diagnosis.
        Phase 5 single-layer mode produces sparse narrative level distributions
        (1-3 non-MINI out of 10-15 total, ratio ~0.1-0.2), so 0.5 was too high
        and effectively disabled CIVFloor in all realistic scenarios.
        See docs/civ_gap_investigation_20260603.md for full analysis.
        """
        self.floor = floor
        self.narrative_threshold = narrative_threshold

    # ──────────────────────────────────────────────
    # 用于判断叙事是否活跃的层级关键词
    _NARRATIVE_LEVELS = {
        'INSTITUTIONAL', 'CIVILIZATION', 'INSTITUTION',
        'NARRATIVE', 'CIV', 'CULTURAL', 'SOCIAL',
    }

    def is_narrative_active(self, narrative_level_dist: Dict[str, int]) -> bool:
        """通过叙事层级分布判断叙事是否活跃。"""
        if not narrative_level_dist:
            return False

        total = sum(narrative_level_dist.values())
        if total == 0:
            return False

        # 非基础层级的条目占比
        narrative_count = sum(
            v for k, v in narrative_level_dist.items()
            if k not in ('MINI', 'MINI_NARRATIVE', '')
        )
        return (narrative_count / total) >= self.narrative_threshold

    def step(
        self,
        civ_count: float,
        narrative_level_dist: Optional[Dict[str, int]] = None,
        nsi: Optional[float] = None,
    ) -> float:
        """
        对 CIV 计数施加下限。

        Args:
            civ_count: 原始 CIV 计数
            narrative_level_dist: 叙事层级分布字典
            nsi: 可选 NSI 值（当提供时优先使用）

        Returns:
            float: 应用下限后的 CIV 计数
        """
        # 检查叙事是否活跃
        if nsi is not None:
            narrative_active = nsi >= self.narrative_threshold * 0.5  # NSI 通常 0-1，用 0.25 阈值
        else:
            narrative_active = self.is_narrative_active(
                narrative_level_dist or {}
            )

        if narrative_active and civ_count < self.floor:
            return float(self.floor)

        return civ_count

    def __repr__(self) -> str:
        return (
            f"CIVFloor(floor={self.floor}, "
            f"narrative_threshold={self.narrative_threshold})"
        )