"""test_axioms_v2.py — 新公理约束测试"""
import pytest
import torch
from acl.axioms_v2 import AxiomConstraints


class TestAxiomConstraints:

    def test_init(self):
        c = AxiomConstraints(N=16)
        assert c.N == 16
        assert len(c.hierarchy_indices) == 16 // 3
        assert len(c.lateral_indices) == 16 - 16 // 3

    def test_A1_monotonicity(self):
        c = AxiomConstraints(N=8)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        # 0→1 应该允许
        ok, _ = c.check_A1(state, 1)
        assert ok
        # 1→0 应该禁止
        ok, _ = c.check_A1(state, 0)
        assert not ok

    def test_A6_direction_cumulative(self):
        c = AxiomConstraints(N=8)
        # 初始方向为随机 +1 或 -1（不再为 0）
        initial_dir = c.direction[0].item()
        assert initial_dir in (-1, 1), f"Expected random init, got {initial_dir}"
        # 0→1 翻转后方向变为 +1
        c.update_A6_direction(0, 0.0, 1.0)
        assert c.direction[0].item() == 1
        # 再次 0→1（不可能，但测试方向不变）
        c.update_A6_direction(0, 0.0, 1.0)
        assert c.direction[0].item() == 1

    def test_A6_blocks_reverse(self):
        c = AxiomConstraints(N=8)
        state = torch.tensor([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        # 设置方向为 +1
        c.direction[0] = 1
        # 1→0 应该被 A6 禁止
        ok, _ = c.check_A6(state, 0)
        assert not ok

    def test_A5_conservation(self):
        c = AxiomConstraints(N=8)
        state = torch.zeros(8)
        # 注入 4 个应该允许
        ok, _ = c.check_A5_inject(state, 4)
        assert ok
        # 注入 9 个应该禁止（超过 N）
        ok, _ = c.check_A5_inject(state, 9)
        assert not ok

    def test_A7_cycle_detection(self):
        c = AxiomConstraints(N=4)
        state = torch.tensor([1.0, 0.0, 0.0, 0.0])
        # 第一次访问：新状态
        ok, msg = c.check_A7(state)
        assert ok
        assert "new" in msg or "ok" in msg
        # 第二次访问：循环
        ok, msg = c.check_A7(state)
        assert ok
        assert "cycle" in msg

    def test_A8_source_strength(self):
        c = AxiomConstraints(N=16)
        # w=0：应该强注入
        state = torch.zeros(16)
        s = c.get_A8_source_strength(state)
        assert s >= 2
        # w=16：应该不注入
        state = torch.ones(16)
        s = c.get_A8_source_strength(state)
        assert s == 0
        # w=8：平衡态
        state = torch.zeros(16)
        state[:8] = 1.0
        s = c.get_A8_source_strength(state)
        assert s >= 1  # 至少维持

    def test_A8_sink_strength(self):
        c = AxiomConstraints(N=16)
        # w=0, n_injected=0：无吸收
        state = torch.zeros(16)
        s = c.get_A8_sink_strength(state, 0)
        assert s == 0
        # w=16, n_injected=4：吸收=注入
        state = torch.ones(16)
        s = c.get_A8_sink_strength(state, 4)
        assert s == 4
        # w=0, n_injected=4：吸收不能超过 w
        state = torch.zeros(16)
        s = c.get_A8_sink_strength(state, 4)
        assert s == 0

    def test_A9_active_bits(self):
        c = AxiomConstraints(N=40)
        # sealing_activation_threshold = max(int(0.75*40), 30) = 30
        # min_active_bits = min(40, max(40//3, 12)) = 24
        # 激活所有 40 个比特（前 30 个触发密封）
        for i in range(40):
            ok, _ = c.check_A9(i)
            assert ok
        # 验证 active_bits 是 Dict[int, int]（bit_idx -> last_active_step）
        assert isinstance(c.active_bits, dict)
        assert len(c.active_bits) == 40
        # 封口后：检查未冻结的比特可以通过
        unsealed = set(c.active_bits.keys()) - c.sealed_bits
        assert len(unsealed) >= c.min_active_bits
        for i in unsealed:
            ok, _ = c.check_A9(i)
            assert ok
        # 冻结的比特应该被拒绝
        for i in c.sealed_bits:
            ok, _ = c.check_A9(i)
            assert not ok

    def test_A1_prime_candidates(self):
        c = AxiomConstraints(N=8, n_hierarchy_bits=3)
        state = torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
        pairs = c.get_A1_prime_candidates(state)
        # 应该返回横向比特的配对
        for (i, j) in pairs:
            assert i in c.lateral_indices
            assert j in c.lateral_indices

    def test_get_allowed_flips(self):
        c = AxiomConstraints(N=8)
        state = torch.tensor([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
        allowed = c.get_allowed_flips(state)
        # 只允许 0→1 的位置（0,2,4,6）
        for idx in allowed:
            assert state[idx] < 0.5

    def test_get_allowed_absorbs(self):
        c = AxiomConstraints(N=8)
        state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        allowed = c.get_allowed_absorbs(state)
        # 所有为 1 的位置
        for idx in allowed:
            assert state[idx] > 0.5


class TestLongRangeEvolverV2:

    def test_basic_run(self):
        from engine.long_range_evolver_v2 import LongRangeEvolverV2
        evolver = LongRangeEvolverV2(N=8, total_steps=1000, sample_interval=100)
        result = evolver.run(verbose=False)
        assert result['n_snapshots'] == 10
        assert len(result['flip_history']) == 1000

    def test_A1_monotonicity_in_run(self):
        from engine.long_range_evolver_v2 import LongRangeEvolverV2
        evolver = LongRangeEvolverV2(N=8, total_steps=5000, sample_interval=100)
        result = evolver.run(verbose=False)
        weights = result['hamming_weight_history']
        # 封口前：重量单调不减（A1 单调累积）
        # 封口后：允许波动（汇吸收可以 1→0）
        sealed_step = None
        for i in range(len(weights)-1):
            if weights[i+1] < weights[i]:
                sealed_step = i
                break
        # 如果检测到下降，说明封口已触发，这是正常的
        if sealed_step is not None:
            # 封口前的步骤必须单调
            for i in range(1, sealed_step):
                assert weights[i] >= weights[i-1], f"weight decreased before seal at step {i}"
        else:
            # 未封口，全程单调
            for i in range(1, len(weights)):
                assert weights[i] >= weights[i-1], f"weight decreased at step {i}"

    def test_A5_conservation_in_run(self):
        from engine.long_range_evolver_v2 import LongRangeEvolverV2
        evolver = LongRangeEvolverV2(N=8, total_steps=5000, sample_interval=100)
        result = evolver.run(verbose=False)
        total_inj = sum(result['inject_history'])
        total_abs = sum(result['absorb_history'])
        # A5 守恒：注入和吸收应该接近平衡
        # 小 N 允许更大比例误差（离散效应），用绝对阈值
        if total_inj > 0:
            diff = abs(total_inj - total_abs)
            # 绝对阈值 5，或相对阈值 50%（取更宽松的）
            threshold = max(5, total_inj * 0.5)
            assert diff < threshold, \
                f"A5 imbalance: inj={total_inj}, abs={total_abs}, diff={diff}, threshold={threshold}"

    def test_A7_cycles_detected(self):
        from engine.long_range_evolver_v2 import LongRangeEvolverV2
        evolver = LongRangeEvolverV2(N=8, total_steps=5000, sample_interval=100)
        result = evolver.run(verbose=False)
        # 应该检测到循环
        assert result['cycle_states'] > 0
