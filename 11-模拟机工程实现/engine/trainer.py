"""
trainer.py — 公理约束训练器

驱动差异反应堆的模型学习：
    损失 = 公理违背度之和
    模型通过反向传播学习满足公理约束的演化规则。
"""

import torch
import torch.nn as nn
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from engine.reactor import DifferenceReactor


@dataclass
class TrainLog:
    """单步训练日志"""
    episode: int
    step: int
    loss: float
    axiom_violations: Dict[str, float]
    state_mean: float
    state_std: float
    unique_values: int


@dataclass
class EpisodeLog:
    """单 episode 训练日志"""
    episode: int
    total_loss: float
    avg_loss: float
    steps: int
    final_state_mean: float
    final_state_std: float
    unique_values: int
    axiom_summary: Dict[str, float]
    stable_structures: int = 0


class AxiomTrainer:
    """公理约束训练器。

    训练循环：
    1. 从初始状态开始 rollout
    2. 每步计算公理损失
    3. 反向传播更新模型参数
    4. 记录训练日志
    """

    def __init__(self, reactor: DifferenceReactor,
                 lr: float = 1e-3,
                 device: str = "cpu"):
        self.reactor = reactor
        self.device = device
        self.optimizer = torch.optim.Adam(
            reactor.model.parameters(), lr=lr
        )
        self.episode_logs: List[EpisodeLog] = []

    def train_step(self, state: torch.Tensor,
                   history: Optional[List[torch.Tensor]] = None
                   ) -> Dict:
        """单步训练。

        Args:
            state: 当前状态
            history: 历史状态

        Returns:
            训练日志字典
        """
        self.optimizer.zero_grad()

        next_state, loss, report = self.reactor.step(state, history)

        # NaN 保护：跳过此步
        if torch.isnan(loss) or torch.isinf(loss):
            self.optimizer.zero_grad()
            return {
                "loss": 0.0,
                "next_state": state.detach(),
                "report": {k: 0.0 for k in report},
            }

        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            self.reactor.model.parameters(), max_norm=1.0
        )
        self.optimizer.step()

        return {
            "loss": loss.item(),
            "next_state": next_state.detach(),
            "report": {k: v.raw_violation for k, v in report.items()},
            "axiom_reports": report,  # 保留完整 AxiomReport 对象
        }

    def train_episode(self, initial_state: torch.Tensor,
                      steps: int = 100,
                      log_interval: int = 10
                      ) -> EpisodeLog:
        """训练一个 episode。

        Args:
            initial_state: 初始状态
            steps: 每 episode 的步数
            log_interval: 日志打印间隔

        Returns:
            EpisodeLog
        """
        state = initial_state.to(self.device)
        history = [state.detach()]
        total_loss = 0.0
        axiom_accum = {}

        for step in range(steps):
            result = self.train_step(state, history)
            total_loss += result["loss"]
            state = result["next_state"]
            history.append(state.detach())

            # 累积公理违背度
            for k, v in result["report"].items():
                axiom_accum[k] = axiom_accum.get(k, 0.0) + v

            if (step + 1) % log_interval == 0:
                unique = len(torch.unique(state.round()))
                print(f"  step {step+1}/{steps}  "
                      f"loss={result['loss']:.4f}  "
                      f"unique={unique}  "
                      f"mean={state.mean():.3f}")

        # 统计
        unique = len(torch.unique(state.round()))
        axiom_summary = {
            k: v / steps for k, v in axiom_accum.items()
        }

        # 检测稳定结构
        structures = self.reactor.layer.detect_stable_structures(history)

        log = EpisodeLog(
            episode=len(self.episode_logs),
            total_loss=total_loss,
            avg_loss=total_loss / steps,
            steps=steps,
            final_state_mean=float(state.mean()),
            final_state_std=float(state.std()),
            unique_values=unique,
            axiom_summary=axiom_summary,
            stable_structures=len(structures),
        )
        self.episode_logs.append(log)
        return log

    def train(self, episodes: int = 100,
              steps_per_episode: int = 100,
              log_interval: int = 10
              ) -> List[EpisodeLog]:
        """完整训练循环。

        Args:
            episodes: 训练 episode 数
            steps_per_episode: 每 episode 步数
            log_interval: 日志打印间隔

        Returns:
            所有 episode 的日志
        """
        logs = []
        for ep in range(episodes):
            print(f"\n=== Episode {ep+1}/{episodes} ===")
            initial = self.reactor.layer.initial_state()
            log = self.train_episode(initial, steps_per_episode, log_interval)
            logs.append(log)

            print(f"  total_loss={log.total_loss:.4f}  "
                  f"unique={log.unique_values}  "
                  f"structures={log.stable_structures}  "
                  f"mean={log.final_state_mean:.3f}")

        return logs

    def evaluate(self, state: torch.Tensor,
                 steps: int = 100) -> Dict:
        """评估模式（不训练）。

        Args:
            state: 初始状态
            steps: 评估步数

        Returns:
            评估结果
        """
        self.reactor.model.eval()
        with torch.no_grad():
            history, total_loss, reports = self.reactor.rollout(
                state, steps, train=False
            )
        self.reactor.model.train()

        # 统计
        final = history[-1]
        structures = self.reactor.layer.detect_stable_structures(history)

        # 公理违背度统计
        axiom_accum = {}
        for report in reports:
            for k, v in report.items():
                axiom_accum[k] = axiom_accum.get(k, 0.0) + v.raw_violation

        return {
            "total_loss": total_loss.item(),
            "avg_loss": total_loss.item() / steps,
            "final_state_mean": float(final.mean()),
            "final_state_std": float(final.std()),
            "unique_values": len(torch.unique(final.round())),
            "stable_structures": len(structures),
            "axiom_summary": {
                k: v / steps for k, v in axiom_accum.items()
            },
            "history": history,
        }
