"""
engine/detectors/spatial_correlation.py — 空间关联探测器 (P4)

检测 3D 嵌入空间中的空间关联函数 C(r)。

理论预测：
- 短程有序：C(r) ~ exp(-r/xi)（关联长度 xi 有限）
- 长程有序：C(r) → const（xi → ∞）
- 幂律关联：C(r) ~ r^{-alpha}（临界态）

检测方法：
1. 从轨迹中计算每对比特的翻转相关性
2. 按 3D 欧氏距离分箱
3. 拟合关联长度 xi
4. 检测有序/临界态信号
"""

import torch
import numpy as np
from typing import Dict, List, Optional


class SpatialCorrelationDetector:
    """空间关联探测器"""

    def __init__(self, N: int, n_per_group: int = 16, L: float = 1.0):
        self.N = N
        self.n_per_group = n_per_group
        self.L = L
        self.epsilon = L / n_per_group

    def bit_to_3d(self, bit_idx: int) -> np.ndarray:
        """比特索引 -> 3D 坐标"""
        n = max(self.n_per_group, 1)
        group = min(bit_idx // n, 2)
        idx_in = bit_idx % n
        coord = np.zeros(3)
        coord[group] = self.epsilon * (idx_in + 0.5)
        return coord

    def compute_spatial_correlation(self, trajectory: torch.Tensor,
                                      max_samples: int = 200) -> Dict:
        """计算空间关联函数 C(r)

        Args:
            trajectory: (T, N) 比特状态轨迹
            max_samples: 最大采样状态数

        Returns:
            dict with correlation_curve, correlation_length, order_detected
        """
        T = trajectory.shape[0]
        if T < 10:
            return {'error': 'trajectory too short'}

        N = self.N
        device = trajectory.device

        # 降采样
        n_sample = min(T, max_samples)
        indices = torch.linspace(0, T - 1, n_sample).long()
        traj_sample = trajectory[indices]  # (n_sample, N)

        # 计算比特间相关性矩阵
        mean = traj_sample.mean(dim=0, keepdim=True)
        std = traj_sample.std(dim=0, keepdim=True).clamp(min=1e-8)
        normalized = (traj_sample - mean) / std
        corr_matrix = (normalized.T @ normalized) / n_sample  # (N, N)
        corr_matrix = corr_matrix.cpu().numpy()

        # 3D 距离矩阵
        coords = np.array([self.bit_to_3d(i) for i in range(N)])
        dist_matrix = np.zeros((N, N))
        for i in range(N):
            for j in range(N):
                dist_matrix[i, j] = np.linalg.norm(coords[i] - coords[j])

        # 按距离分箱
        max_dist = dist_matrix.max()
        if max_dist <= 0:
            return {'error': 'zero distance matrix'}

        n_bins = min(20, N // 2)
        bin_edges = np.linspace(0, max_dist, n_bins + 1)

        corr_by_dist = {}
        for b in range(n_bins):
            lo, hi = bin_edges[b], bin_edges[b + 1]
            mask = (dist_matrix >= lo) & (dist_matrix < hi)
            # 排除对角线
            mask = mask & ~np.eye(N, dtype=bool)
            if mask.any():
                vals = corr_matrix[mask]
                center = (lo + hi) / 2
                corr_by_dist[float(center)] = float(np.mean(vals))

        # 拟合关联长度
        dists = sorted(corr_by_dist.keys())
        valid = [(d, corr_by_dist[d]) for d in dists if abs(corr_by_dist[d]) > 1e-10]

        correlation_length = 0.0
        r_squared = 0.0
        fit_type = 'unknown'

        if len(valid) >= 3:
            x = np.array([v[0] for v in valid])
            y = np.array([v[1] for v in valid])

            # 尝试指数拟合: C(r) = C0 * exp(-r/xi)
            # log|C| = log(C0) - r/xi
            try:
                pos = y > 1e-10
                if pos.sum() >= 3:
                    x_exp = x[pos]
                    y_exp = np.log(y[pos])
                    if x_exp.std() > 0 and y_exp.std() > 0:
                        slope_exp, intercept_exp = np.polyfit(x_exp, y_exp, 1)
                        xi_exp = -1.0 / slope_exp if slope_exp < 0 else float('inf')
                        ss_res = np.sum((y_exp - slope_exp * x_exp - intercept_exp) ** 2)
                        ss_tot = np.sum((y_exp - y_exp.mean()) ** 2)
                        r2_exp = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                    else:
                        xi_exp = 0.0
                        r2_exp = 0.0
                else:
                    xi_exp = 0.0
                    r2_exp = 0.0
            except Exception:
                xi_exp = 0.0
                r2_exp = 0.0

            # 尝试幂律拟合: C(r) ~ r^{-alpha}
            try:
                pos = (y > 1e-10) & (x > 1e-10)
                if pos.sum() >= 3:
                    x_pow = np.log(x[pos])
                    y_pow = np.log(y[pos])
                    if x_pow.std() > 0 and y_pow.std() > 0:
                        slope_pow, intercept_pow = np.polyfit(x_pow, y_pow, 1)
                        alpha_pow = -slope_pow
                        ss_res = np.sum((y_pow - slope_pow * x_pow - intercept_pow) ** 2)
                        ss_tot = np.sum((y_pow - y_pow.mean()) ** 2)
                        r2_pow = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                    else:
                        alpha_pow = 0.0
                        r2_pow = 0.0
                else:
                    alpha_pow = 0.0
                    r2_pow = 0.0
            except Exception:
                alpha_pow = 0.0
                r2_pow = 0.0

            # 选择更好的拟合
            if r2_exp > r2_pow and xi_exp > 0 and xi_exp < float('inf'):
                correlation_length = xi_exp
                r_squared = r2_exp
                fit_type = 'exponential'
            elif r2_pow > r2_exp and alpha_pow > 0:
                correlation_length = alpha_pow  # 用幂律指数代替
                r_squared = r2_pow
                fit_type = 'power_law'
            else:
                correlation_length = xi_exp if xi_exp > 0 else 0.0
                r_squared = max(r2_exp, r2_pow)
                fit_type = 'undetermined'
        else:
            xi_exp = 0.0
            alpha_pow = 0.0

        # 有序信号检测
        # 短程有序：有限关联长度，指数衰减
        short_range_order = (
            fit_type == 'exponential' and
            correlation_length > 0 and
            correlation_length < max_dist and
            r_squared > 0.5
        )

        # 长程有序：关联不衰减（所有距离上 C(r) > 0）
        all_positive = all(v > 0 for v in corr_by_dist.values())
        long_range_order = all_positive and len(corr_by_dist) > 3

        # 临界态：幂律关联
        critical = (
            fit_type == 'power_law' and
            alpha_pow > 0 and
            r_squared > 0.5
        )

        return {
            'correlation_curve': corr_by_dist,
            'correlation_length': float(correlation_length),
            'fit_type': fit_type,
            'r_squared': float(r_squared),
            'exponential_xi': float(xi_exp) if xi_exp < float('inf') else -1.0,
            'power_law_alpha': float(alpha_pow),
            'short_range_order': short_range_order,
            'long_range_order': long_range_order,
            'critical': critical,
            'n_data_points': len(valid),
            'max_distance': float(max_dist),
        }

    def compute_from_trajectory_3d(self, trajectory_3d: np.ndarray,
                                     bit_indices: Optional[List[int]] = None) -> Dict:
        """从 3D 轨迹计算空间关联

        Args:
            trajectory_3d: (T, 3) 3D 坐标轨迹
            bit_indices: 要分析的比特索引（None = 全部）
        """
        T = trajectory_3d.shape[0]
        if T < 10:
            return {'error': 'trajectory too short'}

        # 计算 3D 坐标的关联函数
        mean = trajectory_3d.mean(axis=0)
        centered = trajectory_3d - mean

        # 自关联函数
        max_lag = T // 4
        acf = []
        for dt in range(1, max_lag + 1):
            corr = (centered[dt:] * centered[:T - dt]).sum(axis=1).mean()
            acf.append(float(corr))

        acf = np.array(acf)
        lags = np.arange(1, max_lag + 1)

        # 归一化
        if acf[0] > 1e-10:
            acf = acf / acf[0]

        # 拟合关联长度
        valid = acf > 1e-10
        if valid.sum() >= 3:
            x = np.log(lags[valid])
            y = np.log(acf[valid])
            if x.std() > 0 and y.std() > 0:
                slope, intercept = np.polyfit(x, y, 1)
                xi = -1.0 / slope if slope < 0 else float('inf')
                ss_res = np.sum((y - slope * x - intercept) ** 2)
                ss_tot = np.sum((y - y.mean()) ** 2)
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
            else:
                xi = 0.0
                r2 = 0.0
        else:
            xi = 0.0
            r2 = 0.0

        return {
            'acf': acf.tolist(),
            'lags': lags.tolist(),
            'correlation_length_3d': float(xi) if xi < float('inf') else -1.0,
            'r_squared': float(r2),
        }

    def analyze_from_evolver_result(self, result: Dict,
                                     max_samples: int = 200) -> Dict:
        """从演化器结果分析"""
        if 'snapshots' not in result or not result['snapshots']:
            return {'error': 'no snapshots'}

        states = []
        for s in result['snapshots']:
            if hasattr(s, 'state'):
                states.append(s.state)
            else:
                states.append(s)

        if not states:
            return {'error': 'no valid snapshots'}

        traj = torch.stack(states, dim=0)
        return self.compute_spatial_correlation(traj, max_samples)
