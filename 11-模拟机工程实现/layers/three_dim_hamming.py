"""
three_dim_hamming.py — 三维汉明格点层

把 N 个比特均分为三组，对应三维空间的 x, y, z 三个分量。
实现 WorldBase §4.2 的分块嵌入映射和 §5.2 的中截面结构。

关键概念：
- 分块嵌入：{0,1}^N → [0,L]^3，每组 N/3 个比特
- 中截面：w = N/2 的层，强力 su(3) 的载体
- 一阶变易算符 E_ij：中截面上的差异移动（保持 w 不变）
"""

import torch
from typing import List, Optional, Tuple, Dict
from layers.hamming_layer import HammingLattice
from engine.hamming_engine import HammingMeasurement


class ThreeDimHammingLattice(HammingLattice):
    """三维汉明格点层

    把 N 个比特均分为三组，每组对应一个空间维度。
    N 必须是 3 的倍数。

    分块嵌入映射：
        ι_ε(x)_k = ε_N * Σ_{i∈G_k} x_i,  k=0,1,2
    其中 G_k = {k*n, ..., (k+1)*n-1}, n = N/3
    """

    name = "three_dim_hamming"

    def __init__(self, N: int = 24, device: str = "cpu",
                 stability_window: int = 8,
                 use_strict_axioms: bool = True,
                 dag_enabled: bool = True,
                 L: float = 1.0):
        """
        Args:
            N: 比特数（必须是 3 的倍数）
            device: 计算设备
            stability_window: 稳定性检测窗口
            use_strict_axioms: 是否使用严格化公理引擎
            dag_enabled: 是否启用 DAG 方向约束
            L: 嵌入空间尺寸 [0,L]^3
        """
        if N % 3 != 0:
            raise ValueError(f"N 必须是 3 的倍数，当前 N={N}")
        super().__init__(N=N, device=device,
                         stability_window=stability_window,
                         use_strict_axioms=use_strict_axioms,
                         dag_enabled=dag_enabled)
        self.n = N // 3  # 每组比特数
        self.L = L
        self.epsilon = L / self.n  # 格点间距

    # --- 分块嵌入 ---

    def group_indices(self, k: int) -> Tuple[int, int]:
        """返回第 k 组的起始和结束索引 [start, end)"""
        assert 0 <= k < 3
        return k * self.n, (k + 1) * self.n

    def embed_3d(self, state: torch.Tensor) -> torch.Tensor:
        """分块嵌入映射 {0,1}^N → R^3

        Args:
            state: (N,) 或 (B, N) 的二值状态
        Returns:
            coords: (3,) 或 (B, 3) 的三维坐标
        """
        if state.dim() == 1:
            coords = torch.zeros(3, device=state.device, dtype=torch.float32)
            for k in range(3):
                start, end = self.group_indices(k)
                coords[k] = self.epsilon * state[start:end].sum()
            return coords
        else:
            B = state.shape[0]
            coords = torch.zeros(B, 3, device=state.device, dtype=torch.float32)
            for k in range(3):
                start, end = self.group_indices(k)
                coords[:, k] = self.epsilon * state[:, start:end].sum(dim=1)
            return coords

    def embed_3d_batch(self, states: torch.Tensor) -> torch.Tensor:
        """批量分块嵌入（高效版本）"""
        return self.embed_3d(states)

    # --- 3D 距离 ---

    def euclidean_distance(self, state1: torch.Tensor,
                           state2: torch.Tensor) -> float:
        """嵌入空间中的欧氏距离"""
        c1 = self.embed_3d(state1)
        c2 = self.embed_3d(state2)
        return ((c1 - c2) ** 2).sum().sqrt().item()

    def hamming_distance_3d(self, state1: torch.Tensor,
                            state2: torch.Tensor) -> Tuple[int, int, int, int]:
        """分组汉明距离 (dx, dy, dz, total)"""
        d_total = HammingMeasurement.hamming_distance(state1, state2)
        dx = HammingMeasurement.hamming_distance(
            state1[0:self.n], state2[0:self.n])
        dy = HammingMeasurement.hamming_distance(
            state1[self.n:2*self.n], state2[self.n:2*self.n])
        dz = HammingMeasurement.hamming_distance(
            state1[2*self.n:3*self.n], state2[2*self.n:3*self.n])
        return dx, dy, dz, d_total

    # --- 中截面 ---

    def mid_surface_weight(self) -> int:
        """中截面的汉明重量 = N/2"""
        return self.N // 2

    def is_on_mid_surface(self, state: torch.Tensor) -> bool:
        """检查状态是否在中截面上"""
        w = state.sum().long().item()
        return w == self.mid_surface_weight()

    def random_mid_surface_state(self, batch_size: int = 1) -> torch.Tensor:
        """生成随机中截面状态（w = N/2）"""
        if batch_size == 1:
            state = torch.zeros(self.N, device=self.device)
            # 随机选择 N/2 个位置设为 1
            indices = torch.randperm(self.N, device=self.device)[:self.mid_surface_weight()]
            state[indices] = 1.0
            return state
        else:
            states = torch.zeros(batch_size, self.N, device=self.device)
            for b in range(batch_size):
                indices = torch.randperm(self.N, device=self.device)[:self.mid_surface_weight()]
                states[b, indices] = 1.0
            return states

    def mid_surface_size(self) -> int:
        """中截面大小 = C(N, N/2)"""
        from math import comb
        return comb(self.N, self.N // 2)

    def enumerate_mid_surface(self, max_states: int = 1000) -> List[torch.Tensor]:
        """枚举中截面状态（仅适用于小 N）"""
        from itertools import combinations
        if self.N > 20:
            raise ValueError(f"N={self.N} 太大，中截面有 C({self.N},{self.N//2}) 个状态")

        states = []
        for combo in combinations(range(self.N), self.mid_surface_weight()):
            state = torch.zeros(self.N)
            state[list(combo)] = 1.0
            states.append(state)
            if len(states) >= max_states:
                break
        return states

    # --- 3D 势场 ---

    def potential_at(self, state: torch.Tensor,
                     sources: List[torch.Tensor]) -> float:
        """计算状态在多个源产生的势场中的总势

        Φ(x) = -Σ_s 1/d_H(x,s)
        """
        phi = 0.0
        for s in sources:
            d = HammingMeasurement.hamming_distance(state, s)
            if d > 0:
                phi -= 1.0 / d
        return phi

    def potential_3d_at(self, state: torch.Tensor,
                        sources: List[torch.Tensor]) -> float:
        """计算 3D 嵌入空间中的势场

        Φ(x) = -Σ_s 1/|ι(x) - ι(s)|
        """
        x = self.embed_3d(state)
        phi = 0.0
        for s in sources:
            s_coords = self.embed_3d(s)
            dist = ((x - s_coords) ** 2).sum().sqrt().item()
            if dist > 1e-10:
                phi -= 1.0 / dist
        return phi

    def potential_field(self, sources: List[torch.Tensor],
                        grid_resolution: int = 5) -> Dict:
        """在 3D 网格上计算势场

        简化：只在每个维度的 n 个格点上采样
        """
        # 生成网格点
        n = min(grid_resolution, self.n)
        phi_grid = {}

        for ix in range(n + 1):
            for iy in range(n + 1):
                for iz in range(n + 1):
                    # 构造状态：每组有 ix*n/n, iy*n/n, iz*n/n 个 1
                    state = torch.zeros(self.N)
                    nx = int(ix * self.n / n)
                    ny = int(iy * self.n / n)
                    nz = int(iz * self.n / n)
                    state[:nx] = 1.0
                    state[self.n:self.n+ny] = 1.0
                    state[2*self.n:2*self.n+nz] = 1.0
                    phi = self.potential_3d_at(state, sources)
                    phi_grid[(ix, iy, iz)] = phi

        return phi_grid

    # --- 一阶变易算符（中截面上的差异移动） ---

    def apply_E_ij(self, state: torch.Tensor, i: int, j: int) -> Optional[torch.Tensor]:
        """应用一阶变易算符 E_ij

        E_ij|x> = |x'> 若 x_i=1, x_j=0, x'_i=0, x'_j=1
                   None  否则

        保持汉明重量不变（中截面上闭合）。
        """
        if state.dim() != 1:
            raise ValueError("E_ij 只支持 1D 状态")

        if state[i] > 0.5 and state[j] < 0.5:
            new_state = state.clone()
            new_state[i] = 0.0
            new_state[j] = 1.0
            return new_state
        return None

    def get_valid_E_moves(self, state: torch.Tensor) -> List[Tuple[int, int]]:
        """获取所有有效的 E_ij 移动

        Returns:
            [(i, j), ...] 满足 x_i=1, x_j=0 的所有对
        """
        if state.dim() != 1:
            raise ValueError("只支持 1D 状态")
        ones = (state > 0.5).nonzero(as_tuple=True)[0].tolist()
        zeros = (state < 0.5).nonzero(as_tuple=True)[0].tolist()
        moves = []
        for i in ones:
            for j in zeros:
                moves.append((i, j))
        return moves

    def estimate_active_bits(self, state: torch.Tensor) -> int:
        """估计活跃比特数（中截面上 w=N/2 时）"""
        return state.sum().int().item()

    # --- 统计信息 ---

    def stats(self, state: torch.Tensor) -> Dict:
        """返回状态的统计信息"""
        w = state.sum().int().item()
        coords = self.embed_3d(state)
        return {
            'hamming_weight': w,
            'mid_surface_weight': self.mid_surface_weight(),
            'on_mid_surface': self.is_on_mid_surface(state),
            'coords_3d': coords.tolist(),
            'group_weights': [
                state[0:self.n].sum().item(),
                state[self.n:2*self.n].sum().item(),
                state[2*self.n:3*self.n].sum().item(),
            ],
        }
