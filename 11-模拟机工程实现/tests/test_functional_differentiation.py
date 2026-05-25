"""
tests/test_functional_differentiation.py — 功能分化测试

Phase 2 P2 组件 #2 测试
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.functional_differentiation import (
    FunctionalDifferentiation, FunctionalState, ComponentContribution
)


class TestFunctionalDifferentiation:
    """FunctionalDifferentiation 测试套件"""

    def setup_method(self):
        self.fd = FunctionalDifferentiation(
            differentiation_threshold=0.3,
            min_components=2,
            min_observations=5,
            stability_window=10,
        )

    def test_initial_state(self):
        """初始状态：无组件，未分化"""
        assert not self.fd.is_differentiated
        assert self.fd.differentiation_index_value == 0.0
        assert self.fd.state.n_components == 0

    def test_register_component(self):
        """注册组件（不触发 _update_state，需手动记录贡献后状态才更新）"""
        self.fd.register_component("A")
        assert "A" in self.fd._components

    def test_record_contribution(self):
        """记录贡献"""
        self.fd.record_contribution("A", 0.8)
        assert "A" in self.fd._components
        assert self.fd._components["A"].n_observations == 1

    def test_record_contributions_batch(self):
        """批量记录贡献"""
        self.fd.record_contributions({"A": 0.8, "B": 0.2, "C": 0.5})
        assert len(self.fd._components) == 3
        assert self.fd._components["A"].n_observations == 1

    def test_differentiation_index_uniform(self):
        """均匀贡献 → 低分化指数"""
        for _ in range(10):
            self.fd.record_contributions({"A": 0.5, "B": 0.5, "C": 0.5})
        gini = self.fd.get_differentiation_index()
        assert gini < 0.1

    def test_differentiation_index_unequal(self):
        """不均匀贡献 → 高分化指数"""
        for _ in range(10):
            self.fd.record_contributions({"A": 0.9, "B": 0.05, "C": 0.05})
        gini = self.fd.get_differentiation_index()
        assert gini > 0.3

    def test_differentiation_threshold(self):
        """分化阈值判定"""
        fd = FunctionalDifferentiation(
            differentiation_threshold=0.2,
            min_observations=3,
        )
        for _ in range(5):
            fd.record_contributions({"A": 0.9, "B": 0.1})
        assert fd.is_differentiated

    def test_not_differentiated_uniform(self):
        """均匀贡献 → 未分化"""
        for _ in range(10):
            self.fd.record_contributions({"A": 0.5, "B": 0.5})
        assert not self.fd.is_differentiated

    def test_component_roles(self):
        """功能角色分类"""
        for _ in range(10):
            self.fd.record_contributions({"A": 0.8, "B": 0.5, "C": 0.2})

        roles = self.fd.get_component_roles()
        assert "A" in roles
        assert "B" in roles
        assert "C" in roles

    def test_contribution_distribution(self):
        """贡献分布"""
        self.fd.record_contributions({"A": 0.8, "B": 0.2})
        dist = self.fd.get_contribution_distribution()
        assert "A" in dist
        assert "B" in dist
        assert abs(dist["A"] - 0.8) < 1e-6
        assert abs(dist["B"] - 0.2) < 1e-6

    def test_get_contributions_for_detector(self):
        """获取 SixThresholdDetector 格式"""
        self.fd.record_contributions({"A": 0.8, "B": 0.2})
        contributions = self.fd.get_component_contributions_for_detector()
        assert "A" in contributions
        assert "B" in contributions

    def test_summary(self):
        """摘要信息"""
        self.fd.record_contributions({"A": 0.8, "B": 0.2})
        summary = self.fd.get_summary()
        assert 'is_differentiated' in summary
        assert 'differentiation_index' in summary
        assert 'n_components' in summary
        assert 'roles' in summary
        assert 'distribution' in summary

    def test_reset(self):
        """重置状态"""
        self.fd.record_contributions({"A": 0.8, "B": 0.2})
        self.fd.reset()
        assert not self.fd.is_differentiated
        assert len(self.fd._components) == 0
        assert len(self.fd._differentiation_history) == 0

    def test_dominant_component(self):
        """主导组件识别"""
        for _ in range(10):
            self.fd.record_contributions({"A": 0.9, "B": 0.05, "C": 0.05})
        assert self.fd.state.dominant_component == "A"

    def test_weakest_component(self):
        """最弱组件识别"""
        for _ in range(10):
            self.fd.record_contributions({"A": 0.9, "B": 0.08, "C": 0.02})
        assert self.fd.state.weakest_component == "C"

    def test_contribution_trend(self):
        """贡献趋势"""
        comp = ComponentContribution(component_id="A")
        comp.contributions = [0.1, 0.2, 0.3, 0.4, 0.5]
        assert comp.contribution_trend > 0

    def test_recent_contribution(self):
        """最近贡献"""
        comp = ComponentContribution(component_id="A")
        comp.contributions = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.9, 0.9]
        assert comp.recent_contribution > comp.mean_contribution

    def test_functional_state_dataclass(self):
        """FunctionalState 数据类"""
        state = FunctionalState(
            is_differentiated=True,
            differentiation_index=0.6,
            n_components=3,
            n_distinct_roles=3,
        )
        assert state.is_differentiated
        assert state.differentiation_index == 0.6

    def test_min_observations_not_met(self):
        """观察次数不足 → 不做分化判定"""
        fd = FunctionalDifferentiation(min_observations=10)
        for _ in range(3):
            fd.record_contributions({"A": 0.9, "B": 0.1})
        assert not fd.is_differentiated


class TestFunctionalDifferentiationEdgeCases:
    """边界情况测试"""

    def setup_method(self):
        self.fd = FunctionalDifferentiation(
            differentiation_threshold=0.3,
            min_components=2,
            min_observations=5,
            stability_window=10,
        )

    def test_single_component(self):
        """单组件 → 无法分化"""
        fd = FunctionalDifferentiation(min_components=2)
        for _ in range(10):
            fd.record_contribution("A", 0.5)
        assert not fd.is_differentiated

    def test_zero_contributions(self):
        """零贡献"""
        fd = FunctionalDifferentiation()
        for _ in range(10):
            fd.record_contributions({"A": 0.0, "B": 0.0})
        gini = fd.get_differentiation_index()
        assert gini == 0.0

    def test_negative_contribution_clamped(self):
        """负贡献应被截断为 0"""
        self.fd.record_contribution("A", -0.5)
        assert self.fd._components["A"].contributions[-1] == 0.0

    def test_many_components(self):
        """多组件"""
        fd = FunctionalDifferentiation(min_observations=3)
        for _ in range(10):
            contributions = {f"comp_{i}": 1.0 / (i + 1) for i in range(10)}
            fd.record_contributions(contributions)
        assert fd.state.n_components == 10
        gini = fd.get_differentiation_index()
        assert gini > 0.0

    def test_dynamic_registration(self):
        """动态注册：record_contribution 自动注册"""
        self.fd.record_contribution("auto", 0.5)
        assert "auto" in self.fd._components

    def test_summary_before_any_record(self):
        """记录前获取摘要"""
        summary = self.fd.get_summary()
        assert summary['n_components'] == 0
        assert summary['differentiation_index'] == 0.0
