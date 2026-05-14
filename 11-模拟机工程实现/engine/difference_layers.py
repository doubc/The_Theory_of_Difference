"""
difference_layers.py — 差异分层量化 (D0-D4)

基于差异论V1.7的差异分层体系：
- D0: 原初可区分性 — 状态是否有差异（最低条件）
- D1: 结构差异 — 聚簇和层级化形成的稳定结构
- D2: 分布差异 — 差异在空间和时间上的不均匀分布
- D3: 语义差异 — 差异被命名、范畴化（当前工程无直接对应，留接口）
- D4: 事件差异 — 差异的突然集中或释放（底图事件）
"""

from dataclasses import dataclass
from typing import List, Optional
import torch


@dataclass
class DifferenceLayerReport:
    """各层差异的量化报告"""
    d0_distinguishability: float = 0.0   # 原初可区分性 [0,1]
    d1_structural: float = 0.0           # 结构差异 [0,1]
    d2_distributional: float = 0.0       # 分布差异 [0,1]
    d3_semantic: float = 0.0             # 语义差异 [0,1]（占位）
    d4_event: float = 0.0                # 事件差异 [0,1]

    @property
    def total_difference_density(self) -> float:
        """综合差异密度 K_t（V1.7定义）"""
        return (self.d0_distinguishability + self.d1_structural +
                self.d2_distributional + self.d4_event) / 4.0

    @property
    def is_critical(self) -> bool:
        """是否达到临界差异密度（可能触发制度相变）"""
        return self.total_difference_density > 0.7

    def __str__(self) -> str:
        return (
            f"D0(原初): {self.d0_distinguishability:.3f} | "
            f"D1(结构): {self.d1_structural:.3f} | "
            f"D2(分布): {self.d2_distributional:.3f} | "
            f"D3(语义): {self.d3_semantic:.3f} | "
            f"D4(事件): {self.d4_event:.3f} | "
            f"Kt: {self.total_difference_density:.3f}"
        )


class DifferenceLayerAnalyzer:
    """差异分层分析器"""

    def __init__(self, n_bins: int = 10):
        self.n_bins = n_bins

    def analyze(self, state: torch.Tensor,
                history: Optional[List[torch.Tensor]] = None,
                structures: Optional[List] = None) -> DifferenceLayerReport:
        """分析当前状态的各层差异"""
        d0 = self._d0_distinguishability(state)
        d1 = self._d1_structural(state, structures)
        d2 = self._d2_distributional(state)
        d4 = self._d4_event(state, history)

        return DifferenceLayerReport(
            d0_distinguishability=d0,
            d1_structural=d1,
            d2_distributional=d2,
            d3_semantic=0.0,  # 占位
            d4_event=d4,
        )

    def _d0_distinguishability(self, state: torch.Tensor) -> float:
        """D0: 原初可区分性
        衡量：状态中有多少可区分的不同值
        完全均匀（所有值相同）→ 0
        完全随机（所有值不同）→ 1
        """
        unique = torch.unique(state)
        total = state.numel()
        if total == 0:
            return 0.0
        return float(min(1.0, unique.numel() / min(total, self.n_bins * 2)))

    def _d1_structural(self, state: torch.Tensor,
                        structures: Optional[List] = None) -> float:
        """D1: 结构差异
        衡量：检测到的稳定结构覆盖了多少状态空间
        无结构 → 0
        全覆盖 → 1
        """
        if structures is None or len(structures) == 0:
            # 无结构信息：用空间自相关代理
            if state.dim() < 2:
                return 0.0
            # 计算相邻像素的相关性（高相关=有结构）
            s = state.float()
            if s.dim() == 4:
                s = s[0, 0]
            if s.shape[0] < 2 or s.shape[1] < 2:
                return 0.0
            h_diff = (s[1:, :] - s[:-1, :]).abs().mean().item()
            v_diff = (s[:, 1:] - s[:, :-1]).abs().mean().item()
            avg_diff = (h_diff + v_diff) / 2.0
            # 差异适中=有结构，差异极小=均匀，差异极大=噪声
            return max(0.0, 1.0 - abs(avg_diff - 0.3) * 3.0)

        # 有结构信息：计算结构覆盖率
        total_area = state.numel()
        covered = sum(s.mask.sum().item() for s in structures)
        return min(1.0, covered / max(1, total_area))

    def _d2_distributional(self, state: torch.Tensor) -> float:
        """D2: 分布差异
        衡量：差异在空间上的不均匀程度
        均匀分布 → 0
        高度不均匀 → 1
        """
        s = state.float().flatten()
        if s.numel() < 2:
            return 0.0
        # 用变异系数（CV）衡量不均匀程度
        mean = s.mean().item()
        std = s.std().item()
        if mean < 1e-6:
            return 0.0
        cv = std / (mean + 1e-6)
        return float(min(1.0, cv / 2.0))

    def _d4_event(self, state: torch.Tensor,
                   history: Optional[List[torch.Tensor]] = None) -> float:
        """D4: 事件差异
        衡量：最近是否发生了底图事件（差异的突然集中或释放）
        平稳 → 0
        突变 → 1
        """
        if history is None or len(history) < 2:
            return 0.0
        # 最近两步的变化幅度
        recent_delta = (history[-1] - history[-2]).abs().mean().item()
        # 历史平均变化幅度
        if len(history) >= 4:
            avg_delta = sum(
                (history[i+1] - history[i]).abs().mean().item()
                for i in range(max(0, len(history)-8), len(history)-1)
            ) / min(len(history)-1, 7)
            if avg_delta < 1e-6:
                return 0.5 if recent_delta > 0.01 else 0.0
            ratio = recent_delta / (avg_delta + 1e-6)
            return float(min(1.0, max(0.0, (ratio - 1.0) / 2.0)))
        return float(min(1.0, recent_delta * 5.0))
