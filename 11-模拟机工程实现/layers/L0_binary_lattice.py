"""
L0_binary_lattice.py — 第一层：二元格点

最小可运行的世界层。
状态空间：batch × channel × H × W，值域 [0, 1]
源端（左边界注入）、汇端（右边界吸收）
"""

from typing import List, Optional, Dict, Tuple
import torch
import torch.nn.functional as F
import numpy as np
from layers.layer_base import LayerBase
from acl.axiom_base import StableStructure


class L0BinaryLattice(LayerBase):
    name = "L0_binary_lattice"

    # 用于升维压力累积积分的滑动窗口
    _ascent_window_size: int = 16   # 与 stability_window 保持一致
    _residual_buffer: list          # 缓存最近 N 步的守恒残差，用于累积积分

    # v2 结构检测：跨窗口生命周期追踪
    _struct_registry: Dict[int, dict]        # struct_id → {first_seen, last_seen, window_count, pattern_sig}
    _next_struct_id: int                     # 自增 ID
    _prev_labels: Optional[torch.Tensor]     # 上一窗口的连通分量标记（用于匹配）
    _interaction_graph: Dict[Tuple[int,int], int]  # (id_a, id_b) → 共存次数

    def __init__(self, shape=(4, 4), device="cpu",
                 source_side="left", sink_side="right"):
        self.shape = shape
        self.device = device
        self.source_side = source_side
        self.sink_side = sink_side
        self.stability_window = 16
        self._residual_buffer = []  # 重置为空列表，让 __init__ 后自动初始化

        # v2 状态
        self._struct_registry = {}
        self._next_struct_id = 0
        self._prev_labels = None
        self._interaction_graph = {}

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
        """v2：多结构分离 + 跨窗口生命周期追踪

        5项标准：
        1. 时间稳定性：每像素标准差 < 阈值（同 v1）
        2. 空间连通性：连通分量分离多个独立结构
        3. 边界闭合：结构边缘是否完整封闭
        4. 物质更替率：结构形似但格点变动（活结构的定义）
        5. 结构间交互：多结构共存时的竞争/合作

        跨窗口追踪通过 spatial IoU 匹配实现，
        生命周期从首次出现累计到当前窗口。
        """
        if len(history) < self.stability_window:
            return []

        window = history[-self.stability_window:]
        states = torch.stack(window, dim=0)  # (T, B, C, H, W)

        # --- 第1标准：时间稳定性 ---
        temporal_std = states.std(dim=0)
        temporal_mean = states.mean(dim=0)
        active = (temporal_mean >= 0.1) & (temporal_mean <= 0.9)
        stable = temporal_std < 0.1
        stable_mask = (stable & active).squeeze(0).squeeze(0)  # (H, W) bool

        if not stable_mask.any():
            self._prev_labels = None
            return []

        # --- 第2标准：连通分量分离 ---
        components_np = self._flood_fill_labels(
            stable_mask.cpu().numpy().astype(np.uint8)
        )
        num_components = int(components_np.max())

        # --- 跨窗口结构匹配 ---
        # 用连通分量标记与上一窗口的标记做 spatial IoU 匹配
        component_labels = torch.from_numpy(components_np).to(self.device)
        matched_ids = self._match_structures(component_labels, num_components)

        # --- 全局指标：总稳定面积（用于 connectivity_ratio 计算）---
        total_stable_area = sum(
            int((component_labels == (c + 1)).sum().item())
            for c in range(num_components)
        )

        # --- 逐结构计算 ---
        structures = []
        for comp_idx in range(num_components):
            comp_label = comp_idx + 1
            struct_mask = component_labels == comp_label  # (H, W) bool

            if not struct_mask.any():
                continue

            # 生命周期
            struct_id = matched_ids.get(comp_label, self._next_struct_id)
            lifetime = self._update_lifetime(struct_id, struct_mask)

            # 边界检测
            boundary = self._detect_boundary(struct_mask.float())

            # closure 拆分：boundary_closure_score + connectivity_ratio
            # （对应审计报告 Section 3 同名异义修复）
            struct_area = int(struct_mask.sum().item())
            # boundary_closure_score: 边界紧致度，perimeter/area 归一化
            #   → 0=完全闭合（圆最优），越大越开放/碎片化
            boundary_closure_score = self._check_closure(boundary, struct_mask)
            # connectivity_ratio: 本结构占全局稳定区域的比例
            #   → [0,1]，1=独占总面积（单结构主导），越小越分散
            connectivity_ratio = struct_area / max(1, total_stable_area)

            # 物质更替率（仅对匹配到的老结构计算，新结构默认 0）
            if comp_label in matched_ids:
                turnover = self._compute_structure_turnover(
                    struct_mask, states, temporal_mean
                )
            else:
                turnover = 0.0

            # 模式签名（确保 temporal_mean 与 struct_mask 维度一致）
            tm_squeezed = temporal_mean.squeeze(0).squeeze(0)  # (H, W)
            pattern = tm_squeezed[struct_mask].mean().unsqueeze(0)

            structures.append(StableStructure(
                mask=struct_mask,
                lifetime=lifetime,
                pattern_signature=pattern,
                boundary_map=boundary.float(),
                material_turnover=float(turnover),
                source_layer=self.name,
                connectivity_ratio=connectivity_ratio,
                boundary_closure_score=boundary_closure_score,
                source_trace=[{"struct_id": struct_id,
                               "component_size": struct_area}],
            ))

        # --- 第5标准：结构间交互 ---
        self._record_interactions(component_labels, num_components)

        # 更新 registry 中的 prev_label，确保下次窗口可以匹配
        for comp_label, struct_id in matched_ids.items():
            if struct_id in self._struct_registry:
                self._struct_registry[struct_id]["prev_label"] = comp_label

        # 保存当前窗口标记供下次匹配
        self._prev_labels = component_labels

        return structures

    # ========== v2 辅助方法 ==========

    def _flood_fill_labels(self, mask: np.ndarray) -> np.ndarray:
        """8邻域连通分量标记（Python flood-fill，适用于小网格）"""
        labels = np.zeros_like(mask, dtype=np.int32)
        next_label = 1
        h, w = mask.shape

        for r in range(h):
            for c in range(w):
                if mask[r, c] and labels[r, c] == 0:
                    stack = [(r, c)]
                    labels[r, c] = next_label
                    while stack:
                        y, x = stack.pop()
                        for ny, nx in [
                            (y-1, x), (y+1, x), (y, x-1), (y, x+1),
                            (y-1, x-1), (y-1, x+1), (y+1, x-1), (y+1, x+1),
                        ]:
                            if 0 <= ny < h and 0 <= nx < w:
                                if mask[ny, nx] and labels[ny, nx] == 0:
                                    labels[ny, nx] = next_label
                                    stack.append((ny, nx))
                    next_label += 1
        return labels

    def _match_structures(self, current_labels: torch.Tensor,
                          num_components: int) -> Dict[int, int]:
        """用 spatial IoU 将当前窗口的结构匹配到历史结构

        Returns: {comp_label → struct_id}
        新结构分配 self._next_struct_id
        """
        matched = {}
        if self._prev_labels is None or num_components == 0:
            # 第一次检测，全部新建
            for c in range(1, num_components + 1):
                matched[c] = self._next_struct_id
                self._next_struct_id += 1
            return matched

        prev_ids = set(pid.item() for pid in torch.unique(self._prev_labels) if pid > 0)
        taken_ids = set()

        for c in range(1, num_components + 1):
            cur_mask = current_labels == c
            best_iou, best_prev = 0.0, -1

            for pid in prev_ids:
                if pid in taken_ids:
                    continue
                prev_mask = self._prev_labels == pid
                intersection = (cur_mask & prev_mask).sum().item()
                union = (cur_mask | prev_mask).sum().item()
                iou = intersection / max(1, union)
                if iou > best_iou:
                    best_iou = iou
                    best_prev = pid

            # IoU > 0.3 认为同一结构
            if best_iou > 0.3 and best_prev > 0:
                # 找到 prev_label → struct_id 的映射
                for sid, reg in self._struct_registry.items():
                    if reg.get("prev_label") == best_prev:
                        matched[c] = sid
                        taken_ids.add(best_prev)
                        reg["prev_label"] = c  # 更新标记
                        break
                else:
                    # 匹配了但没有 registry 记录，当作新结构
                    matched[c] = self._next_struct_id
                    self._next_struct_id += 1
            else:
                matched[c] = self._next_struct_id
                self._next_struct_id += 1

        return matched

    def _update_lifetime(self, struct_id: int,
                         mask: torch.Tensor) -> int:
        """更新结构生命周期，返回当前窗口数"""
        if struct_id not in self._struct_registry:
            self._struct_registry[struct_id] = {
                "window_count": 0,
                "mask": mask,
                "prev_label": -1,
            }
        self._struct_registry[struct_id]["window_count"] += 1
        self._struct_registry[struct_id]["mask"] = mask
        # 生命周期 = 窗口数 × 窗口大小（步数）
        return self._struct_registry[struct_id]["window_count"] * self.stability_window

    def _detect_boundary(self, struct_mask: torch.Tensor) -> torch.Tensor:
        """梯度法检测结构边界。

        对结构掩码做 4 邻域卷积检测边缘：
        像素是边界当且仅当它在结构内但至少有一个邻居在结构外。
        """
        mask = struct_mask.float().unsqueeze(0).unsqueeze(0)  # (1,1,H,W)
        kernel = torch.tensor(
            [[0., 1., 0.], [1., 0., 1.], [0., 1., 0.]],
            device=mask.device
        ).view(1, 1, 3, 3)

        neighbor_sum = F.conv2d(mask, kernel, padding=1)  # (1,1,H,W)
        # 边界：结构内 + 邻域中有非结构像素
        boundary = (mask > 0) & (neighbor_sum < 4 * mask) & (neighbor_sum > 0)
        return boundary.squeeze(0).squeeze(0)

    def _check_closure(self, boundary: torch.Tensor,
                       struct_mask: torch.Tensor) -> float:
        """闭合度：边界像素数 / 结构面积。值越小越闭合。

        完全闭合的圆形：周长^2/面积 有理论下限，
        这里用简化的边界比例：
        - < 0.3: 封闭良好
        - 0.3-0.6: 部分开放
        - > 0.6: 结构碎片化
        """
        area = struct_mask.sum().item()
        perimeter = boundary.sum().item()
        if area == 0:
            return 0.0
        closure_ratio = perimeter / area
        # 归一化到 [0,1]，0=完全闭合,1=完全开放
        return min(1.0, closure_ratio / 2.0)

    def _compute_structure_turnover(self, struct_mask: torch.Tensor,
                                    states: torch.Tensor,
                                    temporal_mean: torch.Tensor) -> float:
        """物质更替率：结构区域内每步变化的平均速率

        活结构的核心特征：模式持续但物质更换。
        更替率 = mean(|state[t+1] - state[t]|) / mean(state) 对结构区域取均值

        高更替 + 高模式稳定性 = 活结构
        低更替 + 高模式稳定性 = 死结构（冻结）
        """
        # states: (T, B, C, H, W), struct_mask: (H, W)
        mask_expanded = struct_mask.unsqueeze(0).unsqueeze(0).unsqueeze(0)  # (1,1,1,H,W)

        # 提取结构区域的状态时间序列
        struct_states = states[:, :, :, struct_mask]  # (T, B, C, N_pixels)

        if struct_states.shape[-1] == 0:
            return 0.0

        # 每步变化
        diffs = (struct_states[1:] - struct_states[:-1]).abs()  # (T-1, B, C, N_pixels)
        mean_diff = diffs.mean().item()

        # 平均激活度
        mean_activation = struct_states.mean().item()

        if mean_activation < 1e-8:
            return 0.0

        return mean_diff / mean_activation

    def _record_interactions(self, component_labels: torch.Tensor,
                             num_components: int):
        """记录结构间共存关系"""
        comps = list(range(1, num_components + 1))
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                pair = (comps[i], comps[j])
                self._interaction_graph[pair] = \
                    self._interaction_graph.get(pair, 0) + 1

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
        """粗粒化：将 L0 稳定结构映射为 L1 抽象层"""
        if not structures:
            return None

        from .L1_abstract_layer import L1AbstractLayer

        # 取第一个稳定结构的 mask
        struct = structures[0]
        mask = struct.mask

        # 计算粗粒化后的形状
        if mask.dim() >= 2:
            h, w = mask.shape[-2:]
        else:
            h, w = self.shape

        block_size = 4
        l1_h = h // block_size
        l1_w = w // block_size

        return L1AbstractLayer(
            block_size=block_size,
            l1_shape=(l1_h, l1_w),
            source_mask=mask,
        )

    def measure_ascent_pressure(self, history: List[torch.Tensor],
                                 structures: List) -> float:
        """A5+A9：度量升维压力（累积积分版）

        改进自 impulse-directions.md 的分析：
        - 旧公式：pressure = residual × density（瞬时值，只反映"有没有残差"）
        - 新公式：pressure = ∫|residual| dt × structure_density（累积积分，
          反映残差持续存在的时间长度）

        物理含义：残差存在时间越长，说明当前层越无法消解它，
        因此越不可约，越需要升维。

        实现：用滑动窗口缓存最近 _ascent_window_size 步的残差，
        积分 = 窗口内残差的 L1 范数均值 × 窗口大小
        """
        if len(history) < 2 or not structures:
            return 0.0

        # 计算当前步的守恒残差
        q1 = self.measure_invariant(history[-2])
        q2 = self.measure_invariant(history[-1])
        residual = ((q2 - q1) ** 2).mean().item()

        # 累积到滑动窗口（只保留最近 window_size 步）
        self._residual_buffer.append(residual)
        if len(self._residual_buffer) > self._ascent_window_size:
            self._residual_buffer.pop(0)

        # 累积积分：窗口内残差 L1 范数均值 × 窗口大小
        # ∫|residual| dt ≈ mean(|residual|) × window_size
        if len(self._residual_buffer) < 2:
            return 0.0

        integrated_residual = (sum(self._residual_buffer) / len(self._residual_buffer)) * len(self._residual_buffer)

        # 结构密度：稳定格点数 / 总格点数
        # 直接从 StableStructure 的 mask 计算，不依赖 len(structures)
        total_stable_pixels = sum(s.mask.sum().item() for s in structures)
        total_pixels = self.shape[0] * self.shape[1]
        density = total_stable_pixels / max(1, total_pixels)

        # 升维压力 = 累积残差 × 结构密度
        # 关键：累积积分放大时间效应，瞬时残差小但持续时间长时，压力也会增大
        return integrated_residual * density
