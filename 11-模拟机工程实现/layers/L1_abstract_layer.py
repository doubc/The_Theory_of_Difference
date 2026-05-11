"""
L1_abstract_layer.py — L1 抽象层

由 L0 稳定结构粗粒化而来。
对应《差异即世界》中"层级"机制：结构获得递归展开的能力。
"""

from typing import List, Dict, Optional
import torch
import torch.nn.functional as F

from .layer_base import LayerBase
from .coarse_grain import (
    coarse_grain_state,
    coarse_grain_measure_invariant,
    compute_block_boundary_map,
)


class L1AbstractLayer(LayerBase):
    """L1 抽象层：由 L0 粗粒化而来

    状态空间：L0 稳定区域分块均值
    守恒量：被标记块的总激活量
    稳定性：块间差异 + 时间稳定性
    """

    name = "L1_abstract"
    stability_window = 8  # L1 的稳定性窗口更短

    def __init__(
        self,
        block_size: int = 4,
        l1_shape: Optional[tuple] = None,
        source_mask: Optional[torch.Tensor] = None,
    ):
        self.block_size = block_size
        self.l1_shape = l1_shape
        self.source_mask = source_mask
        self._axiom_weights = {
            "A2_discreteness": 1.0,
            "A4_min_change": 1.0,
            "A5_conservation": 1.5,
            "A7_stability": 2.0,
        }

    def initial_state(self, batch_size: int = 1) -> torch.Tensor:
        """生成 L1 初始状态

        如果有 source_mask，从随机 L0 状态粗粒化得到。
        否则返回零状态。
        """
        if self.l1_shape is not None:
            b, c, h, w = batch_size, 1, self.l1_shape[0], self.l1_shape[1]
        elif self.source_mask is not None:
            mask = self.source_mask
            if mask.dim() == 2:
                h, w = mask.shape
            else:
                h, w = mask.shape[-2:]
            b, c = batch_size, 1
            h = h // self.block_size
            w = w // self.block_size
        else:
            b, c, h, w = batch_size, 1, 8, 8

        return torch.rand(b, c, h, w) * 0.5

    def project_state(self, raw_state: torch.Tensor,
                      mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """投影到 [0, 1] 范围"""
        state = raw_state.clamp(0.0, 1.0)
        if mask is not None:
            state = state * mask
        return state

    def valid_state(self, state: torch.Tensor) -> bool:
        """检查状态合法性"""
        if torch.isnan(state).any() or torch.isinf(state).any():
            return False
        if state.min() < -0.01 or state.max() > 1.01:
            return False
        return True

    def measure_difference(self, state: torch.Tensor) -> torch.Tensor:
        """L1 差异度量：块间差异"""
        parts = []
        if state.shape[-1] > 1:
            dx = (state[:, :, :, 1:] - state[:, :, :, :-1]).abs()
            dx = F.pad(dx, (0, 1, 0, 0))
            parts.append(dx)
        if state.shape[-2] > 1:
            dy = (state[:, :, 1:, :] - state[:, :, :-1, :]).abs()
            dy = F.pad(dy, (0, 0, 0, 1))
            parts.append(dy)
        if not parts:
            return torch.zeros_like(state)
        return sum(parts) / len(parts)

    def measure_invariant(self, state: torch.Tensor) -> torch.Tensor:
        """L1 守恒量：被标记块的总激活量"""
        if self.source_mask is not None:
            mask = self.source_mask.float()
            if mask.dim() == 2:
                mask = mask.unsqueeze(0).unsqueeze(0)
            # 粗粒化 mask
            _, l1_mask = coarse_grain_state(
                torch.ones_like(state) if state.dim() == 4 else state,
                mask.expand_as(state) if state.dim() == 4 else mask,
                self.block_size,
            )
            return coarse_grain_measure_invariant(state, l1_mask)
        return state.sum(dim=(-1, -2), keepdim=True)

    def transition_cost(self, state: torch.Tensor,
                        next_state: torch.Tensor) -> torch.Tensor:
        """A4：转换成本"""
        return ((next_state - state) ** 2).mean(dim=(-1, -2), keepdim=True)

    def discreteness_violation(self, state: torch.Tensor) -> torch.Tensor:
        """A2：L1 允许连续值，离散性约束较弱"""
        # L1 是连续值层，离散性约束 = 鼓励值聚集
        return (state * (1 - state)).mean()

    def locality_violation(self, state: torch.Tensor,
                           next_state: torch.Tensor) -> torch.Tensor:
        """A3：局域性违背"""
        diff = self.measure_difference(next_state - state)
        return (diff ** 2).mean()

    def inject_difference(self, state: torch.Tensor,
                          source_strength: float = 1.0) -> torch.Tensor:
        """A1：在边界块注入差异"""
        out = state.clone()
        # 在左侧边界注入
        if out.shape[-1] > 0:
            out[:, :, :, 0] = out[:, :, :, 0] + source_strength * 0.1
        return out.clamp(0.0, 1.0)

    def absorb_difference(self, state: torch.Tensor,
                          sink_strength: float = 1.0) -> torch.Tensor:
        """A8：在右侧边界吸收差异"""
        out = state.clone()
        if out.shape[-1] > 0:
            out[:, :, :, -1] = out[:, :, :, -1] - sink_strength * 0.1
        return out.clamp(0.0, 1.0)

    def stability_violation(self, window: List[torch.Tensor]) -> torch.Tensor:
        """A7：稳定性违背"""
        if len(window) < 2:
            return torch.tensor(0.0)
        stacked = torch.stack(window[-self.stability_window:], dim=0)
        return stacked.std(dim=0).mean()

    def detect_stable_structures(self, history: List[torch.Tensor]) -> list:
        """L1 稳定结构检测：块级稳定性"""
        from acl.axiom_base import StableStructure

        if len(history) < self.stability_window:
            return []

        window = history[-self.stability_window:]
        stacked = torch.stack(window, dim=0)  # (T, B, C, H', W')

        temporal_std = stacked.std(dim=0)
        temporal_mean = stacked.mean(dim=0)

        # 稳定块：标准差小，非极端值
        stable_mask = (temporal_std < 0.15) & (temporal_mean > 0.1) & (temporal_mean < 0.9)

        if not stable_mask.any():
            return []

        boundary_map = compute_block_boundary_map(stable_mask.float())
        turnover = float(temporal_std[stable_mask].mean())

        struct = StableStructure(
            mask=stable_mask,
            lifetime=self.stability_window,
            pattern_signature=temporal_mean[stable_mask].mean(),
            boundary_map=boundary_map,
            material_turnover=turnover,
            source_layer=self.name,
        )
        return [struct]

    def coarse_grain(self, structures: list) -> Optional['L1AbstractLayer']:
        """L1 → L2 粗粒化（暂未实现）"""
        return None

    def measure_ascent_pressure(self, history: List[torch.Tensor],
                                structures: list) -> float:
        """升维压力：基于稳定结构的守恒残差"""
        if not structures:
            return 0.0
        turnover = sum(s.material_turnover for s in structures) / len(structures)
        return float(1.0 / (turnover + 1e-6))

    def get_axiom_weight(self, axiom_name: str) -> float:
        """获取公理权重"""
        return self._axiom_weights.get(axiom_name, 1.0)
