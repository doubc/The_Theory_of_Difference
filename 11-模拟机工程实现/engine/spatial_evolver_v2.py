"""
engine/spatial_evolver_v2.py — 空间长程演化器 v2

在 long_range_evolver_v2.py 基础上集成 ThreeDimHammingLattice 空间嵌入层。

核心改动：
1. 快照中记录 3D 坐标
2. 源注入位置选择基于 3D 空间偏好（A8 空间版）
3. 汇吸收位置选择基于 3D 空间偏好
4. 返回结果包含 3D 轨迹

演化逻辑完全复用 LongRangeEvolverV2，只做空间增强。
"""

import torch
import numpy as np
from typing import List, Optional, Dict, Tuple
from layers.three_dim_hamming import ThreeDimHammingLattice
from acl.axioms_v2 import AxiomConstraints


class SpatialSnapshot:
    """空间轨迹快照"""
    def __init__(self, step: int, state: torch.Tensor,
                 flip_idx: int, n_inject: int, n_absorb: int,
                 n_lateral: int, w: int,
                 coords_3d: np.ndarray):
        self.step = step
        self.state = state.clone()
        self.flip_idx = flip_idx
        self.n_inject = n_inject
        self.n_absorb = n_absorb
        self.n_lateral = n_lateral
        self.w = w
        self.coords_3d = coords_3d.copy()  # (3,) 坐标


class SpatialLongRangeEvolver:
    """空间长程演化器（集成 3D 空间嵌入层）"""

    def __init__(self, N: int = 48,
                 total_steps: int = 5000,
                 sample_interval: int = 100,
                 device: str = "cpu",
                 n_hierarchy_bits: int = None,
                 L: float = 1.0):
        # 自动对齐到 3 的倍数
        if N % 3 != 0:
            N = N + (3 - N % 3)
        self.N = N
        self.total_steps = total_steps
        self.sample_interval = sample_interval
        self.device = device

        # 空间嵌入层
        self.spatial_layer = ThreeDimHammingLattice(N=N, L=L, device=device)

        # 公理约束器
        self.constraints = AxiomConstraints(N, n_hierarchy_bits)

        # 轨迹记录
        self.snapshots: List[SpatialSnapshot] = []
        self.flip_history: List[int] = []
        self.hamming_weight_history: List[int] = []
        self.inject_history: List[int] = []
        self.absorb_history: List[int] = []
        self.lateral_history: List[int] = []
        self.coords_history: List[np.ndarray] = []  # 3D 坐标历史

    def _spatial_source_weights(self, state: torch.Tensor) -> torch.Tensor:
        """A8 空间版：源注入位置权重

        偏好：
        1. 距离已有 1 较远的位置（空间均匀化）
        2. 汉明重量较低的区域（注入差异）
        """
        N = self.N
        n = N // 3
        weights = torch.ones(N)

        # 计算每个比特的 3D 坐标
        coords = np.zeros((N, 3))
        for i in range(N):
            group = i // n
            idx_in = i % n
            coords[i, group] = self.spatial_layer.epsilon * (idx_in + 0.5)

        # 当前状态中 1 的位置
        ones_mask = state > 0.5
        if ones_mask.sum() > 0:
            ones_coords = coords[ones_mask.cpu().numpy()]

            # 对每个 0 位置，计算到最近 1 的距离
            zeros_mask = state < 0.5
            zero_indices = zeros_mask.nonzero(as_tuple=True)[0]

            for idx in zero_indices:
                coord = coords[idx.item()]
                # 到所有 1 的最小距离
                dists = np.linalg.norm(ones_coords - coord, axis=1)
                min_dist = dists.min()
                # 权重正比于距离（越远越容易被注入）
                weights[idx] = 1.0 + min_dist * 5.0

        return weights

    def _spatial_sink_weights(self, state: torch.Tensor) -> torch.Tensor:
        """A8 空间版：汇吸收位置权重

        偏好：
        1. 距离已有 0 较远的位置（空间均匀化）
        2. 汉明重量较高的区域（吸收差异）
        """
        N = self.N
        n = N // 3
        weights = torch.ones(N)

        coords = np.zeros((N, 3))
        for i in range(N):
            group = i // n
            idx_in = i % n
            coords[i, group] = self.spatial_layer.epsilon * (idx_in + 0.5)

        zeros_mask = state < 0.5
        if zeros_mask.sum() > 0:
            zeros_coords = coords[zeros_mask.cpu().numpy()]
            ones_mask = state > 0.5
            one_indices = ones_mask.nonzero(as_tuple=True)[0]

            for idx in one_indices:
                coord = coords[idx.item()]
                dists = np.linalg.norm(zeros_coords - coord, axis=1)
                min_dist = dists.min()
                weights[idx] = 1.0 + min_dist * 5.0

        return weights

    def run(self, initial_state: Optional[torch.Tensor] = None,
            verbose: bool = True,
            step_callback: Optional[callable] = None) -> Dict:
        """运行空间长程演化

        Args:
            initial_state: 初始状态
            verbose: 是否打印详情
            step_callback: 每 sample_interval 步调用的回调函数
                           签名: callback(step: int, state: torch.Tensor,
                                          snapshot: SpatialSnapshot,
                                          constraints: AxiomConstraints) -> None
        """

        if initial_state is None:
            state = torch.zeros(self.N, device=self.device)
        else:
            state = initial_state.clone().to(self.device)

        self.snapshots = []
        self.flip_history = []
        self.hamming_weight_history = []
        self.inject_history = []
        self.absorb_history = []
        self.lateral_history = []
        self.coords_history = []

        if verbose:
            print(f"[SpatialEvolver] N={self.N}, T={self.total_steps}, "
                  f"L={self.spatial_layer.L}, eps={self.spatial_layer.epsilon:.4f}")
            print(f"  Hierarchy bits: {self.constraints.n_hierarchy}, "
                  f"Lateral bits: {self.constraints.n_lateral}")

        for step in range(self.total_steps):
            w_before = state.sum().long().item()

            # ====== 1. 源注入（A1 + A8 空间调制）======
            source_strength = self.constraints.get_A8_source_strength(state)
            actual_inject = 0
            if source_strength > 0:
                h_candidates = [i for i in self.constraints.hierarchy_indices
                                if state[i] < 0.5 and self.constraints.direction[i].item() >= 0]
                l_candidates = [i for i in self.constraints.lateral_indices
                                if state[i] < 0.5 and self.constraints.direction[i].item() >= 0]
                all_candidates = h_candidates + l_candidates
                if all_candidates:
                    n_inject = min(source_strength, len(all_candidates))
                    ok, _ = self.constraints.check_A5_inject(state, n_inject)
                    if ok:
                        # 空间加权选择
                        spatial_w = self._spatial_source_weights(state)
                        candidate_weights = spatial_w[all_candidates]
                        candidate_weights = candidate_weights / candidate_weights.sum()
                        n_choose = min(n_inject, len(all_candidates))
                        indices = torch.multinomial(candidate_weights, n_choose, replacement=False)
                        chosen = [all_candidates[idx.item()] for idx in indices]
                        for idx in chosen:
                            a9_ok, _ = self.constraints.check_A9(idx)
                            if not a9_ok:
                                continue
                            state[idx] = 1.0
                            self.constraints.record_inject(1)
                            self.constraints.record_active(idx)
                            self.constraints.direction[idx] = 1
                            actual_inject += 1
                    else:
                        n_inject = 0
                else:
                    n_inject = 0
            else:
                n_inject = 0

            # ====== 2. 内部演化（A4 + A1 + A6 + A8）======
            allowed = self.constraints.get_allowed_flips(state)
            if allowed:
                weights = self.constraints.get_A8_weights(state)
                allowed_weights = weights[allowed]
                allowed_weights = allowed_weights / allowed_weights.sum()
                flip_idx = allowed[torch.multinomial(allowed_weights, 1).item()]
                a9_ok, _ = self.constraints.check_A9(flip_idx)
                if a9_ok:
                    old_val = state[flip_idx].item()
                    state[flip_idx] = 1.0 - state[flip_idx]
                    new_val = state[flip_idx].item()
                    self.constraints.update_A6_direction(flip_idx, old_val, new_val)
                    self.constraints.record_active(flip_idx)
                else:
                    flip_idx = -1
            else:
                flip_idx = -1

            # ====== 3. 横向演化（A1' + A5）======
            lateral_pairs = self.constraints.get_A1_prime_candidates(state)
            n_lateral = 0
            for (i, j) in lateral_pairs:
                if state[i] > 0.5 and state[j] < 0.5:
                    a9_ok_i, _ = self.constraints.check_A9(i)
                    a9_ok_j, _ = self.constraints.check_A9(j)
                    if not a9_ok_i or not a9_ok_j:
                        continue
                    state[i] = 0.0
                    state[j] = 1.0
                    self.constraints.update_A6_direction(i, 1.0, 0.0)
                    self.constraints.update_A6_direction(j, 0.0, 1.0)
                    self.constraints.record_active(i)
                    self.constraints.record_active(j)
                    self.constraints.strengthen_binding(i, j, amount=0.1)
                    n_lateral += 1

            # ====== 4. 汇吸收（A8 空间版 + A5 平衡）======
            sink_strength = self.constraints.get_A8_sink_strength(state, n_inject)
            if sink_strength > 0:
                allowed_abs = self.constraints.get_allowed_absorbs(state)
                lateral_abs = [i for i in allowed_abs if i in self.constraints.lateral_indices]
                hierarchy_abs = [i for i in allowed_abs if i in self.constraints.hierarchy_indices]
                absorb_targets = lateral_abs + hierarchy_abs
                n_absorb = min(sink_strength, len(absorb_targets))

                if n_absorb > 0:
                    ok, _ = self.constraints.check_A5_absorb(state, n_absorb)
                    if ok:
                        # 空间加权选择汇吸收位置
                        spatial_w = self._spatial_sink_weights(state)
                        if len(absorb_targets) <= n_absorb:
                            chosen = absorb_targets
                        else:
                            target_weights = spatial_w[absorb_targets]
                            target_weights = target_weights / target_weights.sum()
                            n_choose = min(n_absorb, len(absorb_targets))
                            indices = torch.multinomial(target_weights, n_choose, replacement=False)
                            chosen = [absorb_targets[idx.item()] for idx in indices]
                        for idx in chosen:
                            state[idx] = 0.0
                            self.constraints.record_absorb(1)
                            if idx in self.constraints.lateral_indices:
                                self.constraints.direction[idx] = 0
                            else:
                                self.constraints.direction[idx] = -1
                    else:
                        n_absorb = 0
                else:
                    n_absorb = 0
            else:
                n_absorb = 0

            # ====== 5. A7 循环检测 ======
            self.constraints.check_A7(state)

            # ====== 6. 记录 ======
            w_after = state.sum().long().item()
            coords_3d = self.spatial_layer.embed_3d(state).cpu().numpy()

            self.flip_history.append(flip_idx)
            self.hamming_weight_history.append(w_after)
            self.inject_history.append(actual_inject)
            self.absorb_history.append(n_absorb)
            self.lateral_history.append(n_lateral)
            self.coords_history.append(coords_3d)

            # ====== 7. 采样 ======
            if step % self.sample_interval == 0:
                snapshot = SpatialSnapshot(
                    step=step, state=state, flip_idx=flip_idx,
                    n_inject=n_inject, n_absorb=n_absorb,
                    n_lateral=n_lateral, w=w_after,
                    coords_3d=coords_3d
                )
                self.snapshots.append(snapshot)

                # Phase 2: step callback (XiàngDetector, PersistentBiasMemory, etc.)
                if step_callback is not None:
                    step_callback(step, state, snapshot, self.constraints)

                if verbose and step % (self.sample_interval * 5) == 0:
                    n_cycles = len(self.constraints.cycle_states)
                    n_active = len(self.constraints.active_bits)
                    print(f"  Step {step:6d}: w={w_after:3d}, "
                          f"inj={n_inject}, abs={n_absorb}, lat={n_lateral}, "
                          f"active={n_active}, cycles={n_cycles}, "
                          f"pos=[{coords_3d[0]:.2f},{coords_3d[1]:.2f},{coords_3d[2]:.2f}]")

        if verbose:
            print(f"[SpatialEvolver] Done. {len(self.snapshots)} snapshots.")
            print(f"  Cycles: {len(self.constraints.cycle_states)}")
            print(f"  Sealed: {self.constraints.sealed} ({len(self.constraints.sealed_bits)} bits, "
                  f"ratio={self.constraints.get_sealed_ratio():.2f})")
            print(f"  Total inject: {self.constraints.total_injected}, "
                  f"absorb: {self.constraints.total_absorbed}")

        return {
            'total_steps': self.total_steps,
            'n_snapshots': len(self.snapshots),
            'final_state': state,
            'flip_history': self.flip_history,
            'hamming_weight_history': self.hamming_weight_history,
            'inject_history': self.inject_history,
            'absorb_history': self.absorb_history,
            'lateral_history': self.lateral_history,
            'snapshots': self.snapshots,
            'cycle_states': len(self.constraints.cycle_states),
            'active_bits': len(self.constraints.active_bits),
            'direction': self.constraints.direction.clone(),
            'clusters': self.constraints.get_clusters(),
            'binding_strength': self.constraints.binding_strength.clone(),
            'sealed': self.constraints.sealed,
            'sealed_bits': len(self.constraints.sealed_bits),
            'sealed_ratio': self.constraints.get_sealed_ratio(),
            'total_injected': self.constraints.total_injected,
            'total_absorbed': self.constraints.total_absorbed,
            # 空间增强字段
            'coords_history': self.coords_history,
            'spatial_layer': self.spatial_layer,
        }

    def get_trajectory_tensor(self) -> torch.Tensor:
        if not self.snapshots:
            return torch.zeros(0, self.N)
        return torch.stack([s.state for s in self.snapshots], dim=0)

    def get_3d_trajectory(self) -> np.ndarray:
        """获取 3D 坐标轨迹 (T, 3)"""
        if not self.snapshots:
            return np.zeros((0, 3))
        return np.array([s.coords_3d for s in self.snapshots])

    def get_flip_sequence(self) -> torch.Tensor:
        return torch.tensor(self.flip_history, dtype=torch.long)

    def get_hamming_weight_sequence(self) -> torch.Tensor:
        return torch.tensor(self.hamming_weight_history, dtype=torch.long)
