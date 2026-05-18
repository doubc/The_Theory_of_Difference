"""tests/test_gauge_spatial_detectors.py — P3+P4 探测器测试"""
import pytest
import torch
import numpy as np
from engine.detectors.gauge_field import GaugeFieldDetector
from engine.detectors.spatial_correlation import SpatialCorrelationDetector
from engine.spatial_evolver_v2 import SpatialLongRangeEvolver


class TestGaugeFieldDetector:

    def test_init(self):
        det = GaugeFieldDetector(N=24)
        assert det.N == 24
        assert det.mid_w == 12

    def test_N_must_be_even(self):
        with pytest.raises(ValueError):
            GaugeFieldDetector(N=25)

    def test_generate_mid_surface_states(self):
        det = GaugeFieldDetector(N=24)
        states = det.generate_mid_surface_states(10)
        assert len(states) == 10
        for s in states:
            assert s.sum().item() == 12

    def test_sample_mid_surface_from_trajectory(self):
        det = GaugeFieldDetector(N=24)
        # 构造包含中截面状态的轨迹
        traj = torch.zeros(100, 24)
        for t in range(100):
            if t % 2 == 0:
                traj[t, :12] = 1.0  # 中截面状态
            else:
                traj[t, :6] = 1.0   # 非中截面
        mid_states = det.sample_mid_surface_states(traj, max_samples=50)
        assert len(mid_states) > 0
        assert len(mid_states) <= 50

    def test_verify_CR1_on_state(self):
        det = GaugeFieldDetector(N=24)
        state = torch.zeros(24)
        state[:12] = 1.0  # 12 个 1
        result = det.verify_CR1_on_state(state)
        assert 'CR1_holds' in result

    def test_verify_CR2_on_state(self):
        det = GaugeFieldDetector(N=24)
        state = torch.zeros(24)
        state[:12] = 1.0
        result = det.verify_CR2_on_state(state)
        assert 'CR2_holds' in result

    def test_count_generators(self):
        det = GaugeFieldDetector(N=24)
        gen3 = det.count_generators(k=3)
        assert gen3['total_generators'] == 8
        assert gen3['algebra'] == 'su(3)'

        gen2 = det.count_generators(k=2)
        assert gen2['total_generators'] == 3
        assert gen2['algebra'] == 'su(2)'

    def test_analyze_mid_surface(self):
        det = GaugeFieldDetector(N=12)  # 小 N 加速
        traj = torch.zeros(20, 12)
        for t in range(20):
            traj[t, :6] = 1.0  # 中截面 w=6
        result = det.analyze_mid_surface(traj, max_samples=20)
        assert 'CR1_pass' in result
        assert 'su3_signal' in result
        assert result['n_mid_surface_states'] > 0

    def test_analyze_from_spatial_result(self):
        """从 SpatialEvolver 结果分析"""
        evolver = SpatialLongRangeEvolver(N=12, total_steps=200, sample_interval=20)
        result = evolver.run(verbose=False)
        det = GaugeFieldDetector(N=12)
        analysis = det.analyze_from_spatial_result(result)
        assert 'su3_signal' in analysis


class TestSpatialCorrelationDetector:

    def test_init(self):
        det = SpatialCorrelationDetector(N=24)
        assert det.N == 24
        assert det.n_per_group == 16  # default

    def test_bit_to_3d(self):
        det = SpatialCorrelationDetector(N=24, n_per_group=8)
        c0 = det.bit_to_3d(0)
        assert c0[0] > 0
        assert c0[1] == 0
        assert c0[2] == 0
        c8 = det.bit_to_3d(8)
        assert c8[0] == 0
        assert c8[1] > 0
        assert c8[2] == 0

    def test_compute_spatial_correlation(self):
        det = SpatialCorrelationDetector(N=12, n_per_group=4)
        # 构造相关轨迹：相邻比特倾向于同值
        traj = torch.zeros(50, 12)
        for t in range(50):
            val = torch.rand(1).item()
            for i in range(12):
                if torch.rand(1).item() < 0.7:
                    traj[t, i] = val
                else:
                    traj[t, i] = 1.0 - val
        result = det.compute_spatial_correlation(traj, max_samples=50)
        assert 'correlation_curve' in result
        assert 'correlation_length' in result
        assert 'fit_type' in result

    def test_compute_from_trajectory_3d(self):
        det = SpatialCorrelationDetector(N=12)
        traj_3d = np.random.randn(100, 3).cumsum(axis=0)
        result = det.compute_from_trajectory_3d(traj_3d)
        assert 'acf' in result
        assert 'correlation_length_3d' in result

    def test_short_range_order_detection(self):
        """短程有序：指数衰减关联"""
        det = SpatialCorrelationDetector(N=12, n_per_group=4)
        # 构造指数衰减关联的轨迹
        traj = torch.zeros(100, 12)
        for t in range(100):
            base = torch.rand(1).item()
            for i in range(12):
                # 相邻比特有高相关性，远端低相关
                prob = base * np.exp(-i * 0.3) + 0.5 * (1 - np.exp(-i * 0.3))
                traj[t, i] = 1.0 if torch.rand(1).item() < prob else 0.0
        result = det.compute_spatial_correlation(traj, max_samples=100)
        # 至少应该有合理的关联曲线
        assert len(result.get('correlation_curve', {})) > 0

    def test_analyze_from_evolver_result(self):
        """从 SpatialEvolver 结果分析"""
        evolver = SpatialLongRangeEvolver(N=12, total_steps=200, sample_interval=20)
        result = evolver.run(verbose=False)
        det = SpatialCorrelationDetector(N=12, n_per_group=4)
        analysis = det.analyze_from_evolver_result(result)
        assert 'correlation_curve' in analysis


class TestEndToEndSpatialDetection:

    def test_full_pipeline(self):
        """完整检测流程"""
        N = 24
        evolver = SpatialLongRangeEvolver(N=N, total_steps=500, sample_interval=50)
        result = evolver.run(verbose=False)

        # 维度锁定
        from engine.detectors.dimension_locking import DimensionLockingDetector
        dim_det = DimensionLockingDetector(N=N, n_per_group=N//3)
        dim_result = dim_det.analyze_from_evolver_result(result)
        assert 'pca' in dim_result

        # 规范场
        gauge_det = GaugeFieldDetector(N=N)
        gauge_result = gauge_det.analyze_from_spatial_result(result)
        assert 'su3_signal' in gauge_result

        # 空间关联
        corr_det = SpatialCorrelationDetector(N=N, n_per_group=N//3)
        corr_result = corr_det.analyze_from_evolver_result(result)
        assert 'correlation_curve' in corr_result
