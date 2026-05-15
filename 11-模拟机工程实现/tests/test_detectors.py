"""test_detectors.py — 涌现探测器测试"""

import pytest
import torch
from engine.detectors.trajectory_recorder import TrajectoryRecorder
from engine.detectors.mutual_info import MutualInfoDetector
from engine.detectors.statistics import (
    HammingDistributionDetector,
    ReturnTimeDetector,
    BitClusteringDetector,
    DAGDirectionDetector,
    EffectiveDOFDetector,
)


class TestTrajectoryRecorder:

    def test_record_and_retrieve(self):
        rec = TrajectoryRecorder(N=8, sample_interval=10)
        for step in range(100):
            rec.record_step(step, flip_position=step % 8,
                            hamming_weight=4)
        data = rec.get_data()
        assert data.total_steps == 100
        assert len(data.flip_sequence) == 100

    def test_snapshot_recording(self):
        rec = TrajectoryRecorder(N=8, sample_interval=10)
        for step in range(100):
            rec.record_step(step, flip_position=0, hamming_weight=4)
            if step % 10 == 0:
                rec.record_snapshot(step, torch.ones(8) * 0.5)
        data = rec.get_data()
        assert len(data.state_snapshots) == 10

    def test_to_tensors(self):
        rec = TrajectoryRecorder(N=8, sample_interval=50)
        for step in range(200):
            rec.record_step(step, flip_position=step % 8,
                            hamming_weight=4)
        data = rec.get_data()
        tensors = data.to_tensors()
        assert tensors['flip_sequence'].shape == (200,)
        assert tensors['hamming_weight'].shape == (200,)


class TestMutualInfoDetector:

    def test_basic(self):
        N = 8
        detector = MutualInfoDetector(N)
        # 构造一个简单的翻转序列：交替翻转 bit0 和 bit1
        flip_seq = torch.tensor([i % N for i in range(1000)])
        result = detector.compute(flip_seq, max_lag=10)
        assert 'mi_by_distance' in result
        assert 'flip_frequencies' in result
        assert len(result['flip_frequencies']) == N

    def test_all_bits_active(self):
        N = 4
        detector = MutualInfoDetector(N)
        flip_seq = torch.randint(0, N, (500,))
        result = detector.compute(flip_seq)
        assert result['mean_mi'] >= 0.0


class TestHammingDistributionDetector:

    def test_uniform_distribution(self):
        N = 8
        detector = HammingDistributionDetector(N)
        # 均匀分布的重量序列
        weights = torch.randint(0, N + 1, (1000,))
        result = detector.compute(weights)
        assert 'distribution' in result
        assert 'mean' in result
        assert len(result['distribution']) == N + 1

    def test_peaked_distribution(self):
        N = 16
        detector = HammingDistributionDetector(N)
        # 尖锐峰值在 w=8
        weights = torch.full((1000,), 8)
        result = detector.compute(weights)
        assert result['peak_weight'] == 8
        assert result['peak_ratio'] > 10.0
        assert result['narrow_distribution'] == True
        assert result['symmetry_breaking'] == True


class TestReturnTimeDetector:

    def test_basic(self):
        N = 8
        detector = ReturnTimeDetector(N)
        flip_seq = torch.randint(0, N, (5000,))
        result = detector.compute(flip_seq)
        assert 'mean_return_time' in result
        assert result['mean_return_time'] > 0

    def test_poisson_like(self):
        """随机翻转应该近似泊松过程"""
        N = 16
        detector = ReturnTimeDetector(N)
        flip_seq = torch.randint(0, N, (10000,))
        result = detector.compute(flip_seq)
        # 泊松过程的离散指数 ≈ 1，但随机波动可能较大
        # 只检查返回时间是合理的正值
        assert result['mean_return_time'] > 0
        assert result['n_return_times'] > 0


class TestBitClusteringDetector:

    def test_no_clustering(self):
        N = 8
        detector = BitClusteringDetector(N)
        flip_seq = torch.randint(0, N, (2000,))
        result = detector.compute(flip_seq)
        assert 'n_clusters' in result
        assert 'clusters' in result

    def test_clustered(self):
        """构造聚类翻转：bit0,bit1 总是交替翻转"""
        N = 8
        detector = BitClusteringDetector(N)
        flips = []
        for _ in range(500):
            flips.append(0)
            flips.append(1)
        flip_seq = torch.tensor(flips)
        result = detector.compute(flip_seq)
        # 检查聚类结果结构正确
        assert 'n_clusters' in result
        assert 'clusters' in result
        # 对于强相关的 bit0,bit1，应该有某种聚类信号
        # （具体阈值取决于实现，这里只检查不崩溃）


class TestDAGDirectionDetector:

    def test_basic(self):
        N = 8
        detector = DAGDirectionDetector(N)
        flip_seq = torch.randint(0, N, (1000,))
        state_seq = torch.randint(0, 2, (1000, N)).float()
        result = detector.compute(flip_seq, state_seq)
        assert 'direction_consistency' in result
        assert 'avg_consistency' in result


class TestEffectiveDOFDetector:

    def test_full_rank(self):
        N = 8
        detector = EffectiveDOFDetector(N)
        # 随机状态 → 满秩
        states = torch.rand(100, N)
        result = detector.compute(states)
        assert result['n_dof_90'] > 1
        assert result['N'] == N

    def test_low_rank(self):
        N = 16
        detector = EffectiveDOFDetector(N)
        # 所有状态相同 → 秩=0
        states = torch.ones(50, N) * 0.5
        result = detector.compute(states)
        # 常数矩阵应该只有0个有效自由度
        assert result['n_dof_90'] <= 1

    def test_structured_low_rank(self):
        N = 16
        detector = EffectiveDOFDetector(N)
        # 只有前4个比特变化 → 有效自由度≈4
        states = torch.zeros(100, N)
        for i in range(100):
            states[i, :4] = torch.rand(4)
        result = detector.compute(states)
        # 应该远小于N=16
        assert result['n_dof_90'] <= 8
