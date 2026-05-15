"""
engine/detectors/mutual_info.py — 比特互信息探测器（向量化版本）

检测比特位之间的翻转相关性。
如果 I(i;j) 随汉明距离衰减 → 引力信号（近距相互作用）。
"""

import torch
import numpy as np
from typing import Dict


class MutualInfoDetector:
    """比特互信息探测器（向量化版本）"""

    def __init__(self, N: int):
        self.N = N

    def compute(self, flip_sequence: torch.Tensor,
                max_lag: int = 50) -> Dict:
        """计算比特互信息（向量化版本）"""
        T = flip_sequence.shape[0]
        if T < 100:
            return {'error': 'sequence too short'}

        N = self.N
        device = flip_sequence.device

        # 构建比特翻转矩阵 (T, N) - 向量化
        flip_matrix = torch.zeros(T, N, device=device)
        valid_mask = (flip_sequence >= 0) & (flip_sequence < N)
        valid_indices = flip_sequence[valid_mask].long()
        valid_times = torch.arange(T, device=device)[valid_mask]
        flip_matrix[valid_times, valid_indices] = 1.0

        # 边缘概率
        p_flip = flip_matrix.mean(dim=0).clamp(min=1e-8, max=1 - 1e-8)

        # 联合概率矩阵 (N, N) - 向量化矩阵乘法
        joint = (flip_matrix.T @ flip_matrix) / T

        # 互信息矩阵 (N, N)
        p_i = p_flip.unsqueeze(1)  # (N, 1)
        p_j = p_flip.unsqueeze(0)  # (1, N)
        p_product = p_i * p_j
        mi_matrix = joint * (joint.clamp(min=1e-8).log() - p_product.clamp(min=1e-8).log())
        mi_matrix = mi_matrix.clamp(min=0.0)

        # 按距离分箱的互信息（向量化）
        indices = torch.arange(N, device=device)
        diff_matrix = torch.abs(indices.unsqueeze(1) - indices.unsqueeze(0))
        dist_matrix = torch.min(diff_matrix, N - diff_matrix)  # 循环距离

        mi_by_distance = {}
        for d in range(1, N // 2 + 1):
            mask = (dist_matrix == d)
            if mask.any():
                vals = mi_matrix[mask].cpu().numpy()
                mi_by_distance[int(d)] = vals.tolist()

        mi_distance_avg = {d: np.mean(vals) for d, vals in mi_by_distance.items()}
        mi_distance_std = {d: np.std(vals) for d, vals in mi_by_distance.items()}

        # 距离衰减检测
        distances = sorted(mi_distance_avg.keys())
        if len(distances) >= 3:
            mi_values = [mi_distance_avg[d] for d in distances]
            x = np.array(distances, dtype=float)
            y = np.array(mi_values, dtype=float)
            if x.std() > 0 and y.std() > 0:
                slope = np.corrcoef(x, y)[0, 1] * y.std() / x.std()
            else:
                slope = 0.0
            decay_detected = slope < -0.001
        else:
            slope = 0.0
            decay_detected = False

        return {
            'mi_by_distance': mi_distance_avg,
            'mi_distance_std': mi_distance_std,
            'flip_frequencies': p_flip.cpu().tolist(),
            'decay_slope': float(slope),
            'decay_detected': decay_detected,
            'mean_mi': float(np.mean(list(mi_distance_avg.values())) if mi_distance_avg else 0),
        }
