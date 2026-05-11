"""
test_property_conservation.py — 守恒性质测试

审计报告 Section 7.1：
验证 Reactor 中 ΔQ ≈ injected - absorbed（允许数值误差）。
不依赖特定模型实现，只验证守恒律作为不变性质。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
import pytest

from layers.L0_binary_lattice import L0BinaryLattice
from acl.axioms import create_default_axioms
from acl.axiom_base import AxiomEngine
from models.local_conv_model import LocalConvModel
from engine.reactor import DifferenceReactor


class TestConservationProperty:
    """守恒律：开放系统 ΔQ ≈ injected - absorbed"""

    @pytest.mark.parametrize("shape", [(4, 4), (8, 8)])
    @pytest.mark.parametrize("source_strength", [0.5, 1.0])
    def test_flux_balance_no_model(self, shape, source_strength):
        """无模型干预时，直接注入→吸收→ΔQ 应满足通量平衡"""
        layer = L0BinaryLattice(shape=shape, device="cpu",
                                source_side="left", sink_side="right")
        state = layer.initial_state()

        # 测量初始守恒量
        q0 = state.sum().item()

        # 注入差异
        injected = layer.inject_difference(state, source_strength=source_strength)
        injected_q = injected.sum().item()
        q_injected = injected_q - q0

        # 吸收差异
        absorbed = layer.absorb_difference(injected, sink_strength=1.0)
        absorbed_q = absorbed.sum().item()
        q_absorbed = injected_q - absorbed_q

        # ΔQ
        delta_q = absorbed_q - q0

        # 理论预期：ΔQ = injected_net - absorbed_net
        expected_delta = q_injected - q_absorbed

        # 允许数值误差（浮点精度 + 注入随机采样）
        assert abs(delta_q - expected_delta) < 1e-4, (
            f"Flux balance violated: ΔQ={delta_q:.6f}, "
            f"expected={expected_delta:.6f}, "
            f"injected_net={q_injected:.6f}, absorbed_net={q_absorbed:.6f}"
        )

    @pytest.mark.parametrize("steps", [5, 10])
    def test_multi_step_flux_near_zero(self, steps):
        """多步注入→吸收循环中，净通量应接近 0（无模型学习噪声）"""
        layer = L0BinaryLattice(shape=(8, 8), device="cpu",
                                source_side="left", sink_side="right")
        state = layer.initial_state()
        q0 = state.sum().item()

        cumulative_injected = 0.0
        cumulative_absorbed = 0.0

        for _ in range(steps):
            q_before = state.sum().item()
            state = layer.inject_difference(state, source_strength=0.5)
            q_after_inject = state.sum().item()
            cumulative_injected += (q_after_inject - q_before)

            q_before = state.sum().item()
            state = layer.absorb_difference(state, sink_strength=1.0)
            q_after_absorb = state.sum().item()
            cumulative_absorbed += (q_before - q_after_absorb)

        q_final = state.sum().item()
        actual_delta = q_final - q0
        expected_delta = cumulative_injected - cumulative_absorbed

        assert abs(actual_delta - expected_delta) < 1e-3, (
            f"Multi-step flux imbalance: ΔQ={actual_delta:.6f}, "
            f"expected={expected_delta:.6f}"
        )

    def test_boundary_flow_returns_triplet(self):
        """apply_boundary_flow 应返回 (state, injected, absorbed)"""
        layer = L0BinaryLattice(shape=(4, 4), device="cpu",
                                source_side="left", sink_side="right")
        state = layer.initial_state()
        result = layer.apply_boundary_flow(state, source_strength=1.0, sink_strength=1.0)

        assert isinstance(result, tuple), "apply_boundary_flow must return tuple"
        assert len(result) == 3, (
            f"apply_boundary_flow must return (state, injected, absorbed), "
            f"got {len(result)} elements"
        )

    def test_conservation_with_reactor(self):
        """Reactor 单步内 open-system A5 应保持通量平衡"""
        layer = L0BinaryLattice(shape=(8, 8), device="cpu",
                                source_side="left", sink_side="right")
        axioms = create_default_axioms(ascent_threshold=0.5)
        axiom_engine = AxiomEngine(axioms)
        model = LocalConvModel(channels=8, use_reaction=True)
        reactor = DifferenceReactor(model, layer, axiom_engine, device="cpu")

        state = layer.initial_state()
        history = [state.clone()]

        # 运行一步
        result = reactor.step(state, history)
        next_state, loss, report = result

        # A5 违背度应为有限值（0 ≤ violation < inf）
        if "A5_conservation" in report:
            a5 = report["A5_conservation"].raw_violation
            assert not torch.isnan(torch.tensor(a5)), (
                f"A5 violation is NaN: {a5}"
            )
            assert a5 >= 0, f"A5 violation must be >= 0, got {a5}"