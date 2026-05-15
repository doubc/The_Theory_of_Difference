"""
engine/detectors/ — 涌现统计量探测器集

hamming_distribution.py — 汉明重量分布 P(w)
return_time.py         — 返回时间分布 τ
bit_clustering.py      — 活跃比特聚类
dag_direction.py       — DAG方向一致性
effective_dof.py       — 有效自由度
control_experiment.py  — 对照实验框架
"""

# ============================================================
# hamming_distribution.py
# ============================================================

import torch
import numpy as np
from typing import Dict
from math import comb


class HammingDistributionDetector:
    """汉明重量分布探测器"""

    def __init__(self, N: int):
        self.N = N

    def compute(self, hamming_weight_sequence: torch.Tensor) -> Dict:
        """计算汉明重量分布及统计特征"""
        T = hamming_weight_sequence.shape[0]
        if T == 0:
            return {'error': 'empty sequence'}

        # 分布直方图
        hist = torch.zeros(self.N + 1)
        for w in hamming_weight_sequence:
            hist[w.long().item()] += 1.0
        hist = hist / T

        # 统计量
        weights = hamming_weight_sequence.float()
        mean_w = weights.mean().item()
        std_w = weights.std().item()

        # 与理论二项分布 B(N, 0.5) 的对比（无约束随机游走）
        p = 0.5
        theoretical = torch.tensor(
            [comb(self.N, w) * p**self.N for w in range(self.N + 1)],
            dtype=torch.float32
        )

        # KL 散度 D_KL(P_empirical || P_theoretical)
        kl_div = (hist * (hist.clamp(min=1e-8).log() - theoretical.clamp(min=1e-8).log())).sum().item()

        # 峰度（尖锐度）
        if std_w > 0:
            kurtosis = ((weights - mean_w)**4).mean().item() / std_w**4 - 3.0
        else:
            kurtosis = 0.0

        # 峰值位置
        peak_w = hist.argmax().item()
        peak_ratio = hist[peak_w].item() / hist.mean().item()

        # 信号检测
        symmetry_breaking = peak_ratio > 2.0 and abs(peak_w - self.N // 2) < self.N // 4
        narrow_distribution = std_w < self.N * 0.15  # 比二项分布窄

        return {
            'distribution': hist.tolist(),
            'mean': mean_w,
            'std': std_w,
            'kurtosis': kurtosis,
            'peak_weight': peak_w,
            'peak_ratio': peak_ratio,
            'kl_divergence': kl_div,
            'symmetry_breaking': symmetry_breaking,
            'narrow_distribution': narrow_distribution,
        }


# ============================================================
# return_time.py
# ============================================================

class ReturnTimeDetector:
    """返回时间分布探测器"""

    def __init__(self, N: int):
        self.N = N

    def compute(self, flip_sequence: torch.Tensor,
                max_return_time: int = 1000) -> Dict:
        """计算每个比特的返回时间分布"""
        T = flip_sequence.shape[0]
        if T < 100:
            return {'error': 'sequence too short'}

        # 对每个比特，计算连续两次翻转之间的时间间隔
        return_times = {i: [] for i in range(self.N)}
        last_flip = {i: -1 for i in range(self.N)}

        for t in range(T):
            pos = flip_sequence[t].item()
            if 0 <= pos < self.N:
                if last_flip[pos] >= 0:
                    rt = t - last_flip[pos]
                    if rt <= max_return_time:
                        return_times[pos].append(rt)
                last_flip[pos] = t

        # 合并所有比特的返回时间
        all_return_times = []
        for i in range(self.N):
            all_return_times.extend(return_times[i])

        if not all_return_times:
            return {'error': 'no return times found'}

        rt_tensor = torch.tensor(all_return_times, dtype=torch.float32)

        # 统计量
        mean_rt = rt_tensor.mean().item()
        std_rt = rt_tensor.std().item()
        median_rt = rt_tensor.median().item()

        # 幂律检验：log-log 线性回归
        # 分箱统计
        max_rt = min(int(rt_tensor.max().item()), max_return_time)
        hist = torch.zeros(max_rt)
        for rt in all_return_times:
            if 1 <= rt <= max_rt:
                hist[int(rt) - 1] += 1.0
        hist = hist / hist.sum()

        # log-log 斜率（幂律指数）
        log_x = []
        log_y = []
        for i in range(max_rt):
            if hist[i] > 1e-8:
                log_x.append(np.log(i + 1))
                log_y.append(np.log(hist[i].item()))

        if len(log_x) >= 3:
            log_x = np.array(log_x)
            log_y = np.array(log_y)
            slope = np.corrcoef(log_x, log_y)[0, 1] * log_y.std() / log_x.std()
        else:
            slope = 0.0

        # 泊松检验：均值 ≈ 方差（泊松分布特征）
        dispersion = std_rt**2 / max(mean_rt, 1e-8)  # 离散指数
        poisson_like = 0.5 < dispersion < 2.0  # 接近1 = 泊松
        power_law_like = slope < -1.0 and slope > -3.0  # 幂律范围

        return {
            'mean_return_time': mean_rt,
            'std_return_time': std_rt,
            'median_return_time': median_rt,
            'power_law_slope': float(slope),
            'dispersion_index': float(dispersion),
            'poisson_like': poisson_like,
            'power_law_like': power_law_like,
            'n_return_times': len(all_return_times),
        }


# ============================================================
# bit_clustering.py
# ============================================================

class BitClusteringDetector:
    """活跃比特聚类探测器"""

    def __init__(self, N: int):
        self.N = N

    def compute(self, flip_sequence: torch.Tensor,
                window_size: int = 1000) -> Dict:
        """基于翻转相关性对比特进行聚类（向量化版本）"""
        T = flip_sequence.shape[0]
        if T < window_size:
            return {'error': 'sequence too short'}

        # 构建翻转矩阵 (T, N) - 向量化
        flip_matrix = torch.zeros(T, self.N, device=flip_sequence.device)
        valid_mask = (flip_sequence >= 0) & (flip_sequence < self.N)
        valid_indices = flip_sequence[valid_mask].long()
        valid_times = torch.arange(T, device=flip_sequence.device)[valid_mask]
        flip_matrix[valid_times, valid_indices] = 1.0

        # 向量化计算相关性矩阵
        # 标准化
        mean = flip_matrix.mean(dim=0, keepdim=True)
        std = flip_matrix.std(dim=0, keepdim=True).clamp(min=1e-8)
        normalized = (flip_matrix - mean) / std
        corr_matrix = (normalized.T @ normalized) / T
        corr_matrix = corr_matrix.cpu()

        # 简单聚类：相关性 > 阈值的比特归为一组
        threshold = 0.1
        visited = set()
        clusters = []
        for i in range(self.N):
            if i in visited:
                continue
            cluster = [i]
            visited.add(i)
            for j in range(self.N):
                if j not in visited and abs(corr_matrix[i, j].item()) > threshold:
                    cluster.append(j)
                    visited.add(j)
            if len(cluster) >= 2:
                clusters.append(cluster)

        n_clusters = len(clusters)
        max_cluster_size = max(len(c) for c in clusters) if clusters else 0
        avg_cluster_size = np.mean([len(c) for c in clusters]) if clusters else 0
        clustered_bits = sum(len(c) for c in clusters)
        cluster_ratio = clustered_bits / self.N
        significant_clusters = cluster_ratio > 0.2 and max_cluster_size >= 3

        return {
            'n_clusters': n_clusters,
            'clusters': clusters,
            'max_cluster_size': max_cluster_size,
            'avg_cluster_size': float(avg_cluster_size),
            'cluster_ratio': float(cluster_ratio),
            'significant_clusters': significant_clusters,
        }


# ============================================================
# dag_direction.py
# ============================================================

class DAGDirectionDetector:
    """DAG方向一致性探测器"""

    def __init__(self, N: int):
        self.N = N

    def compute(self, flip_sequence: torch.Tensor,
                state_sequence: torch.Tensor,
                sample_interval: int = 1) -> Dict:
        """检测DAG方向的一致性

        Args:
            flip_sequence: (T,) 翻转位置
            state_sequence: (T', N) 状态序列（可以是降采样的）
            sample_interval: 状态序列的采样间隔（用于对齐）
        """
        T = flip_sequence.shape[0]
        T_s = state_sequence.shape[0]
        if T < 100:
            return {'error': 'sequence too short'}

        # 将翻转序列降采样到与状态序列相同的分辨率
        # 或者将状态序列插值到翻转序列的分辨率
        # 简化：使用状态序列的分辨率
        if T_s < 2:
            return {'error': 'state sequence too short'}

        # 计算每个状态采样点之间的翻转方向
        n_0_to_1 = torch.zeros(self.N)
        n_1_to_0 = torch.zeros(self.N)

        # 计算每个采样区间内的翻转
        interval = max(1, T // T_s)
        for s_idx in range(min(T_s - 1, T // interval)):
            t_start = s_idx * interval
            t_end = min((s_idx + 1) * interval, T - 1)

            for t in range(t_start, t_end):
                if t + 1 >= T:
                    break
                pos = flip_sequence[t].item()
                if 0 <= pos < self.N:
                    # 用状态序列判断方向
                    if s_idx + 1 < T_s:
                        s_before = state_sequence[s_idx, pos] if state_sequence.dim() > 1 else state_sequence[s_idx]
                        s_after = state_sequence[s_idx + 1, pos] if state_sequence.dim() > 1 else state_sequence[s_idx + 1]
                        if s_before < 0.5 and s_after > 0.5:
                            n_0_to_1[pos] += 1
                        elif s_before > 0.5 and s_after < 0.5:
                            n_1_to_0[pos] += 1

        # 方向一致性：|0→1 - 1→0| / (0→1 + 1→0)
        total = n_0_to_1 + n_1_to_0
        direction_consistency = torch.zeros(self.N)
        for i in range(self.N):
            if total[i] > 0:
                direction_consistency[i] = abs(n_0_to_1[i] - n_1_to_0[i]) / total[i]

        # 整体一致性
        active_bits = (total > 10).sum().item()
        if active_bits > 0:
            avg_consistency = direction_consistency[total > 10].mean().item()
        else:
            avg_consistency = 0.0

        # 单向流检测：一致性 > 0.8 的比特比例
        unidirectional = (direction_consistency > 0.8).sum().item() / self.N

        # 信号：显著的时间箭头
        time_arrow = unidirectional > 0.3 and avg_consistency > 0.6

        return {
            'direction_consistency': direction_consistency.tolist(),
            'avg_consistency': float(avg_consistency),
            'unidirectional_ratio': float(unidirectional),
            'n_0_to_1': n_0_to_1.tolist(),
            'n_1_to_0': n_1_to_0.tolist(),
            'active_bits': int(active_bits),
            'time_arrow_detected': time_arrow,
        }


# ============================================================
# effective_dof.py
# ============================================================

class EffectiveDOFDetector:
    """有效自由度探测器"""

    def __init__(self, N: int):
        self.N = N

    def compute(self, state_snapshots: torch.Tensor) -> Dict:
        """用PCA分析有效自由度

        Args:
            state_snapshots: (n_snapshots, N) 状态快照矩阵
        """
        n = state_snapshots.shape[0]
        if n < 10:
            return {'error': 'too few snapshots'}

        # 中心化
        mean = state_snapshots.mean(dim=0, keepdim=True)
        centered = state_snapshots - mean

        # SVD（等价于PCA）
        try:
            # 添加微小噪声避免全零矩阵的数值问题
            centered = centered + torch.randn_like(centered) * 1e-10
            U, S, V = torch.svd(centered)
        except Exception as e:
            return {'error': f'SVD failed: {e}'}

        # 解释方差比例
        total_var = (S ** 2).sum()
        explained_var = (S ** 2) / total_var.clamp(min=1e-8)
        cumulative_var = torch.cumsum(explained_var, dim=0)

        # 有效自由度：解释90%方差所需的主成分数
        # 忽略极小的奇异值（绝对阈值）
        abs_threshold = S[0].item() * 0.01
        # 同时要求奇异值不能太小（至少为最大值的1%）
        # 如果最大值本身就很小（<1e-6），说明是常数矩阵
        if S[0].item() < 1e-6:
            n_dof_90 = 0
        else:
            n_dof_90 = (cumulative_var < 0.9).sum().item() + 1
        n_dof_95 = 0 if S[0].item() < 1e-6 else (cumulative_var < 0.95).sum().item() + 1
        n_dof_99 = 0 if S[0].item() < 1e-6 else (cumulative_var < 0.99).sum().item() + 1

        # 自由度压缩比
        compression_ratio = n_dof_90 / self.N if self.N > 0 else 1.0

        # 信号：有效自由度 << N
        low_dimensional = compression_ratio < 0.5 and n_dof_90 < self.N // 2

        return {
            'singular_values': S.tolist(),
            'explained_variance': explained_var.tolist(),
            'cumulative_variance': cumulative_var.tolist(),
            'n_dof_90': int(n_dof_90),
            'n_dof_95': int(n_dof_95),
            'n_dof_99': int(n_dof_99),
            'compression_ratio': float(compression_ratio),
            'low_dimensional': low_dimensional,
            'N': self.N,
        }


# ============================================================
# control_experiment.py
# ============================================================

class ControlExperiment:
    """对照实验框架

    运行4种条件，对比统计量差异：
    1. 实验组：九公理约束 + 源/汇通量
    2. 对照组1：无公理约束 + 相同源/汇（纯随机游走）
    3. 对照组2：有公理约束 + 无源/汇（封闭系统）
    4. 对照组3：无公理约束 + 无源/汇（纯随机封闭）
    """

    def __init__(self, N: int = 16, total_steps: int = 10000,
                 sample_interval: int = 100, device: str = "cpu"):
        self.N = N
        self.total_steps = total_steps
        self.sample_interval = sample_interval
        self.device = device

    def run_all(self, verbose: bool = True) -> Dict:
        """运行所有4种条件"""
        from layers.hamming_layer import HammingLattice, SourceSinkConfig
        from engine.long_range_evolver import LongRangeEvolver

        results = {}

        # 条件1：实验组（公理 + 通量）
        if verbose:
            print("=" * 60)
            print("Condition 1: Axioms + Source/Sink (Experimental)")
            print("=" * 60)
        config1 = SourceSinkConfig(n_sources=2, n_sinks=2,
                                   source_strength=2, sink_strength=2,
                                   dynamic_position=True)
        layer1 = HammingLattice(N=self.N, device=self.device,
                                use_strict_axioms=True, dag_enabled=True,
                                source_sink_config=config1)
        evolver1 = LongRangeEvolver(layer1, self.total_steps, self.sample_interval)
        results['experimental'] = evolver1.run(verbose=verbose)

        # 条件2：无公理 + 通量
        if verbose:
            print("\n" + "=" * 60)
            print("Condition 2: No Axioms + Source/Sink (Control)")
            print("=" * 60)
        config2 = SourceSinkConfig(n_sources=2, n_sinks=2,
                                   source_strength=2, sink_strength=2,
                                   dynamic_position=False)
        layer2 = HammingLattice(N=self.N, device=self.device,
                                use_strict_axioms=False, dag_enabled=False,
                                source_sink_config=config2)
        evolver2 = LongRangeEvolver(layer2, self.total_steps, self.sample_interval)
        results['no_axioms'] = evolver2.run(verbose=verbose)

        # 条件3：公理 + 无通量
        if verbose:
            print("\n" + "=" * 60)
            print("Condition 3: Axioms + No Flux (Closed)")
            print("=" * 60)
        config3 = SourceSinkConfig(n_sources=0, n_sinks=0,
                                   source_strength=0, sink_strength=0)
        layer3 = HammingLattice(N=self.N, device=self.device,
                                use_strict_axioms=True, dag_enabled=True,
                                source_sink_config=config3)
        evolver3 = LongRangeEvolver(layer3, self.total_steps, self.sample_interval)
        results['no_flux'] = evolver3.run(verbose=verbose)

        # 条件4：无公理 + 无通量
        if verbose:
            print("\n" + "=" * 60)
            print("Condition 4: No Axioms + No Flux (Random Closed)")
            print("=" * 60)
        config4 = SourceSinkConfig(n_sources=0, n_sinks=0,
                                   source_strength=0, sink_strength=0)
        layer4 = HammingLattice(N=self.N, device=self.device,
                                use_strict_axioms=False, dag_enabled=False,
                                source_sink_config=config4)
        evolver4 = LongRangeEvolver(layer4, self.total_steps, self.sample_interval)
        results['random_closed'] = evolver4.run(verbose=verbose)

        return results
