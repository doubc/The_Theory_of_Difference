"""
dimension_locking_v2.py — 维度锁定探测器 V2

用 3D 坐标 PCA 替代原始 72 维状态空间 PCA，
直接测量嵌入几何的维度而非状态空间的独立模式数。

背景：exp_146 中 D_eff=18.5 与理论预期 D_eff≈3 的差异
根因为方法论不匹配 —— 72 维状态空间 PCA 测量的是系统自由度数量，
而理论预测的是 3D 汉明格嵌入几何的维度。

详见 docs/dimension_locking_methodology_analysis.md
"""

import math
import torch
import numpy as np
from typing import Dict, List, Optional, Tuple


# =====================================================================
# Section 4.1 — 3D 坐标 PCA（主修复）
# =====================================================================

class DimensionLockingDetectorV2:
    """维度锁定探测器 V2

    在 3D 嵌入坐标上执行 PCA，直接测量系统在嵌入几何中的有效维度。
    使用参与比（participation ratio）和各向异性比（anisotropy ratio）
    作为主要诊断指标，而非简单的主成分计数。

    Example:
        >>> detector = DimensionLockingDetectorV2(N=72)
        >>> snapshots = torch.randint(0, 2, (40, 72), dtype=torch.float32)
        >>> result = detector.detect(snapshots)
        >>> result['dimension_locked_3']  # True/False
    """

    def __init__(self, N: int, device: str = "cpu"):
        """
        Args:
            N: 比特数（必须是 3 的倍数）
            device: 计算设备
        """
        if N % 3 != 0:
            raise ValueError(f"N 必须是 3 的倍数，当前 N={N}")
        self.N = N
        self.device = device
        from layers.three_dim_hamming import ThreeDimHammingLattice
        self.lattice = ThreeDimHammingLattice(N=N, device=device)

    def detect(self, state_snapshots: torch.Tensor) -> Dict:
        """在 3D 嵌入坐标上 PCA 分析维度锁定

        Args:
            state_snapshots: (n_snapshots, N) 二值状态快照矩阵

        Returns:
            dict 维度锁定诊断结果
        """
        n = state_snapshots.shape[0]
        if n < 10:
            return {'error': 'too few snapshots', 'dimension_locked_3': False}

        # 1. 将所有状态映射到 3D 坐标
        coords = self.lattice.embed_3d(state_snapshots)  # (n, 3)

        # 2. 中心化
        mean = coords.mean(dim=0, keepdim=True)
        centered = coords - mean

        # 3. SVD 分解 (n, 3) 矩阵
        try:
            centered = centered + torch.randn_like(centered) * 1e-10
            U, S, V = torch.svd(centered)
        except Exception as e:
            return {'error': f'SVD failed: {e}', 'dimension_locked_3': False}

        # 4. 协方差矩阵的特征值
        eigenvalues = (S ** 2) / (n - 1)
        total_var = eigenvalues.sum()
        explained = eigenvalues / total_var.clamp(min=1e-10)

        # 5. 参与比 PR = (sum(lambda))^2 / sum(lambda^2)
        #    PR 在 [1, 3] 之间，3 表示各向同性 3D 探索
        pr = (eigenvalues.sum() ** 2) / (eigenvalues ** 2).sum().clamp(min=1e-10)
        pr = pr.item()

        # 6. 各向异性比 = 最小特征值 / 最大特征值
        #    接近 1 = 各向同性，接近 0 = 退化（降维）
        sorted_eigs = eigenvalues.sort(descending=True).values
        anisotropy = (sorted_eigs[-1] / sorted_eigs[0].clamp(min=1e-10)).item()

        # 7. 3D 坐标有效自由度（累计方差 > 95%）
        cumvar = torch.cumsum(explained, dim=0)
        d_eff_coord = (cumvar < 0.95).sum().item() + 1

        # 8. 关键诊断信息
        coord_std = coords.std(dim=0)

        # 9. 维度锁定判决
        #    条件：所有 3 维活跃 AND 参与比 > 2.0 AND 各向异性 > 0.05
        dimension_locked = (
            d_eff_coord >= 3
            and pr > 2.0
            and anisotropy > 0.05
        )

        return {
            'D_eff_3d': d_eff_coord,
            'participation_ratio': pr,
            'anisotropy_ratio': anisotropy,
            'eigenvalues': eigenvalues.tolist(),
            'explained_variance': explained.tolist(),
            'cumulative_variance': cumvar.tolist(),
            'coord_mean': mean.squeeze(0).tolist(),
            'coord_std': coord_std.tolist(),
            'n_snapshots': n,
            'dimension_locked_3': dimension_locked,
        }


# =====================================================================
# Section 4.2 — 关联维 D_2（互补非线性探针）
# =====================================================================

def correlation_dimension_3d(state_snapshots: torch.Tensor,
                              N: int,
                              r_values: Optional[List[float]] = None,
                              device: str = "cpu") -> Dict:
    """计算 3D 嵌入空间的 Grassberger-Procaccia 关联维 D_2

    关联维测量轨迹在嵌入空间中填充的拓扑维数：
    - D_2 ≈ 3：轨迹填满整个 3D 空间（各向同性扩散）
    - D_2 < 3：轨迹被约束在低维子流形上（曲面/曲线）
    - D_2 ≈ 0：轨迹收敛到固定点

    Args:
        state_snapshots: (n_snapshots, N) 二值状态快照矩阵
        N: 比特数（必须是 3 的倍数）
        r_values: 距离阈值列表（自动生成若为 None）
        device: 计算设备

    Returns:
        dict: {'D_2', 'r_values', 'C_values', 'dimension_locked'}
    """
    from layers.three_dim_hamming import ThreeDimHammingLattice
    lattice = ThreeDimHammingLattice(N=N, device=device)

    # 映射到 3D 坐标
    coords = lattice.embed_3d(state_snapshots)  # (n, 3)
    n = coords.shape[0]
    if n < 5:
        return {'D_2': -1.0, 'error': 'too few snapshots', 'dimension_locked': False}

    # 成对欧氏距离
    diff = coords.unsqueeze(0) - coords.unsqueeze(1)  # (n, n, 3)
    dists = (diff ** 2).sum(dim=-1).sqrt()  # (n, n)

    # 提取上三角（排除自身对）
    mask = torch.triu(torch.ones(n, n, device=device), diagonal=1).bool()
    upper_dists = dists[mask]

    if upper_dists.numel() < 2:
        return {'D_2': -1.0, 'error': 'too few pairs', 'dimension_locked': False}

    # 自动生成距离阈值
    if r_values is None:
        eps = 1e-6
        r_min = max(upper_dists.min().item(), eps)
        r_max = upper_dists.max().item()
        r_values = torch.logspace(
            math.log10(r_min),
            math.log10(r_max),
            steps=20
        ).tolist()

    # 关联积分 C(r) = 距离 < r 的对数 / 总对数
    C_values = []
    n_pairs = len(upper_dists)
    for r in r_values:
        C = (upper_dists < r).sum().item() / n_pairs
        C_values.append(C)

    # 从 log-log 斜率估计 D_2：C(r) ~ r^{D_2}
    # 在标度区（C ∈ [1e-4, 0.9]）做线性回归
    log_r = []
    log_C = []
    for r, C in zip(r_values, C_values):
        if 1e-8 < C < 0.9:
            log_r.append(math.log(r))
            log_C.append(math.log(C))

    D_2 = -1.0
    if len(log_r) >= 3:
        lr = np.array(log_r)
        lC = np.array(log_C)
        # 斜率
        slope = np.corrcoef(lr, lC)[0, 1] * lC.std() / lr.std()
        D_2 = float(slope)

    return {
        'D_2': D_2,
        'r_values': r_values,
        'C_values': C_values,
        'n_snapshots': n,
        'n_pairs': n_pairs,
        'dimension_locked': 2.0 < D_2 < 4.5,
        'scaling_region_points': len(log_r),
    }


# =====================================================================
# Section 4.3 — 零模型比较
# =====================================================================

def dimension_null_comparison(state_snapshots: torch.Tensor,
                               N: int,
                               n_null_steps: int = 2000,
                               n_null_seeds: int = 5,
                               device: str = "cpu") -> Dict:
    """比较实际 D_eff 与 3D 格点随机游走和自由随机游走的零模型

    通过对比，判断系统动力学是否与 3D 汉明格几何一致：
    - ratio_3d ≈ 1.0：实际与 3D 模型一致
    - ratio_random << 1.0：实际比自由随机游走更受约束

    Args:
        state_snapshots: (n_snapshots, N) 实际轨迹快照
        N: 比特数（必须是 3 的倍数）
        n_null_steps: 零模型模拟步数
        n_null_seeds: 零模型模拟种子数
        device: 计算设备

    Returns:
        dict: {'D_eff_actual', 'D_eff_3d_null', 'D_eff_random_null', ...}
    """
    from engine.detectors.statistics import EffectiveDOFDetector

    detector = EffectiveDOFDetector(N=N)
    n_snapshots = state_snapshots.shape[0]

    # 实际 D_eff
    actual_result = detector.compute(state_snapshots)
    if 'error' in actual_result:
        return {'error': f'actual compute failed: {actual_result["error"]}'}
    D_eff_actual = actual_result['n_dof_90']

    # 零模型 1：3D 汉明格随机游走（单比特翻转）
    D_eff_3d_nulls = []
    for seed in range(n_null_seeds):
        torch.manual_seed(seed + 10000)
        state = torch.zeros(N, device=device)
        state[:N // 2] = 1.0  # 从半满状态开始
        snapshots = []
        for step in range(n_null_steps):
            idx = torch.randint(0, N, (1,), device=device).item()
            state[idx] = 1.0 - state[idx]
            if step % (n_null_steps // n_snapshots) == 0:
                snapshots.append(state.clone())
        if len(snapshots) >= 10:
            null_tensor = torch.stack(snapshots[:n_snapshots]).to(device)
            r = detector.compute(null_tensor)
            if 'error' not in r:
                D_eff_3d_nulls.append(r['n_dof_90'])

    # 零模型 2：无约束随机游走（多比特翻转）
    D_eff_random_nulls = []
    for seed in range(n_null_seeds):
        torch.manual_seed(seed + 20000)
        state = torch.zeros(N, device=device)
        state[:N // 2] = 1.0
        snapshots = []
        for step in range(n_null_steps):
            n_flip = torch.randint(1, 4, (1,)).item()
            for _ in range(n_flip):
                idx = torch.randint(0, N, (1,), device=device).item()
                state[idx] = 1.0 - state[idx]
            if step % (n_null_steps // n_snapshots) == 0:
                snapshots.append(state.clone())
        if len(snapshots) >= 10:
            null_tensor = torch.stack(snapshots[:n_snapshots]).to(device)
            r = detector.compute(null_tensor)
            if 'error' not in r:
                D_eff_random_nulls.append(r['n_dof_90'])

    D_eff_3d_null = float(np.mean(D_eff_3d_nulls)) if D_eff_3d_nulls else -1.0
    D_eff_random_null = float(np.mean(D_eff_random_nulls)) if D_eff_random_nulls else -1.0

    return {
        'D_eff_actual': D_eff_actual,
        'D_eff_3d_null': D_eff_3d_null,
        'D_eff_random_null': D_eff_random_null,
        'ratio_3d': D_eff_actual / max(1.0, D_eff_3d_null),
        'ratio_random': D_eff_actual / max(1.0, D_eff_random_null),
        'matches_3d_null': abs(D_eff_actual - D_eff_3d_null) < 5,
        'below_random': D_eff_actual < D_eff_random_null * 0.8,
    }


# =====================================================================
# 便捷函数：一站式维度锁定分析
# =====================================================================

def full_dimension_analysis(state_snapshots: torch.Tensor,
                             N: int,
                             device: str = "cpu") -> Dict:
    """运行所有三种维度锁定的互补测量

    返回一站式诊断结果，包含原始 72 维 PCA、3D 坐标 PCA、
    关联维 D_2 和零模型比较的汇总。

    Args:
        state_snapshots: (n_snapshots, N) 二值状态快照矩阵
        N: 比特数（必须是 3 的倍数）
        device: 计算设备

    Returns:
        dict: 综合维度锁定诊断结果
    """
    from engine.detectors.statistics import EffectiveDOFDetector

    results = {}

    # 1. 原始 72 维 PCA（二级指标，保留向后兼容）
    ef_detector = EffectiveDOFDetector(N=N)
    raw_result = ef_detector.compute(state_snapshots)
    if 'error' not in raw_result:
        results['raw_pca'] = {
            'D_eff_90': raw_result['n_dof_90'],
            'compression_ratio': raw_result['compression_ratio'],
        }

    # 2. 3D 坐标 PCA（主指标）
    v2_detector = DimensionLockingDetectorV2(N=N, device=device)
    coord_result = v2_detector.detect(state_snapshots)
    if 'error' not in coord_result:
        results['coord_pca'] = {
            'D_eff_3d': coord_result['D_eff_3d'],
            'participation_ratio': coord_result['participation_ratio'],
            'anisotropy_ratio': coord_result['anisotropy_ratio'],
            'coord_std': coord_result['coord_std'],
            'dimension_locked': coord_result['dimension_locked_3'],
        }

    # 3. 关联维 D_2（互补非线性探针）
    cd_result = correlation_dimension_3d(
        state_snapshots, N=N, device=device
    )
    if 'error' not in cd_result:
        results['correlation_dim'] = {
            'D_2': cd_result['D_2'],
            'dimension_locked': cd_result.get('dimension_locked', False),
        }

    # 4. 综合判决
    coord_locked = results.get('coord_pca', {}).get('dimension_locked', False)
    cd_locked = results.get('correlation_dim', {}).get('dimension_locked', False)

    results['verdict'] = {
        'dimension_locked': coord_locked and cd_locked,
        'coord_pca_pass': coord_locked,
        'correlation_dim_pass': cd_locked,
        'n_measurements': 2,
        'n_passed': int(coord_locked) + int(cd_locked),
    }

    return results
