"""
engine/detectors/trajectory_recorder.py — 轨迹记录器

记录演化过程中的完整数据，供后续统计分析。

记录内容：
- 状态快照（每 sample_interval 步）
- 比特翻转序列（每步）
- 汉明重量序列（每步）
- 源/汇通量记录（每步）
- 公理违背度（每 sample_interval 步）
"""

import torch
from typing import List, Optional, Dict
from dataclasses import dataclass, field


@dataclass
class StepRecord:
    """单步记录"""
    step: int
    flip_position: int = -1           # 翻转的比特位置
    hamming_weight: int = 0           # 当前汉明重量
    source_injected: int = 0          # 源注入比特数
    sink_absorbed: int = 0            # 汇吸收比特数
    axiom_loss: float = 0.0           # 公理损失（可选）


@dataclass
class TrajectoryData:
    """完整轨迹数据"""
    N: int = 0
    total_steps: int = 0
    sample_interval: int = 100

    # 完整序列（每步）
    flip_sequence: List[int] = field(default_factory=list)         # 翻转位置序列
    hamming_weight_sequence: List[int] = field(default_factory=list)  # 重量序列
    source_inject_sequence: List[int] = field(default_factory=list)   # 注入序列
    sink_absorb_sequence: List[int] = field(default_factory=list)     # 吸收序列

    # 采样快照（每 sample_interval 步）
    state_snapshots: List[torch.Tensor] = field(default_factory=list)
    snapshot_steps: List[int] = field(default_factory=list)

    # 元数据
    metadata: Dict = field(default_factory=dict)

    def to_tensors(self) -> Dict[str, torch.Tensor]:
        """转换为张量字典"""
        return {
            'flip_sequence': torch.tensor(self.flip_sequence, dtype=torch.long),
            'hamming_weight': torch.tensor(self.hamming_weight_sequence, dtype=torch.long),
            'source_inject': torch.tensor(self.source_inject_sequence, dtype=torch.long),
            'sink_absorb': torch.tensor(self.sink_absorb_sequence, dtype=torch.long),
            'state_matrix': torch.stack(self.state_snapshots) if self.state_snapshots else torch.zeros(0),
        }


class TrajectoryRecorder:
    """轨迹记录器"""

    def __init__(self, N: int, sample_interval: int = 100):
        self.N = N
        self.sample_interval = sample_interval
        self.data = TrajectoryData(N=N, sample_interval=sample_interval)

    def record_step(self, step: int, flip_position: int,
                    hamming_weight: int,
                    source_injected: int = 0, sink_absorbed: int = 0,
                    axiom_loss: float = 0.0):
        """记录单步"""
        self.data.flip_sequence.append(flip_position)
        self.data.hamming_weight_sequence.append(hamming_weight)
        self.data.source_inject_sequence.append(source_injected)
        self.data.sink_absorb_sequence.append(sink_absorbed)

    def record_snapshot(self, step: int, state: torch.Tensor):
        """记录状态快照"""
        self.data.state_snapshots.append(state.clone().detach())
        self.data.snapshot_steps.append(step)

    def get_data(self) -> TrajectoryData:
        """获取完整轨迹数据"""
        self.data.total_steps = len(self.data.flip_sequence)
        return self.data

    def summary(self) -> str:
        """摘要"""
        d = self.data
        n_snapshots = len(d.state_snapshots)
        total_flips = len([f for f in d.flip_sequence if f >= 0])
        avg_weight = sum(d.hamming_weight_sequence) / max(1, len(d.hamming_weight_sequence))
        return (
            f"Trajectory: {d.total_steps} steps, {n_snapshots} snapshots, "
            f"{total_flips} flips, avg_w={avg_weight:.1f}"
        )
