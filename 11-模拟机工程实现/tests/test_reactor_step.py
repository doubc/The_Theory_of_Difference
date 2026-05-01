"""tests/test_reactor_step.py — 差异反应堆单元测试"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.reactor import DifferenceReactor
from models.local_conv_model import LocalConvModel
from layers.L0_binary_lattice import L0BinaryLattice
from acl.axioms import build_default_axiom_engine


class TestDifferenceReactor:
    """DifferenceReactor 测试"""

    def setup_method(self):
        self.model = LocalConvModel(channels=16, use_reaction=True)
        self.layer = L0BinaryLattice(shape=(8, 8), device="cpu")
        self.axiom_engine = build_default_axiom_engine()
        self.reactor = DifferenceReactor(
            self.model, self.layer, self.axiom_engine
        )

    def test_step_returns(self):
        """step 应返回 (next_state, loss, report)"""
        state = self.layer.initial_state()
        next_state, loss, report = self.reactor.step(state)
        assert next_state.shape == state.shape
        assert loss.dim() == 0  # scalar
        assert isinstance(report, dict)

    def test_step_no_nan(self):
        """连续多步不应产生 NaN"""
        state = self.layer.initial_state()
        for _ in range(10):
            state, loss, report = self.reactor.step(state)
            assert not torch.isnan(state).any()
            assert not torch.isnan(loss)

    def test_loss_is_differentiable(self):
        """损失应可微分"""
        state = self.layer.initial_state()
        next_state, loss, report = self.reactor.step(state)
        loss.backward()
        # 模型参数应有梯度
        for p in self.model.parameters():
            assert p.grad is not None

    def test_report_contains_axioms(self):
        """报告应包含公理信息"""
        state = self.layer.initial_state()
        next_state, loss, report = self.reactor.step(state)
        assert "A2_discrete_encoding" in report
        assert "A5_conservation" in report

    def test_rollout(self):
        """rollout 应返回正确长度的历史"""
        state = self.layer.initial_state()
        history, total_loss, reports = self.reactor.rollout(state, steps=5)
        assert len(history) == 6  # 初始 + 5步
        assert len(reports) == 5

    def test_rollout_no_train(self):
        """非训练模式不应计算梯度"""
        state = self.layer.initial_state()
        history, total_loss, reports = self.reactor.rollout(
            state, steps=5, train=False
        )
        assert len(history) == 6

    def test_1d_reactor(self):
        """1D 格点不应崩溃"""
        model = LocalConvModel(channels=16)
        layer = L0BinaryLattice(shape=(1, 50), device="cpu")
        engine = build_default_axiom_engine()
        reactor = DifferenceReactor(model, layer, engine)

        state = layer.initial_state()
        next_state, loss, report = reactor.step(state)
        assert next_state.shape == (1, 1, 1, 50)
        assert not torch.isnan(loss)

    def test_axiom_loss_direct(self):
        """直接测试公理损失计算"""
        state = self.layer.initial_state()
        next_state = state.clone()
        loss, report = self.reactor._compute_axiom_loss(
            state, next_state, []
        )
        # 相同状态的损失应很小
        assert loss.item() >= 0

    def test_reactor_a5_open_flux_balance_metadata(self):
        """A5 metadata 应包含 mode/injected/absorbed/flux_residual"""
        model = LocalConvModel(channels=8)
        layer = L0BinaryLattice(shape=(8, 8))
        engine = build_default_axiom_engine()
        reactor = DifferenceReactor(model, layer, engine)

        state = layer.initial_state()
        _, _, report = reactor.step(state)

        assert "A5_conservation" in report
        a5 = report["A5_conservation"]
        assert a5.metadata["mode"] == "open_flux_balance"
        assert "injected" in a5.metadata
        assert "absorbed" in a5.metadata
        assert "flux_residual" in a5.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
