"""
experiment_config.py — 实验配置 dataclass

统一 CLI 参数、日志写入、文档生成的配置对象。
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
import json


@dataclass
class ExperimentConfig:
    """差异反应堆实验配置。

    支持 1D 和 2D 两种模式，所有字段有合理默认值。
    """

    # --- 网格 ---
    grid_size: int = 32           # 2D 网格边长（1D 时忽略）
    length: int = 50              # 1D 格点长度（2D 时忽略）
    mode: str = "2d"              # "1d" | "2d"

    # --- 训练 ---
    episodes: int = 30
    steps_per_episode: int = 200
    lr: float = 1e-3

    # --- 模型 ---
    channels: int = 32            # CNN 通道数
    use_reaction: bool = True     # 是否启用反应分支
    ascent_threshold: float = 0.5 # 升维阈值

    # --- 边界条件 ---
    source_side: str = "left"
    sink_side: str = "right"
    source_strength: float = 1.0
    sink_strength: float = 1.0

    # --- 运行时 ---
    device: str = "cpu"
    seed: Optional[int] = None    # 随机种子
    verbose: bool = True

    # --- 评估 ---
    eval_steps: int = 300
    log_interval: Optional[int] = None  # 自动设为 steps_per_episode // 4

    @property
    def shape(self) -> tuple:
        """根据 mode 返回实际网格形状"""
        if self.mode == "1d":
            return (1, self.length)
        return (self.grid_size, self.grid_size)

    @property
    def effective_log_interval(self) -> int:
        """日志间隔：用户未设置时默认 steps_per_episode // 4"""
        if self.log_interval is not None:
            return self.log_interval
        return max(1, self.steps_per_episode // 4)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（不含 None 默认值）"""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_header_string(self) -> str:
        """生成实验头信息（用于日志输出）"""
        lines = [
            "=" * 60,
            f"{self.mode.upper()} Difference Reactor Experiment",
            f"  Mode: {self.mode}",
        ]
        if self.mode == "1d":
            lines.append(f"  Length: {self.length}")
        else:
            lines.append(f"  Grid: {self.grid_size}x{self.grid_size}")
        lines.extend([
            f"  Episodes: {self.episodes}",
            f"  Steps/episode: {self.steps_per_episode}",
            f"  Learning rate: {self.lr}",
            f"  Channels: {self.channels}",
            f"  Device: {self.device}",
            f"  Seed: {self.seed}",
            "=" * 60,
        ])
        return "\n".join(lines)

    @classmethod
    def from_cli(cls) -> "ExperimentConfig":
        """从命令行参数构建配置（argparse）。

        使用方式：
            python experiments/exp_2d_reactor.py --grid_size 64 --episodes 50
        """
        import argparse
        parser = argparse.ArgumentParser(description="Difference Reactor Experiment")
        parser.add_argument("--mode", default="2d", choices=["1d", "2d"])
        parser.add_argument("--grid_size", type=int, default=32)
        parser.add_argument("--length", type=int, default=50)
        parser.add_argument("--episodes", type=int, default=30)
        parser.add_argument("--steps_per_episode", type=int, default=200)
        parser.add_argument("--lr", type=float, default=1e-3)
        parser.add_argument("--channels", type=int, default=32)
        parser.add_argument("--device", default="cpu")
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--eval_steps", type=int, default=300)
        parser.add_argument("--log_interval", type=int, default=None)
        parser.add_argument("--ascent_threshold", type=float, default=0.5)

        args = parser.parse_args()
        return cls(**{k: v for k, v in vars(args).items() if v is not None})

    @classmethod
    def preset_quick(cls) -> "ExperimentConfig":
        """预设：快速验证（小规模）"""
        return cls(
            mode="1d", length=30, episodes=5,
            steps_per_episode=50, channels=8,
        )

    @classmethod
    def preset_standard(cls) -> "ExperimentConfig":
        """预设：标准 2D 实验"""
        return cls(
            mode="2d", grid_size=32, episodes=30,
            steps_per_episode=200, channels=32,
        )

    @classmethod
    def preset_large(cls) -> "ExperimentConfig":
        """预设：大规模 2D 实验"""
        return cls(
            mode="2d", grid_size=64, episodes=50,
            steps_per_episode=300, channels=64,
        )
