"""
engine/detectors/mutual_info.py — 比特互信息探测器（3D 空间版）

检测比特位之间的翻转相关性，距离定义为 3D 嵌入空间欧氏距离。
如果 I(r) 随 3D 距离衰减 → 引力信号（近距相互作用）。

改造：
- 旧版：bit-index 距离 |i-j|（循环）
- 新版：3D 欧氏距离 |ι(i)-ι(j)|（需要 ThreeDimHammingLattice）
"""

import torch
import numpy as np
from typing import Dict, Optional


class MutualInfoDetector:
    """比特互信息探测器（3D 空间版）"""

    def __init__(self, N: int, n_groups: int = 3):
        """
        Args:
            N: 总比特数
            n_groups: 分组数（3 = 三维空间）
        """
        self.N = N
        self.n_groups = n_groups
        self.n_per_group = N // n_groups

    def _bit_to_3d_coord(self, bit_idx: int) -> np.ndarray:
        """将比特索引转换为 3D 坐标（归一化到 [0,1]）

        分组方案：
        - 组 0 (0..n-1): x 坐标
        - 组 1 (n..2n-1): y 坐标
        - 组 2 (2n..3n-1): z 坐标
        如果 N 不是 3 的倍数，超出部分归入 z 组。
        """
        n = max(self.n_per_group, 1)
        group = min(bit_idx // n, 2)  # 限制在 0-2
        idx_in_group = bit_idx % n
        coord = np.zeros(3)
        coord[group] = (idx_in_group + 0.5) / n
        return coord

    def _compute_3d_dist_matrix(self) -> torch.Tensor:
        """计算所有比特对之间的 3D 欧氏距离矩阵 (N, N)"""
        coords = np.array([self._bit_to_3d_coord(i) for i in range(self.N)])
        coords_t = torch.tensor(coords, dtype=torch.float32)
        # 欧氏距离矩阵
        dist = torch.cdist(coords_t, coords_t, p=2)
        return dist

    def compute(self, flip_sequence: torch.Tensor,
                max_lag: int = 50,
                use_3d_distance: bool = False) -> Dict:
        """计算比特互信息

        Args:
            flip_sequence: (T,) 翻转位置序列
            max_lag: 最大时间延迟
            use_3d_distance: True=3D欧氏距离, False=旧版bit-index距离
        """
        T = flip_sequence.shape[0]
        if T < 100:
            return {'error': 'sequence too short'}

        N = self.N
        device = flip_sequence.device

        # 构建比特翻转矩阵 (T, N)
        flip_matrix = torch.zeros(T, N, device=device)
        valid_mask = (flip_sequence >= 0) & (flip_sequence < N)
        valid_indices = flip_sequence[valid_mask].long()
        valid_times = torch.arange(T, device=device)[valid_mask]
        flip_matrix[valid_times, valid_indices] = 1.0

        # 边缘概率
        p_flip = flip_matrix.mean(dim=0).clamp(min=1e-8, max=1 - 1e-8)

        # 联合概率矩阵 (N, N)
        joint = (flip_matrix.T @ flip_matrix) / T

        # 互信息矩阵 (N, N)
        p_i = p_flip.unsqueeze(1)  # (N, 1)
        p_j = p_flip.unsqueeze(0)  # (1, N)
        p_product = p_i * p_j
        mi_matrix = joint * (joint.clamp(min=1e-8).log() - p_product.clamp(min=1e-8).log())
        mi_matrix = mi_matrix.clamp(min=0.0)

        # 按距离分箱的互信息
        if use_3d_distance:
            dist_matrix = self._compute_3d_dist_matrix().to(device)
        else:
            # 旧版：bit-index 循环距离
            indices = torch.arange(N, device=device)
            diff_matrix = torch.abs(indices.unsqueeze(1) - indices.unsqueeze(0))
            dist_matrix = torch.min(diff_matrix, N - diff_matrix).float()

        # 按距离分箱
        max_dist = dist_matrix.max().item()
        if max_dist <= 0:
            return {'error': 'zero distance matrix'}

        n_bins = min(20, N // 2)
        bin_edges = np.linspace(0, max_dist, n_bins + 1)

        mi_by_distance = {}
        for b in range(n_bins):
            lo, hi = bin_edges[b], bin_edges[b + 1]
            mask = (dist_matrix >= lo) & (dist_matrix < hi)
            # 排除对角线
            mask = mask & ~torch.eye(N, dtype=torch.bool, device=device)
            if mask.any():
                vals = mi_matrix[mask].cpu().numpy()
                center = (lo + hi) / 2
                mi_by_distance[float(center)] = float(np.mean(vals))

        # 距离衰减检测
        distances = sorted(mi_by_distance.keys())
        if len(distances) >= 3:
            mi_values = [mi_by_distance[d] for d in distances]
            x = np.array(distances, dtype=float)
            y = np.array(mi_values, dtype=float)
            # 只取 y > 0 的点做拟合
            valid = y > 1e-10
            if valid.sum() >= 3:
                x_fit = x[valid]
                y_fit = np.log(y[valid])
                if x_fit.std() > 0 and y_fit.std() > 0:
                    slope = np.corrcoef(x_fit, y_fit)[0, 1] * y_fit.std() / x_fit.std()
                else:
                    slope = 0.0
                decay_detected = slope < -0.01
            else:
                slope = 0.0
                decay_detected = False
        else:
            slope = 0.0
            decay_detected = False

        return {
            'mi_by_distance': mi_by_distance,
            'flip_frequencies': p_flip.cpu().tolist(),
            'decay_slope': float(slope),
            'decay_detected': decay_detected,
            'mean_mi': float(np.mean(list(mi_by_distance.values())) if mi_by_distance else 0),
            'distance_type': '3d_euclidean' if use_3d_distance else 'bit_index',
            'n_bins': len(mi_by_distance),
        }
