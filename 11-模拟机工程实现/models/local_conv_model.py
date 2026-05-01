"""models/local_conv_model.py — 局部卷积模型（增强版）

3×3 卷积 + 增量更新 + 反应分支。
天然满足 A3 局域性约束。

语义：delta=0 时 next_state == state（恒等映射）。
"""

import torch
import torch.nn as nn


class LocalConvModel(nn.Module):
    """局部卷积模型，用于差异反应堆动力学。

    结构：
    - 主干：3层 3x3 卷积 + GELU（局域性保证）
    - 增量更新：next_state = clamp(state + step_scale * tanh(delta), 0, 1)
    - 反应分支：1x1 卷积 + tanh（自强化模式）

    语义保证：当模型输出 delta=0 时，next_state == state（恒等映射）。
    """

    def __init__(self, channels: int = 32, use_reaction: bool = True,
                 step_scale: float = 0.2, learnable_step_scale: bool = True):
        super().__init__()
        self.use_reaction = use_reaction

        # 步长缩放参数
        if learnable_step_scale:
            self.step_scale = nn.Parameter(torch.tensor(float(step_scale)))
        else:
            self.register_buffer("step_scale", torch.tensor(float(step_scale)))

        # 主干：3层 3x3 卷积
        self.backbone = nn.Sequential(
            nn.Conv2d(1, channels, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv2d(channels, 1, kernel_size=3, padding=1),
        )

        # 反应分支：非线性自强化
        if use_reaction:
            self.reaction = nn.Sequential(
                nn.Conv2d(1, channels, kernel_size=1),
                nn.Tanh(),
                nn.Conv2d(channels, 1, kernel_size=1),
                nn.Tanh(),
            )
            # 反应强度参数（可学习，初始化小值）
            self.reaction_scale = nn.Parameter(torch.tensor(0.05))

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Args:
            state: (batch, 1, H, W)，值域 [0, 1]

        Returns:
            next_state: (batch, 1, H, W)，值域 [0, 1]
        """
        # 主干输出 → tanh 压到 [-1, 1]
        delta = torch.tanh(self.backbone(state))

        # 反应分支：非线性自强化
        if self.use_reaction:
            reaction = self.reaction(state)
            delta = delta + self.reaction_scale * reaction

        # 增量更新：state + step_scale * delta
        scale = torch.clamp(self.step_scale, 0.0, 1.0)
        next_state = state + scale * delta
        return next_state.clamp(0.0, 1.0)
