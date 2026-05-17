"""
engine/detectors/gravitational_potential.py — 引力势探测器

测量势场 Phi(x) = -Sigma_s 1/|iota(x)-iota(s)|
验证引力势的 -1/r 标度律。

依赖: ThreeDimHammingLattice.embed_3d(), potential_3d_at()
"""

import torch
import numpy as np
from typing import Dict, List, Optional


class GravitationalPotentialDetector:
    """引力势探测器

    功能：
    1. 计算轨迹上每个状态在源产生的势场中的势
    2. 拟合 Phi(r) ~ -1/r 标度律
    3. 检测引力信号（势随距离单调衰减）

    距离定义：3D 嵌入空间欧氏距离
    """

    def __init__(self, N: int, n_per_group: int = 16, L: float = 1.0):
        self.N = N
        self.n_per_group = n_per_group
        self.L = L
        self.epsilon = L / n_per_group

    def bit_to_3d(self, bit_idx: int) -> np.ndarray:
        """比特索引 -> 3D 坐标"""
        group = bit_idx // self.n_per_group
        idx_in_group = bit_idx % self.n_per_group
        coord = np.zeros(3)
        coord[group] = self.epsilon * (idx_in_group + 0.5)
        return coord

    def embed_state_3d(self, state: torch.Tensor) -> np.ndarray:
        """状态 -> 3D 坐标（分块嵌入）"""
        coords = np.zeros(3)
        for k in range(3):
            start = k * self.n_per_group
            end = start + self.n_per_group
            coords[k] = self.epsilon * state[start:end].sum().item()
        return coords

    def compute_potential_curve(self,
                                 trajectory: torch.Tensor,
                                 source_positions: List[int]) -> Dict:
        """计算势-距离曲线

        Args:
            trajectory: (T, N) 状态轨迹
            source_positions: 源比特索引列表

        Returns:
            dict with potential_curve, fit_result, gravitation_detected
        """
        T = trajectory.shape[0]
        if T < 10:
            return {'error': 'trajectory too short'}

        # 源坐标
        source_coords = np.array([self.bit_to_3d(s) for s in source_positions])

        # 计算每个轨迹点的势和到最近源的距离
        potentials = []
        distances = []

        for t in range(T):
            state = trajectory[t]
            state_coord = self.embed_state_3d(state)

            # 到各源的 3D 距离
            min_dist = float('inf')
            for sc in source_coords:
                d = np.linalg.norm(state_coord - sc)
                if d < min_dist:
                    min_dist = d

            # 势 = -1/d（避免除零）
            if min_dist > 1e-10:
                phi = -1.0 / min_dist
            else:
                phi = -1e10

            potentials.append(phi)
            distances.append(min_dist)

        potentials = np.array(potentials)
        distances = np.array(distances)

        # 按距离分箱计算平均势
        n_bins = min(20, T // 5)
        if n_bins < 3:
            return {'error': 'too few bins'}

        dist_min = distances[distances > 1e-10].min() if (distances > 1e-10).any() else 1e-10
        dist_max = distances.max()
        if dist_max <= dist_min:
            return {'error': 'degenerate distance range'}

        bin_edges = np.linspace(dist_min * 0.9, dist_max * 1.1, n_bins + 1)
        phi_by_dist = {}
        for b in range(n_bins):
            lo, hi = bin_edges[b], bin_edges[b + 1]
            mask = (distances >= lo) & (distances < hi)
            if mask.sum() >= 2:
                center = (lo + hi) / 2
                phi_by_dist[float(center)] = float(potentials[mask].mean())

        # 拟合 Phi(r) = -alpha / r^beta
        # log|Phi| = log(alpha) - beta * log(r)
        dists = sorted(phi_by_dist.keys())
        valid = [(d, phi_by_dist[d]) for d in dists if phi_by_dist[d] < -1e-10]
        gravitation_detected = False
        beta = 0.0
        alpha = 0.0
        r_squared = 0.0

        if len(valid) >= 3:
            x = np.log([v[0] for v in valid])
            y = np.log([-v[1] for v in valid])

            if x.std() > 0 and y.std() > 0:
                slope, intercept = np.polyfit(x, y, 1)
                beta = -slope
                alpha = np.exp(intercept)
                ss_res = np.sum((y - slope * x - intercept) ** 2)
                ss_tot = np.sum((y - y.mean()) ** 2)
                r_squared = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
                r_squared = float(np.clip(r_squared, 0.0, 1.0))
                gravitation_detected = 0.5 < beta < 2.0 and r_squared > 0.5

        return {
            'potential_curve': phi_by_dist,
            'fit_alpha': float(alpha),
            'fit_beta': float(beta),
            'fit_r_squared': float(r_squared),
            'gravitation_detected': gravitation_detected,
            'n_data_points': len(valid),
            'mean_potential': float(potentials.mean()),
        }

    def compute_from_evolver_result(self, result: Dict,
                                     source_positions: Optional[List[int]] = None) -> Dict:
        """从演化器结果计算引力势"""
        if 'snapshots' not in result or not result['snapshots']:
            return {'error': 'no snapshots in result'}

        traj = torch.stack([s.state for s in result['snapshots']], dim=0)

        if source_positions is None:
            clusters = result.get('clusters', [])
            if clusters:
                largest = max(clusters, key=len)
                source_positions = largest[:2]
            else:
                binding = result.get('binding_strength', torch.zeros(self.N, self.N))
                row_sums = binding.sum(dim=1)
                top_indices = row_sums.argsort(descending=True)[:2].tolist()
                source_positions = top_indices

        return self.compute_potential_curve(traj, source_positions)
