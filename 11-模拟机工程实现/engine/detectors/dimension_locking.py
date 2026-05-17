"""
engine/detectors/dimension_locking.py — 维度锁定探测器

检测有效维度 D_eff。
理论预测：A1+A1'+A9 → D_eff = 3

方法：
1. 3D PCA：3 个主成分解释方差比 → D_eff ≈ 3 时前 3 个 PC 解释大部分方差
2. 均方位移 (MSD)：<r²(t)> ~ t^{2/D} → 拟合 D
"""

import torch
import numpy as np
from typing import Dict, Optional


class DimensionLockingDetector:
    """维度锁定探测器"""

    def __init__(self, N: int, n_per_group: int = 16, L: float = 1.0):
        """
        Args:
            N: 总比特数
            n_per_group: 每组比特数
            L: 嵌入空间尺寸
        """
        self.N = N
        self.n_per_group = n_per_group
        self.L = L
        self.epsilon = L / n_per_group

    def embed_state_3d(self, state: torch.Tensor) -> np.ndarray:
        """状态 → 3D 坐标"""
        coords = np.zeros(3)
        for k in range(3):
            start = k * self.n_per_group
            end = start + self.n_per_group
            coords[k] = self.epsilon * state[start:end].sum().item()
        return coords

    def compute_pca(self, trajectory_3d: np.ndarray) -> Dict:
        """3D PCA 分析

        Args:
            trajectory_3d: (T, 3) 3D 坐标轨迹

        Returns:
            dict with eigenvalues, explained_variance, D_eff
        """
        T = trajectory_3d.shape[0]
        if T < 10:
            return {'error': 'trajectory too short'}

        # 中心化
        mean = trajectory_3d.mean(axis=0)
        centered = trajectory_3d - mean

        # PCA
        cov = np.cov(centered.T)  # (3, 3)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)

        # 按特征值从大到小排序
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        # 解释方差比
        total_var = eigenvalues.sum()
        if total_var < 1e-12:
            return {'error': 'zero variance'}

        explained_var = eigenvalues / total_var
        cumulative_var = np.cumsum(explained_var)

        # 有效维度：解释 90% 方差所需的 PC 数
        n_dof_90 = int(np.searchsorted(cumulative_var, 0.90)) + 1
        n_dof_95 = int(np.searchsorted(cumulative_var, 0.95)) + 1

        # 维度锁定信号：前 3 个 PC 解释 > 80% 方差
        locked_3d = explained_var[:3].sum() > 0.80 if len(explained_var) >= 3 else False

        return {
            'eigenvalues': eigenvalues.tolist(),
            'explained_variance': explained_var.tolist(),
            'cumulative_variance': cumulative_var.tolist(),
            'n_dof_90': n_dof_90,
            'n_dof_95': n_dof_95,
            'locked_3d': locked_3d,
            'top3_variance_ratio': float(explained_var[:3].sum()) if len(explained_var) >= 3 else 0.0,
        }

    def compute_msd(self, trajectory_3d: np.ndarray,
                    max_lag: Optional[int] = None) -> Dict:
        """均方位移分析

        <r²(t)> = <|x(t) - x(0)|²> ~ t^{2/D}

        Args:
            trajectory_3d: (T, 3)
            max_lag: 最大时间延迟
        """
        T = trajectory_3d.shape[0]
        if T < 20:
            return {'error': 'trajectory too short'}

        if max_lag is None:
            max_lag = T // 4

        max_lag = min(max_lag, T // 2)

        # 计算 MSD
        msd = []
        for dt in range(1, max_lag + 1):
            displacements = trajectory_3d[dt:] - trajectory_3d[:T - dt]
            sq_dist = (displacements ** 2).sum(axis=1)
            msd.append(float(sq_dist.mean()))

        msd = np.array(msd)
        lags = np.arange(1, max_lag + 1)

        # 拟合 MSD ~ t^{2/D}
        # log(MSD) = (2/D) * log(t) + C
        valid = msd > 1e-12
        if valid.sum() >= 5:
            log_t = np.log(lags[valid])
            log_msd = np.log(msd[valid])

            if log_t.std() > 0 and log_msd.std() > 0:
                slope, intercept = np.polyfit(log_t, log_msd, 1)
                D_eff = 2.0 / slope if slope > 0 else float('inf')
                r_squared = 1.0 - np.sum((log_msd - slope * log_t - intercept) ** 2) / np.sum((log_msd - log_msd.mean()) ** 2)
                r_squared = float(np.clip(r_squared, 0.0, 1.0))
            else:
                D_eff = 0.0
                r_squared = 0.0
                slope = 0.0
        else:
            D_eff = 0.0
            r_squared = 0.0
            slope = 0.0

        # 维度锁定：D_eff ≈ 3
        dimension_locked = 2.0 < D_eff < 4.0 and r_squared > 0.5

        return {
            'msd': msd.tolist(),
            'lags': lags.tolist(),
            'D_eff': float(D_eff),
            'power_slope': float(slope),
            'r_squared': float(r_squared),
            'dimension_locked': dimension_locked,
        }

    def analyze(self, trajectory: torch.Tensor) -> Dict:
        """完整分析：从比特轨迹到维度检测

        Args:
            trajectory: (T, N) 比特状态轨迹
        """
        T = trajectory.shape[0]

        # 转换为 3D 坐标
        traj_3d = np.array([self.embed_state_3d(trajectory[t]) for t in range(T)])

        pca_result = self.compute_pca(traj_3d)
        msd_result = self.compute_msd(traj_3d)

        return {
            'pca': pca_result,
            'msd': msd_result,
            'D_estimate_pca': pca_result.get('n_dof_90', 0),
            'D_estimate_msd': msd_result.get('D_eff', 0),
            'dimension_locked': pca_result.get('locked_3d', False) or msd_result.get('dimension_locked', False),
        }

    def analyze_from_evolver_result(self, result: Dict) -> Dict:
        """从演化器结果分析"""
        if 'snapshots' not in result or not result['snapshots']:
            return {'error': 'no snapshots'}
        traj = torch.stack([s.state for s in result['snapshots']], dim=0)
        return self.analyze(traj)
