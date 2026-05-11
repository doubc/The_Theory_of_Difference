"""
L0_binary_lattice.py — 第一层：二元格点

最小可运行的世界层。
状态空间：batch × channel × H × W，值域 [0, 1]
源端（左边界注入）、汇端（右边界吸收）
"""

from typing import List, Optional
import torch
import torch.nn.functional as F
from layers.layer_base import LayerBase
from acl.axiom_base import StableStructure


class L0BinaryLattice(LayerBase):
    name = "L0_binary_lattice"

    def __init__(self, shape=(4, 4), device="cpu",
                 source_side="left", sink_side="right"):
        self.shape = shape
        self.device = device
        self.source_side = source_side
        self.sink_side = sink_side
        self.stability_window = 16

        # A7 子指标阈值
        self.min_activity = 0.05
        self.max_activity = 0.95

        # 公理权重
        self._axiom_weights = {
            "A2_discrete_encoding": 1.0,
            "A3_locality": 1.0,
            "A4_minimal_variation": 0.5,
            "A5_conservation": 1.0,
            "A7_stability": 0.8,
        }

    def get_axiom_weight(self, axiom_name: str) -> float:
        return self._axiom_weights.get(axiom_name, 0.0)

    # --- 状态空间 ---

    def initial_state(self, batch_size: int = 1) -> torch.Tensor:
        return (torch.rand(batch_size, 1, *self.shape, device=self.device) < 0.3).float()

    def project_state(self, raw_state: torch.Tensor,
                      mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        if mask is not None:
            result = raw_state.clamp(0.0, 1.0)
            return result
        return raw_state.clamp(0.0, 1.0)

    def hard_project(self, raw_state: torch.Tensor) -> torch.Tensor:
        return (raw_state > 0.5).float()

    def valid_state(self, state: torch.Tensor) -> bool:
        return state.shape[-2:] == self.shape

    # --- 差异度量 ---

    def measure_difference(self, state: torch.Tensor) -> torch.Tensor:
        """测量相邻格点的差异值。

        始终返回与输入同 shape 的差异场。
        对 1D (H=1)，只计算水平方向差异；对双方向，计算 x/y 平均。
        边界位置用最近邻填充。
        """
        b, c, h, w = state.shape
        has_x = w > 1
        has_y = h > 1

        if not has_x and not has_y:
            return torch.zeros_like(state)

        # 只有一个方向：直接 pad 回原尺寸
        if has_x and not has_y:
            # dx shape: (b, c, h, w-1)，在最后一维 pad 1 个 0
            dx = (state[:, :, :, 1:] - state[:, :, :, :-1]).abs()
            return F.pad(dx, (0, 1))
        if has_y and not has_x:
            # dy shape: (b, c, h-1, w)，在倒数第二维 pad 1 个 0
            dy = (state[:, :, 1:, :] - state[:, :, :-1, :]).abs()
            return F.pad(dy, (0, 0, 0, 1))

        # 两个方向都有：分别计算后在各自缺失维 pad，再平均
        dx = (state[:, :, :, 1:] - state[:, :, :, :-1]).abs()  # (b, c, h, w-1)
        dy = (state[:, :, 1:, :] - state[:, :, :-1, :]).abs()  # (b, c, h-1, w)

        # dx 水平方向少一列，补回 → (b, c, h, w)
        dx_full = F.pad(dx, (0, 1))
        # dy 垂直方向少一行，补回 → (b, c, h, w)
        dy_full = F.pad(dy, (0, 0, 0, 1))

        return (dx_full + dy_full) / 2.0

    def measure_invariant(self, state: torch.Tensor) -> torch.Tensor:
        """守恒量：总激活量"""
        return state.sum(dim=(-1, -2), keepdim=True)

    def transition_cost(self, state: torch.Tensor,
                        next_state: torch.Tensor) -> torch.Tensor:
        delta = next_state - state
        return (delta ** 2).mean()

    def discreteness_violation(self, state: torch.Tensor) -> torch.Tensor:
        """距离 0/1 的偏离：p*(1-p) 在 p=0 或 1 时为 0"""
        return (state * (1.0 - state)).mean()

    def locality_violation(self, state: torch.Tensor,
                           next_state: torch.Tensor) -> torch.Tensor:
        """局域性由 CNN 结构保证，返回 0"""
        return torch.tensor(0.0, device=state.device)

    # --- 差异源与汇 ---

    def inject_difference(self, state: torch.Tensor,
                          source_strength: float = 1.0) -> torch.Tensor:
        """A1：在源端（左边界）注入差异。

        注入模式：在左边界以一定概率设置高值，
        创建从左到右的差异梯度。

        注意：mask 维度完全基于输入 state 推导，
        不依赖 self.shape，避免 batch/channel/shape 解耦后失配。
        """
        result = state.clone()
        if self.source_side == "left":
            b, c, h, w = state.shape
            # 在左边界注入，宽度至少 1，至多 3
            width = min(3, max(1, w // 4))
            mask = torch.rand(b, c, h, width,
                              device=state.device) < 0.08
            result[:, :, :, :width] = torch.where(
                mask,
                torch.clamp(result[:, :, :, :width] + 0.5 * source_strength, 0.0, 1.0),
                result[:, :, :, :width]
            )
        return result.clamp(0.0, 1.0)

    def absorb_difference(self, state: torch.Tensor,
                          sink_strength: float = 1.0) -> torch.Tensor:
        """A8：在汇端（右边界）吸收差异。

        吸收模式：在右边界附近衰减，
        创建差异汇。

        注意：width 基于输入 state 推导，与 inject_difference 一致。
        """
        result = state.clone()
        if self.sink_side == "right":
            _, _, _, w = state.shape
            width = min(3, max(1, w // 4))
            result[:, :, :, -width:] = result[:, :, :, -width:] * (1.0 - sink_strength * 0.15)
        return result.clamp(0.0, 1.0)

    def apply_boundary_flow(self, state: torch.Tensor,
                            source_strength: float = 1.0,
                            sink_strength: float = 1.0) -> tuple:
        """应用源/汇边界条件，同时返回流量信息。

        用于 A5 开放系统流量平衡：守恒量变化 = 注入量 - 吸收量。

        Returns:
            (next_state, injected_total, absorbed_total)
        """
        # 注入前的总量
        q_before = state.sum(dim=(-1, -2), keepdim=True)

        # 注入源
        after_source = self.inject_difference(state, source_strength)
        # 吸收汇
        after_sink = self.absorb_difference(after_source, sink_strength)

        # 计算净流量
        q_after = after_sink.sum(dim=(-1, -2), keepdim=True)
        injected = (after_source.sum(dim=(-1, -2), keepdim=True) - q_before).clamp(min=0.0)
        absorbed = (q_before + injected - q_after).clamp(min=0.0)

        return after_sink.clamp(0.0, 1.0), injected, absorbed

    # --- 稳定性 ---

    def stability_violation(self, window: List[torch.Tensor]) -> torch.Tensor:
        states = torch.stack(window, dim=0)

        activity = states.mean()
        collapse = torch.relu(torch.tensor(self.min_activity, device=states.device) - activity)
        explosion = torch.relu(activity - torch.tensor(self.max_activity, device=states.device))

        diffs = (states[1:] - states[:-1]).abs().mean(dim=0)
        drift = diffs.mean()

        return collapse + explosion + drift

    def detect_stable_structures(self,
                                 history: List[torch.Tensor]) -> List[StableStructure]:
        """最小版本：检测持续存在的局部区域"""
        if len(history) < self.stability_window:
            return []

        window = history[-self.stability_window:]
        states = torch.stack(window, dim=0)

        # 计算每个位置的时间稳定性
        temporal_std = states.std(dim=0)
        temporal_mean = states.mean(dim=0)

        # 稳定区域：标准差小，且不是全 0 或全 1
        stable_mask = (temporal_std < 0.1) & \
                      (temporal_mean > 0.1) & \
                      (temporal_mean < 0.9)

        if not stable_mask.any():
            return []

        # 简单返回整个稳定区域作为一个结构
        structure = StableStructure(
            mask=stable_mask,
            lifetime=self.stability_window,
            pattern_signature=temporal_mean[stable_mask].mean().unsqueeze(0),
            boundary_map=stable_mask.float(),
            material_turnover=temporal_std.mean().item(),
            source_layer=self.name,
        )
        return [structure]

    # --- 粗粒化 ---

    def upscale_from(self, old_layer, old_state):
        """用 nearest-neighbor 插值将旧层状态适配到本层尺寸。

        选择 nearest（而非 bilinear）是因为二元格点的状态值应保持 0/1，
        不应该出现灰度插值。
        """
        if self.shape == old_layer.shape:
            return old_state.clone()
        return F.interpolate(old_state, size=self.shape, mode='nearest')

    def coarse_grain(self, structures: List) -> Optional[LayerBase]:
        """最小版本：固定 2×2 block 压缩"""
        if not structures:
            return None
        # TODO: 实现真正的粗粒化
        return None

    def measure_ascent_pressure(self, history: List[torch.Tensor],
                                 structures: List) -> float:
        """A5+A9：度量升维压力"""
        if len(history) < 2 or not structures:
            return 0.0

        # 守恒残差
        q1 = self.measure_invariant(history[-2])
        q2 = self.measure_invariant(history[-1])
        residual = ((q2 - q1) ** 2).mean().item()

        # 结构密度
        density = len(structures) / max(1, self.shape[0] * self.shape[1])

        # 压力 = 残差 × 结构密度
        return residual * density
