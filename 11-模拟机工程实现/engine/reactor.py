"""
reactor.py — 差异反应堆核心

反应-扩散动力学：
    state_{t+1} = model(state_t)
    loss = 公理违背度之和

模型预测下一步状态，损失函数驱动模型学习满足公理约束的演化规则。
"""

import torch
import torch.nn as nn
from typing import List, Dict, Optional, Tuple

from acl.axiom_base import AxiomEngine, AxiomReport
from layers.layer_base import LayerBase
from models.local_conv_model import LocalConvModel


class DifferenceReactor:
    """差异反应堆：模型预测 + 公理约束。

    核心循环：
    1. 模型预测 next_state
    2. 应用源/汇边界条件（开放系统）
    3. 计算公理损失
    """

    def __init__(self, model: nn.Module, layer: LayerBase,
                 axiom_engine: AxiomEngine,
                 device: str = "cpu"):
        self.model = model
        self.layer = layer
        self.axiom_engine = axiom_engine
        self.device = device

    def step(self, state: torch.Tensor,
             history: Optional[List[torch.Tensor]] = None
             ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, AxiomReport]]:
        """反应堆单步演化。

        Args:
            state: 当前状态 (batch, 1, H, W)
            history: 历史状态列表（用于 A7 稳定性检测）

        Returns:
            next_state: 下一步状态
            loss: 公理损失（可微分）
            report: 每条公理的违背报告
        """
        if history is None:
            history = []

        # 1. 模型预测下一步
        raw_next = self.model(state)

        # NaN/Inf 保护
        if torch.isnan(raw_next).any() or torch.isinf(raw_next).any():
            raw_next = torch.nan_to_num(raw_next, nan=0.5, posinf=1.0, neginf=0.0)

        next_state = self.layer.project_state(raw_next)
        next_state = next_state.clamp(0.0, 1.0)

        # 2. 开放系统：源/汇边界条件，同时获取流量
        boundary_info = {}
        if hasattr(self.layer, 'apply_boundary_flow'):
            next_state, injected, absorbed = self.layer.apply_boundary_flow(next_state)
            boundary_info = {"injected": injected, "absorbed": absorbed}
        else:
            next_state = self.layer.inject_difference(next_state)
            next_state = self.layer.absorb_difference(next_state)

        # 3. 计算公理损失（可微分）
        loss, report = self._compute_axiom_loss(
            state, next_state, history, boundary_info=boundary_info
        )

        return next_state, loss, report

    def _compute_axiom_loss(self, state: torch.Tensor,
                            next_state: torch.Tensor,
                            history: List[torch.Tensor],
                            boundary_info: Optional[Dict[str, torch.Tensor]] = None
                            ) -> Tuple[torch.Tensor, Dict[str, AxiomReport]]:
        """计算可微分的公理损失。

        直接用 PyTorch 操作计算，保证梯度可回传。
        """
        loss_parts = []
        report = {}

        # --- A2: 离散性 ---
        # 状态应接近 0 或 1，惩罚中间值
        a2_val = (next_state * (1.0 - next_state)).mean()
        w2 = self.layer.get_axiom_weight("A2_discrete_encoding")
        a2_loss = a2_val * w2
        loss_parts.append(a2_loss)
        report["A2_discrete_encoding"] = AxiomReport(
            name="A2_discrete_encoding",
            raw_violation=float(a2_val.detach()),
            weight=w2,
            weighted_violation=float(a2_loss.detach()),
        )

        # --- A3: 局域性 ---
        # 由 CNN 结构保证，loss 权重为 0
        report["A3_locality"] = AxiomReport(
            name="A3_locality",
            raw_violation=0.0,
            weight=0.0,
            weighted_violation=0.0,
        )

        # --- A4: 最小变易 ---
        # 变化不应过大
        a4_val = ((next_state - state) ** 2).mean()
        w4 = self.layer.get_axiom_weight("A4_minimal_variation")
        a4_loss = a4_val * w4
        loss_parts.append(a4_loss)
        report["A4_minimal_variation"] = AxiomReport(
            name="A4_minimal_variation",
            raw_violation=float(a4_val.detach()),
            weight=w4,
            weighted_violation=float(a4_loss.detach()),
        )

        # --- A5: 守恒（开放系统流量平衡） ---
        # 开放系统中，守恒律应为：ΔQ = 注入量 - 吸收量
        # 残差 = ΔQ - (注入 - 吸收)，应趋近于 0
        q_now = self.layer.measure_invariant(state)
        q_next = self.layer.measure_invariant(next_state)
        delta_q = q_next - q_now

        if boundary_info:
            injected = boundary_info.get("injected", torch.zeros_like(q_now))
            absorbed = boundary_info.get("absorbed", torch.zeros_like(q_now))

            expected_delta = injected - absorbed
            flux_residual = delta_q - expected_delta

            a5_val = (flux_residual ** 2 / (q_now ** 2 + 1e-6)).mean()

            a5_metadata = {
                "mode": "open_flux_balance",
                "actual_delta": float(delta_q.detach().mean()),
                "expected_delta": float(expected_delta.detach().mean()),
                "injected": float(injected.detach().mean()),
                "absorbed": float(absorbed.detach().mean()),
                "flux_residual": float(flux_residual.detach().mean()),
            }
        else:
            a5_val = (delta_q ** 2 / (q_now ** 2 + 1e-6)).mean()
            a5_metadata = {
                "mode": "closed_conservation",
                "conservation_residual": float(a5_val.detach()),
            }

        w5 = self.layer.get_axiom_weight("A5_conservation")
        a5_loss = a5_val * w5
        loss_parts.append(a5_loss)
        report["A5_conservation"] = AxiomReport(
            name="A5_conservation",
            raw_violation=float(a5_val.detach()),
            weight=w5,
            weighted_violation=float(a5_loss.detach()),
            metadata=a5_metadata,
        )

        # --- A7: 稳定性 ---
        # 历史足够长时，鼓励模式持续
        w7 = self.layer.get_axiom_weight("A7_stability")
        if len(history) >= self.layer.stability_window:
            window = history[-self.layer.stability_window:]
            a7_loss = self._stability_loss(next_state, window) * w7
            loss_parts.append(a7_loss)
            report["A7_stability"] = AxiomReport(
                name="A7_stability",
                raw_violation=float(a7_loss.detach() / max(w7, 1e-8)),
                weight=w7,
                weighted_violation=float(a7_loss.detach()),
            )
        else:
            report["A7_stability"] = AxiomReport(
                name="A7_stability",
                raw_violation=0.0,
                weight=0.0,
                weighted_violation=0.0,
            )

        # --- 空间多样性（打破均匀化） ---
        # 差异论核心：差异是本原，均匀化是热寂
        # 两种多样性度量：
        # 1. 梯度多样性：空间梯度非零
        # 2. 值多样性：0 和 1 共存（二元多样性）

        # 梯度多样性
        grad_parts = []
        if next_state.shape[-1] > 1:
            grad_x = (next_state[:, :, :, 1:] - next_state[:, :, :, :-1]).abs().mean()
            grad_parts.append(grad_x)
        if next_state.shape[-2] > 1:
            grad_y = (next_state[:, :, 1:, :] - next_state[:, :, :-1, :]).abs().mean()
            grad_parts.append(grad_y)
        if grad_parts:
            spatial_grad = sum(grad_parts) / len(grad_parts) + 1e-8
        else:
            spatial_grad = torch.tensor(1e-8, device=next_state.device)
        grad_diversity = torch.exp(-spatial_grad * 5.0)

        # 值多样性：鼓励 0 和 1 共存
        # p*(1-p) 在 p=0.5 时最大，在 p=0 或 1 时为 0
        # 但我们想要 p 接近 0 或 1 且两者都有
        # 所以用：1 - |mean(round(state)) - 0.5|*2
        # 即：如果 50% 是 1，多样性最高
        p_mean = next_state.mean()
        value_diversity = 1.0 - torch.abs(p_mean - 0.5) * 2.0
        value_diversity = torch.clamp(value_diversity, 0.0, 1.0)

        # 组合：两者都鼓励
        diversity_loss = 0.5 * grad_diversity + 0.5 * (1.0 - value_diversity)
        loss_parts.append(0.3 * diversity_loss)
        report["spatial_diversity"] = AxiomReport(
            name="spatial_diversity",
            raw_violation=float(diversity_loss.detach()),
            weight=0.3,
            weighted_violation=float((0.3 * diversity_loss).detach()),
            metadata={
                "gradient": float(spatial_grad.detach()),
                "value_diversity": float(value_diversity.detach()),
            },
        )

        # 累积总损失
        loss = sum(loss_parts)
        return loss, report

    def _stability_loss(self, next_state: torch.Tensor,
                        window: List[torch.Tensor]) -> torch.Tensor:
        """A7 稳定性损失：鼓励模式持续。

        逻辑：
        - 如果 next_state 与历史窗口的模式相似，奖励（负 loss）
        - 如果 next_state 与历史模式不相似，惩罚（正 loss）
        """
        states = torch.stack(window, dim=0)  # (T, B, C, H, W)

        # 计算历史模式：时间均值
        pattern_mean = states.mean(dim=0)

        # next_state 与历史模式的余弦相似度
        flat_next = next_state.flatten()
        flat_mean = pattern_mean.flatten()

        if flat_next.numel() == 0:
            return torch.tensor(0.0, device=next_state.device)

        cos_sim = nn.functional.cosine_similarity(
            flat_next.unsqueeze(0), flat_mean.unsqueeze(0)
        )

        # 损失 = 1 - cos_sim（越相似，损失越小）
        return 1.0 - cos_sim.squeeze()

    def rollout(self, state: torch.Tensor, steps: int,
                train: bool = False
                ) -> Tuple[List[torch.Tensor], float, List[Dict]]:
        """连续 rollout 多步。

        Args:
            state: 初始状态
            steps: 步数
            train: 是否需要梯度

        Returns:
            history: 状态历史
            total_loss: 总损失
            reports: 每步报告
        """
        history = [state.detach()]
        total_loss = torch.tensor(0.0, device=state.device)
        reports = []
        current = state

        for i in range(steps):
            if train:
                next_state, loss, report = self.step(current, history)
                total_loss = total_loss + loss
            else:
                with torch.no_grad():
                    next_state, loss, report = self.step(current, history)

            history.append(next_state.detach())
            reports.append(report)
            current = next_state

        return history, total_loss, reports
