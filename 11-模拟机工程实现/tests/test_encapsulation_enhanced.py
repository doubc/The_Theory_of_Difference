"""
tests/test_encapsulation_enhanced.py — 封装引擎增强测试（Phase 2 P2）

测试界面调节度指标和交换追踪功能。
"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.encapsulation_engine import EncapsulationEngine


class TestEncapsulationEnhanced:
    """封装引擎增强功能测试"""

    def setup_method(self):
        self.engine = EncapsulationEngine(
            binding_threshold=0.1,
            min_group_size=2,
        )
        self.state = torch.tensor([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])

        # 创建一些绑定强度
        n = len(self.state)
        binding = torch.zeros(n, n)
        binding[0, 1] = 0.5
        binding[1, 0] = 0.5
        binding[2, 3] = 0.3
        binding[3, 2] = 0.3
        binding[4, 5] = 0.4
        binding[5, 4] = 0.4

        self.engine.encapsulate(
            state=self.state,
            frozen_bits={0, 1, 2, 3, 4, 5},
            binding_strength=binding,
            active_bits={6, 7},
            layer=0,
        )

    def test_compute_interface_regulation(self):
        """计算界面调节度"""
        result = self.engine.compute_interface_regulation(0)
        assert 'interface_regulation' in result
        assert 'active_exchanges' in result
        assert 'total_boundary_edges' in result
        assert 'exchange_rate' in result
        assert 0.0 <= result['interface_regulation'] <= 1.0

    def test_compute_interface_regulation_with_exchange_record(self):
        """使用显式交换记录计算界面调节度"""
        # 记录一些交换
        self.engine.track_exchange(0, 0, 5)  # 封装比特 0 有 5 次交换
        self.engine.track_exchange(0, 1, 3)  # 封装比特 1 有 3 次交换

        exchange_record = self.engine.get_exchange_record(0)
        result = self.engine.compute_interface_regulation(
            0, exchange_record=exchange_record)

        # 有交换记录的封装比特比例
        assert result['active_exchanges'] >= 2

    def test_compute_all_interface_regulations(self):
        """计算所有层级的界面调节度"""
        results = self.engine.compute_all_interface_regulations()
        assert 0 in results
        assert 'interface_regulation' in results[0]

    def test_track_exchange(self):
        """追踪交换事件"""
        self.engine.track_exchange(0, 0, 3)
        self.engine.track_exchange(0, 0, 2)
        record = self.engine.get_exchange_record(0)
        assert record[0] == 5  # 3 + 2

    def test_track_exchange_multiple_boundaries(self):
        """追踪多条边界"""
        self.engine.track_exchange(0, 0, 1)
        self.engine.track_exchange(0, 1, 2)
        self.engine.track_exchange(0, 2, 3)
        record = self.engine.get_exchange_record(0)
        assert len(record) == 3

    def test_get_exchange_record_empty(self):
        """获取空交换记录"""
        record = self.engine.get_exchange_record(99)  # 不存在的层级
        assert record == {}

    def test_interface_regulation_no_encapsulation(self):
        """无封装时的界面调节度"""
        result = self.engine.compute_interface_regulation(99)  # 不存在的层级
        assert result['interface_regulation'] == 0.0
        assert result['active_exchanges'] == 0
        assert result['total_boundary_edges'] == 0

    def test_interface_regulation_all_active(self):
        """全部活跃交换"""
        # 记录所有封装比特都有交换
        enc_bits = self.engine.encapsulated_bits.get(0, [])
        exchange_record = {enc.bit_id: 1 for enc in enc_bits}
        result = self.engine.compute_interface_regulation(
            0, exchange_record=exchange_record)
        assert result['interface_regulation'] == 1.0

    def test_interface_regulation_none_active(self):
        """无活跃交换"""
        exchange_record = {enc.bit_id: 0 for enc in self.engine.encapsulated_bits.get(0, [])}
        result = self.engine.compute_interface_regulation(
            0, exchange_record=exchange_record)
        assert result['interface_regulation'] == 0.0
