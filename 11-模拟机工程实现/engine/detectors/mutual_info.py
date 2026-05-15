"""
engine/detectors/mutual_info.py — 比特互信息探测器

检测比特位之间的翻转相关性。
如果 I(i;j) 随汉明距离衰减 → 引力信号（近距相互作用）。

方法：
1. 对比特翻转序列做自相关分析
2. 计算每对 (i,j) 的互信息 I(i;j) = H(i) + H(j) - H(i,j)
3. 按汉明距离分组，看 I(d) 的衰减曲线
4. 与无约束随机游走的互信息对比
"""

import torch
import numpy as np
from typing import Dict, Tuple


class MutualInfoDetector:
    """比特互信息探测器"""

    def __init__(self, N: int):
        self.N = N

    def compute(self, flip_sequence: torch.Tensor,
                max_lag: int = 50,
                n_bins: int = 20) -> Dict:
        """计算比特互信息

        Args:
            flip_sequence: (T,) 翻转位置序列
            max_lag: 最大时间延迟
            n_bins: 距离分箱数

        Returns:
            互信息结果字典
        """
        T = flip_sequence.shape[0]
        if T < max_lag * 2:
            return {'error': 'sequence too short'}

        # 构建比特翻转矩阵 (T, N)
        flip_matrix = torch.zeros(T, self.N)
        for t in range(T):
            pos = flip_sequence[t].item()
            if 0 <= pos < self.N:
                flip_matrix[t, pos] = 1.0

        # 1. 每个比特的翻转频率（边缘熵）
        p_flip = flip_matrix.mean(dim=0)  # (N,) 翻转频率
        p_flip = p_flip.clamp(min=1e-8, max=1 - 1e-8)
        h_individual = -(p_flip * p_flip.log() + (1 - p_flip) * (1 - p_flip).log())

        # 2. 比特对联合翻转概率（延迟互信息）
        # I(i; j, lag) = Σ p(i_t, j_{t+lag}) log[p(i_t, j_{t+lag}) / (p(i_t) p(j_{t+lag}))]
        mi_by_lag = {}
        for lag in range(1, min(max_lag, T // 2)):
            mi_sum = 0.0
            count = 0
            for i in range(self.N):
                for j in range(self.N):
                    if i == j:
                        continue
                    # 联合概率 p(i_t=1, j_{t+lag}=1)
                    fi = flip_matrix[:T-lag, i]
                    fj = flip_matrix[lag:, j]
                    p_joint = (fi * fj).mean().item()
                    p_i = p_flip[i].item()
                    p_j = p_flip[j].item()

                    if p_joint > 1e-8 and p_i > 1e-8 and p_j > 1e-8:
                        mi = p_joint * np.log(p_joint / (p_i * p_j))
                        mi_sum += max(0, mi)
                        count += 1

            mi_by_lag[lag] = mi_sum / max(1, count)

        # 3. 按距离分箱的互信息（需要位置信息）
        # 对于汉明空间，距离 = |i-j|（循环）
        mi_by_distance = {}
        for i in range(self.N):
            for j in range(i + 1, self.N):
                d = min(abs(i - j), self.N - abs(i - j))  # 循环距离
                fi = flip_matrix[:, i]
                fj = flip_matrix[:, j]
                p_joint = (fi * fj).mean().item()
                p_i = p_flip[i].item()
                p_j = p_flip[j].item()
                if p_joint > 1e-8:
                    mi = p_joint * np.log(p_joint / (p_i * p_j))
                else:
                    mi = 0.0
                d_key = int(d)
                if d_key not in mi_by_distance:
                    mi_by_distance[d_key] = []
                mi_by_distance[d_key].append(max(0, mi))

        # 平均每个距离的互信息
        mi_distance_avg = {d: np.mean(vals) for d, vals in mi_by_distance.items()}
        mi_distance_std = {d: np.std(vals) for d, vals in mi_by_distance.items()}

        # 4. 检测信号：互信息是否随距离衰减
        distances = sorted(mi_distance_avg.keys())
        if len(distances) >= 3:
            mi_values = [mi_distance_avg[d] for d in distances]
            # 简单线性回归斜率
            x = np.array(distances, dtype=float)
            y = np.array(mi_values, dtype=float)
            if x.std() > 0:
                slope = np.corrcoef(x, y)[0, 1] * y.std() / x.std()
            else:
                slope = 0.0
            decay_detected = slope < -0.001  # 负斜率 = 衰减
        else:
            slope = 0.0
            decay_detected = False

        return {
            'mi_by_distance': mi_distance_avg,
            'mi_distance_std': mi_distance_std,
            'mi_by_lag': mi_by_lag,
            'flip_frequencies': p_flip.tolist(),
            'decay_slope': float(slope),
            'decay_detected': decay_detected,
            'mean_mi': float(np.mean(list(mi_distance_avg.values()))),
        }
