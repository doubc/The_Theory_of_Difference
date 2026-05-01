"""
world_engine.py — 世界引擎核心循环

支持：
- 差异反应堆动力学（反应-扩散）
- 公理约束训练
- 多层递归运行（升维后自动切换新层）
- 区域分类（死寂/爆炸/稳定/边界）
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
import torch
import torch.nn as nn

from acl.axiom_base import AxiomEngine, StepReport, StableStructure
from layers.layer_base import LayerBase
from engine.reactor import DifferenceReactor
from engine.trainer import AxiomTrainer


@dataclass
class RegionMap:
    """状态空间的区域分类"""
    dead: torch.Tensor        # 死寂区 → 转为吸收体
    explode: torch.Tensor     # 爆炸区 → 转为辐射源
    stable: torch.Tensor      # 稳定区 → 正常演化
    boundary: torch.Tensor    # 边界区 → 重点关注


class WorldEngine:
    """
    差异论局部世界实验机的核心循环。

    集成差异反应堆和公理约束训练。
    升维后自动在新层继续运行，不中断。
    """

    def __init__(self, model: nn.Module, layer: LayerBase,
                 axiom_engine: AxiomEngine,
                 lr: float = 1e-3,
                 device: str = "cpu"):
        self.model = model
        self.axiom_engine = axiom_engine
        self.device = device

        # 创建反应堆和训练器
        self.reactor = DifferenceReactor(model, layer, axiom_engine, device)
        self.trainer = AxiomTrainer(self.reactor, lr=lr, device=device)

        self.layer_stack: List[LayerBase] = [layer]
        self.global_step = 0
        self.ascent_history: List[Dict] = []

    @property
    def layer(self) -> LayerBase:
        return self.layer_stack[-1]

    def run(self, max_steps: int = 1000,
            ascent_check_interval: int = 64,
            train: bool = True) -> Dict:
        """主循环。

        Args:
            max_steps: 最大步数
            ascent_check_interval: 升维检测间隔
            train: 是否训练模型

        Returns:
            运行结果字典
        """
        state = self.layer.initial_state().to(self.device)
        history = [state.detach()]
        all_reports = []
        structures_buffer = []

        step = 0
        while step < max_steps:
            # --- 区域分类 ---
            regions = self._classify_regions(state, history, self.layer)

            # --- 演化一步 ---
            if train:
                result = self.trainer.train_step(state, history)
                next_state = result["next_state"]
                loss_val = result["loss"]
                axiom_reports = result.get("axiom_reports", {})
            else:
                with torch.no_grad():
                    next_state, loss, report_raw = self.reactor.step(state, history)
                loss_val = loss.item()
                axiom_reports = report_raw
                next_state = next_state.detach()

            all_reports.append(StepReport(
                step=self.global_step,
                layer_name=self.layer.name,
                total_loss=loss_val,
                axiom_reports=axiom_reports,
                regions={
                    "dead": regions.dead.sum().item(),
                    "explode": regions.explode.sum().item(),
                    "stable": regions.stable.sum().item(),
                    "boundary": regions.boundary.sum().item(),
                }
            ))

            state = next_state
            history.append(state.detach())
            self.global_step += 1
            step += 1

            # --- 定期检测稳定结构 ---
            if step % ascent_check_interval == 0:
                new_structures = self.layer.detect_stable_structures(history)
                structures_buffer.extend(new_structures)

                # --- 检查升维 ---
                if self.axiom_engine.check_ascent(
                    self.layer, history, structures_buffer
                ):
                    new_layer = self.layer.coarse_grain(structures_buffer)
                    if new_layer is not None:
                        self.ascent_history.append({
                            "from_layer": self.layer.name,
                            "to_layer": new_layer.name,
                            "at_step": self.global_step,
                            "structures_count": len(structures_buffer),
                        })
                        self.layer_stack.append(new_layer)
                        state = new_layer.initial_state().to(self.device)
                        history = [state.detach()]
                        structures_buffer = []
                        continue

        return {
            "total_steps": self.global_step,
            "layer_stack": [l.name for l in self.layer_stack],
            "ascents": self.ascent_history,
            "reports": all_reports,
            "final_state": state,
            "structures_detected": len(structures_buffer),
        }

    def train(self, episodes: int = 50, steps_per_episode: int = 100):
        """训练模式：运行多个 episode 的训练。

        Args:
            episodes: episode 数
            steps_per_episode: 每 episode 步数

        Returns:
            训练日志列表
        """
        return self.trainer.train(episodes, steps_per_episode)

    def evaluate(self, steps: int = 200) -> Dict:
        """评估模式：不训练，只运行。

        Args:
            steps: 评估步数

        Returns:
            评估结果
        """
        state = self.layer.initial_state().to(self.device)
        return self.trainer.evaluate(state, steps)

    def _classify_regions(self, state: torch.Tensor,
                          history: List[torch.Tensor],
                          layer: LayerBase) -> RegionMap:
        """把状态空间分为四类区域"""
        if len(history) < 8:
            ones = torch.ones_like(state, dtype=torch.bool)
            return RegionMap(
                dead=torch.zeros_like(state, dtype=torch.bool),
                explode=torch.zeros_like(state, dtype=torch.bool),
                stable=ones,
                boundary=torch.zeros_like(state, dtype=torch.bool),
            )

        recent = history[-8:]

        # 活动度
        activity = torch.stack([s.mean() for s in recent]).mean()

        # 波动度
        volatility = torch.stack([
            (recent[i + 1] - recent[i]).abs().mean()
            for i in range(len(recent) - 1)
        ]).mean()

        # 模式持续性
        persistence = self._quick_pattern_persistence(recent)

        # 分区
        dead = (activity < 0.05) & (volatility < 0.01)
        explode = (activity > 0.95) | (volatility > 0.8)
        stable = (persistence > 0.7) & ~dead & ~explode
        boundary = ~dead & ~explode & ~stable

        dead_mask = torch.full_like(state, fill_value=float(dead), dtype=torch.bool)
        explode_mask = torch.full_like(state, fill_value=float(explode), dtype=torch.bool)
        stable_mask = torch.full_like(state, fill_value=float(stable), dtype=torch.bool)
        boundary_mask = ~dead_mask & ~explode_mask & ~stable_mask

        return RegionMap(
            dead=dead_mask.bool(),
            explode=explode_mask.bool(),
            stable=stable_mask.bool(),
            boundary=boundary_mask.bool(),
        )

    def _quick_pattern_persistence(self, window: List[torch.Tensor]) -> float:
        """快速计算模式持续性"""
        if len(window) < 2:
            return 1.0
        fields = [layer_measure_diff(s) for s in window]
        corrs = []
        for i in range(len(fields) - 1):
            a = fields[i].flatten()
            b = fields[i + 1].flatten()
            if a.numel() == 0:
                continue
            corr = torch.nn.functional.cosine_similarity(
                a.unsqueeze(0), b.unsqueeze(0)
            )
            corrs.append(corr.item())
        return sum(corrs) / len(corrs) if corrs else 0.0


def layer_measure_diff(state: torch.Tensor) -> torch.Tensor:
    """快速差异度量（兼容 1D）"""
    parts = []
    if state.shape[-1] > 1:
        parts.append((state[:, :, :, 1:] - state[:, :, :, :-1]).abs())
    if state.shape[-2] > 1:
        parts.append((state[:, :, 1:, :] - state[:, :, :-1, :]).abs())
    if not parts:
        return torch.zeros_like(state)
    if len(parts) == 1:
        return parts[0]
    # 对齐形状后平均
    return (parts[0][..., :-1, :] + parts[1][..., :, :-1]) / 2.0
